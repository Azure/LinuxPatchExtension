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
import shutil
from src.bootstrap.Constants import Constants


class ArgumentComposer(object):
    """ Helps encapsulate argument composition for Core from default settings that can be customized as desired prior to composition """

    def __init__(self):
        # Constants
        self.__EXEC = "MsftLinuxPatchCore.py"
        self.__TESTS_FOLDER = "tests"
        self.__SCRATCH_FOLDER = "scratch"
        self.__ARG_TEMPLATE = "{0} {1} {2} {3} \'{4}\' {5} \'{6}\'"

        # sequence number
        self.sequence_number = 1

        # environment settings
        self.__log_folder = self.__config_folder = self.__status_folder = self.__get_scratch_folder()

        # config settings
        self.operation = Constants.INSTALLATION
        self.activity_id = 'c365ab46-a12a-4388-853b-5240a0702124'
        self.start_time = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        self.maximum_duration = 'PT2H'
        self.reboot_setting = 'Never'
        self.classifications_to_include = []
        self.patches_to_include = []
        self.patches_to_exclude = []
        self.patch_rollout_id = "" #ToDo: tests with a date present, will be added with further changes on using patch_rollout_id in status

        # REAL environment settings
        self.emulator_enabled = False


    def get_composed_arguments(self):
        """ Serializes state into arguments for consumption """
        environment_settings = {
            "logFolder": self.__log_folder,
            "configFolder": self.__config_folder,
            "statusFolder": self.__status_folder
        }

        config_settings = {
            "operation": self.operation,
            "activityId": self.activity_id,
            "startTime": self.start_time,
            "maximumDuration": self.maximum_duration,
            "rebootSetting": self.reboot_setting,
            "classificationsToInclude": self.classifications_to_include,
            "patchesToInclude": self.patches_to_include,
            "patchesToExclude": self.patches_to_exclude,
            "patchRolloutId": self.patch_rollout_id
        }

        return str(self.__ARG_TEMPLATE.format(self.__EXEC, Constants.ARG_SEQUENCE_NUMBER, self.sequence_number,
                                              Constants.ARG_ENVIRONMENT_SETTINGS, self.__get_encoded_json_str(environment_settings),
                                              Constants.ARG_CONFIG_SETTINGS, self.__get_encoded_json_str(config_settings),
                                              Constants.ARG_INTERNAL_RECORDER_ENABLED, str(False),
                                              Constants.ARG_INTERNAL_EMULATOR_ENABLED, str(self.emulator_enabled))).split(' ')

    @staticmethod
    def __get_encoded_json_str(obj):
        return base64.b64encode(json.dumps(obj))

    def __get_scratch_folder(self):
        """ Returns a predetermined scratch folder and guarantees it exists and is empty. """
        tests_folder = self.__try_get_tests_folder()
        scratch_folder = os.path.join(tests_folder, self.__SCRATCH_FOLDER)
        if os.path.exists(scratch_folder):
            shutil.rmtree(scratch_folder, ignore_errors=True)
        os.mkdir(scratch_folder)
        return scratch_folder

    def __try_get_tests_folder(self, path=os.getcwd()):
        """ Returns the current working directory if there's no folder with tests in its name in the absolute path
            else recursively goes upwards until it is found. """
        if os.path.exists(path) and self.__TESTS_FOLDER in path and not path.endswith(self.__TESTS_FOLDER):
            parent_path = os.path.abspath(os.path.join(path, os.pardir))
            return self.__try_get_tests_folder(parent_path)
        return path


