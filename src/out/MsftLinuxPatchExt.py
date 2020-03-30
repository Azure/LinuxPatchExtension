# --------------------------------------------------------------------------------------------------------------------
# <copyright file="MsftLinuxPatchExt.py" company="Microsoft">
#   Copyright (c) Microsoft Corporation. All rights reserved.
# </copyright>
# --------------------------------------------------------------------------------------------------------------------

from __future__ import print_function
from abc import ABCMeta, abstractmethod
import time
import os.path
import traceback
import sys
import subprocess
import signal
import datetime
import os
import platform
import json
import base64
import re
import errno
import collections


# region ########## ActionHandler.py ##########
class ActionHandler(object):
    """Responsible for identifying the action to perform based on the user input"""
    def __init__(self, logger, utility, runtime_context_handler, json_file_handler, ext_env_handler, ext_config_settings_handler, core_state_handler, ext_state_handler, ext_output_status_handler, process_handler, cmd_exec_start_time, seq_no):
        self.logger = logger
        self.utility = utility
        self.runtime_context_handler = runtime_context_handler
        self.json_file_handler = json_file_handler
        self.ext_env_handler = ext_env_handler
        self.ext_config_settings_handler = ext_config_settings_handler
        self.core_state_handler = core_state_handler
        self.ext_state_handler = ext_state_handler
        self.ext_output_status_handler = ext_output_status_handler
        self.process_handler = process_handler
        self.cmd_exec_start_time = cmd_exec_start_time
        self.seq_no = seq_no

    def determine_operation(self, command):
        switcher = {
            "-install": self.install,
            "-uninstall": self.uninstall,
            "-disable": self.disable,
            "-enable": self.enable,
            "-update": self.update,
            "-reset": self.reset
        }
        try:
            return switcher[command]()
        except KeyError as e:
            raise e

    def install(self):
        self.logger.log("Extension installation started")
        install_command_handler = InstallCommandHandler(self.logger, self.ext_env_handler)
        return install_command_handler.execute_handler_action()

    def update(self):
        """ as per the extension user guide, upon update request, Azure agent calls
         1. disable on the prev version
         2. update on the new version
         3. uninstall on the prev version
         4. install (if updateMode is UpdateWithInstall)
         5. enable on the new version
         on uninstall the agent deletes removes configuration files"""
        # todo: in the test run verify if CoreState.json, ExtState.json and the .status files are deleted, if yes, move them to a separate location
        self.logger.log("Extension updated")
        return Constants.ExitCode.Okay

    def uninstall(self):
        # ToDo: verify if the agent deletes config files. And find out from the extension/agent team if we need to delete older logs
        self.logger.log("Extension uninstalled")
        return Constants.ExitCode.Okay

    def enable(self):
        self.logger.log("Enable triggered on extension")
        enable_command_handler = EnableCommandHandler(self.logger, self.utility, self.runtime_context_handler, self.ext_env_handler, self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, self.ext_output_status_handler, self.process_handler, self.cmd_exec_start_time, self.seq_no)
        return enable_command_handler.execute_handler_action()

    def disable(self):
        self.logger.log("Disable triggered on extension")
        prev_patch_max_end_time = self.cmd_exec_start_time + datetime.timedelta(hours=0, minutes=Constants.DISABLE_MAX_RUNTIME)
        self.runtime_context_handler.process_previous_patch_operation(self.core_state_handler, self.process_handler, prev_patch_max_end_time, core_state_content=None)
        self.logger.log("Extension disabled successfully")
        return Constants.ExitCode.Okay

    def reset(self):
        #ToDo: do we have to delete log and status files? and raise error if delete fails?
        self.logger.log("Reset triggered on extension, deleting CoreState and ExtState files")
        self.utility.delete_file(self.core_state_handler.dir_path, self.core_state_handler.file, raise_if_not_found=False)
        self.utility.delete_file(self.ext_state_handler.dir_path, self.ext_state_handler.file, raise_if_not_found=False)
        return Constants.ExitCode.Okay

# endregion ########## ActionHandler.py ##########


# region ########## Constants.py ##########
class Constants(object):
    """Static class contains all constant variables"""

    class EnumBackport(object):
        class __metaclass__(type):
            def __iter__(self):
                for item in self.__dict__:
                    if item == self.__dict__[item]:
                        yield item

    # Runtime environments
    TEST = 'Test'
    DEV = 'Dev'
    PROD = 'Prod'         # Azure Native Patch Management
    UNKNOWN_ENV = 'Unknown'     # Non-functional code placeholder prior to compile

    # File Constants
    HANDLER_ENVIRONMENT_FILE = 'HandlerEnvironment.json'
    HANDLER_MANIFEST_FILE = 'HandlerManifest.json'
    CORE_STATE_FILE = 'CoreState.json'
    EXT_STATE_FILE = 'ExtState.json'
    HANDLER_ENVIRONMENT_FILE_PATH = os.getcwd()
    CONFIG_SETTINGS_FILE_EXTENSION = '.settings'
    STATUS_FILE_EXTENSION = '.status'
    CORE_CODE_FILE_NAME = 'MsftLinuxPatchCore.py'
    LOG_FILE_EXTENSION = '.log'
    LOG_FILES_TO_RETAIN = 10
    MAX_LOG_FILES_ALLOWED = 40

    # Environment variables
    SEQ_NO_ENVIRONMENT_VAR = "ConfigSequenceNumber"

    # Max runtime for specific commands in minutes
    ENABLE_MAX_RUNTIME = 3
    DISABLE_MAX_RUNTIME = 13

    # Todo: will be implemented later
    # Telemetry Categories
    TelemetryExtState = "State"
    TelemetryConfig = "Config"
    TelemetryError = "Error"
    TelemetryWarning = "Warning"
    TelemetryInfo = "Info"
    TelemetryDebug = "Debug"

    # Re-try limit for file operations
    MAX_IO_RETRIES = 5

    # Operations
    NOOPERATION = "NoOperation"
    PATCH_NOOPERATION_SUMMARY = "PatchNoOperationSummary"

    # HandlerEnvironment constants
    class EnvSettingsFields(EnumBackport):
        version = "version"
        settings_parent_key = "handlerEnvironment"
        log_folder = "logFolder"
        config_folder = "configFolder"
        status_folder = "statusFolder"

    # Config Settings json keys
    RUNTIME_SETTINGS = "runtimeSettings"
    HANDLER_SETTINGS = "handlerSettings"
    PUBLIC_SETTINGS = "publicSettings"

    # Public Settings within Config Settings
    class ConfigPublicSettingsFields(EnumBackport):
        operation = "operation"
        activity_id = "activityId"
        start_time = "startTime"
        maximum_duration = "maximumDuration"
        reboot_setting = "rebootSetting"
        include_classifications = "classificationsToInclude"
        include_patches = "patchesToInclude"
        exclude_patches = "patchesToExclude"
        internal_settings = "internalSettings"

    # ExtState.json keys
    class ExtStateFields(EnumBackport):
        ext_seq = "extensionSequence"
        ext_seq_number = "number"
        ext_seq_achieve_enable_by = "achieveEnableBy"
        ext_seq_operation = "operation"

    # <SequenceNumber>.status keys
    class StatusFileFields(EnumBackport):
        version = "version"
        timestamp_utc = "timestampUTC"
        status = "status"
        status_name = "name"
        status_operation = "operation"
        status_status = "status"
        status_code = "code"
        status_formatted_message = "formattedMessage"
        status_formatted_message_lang = "lang"
        status_formatted_message_message = "message"
        status_substatus = "substatus"

    # CoreState.json keys
    class CoreStateFields(EnumBackport):
        parent_key = "coreSequence"
        number = "number"
        action = "action"
        completed = "completed"
        last_heartbeat = "lastHeartbeat"
        process_ids = "processIds"

    # Status values
    class Status(EnumBackport):
        Transitioning = "Transitioning"
        Error = "Error"
        Success = "Success"
        Warning = "Warning"

    class ExitCode(EnumBackport):
        Okay = 0
        HandlerFailed = -1
        MissingConfig = -2
        BadConfig = -3
        UnsupportedOperatingSystem = 51
        MissingDependency = 52
        ConfigurationError = 53
        BadHandlerEnvironmentFile = 3560
        UnableToReadStatusFile = 3561
        CreateFileLoggerFailure = 3562
        ReadingAndDeserializingConfigFileFailure = 3563
        InvalidConfigSettingPropertyValue = 3564
        CreateLoggerFailure = 3565
        CreateStatusWriterFailure = 3566

