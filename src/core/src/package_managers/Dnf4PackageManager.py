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

"""Dnf4PackageManager for Rhel 10"""
import json
import re

from core.src.core_logic.VersionComparator import VersionComparator
from core.src.bootstrap.Constants import Constants
from core.src.package_managers.PackageManager import PackageManager


class Dnf4PackageManager(PackageManager):
    """Implementation of dnf4 package management operations"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(Dnf4PackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)
        # Repo refresh
        self.cmd_clean_cache = "sudo dnf4 -q clean expire-cache"
        self.cmd_repo_refresh = self.cmd_get_all_updates = "sudo dnf4 -q check-update"

        # Support to get updates and their dependencies
        self.single_package_check_versions = 'sudo dnf4 list --available <PACKAGE-NAME> '
        self.single_package_check_installed = 'sudo dnf4 list --installed <PACKAGE-NAME> '
        self.single_package_upgrade_simulation_cmd = 'sudo dnf4 install --assumeno --skip-broken '

        # Install update
        self.single_package_upgrade_cmd = 'sudo dnf4 -y install '

        # Support to check for processes requiring restart
        self.needs_restarting_with_flag = 'sudo LANG=en_US.UTF8 needs-restarting -r'

        # Package manager exit code(s)
        self.dnf4_exitcode_ok = [0, 100]
        # DNF4 valid exit codes for simulation commands
        self.dnf4_simulation_valid_exit_codes = [0, 1]
        self.dnf4_not_installed_exit_code = 1

        # Package manager success/failure text
        self.dnf4_not_installed_text = "No matching packages to list"
        self.dnf4_dependency_success_text = ["Installing dependencies:", "Upgrading:", "Dependencies resolved."]
        self.dnf4_dependency_exit_text = "Transaction Summary"
        self.dnf4_dependency_failure_text = "Skipping packages with broken dependencies"
        self.dnf4_subscription_failure_texts = ["Unable to read consumer identity", "This system is not registered with an entitlement server"]
        self.dnf4_list_installed_command_patterns = "list --installed"

        # Auto OS updates
        self.current_auto_os_update_service = None
        self.os_patch_configuration_settings_file_path = ''
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
        self.__init_constants_for_dnf4_automatic()

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.DNF4)
        self.STR_TOTAL_DOWNLOAD_SIZE = "Total download size: "
        self.version_comparator = VersionComparator()

        self.package_install_expected_avg_time_in_seconds = 90  # Setting a default value of 90 seconds as the avg time to install a package using dnf4.

    def refresh_repo(self):
        self.composite_logger.log("[DNF4] Refreshing local repo...")
        self.invoke_package_manager(self.cmd_clean_cache)
        self.invoke_package_manager(self.cmd_repo_refresh)

    # region Get Available Updates
    def invoke_package_manager_advanced(self, command, raise_on_exception=True):
        """Get missing updates using the command input"""
        self.composite_logger.log_verbose("[DNF4] Invoking package manager. [Command={0}]".format(str(command)))
        code, out = self.env_layer.run_command_output(command, False, False)
        self.validate_dnf4_output(out)
        is_valid_not_installed = (self.dnf4_list_installed_command_patterns in command and code == self.dnf4_not_installed_exit_code and self.dnf4_not_installed_text in (out or ""))

        if code in self.dnf4_exitcode_ok or is_valid_not_installed:
            self.composite_logger.log_debug('[DNF4] Invoked package manager. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
        else:
            self.composite_logger.log_warning('[ERROR] Customer environment error. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
            error_msg = "Customer environment error: Investigate and resolve unexpected return code ({0}) from package manager on command: {1}".format(str(code), command)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            if raise_on_exception:
                raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

        return out, code

    def validate_dnf4_output(self, output):
        for failure_text in self.dnf4_subscription_failure_texts:
            if failure_text in output:
                self.composite_logger.log_error("[DNF4] Subscription/entitlement failure detected. [{0}]".format(failure_text))
                raise Exception("System is not properly registered with subscription service.")

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_verbose("[DNF4] Discovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug("[DNF4] Get all updates : [Cached={0}][PackagesCount={1}]]".format(str(cached), len(self.all_updates_cached)))
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        out = self.invoke_package_manager(self.cmd_get_all_updates)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)
        self.composite_logger.log_debug("[DNF4] Get all updates : [Cached={0}][PackagesCount={1}]]".format(str(False), len(self.all_updates_cached)))
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates. NOTE: Classification based categorization of patches is not available in Rhel 10 as of now"""
        self.composite_logger.log_verbose("[DNF4] Discovering all packages as 'security' packages, since DNF4 does not support package classification...")
        security_packages, security_package_versions = self.get_all_updates(cached=False)
        self.composite_logger.log_debug("[DNF4] Discovered 'security' packages. [Count={0}]".format(len(security_packages)))
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates."""
        self.composite_logger.log_verbose("[DNF4] Discovering 'other' packages...")
        return [], []

    def set_max_patch_publish_date(self, max_patch_publish_date=str()):
        pass
    # endregion

    # region Output Parser(s)
    def extract_packages_and_versions(self, output):
        """Returns packages and versions from given output"""
        packages, versions = self.extract_packages_and_versions_including_duplicates(output)
        packages, versions = self.dedupe_update_packages_to_get_latest_versions(packages, versions)
        return packages, versions

    def extract_packages_and_versions_including_duplicates(self, output):
        """Returns packages and versions from given output"""
        # DNF check-update returns 3-column format: package.arch version repo
        # Sample output : python3-rpm.x86_64              4.19.1.1-23.el10                        rhel-10-baseos-rhui-rpms
        self.composite_logger.log_verbose("[DNF4] Extracting package and version data...")
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
                self.composite_logger.log_verbose("[DNF4] > Inapplicable line ({0}): {1}".format(line_index, lines[line_index]))

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
                is_deduped_package_latest = self.version_comparator.compare_versions(deduped_package_version,
                                                                                     duplicate_package_version)
                if is_deduped_package_latest < 0:
                    deduped_package_versions[deduped_packages.index(package)] = duplicate_package_version
                continue

            deduped_packages.append(package)
            deduped_package_versions.append(package_versions[index])

        return deduped_packages, deduped_package_versions

    @staticmethod
    def __is_package(chunk):
        # Using a list comprehension to determine if chunk is a package
        return any(chunk.endswith(ext) for ext in Constants.SUPPORTED_PACKAGE_ARCH)
    # endregion

    # region Install Update
    def get_composite_package_identifier(self, package, package_version):
        package_without_arch, arch = self.get_product_name_and_arch(package)
        package_identifier = package_without_arch + '-' + str(package_version)
        if arch is not None:
            package_identifier += arch
        return package_identifier

    def install_updates_fail_safe(self, excluded_packages):
        return

    def install_security_updates_azgps_coordinated(self):
        """This is not applicable for dnf4 yet. DNF4 will not have this method implemented"""
        pass

    def try_meet_azgps_coordinated_requirements(self):
        """This is not applicable for dnf4 yet. DNF4 will not have this method implemented"""
        pass
    # endregion

    # region Package Information
    def get_all_available_versions_of_package(self, package_name):
        """Returns a list of all the available versions of a package"""
        # Sample output format ( plugin : kernel)
        #      Updating Subscription Management repositories.
        #      Last metadata expiration check: 0:46:06 ago on Tue Jun 30 19:39:22 2026.
        #      Available Packages
        #      kernel.x86_64             6.12.0-211.28.1.el10_2             rhel-10-baseos-rhui-rpms
        cmd = self.single_package_check_versions.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)
        return package_versions

    def is_package_version_installed(self, package_name, package_version):
        """Returns true if the specific package version is installed"""
        # Sample output for the command `dnf4 list --installed kernel`:
        #      Updating Subscription Management repositories.
        #      Installed Packages
        #      kernel.x86_64             6.12.0-211.22.1.el10_2              @System
        self.composite_logger.log_verbose("[DNF4] Checking package install status. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
        cmd = self.single_package_check_installed.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)

        for index, package in enumerate(packages):
            if package == package_name and (package_versions[index] == package_version):
                self.composite_logger.log_debug("[DNF4] Installed version match found. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
                return True
            else:
                self.composite_logger.log_verbose("[DNF4] Did not match: " + package + " (" + package_versions[index] + ")")

        # If no matching package name and version are found in the package manager output, the requested version is not installed (it may have been replaced, upgraded, or removed)
        self.composite_logger.log_debug("[DNF4] Installed version match NOT found. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
        return False

    def extract_dependencies(self, output, packages):
        # Extracts dependent packages from output. Refer dnf4_output_expected_format.txt for examples of output formats.
        dependencies = []

        # Handle non-blocking dependency failure / nothing-to-do cases
        if self.dnf4_dependency_failure_text in output:
            self.composite_logger.log_warning("[DNF4] Packages skipped due to broken dependencies (non-blocking)")
            return dependencies

        package_arch_to_look_for = ["x86_64", "noarch", "i686", "aarch64"]

        lines = output.strip().splitlines()
        in_dependency_section = False

        for line_index in range(0, len(lines)):
            line_str = lines[line_index].strip()
            # Detect start of dependency section
            if any(line_str.startswith(text) for text in self.dnf4_dependency_success_text):
                in_dependency_section = True

            #  Detect exit of dependency section
            if in_dependency_section and line_str.startswith(self.dnf4_dependency_exit_text):
                self.composite_logger.log_verbose("[DNF4] Exiting dependency section. Remaining output lines are skipped.")
                break

            line = re.split(r'\s+', line_str)
            dependent_package_name = ""

            if self.is_valid_update(line, package_arch_to_look_for):
                dependent_package_name = self.get_product_name_with_arch(line, package_arch_to_look_for)
            else:
                self.composite_logger.log_verbose("[DNF4] Inapplicable line: " + str(line))
                continue

            #  Remove input packages (support both pkg and pkg.arch)
            if len(dependent_package_name) != 0 and dependent_package_name not in packages and dependent_package_name not in dependencies:
                self.composite_logger.log_verbose("[DNF4] Dependency detected: " + dependent_package_name)
                dependencies.append(dependent_package_name)

        return dependencies

    def add_arch_dependencies(self, package_manager, package, version, packages, package_versions, package_and_dependencies, package_and_dependency_versions):
        """Not needed since it already supports multi-architecture. Refer to PR description for details."""
        pass

    def is_valid_update(self, package_details_in_output, package_arch_to_look_for):
        # Verifies whether the line under consideration (i.e. package_details_in_output) contains relevant package details.
        # package_details_in_output will be of the following format if it is valid
        # Sample package details in DNF4:
        # perl-lib                                                           x86_64                                                   0.65-512.2.el10_0                                                      rhel-10-appstream-rhui-rpms                                                    16 k
        return len(package_details_in_output) == 6 and self.is_arch_in_package_details(package_details_in_output[1], package_arch_to_look_for)

    @staticmethod
    def is_arch_in_package_details(package_detail, package_arch_to_look_for):
        # Using a list comprehension to determine if chunk is a package
        return len([p for p in package_arch_to_look_for if p in package_detail]) == 1

    def get_dependent_list(self, packages):
        """Returns dependent List for the list of packages"""
        package_names = " ".join(packages)
        cmd = self.single_package_upgrade_simulation_cmd + package_names
        code, output = self.env_layer.run_command_output(cmd, False, False)
        self.composite_logger.log_verbose("[DNF4] Dependency simulation. [Command={0}][Code={1}]".format(cmd, str(code)))
        if code not in self.dnf4_simulation_valid_exit_codes:
            self.composite_logger.log_error("[DNF4] Unexpected failure during dependency simulation. [Command={0}][Code={1}][Output={2}]".format(cmd, str(code), output))
            error_msg = "DNF4 dependency simulation failed. Investigate and resolve unexpected return code({0}) from package manager on command: {1} ".format(str(code), cmd)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

        dependencies = self.extract_dependencies(output, packages)
        self.composite_logger.log_verbose("[DNF4] Resolved dependencies. [Command={0}][Packages={1}][DependencyCount={2}]".format(str(cmd), str(packages), len(dependencies)))
        return dependencies

    def get_product_name(self, package_name):
        """Retrieve package name"""
        return package_name

    def get_product_name_and_arch(self, package_name):
        """Splits out product name and architecture - if this is changed, modify in PackageFilter also"""
        architectures = Constants.SUPPORTED_PACKAGE_ARCH
        for arch in architectures:
            if package_name.endswith(arch):
                return package_name[:-len(arch)], arch
        return package_name, None

    def get_product_name_with_arch(self, package_detail, package_arch_to_look_for):
        """Retrieve product name with arch separated by '.'. Note: This format is default in dnf4. Refer samples noted within func extract_dependencies() for more clarity"""
        return package_detail[0] + "." + package_detail[1] if package_detail[1] in package_arch_to_look_for else \
        package_detail[1]

    def get_package_size(self, output):
        """Retrieve package size from installation output string"""
        # Sample output line:
        # Total download size: 15 M
        if "Nothing to do" not in output:
            lines = output.strip().split('\n')
            for line in lines:
                if line.find(self.STR_TOTAL_DOWNLOAD_SIZE) >= 0:
                    return line.replace(self.STR_TOTAL_DOWNLOAD_SIZE, "")
        return Constants.UNKNOWN_PACKAGE_SIZE
    # endregion

    # region auto OS updates
    def __init_constants_for_dnf4_automatic(self):
        self.dnf4_automatic_configuration_file_path = '/etc/dnf/automatic.conf'
        self.dnf4_automatic_install_check_cmd = ' rpm -qa | grep dnf-automatic'
        self.dnf4_automatic_enable_on_reboot_check_cmd = 'systemctl is-enabled dnf-automatic.timer'
        self.dnf4_automatic_disable_on_reboot_cmd = 'systemctl disable --now dnf-automatic.timer'
        self.dnf4_automatic_enable_on_reboot_cmd = 'systemctl enable --now dnf-automatic.timer'
        self.dnf4_automatic_config_pattern_match_text = ' = (no|yes)'
        self.dnf4_automatic_download_updates_identifier_text = 'download_updates'
        self.dnf4_automatic_apply_updates_identifier_text = 'apply_updates'
        self.dnf4_automatic_enable_on_reboot_identifier_text = "enable_on_reboot"
        self.dnf4_automatic_installation_state_identifier_text = "installation_state"
        self.dnf4_auto_os_update_service = "dnf-automatic"

    def get_current_auto_os_patch_state(self):
        """Gets the current auto OS update patch state on the machine"""
        self.composite_logger.log("[DNF4] Fetching the current automatic OS patch state on the machine...")
        current_auto_os_patch_state_for_dnf_automatic = self.__get_current_auto_os_patch_state_for_dnf_automatic()
        self.composite_logger.log("[DNF4] OS patch state per auto OS update service: [dnf-automatic={0}]".format(str(current_auto_os_patch_state_for_dnf_automatic)))

        if current_auto_os_patch_state_for_dnf_automatic == Constants.AutomaticOSPatchStates.ENABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.ENABLED
        elif current_auto_os_patch_state_for_dnf_automatic == Constants.AutomaticOSPatchStates.DISABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.DISABLED
        else:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.UNKNOWN

        self.composite_logger.log_debug("[DNF4] Overall Auto OS Patch State based on all auto OS update service states [OverallAutoOSPatchState={0}]".format(str(current_auto_os_patch_state)))
        return current_auto_os_patch_state

    def __get_current_auto_os_patch_state_for_dnf_automatic(self):
        """Gets current auto OS update patch state for dnf-automatic"""
        self.composite_logger.log_debug("[DNF4] Fetching current automatic OS patch state in dnf-automatic service. This includes checks on whether the service is installed, current auto patch enable state and whether it is set to enable on reboot")
        self.__init_auto_update_for_dnf_automatic()
        is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

        apply_updates = self.__get_extension_standard_value_for_apply_updates(apply_updates_value)

        if apply_updates == self.apply_updates_enabled or enable_on_reboot_value:
            return Constants.AutomaticOSPatchStates.ENABLED
        # OS patch state is considered to be disabled: a) if it was successfully disabled or b) if the service is not installed
        elif not is_service_installed or (apply_updates == self.apply_updates_disabled and not enable_on_reboot_value):
            return Constants.AutomaticOSPatchStates.DISABLED
        else:
            return Constants.AutomaticOSPatchStates.UNKNOWN

    def __init_auto_update_for_dnf_automatic(self):
        """Initializes all generic auto OS update variables with the config values for dnf automatic service"""
        self.os_patch_configuration_settings_file_path = self.dnf4_automatic_configuration_file_path
        self.download_updates_identifier_text = self.dnf4_automatic_download_updates_identifier_text
        self.apply_updates_identifier_text = self.dnf4_automatic_apply_updates_identifier_text
        self.enable_on_reboot_identifier_text = self.dnf4_automatic_enable_on_reboot_identifier_text
        self.installation_state_identifier_text = self.dnf4_automatic_installation_state_identifier_text
        self.auto_update_config_pattern_match_text = self.dnf4_automatic_config_pattern_match_text
        self.enable_on_reboot_check_cmd = self.dnf4_automatic_enable_on_reboot_check_cmd
        self.enable_on_reboot_cmd = self.dnf4_automatic_enable_on_reboot_cmd
        self.install_check_cmd = self.dnf4_automatic_install_check_cmd
        self.current_auto_os_update_service = self.dnf4_auto_os_update_service

    def __get_current_auto_os_updates_setting_on_machine(self):
        """Gets all the update settings related to auto OS updates currently set on the machine"""
        try:
            download_updates_value = ""
            apply_updates_value = ""
            is_service_installed = False
            enable_on_reboot_value = False

            # get install state
            if not self.is_auto_update_service_installed(self.install_check_cmd):
                return is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value

            is_service_installed = True
            enable_on_reboot_value = self.is_service_set_to_enable_on_reboot(self.enable_on_reboot_check_cmd)

            self.composite_logger.log_debug("[DNF4] Checking if auto updates are currently enabled...")
            image_default_patch_configuration = self.env_layer.file_system.read_with_retry(self.os_patch_configuration_settings_file_path, raise_if_not_found=False)
            if image_default_patch_configuration is not None:
                settings = image_default_patch_configuration.strip().split('\n')
                for setting in settings:
                    match = re.search(self.download_updates_identifier_text + self.auto_update_config_pattern_match_text, str(setting))
                    if match is not None:
                        download_updates_value = match.group(1)

                    match = re.search(self.apply_updates_identifier_text + self.auto_update_config_pattern_match_text, str(setting))
                    if match is not None:
                        apply_updates_value = match.group(1)

            if download_updates_value == "":
                self.composite_logger.log_verbose("[DNF4] Machine did not have any value set for [Setting={0}]".format(str(self.download_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("[DNF4] Current value set for [{0}={1}]".format(str(self.download_updates_identifier_text) , str(download_updates_value)))

            if apply_updates_value == "":
                self.composite_logger.log_verbose("[DNF4] Machine did not have any value set for [Setting={0}]".format(str(self.apply_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("[DNF4] Current value set for [{0}={1}]".format(str(self.apply_updates_identifier_text), str(apply_updates_value)))
            return is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value

        except Exception as error:
            raise Exception("[DNF4] Error occurred in fetching current auto OS update settings from the machine. [Exception={0}]".format(repr(error)))

    def is_auto_update_service_installed(self, install_check_cmd):
        """Checks if the auto update service is enable_on_reboot on the VM"""
        self.composite_logger.log_verbose("[DNF4] Checking if auto update service is installed. [Command={0}]".format(install_check_cmd))
        code, out = self.env_layer.run_command_output(install_check_cmd, False, False)
        is_installed = len(out.strip()) > 0 and code == 0
        self.composite_logger.log_debug("[DNF4] Auto update service check completed. [Command={0}][Code={1}][Output={2}][Installed={3}]".format(install_check_cmd, str(code), out, str(is_installed)))
        return is_installed

    def is_service_set_to_enable_on_reboot(self, command):
        """Checking if auto update is enable_on_reboot on the machine. An enable_on_reboot service will be activated (if currently inactive) on machine reboot"""
        self.composite_logger.log_verbose("[DNF4] Checking if auto update service is set to enable on reboot. [Command={0}]".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)
        is_enable_on_reboot = len(out.strip()) > 0 and code == 0 and out.strip().lower() == "enabled"
        self.composite_logger.log_debug("[DNF4] Auto update service enable on reboot check completed. [Command={0}][Code={1}][EnabledOnReboot={2}]".format(command, str(code), str(is_enable_on_reboot)))
        return is_enable_on_reboot

    def __get_extension_standard_value_for_apply_updates(self, apply_updates_value):
        if apply_updates_value.lower() == 'yes':
            return self.apply_updates_enabled
        elif apply_updates_value.lower() == 'no':
            return self.apply_updates_disabled
        else:
            return self.apply_updates_unknown

    def disable_auto_os_update(self):
        """Disables auto OS updates on the machine only if they are enabled and logs the default settings the machine comes with"""
        try:
            self.composite_logger.log_verbose("[DNF4] Disabling auto OS updates in all identified services...")
            self.disable_auto_os_update_for_dnf_automatic()
            self.composite_logger.log_debug("[DNF4] Successfully disabled auto OS updates")
        except Exception as error:
            self.composite_logger.log_error("[DNF4] Could not disable auto OS updates. [Error={0}]".format(repr(error)))
            raise

    def disable_auto_os_update_for_dnf_automatic(self):
        """Disables auto OS updates, using dnf-automatic service, and logs the default settings the machine comes with"""
        self.composite_logger.log_verbose("[DNF4] Disabling auto OS updates using dnf-automatic")
        self.__init_auto_update_for_dnf_automatic()

        self.backup_image_default_patch_configuration_if_not_exists()

        if not self.is_auto_update_service_installed(self.dnf4_automatic_install_check_cmd):
            self.composite_logger.log_debug("[DNF4] Cannot disable as dnf-automatic is not installed on the machine")
            return

        self.composite_logger.log_verbose("[DNF4] Preemptively disabling auto OS updates using dnf-automatic")
        self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "no", self.dnf4_automatic_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "no", self.dnf4_automatic_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.dnf4_automatic_disable_on_reboot_cmd)
        self.composite_logger.log_debug("[DNF4] Successfully disabled auto OS updates using dnf-automatic")

    def disable_auto_update_on_reboot(self, command):
        self.composite_logger.log_verbose("[DNF4] Disabling auto update on reboot. [Command={0}] ".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != 0:
            self.composite_logger.log_error("[DNF4][ERROR] Error disabling auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("[DNF4] Disabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))

    def backup_image_default_patch_configuration_if_not_exists(self):
        """Records the default system settings for auto OS updates within patch extension artifacts for future reference.
        We only log the default system settings a VM comes with, any subsequent updates will not be recorded"""
        """ JSON format for backup file:
                    {
                        "dnf-automatic": {
                            "apply_updates": "yes/no/empty string",
                            "download_updates": "yes/no/empty string",
                            "enable_on_reboot": true/false,
                            "installation_state": true/false
                        }
                    } """
        try:
            self.composite_logger.log_debug("[DNF4] Ensuring there is a backup of the default patch state for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
            image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()

            # verify if existing backup is valid if not, write to backup
            is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)
            if is_backup_valid:
                self.composite_logger.log_debug("[DNF4] Since extension has a valid backup, no need to log the current settings again. [Default Auto OS update settings={0}] [File path={1}]".format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
            else:
                self.composite_logger.log_debug("[DNF4] Since the backup is invalid, will add a new backup with the current auto OS update settings")
                self.composite_logger.log_debug("[DNF4] Fetching current auto OS update settings for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
                is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

                backup_image_default_patch_configuration_json_to_add = {
                    self.current_auto_os_update_service: {
                        self.download_updates_identifier_text: download_updates_value,
                        self.apply_updates_identifier_text: apply_updates_value,
                        self.enable_on_reboot_identifier_text: enable_on_reboot_value,
                        self.installation_state_identifier_text: is_service_installed
                    }
                }
                image_default_patch_configuration_backup.update(backup_image_default_patch_configuration_json_to_add)
                self.composite_logger.log_debug("[DNF4] Logging default system configuration settings for auto OS updates. [Settings={0}] [Log file path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
                self.env_layer.file_system.write_with_retry(self.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(image_default_patch_configuration_backup)), mode='w+')
        except Exception as error:
            error_message = "[DNF4] Exception during fetching and logging default auto update settings on the machine. [Exception={0}]".format(repr(error))
            self.composite_logger.log_error(error_message)
            self.status_handler.add_error_to_status(error_message, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        """Verifies if default auto update configurations, for a service under consideration, are saved in backup"""
        return self.is_backup_valid_for_dnf_automatic(image_default_patch_configuration_backup)

    def is_backup_valid_for_dnf_automatic(self, image_default_patch_configuration_backup):
        if self.dnf4_auto_os_update_service in image_default_patch_configuration_backup \
                and self.dnf4_automatic_download_updates_identifier_text in image_default_patch_configuration_backup[self.dnf4_auto_os_update_service] \
                and self.dnf4_automatic_apply_updates_identifier_text in image_default_patch_configuration_backup[self.dnf4_auto_os_update_service] \
                and self.dnf4_automatic_enable_on_reboot_identifier_text in image_default_patch_configuration_backup[self.dnf4_auto_os_update_service] \
                and self.dnf4_automatic_installation_state_identifier_text in image_default_patch_configuration_backup[self.dnf4_auto_os_update_service]:
            self.composite_logger.log_debug("[DNF4] Extension has a valid backup for default dnf-automatic configuration settings")
            return True
        else:
            self.composite_logger.log_debug("[DNF4] Extension does not have a valid backup for default dnf-automatic configuration settings")
            return False

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value="no", config_pattern_match_text=""):
        """Updates (or adds if it doesn't exist) the given patch_configuration_sub_setting with the given value in os_patch_configuration_settings_file"""
        try:
            # note: adding space between the patch_configuration_sub_setting and value since, we will have to do that if we have to add a patch_configuration_sub_setting that did not exist before
            self.composite_logger.log_debug("[DNF4] Updating system configuration settings for auto OS updates. [Patch Configuration Sub Setting={0}] [Value={1}]".format(str(patch_configuration_sub_setting), value))
            os_patch_configuration_settings = self.env_layer.file_system.read_with_retry(self.os_patch_configuration_settings_file_path)
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

            self.env_layer.file_system.write_with_retry(self.os_patch_configuration_settings_file_path, '{0}'.format(updated_patch_configuration_sub_setting.lstrip()), mode='w+')
        except Exception as error:
            error_msg = "[DNF4] Error occurred while updating system configuration settings for auto OS updates. [Patch Configuration={0}] [Error={1}]".format(str(patch_configuration_sub_setting), repr(error))
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def revert_auto_os_update_to_system_default(self):
        """Reverts the auto OS update patch state on the machine to its system default value, if one exists in our backup file"""
        # type () -> None
        self.composite_logger.log("[DNF4] Reverting the current automatic OS patch state on the machine to its system default value before patchmode was set to 'AutomaticByPlatform'")
        self.revert_auto_os_update_to_system_default_for_dnf_automatic()
        self.composite_logger.log_debug("[DNF4] Successfully reverted auto OS updates to system default config")

    def revert_auto_os_update_to_system_default_for_dnf_automatic(self):
        """Reverts the auto OS update patch state on the machine to its system default value for given service, if applicable"""
        # type () -> None
        self.__init_auto_update_for_dnf_automatic()
        self.composite_logger.log("[DNF4] Reverting the current automatic OS patch state on the machine to its system default value for [Service={0}]".format(str(self.current_auto_os_update_service)))
        is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

        if not is_service_installed:
            self.composite_logger.log_debug("[DNF4] Machine default auto OS update service is not installed on the VM and hence no config to revert. [Service={0}]".format(str(self.current_auto_os_update_service)))
            return

        self.composite_logger.log_verbose("[DNF4] Logging current configuration settings for auto OS updates [Service={0}][Is_Service_Installed={1}][Machine_default_update_enable_on_reboot={2}][{3}={4}]][{5}={6}]".format(str(self.current_auto_os_update_service), str(is_service_installed), str(enable_on_reboot_value),
                    str(self.download_updates_identifier_text), str(download_updates_value), str(self.apply_updates_identifier_text), str(apply_updates_value)))

        image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()
        self.composite_logger.log_verbose("[DNF4] Logging system default configuration settings for auto OS updates. [Settings={0}]".format(str(image_default_patch_configuration_backup)))
        is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)

        if is_backup_valid:
            download_updates_value_from_backup = image_default_patch_configuration_backup[self.current_auto_os_update_service][self.download_updates_identifier_text]
            apply_updates_value_from_backup = image_default_patch_configuration_backup[self.current_auto_os_update_service][self.apply_updates_identifier_text]
            enable_on_reboot_value_from_backup = image_default_patch_configuration_backup[self.current_auto_os_update_service][self.enable_on_reboot_identifier_text]

            self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, download_updates_value_from_backup, self.auto_update_config_pattern_match_text)
            self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, apply_updates_value_from_backup, self.auto_update_config_pattern_match_text)
            if str(enable_on_reboot_value_from_backup).lower() == 'true':
                self.enable_auto_update_on_reboot()
        else:
            self.composite_logger.log_debug("[DNF4] Backup is invalid or does not exist for current service. Unable to revert auto OS patch settings to system default value. [Service={0}]".format(str(self.current_auto_os_update_service)))

    def enable_auto_update_on_reboot(self):
        """Enables machine default auto update on reboot"""
        # type () -> None
        command = self.enable_on_reboot_cmd
        self.composite_logger.log_verbose("[DNF4] Enabling auto update on reboot. [Command={0}] ".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != 0:
            self.composite_logger.log_error("[DNF4][ERROR] Error enabling auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("[DNF4] Enabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))

    def __get_image_default_patch_configuration_backup(self):
        """Get image_default_patch_configuration_backup file"""
        image_default_patch_configuration_backup = {}
        # Read existing backup since it also contains backup from other update services. We need to preserve any existing data within the backup file
        if self.image_default_patch_configuration_backup_exists():
            try:
                image_default_patch_configuration_backup = json.loads(self.env_layer.file_system.read_with_retry(self.image_default_patch_configuration_backup_path))
            except Exception as error:
                self.composite_logger.log_error("[DNF4] Unable to read backup for default patch state. Will attempt to re-write. [Exception={0}]".format(repr(error)))
        return image_default_patch_configuration_backup
    # endregion

    # region Reboot Management
    def is_reboot_pending(self):
        """Checks if there is a pending reboot on the machine."""
        self.composite_logger.log_verbose("[DNF4] Checking if reboot is required [Command={0}]".format(self.needs_restarting_with_flag))
        code, output = self.env_layer.run_command_output(self.needs_restarting_with_flag, False, False)
        reboot_required = (code == 1)
        self.composite_logger.log_debug("[DNF4] >  Outcome of reboot required check. [Command={0}][Code={1}][ComputedValueOfRebootRequired={2}]".format(str(self.needs_restarting_with_flag), str(code), str(reboot_required)))
        return reboot_required

    def do_processes_require_restart(self):
        """Fulfilling base class contract. Not needed for DNF4"""
        pass
    # endregion

    def set_security_esm_package_status(self, operation, packages):
        """Set the security-ESM classification for the esm packages. Only needed for apt. No-op for dnf4, yum and zypper."""
        return

    def separate_out_esm_packages(self, packages, package_versions):
        """Filter out packages from the list where the version matches the UA_ESM_REQUIRED string.
        Only needed for apt. No-op for dnf4, dnf5 yum and zypper"""
        esm_packages = []
        esm_package_versions = []
        esm_packages_found = False

        return packages, package_versions, esm_packages, esm_package_versions, esm_packages_found

    def get_package_install_expected_avg_time_in_seconds(self):
        return self.package_install_expected_avg_time_in_seconds

    # region Update certificates in factory defaults
    def try_install_mokutil(self):
        """Attempts to install mokutil"""
        pass

    def try_update_certs(self):
        """Attempts to update certificate status"""
        pass
    # endregion

