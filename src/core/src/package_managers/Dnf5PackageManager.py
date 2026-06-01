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

"""Dnf5PackageManager for Azure Linux and RHEL"""
import json
import re

from abc import ABCMeta
from core.src.bootstrap.Constants import Constants
from core.src.package_managers.PackageManager import PackageManager


class Dnf5PackageManager(PackageManager):
    """Implementation of Azure Linux/ RHEL package management operations"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(Dnf5PackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)
        # Repo refresh
        self.cmd_clean_cache = "sudo dnf5 -q clean expire-cache"
        self.cmd_repo_refresh = "sudo dnf5 -q check-update"

        #  Get updates and dependencies. dnf5 'list available <pkg>' returns BOTH installed and available versions.
        # This command is used for both version lookup and installed-state checks.
        self.single_package_installed_and_available_query = 'sudo dnf5 list available <PACKAGE-NAME> '
        self.single_package_upgrade_simulation_cmd = "sudo dnf5 install --assumeno --skip-broken "

        # Install update
        # dnf5 does not support --skip-broken for upgrade; uses full system upgrade
        # --allowerasing enables safe dependency resolution instead of skipping package
        self.single_package_upgrade_cmd = 'sudo dnf5 -y upgrade --allowerasing'

        # Support to check if reboot is required
        # dnf-utils not required (needs-restarting is built into dnf5)
        self.needs_restarting_with_flag = 'sudo LANG=en_US.UTF8 dnf5 needs-restarting'

        # DNF5 exit codes
        self.dnf_exitcode_ok = 0
        self.dnf_exitcode_updates_available = 100
        # Commands where 100 is expected
        self.commands_allowing_100_exitcode = ["check-update"]

        # DNF5 valid exit codes for simulation commands
        self.dnf5_simulation_valid_exit_codes = [0, 1]
        self.dnf5_dependency_failure_text = ["Skipping packages with broken dependencies", "Nothing to do."]
        self.dnf5_dependency_success_text = "Installing dependencies:"
        self.dnf5_dependency_exit_text = "Transaction Summary"
        self.dnf5_dependency_skip_text = "Package"

        self.dnf5_skip_unnecessary_text = ["Updating and loading repositories:", "Repositories loaded.", "Available packages", "Installed packages", "No matching packages"]
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.DNF)

        # Caching for updates
        self.all_updates_cached = []
        self.all_update_versions_cached = []

        # auto OS updates
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
        self.__init_constants_for_dnf5_automatic()
        self.STR_TOTAL_DOWNLOAD_SIZE = "Total download size: "
        self.package_install_expected_avg_time_in_seconds = 90

    __metaclass__ = ABCMeta  # For Python 3.0+, it changes to class Abstract(metaclass=ABCMeta)

    def __init_constants_for_dnf5_automatic(self):
        self.dnf5_automatic_configuration_service = 'systemctl cat dnf5-automatic.service'
        self.dnf5_automatic_install_check_cmd = 'rpm -qa | grep dnf5-plugin-automatic'
        self.dnf5_automatic_enable_on_reboot_check_cmd = 'systemctl is-enabled dnf5-automatic.timer'
        self.dnf5_automatic_disable_on_reboot_cmd = 'systemctl disable --now dnf5-automatic.timer'
        self.dnf5_automatic_enable_on_reboot_cmd = 'systemctl enable --now dnf5-automatic.timer'
        self.dnf5_automatic_override_dir = '/etc/systemd/system/dnf5-automatic.service.d'
        self.dnf5_automatic_override_file = '/etc/systemd/system/dnf5-automatic.service.d/override.conf'

        self.dnf5_automatic_download_updates_identifier_text = "download_updates"
        self.dnf5_automatic_apply_updates_identifier_text = "apply_updates"

        # ExecStart flag identifiers
        self.dnf5_automatic_download_updates_flag = '--downloadupdates'
        self.dnf5_automatic_no_download_updates_flag = '--no-downloadupdates'
        self.dnf5_automatic_apply_updates_flag = '--installupdates'
        self.dnf5_automatic_no_apply_updates_flag = '--no-installupdates'

        self.dnf5_automatic_enable_on_reboot_identifier_text = "enable_on_reboot"
        self.dnf5_automatic_installation_state_identifier_text = "installation_state"
        self.dnf5_auto_os_update_service = "dnf5-automatic"

    def __init_auto_update_for_dnf5_automatic(self):
        self.dnf5_automatic_configuration_file_path = self.dnf5_automatic_override_file
        self.os_patch_configuration_settings_read_cmd = self.dnf5_automatic_configuration_service
        self.download_updates_identifier_text = self.dnf5_automatic_download_updates_identifier_text
        self.apply_updates_identifier_text = self.dnf5_automatic_apply_updates_identifier_text
        self.enable_on_reboot_identifier_text = self.dnf5_automatic_enable_on_reboot_identifier_text
        self.installation_state_identifier_text = self.dnf5_automatic_installation_state_identifier_text
        self.enable_on_reboot_check_cmd = self.dnf5_automatic_enable_on_reboot_check_cmd
        self.enable_on_reboot_cmd = self.dnf5_automatic_enable_on_reboot_cmd
        self.install_check_cmd = self.dnf5_automatic_install_check_cmd
        self.current_auto_os_update_service = self.dnf5_auto_os_update_service

    def refresh_repo(self):
        self.composite_logger.log("[DNF5] Refreshing local repo...")
        self.invoke_package_manager(self.cmd_clean_cache)
        self.invoke_package_manager(self.cmd_repo_refresh)

    # AssessPatch method
    def invoke_package_manager_advanced(self, command, raise_on_exception=True):
        self.composite_logger.log_verbose("[DNF5] Invoking package manager. [Command={0}]".format(str(command)))
        # env_layer.run_command_output returns (code, output)
        code, out = self.env_layer.run_command_output(command, False, False)

        if code == self.dnf_exitcode_ok:
            self.composite_logger.log_debug('[DNF5] Invoked package manager. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))

        elif code == self.dnf_exitcode_updates_available and any(
                allowed_cmd in command for allowed_cmd in self.commands_allowing_100_exitcode):
            self.composite_logger.log_debug('[DNF5] Updates available. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
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
        packages, versions = self.extract_packages_and_versions_including_duplicates(output)
        packages, versions = self.dedupe_update_packages_to_get_latest_versions(packages, versions)
        return packages, versions

    def extract_packages_and_versions_including_duplicates(self, output):
        """Returns packages and versions from given output"""
        self.composite_logger.log_verbose("[DNF5] Extracting package and version data...")
        packages, versions = [], []

        lines = output.strip().split('\n')
        for line_index in range(0, len(lines)):

            line = lines[line_index].strip()
            # Do not install Obsoleting Packages. The obsoleting packages list comes towards end in the output.
            if line.startswith("Obsoleting"):
                break

            if not line or any(line.startswith(prefix) for prefix in self.dnf5_skip_unnecessary_text):
                continue

            filtered_line = re.split(r'\s+', lines[line_index].strip())

            # DNF check-update returns 3-column format: package.arch version repo
            #Sample output : rubygem-json.x86_64    2.13.2-2.azl4~20260501      azurelinux-base
            if len(filtered_line) == 3 and self.__is_package(filtered_line[0]):
                packages.append(self.get_product_name(filtered_line[0]))
                versions.append(filtered_line[1])
            else:
                self.composite_logger.log_verbose("[DNF5] > Inapplicable line ({0}): {1}".format(line_index, lines[line_index]))

        return packages, versions

    def dedupe_update_packages_to_get_latest_versions(self, packages, package_versions):
        """Remove duplicate packages and returns the latest/highest version of each package"""
        from core.src.core_logic.VersionComparator import VersionComparator
        deduped_packages = []
        deduped_package_versions = []
        version_comparator = VersionComparator()

        for index, package in enumerate(packages):
            if package in deduped_packages:
                deduped_package_version = deduped_package_versions[deduped_packages.index(package)]
                duplicate_package_version = package_versions[index]
                # use custom comparator output 0 (equal), -1 (deduped package version is the lower one), +1 (deduped package version is the greater one)
                is_deduped_package_latest = version_comparator.compare_versions(deduped_package_version, duplicate_package_version)
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

    # region Get Available Updates
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_verbose("[DNF5] Discovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug("[DNF5] Get all updates : [Cached={0}][PackagesCount={1}]".format(str(cached), len(self.all_updates_cached)))
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        out = self.invoke_package_manager(self.cmd_repo_refresh)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)
        self.composite_logger.log_debug("[DNF5] Get all updates : [Cached={0}][PackagesCount={1}]".format(str(False), len(self.all_updates_cached)))
        return self.all_updates_cached, self.all_update_versions_cached
    # endregion

     # AssessPatch method
    def get_security_updates(self):
        """Get missing security updates. NOTE: Classification based categorization of patches is not available in DNF5 as of now"""
        self.composite_logger.log_verbose("[DNF5] Discovering all packages as 'security' packages, since DNF5 does not support package classification...")
        security_packages, security_package_versions = self.get_all_updates(cached=False)
        self.composite_logger.log_debug("[DNF5] Discovered 'security' packages. [Count={0}]".format(len(security_packages)))
        return security_packages, security_package_versions

    # AssessPatch method
    def get_other_updates(self):
        """Get missing other updates."""
        self.composite_logger.log_verbose("[DNF5] Discovering 'other' packages...")
        return [], []

    def set_max_patch_publish_date(self, max_patch_publish_date=str()):
        pass

    # Install Patch method
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

    def get_product_name_and_arch(self, package_name):
        architectures = Constants.SUPPORTED_PACKAGE_ARCH
        for arch in architectures:
            if package_name.endswith(arch):
                return package_name[:-len(arch)], arch
        return package_name, None

    def install_updates_fail_safe(self, excluded_packages):
        pass

    # AssessPatch method
    def get_all_available_versions_of_package(self, package_name):
        """Returns a list of all the available versions of a package"""
        # Sample output format
        # rubygem-json.x86_64    2.13.2-2.azl4~20260501      azurelinux-base
        # rubygem-json.x86_64    2.14.0-1.azl4~20260501      azurelinux-base
        cmd = self.single_package_installed_and_available_query.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)
        return package_versions

    # AssessPatch method
    def is_package_version_installed(self, package_name, package_version):
        """Returns true if the specific package version is installed"""
        # Sample output format
        # rubygem-json.x86_64    2.13.2-2.azl4~20260501      @System
        self.composite_logger.log_verbose("[DNF5] Checking package install status. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
        cmd = self.single_package_installed_and_available_query.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)

        for index, package in enumerate(packages):
            if package == package_name and (package_versions[index] == package_version):
                self.composite_logger.log_debug("[DNF5] > Installed version match found. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
                return True
            else:
                self.composite_logger.log_verbose("[DNF5] > Did not match: " + package + " (" + package_versions[index] + ")")

        # sometimes packages are removed entirely from the system during installation of other packages
        # so let's check that the package is still needed before
        self.composite_logger.log_debug("[DNF5] > Installed version match NOT found. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
        return False

    def get_dependent_list(self, packages):
        """Returns dependent list for the list of packages
        Parameters:
        - packages (list): List of package names to get dependencies for
        Commands used:
        - sudo dnf install --assumeno --skip-broken <packages> (simulates installation to find dependencies without actually installing)
        Returns: List of dependency package names required for the input packages

        Sample output format: ( Failure case : Dependency Fails and exit code : 0 ) - Raise Exception
        # Updating and loading repositories:
        # Repositories loaded.
        # Problem: package perl-Getopt-Long-1:2.58-521.azl4~20260501.noarch from azurelinux-base requires perl(Pod::Usage) >= 1.14, but none of the providers can be installed
        #   - package perl-Pod-Usage-4:2.05-521.azl4~20260501.noarch from azurelinux-base requires perl(Pod::Text) >= 4, but none of the providers can be installed
        #   - package git-2.53.0-2.azl4~20260501.x86_64 from azurelinux-base requires perl(Getopt::Long), but none of the providers can be installed
        #   - package perl-podlators-1:6.0.2-521.azl4~20260501.noarch from azurelinux-base requires perl(Pod::Simple) >= 3.26, but none of the providers can be installed
        #   - conflicting requests
        #   - nothing provides perl(Text::Wrap) >= 98.112902 needed by perl-Pod-Simple-1:3.47-4.azl4~20260501.noarch from azurelinux-base
        #
        # Package           Arch   Version           Repository      Size
        # Skipping packages with broken dependencies:
        #  git              x86_64 2.53.0-2.azl4~202 azurelinux  56.4 KiB
        #  perl-Getopt-Long noarch 1:2.58-521.azl4~2 azurelinux 144.5 KiB
        #  perl-Pod-Simple  noarch 1:3.47-4.azl4~202 azurelinux 565.3 KiB
        #  perl-Pod-Usage   noarch 4:2.05-521.azl4~2 azurelinux  86.3 KiB
        #  perl-podlators   noarch 1:6.0.2-521.azl4~ azurelinux 317.5 KiB
        # Nothing to do.
        """
        package_names = " ".join(packages)
        cmd = self.single_package_upgrade_simulation_cmd + package_names
        code, output = self.env_layer.run_command_output(cmd, False, False)
        self.composite_logger.log_verbose("[DNF5] Dependency simulation. [Command={0}][Code={1}]".format(cmd, str(code)))
        if code not in self.dnf5_simulation_valid_exit_codes:
            self.composite_logger.log_error("[DNF5] Unexpected failure. [Command={0}][Code={1}][Output={2}]".format(cmd, str(code), output))
            raise Exception("DNF dependency simulation failed")

        if all(text in output for text in self.dnf5_dependency_failure_text):
            self.composite_logger.log_error("[DNF5] All packages skipped due to broken dependencies. [Command={0}]".format(cmd))
            raise Exception("Dependency resolution failed: all packages skipped")

        # Only go here for success case
        dependencies = self.extract_dependencies(output, packages)
        self.composite_logger.log_verbose("[DNF5] Resolved dependencies. [Command={0}][Packages={1}][DependencyCount={2}]".format(str(cmd), str(packages), len(dependencies)))
        return dependencies

    def extract_dependencies(self, output, packages):
        # Sample output format (Success case with dependencies , exit code : 1)
        # Command :  sudo dnf5 install --assumeno --skip-broken jq
        # Updating and loading repositories:
        # Repositories loaded.
        # Package                                                                                                       Arch                   Version                                                                                                       Repository                                                           Size
        # Installing:
        #  jq                                                                                                           x86_64                 1.8.1-3.azl4~20260501                                                                                         azurelinux-base                                                 457.7 KiB
        # Installing dependencies:
        #  oniguruma                                                                                                    x86_64                 6.9.10-3.azl4~20260501                                                                                        azurelinux-base                                                 763.1 KiB
        #
        # Transaction Summary:
        #  Installing:         2 packages
        #
        # Total size of inbound packages is 428 KiB. Need to download 428 KiB.
        # After this operation, 1 MiB extra will be used (install 1 MiB, remove 0 B).
        # Operation aborted by the user.
        dependencies = []
        package_arch_to_look_for = ["x86_64", "noarch", "i686", "aarch64"]

        lines = output.strip().splitlines()
        in_dependency_section = False

        for line_index in range(0, len(lines)):
            line_str = lines[line_index].strip()

            # Detect start of dependency section
            if line_str.startswith(self.dnf5_dependency_success_text):
                in_dependency_section = True
                continue

            #  Detect exit of dependency section
            if in_dependency_section and line_str.startswith(self.dnf5_dependency_exit_text):
                break

            if not in_dependency_section:
                continue

            # Skip empty/header lines
            if not line_str or line_str.startswith(self.dnf5_dependency_skip_text):
                self.composite_logger.log_verbose("[DNF5] > Skipping header/empty line: " + line_str)
                continue

            line = re.split(r'\s+', line_str)
            dependent_package_name = ""

            if self.is_valid_update(line, package_arch_to_look_for):
                dependent_package_name = self.get_product_name_with_arch(line, package_arch_to_look_for)
            else:
                self.composite_logger.log_verbose("[DNF5] > Inapplicable line: " + str(line))
                continue

            #  Remove input packages (support both pkg and pkg.arch)
            base_pkg = dependent_package_name.rsplit('.', 1)[0] if '.' in dependent_package_name else dependent_package_name

            if len(dependent_package_name) != 0 and dependent_package_name not in packages and base_pkg not in packages and dependent_package_name not in dependencies:
                self.composite_logger.log_verbose("[DNF5] > Dependency detected: " + dependent_package_name)
                dependencies.append(dependent_package_name)

        return dependencies

    def is_valid_update(self, package_details_in_output, package_arch_to_look_for):
        # Verifies whether the line under consideration (i.e. package_details_in_output) contains relevant package details.
        # package_details_in_output will be of the following format if it is valid
        #   Sample package details in DNF:
        #   python3-libs                       x86_64                    3.12.3-5.azl3                      azurelinux-official-base   36.05M                      10.52M
        return len(package_details_in_output) >= 3 and self.is_arch_in_package_details(package_details_in_output[1], package_arch_to_look_for)

    @staticmethod
    def is_arch_in_package_details(package_detail, package_arch_to_look_for):
        return len([p for p in package_arch_to_look_for if p in package_detail]) == 1

    def get_product_name(self, package_name):
        """Retrieve package name"""
        return package_name

    def get_product_name_with_arch(self, package_detail, package_arch_to_look_for):
        """
        Returns package name in format: name.arch
        Example:
            ["oniguruma", "x86_64", ...] -> "oniguruma.x86_64"
        """
        if len(package_detail) >= 2 and package_detail[1] in package_arch_to_look_for:
            return package_detail[0] + "." + package_detail[1]
        return ""

    def get_package_size(self, output):
        """Retrieves package size from installation output string
        Parameters:
        - output (string): The output string from DNF installation command
        Returns:
        - String: Package size (e.g., "10 M") or UNKNOWN_PACKAGE_SIZE if not found
        - Total download size : 10M
        """
        if "Nothing to do" not in output:
            lines = output.strip().split('\n')
            for line in lines:
                if line.find(self.STR_TOTAL_DOWNLOAD_SIZE) >= 0:
                    return line.replace(self.STR_TOTAL_DOWNLOAD_SIZE, "")

        return Constants.UNKNOWN_PACKAGE_SIZE

    # Install Patch method
    def install_security_updates_azgps_coordinated(self):
        """
        Install updates on Azure Linux 4 using dnf5.
        Note:
        - DNF5 does not support security classification.
        - This installs all available updates instead.
        """
        out, code = self.invoke_package_manager_advanced(self.single_package_upgrade_cmd,raise_on_exception=False)
        if code != 0:
            self.composite_logger.log_warning("[DNF5] Install failed. [Code={0}][Output={1}]".format(code, out))
        else:
            self.composite_logger.log_debug("[DNF5] Install completed successfully")
        return code, out

    def try_meet_azgps_coordinated_requirements(self):
        """
        no-op for now
        """
        pass

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
        self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "no")
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "no")
        self.disable_auto_update_on_reboot(self.dnf5_automatic_disable_on_reboot_cmd)

        self.composite_logger.log_debug("[DNF5] Successfully disabled auto OS updates using dnf5-automatic")


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
        """ JSON format for backup file:
                    {
                        "dnf5-automatic": {
                            "apply_updates": "yes/no/empty string",
                            "download_updates": "yes/no/empty string",
                            "enable_on_reboot": true/false,
                            "installation_state": true/false
                        }
                    } """
        try:
            self.composite_logger.log_debug("[DNF5] Ensuring there is a backup of the default patch state for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))

            image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()
            # verify if existing backup is valid if not, write to backup
            is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)

            if is_backup_valid:
                self.composite_logger.log_debug("[DNF5] Since extension has a valid backup, no need to log the current settings again. ""[Default Auto OS update settings={0}] [File path={1}]".format(str(image_default_patch_configuration_backup),self.image_default_patch_configuration_backup_path))
            else:
                self.composite_logger.log_debug("[DNF5] Since the backup is invalid, will add a new backup with the current auto OS update settings")
                self.composite_logger.log_debug("[DNF5] Fetching current auto OS update settings for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))

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

                self.composite_logger.log_debug("[DNF5] Logging default system configuration settings for auto OS updates. ""[Settings={0}] [Log file path={1}]".format(str(image_default_patch_configuration_backup),self.image_default_patch_configuration_backup_path))
                self.env_layer.file_system.write_with_retry(self.image_default_patch_configuration_backup_path,'{0}'.format(json.dumps(image_default_patch_configuration_backup)),mode='w+')

        except Exception as error:
            error_message = "[DNF5] Exception during fetching and logging default auto update settings on the machine. [Exception={0}]".format(repr(error))
            self.composite_logger.log_error(error_message)
            self.status_handler.add_error_to_status(error_message, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        """ Verifies if default auto update configurations, for a service under consideration, are saved in backup """
        return self.is_backup_valid_for_dnf5_automatic(image_default_patch_configuration_backup)

    def is_backup_valid_for_dnf5_automatic(self, image_default_patch_configuration_backup):
        if self.dnf5_auto_os_update_service in image_default_patch_configuration_backup \
                and self.dnf5_automatic_download_updates_identifier_text in image_default_patch_configuration_backup[
            self.dnf5_auto_os_update_service] \
                and self.dnf5_automatic_apply_updates_identifier_text in image_default_patch_configuration_backup[
            self.dnf5_auto_os_update_service] \
                and self.dnf5_automatic_enable_on_reboot_identifier_text in image_default_patch_configuration_backup[
            self.dnf5_auto_os_update_service] \
                and self.dnf5_automatic_installation_state_identifier_text in image_default_patch_configuration_backup[
            self.dnf5_auto_os_update_service]:
            self.composite_logger.log_debug("[DNF5] Extension has a valid backup for default dnf5-automatic configuration settings")
            return True
        else:
            self.composite_logger.log_debug("[DNF5] Extension does not have a valid backup for default dnf5-automatic configuration settings")
            return False

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value="no",
                                                  config_pattern_match_text=""):
        try:
            self.__init_auto_update_for_dnf5_automatic()
            _, _, current_download, current_apply = self.__get_current_auto_os_updates_setting_on_machine()

            download_bool = {"yes": True, "no": False}.get(current_download)
            apply_bool = {"yes": True, "no": False}.get(current_apply)

            new_val = True if value.lower() == "yes" else False

            if patch_configuration_sub_setting == self.download_updates_identifier_text:
                download_bool = new_val

            elif patch_configuration_sub_setting == self.apply_updates_identifier_text:
                apply_bool = new_val

            self.composite_logger.log_debug("[DNF5] Applying ExecStart override ""[download_updates={0}][apply_updates={1}]".format(download_bool, apply_bool))

            if download_bool is None and apply_bool is None:
                self.__remove_dnf5_automatic_execstart_override()
            else:
                self.__set_dnf5_automatic_execstart_flags(download_updates=download_bool,apply_updates=apply_bool)

        except Exception as error:
            error_msg = "[DNF5] Error applying ExecStart override via update_os_patch_configuration_sub_setting. [Error={0}]".format(repr(error))
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    # Post Install method/ Install Patch
    def is_reboot_pending(self):
        """Checks reboot requirement for Azure Linux 4 (dnf5)"""
        try:
            code, _ = self.env_layer.run_command_output(self.needs_restarting_with_flag, False, False)
            reboot_required = (code == 1)
            self.composite_logger.log_debug("[DNF5] > Reboot required (needs-restarting) = {0}".format(reboot_required))
            return reboot_required
        except Exception as error:
            self.composite_logger.log_error("[DNF5] Error checking reboot pending: " + repr(error))
        return True  # safe fallback

    # Post Install method / Install Patch
    def do_processes_require_restart(self):
        """
         DNF5 uses `needs-restarting` directly via is_reboot_pending(); separate implementation is not required.
        """
        pass

    def add_arch_dependencies(self, package_manager, package, version, packages, package_versions, package_and_dependencies, package_and_dependency_versions):
        """
         Unnecessary for DNF because the package manager already handles multi-architecture dependencies automatically
         Command Used to confirm above: sudo dnf -y install jq
        """
        pass

    def set_security_esm_package_status(self, operation, packages):
        """No-op for dnf, tdnf, yum and zypper """
        return

    def separate_out_esm_packages(self, packages, package_versions):
        """No-op for dnf, tdnf, yum and zypper """
        return

    def get_package_install_expected_avg_time_in_seconds(self):
        return self.package_install_expected_avg_time_in_seconds

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

        is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value = \
            self.__get_current_auto_os_updates_setting_on_machine()

        if not is_service_installed:
            self.composite_logger.log_debug("[DNF5] Machine default auto OS update service is not installed on the VM and hence no config to revert. [Service={0}]".format(str(self.current_auto_os_update_service)))
            return

        self.composite_logger.log_debug("[DNF5] Logging current configuration settings for auto OS updates ""[Service={0}][Is_Service_Installed={1}][Machine_default_update_enable_on_reboot={2}]".format(str(self.current_auto_os_update_service), str(is_service_installed),str(enable_on_reboot_value)))
        image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()

        self.composite_logger.log_debug("[DNF5] Logging system default configuration settings for auto OS updates. [Settings={0}]".format(str(image_default_patch_configuration_backup)))

        is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)

        if not is_backup_valid:
            self.composite_logger.log_debug("[DNF5] Since the backup is invalid or does not exist for current service, we won't be able to revert auto OS patch settings to their system default value. [Service={0}]".format(str(self.current_auto_os_update_service)))
            return

        backup = image_default_patch_configuration_backup[self.current_auto_os_update_service]

        download_updates_value_from_backup = backup[self.download_updates_identifier_text]
        apply_updates_value_from_backup = backup[self.apply_updates_identifier_text]

        download_bool = None
        apply_bool = None

        if download_updates_value_from_backup == "yes":
            download_bool = True
        elif download_updates_value_from_backup == "no":
            download_bool = False

        if apply_updates_value_from_backup == "yes":
            apply_bool = True
        elif apply_updates_value_from_backup == "no":
            apply_bool = False

        if download_bool is None and apply_bool is None:
            self.__remove_dnf5_automatic_execstart_override()
        else:
            self.__set_dnf5_automatic_execstart_flags(download_updates=download_bool,apply_updates=apply_bool)

        enable_on_reboot_value_from_backup = backup[self.enable_on_reboot_identifier_text]

        if str(enable_on_reboot_value_from_backup).lower() == 'true':
            self.enable_auto_update_on_reboot()
        else:
            self.disable_auto_update_on_reboot(self.dnf5_automatic_disable_on_reboot_cmd)

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
            self.composite_logger.log_debug("[DNF5] Enabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))

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

                ########## AUTO OS METHODS ########

    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        self.composite_logger.log("[DNF5] Fetching the current automatic OS patch state on the machine...")

        current_auto_os_patch_state_for_dnf5_automatic = self.__get_current_auto_os_patch_state_for_dnf5_automatic()

        self.composite_logger.log("[DNF5] OS patch state per auto OS update service: [dnf5-automatic={0}]".format(
            str(current_auto_os_patch_state_for_dnf5_automatic)))

        if current_auto_os_patch_state_for_dnf5_automatic == Constants.AutomaticOSPatchStates.ENABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.ENABLED
        elif current_auto_os_patch_state_for_dnf5_automatic == Constants.AutomaticOSPatchStates.DISABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.DISABLED
        else:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.UNKNOWN

        self.composite_logger.log_debug(
            "[DNF5] Overall Auto OS Patch State based on all auto OS update service states [OverallAutoOSPatchState={0}]".format(
                str(current_auto_os_patch_state)))
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

    def __get_extension_standard_value_for_apply_updates(self, apply_updates_value):
        if apply_updates_value.lower() == 'yes' or apply_updates_value.lower() == 'true':
            return self.apply_updates_enabled
        elif apply_updates_value.lower() == 'no' or apply_updates_value.lower() == 'false':
            return self.apply_updates_disabled
        else:
            return self.apply_updates_unknown

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

            is_service_installed = True
            enable_on_reboot_value = self.is_service_set_to_enable_on_reboot(self.enable_on_reboot_check_cmd)

            self.composite_logger.log_debug("[DNF5] Reading dnf5 automatic config values...")
            service_text = self.invoke_package_manager(self.os_patch_configuration_settings_read_cmd)

            # derive apply_updates
            if self.dnf5_automatic_no_apply_updates_flag in service_text:
                apply_updates_value = "no"
            elif self.dnf5_automatic_apply_updates_flag in service_text:
                apply_updates_value = "yes"
                download_updates_value = "yes"

            # derive download_updates
            if download_updates_value == "":
                if self.dnf5_automatic_no_download_updates_flag in service_text:
                    download_updates_value = "no"
                elif self.dnf5_automatic_download_updates_flag in service_text:
                    download_updates_value = "yes"


            if download_updates_value == "":
                self.composite_logger.log_debug("[DNF5] No explicit value set for [{0}] in ExecStart".format(self.download_updates_identifier_text))
            else:
                self.composite_logger.log_verbose("[DNF5] Current value set for [{0}={1}]".format(self.download_updates_identifier_text,download_updates_value))

            if apply_updates_value == "":
                self.composite_logger.log_debug("[DNF5] No explicit value set for [{0}] in ExecStart".format(self.apply_updates_identifier_text))
            else:
                self.composite_logger.log_verbose("[DNF5] Current value set for [{0}={1}]".format(self.apply_updates_identifier_text,apply_updates_value))

            return is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value

        except Exception as error:
            raise Exception("[DNF5] Error fetching current auto OS update settings. [Exception={0}]".format(repr(error)))

    def is_auto_update_service_installed(self, install_check_cmd):
        """ Checks if the auto update service is installed on the VM """
        code, out = self.env_layer.run_command_output(install_check_cmd, False, False)
        self.composite_logger.log_debug("[DNF5] Checked if auto update service is installed. [Command={0}][Code={1}][Output={2}]".format(install_check_cmd, str(code), out))
        if len(out.strip()) > 0 and code == 0:
            self.composite_logger.log_debug("[DNF5] > Auto OS update service is installed on the machine")
            return True
        else:
            self.composite_logger.log_debug("[DNF5] > Auto OS update service is NOT installed on the machine")
            return False

    def is_service_set_to_enable_on_reboot(self, command):
        """ Checking if auto update is set to enable on reboot on the machine. An enable_on_reboot service will be activated (if currently inactive) on machine reboot """
        code, out = self.env_layer.run_command_output(command, False, False)
        self.composite_logger.log_debug("[DNF5] Checked if auto update service is set to enable on reboot. [Code={0}][Out={1}]".format(str(code), out))
        if len(out.strip()) > 0 and code == 0 and out.strip() == "enabled" :
            self.composite_logger.log_debug("[DNF5] > Auto OS update service will enable on reboot")
            return True
        self.composite_logger.log_debug("[DNF5] > Auto OS update service will NOT enable on reboot")
        return False

    def __set_dnf5_automatic_execstart_flags(self, download_updates=None, apply_updates=None):
        try:
            if download_updates is None and apply_updates is None:
                self.remove_dnf5_automatic_execstart_override()
                return

            flags = ["/usr/bin/dnf5", "automatic", "--timer"]

            if apply_updates is True:
                flags.append("--installupdates")

            elif apply_updates is False:
                if download_updates is True:
                    flags.append("--downloadupdates")
                    flags.append("--no-installupdates")
                elif download_updates is False:
                    flags.append("--no-downloadupdates")
                    flags.append("--no-installupdates")
                else:
                    flags.append("--no-installupdates")
            else:
                if download_updates is True:
                    flags.append("--downloadupdates")
                elif download_updates is False:
                    flags.append("--no-downloadupdates")

            override_text = "[Service]\nExecStart=\nExecStart={0}\n".format(" ".join(flags))

            self.env_layer.run_command_output("sudo mkdir -p {0}".format(self.dnf5_automatic_override_dir), False, False)
            self.env_layer.file_system.write_with_retry(self.dnf5_automatic_override_file, override_text, mode='w+')
            self.env_layer.run_command_output("sudo systemctl daemon-reload", False, False)
            self.composite_logger.log_debug("[DNF5] Wrote override. [ExecStart={0}]".format(" ".join(flags)))

        except Exception as error:
            error_msg = "[DNF5] Error writing override. [Exception={0}]".format(repr(error))
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(
                error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR
            )
            raise

    def __remove_dnf5_automatic_execstart_override(self):
        """Removes systemd override file for dnf5-automatic if it exists."""
        try:
            try:
                self.env_layer.file_system.write_with_retry(self.dnf5_automatic_override_file,"",mode='w+')
            except Exception:
                pass

            self.env_layer.run_command_output("sudo systemctl daemon-reload",False,False)
            self.composite_logger.log_debug("[DNF5] Cleared dnf5 automatic override file. [File={0}]".format(self.dnf5_automatic_override_file))

        except Exception as error:
            error_msg = "[DNF5] Error removing dnf5 automatic override. [Exception={0}]".format(repr(error))
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    # endregion
