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

"""AzL3TdnfPackageManager for Azure Linux"""
import json
import os
import re

from core.src.core_logic.VersionComparator import VersionComparator
from core.src.package_managers.TdnfPackageManager import TdnfPackageManager
from core.src.bootstrap.Constants import Constants


class AzL3TdnfPackageManager(TdnfPackageManager):
    """Implementation of Azure Linux package management operations"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(AzL3TdnfPackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)

        # Support to get updates and their dependencies
        self.tdnf_check = 'sudo tdnf -q list updates <SNAPSHOTTIME>'

        # Install update
        self.install_security_updates_azgps_coordinated_cmd = 'sudo tdnf -y upgrade --skip-broken <SNAPSHOTTIME>'

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

        # Strict SDP specializations
        self.TDNF_MINIMUM_VERSION_FOR_STRICT_SDP = "3.5.8-3.azl3"  # minimum version of tdnf required to support Strict SDP in Azure Linux

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.TDNF)
        self.version_comparator = VersionComparator()

        # if an Auto Patching request comes in on an Azure Linux machine with Security and/or Critical classifications selected, we need to install all patches, since classifications aren't available in Azure Linux repository
        installation_included_classifications = [] if execution_config.included_classifications_list is None else execution_config.included_classifications_list
        if execution_config.health_store_id is not str() and execution_config.operation.lower() == Constants.INSTALLATION.lower() \
                and (env_layer.is_distro_azure_linux(str(env_layer.platform.linux_distribution()))) \
                and 'Critical' in installation_included_classifications and 'Security' in installation_included_classifications:
            self.composite_logger.log_debug("Updating classifications list to install all patches for the Auto Patching request since classification based patching is not available on Azure Linux machines")
            execution_config.included_classifications_list = [Constants.PackageClassification.CRITICAL, Constants.PackageClassification.SECURITY, Constants.PackageClassification.OTHER]

    # region Strict SDP using SnapshotTime
    @staticmethod
    def __generate_command_with_snapshotposixtime_if_specified(command_template, snapshot_posix_time=str()):
        # type: (str, str) -> str
        if snapshot_posix_time == str():
            return command_template.replace('<SNAPSHOTTIME>', str())
        else:
            return command_template.replace('<SNAPSHOTTIME>', ('--snapshottime={0}'.format(str(snapshot_posix_time))))
    # endregion

    # region Get Available Updates
    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_verbose("[AzL3TDNF] Discovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug("[AzL3TDNF] Get all updates : [Cached={0}][PackagesCount={1}]]".format(str(cached), len(self.all_updates_cached)))
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        out = self.invoke_package_manager(self.__generate_command_with_snapshotposixtime_if_specified(self.tdnf_check, self.max_patch_publish_date))
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)
        self.composite_logger.log_debug("[AzL3TDNF] Get all updates : [Cached={0}][PackagesCount={1}]]".format(str(False), len(self.all_updates_cached)))
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates. NOTE: Classification based categorization of patches is not available in Azure Linux as of now"""
        self.composite_logger.log_verbose("[AzL3TDNF] Discovering all packages as 'security' packages, since TDNF does not support package classification...")
        security_packages, security_package_versions = self.get_all_updates(cached=False)
        self.composite_logger.log_debug("[AzL3TDNF] Discovered 'security' packages. [Count={0}]".format(len(security_packages)))
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates."""
        self.composite_logger.log_verbose("[AzL3TDNF] Discovering 'other' packages...")
        return [], []

    def set_max_patch_publish_date(self, max_patch_publish_date=str()):
        """Set the max patch publish date in POSIX time for strict SDP"""
        self.composite_logger.log_debug("[AzL3TDNF] Setting max patch publish date. [MaxPatchPublishDate={0}]".format(str(max_patch_publish_date)))
        self.max_patch_publish_date = str(self.env_layer.datetime.datetime_string_to_posix_time(max_patch_publish_date, '%Y%m%dT%H%M%SZ')) if max_patch_publish_date != str() else max_patch_publish_date
        self.composite_logger.log_debug("[AzL3TDNF] Set max patch publish date. [MaxPatchPublishDatePosixTime={0}]".format(str(self.max_patch_publish_date)))
    # endregion

    # endregion

    # region Install Updates
    def install_updates_fail_safe(self, excluded_packages):
        return

    def install_security_updates_azgps_coordinated(self):
        """Install security updates in Azure Linux following strict SDP"""
        command = self.__generate_command_with_snapshotposixtime_if_specified(self.install_security_updates_azgps_coordinated_cmd, self.max_patch_publish_date)
        out, code = self.invoke_package_manager_advanced(command, raise_on_exception=False)
        return code, out

    def try_meet_azgps_coordinated_requirements(self):
        # type: () -> bool
        """ Check if the system meets the requirements for Azure Linux strict safe deployment and attempt to update TDNF if necessary """
        self.composite_logger.log_debug("[AzL3TDNF] Checking if system meets Azure Linux security updates requirements...")
        # Check if the system is Azure Linux 3.0 or beyond
        if not self.env_layer.is_distro_azure_linux_3_or_beyond():
            self.composite_logger.log_error("[AzL3TDNF] The system does not meet minimum Azure Linux requirement of 3.0 or above for strict safe deployment. Defaulting to regular upgrades.")
            self.set_max_patch_publish_date()  # fall-back
            return False
        else:
            if self.is_minimum_tdnf_version_for_strict_sdp_installed():
                self.composite_logger.log_debug("[AzL3TDNF] Minimum tdnf version for strict safe deployment is installed.")
                return True
            else:
                if not self.try_tdnf_update_to_meet_strict_sdp_requirements():
                    error_msg = "Failed to meet minimum TDNF version requirement for strict safe deployment. Defaulting to regular upgrades."
                    self.composite_logger.log_error(error_msg + "[Error={0}]".format(repr(error_msg)))
                    self.status_handler.add_error_to_status(error_msg)
                    self.set_max_patch_publish_date()  # fall-back
                    return False
                return True

    def is_minimum_tdnf_version_for_strict_sdp_installed(self):
        # type: () -> bool
        """Check if  at least the minimum required version of TDNF is installed"""
        self.composite_logger.log_debug("[AzL3TDNF] Checking if minimum TDNF version required for strict safe deployment is installed...")
        tdnf_version = self.get_tdnf_version()
        minimum_tdnf_version_for_strict_sdp = self.TDNF_MINIMUM_VERSION_FOR_STRICT_SDP
        distro_from_minimum_tdnf_version_for_strict_sdp = re.match(r".*-\d+\.([a-zA-Z0-9]+)$", minimum_tdnf_version_for_strict_sdp).group(1)
        if tdnf_version is None:
            self.composite_logger.log_error("[AzL3TDNF] Failed to get TDNF version. Cannot proceed with strict safe deployment. Defaulting to regular upgrades.")
            return False
        elif re.match(r".*-\d+\.([a-zA-Z0-9]+)$", tdnf_version).group(1) != distro_from_minimum_tdnf_version_for_strict_sdp:
            self.composite_logger.log_warning("[AzL3TDNF] TDNF version installed is not from the same Azure Linux distribution as the minimum required version for strict SDP. [InstalledVersion={0}][MinimumRequiredVersion={1}]".format(tdnf_version, self.TDNF_MINIMUM_VERSION_FOR_STRICT_SDP))
            return False
        elif not self.version_comparator.compare_versions(tdnf_version, minimum_tdnf_version_for_strict_sdp) >= 0:
            self.composite_logger.log_warning("[AzL3TDNF] TDNF version installed is less than the minimum required version for strict SDP. [InstalledVersion={0}][MinimumRequiredVersion={1}]".format(tdnf_version, self.TDNF_MINIMUM_VERSION_FOR_STRICT_SDP))
            return False
        return True

    def get_tdnf_version(self):
        # type: () -> any
        """Get the version of TDNF installed on the system"""
        self.composite_logger.log_debug("[AzL3TDNF] Getting tdnf version...")
        cmd = "rpm -q tdnf | sed -E 's/^tdnf-([0-9]+\\.[0-9]+\\.[0-9]+-[0-9]+\\.[a-zA-Z0-9]+).*/\\1/'"
        code, output = self.env_layer.run_command_output(cmd, False, False)
        if code == 0:
            # Sample output: 3.5.8-3-azl3
            version = output.split()[0] if output else None
            self.composite_logger.log_debug("[AzL3TDNF] TDNF version detected. [Version={0}]".format(version))
            return version
        else:
            self.composite_logger.log_error("[AzL3TDNF] Failed to get TDNF version. [Command={0}][Code={1}][Output={2}]".format(cmd, code, output))
            return None

    def try_tdnf_update_to_meet_strict_sdp_requirements(self):
        # type: () -> bool
        """Attempt to update TDNF to meet the minimum version required for strict SDP"""
        self.composite_logger.log_debug("[AzL3TDNF] Attempting to update TDNF to meet strict safe deployment requirements...")
        cmd = "sudo tdnf -y install tdnf-" + self.TDNF_MINIMUM_VERSION_FOR_STRICT_SDP
        code, output = self.env_layer.run_command_output(cmd, no_output=True, chk_err=False)
        if code == 0:
            self.composite_logger.log_debug("[AzL3TDNF] Successfully updated TDNF for Strict SDP. [Command={0}][Code={1}]".format(cmd, code))
            return True
        else:
            self.composite_logger.log_error("[AzL3TDNF] Failed to update TDNF for Strict SDP. [Command={0}][Code={1}][Output={2}]".format(cmd, code, output))
            return False
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
        self.composite_logger.log("[AzL3TDNF] Fetching the current automatic OS patch state on the machine...")

        current_auto_os_patch_state_for_dnf_automatic = self.__get_current_auto_os_patch_state_for_dnf_automatic()

        self.composite_logger.log("[AzL3TDNF] OS patch state per auto OS update service: [dnf-automatic={0}]".format(str(current_auto_os_patch_state_for_dnf_automatic)))

        if current_auto_os_patch_state_for_dnf_automatic == Constants.AutomaticOSPatchStates.ENABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.ENABLED
        elif current_auto_os_patch_state_for_dnf_automatic == Constants.AutomaticOSPatchStates.DISABLED:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.DISABLED
        else:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.UNKNOWN

        self.composite_logger.log_debug("[AzL3TDNF] Overall Auto OS Patch State based on all auto OS update service states [OverallAutoOSPatchState={0}]".format(str(current_auto_os_patch_state)))
        return current_auto_os_patch_state

    def __get_current_auto_os_patch_state_for_dnf_automatic(self):
        """ Gets current auto OS update patch state for dnf-automatic """
        self.composite_logger.log_debug("[AzL3TDNF] Fetching current automatic OS patch state in dnf-automatic service. This includes checks on whether the service is installed, current auto patch enable state and whether it is set to enable on reboot")
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

            self.composite_logger.log_debug("[AzL3TDNF] Checking if auto updates are currently enabled...")
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
                self.composite_logger.log_debug("[AzL3TDNF] Machine did not have any value set for [Setting={0}]".format(str(self.download_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("[AzL3TDNF] Current value set for [{0}={1}]".format(str(self.download_updates_identifier_text), str(download_updates_value)))

            if apply_updates_value == "":
                self.composite_logger.log_debug("[AzL3TDNF] Machine did not have any value set for [Setting={0}]".format(str(self.apply_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("[AzL3TDNF] Current value set for [{0}={1}]".format(str(self.apply_updates_identifier_text), str(apply_updates_value)))

            return is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value

        except Exception as error:
            raise Exception("[AzL3TDNF] Error occurred in fetching current auto OS update settings from the machine. [Exception={0}]".format(repr(error)))

    def is_auto_update_service_installed(self, install_check_cmd):
        """ Checks if the auto update service is enable_on_reboot on the VM """
        code, out = self.env_layer.run_command_output(install_check_cmd, False, False)
        self.composite_logger.log_debug("[AzL3TDNF] Checked if auto update service is installed. [Command={0}][Code={1}][Output={2}]".format(install_check_cmd, str(code), out))
        if len(out.strip()) > 0 and code == 0:
            self.composite_logger.log_debug("[AzL3TDNF] > Auto OS update service is installed on the machine")
            return True
        else:
            self.composite_logger.log_debug("[AzL3TDNF] > Auto OS update service is NOT installed on the machine")
            return False

    def is_service_set_to_enable_on_reboot(self, command):
        """ Checking if auto update is enable_on_reboot on the machine. An enable_on_reboot service will be activated (if currently inactive) on machine reboot """
        code, out = self.env_layer.run_command_output(command, False, False)
        self.composite_logger.log_debug("[AzL3TDNF] Checked if auto update service is set to enable on reboot. [Code={0}][Out={1}]".format(str(code), out))
        if len(out.strip()) > 0 and code == 0 and 'enabled' in out:
            self.composite_logger.log_debug("[AzL3TDNF] > Auto OS update service will enable on reboot")
            return True
        self.composite_logger.log_debug("[AzL3TDNF] > Auto OS update service will NOT enable on reboot")
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
            self.composite_logger.log_verbose("[AzL3TDNF] Disabling auto OS updates in all identified services...")
            self.disable_auto_os_update_for_dnf_automatic()
            self.composite_logger.log_debug("[AzL3TDNF] Successfully disabled auto OS updates")

        except Exception as error:
            self.composite_logger.log_error("[AzL3TDNF] Could not disable auto OS updates. [Error={0}]".format(repr(error)))
            raise

    def disable_auto_os_update_for_dnf_automatic(self):
        """ Disables auto OS updates, using dnf-automatic service, and logs the default settings the machine comes with """
        self.composite_logger.log_verbose("[AzL3TDNF] Disabling auto OS updates using dnf-automatic")
        self.__init_auto_update_for_dnf_automatic()

        self.backup_image_default_patch_configuration_if_not_exists()

        if not self.is_auto_update_service_installed(self.dnf_automatic_install_check_cmd):
            self.composite_logger.log_debug("[AzL3TDNF] Cannot disable as dnf-automatic is not installed on the machine")
            return

        self.composite_logger.log_verbose("[AzL3TDNF] Preemptively disabling auto OS updates using dnf-automatic")
        self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "no", self.dnf_automatic_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "no", self.dnf_automatic_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.dnf_automatic_disable_on_reboot_cmd)

        self.composite_logger.log_debug("[AzL3TDNF] Successfully disabled auto OS updates using dnf-automatic")

    def disable_auto_update_on_reboot(self, command):
        self.composite_logger.log_verbose("[AzL3TDNF] Disabling auto update on reboot. [Command={0}] ".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != 0:
            self.composite_logger.log_error("[AzL3TDNF][ERROR] Error disabling auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("[AzL3TDNF] Disabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))

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
            self.composite_logger.log_debug("[AzL3TDNF] Ensuring there is a backup of the default patch state for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
            image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()

            # verify if existing backup is valid if not, write to backup
            is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)
            if is_backup_valid:
                self.composite_logger.log_debug("[AzL3TDNF] Since extension has a valid backup, no need to log the current settings again. [Default Auto OS update settings={0}] [File path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
            else:
                self.composite_logger.log_debug("[AzL3TDNF] Since the backup is invalid, will add a new backup with the current auto OS update settings")
                self.composite_logger.log_debug("[AzL3TDNF] Fetching current auto OS update settings for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
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

                self.composite_logger.log_debug("[AzL3TDNF] Logging default system configuration settings for auto OS updates. [Settings={0}] [Log file path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
                self.env_layer.file_system.write_with_retry(self.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(image_default_patch_configuration_backup)), mode='w+')
        except Exception as error:
            error_message = "[AzL3TDNF] Exception during fetching and logging default auto update settings on the machine. [Exception={0}]".format(repr(error))
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
            self.composite_logger.log_debug("[AzL3TDNF] Extension has a valid backup for default dnf-automatic configuration settings")
            return True
        else:
            self.composite_logger.log_debug("[AzL3TDNF] Extension does not have a valid backup for default dnf-automatic configuration settings")
            return False

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value="no", config_pattern_match_text=""):
        """ Updates (or adds if it doesn't exist) the given patch_configuration_sub_setting with the given value in os_patch_configuration_settings_file """
        try:
            # note: adding space between the patch_configuration_sub_setting and value since, we will have to do that if we have to add a patch_configuration_sub_setting that did not exist before
            self.composite_logger.log_debug("[AzL3TDNF] Updating system configuration settings for auto OS updates. [Patch Configuration Sub Setting={0}] [Value={1}]".format(str(patch_configuration_sub_setting), value))
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
            error_msg = "[AzL3TDNF] Error occurred while updating system configuration settings for auto OS updates. [Patch Configuration={0}] [Error={1}]".format(str(patch_configuration_sub_setting), repr(error))
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def revert_auto_os_update_to_system_default(self):
        """ Reverts the auto OS update patch state on the machine to its system default value, if one exists in our backup file """
        # type () -> None
        self.composite_logger.log("[AzL3TDNF] Reverting the current automatic OS patch state on the machine to its system default value before patchmode was set to 'AutomaticByPlatform'")
        self.revert_auto_os_update_to_system_default_for_dnf_automatic()
        self.composite_logger.log_debug("[AzL3TDNF] Successfully reverted auto OS updates to system default config")

    def revert_auto_os_update_to_system_default_for_dnf_automatic(self):
        """ Reverts the auto OS update patch state on the machine to its system default value for given service, if applicable """
        # type () -> None
        self.__init_auto_update_for_dnf_automatic()
        self.composite_logger.log("[AzL3TDNF] Reverting the current automatic OS patch state on the machine to its system default value for [Service={0}]".format(str(self.current_auto_os_update_service)))
        is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

        if not is_service_installed:
            self.composite_logger.log_debug("[AzL3TDNF] Machine default auto OS update service is not installed on the VM and hence no config to revert. [Service={0}]".format(str(self.current_auto_os_update_service)))
            return

        self.composite_logger.log_debug("[AzL3TDNF] Logging current configuration settings for auto OS updates [Service={0}][Is_Service_Installed={1}][Machine_default_update_enable_on_reboot={2}][{3}={4}]][{5}={6}]"
                                        .format(str(self.current_auto_os_update_service), str(is_service_installed), str(enable_on_reboot_value), str(self.download_updates_identifier_text), str(download_updates_value), str(self.apply_updates_identifier_text), str(apply_updates_value)))

        image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()
        self.composite_logger.log_debug("[AzL3TDNF] Logging system default configuration settings for auto OS updates. [Settings={0}]".format(str(image_default_patch_configuration_backup)))
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
            self.composite_logger.log_debug("[AzL3TDNF] Since the backup is invalid or does not exist for current service, we won't be able to revert auto OS patch settings to their system default value. [Service={0}]".format(str(self.current_auto_os_update_service)))

    def enable_auto_update_on_reboot(self):
        """Enables machine default auto update on reboot"""
        # type () -> None
        command = self.enable_on_reboot_cmd
        self.composite_logger.log_verbose("[AzL3TDNF] Enabling auto update on reboot. [Command={0}] ".format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != 0:
            self.composite_logger.log_error("[AzL3TDNF][ERROR] Error enabling auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))
            error_msg = 'Unexpected return code (' + str(code) + ') on command: ' + command
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        else:
            self.composite_logger.log_debug("[AzL3TDNF] Enabled auto update on reboot. [Command={0}][Code={1}][Output={2}]".format(command, str(code), out))

    def __get_image_default_patch_configuration_backup(self):
        """ Get image_default_patch_configuration_backup file"""
        image_default_patch_configuration_backup = {}

        # read existing backup since it also contains backup from other update services. We need to preserve any existing data within the backup file
        if self.image_default_patch_configuration_backup_exists():
            try:
                image_default_patch_configuration_backup = json.loads(self.env_layer.file_system.read_with_retry(self.image_default_patch_configuration_backup_path))
            except Exception as error:
                self.composite_logger.log_error("[AzL3TDNF] Unable to read backup for default patch state. Will attempt to re-write. [Exception={0}]".format(repr(error)))
        return image_default_patch_configuration_backup
    # endregion

    # region Reboot Management
    def is_reboot_pending(self):
        """ Checks if there is a pending reboot on the machine. """
        try:
            pending_file_exists = os.path.isfile(self.REBOOT_PENDING_FILE_PATH)
            pending_processes_exist = self.do_processes_require_restart()
            self.composite_logger.log_debug("[AzL3TDNF] > Reboot required debug flags (tdnf): " + str(pending_file_exists) + ", " + str(pending_processes_exist) + ".")
            return pending_file_exists or pending_processes_exist
        except Exception as error:
            self.composite_logger.log_error('[AzL3TDNF] Error while checking for reboot pending (tdnf): ' + repr(error))
            return True  # defaults for safety

    def do_processes_require_restart(self):
        """Signals whether processes require a restart due to updates"""
        self.composite_logger.log_verbose("[AzL3TDNF] Checking if process requires reboot")
        # Checking using dnf-utils
        code, out = self.env_layer.run_command_output(self.dnf_utils_prerequisite, False, False)  # idempotent, doesn't install if already present
        self.composite_logger.log_verbose("[AzL3TDNF] Idempotent dnf-utils existence check. [Code={0}][Out={1}]".format(str(code), out))

        # Checking for restart for distros with -r flag
        code, out = self.env_layer.run_command_output(self.needs_restarting_with_flag, False, False)
        self.composite_logger.log_verbose("[AzL3TDNF] > Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))
        if out.find("Reboot is required") < 0:
            self.composite_logger.log_debug("[AzL3TDNF] > Reboot not detected to be required (L1).")
        else:
            self.composite_logger.log_debug("[AzL3TDNF] > Reboot is detected to be required (L1).")
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

