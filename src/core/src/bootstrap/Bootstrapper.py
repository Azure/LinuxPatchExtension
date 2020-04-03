""" Environment Manager """
import base64
import json
import os
import sys
from src.bootstrap.ConfigurationFactory import ConfigurationFactory
from src.bootstrap.Constants import Constants
from src.bootstrap.Container import Container
from src.local_loggers.StdOutFileMirror import StdOutFileMirror


class Bootstrapper(object):
    def __init__(self, argv, capture_stdout=True):
        # Environment awareness
        self.current_env = self.get_current_env()
        self.argv = argv
        self.log_file_path, self.real_record_path = self.get_log_file_and_real_record_paths(argv)
        self.recorder_enabled, self.emulator_enabled = self.get_recorder_emulator_flags(argv)

        # Container initialization
        print("Building bootstrap container configuration...")
        self.configuration_factory = ConfigurationFactory(self.log_file_path, self.real_record_path, self.recorder_enabled, self.emulator_enabled)
        self.container = Container()
        self.container.build(self.configuration_factory.get_bootstrap_configuration(self.current_env))

        # Environment layer capture
        self.env_layer = self.container.get('env_layer')

        # Logging initializations
        self.file_logger = self.container.get('file_logger')
        if capture_stdout:
            self.stdout_file_mirror = StdOutFileMirror(self.env_layer, self.file_logger)
        self.composite_logger = self.container.get('composite_logger')
        self.telemetry_writer = None

        print("\nCompleted building bootstrap container configuration.\n")

    @staticmethod
    def get_current_env():
        """ Decides what environment to bootstrap with """
        current_env = os.getenv(Constants.LPE_ENV_VARIABLE, Constants.PROD)
        if str(current_env) not in [Constants.DEV, Constants.TEST, Constants.PROD]:
            print("Unknown environment requested:")
            current_env = Constants.PROD
        print("Bootstrap environment: " + str(current_env))
        return current_env

    def get_log_file_and_real_record_paths(self, argv):
        """ Performs the minimum steps required to determine where to start logging """
        sequence_number = self.get_value_from_argv(argv, Constants.ARG_SEQUENCE_NUMBER)
        environment_settings = json.loads(base64.b64decode(self.get_value_from_argv(argv, Constants.ARG_ENVIRONMENT_SETTINGS)))
        log_folder = environment_settings[Constants.EnvSettings.LOG_FOLDER]  # can throw exception and that's okay (since we can't recover from this)
        log_file_path = os.path.join(log_folder, str(sequence_number) + ".core.log")
        real_rec_path = os.path.join(log_folder, str(sequence_number) + ".core.rec")
        return log_file_path, real_rec_path

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
    def get_value_from_argv(argv, key):
        """ Discovers the value assigned to a given key based on the core contract on arguments """
        for x in range(1, len(argv)):
            if x % 2 == 1:  # key checker
                if str(argv[x]).lower() == key.lower() and x < len(argv):
                    return str(argv[x+1])
        raise Exception("Unable to find key {0} in core arguments: {1}.".format(key, str(argv)))

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
        self.composite_logger.log_debug(" - Instantiating telemetry writer.")
        telemetry_writer = container.get('telemetry_writer')
        self.composite_logger.log_debug(" - Instantiating progress status writer.")
        status_handler = container.get('status_handler')
        return lifecycle_manager, telemetry_writer, status_handler

    def bootstrap_splash_text(self):
        self.composite_logger.log("\n\n[%exec_name%] \t -- \t Copyright (c) Microsoft Corporation. All rights reserved. \nApplication version: 3.0.[%exec_sub_ver%]\n\n")

    def basic_environment_health_check(self):
        self.composite_logger.log("Python version: " + " ".join(sys.version.splitlines()))
        self.composite_logger.log("Linux distribution: " + str(self.env_layer.platform.linux_distribution()) + "\n")

        # Ensure sudo works in the environment
        sudo_check_result = self.env_layer.check_sudo_status()
        self.composite_logger.log_debug("Sudo status check: " + str(sudo_check_result) + "\n")