# endregion ########## Constants.py ##########


# region ########## EnableCommandHandler.py ##########
class EnableCommandHandler(object):
    """ Responsible for executing the action for enable command """
    def __init__(self, logger, utility, runtime_context_handler, ext_env_handler, ext_config_settings_handler, core_state_handler, ext_state_handler, ext_output_status_handler, process_handler, cmd_exec_start_time, seq_no):
        self.logger = logger
        self.utility = utility
        self.runtime_context_handler = runtime_context_handler
        self.ext_env_handler = ext_env_handler
        self.ext_config_settings_handler = ext_config_settings_handler
        self.core_state_handler = core_state_handler
        self.ext_state_handler = ext_state_handler
        self.ext_output_status_handler = ext_output_status_handler
        self.process_handler = process_handler
        self.cmd_exec_start_time = cmd_exec_start_time
        self.seq_no = seq_no
        self.config_public_settings = Constants.ConfigPublicSettingsFields
        self.core_state_fields = Constants.CoreStateFields
        self.status = Constants.Status

    def execute_handler_action(self):
        """ Responsible for taking appropriate action for enable command as per the request sent in Handler Configuration file by user """
        try:
            config_settings = self.ext_config_settings_handler.read_file(self.seq_no)
            prev_patch_max_end_time = self.cmd_exec_start_time + datetime.timedelta(hours=0, minutes=Constants.ENABLE_MAX_RUNTIME)
            self.ext_state_handler.create_file(self.seq_no, config_settings.__getattribute__(self.config_public_settings.operation), prev_patch_max_end_time)
            core_state_content = self.core_state_handler.read_file()

            # if NoOperation is requested, terminate all running processes from previous operation and update status file
            if config_settings.__getattribute__(self.config_public_settings.operation) == Constants.NOOPERATION:
                self.logger.log("NoOperation requested. Terminating older patch operation, if still in progress.")
                self.process_nooperation(config_settings, core_state_content)
            else:
                # if any of the other operations are requested, verify if request is a new request or a re-enable, by comparing sequence number from the prev request and current one
                if core_state_content is None or core_state_content.__getattribute__(self.core_state_fields.number) is None:
                    # first patch request for the VM
                    self.logger.log("No state information was found for any previous patch operation. Launching a new patch operation.")
                    self.launch_new_process(config_settings, create_status_output_file=True)
                else:
                    if int(core_state_content.__getattribute__(self.core_state_fields.number)) != int(self.seq_no):
                        # new request
                        self.process_enable_request(config_settings, prev_patch_max_end_time, core_state_content)
                    else:
                        # re-enable request
                        self.process_reenable_request(config_settings, core_state_content)
        except Exception as error:
            self.logger.log_error("Failed to execute enable. [Exception={0}]".format(repr(error)))
            raise

    def process_enable_request(self, config_settings, prev_patch_max_end_time, core_state_content):
        """ Called when the current request is different from the one before. Identifies and waits for the previous request action to complete, if required before addressing the current request """
        self.logger.log("Terminating older patch operation, if still in progress, as per it's completion duration and triggering the new requested patch opertaion.")
        self.runtime_context_handler.process_previous_patch_operation(self.core_state_handler, self.process_handler, prev_patch_max_end_time, core_state_content)
        self.utility.delete_file(self.core_state_handler.dir_path, self.core_state_handler.file)
        self.launch_new_process(config_settings, create_status_output_file=True)

    def process_reenable_request(self, config_settings, core_state_content):
        """ Called when the current request has the same config as the one before it. Restarts the operation if the previous request has errors, no action otherwise """
        self.logger.log("This is the same request as the previous patch operation. Checking previous request's status")
        if core_state_content.__getattribute__(self.core_state_fields.completed).lower() == 'false':
            running_process_ids = self.process_handler.identify_running_processes(core_state_content.__getattribute__(self.core_state_fields.process_ids))
            if len(running_process_ids) == 0:
                self.logger.log("Re-triggering the patch operation as the previous patch operation was not running and hadn't marked completion either.")
                self.utility.delete_file(self.core_state_handler.dir_path, self.core_state_handler.file)
                self.launch_new_process(config_settings, create_status_output_file=False)
            else:
                self.logger.log("Patch operation is in progress from the previous request. [Operation={0}]".format(config_settings.__getattribute__(self.config_public_settings.operation)))
                exit(Constants.ExitCode.Okay)

        else:
            self.logger.log("Patch operation already completed in the previous request. [Operation={0}]".format(config_settings.__getattribute__(self.config_public_settings.operation)))
            exit(Constants.ExitCode.Okay)

    def launch_new_process(self, config_settings, create_status_output_file):
        """ Creates <sequence number>.status to report the current request's status and launches core code to handle the requested operation """
        # create Status file
        if create_status_output_file:
            self.ext_output_status_handler.write_status_file(self.seq_no, self.ext_env_handler.status_folder, config_settings.__getattribute__(self.config_public_settings.operation), substatus_json=[], status=self.status.Transitioning.lower())
        else:
            self.ext_output_status_handler.update_file(self.seq_no, self.ext_env_handler.status_folder)
        # launch core code in a process and exit extension handler
        process = self.process_handler.start_daemon(self.seq_no, config_settings, self.ext_env_handler)
        self.logger.log("exiting extension handler")
        exit(Constants.ExitCode.Okay)

    def process_nooperation(self, config_settings, core_state_content):
        activity_id = config_settings.__getattribute__(self.config_public_settings.activity_id)
        operation = config_settings.__getattribute__(self.config_public_settings.operation)
        start_time = config_settings.__getattribute__(self.config_public_settings.start_time)
        try:
            self.ext_output_status_handler.set_nooperation_substatus_json(self.seq_no, self.ext_env_handler.status_folder, operation, activity_id, start_time, status=Constants.Status.Transitioning)
            self.runtime_context_handler.terminate_processes_from_previous_operation(self.process_handler, core_state_content)
            self.utility.delete_file(self.core_state_handler.dir_path, self.core_state_handler.file, raise_if_not_found=False)
            # ToDo: log prev activity id later
            self.ext_output_status_handler.set_nooperation_substatus_json(self.seq_no, self.ext_env_handler.status_folder, operation, activity_id, start_time, status=Constants.Status.Success)
            self.logger.log("exiting extension handler")
            exit(Constants.ExitCode.Okay)
        except Exception as error:
            self.logger.log("Error executing NoOperation.")
            self.ext_output_status_handler.set_nooperation_substatus_json(self.seq_no, self.ext_env_handler.status_folder, operation, activity_id, start_time, status=Constants.Status.Error)



