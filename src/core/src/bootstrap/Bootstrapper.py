# coding=utf-8
# Copyright 2020 Microsoft Corporation
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

""" Bootstrapper """
import base64
import json
import os
import sys
import time
from core.src.bootstrap.ConfigurationFactory import ConfigurationFactory
from core.src.bootstrap.Constants import Constants
from core.src.bootstrap.Container import Container
from core.src.local_loggers.StdOutFileMirror import StdOutFileMirror

try:
    import urllib.request as urlreq  # Python 3.x
except ImportError:
    import urllib2 as urlreq         # Python 2.x


class Bootstrapper(object):
    def __init__(self, argv, capture_stdout=True):
        # Environment and basic execution awareness
        self.argv = argv
        self.config_settings = None
        self.current_env = self.__get_current_env()
        self.auto_assessment_only = bool(self.__get_value_from_argv(Constants.ARG_AUTO_ASSESS_ONLY, "False") == "True")
        self.cloud_type = self.__get_cloud_type(self.auto_assessment_only)

        self.log_file_path, self.real_record_path, self.events_folder, self.telemetry_supported = self.__get_path_to_log_files_and_telemetry_dir(argv, self.auto_assessment_only)
        self.recorder_enabled, self.emulator_enabled = self.__get_recorder_emulator_flags()

        # Container initialization
        print("[-- DIALTONE --]\n[BS] Building bootstrap container configuration... " + ("[Environment=" + str(self.current_env) + "]") if self.current_env != Constants.ExecEnv.PROD else "")
        self.configuration_factory = ConfigurationFactory(self.cloud_type, self.log_file_path, self.real_record_path, self.recorder_enabled, self.emulator_enabled, self.events_folder, self.telemetry_supported)
        self.container = Container()
        self.container.build(self.configuration_factory.get_bootstrap_configuration(self.current_env))

        # Environment layer capture
        self.env_layer = self.container.get('env_layer')

        # Logging initializations
        self.auto_assessment_log_file_truncated = False     # used for delayed logging
        self.__reset_auto_assessment_log_file_if_too_large()
        self.file_logger = self.container.get('file_logger')
        self.stdout_file_mirror = StdOutFileMirror(self.env_layer, self.file_logger, capture_stdout, self.current_env)
        self.composite_logger = self.container.get('composite_logger')
        self.telemetry_writer = self.container.get('telemetry_writer')
        self.composite_logger.telemetry_writer = self.telemetry_writer  # Need to set telemetry_writer within logger to enable sending all logs to telemetry

        # Making telemetry better sooner
        self.telemetry_writer.set_task_name(Constants.TelemetryTaskName.AUTO_ASSESSMENT if self.auto_assessment_only else Constants.TelemetryTaskName.EXEC)
        self.telemetry_writer.set_operation_id(self.__get_activity_id_from_config_settings_for_telemetry())

        print("\n[BS] Completed building bootstrap container configuration.")

    # region Public Methods
    def get_foundational_components(self):
        """ Components needed for code execution observability """
        return self.env_layer, self.file_logger, self.composite_logger, self.stdout_file_mirror, self.telemetry_writer

    def build_out_container(self):
        """ First output in a positive bootstrap """
        try:
            # input parameter incorporation
            arguments_config = self.configuration_factory.get_arguments_configuration(self.argv)
            self.container.build(arguments_config)

            # full configuration incorporation
            self.container.build(self.configuration_factory.get_configuration(self.current_env, self.env_layer.get_package_manager()))

            return self.container
        except Exception as error:
            raise Exception("Bootstrapper: Container build out failure. [Error={0}]".format(repr(error)))

    def get_service_components(self):
        """ Components needed for higher-level observability and execution checks """
        return self.container.get('lifecycle_manager'), self.container.get('status_handler'), self.container.get('execution_config')

    def get_patch_components(self):
        """ Components needed for core business-logic execution and controlled core exit """
        return self.container.get('package_manager'), self.container.get('configure_patching_processor'), self.container.get('patch_assessor'), self.container.get('patch_installer')

    def get_core_exec_components(self):
        """ Highest-level execution components in final initialization """
        return self.container.get('core_execution_engine'), self.container.get('exit_janitor')

    def bootstrap_splash_text(self):
        self.composite_logger.log_raw("---------------------------------------------------------------------------------------------------------------------------------------------"
                                      "\n  Microsoft.CPlat.Core.LinuxPatchExtension (Compute Platform \\ AzGPS)    --    Copyright (c) Microsoft Corporation. All rights reserved.  "
                                      "\n  * Component: [%exec_name%]"
                                      "\n  * Version: [%exec_ver%] ([%exec_build_timestamp%])"
                                      "\n  * Source: https://github.com/Azure/LinuxPatchExtension                                                               "
                                      "\n---------------------------------------------------------------------------------------------------------------------------------------------")
        self.composite_logger.log("[BS] Execution environment: [PythonVersion={0}][Distribution={1}][ProcessId={2}][MachineId={3}]".format(sys.version.split()[0], str(self.env_layer.platform.linux_distribution()), str(os.getpid()), self.env_layer.platform.node()))
    # endregion Public Methods

    # region High-risk Methods - no telemetry. must be extremely robust. handler must capture output and return.
    @staticmethod
    def __get_current_env():
        """ Decides what execution environment to bootstrap with """
        current_env = str(os.getenv(Constants.AZGPS_LPE_ENVIRONMENT_VAR, Constants.ExecEnv.PROD))
        current_env = Constants.ExecEnv.PROD if current_env not in [Constants.ExecEnv.DEV, Constants.ExecEnv.TEST, Constants.ExecEnv.PROD] else current_env
        return current_env

    def __get_value_from_argv(self, key, default_value=Constants.DEFAULT_UNSPECIFIED_VALUE):
        """ Discovers the value assigned to a given key based on the core contract on arguments """
        argv = self.argv
        for x in range(1, len(argv)):
            if x % 2 == 1:  # key checker
                if str(argv[x]).lower() == key.lower() and x < len(argv):
                    return str(argv[x + 1])

        if default_value == Constants.DEFAULT_UNSPECIFIED_VALUE:
            raise Exception("Unable to find key {0} in core arguments: {1}.".format(key, str(argv)))
        else:
            return default_value

    def __get_cloud_type(self, auto_assessment_only):
        """ Tries to determine cloud type as efficiently and accurately as possible for dependency injection """
        try:
            if not auto_assessment_only:
                return Constants.CloudType.AZURE        # trivial selection for non-Auto-assessment scenarios

            cloud_type = self.__get_config_setting_value(Constants.ConfigSettings.CLOUD_TYPE)
            if cloud_type not in [Constants.CloudType.AZURE, Constants.CloudType.ARC]:
                raise Exception("Unknown cloud type. [CloudType={0}]".format(str(cloud_type)))
            return Constants.CloudType.AZURE if cloud_type != Constants.CloudType.ARC else Constants.CloudType.ARC
        except Exception as error:                      # this should not happen if services are configured correctly
            print('[BS] Unable to read cloud type. Reverting to instance metadata service check. [Error={0}]'.format(repr(error)))
            return self.__get_cloud_type_using_imds()

    def __get_config_setting_value(self, key):
        """ This is only to be used for highly critical settings in bootstrapper to reduce failure probability. Lazy loading is for improving runtime safety. """
        if self.config_settings is None:
            self.config_settings = self.__get_decoded_json_from_argv(Constants.ARG_CONFIG_SETTINGS)
        return self.config_settings[key]

    def __get_decoded_json_from_argv(self, key):
        """ Discovers and decodes the JSON body of a specific base64 encoded JSON object in input arguments. """
        value = self.__get_value_from_argv(key)
        try:
            decoded_json = json.loads(base64.b64decode(value.replace("b\'", "")).decode())
        except Exception as error:
            raise Exception('Unable to process JSON in core arguments. [Key={0}][Error={1}]'.format(str(key), repr(error)))
        return decoded_json

    @staticmethod
    def __get_cloud_type_using_imds():
        """ Detects cloud type of the VM, in auto-assessment scenarios where the AzGPS Linux Patch Extension runs in Azure Arc.
            Logic taken from Hybrid Compute RP code: https://github.com/PowerShell/DesiredStateConfiguration/blob/dev/src/dsc/dsc_service/service_main.cpp#L115 """
        request = urlreq.Request(Constants.Config.IMDS_END_POINT)
        request.add_header('Metadata', "True")
        request.add_header('UserAgent', "ArcAgent")
        for i in range(0, Constants.MAX_IMDS_CONNECTION_RETRY_COUNT):
            try:
                print("INFO: Bootstrapper: Trying to connect to the IMDS endpoint. [URL={0}][Attempt={1}]".format(str(Constants.Config.IMDS_END_POINT), str(i + 1)))
                res = urlreq.urlopen(request, timeout=2)
                if res.getcode() != 200:
                    raise Exception("Unexpected return code: {0}.".format(str(res.getcode())))
                else:
                    print("- Return code: 200. [CloudType=Azure]\n")
                    return Constants.CloudType.AZURE
            except Exception as error:
                # Failed to connect to Azure IMDS endpoint. This is expected on Arc machine - but not expected on Azure machine.
                print('- IMDS connection attempt failed. [Error={0}]'.format(repr(error)))
                if i < Constants.MAX_IMDS_CONNECTION_RETRY_COUNT - 1:
                    time.sleep(i + 1)
                else:
                    print("INFO: Bootstrapper: Failed to connect to the IMDS endpoint after {0} retries. [CloudType=Arc]\n".format(Constants.MAX_IMDS_CONNECTION_RETRY_COUNT))
                    return Constants.CloudType.ARC

    def __get_recorder_emulator_flags(self):
        """ Determines if the recorder or emulator flags need to be changed from the defaults """
        recorder_enabled = False
        emulator_enabled = False
        try:
            recorder_enabled = bool(self.__get_value_from_argv(Constants.ARG_INTERNAL_RECORDER_ENABLED))
            emulator_enabled = bool(self.__get_value_from_argv(Constants.ARG_INTERNAL_EMULATOR_ENABLED))
            print("INFO: Bootstrapper: [Recorder={0}][Emulator={1}]".format(recorder_enabled, emulator_enabled))
        except Exception:
            pass
        return recorder_enabled, emulator_enabled

    def __get_path_to_log_files_and_telemetry_dir(self, argv, auto_assessment_only):
        """ Performs the minimum steps required to determine where to start logging """
        sequence_number = self.__get_value_from_argv(Constants.ARG_SEQUENCE_NUMBER)
        decode_bytes = base64.b64decode(self.__get_value_from_argv(Constants.ARG_ENVIRONMENT_SETTINGS).replace("b\'", ""))
        decode_value = decode_bytes.decode()
        environment_settings = json.loads(decode_value)
        log_folder = environment_settings[Constants.EnvSettings.LOG_FOLDER]  # can throw exception and that's okay (since we can't recover from this)
        exec_demarcator = ".aa" if auto_assessment_only else ""
        log_file_path = os.path.join(log_folder, str(sequence_number) + exec_demarcator + ".core.log")
        real_rec_path = os.path.join(log_folder, str(sequence_number) + exec_demarcator + ".core.rec")
        events_folder = environment_settings[Constants.EnvSettings.EVENTS_FOLDER]  # can throw exception and that's okay (since we can't recover from this)
        telemetry_supported = environment_settings[Constants.EnvSettings.TELEMETRY_SUPPORTED]
        return log_file_path, real_rec_path, events_folder, telemetry_supported

    def __reset_auto_assessment_log_file_if_too_large(self):
        """ Deletes the auto assessment log file when needed to prevent excessive growth """
        try:
            if self.auto_assessment_only and os.path.exists(self.log_file_path) and os.path.getsize(self.log_file_path) > Constants.MAX_AUTO_ASSESSMENT_LOGFILE_SIZE_IN_BYTES:
                os.remove(self.log_file_path)
                self.auto_assessment_log_file_truncated = True
        except Exception as error:
            print("INFO: Bootstrapper: Error while checking/removing auto-assessment log file. [Path={0}][ExistsRecheck={1}]".format(self.log_file_path, str(os.path.exists(self.log_file_path))))

    def __get_activity_id_from_config_settings_for_telemetry(self):
        """ Returns the activity id of the operation for use in telemetry *only* """
        try:
            return self.__get_config_setting_value(Constants.ConfigSettings.ACTIVITY_ID)
        except Exception as error:
            return Constants.DEFAULT_UNSPECIFIED_VALUE  # no logging because the outcome in telemetry will be self-explanatory
    # endregion High-risk Methods - no telemetry

