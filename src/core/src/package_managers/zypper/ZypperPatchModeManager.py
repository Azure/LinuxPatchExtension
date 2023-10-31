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


class ZypperPatchModeManager(PatchModeManager):
    """ Helps with translating PatchModes set by the customer to in-VM configurations """

    class ZypperAutoOSUpdateServices(Constants.EnumBackport):
        YAST2_ONLINE_UPDATE_CONFIGURATION = "yast2-online-update-configuration"

    class YastOnlineUpdateConfigurationConstants(Constants.EnumBackport):
        OS_PATCH_CONFIGURATION_SETTINGS_FILE_PATH = '/etc/sysconfig/automatic_online_update'
        APPLY_UPDATES_IDENTIFIER_TEXT = 'AOU_ENABLE_CRONJOB'
        AUTO_UPDATE_CONFIG_PATTERN_MATCH_TEXT = '="(true|false)"'
        INSTALLATION_STATE_IDENTIFIER_TEXT = "installation_state"

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager_name):
        super(ZypperPatchModeManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager_name)
        # auto OS updates
        self.current_auto_os_update_service = None
        self.os_patch_configuration_settings_file_path = ''
        self.auto_update_config_pattern_match_text = ""
        self.apply_updates_identifier_text = ""
        self.installation_state_identifier_text = ""

    # region auto OS updates
    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        self.composite_logger.log("Fetching the current automatic OS patch state on the machine...")

        current_auto_os_patch_state_for_yast2_online_update_configuration = self.__get_current_auto_os_patch_state_for_yast2_online_update_configuration()
        self.composite_logger.log("OS patch state per auto OS update service: [yast2-online-update-configuration={0}]".format(str(current_auto_os_patch_state_for_yast2_online_update_configuration)))

        current_auto_os_patch_state = current_auto_os_patch_state_for_yast2_online_update_configuration
        self.composite_logger.log_debug("Overall Auto OS Patch State based on all auto OS update service states [OverallAutoOSPatchState={0}]".format(str(current_auto_os_patch_state)))
        return current_auto_os_patch_state

    def __get_current_auto_os_patch_state_for_yast2_online_update_configuration(self):
        """ Gets current auto OS update patch state for yast2-online-update-configuration """
        self.composite_logger.log_debug("Fetching current automatic OS patch state in yast2-online-update-configuration.")
        self.__init_auto_update_for_yast_online_update_configuration()
        is_service_installed, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

        apply_updates = self.__get_extension_standard_value_for_apply_updates(apply_updates_value)

        # OS patch state is considered to be disabled: a) if it was successfully disabled or b) if the service is not installed
        if not is_service_installed or apply_updates == Constants.AutomaticOSPatchStates.DISABLED:
            return Constants.AutomaticOSPatchStates.DISABLED

        return apply_updates

    @staticmethod
    def __get_extension_standard_value_for_apply_updates(apply_updates_value):
        if apply_updates_value.lower() == 'true':
            return Constants.AutomaticOSPatchStates.ENABLED
        elif apply_updates_value.lower() == 'false':
            return Constants.AutomaticOSPatchStates.DISABLED
        else:
            return Constants.AutomaticOSPatchStates.UNKNOWN

    def __init_auto_update_for_yast_online_update_configuration(self):
        """ Initializes all generic auto OS update variables with the config values for yum cron service """
        self.os_patch_configuration_settings_file_path = self.YastOnlineUpdateConfigurationConstants.OS_PATCH_CONFIGURATION_SETTINGS_FILE_PATH
        self.apply_updates_identifier_text = self.YastOnlineUpdateConfigurationConstants.APPLY_UPDATES_IDENTIFIER_TEXT
        self.auto_update_config_pattern_match_text = self.YastOnlineUpdateConfigurationConstants.AUTO_UPDATE_CONFIG_PATTERN_MATCH_TEXT
        self.installation_state_identifier_text = self.YastOnlineUpdateConfigurationConstants.INSTALLATION_STATE_IDENTIFIER_TEXT
        self.current_auto_os_update_service = self.ZypperAutoOSUpdateServices.YAST2_ONLINE_UPDATE_CONFIGURATION

    def __get_current_auto_os_updates_setting_on_machine(self):
        """ Gets all the update settings related to auto OS updates currently set on the machine """
        try:
            apply_updates_value = ""
            is_service_installed = False

            # get install state
            if not os.path.exists(self.os_patch_configuration_settings_file_path):
                return is_service_installed, apply_updates_value

            is_service_installed = True
            self.composite_logger.log_debug("Checking if auto updates are currently enabled...")
            image_default_patch_configuration = self.env_layer.file_system.read_with_retry(self.os_patch_configuration_settings_file_path, raise_if_not_found=False)
            if image_default_patch_configuration is not None:
                settings = image_default_patch_configuration.strip().split('\n')
                for setting in settings:
                    match = re.search(self.apply_updates_identifier_text + self.auto_update_config_pattern_match_text, str(setting))
                    if match is not None:
                        apply_updates_value = match.group(1)

            if apply_updates_value == "":
                self.composite_logger.log_debug("Machine did not have any value set for [Setting={0}]".format(str(self.apply_updates_identifier_text)))
            else:
                self.composite_logger.log_verbose("Current value set for [{0}={1}]".format(str(self.apply_updates_identifier_text), str(apply_updates_value)))

            return is_service_installed, apply_updates_value

        except Exception as error:
            raise Exception("Error occurred in fetching current auto OS update settings from the machine. [Exception={0}]".format(repr(error)))

    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enable_on_reboot and logs the default settings the machine comes with """
        try:
            self.composite_logger.log("Disabling auto OS updates in all identified services...")
            self.disable_auto_os_update_for_yast_online_update_configuration()
            self.composite_logger.log_debug("Completed attempt to disable auto OS updates")

        except Exception as error:
            self.composite_logger.log_error("Could not disable auto OS updates. [Error={0}]".format(repr(error)))
            raise

    def disable_auto_os_update_for_yast_online_update_configuration(self):
        """ Disables auto OS updates, using yast online, and logs the default settings the machine comes with """
        self.composite_logger.log("Disabling auto OS updates using yast online update configuration")
        self.__init_auto_update_for_yast_online_update_configuration()

        self.backup_image_default_patch_configuration_if_not_exists()
        # check if file exists, if not do nothing
        if not os.path.exists(self.os_patch_configuration_settings_file_path):
            self.composite_logger.log_debug("Cannot disable auto updates using yast2-online-update-configuration because the configuration file does not exist, indicating the service is not installed")
            return

        self.composite_logger.log_debug("Preemptively disabling auto OS updates using yum-cron")
        self.update_os_patch_configuration_sub_setting(self.apply_updates_identifier_text, "false", self.auto_update_config_pattern_match_text)

        self.composite_logger.log("Successfully disabled auto OS updates using yast2-online-update-configuration")

    def backup_image_default_patch_configuration_if_not_exists(self):
        """ Records the default system settings for auto OS updates within patch extension artifacts for future reference.
        We only log the default system settings a VM comes with, any subsequent updates will not be recorded"""
        """ JSON format for backup file:
                            {
                                "yast2-online-update-configuration": {
                                    "apply_updates": "true/false/empty string"
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
                is_service_installed, apply_updates_value = self.__get_current_auto_os_updates_setting_on_machine()

                backup_image_default_patch_configuration_json_to_add = {
                    self.current_auto_os_update_service: {
                        self.apply_updates_identifier_text: apply_updates_value,
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

        # NOTE: Adding a separate function to check backup for multiple auto OS update services, if more are added in future.
        return self.is_backup_valid_for_yast_online_update_configuration(image_default_patch_configuration_backup)

    def is_backup_valid_for_yast_online_update_configuration(self, image_default_patch_configuration_backup):
        if self.ZypperAutoOSUpdateServices.YAST2_ONLINE_UPDATE_CONFIGURATION in image_default_patch_configuration_backup \
                and self.apply_updates_identifier_text in image_default_patch_configuration_backup[self.ZypperAutoOSUpdateServices.YAST2_ONLINE_UPDATE_CONFIGURATION]:
            self.composite_logger.log_debug("Extension has a valid backup for default yum-cron configuration settings")
            return True
        else:
            self.composite_logger.log_debug("Extension does not have a valid backup for default yum-cron configuration settings")
            return False

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value="false", config_pattern_match_text=""):
        """ Updates (or adds if it doesn't exist) the given patch_configuration_sub_setting with the given value in os_patch_configuration_settings_file """
        try:
            self.composite_logger.log_debug("Updating system configuration settings for auto OS updates. [Patch Configuration Sub Setting={0}][Value={1}]".format(str(patch_configuration_sub_setting), value))
            os_patch_configuration_settings = self.env_layer.file_system.read_with_retry(self.os_patch_configuration_settings_file_path)
            patch_configuration_sub_setting_to_update = patch_configuration_sub_setting + '="' + value + '"'
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
    # endregion

