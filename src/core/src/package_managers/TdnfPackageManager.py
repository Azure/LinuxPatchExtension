# Copyright 2025 Microsoft Corporation
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

"""TdnfPackageManager for Mariner/Azure Linux"""
import json
import os
import re
from core.src.package_managers.PackageManager import PackageManager
from core.src.bootstrap.Constants import Constants


class TdnfPackageManager(PackageManager):
    """Implementation of Mariner package management operations"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(TdnfPackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)
        # Repo refresh
        # There is no command as this is a no op.
        # TODO: add -snapshottime to all commands

        # Support to get updates and their dependencies
        self.tdnf_check = 'sudo tdnf -q list updates'
        # self.tdnf_check_security_prerequisite = 'sudo tdnf -y install yum-plugin-security'
        self.tdnf_check_security = 'sudo tdnf -q --security list updates'
        # self.single_package_check_versions = 'sudo tdnf list available <PACKAGE-NAME> --showduplicates'
        # self.single_package_check_installed = 'sudo tdnf list installed <PACKAGE-NAME>'
        # self.single_package_upgrade_simulation_cmd = 'LANG=en_US.UTF8 sudo tdnf install --assumeno --skip-broken '
        #
        # # Install update
        # self.single_package_upgrade_cmd = 'sudo tdnf -y install --skip-broken '
        # self.all_but_excluded_upgrade_cmd = 'sudo tdnf -y update --exclude='
        #
        # Package manager exit code(s)
        self.tdnf_exitcode_no_applicable_packages = 0
        self.tdnf_exitcode_ok = 1
        self.tdnf_exitcode_updates_available = 100
        #
        # Support to check for processes requiring restart
        self.dnf_utils_prerequisite = 'sudo tdnf -y install dnf-utils'
        self.needs_restarting_with_flag = 'sudo LANG=en_US.UTF8 needs-restarting -r'
        # self.yum_ps_prerequisite = 'sudo yum -y install yum-plugin-ps'
        # self.yum_ps = 'sudo yum ps'

        # TODO: disabling automatic OS updates

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.TDNF)
        # self.STR_TOTAL_DOWNLOAD_SIZE = "Total download size: "
        #
        # self.package_install_expected_avg_time_in_seconds = 90  # As per telemetry data, the average time to install package is around 90 seconds for yum.

    def refresh_repo(self):
        pass  # Refresh the repo is no ops in TDNF

    # region Get Available Updates
    def invoke_package_manager_advanced(self, command, raise_on_exception=True):
        """Get missing updates using the command input"""
        self.composite_logger.log_verbose("[TDNF] Invoking package manager. [Command={0}]".format(str(command)))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code not in [self.tdnf_exitcode_ok, self.tdnf_exitcode_no_applicable_packages, self.tdnf_exitcode_updates_available]:
            self.composite_logger.log_warning('[ERROR] Customer environment error. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
            error_msg = "Customer environment error: Investigate and resolve unexpected return code ({0}) from package manager on command: {1}".format(str(code), command)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            if raise_on_exception:
                raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
            # more return codes should be added as appropriate
        else:  # verbose diagnostic log
            self.composite_logger.log_debug('[TDNF] Invoked package manager. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
        return out, code

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_verbose("[TDNF] Discovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug("[TDNF] Get all updates : [Cached={0}][PackagesCount={1}]]".format(str(cached), len(self.all_updates_cached)))
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        out = self.invoke_package_manager(self.tdnf_check)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)

        self.composite_logger.log_debug("[TDNF] Get all updates : [Cached={0}][PackagesCount={1}]]".format(str(False), len(self.all_updates_cached)))
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates"""
        self.composite_logger.log_verbose("[TDNF] Discovering 'security' packages...")

        out = self.invoke_package_manager(self.tdnf_check_security)
        security_packages, security_package_versions = self.extract_packages_and_versions(out)
        self.composite_logger.log_debug("[TDNF] Discovered 'security' packages. [Count={0}]".format(len(security_packages)))
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates"""
        self.composite_logger.log_verbose("[TDNF] Discovering 'other' packages...")
        other_packages = []
        other_package_versions = []

        all_packages, all_package_versions = self.get_all_updates(True)
        security_packages, security_package_versions = self.get_security_updates()

        for index, package in enumerate(all_packages):
            if package not in security_packages:
                other_packages.append(package)
                other_package_versions.append(all_package_versions[index])

        self.composite_logger.log_debug("[TDNF] Discovered 'other' packages. [Count={0}]".format(len(other_packages)))
        return other_packages, other_package_versions

    def set_max_patch_publish_date(self, max_patch_publish_date=str()):
        pass
        #TODO

    # endregion

    # region Output Parser(s)
    def extract_packages_and_versions(self, output):
        """Returns packages and versions from given output"""
        packages, versions = self.extract_packages_and_versions_including_duplicates(output)
        packages, versions = self.dedupe_update_packages(packages, versions)
        return packages, versions

    def extract_packages_and_versions_including_duplicates(self, output):
        """Returns packages and versions from given output"""
        self.composite_logger.log_verbose("[TDNF] Extracting package and version data...")
        packages = []
        versions = []
        package_extensions = Constants.SUPPORTED_PACKAGE_ARCH

        def is_package(chunk):
            # Using a list comprehension to determine if chunk is a package
            return len([p for p in package_extensions if p in chunk]) == 1

        lines = output.strip().split('\n')

        for line_index in range(0, len(lines)):
            # Do not install Obsoleting Packages. The obsoleting packages list comes towards end in the output.
            if lines[line_index].strip().startswith("Obsoleting Packages"):
                break

            line = re.split(r'\s+', lines[line_index].strip())
            next_line = []

            if line_index < len(lines) - 1:
                next_line = re.split(r'\s+', lines[line_index + 1].strip())

            # If we run into a length of 3, we'll accept it and continue
            if len(line) == 3 and is_package(line[0]):
                packages.append(self.get_product_name(line[0]))
                versions.append(line[1])
            # We will handle these two edge cases where the output is on
            # two different lines and treat them as one line
            elif len(line) == 1 and len(next_line) == 2 and is_package(line[0]):
                packages.append(self.get_product_name(line[0]))
                versions.append(next_line[0])
                line_index += 1
            elif len(line) == 2 and len(next_line) == 1 and is_package(line[0]):
                packages.append(self.get_product_name(line[0]))
                versions.append(line[1])
                line_index += 1
            else:
                self.composite_logger.log_verbose("[TDNF] > Inapplicable line (" + str(line_index) + "): " + lines[line_index])

        return packages, versions
    # endregion
    # endregion

    # region Install Updates
    # endregion

    # region Package Information
    def get_product_name(self, package_name):
        """Retrieve package name """
        return package_name
    # endregion

    # region Reboot Management
    def is_reboot_pending(self):
        """ Checks if there is a pending reboot on the machine. """
        try:
            pending_file_exists = os.path.isfile(self.REBOOT_PENDING_FILE_PATH)  # not intended for tdnf, but supporting as back-compat
            pending_processes_exist = self.do_processes_require_restart()
            self.composite_logger.log_debug("[TDNF] > Reboot required debug flags (tdnf): " + str(pending_file_exists) + ", " + str(pending_processes_exist) + ".")
            return pending_file_exists or pending_processes_exist
        except Exception as error:
            self.composite_logger.log_error('[TDNF] Error while checking for reboot pending (tdnf): ' + repr(error))
            return True  # defaults for safety

    def do_processes_require_restart(self):
        """Signals whether processes require a restart due to updates"""
        self.composite_logger.log_verbose("[TDNF] Checking if process requires reboot")
        # Checking using dnf-utils
        code, out = self.env_layer.run_command_output(self.dnf_utils_prerequisite, False, False)  # idempotent, doesn't install if already present
        self.composite_logger.log_verbose("[TDNF] Idempotent dnf-utils existence check. [Code={0}][Out={1}]".format(str(code), out))

        # Checking for restart for distros with -r flag
        code, out = self.env_layer.run_command_output(self.needs_restarting_with_flag, False, False)
        self.composite_logger.log_verbose("[TDNF] > Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))
        if out.find("Reboot is required") < 0:
            self.composite_logger.log_debug("[TDNF] > Reboot not detected to be required (L1).")
        else:
            self.composite_logger.log_debug("[TDNF] > Reboot is detected to be required (L1).")
            return True

        # TODO: check if Double-checking using yum ps equivalent should be used?
        return False

    # endregion

    # region To review and remove later
    def get_composite_package_identifier(self, package_name, package_version):
        pass

    def install_updates_fail_safe(self, excluded_packages):
        pass

    def install_security_updates_azgps_coordinated(self):
        pass

    def get_all_available_versions_of_package(self, package_name):
        """ Returns a list of all the available version of a package """
        pass

    def is_package_version_installed(self, package_name, package_version):
        """ Returns true if the specific package version is installed """
        pass

    def get_dependent_list(self, package_name):
        """Retrieve available updates. Expect an array being returned"""
        pass

    def get_package_size(self, output):
        """Retrieve package size from installation output string"""
        pass

    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        pass

    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enabled and logs the default settings the machine comes with """
        pass

    def backup_image_default_patch_configuration_if_not_exists(self):
        """ Records the default system settings for auto OS updates within patch extension artifacts for future reference.
        We only log the default system settings a VM comes with, any subsequent updates will not be recorded"""
        pass

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        pass

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value, patch_configuration_sub_setting_pattern_to_match):
        pass

    def add_arch_dependencies(self, package_manager, package, version, packages, package_versions, package_and_dependencies, package_and_dependency_versions):
        """
        Add the packages with same name as that of input parameter package but with different architectures from packages list to the list package_and_dependencies.
        Only required for yum. No-op for apt and zypper.

        Parameters:
        package_manager (PackageManager): Package manager used.
        package (string): Input package for which same package name but different architecture need to be added in the list package_and_dependencies.
        version (string): version of the package.
        packages (List of strings): List of all packages selected by user to install.
        package_versions (List of strings): Versions of packages in packages list.
        package_and_dependencies (List of strings): List of packages along with dependencies. This function adds packages with same name as input parameter package
                                                    but different architecture in this list.
        package_and_dependency_versions (List of strings): Versions of packages in package_and_dependencies.
        """
        pass

    def set_security_esm_package_status(self, operation, packages):
        pass

    def separate_out_esm_packages(self, packages, package_versions):
        pass

    def get_package_install_expected_avg_time_in_seconds(self):
        """Retrieves average time to install package in seconds."""
        pass
    # endregion


