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

import json
import os
import shutil
import time
from core.src.bootstrap.Constants import Constants
from core.src.service_interfaces.LifecycleManager import LifecycleManager


class LifecycleManagerAzure(LifecycleManager):
    """Class for managing the core code's lifecycle within the extension wrapper"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(LifecycleManagerAzure, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)

        # Handshake file paths
        self.ext_state_file_path = os.path.join(self.execution_config.config_folder, Constants.EXT_STATE_FILE)
        self.core_state_file_path = os.path.join(self.execution_config.config_folder, Constants.CORE_STATE_FILE)
        # Writing to log
        self.composite_logger.log_debug("Initializing LifecycleManagerAzure")

    # region - State checkers
    def execution_start_check(self):
        self.composite_logger.log_debug("\nExecution start check initiating...")

        if self.execution_config.exec_auto_assess_only:
            timer_start_time = self.env_layer.datetime.datetime_utcnow()
            while True:
                extension_sequence = self.read_extension_sequence()
                core_sequence = self.read_core_sequence()

                # Timer evaluation
                current_time = self.env_layer.datetime.datetime_utcnow()
                elapsed_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(current_time - timer_start_time)

                # Check for sequence number mismatches
                if int(self.execution_config.sequence_number) != int(core_sequence['number']):
                    if int(self.execution_config.sequence_number) < int(extension_sequence['number']) or int(self.execution_config.sequence_number) < int(core_sequence['number']):
                        self.composite_logger.log_warning("Auto-assessment NOT STARTED as newer sequence number detected. [Attempted={0}][DetectedExt={1}][DetectedCore={2}]".format(str(self.execution_config.sequence_number), str(extension_sequence['number']), str(core_sequence['number'])))
                    elif int(self.execution_config.sequence_number) > int(extension_sequence['number']) or int(self.execution_config.sequence_number) > int(core_sequence['number']):
                        self.composite_logger.log_error("Auto-assessment NOT STARTED as an extension state anomaly was detected. [Attempted={0}][DetectedExt={1}][DetectedCore={2}]".format(str(self.execution_config.sequence_number), str(extension_sequence['number']), str(core_sequence['number'])))
                    self.composite_logger.file_logger.close()
                    self.env_layer.exit(0)

                # DEFINITELY SAFE TO START. Correct sequence number marked as completed
                if core_sequence['completed'].lower() == 'true':
                    self.composite_logger.log("Auto-assessment is SAFE to start. Existing sequence number marked as COMPLETED.\n")
                    self.read_only_mode = False
                    break

                # Check for active running processes if not completed
                if len(self.identify_running_processes(core_sequence['processIds'])) != 0:
                    if os.getpid() in core_sequence['processIds']:
                        self.composite_logger.log("Auto-assessment is SAFE to start. Core sequence ownership is already established.\n")
                        self.read_only_mode = False
                        break

                    # DEFINITELY _NOT_ SAFE TO START. Possible reasons: full core operation is in progress (okay), some previous auto-assessment is still running (bad scheduling, adhoc run, or process stalled)
                    if elapsed_time_in_minutes > Constants.MAX_AUTO_ASSESSMENT_WAIT_FOR_MAIN_CORE_EXEC_IN_MINUTES:    # will wait up to the max allowed
                        self.composite_logger.log_warning("Auto-assessment is NOT safe to start yet.TIMED-OUT waiting to Core to complete. EXITING. [LastHeartbeat={0}][Operation={1}]".format(str(core_sequence['lastHeartbeat']), str(core_sequence['action'])))
                        self.composite_logger.file_logger.close()
                        self.env_layer.exit(0)
                    else:
                        self.composite_logger.file_logger.flush()
                        self.composite_logger.log_warning("Auto-assessment is NOT safe to start yet. Waiting to retry (up to set timeout). [LastHeartbeat={0}][Operation={1}][ElapsedTimeInMinutes={2}][TotalWaitRequiredInMinutes={3}]".format(str(core_sequence['lastHeartbeat']), str(core_sequence['action']), str(elapsed_time_in_minutes), str(Constants.REBOOT_BUFFER_IN_MINUTES)))
                        self.composite_logger.file_logger.flush()
                        time.sleep(30)
                        continue

                # MAYBE SAFE TO START. Safely timeout if wait for any core restart events (from a potential reboot) has exceeded the maximum reboot buffer
                if elapsed_time_in_minutes > Constants.REBOOT_BUFFER_IN_MINUTES:
                    self.composite_logger.log_debug("Auto-assessment is now considered SAFE to start as Core timed-out in reporting completion mark. [LastHeartbeat={0}][Operation={1}]".format(str(core_sequence['lastHeartbeat']), str(core_sequence['action'])))
                    self.read_only_mode = False
                    break

                # Briefly pause execution to re-check all states (including reboot buffer) again
                self.composite_logger.file_logger.flush()
                self.composite_logger.log_debug("Auto-assessment is waiting for Core state completion mark (up to set timeout). [LastHeartbeat={0}][Operation={1}][ElapsedTimeInMinutes={2}][TotalWaitRequiredInMinutes={3}]".format(str(core_sequence['lastHeartbeat']), str(core_sequence['action']), str(elapsed_time_in_minutes), str(Constants.REBOOT_BUFFER_IN_MINUTES)))
                self.composite_logger.file_logger.flush()
                time.sleep(30)

            # Signalling take-over of core state by auto-assessment after safety checks for any competing process
            self.update_core_sequence(completed=False)
            # Refresh status file in memory to be up-to-date
            self.status_handler.load_status_file_components()
        else:
            # Logic for all non-Auto-assessment operations
            extension_sequence = self.read_extension_sequence()
            core_sequence = self.read_core_sequence()

            if int(extension_sequence['number']) == int(self.execution_config.sequence_number):
                if core_sequence['completed'] is True:
                    # Block attempts to execute what last completed (fully) again
                    self.composite_logger.log_warning("LifecycleManager recorded false enable for completed sequence {0}.".format(str(extension_sequence['number'])))
                    self.composite_logger.file_logger.close()
                    self.env_layer.exit(0)
                else:
                    # Incomplete current execution
                    self.composite_logger.log_debug("Restarting execution for incomplete sequence number: {0}.".format(str(self.execution_config.sequence_number)))
            elif int(extension_sequence['number']) < int(self.execution_config.sequence_number):
                # Allow this but log a warning
                self.composite_logger.log_warning("Unexpected lower sequence number: {0} < {1}.".format(str(self.execution_config.sequence_number), str(extension_sequence['number'])))
            else:
                # New sequence number
                self.composite_logger.log_debug("New sequence number accepted for execution: {0} > {1}.".format(str(self.execution_config.sequence_number), str(extension_sequence['number'])))

        self.composite_logger.log_debug("Completed execution start check.")     

    def lifecycle_status_check(self):
        self.composite_logger.log_verbose("Performing lifecycle status check...")
        extension_sequence = self.read_extension_sequence()
        if int(extension_sequence['number']) == int(self.execution_config.sequence_number):
            self.composite_logger.log_verbose("Extension sequence number verified to have not changed: {0}".format(str(extension_sequence['number'])))
            self.update_core_sequence(completed=False)
        else:
            self.composite_logger.log_error("Extension goal state has changed. Terminating current sequence: {0}".format(self.execution_config.sequence_number))
            self.status_handler.report_sequence_number_changed_termination()        # fail everything in a sequence number change
            self.update_core_sequence(completed=True)       # forced-to-complete scenario | extension wrapper will be watching for this event
            self.composite_logger.file_logger.close()
            self.env_layer.exit(0)
        self.composite_logger.log_verbose("Completed lifecycle status check.")

    # End region State checkers      
    # region - Identity
    def get_vm_cloud_type(self):
        return Constants.VMCloudType.AZURE
    # endregion

