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

"""ZypperPackageManager for SUSE"""
import json
import os
import re
import time
from core.src.package_managers.PackageManager import PackageManager
from core.src.bootstrap.Constants import Constants


class ZypperPackageManager(PackageManager):
    """Implementation of SUSE package management operations"""

    class ZypperAutoOSUpdateServices(Constants.EnumBackport):
        YAST2_ONLINE_UPDATE_CONFIGURATION = "yast2-online-update-configuration"

    class YastOnlineUpdateConfigurationConstants(Constants.EnumBackport):
        OS_PATCH_CONFIGURATION_SETTINGS_FILE_PATH = '/etc/sysconfig/automatic_online_update'
        APPLY_UPDATES_IDENTIFIER_TEXT = 'AOU_ENABLE_CRONJOB'
        AUTO_UPDATE_CONFIG_PATTERN_MATCH_TEXT = '="(true|false)"'
        INSTALLATION_STATE_IDENTIFIER_TEXT = "installation_state"

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(ZypperPackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)
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
        self.zypper_retriable_exit_codes = [self.zypper_exitcode_zypp_locked, self.zypper_exitcode_zypp_lib_exit_err, self.zypper_exitcode_repos_skipped]

        # Additional output messages that corresponds with exit code 103
        self.zypper_out_zypper_updated_msg = 'Warning: One of the installed patches affects the package manager itself. Run this command once more to install any other needed patches.'

        # Support to check for processes requiring restart
        self.zypper_ps = "sudo zypper ps -s"

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.ZYPPER)
        self.zypper_get_process_tree_cmd = 'ps --forest -o pid,cmd -g $(ps -o sid= -p {})'
        self.package_manager_max_retries = 5
        self.zypp_lock_timeout_backup = None

        # auto OS updates
        self.current_auto_os_update_service = None
        self.os_patch_configuration_settings_file_path = ''
        self.auto_update_config_pattern_match_text = ""
        self.apply_updates_identifier_text = ""
        self.installation_state_identifier_text = ""

        # # commands for YaST2 online update configuration
        # self.__init_constants_for_yast2_online_update_configuration()

    def refresh_repo(self):
        self.composite_logger.log("Refreshing local repo...")
        # self.invoke_package_manager(self.repo_clean)  # purges local metadata for rebuild - addresses a possible customer environment error
        try:
            self.invoke_package_manager(self.repo_refresh)
        except Exception as error:
            # Reboot if not already done
            if self.status_handler.get_installation_reboot_status() == Constants.RebootStatus.COMPLETED:
                self.composite_logger.log_warning("Unable to refresh repo (retries exhausted after reboot).")
                raise
            else:
                self.composite_logger.log_warning("Setting force_reboot flag to True.")
                self.force_reboot = True

    def __refresh_repo_services(self):
        """ Similar to refresh_repo, but refreshes services in case no repos are defined. """
        self.composite_logger.log("Refreshing local repo services...")
        try:
            self.invoke_package_manager(self.repo_refresh_services)
        except Exception as error:
            # Reboot if not already done
            if self.status_handler.get_installation_reboot_status() == Constants.RebootStatus.COMPLETED:
                self.composite_logger.log_warning("Unable to refresh repo services (retries exhausted after reboot).")
                raise
            else:
                self.composite_logger.log_warning("Setting force_reboot flag to True after refreshing repo services.")
                self.force_reboot = True

    # region Get Available Updates
    def invoke_package_manager_advanced(self, command, raise_on_exception=True):
        """Get missing updates using the command input"""
        self.composite_logger.log_debug('\nInvoking package manager using: ' + command)
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

                self.log_errors_on_invoke(command, out, code)
                error_msg = 'Unexpected return code (' + str(code) + ') from package manager on command: ' + command
                self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)

                # Not a retriable error code, so raise an exception
                if code not in self.zypper_retriable_exit_codes and raise_on_exception:
                    raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

                # Retriable error code, so check number of retries and wait then retry if applicable; otherwise, raise error after max retries
                if i < self.package_manager_max_retries:
                    self.composite_logger.log_warning("Exception on package manager invoke. [Exception={0}] [RetryCount={1}]".format(error_msg, str(i)))
                    time.sleep(pow(2, i + 2))
                    continue
                else:
                    error_msg = "Unable to invoke package manager (retries exhausted) [{0}] [RetryCount={1}]".format(error_msg, str(i))
                    self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
                    if raise_on_exception:
                        raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
            else:  # verbose diagnostic log
                self.log_success_on_invoke(code, out)

            self.__handle_zypper_updated_or_reboot_exit_codes(command, out, code)

            return out, code

    def __handle_zypper_updated_or_reboot_exit_codes(self, command, out, code):
        """ Handles exit code 102 or 103 when returned from invoking package manager.
            Does not repeat installation or reboot if it is a dry run. """
        if "--dry-run" in command:
            self.composite_logger.log_debug(
                " - Exit code {0} detected from command \"{1}\", but it was a dry run. Continuing execution without performing additional actions.".format(
                str(code), command))
            return

        if code == self.zypper_exitcode_zypper_updated or self.zypper_out_zypper_updated_msg in out:
            self.composite_logger.log_debug(
                " - One of the installed patches affects the package manager itself. Patch installation run will be repeated.")
            self.set_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, True)
        elif code == self.zypper_exitcode_reboot_required:
            self.composite_logger.log_warning(
                " - Machine requires reboot after patch installation. Setting force_reboot flag to True.")
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

    def log_errors_on_invoke(self, command, out, code):
        """Logs verbose error messages if there is an error on invoke_package_manager"""
        self.composite_logger.log('[ERROR] Package manager was invoked using: ' + command)
        self.composite_logger.log_warning(" - Return code from package manager: " + str(code))
        self.composite_logger.log_warning(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
        self.log_process_tree_if_exists(out)
        self.telemetry_writer.write_execution_error(command, code, out)

    def log_success_on_invoke(self, code, out):
        """Logs verbose success messages on invoke_package_manager"""
        self.composite_logger.log_verbose("\n\n==[SUCCESS]===============================================================")
        self.composite_logger.log_debug(" - Return code from package manager: " + str(code))
        self.composite_logger.log_debug(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
        self.composite_logger.log_verbose("==========================================================================\n\n")

    def log_process_tree_if_exists(self, out):
        """Logs the process tree based on locking PID in output, if there is a process tree to be found"""
        process_tree = self.get_process_tree_from_pid_in_output(out)
        if process_tree is not None:
            self.composite_logger.log_warning(" - Process tree for the pid in output: \n{}".format(str(process_tree)))

    def set_lock_timeout_and_backup_original(self):
        """Saves the env var ZYPP_LOCK_TIMEOUT and sets it to 5"""
        self.zypp_lock_timeout_backup = self.env_layer.get_env_var('ZYPP_LOCK_TIMEOUT')
        self.composite_logger.log_debug("Original value of ZYPP_LOCK_TIMEOUT env var: {0}".format(str(self.zypp_lock_timeout_backup)))
        self.env_layer.set_env_var('ZYPP_LOCK_TIMEOUT', 5)

    def restore_original_lock_timeout(self):
        """Restores the original value of the env var ZYPP_LOCK_TIMEOUT, if any was saved"""
        if self.zypp_lock_timeout_backup is None:
            self.composite_logger.log_debug("Attempted to restore original lock timeout when none was saved")

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
        self.composite_logger.log_debug("\nDiscovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug(" - Returning cached package data.")
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        out = self.invoke_package_manager(self.zypper_check)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)
        self.composite_logger.log_debug("Discovered " + str(len(self.all_updates_cached)) + " package entries.")
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates"""
        self.composite_logger.log_debug("\nDiscovering 'security' packages...")
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
                self.composite_logger.log_debug(" - " + str(package) + " [" + str(all_package_versions[index]) + "]")

        self.composite_logger.log_debug("Discovered " + str(len(security_packages)) + " 'security' package entries.\n")
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates"""
        self.composite_logger.log_debug("\nDiscovering 'other' packages...")
        other_packages = []
        other_package_versions = []

        # Get all security packages
        out = self.invoke_package_manager(self.zypper_install_security_patches_simulate)
        packages_from_patch_data = self.extract_packages_from_patch_data(out)

        # SPECIAL CONDITION IF ZYPPER UPDATE IS DETECTED - UNAVOIDABLE SECURITY UPDATE(S) WILL BE INSTALLED AND THE RUN REPEATED FOR 'OTHER".
        if self.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, True):
            self.composite_logger.log_warning("Important: Zypper-related security updates are necessary to continue - those will be installed first.")
            self.composite_logger.log_warning("Temporarily skipping 'other' package entry discovery due to Zypper-related security updates.\n")
            return self.get_security_updates()  # TO DO: in some cases, some misc security updates may sneak in - filter this (to do item)
            # also for above: also note that simply force updating only zypper does not solve the issue - tried

        # Subtract from all package data
        all_packages, all_package_versions = self.get_all_updates(True)

        for index, package in enumerate(all_packages):
            if package not in packages_from_patch_data:
                other_packages.append(package)
                other_package_versions.append(all_package_versions[index])
                self.composite_logger.log_debug(" - " + str(package) + " [" + str(all_package_versions[index]) + "]")

        self.composite_logger.log_debug("Discovered " + str(len(other_packages)) + " 'other' package entries.\n")
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

        lines = output.strip().split('\n')
        for line in lines:
            line_split = line.split(' | ')
            if len(line_split) == 6 and line_split[1].strip() != 'Repository':
                package = line_split[2].strip()
                packages.append(package)
                version = line_split[4].strip()
                versions.append(version)
                self.composite_logger.log_debug(" - Applicable line: " + line + ". Package: " + package + ". Version: " + version + ".")
            else:
                self.composite_logger.log_debug(" - Inapplicable line: " + line)

        return packages, versions

    def extract_packages_from_patch_data(self, output):
        """Returns packages (sometimes with version information embedded) from patch data"""
        self.composite_logger.log_debug("\nExtracting package entries from security patch data...")
        packages = []
        parser_seeing_packages_flag = False

        lines = output.strip().split('\n')
        for line in lines:
            if not parser_seeing_packages_flag:
                if 'package is going to be installed' in line or 'package is going to be upgraded' in line or \
                        'packages are going to be installed:' in line or 'packages are going to be upgraded:' in line:
                    self.composite_logger.log_debug(" - Start marker line: " + line)
                    parser_seeing_packages_flag = True  # Start -- Next line contains information we need
                else:
                    self.composite_logger.log_debug(" - Inapplicable line: " + line)
                continue

            if not line or line.isspace():
                self.composite_logger.log_debug(" - End marker line: " + line)
                parser_seeing_packages_flag = False
                continue  # End -- We're past a package information block

            line_parts = line.strip().split(' ')
            self.composite_logger.log_debug(" - Package list line: " + line)
            for line_part in line_parts:
                packages.append(line_part)
                self.composite_logger.log_debug("    - Package: " + line_part)

        self.composite_logger.log_debug("\nExtracted " + str(len(packages)) + " prospective package entries from security patch data.\n")
        return packages
    # endregion
    # endregion

    # region Install Update
    def get_composite_package_identifier(self, package, package_version):
        return package + '=' + package_version

    def install_updates_fail_safe(self, excluded_packages):
        return

    def accept_eula_for_patches(self):
        """ Accepts eula for patches based on the config provided by customers """
        pass
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

    # region auto OS updates
    # def __init_constants_for_yast2_online_update_configuration(self):
    #     self.yast2_online_update_configuration_os_patch_configuration_settings_file_path = '/etc/sysconfig/automatic_online_update'
    #     self.yast2_online_update_configuration_apply_updates_identifier_text = 'AOU_ENABLE_CRONJOB'
    #     self.yast2_online_update_configuration_auto_update_config_pattern_match_text = '="(true|false)"'
    #     self.yast2_online_update_configuration_installation_state_identifier_text = "installation_state"

    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        self.composite_logger.log("Fetching the current automatic OS patch state on the machine...")

        current_auto_os_patch_state_for_yast2_online_update_configuration = self.__get_current_auto_os_patch_state_for_yast2_online_update_configuration()
        self.composite_logger.log("OS patch state per auto OS update service: [yast2-online-update-configuration={0}]".format(str(current_auto_os_patch_state_for_yast2_online_update_configuration)))

        current_auto_os_patch_state = current_auto_os_patch_state_for_yast2_online_update_configuration
        self.composite_logger.log_debug("Overall Auto OS Patch State based on all auto OS update service states [OverallAutoOSPatchState={0}]".format(str(current_auto_os_patch_state)))
        return current_auto_os_patch_state

    def __get_current_auto_os_patch_state_for_yast2_online_update_configuration(self):
        """ Gets current auto OS update patch state for yast2-online-update-configuration """
        self.composite_logger.log_debug("Fetching current automatic OS patch state in yast2-online-update-configuration.")
        self.__init_auto_update_for_yast_online_update_configuration()
        is_service_installed, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

        apply_updates = self.__get_extension_standard_value_for_apply_updates(apply_updates_value)

        # OS patch state is considered to be disabled: a) if it was successfully disabled or b) if the service is not installed
        if not is_service_installed or apply_updates == Constants.AutomaticOSPatchStates.DISABLED:
            return Constants.AutomaticOSPatchStates.DISABLED

        return apply_updates

    @staticmethod
    def __get_extension_standard_value_for_apply_updates(apply_updates_value):
        if apply_updates_value.lower() == 'true':
            return Constants.AutomaticOSPatchStates.ENABLED
        elif apply_updates_value.lower() == 'false':
            return Constants.AutomaticOSPatchStates.DISABLED
        else:
            return Constants.AutomaticOSPatchStates.UNKNOWN

    def __init_auto_update_for_yast_online_update_configuration(self):
        """ Initializes all generic auto OS update variables with the config values for yum cron service """
        self.os_patch_configuration_settings_file_path = self.YastOnlineUpdateConfigurationConstants.OS_PATCH_CONFIGURATION_SETTINGS_FILE_PATH
        self.apply_updates_identifier_text = self.YastOnlineUpdateConfigurationConstants.APPLY_UPDATES_IDENTIFIER_TEXT
        self.auto_update_config_pattern_match_text = self.YastOnlineUpdateConfigurationConstants.AUTO_UPDATE_CONFIG_PATTERN_MATCH_TEXT
        self.installation_state_identifier_text = self.YastOnlineUpdateConfigurationConstants.INSTALLATION_STATE_IDENTIFIER_TEXT
        self.current_auto_os_update_service = self.ZypperAutoOSUpdateServices.YAST2_ONLINE_UPDATE_CONFIGURATION

    def __get_current_auto_os_updates_setting_on_machine(self):
        """ Gets all the update settings related to auto OS updates currently set on the machine """
        try:
            apply_updates_value = ""
            is_service_installed = False

            # get install state
            if not os.path.exists(self.os_patch_configuration_settings_file_path):
                return is_service_installed, apply_updates_value

            is_service_installed = True
            self.composite_logger.log_debug("Checking if auto updates are currently enabled...")
            image_default_patch_configuration = self.env_layer.file_system.read_with_retry(self.os_patch_configuration_settings_file_path, raise_if_not_found=False)
            if image_default_patch_configuration is not None:
                settings = image_default_patch_configuration.strip().split('\n')
                for setting in settings:
                    match = re.search(self.apply_updates_identifier_text + self.auto_update_config_pattern_match_text, str(setting))
                    if match is not None:
                        apply_updates_value = match.group(1)

            if apply_updates_value == "":
                self.composite_logger.log_debug("Machine did not have any value set for [Setting={0}]".format(str(self.apply_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("Current value set for [{0}={1}]".format(str(self.apply_updates_identifier_text), str(apply_updates_value)))

            return is_service_installed, apply_updates_value

        except Exception as error:
            raise Exception("Error occurred in fetching current auto OS update settings from the machine. [Exception={0}]".format(repr(error)))

    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enable_on_reboot and logs the default settings the machine comes with """
        try:
            self.composite_logger.log("Disabling auto OS updates in all identified services...")
            self.disable_auto_os_update_for_yast_online_update_configuration()
            self.composite_logger.log_debug("Completed attempt to disable auto OS updates")

        except Exception as error:
            self.composite_logger.log_error("Could not disable auto OS updates. [Error={0}]".format(repr(error)))
            raise

    def disable_auto_os_update_for_yast_online_update_configuration(self):
        """ Disables auto OS updates, using yast online, and logs the default settings the machine comes with """
        self.composite_logger.log("Disabling auto OS updates using yast online update configuration")
        self.__init_auto_update_for_yast_online_update_configuration()

        self.backup_image_default_patch_configuration_if_not_exists()
        # check if file exists, if not do nothing
        if not os.path.exists(self.os_patch_configuration_settings_file_path):
            self.composite_logger.log_debug("Cannot disable auto updates using yast2-online-update-configuration because the configuration file does not exist, indicating the service is not installed")
            return

        self.composite_logger.log_debug("Preemptively disabling auto OS updates using yum-cron")
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "false", self.auto_update_config_pattern_match_text)

        self.composite_logger.log("Successfully disabled auto OS updates using yast2-online-update-configuration")

    def backup_image_default_patch_configuration_if_not_exists(self):
        """ Records the default system settings for auto OS updates within patch extension artifacts for future reference.
        We only log the default system settings a VM comes with, any subsequent updates will not be recorded"""
        """ JSON format for backup file:
                            {
                                "yast2-online-update-configuration": {
                                    "apply_updates": "true/false/empty string"
                                    "install_state": true/false
                                }
                            } """
        try:
            self.composite_logger.log_debug("Ensuring there is a backup of the default patch state for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
            image_default_patch_configuration_backup = {}

            # read existing backup since it also contains backup from other update services. We need to preserve any existing data within the backup file
            if self.image_default_patch_configuration_backup_exists():
                try:
                    image_default_patch_configuration_backup = json.loads(self.env_layer.file_system.read_with_retry(self.image_default_patch_configuration_backup_path))
                except Exception as error:
                    self.composite_logger.log_error("Unable to read backup for default patch state. Will attempt to re-write. [Exception={0}]".format(repr(error)))

            # verify if existing backup is valid if not, write to backup
            is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)
            if is_backup_valid:
                self.composite_logger.log_debug("Since extension has a valid backup, no need to log the current settings again. [Default Auto OS update settings={0}] [File path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
            else:
                self.composite_logger.log_debug("Since the backup is invalid, will add a new backup with the current auto OS update settings")
                self.composite_logger.log_debug("Fetching current auto OS update settings for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
                is_service_installed, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

                backup_image_default_patch_configuration_json_to_add = {
                    self.current_auto_os_update_service: {
                        self.apply_updates_identifier_text: apply_updates_value,
                        self.installation_state_identifier_text: is_service_installed
                    }
                }

                image_default_patch_configuration_backup.update(backup_image_default_patch_configuration_json_to_add)

                self.composite_logger.log_debug("Logging default system configuration settings for auto OS updates. [Settings={0}] [Log file path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
                self.env_layer.file_system.write_with_retry(self.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(image_default_patch_configuration_backup)), mode='w+')
        except Exception as error:
            error_message = "Exception during fetching and logging default auto update settings on the machine. [Exception={0}]".format(repr(error))
            self.composite_logger.log_error(error_message)
            self.status_handler.add_error_to_status(error_message, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        """ Verifies if default auto update configurations, for a service under consideration, are saved in backup """

        # NOTE: Adding a separate function to check backup for multiple auto OS update services, if more are added in future.
        return self.is_backup_valid_for_yast_online_update_configuration(image_default_patch_configuration_backup)

    def is_backup_valid_for_yast_online_update_configuration(self, image_default_patch_configuration_backup):
        if self.ZypperAutoOSUpdateServices.YAST2_ONLINE_UPDATE_CONFIGURATION in image_default_patch_configuration_backup \
                and self.apply_updates_identifier_text in image_default_patch_configuration_backup[self.ZypperAutoOSUpdateServices.YAST2_ONLINE_UPDATE_CONFIGURATION]:
            self.composite_logger.log_debug("Extension has a valid backup for default yum-cron configuration settings")
            return True
        else:
            self.composite_logger.log_debug("Extension does not have a valid backup for default yum-cron configuration settings")
            return False

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value="false", config_pattern_match_text=""):
        """ Updates (or adds if it doesn't exist) the given patch_configuration_sub_setting with the given value in os_patch_configuration_settings_file """
        try:
            self.composite_logger.log_debug("Updating system configuration settings for auto OS updates. [Patch Configuration Sub Setting={0}] [Value={1}]".format(str(patch_configuration_sub_setting), value))
            os_patch_configuration_settings = self.env_layer.file_system.read_with_retry(self.os_patch_configuration_settings_file_path)
            patch_configuration_sub_setting_to_update = patch_configuration_sub_setting + '="' + value + '"'
            patch_configuration_sub_setting_found_in_file = False
            updated_patch_configuration_sub_setting = ""
            settings = os_patch_configuration_settings.strip().split('\n')

            # update value of existing setting
            for i in range(len(settings)):
                match = re.search(patch_configuration_sub_setting + config_pattern_match_text, settings[i])
                if match is not None:
                    settings[i] = patch_configuration_sub_setting_to_update
                    patch_configuration_sub_setting_found_in_file = True
                updated_patch_configuration_sub_setting += settings[i] + "\n"

            # add setting to configuration file, since it doesn't exist
            if not patch_configuration_sub_setting_found_in_file:
                updated_patch_configuration_sub_setting += patch_configuration_sub_setting_to_update + "\n"

            self.env_layer.file_system.write_with_retry(self.os_patch_configuration_settings_file_path, '{0}'.format(updated_patch_configuration_sub_setting.lstrip()), mode='w+')
        except Exception as error:
            error_msg = "Error occurred while updating system configuration settings for auto OS updates. [Patch Configuration={0}] [Error={1}]".format(str(patch_configuration_sub_setting), repr(error))
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise
    # endregion

    # region Reboot Management
    def is_reboot_pending(self):
        """ Checks if there is a pending reboot on the machine. """
        try:
            pending_file_exists = os.path.isfile(self.REBOOT_PENDING_FILE_PATH)  # not intended for zypper, but supporting as back-compat
            pending_processes_exist = self.do_processes_require_restart()
            self.composite_logger.log_debug(" - Reboot required debug flags (zypper): " + str(pending_file_exists) + ", " + str(pending_processes_exist) + ".")
            return pending_file_exists or pending_processes_exist
        except Exception as error:
            self.composite_logger.log_error('Error while checking for reboot pending (zypper): ' + repr(error))
            return True  # defaults for safety

    def do_processes_require_restart(self):
        """Signals whether processes require a restart due to updates"""
        output = self.invoke_package_manager(self.zypper_ps)
        lines = output.strip().split('\n')

        process_list_flag = False
        process_count = 0
        process_list_verbose = ""
        for line in lines:
            if not process_list_flag:  # keep going until the process list starts
                if not all(word in line for word in ["PID", "PPID", "UID", "User", "Command", "Service"]):
                    self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                    continue
                else:
                    self.composite_logger.log_debug(" - Process list started: " + str(line))
                    process_list_flag = True
                    continue

            process_details = line.split(' |')
            if len(process_details) < 6:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue
            else:
                self.composite_logger.log_debug(" - Applicable line: " + str(line))
                process_count += 1
                process_list_verbose += process_details[4].strip() + " (" + process_details[0].strip() + "), "  # process name and id

        self.composite_logger.log(" - Processes requiring restart (" + str(process_count) + "): [" + process_list_verbose + "<eol>]")
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