# endregion ########## EnableCommandHandler.py ##########


# region ########## InstallCommandHandler.py ##########
class InstallCommandHandler(object):

    def __init__(self, logger, ext_env_handler):
        self.logger = logger
        self.ext_env_handler = ext_env_handler

    def execute_handler_action(self):
        self.validate_os_type()
        self.validate_environment()
        self.logger.log("Install Command Completed")
        return Constants.ExitCode.Okay

    def validate_os_type(self):
        os_type = sys.platform
        self.logger.log("Validating OS. [Platform={0}]".format(os_type))
        if not os_type.__contains__('linux'):
            error_msg = "Incompatible system: This update is for Linux OS"
            self.logger.log_error_and_raise_new_exception(error_msg, Exception)
        return True

    def validate_environment(self):
        file = Constants.HANDLER_ENVIRONMENT_FILE
        env_settings_fields = Constants.EnvSettingsFields
        config_type = env_settings_fields.settings_parent_key
        self.logger.log("Validating file. [File={0}]".format(file))

        if self.ext_env_handler.handler_environment_json is not None and self.ext_env_handler.handler_environment_json is not Exception:
            if len(self.ext_env_handler.handler_environment_json) != 1:
                error_msg = "Incorrect file format. [File={0}]".format(file)
                self.logger.log_error_and_raise_new_exception(error_msg, Exception)

            self.validate_key(config_type, self.ext_env_handler.handler_environment_json[0], 'dict', True, file)
            self.validate_key(env_settings_fields.log_folder, self.ext_env_handler.handler_environment_json[0][config_type], ['str', 'unicode'], True, file)
            self.validate_key(env_settings_fields.config_folder, self.ext_env_handler.handler_environment_json[0][config_type], ['str', 'unicode'], True, file)
            self.validate_key(env_settings_fields.status_folder, self.ext_env_handler.handler_environment_json[0][config_type], ['str', 'unicode'], True, file)
            self.logger.log("Handler Environment validated")
        else:
            error_msg = "No content in file. [File={0}]".format(file)
            self.logger.log_error_and_raise_new_exception(error_msg, Exception)

    """ Validates json files for required key/value pairs """
    def validate_key(self, key, config_type, data_type, is_required, file):
        if is_required:
            # Required key doesn't exist in config file
            if key not in config_type:
                error_msg = "Config not found in file. [Config={0}] [File={1}]".format(key, file)
                self.logger.log_error_and_raise_new_exception(error_msg, Exception)
            # Required key doesn't have value
            elif data_type is not bool and not config_type[key]:
                error_msg = "Empty value error. [Config={0}]".format(key)
                self.logger.log_error_and_raise_new_exception(error_msg, Exception)
            # Required key does not have value of expected datatype
            elif type(config_type[key]).__name__  not in data_type:
                error_msg = "Unexpected data type. [config={0}] in [file={1}]".format(key, file)
                self.logger.log_error_and_raise_new_exception(error_msg, Exception)
        else:
            # Expected data type for an optional key
            if key in config_type and config_type[key] and type(config_type[key]).__name__  not in data_type:
                error_msg = "Unexpected data type. [config={0}] in [file={1}]".format(key, file)
                self.logger.log_error_and_raise_new_exception(error_msg, Exception)

# endregion ########## InstallCommandHandler.py ##########


# region ########## ProcessHandler.py ##########
class ProcessHandler(object):
    def __init__(self, logger):
        self.logger = logger

    def get_public_config_settings(self, config_settings):
        """ Fetches only public settings from given config_settings and returns them in json format """
        public_config_settings = {}
        public_settings_keys = Constants.ConfigPublicSettingsFields
        if config_settings is not None:
            public_config_settings.update({public_settings_keys.operation: config_settings.__getattribute__(public_settings_keys.operation),
                                           public_settings_keys.activity_id: config_settings.__getattribute__(public_settings_keys.activity_id),
                                           public_settings_keys.start_time: config_settings.__getattribute__(public_settings_keys.start_time),
                                           public_settings_keys.maximum_duration: config_settings.__getattribute__(public_settings_keys.maximum_duration),
                                           public_settings_keys.reboot_setting: config_settings.__getattribute__(public_settings_keys.reboot_setting),
                                           public_settings_keys.include_classifications: config_settings.__getattribute__(public_settings_keys.include_classifications),
                                           public_settings_keys.include_patches: config_settings.__getattribute__(public_settings_keys.include_patches),
                                           public_settings_keys.exclude_patches: config_settings.__getattribute__(public_settings_keys.exclude_patches),
                                           public_settings_keys.internal_settings: config_settings.__getattribute__(public_settings_keys.internal_settings)})
        return public_config_settings

    def get_env_settings(self, ext_env_handler):
        """ Fetches configs required by the core code from HandlerEnvironment file returns them in json format """
        env_settings = {}
        env_settings_keys = Constants.EnvSettingsFields
        if env_settings is not None:
            env_settings.update({env_settings_keys.log_folder: ext_env_handler.log_folder})
            env_settings.update({env_settings_keys.config_folder: ext_env_handler.config_folder})
            env_settings.update({env_settings_keys.status_folder: ext_env_handler.status_folder})
        return env_settings

    def start_daemon(self, seq_no, config_settings, ext_env_handler):
        """ Launches the core code in a separate independent process with required arguements and exits the current process immediately """
        exec_path = os.path.join(os.getcwd(), Constants.CORE_CODE_FILE_NAME)
        public_config_settings = base64.b64encode(json.dumps(self.get_public_config_settings(config_settings)).encode("utf-8")).decode("utf-8")
        env_settings = base64.b64encode(json.dumps(self.get_env_settings(ext_env_handler)).encode("utf-8")).decode("utf-8")

        args = " -sequenceNumber {0} -environmentSettings \'{1}\' -configSettings \'{2}\'".format(str(seq_no), env_settings, public_config_settings)
        command = ["python " + exec_path + " " + args]
        self.logger.log("Launching process. [command={0}]".format(str(command)))
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.pid is not None:
            self.logger.log("New shell process launched successfully. [Process ID (PID)={0}]".format(str(process.pid)))
            return process
        self.logger.log_error("Error launching process for given sequence. [sequence={0}]".format(seq_no))

    def identify_running_processes(self, process_ids):
        """ Returns a list of all currently active processes from the given list of process ids """
        running_process_ids = []
        for process_id in process_ids:
            if process_id != "":
                process_id = int(process_id)
                if self.is_process_running(process_id):
                    running_process_ids.append(process_id)
        self.logger.log("Processes still running from the previous request: [PIDs={0}]".format(str(running_process_ids)))
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

    def kill_process(self, pid):
        try:
            if self.is_process_running(pid):
                self.logger.log("Terminating process: [PID={0}]".format(str(pid)))
                os.kill(pid, signal.SIGTERM)
        except OSError as error:
            self.logger.log_error("Error terminating process. [Process ID={0}] [Error={1}]".format(pid, repr(error)))
            raise

