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
import datetime


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
    EXT_VERSION = "1.6.62"

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
    MAX_RETRY_ATTEMPTS_FOR_ERROR_MITIGATION = 10

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
    TEMP_FOLDER_CLEANUP_ARTIFACT_LIST = ["*.list", "azgps*"]

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
    AUTO_ASSESSMENT_MAXIMUM_DURATION = "PT1H"           # maximum time assessment is expected to take
    AUTO_ASSESSMENT_CRON_INTERVAL = "PT1H"              # wake up to check for persistent assessment information this frequently
    AUTO_ASSESSMENT_INTERVAL_BUFFER = "PT1H"            # allow for an hour's buffer from max interval passed down (PT6H) to keep within "max" SLA

    # wait time after status updates
    WAIT_TIME_AFTER_HEALTHSTORE_STATUS_UPDATE_IN_SECS = 20

    # Status file states
    STATUS_TRANSITIONING = "Transitioning"
    STATUS_ERROR = "Error"
    STATUS_SUCCESS = "Success"
    STATUS_WARNING = "Warning"

    # Status file size
    class StatusTruncationConfig(EnumBackport):
        INTERNAL_FILE_SIZE_LIMIT_IN_BYTES = 126 * 1024
        AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES = 128 * 1024
        MIN_ASSESSMENT_PATCHES_TO_RETAIN = 5
        TRUNCATION_WARNING_MESSAGE = "Package lists were truncated to limit reporting data volume. In-VM logs contain complete lists."
        TURN_ON_TRUNCATION = True
        MIN_TRUNCATION_INTERVAL_IN_SEC = 60
        EPOCH = datetime.datetime(1971, 1, 1, 0, 0, 0)

    # Wrapper-core handshake files
    EXT_STATE_FILE = 'ExtState.json'
    CORE_STATE_FILE = 'CoreState.json'

    # Operating System distributions
    UBUNTU = 'Ubuntu'
    RED_HAT = 'Red Hat'
    SUSE = 'SUSE'
    CENTOS = 'CentOS'
    AZURE_LINUX = ['Microsoft Azure Linux', 'Common Base Linux Mariner']

    # Package Managers
    APT = 'apt'
    TDNF = 'tdnf'
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
    MAX_COMPLETE_STATUS_FILES_TO_RETAIN = 10
    SET_CHECK_SUDO_STATUS_TRUE = True
    MAX_CHECK_SUDO_ATTEMPTS = 6
    MAX_CHECK_SUDO_INTERVAL_IN_SEC = 300

    class PackageBatchConfig(EnumBackport):
        # Batch Patching Parameters
        MAX_BATCH_SIZE_FOR_PACKAGES = 300
        MAX_PHASES_FOR_BATCH_PATCHING = 2

        # Batch size decay factor is factor to which batch size is decreased in batch patching to install remaining packages in case there
        # are some package install failures with original batch size.
        BATCH_SIZE_DECAY_FACTOR = 10

        # We need to keep some buffer time between calculation of batch size and starting batch patching because after calculating the batch size,
        # there would be little time taken before the batch patching is started. The function is_package_install_time_available is called before installing a batch.
        # If we do not keep buffer then is_package_install_time_available would return false.
        BUFFER_TIME_FOR_BATCH_PATCHING_START_IN_MINUTES = 5

    class PackageClassification(EnumBackport):
        UNCLASSIFIED = 'Unclassified'
        CRITICAL = 'Critical'
        SECURITY = 'Security'
        SECURITY_ESM = 'Security-ESM'
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
    REBOOT_BUFFER_IN_MINUTES = 15                # minimum MW time required to consider rebooting if required (notify - 3, wait - 7, machine - 5)
    REBOOT_NOTIFY_WINDOW_IN_MINUTES = 3          # time to broadcast reboot notification to other processes as part of the reboot command
    REBOOT_WAIT_TIMEOUT_IN_MINUTES_MIN = 7       # minimum time to wait for a reboot to have started in the current execution context
    REBOOT_WAIT_TIMEOUT_IN_MINUTES_MAX = 40      # maximum possible** time to wait for a reboot to have started in the current execution context (**IF MW time remaining allows it)
    REBOOT_TO_MACHINE_READY_TIME_IN_MINUTES = 5  # time to wait for the machine to be ready after a reboot actually happens
    REBOOT_WAIT_PULSE_INTERVAL_IN_SECONDS = 60   # time to wait between checks for reboot completion

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
        WARNING = 2

    class PatchOperationErrorCodes(EnumBackport):
        INFORMATIONAL = "INFORMATIONAL"
        DEFAULT_ERROR = "ERROR"  # default error code
        OPERATION_FAILED = "OPERATION_FAILED"
        PACKAGE_MANAGER_FAILURE = "PACKAGE_MANAGER_FAILURE"
        NEWER_OPERATION_SUPERSEDED = "NEWER_OPERATION_SUPERSEDED"
        UA_ESM_REQUIRED = "UA_ESM_REQUIRED"
        TRUNCATION = "PACKAGE_LIST_TRUNCATED"

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
    TELEMETRY_MAX_EVENT_COUNT_THROTTLE = 360
    TELEMETRY_MAX_TIME_IN_SECONDS_FOR_EVENT_COUNT_THROTTLE = 300

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
    PYTHON_NOT_COMPATIBLE_ERROR_MSG = "Unsupported older Python version. Minimum Python version required is 2.7. [DetectedPythonVersion={0}]"
    INFO_STRICT_SDP_SUCCESS = "Success: Safely patched your VM in a AzGPS-coordinated global rollout. https://aka.ms/AzGPS/StrictSDP [Target={0}]"
    UTC_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    # EnvLayer Constants
    class EnvLayer(EnumBackport):
        PRIVILEGED_OP_MARKER = "Privileged_Op_e6df678d-d09b-436a-a08a-65f2f70a6798"
        PRIVILEGED_OP_REBOOT = PRIVILEGED_OP_MARKER + "Reboot_Exception"
        PRIVILEGED_OP_EXIT = PRIVILEGED_OP_MARKER + "Exit_"

    # Supported Package Architectures - if this is changed, review TdnfPackageManager and YumPackageManager
    SUPPORTED_PACKAGE_ARCH = ['.x86_64', '.noarch', '.i686', '.aarch64']

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
        FAILED: 1,
        INSTALLED: 2,
        AVAILABLE: 3,
        PENDING: 4,
        EXCLUDED: 5,
        NOT_SELECTED: 6
    }

    # Ubuntu Pro Client constants.
    class UbuntuProClientSettings(EnumBackport):
        FEATURE_ENABLED = True
        MINIMUM_PYTHON_VERSION_REQUIRED = (3, 5)  # using tuple as we can compare this with sys.version_info. The comparison will happen in the same order. Major version checked first. Followed by Minor version.
        MAX_OS_MAJOR_VERSION_SUPPORTED = 24
        MINIMUM_CLIENT_VERSION = "27.14.4"

    class BufferMessage(EnumBackport):
        TRUE = 0
        FALSE = 1
        FLUSH = 2
