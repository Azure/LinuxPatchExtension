# Copyright 2020 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.7+

"""ZypperPackageManager for SUSE"""
import json
import os
import re
import time
from core.src.package_managers.PackageManager import PackageManager
from core.src.bootstrap.Constants import Constants

# do not instantiate directly - these are exclusively for type hinting support
from core.src.bootstrap.EnvLayer import EnvLayer
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.src.local_loggers.CompositeLogger import CompositeLogger
from core.src.service_interfaces.TelemetryWriter import TelemetryWriter
from core.src.service_interfaces.StatusHandler import StatusHandler
from core.src.package_managers.PatchModeManager import PatchModeManager
from core.src.package_managers.SourcesManager import SourcesManager
from core.src.package_managers.HealthManager import HealthManager


class ZypperPackageManager(PackageManager):
    """Implementation of SUSE package management operations"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, patch_mode_manager, sources_manager, health_manager, package_manager_name):
        # type: (EnvLayer, ExecutionConfig, CompositeLogger, TelemetryWriter, StatusHandler, PatchModeManager, SourcesManager, HealthManager, str) -> None
        super(ZypperPackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler, patch_mode_manager, sources_manager, health_manager, package_manager_name)
        # Repo refresh
        self.repo_clean = 'sudo zypper clean -a'
        self.repo_refresh = 'sudo zypper refresh'
        self.repo_refresh_services = 'sudo zypper refresh --services'

        # Support to get updates and their dependencies
        self.zypper_check = 'sudo LANG=en_US.UTF8 zypper list-updates'
        self.zypper_check_security = 'sudo LANG=en_US.UTF8 zypper list-patches --category security'
        self.single_package_check_versions = 'LANG=en_US.UTF8 zypper search -s <PACKAGE-NAME>'
        self.single_package_upgrade_simulation_cmd = 'sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run '
        self.zypper_install_security_patches_simulate = 'sudo LANG=en_US.UTF8 zypper --non-interactive patch --category security --dry-run'

        # Install update
        self.single_package_upgrade_cmd = 'sudo zypper --non-interactive update '
        self.zypper_install_security_patches = 'sudo zypper --non-interactive patch --category security'

        # Package manager exit code(s)
        self.zypper_exitcode_ok = 0
        self.zypper_exitcode_zypp_lib_exit_err = 4
        self.zypper_exitcode_no_repos = 6
        self.zypper_exitcode_zypp_locked = 7
        self.zypper_exitcode_zypp_exit_err_commit = 8
        self.zypper_exitcode_reboot_required = 102
        self.zypper_exitcode_zypper_updated = 103
        self.zypper_exitcode_repos_skipped = 106
        self.zypper_success_exit_codes = [self.zypper_exitcode_ok, self.zypper_exitcode_zypper_updated, self.zypper_exitcode_reboot_required]
        self.zypper_retryable_exit_codes = [self.zypper_exitcode_zypp_locked, self.zypper_exitcode_zypp_lib_exit_err, self.zypper_exitcode_repos_skipped]

        # Additional output messages that corresponds with exit code 103
        self.zypper_out_zypper_updated_msg = 'Warning: One of the installed patches affects the package manager itself. Run this command once more to install any other needed patches.'

        # Support to check for processes requiring restart
        self.zypper_ps = "sudo zypper ps -s"

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.ZYPPER)
        self.zypper_get_process_tree_cmd = 'ps --forest -o pid,cmd -g $(ps -o sid= -p {})'
        self.package_manager_max_retries = 5
        self.zypp_lock_timeout_backup = None

    def refresh_repo(self):
        self.composite_logger.log("Refreshing local repo...")
        # self.invoke_package_manager(self.repo_clean)  # purges local metadata for rebuild - addresses a possible customer environment error
        try:
            self.invoke_package_manager(self.repo_refresh)
        except Exception as error:
            # Reboot if not already done
            if self.status_handler.get_installation_reboot_status() == Constants.RebootStatus.COMPLETED:
                self.composite_logger.log_warning("[ZPM] Unable to refresh repo (retries exhausted after reboot).")
                raise
            else:
                self.composite_logger.log_warning("[ZPM] Setting force_reboot flag to True.")
                self.force_reboot = True

    def __refresh_repo_services(self):
        """ Similar to refresh_repo, but refreshes services in case no repos are defined. """
        self.composite_logger.log("Refreshing local repo services...")
        try:
            self.invoke_package_manager(self.repo_refresh_services)
        except Exception as error:
            # Reboot if not already done
            if self.status_handler.get_installation_reboot_status() == Constants.RebootStatus.COMPLETED:
                self.composite_logger.log_warning("[ZPM] Unable to refresh repo services (retries exhausted after reboot).")
                raise
            else:
                self.composite_logger.log_warning("[ZPM] Setting force_reboot flag to True after refreshing repo services.")
                self.force_reboot = True

    # region Get Available Updates
    def invoke_package_manager_advanced(self, command, raise_on_exception=True):
        """Get missing updates using the command input"""
        self.composite_logger.log_debug('[ZPM] Invoking package manager. [Command={0}]'.format(command))
        repo_refresh_services_attempted = False

        for i in range(1, self.package_manager_max_retries + 1):
            self.set_lock_timeout_and_backup_original()
            code, out = self.env_layer.run_command_output(command, False, False)
            self.restore_original_lock_timeout()

            if code not in self.zypper_success_exit_codes:  # more known return codes should be added as appropriate
                # Refresh repo services if no repos are defined
                if code == self.zypper_exitcode_no_repos and command != self.repo_refresh_services and not repo_refresh_services_attempted:
                    self.composite_logger.log_warning("Warning: no repos defined on command: {0}".format(str(command)))
                    self.__refresh_repo_services()
                    repo_refresh_services_attempted = True
                    continue

                if code == self.zypper_exitcode_zypp_exit_err_commit:
                    # Run command again with --replacefiles to fix file conflicts
                    self.composite_logger.log_warning("Warning: package conflict detected on command: {0}".format(str(command)))
                    modified_command = self.modify_upgrade_or_patch_command_to_replacefiles(command)
                    if modified_command is not None:
                        command = modified_command
                        self.composite_logger.log_debug("Retrying with modified command to replace files: {0}".format(str(command)))
                        continue

                # Retryable error code, so check number of retries and wait then retry if applicable; otherwise, raise error after max retries
                if i < self.package_manager_max_retries and code in self.zypper_retryable_exit_codes:
                    self.composite_logger.log_verbose("[ZPM] Retryable Package Manager ERROR. [Command={0}][Code={1}][Output={2}][RetryCount={0}]".format(command, str(code), str(out), str(i)))
                    time.sleep(pow(2, i + 2))
                    continue
                else:
                    self.composite_logger.log_error("[ZPM] Package Manager ERROR. [Command={0}][Code={1}][Output={2}]".format(command, str(code), str(out)))
                    self.status_handler.add_error_to_status_and_log_error(message="Unexpected return code from package manager. [Code={0}][Command={1}]".format(str(code), command),
                                                                          raise_exception=bool(code not in self.zypper_retryable_exit_codes and raise_on_exception), error_code=Constants.PatchOperationErrorCodes.CL_PACKAGE_MANAGER_FAILURE)
                    self.log_process_tree_if_exists(out)
            else:
                self.composite_logger.log_verbose("[ZPM] Package Manager SUCCESS. [Command={0}][Code={1}][Output={2}]".format(command, str(code), str(out)))

            self.__handle_zypper_updated_or_reboot_exit_codes(command, out, code)

            return out, code

    def __handle_zypper_updated_or_reboot_exit_codes(self, command, out, code):
        """ Handles exit code 102 or 103 when returned from invoking package manager.
            Does not repeat installation or reboot if it is a dry run. """
        if "--dry-run" in command:
            self.composite_logger.log_debug(" - Exit code {0} detected from command \"{1}\", but it was a dry run. Continuing execution without performing additional actions.".format(str(code), command))
            return

        if code == self.zypper_exitcode_zypper_updated or self.zypper_out_zypper_updated_msg in out:
            self.composite_logger.log_debug(" - One of the installed patches affects the package manager itself. Patch installation run will be repeated.")
            self.set_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, True)
        elif code == self.zypper_exitcode_reboot_required:
            self.composite_logger.log_warning(" - Machine requires reboot after patch installation. Setting force_reboot flag to True.")
            self.force_reboot = True

    def modify_upgrade_or_patch_command_to_replacefiles(self, command):
        """ Modifies a command to invoke_package_manager for update or patch to include a --replacefiles flag. 
            If it is a dry run or already has the flag, it returns None. Otherwise, returns the new command. """
        if "--dry-run" in command or "--replacefiles" in command:
            return None

        if self.single_package_upgrade_cmd in command:
            return command.replace(self.single_package_upgrade_cmd, self.single_package_upgrade_cmd + '--replacefiles ')
        elif self.zypper_install_security_patches in command:
            return command.replace(self.zypper_install_security_patches, self.zypper_install_security_patches + ' --replacefiles')

    def log_process_tree_if_exists(self, out):
        """Logs the process tree based on locking PID in output, if there is a process tree to be found"""
        process_tree = self.get_process_tree_from_pid_in_output(out)
        if process_tree is not None:
            self.composite_logger.log_verbose("[ZPM] Process tree for the PID in output: \n{0}".format(str(process_tree)))

    def set_lock_timeout_and_backup_original(self):
        """Saves the env var ZYPP_LOCK_TIMEOUT and sets it to 5"""
        self.zypp_lock_timeout_backup = self.env_layer.get_env_var('ZYPP_LOCK_TIMEOUT')
        self.composite_logger.log_verbose("[ZPM] Original value of ZYPP_LOCK_TIMEOUT env var: {0}".format(str(self.zypp_lock_timeout_backup)))
        self.env_layer.set_env_var('ZYPP_LOCK_TIMEOUT', 5)

    def restore_original_lock_timeout(self):
        """Restores the original value of the env var ZYPP_LOCK_TIMEOUT, if any was saved"""
        if self.zypp_lock_timeout_backup is None:
            self.composite_logger.log_debug("[ZPM] Attempted to restore original lock timeout when none was saved.")
        self.env_layer.set_env_var('ZYPP_LOCK_TIMEOUT', self.zypp_lock_timeout_backup)
        self.zypp_lock_timeout_backup = None

    def get_process_tree_from_pid_in_output(self, message):
        """ Fetches pid from the error message by searching for the text 'pid' and returns the process tree with all details.
            Example:
                input: message (string): Output from package manager: | System management is locked by the application with pid 7914 (/usr/bin/zypper).
                returns (string):
                      PID CMD
                     7736 /bin/bash
                     7912  \_ python3 package_test.py
                     7913  |   \_ sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run bind-utils
                     7914  |       \_ zypper --non-interactive update --dry-run bind-utils
                     7982  |           \_ /usr/bin/python3 /usr/lib/zypp/plugins/urlresolver/susecloud
                     7984  |               \_ /usr/bin/python3 /usr/bin/azuremetadata --api latest --subscriptionId --billingTag --attestedData --signature
                     7986  \_ python3 package_test.py
                     8298      \_ sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run grub2-i386-pc """

        """ First find pid xxxxx within output string.
            Example: 'Output from package manager: | System management is locked by the application with pid 7914 (/usr/bin/zypper).'
            pid_substr_search will contain: ' pid 7914' """
        regex = re.compile(' pid \d+')
        pid_substr_search = regex.search(message)
        if pid_substr_search is None:
            return None

        """ Now extract just pid text from pid_substr_search.
            Example (pid_substr_search): ' pid 7914'   
            pid_search will contain: '7914' """
        regex = re.compile('\d+')
        pid_search = regex.search(pid_substr_search.group())
        if pid_search is None:
            return None

        pid = pid_search.group()

        # Gives a process tree so the calling process name(s) can be identified
        # TODO: consider revisiting in the future to reduce the result to this pid only instead of entire tree
        get_process_tree_cmd = self.zypper_get_process_tree_cmd.format(str(pid))
        code, out = self.env_layer.run_command_output(get_process_tree_cmd, False, False)

        # Failed to get process tree
        if code != 0 or len(out) == 0:
            return None

        # The command returned a process tree that did not contain this process
        # This can happen when the process doesn't exist because a process tree is always returned
        if out.find(pid + " ") == -1:
            return None

        return out

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_verbose("[ZPM] Discovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_verbose(" - Returning cached package data.")
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        out = self.invoke_package_manager(self.zypper_check)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)
        self.composite_logger.log_debug("[ZPM] Discovered " + str(len(self.all_updates_cached)) + " package entries.")
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates"""
        self.composite_logger.log_verbose("[ZPM] Discovering 'security' packages...")
        security_packages = []
        security_package_versions = []

        # Get all security packages
        out = self.invoke_package_manager(self.zypper_install_security_patches_simulate)
        packages_from_patch_data = self.extract_packages_from_patch_data(out)

        # Correlate and enrich with versions from all package data
        all_packages, all_package_versions = self.get_all_updates(True)

        for index, package in enumerate(all_packages):
            if package in packages_from_patch_data:
                security_packages.append(package)
                security_package_versions.append(all_package_versions[index])
                self.composite_logger.log_verbose(" - " + str(package) + " [" + str(all_package_versions[index]) + "]")

        self.composite_logger.log_debug("[ZPM] Discovered " + str(len(security_packages)) + " 'security' package entries.\n")
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates"""
        self.composite_logger.log_verbose("[ZPM] Discovering 'other' packages...")
        other_packages = []
        other_package_versions = []

        # Get all security packages
        out = self.invoke_package_manager(self.zypper_install_security_patches_simulate)
        packages_from_patch_data = self.extract_packages_from_patch_data(out)

        # SPECIAL CONDITION IF ZYPPER UPDATE IS DETECTED - UNAVOIDABLE SECURITY UPDATE(S) WILL BE INSTALLED AND THE RUN REPEATED FOR 'OTHER".
        if self.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, True):
            self.status_handler.add_error_to_status_and_log_warning("Important: Zypper-related security updates are necessary to continue - those will be installed first. Temporarily skipping 'other' package entry discovery due to Zypper-related security updates.")
            return self.get_security_updates()  # TO DO: in some cases, some misc security updates may sneak in - filter this (to do item)
            # also for above: also note that simply force updating only zypper does not solve the issue - tried

        # Subtract from all package data
        all_packages, all_package_versions = self.get_all_updates(True)

        for index, package in enumerate(all_packages):
            if package not in packages_from_patch_data:
                other_packages.append(package)
                other_package_versions.append(all_package_versions[index])
                self.composite_logger.log_verbose(" - " + str(package) + " [" + str(all_package_versions[index]) + "]")

        self.composite_logger.log_debug("[ZPM] Discovered " + str(len(other_packages)) + " 'other' package entries.")
        return other_packages, other_package_versions
    # endregion

    # region Output Parser(s)
    def extract_packages_and_versions(self, output):
        """Returns packages and versions from given output"""

        # Sample output for the cmd 'zypper list-updates' is :
        # Loading repository data...
        # Reading installed packages...
        # S | Repository         | Name               | Current Version | Available Version | Arch
        # --+--------------------+--------------------+-----------------+-------------------+-------#
        # v | SLES12-SP2-Updates | kernel-default     | 4.4.38-93.1     | 4.4.49-92.11.1    | x86_64
        # v | SLES12-SP2-Updates | libgoa-1_0-0       | 3.20.4-7.2      | 3.20.5-9.6        | x86_64

        self.composite_logger.log_debug("\nExtracting package and version data...")
        packages = []
        versions = []
        debug_log = str()

        lines = output.strip().split('\n')
        for line in lines:
            line_split = line.split(' | ')
            if len(line_split) == 6 and line_split[1].strip() != 'Repository':
                package = line_split[2].strip()
                packages.append(package)
                version = line_split[4].strip()
                versions.append(version)
                debug_log += "[A] {0}, [P={1},V={2}]\n".format(str(line), package, version)
            else:
                debug_log += "[N] {0}\n".format(str(line))

        self.composite_logger.log_debug("[ZPM] Debug log on extracting packages and versions: {0}".format(debug_log))
        return packages, versions

    def extract_packages_from_patch_data(self, output):
        """Returns packages (sometimes with version information embedded) from patch data"""
        self.composite_logger.log_verbose("Extracting package entries from security patch data...")
        packages = []
        debug_log = str()
        parser_seeing_packages_flag = False

        lines = output.strip().split('\n')
        for line in lines:
            if not parser_seeing_packages_flag:
                if 'package is going to be installed' in line or 'package is going to be upgraded' in line or \
                        'packages are going to be installed:' in line or 'packages are going to be upgraded:' in line:
                    debug_log += "[S] {0}\n".format(str(line))  # start marker line
                    parser_seeing_packages_flag = True          # start -- next line contains information we need
                else:
                    debug_log += "[N] {0}\n".format(str(line))
                continue

            if not line or line.isspace():
                debug_log += "[E] {0}\n".format(str(line))  # end marker line
                parser_seeing_packages_flag = False
                continue  # End -- We're past a package information block

            line_parts = line.strip().split(' ')
            debug_log += "[A] {0}\n".format(str(line))  # applicable package list line
            for line_part in line_parts:
                packages.append(line_part)
                debug_log += "[Package] {0}\n".format(str(line_part))

        self.composite_logger.log_debug("[ZPM] Debug log on extracting packages from security patch data: {0}".format(debug_log))
        self.composite_logger.log_verbose("[ZPM] Extracted " + str(len(packages)) + " prospective package entries from security patch data.")
        return packages
    # endregion
    # endregion

    # region Install Update
    def get_composite_package_identifier(self, package, package_version):
        return package + '=' + package_version

    def install_updates_fail_safe(self, excluded_packages):
        return
    # endregion

    # region Package Information
    def get_all_available_versions_of_package(self, package_name):
        """ Returns a list of all the available versions of a package that are not already installed """
        return self.get_all_available_versions_of_package_ex(package_name, include_installed=False, include_available=True)

    def is_package_version_installed(self, package_name, package_version):
        """ Returns true if the specific package version is installed """
        self.composite_logger.log_debug("\nCHECKING PACKAGE INSTALL STATUS FOR: " + str(package_name) + "(" + str(package_version) + ")")
        installed_package_versions = self.get_all_available_versions_of_package_ex(package_name, include_installed=True, include_available=False)
        for version in installed_package_versions:
            if version == package_version:
                self.composite_logger.log_debug(" - Installed version match found.")
                return True
            else:
                self.composite_logger.log_debug(" - Did not match: " + str(version))

        return False

    def get_all_available_versions_of_package_ex(self, package_name, include_installed=False, include_available=True):
        """ Returns a list of all the available versions of a package """
        # Sample output format
        # S | Name                    | Type       | Version      | Arch   | Repository
        # --+-------------------------+------------+--------------+--------+-------------------
        # v | bash                    | package    | 4.3-83.5.2   | x86_64 | SLES12-SP2-Updates

        package_versions = []

        self.composite_logger.log_debug("\nGetting all available versions of package '" + package_name + "' [Installed=" + str(include_installed) + ", Available=" + str(include_available) + "]...")
        cmd = self.single_package_check_versions.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        lines = output.strip().split('\n')

        packages_list_flag = False
        for line in lines:
            if not packages_list_flag:  # keep going until the packages list starts
                if not all(word in line for word in ["S", "Name", "Type", "Version", "Arch", "Repository"]):
                    self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                    continue
                else:
                    self.composite_logger.log_debug(" - Package list started: " + str(line))
                    packages_list_flag = True
                    continue

            package_details = line.split(' |')
            if len(package_details) != 6:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue
            else:
                self.composite_logger.log_debug(" - Applicable line: " + str(line))
                details_status = str(package_details[0].strip())
                details_name = str(package_details[1].strip())
                details_type = str(package_details[2].strip())
                details_version = str(package_details[3].strip())

                if details_name != package_name:
                    self.composite_logger.log_debug("    - Excluding as package name doesn't match exactly: " + details_name)
                    continue
                if details_type == "srcpackage":
                    self.composite_logger.log_debug("    - Excluding as package is of type 'srcpackage'.")
                    continue
                if (details_status == "i" or details_status == "i+") and not include_installed:  # exclude installed as (include_installed not selected)
                    self.composite_logger.log_debug("    - Excluding as package version is installed: " + details_version)
                    continue
                if (details_status != "i" and details_status != "i+") and not include_available:  # exclude available as (include_available not selected)
                    self.composite_logger.log_debug("    - Excluding as package version is available: " + details_version)
                    continue

                package_versions.append(details_version)

        return package_versions

    def extract_dependencies(self, output, packages):
        # Sample output for the cmd
        # 'sudo  LANG=en_US.UTF8 zypper --non-interactive update --dry-run man' is :
        #
        # Refreshing service 'SMT-http_smt-azure_susecloud_net'.
        # Refreshing service 'cloud_update'.
        # Loading repository data...
        # Reading installed packages...
        # Resolving package dependencies...
        #
        # The following 16 NEW packages are going to be installed:
        #   cups-filters-ghostscript ghostscript ghostscript-fonts-other\
        # ghostscript-fonts-std  ghostscript-x11 groff-full libICE6 libjasper1 libjbig2 libjpeg8
        #  libnetpbm11 libSM6 libtiff5 libXt6 netpbm psutils
        #
        # The following package is going to be upgraded:
        #   man

        # 1 package to upgrade, 16 new.
        # Overall download size: 23.7 MiB. Already cached: 0 B. \
        # After the operation, additional 85.1 MiB will be used.
        # Continue? [y/n/? shows all options] (y): y
        dependencies = []
        lines = output.strip().split('\n')

        for line in lines:
            if line.find(" going to be ") < 0:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue

            updates_line = lines[lines.index(line) + 1]
            dependent_package_names = re.split(r'\s+', updates_line)
            for dependent_package_name in dependent_package_names:
                if len(dependent_package_name) != 0 and dependent_package_name not in packages:
                    self.composite_logger.log_debug(" - Dependency detected: " + dependent_package_name)
                    dependencies.append(dependent_package_name)

        return dependencies

    def get_dependent_list(self, packages):
        package_names = ""
        for index, package in enumerate(packages):
            if index != 0:
                package_names += ' '
            package_names += package

        self.composite_logger.log_debug("\nRESOLVING DEPENDENCIES USING COMMAND:: " + str(self.single_package_upgrade_simulation_cmd + package_names))

        output = self.invoke_package_manager(self.single_package_upgrade_simulation_cmd + package_names)
        dependencies = self.extract_dependencies(output, packages)
        self.composite_logger.log_debug(str(len(dependencies)) + " dependent packages were found for packages '" + str(packages) + "'.")
        return dependencies

    def get_product_name(self, package_name):
        """Retrieve product name """
        return package_name

    def get_package_size(self, output):
        """Retrieve package size from installation output string"""
        # Sample output line:
        # Overall download size: 195.0 KiB. Already cached: 0 B. After the operation, additional 281.0 B will be used.
        try:
            if "Nothing to do." in output:
                return Constants.UNKNOWN_PACKAGE_SIZE
            search_txt = r'Overall download size:[ ](.*?)\.[ ]Already'
            search = re.compile(search_txt, re.M | re.S)
            pkg_list = search.findall(str(output))
            if len(pkg_list) == 0 or pkg_list[0] == "":
                return Constants.UNKNOWN_PACKAGE_SIZE
            return pkg_list[0]
        except Exception as error:
            self.composite_logger.log_debug(" - Could not get package size from output: " + repr(error))
            return Constants.UNKNOWN_PACKAGE_SIZE
    # endregion

    # region Reboot Management
    def is_reboot_pending(self):
        """ Checks if there is a pending reboot on the machine. """
        try:
            pending_file_exists = os.path.isfile(self.REBOOT_PENDING_FILE_PATH)  # not intended for zypper, but supporting as back-compat
            pending_processes_exist = self.do_processes_require_restart()
            self.composite_logger.log_debug("[ZPM] Reboot required debug flags (zypper): " + str(pending_file_exists) + ", " + str(pending_processes_exist) + ".")
            return pending_file_exists or pending_processes_exist
        except Exception as error:
            self.composite_logger.log_error('[ZPM] Error while checking for reboot pending (zypper): ' + repr(error))
            return True  # defaults for safety

    def do_processes_require_restart(self):
        """Signals whether processes require a restart due to updates"""
        output = self.invoke_package_manager(self.zypper_ps)
        lines = output.strip().split('\n')
        debug_log = str()

        process_list_flag = False
        process_count = 0
        process_list_verbose = ""
        for line in lines:
            if not process_list_flag:  # keep going until the process list starts
                if not all(word in line for word in ["PID", "PPID", "UID", "User", "Command", "Service"]):
                    debug_log += "[N] {0}\n".format(str(line))      # not applicable
                    continue
                else:
                    debug_log += "[PLS] {0}\n".format(str(line))    # process list started
                    process_list_flag = True
                    continue

            process_details = line.split(' |')
            if len(process_details) < 6:
                debug_log += "[N] {0}\n".format(str(line))  # not applicable
                continue
            else:
                debug_log += "[A] {0}\n".format(str(line))  # applicable
                process_count += 1
                process_list_verbose += process_details[4].strip() + " (" + process_details[0].strip() + "), "  # process name and id

        self.composite_logger.log_debug("[ZPM] Debug log on processes requiring restart: {0}]".format(debug_log))
        self.composite_logger.log("[ZPM] Processes requiring restart. [Count={0}][ProcessList={1}]".format(str(process_count), process_list_verbose))
        return process_count != 0  # True if there were any
    # endregion Reboot Management

    def add_arch_dependencies(self, package_manager, package, packages, package_versions, package_and_dependencies, package_and_dependency_versions):
        """
        Add the packages with same name as that of input parameter package but with different architectures from packages list to the list package_and_dependencies.
        Only required for yum. No-op for apt and zypper.
        """
        return

    def set_security_esm_package_status(self, operation, packages):
        """
        Set the security-ESM classification for the esm packages. Only needed for apt. No-op for yum and zypper.
        """
        pass

    def separate_out_esm_packages(self, packages, package_versions):
        """
        Filter out packages from the list where the version matches the UA_ESM_REQUIRED string.
        Only needed for apt. No-op for yum and zypper
        """
        esm_packages = []
        esm_package_versions = []
        esm_packages_found = False

        return packages, package_versions, esm_packages, esm_package_versions, esm_packages_found

