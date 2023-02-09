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


class Constants(object):
    """Static class contains all constant variables"""
    # Enum Backport to support Enum in python 2.7
    class EnumBackport(object):
        class __metaclass__(type):
            def __iter__(self):
                for item in self.__dict__:
                    if item == self.__dict__[item]:
                        yield item

    DEFAULT_UNSPECIFIED_VALUE = '7d12c6abb5f74eecec4b94e19ac3d418'  # non-colliding default to distinguish between user selection and true default where used
    GLOBAL_EXCLUSION_LIST = ""   # if a package needs to be blocked across all of Azure
    UNKNOWN = "Unknown"

    # Extension version (todo: move to a different file)
    EXT_VERSION = "1.6.41"

    # Runtime environments
    TEST = 'Test'
    DEV = 'Dev'
    PROD = 'Prod'
    LPE_ENV_VARIABLE = "LPE_ENV"    # Overrides environment setting

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

    class Paths(EnumBackport):
        SYSTEMD_ROOT = "/etc/systemd/system/"

    class EnvSettings(EnumBackport):
        LOG_FOLDER = "logFolder"
        CONFIG_FOLDER = "configFolder"
        STATUS_FOLDER = "statusFolder"
        EVENTS_FOLDER = "eventsFolder"
        TELEMETRY_SUPPORTED = "telemetrySupported"

    class ConfigSettings(EnumBackport):
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

    # File to save default settings for auto OS updates
    IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH = "ImageDefaultPatchConfiguration.bak"

    # Auto assessment shell script name
    CORE_AUTO_ASSESS_SH_FILE_NAME = "MsftLinuxPatchAutoAssess.sh"
    AUTO_ASSESSMENT_SERVICE_NAME = "MsftLinuxPatchAutoAssess"
    AUTO_ASSESSMENT_SERVICE_DESC = "Microsoft Azure Linux Patch Extension - Auto Assessment"

    # Operations
    AUTO_ASSESSMENT = 'AutoAssessment'
    ASSESSMENT = "Assessment"
    INSTALLATION = "Installation"
    CONFIGURE_PATCHING = "ConfigurePatching"
    CONFIGURE_PATCHING_AUTO_ASSESSMENT = "ConfigurePatching_AutoAssessment"     # only used internally
    PATCH_ASSESSMENT_SUMMARY = "PatchAssessmentSummary"
    PATCH_INSTALLATION_SUMMARY = "PatchInstallationSummary"
    PATCH_METADATA_FOR_HEALTHSTORE = "PatchMetadataForHealthStore"
    CONFIGURE_PATCHING_SUMMARY = "ConfigurePatchingSummary"

    # patch versions for healthstore when there is no maintenance run id
    PATCH_VERSION_UNKNOWN = "UNKNOWN"

    # Strings used in perf logs
    class PerfLogTrackerParams:
        TASK = "task"
        TASK_STATUS = "task_status"
        PACKAGE_MANAGER = "package_manager"
        NUMBER_OF_TRIALS = "number_of_trials"
        ERROR_MSG = "error_msg"
        INSTALLED_PATCH_COUNT = "installed_patch_count"
        PATCH_OPERATION_SUCCESSFUL = "patch_operation_successful"
        MAINTENANCE_WINDOW = "maintenance_window"
        PERC_MAINTENANCE_WINDOW_USED = "perc_maintenance_window_used"
        MAINTENANCE_WINDOW_EXCEEDED = "maintenance_window_exceeded"
        START_TIME = "start_time"
        END_TIME = "end_time"
        TIME_TAKEN = "time_taken"
        MACHINE_INFO = "machine_info"
        MESSAGE = "message"

    class TaskStatus(EnumBackport):
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    # Patch Modes for Configure Patching
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

    # List of auto OS update services in Yum
    # todo: move to yumpackagemanager
    class YumAutoOSUpdateServices(EnumBackport):
        YUM_CRON = "yum-cron"
        DNF_AUTOMATIC = "dnf-automatic"
        PACKAGEKIT = "packagekit"

    # auto assessment states
    class AutoAssessmentStates(EnumBackport):
        UNKNOWN = "Unknown"
        ERROR = "Error"
        DISABLED = "Disabled"
        ENABLED = "Enabled"

    # To separately preserve assessment + auto-assessment state information
    ASSESSMENT_STATE_FILE = "AssessmentState.json"
    AUTO_ASSESSMENT_MAXIMUM_DURATION = "PT1H"
    MIN_AUTO_ASSESSMENT_INTERVAL = "PT6H"   # do not perform auto-assessment if the last assessment happened less than this time interval ago

    # wait time after status updates
    WAIT_TIME_AFTER_HEALTHSTORE_STATUS_UPDATE_IN_SECS = 20

    # Status file states
    STATUS_TRANSITIONING = "Transitioning"
    STATUS_ERROR = "Error"
    STATUS_SUCCESS = "Success"
    STATUS_WARNING = "Warning"

    # Wrapper-core handshake files
    EXT_STATE_FILE = 'ExtState.json'
    CORE_STATE_FILE = 'CoreState.json'

    # Operating System distributions
    UBUNTU = 'Ubuntu'
    RED_HAT = 'Red Hat'
    SUSE = 'SUSE'
    CENTOS = 'CentOS'

    # Package Managers
    APT = 'apt'
    YUM = 'yum'
    ZYPPER = 'zypper'

    # Package Statuses
    INSTALLED = 'Installed'
    FAILED = 'Failed'
    EXCLUDED = 'Excluded'        # explicitly excluded
    PENDING = 'Pending'
    NOT_SELECTED = 'NotSelected'  # implicitly not installed as it wasn't explicitly included
    AVAILABLE = 'Available'      # assessment only

    UA_ESM_REQUIRED = "UA_ESM_Required"

    UNKNOWN_PACKAGE_SIZE = "Unknown"
    PACKAGE_STATUS_REFRESH_RATE_IN_SECONDS = 10
    MAX_FILE_OPERATION_RETRY_COUNT = 5
    MAX_ASSESSMENT_RETRY_COUNT = 5
    MAX_INSTALLATION_RETRY_COUNT = 3
    MAX_IMDS_CONNECTION_RETRY_COUNT = 5
    MAX_ZYPPER_REPO_REFRESH_RETRY_COUNT = 5
    PATCHING_BATCH_SIZE = 3

    class PackageClassification(EnumBackport):
        UNCLASSIFIED = 'Unclassified'
        CRITICAL = 'Critical'
        SECURITY = 'Security'
        OTHER = 'Other'

    PKG_MGR_SETTING_FILTER_CRITSEC_ONLY = 'FilterCritSecOnly'
    PKG_MGR_SETTING_IDENTITY = 'PackageManagerIdentity'
    PKG_MGR_SETTING_IGNORE_PKG_FILTER = 'IgnorePackageFilter'

    # Reboot Manager
    REBOOT_NEVER = 'Never reboot'
    REBOOT_IF_REQUIRED = 'Reboot if required'
    REBOOT_ALWAYS = 'Always reboot'
    REBOOT_SETTINGS = {  # API to exec-code mapping (+incl. validation)
        'Never': REBOOT_NEVER,
        'IfRequired': REBOOT_IF_REQUIRED,
        'Always': REBOOT_ALWAYS
    }
    REBOOT_BUFFER_IN_MINUTES = 15
    REBOOT_WAIT_TIMEOUT_IN_MINUTES = 5

    # Installation Reboot Statuses
    class RebootStatus(EnumBackport):
        NOT_NEEDED = "NotNeeded"
        REQUIRED = "Required"
        STARTED = "Started"
        COMPLETED = "Completed"
        FAILED = "Failed"
    
    # Enum for VM Cloud Type
    class VMCloudType(EnumBackport):
        UNKNOWN = "Unknown"
        AZURE = "Azure"
        ARC = "Arc"

    IMDS_END_POINT = "http://169.254.169.254/metadata/instance/compute?api-version=2019-06-01"

    # StartedBy Patch Assessment Summary Status Values
    class PatchAssessmentSummaryStartedBy(EnumBackport):
        USER = "User"
        PLATFORM = "Platform"

    # Maintenance Window
    PACKAGE_INSTALL_EXPECTED_MAX_TIME_IN_MINUTES = 5

    # Package Manager Setting
    PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION = "RepeatUpdateRun"

    # Settings for Error Objects logged in status file
    STATUS_ERROR_MSG_SIZE_LIMIT_IN_CHARACTERS = 128
    STATUS_ERROR_LIMIT = 5

    class PatchOperationTopLevelErrorCode(EnumBackport):
        SUCCESS = 0
        ERROR = 1

    class PatchOperationErrorCodes(EnumBackport):
        DEFAULT_ERROR = "ERROR"  # default error code
        OPERATION_FAILED = "OPERATION_FAILED"
        PACKAGE_MANAGER_FAILURE = "PACKAGE_MANAGER_FAILURE"
        NEWER_OPERATION_SUPERSEDED = "NEWER_OPERATION_SUPERSEDED"

    ERROR_ADDED_TO_STATUS = "Error_added_to_status"

    TELEMETRY_ENABLED_AT_EXTENSION = True

    # Telemetry Settings
    # Note: these limits are based on number of characters as confirmed with agent team
    TELEMETRY_MSG_SIZE_LIMIT_IN_CHARS = 3072
    TELEMETRY_EVENT_SIZE_LIMIT_IN_CHARS = 6144
    TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = 4194304
    TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = 41943040
    TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_CHARS = 25  # buffer for the chars dropped text added at the end of the truncated telemetry message
    TELEMETRY_EVENT_COUNTER_MSG_SIZE_LIMIT_IN_CHARS = 15  # buffer for telemetry event counter text added at the end of every message sent to telemetry
    TELEMETRY_MAX_EVENT_COUNT_THROTTLE = 60
    TELEMETRY_MAX_TIME_IN_SECONDS_FOR_EVENT_COUNT_THROTTLE = 60

    # Telemetry Event Level
    class TelemetryEventLevel(EnumBackport):
        Critical = "Critical"
        Error = "Error"
        Warning = "Warning"
        Verbose = "Verbose"
        Informational = "Informational"
        LogAlways = "LogAlways"

    # Telemetry Task Names for disambiguation
    class TelemetryTaskName(EnumBackport):
        UNKNOWN = "Core.Unknown"                     # function parameter default
        STARTUP = "Core.Startup"                     # initial value until execution mode is determined
        EXEC = "Core.Exec"                           # mainline execution triggered from handler
        AUTO_ASSESSMENT = "Core.AutoAssessment"      # auto-assessment triggered from scheduler

    TELEMETRY_NOT_COMPATIBLE_ERROR_MSG = "Unsupported older Azure Linux Agent version. To resolve: http://aka.ms/UpdateLinuxAgent"
    TELEMETRY_COMPATIBLE_MSG = "Minimum Azure Linux Agent version prerequisite met"

    UTC_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    # EnvLayer Constants
    class EnvLayer(EnumBackport):
        PRIVILEGED_OP_MARKER = "Privileged_Op_e6df678d-d09b-436a-a08a-65f2f70a6798"
        PRIVILEGED_OP_REBOOT = PRIVILEGED_OP_MARKER + "Reboot_Exception"
        PRIVILEGED_OP_EXIT = PRIVILEGED_OP_MARKER + "Exit_"

    # Package / Patch State Ordering Constants
    # This ordering ensures that the most important information is preserved in the case of patch object truncation
    PackageClassificationOrderInStatusReporting = {
        PackageClassification.SECURITY: 1,
        PackageClassification.CRITICAL: 2,
        PackageClassification.OTHER: 3,
        PackageClassification.UNCLASSIFIED: 4
    }

    PatchStateOrderInStatusReporting = {
        FAILED: 1,
        INSTALLED: 2,
        AVAILABLE: 3,
        PENDING: 4,
        EXCLUDED: 5,
        NOT_SELECTED: 6
    }