# endregion ########## ProcessHandler.py ##########


# region ########## RuntimeContextHandler.py ##########
class RuntimeContextHandler(object):
    def __init__(self, logger):
        self.logger = logger
        self.core_state_fields = Constants.CoreStateFields

    def terminate_processes_from_previous_operation(self, process_handler, core_state_content):
        """ Terminates all running processes from the previous request """
        self.logger.log("Verifying if previous patch operation is still in progress")
        if core_state_content is None or core_state_content.__getattribute__(self.core_state_fields.completed).lower() == 'true':
            self.logger.log("Previous request is complete")
            return
        # verify if processes from prev request are running
        running_process_ids = process_handler.identify_running_processes(core_state_content.__getattribute__(self.core_state_fields.process_ids))
        if len(running_process_ids) != 0:
            for pid in running_process_ids:
                process_handler.kill_process(pid)

    def process_previous_patch_operation(self, core_state_handler, process_handler, prev_patch_max_end_time, core_state_content):
        """ Waits for the previous request action to complete for a specific time, terminates previous process if it goes over that time """
        self.logger.log("Verifying if previous patch operation is still in progress")
        core_state_content = core_state_handler.read_file() if core_state_content is None else core_state_content
        if core_state_content is None or core_state_content.__getattribute__(self.core_state_fields.completed).lower() == 'true':
            self.logger.log("Previous request is complete")
            return
        # verify if processes from prev request are running
        running_process_ids = process_handler.identify_running_processes(core_state_content.__getattribute__(self.core_state_fields.process_ids))
        if len(running_process_ids) != 0:
            is_patch_complete = self.check_if_patch_completes_in_time(prev_patch_max_end_time, core_state_content.__getattribute__(self.core_state_fields.last_heartbeat), core_state_handler)
            if is_patch_complete:
                self.logger.log("Previous request is complete")
                return
            for pid in running_process_ids:
                self.logger.log("Previous request did not complete in time. Terminating all of it's running processes.")
                process_handler.kill_process(pid)

    def check_if_patch_completes_in_time(self, time_for_prev_patch_to_complete, core_state_last_heartbeat, core_state_handler):
        """ Waits for the previous request to complete in given time, with intermittent status checks """
        if type(time_for_prev_patch_to_complete) is not datetime.datetime:
            raise Exception("System Error: Unable to identify the time to wait for previous request to complete")
        max_wait_interval_in_seconds = 60
        current_time = datetime.datetime.utcnow()
        remaining_wait_time = (time_for_prev_patch_to_complete - current_time).total_seconds()
        core_state_content = None
        while remaining_wait_time > 0:
            next_wait_time_in_seconds = max_wait_interval_in_seconds if remaining_wait_time > max_wait_interval_in_seconds else remaining_wait_time
            core_state_last_heartbeat = core_state_last_heartbeat if core_state_content is None else core_state_content.__getattribute__(self.core_state_fields.last_heartbeat)
            self.logger.log("Previous patch operation is still in progress with last status update at {0}. Waiting for a maximum of {1} seconds for it to complete with intermittent status change checks. Next check will be performed after {2} seconds.".format(str(core_state_last_heartbeat), str(remaining_wait_time), str(next_wait_time_in_seconds)))
            time.sleep(next_wait_time_in_seconds)
            remaining_wait_time = (time_for_prev_patch_to_complete - datetime.datetime.utcnow()).total_seconds()
            # read CoreState.json file again, to verify if the previous processes is completed
            core_state_content = core_state_handler.read_file()
            if core_state_content.__getattribute__(self.core_state_fields.completed).lower() == 'true':
                return True
        return False

# endregion ########## RuntimeContextHandler.py ##########


# region ########## TelemetryWriter.py ##########
class TelemetryWriter(object):
    """Class for writing telemetry data to data transports"""

    def __init__(self):
        self.data_transports = []
        self.activity_id = None

        # Init state report
        self.send_ext_state_info('Started Linux patch extension execution.')
        self.send_machine_config_info()

    # region Primary payloads
    def send_ext_state_info(self, state_info):
        # Expected to send up only pivotal extension state changes
        return self.try_send_message(state_info, Constants.TelemetryExtState)

    def send_config_info(self, config_info, config_type='unknown'):
        # Configuration info
        payload_json = {
            'config_type': config_type,
            'config_value': config_info
        }
        return self.try_send_message(payload_json, Constants.TelemetryConfig)

    def send_error_info(self, error_info):
        # Expected to log significant errors or exceptions
        return self.try_send_message(error_info, Constants.TelemetryError)

    def send_debug_info(self, error_info):
        # Usually expected to instrument possibly problematic code
        return self.try_send_message(error_info, Constants.TelemetryDebug)

    def send_info(self, info):
        # Usually expected to be significant runbook output
        return self.try_send_message(info, Constants.TelemetryInfo)
    # endregion

    # Composed payload
    def send_machine_config_info(self):
        # Machine info
        machine_info = {
            'platform_name': str(platform.linux_distribution()[0]),
            'platform_version': str(platform.linux_distribution()[1]),
            'machine_arch': str(platform.machine())
        }
        return self.send_config_info(machine_info, 'machine_config')

    def send_execution_error(self, cmd, code, output):
        # Expected to log any errors from a cmd execution, including package manager execution errors
        error_payload = {
            'cmd': str(cmd),
            'code': str(code),
            'output': str(output)[0:3072]
        }
        return self.send_error_info(error_payload)
    # endregion

    # region Transport layer
    def try_send_message(self, message, category=Constants.TelemetryInfo):
        raise NotImplementedError

    def close_transports(self):
        """Close data transports"""
        raise NotImplementedError
    # endregion

# endregion ########## TelemetryWriter.py ##########


