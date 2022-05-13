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

from core.src.bootstrap.Bootstrapper import Bootstrapper
from core.src.bootstrap.Constants import Constants


class CoreMain(object):
    def __init__(self, argv):
        """The main entry point of patch operation execution"""
        # Level 1 bootstrapping - bare minimum components to allow for diagnostics in further bootstrapping
        bootstrapper = Bootstrapper(argv)
        file_logger = bootstrapper.file_logger
        composite_logger = bootstrapper.composite_logger
        stdout_file_mirror = bootstrapper.stdout_file_mirror
        telemetry_writer = bootstrapper.telemetry_writer
        lifecycle_manager = status_handler = None

        # Init operation statuses
        patch_operation_requested = Constants.UNKNOWN
        configure_patching_successful = False
        patch_assessment_successful = False
        overall_patch_installation_operation_successful = False

        try:
            # Level 2 bootstrapping
            composite_logger.log_debug("Building out full container...")
            container = bootstrapper.build_out_container()
            lifecycle_manager, status_handler = bootstrapper.build_core_components(container)
            composite_logger.log_debug("Completed building out full container.\n\n")

            # Current operation in status handler is set to either assessment or installation when these operations begin. Setting it to assessment since that is the first operation that runs always.
            # This ensures all errors occurring before assessment starts are logged within the error objects of assessment substatus
            if status_handler.get_current_operation() is None and not bootstrapper.auto_assessment_only:
                status_handler.set_current_operation(Constants.ASSESSMENT)

            # Environment startup
            bootstrapper.bootstrap_splash_text()
            bootstrapper.basic_environment_health_check()
            lifecycle_manager.execution_start_check()  # terminates if this instance shouldn't be running (redundant)

            # Execution config retrieval
            composite_logger.log_debug("Obtaining execution configuration...")
            execution_config = container.get('execution_config')
            telemetry_writer.set_operation_id(execution_config.activity_id)
            telemetry_writer.set_telemetry_is_supported(execution_config.telemetry_supported)
            patch_operation_requested = execution_config.operation.lower()

            patch_assessor = container.get('patch_assessor')
            package_manager = container.get('package_manager')
            configure_patching_processor = container.get('configure_patching_processor')

            # Configure patching always runs first, except if it's AUTO_ASSESSMENT
            if not execution_config.exec_auto_assess_only:
                configure_patching_successful = configure_patching_processor.start_configure_patching()

            # Assessment happens for an Auto Assessment request or for Non Auto Assessment operations, if the operation requested is not Configure Patching
            if execution_config.exec_auto_assess_only or patch_operation_requested != Constants.CONFIGURE_PATCHING.lower():
                patch_assessment_successful = patch_assessor.start_assessment()

            # Patching + additional assessment occurs if the operation is 'Installation' and not Auto Assessment. Need to check both since operation_requested from prev run is preserved in Auto Assessment
            if not execution_config.exec_auto_assess_only and patch_operation_requested == Constants.INSTALLATION.lower():
                # setting current operation here, to include patch_installer init within installation actions, ensuring any exceptions during patch_installer init are added in installation summary errors object
                status_handler.set_current_operation(Constants.INSTALLATION)
                patch_installer = container.get('patch_installer')
                patch_installation_successful = patch_installer.start_installation()
                patch_assessment_successful = False
                patch_assessment_successful = patch_assessor.start_assessment()

                # PatchInstallationSummary to be marked as completed successfully only after the implicit (i.e. 2nd) assessment is completed, as per CRP's restrictions
                if patch_assessment_successful and patch_installation_successful:
                    patch_installer.mark_installation_completed()
                    overall_patch_installation_operation_successful = True
                self.update_patch_substatus_if_pending(patch_operation_requested, overall_patch_installation_operation_successful, patch_assessment_successful, configure_patching_successful, status_handler, composite_logger)

        except Exception as error:
            # Privileged operation handling for non-production use
            if Constants.EnvLayer.PRIVILEGED_OP_MARKER in repr(error):
                composite_logger.log_debug('\nPrivileged operation request intercepted: ' + repr(error))
                raise

            # General handling
            composite_logger.log_error('\nEXCEPTION during patch operation: ' + repr(error))
            composite_logger.log_error('TO TROUBLESHOOT, please save this file before the next invocation: ' + bootstrapper.log_file_path)

            composite_logger.log_debug("Safely completing required operations after exception...")
            if telemetry_writer is not None:
                telemetry_writer.write_event("EXCEPTION: " + repr(error), Constants.TelemetryEventLevel.Error)
            if status_handler is not None:
                composite_logger.log_debug(' - Status handler pending writes flags [I=' + str(overall_patch_installation_operation_successful) + ', A=' + str(patch_assessment_successful) + ']')

                # Add any pending errors to appropriate substatus
                if Constants.ERROR_ADDED_TO_STATUS not in repr(error):
                    status_handler.add_error_to_status("Terminal exception {0}".format(repr(error)), Constants.PatchOperationErrorCodes.OPERATION_FAILED)
                else:
                    status_handler.add_error_to_status("Execution terminated due to last reported error.", Constants.PatchOperationErrorCodes.OPERATION_FAILED)

                self.update_patch_substatus_if_pending(patch_operation_requested, overall_patch_installation_operation_successful, patch_assessment_successful, configure_patching_successful, status_handler, composite_logger)

            else:
                composite_logger.log_error(' - Status handler is not initialized, and status data cannot be written.')
            composite_logger.log_debug("Completed exception handling.\n")

        finally:
            if lifecycle_manager is not None:
                lifecycle_manager.update_core_sequence(completed=True)

            telemetry_writer.write_event("Completed Linux Patch core operation.", Constants.TelemetryEventLevel.Informational)

            stdout_file_mirror.stop()
            file_logger.close(message_at_close="\n<End of output>")

    @staticmethod
    def update_patch_substatus_if_pending(patch_operation_requested, overall_patch_installation_operation_successful, patch_assessment_successful, configure_patching_successful, status_handler, composite_logger):
        if patch_operation_requested == Constants.INSTALLATION.lower() and not overall_patch_installation_operation_successful:
            status_handler.set_current_operation(Constants.INSTALLATION)
            if not patch_assessment_successful:
                status_handler.add_error_to_status("Installation failed due to assessment failure. Please refer the error details in assessment substatus")
            status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)
            # NOTE: For auto patching requests, no need to report patch metadata to health store in case of failure
            composite_logger.log_debug('  -- Persisted failed installation substatus.')
        if not patch_assessment_successful and patch_operation_requested != Constants.CONFIGURE_PATCHING.lower():
            status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
            composite_logger.log_debug('  -- Persisted failed assessment substatus.')
        if not configure_patching_successful:
            status_handler.set_configure_patching_substatus_json(status=Constants.STATUS_ERROR)
            composite_logger.log_debug('  -- Persisted failed configure patching substatus.')

