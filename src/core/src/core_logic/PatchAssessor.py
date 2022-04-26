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

""" A patch assessment """
import time
from core.src.bootstrap.Constants import Constants
import os

class PatchAssessor(object):
    """ Wrapper class of a single patch assessment """
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager, lifecycle_manager):
        self.env_layer = env_layer
        self.execution_config = execution_config

        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.status_handler = status_handler
        self.lifecycle_manager = lifecycle_manager
        self.package_manager = package_manager

        self.assessment_state_file_path = os.path.join(self.execution_config.config_folder, Constants.ASSESSMENT_STATE_FILE)

    def start_assessment(self):
        """ Start a patch assessment """
        self.status_handler.set_current_operation(Constants.ASSESSMENT)
        self.raise_if_agent_incompatible()

        self.composite_logger.log('\nStarting patch assessment...')

        self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_TRANSITIONING)
        self.composite_logger.log("\nMachine Id: " + self.env_layer.platform.node())
        self.composite_logger.log("Activity Id: " + self.execution_config.activity_id)
        self.composite_logger.log("Operation request time: " + self.execution_config.start_time)

        self.composite_logger.log("\n\nGetting available patches...")
        self.package_manager.refresh_repo()
        self.status_handler.reset_assessment_data()

        for i in range(0, Constants.MAX_ASSESSMENT_RETRY_COUNT):
            try:
                if self.lifecycle_manager is not None:
                    self.lifecycle_manager.lifecycle_status_check()     # may terminate the code abruptly, as designed
                packages, package_versions = self.package_manager.get_all_updates()
                self.telemetry_writer.write_event("Full assessment: " + str(packages), Constants.TelemetryEventLevel.Verbose)
                self.status_handler.set_package_assessment_status(packages, package_versions)
                if self.lifecycle_manager is not None:
                    self.lifecycle_manager.lifecycle_status_check()     # may terminate the code abruptly, as designed
                sec_packages, sec_package_versions = self.package_manager.get_security_updates()
                self.telemetry_writer.write_event("Security assessment: " + str(sec_packages), Constants.TelemetryEventLevel.Verbose)
                self.status_handler.set_package_assessment_status(sec_packages, sec_package_versions, "Security")
                self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)
                break
            except Exception as error:
                if i < Constants.MAX_ASSESSMENT_RETRY_COUNT - 1:
                    error_msg = 'Retryable error retrieving available patches: ' + repr(error)
                    self.composite_logger.log_warning(error_msg)
                    self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                    time.sleep(2*(i + 1))
                else:
                    error_msg = 'Error retrieving available patches: ' + repr(error)
                    self.composite_logger.log_error(error_msg)
                    self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                    if Constants.ERROR_ADDED_TO_STATUS not in repr(error):
                        error.args = (error.args, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
                    self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
                    raise

        self.composite_logger.log("\nPatch assessment completed.\n")
        return True

    def raise_if_agent_incompatible(self):
        if self.lifecycle_manager.get_vm_cloud_type() == Constants.VMCloudType.ARC and self.execution_config.operation not in [Constants.ASSESSMENT, Constants.INSTALLATION]:
            self.composite_logger.log("Skipping agent compatibility check for Arc cloud type when operation is not manual")
            return
        if not self.telemetry_writer.is_agent_compatible():
            error_msg = "{0} [{1}]".format(Constants.TELEMETRY_AT_AGENT_NOT_COMPATIBLE_ERROR_MSG, self.telemetry_writer.get_telemetry_diagnostics())
            self.composite_logger.log_error(error_msg)
            self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
            raise Exception(error_msg)

        self.composite_logger.log("{0} [{1}]".format(Constants.TELEMETRY_AT_AGENT_COMPATIBLE_MSG, self.telemetry_writer.get_telemetry_diagnostics()))

    # region - Auto-assessment extensions
    def read_core_sequence(self):
        """ Reads the core sequence file, but additionally establishes if this class is allowed to write to it when the freshest data is evaluated. """
        self.composite_logger.log_debug("Reading core sequence...")
        if not os.path.exists(self.assessment_state_file_path) or not os.path.isfile(self.assessment_state_file_path):
            # Neutralizes directories
            if os.path.isdir(self.assessment_state_file_path):
                self.composite_logger.log_error("Core state file path returned a directory. Attempting to reset.")
                shutil.rmtree(self.assessment_state_file_path)
            # Writes a vanilla core sequence file
            self.read_only_mode = False
            self.update_core_sequence()

        # Read (with retries for only IO Errors)
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.assessment_state_file_path, mode="r") as file_handle:
                    core_sequence = json.load(file_handle)['coreSequence']

                # The following code will only execute in the event of a bug
                if not self.read_only_mode and os.getpid() not in core_sequence['processIds']:
                    self.composite_logger.log_error("SERIOUS ERROR -- Core sequence was taken over in violation of sequence contract.")
                    self.read_only_mode = True  # This should never happen, but we're switching back into read-only mode.
                    if self.execution_config.exec_auto_assess_only:  # Yield execution precedence out of caution, if it's low pri auto-assessment
                        return core_sequence

                if self.read_only_mode:
                    if core_sequence['completed'].lower() == 'true' or len(self.identify_running_processes(core_sequence['processIds'])) == 0:
                        # Short-circuit for re-enable for completed non-auto-assess operations that should not run
                        if not self.execution_config.exec_auto_assess_only and core_sequence['number'] == self.execution_config.sequence_number and core_sequence['completed'].lower() == 'true':
                            self.composite_logger.log_debug("Not attempting to take ownership of core sequence since the sequence number as it's already done and this is the main process.")
                            return core_sequence

                        # Auto-assess over non-auto-assess is not a trivial override and is short-circuited to be evaluated in detail later
                        if self.execution_config.exec_auto_assess_only and not core_sequence["autoAssessment"].lower() == 'true':
                            self.composite_logger.log_debug("Auto-assessment cannot supersede the main core process trivially.")
                            return core_sequence

                        self.composite_logger.log_debug("Attempting to take ownership of core sequence.")
                        self.read_only_mode = False
                        self.update_core_sequence()
                        self.read_only_mode = True

                        # help re-evaluate if assertion succeeded
                        with self.env_layer.file_system.open(self.assessment_state_file_path, mode="r") as file_handle:
                            core_sequence = json.load(file_handle)['coreSequence']

                    if os.getpid() in core_sequence['processIds']:
                        self.composite_logger.log_debug("Successfully took ownership of core sequence.")
                        self.read_only_mode = False

                return core_sequence
            except Exception as error:
                if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                    self.composite_logger.log_warning("Exception on core sequence read. [Exception={0}] [RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to read core state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise

    def update_core_sequence(self, completed=False):
        if self.read_only_mode:
            self.composite_logger.log_debug("Core sequence will not be updated to avoid contention... [DesiredCompletedValue={0}]".format(str(completed)))
            return

        self.composite_logger.log_debug("Updating core sequence... [Completed={0}]".format(str(completed)))
        core_sequence = {'number': self.execution_config.sequence_number,
                         'action': self.execution_config.operation,
                         'completed': str(completed),
                         'lastHeartbeat': str(self.env_layer.datetime.timestamp()),
                         'processIds': [os.getpid()] if not completed else [],
                         'autoAssessment': str(self.execution_config.exec_auto_assess_only)}
        core_state_payload = json.dumps({"coreSequence": core_sequence})

        if os.path.isdir(self.assessment_state_file_path):
            self.composite_logger.log_error("Core state file path returned a directory. Attempting to reset.")
            shutil.rmtree(self.assessment_state_file_path)

        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.assessment_state_file_path, 'w+') as file_handle:
                    file_handle.write(core_state_payload)
            except Exception as error:
                if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                    self.composite_logger.log_warning("Exception on core sequence update. [Exception={0}] [RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to write to core state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise

        self.composite_logger.log_debug("Completed updating core sequence.")

