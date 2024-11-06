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
        # Environment details
        self.global_exclusion_list = str(Constants.GLOBAL_EXCLUSION_LIST) if Constants.GLOBAL_EXCLUSION_LIST else None

        # Decoded input parameters
        self.composite_logger.log_debug(" - Decoding input parameters...[InputParameters={0}]".format(str(execution_parameters)))
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
        self.temp_folder = self.environment_settings[Constants.EnvSettings.TEMP_FOLDER]
        self.__check_and_create_temp_folder_if_not_exists()

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
        self.max_patch_publish_date = self.__get_max_patch_publish_date_from_inclusions(self.included_package_name_mask_list)   # supersedes in a mitigation scenario
        self.health_store_id = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.HEALTH_STORE_ID) if self.max_patch_publish_date == str() else str()
        self.max_patch_publish_date = self.__get_max_patch_publish_date(self.health_store_id) if self.max_patch_publish_date == str() else self.max_patch_publish_date
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
        self.log_file_path = os.path.join(self.log_folder, str(self.sequence_number) + ".core.log")
        self.complete_status_file_path = os.path.join(self.status_folder, str(self.sequence_number) + ".complete" + ".status")
        self.status_file_path = os.path.join(self.status_folder, str(self.sequence_number) + ".status")
        self.include_assessment_with_configure_patching = (self.operation == Constants.CONFIGURE_PATCHING and self.assessment_mode == Constants.AssessmentModes.AUTOMATIC_BY_PLATFORM)
        self.composite_logger.log_debug(" - Derived execution-config settings. [CoreLog={0}][CompleteStatusFile={1}][StatusFile={2}][IncludeAssessmentWithConfigurePatching={3}]"
                                        .format(str(self.log_file_path), str(self.complete_status_file_path), str(self.status_file_path), self.include_assessment_with_configure_patching))

        # Auto assessment overrides
        if self.exec_auto_assess_only:
            self.__transform_execution_config_for_auto_assessment()
        else:
            self.composite_logger.log_debug("Not executing in auto-assessment mode.")

        # EULA config
        self.accept_package_eula = self.__is_eula_accepted_for_all_patches()

    def __transform_execution_config_for_auto_assessment(self):
        self.activity_id = str(uuid.uuid4())
        self.included_classifications_list = self.included_package_name_mask_list = self.excluded_package_name_mask_list = []
        self.maintenance_run_id = None
        self.health_store_id = None
        self.start_time = self.env_layer.datetime.standard_datetime_to_utc(datetime.datetime.utcnow())
        self.duration = Constants.AUTO_ASSESSMENT_MAXIMUM_DURATION
        self.reboot_setting = Constants.REBOOT_NEVER
        self.patch_mode = None
        self.composite_logger.log_debug("Setting execution configuration values for auto assessment. [GeneratedActivityId={0}][StartTime={1}]".format(self.activity_id, str(self.start_time)))

    def __get_max_patch_publish_date(self, health_store_id):
        # type: (str) -> object
        """ Obtains implicit date ceiling for published date - converts pub_off_sku_2024.04.01 to 20240401T000000Z """
        max_patch_publish_date = str()
        if health_store_id is not None and health_store_id != "":
            split = health_store_id.split("_")
            if len(split) == 4 and len(split[3]) == 10:
                max_patch_publish_date = "{0}T000000Z".format(split[3].replace(".", ""))

        self.composite_logger.log_debug("[EC] Getting max patch publish date. [MaxPatchPublishDate={0}][HealthStoreId={1}]".format(str(max_patch_publish_date), str(health_store_id)))
        return max_patch_publish_date

    def __get_max_patch_publish_date_from_inclusions(self, included_package_name_mask_list):
        # type (str) -> str
        # This is for AzGPS mitigation mode execution for Strict safe-deployment of patches.
        mitigation_mode_flag = False
        mitigation_mode_flag_pos = -1
        candidate = str()
        candidate_pos = -1

        for i in range(0, len(included_package_name_mask_list)):
            if mitigation_mode_flag and candidate != str():
                break

            if included_package_name_mask_list[i] == "AzGPS_Mitigation_Mode_No_SLA":
                mitigation_mode_flag = True
                mitigation_mode_flag_pos = i
                continue

            if candidate != str() or not included_package_name_mask_list[i].startswith("MaxPatchPublishDate="):
                continue

            candidate = included_package_name_mask_list[i].replace("MaxPatchPublishDate=", "")
            candidate_split = candidate.split("T")
            if (len(candidate) == 16 and len(candidate_split) == 2 and candidate_split[0].isdigit() and len(candidate_split[0]) == 8
                    and candidate_split[1].endswith("Z") and candidate_split[1][0:6].isdigit()):
                self.composite_logger.log_debug("[EC] Discovered effective MaxPatchPublishDate in patch inclusions. [MaxPatchPublishDate={0}]".format(str(candidate)))
                candidate_pos = i
            else:
                self.composite_logger.log_debug("[EC] Invalid match on MaxPatchPublishDate in patch inclusions. [MaxPatchPublishDate={0}]".format(str(candidate)))
                candidate = str()

        if mitigation_mode_flag and candidate != str() and mitigation_mode_flag_pos != -1 and candidate_pos != -1:
            self.composite_logger.log_warning("AzGPS Mitigation Mode: There is no support or SLA for execution in this mode without explicit direction from AzGPS engineering.")
            included_package_name_mask_list.pop(mitigation_mode_flag_pos)
            included_package_name_mask_list.pop(candidate_pos - 1 if mitigation_mode_flag_pos < candidate_pos else candidate_pos)
            return candidate

        return str()

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
            decoded_bytes = base64.b64decode(value.replace("b\'", ""))
            decoded_value = decoded_bytes.decode()
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
            Can throw exceptions - expected to be handled as appropriate in calling code.
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

    def __check_and_create_temp_folder_if_not_exists(self):
        """Verifies temp folder exists, creates new one if not found"""
        if self.temp_folder is None:
            par_dir = os.path.dirname(self.config_folder)
            if not os.path.exists(par_dir):
                raise Exception("Parent directory for all extension artifacts such as config folder, status folder, etc. not found at [{0}].".format(repr(par_dir)))
            self.temp_folder = os.path.join(par_dir, Constants.TEMP_FOLDER_DIR_NAME)

        if not os.path.exists(self.temp_folder):
            self.composite_logger.log_debug("Temp folder does not exist, creating one from extension core. [Path={0}]".format(str(self.temp_folder)))
            os.mkdir(self.temp_folder)

    def __is_eula_accepted_for_all_patches(self):
        """ Reads customer provided config on EULA acceptance from disk and returns a boolean.
            NOTE: This is a temporary solution and will be deprecated soon """
        is_eula_accepted = False
        try:
            if os.path.exists(Constants.AzGPSPaths.EULA_SETTINGS):
                eula_settings = json.loads(self.env_layer.file_system.read_with_retry(Constants.AzGPSPaths.EULA_SETTINGS) or 'null')
                accept_eula_for_all_patches = self.__fetch_specific_eula_setting(eula_settings, Constants.EulaSettings.ACCEPT_EULA_FOR_ALL_PATCHES)
                accepted_by = self.__fetch_specific_eula_setting(eula_settings, Constants.EulaSettings.ACCEPTED_BY)
                last_modified = self.__fetch_specific_eula_setting(eula_settings, Constants.EulaSettings.LAST_MODIFIED)
                if accept_eula_for_all_patches is not None and accept_eula_for_all_patches in [True, 'True', 'true', '1', 1]:
                    is_eula_accepted = True
                self.composite_logger.log_debug("EULA config values from disk: [AcceptEULAForAllPatches={0}] [AcceptedBy={1}] [LastModified={2}]. Computed value of [IsEULAAccepted={3}]"
                                                .format(str(accept_eula_for_all_patches), str(accepted_by), str(last_modified), str(is_eula_accepted)))
            else:
                self.composite_logger.log_debug("No EULA Settings found on the VM. Computed value of [IsEULAAccepted={0}]".format(str(is_eula_accepted)))
        except Exception as error:
            self.composite_logger.log_debug("Error occurred while reading and parsing EULA settings. Not accepting EULA for any patch. Error=[{0}]".format(repr(error)))

        return is_eula_accepted

    @staticmethod
    def __fetch_specific_eula_setting(settings_source, setting_to_fetch):
        """ Returns the specific setting value from eula_settings_source or None if not found """
        if settings_source is not None and setting_to_fetch is not None and setting_to_fetch in settings_source:
            return settings_source[setting_to_fetch]
        return None

