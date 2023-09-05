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
from core.src.bootstrap.Constants import Constants


class ArgumentComposer(object):
    """ Helps encapsulate argument composition for Core from default settings that can be customized as desired prior to composition """

    def __init__(self):
        # Constants
        self.__EXEC = "MsftLinuxPatchCore.py"
        self.__TESTS_FOLDER = "tests"
        self.__SCRATCH_FOLDER = "scratch"
        self.__ARG_TEMPLATE = "{0} {1} {2} {3} \'{4}\' {5} \'{6}\' {7} {8}"
        self.__CONFIG_FOLDER = "config"
        self.__STATUS_FOLDER = "status"
        self.__LOG_FOLDER = "log"
        self.__EVENTS_FOLDER = "events"
        self.__TEMP_FOLDER = "tmp"

        # sequence number
        self.sequence_number = 1

        # environment settings
        scratch_folder = self.__get_scratch_folder()
        self.__log_folder = self.__get_custom_folder(scratch_folder, self.__LOG_FOLDER)
        self.__config_folder = self.__get_custom_folder(scratch_folder, self.__CONFIG_FOLDER)
        self.__status_folder = self.__get_custom_folder(scratch_folder, self.__STATUS_FOLDER)
        self.events_folder = self.__get_custom_folder(self.__log_folder, self.__EVENTS_FOLDER)
        self.temp_folder = self.__get_custom_folder(scratch_folder, self.__TEMP_FOLDER)
        Constants.Paths.EULA_SETTINGS = os.path.join(scratch_folder, "patch.eula.settings")

        # config settings
        self.operation = Constants.INSTALLATION
        self.activity_id = 'c365ab46-a12a-4388-853b-5240a0702124'
        self.start_time = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        self.maximum_duration = 'PT2H'
        self.reboot_setting = 'Never'
        self.classifications_to_include = []
        self.patches_to_include = []
        self.patches_to_exclude = []
        self.maintenance_run_id = None  # Since this is optional, all possible inputs for this are added in respective tests
        self.health_store_id = None
        self.patch_mode = None
        self.assessment_mode = None
        self.maximum_assessment_interval = "PT3H"

        self.exec_auto_assess_only = False

        # REAL environment settings
        self.emulator_enabled = False

    def get_composed_arguments(self, env_settings={}):
        """ Serializes state into arguments for consumption """
        environment_settings = {
            "logFolder": self.__log_folder,
            "configFolder": self.__config_folder,
            "statusFolder": self.__status_folder,
            "eventsFolder": self.events_folder,
            "tempFolder": self.temp_folder,
            "telemetrySupported": True
        }

        # Apply any extra env settings passed in
        for key in env_settings:
            environment_settings[key] = env_settings[key]

        config_settings = {
            "operation": self.operation,
            "activityId": self.activity_id,
            "startTime": self.start_time,
            "maximumDuration": self.maximum_duration,
            "rebootSetting": self.reboot_setting,
            "classificationsToInclude": self.classifications_to_include,
            "patchesToInclude": self.patches_to_include,
            "patchesToExclude": self.patches_to_exclude,
            "maintenanceRunId": self.maintenance_run_id,
            "healthStoreId": self.health_store_id,
            "patchMode": self.patch_mode,
            "assessmentMode": self.assessment_mode,
            "maximumAssessmentInterval": self.maximum_assessment_interval
        }

        return str(self.__ARG_TEMPLATE.format(self.__EXEC, Constants.ARG_SEQUENCE_NUMBER, self.sequence_number,
                                              Constants.ARG_ENVIRONMENT_SETTINGS, self.__get_encoded_json_str(environment_settings),
                                              Constants.ARG_CONFIG_SETTINGS, self.__get_encoded_json_str(config_settings),
                                              Constants.ARG_AUTO_ASSESS_ONLY, str(self.exec_auto_assess_only),
                                              Constants.ARG_INTERNAL_RECORDER_ENABLED, str(False),
                                              Constants.ARG_INTERNAL_EMULATOR_ENABLED, str(self.emulator_enabled))).split(' ')

    @staticmethod
    def __get_encoded_json_str(obj):
        return base64.b64encode(json.dumps(obj).encode("utf-8"))

    def __get_scratch_folder(self):
        """ Returns a predetermined scratch folder and guarantees it exists and is empty. """
        tests_folder = self.__try_get_tests_folder()
        scratch_folder = os.path.join(tests_folder, self.__SCRATCH_FOLDER)
        if os.path.exists(scratch_folder):
            shutil.rmtree(scratch_folder, ignore_errors=True)
        if not os.path.exists(scratch_folder):
            os.mkdir(scratch_folder)
        return scratch_folder

    @staticmethod
    def __get_custom_folder(par_dir, custom_folder_name):
        """ Returns a predetermined custom folder, and guarantees it exists and is empty. """
        custom_folder = os.path.join(par_dir, custom_folder_name)
        if os.path.exists(custom_folder):
            shutil.rmtree(custom_folder, ignore_errors=True)
        if not os.path.exists(custom_folder):
            os.mkdir(custom_folder)
        return custom_folder

    def __try_get_tests_folder(self, path=os.getcwd()):
        """ Returns the current working directory if there's no folder with tests in its name in the absolute path
            else recursively goes upwards until it is found. """
        if os.path.exists(path) and self.__TESTS_FOLDER in path and not path.endswith(self.__TESTS_FOLDER):
            parent_path = os.path.abspath(os.path.join(path, os.pardir))
            return self.__try_get_tests_folder(parent_path)
        return path


