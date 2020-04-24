import json
import os
import shutil
import time
from src.bootstrap.Constants import Constants


class LifecycleManager(object):
    """Class for managing the core code's lifecycle within the extension wrapper"""

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
        self.composite_logger.log_debug("Execution start check initiating...")
        extension_sequence = self.read_extension_sequence()
        core_sequence = self.read_core_sequence()

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

    def lifecycle_status_check(self):
        self.composite_logger.log_debug("Performing lifecycle status check...")
        extension_sequence = self.read_extension_sequence()
        if int(extension_sequence['number']) == int(self.execution_config.sequence_number):
            self.composite_logger.log_debug("Extension sequence number verified to have not changed: {0}".format(str(extension_sequence['number'])))
        else:
            self.composite_logger.log_error("Extension goal state has changed. Terminating current sequence: {0}".format(self.execution_config.sequence_number))
            self.update_core_sequence(completed=True)   # forced-to-complete scenario | extension wrapper will be watching for this event
            self.env_layer.exit(0)
        self.composite_logger.log_debug("Completed lifecycle status check.")
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
                if i <= Constants.MAX_FILE_OPERATION_RETRY_COUNT:
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
                if i <= Constants.MAX_FILE_OPERATION_RETRY_COUNT:
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
                if i <= Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                    self.composite_logger.log_warning("Exception on core sequence update. [Exception={0}] [RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to write to core state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise

        self.composite_logger.log_debug("Completed updating core sequence.")
    # endregion
