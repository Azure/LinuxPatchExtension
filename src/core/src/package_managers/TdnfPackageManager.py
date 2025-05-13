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

"""TdnfPackageManager for Azure Linux"""
import json
import os
import re

from core.src.core_logic.VersionComparator import VersionComparator
from core.src.package_managers.PackageManager import PackageManager
from core.src.bootstrap.Constants import Constants


class TdnfPackageManager(PackageManager):
    """Implementation of Azure Linux package management operations"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(TdnfPackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)
        # Repo refresh
        self.cmd_clean_cache = "sudo tdnf clean expire-cache"
        self.cmd_repo_refresh = "sudo tdnf -q list updates"

        # fetch snapshottime from health_store_id
        self.snapshot_posix_time = self.__get_posix_time(execution_config.max_patch_publish_date, env_layer)

        # Support to get updates and their dependencies
        self.tdnf_check = self.__generate_command_with_snapshottime('sudo tdnf -q list updates <SNAPSHOTTIME>', self.snapshot_posix_time)
        self.single_package_check_versions = self.__generate_command_with_snapshottime('sudo tdnf list available <PACKAGE-NAME> <SNAPSHOTTIME>', self.snapshot_posix_time)
        self.single_package_check_installed = self.__generate_command_with_snapshottime('sudo tdnf list installed <PACKAGE-NAME> <SNAPSHOTTIME>', self.snapshot_posix_time)
        self.single_package_upgrade_simulation_cmd = self.__generate_command_with_snapshottime('sudo tdnf install --assumeno --skip-broken <SNAPSHOTTIME>', self.snapshot_posix_time)

        # Install update
        self.single_package_upgrade_cmd = self.__generate_command_with_snapshottime('sudo tdnf -y install --skip-broken <SNAPSHOTTIME>', self.snapshot_posix_time)

        # Package manager exit code(s)
        self.tdnf_exitcode_ok = 0
        self.tdnf_exitcode_on_no_action_for_install_update = 8
        self.commands_expecting_no_action_exitcode = [self.single_package_upgrade_simulation_cmd]

        # Support to check for processes requiring restart
        self.dnf_utils_prerequisite = 'sudo tdnf -y install dnf-utils'
        self.needs_restarting_with_flag = 'sudo LANG=en_US.UTF8 needs-restarting -r'

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
        self.__init_constants_for_dnf_automatic()

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.TDNF)
        self.STR_TOTAL_DOWNLOAD_SIZE = "Total download size: "
        self.version_comparator = VersionComparator()

        # if an Auto Patching request comes in on a Azure Linux machine with Security and/or Critical classifications selected, we need to install all patches, since classifications aren't available in Azure Linux repository
        installation_included_classifications = [] if execution_config.included_classifications_list is None else execution_config.included_classifications_list
        if execution_config.health_store_id is not str() and execution_config.operation.lower() == Constants.INSTALLATION.lower() \
                and (env_layer.is_distro_azure_linux(str(env_layer.platform.linux_distribution()))) \
                and 'Critical' in installation_included_classifications and 'Security' in installation_included_classifications:
            self.composite_logger.log_debug("Updating classifications list to install all patches for the Auto Patching request since classification based patching is not available on Azure Linux machines")
            execution_config.included_classifications_list = [Constants.PackageClassification.CRITICAL, Constants.PackageClassification.SECURITY, Constants.PackageClassification.OTHER]

        self.package_install_expected_avg_time_in_seconds = 90  # Setting a default value of 90 seconds as the avg time to install a package using tdnf, might be changed later if needed.

    def refresh_repo(self):
        self.composite_logger.log("[TDNF] Refreshing local repo...")
        self.invoke_package_manager(self.cmd_clean_cache)
        self.invoke_package_manager(self.cmd_repo_refresh)

    # region Strict SDP using SnapshotTime
    def __get_posix_time(self, datetime_to_convert, env_layer):
        """Converts date str received to POSIX time string"""
        posix_time = str()
        datetime_to_convert_format = '%Y%m%dT%H%M%SZ'
        self.composite_logger.log_debug("[TDNF] Getting POSIX time from given datetime. [DateTimeToConvert={0}][DateTimeStringFormat={1}]".format(str(datetime_to_convert), datetime_to_convert_format))
        try:
            if datetime_to_convert != str():
                posix_time = env_layer.datetime.datetime_string_to_posix_time(datetime_to_convert, datetime_to_convert_format)
        except Exception as error:
            self.composite_logger.log_debug("[TDNF] Could not fetch POSIX time from given datetime. [DateTimeToConvert={0}][DateTimeStringFormat={1}][ComputedPosixTime={2}][Error={3}]".format(str(datetime_to_convert), datetime_to_convert_format, posix_time, repr(error)))

        self.composite_logger.log_debug("[TDNF] Computed POSIX time from given datetime. [DateTimeToConvert={0}][DateTimeStringFormat={1}][ComputedPosixTime={2}]".format(str(datetime_to_convert), datetime_to_convert_format, posix_time))
        return posix_time

    @staticmethod
    def __generate_command_with_snapshottime(command_template, snapshotposixtime=str()):
        # type: (str, str) -> str
        """ Prepares a standard command to use snapshottime."""

        # finds azlinux major version, and tdnf version
            # if azlinux < 3.0.20241005
                # no snaphottime
            # if azlinux >= 3.0.20241005 and tdnf < 3.5.8-3
                # 1 attempt to update tdnf
                    # if succeeds, add snapshottime
                    # if fails, no snapshottime
            # if azlinux >= 3.0.20241005 and tdnf >= 3.5.8-3
                # add snapshottime

        if snapshotposixtime == str():
            return command_template.replace('<SNAPSHOTTIME>', str())
        else:
            return command_template.replace('<SNAPSHOTTIME>', ('--snapshottime={0}'.format(str(snapshotposixtime))))
    # endregion

    # region Get Available Updates
    def invoke_package_manager_advanced(self, command, raise_on_exception=True):
        """Get missing updates using the command input"""
        self.composite_logger.log_verbose("[TDNF] Invoking package manager. [Command={0}]".format(str(command)))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code is self.tdnf_exitcode_ok or \
            (any(command_expecting_no_action_exitcode in command for command_expecting_no_action_exitcode in self.commands_expecting_no_action_exitcode) and
             code is self.tdnf_exitcode_on_no_action_for_install_update):
            self.composite_logger.log_debug('[TDNF] Invoked package manager. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
        else:
            self.composite_logger.log_warning('[ERROR] Customer environment error. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
            error_msg = "Customer environment error: Investigate and resolve unexpected return code ({0}) from package manager on command: {1}".format(str(code), command)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            if raise_on_exception:
                raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

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
        """Get missing security updates. NOTE: Classification based categorization of patches is not available in Azure Linux as of now"""
        self.composite_logger.log_verbose("[TDNF] Discovering 'security' packages...")
        security_packages, security_package_versions = [], []
        self.composite_logger.log_debug("[TDNF] Discovered 'security' packages. [Count={0}]".format(len(security_packages)))
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates.
        NOTE: This function will return all available packages since Azure Linux does not support package classification in it's repository"""
        self.composite_logger.log_verbose("[TDNF] Discovering 'other' packages...")
        other_packages, other_package_versions = [], []

        all_packages, all_package_versions = self.get_all_updates(True)

        self.composite_logger.log_debug("[TDNF] Discovered 'other' packages. [Count={0}]".format(len(other_packages)))
        return all_packages, all_package_versions

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
        self.composite_logger.log_verbose("[TDNF] Extracting package and version data...")
        packages, versions = [], []

        lines = output.strip().split('\n')

        for line_index in range(0, len(lines)):
            # Do not install Obsoleting Packages. The obsoleting packages list comes towards end in the output.
            if lines[line_index].strip().startswith("Obsoleting"):
                break

            line = re.split(r'\s+', lines[line_index].strip())

            # If we run into a length of 3, we'll accept it and continue
            if len(line) == 3 and self.__is_package(line[0]):
                packages.append(self.get_product_name(line[0]))
                versions.append(line[1])
            else:
                self.composite_logger.log_verbose("[TDNF] > Inapplicable line (" + str(line_index) + "): " + lines[line_index])

        return packages, versions

    def dedupe_update_packages_to_get_latest_versions(self, packages, package_versions):
        """Remove duplicate packages and returns the latest/highest version of each package """
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
        # Using a list comprehension to determine if chunk is a package
        package_extensions = Constants.SUPPORTED_PACKAGE_ARCH
        return len([p for p in package_extensions if p in chunk]) == 1
    # endregion
    # endregion

    # region Install Updates
    def get_composite_package_identifier(self, package, package_version):
        package_without_arch, arch = self.get_product_name_and_arch(package)
        package_identifier = package_without_arch + '-' + str(package_version)
        if arch is not None:
            package_identifier += arch
        return package_identifier

    def install_updates_fail_safe(self, excluded_packages):
        return

    def install_security_updates_azgps_coordinated(self):
        pass
    # endregion

    # region Package Information
    def get_all_available_versions_of_package(self, package_name):
        """ Returns a list of all the available versions of a package """
        # Sample output format
        # Loaded plugin: tdnfrepogpgcheck
        # azurelinux-repos-shared.noarch                                                                 3.0-3.azl3                                   azurelinux-official-base
        # azurelinux-repos-shared.noarch                                                                 3.0-4.azl3                                   azurelinux-official-base
        cmd = self.single_package_check_versions.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)
        return package_versions

    def is_package_version_installed(self, package_name, package_version):
        """ Returns true if the specific package version is installed """
        # Sample output format
        # Loaded plugin: tdnfrepogpgcheck
        # azurelinux-repos-shared.noarch                                                                 3.0-3.azl3                                                    @System
        self.composite_logger.log_verbose("[TDNF] Checking package install status. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
        cmd = self.single_package_check_installed.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)

        for index, package in enumerate(packages):
            if package == package_name and (package_versions[index] == package_version):
                self.composite_logger.log_debug("[TDNF] > Installed version match found. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
                return True
            else:
                self.composite_logger.log_verbose("[TDNF] > Did not match: " + package + " (" + package_versions[index] + ")")

        # sometimes packages are removed entirely from the system during installation of other packages
        # so let's check that the package is still needed before
        self.composite_logger.log_debug("[TDNF] > Installed version match NOT found. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
        return False

    def extract_dependencies(self, output, packages):
        # Extracts dependent packages from output.
        # sample output
        # Loaded plugin: tdnfrepogpgcheck
        #
        # Upgrading:
        # python3                            x86_64                    3.12.3-5.azl3                      azurelinux-official-base   44.51k                      36.89k
        # python3-curses                     x86_64                    3.12.3-5.azl3                      azurelinux-official-base  165.62k                      71.64k
        # python3-libs                       x86_64                    3.12.3-5.azl3                      azurelinux-official-base   36.05M                      10.52M
        #
        # Total installed size:  36.26M
        # Total download size:  10.62M
        # Error(1032) : Operation aborted.
        dependencies = []
        package_arch_to_look_for = ["x86_64", "noarch", "i686", "aarch64"]  # if this is changed, review Constants

        lines = output.strip().splitlines()

        for line_index in range(0, len(lines)):
            line = re.split(r'\s+', lines[line_index].strip())
            dependent_package_name = ""

            if self.is_valid_update(line, package_arch_to_look_for):
                dependent_package_name = self.get_product_name_with_arch(line, package_arch_to_look_for)
            else:
                self.composite_logger.log_verbose("[TDNF] > Inapplicable line: " + str(line))
                continue

            if len(dependent_package_name) != 0 and dependent_package_name not in packages and dependent_package_name not in dependencies:
                self.composite_logger.log_verbose("[TDNF] > Dependency detected: " + dependent_package_name)
                dependencies.append(dependent_package_name)

        return dependencies

    def add_arch_dependencies(self, package_manager, package, version, packages, package_versions, package_and_dependencies, package_and_dependency_versions):
        """
        Add the packages with same name as that of input parameter package but with different architectures from packages list to the list package_and_dependencies.
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
        package_name_without_arch = package_manager.get_product_name_without_arch(package)
        for possible_arch_dependency, possible_arch_dependency_version in zip(packages, package_versions):
            if package_manager.get_product_name_without_arch(possible_arch_dependency) == package_name_without_arch and possible_arch_dependency not in package_and_dependencies and possible_arch_dependency_version == version:
                package_and_dependencies.append(possible_arch_dependency)
                package_and_dependency_versions.append(possible_arch_dependency_version)

    def is_valid_update(self, package_details_in_output, package_arch_to_look_for):
        # Verifies whether the line under consideration (i.e. package_details_in_output) contains relevant package details.
        # package_details_in_output will be of the following format if it is valid
        #   Sample package details in TDNF:
        #   python3-libs                       x86_64                    3.12.3-5.azl3                      azurelinux-official-base   36.05M                      10.52M
        return len(package_details_in_output) == 6 and self.is_arch_in_package_details(package_details_in_output[1], package_arch_to_look_for)

    @staticmethod
    def is_arch_in_package_details(package_detail, package_arch_to_look_for):
        # Using a list comprehension to determine if chunk is a package
        return len([p for p in package_arch_to_look_for if p in package_detail]) == 1

    def get_dependent_list(self, packages):
        """Returns dependent List for the list of packages"""
        package_names = ""
        for index, package in enumerate(packages):
            if index != 0:
                package_names += ' '
            package_names += package

        self.composite_logger.log_verbose("[TDNF] Resolving dependencies. [Command={0}]".format(str(self.single_package_upgrade_simulation_cmd + package_names)))
        output = self.invoke_package_manager(self.single_package_upgrade_simulation_cmd + package_names)
        dependencies = self.extract_dependencies(output, packages)
        self.composite_logger.log_verbose("[TDNF] Resolved dependencies. [Packages={0}][DependencyCount={1}]".format(str(packages), len(dependencies)))
        return dependencies

    def get_product_name(self, package_name):
        """Retrieve package name """
        return package_name

    def get_product_name_and_arch(self, package_name):
        """Splits out product name and architecture - if this is changed, modify in PackageFilter also"""
        architectures = Constants.SUPPORTED_PACKAGE_ARCH
        for arch in architectures:
            if package_name.endswith(arch):
                return package_name[:-len(arch)], arch
        return package_name, None

    def get_product_name_without_arch(self, package_name):
        """Retrieve product name only"""
        product_name, arch = self.get_product_name_and_arch(package_name)
        return product_name

    def get_product_arch(self, package_name):
        """Retrieve product architecture only"""
        product_name, arch = self.get_product_name_and_arch(package_name)
        return arch

    def get_product_name_with_arch(self, package_detail, package_arch_to_look_for):
        """Retrieve product name with arch separated by '.'. Note: This format is default in tdnf. Refer samples noted within func extract_dependencies() for more clarity"""
        return package_detail[0] + "." + package_detail[1] if package_detail[1] in package_arch_to_look_for else package_detail[1]

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
    def __init_constants_for_dnf_automatic(self):
        self.dnf_automatic_configuration_file_path = '/etc/dnf/automatic.conf'
        self.dnf_automatic_install_check_cmd = 'systemctl list-unit-files --type=service | grep dnf-automatic.service'  # list-unit-files returns installed services, ref: https://www.freedesktop.org/software/systemd/man/systemctl.html#Unit%20File%20Commands
        self.dnf_automatic_enable_on_reboot_check_cmd = 'systemctl is-enabled dnf-automatic.timer'
        self.dnf_automatic_disable_on_reboot_cmd = 'systemctl disable dnf-automatic.timer'
        self.dnf_automatic_enable_on_reboot_cmd = 'systemctl enable dnf-automatic.timer'
        self.dnf_automatic_config_pattern_match_text = ' = (no|yes)'
        self.dnf_automatic_download_updates_identifier_text = 'download_updates'
        self.dnf_automatic_apply_updates_identifier_text = 'apply_updates'
        self.dnf_automatic_enable_on_reboot_identifier_text = "enable_on_reboot"
        self.dnf_automatic_installation_state_identifier_text = "installation_state"
        self.dnf_auto_os_update_service = "dnf-automatic"

    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        self.composite_logger.log("[TDNF] Fetching the current automatic OS patch state on the machine...")

        current_auto_os_patch_state_for_dnf_automatic = self.__get_current_auto_os_patch_state_for_dnf_automatic()

        self.composite_logger.log("[TDNF] OS patch state per auto OS update service: [dnf-automatic={0}]".format(str(current_auto_os_patch_state_for_dnf_automatic)))

        if current_auto_os_patch_state_for_dnf_automatic == Constants.AutomaticOSPatchStates.ENABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.ENABLED
        elif current_auto_os_patch_state_for_dnf_automatic == Constants.AutomaticOSPatchStates.DISABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.DISABLED
        else:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.UNKNOWN

        self.composite_logger.log_debug("[TDNF] Overall Auto OS Patch State based on all auto OS update service states [OverallAutoOSPatchState={0}]".format(str(current_auto_os_patch_state)))
        return current_auto_os_patch_state

    def __get_current_auto_os_patch_state_for_dnf_automatic(self):
        """ Gets current auto OS update patch state for dnf-automatic """
        self.composite_logger.log_debug("[TDNF] Fetching current automatic OS patch state in dnf-automatic service. This includes checks on whether the service is installed, current auto patch enable state and whether it is set to enable on reboot")
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
        """ Initializes all generic auto OS update variables with the config values for dnf automatic service """
        self.os_patch_configuration_settings_file_path = self.dnf_automatic_configuration_file_path
        self.download_updates_identifier_text = self.dnf_automatic_download_updates_identifier_text
        self.apply_updates_identifier_text = self.dnf_automatic_apply_updates_identifier_text
        self.enable_on_reboot_identifier_text = self.dnf_automatic_enable_on_reboot_identifier_text
        self.installation_state_identifier_text = self.dnf_automatic_installation_state_identifier_text
        self.auto_update_config_pattern_match_text = self.dnf_automatic_config_pattern_match_text
        self.enable_on_reboot_check_cmd = self.dnf_automatic_enable_on_reboot_check_cmd
        self.enable_on_reboot_cmd = self.dnf_automatic_enable_on_reboot_cmd
        self.install_check_cmd = self.dnf_automatic_install_check_cmd
        self.current_auto_os_update_service = self.dnf_auto_os_update_service

    def __get_current_auto_os_updates_setting_on_machine(self):
        """ Gets all the update settings related to auto OS updates currently set on the machine """
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

            self.composite_logger.log_debug("[TDNF] Checking if auto updates are currently enabled...")
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
                self.composite_logger.log_debug("[TDNF] Machine did not have any value set for [Setting={0}]".format(str(self.download_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("[TDNF] Current value set for [{0}={1}]".format(str(self.download_updates_identifier_text), str(download_updates_value)))

            if apply_updates_value == "":
                self.composite_logger.log_debug("[TDNF] Machine did not have any value set for [Setting={0}]".format(str(self.apply_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("[TDNF] Current value set for [{0}={1}]".format(str(self.apply_updates_identifier_text), str(apply_updates_value)))

            return is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value

        except Exception as error:
            raise Exception("[TDNF] Error occurred in fetching current auto OS update settings from the machine. [Exception={0}]".format(repr(error)))

    def is_auto_update_service_installed(self, install_check_cmd):
        """ Checks if the auto update service is enable_on_reboot on the VM """
        code, out = self.env_layer.run_command_output(install_check_cmd, False, False)
        self.composite_logger.log_debug("[TDNF] Checked if auto update service is installed. [Command={0}][Code={1}][Output={2}]".format(install_check_cmd, str(code), out))
        if len(out.strip()) > 0 and code == 0:
            self.composite_logger.log_debug("[TDNF] > Auto OS update service is installed on the machine")
            return True
        else:
            self.composite_logger.log_debug("[TDNF] > Auto OS update service is NOT installed on the machine")
            return False

    def is_service_set_to_enable_on_reboot(self, command):
        """ Checking if auto update is enable_on_reboot on the machine. An enable_on_reboot service will be activated (if currently inactive) on machine reboot """
        code, out = self.env_layer.run_command_output(command, False, False)
        self.composite_logger.log_debug("[TDNF] Checked if auto update service is set to enable on reboot. [Code={0}][Out={1}]".format(str(code), out))
        if len(out.strip()) > 0 and code == 0 and 'enabled' in out:
            self.composite_logger.log_debug("[TDNF] > Auto OS update service will enable on reboot")
            return True
        self.composite_logger.log_debug("[TDNF] > Auto OS update service will NOT enable on reboot")
        return False

    def __get_extension_standard_value_for_apply_updates(self, apply_updates_value):
        if apply_updates_value.lower() == 'yes' or apply_updates_value.lower() == 'true':
            return self.apply_updates_enabled
        elif apply_updates_value.lower() == 'no' or apply_updates_value.lower() == 'false':
            return self.apply_updates_disabled
        else:
            return self.apply_updates_unknown

    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enabled and logs the default settings the machine comes with """
        try:
            self.composite_logger.log_verbose("[TDNF] Disabling auto OS updates in all identified services...")
            self.disable_auto_os_update_for_dnf_automatic()
            self.composite_logger.log_debug("[TDNF] Successfully disabled auto OS updates")

        except Exception as error:
            self.composite_logger.log_error("[TDNF] Could not disable auto OS updates. [Error={0}]".format(repr(error)))
            raise

    def disable_auto_os_update_for_dnf_automatic(self):
        """ Disables auto OS updates, using dnf-automatic service, and logs the default settings the machine comes with """
        self.composite_logger.log_verbose("[TDNF] Disabling auto OS updates using dnf-automatic")
        self.__init_auto_update_for_dnf_automatic()

        self.backup_image_default_patch_configuration_if_not_exists()

        if not self.is_auto_update_service_installed(self.dnf_automatic_install_check_cmd):
            self.composite_logger.log_debug("[TDNF] Cannot disable as dnf-automatic is not installed on the machine")
            return

        self.composite_logger.log_verbose("[TDNF] Preemptively disabling auto OS updates using dnf-automatic")
        self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "no", self.dnf_automatic_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "no", self.dnf_automatic_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.dnf_automatic_disable_on_reboot_cmd)

        self.composite_logger.log_debug("[TDNF] Successfully disabled auto OS updates using dnf-automatic")

    def disable_auto_update_on_reboot(self, command):
        self.composite_logger.log_verbose("[TDNF] Disabling auto update on reboot. [Command={0}] ".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != 0:
            self.composite_logger.log_error("[TDNF][ERROR] Error disabling auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("[TDNF] Disabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))

    def backup_image_default_patch_configuration_if_not_exists(self):
        """ Records the default system settings for auto OS updates within patch extension artifacts for future reference.
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
            self.composite_logger.log_debug("[TDNF] Ensuring there is a backup of the default patch state for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
            image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()

            # verify if existing backup is valid if not, write to backup
            is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)
            if is_backup_valid:
                self.composite_logger.log_debug("[TDNF] Since extension has a valid backup, no need to log the current settings again. [Default Auto OS update settings={0}] [File path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
            else:
                self.composite_logger.log_debug("[TDNF] Since the backup is invalid, will add a new backup with the current auto OS update settings")
                self.composite_logger.log_debug("[TDNF] Fetching current auto OS update settings for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
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

                self.composite_logger.log_debug("[TDNF] Logging default system configuration settings for auto OS updates. [Settings={0}] [Log file path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
                self.env_layer.file_system.write_with_retry(self.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(image_default_patch_configuration_backup)), mode='w+')
        except Exception as error:
            error_message = "[TDNF] Exception during fetching and logging default auto update settings on the machine. [Exception={0}]".format(repr(error))
            self.composite_logger.log_error(error_message)
            self.status_handler.add_error_to_status(error_message, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        """ Verifies if default auto update configurations, for a service under consideration, are saved in backup """
        return self.is_backup_valid_for_dnf_automatic(image_default_patch_configuration_backup)

    def is_backup_valid_for_dnf_automatic(self, image_default_patch_configuration_backup):
        if self.dnf_auto_os_update_service in image_default_patch_configuration_backup \
                and self.dnf_automatic_download_updates_identifier_text in image_default_patch_configuration_backup[self.dnf_auto_os_update_service] \
                and self.dnf_automatic_apply_updates_identifier_text in image_default_patch_configuration_backup[self.dnf_auto_os_update_service] \
                and self.dnf_automatic_enable_on_reboot_identifier_text in image_default_patch_configuration_backup[self.dnf_auto_os_update_service] \
                and self.dnf_automatic_installation_state_identifier_text in image_default_patch_configuration_backup[self.dnf_auto_os_update_service]:
            self.composite_logger.log_debug("[TDNF] Extension has a valid backup for default dnf-automatic configuration settings")
            return True
        else:
            self.composite_logger.log_debug("[TDNF] Extension does not have a valid backup for default dnf-automatic configuration settings")
            return False

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value="no", config_pattern_match_text=""):
        """ Updates (or adds if it doesn't exist) the given patch_configuration_sub_setting with the given value in os_patch_configuration_settings_file """
        try:
            # note: adding space between the patch_configuration_sub_setting and value since, we will have to do that if we have to add a patch_configuration_sub_setting that did not exist before
            self.composite_logger.log_debug("[TDNF] Updating system configuration settings for auto OS updates. [Patch Configuration Sub Setting={0}] [Value={1}]".format(str(patch_configuration_sub_setting), value))
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
            error_msg = "[TDNF] Error occurred while updating system configuration settings for auto OS updates. [Patch Configuration={0}] [Error={1}]".format(str(patch_configuration_sub_setting), repr(error))
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def revert_auto_os_update_to_system_default(self):
        """ Reverts the auto OS update patch state on the machine to its system default value, if one exists in our backup file """
        # type () -> None
        self.composite_logger.log("[TDNF] Reverting the current automatic OS patch state on the machine to its system default value before patchmode was set to 'AutomaticByPlatform'")
        self.revert_auto_os_update_to_system_default_for_dnf_automatic()
        self.composite_logger.log_debug("[TDNF] Successfully reverted auto OS updates to system default config")

    def revert_auto_os_update_to_system_default_for_dnf_automatic(self):
        """ Reverts the auto OS update patch state on the machine to its system default value for given service, if applicable """
        # type () -> None
        self.__init_auto_update_for_dnf_automatic()
        self.composite_logger.log("[TDNF] Reverting the current automatic OS patch state on the machine to its system default value for [Service={0}]".format(str(self.current_auto_os_update_service)))
        is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

        if not is_service_installed:
            self.composite_logger.log_debug("[TDNF] Machine default auto OS update service is not installed on the VM and hence no config to revert. [Service={0}]".format(str(self.current_auto_os_update_service)))
            return

        self.composite_logger.log_debug("[TDNF] Logging current configuration settings for auto OS updates [Service={0}][Is_Service_Installed={1}][Machine_default_update_enable_on_reboot={2}][{3}={4}]][{5}={6}]"
                                        .format(str(self.current_auto_os_update_service), str(is_service_installed), str(enable_on_reboot_value), str(self.download_updates_identifier_text), str(download_updates_value), str(self.apply_updates_identifier_text), str(apply_updates_value)))

        image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()
        self.composite_logger.log_debug("[TDNF] Logging system default configuration settings for auto OS updates. [Settings={0}]".format(str(image_default_patch_configuration_backup)))
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
            self.composite_logger.log_debug("[TDNF] Since the backup is invalid or does not exist for current service, we won't be able to revert auto OS patch settings to their system default value. [Service={0}]".format(str(self.current_auto_os_update_service)))

    def enable_auto_update_on_reboot(self):
        """Enables machine default auto update on reboot"""
        # type () -> None
        command = self.enable_on_reboot_cmd
        self.composite_logger.log_verbose("[TDNF] Enabling auto update on reboot. [Command={0}] ".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != 0:
            self.composite_logger.log_error("[TDNF][ERROR] Error enabling auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("[TDNF] Enabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))

    def __get_image_default_patch_configuration_backup(self):
        """ Get image_default_patch_configuration_backup file"""
        image_default_patch_configuration_backup = {}

        # read existing backup since it also contains backup from other update services. We need to preserve any existing data within the backup file
        if self.image_default_patch_configuration_backup_exists():
            try:
                image_default_patch_configuration_backup = json.loads(self.env_layer.file_system.read_with_retry(self.image_default_patch_configuration_backup_path))
            except Exception as error:
                self.composite_logger.log_error("[TDNF] Unable to read backup for default patch state. Will attempt to re-write. [Exception={0}]".format(repr(error)))
        return image_default_patch_configuration_backup
    # endregion

    # region Reboot Management
    def is_reboot_pending(self):
        """ Checks if there is a pending reboot on the machine. """
        try:
            pending_file_exists = os.path.isfile(self.REBOOT_PENDING_FILE_PATH)
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

        return False
    # endregion

    def set_security_esm_package_status(self, operation, packages):
        """ Set the security-ESM classification for the esm packages. Only needed for apt. No-op for tdnf, yum and zypper."""
        pass

    def separate_out_esm_packages(self, packages, package_versions):
        """Filter out packages from the list where the version matches the UA_ESM_REQUIRED string.
        Only needed for apt. No-op for tdnf, yum and zypper"""
        esm_packages = []
        esm_package_versions = []
        esm_packages_found = False

        return packages, package_versions, esm_packages, esm_package_versions, esm_packages_found

    def get_package_install_expected_avg_time_in_seconds(self):
        return self.package_install_expected_avg_time_in_seconds

