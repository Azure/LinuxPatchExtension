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

    # Runtime environments
    TEST = 'Test'
    DEV = 'Dev'
    PROD = 'Prod'
    LPE_ENV_VARIABLE = "LPE_ENV"    # Overrides environment setting

    # Execution Arguments
    ARG_SEQUENCE_NUMBER = '-sequenceNumber'
    ARG_ENVIRONMENT_SETTINGS = "-environmentSettings"
    ARG_CONFIG_SETTINGS = "-configSettings"
    ARG_PROTECTED_CONFIG_SETTINGS = "-protectedConfigSettings"
    ARG_INTERNAL_RECORDER_ENABLED = "-recorderEnabled"
    ARG_INTERNAL_EMULATOR_ENABLED = "-emulatorEnabled"

    class EnvSettings(EnumBackport):
        LOG_FOLDER = "logFolder"
        CONFIG_FOLDER = "configFolder"
        STATUS_FOLDER = "statusFolder"

    class ConfigSettings(EnumBackport):
        OPERATION = 'operation'
        ACTIVITY_ID = 'activityId'
        START_TIME = 'startTime'
        MAXIMUM_DURATION = 'maximumDuration'
        REBOOT_SETTING = 'rebootSetting'
        CLASSIFICATIONS_TO_INCLUDE = 'classificationsToInclude'
        PATCHES_TO_INCLUDE = 'patchesToInclude'
        PATCHES_TO_EXCLUDE = 'patchesToExclude'
        PATCH_ROLLOUT_ID = 'patchRolloutId'

    # Operations
    ASSESSMENT = "Assessment"
    INSTALLATION = "Installation"
    PATCH_ASSESSMENT_SUMMARY = "PatchAssessmentSummary"
    PATCH_INSTALLATION_SUMMARY = "PatchInstallationSummary"
    PATCH_METADATA_FOR_HEALTHSTORE = "PatchMetadataForHealthStore"

    # patch versions for healthstore when there is no patch rollout id
    PATCH_VERSION_UNKNOWN = "UNKNOWN"

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

    UNKNOWN_PACKAGE_SIZE = "Unknown"
    PACKAGE_STATUS_REFRESH_RATE_IN_SECONDS = 10
    MAX_FILE_OPERATION_RETRY_COUNT = 5
    MAX_ASSESSMENT_RETRY_COUNT = 5
    MAX_INSTALLATION_RETRY_COUNT = 3

    # Package Classifications
    PACKAGE_CLASSIFICATIONS = {
        0: 'Unclassified',           # doesn't serve a functional purpose in bit mask, but stands in for 'All' in code
        1: 'Critical',
        2: 'Security',
        4: 'Other'
    }
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
        # todo: finalize these error codes
        PACKAGE_MANAGER_FAILURE = "PACKAGE_MANAGER_FAILURE"
        OPERATION_FAILED = "OPERATION_FAILED"
        DEFAULT_ERROR = "ERROR"  # default error code

    ERROR_ADDED_TO_STATUS = "Error_added_to_status"

    # Telemetry Categories
    TELEMETRY_OPERATION_STATE = "State"
    TELEMETRY_CONFIG = "Config"
    TELEMETRY_PACKAGE = "PackageInfo"
    TELEMETRY_ERROR = "Error"
    TELEMETRY_INFO = "Info"
    TELEMETRY_DEBUG = "Debug"

    # EnvLayer Constants
    class EnvLayer(EnumBackport):
        PRIVILEGED_OP_MARKER = "Privileged_Op_e6df678d-d09b-436a-a08a-65f2f70a6798"
        PRIVILEGED_OP_REBOOT = PRIVILEGED_OP_MARKER + "Reboot_Exception"
        PRIVILEGED_OP_EXIT = PRIVILEGED_OP_MARKER + "Exit_"
