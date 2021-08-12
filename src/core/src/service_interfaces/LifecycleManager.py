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
import errno
import json
import os
import shutil
import time
from core.src.bootstrap.Constants import Constants


class LifecycleManager(object):
    """ Parent class for LifecycleManagers of Azure and ARC ( auto assessment ), manages lifecycle within the extension wrapper ~ """

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer):
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer

        # Handshake file paths
        self.ext_state_file_path = os.path.join(self.execution_config.config_folder, Constants.EXT_STATE_FILE)
        self.core_state_file_path = os.path.join(self.execution_config.config_folder, Constants.CORE_STATE_FILE)

    # region - State checkers
    def execution_start_check(self):
        pass

    def lifecycle_status_check(self):
        pass
    # endregion

    # region - State management
    def read_extension_sequence(self):
        self.composite_logger.log_debug("Reading extension sequence...")
        if not os.path.exists(self.ext_state_file_path) or not os.path.isfile(self.ext_state_file_path):
            raise Exception("Extension state file not found.")

        # Read (with retries for only IO Errors)
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.ext_state_file_path, mode="r") as file_handle:
                    return json.load(file_handle)['extensionSequence']
            except Exception as error:
                if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                    self.composite_logger.log_warning("Exception on extension sequence read. [Exception={0}] [RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i+1)
                else:
                    self.composite_logger.log_error("Unable to read extension state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise

    def read_core_sequence(self):
        self.composite_logger.log_debug("Reading core sequence...")
        if not os.path.exists(self.core_state_file_path) or not os.path.isfile(self.core_state_file_path):
            # Neutralizes directories
            if os.path.isdir(self.core_state_file_path):
                self.composite_logger.log_error("Core state file path returned a directory. Attempting to reset.")
                shutil.rmtree(self.core_state_file_path)
            # Writes a vanilla core sequence file
            self.update_core_sequence()

        # Read (with retries for only IO Errors) - TODO: Refactor common code
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.core_state_file_path, mode="r") as file_handle:
                    core_sequence = json.load(file_handle)['coreSequence']
                    return core_sequence
            except Exception as error:
                if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                    self.composite_logger.log_warning("Exception on core sequence read. [Exception={0}] [RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to read core state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise

    def update_core_sequence(self, completed=False):
        self.composite_logger.log_debug("Updating core sequence...")
        core_sequence = {'number': self.execution_config.sequence_number,
                         'action': self.execution_config.operation,
                         'completed': str(completed),
                         'lastHeartbeat': str(self.env_layer.datetime.timestamp()),
                         'processIds': [os.getpid()]}
        core_state_payload = json.dumps({"coreSequence": core_sequence})

        if os.path.isdir(self.core_state_file_path):
            self.composite_logger.log_error("Core state file path returned a directory. Attempting to reset.")
            shutil.rmtree(self.core_state_file_path)

        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.core_state_file_path, 'w+') as file_handle:
                    file_handle.write(core_state_payload)
            except Exception as error:
                if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                    self.composite_logger.log_warning("Exception on core sequence update. [Exception={0}] [RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to write to core state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise

        self.composite_logger.log_debug("Completed updating core sequence.")
    # endregion

    # region - Process Management
    def identify_running_processes(self, process_ids):
        """ Returns a list of all currently active processes from the given list of process ids """
        running_process_ids = []
        for process_id in process_ids:
            if process_id != "":
                process_id = int(process_id)
                if self.is_process_running(process_id):
                    running_process_ids.append(process_id)
        self.composite_logger.log("Processes still running from the previous request: [PIDs={0}]".format(str(running_process_ids)))
        return running_process_ids

    def is_process_running(self, pid):
        # check to see if the process is still alive
        try:
            # Sending signal 0 to a pid will raise an OSError exception if the pid is not running, and do nothing otherwise.
            os.kill(pid, 0)
            return True
        except OSError as error:
            if error.errno == errno.ESRCH:
                # ESRCH == No such process
                return False
            elif error.errno == errno.EPERM:
                # EPERM = No permission, which means there's a process to which access is denied
                return True
            else:
                # According to "man 2 kill" possible error values are (EINVAL, EPERM, ESRCH) Thus considering this as an error
                return False
    # endregion

    # region - Identity
    def get_vm_context(self):
        pass
    #endregion
