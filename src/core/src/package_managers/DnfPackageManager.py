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

"""DnfPackageManager for Azure Linux L4 and RHEL 10"""
from abc import ABCMeta
import json
from core.src.bootstrap.Constants import Constants
from core.src.package_managers.PackageManager import PackageManager


class DnfPackageManager(PackageManager):
    """Implementation of Azure Linux L4/RHEL 10 DNF5 package management operations"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(DnfPackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)

        self.cmd_clean_cache = "sudo dnf5 -q clean expire-cache"
        self.cmd_repo_refresh = "sudo dnf5 -q check-update "

        # TODO: Add AzL4/Red hat 10 DNF5 specific initialization
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, 'dnf5')

        # auto OS updates
        self.current_auto_os_update_service = None
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

    __metaclass__ = ABCMeta  # For Python 3.0+, it changes to class Abstract(metaclass=ABCMeta)

    def refresh_repo(self):
        self.composite_logger.log("[DNF] Refreshing local repo...")
        self.invoke_package_manager(self.cmd_clean_cache)
        self.invoke_package_manager(self.cmd_repo_refresh)

    # AssessPatch method
    def invoke_package_manager_advanced(self, command, raise_on_exception=True):
        self.composite_logger.log_verbose("[DNF] Invoking package manager. [Command={0}]".format(str(command)))
        # env_layer.run_command_output returns (code, output)
        code, out = self.env_layer.run_command_output(command, False, False)

        # Treat exit code 0 as success. No updates available.
        if code == 0:
            self.composite_logger.log_debug('[DNF] Invoked package manager. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))

        elif code == 100:
            # Updates available
            self.composite_logger.log_debug(
                '[DNF] Updates available. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
        else:
            self.composite_logger.log_warning('[ERROR] Customer environment error. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
            error_msg = "Customer environment error: Investigate and resolve unexpected return code ({0}) from package manager on command: {1}".format(str(code), command)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            if raise_on_exception:
                raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

        return out, code

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
        raise NotImplementedError("DNF: get_all_updates not implemented yet")

     # AssessPatch method
    def get_security_updates(self):
        """Gets all missing security updates available for the system and returns packages and versions list
        Command:
        - sudo dnf -q check-update --security (checks for available security updates only)
        Returns:
        - List of security package names
        - List of corresponding security package versions
        """
        raise NotImplementedError("DNF: get_security_updates not implemented yet")

    # AssessPatch method
    def get_other_updates(self):
        """Gets missing (non-security) updates. Record log and return
        """
        return [], []

    def set_max_patch_publish_date(self, max_patch_publish_date=str()):
        raise NotImplementedError("DNF: set_max_patch_publish_date not implemented yet")

    # Install Patch method
    def get_composite_package_identifier(self, package_name, package_version):
        """Creates a version+architecture-specific package identifier for install commands
        Parameters:
        - package_name (string): Name of the package (may include architecture)
        - package_version (string): Version of the package
        Returns:
        - String: Composite package identifier (e.g., "package-1.0.0.x86_64")
        """
        raise NotImplementedError("DNF: get_composite_package_identifier not implemented yet")

    def install_updates_fail_safe(self, excluded_packages):
        raise NotImplementedError("DNF: install_updates_fail_safe not implemented yet")

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
        raise NotImplementedError("DNF: get_all_available_versions_of_package not implemented yet")

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
        raise NotImplementedError("DNF: is_package_version_installed not implemented yet")


    def get_dependent_list(self, packages):
        """Returns dependent list for the list of packages
        Parameters:
        - packages (list): List of package names to get dependencies for
        Commands used:
        - sudo dnf install --assumeno --skip-broken <packages> (simulates installation to find dependencies without actually installing)
        Returns: List of dependency package names required for the input packages
        """
        raise NotImplementedError("DNF: get_dependent_list not implemented yet")

    def get_product_name(self, package_name):
        raise NotImplementedError("DNF: get_product_name not implemented yet")

    def get_package_size(self, output):
        """Retrieves package size from installation output string
        Parameters:
        - output (string): The output string from DNF installation command
        Returns:
        - String: Package size (e.g., "15 M") or UNKNOWN_PACKAGE_SIZE if not found
        """
        raise NotImplementedError("DNF: get_package_size not implemented yet")

    # Install Patch method
    def install_security_updates_azgps_coordinated(self):
        """Installs security updates in Azure Linux 4 following strict safe deployment practices
        Commands used:
        - sudo dnf -y upgrade --security --skip-broken (installs security updates only)
        Returns:
        - Tuple of (return code, output) from the command execution
        """
        raise NotImplementedError("DNF: install_security_updates_azgps_coordinated not implemented yet")

    def try_meet_azgps_coordinated_requirements(self):
        """
        Do we need this for dnf?
        """
        raise NotImplementedError("DNF: try_meet_azgps_coordinated_requirements not implemented yet")

    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        self.composite_logger.log("[DNF] Fetching the current automatic OS patch state on the machine...")

        current_auto_os_patch_state_for_dnf5_automatic = self.__get_current_auto_os_patch_state_for_dnf5_automatic()

        self.composite_logger.log("[DNF] OS patch state per auto OS update service: [dnf5-automatic={0}]".format(str(current_auto_os_patch_state_for_dnf5_automatic)))

        if current_auto_os_patch_state_for_dnf5_automatic == Constants.AutomaticOSPatchStates.ENABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.ENABLED
        elif current_auto_os_patch_state_for_dnf5_automatic == Constants.AutomaticOSPatchStates.DISABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.DISABLED
        else:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.UNKNOWN

        self.composite_logger.log_debug("[DNF] Overall Auto OS Patch State based on all auto OS update service states [OverallAutoOSPatchState={0}]".format(str(current_auto_os_patch_state)))
        return current_auto_os_patch_state

    def __get_current_auto_os_patch_state_for_dnf5_automatic(self):
        """ Gets current auto OS update patch state for dnf5-automatic """
        self.composite_logger.log_debug("[DNF] Fetching current automatic OS patch state in dnf5-automatic service. This includes checks on whether the service is installed, current auto patch enable state and whether it is set to enable on reboot")
        self.__init_auto_update_for_dnf5_automatic()

        is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

        if not is_service_installed:
            return Constants.AutomaticOSPatchStates.DISABLED

        if enable_on_reboot_value:
            return Constants.AutomaticOSPatchStates.ENABLED

        return Constants.AutomaticOSPatchStates.DISABLED

    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enabled and logs the default settings the machine comes with """
        try:
            self.composite_logger.log_verbose("[DNF] Disabling auto OS updates in all identified services...")
            self.__disable_auto_os_update_for_dnf5_automatic()
            self.composite_logger.log_debug("[DNF] Successfully disabled auto OS updates")

        except Exception as error:
            self.composite_logger.log_error("[DNF] Could not disable auto OS updates. [Error={0}]".format(repr(error)))
            raise

    def __disable_auto_os_update_for_dnf5_automatic(self):
        """ Disables auto OS updates, using dnf5-automatic service, and logs the default settings the machine comes with """
        self.composite_logger.log_verbose("[DNF] Disabling auto OS updates using dnf5-automatic")
        self.__init_auto_update_for_dnf5_automatic()

        self.backup_image_default_patch_configuration_if_not_exists()

        if not self.is_auto_update_service_installed(self.dnf5_automatic_install_check_cmd):
            self.composite_logger.log_debug("[DNF] Cannot disable as dnf5-automatic is not installed on the machine")
            return

        self.composite_logger.log_verbose("[DNF] Preemptively disabling auto OS updates using dnf5-automatic")
        self.disable_auto_update_on_reboot(self.dnf5_automatic_disable_on_reboot_cmd)

        self.composite_logger.log_debug("[DNF] Successfully disabled auto OS updates using dnf5-automatic")

    def disable_auto_update_on_reboot(self, command):
        """ Disables auto update on reboot by executing systemctl command """
        self.composite_logger.log_verbose("[DNF] Disabling auto update on reboot. [Command={0}] ".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != 0:
            self.composite_logger.log_error("[DNF][ERROR] Error disabling auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("[DNF] Disabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))

    def backup_image_default_patch_configuration_if_not_exists(self):
        """
        This method saves the original auto-update configuration so it can be restored later.
        """
        try:
            self.composite_logger.log_debug("[DNF] Ensuring there is a backup of the default patch state for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))

            # read existing backup since it also contains backup from other update services. We need to preserve any existing data within the backup file
            image_default_patch_configuration_backup = {}
            if self.image_default_patch_configuration_backup_exists():
                try:
                    image_default_patch_configuration_backup = json.loads(self.env_layer.file_system.read_with_retry(self.image_default_patch_configuration_backup_path))
                except Exception as error:
                    self.composite_logger.log_error("[DNF] Unable to read backup for default patch state. Will attempt to re-write. [Exception={0}]".format(repr(error)))

            # verify if existing backup is valid if not, write to backup
            is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)
            if is_backup_valid:
                self.composite_logger.log_debug("[DNF] Since extension has a valid backup, no need to log the current settings again. [Default Auto OS update settings={0}] [File path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
            else:
                self.composite_logger.log_debug("[DNF] Since the backup is invalid, will add a new backup with the current auto OS update settings")
                self.composite_logger.log_debug("[DNF] Fetching current auto OS update settings for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
                is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

                backup_image_default_patch_configuration_json_to_add = {
                    self.current_auto_os_update_service: {
                        self.enable_on_reboot_identifier_text: enable_on_reboot_value,
                        self.installation_state_identifier_text: is_service_installed
                    }
                }

                image_default_patch_configuration_backup.update(backup_image_default_patch_configuration_json_to_add)

                self.composite_logger.log_debug("[DNF] Logging default system configuration settings for auto OS updates. [Settings={0}] [Log file path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
                self.env_layer.file_system.write_with_retry(self.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(image_default_patch_configuration_backup)), mode='w+')
        except Exception as error:
            error_message = "[DNF] Exception during fetching and logging default auto update settings on the machine. [Exception={0}]".format(repr(error))
            self.composite_logger.log_error(error_message)
            self.status_handler.add_error_to_status(error_message, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        # Validate backup JSON for dnf5 automatic service
        try:
            if self.dnf5_auto_os_update_service in image_default_patch_configuration_backup \
                    and self.dnf5_automatic_enable_on_reboot_identifier_text in image_default_patch_configuration_backup[self.dnf5_auto_os_update_service] \
                    and self.dnf5_automatic_installation_state_identifier_text in image_default_patch_configuration_backup[self.dnf5_auto_os_update_service]:
                self.composite_logger.log_debug("[DNF] Extension has a valid backup for default dnf5-automatic configuration settings")
                return True
            else:
                self.composite_logger.log_debug("[DNF] Extension does not have a valid backup for default dnf5-automatic configuration settings")
                return False
        except Exception:
            return False

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value, patch_configuration_sub_setting_pattern_to_match):
        raise NotImplementedError("DNF: update_os_patch_configuration_sub_setting not implemented yet")

    # Post Install method/ Install Patch
    def is_reboot_pending(self):
        """Checks if there is a pending reboot on the machine
        Returns:
        - Boolean: True if reboot is pending, False otherwise
        """
        raise NotImplementedError("DNF: is_reboot_pending not implemented yet")

    # Post Install method / Install Patch
    def do_processes_require_restart(self):
        """Checks if processes require a restart due to updates
        Commands used:
        - sudo dnf -y install dnf-utils (installs dnf-utils if not already present)
        - sudo LANG=en_US.UTF8 needs-restarting -r (checks if processes require restart)
        Returns:
        - Boolean: True if processes require restart, False otherwise
        """
        raise NotImplementedError("DNF: do_processes_require_restart not implemented yet")

    def add_arch_dependencies(self, package_manager, package, version, packages, package_versions, package_and_dependencies, package_and_dependency_versions):
        """
         Unnecessary for DNF because the package manager already handles multi-architecture dependencies automatically
         Command Used to confirm above: sudo dnf -y install jq
        """
        return

    def set_security_esm_package_status(self, operation, packages):
        """No-op for dnf, tdnf, yum and zypper """
        return

    def separate_out_esm_packages(self, packages, package_versions):
        """No-op for dnf, tdnf, yum and zypper """
        return

    def get_package_install_expected_avg_time_in_seconds(self):
        raise NotImplementedError("DNF: get_package_install_expected_avg_time_in_seconds not implemented yet")

    # ConfigurePatch method
    def revert_auto_os_update_to_system_default(self):
        """ Reverts the auto OS update patch state on the machine to its system default value, if one exists in our backup file """
        raise NotImplementedError("DNF: revert_auto_os_update_to_system_default not implemented yet")

    # region auto OS updates
    def __init_constants_for_dnf5_automatic(self):
        self.dnf5_automatic_configuration_service = 'systemctl cat dnf5-automatic.service'
        self.dnf5_automatic_install_check_cmd = 'rpm -qa | grep dnf5-plugin-automatic'
        self.dnf5_automatic_enable_on_reboot_check_cmd = 'systemctl is-enabled dnf5-automatic.timer'
        self.dnf5_automatic_disable_on_reboot_cmd = 'systemctl disable --now dnf5-automatic.timer'
        self.dnf5_automatic_enable_on_reboot_cmd = 'systemctl enable --now dnf5-automatic.timer'
        self.dnf5_automatic_config_pattern_match_text = None
        # Detect them from ExecStart flags instead of a file:
        self.dnf5_automatic_download_updates_identifier_text = '--downloadupdates'
        self.dnf5_automatic_apply_updates_identifier_text = '--installupdates'
        self.dnf5_automatic_enable_on_reboot_identifier_text = "enable_on_reboot"
        self.dnf5_automatic_installation_state_identifier_text = "installation_state"
        self.dnf5_auto_os_update_service = "dnf5-automatic"

    def __init_auto_update_for_dnf5_automatic(self):
        """ Initializes all generic auto OS update variables with the config values for dnf5 automatic service """
        self.os_patch_configuration_settings_read_cmd = self.dnf5_automatic_configuration_service
        self.download_updates_identifier_text = self.dnf5_automatic_download_updates_identifier_text
        self.apply_updates_identifier_text = self.dnf5_automatic_apply_updates_identifier_text
        self.enable_on_reboot_identifier_text = self.dnf5_automatic_enable_on_reboot_identifier_text
        self.installation_state_identifier_text = self.dnf5_automatic_installation_state_identifier_text
        self.enable_on_reboot_check_cmd = self.dnf5_automatic_enable_on_reboot_check_cmd
        self.enable_on_reboot_cmd = self.dnf5_automatic_enable_on_reboot_cmd
        self.install_check_cmd = self.dnf5_automatic_install_check_cmd
        self.current_auto_os_update_service = self.dnf5_auto_os_update_service

    def __get_current_auto_os_updates_setting_on_machine(self):
        """ Gets all the update settings related to auto OS updates via dnf """
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

            self.composite_logger.log_debug(
                "[DNF] Checking if auto updates are currently enabled...")

            # Check systemd service unit file for ExecStart flags to determine current settings
            # Get the dnf5-automatic.service configuration
            code, unit_output = self.env_layer.run_command_output(self.os_patch_configuration_settings_read_cmd, False, False)

            if code == 0:
                self.composite_logger.log_debug(
                    "[DNF] Retrieved dnf5-automatic service unit configuration...")

                # ExecStart line format example: ExecStart=/usr/bin/dnf5 automatic --timer
                for line in unit_output.split('\n'):
                    if line.strip().startswith('ExecStart=') and 'dnf5 automatic' in line:
                        self.composite_logger.log_debug("[DNF] ExecStart line: {0}".format(line))
                        break

                return is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value

        except Exception as error:
            raise Exception(
                "[DNF] Error occurred in fetching current auto OS update settings from the machine (dnf5). [Exception={0}]".format(
                    repr(error)))

    def is_auto_update_service_installed(self, install_check_cmd):
        """ Checks if the auto update service is installed on the VM """
        code, out = self.env_layer.run_command_output(install_check_cmd, False, False)
        self.composite_logger.log_debug("[DNF] Checked if auto update service is installed. [Command={0}][Code={1}][Output={2}]".format(install_check_cmd, str(code), out))
        if len(out.strip()) > 0 and code == 0:
            self.composite_logger.log_debug("[DNF] > Auto OS update service is installed on the machine")
            return True
        else:
            self.composite_logger.log_debug("[DNF] > Auto OS update service is NOT installed on the machine")
            return False

    def is_service_set_to_enable_on_reboot(self, command):
        """ Checking if auto update is set to enable on reboot on the machine. An enable_on_reboot service will be activated (if currently inactive) on machine reboot """
        code, out = self.env_layer.run_command_output(command, False, False)
        self.composite_logger.log_debug("[DNF] Checked if auto update service is set to enable on reboot. [Code={0}][Out={1}]".format(str(code), out))
        if len(out.strip()) > 0 and code == 0 and 'enabled' in out:
            self.composite_logger.log_debug("[DNF] > Auto OS update service will enable on reboot")
            return True
        self.composite_logger.log_debug("[DNF] > Auto OS update service will NOT enable on reboot")
        return False

    def enable_auto_update_on_reboot(self):
        """ Enables machine default auto update on reboot """
        # type () -> None
        command = self.enable_on_reboot_cmd
        self.composite_logger.log_verbose("[DNF] Enabling auto update on reboot. [Command={0}] ".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != 0:
            self.composite_logger.log_error("[DNF][ERROR] Error enabling auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("[DNF] Enabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))

    # endregion
