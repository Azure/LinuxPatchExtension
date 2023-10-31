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
from abc import ABCMeta, abstractmethod
from core.src.bootstrap.Constants import Constants
import time


class PatchModeManager(object):
    """Base class of package manager"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager_name):
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.status_handler = status_handler
        self.package_manager_name = package_manager_name

        # auto OS updates
        self.image_default_patch_configuration_backup_path = os.path.join(self.execution_config.config_folder, Constants.IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH)

    __metaclass__ = ABCMeta  # For Python 3.0+, it changes to class Abstract(metaclass=ABCMeta)

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
        We only log the default system settings a VM comes with, any subsequent updates will not be recorded """
        pass

    def image_default_patch_configuration_backup_exists(self):
        """ Checks whether default auto OS update settings have been recorded earlier within patch extension artifacts """
        self.composite_logger.log_verbose("[PMM] Checking if extension contains a backup for default auto OS update configuration settings...")

        # backup does not exist
        if not os.path.exists(self.image_default_patch_configuration_backup_path) or not os.path.isfile(self.image_default_patch_configuration_backup_path):
            self.composite_logger.log_verbose("[PMM] Default system configuration settings for auto OS updates aren't recorded in the extension.")
            return False

        return True

    @abstractmethod
    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        pass

    @abstractmethod
    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value, patch_configuration_sub_setting_pattern_to_match):
        pass
    # endregion

