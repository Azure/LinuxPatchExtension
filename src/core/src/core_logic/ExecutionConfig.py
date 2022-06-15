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

import base64
import datetime
import json
import os
import uuid
from core.src.bootstrap.Constants import Constants


class ExecutionConfig(object):
    def __init__(self, env_layer, composite_logger, execution_parameters):
        self.env_layer = env_layer
        self.composite_logger = composite_logger
        self.execution_parameters = eval(execution_parameters)
        self.composite_logger.log_debug(" - Input parameters... [InputParameters={0}]".format(str(execution_parameters)))
        # Environment details
        self.global_exclusion_list = str(Constants.GLOBAL_EXCLUSION_LIST) if Constants.GLOBAL_EXCLUSION_LIST else None

        # Decoded input parameters
        self.composite_logger.log_debug(" - Decoding input parameters...")
        self.sequence_number = self.__get_value_from_argv(self.execution_parameters, Constants.ARG_SEQUENCE_NUMBER)
        self.environment_settings = self.__get_decoded_json_from_argv(self.execution_parameters, Constants.ARG_ENVIRONMENT_SETTINGS)
        self.config_settings = self.__get_decoded_json_from_argv(self.execution_parameters, Constants.ARG_CONFIG_SETTINGS)
        self.exec_auto_assess_only = (self.__get_value_from_argv(self.execution_parameters, Constants.ARG_AUTO_ASSESS_ONLY, False)).lower() == 'true'

        # Environment Settings
        self.composite_logger.log_debug(" - Parsing environment settings...")
        self.log_folder = self.environment_settings[Constants.EnvSettings.LOG_FOLDER]
        self.config_folder = self.environment_settings[Constants.EnvSettings.CONFIG_FOLDER]
        self.status_folder = self.environment_settings[Constants.EnvSettings.STATUS_FOLDER]
        self.events_folder = self.environment_settings[Constants.EnvSettings.EVENTS_FOLDER]
        self.telemetry_supported = self.environment_settings[Constants.EnvSettings.TELEMETRY_SUPPORTED]

        # Config Settings
        self.composite_logger.log_debug(" - Parsing configuration settings... [ConfigSettings={0}]".format(str(self.config_settings)))
        self.operation = self.config_settings[Constants.ConfigSettings.OPERATION]
        self.activity_id = self.config_settings[Constants.ConfigSettings.ACTIVITY_ID]
        self.start_time = self.config_settings[Constants.ConfigSettings.START_TIME]
        self.duration = self.__convert_iso8601_duration_to_timedelta_str(self.config_settings[Constants.ConfigSettings.MAXIMUM_DURATION])
        self.included_classifications_list = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.CLASSIFICATIONS_TO_INCLUDE, [])
        self.included_package_name_mask_list = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.PATCHES_TO_INCLUDE, [])
        self.excluded_package_name_mask_list = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.PATCHES_TO_EXCLUDE, [])
        self.maintenance_run_id = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.MAINTENANCE_RUN_ID)
        self.health_store_id = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.HEALTH_STORE_ID)
        if self.operation == Constants.INSTALLATION:
            self.reboot_setting = self.config_settings[Constants.ConfigSettings.REBOOT_SETTING]     # expected to throw if not present
        else:
            self.reboot_setting = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.REBOOT_SETTING, Constants.REBOOT_NEVER)     # safe extension-level default
        self.patch_mode = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.PATCH_MODE)
        self.assessment_mode = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.ASSESSMENT_MODE)
        self.maximum_assessment_interval = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.MAXIMUM_ASSESSMENT_INTERVAL)

        # Accommodation for bugs in higher-level components where 'Security' is being selected without selecting 'Critical' - should be rolled back no later than Jan 2022
        if self.included_classifications_list is not None and ('Security' in self.included_classifications_list and 'Critical' not in self.included_classifications_list):
            self.composite_logger.log_debug("The included_classifications_list was corrected to include 'Critical' when 'Security' was specified.")
            self.included_classifications_list = ['Critical'] + self.included_classifications_list

        # Derived Settings
        self.composite_logger.log_debug(" - Establishing data publishing paths...")
        self.log_file_path = os.path.join(self.log_folder, str(self.sequence_number) + ".core.log")
        self.composite_logger.log_debug("  -- Core log: " + str(self.log_file_path))
        self.status_file_path = os.path.join(self.status_folder, str(self.sequence_number) + ".status")
        self.composite_logger.log_debug("  -- Status file: " + str(self.status_file_path))

        # Auto assessment overrides
        if self.exec_auto_assess_only:
            self.__transform_execution_config_for_auto_assessment()
        else:
            self.composite_logger.log_debug("Not executing in auto-assessment mode.")

    def __transform_execution_config_for_auto_assessment(self):
        self.composite_logger.log_debug("Setting execution configuration values for auto assessment.")
        self.activity_id = str(uuid.uuid4())
        self.included_classifications_list = self.included_package_name_mask_list = self.excluded_package_name_mask_list = []
        self.maintenance_run_id = None
        self.start_time = self.env_layer.datetime.standard_datetime_to_utc(datetime.datetime.utcnow())
        self.duration = Constants.AUTO_ASSESSMENT_MAXIMUM_DURATION
        self.reboot_setting = Constants.REBOOT_NEVER
        self.patch_mode = None

    @staticmethod
    def __get_value_from_argv(argv, key, default_value=Constants.DEFAULT_UNSPECIFIED_VALUE):
        """ Discovers the value associated with a specific parameter in input arguments. """
        for x in range(1, len(argv)):
            if x % 2 == 1:  # key checker
                if str(argv[x]).lower() == key.lower() and x < len(argv):
                    return str(argv[x+1])

        if default_value == Constants.DEFAULT_UNSPECIFIED_VALUE:
            raise Exception("Unable to find key {0} in core arguments: {1}.".format(key, str(argv)))
        else:
            return str(default_value)

    def __get_decoded_json_from_argv(self, argv, key):
        """ Discovers and decodes the JSON body of a specific base64 encoded JSON object in input arguments. """
        value = self.__get_value_from_argv(argv, key)

        try:
            decoded_value = base64.b64decode(value.replace("b\'", ""))
            decoded_json = json.loads(decoded_value)
        except Exception as error:
            self.composite_logger.log_error('Unable to process JSON in core arguments for key: {0}. Details: {1}.'.format(str(key), repr(error)))
            raise

        return decoded_json

    def __get_execution_configuration_value_safely(self, config_json, key, default_value=Constants.DEFAULT_UNSPECIFIED_VALUE):
        """ Allows a update deployment configuration value to be queried safely with a fall-back default (optional). """
        if key in config_json:
            value = config_json[key]
            return value
        else:  # If it is not present
            if default_value is Constants.DEFAULT_UNSPECIFIED_VALUE:  # return None if no preferred fallback
                self.composite_logger.log_debug('Warning: Config JSON did not contain ' + key + '. Returning None.')
                return None
            else:  # return preferred fallback value
                self.composite_logger.log_debug('Warning: Config JSON did not contain ' + key + '. Using default value (' + str(default_value) + ') instead.')
                return default_value

    def __convert_iso8601_duration_to_timedelta_str(self, duration):
        """
            Supports only a subset of the spec as applicable to patch management.
            No non-default period (Y,M,W,D) is supported. Time is supported (H,M,S).
            Can throw exceptions - expected to handled as appropriate in calling code.
        """
        remaining = str(duration)
        if 'PT' not in remaining:
            raise Exception("Unexpected duration format. [Duration={0}]".format(duration))

        discard, remaining = self.__extract_most_significant_unit_from_duration(remaining, 'PT')
        hours, remaining = self.__extract_most_significant_unit_from_duration(remaining, 'H')
        minutes, remaining = self.__extract_most_significant_unit_from_duration(remaining, 'M')
        seconds, remaining = self.__extract_most_significant_unit_from_duration(remaining, 'S')

        return str(datetime.timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds)))

    @staticmethod
    def __extract_most_significant_unit_from_duration(duration_portion, unit_delimiter):
        """ Internal helper function"""
        duration_split = duration_portion.split(unit_delimiter)
        most_significant_unit = 0
        if len(duration_split) == 2:  # found and extracted
            most_significant_unit = duration_split[0]
            remaining_duration_portion = duration_split[1]
        elif len(duration_split) == 1:  # not found
            remaining_duration_portion = duration_split[0]
        else:  # bad data
            raise Exception("Invalid duration portion: {0}".format(str(duration_portion)))
        return most_significant_unit, remaining_duration_portion
