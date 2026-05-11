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

"""AzL4DnfPackageManager for Azure Linux L4"""
from abc import ABCMeta
from core.src.bootstrap.Constants import Constants
from core.src.package_managers.PackageManager import PackageManager


class AzL4DnfPackageManager(PackageManager):
    """Implementation of Azure Linux L4 DNF package management operations"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(AzL4DnfPackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)
        # TODO: Add AzL4 DNF specific initialization
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, 'dnf')

    __metaclass__ = ABCMeta  # For Python 3.0+, it changes to class Abstract(metaclass=ABCMeta)

    # ConfigurePatch Method
    def refresh_repo(self):
        """Refreshes the DNF repository cache and lists available updates by cleaning expired cache entries
        Commands:
        - sudo dnf clean expire-cache (cleans expired cache entries)
        - sudo dnf -q check-update (checks for available updates)
        """
        pass

    # AssessPatch method
    def invoke_package_manager_advanced(self, command, raise_on_exception=True):
        """Invokes the DNF package manager with standardized command execution, logging, and error handling
        Parameters:
        - command (string): The DNF command to execute
        - raise_on_exception (boolean): Whether to raise exception on non-zero exit code
        Returns:
        - Tuple of (output, return_code) from the command execution
        """
        pass

    # AssessPatch method
    def get_all_updates(self, cached=False):
        """Gets all missing updates available for the system and returns the cached updates list and versions list
        Cache Check Logic:
        - If cached=True and cache has data, return cached updates and versions immediately (high performance reuse)
        - If cache miss or cached=False, execute the DNF command to get fresh updates and populate cache
        Command:
        - sudo dnf -q check-update (checks for all available updates)
        1. If cached=True and cache has data, return cached results
        2. Execute command, parse output, cache results
        3. Return all_updates_cached and all_update_versions_cached
        """
        return [], []

     # AssessPatch method
    def get_security_updates(self):
        """Gets all missing security updates available for the system and returns packages and versions list
        Command:
        - sudo dnf -q check-update --security (checks for available security updates only)
        Returns:
        - List of security package names
        - List of corresponding security package versions
        """
        pass

    # AssessPatch method
    def get_other_updates(self):
        """Gets missing (non-security) updates. Record log and return
        """
        return [], []

    def set_max_patch_publish_date(self, max_patch_publish_date=str()):
        pass

    # Install Patch method
    def get_composite_package_identifier(self, package_name, package_version):
        """Creates a version+architecture-specific package identifier for install commands
        Parameters:
        - package_name (string): Name of the package (may include architecture)
        - package_version (string): Version of the package
        Returns:
        - String: Composite package identifier (e.g., "package-1.0.0.x86_64")
        """
        pass

    def install_updates_fail_safe(self, excluded_packages):
        pass

    # AssessPatch method
    def get_all_available_versions_of_package(self, package_name):
        """Returns a list of all available versions of a package
        Parameters:
        - package_name (string): Name of the package to get versions for
        Commands used:
        - sudo dnf list --available <package_name> (lists all available versions of the package)
        Returns:
        - List of all available package versions
        """
        return []

    # AssessPatch method
    def is_package_version_installed(self, package_name, package_version):
        """Checks if a specific package version is installed
        Parameters:
        - package_name (string): Name of the package
        - package_version (string): Version of the package to check
        Commands used:
        - sudo dnf list installed <package_name> (checks if specific package version is installed)
        Returns:
        - Boolean: True if the specific package version is installed, False otherwise
        """
        pass


    def get_dependent_list(self, packages):
        """Returns dependent list for the list of packages
        Parameters:
        - packages (list): List of package names to get dependencies for
        Commands used:
        - sudo dnf install --assumeno --skip-broken <packages> (simulates installation to find dependencies without actually installing)
        Returns: List of dependency package names required for the input packages
        """
        pass

    def get_product_name(self, package_name):
        pass

    def get_package_size(self, output):
        """Retrieves package size from installation output string
        Parameters:
        - output (string): The output string from DNF installation command
        Returns:
        - String: Package size (e.g., "15 M") or UNKNOWN_PACKAGE_SIZE if not found
        """
        pass

    # Install Patch method
    def install_security_updates_azgps_coordinated(self):
        """Installs security updates in Azure Linux 4 following strict safe deployment practices
        Commands used:
        - sudo dnf -y upgrade --security --skip-broken (installs security updates only)
        Returns:
        - Tuple of (return code, output) from the command execution
        """
        pass

    def try_meet_azgps_coordinated_requirements(self):
        """
        Do we need this for dnf5?
        """
        return False

    # ConfigurePatch Method
    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        pass

    # ConfigurePatch Method
    def disable_auto_os_update(self):
        """
        Disables auto OS updates on the machine only if they are enabled
        Comments from yashna : The current VM with AzLinux4 installed doesnt have dnf automatic/auto OS updates installed.
        Will we have this installed in other machines which leads to my question on whether we need this or not ?
        """
        pass

    def backup_image_default_patch_configuration_if_not_exists(self):
        """
        This method saves the original auto-update configuration so it can be restored later.
        """
        pass

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        pass

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value, patch_configuration_sub_setting_pattern_to_match):
        pass

    # Post Install method/ Install Patch
    def is_reboot_pending(self):
        """Checks if there is a pending reboot on the machine
        Returns:
        - Boolean: True if reboot is pending, False otherwise
        """
        pass

    # Post Install method / Install Patch
    def do_processes_require_restart(self):
        """Checks if processes require a restart due to updates
        Commands used:
        - sudo dnf -y install dnf-utils (installs dnf-utils if not already present)
        - sudo LANG=en_US.UTF8 needs-restarting -r (checks if processes require restart)
        Returns:
        - Boolean: True if processes require restart, False otherwise
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
        pass

    def separate_out_esm_packages(self, packages, package_versions):
        """No-op for dnf, tdnf, yum and zypper """
        pass

    def get_package_install_expected_avg_time_in_seconds(self):
        pass

    # ConfigurePatch method
    def revert_auto_os_update_to_system_default(self):
        """ Reverts the auto OS update patch state on the machine to its system default value, if one exists in our backup file """
        pass

