# Copyright 2020 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.7+


class Constants(object):
    """Static class contains all constant variables"""
    # Enum Backport to support Enum in python 2.7
    class EnumBackport(object):
        class __metaclass__(type):
            def __iter__(self):
                for item in self.__dict__:
                    if item == self.__dict__[item]:
                        yield item

    class ExecEnv(EnumBackport):
        DEV = 'Dev'
        TEST = 'Test'
        PROD = 'Prod'

    class ExitCode(EnumBackport):
        Okay = 0
        CriticalError = 1
        CriticalError_NoLog = 2
        CriticalError_NoStatus = 3
        CriticalError_Reported = 4

    DEFAULT_UNSPECIFIED_VALUE = '7d12c6abb5f74eecec4b94e19ac3d418'  # non-colliding default to distinguish between user selection and true default where used
    
    AZGPS_LPE_VERSION = "[%exec_ver%]"
    AZGPS_LPE_ENVIRONMENT_VAR = "AZPGS_LPE_ENV"    # Overrides environment setting

    class BufferMessage(EnumBackport):
        TRUE = 0
        FALSE = 1
        FLUSH = 2

    # Execution Arguments
    ARG_SEQUENCE_NUMBER = '-sequenceNumber'
    ARG_ENVIRONMENT_SETTINGS = "-environmentSettings"
    ARG_CONFIG_SETTINGS = "-configSettings"
    ARG_AUTO_ASSESS_ONLY = "-autoAssessOnly"
    ARG_PROTECTED_CONFIG_SETTINGS = "-protectedConfigSettings"
    ARG_INTERNAL_RECORDER_ENABLED = "-recorderEnabled"
    ARG_INTERNAL_EMULATOR_ENABLED = "-emulatorEnabled"

    # Max values
    MAX_AUTO_ASSESSMENT_LOGFILE_SIZE_IN_BYTES = 5*1024*1024
    MAX_AUTO_ASSESSMENT_WAIT_FOR_MAIN_CORE_EXEC_IN_MINUTES = 3 * 60
    UTC_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    class Config(EnumBackport):
        AZGPS_PACKAGE_EXCLUSION_LIST = ""  # if a package needs to be blocked across all of Azure
        IMDS_END_POINT = "http://169.254.169.254/metadata/instance/compute?api-version=2019-06-01"
        PACKAGE_INSTALL_EXPECTED_MAX_TIME_IN_MINUTES = 5
        REBOOT_BUFFER_IN_MINUTES = 15
        REBOOT_WAIT_TIMEOUT_IN_MINUTES = 5
        STATUS_ERROR_MSG_SIZE_LIMIT_IN_CHARACTERS = 128
        STATUS_ERROR_LIMIT = 5
        LIFECYCLE_MANAGER_STATUS_CHECK_WAIT_IN_SECS = 30

    class SystemPaths(EnumBackport):
        SYSTEMD_ROOT = "/etc/systemd/system/"

    class AzGPSPaths(EnumBackport):
        EULA_SETTINGS = "/var/lib/azure/linuxpatchextension/patch.eula.settings"

    class EnvSettings(EnumBackport):
        LOG_FOLDER = "logFolder"
        CONFIG_FOLDER = "configFolder"
        STATUS_FOLDER = "statusFolder"
        EVENTS_FOLDER = "eventsFolder"
        TEMP_FOLDER = "tempFolder"
        TELEMETRY_SUPPORTED = "telemetrySupported"

    class ConfigSettings(EnumBackport):
        CLOUD_TYPE = 'cloudType'
        OPERATION = 'operation'
        ACTIVITY_ID = 'activityId'
        START_TIME = 'startTime'
        MAXIMUM_DURATION = 'maximumDuration'
        REBOOT_SETTING = 'rebootSetting'
        CLASSIFICATIONS_TO_INCLUDE = 'classificationsToInclude'
        PATCHES_TO_INCLUDE = 'patchesToInclude'
        PATCHES_TO_EXCLUDE = 'patchesToExclude'
        MAINTENANCE_RUN_ID = 'maintenanceRunId'
        HEALTH_STORE_ID = 'healthStoreId'
        PATCH_MODE = 'patchMode'
        ASSESSMENT_MODE = 'assessmentMode'
        MAXIMUM_ASSESSMENT_INTERVAL = 'maximumAssessmentInterval'

    class EulaSettings(EnumBackport):
        ACCEPT_EULA_FOR_ALL_PATCHES = 'AcceptEULAForAllPatches'
        ACCEPTED_BY = 'AcceptedBy'
        LAST_MODIFIED = 'LastModified'

    TEMP_FOLDER_DIR_NAME = "tmp"
    TEMP_FOLDER_CLEANUP_ARTIFACT_LIST = ["*.list"]

    # Auto assessment shell script name
    CORE_AUTO_ASSESS_SH_FILE_NAME = "AzGPSLinuxPatchAutoAssess.sh"
    AUTO_ASSESSMENT_SERVICE_NAME = "AzGPSLinuxPatchAutoAssess"
    AUTO_ASSESSMENT_SERVICE_DESC = "Azure Guest Patching Service - Auto Assessment"

    # Operations
    class Op(EnumBackport):
        # NO_OPERATION = "NoOperation"     # not used in Core
        CONFIGURE_PATCHING = "ConfigurePatching"
        CONFIGURE_PATCHING_AUTO_ASSESSMENT = "ConfigurePatching_AutoAssessment"  # only used internally
        ASSESSMENT = "Assessment"
        INSTALLATION = "Installation"

    class OpSummary(EnumBackport):
        # NO_OPERATION = "PatchNoOperationSummary"      # not used in Core
        CONFIGURE_PATCHING = "ConfigurePatchingSummary"
        ASSESSMENT = "PatchAssessmentSummary"
        INSTALLATION = "PatchInstallationSummary"
        PATCH_METADATA_FOR_HEALTHSTORE = "PatchMetadataForHealthStore"

    # patch versions for healthstore when there is no maintenance run id
    PATCH_VERSION_UNKNOWN = "UNKNOWN"

    # Strings used in perf logs
    class PerfLogTrackerParams(EnumBackport):
        TASK = "Task"
        TASK_STATUS = "TaskStatus"
        PACKAGE_MANAGER = "PackageManager"
        RETRY_COUNT = "RetryCount"
        ERROR_MSG = "ErrorMsg"
        INSTALLED_PATCH_COUNT = "InstalledPatchCount"
        PATCH_OPERATION_SUCCESSFUL = "PatchOperationSuccessful"
        MAINTENANCE_WINDOW = "MaintenanceWindow"
        MAINTENANCE_WINDOW_USED_PERCENT = "MaintenanceWindowUsedPercent"
        MAINTENANCE_WINDOW_EXCEEDED = "MaintenanceWindowExceeded"
        START_TIME = "StartTime"
        END_TIME = "EndTime"
        TIME_TAKEN_IN_SECS = "TimeTakenInSecs"
        MACHINE_INFO = "MachineInfo"
        MESSAGE = "Message"

    class TaskStatus(EnumBackport):
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    # region - Configure Patching
    class PatchModes(EnumBackport):
        IMAGE_DEFAULT = "ImageDefault"
        AUTOMATIC_BY_PLATFORM = "AutomaticByPlatform"

    class AssessmentModes(EnumBackport):
        IMAGE_DEFAULT = "ImageDefault"
        AUTOMATIC_BY_PLATFORM = "AutomaticByPlatform"

    # automatic OS patch states for configure patching
    class AutomaticOSPatchStates(EnumBackport):
        UNKNOWN = "Unknown"
        DISABLED = "Disabled"
        ENABLED = "Enabled"

    class AutoAssessmentStates(EnumBackport):
        UNKNOWN = "Unknown"
        ERROR = "Error"
        DISABLED = "Disabled"
        ENABLED = "Enabled"

    # File to save default settings for auto OS updates
    IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH = "ImageDefaultPatchConfiguration.bak"

    class YumAutoOSUpdateServices(EnumBackport):
        YUM_CRON = "yum-cron"
        DNF_AUTOMATIC = "dnf-automatic"
        PACKAGEKIT = "packagekit"
    # endregion - Configure Patching

    # To separately preserve assessment + auto-assessment state information

    AUTO_ASSESSMENT_MAXIMUM_DURATION = "PT1H"           # maximum time assessment is expected to take
    AUTO_ASSESSMENT_CRON_INTERVAL = "PT1H"              # wake up to check for persistent assessment information this frequently
    AUTO_ASSESSMENT_INTERVAL_BUFFER = "PT1H"            # allow for an hour's buffer from max interval passed down (PT6H) to keep within "max" SLA

    # wait time after status updates
    WAIT_TIME_AFTER_HEALTHSTORE_STATUS_UPDATE_IN_SECS = 20

    # Wrapper-core handshake files
    class StateFiles(EnumBackport):
        EXT = 'ExtState.json'
        CORE = 'CoreState.json'
        ASSESSMENT = "AssessmentState.json"
        HEARTBEAT = "Heartbeat.json"

    # Package Managers
    APT = 'apt'
    YUM = 'yum'
    ZYPPER = 'zypper'

    class Status(EnumBackport):
        TRANSITIONING = "Transitioning"
        SUCCESS = "Success"
        ERROR = "Error"
        WARNING = "Warning"

    # Package Statuses
    class PackageStatus(EnumBackport):
        INSTALLED = "Installed"
        FAILED = "Failed"
        EXCLUDED = "Excluded"               # explicitly excluded
        PENDING = "Pending"
        NOT_SELECTED = "NotSelected"        # implicitly not installed as it wasn't explicitly included
        AVAILABLE = "Available"             # assessment only, but unused as it's implicit when we don't do inventory

    class PackageClassification(EnumBackport):
        UNCLASSIFIED = 'Unclassified'
        CRITICAL = 'Critical'
        SECURITY = 'Security'
        SECURITY_ESM = 'Security-ESM'
        OTHER = 'Other'

    UA_ESM_REQUIRED = "UA_ESM_Required"

    UNKNOWN_PACKAGE_SIZE = "Unknown"
    PACKAGE_STATUS_REFRESH_RATE_IN_SECONDS = 10
    MAX_FILE_OPERATION_RETRY_COUNT = 5
    MAX_PATCH_OPERATION_RETRY_COUNT = 5
    MAX_ASSESSMENT_RETRY_COUNT = 5
    MAX_INSTALLATION_RETRY_COUNT = 3
    MAX_IMDS_CONNECTION_RETRY_COUNT = 5
    MAX_ZYPPER_REPO_REFRESH_RETRY_COUNT = 5
    MAX_BATCH_SIZE_FOR_PACKAGES = 3
    MAX_COMPLETE_STATUS_FILES_TO_RETAIN = 10

    # region Telemetry related
    class TelemetryConfig(EnumBackport):
        """ Telemetry limits that are imposed by the Azure Linux Agent """
        MSG_SIZE_LIMIT_IN_CHARS = 3072
        EVENT_SIZE_LIMIT_IN_CHARS = 6144
        EVENT_FILE_SIZE_LIMIT_IN_CHARS = 4194304
        DIR_SIZE_LIMIT_IN_CHARS = 41943040
        BUFFER_FOR_DROPPED_COUNT_MSG_IN_CHARS = 25          # buffer for the chars dropped text added at the end of the truncated telemetry message
        EVENT_COUNTER_MSG_SIZE_LIMIT_IN_CHARS = 15          # buffer for telemetry event counter text added at the end of every message sent to telemetry
        MAX_EVENT_COUNT_THROTTLE = 72                       # increased by Agent team for AzGPS in 2023 (up from 60)
        MAX_TIME_IN_SECONDS_FOR_EVENT_COUNT_THROTTLE = 60

    class TelemetryTaskName(EnumBackport):
        UNKNOWN = "Core.Unknown"                     # function parameter default
        STARTUP = "Core.Startup"                     # initial value until execution mode is determined
        EXEC = "Core.Exec"                           # mainline execution triggered from handler
        AUTO_ASSESSMENT = "Core.AutoAssessment"      # auto-assessment triggered from scheduler

    class EventLevel(EnumBackport):
        # Critical = "Critical"         # unused by AzGPS
        Error = "Error"
        Warning = "Warning"
        Info = "Informational"
        Debug = "Debug"
        Verbose = "Verbose"             # do not log to telemetry - AzGPS override
        # LogAlways = "LogAlways"       # unused by AzGPS
    # endregion Telemetry related

    class RebootSettings(EnumBackport):
        NEVER = "Never"                 # Never reboot
        IF_REQUIRED = "IfRequired"      # Reboot if required
        ALWAYS = "Always"               # Reboot at least once

    # region Internal constants
    class CloudType(EnumBackport):
        UNKNOWN = "Unknown"
        AZURE = "Azure"
        ARC = "Arc"

    # Package Manager Setting
    PKG_MGR_SETTING_IDENTITY = 'PackageManagerIdentity'
    PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION = "RepeatUpdateRun"
    ERROR_ADDED_TO_STATUS = "Error_added_to_status"

    # EnvLayer Constants
    class EnvLayer(EnumBackport):
        PRIVILEGED_OP_MARKER = "Privileged_Op_e6df678d-d09b-436a-a08a-65f2f70a6798"
        PRIVILEGED_OP_REBOOT = PRIVILEGED_OP_MARKER + "Reboot_Exception"
        PRIVILEGED_OP_EXIT = PRIVILEGED_OP_MARKER + "Exit_"
    # endregion Internal constants

    # region Status Handler constants
    class PatchOperationTopLevelErrorCode(EnumBackport):
        SUCCESS = 0
        ERROR = 1

    class PatchOperationErrorCodes(EnumBackport):
        """ Error codes for significant errors. CL_ = Client error, SV_ = Service error. Others = specialized errors. """
        INFO = "INFO"  # informational message; no error
        DEFAULT_ERROR = "ERROR"  # default error code
        OPERATION_FAILED = "OPERATION_FAILED"
        CL_PYTHON_TOO_OLD = "CL_PYTHON_TOO_OLD"
        CL_SUDO_CHECK_FAILED = "CL_SUDO_CHECK_FAILED"
        CL_AGENT_TOO_OLD = "CL_AGENT_TOO_OLD"
        CL_PACKAGE_MANAGER_FAILURE = "CL_PACKAGE_MANAGER_FAILURE"
        CL_NEWER_OPERATION_SUPERSEDED = "CL_NEWER_OPERATION_SUPERSEDED"
        CL_SYSTEMD_NOT_PRESENT = "CL_SYSTEMD_NOT_PRESENT"
        SV_MAINTENANCE_WINDOW_ERROR = "SV_MAINTENANCE_WINDOW_ERROR"
        PATCH_MODE_SET_FAILURE = "PATCH_MODE_SET_FAILURE"
        UA_ESM_REQUIRED = "UA_ESM_REQUIRED"

    class Errors(EnumBackport):
        UNHANDLED_EXCEPTION = "Severe unhandled exception. [Error={0}]"
        PYTHON_NOT_COMPATIBLE = "Unsupported older Python version. Minimum Python version required is 2.7. [DetectedPythonVersion={0}]"
        SUDO_FAILURE = "Sudo status check failed. Please ensure the computer is configured correctly for sudo invocation."
        NO_TELEMETRY_SUPPORT_AT_AGENT = "Unsupported older Azure Linux Agent version. To resolve: https://aka.ms/UpdateLinuxAgent"
        MINIMUM_REQUIREMENTS_NOT_MET = "Minimum requirements for patch operation execution were not met. [PythonNotCompatible={0}][SudoFailure={1}][OldAgentVersion={2}]"
        INVALID_REBOOT_SETTING = "Invalid reboot setting. Resetting to default. [RequestedRebootSetting={0}][DefaultRebootSetting={1}]"
        SYSTEMD_NOT_PRESENT = "Systemd is not available on this system, and platform-based auto-assessment cannot be configured."
        INSTALLATION_FAILED_DUE_TO_ASSESSMENT_FAILURE = "Patch installation failed due to assessment failure. Please refer to the error details in the assessment substatus."

    # Installation Reboot Statuses
    class RebootStatus(EnumBackport):
        NOT_NEEDED = "NotNeeded"
        REQUIRED = "Required"
        STARTED = "Started"
        COMPLETED = "Completed"
        FAILED = "Failed"

    # StartedBy Patch Assessment Summary Status Values
    class PatchAssessmentSummaryStartedBy(EnumBackport):
        USER = "User"
        PLATFORM = "Platform"

    # Package / Patch State Ordering Constants
    # This ordering ensures that the most important information is preserved in the case of patch object truncation
    PackageClassificationOrderInStatusReporting = {
        PackageClassification.CRITICAL: 1,
        PackageClassification.SECURITY: 2,
        PackageClassification.SECURITY_ESM: 3,
        PackageClassification.OTHER: 4,
        PackageClassification.UNCLASSIFIED: 5
    }

    PatchStateOrderInStatusReporting = {
        PackageStatus.FAILED: 1,
        PackageStatus.INSTALLED: 2,
        PackageStatus.AVAILABLE: 3,
        PackageStatus.PENDING: 4,
        PackageStatus.EXCLUDED: 5,
        PackageStatus.NOT_SELECTED: 6
    }
    # endregion Status Handler constants



    # Ubuntu Pro Client constants.
    class UbuntuProClientSettings(EnumBackport):
        FEATURE_ENABLED = True
        MINIMUM_PYTHON_VERSION_REQUIRED = (3, 5)  # using tuple as we can compare this with sys.version_info. The comparison will happen in the same order. Major version checked first. Followed by Minor version.
        MAX_OS_MAJOR_VERSION_SUPPORTED = 18
        MINIMUM_CLIENT_VERSION = "27.14.4"

