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

import collections
import os
import os.path
import re
from extension.src.Constants import Constants


class ExtConfigSettingsHandler(object):
    """ Responsible for managing any operations with <Sequence Number>.settings file """
    def __init__(self, logger, json_file_handler, config_folder):
        self.config_folder = config_folder
        self.logger = logger
        self.json_file_handler = json_file_handler
        self.file_ext = Constants.CONFIG_SETTINGS_FILE_EXTENSION
        self.runtime_settings_key = Constants.RUNTIME_SETTINGS
        self.handler_settings_key = Constants.HANDLER_SETTINGS
        self.public_settings_key = Constants.PUBLIC_SETTINGS
        self.public_settings_all_keys = Constants.ConfigPublicSettingsFields

    def get_seq_no(self, is_enable_request=False):
        """ Fetches sequence number, initially from the env variable. If nothing is set in env variable then fetches from config folder based on timestamp, since GA updates the settings file before calling a command """
        try:
            # get seq no from env var
            seq_no = self.__get_seq_no_from_env_var()

            if seq_no is None:
                if is_enable_request:
                    self.logger.log_warning("Since sequence number is not provided in the environment variable, will try to fetch from the most recent settings file")
                    # get seq no from settings file
                    return self.__get_seq_no_from_config_settings()
                else:
                    self.logger.log_error("Sequence number not provided.")
                    return None

            # verify if config settings file exists for the seq_no
            if not self.__verify_config_settings_file_exists(seq_no):
                self.logger.log_error("Could not verify sequence number found in environment variable with any configuration settings files on the machine")
                return None

            return seq_no

        except Exception as error:
            self.logger.log_error("Error occurred while fetching sequence number. [Exception={0}]".format(repr(error)))
            raise

    def __get_seq_no_from_env_var(self):
        """ Queries the environment variable to get seq_no and verifies if the corresponding <seq_no>.settings file exists """
        self.logger.log("Fetching and validating sequence number from the environment variable")
        seq_no = os.getenv(Constants.SEQ_NO_ENVIRONMENT_VAR)

        if seq_no is None:
            self.logger.log_warning("Sequence number not found in the environment variable.")
            return None

        self.logger.log("Sequence number set in environment variable. [Sequence No={0}]".format(str(seq_no)))
        return seq_no

    def __verify_config_settings_file_exists(self, seq_no):
        settings_file_path = os.path.join(self.config_folder, str(seq_no) + self.file_ext)
        if os.path.exists(settings_file_path) and os.path.isfile(settings_file_path):
            self.logger.log("Configuration settings file exists for the current sequence number. [Sequence No={0}]".format(str(seq_no)))
            return True

        self.logger.log_error("Configuration settings file not found, for the current sequence number. [Sequence No={0}]".format(str(seq_no)))
        return False

    def __get_seq_no_from_config_settings(self):
        """ Fetches seq no from the most recent *.settings file in config folder """
        self.logger.log("Fetching sequence number from the recently modified config settings file within config folder.")
        seq_no = None
        cur_seq_no = None
        freshest_time = None
        for subdir, dirs, files in os.walk(self.config_folder):
            for file in files:
                try:
                    if re.match('^\d+' + self.file_ext + '$', file):
                        cur_seq_no = int(os.path.basename(file).split('.')[0])
                        file_modified_time = os.path.getmtime(os.path.join(self.config_folder, file))
                        self.logger.log("Sequence number being considered and the corresponding file modified time. [Sequence No={0}] [Modified={1}]".format(str(cur_seq_no), str(file_modified_time)))
                        if freshest_time is None:
                            freshest_time = file_modified_time
                            seq_no = cur_seq_no
                        else:
                            current_file_m_time = file_modified_time
                            if current_file_m_time > freshest_time:
                                freshest_time = current_file_m_time
                                seq_no = cur_seq_no
                except ValueError:
                    continue
        if seq_no is None:
            self.logger.log("Could not find sequence number from the config folder")
        else:
            self.logger.log("Most recent sequence number found from config settings is [Sequence No={0}]".format(str(seq_no)))
        return seq_no

    def read_file(self, seq_no):
        """ Fetches config from <seq_no>.settings file in <self.config_folder>. Raises an exception if no content/file found/errors processing file """
        try:
            file_name = str(seq_no) + self.file_ext
            config_settings_json = self.json_file_handler.get_json_file_content(file_name, self.config_folder, raise_if_not_found=True)
            if config_settings_json is not None and self.are_config_settings_valid(config_settings_json):
                operation = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.operation)
                activity_id = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.activity_id)
                start_time = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.start_time)
                max_duration = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.maximum_duration, raise_if_not_found=False)
                reboot_setting = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.reboot_setting, raise_if_not_found=False)
                include_classifications = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.include_classifications, raise_if_not_found=False)
                include_patches = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.include_patches, raise_if_not_found=False)
                exclude_patches = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.exclude_patches, raise_if_not_found=False)
                internal_settings = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.internal_settings, raise_if_not_found=False)
                maintenance_run_id = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.maintenance_run_id, raise_if_not_found=False)
                if maintenance_run_id is None:
                    # read maintenenacerunId first, if that doesn't exist,read patch rollout id and pass it through as maintenance run id
                    # todo: remove patch rollout id later
                    maintenance_run_id = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.patch_rollout_id, raise_if_not_found=False)
                patch_mode = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.patch_mode, raise_if_not_found=False)
                assessment_mode = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.assessment_mode, raise_if_not_found=False)
                maximum_assessment_interval = assessment_mode = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.maximum_assessment_interval, raise_if_not_found=False)
                config_settings_values = collections.namedtuple("config_settings", [self.public_settings_all_keys.operation, self.public_settings_all_keys.activity_id, self.public_settings_all_keys.start_time,
                                                                                    self.public_settings_all_keys.maximum_duration, self.public_settings_all_keys.reboot_setting, self.public_settings_all_keys.include_classifications,
                                                                                    self.public_settings_all_keys.include_patches, self.public_settings_all_keys.exclude_patches, self.public_settings_all_keys.internal_settings,
                                                                                    self.public_settings_all_keys.maintenance_run_id, self.public_settings_all_keys.patch_mode,
                                                                                    self.public_settings_all_keys.assessment_mode, self.public_settings_all_keys.maximum_assessment_interval])
                return config_settings_values(operation, activity_id, start_time, max_duration, reboot_setting, include_classifications, include_patches, exclude_patches,
                                              internal_settings, maintenance_run_id, patch_mode, assessment_mode, maximum_assessment_interval)
            else:
                config_invalid_due_to = "no content found in the file" if config_settings_json is None else "settings not in expected format"
                raise Exception("Config Settings json file invalid due to " + config_invalid_due_to)
        except Exception as error:
            error_msg = "Error processing config settings file. [Sequence Number={0}] [Exception= {1}]".format(seq_no, repr(error))
            self.logger.log_error(error_msg)
            raise

    def are_config_settings_valid(self, config_settings_json):
        """ Validates all the configs in <seq_no>.settings file. Raises an exception if any issues found """
        try:
            if config_settings_json is None or type(config_settings_json) is not dict or not bool(config_settings_json):
                self.logger.log_error("Configuration settings not of expected format")
                return False
            # file contains "runtimeSettings"
            if self.runtime_settings_key not in config_settings_json or type(config_settings_json[self.runtime_settings_key]) != list or config_settings_json[self.runtime_settings_key] is None or len(config_settings_json[self.runtime_settings_key]) == 0:
                self.logger.log_error("runtimeSettings not of expected format")
                return False
            # file contains "handlerSettings"
            if self.handler_settings_key not in config_settings_json[self.runtime_settings_key][0] or type(config_settings_json[self.runtime_settings_key][0][self.handler_settings_key]) is not dict \
                    or config_settings_json[self.runtime_settings_key][0][self.handler_settings_key] is None or not bool(config_settings_json[self.runtime_settings_key][0][self.handler_settings_key]):
                self.logger.log_error("handlerSettings not of expected format")
                return False
            # file contains "publicSettings"
            if self.public_settings_key not in config_settings_json[self.runtime_settings_key][0][self.handler_settings_key] or type(config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key]) is not dict \
                    or config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key] is None or not bool(config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key]):
                self.logger.log_error("publicSettings not of expected format")
                return False

            # verifying Configuration settings contain all the mandatory keys
            for public_setting in [self.public_settings_all_keys.operation, self.public_settings_all_keys.activity_id, self.public_settings_all_keys.start_time]:
                if public_setting in config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key] and config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key][public_setting]:
                    continue
                else:
                    self.logger.log_error("Mandatory key missing in publicSettings section of the configuration settings: " + str(public_setting))
                    return False
            return True
        except Exception as error:
            self.logger.log_error(error)
            return False

    def get_ext_config_value_safely(self, config_settings_json, key, raise_if_not_found=True):
        """ Allows a patch deployment configuration value to be queried safely with a fall-back default (optional).
        An exception will be raised if default_value is not explicitly set when called (considered by-design). """

        if config_settings_json is not None and len(config_settings_json) != 0:
            if key in config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key]:
                value = config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key][key]
                return value
            else:  # If it is not present
                if raise_if_not_found:
                    raise Exception("Value not found for given config. [Config={0}]".format(key))
                else:
                    return None
        return None

