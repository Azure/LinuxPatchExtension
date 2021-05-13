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

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.YUM)
        self.STR_TOTAL_DOWNLOAD_SIZE = "Total download size: "

        # if an Auto Patching request comes in on a CentOS machine with Security and/or Critical classifications selected, we need to install all patches
        installation_included_classifications = [] if execution_config.included_classifications_list is None else execution_config.included_classifications_list
        if execution_config.maintenance_run_id is not None and execution_config.operation.lower() == Constants.INSTALLATION.lower() \
                and 'CentOS' in str(env_layer.platform.linux_distribution()) \
                and ('Critical' in installation_included_classifications or 'Security' in installation_included_classifications):
            self.composite_logger.log_debug("Updating classifications list to install all patches for the Auto Patching request since classification based patching is not available on CentOS machines")
            execution_config.included_classifications_list = [Constants.PACKAGE_CLASSIFICATIONS.__getitem__(1), Constants.PACKAGE_CLASSIFICATIONS.__getitem__(2), Constants.PACKAGE_CLASSIFICATIONS.__getitem__(4)]

    def refresh_repo(self):
        pass  # Refresh the repo is no ops in YUM

    # region Get Available Updates
    def invoke_package_manager(self, command):
        """Get missing updates using the command input"""
        self.composite_logger.log_debug('\nInvoking package manager using: ' + command)
        code, out = self.env_layer.run_command_output(command, False, False)
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
    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enabled and logs the default settings the machine comes with """
        pass

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        return True

    def backup_image_default_patch_configuration_if_not_exists(self):
        """ Records the default system settings for auto OS updates within patch extension artifacts for future reference.
        We only log the default system settings a VM comes with, any subsequent updates will not be recorded"""
        pass

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value):
        pass
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
