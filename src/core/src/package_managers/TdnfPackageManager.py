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
import re

from abc import ABCMeta, abstractmethod
from core.src.core_logic.VersionComparator import VersionComparator
from core.src.bootstrap.Constants import Constants
from core.src.package_managers.PackageManager import PackageManager


class TdnfPackageManager(PackageManager):
    """Implementation of Tdnf package management operations"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(TdnfPackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)
        # Repo refresh
        self.cmd_clean_cache = "sudo tdnf clean expire-cache"
        self.cmd_repo_refresh = "sudo tdnf -q list updates"

        # Support to get updates and their dependencies
        self.single_package_check_versions = 'sudo tdnf list available <PACKAGE-NAME> '
        self.single_package_check_installed = 'sudo tdnf list installed <PACKAGE-NAME> '
        self.single_package_upgrade_simulation_cmd = 'sudo tdnf install --assumeno --skip-broken '

        # Install update
        self.single_package_upgrade_cmd = 'sudo tdnf -y install --skip-broken '

        # Package manager exit code(s)
        self.tdnf_exitcode_ok = 0
        self.tdnf_exitcode_on_no_action_for_install_update = 8
        self.commands_expecting_no_action_exitcode = [self.single_package_upgrade_simulation_cmd]

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.TDNF)
        self.STR_TOTAL_DOWNLOAD_SIZE = "Total download size: "
        self.version_comparator = VersionComparator()

        self.package_install_expected_avg_time_in_seconds = 90  # Setting a default value of 90 seconds as the avg time to install a package using tdnf, might be changed later if needed.

    def refresh_repo(self):
        self.composite_logger.log("[TDNF] Refreshing local repo...")
        self.invoke_package_manager(self.cmd_clean_cache)
        self.invoke_package_manager(self.cmd_repo_refresh)

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
    @abstractmethod
    def get_all_updates(self, cached=False):
        """Same behavior as get_available_updates, but higher performance with no filters"""
        pass
        return [], []  # only here to suppress a static syntax validation problem

    @abstractmethod
    def get_security_updates(self):
        pass

    @abstractmethod
    def get_other_updates(self):
        pass

    @abstractmethod
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

    # region Install Update
    def get_composite_package_identifier(self, package, package_version):
        package_without_arch, arch = self.get_product_name_and_arch(package)
        package_identifier = package_without_arch + '-' + str(package_version)
        if arch is not None:
            package_identifier += arch
        return package_identifier

    @abstractmethod
    def install_updates_fail_safe(self, excluded_packages):
        pass

    @abstractmethod
    def install_security_updates_azgps_coordinated(self):
        pass

    @abstractmethod
    def try_meet_azgps_coordinated_requirements(self):
        # type: () -> bool
        """ Returns true if the package manager meets the requirements for azgps coordinated security updates """
        return False
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

        cmd = self.single_package_upgrade_simulation_cmd + package_names
        output = self.invoke_package_manager(cmd)
        dependencies = self.extract_dependencies(output, packages)
        self.composite_logger.log_verbose("[TDNF] Resolved dependencies. [Command={0}][Packages={1}][DependencyCount={2}]".format(str(cmd), str(packages), len(dependencies)))
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
    @abstractmethod
    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        pass

    @abstractmethod
    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enabled and logs the default settings the machine comes with """
        pass

    @abstractmethod
    def backup_image_default_patch_configuration_if_not_exists(self):
        """ Records the default system settings for auto OS updates within patch extension artifacts for future reference.
        We only log the default system settings a VM comes with, any subsequent updates will not be recorded"""
        pass

    @abstractmethod
    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        pass

    @abstractmethod
    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value, patch_configuration_sub_setting_pattern_to_match):
        pass
    # endregion

    @abstractmethod
    def is_reboot_pending(self):
        """ Checks if there is a pending reboot on the machine. """
        pass

    @abstractmethod
    def do_processes_require_restart(self):
        """ Signals whether processes require a restart due to updates to files """
        pass

    @abstractmethod
    def set_security_esm_package_status(self, operation, packages):
        pass

    @abstractmethod
    def separate_out_esm_packages(self, packages, package_versions):
        pass

    def get_package_install_expected_avg_time_in_seconds(self):
        return self.package_install_expected_avg_time_in_seconds

