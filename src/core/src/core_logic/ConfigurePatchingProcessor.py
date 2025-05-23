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

""" Configure Patching """
from core.src.bootstrap.Constants import Constants


class ConfigurePatchingProcessor(object):
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager, auto_assess_service_manager, auto_assess_timer_manager, lifecycle_manager):
        self.env_layer = env_layer
        self.execution_config = execution_config

        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.status_handler = status_handler

        self.package_manager = package_manager
        self.auto_assess_service_manager = auto_assess_service_manager
        self.auto_assess_timer_manager = auto_assess_timer_manager
        self.lifecycle_manager = lifecycle_manager

        self.current_auto_os_patch_state = Constants.AutomaticOSPatchStates.UNKNOWN
        self.current_auto_assessment_state = Constants.AutoAssessmentStates.UNKNOWN
        self.configure_patching_successful = True
        self.configure_patching_exception_error = None

    def start_configure_patching(self):
        """ Start configure patching """
        try:
            self.composite_logger.log("\nStarting configure patching... [MachineId: " + self.env_layer.platform.vm_name() + "][ActivityId: " + self.execution_config.activity_id + "][StartTime: " + self.execution_config.start_time + "]")
            self.status_handler.set_current_operation(Constants.CONFIGURE_PATCHING)
            self.__raise_if_telemetry_unsupported()

            self.__report_consolidated_configure_patch_status(status=Constants.STATUS_TRANSITIONING)
            self.__try_set_patch_mode()
            self.__try_set_auto_assessment_mode()

            # If the tracked operation is Configure patching, we cannot write a final status until assessment has also written a final status (mitigation for a CRP bug)
            if self.execution_config.operation.lower() != Constants.CONFIGURE_PATCHING.lower():
                self.set_configure_patching_final_overall_status()
        except Exception as error:
            self.current_auto_assessment_state = Constants.AutoAssessmentStates.ERROR
            self.configure_patching_exception_error = error
            # If the tracked operation is Configure patching, we cannot write a final status until assessment has also written a final status (mitigation for a CRP bug)
            if self.execution_config.operation != Constants.CONFIGURE_PATCHING.lower():
                self.__report_consolidated_configure_patch_status(status=Constants.STATUS_ERROR, error=self.configure_patching_exception_error)
            self.configure_patching_successful &= False

        self.composite_logger.log("\nConfigure patching completed.\n")
        return self.configure_patching_successful

    def set_configure_patching_final_overall_status(self):
        """ Writes the final overall status after any pre-requisite operation is also in a terminal state - currently this is only assessment """
        overall_status = Constants.STATUS_SUCCESS if self.configure_patching_successful else Constants.STATUS_ERROR
        if self.configure_patching_exception_error is None:
            self.__report_consolidated_configure_patch_status(status=overall_status)
        else:
            self.__report_consolidated_configure_patch_status(status=overall_status, error=self.configure_patching_exception_error)

    def __try_set_patch_mode(self):
        """ Set the patch mode for the VM """
        try:
            self.status_handler.set_current_operation(Constants.CONFIGURE_PATCHING)
            self.current_auto_os_patch_state = self.package_manager.get_current_auto_os_patch_state()

            # disable auto OS updates if VM is configured for platform updates only.
            # NOTE: this condition will be false for Assessment operations, since patchMode is not sent in the API request
            if self.current_auto_os_patch_state != Constants.AutomaticOSPatchStates.DISABLED and self.execution_config.patch_mode == Constants.PatchModes.AUTOMATIC_BY_PLATFORM:
                self.package_manager.disable_auto_os_update()
            elif self.current_auto_os_patch_state == Constants.AutomaticOSPatchStates.DISABLED and self.execution_config.patch_mode == Constants.PatchModes.IMAGE_DEFAULT:
                self.package_manager.revert_auto_os_update_to_system_default()

            self.current_auto_os_patch_state = self.package_manager.get_current_auto_os_patch_state()

            if self.execution_config.patch_mode == Constants.PatchModes.AUTOMATIC_BY_PLATFORM and self.current_auto_os_patch_state == Constants.AutomaticOSPatchStates.UNKNOWN:
                # NOTE: only sending details in error objects for customer visibility on why patch state is unknown, overall configurepatching status will remain successful
                self.configure_patching_exception_error = "Could not disable one or more automatic OS update services. Please check if they are configured correctly"

            self.composite_logger.log_debug("Completed processing patch mode configuration.")
        except Exception as error:
            self.composite_logger.log_error("Error while processing patch mode configuration. [Error={0}]".format(repr(error)))
            self.configure_patching_exception_error = error
            self.configure_patching_successful &= False

    def __try_set_auto_assessment_mode(self):
        """ Sets the preferred auto-assessment mode for the VM """
        try:
            self.status_handler.set_current_operation(Constants.CONFIGURE_PATCHING_AUTO_ASSESSMENT)
            self.composite_logger.log_debug("Systemd information: {0}".format(str(self.auto_assess_service_manager.get_version())))     # proactive support telemetry

            if self.execution_config.assessment_mode is None:
                self.composite_logger.log_debug("No assessment mode config was present. No configuration changes will occur.")
            elif self.execution_config.assessment_mode == Constants.AssessmentModes.AUTOMATIC_BY_PLATFORM:
                self.composite_logger.log_debug("Enabling platform-based automatic assessment.")
                if not self.auto_assess_service_manager.systemd_exists():
                    raise Exception("Systemd is not available on this system, and platform-based auto-assessment cannot be configured.")
                self.auto_assess_service_manager.create_and_set_service_idem()
                self.auto_assess_timer_manager.create_and_set_timer_idem()
                self.current_auto_assessment_state = Constants.AutoAssessmentStates.ENABLED
            elif self.execution_config.assessment_mode == Constants.AssessmentModes.IMAGE_DEFAULT:
                self.composite_logger.log_debug("Disabling platform-based automatic assessment.")
                self.auto_assess_timer_manager.remove_timer()
                self.auto_assess_service_manager.remove_service()
                self.current_auto_assessment_state = Constants.AutoAssessmentStates.DISABLED
            else:
                raise Exception("Unknown assessment mode specified. [AssessmentMode={0}]".format(self.execution_config.assessment_mode))

            self.__report_consolidated_configure_patch_status()
            self.composite_logger.log_debug("Completed processing automatic assessment mode configuration.")
        except Exception as error:
            # deliberately not setting self.configure_patching_exception_error here as it does not feed into the parent object. Not a bug, if you're thinking about it.
            self.composite_logger.log_error("Error while processing automatic assessment mode configuration. [Error={0}]".format(repr(error)))
            self.__report_consolidated_configure_patch_status(status=Constants.STATUS_TRANSITIONING, error=error)
            self.configure_patching_successful &= False

        # revert operation back to parent
        self.composite_logger.log_debug("Restoring status handler operation to {0}.".format(Constants.CONFIGURE_PATCHING))
        self.status_handler.set_current_operation(Constants.CONFIGURE_PATCHING)

    def __report_consolidated_configure_patch_status(self, status=Constants.STATUS_TRANSITIONING, error=Constants.DEFAULT_UNSPECIFIED_VALUE):
        """ Reports """
        self.composite_logger.log_debug("Reporting consolidated current configure patch status. [OSPatchState={0}][AssessmentState={1}]".format(self.current_auto_os_patch_state, self.current_auto_assessment_state))

        # report error if specified
        if error != Constants.DEFAULT_UNSPECIFIED_VALUE:
            error_msg = 'Error: ' + repr(error)
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR, current_operation_override_for_error=Constants.CONFIGURE_PATCHING_AUTO_ASSESSMENT)

        # write consolidated status
        self.status_handler.set_configure_patching_substatus_json(status=status,
                                                                  automatic_os_patch_state=self.current_auto_os_patch_state,
                                                                  auto_assessment_state=self.current_auto_assessment_state)

    def __raise_if_telemetry_unsupported(self):
        if self.lifecycle_manager.get_vm_cloud_type() == Constants.VMCloudType.ARC and self.execution_config.operation not in [Constants.ASSESSMENT, Constants.INSTALLATION]:
            self.composite_logger.log("Skipping telemetry compatibility check for Arc cloud type when operation is not manual")
            return
        if not self.telemetry_writer.is_telemetry_supported():
            error_msg = "{0}".format(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG)
            raise Exception(error_msg)

        self.composite_logger.log("{0}".format(Constants.TELEMETRY_COMPATIBLE_MSG))
