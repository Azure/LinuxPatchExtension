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
        self.single_package_upgrade_simulation_cmd = 'LANG=en_US.UTF8 sudo yum install --assumeno '

        # Install update
        self.single_package_upgrade_cmd = 'sudo yum -y install '
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
        self.yum_cron = 'yum cron'
        self.dnf_automatic = 'dnf-automatic'
        self.packagekit = 'PackageKit'
        self.auto_os_update_service_list = [self.yum_cron, self.dnf_automatic, self.packagekit]
        self.os_patch_configuration_settings_file_path = ''
        self.auto_update_service_enabled = False
        self.auto_update_config_pattern_match_text = ""
        self.download_updates_identifier_text = ""
        self.download_updates_value = ""
        self.apply_updates_identifier_text = ""
        self.apply_updates_value = ""
        self.enable_on_reboot_identifier_text = "enable_on_reboot"
        self.enable_on_reboot_value = False
        self.enable_on_reboot_check_cmd = ''

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
        if execution_config.maintenance_run_id is not None and execution_config.operation.lower() == Constants.INSTALLATION.lower() \
                and 'CentOS' in str(env_layer.platform.linux_distribution()) \
                and 'Critical' in installation_included_classifications and 'Security' in installation_included_classifications:
            self.composite_logger.log_debug("Updating classifications list to install all patches for the Auto Patching request since classification based patching is not available on CentOS machines")
            execution_config.included_classifications_list = [Constants.PackageClassification.CRITICAL, Constants.PackageClassification.SECURITY, Constants.PackageClassification.OTHER]

        # Known errors and the corresponding action items
        self.known_errors_and_fixes = {"SSL peer rejected your certificate as expired": self.fix_ssl_certificate_issue,
                                       "Error: Cannot retrieve repository metadata (repomd.xml) for repository": self.fix_ssl_certificate_issue,
                                       "Error: Failed to download metadata for repo":  self.fix_ssl_certificate_issue}
        
        self.yum_update_client_package = "sudo yum update -y --disablerepo='*' --enablerepo='*microsoft*'"

    def refresh_repo(self):
        pass  # Refresh the repo is no ops in YUM

    # region Get Available Updates
    def invoke_package_manager(self, command):
        """Get missing updates using the command input"""
        self.composite_logger.log_debug('\nInvoking package manager using: ' + command)
        code, out = self.env_layer.run_command_output(command, False, False)

        code, out = self.try_mitigate_issues_if_any(command, code, out)

        if code not in [self.yum_exitcode_ok, self.yum_exitcode_no_applicable_packages, self.yum_exitcode_updates_available]:
            self.composite_logger.log('[ERROR] Package manager was invoked using: ' + command)
            self.composite_logger.log_warning(" - Return code from package manager: " + str(code))
            self.composite_logger.log_warning(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.telemetry_writer.write_execution_error(command, code, out)
            error_msg = 'Unexpected return code (' + str(code) + ') from package manager on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
            # more return codes should be added as appropriate
        else:  # verbose diagnostic log
            self.composite_logger.log_debug("\n\n==[SUCCESS]===============================================================")
            self.composite_logger.log_debug(" - Return code from package manager: " + str(code))
            self.composite_logger.log_debug(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.composite_logger.log_debug("==========================================================================\n\n")
        return out

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_debug("\nDiscovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug(" - Returning cached package data.")
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        out = self.invoke_package_manager(self.yum_check)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)
        self.composite_logger.log_debug("Discovered " + str(len(self.all_updates_cached)) + " package entries.")
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates"""
        self.composite_logger.log("\nDiscovering 'security' packages...")
        self.install_yum_security_prerequisite()
        out = self.invoke_package_manager(self.yum_check_security)
        security_packages, security_package_versions = self.extract_packages_and_versions(out)

        if len(security_packages) == 0 and 'CentOS' in str(self.env_layer.platform.linux_distribution()):   # deliberately non-terminal
            self.composite_logger.log_warning("Classification-based patching is only supported on YUM if the machine is independently configured to receive classification information.")

        self.composite_logger.log("Discovered " + str(len(security_packages)) + " 'security' package entries.")
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates"""
        self.composite_logger.log("\nDiscovering 'other' packages...")
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

        self.composite_logger.log("Discovered " + str(len(other_packages)) + " 'other' package entries.")
        return other_packages, other_package_versions

    def install_yum_security_prerequisite(self):
        """Not installed by default in versions prior to RHEL 7. This step is idempotent and fast, so we're not writing more complex code."""
        self.composite_logger.log_debug('Ensuring RHEL yum-plugin-security is present.')
        code, out = self.env_layer.run_command_output(self.yum_check_security_prerequisite, False, False)
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output : \n|\t" + "\n|\t".join(out.splitlines()))
    # endregion

    # region Output Parser(s)
    def extract_packages_and_versions(self, output):
        """Returns packages and versions from given output"""
        packages, versions = self.extract_packages_and_versions_including_duplicates(output)
        packages, versions = self.dedupe_update_packages(packages, versions)
        return packages, versions

    def extract_packages_and_versions_including_duplicates(self, output):
        """Returns packages and versions from given output"""
        self.composite_logger.log_debug("\nExtracting package and version data...")
        packages = []
        versions = []
        package_extensions = ['.x86_64', '.noarch', '.i686']

        def is_package(chunk):
            # Using a list comprehension to determine if chunk is a package
            return len([p for p in package_extensions if p in chunk]) == 1

        lines = output.strip().split('\n')

        for line_index in range(0, len(lines)):
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
                self.composite_logger.log_debug(" - Inapplicable line (" + str(line_index) + "): " + lines[line_index])

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

        self.composite_logger.log_debug("[FAIL SAFE MODE] UPDATING PACKAGES USING COMMAND: " + cmd)
        self.invoke_package_manager(cmd)
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
        self.composite_logger.log_debug("\nCHECKING PACKAGE INSTALL STATUS FOR: " + str(package_name) + " (" + str(package_version) + ")")
        cmd = self.single_package_check_installed.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)

        for index, package in enumerate(packages):
            if package == package_name and (package_versions[index] == package_version):
                self.composite_logger.log_debug(" - Installed version match found.")
                return True
            else:
                self.composite_logger.log_debug(" - Did not match: " + package + " (" + package_versions[index] + ")")

        # sometimes packages are removed entirely from the system during installation of other packages
        # so let's check that the package is still needed before

        return False

    def get_dependent_list(self, package_name):
        # Sample output for the cmd 'sudo yum update --assumeno selinux-policy.noarch' is :
        #
        # Loaded plugins: langpacks, product-id, search-disabled-repos
        # Resolving Dependencies
        # --> Running transaction check
        # ---> Package selinux-policy.noarch 0:3.13.1-102.el7_3.15 will be updated
        # --> Processing Dependency: selinux-policy = 3.13.1-102.el7_3.15 for \
        # package: selinux-policy-targeted-3.13.1-102.el7_3.15.noarch
        # --> Processing Dependency: selinux-policy = 3.13.1-102.el7_3.15 for \
        # package: selinux-policy-targeted-3.13.1-102.el7_3.15.noarch
        # ---> Package selinux-policy.noarch 0:3.13.1-102.el7_3.16 will be an update
        # --> Running transaction check
        # ---> Package selinux-policy-targeted.noarch 0:3.13.1-102.el7_3.15 will be updated
        # ---> Package selinux-policy-targeted.noarch 0:3.13.1-102.el7_3.16 will be an update
        # --> Finished Dependency Resolution

        self.composite_logger.log_debug("\nRESOLVING DEPENDENCIES USING COMMAND: " + str(self.single_package_upgrade_simulation_cmd + package_name))
        dependent_updates = []

        output = self.invoke_package_manager(self.single_package_upgrade_simulation_cmd + package_name)
        lines = output.strip().split('\n')

        for line in lines:
            if line.find(" will be updated") < 0 and line.find(" will be an update") < 0 and line.find(" will be installed") < 0:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue

            updates_line = re.split(r'\s+', line.strip())
            if len(updates_line) != 7:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue

            dependent_package_name = self.get_product_name(updates_line[2])
            if len(dependent_package_name) != 0 and dependent_package_name != package_name:
                self.composite_logger.log_debug(" - Dependency detected: " + dependent_package_name)
                dependent_updates.append(dependent_package_name)

        self.composite_logger.log_debug(str(len(dependent_updates)) + " dependent updates were found for package '" + package_name + "'.")
        return dependent_updates

    def get_product_name(self, package_name):
        """Retrieve product name including arch where present"""
        return package_name

    def get_product_name_and_arch(self, package_name):
        """Splits out product name and architecture - if this is changed, modify in PackageFilter also"""
        architectures = ['.x86_64', '.noarch', '.i686']
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

    def get_package_version_without_epoch(self, package_version):
        """Returns the package version stripped of any epoch"""
        package_version_split = str(package_version).split(':', 1)

        if len(package_version_split) == 2:
            self.composite_logger.log_debug("   - Removed epoch from version (" + package_version + "): " + package_version_split[1])
            return package_version_split[1]

        if len(package_version_split) != 1:
            self.composite_logger.log_error("Unexpected error during version epoch removal from: " + package_version)

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
        self.yum_cron_install_cmd = 'yum -y install yum-cron'
        self.yum_cron_enable_on_reboot_check_cmd = 'systemctl is-enabled yum-cron'
        self.yum_cron_disable_on_reboot_cmd = 'systemctl disable yum-cron'
        self.yum_cron_config_pattern_match_text = ' = (no|yes)'
        self.yum_cron_download_updates_identifier_text = 'download_updates'
        self.yum_cron_apply_updates_identifier_text = 'apply_updates'
        self.yum_cron_enable_on_reboot_identifier_text = "enable_on_reboot"

    def __init_constants_for_dnf_automatic(self):
        self.dnf_automatic_configuration_file_path = '/etc/dnf/automatic.conf'
        self.dnf_automatic_install_check_cmd = 'systemctl list-unit-files --type=service | grep dnf-automatic.service'  # list-unit-files returns installed services, ref: https://www.freedesktop.org/software/systemd/man/systemctl.html#Unit%20File%20Commands
        self.dnf_automatic_install_cmd = 'yum -y install dnf-automatic'
        self.dnf_automatic_enable_on_reboot_check_cmd = 'systemctl is-enabled dnf-automatic.timer'
        self.dnf_automatic_disable_on_reboot_cmd = 'systemctl disable dnf-automatic.timer'
        self.dnf_automatic_config_pattern_match_text = ' = (no|yes)'
        self.dnf_automatic_download_updates_identifier_text = 'download_updates'
        self.dnf_automatic_apply_updates_identifier_text = 'apply_updates'
        self.dnf_automatic_enable_on_reboot_identifier_text = "enable_on_reboot"

    def __init_constants_for_packagekit(self):
        self.packagekit_configuration_file_path = '/etc/PackageKit/PackageKit.conf'
        self.packagekit_install_check_cmd = 'systemctl list-unit-files --type=service | grep packagekit.service'  # list-unit-files returns installed services, ref: https://www.freedesktop.org/software/systemd/man/systemctl.html#Unit%20File%20Commands
        self.packagekit_install_cmd = 'yum -y install gnome-packagekit PackageKit-yum'
        self.packagekit_enable_on_reboot_check_cmd = 'systemctl is-enabled packagekit'
        self.packagekit_disable_on_reboot_cmd = 'systemctl disable packagekit'
        self.packagekit_config_pattern_match_text = ' = (false|true)'
        self.packagekit_download_updates_identifier_text = 'GetPreparedUpdates'  # todo: dummy value, get real value
        self.packagekit_apply_updates_identifier_text = 'WritePreparedUpdates'
        self.packagekit_enable_on_reboot_identifier_text = "enable_on_reboot"

    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        self.composite_logger.log("Fetching the current automatic OS patch state on the machine...")

        # This function can be called for a specific auto update service (when called from disable auto OS updates code flow), or for all auto OS update services (when called from ConfigurePatchingProcessor to fetch status)
        # apply_updates_identifier_text will be initialized only when this function is called for a specific auto update service. If not initialized, we need to check status from all services
        # todo: revisit this, we need to check apply_updates for each service and decide on enable or disable based on all statuses
        if self.apply_updates_identifier_text == "":
            for os_auto_update_service in self.auto_os_update_service_list:
                if os_auto_update_service == self.yum_cron:
                    self.composite_logger.log_debug("Fetching current automatic OS patch state in yum-cron service. This includes checks on current enable state and whether it is set to enable on reboot")
                    self.__init_auto_update_for_yum_cron()
                    self.__get_current_auto_os_updates_setting_on_machine()
                    if self.enable_on_reboot_value or self.apply_updates_value.lower() == 'yes':
                        break
                elif os_auto_update_service == self.dnf_automatic:
                    self.composite_logger.log_debug("Fetching current automatic OS patch state in dnf-automatic service. This includes checks on current state and whether it is set to enable on reboot")
                    self.__init_auto_update_for_dnf_automatic()
                    self.__get_current_auto_os_updates_setting_on_machine()
                    if self.enable_on_reboot_value or self.apply_updates_value.lower() == 'yes':
                        break
                elif os_auto_update_service == self.packagekit:
                    self.composite_logger.log_debug("Fetching current automatic OS patch state in packagekit service. This includes checks on current state and whether it is set to enable on reboot")
                    self.__init_auto_update_for_packagekit()
                    self.__get_current_auto_os_updates_setting_on_machine()
                    if self.enable_on_reboot_value or self.apply_updates_value.lower() == 'true':
                        break
        else:
            self.__get_current_auto_os_updates_setting_on_machine()  # Since auto update service is already identified, this will fetch config for that service

        if (self.apply_updates_value.lower() == 'no' or self.apply_updates_value.lower() == 'false') and not self.enable_on_reboot_value:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.DISABLED
        elif self.apply_updates_value.lower() == 'yes' or self.apply_updates_value.lower() == 'true' or self.enable_on_reboot_value:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.ENABLED
        else:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.UNKNOWN

        self.composite_logger.log_debug("Overall Auto OS Patch State based on current enable status and enable on reboot status [OverallAutoOSPatchState={0}] [CurrentAutoOSPatchEnabled={1}] [AutoOSPatchSetToEnableOnReboot={2}]"
                                        .format(str(current_auto_os_patch_state), str(self.apply_updates_value), self.enable_on_reboot_value))
        return current_auto_os_patch_state

    def __init_auto_update_for_yum_cron(self):
        """ Initializes all generic auto OS update variables with the config values for yum cron service """
        self.os_patch_configuration_settings_file_path = self.yum_cron_configuration_settings_file_path
        self.download_updates_identifier_text = self.yum_cron_download_updates_identifier_text
        self.apply_updates_identifier_text = self.yum_cron_apply_updates_identifier_text
        self.auto_update_config_pattern_match_text = self.yum_cron_config_pattern_match_text
        self.enable_on_reboot_check_cmd = self.yum_cron_enable_on_reboot_check_cmd

    def __init_auto_update_for_dnf_automatic(self):
        """ Initializes all generic auto OS update variables with the config values for dnf automatic service """
        self.os_patch_configuration_settings_file_path = self.dnf_automatic_configuration_file_path
        self.download_updates_identifier_text = self.dnf_automatic_download_updates_identifier_text
        self.apply_updates_identifier_text = self.dnf_automatic_apply_updates_identifier_text
        self.auto_update_config_pattern_match_text = self.dnf_automatic_config_pattern_match_text
        self.enable_on_reboot_check_cmd = self.dnf_automatic_enable_on_reboot_check_cmd

    def __init_auto_update_for_packagekit(self):
        """ Initializes all generic auto OS update variables with the config values for packagekit service """
        self.os_patch_configuration_settings_file_path = self.packagekit_configuration_file_path
        self.download_updates_identifier_text = self.packagekit_download_updates_identifier_text
        self.apply_updates_identifier_text = self.packagekit_apply_updates_identifier_text
        self.auto_update_config_pattern_match_text = self.packagekit_config_pattern_match_text
        self.enable_on_reboot_check_cmd = self.packagekit_enable_on_reboot_check_cmd

    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enable_on_reboot and logs the default settings the machine comes with """
        try:
            self.composite_logger.log_debug("Disabling auto OS updates in all identified services...")
                # todo: Better way to implement this? Keeping functions separate since not all services have the same steps to disable and identifying the service specific commands is easier this way
            self.disable_auto_os_update_for_yum_cron()
            self.disable_auto_os_update_for_dnf_automatic()
            self.disable_auto_os_update_for_packagekit()
            self.composite_logger.log_debug("Successfully disabled auto OS updates")

        except Exception as error:
            self.composite_logger.log_error("Could not disable auto OS updates. [Error={0}]".format(repr(error)))
            raise

    def disable_auto_os_update_for_yum_cron(self):
        """ Disables auto OS updates, using yum cron service, and logs the default settings the machine comes with """
        self.composite_logger.log("Disabling auto OS updates using yum cron")
        auto_update_service_installed = True
        self.__init_auto_update_for_yum_cron()

        if not self.is_auto_update_service_installed(self.yum_cron_install_check_cmd):
            self.composite_logger.log_debug("Installing yum-cron...")
            auto_update_service_installed = self.install_auto_update_service(self.yum_cron_install_cmd)

        if not auto_update_service_installed:
            self.composite_logger.log("Could not install yum-cron on the machine.")
            return

        self.backup_image_default_patch_configuration_if_not_exists()
        self.composite_logger.log_debug("Preemptively disabling auto OS updates using yum-cron")
        self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "no", self.yum_cron_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "no", self.yum_cron_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.yum_cron_disable_on_reboot_cmd)

        self.composite_logger.log("Successfully disabled auto OS updates using yum-cron")

    def disable_auto_os_update_for_dnf_automatic(self):
        """ Disables auto OS updates, using dnf-automatic service, and logs the default settings the machine comes with """
        self.composite_logger.log("Disabling auto OS updates using dnf automatic")
        auto_update_service_installed = True
        self.__init_auto_update_for_dnf_automatic()

        if not self.is_auto_update_service_installed(self.dnf_automatic_install_check_cmd):
            self.composite_logger.log_debug("Installing dnf-automatic...")
            auto_update_service_installed = self.install_auto_update_service(self.dnf_automatic_install_cmd)

        if not auto_update_service_installed:
            self.composite_logger.log("Could not install dnf-automatic on the machine.")
            return

        self.backup_image_default_patch_configuration_if_not_exists()
        self.composite_logger.log_debug("Preemptively disabling auto OS updates using dnf-automatic")
        self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "no", self.dnf_automatic_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "no", self.dnf_automatic_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.dnf_automatic_disable_on_reboot_cmd)

        self.composite_logger.log("Successfully disabled auto OS updates using dnf-automatic")

    def disable_auto_os_update_for_packagekit(self):
        """ Disables auto OS updates, using packagekit service, and logs the default settings the machine comes with """
        self.composite_logger.log("Disabling auto OS updates using packagekit")
        auto_update_service_installed = True
        self.__init_auto_update_for_packagekit()

        if not self.is_auto_update_service_installed(self.packagekit_install_check_cmd):
            self.composite_logger.log_debug("Installing packagekit...")
            auto_update_service_installed = self.install_auto_update_service(self.packagekit_install_cmd)

        if not auto_update_service_installed:
            self.composite_logger.log("Could not install packagekit on the machine.")
            return

        self.backup_image_default_patch_configuration_if_not_exists()
        self.composite_logger.log_debug("Preemptively disabling auto OS updates using packagekit")
        #todo: uncomment after finding the correct value
        # self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "false", self.dnf_automatic_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "false", self.dnf_automatic_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.dnf_automatic_disable_on_reboot_cmd)

        self.composite_logger.log("Successfully disabled auto OS updates using dnf-automatic")

    def is_service_set_to_enable_on_reboot(self, command):
        """ Checking if auto update is enable_on_reboot on the machine. An enable_on_reboot service will be activated (if currently inactive) on machine reboot """
        self.composite_logger.log_debug("Checking if auto update service is set to enable on reboot...")
        code, out = self.env_layer.run_command_output(command, False, False)
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))
        if len(out.strip()) > 0 and code == 0 and 'enabled' in out:
            self.composite_logger.log_debug("Auto OS update will enable on reboot")
            return True
        self.composite_logger.log_debug("Auto OS update will NOT enable on reboot")
        return False

    def backup_image_default_patch_configuration_if_not_exists(self):
        """ Records the default system settings for auto OS updates within patch extension artifacts for future reference.
        We only log the default system settings a VM comes with, any subsequent updates will not be recorded"""
        try:
            if not self.image_default_patch_configuration_backup_exists():
                self.__get_current_auto_os_updates_setting_on_machine()

                backup_image_default_patch_configuration_json = {
                    self.download_updates_identifier_text: self.download_updates_value,
                    self.apply_updates_identifier_text: self.apply_updates_value,
                    self.enable_on_reboot_identifier_text: self.enable_on_reboot_value
                }

                self.composite_logger.log_debug("Logging default system configuration settings for auto OS updates. [Settings={0}] [Log file path={1}]"
                                                .format(str(backup_image_default_patch_configuration_json), self.image_default_patch_configuration_backup_path))
                self.env_layer.file_system.write_with_retry(self.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(backup_image_default_patch_configuration_json)), mode='w+')
        except Exception as error:
            error_message = "Exception during fetching and logging default auto update settings on the machine. [Exception={0}]".format(repr(error))
            self.composite_logger.log_error(error_message)
            self.status_handler.add_error_to_status(error_message, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        if self.download_updates_identifier_text in image_default_patch_configuration_backup and self.apply_updates_identifier_text in image_default_patch_configuration_backup and self.enable_on_reboot_identifier_text in image_default_patch_configuration_backup:
            self.composite_logger.log_debug("Extension already has a valid backup of the default system configuration settings for auto OS updates.")
            return True
        else:
            self.composite_logger.log_error("Extension does not have a valid backup of the default system configuration settings for auto OS updates.")
            return False

    def __get_current_auto_os_updates_setting_on_machine(self):
        """ Gets all the update settings related to auto OS updates currently set on the machine """
        try:
            self.enable_on_reboot_value = self.is_service_set_to_enable_on_reboot(self.enable_on_reboot_check_cmd)

            self.composite_logger.log_debug("Checking if auto updates are currently enabled...")
            image_default_patch_configuration = self.env_layer.file_system.read_with_retry(self.os_patch_configuration_settings_file_path, raise_if_not_found=False)
            if image_default_patch_configuration is not None:
                settings = image_default_patch_configuration.strip().split('\n')
                for setting in settings:
                    match = re.search(self.download_updates_identifier_text + self.auto_update_config_pattern_match_text, str(setting))
                    if match is not None:
                        self.download_updates_value = match.group(1)

                    match = re.search(self.apply_updates_identifier_text + self.auto_update_config_pattern_match_text, str(setting))
                    if match is not None:
                        self.apply_updates_value = match.group(1)

            if self.download_updates_value == "":
                self.composite_logger.log_debug("Machine did not have any value set for [Setting={0}]".format(str(self.download_updates_identifier_text)))

            if self.apply_updates_value == "":
                self.composite_logger.log_debug("Machine did not have any value set for [Setting={0}]".format(str(self.apply_updates_identifier_text)))

            elif self.apply_updates_value == "yes":
                self.composite_logger.log_debug("Auto updates are currently enabled")
            elif self.apply_updates_value == "no":
                self.composite_logger.log_debug("Auto updates are NOT currently enabled")

        except Exception as error:
            raise Exception("Error occurred in fetching default auto OS updates from the machine. [Exception={0}]".format(repr(error)))

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value="no", config_pattern_match_text=""):
        """ Updates (or adds if it doesn't exist) the given patch_configuration_sub_setting with the given value in os_patch_configuration_settings_file """
        try:
            # note: adding space between the patch_configuration_sub_setting and value since, we will have to do that if we have to add a patch_configuration_sub_setting that did not exist before
            self.composite_logger.log("Updating system configuration settings for auto OS updates. [Patch Configuration Sub Setting={0}] [Value={1}]".format(str(patch_configuration_sub_setting), value))
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

            # ToDo: This adds some whitespace at the beginning of the first line in the settings file which is auto adjusted in the file later, so shouldn't have any issues right now. strip()/lstrip() on the string, does not work, will have to test accross versions and identify the impact
            self.env_layer.file_system.write_with_retry(self.os_patch_configuration_settings_file_path, '{0}'.format(updated_patch_configuration_sub_setting.lstrip()), mode='w+')
        except Exception as error:
            error_msg = "Error occurred while updating system configuration settings for auto OS updates. [Patch Configuration={0}] [Error={1}]".format(str(patch_configuration_sub_setting), repr(error))
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def disable_auto_update_on_reboot(self, command):
        self.composite_logger.log_debug("Disabling auto update on reboot using command: " + str(command))
        code, out = self.env_layer.run_command_output(command, False, False)
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))

        if code != 0:
            self.composite_logger.log('[ERROR] Command invoked: ' + command)
            self.telemetry_writer.write_execution_error(command, code, out)
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

        self.composite_logger.log_debug("Auto update on reboot disabled")

    def is_auto_update_service_installed(self, install_check_cmd):
        """ Checks if the auto update service is enable_on_reboot on the VM """
        self.composite_logger.log_debug("Checking if auto update service is installed...")
        code, out = self.env_layer.run_command_output(install_check_cmd, False, False)
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))
        if len(out.strip()) > 0 and code == 0:
            self.composite_logger.log_debug("Auto OS update is installed on the machine")
            return True
        else:
            self.composite_logger.log_debug("Auto OS update is NOT installed on the machine")
            return False

    def install_auto_update_service(self, command):
        self.composite_logger.log_debug("Installing auto updates using command: " + str(command))
        code, out = self.env_layer.run_command_output(command, False, False)
        if code != 0:
            self.composite_logger.log('[ERROR] Package manager was invoked using: ' + command)
            self.composite_logger.log_warning(" - Return code from package manager: " + str(code))
            self.composite_logger.log_debug(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            return False
        else:
            self.composite_logger.log_debug("\n\n==[SUCCESS]===============================================================")
            self.composite_logger.log_debug(" - Return code from package manager: " + str(code))
            self.composite_logger.log_debug(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.composite_logger.log_debug("==========================================================================\n\n")
            self.composite_logger.log_debug("\nAuto update service installed.")
            return True

    # endregion

    # region Handling known errors
    def try_mitigate_issues_if_any(self, command, code, out):
        """ Attempt to fix the errors occurred while executing a command. Repeat check until no issues found """
        if "Error" in out or "Errno" in out:
            issue_mitigated = self.check_known_issues_and_attempt_fix(out)
            if issue_mitigated:
                self.composite_logger.log_debug('\nPost mitigation, invoking package manager again using: ' + command)
                code_after_fix_attempt, out_after_fix_attempt = self.env_layer.run_command_output(command, False, False)
                return self.try_mitigate_issues_if_any(command, code_after_fix_attempt, out_after_fix_attempt)
        return code, out

    def check_known_issues_and_attempt_fix(self, output):
        """ Checks if issue falls into known issues and attempts to mitigate """
        self.composite_logger.log_debug("Output from package manager containing error: \n|\t" + "\n|\t".join(output.splitlines()))
        self.composite_logger.log_debug("\nChecking if this is a known error...")
        for error in self.known_errors_and_fixes:
            if error in output:
                self.composite_logger.log_debug("\nFound a match within known errors list, attempting a fix...")
                self.known_errors_and_fixes[error]()
                return True

        self.composite_logger.log_debug("\nThis is not a known error for the extension and will require manual intervention")
        return False

    def fix_ssl_certificate_issue(self):
        command = self.yum_update_client_package
        self.composite_logger.log_debug("\nUpdating client package to avoid errors from older certificates using command: [Command={0}]".format(str(command)))
        code, out = self.env_layer.run_command_output(command, False, False)
        if code != self.yum_exitcode_no_applicable_packages:
            self.composite_logger.log('[ERROR] Package manager was invoked using: ' + command)
            self.composite_logger.log_warning(" - Return code from package manager: " + str(code))
            self.composite_logger.log_warning(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.telemetry_writer.write_execution_error(command, code, out)
            error_msg = 'Unexpected return code (' + str(code) + ') from package manager on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("\n\n==[SUCCESS]===============================================================")
            self.composite_logger.log_debug(" - Return code from package manager: " + str(code))
            self.composite_logger.log_debug(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.composite_logger.log_debug("==========================================================================\n\n")
            self.composite_logger.log_debug("\nClient package update complete.")
    # endregion

    def do_processes_require_restart(self):
        """Signals whether processes require a restart due to updates"""
        self.composite_logger.log_debug("Checking if process requires reboot")
        # Checking using yum-utils
        self.composite_logger.log_debug("Ensuring yum-utils is present.")
        code, out = self.env_layer.run_command_output(self.yum_utils_prerequisite, False, False)  # idempotent, doesn't install if already present
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))

        # Checking for restart for distros with -r flag such as RHEL 7+
        code, out = self.env_layer.run_command_output(self.needs_restarting_with_flag, False, False)
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))
        if out.find("Reboot is required") < 0:
            self.composite_logger.log_debug(" - Reboot not detected to be required (L1).")
        else:
            self.composite_logger.log_debug(" - Reboot is detected to be required (L1).")
            return True

        # Checking for restart for distro without -r flag such as RHEL 6 and CentOS 6
        if str(self.env_layer.platform.linux_distribution()[1]).split('.')[0] == '6':
            code, out = self.env_layer.run_command_output(self.needs_restarting, False, False)
            self.composite_logger.log_debug(" - Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))
            if len(out.strip()) == 0 and code == 0:
                self.composite_logger.log_debug(" - Reboot not detected to be required (L2).")
            else:
                self.composite_logger.log_debug(" - Reboot is detected to be required (L2).")
                return True

        # Double-checking using yum ps (where available)
        self.composite_logger.log_debug("Ensuring yum-plugin-ps is present.")
        code, out = self.env_layer.run_command_output(self.yum_ps_prerequisite, False, False)  # idempotent, doesn't install if already present
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))

        output = self.invoke_package_manager(self.yum_ps)
        lines = output.strip().split('\n')

        process_list_flag = False
        process_count = 0
        process_list_verbose = ""

        for line in lines:
            if not process_list_flag:  # keep going until the process list starts
                if line.find("pid") < 0 and line.find("proc") < 0 and line.find("uptime") < 0:
                    self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                    continue
                else:
                    self.composite_logger.log_debug(" - Process list started: " + str(line))
                    process_list_flag = True
                    continue

            process_details = re.split(r'\s+', line.strip())
            if len(process_details) < 7:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue
            else:
                self.composite_logger.log_debug(" - Applicable line: " + str(line))
                process_count += 1
                process_list_verbose += process_details[1] + " (" + process_details[0] + "), "  # process name and id

        self.composite_logger.log(" - Processes requiring restart (" + str(process_count) + "): [" + process_list_verbose + "<eol>]")
        return process_count != 0  # True if there were any
