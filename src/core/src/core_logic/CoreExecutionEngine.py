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

""" Core Execution Engine """
import os
import sys
from core.src.bootstrap.Constants import Constants

# do not instantiate directly - these are exclusively for type hinting support
from core.src.bootstrap.EnvLayer import EnvLayer
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.src.local_loggers.FileLogger import FileLogger
from core.src.local_loggers.CompositeLogger import CompositeLogger
from core.src.service_interfaces.TelemetryWriter import TelemetryWriter
from core.src.service_interfaces.StatusHandler import StatusHandler
from core.src.package_managers.PackageManager import PackageManager
from core.src.core_logic.patch_operators.ConfigurePatchingProcessor import ConfigurePatchingProcessor
from core.src.core_logic.patch_operators.PatchAssessor import PatchAssessor
from core.src.core_logic.patch_operators.PatchInstaller import PatchInstaller
from core.src.service_interfaces.lifecycle_managers.LifecycleManager import LifecycleManager


class CoreExecutionEngine(object):
    def __init__(self, env_layer, execution_config, file_logger, composite_logger, telemetry_writer,lifecycle_manager, status_handler, package_manager, configure_patching_processor, patch_assessor, patch_installer):
        # type: (EnvLayer, ExecutionConfig, FileLogger, CompositeLogger, TelemetryWriter, LifecycleManager, StatusHandler, PackageManager, ConfigurePatchingProcessor, PatchAssessor, PatchInstaller) -> None

        # All the entities below are guaranteed to be working at initialization
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.file_logger = file_logger
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.lifecycle_manager = lifecycle_manager
        self.status_handler = status_handler

        # Frequently referred fields
        self.patch_operation_requested = self.execution_config.operation.lower()
        self.package_manager = package_manager
        self.configure_patching_processor = configure_patching_processor
        self.patch_assessor = patch_assessor
        self.patch_installer = patch_installer

    def execute(self):
        # type: () -> None
        """ Execution orchestrator for patch operations (business logic).
         Each operation is expected to be self-contained and no longer raise exceptions -by design- (but failures can be tolerated for investigation)."""

        # Init operation statuses
        self.check_minimum_environment_requirements_and_report(self.patch_operation_requested)

        # Auto-assessment only
        if self.execution_config.exec_auto_assess_only:
            self.patch_assessor.start_operation_with_retries()      # auto-assessment only
            return

        # Configure-patching and Assessment always happen together for both operations - historical note: this is due to a CRP bug whose mitigation is baked into lower layers
        self.configure_patching_processor.start_operation_with_retries()
        self.patch_assessor.start_operation_with_retries()
        self.configure_patching_processor.set_final_operation_status()  # configure patching can only be closed after assessment - required for CRP operation tracking

        # Installation
        if self.patch_operation_requested == Constants.Op.INSTALLATION.lower():
            self.patch_installer.start_operation_with_retries()

            # second assessment after patch installation
            self.patch_assessor.reset_operation_internal_state()
            self.patch_assessor.start_operation_with_retries()

            if not self.patch_assessor.operation_successful:
                self.patch_installer.operation_successful_incl_assessment = False

            self.patch_installer.set_final_operation_status()       # installation is only closed after the final assessment - required for CRP operation tracking

        return

    def try_set_final_status_handler_statuses(self):
        """ Non-throwing call-path for caller safety """
        try:
            self.set_final_status_handler_statuses()
        except Exception:
            pass

    def set_final_status_handler_statuses(self):
        """ """
        debug_log = "[CEE] Writing final status handler statuses. "

        if not self.configure_patching_processor.operation_successful:
            self.composite_logger.log_verbose("[CEE] Persisting final configure patching status.")
            self.status_handler.set_configure_patching_substatus_json(status=Constants.Status.ERROR, automatic_os_patch_state=self.configure_patching_processor.current_auto_os_patch_state, auto_assessment_state=self.configure_patching_processor.current_auto_assessment_state)
            debug_log += "[CP=Error]"

        if not self.patch_assessor.operation_successful:
            if self.patch_operation_requested == Constants.Op.INSTALLATION.lower():
                self.composite_logger.log_verbose("[CEE] Noting installation failed due to an assessment failure.")
                self.status_handler.add_error_to_status(message=Constants.Errors.INSTALLATION_FAILED_DUE_TO_ASSESSMENT_FAILURE, error_code=Constants.PatchOperationErrorCodes.OPERATION_FAILED, current_operation_override_for_error=Constants.Op.INSTALLATION)
                debug_log += "[IP_AF=StatusAdd]"
            if self.patch_operation_requested != Constants.Op.CONFIGURE_PATCHING.lower():
                self.composite_logger.log_verbose("[CEE] Persisting final assess patches status.")
                self.status_handler.set_assessment_substatus_json(status=Constants.Status.ERROR)
                debug_log += "[AP=Error]"

        if self.patch_operation_requested == Constants.Op.INSTALLATION.lower() and not (self.patch_installer.operation_successful and self.patch_assessor.operation_successful):
            self.composite_logger.log_verbose("[CEE] Persisting final install patches status.")
            self.status_handler.set_installation_substatus_json(status=Constants.Status.ERROR)
            debug_log += "[IP=Error]"

        self.composite_logger.log_debug(debug_log + "[#]")

    # region - Pre-operational housekeeping
    def perform_housekeeping_tasks(self):
        # type: () -> None
        """ Performs environment maintenance tasks that need to happen before core business logic execution. """
        if os.path.exists(self.execution_config.temp_folder):
            self.composite_logger.log_debug("[CEE] Deleting all files of certain format from temp folder [FileFormat={0}][TempFolderLocation={1}]".format(Constants.TEMP_FOLDER_CLEANUP_ARTIFACT_LIST, str(self.execution_config.temp_folder)))
            self.env_layer.file_system.delete_files_from_dir(self.execution_config.temp_folder, Constants.TEMP_FOLDER_CLEANUP_ARTIFACT_LIST)
    # endregion - Pre-operational housekeeping

    # region - Minimum environment requirements
    def check_minimum_environment_requirements_and_report(self, patch_operation_requested):
        # type: (Constants.Op) -> None
        """ Checks all minimum environment requirements and reports to status_handler if needed """
        status_py, error_py = self.__check_if_min_python_version_met()
        status_sudo, error_sudo = self.__check_sudo_status()
        status_tel, error_tel = self.__check_telemetry_support_at_agent()

        for patch_operation in [Constants.Op.CONFIGURE_PATCHING, Constants.Op.ASSESSMENT, Constants.Op.INSTALLATION]:
            if patch_operation_requested != Constants.Op.INSTALLATION.lower() and patch_operation == Constants.Op.INSTALLATION:
                continue
            self.status_handler.set_current_operation(patch_operation)
            if not status_py:
                self.status_handler.add_error_to_status(error_py, error_code=Constants.PatchOperationErrorCodes.CL_PYTHON_TOO_OLD)
            if not status_sudo:
                self.status_handler.add_error_to_status(error_sudo, error_code=Constants.PatchOperationErrorCodes.CL_SUDO_CHECK_FAILED)
            if not status_tel:
                self.status_handler.add_error_to_status(error_tel, error_code=Constants.PatchOperationErrorCodes.CL_AGENT_TOO_OLD)
            if status_py & status_sudo & status_tel is not True:
                self.status_handler.set_operation_substatus_json(operation_name=patch_operation, status=Constants.Status.ERROR)

        if status_py & status_sudo & status_tel is not True:
            raise Exception(Constants.Errors.MINIMUM_REQUIREMENTS_NOT_MET.format(str(status_py),str(status_sudo),str(status_tel)))

    @staticmethod
    def __check_if_min_python_version_met():
        # type: () -> (bool, str)
        if sys.version_info < (2, 7):
            error_msg = Constants.Errors.PYTHON_NOT_COMPATIBLE.format(sys.version_info)
            return False, error_msg
        else:
            return True, None

    def __check_sudo_status(self):
        # type: () ->  (bool, str)
        """ Checks if we can invoke sudo successfully.
            Reference output: tools/references/cmd_output_references/sudo_output_expected.txt """
        try:
            self.composite_logger.log_debug("Performing sudo status check... This should complete within 10 seconds.")
            return_code, output = self.env_layer.run_command_output("sudo timeout 10 id && echo True || echo False", False, False)

            output_lines = output.splitlines()
            if len(output_lines) >= 2 and output_lines[1] == "True":
                return True, None
            else:
                error_msg = Constants.Errors.SUDO_FAILURE + " [Output={0}]".format(output)
        except Exception as exception:
            error_msg = Constants.Errors.SUDO_FAILURE + " [Error={0}]".format(str(exception))

        return False, error_msg

    def __check_telemetry_support_at_agent(self):
        # type: () -> (bool, str)
        """ Checks if telemetry is supported by the Azure Linux Agent. Mocks a response if Arc. """
        if self.telemetry_writer.is_telemetry_supported() or self.lifecycle_manager.get_cloud_type() == Constants.CloudType.ARC:
            return True, None
        else:
            return False, Constants.Errors.NO_TELEMETRY_SUPPORT_AT_AGENT
    # endregion - Minimum environment requirements