# region ########## Utility.py ##########
class Utility(object):
    def __init__(self, logger):
        self.logger = logger
        self.retry_count = Constants.MAX_IO_RETRIES

    def delete_file(self, dir_path, file, raise_if_not_found=True):
        """ Retries delete operation for a set number of times before failing """
        self.logger.log("Deleting file. [File={0}]".format(file))
        file_path = os.path.join(dir_path, file)
        error_msg = ""
        if os.path.exists(file_path) and os.path.isfile(file_path):
            for retry in range(0, self.retry_count):
                try:
                    time.sleep(retry)
                    os.remove(file_path)
                    return True
                except Exception as e:
                    error_msg = "Trial {0}: Could not delete file. [File={1}] [Exception={2}]".format(retry+1, file, repr(e))
                    self.logger.log_error(error_msg)
            error_msg = "Failed to delete file after {0} tries. [File={1}] [Exception={2}]".format(self.retry_count, file, error_msg)
            self.logger.log_error(error_msg)
        else:
            error_msg = "File Not Found: [File={0}] in [path={1}]".format(file, dir_path)
            self.logger.log_error(error_msg)
        if raise_if_not_found:
            raise Exception(error_msg)

    def create_log_file(self, log_folder, seq_no):
        """ Creates <sequencenumber>.ext.log file under the path for logFolder provided in HandlerEnvironment """
        file_path = str(seq_no) + str(".ext") + Constants.LOG_FILE_EXTENSION
        if seq_no is not None and os.path.exists(log_folder):
            self.logger.log("Creating log file. [File={0}]".format(file_path))
            return FileLogger(log_folder, file_path)
        else:
            self.logger.log_error("File creation error: [File={0}]".format(file_path))
            return None

    def get_datetime_from_str(self, date_str):
        return datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")

    def get_str_from_datetime(self, date):
        return date.strftime("%Y-%m-%dT%H:%M:%SZ")

# endregion ########## Utility.py ##########


# region ########## CoreStateHandler.py ##########
class CoreStateHandler(object):
    """ Responsible for managing CoreState.json file """
    def __init__(self, dir_path, json_file_handler):
        self.dir_path = dir_path
        self.file = Constants.CORE_STATE_FILE
        self.json_file_handler = json_file_handler
        self.core_state_fields = Constants.CoreStateFields

    def read_file(self):
        """ Fetches config from CoreState.json. Returns None if no content/file found """
        core_state_json = self.json_file_handler.get_json_file_content(self.file, self.dir_path, raise_if_not_found=False)
        parent_key = self.core_state_fields.parent_key
        core_state_values = collections.namedtuple(parent_key, [self.core_state_fields.number, self.core_state_fields.action, self.core_state_fields.completed, self.core_state_fields.last_heartbeat, self.core_state_fields.process_ids])
        if core_state_json is not None:
            seq_no = self.json_file_handler.get_json_config_value_safely(core_state_json, self.core_state_fields.number, parent_key)
            action = self.json_file_handler.get_json_config_value_safely(core_state_json, self.core_state_fields.action, parent_key)
            completed = self.json_file_handler.get_json_config_value_safely(core_state_json, self.core_state_fields.completed, parent_key)
            last_heartbeat = self.json_file_handler.get_json_config_value_safely(core_state_json, self.core_state_fields.last_heartbeat, parent_key)
            process_ids = self.json_file_handler.get_json_config_value_safely(core_state_json, self.core_state_fields.process_ids, parent_key)
            return core_state_values(seq_no, action, completed, last_heartbeat, process_ids)


# endregion ########## CoreStateHandler.py ##########


# region ########## ExtConfigSettingsHandler.py ##########
class ExtConfigSettingsHandler(object):
    """ Responsible for managing any operations with <Sequence Number>.settings file """
    def __init__(self, logger, json_file_handler, config_folder):
        self.config_folder = config_folder
        self.logger = logger
        self.json_file_handler = json_file_handler
        self.file_ext = Constants.CONFIG_SETTINGS_FILE_EXTENSION
        self.runtime_settings_key = Constants.RUNTIME_SETTINGS
        self.handler_settings_key = Constants.HANDLER_SETTINGS
        self.public_settings_key = Constants.PUBLIC_SETTINGS
        self.public_settings_all_keys = Constants.ConfigPublicSettingsFields

    def get_seq_no(self):
        """ Fetches sequence number, initially from the env variable. If nothing is set in env variable then fetches from config folder based on timestamp, since GA updates the settings file before calling a command """
        try:
            seq_no = os.getenv(Constants.SEQ_NO_ENVIRONMENT_VAR)
            if seq_no is not None:
                return seq_no

            seq_no = None
            cur_seq_no = None
            freshest_time = None
            for subdir, dirs, files in os.walk(self.config_folder):
                for file in files:
                    try:
                        if re.match('^\d+' + self.file_ext + '$', file):
                            cur_seq_no = int(os.path.basename(file).split('.')[0])
                            if freshest_time is None:
                                freshest_time = os.path.getmtime(os.path.join(self.config_folder, file))
                                seq_no = cur_seq_no
                            else:
                                current_file_m_time = os.path.getmtime(os.path.join(self.config_folder, file))
                                if current_file_m_time > freshest_time:
                                    freshest_time = current_file_m_time
                                    seq_no = cur_seq_no
                    except ValueError:
                        continue
            return seq_no
        except Exception as error:
            error_message = "Error occurred while fetching sequence number"
            self.logger.log_error(error_message)
            raise

    def read_file(self, seq_no):
        """ Fetches config from <seq_no>.settings file in <self.config_folder>. Raises an exception if no content/file found/errors processing file """
        try:
            file = str(seq_no) + self.file_ext
            config_settings_json = self.json_file_handler.get_json_file_content(file, self.config_folder, raise_if_not_found=True)
            if config_settings_json is not None and self.are_config_settings_valid(config_settings_json):
                operation = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.operation)
                activity_id = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.activity_id)
                start_time = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.start_time)
                max_duration = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.maximum_duration, raise_if_not_found=False)
                reboot_setting = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.reboot_setting, raise_if_not_found=False)
                include_classifications = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.include_classifications, raise_if_not_found=False)
                include_patches = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.include_patches, raise_if_not_found=False)
                exclude_patches = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.exclude_patches, raise_if_not_found=False)
                internal_settings = self.get_ext_config_value_safely(config_settings_json, self.public_settings_all_keys.internal_settings, raise_if_not_found=False)

                config_settings_values = collections.namedtuple("config_settings", [self.public_settings_all_keys.operation, self.public_settings_all_keys.activity_id, self.public_settings_all_keys.start_time,
                                                                                    self.public_settings_all_keys.maximum_duration, self.public_settings_all_keys.reboot_setting, self.public_settings_all_keys.include_classifications,
                                                                                    self.public_settings_all_keys.include_patches, self.public_settings_all_keys.exclude_patches, self.public_settings_all_keys.internal_settings])
                return config_settings_values(operation, activity_id, start_time, max_duration, reboot_setting, include_classifications, include_patches, exclude_patches, internal_settings)
            else:
                #ToDo log which of the 2 conditions failed, similar to this logs in other multiple condition checks
                raise Exception("Config Settings json file invalid")
        except Exception as error:
            error_msg = "Error processing config settings file. [Sequence Number={0}] [Exception= {1}]".format(seq_no, repr(error))
            self.logger.log_error(error_msg)
            raise

    def are_config_settings_valid(self, config_settings_json):
        """ Validates all the configs in <seq_no>.settings file. Raises an exception if any issues found """
        try:
            if config_settings_json is None or type(config_settings_json) is not dict or not bool(config_settings_json):
                self.logger.log_error("Configuration settings not of expected format")
                return False
            # file contains "runtimeSettings"
            if self.runtime_settings_key not in config_settings_json or type(config_settings_json[self.runtime_settings_key]) is not list or config_settings_json[self.runtime_settings_key] is None or len(config_settings_json[self.runtime_settings_key]) is 0:
                self.logger.log_error("runtimeSettings not of expected format")
                return False
            # file contains "handlerSettings"
            if self.handler_settings_key not in config_settings_json[self.runtime_settings_key][0] or type(config_settings_json[self.runtime_settings_key][0][self.handler_settings_key]) is not dict \
                    or config_settings_json[self.runtime_settings_key][0][self.handler_settings_key] is None or not bool(config_settings_json[self.runtime_settings_key][0][self.handler_settings_key]):
                self.logger.log_error("handlerSettings not of expected format")
                return False
            # file contains "publicSettings"
            if self.public_settings_key not in config_settings_json[self.runtime_settings_key][0][self.handler_settings_key] or type(config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key]) is not dict \
                    or config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key] is None or not bool(config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key]):
                self.logger.log_error("publicSettings not of expected format")
                return False

            # verifying Configuration settings contain all the mandatory keys
            for public_setting in [self.public_settings_all_keys.operation, self.public_settings_all_keys.activity_id, self.public_settings_all_keys.start_time]:
                if public_setting in config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key] and config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key][public_setting]:
                    continue
                else:
                    self.logger.log_error("Mandatory key missing in publicSettings section of the configuration settings: " + str(public_setting))
                    return False
            return True
        except Exception as error:
            self.logger.log_error(error)
            return False

    def get_ext_config_value_safely(self, config_settings_json, key, raise_if_not_found=True):
        """ Allows a patch deployment configuration value to be queried safely with a fall-back default (optional).
        An exception will be raised if default_value is not explicitly set when called (considered by-design). """

        if config_settings_json is not None and len(config_settings_json) is not 0:
            if key in config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key]:
                value = config_settings_json[self.runtime_settings_key][0][self.handler_settings_key][self.public_settings_key][key]
                return value
            else:  # If it is not present
                if raise_if_not_found:
                    raise Exception("Value not found for given config. [Config={0}]".format(key))
                else:
                    return None
        return None

