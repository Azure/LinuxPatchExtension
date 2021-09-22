# Copyright 2020 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.7+

"""The is base package manager, which defines the package management relevant operations"""
import json
import os
from abc import ABCMeta, abstractmethod
from core.src.bootstrap.Constants import Constants
import time


class PackageManager(object):
    """Base class of package manager"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        self.env_layer = env_layer
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.status_handler = status_handler
        self.single_package_upgrade_cmd = ''
        self.single_package_upgrade_simulation_cmd = 'simulate-install'
        self.package_manager_settings = {}

        # Enabling caching for high performance retrieval (only for code explicitly requesting it)
        self.all_updates_cached = []
        self.all_update_versions_cached = []

        # auto OS updates
        self.image_default_patch_configuration_backup_path = os.path.join(execution_config.config_folder, Constants.IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH)

        # Constants
        self.STR_NOTHING_TO_DO = "Error: Nothing to do"
        self.STR_ONLY_UPGRADES = "Skipping <PACKAGE>, it is not installed and only upgrades are requested."
        self.STR_OBSOLETED = "Package <PACKAGE> is obsoleted"
        self.STR_REPLACED = "\nReplaced:\n"

    __metaclass__ = ABCMeta  # For Python 3.0+, it changes to class Abstract(metaclass=ABCMeta)

    @abstractmethod
    def refresh_repo(self):
        """Resynchronize the package index files from their sources."""
        pass

    # region Get Available Updates
    @abstractmethod
    def invoke_package_manager(self, command):
        pass

    def get_available_updates(self, package_filter):
        """Returns List of all installed packages with available updates."""
        class_packages, class_versions = self.get_updates_for_classification(package_filter)
        incl_packages, incl_versions = self.get_updates_for_inclusions(package_filter)

        # classification's package version will supersede any inclusion package version (for future reference: this is by design and not a bug)
        packages, package_versions = self.dedupe_update_packages(class_packages + incl_packages, class_versions + incl_versions)

        return packages, package_versions

    # region Classification-based (incl. All) update check
    def get_updates_for_classification(self, package_filter):
        """Get missing updates for classifications"""
        if package_filter.is_invalid_classification_combination():
            error_msg = "Invalid classification combination selection detected. Please edit the update deployment configuration, " \
                            "unselect + reselect the desired classifications and save."
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

        if package_filter.is_msft_critsec_classification_only():
            return self.get_security_updates()
        elif package_filter.is_msft_other_classification_only():
            return self.get_other_updates()
        elif package_filter.is_msft_all_classification_included():
            return self.get_all_updates()
        else:
            return [], []  # happens when nothing was selected, and inclusions are present

    @abstractmethod
    def get_all_updates(self, cached=False):
        """Same behavior as get_available_updates, but higher performance with no filters"""
        pass
        return [], []  # only here to suppress a static syntax validation problem

    @abstractmethod
    def get_security_updates(self):
        pass

    @abstractmethod
    def get_other_updates(self):
        pass
    # endregion

    def get_updates_for_inclusions(self, package_filter):
        """Get missing updates for inclusions"""
        self.composite_logger.log_debug("Checking for inclusions...")

        # Trivial empty list cases
        if not package_filter.is_inclusion_list_present():
            self.composite_logger.log_debug(" - No inclusion list was present.")
            return [], []
        if package_filter.is_msft_all_classification_included():  # remember that this function is inclusion-list aware if you suspect there's a bug here
            self.composite_logger.log_debug(" - Inclusion list was present, but all classifications were selected - inclusions are irrelevant and will be ignored.")
            return [], []

        # Get all available updates
        self.composite_logger.log_debug("Getting all available updates for filtering...")
        packages, package_versions = self.get_all_updates(True)  # if a cached version is available, that is fine here
        included_packages = []
        included_package_versions = []
        not_included_packages = []

        # Check for inclusions
        for index, package in enumerate(packages):
            if package_filter.check_for_inclusion(package, package_versions[index]):    # check for the latest version
                self.composite_logger.log_debug(" - Package satisfied inclusion list: " + str(package) + " (version=" + package_versions[index] + ")")
                included_packages.append(package)
                included_package_versions.append(package_versions[index])

            elif package_filter.check_for_inclusion(package):                           # check for all available versions
                available_versions = self.get_all_available_versions_of_package(package)
                matched = False
                for available_version in available_versions:
                    if not package_filter.check_for_inclusion(package, available_version):
                        continue
                    self.composite_logger.log_debug(" - Package satisfied inclusion list: " + str(package) + " (version=" + available_version + ", latest version=" + package_versions[index] + ")")
                    included_packages.append(package)
                    included_package_versions.append(available_version)
                    matched = True
                    break

                if not matched:
                    self.composite_logger.log_warning(" - Package [" + package + "] is available, but not the specific version requested. Available versions found: " + str(available_versions))
                    not_included_packages.append(package)

            else:                                                                       # no match
                self.composite_logger.log_debug(" - Package didn't satisfy inclusion list: " + str(package))
                not_included_packages.append(package)

        return included_packages, included_package_versions

    @staticmethod
    def dedupe_update_packages(packages, package_versions):
        """Remove duplicate packages and returns"""
        deduped_packages = []
        deduped_package_versions = []

        for index, package in enumerate(packages):
            if package in deduped_packages:
                continue  # Already included

            deduped_packages.append(package)
            deduped_package_versions.append(package_versions[index])

        return deduped_packages, deduped_package_versions
    # endregion

    # region Install Update
    def get_install_command(self, cmd, packages, package_versions):
        """ Composes the install command for one or more packages with versions"""
        composite_cmd = cmd
        for index, package in enumerate(packages):
            if index != 0:
                composite_cmd += ' '
            if package_versions[index] != Constants.DEFAULT_UNSPECIFIED_VALUE:
                composite_cmd += self.get_composite_package_identifier(package, package_versions[index])
            else:
                composite_cmd += ' ' + package

        return composite_cmd

    @abstractmethod
    def get_composite_package_identifier(self, package_name, package_version):
        pass
        return ""  # only here to suppress a static syntax validation problem

    @abstractmethod
    def install_updates_fail_safe(self, excluded_packages):
        pass

    def install_update_and_dependencies(self, package_and_dependencies, package_and_dependency_versions, simulate=False):
        """Install a single package along with its dependencies (explicitly)"""
        install_result = Constants.INSTALLED
        package_no_longer_required = False
        code_path = "| Install"
        start_time = time.time()

        if type(package_and_dependencies) is str:
            package_and_dependencies = [package_and_dependencies]
            package_and_dependency_versions = [package_and_dependency_versions]

        if simulate is False:
            cmd = self.single_package_upgrade_cmd
        else:
            cmd = self.single_package_upgrade_simulation_cmd
        exec_cmd = str(self.get_install_command(cmd, package_and_dependencies, package_and_dependency_versions))

        self.composite_logger.log_debug("UPDATING PACKAGE (WITH DEPENDENCIES) USING COMMAND: " + exec_cmd)
        code, out = self.env_layer.run_command_output(exec_cmd, False, False)
        package_size = self.get_package_size(out)
        self.composite_logger.log_debug("\n<PackageInstallOutput>\n" + out + "\n</PackageInstallOutput>")  # wrapping multi-line for readability

        # special case of package no longer being required (or maybe even present on the system)
        if code == 1 and self.get_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY) == Constants.YUM:
            self.composite_logger.log_debug(" - Detecting if package is no longer required (as return code is 1):")
            if self.STR_NOTHING_TO_DO in out:
                code_path += " > Nothing to do. (succeeded)"
                self.composite_logger.log_debug("    - Evidence of package no longer required detected.")
                package_no_longer_required = True
                code = 0
            else:
                code_path += " > Nothing to do. (possible failure, tbd)"
                self.composite_logger.log_debug("    - Evidence of package no longer required NOT detected.")

        if not package_no_longer_required:
            if not self.is_package_version_installed(package_and_dependencies[0], package_and_dependency_versions[0]):
                if code == 0 and self.STR_ONLY_UPGRADES.replace('<PACKAGE>', package_and_dependencies[0]) in out:
                    # It is premature to fail this package. In the *unlikely* case it never gets picked up, it'll remain NotStarted.
                    # The NotStarted status must not be written again in the calling function (it's not at the time of this writing).
                    code_path += " > Package has no prior version. (no operation; return 'not started')"
                    install_result = Constants.PENDING
                    self.composite_logger.log_warning(" |- Package " + package_and_dependencies[0] + " (" + package_and_dependency_versions[0] + ") needs to already have an older version installed in order to be upgraded. " +
                                                   "\n |- Another upgradeable package requiring it as a dependency can cause it to get installed later. No action may be required.\n")

                elif code == 0 and self.STR_OBSOLETED.replace('<PACKAGE>', self.get_composite_package_identifier(package_and_dependencies[0], package_and_dependency_versions[0])) in out:
                    # Package can be obsoleted by another package installed in the run (via dependencies)
                    code_path += " > Package obsoleted. (succeeded)"
                    install_result = Constants.INSTALLED    # close approximation to obsoleted
                    self.composite_logger.log_debug(" - Package was discovered to be obsoleted.")

                elif code == 0 and len(out.split(self.STR_REPLACED)) > 1 and package_and_dependencies[0] in out.split(self.STR_REPLACED)[1]:
                    code_path += " > Package replaced. (succeeded)"
                    install_result = Constants.INSTALLED    # close approximation to replaced
                    self.composite_logger.log_debug(" - Package was discovered to be replaced by another during its installation.")

                else:  # actual failure
                    install_result = Constants.FAILED
                    if code != 0:
                        code_path += " > Package NOT installed. (failed)"
                        self.composite_logger.log_error(" |- Package failed to install: " + package_and_dependencies[0] + " (" + package_and_dependency_versions[0] + "). " +
                                                     "\n |- Error code: " + str(code) + ". Command used: " + exec_cmd +
                                                     "\n |- Command output: " + out + "\n")
                    else:
                        code_path += " > Package NOT installed but return code: 0. (failed)"
                        self.composite_logger.log_error(" |- Package appears to have not been installed: " + package_and_dependencies[0] + " (" + package_and_dependency_versions[0] + "). " +
                                                     "\n |- Return code: 0. Command used: " + exec_cmd + "\n" +
                                                     "\n |- Command output: " + out + "\n")
            elif code != 0:
                code_path += " > Info, package installed, non-zero return. (succeeded)"
                self.composite_logger.log_warning(" - [Info] Desired package version was installed, but the package manager returned a non-zero return code: " + str(code) + ". Command used: " + exec_cmd + "\n")
            else:
                code_path += " > Info, Package installed, zero return. (succeeded)"

        if not simulate:
            if install_result == Constants.FAILED:
                error = self.telemetry_writer.write_package_info(package_and_dependencies[0], package_and_dependency_versions[0], package_size, round(time.time() - start_time, 2), install_result, code_path, exec_cmd, str(out))
            else:
                error = self.telemetry_writer.write_package_info(package_and_dependencies[0], package_and_dependency_versions[0], package_size, round(time.time() - start_time, 2), install_result, code_path, exec_cmd)

            if error is not None:
                self.composite_logger.log_debug('\nEXCEPTION writing package telemetry: ' + repr(error))

        return install_result
    # endregion

    # region Package Information
    @abstractmethod
    def get_all_available_versions_of_package(self, package_name):
        """ Returns a list of all the available version of a package """
        pass
        return []  # only here to suppress a static syntax validation problem

    @abstractmethod
    def is_package_version_installed(self, package_name, package_version):
        """ Returns true if the specific package version is installed """
        pass

    @abstractmethod
    def get_dependent_list(self, package_name):
        """Retrieve available updates. Expect an array being returned"""
        pass

    @abstractmethod
    def get_product_name(self, package_name):
        """Retrieve package name """
        pass

    @abstractmethod
    def get_package_size(self, output):
        """Retrieve package size from installation output string"""
        pass
    # endregion

    # region Package Manager Settings
    def get_package_manager_setting(self, setting_key, default_value='d5414abb-62f9-40e3-96e1-d579f85a79ba'):
        # type: (str, object) -> "" # type hinting to remove a warning
        """Gets any set package manager setting"""
        if setting_key in self.package_manager_settings:
            return self.package_manager_settings[setting_key]
        elif default_value != 'd5414abb-62f9-40e3-96e1-d579f85a79ba':  # this is the way it is because of a limitation of the packager script - the guid could have been Constants.DEFAULT_UNSPECIFIED_VALUE
            return default_value
        else:
            error_msg = "Setting key [" + setting_key + "] does not exist in package manager settings."
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

    def set_package_manager_setting(self, setting_key, setting_value=""):
        # type: (str, object) -> "" # type hinting to remove a warning
        """Sets package manager setting"""
        self.package_manager_settings[setting_key] = setting_value
    # endregion

    # region auto OS updates
    @abstractmethod
    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        pass

    @abstractmethod
    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enabled and logs the default settings the machine comes with """
        pass

    @abstractmethod
    def backup_image_default_patch_configuration_if_not_exists(self):
        """ Records the default system settings for auto OS updates within patch extension artifacts for future reference.
        We only log the default system settings a VM comes with, any subsequent updates will not be recorded"""
        pass

    def image_default_patch_configuration_backup_exists(self):
        """ Checks whether default auto OS update settings have been recorded earlier within patch extension artifacts """
        self.composite_logger.log_debug("Checking if extension contains a backup for default auto OS update configuration settings...")

        # backup does not exist
        if not os.path.exists(self.image_default_patch_configuration_backup_path) or not os.path.isfile(self.image_default_patch_configuration_backup_path):
            self.composite_logger.log_debug("Default system configuration settings for auto OS updates aren't recorded in the extension")
            return False

        # verify if the existing backup is valid
        try:
            image_default_patch_configuration_backup = json.loads(self.env_layer.file_system.read_with_retry(self.image_default_patch_configuration_backup_path))
            if self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup):
                self.composite_logger.log_debug("Since extension has a valid backup, no need to log the current settings again. "
                                                "[Default Auto OS update settings={0}] [File path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
                return True
            else:
                self.composite_logger.log_error("Since the backup is invalid, will add a new backup with the current auto OS update settings")
                return False
        except Exception as error:
            self.composite_logger.log_error("Unable to read backup for default auto OS update settings. [Exception={0}]".format(repr(error)))
            return False

    @abstractmethod
    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        pass

    @abstractmethod
    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value, patch_configuration_sub_setting_pattern_to_match):
        pass
    # endregion

    # region Handling known errors
    def try_mitigate_issues_if_any(self, command, code, out):
        """ Attempt to fix the errors occurred while executing a command. Repeat check until no issues found """
        pass

    def check_known_issues_and_attempt_fix(self, output):
        """ Checks if issue falls into known issues and attempts to mitigate """
        return True

    # endregion

    @abstractmethod
    def do_processes_require_restart(self):
        """Signals whether processes require a restart due to updates to files"""
        pass

