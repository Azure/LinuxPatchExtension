# Copyright 2026 Microsoft Corporation
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

"""Dnf5PackageManager for Azure Linux 4 or above"""
import json
import re

from core.src.core_logic.VersionComparator import VersionComparator
from core.src.bootstrap.Constants import Constants
from core.src.package_managers.PackageManager import PackageManager


class Dnf5PackageManager(PackageManager):
    """Implementation of DNF5 management operations"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(Dnf5PackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)
        # Repo refresh
        self.cmd_clean_cache = "sudo dnf5 -q clean expire-cache"
        self.cmd_repo_refresh = self.cmd_get_all_updates = "sudo dnf5 -q check-update"

        #  Get updates and dependencies.
        self.single_package_check_versions = 'sudo dnf5 list --available <PACKAGE-NAME> '
        self.single_package_check_installed = 'sudo dnf5 list --installed <PACKAGE-NAME> '

        self.single_package_upgrade_simulation_cmd = "sudo dnf5 install --assumeno --skip-broken "

        # Install update
        self.single_package_upgrade_cmd = 'sudo dnf5 -y upgrade '
        # Support to check if reboot is required
        # dnf-utils not required (needs-restarting is built into dnf5)
        self.needs_restarting_with_flag = 'sudo LANG=en_US.UTF8 dnf5 needs-restarting -r'

        # DNF5 exit codes
        self.dnf_exitcode_ok = [0, 100]
        # DNF5 valid exit codes for simulation commands
        self.dnf5_simulation_valid_exit_codes = [0, 1]
        self.dnf5_dependency_failure_text = ["Skipping packages with broken dependencies", "Nothing to do."]
        self.dnf5_dependency_success_text = "Installing dependencies:"
        self.dnf5_dependency_exit_text = "Transaction Summary"
        self.dnf5_not_installed_exit_code = 1
        self.dnf5_not_installed_text = "No matching packages to list"
        self.dnf5_list_installed_command_patterns = "list --installed"

        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.DNF5)

        # auto OS updates
        self.current_auto_os_update_service = None
        self.os_patch_default_configuration_settings_file_path = ''
        self.os_patch_override_configuration_settings_file_path = ''
        self.auto_update_service_enabled = False
        self.auto_update_config_pattern_match_text = ""
        self.download_updates_identifier_text = ""
        self.apply_updates_identifier_text = ""
        self.enable_on_reboot_identifier_text = ""
        self.enable_on_reboot_check_cmd = ''
        self.enable_on_reboot_cmd = ''
        self.installation_state_identifier_text = ""
        self.install_check_cmd = ""
        self.apply_updates_enabled = "Enabled"
        self.apply_updates_disabled = "Disabled"
        self.apply_updates_unknown = "Unknown"

        # commands for DNF Automatic updates service
        self.__init_constants_for_dnf5_automatic()

        self.STR_TOTAL_DOWNLOAD_SIZE = "Total download size: "
        self.package_install_expected_avg_time_in_seconds = 90
        self.version_comparator = VersionComparator()

    def refresh_repo(self):
        self.composite_logger.log("[DNF5] Refreshing local repo...")
        self.invoke_package_manager(self.cmd_clean_cache)
        self.invoke_package_manager(self.cmd_repo_refresh)

    # region Get Available Updates
    def invoke_package_manager_advanced(self, command, raise_on_exception=True):
        self.composite_logger.log_verbose("[DNF5] Invoking package manager. [Command={0}]".format(str(command)))
        code, out = self.env_layer.run_command_output(command, False, False)
        is_valid_not_installed = (self.dnf5_list_installed_command_patterns in command and code == self.dnf5_not_installed_exit_code and self.dnf5_not_installed_text in (out or ""))

        if code in self.dnf_exitcode_ok or is_valid_not_installed:
            self.composite_logger.log_debug('[DNF5] Invoked package manager. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
        else:
            self.composite_logger.log_warning('[ERROR] Customer environment error. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
            error_msg = "Customer environment error: Investigate and resolve unexpected return code ({0}) from package manager on command: {1}".format(str(code), command)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            if raise_on_exception:
                raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

        return out, code

    # region Output Parser(s)
    def extract_packages_and_versions(self, output):
        """Returns packages and versions from given output"""
        #Sample Output :rubygem-json.x86_64   2.13.2-2.azl4~20260501   azurelinux-base
        packages, versions = self.extract_packages_and_versions_including_duplicates(output)
        packages, versions = self.dedupe_update_packages_to_get_latest_versions(packages, versions)
        return packages, versions

    def extract_packages_and_versions_including_duplicates(self, output):
        """Returns packages and versions from given output"""
        # DNF check-update returns 3-column format: package.arch version repo
        # Sample output : rubygem-json.x86_64    2.13.2-2.azl4~20260501      azurelinux-base
        self.composite_logger.log_verbose("[DNF5] Extracting package and version data...")
        packages, versions = [], []
        lines = output.strip().split('\n')
        for line_index in range(0, len(lines)):
            line = lines[line_index].strip()
            # Do not install Obsoleting Packages. The obsoleting packages list comes towards end in the output.
            if line.startswith("Obsoleting"):
                break

            filtered_line = re.split(r'\s+', lines[line_index].strip())
            if len(filtered_line) == 3 and self.__is_package(filtered_line[0]):
                packages.append(self.get_product_name(filtered_line[0]))
                versions.append(filtered_line[1])
            else:
                self.composite_logger.log_verbose("[DNF5] > Inapplicable line ({0}): {1}".format(line_index, lines[line_index]))

        return packages, versions

    def dedupe_update_packages_to_get_latest_versions(self, packages, package_versions):
        """Remove duplicate packages and returns the latest/highest version of each package"""
        deduped_packages = []
        deduped_package_versions = []

        for index, package in enumerate(packages):
            if package in deduped_packages:
                deduped_package_version = deduped_package_versions[deduped_packages.index(package)]
                duplicate_package_version = package_versions[index]
                # use custom comparator output 0 (equal), -1 (deduped package version is the lower one), +1 (deduped package version is the greater one)
                is_deduped_package_latest = self.version_comparator.compare_versions(deduped_package_version, duplicate_package_version)
                if is_deduped_package_latest < 0:
                    deduped_package_versions[deduped_packages.index(package)] = duplicate_package_version
                continue

            deduped_packages.append(package)
            deduped_package_versions.append(package_versions[index])

        return deduped_packages, deduped_package_versions

    @staticmethod
    def __is_package(chunk):
        """Using a list comprehension to determine if chunk is a package"""
        return any(chunk.endswith(ext) for ext in Constants.SUPPORTED_PACKAGE_ARCH)
    # endregion

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_verbose("[DNF5] Discovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug("[DNF5] Get all updates : [Cached={0}][PackagesCount={1}]".format(str(cached), len(self.all_updates_cached)))
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        out = self.invoke_package_manager(self.cmd_get_all_updates)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)
        self.composite_logger.log_debug("[DNF5] Get all updates : [Cached={0}][PackagesCount={1}]".format(str(False), len(self.all_updates_cached)))
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates. NOTE: Classification based categorization of patches is not available in DNF5 as of now"""
        self.composite_logger.log_verbose("[DNF5] Discovering all packages as 'security' packages, since DNF5 does not support package classification...")
        security_packages, security_package_versions = self.get_all_updates(cached=False)
        self.composite_logger.log_debug("[DNF5] Discovered 'security' packages. [Count={0}]".format(len(security_packages)))
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates."""
        self.composite_logger.log_verbose("[DNF5] Discovering 'other' packages...")
        return [], []

    def set_max_patch_publish_date(self, max_patch_publish_date=str()):
        pass
    # endregion

    # region Install Update
    def get_composite_package_identifier(self, package, package_version):
        """Creates a version+architecture-specific package identifier for install commands
        Parameters:
        - package_name (string): Name of the package (may include architecture)
        - package_version (string): Version of the package
        Returns:
        - String: Composite package identifier (e.g., "package-1.0.0.x86_64")
        """
        package_without_arch, arch = self.get_product_name_and_arch(package)
        package_identifier = package_without_arch + '-' + str(package_version)
        if arch is not None:
            package_identifier += arch
        return package_identifier

    def install_updates_fail_safe(self, excluded_packages):
        return

    def install_security_updates_azgps_coordinated(self):
        """This is not applicable for dnf5 yet. DNF5 will not have this method implemented """
        pass

    def try_meet_azgps_coordinated_requirements(self):
        """This is not applicable for dnf5 yet. DNF5 will not have this method implemented"""
        pass
    # endregion

    def get_product_name_and_arch(self, package_name):
        architectures = Constants.SUPPORTED_PACKAGE_ARCH
        for arch in architectures:
            if package_name.endswith(arch):
                return package_name[:-len(arch)], arch
        return package_name, None

    # region Package Information
    def get_all_available_versions_of_package(self, package_name):
        """Returns a list of all the available versions of a package"""
        # Sample output format
        # rubygem-json.x86_64    2.13.2-2.azl4~20260501      azurelinux-base
        # rubygem-json.x86_64    2.14.0-1.azl4~20260501      azurelinux-base
        cmd = self.single_package_check_versions.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)
        return package_versions

    def is_package_version_installed(self, package_name, package_version):
        """Returns true if the specific package version is installed"""
        # Sample output format
        # rubygem-json.x86_64    2.13.2-2.azl4~20260501      @System
        self.composite_logger.log_verbose("[DNF5] Checking package install status. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
        cmd = self.single_package_check_installed.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)

        for index, package in enumerate(packages):
            if package == package_name and (package_versions[index] == package_version):
                self.composite_logger.log_debug("[DNF5] > Installed version match found. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
                return True
            else:
                self.composite_logger.log_verbose("[DNF5] > Did not match: " + package + " (" + package_versions[index] + ")")

        # If no matching package name and version are found in the package manager output, the requested version is not installed (it may have been replaced, upgraded, or removed)
        self.composite_logger.log_debug("[DNF5] > Installed version match NOT found. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
        return False

    def get_dependent_list(self, packages):
        """Returns dependent list for the list of packages"""
        # Gets the dependent list from packages.Refer dnf5_output_expected_format.txt for examples of output formats.
        package_names = " ".join(packages)
        cmd = self.single_package_upgrade_simulation_cmd + package_names
        # Dependency simulation using dnf5 install --assumeno --skip-broken has non-standard exit code behavior. A valid simulation run may return exit code 1 (e.g., "Operation aborted by the user"),
        # while dependency resolution failures may still return exit code 0 with output indicating skipped packages (e.g., "Skipping packages with broken dependencies" and "Nothing to do.").
        # calling the runcommand directly to get the output as well as code to determine failure/success cases
        code, output = self.env_layer.run_command_output(cmd, False, False)
        self.composite_logger.log_verbose("[DNF5] Dependency simulation. [Command={0}][Code={1}]".format(cmd, str(code)))
        if code not in self.dnf5_simulation_valid_exit_codes:
            self.composite_logger.log_error("[DNF5] Unexpected failure. [Command={0}][Code={1}][Output={2}]".format(cmd, str(code), output))
            error_msg = "DNF5 dependency simulation failed. Investigate and resolve unexpected return code({0}) from package manager on command: {1} ".format(str(code), cmd)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

        dependencies = self.extract_dependencies(output, packages)
        self.composite_logger.log_verbose("[DNF5] Resolved dependencies. [Command={0}][Packages={1}][DependencyCount={2}]".format(str(cmd), str(packages), len(dependencies)))
        return dependencies

    def extract_dependencies(self, output, packages):
        # Extracts dependent packages from output. Refer dnf5_output_expected_format.txt for examples of output formats.
        dependencies = []

        # Handle non-blocking dependency failure / nothing-to-do cases
        if all(text in output for text in self.dnf5_dependency_failure_text):
            self.composite_logger.log_warning("[DNF5] Packages skipped due to broken dependencies (non-blocking)")
            return dependencies

        package_arch_to_look_for = ["x86_64", "noarch", "i686", "aarch64"]

        lines = output.strip().splitlines()
        in_dependency_section = False

        for line_index in range(0, len(lines)):
            line_str = lines[line_index].strip()

            # Detect start of dependency section
            if line_str.startswith(self.dnf5_dependency_success_text):
                in_dependency_section = True

            #  Detect exit of dependency section
            if in_dependency_section and line_str.startswith(self.dnf5_dependency_exit_text):
                self.composite_logger.log_verbose("[DNF5] Exiting dependency section. Remaining output lines are skipped.")
                break

            line = re.split(r'\s+', line_str)
            dependent_package_name = ""

            if self.is_valid_update(line, package_arch_to_look_for):
                dependent_package_name = self.get_product_name_with_arch(line, package_arch_to_look_for)
            else:
                self.composite_logger.log_verbose("[DNF5] > Inapplicable line: " + str(line))
                continue

            #  Remove input packages (support both pkg and pkg.arch)
            if len(dependent_package_name) != 0 and dependent_package_name not in packages and dependent_package_name not in dependencies:
                self.composite_logger.log_verbose("[DNF5] > Dependency detected: " + dependent_package_name)
                dependencies.append(dependent_package_name)

        return dependencies

    def add_arch_dependencies(self, package_manager, package, version, packages, package_versions, package_and_dependencies, package_and_dependency_versions):
        # Not needed since it already supports multi-architecture. Refer dnf5_output_expected_format.txt for examples of output formats.
        pass

    def is_valid_update(self, package_details_in_output, package_arch_to_look_for):
        # Verifies whether the line under consideration (i.e. package_details_in_output) contains relevant package details.
        # package_details_in_output will be of the following format if it is valid
        #   Sample package details in DNF:
        #   python3-libs                       x86_64                    3.12.3-5.azl3                      azurelinux-official-base   36.05M                      10.52M
        return len(package_details_in_output) == 6 and self.is_arch_in_package_details(package_details_in_output[1], package_arch_to_look_for)

    @staticmethod
    def is_arch_in_package_details(package_detail, package_arch_to_look_for):
        return len([p for p in package_arch_to_look_for if p in package_detail]) == 1

    def get_product_name(self, package_name):
        """Retrieve package name"""
        return package_name

    def get_product_name_with_arch(self, package_detail, package_arch_to_look_for):
        """Returns package name in format: name.arch
        Example:
            ["oniguruma", "x86_64", ...] -> "oniguruma.x86_64"""
        if package_detail[1] in package_arch_to_look_for:
            return package_detail[0] + "." + package_detail[1]
        return ""

    def get_package_size(self, output):
        """Retrieves package size from installation output string"""
         # Sample Output line:
         # Total download size : 10M
        if "Nothing to do" not in output:
            lines = output.strip().split('\n')
            for line in lines:
                if line.find(self.STR_TOTAL_DOWNLOAD_SIZE) >= 0:
                    return line.replace(self.STR_TOTAL_DOWNLOAD_SIZE, "")
        return Constants.UNKNOWN_PACKAGE_SIZE
    # endregion

    # region auto OS updates
    def __init_constants_for_dnf5_automatic(self):
        self.dnf5_automatic_configuration_service = 'systemctl cat dnf5-automatic.service'
        self.dnf5_automatic_install_check_cmd = 'rpm -qa | grep dnf5-plugin-automatic'
        self.dnf5_automatic_enable_on_reboot_check_cmd = 'systemctl is-enabled dnf5-automatic.timer'
        self.dnf5_automatic_disable_on_reboot_cmd = 'systemctl disable --now dnf5-automatic.timer'
        self.dnf5_automatic_enable_on_reboot_cmd = 'systemctl enable --now dnf5-automatic.timer'
        self.dnf5_automatic_default_configuration_file_path = '/usr/share/dnf5/dnf5-plugins/automatic.conf'
        self.dnf5_automatic_override_configuration_file_path = '/etc/dnf/automatic.conf'
        self.dnf5_automatic_config_pattern_match_text = ' = (no|yes)'
        self.dnf5_automatic_download_updates_identifier_text = "download_updates"
        self.dnf5_automatic_apply_updates_identifier_text = "apply_updates"
        self.dnf5_automatic_enable_on_reboot_identifier_text = "enable_on_reboot"
        self.dnf5_automatic_installation_state_identifier_text = "installation_state"
        self.dnf5_auto_os_update_service = "dnf5-automatic"
        self.dnf5_default_auto_os_config_backup_key = "default-dnf5-automatic"
        self.dnf5_override_auto_os_config_backup_key = "override-dnf5-automatic"
        self.dnf5_automatic_remove_override_configuration_file_cmd = 'rm -f /etc/dnf/automatic.conf'

    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        self.composite_logger.log("[DNF5] Fetching the current automatic OS patch state on the machine...")
        current_auto_os_patch_state_for_dnf5_automatic = self.__get_current_auto_os_patch_state_for_dnf5_automatic()
        self.composite_logger.log("[DNF5] OS patch state per auto OS update service: [dnf5-automatic={0}]".format(str(current_auto_os_patch_state_for_dnf5_automatic)))

        if current_auto_os_patch_state_for_dnf5_automatic == Constants.AutomaticOSPatchStates.ENABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.ENABLED
        elif current_auto_os_patch_state_for_dnf5_automatic == Constants.AutomaticOSPatchStates.DISABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.DISABLED
        else:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.UNKNOWN

        self.composite_logger.log_debug("[DNF5] Overall Auto OS Patch State based on all auto OS update service states [OverallAutoOSPatchState={0}]".format(str(current_auto_os_patch_state)))
        return current_auto_os_patch_state

    def __get_current_auto_os_patch_state_for_dnf5_automatic(self):
        """Gets current auto OS update patch state for dnf5-automatic"""
        self.composite_logger.log_debug("[DNF5] Fetching current automatic OS patch state in dnf5-automatic service.")
        self.__init_auto_update_for_dnf5_automatic()
        is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

        apply_updates = self.__get_extension_standard_value_for_apply_updates(apply_updates_value)

        if apply_updates == self.apply_updates_enabled or enable_on_reboot_value:
            return Constants.AutomaticOSPatchStates.ENABLED
        # OS patch state is considered to be disabled: a) if it was successfully disabled or b) if the service is not installed
        elif not is_service_installed or (apply_updates == self.apply_updates_disabled and not enable_on_reboot_value):
            return Constants.AutomaticOSPatchStates.DISABLED
        else:
            return Constants.AutomaticOSPatchStates.UNKNOWN

    def __init_auto_update_for_dnf5_automatic(self):
        self.os_patch_default_configuration_settings_file_path = self.dnf5_automatic_default_configuration_file_path
        self.os_patch_override_configuration_settings_file_path = self.dnf5_automatic_override_configuration_file_path
        self.auto_update_config_pattern_match_text = self.dnf5_automatic_config_pattern_match_text
        self.download_updates_identifier_text = self.dnf5_automatic_download_updates_identifier_text
        self.apply_updates_identifier_text = self.dnf5_automatic_apply_updates_identifier_text
        self.enable_on_reboot_identifier_text = self.dnf5_automatic_enable_on_reboot_identifier_text
        self.installation_state_identifier_text = self.dnf5_automatic_installation_state_identifier_text
        self.enable_on_reboot_check_cmd = self.dnf5_automatic_enable_on_reboot_check_cmd
        self.enable_on_reboot_cmd = self.dnf5_automatic_enable_on_reboot_cmd
        self.install_check_cmd = self.dnf5_automatic_install_check_cmd
        self.current_auto_os_update_service = self.dnf5_auto_os_update_service
        self.os_patch_default_configuration_backup_key = self.dnf5_default_auto_os_config_backup_key
        self.os_patch_override_configuration_backup_key = self.dnf5_override_auto_os_config_backup_key

    def __get_current_auto_os_updates_setting_on_machine(self):
        """Gets all auto-OS update settings for dnf5-automatic (DNF5) via config + timer state."""
        try:
            download_updates_value = ""
            apply_updates_value = ""
            is_service_installed = False
            enable_on_reboot_value = False

            # install state
            if not self.is_auto_update_service_installed(self.install_check_cmd):
                return is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value

            code, service_output = self.env_layer.run_command_output(self.dnf5_automatic_configuration_service, False, False)
            exec_start_line = ""
            #Only print ExecStart details
            for line in service_output.splitlines():
                if line.strip().startswith("ExecStart"):
                    exec_start_line = line.strip()
                    break
            self.composite_logger.log_debug("[DNF5] dnf5-automatic ExecStart details. [Command={0}][Code={1}][Output={2}]".format(self.dnf5_automatic_configuration_service, str(code), exec_start_line))

            is_service_installed = True
            enable_on_reboot_value = self.is_service_set_to_enable_on_reboot(self.enable_on_reboot_check_cmd)

            self.composite_logger.log_verbose("[DNF5] Checking if auto updates are currently enabled...")
            default_download_updates_value, default_apply_updates_value, override_download_updates_value, override_apply_updates_value = self.__get_default_and_override_config_values()

            download_updates_value = (override_download_updates_value if override_download_updates_value != "" else default_download_updates_value)

            apply_updates_value = (
                override_apply_updates_value
                if override_apply_updates_value != ""
                else default_apply_updates_value
            )

            if download_updates_value == "":
                self.composite_logger.log_verbose("[DNF5] Machine did not have any value set for [Setting={0}]".format(str(self.download_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("[DNF5]  Current value set for [{0}={1}]".format(str(self.download_updates_identifier_text), str(download_updates_value)))
            if apply_updates_value == "":
                self.composite_logger.log_verbose("[DNF5] Machine did not have any value set for [Setting={0}]".format(str(self.apply_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("[DNF5] Current value set for [{0}={1}]".format(str(self.apply_updates_identifier_text), str(apply_updates_value)))
            return is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value

        except Exception as error:
            raise Exception("[DNF5] Error fetching current auto OS update settings. [Exception={0}]".format(repr(error)))

    def is_auto_update_service_installed(self, install_check_cmd):
        """ Checks if the auto update service is installed on the VM """
        self.composite_logger.log_verbose("[DNF5] Checking if auto update service is installed. [Command={0}]".format(install_check_cmd))
        code, out = self.env_layer.run_command_output(install_check_cmd, False, False)
        is_installed = len(out.strip()) > 0 and code == 0
        self.composite_logger.log_debug("[DNF5] Auto update service check completed. [Command={0}][Code={1}][Output={2}][Installed={3}]".format(install_check_cmd, str(code), out, str(is_installed)))
        return is_installed

    def is_service_set_to_enable_on_reboot(self, command):
        """ Checking if auto update is set to enable on reboot on the machine. An enable_on_reboot service will be activated (if currently inactive) on machine reboot """
        self.composite_logger.log_verbose("[DNF5] Checking if auto update service is set to enable on reboot. [Command={0}]".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)
        is_enable_on_reboot = len(out.strip()) > 0 and code == 0 and out.strip().lower() == "enabled"
        self.composite_logger.log_debug("[DNF5] Auto update service enable on reboot check completed. [Command={0}][Code={1}][IsServiceSetToEnableOnReboot={2}]".format(command, str(code), str(is_enable_on_reboot)))
        return is_enable_on_reboot

    def __get_extension_standard_value_for_apply_updates(self, apply_updates_value):
        if apply_updates_value.lower() == 'yes':
            return self.apply_updates_enabled
        elif apply_updates_value.lower() == 'no':
            return self.apply_updates_disabled
        else:
            return self.apply_updates_unknown

    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enabled and logs the default settings the machine comes with """
        try:
            self.composite_logger.log_verbose("[DNF5] Disabling auto OS updates in all identified services...")
            self.__disable_auto_os_update_for_dnf5_automatic()
            self.composite_logger.log_debug("[DNF5] Successfully disabled auto OS updates")

        except Exception as error:
            self.composite_logger.log_error("[DNF5] Could not disable auto OS updates. [Error={0}]".format(repr(error)))
            raise

    def __disable_auto_os_update_for_dnf5_automatic(self):
        """ Disables auto OS updates, using dnf5-automatic service, and logs the default settings the machine comes with """
        self.composite_logger.log_verbose("[DNF5] Disabling auto OS updates using dnf5-automatic")
        self.__init_auto_update_for_dnf5_automatic()
        self.backup_image_default_patch_configuration_if_not_exists()

        if not self.is_auto_update_service_installed(self.dnf5_automatic_install_check_cmd):
            self.composite_logger.log_debug("[DNF5] Cannot disable as dnf5-automatic is not installed on the machine")
            return

        self.composite_logger.log_verbose("[DNF5] Preemptively disabling auto OS updates using dnf5-automatic")
        # Check if override.conf file exists, if not copy/create from default config location
        self.__ensure_override_configuration_exists()
        self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "no", self.dnf5_automatic_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "no", self.dnf5_automatic_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.dnf5_automatic_disable_on_reboot_cmd)
        self.composite_logger.log_debug("[DNF5] Successfully disabled auto OS updates using dnf5-automatic")

    def __ensure_override_configuration_exists(self):
        override_config_file = self.env_layer.file_system.read_with_retry(self.os_patch_override_configuration_settings_file_path, raise_if_not_found=False)
        if override_config_file is not None:
            return

        self.composite_logger.log_debug("[DNF5] Override configuration file does not exist.Creating it from default configuration.")
        default_config = self.env_layer.file_system.read_with_retry(self.os_patch_default_configuration_settings_file_path)
        self.env_layer.file_system.write_with_retry(self.os_patch_override_configuration_settings_file_path, default_config, mode='w+')

    def disable_auto_update_on_reboot(self, command):
        """ Disables auto update on reboot by executing systemctl command """
        self.composite_logger.log_verbose("[DNF5] Disabling auto update on reboot. [Command={0}] ".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != 0:
            self.composite_logger.log_error("[DNF5][ERROR] Error disabling auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("[DNF5] Disabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))

    def backup_image_default_patch_configuration_if_not_exists(self):
        """ Records the default system settings for auto OS updates within patch extension artifacts for future reference.
            Log the default system settings a VM comes with, any subsequent updates will not be recorded"""
        """ JSON format for backup file:
                    {
                        "default-dnf5-automatic": {
                                    "apply_updates": "yes/no/empty string",
                                    "download_updates": "yes/no/empty string",
                                    "enable_on_reboot": true/false,
                                    "installation_state": true/false
                        },
                        "override-dnf5-automatic": {
                                    "apply_updates": "yes/no/empty string",
                                    "download_updates": "yes/no/empty string",
                                    "enable_on_reboot": true/false,
                                    "installation_state": true/false
                        }
                    } """
        try:
            self.composite_logger.log_verbose("[DNF5] Ensuring there is a backup of the default patch state for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))

            image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()
            # verify if existing backup is valid if not, write to backup
            is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)

            if is_backup_valid:
                self.composite_logger.log_debug("[DNF5] Since extension has a valid backup, no need to log the current settings again. ""[Default Auto OS update settings={0}] [File path={1}]".format(str(image_default_patch_configuration_backup),self.image_default_patch_configuration_backup_path))
            else:
                self.composite_logger.log_debug("[DNF5] Since the backup is invalid, will add a new backup with the current auto OS update settings")
                self.composite_logger.log_verbose("[DNF5] Fetching current auto OS update settings for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))

                is_service_installed, enable_on_reboot_value, _, _ = self.__get_current_auto_os_updates_setting_on_machine()

                default_download_updates_value, default_apply_updates_value, override_download_updates_value, override_apply_updates_value = self.__get_default_and_override_config_values()

                backup_image_default_patch_configuration_json_to_add = {
                    self.os_patch_default_configuration_backup_key: {
                        self.download_updates_identifier_text: default_download_updates_value,
                        self.apply_updates_identifier_text: default_apply_updates_value,
                        self.enable_on_reboot_identifier_text: enable_on_reboot_value,
                        self.installation_state_identifier_text: is_service_installed
                    },
                    self.os_patch_override_configuration_backup_key: {
                        self.download_updates_identifier_text: override_download_updates_value,
                        self.apply_updates_identifier_text: override_apply_updates_value,
                        self.enable_on_reboot_identifier_text: enable_on_reboot_value,
                        self.installation_state_identifier_text: is_service_installed
                    }
                }
                image_default_patch_configuration_backup.update(backup_image_default_patch_configuration_json_to_add)

                self.composite_logger.log_debug("[DNF5] Logging default system configuration settings for auto OS updates. [Settings={0}] [Log file path={1}]"
                                                .format(str(image_default_patch_configuration_backup),self.image_default_patch_configuration_backup_path))
                self.env_layer.file_system.write_with_retry(self.image_default_patch_configuration_backup_path,'{0}'.format(json.dumps(image_default_patch_configuration_backup)),mode='w+')
        except Exception as error:
            self.composite_logger.log_error("[DNF5] Exception during fetching and logging default auto update settings on the machine. [Exception={0}]".format(repr(error)))
            self.status_handler.add_error_to_status("[DNF5] Exception during fetching and logging default auto update settings on the machine. [Exception={0}]".format(repr(error)), Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def __get_default_and_override_config_values(self):
        self.composite_logger.log_debug("[DNF5] Reading default configuration file. [Path={0}]".format(self.os_patch_default_configuration_settings_file_path))
        default_download_updates_value, default_apply_updates_value = self.__get_config_values(self.os_patch_default_configuration_settings_file_path)
        self.composite_logger.log_debug("[DNF5] Default configuration values found.[download_updates={0}][apply_updates={1}]".format(default_download_updates_value, default_apply_updates_value))

        self.composite_logger.log_debug("[DNF5] Reading override configuration file. [Path={0}]".format(self.os_patch_override_configuration_settings_file_path))
        override_download_updates_value, override_apply_updates_value = self.__get_config_values(self.os_patch_override_configuration_settings_file_path)
        self.composite_logger.log_debug("[DNF5] Override configuration values found.[download_updates={0}][apply_updates={1}]".format(override_download_updates_value, override_apply_updates_value))

        return default_download_updates_value, default_apply_updates_value, override_download_updates_value, override_apply_updates_value

    def __get_config_values(self, config_file_path):
        download_updates_value = ""
        apply_updates_value = ""

        self.composite_logger.log_debug("[DNF5] Reading config file. [Path={0}]".format(config_file_path))
        config = self.env_layer.file_system.read_with_retry(config_file_path, raise_if_not_found=False)
        if config is None:
            self.composite_logger.log_debug("[DNF5] Config file not found. [Path={0}]".format(config_file_path))
            return download_updates_value, apply_updates_value

        settings = config.strip().split('\n')

        for setting in settings:
            match = re.search(self.download_updates_identifier_text + self.auto_update_config_pattern_match_text, str(setting))
            if match is not None:
                download_updates_value = match.group(1)
                self.composite_logger.log_debug("[DNF5] Found download_updates setting.[Value={0}]".format(download_updates_value))

            match = re.search(self.apply_updates_identifier_text + self.auto_update_config_pattern_match_text, str(setting))
            if match is not None:
                apply_updates_value = match.group(1)
                self.composite_logger.log_debug("[DNF5] Found apply_updates setting.[Value={0}]".format(apply_updates_value))

        self.composite_logger.log_debug("[DNF5] Finished parsing configuration values.[Path={0}][DownloadUpdates={1}][ApplyUpdates={2}]".format(config_file_path, download_updates_value, apply_updates_value))

        return download_updates_value, apply_updates_value

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        """ Verifies if default auto update configurations, for a service under consideration, are saved in backup """
        return self.is_backup_valid_for_dnf5_automatic(image_default_patch_configuration_backup)

    def is_backup_valid_for_dnf5_automatic(self, image_default_patch_configuration_backup):
            default_backup_valid = self.__is_backup_valid(
                image_default_patch_configuration_backup,
                self.os_patch_default_configuration_backup_key
            )

            override_backup_valid = self.__is_backup_valid(
                image_default_patch_configuration_backup,
                self.os_patch_override_configuration_backup_key
            )

            if default_backup_valid and override_backup_valid:
                self.composite_logger.log_debug(
                    "[DNF5] Extension has a valid backup for default and override dnf5-automatic configuration settings"
                )
                return True

            self.composite_logger.log_debug(
                "[DNF5] Extension does not have a valid backup for default and override dnf5-automatic configuration settings"
            )
            return False

    def __is_backup_valid(self, image_default_patch_configuration_backup, backup_key):
        return (backup_key in image_default_patch_configuration_backup
                and self.dnf5_automatic_download_updates_identifier_text
                in image_default_patch_configuration_backup[backup_key]
                and self.dnf5_automatic_apply_updates_identifier_text
                in image_default_patch_configuration_backup[backup_key]
                and self.dnf5_automatic_enable_on_reboot_identifier_text
                in image_default_patch_configuration_backup[backup_key]
                and self.dnf5_automatic_installation_state_identifier_text
                in image_default_patch_configuration_backup[backup_key])

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value="no",config_pattern_match_text="", config_file_path=None):
        try:
            # note: adding space between the patch_configuration_sub_setting and value since, we will have to do that if we have to add a patch_configuration_sub_setting that did not exist before
            if config_file_path is None:
                config_file_path = self.os_patch_override_configuration_settings_file_path
            self.composite_logger.log_debug("[DNF5] Updating system configuration settings for auto OS updates. [Patch Configuration Sub Setting={0}] [Value={1}]".format(
                    str(patch_configuration_sub_setting), value))
            os_patch_configuration_settings = self.env_layer.file_system.read_with_retry(config_file_path)
            patch_configuration_sub_setting_to_update = patch_configuration_sub_setting + ' = ' + value
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

            self.env_layer.file_system.write_with_retry(config_file_path,'{0}'.format(updated_patch_configuration_sub_setting.lstrip()),mode='w+')
        except Exception as error:
            error_msg = "[DNF5] Error occurred while updating system configuration settings for auto OS updates. [Patch Configuration={0}] [Error={1}]".format(
                str(patch_configuration_sub_setting), repr(error))
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def revert_auto_os_update_to_system_default(self):
        """ Reverts the auto OS update patch state on the machine to its system default value, if one exists in our backup file """
        # type () -> None
        self.composite_logger.log("[DNF5] Reverting the current automatic OS patch state on the machine to its system default value before patchmode was set to 'AutomaticByPlatform'")
        self.revert_auto_os_update_to_system_default_for_dnf5_automatic()
        self.composite_logger.log_debug("[DNF5] Successfully reverted auto OS updates to system default config")

    def revert_auto_os_update_to_system_default_for_dnf5_automatic(self):
        """ Reverts the auto OS update patch state on the machine to its system default value for dnf5-automatic service, if applicable """
        # type () -> None
        self.__init_auto_update_for_dnf5_automatic()
        self.composite_logger.log("[DNF5] Reverting the current automatic OS patch state on the machine to its system default value for [Service={0}]".format(str(self.current_auto_os_update_service)))
        is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

        if not is_service_installed:
            self.composite_logger.log_debug("[DNF5] Machine default auto OS update service is not installed on the VM and hence no config to revert. [Service={0}]".format(str(self.current_auto_os_update_service)))
            return

        default_download_updates_value, default_apply_updates_value, override_download_updates_value, override_apply_updates_value = self.__get_default_and_override_config_values()
        self.composite_logger.log_verbose("[DNF5] Logging current configuration settings for auto OS updates "
        "[Service={0}]""[Is_Service_Installed={1}]""[Machine_default_update_enable_on_reboot={2}]""[Effective_download_updates={3}]"
        "[Effective_apply_updates={4}]"
        "[Default_download_updates={5}]""[Default_apply_updates={6}]""[Override_download_updates={7}]""[Override_apply_updates={8}]"
        .format(str(self.current_auto_os_update_service), str(is_service_installed), str(enable_on_reboot_value),
        str(download_updates_value),
        str(apply_updates_value),
        str(default_download_updates_value),
        str(default_apply_updates_value),
        str(override_download_updates_value),
        str(override_apply_updates_value)))
        # self.composite_logger.log_verbose("[DNF5] Logging current configuration settings for auto OS updates [Service={0}][Is_Service_Installed={1}][Machine_default_update_enable_on_reboot={2}]".format(
        #         str(self.current_auto_os_update_service), str(is_service_installed), str(enable_on_reboot_value)))

        image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()
        self.composite_logger.log_verbose("[DNF5] Logging system default configuration settings for auto OS updates. [Settings={0}]".format(str(image_default_patch_configuration_backup)))
        is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)

        if is_backup_valid:
            default_backup = image_default_patch_configuration_backup[self.os_patch_default_configuration_backup_key]
            override_backup = image_default_patch_configuration_backup[self.os_patch_override_configuration_backup_key]

            self.__restore_default_configuration_from_backup(default_backup)
            self.__restore_override_configuration_from_backup(override_backup)
            self.__restore_enable_on_reboot_state_from_backup(default_backup)
            # download_updates_value_from_backup = image_default_patch_configuration_backup[self.current_auto_os_update_service][self.download_updates_identifier_text]
            # apply_updates_value_from_backup = image_default_patch_configuration_backup[self.current_auto_os_update_service][self.apply_updates_identifier_text]
            # enable_on_reboot_value_from_backup = image_default_patch_configuration_backup[self.current_auto_os_update_service][self.enable_on_reboot_identifier_text]
            #
            # self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, download_updates_value_from_backup, self.auto_update_config_pattern_match_text)
            # self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, apply_updates_value_from_backup, self.auto_update_config_pattern_match_text)
            # if str(enable_on_reboot_value_from_backup).lower() == 'true':
            #     self.enable_auto_update_on_reboot()
        else:
            self.composite_logger.log_debug("[DNF5] Since the backup is invalid or does not exist for current service, we won't be able to revert auto OS patch settings to their system default value. [Service={0}]".format(str(self.current_auto_os_update_service)))

    def __remove_override_configuration_if_exists(self):
        """Removes dnf5-automatic override configuration file if it exists.Missing override file is valid by design, so this method must not throw
        when the file is absent."""
        override_config_file = self.env_layer.file_system.read_with_retry(self.os_patch_override_configuration_settings_file_path, raise_if_not_found=False)

        if override_config_file is None:
            self.composite_logger.log_debug("[DNF5] Override configuration file does not exist. Nothing to remove. [Path={0}]".format(self.os_patch_override_configuration_settings_file_path))
            return

        self.composite_logger.log_debug("[DNF5] Removing override configuration file to restore machine default. [Path={0}]".format(self.os_patch_override_configuration_settings_file_path) )

        code, out = self.env_layer.run_command_output(self.dnf5_automatic_remove_override_configuration_file_cmd, False, False)

        if code != 0:
            error_msg = "[DNF5] Error removing override configuration file. [Command={0}][Code={1}][Output={2}]".format(
                self.dnf5_automatic_remove_override_configuration_file_cmd,
                str(code),
                out
            )
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(
                error_msg,
                Constants.PatchOperationErrorCodes.OPERATION_FAILED
            )
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

        self.composite_logger.log_debug(
            "[DNF5] Removed override configuration file. [Command={0}][Code={1}][Output={2}]"
            .format(self.dnf5_automatic_remove_override_configuration_file_cmd, str(code), out)
        )

    def __restore_default_configuration_from_backup(self, default_backup):
        """Restore default dnf5-automatic configuration to its backed up state."""

        default_download_updates = default_backup[self.download_updates_identifier_text]
        default_apply_updates = default_backup[self.apply_updates_identifier_text]

        self.composite_logger.log_debug("[DNF5] Restoring default dnf5-automatic configuration values from backup.[Path={0}][download_updates={1}][apply_updates={2}]"
            .format(self.os_patch_default_configuration_settings_file_path, str(default_download_updates),str(default_apply_updates)
            )
        )

        self.update_os_patch_configuration_sub_setting(
            self.download_updates_identifier_text,
            default_download_updates,
            self.auto_update_config_pattern_match_text,
            self.os_patch_default_configuration_settings_file_path
        )

        self.update_os_patch_configuration_sub_setting(
            self.apply_updates_identifier_text,
            default_apply_updates,
            self.auto_update_config_pattern_match_text,
            self.os_patch_default_configuration_settings_file_path
        )

    def __restore_override_configuration_from_backup(self, override_backup):
        """Restore override dnf5-automatic configuration to its backed up state."""

        override_download_updates = override_backup[self.download_updates_identifier_text]
        override_apply_updates = override_backup[self.apply_updates_identifier_text]

        # Empty values indicate override file did not exist before onboarding.
        if override_download_updates == "" and override_apply_updates == "":
            self.composite_logger.log_debug(
                "[DNF5] Override dnf5-automatic configuration did not exist before onboarding. "
                "Removing override configuration file if it exists."
            )

            self.__remove_override_configuration_if_exists()
            return

        self.composite_logger.log_debug(
            "[DNF5] Restoring override dnf5-automatic configuration values from backup. "
            "[Path={0}][download_updates={1}][apply_updates={2}]"
            .format(
                self.os_patch_override_configuration_settings_file_path,
                str(override_download_updates),
                str(override_apply_updates)
            )
        )

        self.__ensure_override_configuration_exists()

        self.update_os_patch_configuration_sub_setting(
            self.download_updates_identifier_text,
            override_download_updates,
            self.auto_update_config_pattern_match_text,
            self.os_patch_override_configuration_settings_file_path
        )

        self.update_os_patch_configuration_sub_setting(
            self.apply_updates_identifier_text,
            override_apply_updates,
            self.auto_update_config_pattern_match_text,
            self.os_patch_override_configuration_settings_file_path
        )

    def __restore_enable_on_reboot_state_from_backup(self, default_backup):
        enable_on_reboot_value = default_backup[self.enable_on_reboot_identifier_text]

        if str(enable_on_reboot_value).lower() == 'true':
            self.composite_logger.log_debug(
                "[DNF5] Restoring dnf5-automatic timer to enabled state from backup."
            )

            self.enable_auto_update_on_reboot()

    def enable_auto_update_on_reboot(self):
        """ Enables machine default auto update on reboot """
        # type () -> None
        command = self.enable_on_reboot_cmd
        self.composite_logger.log_verbose("[DNF5] Enabling auto update on reboot. [Command={0}] ".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != 0:
            self.composite_logger.log_error("[DNF5][ERROR] Error enabling auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("[DNF5] Enabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code),out))

    def __get_image_default_patch_configuration_backup(self):
        """ Get image_default_patch_configuration_backup file"""
        image_default_patch_configuration_backup = {}
        # read existing backup since it also contains backup from other update services. We need to preserve any existing data within the backup file
        if self.image_default_patch_configuration_backup_exists():
            try:
                image_default_patch_configuration_backup = json.loads(self.env_layer.file_system.read_with_retry(self.image_default_patch_configuration_backup_path))
            except Exception as error:
                self.composite_logger.log_error("[DNF5] Unable to read backup for default patch state. Will attempt to re-write. [Exception={0}]".format(repr(error)))
        return image_default_patch_configuration_backup
    #endregion

    # region Reboot Management
    def is_reboot_pending(self):
        """Checks if reboot is required"""
        self.composite_logger.log_verbose("[DNF5] Checking if reboot is required [Command={0}]".format(self.needs_restarting_with_flag))
        code, output = self.env_layer.run_command_output(self.needs_restarting_with_flag, False, False)
        reboot_required = (code == 1)
        self.composite_logger.log_debug("[DNF5] > Outcome of reboot required check. [Command={0}][Code={1}][ComputedValueOfRebootRequired={2}]".format(str(self.needs_restarting_with_flag), str(code), str(reboot_required)))
        return reboot_required

    def do_processes_require_restart(self):
        """Fulfilling base class contract. Not needed for DNF5"""
        pass
    # endregion

    def set_security_esm_package_status(self, operation, packages):
        """No-op for dnf5, tdnf, yum and zypper """
        return

    def separate_out_esm_packages(self, packages, package_versions):
        """Filter out packages from the list where the version matches the UA_ESM_REQUIRED string.Only needed for apt. No-op for tdnf, dnf5, yum and zypper"""
        esm_packages = []
        esm_package_versions = []
        esm_packages_found = False
        return packages, package_versions, esm_packages, esm_package_versions, esm_packages_found

    def get_package_install_expected_avg_time_in_seconds(self):
        return self.package_install_expected_avg_time_in_seconds

    # region Update certificates in factory defaults
    def try_install_mokutil(self):
        """ Attempts to install mokutil """
        pass

    def try_update_certs(self):
        """ Attempts to update certificate status """
        pass
    # endregion
