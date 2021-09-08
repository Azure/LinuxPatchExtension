# Copyright 2021 Microsoft Corporation
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

class LifecycleManagerArc(LifecycleManager):
    """Class for managing the core code's lifecycle within the extension wrapper"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer):
        super(LifecycleManagerArc,self).__init__(env_layer,execution_config,composite_logger,telemetry_writer)

        # Handshake file paths
        self.ext_state_file_path = os.path.join(self.execution_config.config_folder, Constants.EXT_STATE_FILE)
        self.core_state_file_path = os.path.join(self.execution_config.config_folder, Constants.CORE_STATE_FILE)
        # Writing to log
        self.composite_logger.log_debug("Initializing LifecycleManagerArc")
        # Variables
        self.arc_root = "/var/lib/waagent/"
        self.arc_core_state_file_name = "CoreState.json"
        self.arc_extension_folder_pattern = "Microsoft.SoftwareUpdateManagement.LinuxOsUpdateExtension-*"
        self.config_folder_path = "/config/"

    # region - State checkers
    def execution_start_check(self):
        self.composite_logger.log_debug("Execution start check initiating...")
        extension_sequence = self.read_extension_sequence()
        core_sequence = self.read_core_sequence()
        arc_core_sequence = self.read_arc_core_sequence()

        if arc_core_sequence['completed'] == "False":
            self.composite_logger.log_warning("Arc extension with sequence number {0} is currently running. Exiting autoassessment".format(str(arc_core_sequence['number'])))
            self.update_core_sequence(completed=True)   # forced-to-complete scenario | extension wrapper will be watching for this event
            self.env_layer.exit(0)

        if self.execution_config.exec_auto_assess_only:
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
                if core_sequence['completed'].lower() == 'true':
                    self.composite_logger.log_debug("Auto-assessment is safe to start. Existing sequence number marked as completed.")
                    self.update_core_sequence(completed=False)  # signalling core restart with auto-assessment as its safe to do so
                else:
                    self.composite_logger.log_debug("Auto-assessment may not be safe to start yet as core sequence is not marked completed.")
                    if len(self.identify_running_processes(core_sequence['processIds'])) != 0:
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
                            if len(self.identify_running_processes(core_sequence['processIds'])) != 0:
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

    def get_arc_core_state_file(self):
        """ Retrieve Arc folder path (including version ) """
        cmd = "ls " + self.arc_root + " | grep " + self.arc_extension_folder_pattern
        code, out = self.env_layer.run_command_output(cmd, False, False)
        if out == "" or "not recognized as an internal or external command" in out:
            self.composite_logger.log_warning("Could not find location of ARC core status file")
            return ""
        lines = out.split("\n")
        dir_name = lines[0].lstrip()
        core_state_file_path = self.arc_root + dir_name + self.config_folder_path + self.arc_core_state_file_name
        return core_state_file_path

    def read_arc_core_sequence(self):
        self.composite_logger.log_debug("Reading arc extension core sequence...")
        core_state_file_path = self.get_arc_core_state_file()
        if not os.path.exists(core_state_file_path) or not os.path.isfile(core_state_file_path):
            ''' Dummy core sequence in case of arc core state is not found '''
            completed = True
            core_sequence = {'number': 0,
                             'action': self.execution_config.operation,
                             'completed': str(completed),
                             'lastHeartbeat': str(self.env_layer.datetime.timestamp()),
                             'processIds': []}
            return core_sequence
        
        # Read (with retries for only IO Errors) - TODO: Refactor common code
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(core_state_file_path, mode="r") as file_handle:
                    core_sequence = json.load(file_handle)['coreSequence']
                    return core_sequence
            except Exception as error:
                if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                    self.composite_logger.log_warning("Exception on arc core sequence read. [Exception={0}] [RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to read arc core state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise
    
    def lifecycle_status_check(self):
        self.composite_logger.log_debug("Performing lifecycle status check...")
        extension_sequence = self.read_extension_sequence()
        arc_core_sequence = self.read_arc_core_sequence()

        if int(extension_sequence['number']) == int(self.execution_config.sequence_number):
            self.composite_logger.log_debug("Extension sequence number verified to have not changed: {0}".format(str(extension_sequence['number'])))
        else:
            self.composite_logger.log_error("Extension goal state has changed. Terminating current sequence: {0}".format(self.execution_config.sequence_number))
            self.update_core_sequence(completed=True)   # forced-to-complete scenario | extension wrapper will be watching for this event
            self.env_layer.exit(0)
        self.composite_logger.log_debug("Completed lifecycle status check.")

        if arc_core_sequence['completed'] == "False":
            self.composite_logger.log_warning("Arc extension with sequence number {0} is currently running. Exiting autoassessment".format(str(arc_core_sequence['number'])))
            self.update_core_sequence(completed=True)   # forced-to-complete scenario | extension wrapper will be watching for this event
            self.env_layer.exit(0)

    # End region State checkers 

    # region - Identity
    def get_vm_cloud_type(self):
        return Constants.VMCloudType.ARC
    # endregion

