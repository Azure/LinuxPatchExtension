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

""" Configure Patching """
from core.src.bootstrap.Constants import Constants
from core_logic.patch_operators.PatchOperator import PatchOperator

# do not instantiate directly - these are exclusively for type hinting support
from core.src.bootstrap.EnvLayer import EnvLayer
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.src.local_loggers.CompositeLogger import CompositeLogger
from core.src.service_interfaces.TelemetryWriter import TelemetryWriter
from core.src.service_interfaces.StatusHandler import StatusHandler
from core.src.package_managers.PackageManager import PackageManager
from core.src.core_logic.ServiceManager import ServiceManager
from core.src.core_logic.TimerManager import TimerManager
from core.src.service_interfaces.lifecycle_managers.LifecycleManager import LifecycleManager


class ConfigurePatchingProcessor(PatchOperator):
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager, auto_assess_service_manager, auto_assess_timer_manager, lifecycle_manager):
        # type: (EnvLayer, ExecutionConfig, CompositeLogger, TelemetryWriter, StatusHandler, PackageManager, ServiceManager, TimerManager, LifecycleManager) -> None
        super(ConfigurePatchingProcessor, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager, lifecycle_manager, operation_name=Constants.Op.CONFIGURE_PATCHING)
        self.current_auto_os_patch_state = Constants.AutomaticOSPatchStates.UNKNOWN
        self.current_auto_assessment_state = Constants.AutoAssessmentStates.UNKNOWN

        # Auto-assessment bits
        self.auto_assess_service_manager = auto_assess_service_manager
        self.auto_assess_timer_manager = auto_assess_timer_manager

    # region - PatchOperator interface implementations
    def should_operation_run(self):
        """ [Interface implementation] Performs evaluation of if the specific operation should be running at all """
        self.lifecycle_manager.lifecycle_status_check()
        return True

    def start_retryable_operation_unit(self):
        """ [Interface implementation] The core retryable actions for patch operation """
        self.operation_successful = True
        self.operation_exception_error = None
        self.__try_set_patch_mode()
        self.__try_set_auto_assessment_mode()

        if self.execution_config.operation.lower() != Constants.Op.CONFIGURE_PATCHING.lower():
            # Mitigation for CRP bug ---- Final status for configure patching CANNOT be written until assessment is complete. Okay to write for other operations.
            self.set_final_operation_status()

    def process_operation_terminal_exception(self, error):
        """ [Interface implementation] Exception handling post all retries for the patch operation """
        self.current_auto_assessment_state = Constants.AutoAssessmentStates.ERROR if self.current_auto_assessment_state not in (Constants.AutoAssessmentStates.ENABLED, Constants.AutoAssessmentStates.DISABLED) else self.current_auto_assessment_state
        self.operation_exception_error = error

        if self.execution_config.operation != Constants.Op.CONFIGURE_PATCHING.lower():
            # Mitigation for CRP bug ---- Final status for configure patching CANNOT be written until assessment is complete. Okay to write for other operations.
            self.set_operation_status(status=Constants.Status.ERROR, error=self.operation_exception_error)
        self.operation_successful &= False

    def set_final_operation_status(self):
        """ [Interface implementation] Business logic to write the final status (implicitly covering external dependencies from external callers) """
        """ Writes the final overall status after any pre-requisite operation is also in a terminal state - currently this is only assessment """
        overall_status = Constants.Status.SUCCESS if self.operation_successful else Constants.Status.ERROR
        self.set_operation_status(status=overall_status, error=self.operation_exception_error)

    def set_operation_status(self, status=Constants.Status.TRANSITIONING, error=None):
        """ [Interface implementation] Generic operation status setter """
        self.operation_status = status
        self.composite_logger.log_debug("[CPP] Reporting consolidated current configure patch status. [OSPatchState={0}][AssessmentState={1}]".format(self.current_auto_os_patch_state, self.current_auto_assessment_state))
        if error is not None:
            self.status_handler.add_error_to_status_and_log_error(message="Error in configure patching operation. [Error={0}] ".format(repr(error)), raise_exception=False)
        self.status_handler.set_configure_patching_substatus_json(status=status, automatic_os_patch_state=self.current_auto_os_patch_state, auto_assessment_state=self.current_auto_assessment_state)
    # endregion - PatchOperator interface implementations

    # region - Retryable operation support
    def __try_set_patch_mode(self):
        """ Set the patch mode for the VM """
        try:
            self.status_handler.set_current_operation(Constants.Op.CONFIGURE_PATCHING)
            self.current_auto_os_patch_state = self.package_manager.patch_mode_manager.get_current_auto_os_patch_state()

            if self.execution_config.patch_mode == Constants.PatchModes.AUTOMATIC_BY_PLATFORM and self.current_auto_os_patch_state != Constants.AutomaticOSPatchStates.DISABLED:
                # disable auto OS updates if VM is configured for platform updates only.
                # NOTE: this condition will be false for Assessment operations, since patchMode is not sent in the API request
                self.package_manager.patch_mode_manager.disable_auto_os_update()
                self.current_auto_os_patch_state = self.package_manager.patch_mode_manager.get_current_auto_os_patch_state()
            elif self.execution_config.patch_mode == Constants.PatchModes.IMAGE_DEFAULT and self.current_auto_os_patch_state == Constants.PatchModes.AUTOMATIC_BY_PLATFORM and self.package_manager.patch_mode_manager.image_default_patch_configuration_backup_exists():
                raise Exception("PatchMode transition to ImageDefault is currently not supported.")     # This was excluded in the original PatchMode implementation, and not caught later in the backlog.

            if self.execution_config.patch_mode == Constants.PatchModes.AUTOMATIC_BY_PLATFORM and self.current_auto_os_patch_state == Constants.AutomaticOSPatchStates.UNKNOWN:
                # NOTE: only sending details in error objects for customer visibility on why patch state is unknown, overall ConfigurePatching status will remain successful
                self.operation_successful &= False
                self.operation_exception_error = "Could not disable one or more automatic OS update services. Please check if they are configured correctly."

            self.composite_logger.log_verbose("[CPP] Completed processing patch mode configuration.")
        except Exception as error:
            self.composite_logger.log_error("Error while processing patch mode configuration. [Error={0}]".format(repr(error)))
            self.operation_exception_error = error
            self.operation_successful &= False

    def __try_set_auto_assessment_mode(self):
        """ Sets the preferred auto-assessment mode for the VM """
        try:
            self.status_handler.set_current_operation(Constants.Op.CONFIGURE_PATCHING_AUTO_ASSESSMENT)
            self.composite_logger.log_debug("[CPP] Systemd information: {0}".format(str(self.auto_assess_service_manager.get_version())))     # proactive support telemetry

            if self.execution_config.assessment_mode is None:
                self.composite_logger.log_warning("[CPP] No assessment mode config was present. Treating as disabled.")
            elif self.execution_config.assessment_mode == Constants.AssessmentModes.AUTOMATIC_BY_PLATFORM:
                self.composite_logger.log_debug("[CPP] Enabling platform-based automatic assessment.")
                if not self.auto_assess_service_manager.systemd_exists():
                    self.status_handler.add_error_to_status_and_log_error(message=Constants.Errors.SYSTEMD_NOT_PRESENT, raise_exception=True, error_code=Constants.PatchOperationErrorCodes.CL_SYSTEMD_NOT_PRESENT)
                self.auto_assess_service_manager.create_and_set_service_idem()
                self.auto_assess_timer_manager.create_and_set_timer_idem()
                self.current_auto_assessment_state = Constants.AutoAssessmentStates.ENABLED
            elif self.execution_config.assessment_mode in Constants.AssessmentModes.IMAGE_DEFAULT:
                self.composite_logger.log_debug("[CPP] Disabling platform-based automatic assessment.")
                self.auto_assess_timer_manager.remove_timer()
                self.auto_assess_service_manager.remove_service()
                self.current_auto_assessment_state = Constants.AutoAssessmentStates.DISABLED
            else:
                raise Exception("Unknown AssessmentMode specified. [AssessmentMode={0}]".format(self.execution_config.assessment_mode))

            self.set_operation_status()
            self.composite_logger.log_verbose("[CPP] Completed processing automatic assessment mode configuration.")
        except Exception as error:
            # deliberately not setting self.operation_exception_error here as it does not feed into the parent object. Not a bug, if you're thinking about it.
            self.composite_logger.log_error("Error while processing automatic assessment mode configuration. [Error={0}]".format(repr(error)))
            self.set_operation_status(status=Constants.Status.TRANSITIONING, error=repr(error))
            self.operation_successful &= False

        # revert operation back to parent
        self.composite_logger.log_verbose("[CPP] Restoring status handler operation to {0}.".format(Constants.Op.CONFIGURE_PATCHING))
        self.status_handler.set_current_operation(Constants.Op.CONFIGURE_PATCHING)
    # endregion - Retryable operation support

