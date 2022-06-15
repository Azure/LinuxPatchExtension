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

import os


class Constants(object):
    """Static class contains all constant variables"""

    class EnumBackport(object):
        class __metaclass__(type):
            def __iter__(self):
                for item in self.__dict__:
                    if item == self.__dict__[item]:
                        yield item

    # Extension version (todo: move to a different file)
    EXT_VERSION = "1.6.38"

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
    CORE_AUTO_ASSESS_SH_FILE_NAME = "MsftLinuxPatchAutoAssess.sh"
    LOG_FILE_EXTENSION = '.log'
    LOG_FILES_TO_RETAIN = 15
    MAX_LOG_FILES_ALLOWED = 40

    # Environment variables
    SEQ_NO_ENVIRONMENT_VAR = "ConfigSequenceNumber"
    CORE_MODULE = "Core"
    EXTENSION_MODULE = "Extension"

    # Max runtime for specific commands in minutes
    ENABLE_MAX_RUNTIME = 3
    DISABLE_MAX_RUNTIME = 13

    # Telemetry Settings
    # Note: these limits are based on number of characters as confirmed with agent team
    TELEMETRY_MSG_SIZE_LIMIT_IN_CHARS = 3072
    TELEMETRY_EVENT_SIZE_LIMIT_IN_CHARS = 6144
    TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = 4194304
    TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = 41943040
    TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_CHARS = 25  # buffer for the chars dropped text added at the end of the truncated telemetry message

    TELEMETRY_ENABLED_AT_EXTENSION = True
    TELEMETRY_AT_AGENT_NOT_COMPATIBLE_ERROR_MSG = "The minimum Azure Linux Agent version prerequisite for Linux patching was not met. Please update the Azure Linux Agent on this machine following instructions here: http://aka.ms/UpdateLinuxAgent"
    TELEMETRY_AT_AGENT_COMPATIBLE_MSG = "The minimum Azure Linux Agent version prerequisite for Linux patching was met."

    AZURE_GUEST_AGENT_EXTENSION_SUPPORTED_FEATURES_ENV_VAR = 'AZURE_GUEST_AGENT_EXTENSION_SUPPORTED_FEATURES'
    TELEMETRY_EXTENSION_PIPELINE_SUPPORTED_KEY = 'ExtensionTelemetryPipeline'

    # Telemetry Event Level
    class TelemetryEventLevel(EnumBackport):
        Critical = "Critical"
        Error = "Error"
        Warning = "Warning"
        Verbose = "Verbose"
        Informational = "Informational"
        LogAlways = "LogAlways"

    TELEMETRY_TASK_NAME = "Handler"

    UTC_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    # Re-try limit for file operations
    MAX_IO_RETRIES = 5

    # Re-try limit for verifying core process has started successfully
    MAX_PROCESS_STATUS_CHECK_RETRIES = 5

    # Operations
    NOOPERATION = "NoOperation"
    PATCH_NOOPERATION_SUMMARY = "PatchNoOperationSummary"
    ASSESSMENT = "Assessment"
    PATCH_ASSESSMENT_SUMMARY = "PatchAssessmentSummary"
    INSTALLATION = "Installation"
    PATCH_INSTALLATION_SUMMARY = "PatchInstallationSummary"
    CONFIGURE_PATCHING = "ConfigurePatching"
    CONFIGURE_PATCHING_SUMMARY = "ConfigurePatchingSummary"

    # Handler actions
    ENABLE = "Enable"
    UPDATE = "Update"
    RESET = "Reset"
    INSTALL = "Install"
    UNINSTALL = "Uninstall"
    DISABLE = "Disable"

    # Settings for Error Objects logged in status file
    STATUS_ERROR_MSG_SIZE_LIMIT_IN_CHARACTERS = 128
    STATUS_ERROR_LIMIT = 5

    class PatchOperationTopLevelErrorCode(EnumBackport):
        SUCCESS = 0
        ERROR = 1

    class PatchOperationErrorCodes(EnumBackport):
        # todo: finalize these error codes
        PACKAGE_MANAGER_FAILURE = "PACKAGE_MANAGER_FAILURE"
        OPERATION_FAILED = "OPERATION_FAILED"
        DEFAULT_ERROR = "ERROR"  # default error code

    ERROR_ADDED_TO_STATUS = "Error_added_to_status"
    PYTHON_NOT_FOUND = "Python version could not be discovered for core invocation."

    # HandlerEnvironment constants
    class EnvSettingsFields(EnumBackport):
        version = "version"
        settings_parent_key = "handlerEnvironment"
        log_folder = "logFolder"
        config_folder = "configFolder"
        status_folder = "statusFolder"
        events_folder = "eventsFolder"
        events_folder_preview = "eventsFolder_preview"
        telemetry_supported = "telemetrySupported"

    # Config Settings json keys
    RUNTIME_SETTINGS = "runtimeSettings"
    HANDLER_SETTINGS = "handlerSettings"
    PUBLIC_SETTINGS = "publicSettings"
    AUTO_ASSESS_ONLY = "autoAssessOnly"

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
        maintenance_run_id = "maintenanceRunId"
        health_store_id = "healthStoreId"
        patch_mode = "patchMode"
        assessment_mode = 'assessmentMode'
        maximum_assessment_interval = 'maximumAssessmentInterval'

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
        substatus_errors = "errors"

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
        UnsupportedOperatingSystem = 51
        MissingDependency = 52
        ConfigurationError = 53
        BadHandlerEnvironmentFile = 81
        UnableToReadStatusFile = 82
        CreateFileLoggerFailure = 83
        ReadingAndDeserializingConfigFileFailure = 84
        InvalidConfigSettingPropertyValue = 85
        CreateLoggerFailure = 86
        CreateStatusWriterFailure = 87
        HandlerFailed = 88
        MissingConfig = 89
        OperationNotSupported = 90

    class AgentEnvVarStatusCode(EnumBackport):
        AGENT_ENABLED = "AGENT_ENABLED"
        FAILED_TO_GET_AGENT_SUPPORTED_FEATURES = "FAILED_TO_GET_AGENT_SUPPORTED_FEATURES"
        FAILED_TO_GET_TELEMETRY_KEY = "FAILED_TO_GET_TELEMETRY_KEY"
