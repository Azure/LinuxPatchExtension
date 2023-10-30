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
from core.src.bootstrap.Bootstrapper import Bootstrapper
from core.src.bootstrap.ExitJanitor import ExitJanitor
from core.src.bootstrap.Constants import Constants


class CoreMain(object):
    def __init__(self, argv):
        """ Execution start point for core patch operations """
        try:
            self.stdout_file_mirror = self.file_logger = self.lifecycle_manager = self.telemetry_writer = None
            self.safely_execute_core(argv)
        except Exception as error:  # this should never catch a failure in production - but defensive coding et al.
            ExitJanitor.safely_handle_extreme_failure(self.stdout_file_mirror, self.file_logger, self.lifecycle_manager, self.telemetry_writer, error)

    def safely_execute_core(self, argv):
        """ Encapsulates sequential safe initialization of components and delegates business-logic execution to the CoreExecutionEngine """
        # ---------------------------------------------------------------------
        # Level 1 bootstrap - absolute bare minimum required for observability
        # ---------------------------------------------------------------------
        current_env = Constants.ExecEnv.PROD
        try:
            bootstrapper = Bootstrapper(argv)
            current_env = bootstrapper.current_env
            env_layer, self.file_logger, composite_logger, self.stdout_file_mirror, self.telemetry_writer = bootstrapper.get_foundational_components()
            container = lifecycle_manager = status_handler = execution_config = None    # for explicit clarity only
            bootstrapper.bootstrap_splash_text()
            if bootstrapper.auto_assessment_log_file_truncated:
                composite_logger.log_debug("[CM] Auto-assessment log file was truncated.")
        except Exception as error:
            print("Critical: L1 Bootstrap failure. No logs were written. [Error={0}]".format(repr(error)))
            return ExitJanitor.final_exit(Constants.ExitCode.CriticalError_NoLog, self.stdout_file_mirror, self.file_logger, self.lifecycle_manager, self.telemetry_writer, current_env)   # return is only for IDE hinting

        # ---------------------------------------------------------------------------------------
        # Level 2 bootstrap - required for service-side reporting & minimal lifecycle management
        # ---------------------------------------------------------------------------------------
        try:
            container = bootstrapper.build_out_container()      # nothing below this except maybe ExecutionConfig should fail (malformed input) - all init path code should be highly robust
            self.lifecycle_manager, status_handler, execution_config = bootstrapper.get_service_components()
            self.lifecycle_manager.execution_start_check()           # terminates execution gracefully if nothing to do
            package_manager = configure_patching_processor = patch_assessor = patch_installer = None
            core_exec = exit_janitor = None
        except Exception as error:
            composite_logger.log_error("Critical: L2 Bootstrap failure. No status was written. [Error={0}][LogLocation={1}]".format(repr(error), bootstrapper.log_file_path))
            return ExitJanitor.final_exit(Constants.ExitCode.CriticalError_NoStatus, self.stdout_file_mirror, self.file_logger, self.lifecycle_manager, self.telemetry_writer, current_env)   # return is only for IDE hinting

        # ---------------------------------------------------
        # Level 3 bootstrap - patch component initialization
        # ---------------------------------------------------
        try:
            package_manager, configure_patching_processor, patch_assessor, patch_installer = bootstrapper.get_patch_components()
            core_exec, exit_janitor = bootstrapper.get_core_exec_components()
        except Exception as error:
            composite_logger.log_error("Critical: L3 Bootstrap failure. [Error={0}][LogLocation={1}]".format(repr(error), bootstrapper.log_file_path))
            return ExitJanitor.final_exit(Constants.ExitCode.CriticalError_Reported, self.stdout_file_mirror, self.file_logger, self.lifecycle_manager, self.telemetry_writer, current_env)   # return is only for IDE hinting

        # ------------------------------
        # Core business logic execution
        # ------------------------------
        try:
            core_exec.perform_housekeeping_tasks()
            core_exec.execute()
            core_exec.set_final_status_handler_statuses()

        except Exception as error:
            if Constants.EnvLayer.PRIVILEGED_OP_MARKER in repr(error):  # Privileged operation handling for non-production use
                composite_logger.log_debug('[CM] Privileged operation request intercepted: ' + repr(error))
                raise

            core_exec.try_set_final_status_handler_statuses()
            exit_janitor.handle_terminal_exception(exception=error, log_file_path=bootstrapper.log_file_path)

        finally:
            exit_janitor.perform_housekeeping_tasks()
            exit_janitor.final_exit(Constants.ExitCode.Okay, self.stdout_file_mirror, self.file_logger, self.lifecycle_manager, self.telemetry_writer, current_env)