# endregion ########## ExtConfigSettingsHandler.py ##########


# region ########## ExtEnvHandler.py ##########
class ExtEnvHandler(object):
    """ Responsible for all operations with HandlerEnvironment.json file """
    def __init__(self, json_file_handler, handler_env_file=Constants.HANDLER_ENVIRONMENT_FILE, handler_env_file_path=Constants.HANDLER_ENVIRONMENT_FILE_PATH):
        json_file_handler = json_file_handler
        self.env_settings_all_keys = Constants.EnvSettingsFields

        self.handler_environment_json = json_file_handler.get_json_file_content(handler_env_file, handler_env_file_path, raise_if_not_found=True)
        if self.handler_environment_json is not None:
            self.log_folder = self.get_ext_env_config_value_safely(self.env_settings_all_keys.log_folder)
            self.config_folder = self.get_ext_env_config_value_safely(self.env_settings_all_keys.config_folder)
            self.status_folder = self.get_ext_env_config_value_safely(self.env_settings_all_keys.status_folder)

    def get_ext_env_config_value_safely(self, key, raise_if_not_found=True):
        """ Allows a update deployment configuration value to be queried safely with a fall-back default (optional).
        An exception will be raised if default_value is not explicitly set when called (considered by-design). """
        config_type = self.env_settings_all_keys.settings_parent_key
        if self.handler_environment_json is not None and len(self.handler_environment_json) is not 0:
            if key in self.handler_environment_json[0][config_type]:
                value = self.handler_environment_json[0][config_type][key]
                return value
            else:   # If it is not present
                if raise_if_not_found:
                    raise Exception("Value not found for given config. [Config={0}]".format(key))
                else:
                    return None
        return None

# endregion ########## ExtEnvHandler.py ##########


