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

import json
import os
import re
from core.src.bootstrap.Constants import Constants
from core.src.package_managers.PatchModeManager import PatchModeManager


class AptPatchModeManager(PatchModeManager):
    """ Helps with translating PatchModes set by the customer to in-VM configurations """

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(AptPatchModeManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager_name=Constants.APT)
        self.update_package_list = 'APT::Periodic::Update-Package-Lists'
        self.unattended_upgrade = 'APT::Periodic::Unattended-Upgrade'
        self.os_patch_configuration_settings_file_path = '/etc/apt/apt.conf.d/20auto-upgrades'
        self.update_package_list_value = ""
        self.unattended_upgrade_value = ""

    # region auto OS updates
    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        self.composite_logger.log_verbose("[APMM] Fetching the current automatic OS patch state on the machine...")
        if os.path.exists(self.os_patch_configuration_settings_file_path):
            self.__get_current_auto_os_updates_setting_on_machine()
        if not os.path.exists(self.os_patch_configuration_settings_file_path) or int(self.unattended_upgrade_value) == 0:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.DISABLED
        elif int(self.unattended_upgrade_value) == 1:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.ENABLED
        else:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.UNKNOWN

        self.composite_logger.log_debug("[APMM] Current Auto OS Patch State detected. [State={0}]".format(str(current_auto_os_patch_state)))
        return current_auto_os_patch_state

    def __get_current_auto_os_updates_setting_on_machine(self):
        """ Gets all the update settings related to auto OS updates currently set on the machine """
        try:
            image_default_patch_configuration = self.env_layer.file_system.read_with_retry(self.os_patch_configuration_settings_file_path)
            settings = image_default_patch_configuration.strip().split('\n')
            for setting in settings:
                if self.update_package_list in str(setting):
                    self.update_package_list_value = re.search(self.update_package_list + ' *"(.*?)".', str(setting)).group(1)
                if self.unattended_upgrade in str(setting):
                    self.unattended_upgrade_value = re.search(self.unattended_upgrade + ' *"(.*?)".', str(setting)).group(1)

            if self.update_package_list_value == "":
                self.composite_logger.log_debug("[APMM] Machine did not have any value set for [Setting={0}]".format(str(self.update_package_list)))

            if self.unattended_upgrade_value == "":
                self.composite_logger.log_debug("[APMM] Machine did not have any value set for [Setting={0}]".format(str(self.unattended_upgrade)))

        except Exception as error:
            raise Exception("Error occurred in fetching default auto OS updates from the machine. [Exception={0}]".format(repr(error)))

    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enabled and logs the default settings the machine comes with """
        try:
            self.composite_logger.log_verbose("[APMM] Disabling auto OS updates if they are enabled...")
            self.backup_image_default_patch_configuration_if_not_exists()
            self.update_os_patch_configuration_sub_setting(self.update_package_list, "0")
            self.update_os_patch_configuration_sub_setting(self.unattended_upgrade, "0")
            self.composite_logger.log_verbose("[APMM] Successfully disabled auto OS updates")
        except Exception as error:
            self.composite_logger.log_error("Could not disable auto OS updates. [Error={0}]".format(repr(error)))
            raise

    def backup_image_default_patch_configuration_if_not_exists(self):
        """ Records the default system settings for auto OS updates within patch extension artifacts for future reference.
        We only log the default system settings a VM comes with, any subsequent updates will not be recorded"""
        try:
            image_default_patch_configuration_backup = {}
            image_default_patch_configuration_backup_exists = self.image_default_patch_configuration_backup_exists()

            # read existing backup since it also contains backup from other update services. We need to preserve any existing data with backup file
            if image_default_patch_configuration_backup_exists:
                try:
                    image_default_patch_configuration_backup = json.loads(self.env_layer.file_system.read_with_retry(self.image_default_patch_configuration_backup_path))
                except Exception as error:
                    self.composite_logger.log_error("[APMM] Unable to read backup for default patch state. Will attempt to re-write. [Exception={0}]".format(repr(error)))

            # verify if existing backup is valid if not, write to backup
            is_backup_valid = image_default_patch_configuration_backup_exists and self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)
            if is_backup_valid:
                self.composite_logger.log_verbose("[APMM] Since extension has a valid backup, no need to log the current settings again. [Default Auto OS update settings={0}][File path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
            else:
                self.composite_logger.log_verbose("[APMM] Since the backup is invalid or does not exist, will add a new backup with the current auto OS update settings")
                self.__get_current_auto_os_updates_setting_on_machine()

                backup_image_default_patch_configuration_json = {
                    self.update_package_list: self.update_package_list_value,
                    self.unattended_upgrade: self.unattended_upgrade_value
                }

                self.composite_logger.log_debug("[APMM] Logging default system configuration settings for auto OS updates. [Settings={0}][Log file path={1}]"
                                                .format(str(backup_image_default_patch_configuration_json), self.image_default_patch_configuration_backup_path))
                self.env_layer.file_system.write_with_retry(self.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(backup_image_default_patch_configuration_json)), mode='w+')
        except Exception as error:
            error_message = "Exception during fetching and logging default auto OS update settings on the machine. [Exception={0}]".format(repr(error))
            self.status_handler.add_error_to_status_and_log_error(error_message, raise_exception=True, error_code=Constants.PatchOperationErrorCodes.PATCH_MODE_SET_FAILURE)

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        if self.update_package_list in image_default_patch_configuration_backup and self.unattended_upgrade in image_default_patch_configuration_backup:
            self.composite_logger.log_verbose("[APMM] Extension already has a valid backup of the default system configuration settings for auto OS updates.")
            return True
        else:
            self.composite_logger.log_verbose("[APMM] Extension does not have a valid backup of the default system configuration settings for auto OS updates.")
            return False

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value="0", patch_configuration_sub_setting_pattern_to_match=""):
        """ Updates (or adds if it doesn't exist) the given patch_configuration_sub_setting with the given value in os_patch_configuration_settings_file """
        try:
            # note: adding space between the patch_configuration_sub_setting and value since, we will have to do that if we have to add a patch_configuration_sub_setting that did not exist before
            self.composite_logger.log_debug("[APMM] Updating system configuration settings for auto OS updates. [Patch Configuration Sub Setting={0}][Value={1}]".format(str(patch_configuration_sub_setting), value))
            os_patch_configuration_settings = self.env_layer.file_system.read_with_retry(self.os_patch_configuration_settings_file_path)
            patch_configuration_sub_setting_to_update = patch_configuration_sub_setting + ' "' + value + '";'
            patch_configuration_sub_setting_found_in_file = False
            updated_patch_configuration_sub_setting = ""
            settings = os_patch_configuration_settings.strip().split('\n')

            # update value of existing setting
            for i in range(len(settings)):
                if patch_configuration_sub_setting in settings[i]:
                    settings[i] = patch_configuration_sub_setting_to_update
                    patch_configuration_sub_setting_found_in_file = True
                updated_patch_configuration_sub_setting += settings[i] + "\n"

            # add setting to configuration file, since it doesn't exist
            if not patch_configuration_sub_setting_found_in_file:
                updated_patch_configuration_sub_setting += patch_configuration_sub_setting_to_update + "\n"

            self.env_layer.file_system.write_with_retry(self.os_patch_configuration_settings_file_path, '{0}'.format(updated_patch_configuration_sub_setting.lstrip()), mode='w+')
        except Exception as error:
            error_message = "Error occurred while updating system configuration settings for auto OS updates. [Patch Configuration={0}][Error={1}]".format(str(patch_configuration_sub_setting), repr(error))
            self.status_handler.add_error_to_status_and_log_error(error_message, raise_exception=True, error_code=Constants.PatchOperationErrorCodes.PATCH_MODE_SET_FAILURE)
    # endregion

