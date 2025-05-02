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

""" Environment Manager """
import base64
import json
import os
import sys
import time
from core.src.bootstrap.ConfigurationFactory import ConfigurationFactory
from core.src.bootstrap.Constants import Constants
from core.src.bootstrap.Container import Container
from core.src.local_loggers.StdOutFileMirror import StdOutFileMirror


class Bootstrapper(object):
    def __init__(self, argv, capture_stdout=True):
        # Environment and basic execution awareness
        self.current_env = self.get_current_env()
        self.argv = argv
        self.auto_assessment_only = bool(self.get_value_from_argv(self.argv, Constants.ARG_AUTO_ASSESS_ONLY, "False") == "True")
        self.log_file_path, self.real_record_path, self.events_folder, self.telemetry_supported = self.get_path_to_log_files_and_telemetry_dir(argv, self.auto_assessment_only)
        self.recorder_enabled, self.emulator_enabled = self.get_recorder_emulator_flags(argv)

        # Container initialization
        print("Building bootstrap container configuration...")
        self.configuration_factory = ConfigurationFactory(self.log_file_path, self.real_record_path, self.recorder_enabled, self.emulator_enabled, self.events_folder, self.telemetry_supported)
        self.container = Container()
        self.container.build(self.configuration_factory.get_bootstrap_configuration(self.current_env))

        # Environment layer capture
        self.env_layer = self.container.get('env_layer')

        # Logging initializations
        self.reset_auto_assessment_log_file_if_needed()
        self.file_logger = self.container.get('file_logger')
        if capture_stdout:
            self.stdout_file_mirror = StdOutFileMirror(self.env_layer, self.file_logger)
        self.composite_logger = self.container.get('composite_logger')
        self.telemetry_writer = self.container.get('telemetry_writer')
        self.composite_logger.telemetry_writer = self.telemetry_writer  # Need to set telemetry_writer within logger to enable sending all logs to telemetry

        print("\nCompleted building bootstrap container configuration.\n")

    @staticmethod
    def get_current_env():
        """ Decides what environment to bootstrap with """
        current_env = str(os.getenv(Constants.LPE_ENV_VARIABLE, Constants.PROD))
        if current_env not in [Constants.DEV, Constants.TEST, Constants.PROD]:
            print("Unknown environment requested: {0}".format(current_env))
            current_env = Constants.PROD
        print("Bootstrap environment: {0}".format(current_env))
        return current_env

    def get_path_to_log_files_and_telemetry_dir(self, argv, auto_assessment_only):
        """ Performs the minimum steps required to determine where to start logging """
        sequence_number = self.get_value_from_argv(argv, Constants.ARG_SEQUENCE_NUMBER)
        decode_bytes = base64.b64decode(self.get_value_from_argv(argv, Constants.ARG_ENVIRONMENT_SETTINGS).replace("b\'", ""))
        decode_value = decode_bytes.decode()
        environment_settings = json.loads(decode_value)
        log_folder = environment_settings[Constants.EnvSettings.LOG_FOLDER]  # can throw exception and that's okay (since we can't recover from this)
        exec_demarcator = ".aa" if auto_assessment_only else ""
        log_file_path = os.path.join(log_folder, str(sequence_number) + exec_demarcator + ".core.log")
        real_rec_path = os.path.join(log_folder, str(sequence_number) + exec_demarcator + ".core.rec")
        events_folder = environment_settings[Constants.EnvSettings.EVENTS_FOLDER]  # can throw exception and that's okay (since we can't recover from this)
        telemetry_supported = environment_settings[Constants.EnvSettings.TELEMETRY_SUPPORTED]
        return log_file_path, real_rec_path, events_folder, telemetry_supported

    def reset_auto_assessment_log_file_if_needed(self):
        """ Deletes the auto assessment log file when needed to prevent excessive growth """
        try:
            if self.auto_assessment_only and os.path.exists(self.log_file_path) and os.path.getsize(self.log_file_path) > Constants.MAX_AUTO_ASSESSMENT_LOGFILE_SIZE_IN_BYTES:
                os.remove(self.log_file_path)
        except Exception as error:
            print("INFO: Error while checking/removing auto-assessment log file. [Path={0}][ExistsRecheck={1}]".format(self.log_file_path, str(os.path.exists(self.log_file_path))))

    def get_recorder_emulator_flags(self, argv):
        """ Determines if the recorder or emulator flags need to be changed from the defaults """
        recorder_enabled = False
        emulator_enabled = False
        try:
            recorder_enabled = bool(self.get_value_from_argv(argv, Constants.ARG_INTERNAL_RECORDER_ENABLED))
            emulator_enabled = bool(self.get_value_from_argv(argv, Constants.ARG_INTERNAL_EMULATOR_ENABLED))
        except Exception as error:
            print("INFO: Default environment layer settings loaded.")
        return recorder_enabled, emulator_enabled

    @staticmethod
    def get_value_from_argv(argv, key, default_value=Constants.DEFAULT_UNSPECIFIED_VALUE):
        """ Discovers the value assigned to a given key based on the core contract on arguments """
        for x in range(1, len(argv)):
            if x % 2 == 1:  # key checker
                if str(argv[x]).lower() == key.lower() and x < len(argv):
                    return str(argv[x+1])

        if default_value == Constants.DEFAULT_UNSPECIFIED_VALUE:
            raise Exception("Unable to find key {0} in core arguments: {1}.".format(key, str(argv)))
        else:
            return default_value

    def build_out_container(self):
        # First output in a positive bootstrap
        try:
            # input parameter incorporation
            arguments_config = self.configuration_factory.get_arguments_configuration(self.argv)
            self.container.build(arguments_config)

            # full configuration incorporation
            self.container.build(self.configuration_factory.get_configuration(self.current_env, self.env_layer.get_package_manager()))

            return self.container
        except Exception as error:
            self.composite_logger.log_error('\nEXCEPTION during patch management core bootstrap: ' + repr(error))
            raise
        pass

    def build_core_components(self, container):
        self.composite_logger.log_debug(" - Instantiating lifecycle manager.")
        lifecycle_manager = container.get('lifecycle_manager')
        self.composite_logger.log_debug(" - Instantiating progress status writer.")
        status_handler = container.get('status_handler')
        return lifecycle_manager, status_handler

    def bootstrap_splash_text(self):
        self.composite_logger.log("\n\n[%exec_name%] \t -- \t Copyright (c) Microsoft Corporation. All rights reserved. \nBuild Date: [%exec_build_date%]\n\n")

    def basic_environment_health_check(self):
        self.composite_logger.log("Python version: " + " ".join(sys.version.splitlines()))
        self.composite_logger.log("Linux distribution: " + str(self.env_layer.platform.linux_distribution()) + "\n")
        self.composite_logger.log("Process id: " + str(os.getpid()))

        # Ensure sudo works in the environment
        sudo_check_result = self.check_sudo_status_with_retry()
        self.composite_logger.log_debug("Sudo status check: " + str(sudo_check_result) + "\n")

    def check_sudo_status_with_retry(self, raise_if_not_sudo=True):
        # type:(bool) -> any
        """ retry to invoke sudo check """
        for attempts in range(1, Constants.MAX_CHECK_SUDO_RETRY_COUNT + 1):
            try:
                sudo_status = self.check_sudo_status(raise_if_not_sudo=raise_if_not_sudo)

                if sudo_status and attempts > 1:
                    self.composite_logger.log_debug("Sudo Check Successfully [RetryCount={0}][MaxRetryCount={1}]".format(str(attempts), Constants.MAX_CHECK_SUDO_RETRY_COUNT))
                    return sudo_status

                elif sudo_status is None or sudo_status is False:
                    if attempts < Constants.MAX_CHECK_SUDO_RETRY_COUNT:
                        self.composite_logger.log_debug("Retrying sudo status check after a delay of [ElapsedTimeInSeconds={0}][RetryCount={1}]".format(Constants.MAX_CHECK_SUDO_INTERVAL_IN_SEC, str(attempts)))
                        time.sleep(Constants.MAX_CHECK_SUDO_INTERVAL_IN_SEC)
                        continue

                    elif attempts >= Constants.MAX_CHECK_SUDO_RETRY_COUNT:
                        raise

            except Exception as exception:
                if attempts >= Constants.MAX_CHECK_SUDO_RETRY_COUNT:
                    self.composite_logger.log_error("Customer environment error (sudo failure). [Exception={0}][MaxRetryCount={1}]".format(str(exception), str(attempts)))
                    if raise_if_not_sudo:
                        raise
                self.composite_logger.log_debug("Retrying sudo status check after a delay of [ElapsedTimeInSeconds={0}][RetryCount={1}]".format(Constants.MAX_CHECK_SUDO_INTERVAL_IN_SEC, str(attempts)))
                time.sleep(Constants.MAX_CHECK_SUDO_INTERVAL_IN_SEC)

    def check_sudo_status(self, raise_if_not_sudo=True):
        # type:(bool) -> any
        """ Checks if we can invoke sudo successfully. """
        try:
            self.composite_logger.log("Performing sudo status check... This should complete within 10 seconds.")
            return_code, output = self.env_layer.run_command_output("timeout 10 sudo id && echo True || echo False", False, False)
            # output should look like either this (bad):
            #   [sudo] password for username:
            #   False
            # or this (good):
            #   uid=0(root) gid=0(root) groups=0(root)
            #   True

            output_lines = output.splitlines()
            if len(output_lines) < 2:
                raise Exception("Unexpected sudo check result. Output: " + " ".join(output.split("\n")))

            if output_lines[1] == "True":
                return True
            elif output_lines[1] == "False":
                if raise_if_not_sudo:
                    raise Exception("Unable to invoke sudo successfully. Output: " + " ".join(output.split("\n")))
                return False
            else:
                raise Exception("Unexpected sudo check result. Output: " + " ".join(output.split("\n")))
        except Exception as exception:
            self.composite_logger.log_debug("Sudo status check failed. Please ensure the computer is configured correctly for sudo invocation. " +
                                            "Exception details: " + str(exception))
            if raise_if_not_sudo:
                raise