# region ########## ExtOutputStatusHandler.py ##########
class ExtOutputStatusHandler(object):
    """ Responsible for managing <sequence number>.status file in the status folder path given in HandlerEnvironment.json """
    def __init__(self, logger, json_file_handler):
        self.logger = logger
        self.json_file_handler = json_file_handler
        self.file_ext = Constants.STATUS_FILE_EXTENSION
        self.file_keys = Constants.StatusFileFields
        self.status = Constants.Status

    def write_status_file(self, seq_no, dir_path, operation, substatus_json, status=Constants.Status.Transitioning.lower()):
        self.logger.log("Writing status file to provide patch management data for [Sequence={0}]".format(str(seq_no)))
        file_name = str(seq_no) + self.file_ext
        content = [{
            self.file_keys.version: "1.0",
            self.file_keys.timestamp_utc: str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")),
            self.file_keys.status: {
                self.file_keys.status_name: "Azure Patch Management",
                self.file_keys.status_operation: str(operation),
                self.file_keys.status_status: status.lower(),
                self.file_keys.status_code: 0,
                self.file_keys.status_formatted_message: {
                    self.file_keys.status_formatted_message_lang: "en-US",
                    self.file_keys.status_formatted_message_message: ""
                },
                self.file_keys.status_substatus: substatus_json
            }
        }]
        self.json_file_handler.write_to_json_file(dir_path, file_name, content)

    def read_file(self, seq_no, dir_path):
        file_name = str(seq_no) + self.file_ext
        status_json = self.json_file_handler.get_json_file_content(file_name, dir_path)
        if status_json is None:
            return None
        return status_json

    def update_key_value_safely(self, status_json, key, value_to_update, parent_key=None):
        if status_json is not None and len(status_json) is not 0:
            if parent_key is None:
                status_json[0].update({key: value_to_update})
            else:
                if parent_key in status_json[0]:
                    status_json[0].get(parent_key).update({key: value_to_update})
                else:
                    self.logger.log_error("Error updating config value in status file. [Config={0}]".format(key))

    def update_file(self, seq_no, dir_path):
        """ Reseting status=Transitioning and code=0 with latest timestamp, while retaining all other values"""
        try:
            file_name = str(seq_no) + self.file_ext
            self.logger.log("Updating file. [File={0}]".format(file_name))
            status_json = self.read_file(str(seq_no), dir_path)

            if status_json is None:
                self.logger.log_error("Error processing file. [File={0}]".format(file_name))
                return
            self.update_key_value_safely(status_json, self.file_keys.status_status, self.status.Transitioning.lower(), self.file_keys.status_status)
            self.update_key_value_safely(status_json, self.file_keys.status_code, 0, self.file_keys.status_status)
            self.update_key_value_safely(status_json, self.file_keys.timestamp_utc, str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")))
            self.json_file_handler.write_to_json_file(dir_path, file_name, status_json)
        except Exception as error:
            error_message = "Error in status file creation: " + repr(error)
            self.logger.log_error(error_message)
            raise

    def set_nooperation_substatus_json(self, seq_no, dir_path, operation, activity_id, start_time, status=Constants.Status.Transitioning, code=0):
        """ Prepare the nooperation substatus json including the message containing nooperation summary """
        # Wrap patches into nooperation summary
        nooperation_summary_json = self.new_nooperation_summary_json(activity_id, start_time)

        # Wrap nooperation summary into nooperation substatus
        nooperation_substatus_json = self.new_substatus_json_for_operation(Constants.PATCH_NOOPERATION_SUMMARY, status, code, json.dumps(nooperation_summary_json))

        # Update status on disk
        self.write_status_file(seq_no, dir_path, operation, nooperation_substatus_json, status)

    def new_nooperation_summary_json(self, activity_id, start_time):
        """ This is the message inside the nooperation substatus """
        # Compose substatus message
        return {
            "activityId": str(activity_id),
            "startTime": str(start_time),
            "lastModifiedTime": str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")),
            "errors": ""  # TODO: Implement this to spec
        }

    def new_substatus_json_for_operation(self, operation_name, status="Transitioning", code=0, message=json.dumps("{}")):
        """ Generic substatus for nooperation """
        # NOTE: Todo Function is same for assessment and install, can be generalized later
        return {
            "name": str(operation_name),
            "status": str(status).lower(),
            "code": code,
            "formattedMessage": {
                "lang": "en-US",
                "message": str(message)
            }
        }

# endregion ########## ExtOutputStatusHandler.py ##########


# region ########## ExtStateHandler.py ##########
class ExtStateHandler(object):
    """ Responsible for managing ExtState.json file """
    def __init__(self, dir_path, utility, json_file_handler):
        self.dir_path = dir_path
        self.file = Constants.EXT_STATE_FILE
        self.utility = utility
        self.json_file_handler = json_file_handler
        self.ext_fields = Constants.ExtStateFields

    def create_file(self, sequence_number, operation, prev_patch_max_end_time):
        """ Creates ExtState.json file using the config provided in Handler Configuration  """
        parent_key = self.ext_fields.ext_seq
        ext_state = {parent_key: {}}
        ext_state[parent_key][self.ext_fields.ext_seq_number] = sequence_number
        ext_state[parent_key][self.ext_fields.ext_seq_achieve_enable_by] = self.utility.get_str_from_datetime(prev_patch_max_end_time)
        ext_state[parent_key][self.ext_fields.ext_seq_operation] = operation
        self.json_file_handler.write_to_json_file(self.dir_path, self.file, ext_state)

    def read_file(self):
        """ Returns the config values in the file """
        parent_key = self.ext_fields.ext_seq
        ext_state_values = collections.namedtuple(parent_key, [self.ext_fields.ext_seq_number, self.ext_fields.ext_seq_achieve_enable_by, self.ext_fields.ext_seq_operation])
        seq_no = None
        achieve_enable_by = None
        operation_type = None
        ext_state_json = self.json_file_handler.get_json_file_content(self.file, self.dir_path, raise_if_not_found=False)
        if ext_state_json is not None:
            seq_no = self.json_file_handler.get_json_config_value_safely(ext_state_json, self.ext_fields.ext_seq_number, parent_key)
            achieve_enable_by = self.json_file_handler.get_json_config_value_safely(ext_state_json, self.ext_fields.ext_seq_achieve_enable_by, parent_key)
            operation_type = self.json_file_handler.get_json_config_value_safely(ext_state_json, self.ext_fields.ext_seq_operation, parent_key)
        return ext_state_values(seq_no, achieve_enable_by, operation_type)

# endregion ########## ExtStateHandler.py ##########


# region ########## JsonFileHandler.py ##########
class JsonFileHandler(object):
    def __init__(self, logger):
        self.logger = logger
        self.retry_count = Constants.MAX_IO_RETRIES

    def get_json_file_content(self, file, dir_path, raise_if_not_found=False):
        """ Returns content read from the given json file under the directory/path. Re-tries the operation a certain number of times and raises an exception if it still fails """
        file_path = os.path.join(dir_path, file)
        error_msg = ""
        self.logger.log("Reading file. [File={0}]".format(file))
        for retry in range(0, self.retry_count):
            try:
                time.sleep(retry)
                with open(file_path, 'r') as file_handle:
                    file_contents = file_handle.read()
                    return json.loads(file_contents)
            except ValueError as e:
                error_msg = "Incorrect file format. [File={0}] [Location={1}] [Exception={2}]".format(file, str(file_path), repr(e))
                self.logger.log_error(error_msg)
            except Exception as e:
                error_msg = "Trial {0}: Could not read file. [File={1}] [Location={2}] [Exception={3}]".format(retry + 1, file, str(file_path), repr(e))
                self.logger.log_error(error_msg)

        error_msg = "Failed to read file after {0} tries. [File={1}] [Location={2}] [Exception={3}]".format(self.retry_count, file, str(file_path), error_msg)
        self.logger.log_error(error_msg)
        if raise_if_not_found:
            raise Exception(error_msg)

    def get_json_config_value_safely(self, handler_json, key, parent_key, raise_if_not_found=True):
        """ Allows a update deployment configuration value to be queried safely with a fall-back default (optional). An exception will be raised if default_value is not explicitly set when called (considered by-design). """
        if handler_json is not None and len(handler_json) is not 0:
            if key in handler_json[parent_key]:
                value = handler_json[parent_key][key]
                return value
            else:   # If it is not present
                if raise_if_not_found:
                    raise Exception("Value not found for given config. [Config={0}]".format(key))
        return None

    def write_to_json_file(self, dir_path, file, content):
        """ Retries create operation for a set number of times before failing """
        if os.path.exists(dir_path):
            file_path = os.path.join(dir_path, file)
            error_message = ""
            self.logger.log("Writing file. [File={0}]".format(file))
            for retry in range(0, self.retry_count):
                try:
                    time.sleep(retry)
                    with open(file_path, 'w') as json_file:
                        json.dump(content, json_file, default=self.json_default_converter)
                        return
                except Exception as error:
                    error_message = "Trial {0}: Could not write to file. [File={1}] [Location={2}] [Exception={3}]".format(retry+1, file, str(file_path), error)
                    self.logger.log_error(error_message)
            error_msg = "Failed to write to file after {0} tries. [File={1}] [Location={2}] [Exception={3}]".format(self.retry_count, file, str(file_path), error_message)
            self.logger.log_error_and_raise_new_exception(error_msg, Exception)
        else:
            error_msg = "Directory Not Found: [Directory={0}]".format(dir_path)
            self.logger.log_error_and_raise_new_exception(error_msg, Exception)

    def json_default_converter(self, value):
        return value.__str__()

# endregion ########## JsonFileHandler.py ##########


# region ########## FileLogger.py ##########
class FileLogger(object):
    """Facilitates writing selected logs to a file"""

    def __init__(self, log_folder, log_file):
        # opening/creating the log file
        try:
            self.log_file_path = os.path.join(log_folder, log_file)
            self.log_file_handle = open(self.log_file_path, "a")
        except Exception as error:
            sys.stdout.write("FileLogger - Error opening file. [File={0}] [Exception={1}]".format(self.log_file_path, repr(error)))

        # Retaining 10 most recent log files, deleting others
        self.delete_older_log_files(log_folder)
        # verifying if the log file retention was applied.
        log_files = self.get_all_log_files(log_folder)
        if len(log_files) > Constants.MAX_LOG_FILES_ALLOWED:
            print("Retention failed for log files")
            raise Exception("Retention failed for log files")

    def __del__(self):
        self.close()

    def get_all_log_files(self, log_folder):
        """ Returns all files with .log extension within the given folder"""
        return [os.path.join(log_folder, file) for file in os.listdir(log_folder) if (file.lower().endswith('.log'))]

    def delete_older_log_files(self, log_folder):
        """ deletes older log files, retaining only the last 10 log files """
        print("Retaining " + str(Constants.LOG_FILES_TO_RETAIN) + " most recent operation logs, deleting others.")
        try:
            log_files = self.get_all_log_files(log_folder)
            log_files.sort(key=os.path.getmtime, reverse=True)
        except Exception as e:
            print("Error identifying log files to delete. [Exception={0}]".format(repr(e)))
            return

        if len(log_files) >= Constants.LOG_FILES_TO_RETAIN:
            for file in log_files[Constants.LOG_FILES_TO_RETAIN:]:
                try:
                    if os.path.exists(file):
                        os.remove(file)
                        print("Deleted [File={0}]".format(repr(file)))
                except Exception as e:
                    print("Error deleting log file. [File={0} [Exception={1}]]".format(repr(file), repr(e)))

    def write(self, message, fail_silently=True):
        try:
            if self.log_file_handle is not None:
                self.log_file_handle.write(message)
            else:
                raise Exception("Log file not found")
        except IOError:
            # DO NOT write any errors here to stdout
            if not fail_silently:
                raise
        except ValueError as error:
            sys.stdout.write("FileLogger - [Error={0}]".format(repr(error)))
        except Exception as error:
            sys.stdout.write("FileLogger - Error opening file. [File={0}] [Exception={1}]".format(self.log_file_path, repr(error)))

    def flush(self):
        if self.log_file_handle is not None:
            self.log_file_handle.flush()

    def close(self):
        if self.log_file_handle is not None:
            self.log_file_handle.close()

# endregion ########## FileLogger.py ##########


# region ########## Logger.py ##########
class Logger(object):
    def __init__(self, file_logger=None, current_env=None):
        self.file_logger = file_logger
        self.ERROR = "ERROR:"
        self.WARNING = "WARNING:"
        self.DEBUG = "DEBUG:"
        self.VERBOSE = "VERBOSE:"
        self.current_env = current_env
        self.NEWLINE_REPLACE_CHAR = " "

    def log(self, message):
        """log output"""
        for line in message.splitlines():  # allows the extended file logger to strip unnecessary white space
            print(line)
            if self.file_logger is not None:
                self.file_logger.write(line)

    def log_error(self, message):
        """log errors"""
        message = (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        print(self.ERROR + " " + message)
        if self.file_logger is not None:
            self.file_logger.write(self.ERROR + " " + message)

    def log_error_and_raise_new_exception(self, message, exception):
        """log errors and raise exception passed in as an arg"""
        self.log_error(repr(message))
        raise exception(message)

    def log_warning(self, message):
        """log warning"""
        message = (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        print(self.WARNING + " " + message)
        if self.file_logger is not None:
            self.file_logger.write(self.WARNING + " " + message)

    def log_debug(self, message):
        """log debug"""
        message = message.strip()
        if self.current_env in (Constants.DEV, Constants.TEST):
            print(self.current_env + ": " + message)  # send to standard output if dev or test env
        if self.file_logger is not None:
            self.file_logger.write(self.DEBUG + " " + "\n\t".join(message.splitlines()).strip())

    def log_verbose(self, message):
        """log verbose"""
        if self.file_logger is not None:
            self.file_logger.write(self.VERBOSE + " " + "\n\t".join(message.strip().splitlines()).strip())

# endregion ########## Logger.py ##########


# region ########## StdOutFileMirror.py ##########
class StdOutFileMirror(object):
    """Mirrors all terminal output to a local file"""

    def __init__(self, file_logger):
        self.terminal = sys.stdout  # preserve for recovery
        self.file_logger = file_logger

        if self.file_logger.log_file_handle is not None:
            sys.stdout = self
            sys.stdout.write(str('-'*128) + "\n")   # provoking an immediate failure if anything is wrong
        else:
            sys.stdout = self.terminal
            sys.stdout.write("WARNING: StdOutFileMirror - Skipping as FileLogger is not initialized")

    def write(self, message):
        self.terminal.write(message)  # enable standard job output

        if len(message.strip()) > 0:
            try:
                timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                self.file_logger.write("\n" + timestamp + "> " + repr(message), fail_silently=False)  # also write to the file logger file
            except Exception as error:
                sys.stdout = self.terminal  # suppresses further job output mirror failures
                sys.stdout.write("WARNING: StdOutFileMirror - Error writing to log file: " + repr(error))

    def flush(self):
        pass

    def stop(self):
        sys.stdout = self.terminal

# endregion ########## StdOutFileMirror.py ##########


# region ########## __main__.py ##########
def main(argv):
    stdout_file_mirror = None
    file_logger = None
    logger = Logger()
    try:
        # initializing action handler
        # args will have values install, uninstall, etc, as given in MsftLinuxPatchExtShim.sh in the operation var
        cmd_exec_start_time = datetime.datetime.utcnow()
        utility = Utility(logger)
        runtime_context_handler = RuntimeContextHandler(logger)
        json_file_handler = JsonFileHandler(logger)
        ext_env_handler = ExtEnvHandler(json_file_handler)
        if ext_env_handler.handler_environment_json is not None and ext_env_handler.config_folder is not None:
            config_folder = ext_env_handler.config_folder
            if config_folder is None or not os.path.exists(config_folder):
                logger.log_error("Config folder not found at [{0}].".format(repr(config_folder)))
                exit(Constants.ExitCode.MissingConfig)

            ext_config_settings_handler = ExtConfigSettingsHandler(logger, json_file_handler, config_folder)
            seq_no = ext_config_settings_handler.get_seq_no()
            if seq_no is None:
                logger.log_error("Sequence number for current operation not found")
                exit(Constants.ExitCode.MissingConfig)

            file_logger = utility.create_log_file(ext_env_handler.log_folder, seq_no)
            if file_logger is not None:
                stdout_file_mirror = StdOutFileMirror(file_logger)

            core_state_handler = CoreStateHandler(config_folder, json_file_handler)
            ext_state_handler = ExtStateHandler(config_folder, utility, json_file_handler)
            ext_output_status_handler = ExtOutputStatusHandler(logger, json_file_handler)
            process_handler = ProcessHandler(logger)
            action_handler = ActionHandler(logger, utility, runtime_context_handler, json_file_handler, ext_env_handler, ext_config_settings_handler, core_state_handler, ext_state_handler, ext_output_status_handler, process_handler, cmd_exec_start_time, seq_no)
            action_handler.determine_operation(argv[1])
        else:
            error_cause = "No configuration provided in HandlerEnvironment" if ext_env_handler.handler_environment_json is None else "Path to config folder not specified in HandlerEnvironment"
            error_msg = "Error processing file. [File={0}] [Error={1}]".format(Constants.HANDLER_ENVIRONMENT_FILE, error_cause)
            raise Exception(error_msg)
    except Exception as error:
        logger.log_error(repr(error))
        raise
        # todo: add a exitcode instead of raising an exception
    finally:
        if stdout_file_mirror is not None:
            stdout_file_mirror.stop()
        if file_logger is not None:
            file_logger.close()

if __name__ == '__main__':
    main(sys.argv)
# endregion ########## __main__.py ##########
