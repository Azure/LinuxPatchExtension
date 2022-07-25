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

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(LifecycleManagerArc,self).__init__(env_layer,execution_config,composite_logger,telemetry_writer, status_handler)

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
        self.arc_core_state_file_path = self.get_arc_core_state_file()

    # region - State checkers
    def execution_start_check(self):
        self.composite_logger.log_debug("\nExecution start check initiating...")

        if self.execution_config.exec_auto_assess_only:
            timer_start_time = self.env_layer.datetime.datetime_utcnow()
            while True:
                extension_sequence = self.read_extension_sequence()
                core_sequence = self.read_core_sequence()
                arc_core_sequence = self.read_arc_core_sequence()

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

                # DEFINITELY NOT SAFE TO START. ARC Assessment/Patch Operation is running. It is not required to start Auto-Assessment
                if arc_core_sequence['completed'].lower() == 'false':
                    self.composite_logger.log_error("Auto-assessment NOT STARTED as arc extension is running. [Attempted={0}][ARCSequenceNo={1}]".format(str(self.execution_config.sequence_number), str(arc_core_sequence['number'])))
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
        core_state_file_path = self.arc_core_state_file_path
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

