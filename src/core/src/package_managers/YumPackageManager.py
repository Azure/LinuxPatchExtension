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

"""YumPackageManager for Redhat and CentOS"""
import json
import os
import re
from core.src.package_managers.PackageManager import PackageManager
from core.src.bootstrap.Constants import Constants


class YumPackageManager(PackageManager):
    """Implementation of Redhat/CentOS package management operations"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(YumPackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)
        # Repo refresh
        # There is no command as this is a no op.

        # Support to get updates and their dependencies
        self.yum_check = 'sudo yum -q check-update'
        self.yum_check_security_prerequisite = 'sudo yum -y install yum-plugin-security'
        self.yum_check_security = 'sudo yum -q --security check-update'
        self.single_package_check_versions = 'sudo yum list available <PACKAGE-NAME> --showduplicates'
        self.single_package_check_installed = 'sudo yum list installed <PACKAGE-NAME>'
        self.single_package_upgrade_simulation_cmd = 'LANG=en_US.UTF8 sudo yum install --assumeno --skip-broken '

        # Install update
        self.single_package_upgrade_cmd = 'sudo yum -y install --skip-broken '
        self.all_but_excluded_upgrade_cmd = 'sudo yum -y update --exclude='

        # Package manager exit code(s)
        self.yum_exitcode_no_applicable_packages = 0
        self.yum_exitcode_ok = 1
        self.yum_exitcode_updates_available = 100

        # Support to check for processes requiring restart
        self.yum_utils_prerequisite = 'sudo yum -y install yum-utils'
        self.needs_restarting = 'sudo LANG=en_US.UTF8 needs-restarting'
        self.needs_restarting_with_flag = 'sudo LANG=en_US.UTF8 needs-restarting -r'
        self.yum_ps_prerequisite = 'sudo yum -y install yum-plugin-ps'
        self.yum_ps = 'sudo yum ps'

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

        # commands for YUM Cron service
        self.__init_constants_for_yum_cron()

        # commands for DNF Automatic updates service
        self.__init_constants_for_dnf_automatic()

        # commands for PackageKit service
        self.__init_constants_for_packagekit()

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.YUM)
        self.STR_TOTAL_DOWNLOAD_SIZE = "Total download size: "

        # if an Auto Patching request comes in on a CentOS machine with Security and/or Critical classifications selected, we need to install all patches
        installation_included_classifications = [] if execution_config.included_classifications_list is None else execution_config.included_classifications_list
        if execution_config.health_store_id is not str() and execution_config.operation.lower() == Constants.INSTALLATION.lower() \
                and 'CentOS' in str(env_layer.platform.linux_distribution()) \
                and 'Critical' in installation_included_classifications and 'Security' in installation_included_classifications:
            self.composite_logger.log_debug("Updating classifications list to install all patches for the Auto Patching request since classification based patching is not available on CentOS machines")
            execution_config.included_classifications_list = [Constants.PackageClassification.CRITICAL, Constants.PackageClassification.SECURITY, Constants.PackageClassification.OTHER]

        # Known errors and the corresponding action items
        self.known_errors_and_fixes = {"SSL peer rejected your certificate as expired": self.fix_ssl_certificate_issue,
                                       "Error: Cannot retrieve repository metadata (repomd.xml) for repository": self.fix_ssl_certificate_issue,
                                       "Error: Failed to download metadata for repo":  self.fix_ssl_certificate_issue}

        self.yum_update_client_package = "sudo yum update -y --disablerepo='*' --enablerepo='*microsoft*'"

        self.package_install_expected_avg_time_in_seconds = 90  # As per telemetry data, the average time to install package is around 90 seconds for yum.

    def refresh_repo(self):
        pass  # Refresh the repo is no ops in YUM

    # region Get Available Updates
    def invoke_package_manager_advanced(self, command, raise_on_exception=True):
        """Get missing updates using the command input"""
        self.composite_logger.log_verbose("[YPM] Invoking package manager. [Command={0}]".format(str(command)))
        code, out = self.env_layer.run_command_output(command, False, False)

        code, out = self.try_mitigate_issues_if_any(command, code, out, raise_on_exception)

        if code not in [self.yum_exitcode_ok, self.yum_exitcode_no_applicable_packages, self.yum_exitcode_updates_available]:
            self.composite_logger.log_warning('[ERROR] Customer environment error. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
            error_msg = "Customer environment error: Investigate and resolve unexpected return code ({0}) from package manager on command: {1}".format(str(code), command)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            if raise_on_exception:
                raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
            # more return codes should be added as appropriate
        else:  # verbose diagnostic log
            self.composite_logger.log_debug('[YPM] Invoked package manager. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
        return out, code

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_verbose("[YPM] Discovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug("[YPM] Get all updates : [Cached={0}][PackagesCount={1}]]".format(str(cached), len(self.all_updates_cached)))
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        out = self.invoke_package_manager(self.yum_check)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)

        self.composite_logger.log_debug("[YPM] Get all updates : [Cached={0}][PackagesCount={1}]]".format(str(False), len(self.all_updates_cached)))
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates"""
        self.composite_logger.log_verbose("[YPM] Discovering 'security' packages...")

        if not self.__is_image_rhel8_or_higher():
            self.install_yum_security_prerequisite()

        out = self.invoke_package_manager(self.yum_check_security)
        security_packages, security_package_versions = self.extract_packages_and_versions(out)

        if len(security_packages) == 0 and 'CentOS' in str(self.env_layer.platform.linux_distribution()):   # deliberately non-terminal
            self.composite_logger.log_warning("Classification-based patching is only supported on YUM if the machine is independently configured to receive classification information.")

        self.composite_logger.log_debug("[YPM] Discovered 'security' packages. [Count={0}]".format(len(security_packages)))
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates"""
        self.composite_logger.log_verbose("[YPM] Discovering 'other' packages...")
        other_packages = []
        other_package_versions = []

        all_packages, all_package_versions = self.get_all_updates(True)
        security_packages, security_package_versions = self.get_security_updates()
        if len(security_packages) == 0 and 'CentOS' in str(self.env_layer.platform.linux_distribution()):  # deliberately terminal - erring on the side of caution to avoid dissat in uninformed customers
            self.composite_logger.log_error("Please review patch management documentation for information on classification-based patching on YUM.")
            error_msg = "Classification-based patching is only supported on YUM if the computer is independently configured to receive classification information." \
                        "Please remove classifications from update deployments to CentOS machines to bypass this error."
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

        for index, package in enumerate(all_packages):
            if package not in security_packages:
                other_packages.append(package)
                other_package_versions.append(all_package_versions[index])

        self.composite_logger.log_debug("[YPM] Discovered 'other' packages. [Count={0}]".format(len(other_packages)))
        return other_packages, other_package_versions

    def __is_image_rhel8_or_higher(self):
        """ Check if image is RHEL8+ return true else false """
        if self.env_layer.platform.linux_distribution() is not None:
            os_offer, os_version, os_code = self.env_layer.platform.linux_distribution()

            if "Red Hat Enterprise Linux" in os_offer and int(os_version.split('.')[0]) >= 8:
                self.composite_logger.log_debug("[YPM] RHEL version >= 8 detected. [DetectedVersion={0}]".format(str(os_version)))
                return True

        return False

    def set_max_patch_publish_date(self, max_patch_publish_date=str()):
        pass

    def install_yum_security_prerequisite(self):
        """Not installed by default in versions prior to RHEL 7. This step is idempotent and fast, so we're not writing more complex code."""
        code, out = self.env_layer.run_command_output(self.yum_check_security_prerequisite, False, False)
        self.composite_logger.log_verbose("[YPM] Ensuring RHEL yum-plugin-security is present. [Code={0}][Out={1}]".format(str(code), out))
    # endregion

    # region Output Parser(s)
    def extract_packages_and_versions(self, output):
        """Returns packages and versions from given output"""
        packages, versions = self.extract_packages_and_versions_including_duplicates(output)
        packages, versions = self.dedupe_update_packages(packages, versions)
        return packages, versions

    def extract_packages_and_versions_including_duplicates(self, output):
        """Returns packages and versions from given output"""
        self.composite_logger.log_verbose("[YPM] Extracting package and version data...")
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
                self.composite_logger.log_verbose("[YPM] > Inapplicable line (" + str(line_index) + "): " + lines[line_index])

        return packages, versions
    # endregion
    # endregion

    # region Install Update
    def get_composite_package_identifier(self, package, package_version):
        package_without_arch, arch = self.get_product_name_and_arch(package)
        package_identifier = package_without_arch + '-' + self.get_package_version_without_epoch(package_version)
        if arch is not None:
            package_identifier += arch
        return package_identifier

    def install_updates_fail_safe(self, excluded_packages):
        excluded_string = ""
        for excluded_package in excluded_packages:
            excluded_string += excluded_package + ' '
        cmd = self.all_but_excluded_upgrade_cmd + excluded_string

        self.composite_logger.log_debug("[YPM][FAIL SAFE MODE] UPDATING PACKAGES USING COMMAND: " + cmd)
        self.invoke_package_manager(cmd)

    def install_security_updates_azgps_coordinated(self):
        pass
    # endregion

    # region Package Information
    def get_all_available_versions_of_package(self, package_name):
        """ Returns a list of all the available versions of a package """
        # Sample output format
        # Available Packages
        # kernel.x86_64                                                                                    3.10.0-862.el7                                                                                         base
        # kernel.x86_64                                                                                    3.10.0-862.2.3.el7                                                                                     updates
        # kernel.x86_64                                                                                    3.10.0-862.3.2.el7                                                                                     updates
        cmd = self.single_package_check_versions.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)
        return package_versions

    def is_package_version_installed(self, package_name, package_version):
        """ Returns true if the specific package version is installed """
        # Loaded plugins: product-id, search-disabled-repos, subscription-manager
        # Installed Packages
        # kernel.x86_64                                                                                   3.10.0-514.el7                                                                                    @anaconda/7.3
        self.composite_logger.log_verbose("[YPM] Checking package install status. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
        cmd = self.single_package_check_installed.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)

        for index, package in enumerate(packages):
            if package == package_name and (package_versions[index] == package_version):
                self.composite_logger.log_debug("[YPM] > Installed version match found. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
                return True
            else:
                self.composite_logger.log_verbose("[YPM] > Did not match: " + package + " (" + package_versions[index] + ")")

        # sometimes packages are removed entirely from the system during installation of other packages
        # so let's check that the package is still needed before
        self.composite_logger.log_debug("[YPM] > Installed version match NOT found. [PackageName={0}][PackageVersion={1}]".format(str(package_name), str(package_version)))
        return False

    def extract_dependencies(self, output, packages):
        # Extracts dependent packages from output. Refer yum_update_output_expected_formats.txt for examples of supported output formats.

        dependencies = []
        package_arch_to_look_for = ["x86_64", "noarch", "i686", "aarch64"]  # if this is changed, review Constants

        lines = output.strip().splitlines()

        for line_index in range(0, len(lines)):
            line = re.split(r'\s+', (lines[line_index].replace("--->", "")).strip())
            next_line = []
            dependent_package_name = ""

            if line_index < len(lines) - 1:
                next_line = re.split(r'\s+', (lines[line_index + 1].replace("--->", "")).strip())

            if self.is_valid_update(line, package_arch_to_look_for):
                dependent_package_name = self.get_product_name_with_arch(line, package_arch_to_look_for)
            elif self.is_valid_update(line+next_line, package_arch_to_look_for):
                dependent_package_name = self.get_product_name_with_arch(line+next_line, package_arch_to_look_for)
            else:
                self.composite_logger.log_verbose("[YPM] > Inapplicable line: " + str(line))
                continue

            if len(dependent_package_name) != 0 and dependent_package_name not in packages and dependent_package_name not in dependencies:
                self.composite_logger.log_verbose("[YPM] > Dependency detected: " + dependent_package_name)
                dependencies.append(dependent_package_name)

        return dependencies

    def is_valid_update(self, package_details_in_output, package_arch_to_look_for):
        # Verifies whether the line under consideration (i.e. package_details_in_output) contains relevant package details.
        # package_details_in_output will be of the following format if it is valid
        #   In Yum 3: Package selinux-policy.noarch 0:3.13.1-102.el7_3.15 will be updated
        #   In Yum 4: kernel-tools        x86_64  4.18.0-372.64.1.el8_6 rhel-8-for-x86_64-baseos-eus-rhui-rpms  8.4 M
        return len(package_details_in_output) == 6 and self.is_arch_in_package_details(package_details_in_output[1], package_arch_to_look_for)

    @staticmethod
    def is_arch_in_package_details(package_detail, package_arch_to_look_for):
        # Using a list comprehension to determine if chunk is a package
        return len([p for p in package_arch_to_look_for if p in package_detail]) == 1

    def get_dependent_list(self, packages):
        package_names = ""
        for index, package in enumerate(packages):
            if index != 0:
                package_names += ' '
            package_names += package

        self.composite_logger.log_verbose("[YPM] Resolving dependencies. [Command={0}]".format(str(self.single_package_upgrade_simulation_cmd + package_names)))
        output = self.invoke_package_manager(self.single_package_upgrade_simulation_cmd + package_names)
        dependencies = self.extract_dependencies(output, packages)
        self.composite_logger.log_verbose("[YPM] Resolved dependencies. [Packages={0}][DependencyCount={1}]".format(str(packages), len(dependencies)))
        return dependencies

    def get_product_name(self, package_name):
        """Retrieve product name including arch where present"""
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
        """Retrieve product name with arch separated by '.'. Note: This format is default in yum3. Refer samples noted within func extract_dependencies() for more clarity"""
        return package_detail[0] + "." + package_detail[1] if package_detail[1] in package_arch_to_look_for else package_detail[1]

    def get_package_version_without_epoch(self, package_version):
        """Returns the package version stripped of any epoch"""
        package_version_split = str(package_version).split(':', 1)

        if len(package_version_split) == 2:
            self.composite_logger.log_verbose("[YPM]   > Removed epoch from version (" + package_version + "): " + package_version_split[1])
            return package_version_split[1]

        if len(package_version_split) != 1:
            self.composite_logger.log_error("[YPM] Unexpected error during version epoch removal from package version. [PackageVersion={0}]".format(package_version))

        return package_version

    def get_package_size(self, output):
        """Retrieve package size from installation output string"""
        # Sample output line:
        # Total download size: 15 M
        if "No packages were marked for update" not in output:
            lines = output.strip().split('\n')
            for line in lines:
                if line.find(self.STR_TOTAL_DOWNLOAD_SIZE) >= 0:
                    return line.replace(self.STR_TOTAL_DOWNLOAD_SIZE, "")

        return Constants.UNKNOWN_PACKAGE_SIZE
    # endregion

    # region auto OS updates
    def __init_constants_for_yum_cron(self):
        self.yum_cron_configuration_settings_file_path = '/etc/yum/yum-cron.conf'
        self.yum_cron_install_check_cmd = 'systemctl list-unit-files --type=service | grep yum-cron.service'  # list-unit-files returns installed services, ref: https://www.freedesktop.org/software/systemd/man/systemctl.html#Unit%20File%20Commands
        self.yum_cron_enable_on_reboot_check_cmd = 'systemctl is-enabled yum-cron'
        self.yum_cron_disable_on_reboot_cmd = 'systemctl disable yum-cron'
        self.yum_cron_enable_on_reboot_cmd = 'systemctl enable yum-cron'
        self.yum_cron_config_pattern_match_text = ' = (no|yes)'
        self.yum_cron_download_updates_identifier_text = 'download_updates'
        self.yum_cron_apply_updates_identifier_text = 'apply_updates'
        self.yum_cron_enable_on_reboot_identifier_text = "enable_on_reboot"
        self.yum_cron_installation_state_identifier_text = "installation_state"

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

    def __init_constants_for_packagekit(self):
        self.packagekit_configuration_file_path = '/etc/PackageKit/PackageKit.conf'
        self.packagekit_install_check_cmd = 'systemctl list-unit-files --type=service | grep packagekit.service'  # list-unit-files returns installed services, ref: https://www.freedesktop.org/software/systemd/man/systemctl.html#Unit%20File%20Commands
        self.packagekit_enable_on_reboot_check_cmd = 'systemctl is-enabled packagekit'
        self.packagekit_disable_on_reboot_cmd = 'systemctl disable packagekit'
        self.packagekit_enable_on_reboot_cmd = 'systemctl enable packagekit'
        self.packagekit_config_pattern_match_text = ' = (false|true)'
        self.packagekit_download_updates_identifier_text = 'GetPreparedUpdates'  # todo: dummy value, get real value or add telemetry to gather value
        self.packagekit_apply_updates_identifier_text = 'WritePreparedUpdates'
        self.packagekit_enable_on_reboot_identifier_text = "enable_on_reboot"
        self.packagekit_installation_state_identifier_text = "installation_state"

    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        self.composite_logger.log("Fetching the current automatic OS patch state on the machine...")

        current_auto_os_patch_state_for_yum_cron = self.__get_current_auto_os_patch_state_for_yum_cron()
        current_auto_os_patch_state_for_dnf_automatic = self.__get_current_auto_os_patch_state_for_dnf_automatic()
        current_auto_os_patch_state_for_packagekit = self.__get_current_auto_os_patch_state_for_packagekit()

        self.composite_logger.log("OS patch state per auto OS update service: [yum-cron={0}] [dnf-automatic={1}] [packagekit={2}]"
                                  .format(str(current_auto_os_patch_state_for_yum_cron), str(current_auto_os_patch_state_for_dnf_automatic), str(current_auto_os_patch_state_for_packagekit)))

        if current_auto_os_patch_state_for_yum_cron == Constants.AutomaticOSPatchStates.ENABLED \
                or current_auto_os_patch_state_for_dnf_automatic == Constants.AutomaticOSPatchStates.ENABLED \
                or current_auto_os_patch_state_for_packagekit == Constants.AutomaticOSPatchStates.ENABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.ENABLED
        elif current_auto_os_patch_state_for_yum_cron == Constants.AutomaticOSPatchStates.DISABLED \
                and current_auto_os_patch_state_for_dnf_automatic == Constants.AutomaticOSPatchStates.DISABLED \
                and current_auto_os_patch_state_for_packagekit == Constants.AutomaticOSPatchStates.DISABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.DISABLED
        else:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.UNKNOWN

        self.composite_logger.log_debug("Overall Auto OS Patch State based on all auto OS update service states [OverallAutoOSPatchState={0}]".format(str(current_auto_os_patch_state)))
        return current_auto_os_patch_state

    def __get_current_auto_os_patch_state_for_yum_cron(self):
        """ Gets current auto OS update patch state for yum-cron """
        self.composite_logger.log_debug("Fetching current automatic OS patch state in yum-cron service. This includes checks on whether the service is installed, current auto patch enable state and whether it is set to enable on reboot")
        self.__init_auto_update_for_yum_cron()
        is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

        apply_updates = self.__get_extension_standard_value_for_apply_updates(apply_updates_value)

        if apply_updates == self.apply_updates_enabled or enable_on_reboot_value:
            return Constants.AutomaticOSPatchStates.ENABLED
        # OS patch state is considered to be disabled: a) if it was successfully disabled or b) if the service is not installed
        elif not is_service_installed or (apply_updates == self.apply_updates_disabled and not enable_on_reboot_value):
            return Constants.AutomaticOSPatchStates.DISABLED
        else:
            return Constants.AutomaticOSPatchStates.UNKNOWN

    def __get_current_auto_os_patch_state_for_dnf_automatic(self):
        """ Gets current auto OS update patch state for dnf-automatic """
        self.composite_logger.log_debug("Fetching current automatic OS patch state in dnf-automatic service. This includes checks on whether the service is installed, current auto patch enable state and whether it is set to enable on reboot")
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

    def __get_current_auto_os_patch_state_for_packagekit(self):
        """ Gets current auto OS update patch state for packagekit """
        self.composite_logger.log_debug("Fetching current automatic OS patch state in packagekit service. This includes checks on whether the service is installed, current auto patch enable state and whether it is set to enable on reboot")
        self.__init_auto_update_for_packagekit()
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

    def __init_auto_update_for_yum_cron(self):
        """ Initializes all generic auto OS update variables with the config values for yum cron service """
        self.os_patch_configuration_settings_file_path = self.yum_cron_configuration_settings_file_path
        self.download_updates_identifier_text = self.yum_cron_download_updates_identifier_text
        self.apply_updates_identifier_text = self.yum_cron_apply_updates_identifier_text
        self.enable_on_reboot_identifier_text = self.yum_cron_enable_on_reboot_identifier_text
        self.installation_state_identifier_text = self.yum_cron_installation_state_identifier_text
        self.auto_update_config_pattern_match_text = self.yum_cron_config_pattern_match_text
        self.enable_on_reboot_check_cmd = self.yum_cron_enable_on_reboot_check_cmd
        self.enable_on_reboot_cmd = self.yum_cron_enable_on_reboot_cmd
        self.install_check_cmd = self.yum_cron_install_check_cmd
        self.current_auto_os_update_service = Constants.YumAutoOSUpdateServices.YUM_CRON

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
        self.current_auto_os_update_service = Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC

    def __init_auto_update_for_packagekit(self):
        """ Initializes all generic auto OS update variables with the config values for packagekit service """
        self.os_patch_configuration_settings_file_path = self.packagekit_configuration_file_path
        self.download_updates_identifier_text = self.packagekit_download_updates_identifier_text
        self.apply_updates_identifier_text = self.packagekit_apply_updates_identifier_text
        self.enable_on_reboot_identifier_text = self.packagekit_enable_on_reboot_identifier_text
        self.installation_state_identifier_text = self.packagekit_installation_state_identifier_text
        self.auto_update_config_pattern_match_text = self.packagekit_config_pattern_match_text
        self.enable_on_reboot_check_cmd = self.packagekit_enable_on_reboot_check_cmd
        self.enable_on_reboot_cmd = self.packagekit_enable_on_reboot_cmd
        self.install_check_cmd = self.packagekit_install_check_cmd
        self.current_auto_os_update_service = Constants.YumAutoOSUpdateServices.PACKAGEKIT

    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enable_on_reboot and logs the default settings the machine comes with """
        try:
            self.composite_logger.log_verbose("[YPM] Disabling auto OS updates in all identified services...")
            self.disable_auto_os_update_for_yum_cron()
            self.disable_auto_os_update_for_dnf_automatic()
            self.disable_auto_os_update_for_packagekit()
            self.composite_logger.log_debug("[YPM] Successfully disabled auto OS updates")

        except Exception as error:
            self.composite_logger.log_error("[YPM] Could not disable auto OS updates. [Error={0}]".format(repr(error)))
            raise

    def disable_auto_os_update_for_yum_cron(self):
        """ Disables auto OS updates, using yum cron service, and logs the default settings the machine comes with """
        self.composite_logger.log_verbose("[YPM] Disabling auto OS updates using yum-cron")
        self.__init_auto_update_for_yum_cron()

        self.backup_image_default_patch_configuration_if_not_exists()
        if not self.is_auto_update_service_installed(self.yum_cron_install_check_cmd):
            self.composite_logger.log_debug("[YPM] Cannot disable as yum-cron is not installed on the machine")
            return

        self.composite_logger.log_verbose("[YPM] Preemptively disabling auto OS updates using yum-cron")
        self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "no", self.yum_cron_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "no", self.yum_cron_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.yum_cron_disable_on_reboot_cmd)

        self.composite_logger.log_debug("[YPM] Successfully disabled auto OS updates using yum-cron")

    def disable_auto_os_update_for_dnf_automatic(self):
        """ Disables auto OS updates, using dnf-automatic service, and logs the default settings the machine comes with """
        self.composite_logger.log_verbose("[YPM] Disabling auto OS updates using dnf-automatic")
        self.__init_auto_update_for_dnf_automatic()

        self.backup_image_default_patch_configuration_if_not_exists()

        if not self.is_auto_update_service_installed(self.dnf_automatic_install_check_cmd):
            self.composite_logger.log_debug("[YPM] Cannot disable as dnf-automatic is not installed on the machine")
            return

        self.composite_logger.log_verbose("[YPM] Preemptively disabling auto OS updates using dnf-automatic")
        self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "no", self.dnf_automatic_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "no", self.dnf_automatic_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.dnf_automatic_disable_on_reboot_cmd)

        self.composite_logger.log_debug("[YPM] Successfully disabled auto OS updates using dnf-automatic")

    def disable_auto_os_update_for_packagekit(self):
        """ Disables auto OS updates, using packagekit service, and logs the default settings the machine comes with """
        self.composite_logger.log_verbose("[YPM] Disabling auto OS updates using packagekit")
        self.__init_auto_update_for_packagekit()

        self.backup_image_default_patch_configuration_if_not_exists()

        if not self.is_auto_update_service_installed(self.packagekit_install_check_cmd):
            self.composite_logger.log_debug("[YPM] Cannot disable as packagekit is not installed on the machine")
            return

        self.composite_logger.log_verbose("[YPM] Preemptively disabling auto OS updates using packagekit")
        #todo: uncomment after finding the correct value
        # self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "false", self.packagekit_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "false", self.packagekit_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.packagekit_disable_on_reboot_cmd)

        self.composite_logger.log_debug("[YPM] Successfully disabled auto OS updates using packagekit")

    def is_service_set_to_enable_on_reboot(self, command):
        """ Checking if auto update is enable_on_reboot on the machine. An enable_on_reboot service will be activated (if currently inactive) on machine reboot """
        code, out = self.env_layer.run_command_output(command, False, False)
        self.composite_logger.log_debug("[YPM] Checked if auto update service is set to enable on reboot. [Code={0}][Out={1}]".format(str(code), out))
        if len(out.strip()) > 0 and code == 0 and 'enabled' in out:
            self.composite_logger.log_debug("[YPM] > Auto OS update service will enable on reboot")
            return True
        self.composite_logger.log_debug("[YPM] > Auto OS update service will NOT enable on reboot")
        return False

    def backup_image_default_patch_configuration_if_not_exists(self):
        """ Records the default system settings for auto OS updates within patch extension artifacts for future reference.
        We only log the default system settings a VM comes with, any subsequent updates will not be recorded"""
        """ JSON format for backup file:
                    {
                        "yum-cron": {
                            "apply_updates": "yes/no/empty string",
                            "download_updates": "yes/no/empty string",
                            "enable_on_reboot": true/false,
                            "installation_state": true/false
                        },
                        "dnf-automatic": {
                            "apply_updates": "yes/no/empty string",
                            "download_updates": "yes/no/empty string",
                            "enable_on_reboot": true/false,
                            "installation_state": true/false
                        },
                        "packagekit": {
                            "WritePreparedUpdates": "true/false/empty string",
                            "GetPreparedUpdates": "true/false/empty string", //NOTE: This property name is pending validation as noted in another comment where the name is initialized
                            "enable_on_reboot": true/false,
                            "installation_state": true/false
                        }
                    } """
        try:
            self.composite_logger.log_debug("[YPM] Ensuring there is a backup of the default patch state for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
            image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()

            # verify if existing backup is valid if not, write to backup
            is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)
            if is_backup_valid:
                self.composite_logger.log_debug("[YPM] Since extension has a valid backup, no need to log the current settings again. [Default Auto OS update settings={0}] [File path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
            else:
                self.composite_logger.log_debug("[YPM] Since the backup is invalid, will add a new backup with the current auto OS update settings")
                self.composite_logger.log_debug("[YPM] Fetching current auto OS update settings for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
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

                self.composite_logger.log_debug("[YPM] Logging default system configuration settings for auto OS updates. [Settings={0}] [Log file path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
                self.env_layer.file_system.write_with_retry(self.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(image_default_patch_configuration_backup)), mode='w+')
        except Exception as error:
            error_message = "[YPM] Exception during fetching and logging default auto update settings on the machine. [Exception={0}]".format(repr(error))
            self.composite_logger.log_error(error_message)
            self.status_handler.add_error_to_status(error_message, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        """ Verifies if default auto update configurations, for a service under consideration, are saved in backup """
        switcher = {
            Constants.YumAutoOSUpdateServices.YUM_CRON: self.is_backup_valid_for_yum_cron,
            Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC: self.is_backup_valid_for_dnf_automatic,
            Constants.YumAutoOSUpdateServices.PACKAGEKIT: self.is_backup_valid_for_packagekit
        }
        try:
            return switcher[self.current_auto_os_update_service](image_default_patch_configuration_backup)
        except KeyError as e:
            raise e

    def is_backup_valid_for_yum_cron(self, image_default_patch_configuration_backup):
        if Constants.YumAutoOSUpdateServices.YUM_CRON in image_default_patch_configuration_backup \
                and self.yum_cron_download_updates_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.YUM_CRON] \
                and self.yum_cron_apply_updates_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.YUM_CRON] \
                and self.yum_cron_enable_on_reboot_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.YUM_CRON] \
                and self.yum_cron_installation_state_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.YUM_CRON]:
            self.composite_logger.log_debug("[YPM] Extension has a valid backup for default yum-cron configuration settings")
            return True
        else:
            self.composite_logger.log_debug("[YPM] Extension does not have a valid backup for default yum-cron configuration settings")
            return False

    def is_backup_valid_for_dnf_automatic(self, image_default_patch_configuration_backup):
        if Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC in image_default_patch_configuration_backup \
                and self.dnf_automatic_download_updates_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC] \
                and self.dnf_automatic_apply_updates_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC] \
                and self.dnf_automatic_enable_on_reboot_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC] \
                and self.dnf_automatic_installation_state_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC]:
            self.composite_logger.log_debug("[YPM] Extension has a valid backup for default dnf-automatic configuration settings")
            return True
        else:
            self.composite_logger.log_debug("[YPM] Extension does not have a valid backup for default dnf-automatic configuration settings")
            return False

    def is_backup_valid_for_packagekit(self, image_default_patch_configuration_backup):
        if Constants.YumAutoOSUpdateServices.PACKAGEKIT in image_default_patch_configuration_backup \
                and self.packagekit_download_updates_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT] \
                and self.packagekit_apply_updates_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT] \
                and self.packagekit_enable_on_reboot_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT] \
                and self.packagekit_installation_state_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT]:
            self.composite_logger.log_debug("[YPM] Extension has a valid backup for default packagekit configuration settings")
            return True
        else:
            self.composite_logger.log_debug("[YPM] Extension does not have a valid backup for default packagekit configuration settings")
            return False

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

            self.composite_logger.log_debug("[YPM] Checking if auto updates are currently enabled...")
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
                self.composite_logger.log_debug("[YPM] Machine did not have any value set for [Setting={0}]".format(str(self.download_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("[YPM] Current value set for [{0}={1}]".format(str(self.download_updates_identifier_text), str(download_updates_value)))

            if apply_updates_value == "":
                self.composite_logger.log_debug("[YPM] Machine did not have any value set for [Setting={0}]".format(str(self.apply_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("[YPM] Current value set for [{0}={1}]".format(str(self.apply_updates_identifier_text), str(apply_updates_value)))

            return is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value

        except Exception as error:
            raise Exception("[YPM] Error occurred in fetching current auto OS update settings from the machine. [Exception={0}]".format(repr(error)))

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value="no", config_pattern_match_text=""):
        """ Updates (or adds if it doesn't exist) the given patch_configuration_sub_setting with the given value in os_patch_configuration_settings_file """
        try:
            # note: adding space between the patch_configuration_sub_setting and value since, we will have to do that if we have to add a patch_configuration_sub_setting that did not exist before
            self.composite_logger.log_debug("[YPM] Updating system configuration settings for auto OS updates. [Patch Configuration Sub Setting={0}] [Value={1}]".format(str(patch_configuration_sub_setting), value))
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
            error_msg = "[YPM] Error occurred while updating system configuration settings for auto OS updates. [Patch Configuration={0}] [Error={1}]".format(str(patch_configuration_sub_setting), repr(error))
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def disable_auto_update_on_reboot(self, command):
        self.composite_logger.log_verbose("[YPM] Disabling auto update on reboot. [Command={0}] ".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != 0:
            self.composite_logger.log_error("[YPM][ERROR] Error disabling auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("[YPM] Disabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))

    def enable_auto_update_on_reboot(self):
        command = self.enable_on_reboot_cmd
        self.composite_logger.log_verbose("[YPM] Enabling auto update on reboot. [Command={0}] ".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != 0:
            self.composite_logger.log_error("[YPM][ERROR] Error enabling auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("[YPM] Enabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))

    def is_auto_update_service_installed(self, install_check_cmd):
        """ Checks if the auto update service is enable_on_reboot on the VM """
        code, out = self.env_layer.run_command_output(install_check_cmd, False, False)
        self.composite_logger.log_debug("[YPM] Checked if auto update service is installed. [Command={0}][Code={1}][Output={2}]".format(install_check_cmd, str(code), out))
        if len(out.strip()) > 0 and code == 0:
            self.composite_logger.log_debug("[YPM] > Auto OS update service is installed on the machine")
            return True
        else:
            self.composite_logger.log_debug("[YPM] > Auto OS update service is NOT installed on the machine")
            return False

    def revert_auto_os_update_to_system_default(self):
        """ Reverts the auto OS update patch state on the machine to it's system default value, if one exists in our backup file """
        self.composite_logger.log("[YPM] Reverting the current automatic OS patch state on the machine to it's system default value before patchmode was set to 'AutomaticByPlatform'")
        self.revert_auto_os_update_to_system_default_for_service(Constants.YumAutoOSUpdateServices.YUM_CRON)
        self.revert_auto_os_update_to_system_default_for_service(Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC)
        self.revert_auto_os_update_to_system_default_for_service(Constants.YumAutoOSUpdateServices.PACKAGEKIT)
        self.composite_logger.log_debug("[YPM] Successfully reverted auto OS updates to system default config")

    def revert_auto_os_update_to_system_default_for_service(self, service):
        """ Reverts the auto OS update patch state on the machine to it's system default value for given service, if applicable """
        self.composite_logger.log("[YPM] Reverting the current automatic OS patch state on the machine to it's system default value for [Service={0}]]".format(str(service)))
        self.__init_auto_update_for_service(service)
        is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

        if not is_service_installed:
            self.composite_logger.log_debug("[YPM] Machine default auto OS update service is not installed on the VM and hence no config to revert. [Service={0}]".format(str(service)))
            return

        self.composite_logger.log_debug("[YPM] Logging current configuration settings for auto OS updates [Service={0}][Is_Service_Installed={1}][Machine_default_update_enable_on_reboot={2}][{3}={4}]][{5}={6}]"
                                        .format(str(self.current_auto_os_update_service), str(is_service_installed), str(enable_on_reboot_value), str(self.download_updates_identifier_text), str(download_updates_value), str(self.apply_updates_identifier_text), str(apply_updates_value)))

        image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()
        self.composite_logger.log_debug("[YPM] Logging system default configuration settings for auto OS updates. [Settings={0}]".format(str(image_default_patch_configuration_backup)))
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
            self.composite_logger.log_debug("[YPM] Since the backup is invalid or does not exist for current service, we won't be able to revert auto OS patch settings to their system default value. [Service={0}]".format(str(service)))

    def __init_auto_update_for_service(self, service):
        """ Verifies if default auto update configurations, for a service under consideration, are saved in backup """
        switcher = {
            Constants.YumAutoOSUpdateServices.YUM_CRON: self.__init_auto_update_for_yum_cron,
            Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC: self.__init_auto_update_for_dnf_automatic,
            Constants.YumAutoOSUpdateServices.PACKAGEKIT: self.__init_auto_update_for_packagekit
        }
        try:
            return switcher[service]()
        except KeyError as e:
            raise e

    def __get_image_default_patch_configuration_backup(self):
        """ Get image_default_patch_configuration_backup file"""
        image_default_patch_configuration_backup = {}

        # read existing backup since it also contains backup from other update services. We need to preserve any existing data within the backup file
        if self.image_default_patch_configuration_backup_exists():
            try:
                image_default_patch_configuration_backup = json.loads(self.env_layer.file_system.read_with_retry(self.image_default_patch_configuration_backup_path))
            except Exception as error:
                self.composite_logger.log_error("[YPM] Unable to read backup for default patch state. [Exception={0}]".format(repr(error)))
        return image_default_patch_configuration_backup
    # endregion

    # region Handling known errors
    def try_mitigate_issues_if_any(self, command, code, out, raise_on_exception=True, seen_errors=None, retry_count=0, max_retries=Constants.MAX_RETRY_ATTEMPTS_FOR_ERROR_MITIGATION):
        """ Attempt to fix the errors occurred while executing a command. Repeat check until no issues found
        Args:
            raise_on_exception (bool): If true, should raise exception on issue mitigation failures.
            seen_errors (Any): Hash set used to maintain a list of errors strings seen in the call stack.
            retry_count (int): Count of number of retries made to resolve errors.
            max_retries (int): Maximum number of retries allowed before exiting the retry loop.
        """
        if seen_errors is None:
            seen_errors = set()

        # Keep an upper bound on the size of the call stack to prevent an unbounded loop if error mitigation fails.
        if retry_count >= max_retries:
            self.log_error_mitigation_failure(out, raise_on_exception)
            return code, out

        if "Error" in out or "Errno" in out:

            # Preemptively exit the retry loop if the same error string is repeating in the call stack.
            # This implies that self.check_known_issues_and_attempt_fix may have failed to mitigate the error.
            if out in seen_errors:
                self.log_error_mitigation_failure(out, raise_on_exception)
                return code, out

            seen_errors.add(out)
            issue_mitigated = self.check_known_issues_and_attempt_fix(out)
            if issue_mitigated:
                self.composite_logger.log_debug('Post mitigation, invoking package manager again using: ' + command)
                code_after_fix_attempt, out_after_fix_attempt = self.env_layer.run_command_output(command, False, False)
                return self.try_mitigate_issues_if_any(command, code_after_fix_attempt, out_after_fix_attempt, raise_on_exception, seen_errors, retry_count + 1, max_retries)
        return code, out

    def check_known_issues_and_attempt_fix(self, output):
        """ Checks if issue falls into known issues and attempts to mitigate """
        self.composite_logger.log_debug("[YPM] Checking against known errors: [Out={0}]".format(output))
        for error in self.known_errors_and_fixes:
            if error in output:
                self.composite_logger.log_debug("[YPM] Found a match within known errors list, attempting a fix...")
                self.known_errors_and_fixes[error]()
                return True

        self.composite_logger.log_error("[YPM] Customer Environment Error: Not a known error. Please investigate and address. [Out={0}]".format(output))
        return False

    def fix_ssl_certificate_issue(self):
        command = self.yum_update_client_package
        self.composite_logger.log_debug("[Customer-environment-error] Updating client package to avoid errors from older certificates using command: [Command={0}]".format(str(command)))
        code, out = self.env_layer.run_command_output(command, False, False)
        if code != self.yum_exitcode_no_applicable_packages:
            error_msg = 'Customer environment error (expired SSL certs):  [Command={0}][Code={1}]'.format(command,str(code))
            self.composite_logger.log_error("{0}[Out={1}]".format(error_msg, out))
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_verbose("\n\n==[SUCCESS]===============================================================")
            self.composite_logger.log_debug("Client package update complete. [Code={0}][Out={1}]".format(str(code), out))
            self.composite_logger.log_verbose("==========================================================================\n\n")

    def log_error_mitigation_failure(self, output, raise_on_exception=True):
        self.composite_logger.log_error("[YPM] Customer Environment Error: Unable to auto-mitigate known issue. Please investigate and address. [Out={0}]".format(output))
        if raise_on_exception:
            error_msg = 'Customer environment error (Unable to auto-mitigate known issue):  [Out={0}]'.format(output)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
    # endregion

    # region Reboot Management
    def is_reboot_pending(self):
        """ Checks if there is a pending reboot on the machine. """
        try:
            pending_file_exists = os.path.isfile(self.REBOOT_PENDING_FILE_PATH)  # not intended for yum, but supporting as back-compat
            pending_processes_exist = self.do_processes_require_restart()
            self.composite_logger.log_debug("[YPM] > Reboot required debug flags (yum): " + str(pending_file_exists) + ", " + str(pending_processes_exist) + ".")
            return pending_file_exists or pending_processes_exist
        except Exception as error:
            self.composite_logger.log_error('[YPM] Error while checking for reboot pending (yum): ' + repr(error))
            return True  # defaults for safety

    def do_processes_require_restart(self):
        """Signals whether processes require a restart due to updates"""
        self.composite_logger.log_verbose("[YPM] Checking if process requires reboot")
        # Checking using yum-utils
        code, out = self.env_layer.run_command_output(self.yum_utils_prerequisite, False, False)  # idempotent, doesn't install if already present
        self.composite_logger.log_verbose("[YPM] Idempotent yum-utils existence check. [Code={0}][Out={1}]".format(str(code), out))

        # Checking for restart for distros with -r flag such as RHEL 7+
        code, out = self.env_layer.run_command_output(self.needs_restarting_with_flag, False, False)
        self.composite_logger.log_verbose("[YPM] > Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))
        if out.find("Reboot is required") < 0:
            self.composite_logger.log_debug("[YPM] > Reboot not detected to be required (L1).")
        else:
            self.composite_logger.log_debug("[YPM] > Reboot is detected to be required (L1).")
            return True

        # Checking for restart for distro without -r flag such as RHEL 6 and CentOS 6
        if str(self.env_layer.platform.linux_distribution()[1]).split('.')[0] == '6':
            code, out = self.env_layer.run_command_output(self.needs_restarting, False, False)
            self.composite_logger.log_verbose("[YPM] > Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))
            if len(out.strip()) == 0 and code == 0:
                self.composite_logger.log_debug("[YPM] > Reboot not detected to be required (L2).")
            else:
                self.composite_logger.log_debug("[YPM] > Reboot is detected to be required (L2).")
                return True

        # Double-checking using yum ps (where available)
        code, out = self.env_layer.run_command_output(self.yum_ps_prerequisite, False, False)  # idempotent, doesn't install if already present
        if out.find("Unable to find a match: yum-plugin-security") < 0:
            self.composite_logger.log_debug("[YPM][Info] yum-plugin-ps is not present. This is okay on RHEL8+. [Code={0}][Out={1}]".format(str(code), out))
        else:
            self.composite_logger.log_debug("[YPM] Idempotent yum-plugin-ps existence check. [Code={0}][Out={1}]".format(str(code), out))

        output = self.invoke_package_manager(self.yum_ps)
        lines = output.strip().split('\n')

        process_list_flag = False
        process_count = 0
        process_list_verbose = ""

        for line in lines:
            if not process_list_flag:  # keep going until the process list starts
                if line.find("pid") < 0 and line.find("proc") < 0 and line.find("uptime") < 0:
                    self.composite_logger.log_verbose("[YPM] > Inapplicable line: " + str(line))
                    continue
                else:
                    self.composite_logger.log_verbose("[YPM] > Process list started: " + str(line))
                    process_list_flag = True
                    continue

            process_details = re.split(r'\s+', line.strip())
            if len(process_details) < 7:
                self.composite_logger.log_verbose("[YPM] > Inapplicable line: " + str(line))
                continue
            else:
                # The first string should be process ID and hence it should be integer.
                # If first string is not process ID then the line is not for a process detail.
                try:
                    int(process_details[0])
                except Exception:
                    self.composite_logger.log_verbose("[YPM] > Inapplicable line: " + str(line))
                    continue

                self.composite_logger.log_verbose("[YPM] > Applicable line: " + str(line))
                process_count += 1
                process_list_verbose += process_details[1] + " (" + process_details[0] + "), "  # process name and id

        self.composite_logger.log_debug("[YPM] Processes requiring restart (" + str(process_count) + "): [" + process_list_verbose + "<eol>]")
        return process_count != 0  # True if there were any
    # endregion Reboot Management

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

    def set_security_esm_package_status(self, operation, packages):
        """
        Set the security-ESM classification for the esm packages. Only needed for apt. No-op for tdnf, yum and zypper.
        """
        pass

    def separate_out_esm_packages(self, packages, package_versions):
        """
        Filter out packages from the list where the version matches the UA_ESM_REQUIRED string.
        Only needed for apt. No-op for tdnf, yum and zypper
        """
        esm_packages = []
        esm_package_versions = []
        esm_packages_found = False

        return packages, package_versions, esm_packages, esm_package_versions, esm_packages_found

    def get_package_install_expected_avg_time_in_seconds(self):
        return self.package_install_expected_avg_time_in_seconds

