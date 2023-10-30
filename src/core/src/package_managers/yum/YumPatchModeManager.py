# Copyright 2023 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.7+

import os
import re
import json
from core.src.bootstrap.Constants import Constants
from core.src.package_managers.PatchModeManager import PatchModeManager


class YumPatchModeManager(PatchModeManager):
    """ Helps with translating PatchModes set by the customer to in-VM configurations """

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(YumPatchModeManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager_name=Constants.APT)
        # auto OS updates
        self.current_auto_os_update_service = None
        self.os_patch_configuration_settings_file_path = ''
        self.auto_update_service_enabled = False
        self.auto_update_config_pattern_match_text = ""
        self.download_updates_identifier_text = ""
        self.apply_updates_identifier_text = ""
        self.enable_on_reboot_identifier_text = ""
        self.enable_on_reboot_check_cmd = ''
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

    # region auto OS updates
    def __init_constants_for_yum_cron(self):
        self.yum_cron_configuration_settings_file_path = '/etc/yum/yum-cron.conf'
        self.yum_cron_install_check_cmd = 'systemctl list-unit-files --type=service | grep yum-cron.service'  # list-unit-files returns installed services, ref: https://www.freedesktop.org/software/systemd/man/systemctl.html#Unit%20File%20Commands
        self.yum_cron_enable_on_reboot_check_cmd = 'systemctl is-enabled yum-cron'
        self.yum_cron_disable_on_reboot_cmd = 'systemctl disable yum-cron'
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

        self.composite_logger.log("OS patch state per auto OS update service: [yum-cron={0}][dnf-automatic={1}][packagekit={2}]"
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
        self.install_check_cmd = self.packagekit_install_check_cmd
        self.current_auto_os_update_service = Constants.YumAutoOSUpdateServices.PACKAGEKIT

    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enable_on_reboot and logs the default settings the machine comes with """
        try:
            self.composite_logger.log("Disabling auto OS updates in all identified services...")
            self.disable_auto_os_update_for_yum_cron()
            self.disable_auto_os_update_for_dnf_automatic()
            self.disable_auto_os_update_for_packagekit()
            self.composite_logger.log_debug("Successfully disabled auto OS updates")

        except Exception as error:
            self.composite_logger.log_error("Could not disable auto OS updates. [Error={0}]".format(repr(error)))
            raise

    def disable_auto_os_update_for_yum_cron(self):
        """ Disables auto OS updates, using yum cron service, and logs the default settings the machine comes with """
        self.composite_logger.log("Disabling auto OS updates using yum-cron")
        self.__init_auto_update_for_yum_cron()

        self.backup_image_default_patch_configuration_if_not_exists()
        if not self.is_auto_update_service_installed(self.yum_cron_install_check_cmd):
            self.composite_logger.log_debug("Cannot disable as yum-cron is not installed on the machine")
            return

        self.composite_logger.log_debug("Preemptively disabling auto OS updates using yum-cron")
        self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "no", self.yum_cron_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "no", self.yum_cron_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.yum_cron_disable_on_reboot_cmd)

        self.composite_logger.log("Successfully disabled auto OS updates using yum-cron")

    def disable_auto_os_update_for_dnf_automatic(self):
        """ Disables auto OS updates, using dnf-automatic service, and logs the default settings the machine comes with """
        self.composite_logger.log("Disabling auto OS updates using dnf-automatic")
        self.__init_auto_update_for_dnf_automatic()

        self.backup_image_default_patch_configuration_if_not_exists()

        if not self.is_auto_update_service_installed(self.dnf_automatic_install_check_cmd):
            self.composite_logger.log_debug("Cannot disable as dnf-automatic is not installed on the machine")
            return

        self.composite_logger.log_debug("Preemptively disabling auto OS updates using dnf-automatic")
        self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "no", self.dnf_automatic_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "no", self.dnf_automatic_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.dnf_automatic_disable_on_reboot_cmd)

        self.composite_logger.log("Successfully disabled auto OS updates using dnf-automatic")

    def disable_auto_os_update_for_packagekit(self):
        """ Disables auto OS updates, using packagekit service, and logs the default settings the machine comes with """
        self.composite_logger.log("Disabling auto OS updates using packagekit")
        self.__init_auto_update_for_packagekit()

        self.backup_image_default_patch_configuration_if_not_exists()

        if not self.is_auto_update_service_installed(self.packagekit_install_check_cmd):
            self.composite_logger.log_debug("Cannot disable as packagekit is not installed on the machine")
            return

        self.composite_logger.log_debug("Preemptively disabling auto OS updates using packagekit")
        #todo: uncomment after finding the correct value
        # self.update_os_patch_configuration_sub_setting(self.download_updates_identifier_text, "false", self.packagekit_config_pattern_match_text)
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "false", self.packagekit_config_pattern_match_text)
        self.disable_auto_update_on_reboot(self.packagekit_disable_on_reboot_cmd)

        self.composite_logger.log("Successfully disabled auto OS updates using packagekit")

    def is_service_set_to_enable_on_reboot(self, command):
        """ Checking if auto update is enable_on_reboot on the machine. An enable_on_reboot service will be activated (if currently inactive) on machine reboot """
        self.composite_logger.log_debug("Checking if auto update service is set to enable on reboot...")
        code, out = self.env_layer.run_command_output(command, False, False)
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))
        if len(out.strip()) > 0 and code == 0 and 'enabled' in out:
            self.composite_logger.log_debug("Auto OS update service will enable on reboot")
            return True
        self.composite_logger.log_debug("Auto OS update service will NOT enable on reboot")
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
                            "install_state": true/false
                        },
                        "dnf-automatic": {
                            "apply_updates": "yes/no/empty string",
                            "download_updates": "yes/no/empty string",
                            "enable_on_reboot": true/false,
                            "install_state": true/false
                        },
                        "packagekit": {
                            "WritePreparedUpdates": "true/false/empty string",
                            "GetPreparedUpdates": "true/false/empty string", //NOTE: This property name is pending validation as noted in another comment where the name is initialized
                            "enable_on_reboot": true/false,
                            "install_state": true/false
                        }
                    } """
        try:
            self.composite_logger.log_debug("Ensuring there is a backup of the default patch state for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
            image_default_patch_configuration_backup = {}

            # read existing backup since it also contains backup from other update services. We need to preserve any existing data within the backup file
            if self.image_default_patch_configuration_backup_exists():
                try:
                    image_default_patch_configuration_backup = json.loads(self.env_layer.file_system.read_with_retry(self.image_default_patch_configuration_backup_path))
                except Exception as error:
                    self.composite_logger.log_error("Unable to read backup for default patch state. Will attempt to re-write. [Exception={0}]".format(repr(error)))

            # verify if existing backup is valid if not, write to backup
            is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)
            if is_backup_valid:
                self.composite_logger.log_debug("Since extension has a valid backup, no need to log the current settings again. [Default Auto OS update settings={0}][File path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
            else:
                self.composite_logger.log_debug("Since the backup is invalid, will add a new backup with the current auto OS update settings")
                self.composite_logger.log_debug("Fetching current auto OS update settings for [AutoOSUpdateService={0}]".format(str(self.current_auto_os_update_service)))
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

                self.composite_logger.log_debug("Logging default system configuration settings for auto OS updates. [Settings={0}][Log file path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
                self.env_layer.file_system.write_with_retry(self.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(image_default_patch_configuration_backup)), mode='w+')
        except Exception as error:
            error_message = "Exception during fetching and logging default auto update settings on the machine. [Exception={0}]".format(repr(error))
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
            self.composite_logger.log_debug("Extension has a valid backup for default yum-cron configuration settings")
            return True
        else:
            self.composite_logger.log_debug("Extension does not have a valid backup for default yum-cron configuration settings")
            return False

    def is_backup_valid_for_dnf_automatic(self, image_default_patch_configuration_backup):
        if Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC in image_default_patch_configuration_backup \
                and self.dnf_automatic_download_updates_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC] \
                and self.dnf_automatic_apply_updates_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC] \
                and self.dnf_automatic_enable_on_reboot_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC] \
                and self.dnf_automatic_installation_state_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC]:
            self.composite_logger.log_debug("Extension has a valid backup for default dnf-automatic configuration settings")
            return True
        else:
            self.composite_logger.log_debug("Extension does not have a valid backup for default dnf-automatic configuration settings")
            return False

    def is_backup_valid_for_packagekit(self, image_default_patch_configuration_backup):
        if Constants.YumAutoOSUpdateServices.PACKAGEKIT in image_default_patch_configuration_backup \
                and self.packagekit_download_updates_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT] \
                and self.packagekit_apply_updates_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT] \
                and self.packagekit_enable_on_reboot_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT] \
                and self.packagekit_installation_state_identifier_text in image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT]:
            self.composite_logger.log_debug("Extension has a valid backup for default packagekit configuration settings")
            return True
        else:
            self.composite_logger.log_debug("Extension does not have a valid backup for default packagekit configuration settings")
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

            self.composite_logger.log_debug("Checking if auto updates are currently enabled...")
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
                self.composite_logger.log_debug("Machine did not have any value set for [Setting={0}]".format(str(self.download_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("Current value set for [{0}={1}]".format(str(self.download_updates_identifier_text), str(download_updates_value)))

            if apply_updates_value == "":
                self.composite_logger.log_debug("Machine did not have any value set for [Setting={0}]".format(str(self.apply_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("Current value set for [{0}={1}]".format(str(self.apply_updates_identifier_text), str(apply_updates_value)))

            return is_service_installed, enable_on_reboot_value, download_updates_value, apply_updates_value

        except Exception as error:
            raise Exception("Error occurred in fetching current auto OS update settings from the machine. [Exception={0}]".format(repr(error)))

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value="no", config_pattern_match_text=""):
        """ Updates (or adds if it doesn't exist) the given patch_configuration_sub_setting with the given value in os_patch_configuration_settings_file """
        try:
            # note: adding space between the patch_configuration_sub_setting and value since, we will have to do that if we have to add a patch_configuration_sub_setting that did not exist before
            self.composite_logger.log_debug("Updating system configuration settings for auto OS updates. [Patch Configuration Sub Setting={0}][Value={1}]".format(str(patch_configuration_sub_setting), value))
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
            error_msg = "Error occurred while updating system configuration settings for auto OS updates. [Patch Configuration={0}][Error={1}]".format(str(patch_configuration_sub_setting), repr(error))
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
            self.composite_logger.log_debug("Auto OS update service is installed on the machine")
            return True
        else:
            self.composite_logger.log_debug("Auto OS update service is NOT installed on the machine")
            return False
    # endregion

