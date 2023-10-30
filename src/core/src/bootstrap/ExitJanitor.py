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

""" ExitJanitor - responsible for orchestrating all cleanup activities at managed execution termination """
import os
from core.src.bootstrap.Constants import Constants

# do not instantiate directly - these are exclusively for type hinting support
from core.src.bootstrap.EnvLayer import EnvLayer
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.src.local_loggers.CompositeLogger import CompositeLogger


class ExitJanitor(object):
    def __init__(self, env_layer, execution_config, composite_logger):
        # type: (EnvLayer, ExecutionConfig, CompositeLogger) -> None

        # All the entities below are guaranteed to be working at initialization
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.composite_logger = composite_logger

    # region - Rudimentary clean up with minimal dependencies
    @staticmethod
    def final_exit(exit_code=Constants.ExitCode.Okay, stdout_file_mirror=None, file_logger=None, lifecycle_manager=None, telemetry_writer=None, config_env=Constants.ExecEnv.PROD):
        """ Common code for exit in almost all cases (some exceptions apply) """
        if telemetry_writer is not None:
            telemetry_writer.write_event("[EJ][EXIT] Completed Linux Patch Core execution.", Constants.EventLevel.Info)
        if lifecycle_manager is not None:
            lifecycle_manager.update_core_sequence(completed=True)
        if stdout_file_mirror is not None:
            stdout_file_mirror.stop()
        if file_logger is not None:
            file_logger.close(message_at_close="\n[EJ][EXIT] End of all output. Execution complete.")

        if config_env != Constants.ExecEnv.DEV:
            exit(exit_code)
            #raise Exception("[EJ][DEV] Intercepted exit. [ExitCode={0}]".format(str(exit_code)), Constants.EnvLayer.PRIVILEGED_OP_MARKER)

    @staticmethod
    def safely_handle_extreme_failure(stdout_file_mirror, file_logger, lifecycle_manager, telemetry_writer, exception, config_env=Constants.ExecEnv.PROD):
        """ Encapsulates the most basic failure management without instantiation of even ExitJanitor """
        if Constants.EnvLayer.PRIVILEGED_OP_MARKER in repr(exception):
            raise  # Privileged operation handling for non-production use
        print(Constants.Errors.UNHANDLED_EXCEPTION.format(repr(exception)))     # should be captured by handler
        ExitJanitor.final_exit(Constants.ExitCode.CriticalError, stdout_file_mirror, file_logger, lifecycle_manager, telemetry_writer)
    # endregion - Rudimentary clean up with minimal dependencies

    # region - Post-operational housekeeping
    def perform_housekeeping_tasks(self):
        # type: () -> None
        """ Performs environment maintenance tasks that need to happen after core business logic execution. """
        if os.path.exists(self.execution_config.temp_folder):
            self.composite_logger.log_debug("[EJ] Deleting all files of certain format from temp folder [FileFormat={0}][TempFolderLocation={1}]".format(Constants.TEMP_FOLDER_CLEANUP_ARTIFACT_LIST, str(self.execution_config.temp_folder)))
            self.env_layer.file_system.delete_files_from_dir(self.execution_config.temp_folder, Constants.TEMP_FOLDER_CLEANUP_ARTIFACT_LIST)
    # endregion - Post-operational housekeeping

    def handle_terminal_exception(self, exception, log_file_path):
        # type: (Exception, str) -> None
        """ Highest-level exception handling for core operations """
        self.composite_logger.log_error("TERMINAL EXCEPTION: {0}.\nLOGS FOR SUPPORT: {1}".format(str(exception.args[0] if len(exception.args) > 1 else repr(exception)), log_file_path))
        self.composite_logger.log_debug("[EJ] Terminal exception details for debugging: {0}".format(repr(exception)))

