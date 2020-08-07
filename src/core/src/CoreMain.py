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

from src.bootstrap.Bootstrapper import Bootstrapper
from src.bootstrap.Constants import Constants


class CoreMain(object):
    def __init__(self, argv):
        """The main entry point of patch operation execution"""
        # Level 1 bootstrapping - bare minimum components to allow for diagnostics in further bootstrapping
        bootstrapper = Bootstrapper(argv)
        file_logger = bootstrapper.file_logger
        composite_logger = bootstrapper.composite_logger
        stdout_file_mirror = bootstrapper.stdout_file_mirror
        lifecycle_manager = telemetry_writer = status_handler = None

        # Init operation statuses
        patch_operation_requested = Constants.UNKNOWN
        patch_assessment_successful = False
        patch_installation_successful = False

        try:
            # Level 2 bootstrapping
            composite_logger.log_debug("Building out full container...")
            container = bootstrapper.build_out_container()
            lifecycle_manager, telemetry_writer, status_handler = bootstrapper.build_core_components(container)
            composite_logger.log_debug("Completed building out full container.\n\n")

            # Basic environment check
            bootstrapper.bootstrap_splash_text()
            bootstrapper.basic_environment_health_check()
            lifecycle_manager.execution_start_check()      # terminates if this instance shouldn't be running (redundant)

            # Execution config retrieval
            composite_logger.log_debug("Obtaining execution configuration...")
            execution_config = container.get('execution_config')
            patch_operation_requested = execution_config.operation.lower()
            patch_assessor = container.get('patch_assessor')
            patch_installer = container.get('patch_installer')

            # Update patch metadata summary in status for auto patching installation requests, to be reported to health store
            if execution_config.patch_rollout_id is not None and patch_operation_requested == Constants.INSTALLATION.lower():
                status_handler.set_patch_metadata_for_health_store_substatus_json(report_to_health_store=True, wait_after_update=True)
                # updating metadata summary again with reporting to health store turned off
                status_handler.set_patch_metadata_for_health_store_substatus_json(report_to_health_store=False, wait_after_update=False)

            # Assessment happens no matter what
            patch_assessment_successful = patch_assessor.start_assessment()

            # Patching + additional assessment occurs if the operation is 'Installation'
            if patch_operation_requested == Constants.INSTALLATION.lower():
                patch_installation_successful = patch_installer.start_installation()
                patch_assessment_successful = patch_assessor.start_assessment()

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
                telemetry_writer.send_error_info("EXCEPTION: " + repr(error))
            if status_handler is not None:
                composite_logger.log_debug(' - Status handler pending writes flags [I=' + str(patch_installation_successful) + ', A=' + str(patch_assessment_successful) + ']')
                if patch_operation_requested == Constants.INSTALLATION.lower() and not patch_installation_successful:
                    status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)
                    composite_logger.log_debug('  -- Persisted failed installation substatus.')
                if not patch_assessment_successful:
                    status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
                    composite_logger.log_debug('  -- Persisted failed assessment substatus.')

                if Constants.ERROR_ADDED_TO_STATUS not in repr(error):
                    status_handler.add_error_to_status("Terminal exception {0}".format(repr(error)), Constants.PatchOperationErrorCodes.OPERATION_FAILED)
                else:
                    status_handler.add_error_to_status("Execution terminated due to last reported error.", Constants.PatchOperationErrorCodes.OPERATION_FAILED)

            else:
                composite_logger.log_error(' - Status handler is not initialized, and status data cannot be written.')
            composite_logger.log_debug("Completed exception handling.\n")

        finally:
            if lifecycle_manager is not None:
                lifecycle_manager.update_core_sequence(completed=True)

            telemetry_writer.send_runbook_state_info("Succeeded.")
            telemetry_writer.close_transports()

            stdout_file_mirror.stop()
            file_logger.close(message_at_close="<End of output>")
