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

import datetime
import os
import sys
from extension.src.ActionHandler import ActionHandler
from extension.src.EnvLayer import EnvLayer
from extension.src.EnvHealthManager import EnvHealthManager
from extension.src.RuntimeContextHandler import RuntimeContextHandler
from extension.src.TelemetryWriter import TelemetryWriter
from extension.src.file_handlers.JsonFileHandler import JsonFileHandler
from extension.src.file_handlers.CoreStateHandler import CoreStateHandler
from extension.src.file_handlers.ExtConfigSettingsHandler import ExtConfigSettingsHandler
from extension.src.file_handlers.ExtEnvHandler import ExtEnvHandler
from extension.src.file_handlers.ExtOutputStatusHandler import ExtOutputStatusHandler
from extension.src.file_handlers.ExtStateHandler import ExtStateHandler
from extension.src.local_loggers.Logger import Logger
from extension.src.ProcessHandler import ProcessHandler
from extension.src.Utility import Utility
from extension.src.Constants import Constants


def main(argv):
    stdout_file_mirror = None
    file_logger = None
    logger = Logger()
    telemetry_writer = TelemetryWriter(logger)
    logger.telemetry_writer = telemetry_writer  # Need to set telemetry_writer within logger to enable sending all logs to telemetry
    try:
        # initializing action handler
        # args will have values install, uninstall, etc, as given in MsftLinuxPatchExtShim.sh in the operation var
        cmd_exec_start_time = datetime.datetime.utcnow()
        utility = Utility(logger)
        runtime_context_handler = RuntimeContextHandler(logger)
        json_file_handler = JsonFileHandler(logger)
        ext_env_handler = ExtEnvHandler(json_file_handler)
        env_layer = EnvLayer()
        env_health_manager = EnvHealthManager(env_layer)
        if ext_env_handler.handler_environment_json is not None and ext_env_handler.config_folder is not None:
            config_folder = ext_env_handler.config_folder
            if config_folder is None or not os.path.exists(config_folder):
                logger.log_error("Config folder not found at [{0}].".format(repr(config_folder)))
                exit(Constants.ExitCode.MissingConfig)

            ext_config_settings_handler = ExtConfigSettingsHandler(logger, json_file_handler, config_folder)
            core_state_handler = CoreStateHandler(config_folder, json_file_handler)
            ext_state_handler = ExtStateHandler(config_folder, utility, json_file_handler)
            ext_output_status_handler = ExtOutputStatusHandler(logger, utility, json_file_handler, ext_env_handler.status_folder)
            process_handler = ProcessHandler(logger, env_layer, ext_output_status_handler)
            action_handler = ActionHandler(logger, telemetry_writer, utility, runtime_context_handler, json_file_handler, env_health_manager, ext_env_handler, ext_config_settings_handler, core_state_handler, ext_state_handler, ext_output_status_handler, process_handler, cmd_exec_start_time)
            action_handler.determine_operation(argv[1])
        else:
            error_cause = "No configuration provided in HandlerEnvironment" if ext_env_handler.handler_environment_json is None else "Path to config folder not specified in HandlerEnvironment"
            error_msg = "Error processing file. [File={0}] [Error={1}]".format(Constants.HANDLER_ENVIRONMENT_FILE, error_cause)
            raise Exception(error_msg)
    except Exception as error:
        logger.log_error(repr(error))
        return Constants.ExitCode.HandlerFailed
    finally:
        if stdout_file_mirror is not None:
            stdout_file_mirror.stop()
        if file_logger is not None:
            file_logger.close()


if __name__ == '__main__':
    main(sys.argv)