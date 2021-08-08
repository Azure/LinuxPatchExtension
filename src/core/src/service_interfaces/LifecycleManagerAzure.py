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

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer):
        super(LifecycleManagerAzure,self).__init__(env_layer,execution_config,composite_logger,telemetry_writer)

        # Handshake file paths
        self.ext_state_file_path = os.path.join(self.execution_config.config_folder, Constants.EXT_STATE_FILE)
        self.core_state_file_path = os.path.join(self.execution_config.config_folder, Constants.CORE_STATE_FILE)

    # region - State checkers
    def execution_start_check(self):
        self.composite_logger.log_debug("Execution start check initiating...")
        extension_sequence = self.read_extension_sequence()
        core_sequence = self.read_core_sequence()

        if self.execution_config.operation == Constants.AUTO_ASSESSMENT:
            # newer sequence number has been observed, do not run
            if int(self.execution_config.sequence_number) < int(extension_sequence['number']) \
                    or int(self.execution_config.sequence_number) < int(core_sequence['number']):
                self.composite_logger.log_warning("Auto-assessment not started as newer sequence number detected. [Attempted={0}][DetectedExt={1}][DetectedCore={2}]".format(str(self.execution_config.sequence_number), str(extension_sequence['number']), str(core_sequence['number'])))
                                                                                                                                                                                                         
                self.env_layer.exit(0)

            # anomalous extension state encountered, do not run - this needs to be investigated if ever encountered
            if int(self.execution_config.sequence_number) > int(extension_sequence['number']) \
                    or int(self.execution_config.sequence_number) > int(core_sequence['number']):
                self.composite_logger.log_error("Auto-assessment not started as an extension state anomaly was detected. [Attempted={0}][DetectedExt={1}][DetectedCore={2}]".format(str(self.execution_config.sequence_number), str(extension_sequence['number']),str(core_sequence['number'])))
                self.env_layer.exit(0)

            # attempted sequence number is same as recorded core sequence - expected
            if int(self.execution_config.sequence_number) == int(core_sequence['number']):
                if bool(core_sequence['completed']):
                    self.composite_logger.log_debug("Auto-assessment is safe to start. Existing sequence number marked as completed.")
                    self.update_core_sequence(completed=False)  # signalling core restart with auto-assessment as its safe to do so
                else:
                    self.composite_logger.log_debug("Auto-assessment may not be safe to start yet as core sequence is not marked completed.")
                    if len(self.identify_running_processes(core_sequence['process_ids'])) != 0:
                        # NOT SAFE TO START
                        # Possible reasons: full core operation is in progress (okay), some previous auto-assessment is still running (bad scheduling, adhoc run, or process stalled)
                        self.composite_logger.log_warning("Auto-assessment is NOT safe to start yet. Existing core process(es) running. Exiting. [LastHeartbeat={0}][Operation={1}]".format(str(core_sequence['lastHeartbeat']), str(core_sequence['action'])))
                        self.env_layer.exit(0)
                    else:
                        # MAY BE SAFE TO START
                        self.composite_logger.log_warning("Auto-assessment is LIKELY safe to start, BUT core sequence anomalies were detected. Evaluating further. [LastHeartbeat={0}][Operation={1}]".format(str(core_sequence['lastHeartbeat']), str(core_sequence['action'])))

                        # wait to see if Core comes back from a restart
                        timer_start_time = self.env_layer.datetime.datetime_utcnow()
                        while True:
                            core_sequence = self.read_core_sequence()

                            # Main Core process suddenly started running (expected after reboot) - don't run
                            if len(self.identify_running_processes(core_sequence['process_ids'])) != 0:
                                self.composite_logger.log_warning("Auto-assessment is NOT safe to start as core process(es) started running. Exiting. [LastHeartbeat={0}][Operation={1}]".format(str(core_sequence['lastHeartbeat']), str(core_sequence['action'])))
                                self.env_layer.exit(0)

                            # If timed out without the main Core process starting, assume it's safe to proceed
                            current_time = self.env_layer.datetime.datetime_utcnow()
                            elapsed_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(current_time - timer_start_time)
                            if elapsed_time_in_minutes > Constants.REBOOT_BUFFER_IN_MINUTES:
                                self.composite_logger.log_debug("Auto-assessment is now considered safe to start since Core did not start after a reboot buffer wait period. [LastHeartbeat={0}][Operation={1}]".format(str(core_sequence['lastHeartbeat']), str(core_sequence['action'])))
                                break

                        self.update_core_sequence(completed=False)  # signalling core restart with auto-assessment as its safe to do so
        else:
            # Logic for all non-Auto-assessment operations
            if int(extension_sequence['number']) == int(self.execution_config.sequence_number):
                if core_sequence['completed'] is True:
                    # Block attempts to execute what last completed (fully) again
                    self.composite_logger.log_warning("LifecycleManager recorded false enable for completed sequence {0}.".format(str(extension_sequence['number'])))
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