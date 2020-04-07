import os


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
