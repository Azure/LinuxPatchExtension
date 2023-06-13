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

import glob
import json
import os
import re
import shutil
import time
from core.src.bootstrap.Constants import Constants
from collections import OrderedDict


class StatusHandler(object):
    """Class for managing the core code's lifecycle within the extension wrapper"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, vm_cloud_type):
        # Map supporting components for operation
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer  # not used immediately but need to know if there are issues persisting status
        self.complete_status_file_path = self.execution_config.complete_status_file_path
        self.status_file_path = self.execution_config.status_file_path
        self.__log_file_path = self.execution_config.log_file_path
        self.vm_cloud_type = vm_cloud_type

        # Status components
        self.__high_level_status_message = ""

        # Internal in-memory representation of Patch Installation data
        self.__installation_substatus_json = None
        self.__installation_summary_json = None
        self.__installation_packages = []
        self.__installation_errors = []
        self.__installation_total_error_count = 0  # All errors during install, includes errors not in error objects due to size limit
        self.__maintenance_window_exceeded = False
        self.__installation_reboot_status = Constants.RebootStatus.NOT_NEEDED

        # Internal in-memory representation of Patch Assessment data
        self.__assessment_substatus_json = None
        self.__assessment_summary_json = None
        self.__assessment_packages = []
        self.__assessment_errors = []
        self.__assessment_total_error_count = 0  # All errors during assess, includes errors not in error objects due to size limit
        self.__assessment_packages_map = OrderedDict()
        self.__assessment_truncated_removed = []

        # Internal in-memory representation of Patch Metadata for HealthStore
        self.__metadata_for_healthstore_substatus_json = None
        self.__metadata_for_healthstore_summary_json = None
        self.__report_to_healthstore = False
        self.__patch_version = Constants.PATCH_VERSION_UNKNOWN

        # Internal in-memory representation of Configure Patching data
        self.__configure_patching_substatus_json = None
        self.__configure_patching_summary_json = None
        self.__configure_patching_errors = []
        self.__configure_patching_top_level_error_count = 0  # All errors during configure patching (excluding auto-assessment), includes errors not in error objects due to size limit
        self.__configure_patching_auto_assessment_errors = []
        self.__configure_patching_auto_assessment_error_count = 0  # All errors relating to auto-assessment configuration.

        # Load the currently persisted status file into memory
        self.load_status_file_components(initial_load=True)

        # Tracker for reboot pending status, the value is updated externally(PatchInstaller.py) whenever package is installed. As this var is directly written in status file, setting the default to False, instead of Empty/Unknown, to maintain a true bool field as per Agent team's architecture
        self.is_reboot_pending = False

        # Discovers OS name and version for package id composition
        self.__os_name_and_version = self.get_os_name_and_version()

        self.__current_operation = None

        # Update patch metadata summary in status for auto patching installation requests, to be reported to healthstore
        if (execution_config.maintenance_run_id is not None or execution_config.health_store_id is not None) and execution_config.operation.lower() == Constants.INSTALLATION.lower():
            if self.__installation_reboot_status != Constants.RebootStatus.STARTED:
                self.set_patch_metadata_for_healthstore_substatus_json(report_to_healthstore=True, wait_after_update=True)
                # updating metadata summary again with reporting to healthstore turned off
                self.set_patch_metadata_for_healthstore_substatus_json(report_to_healthstore=False, wait_after_update=False)
            else:
                self.composite_logger.log_debug("Since this is the previous patch operation re-triggered after a reboot, healthstore has the operation commencement details. "
                                                "So, not sending another report to healthstore")

        # Enable reboot completion status capture
        if self.__installation_reboot_status == Constants.RebootStatus.STARTED:
            self.set_installation_reboot_status(Constants.RebootStatus.COMPLETED)  # switching to completed after the reboot

    # region - Package Data
    def reset_assessment_data(self):
        """ Externally available method to wipe out any assessment package records in memory. """
        self.__assessment_substatus_json = None
        self.__assessment_summary_json = None
        self.__assessment_packages = []
        self.__assessment_errors = []
        self.__assessment_total_error_count = 0
        self.__assessment_truncated_removed = []
        self.__assessment_packages_map = OrderedDict()

    def set_package_assessment_status(self, package_names, package_versions, classification="Other", status="Available"):
        """ Externally available method to set assessment status for one or more packages of the **SAME classification and status** """
        self.composite_logger.log_debug("Setting package assessment status in bulk. [Count={0}]".format(str(len(package_names))))
        for package_name, package_version in zip(package_names, package_versions):
            patch_already_saved = False
            patch_id = self.__get_patch_id(package_name, package_version)

            # Lazy initialization, getting None when initialize in __init__
            if self.__assessment_packages_map is None:
                self.__assessment_packages_map = OrderedDict()
            # Match patch_id in map and update existing patch's classification i.e from other -> security
            if len(self.__assessment_packages_map) > 0 and patch_id in self.__assessment_packages_map:
                self.__assessment_packages_map.setdefault(patch_id, {})['classifications'] = [classification]
                patch_already_saved = True

            if patch_already_saved is False:
                record = {
                    "patchId": str(patch_id),
                    "name": str(package_name),
                    "version": str(package_version),
                    "classifications": [classification]
                    # "patchState": str(status) # Allows for capturing 'Installed' packages in addition to 'Available', when commented out, if spec changes
                }
                # Add new patch to map
                self.__assessment_packages_map[patch_id] = record

        self.__assessment_packages = list(self.__assessment_packages_map.values())
        self.__assessment_packages = self.sort_packages_by_classification_and_state(self.__assessment_packages)
        self.set_assessment_substatus_json()

    def sort_packages_by_classification_and_state(self, packages_list):
        """ Sorts a list of packages (usually either self.__assessment_packages or self.__installation_packages) by classification and patchState properties.
            (sorting order from highest priority to lowest):
            1. Classification: Critical, Security, Other, Unclassified
            2. Patch Installation State: Failed, Installed, Available, Pending, Excluded, NotSelected
        """
        def sort_patch_state_key(x):
            # Only for installation result packages
            if "patchInstallationState" in x.keys():
                return Constants.PatchStateOrderInStatusReporting[x["patchInstallationState"]]
            else:
                return 0

        def sort_classification_key(x):
            lowest_classification = Constants.PackageClassificationOrderInStatusReporting[x["classifications"][0]]
            for i in range(1, len(x["classifications"])):
                lowest_classification = min(lowest_classification, Constants.PackageClassificationOrderInStatusReporting[x["classifications"][i]])
            return lowest_classification

        # Sort by patch state first then sort by classification so each type of classification is already sorted at the end
        list_sorted_by_patch_state = sorted(packages_list, key=sort_patch_state_key)
        list_sorted_by_classification = sorted(list_sorted_by_patch_state, key=sort_classification_key)
        # COMMENT: these sort calls can be combined into one by separating the value ranges in the tables above, such as classification_order to 100, 200, 300, etc
        # and having one key function that combines the result of classification_order and patch_state_order
        return list_sorted_by_classification

    def set_package_install_status(self, package_names, package_versions, status="Pending", classification=None):
        """ Externally available method to set installation status for one or more packages of the **SAME classification and status** """
        self.composite_logger.log_debug("Setting package installation status in bulk. [Count={0}]".format(str(len(package_names))))
        package_names, package_versions = self.validate_packages_being_installed(package_names, package_versions)
        package_install_status_summary = ""

        for package_name, package_version in zip(package_names, package_versions):
            patch_already_saved = False
            patch_id = self.__get_patch_id(package_name, package_version)
            for i in range(0, len(self.__installation_packages)):
                if patch_id == self.__installation_packages[i]['patchId']:
                    patch_already_saved = True
                    if classification is not None:
                        self.__installation_packages[i]['classifications'] = [classification]
                    self.__installation_packages[i]['patchInstallationState'] = status

            if patch_already_saved is False:
                if classification is None:
                    classification = Constants.PackageClassification.OTHER
                record = {
                    "patchId": str(patch_id),
                    "name": str(package_name),
                    "version": str(package_version),
                    "classifications": [classification],
                    "patchInstallationState": str(status)
                }
                self.__installation_packages.append(record)

            package_install_status_summary += "[P={0},V={1}] ".format(str(package_name), str(package_version))

        self.composite_logger.log_debug("Package install status summary [Status= " + status + "] : " + package_install_status_summary)
        self.__installation_packages = self.sort_packages_by_classification_and_state(self.__installation_packages)
        self.set_installation_substatus_json()

    @staticmethod
    def validate_packages_being_installed(package_names, package_versions):
        # Data normalization and corruption guards - if these exceptions hit, a bug has been introduced elsewhere
        if isinstance(package_names, str) != isinstance(package_versions, str):
            raise Exception("Internal error: Package name and version data corruption detected.")
        if isinstance(package_names, str):
            package_names, package_versions = [package_names], [package_versions]
        if len(package_names) != len(package_versions):
            raise Exception("Internal error: Bad package name and version data received for status reporting. [Names={0}][Versions={1}]".format(str(len(package_names)), str(len(package_versions))))
        return package_names, package_versions

    def set_package_install_status_classification(self, package_names, package_versions, classification=None):
        """ Externally available method to set classification for one or more packages being installed """
        if classification is None:
            self.composite_logger.log_debug("Classification not provided for the set of packages being installed. [Package Count={0}]".format(str(len(package_names))))
            return

        self.validate_packages_being_installed(package_names, package_versions)

        self.composite_logger.log_debug("Setting package installation classification in bulk. [Count={0}]".format(str(len(package_names))))
        package_classification_summary = ""
        for package_name, package_version in zip(package_names, package_versions):
            classification_matching_package_found = False
            patch_id = self.__get_patch_id(package_name, package_version)
            for i in range(0, len(self.__installation_packages)):
                if patch_id == self.__installation_packages[i]['patchId']:
                    classification_matching_package_found = True
                    self.__installation_packages[i]['classifications'] = [classification]
            package_classification_summary += "[P={0},V={1},C={2}] ".format(str(package_name), str(package_version), str(classification if classification is not None and classification_matching_package_found else "-"))

        self.composite_logger.log_debug("Package install status summary (classification): " + package_classification_summary)
        self.__installation_packages = self.sort_packages_by_classification_and_state(self.__installation_packages)
        self.set_installation_substatus_json()

    def __get_patch_id(self, package_name, package_version):
        """ Returns normalized patch id """
        return "{0}_{1}_{2}".format(str(package_name), str(package_version), self.__os_name_and_version)

    def get_os_name_and_version(self):
        try:
            if self.env_layer.platform.system() != "Linux":
                raise Exception("Unsupported OS type: {0}.".format(self.env_layer.platform.system()))
            platform_info = self.env_layer.platform.linux_distribution()
            return "{0}_{1}".format(platform_info[0], platform_info[1])
        except Exception as error:
            self.composite_logger.log_error("Unable to determine platform information: {0}".format(repr(error)))
            return "unknownDist_unknownVer"
    # endregion

    # region - Installation Reboot Status
    def get_installation_reboot_status(self):
        """ Safe retrieval of currently stored reboot status (stateful) """
        return self.__installation_reboot_status

    def set_installation_reboot_status(self, new_reboot_status):
        """ Valid reboot statuses: NotNeeded, Required, Started, Failed, Completed """
        if new_reboot_status not in [Constants.RebootStatus.NOT_NEEDED, Constants.RebootStatus.REQUIRED, Constants.RebootStatus.STARTED, Constants.RebootStatus.FAILED, Constants.RebootStatus.COMPLETED]:
            raise "Invalid reboot status specified. [Status={0}]".format(str(new_reboot_status))

        # State transition validation
        if (new_reboot_status == Constants.RebootStatus.NOT_NEEDED and self.__installation_reboot_status not in [Constants.RebootStatus.NOT_NEEDED])\
                or (new_reboot_status == Constants.RebootStatus.REQUIRED and self.__installation_reboot_status not in [Constants.RebootStatus.NOT_NEEDED, Constants.RebootStatus.REQUIRED, Constants.RebootStatus.COMPLETED])\
                or (new_reboot_status == Constants.RebootStatus.STARTED and self.__installation_reboot_status not in [Constants.RebootStatus.NOT_NEEDED, Constants.RebootStatus.REQUIRED, Constants.RebootStatus.STARTED])\
                or (new_reboot_status == Constants.RebootStatus.FAILED and self.__installation_reboot_status not in [Constants.RebootStatus.STARTED, Constants.RebootStatus.FAILED])\
                or (new_reboot_status == Constants.RebootStatus.COMPLETED and self.__installation_reboot_status not in [Constants.RebootStatus.STARTED, Constants.RebootStatus.COMPLETED]):
            self.composite_logger.log_error("Invalid reboot status transition attempted. [CurrentRebootStatus={0}] [NewRebootStatus={1}]".format(self.__installation_reboot_status, str(new_reboot_status)))
            return

        # Persisting new reboot status (with machine state incorporation)
        self.composite_logger.log_debug("Setting new installation reboot status. [NewRebootStatus={0}] [CurrentRebootStatus={1}]".format(str(new_reboot_status), self.__installation_reboot_status))
        self.__installation_reboot_status = new_reboot_status
        self.set_installation_substatus_json()

    def __refresh_installation_reboot_status(self):
        """ Discovers if the system needs a reboot. Never allows going back to NotNeeded (deliberate). ONLY called internally. """
        self.composite_logger.log_debug("Checking if reboot status needs to reflect machine reboot status.")
        if self.__installation_reboot_status in [Constants.RebootStatus.NOT_NEEDED, Constants.RebootStatus.COMPLETED]:
            # Checks only if it's a state transition we allow
            reboot_needed = self.is_reboot_pending
            if reboot_needed:
                self.composite_logger.log_debug("Machine reboot status has changed to 'Required'.")
                self.__installation_reboot_status = Constants.RebootStatus.REQUIRED

    def set_reboot_pending(self, is_reboot_pending):
        log_message = "Setting reboot pending status. [RebootPendingStatus={0}]".format(str(is_reboot_pending))
        self.composite_logger.log_debug(log_message)
        self.is_reboot_pending = is_reboot_pending
    # endregion

    # region - Terminal state management
    def report_sequence_number_changed_termination(self):
        """ Based on the current operation, adds an error status and sets the substatus to error """
        current_operation = self.execution_config.operation.lower()
        error_code = Constants.PatchOperationErrorCodes.NEWER_OPERATION_SUPERSEDED
        message = "Execution was stopped due to a newer operation taking precedence."

        if current_operation == Constants.ASSESSMENT.lower() or self.execution_config.exec_auto_assess_only:
            self.add_error_to_status(message, error_code, current_operation_override_for_error=Constants.ASSESSMENT)
            self.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
        elif current_operation == Constants.CONFIGURE_PATCHING.lower() or current_operation == Constants.CONFIGURE_PATCHING_AUTO_ASSESSMENT.lower():
            self.add_error_to_status(message, error_code, current_operation_override_for_error=Constants.CONFIGURE_PATCHING)
            self.add_error_to_status(message, error_code, current_operation_override_for_error=Constants.CONFIGURE_PATCHING_AUTO_ASSESSMENT)
            self.set_configure_patching_substatus_json(status=Constants.STATUS_ERROR)
        elif current_operation == Constants.INSTALLATION.lower():
            self.add_error_to_status(message, error_code, current_operation_override_for_error=Constants.INSTALLATION)
            self.set_installation_substatus_json(status=Constants.STATUS_ERROR)
    # endregion - Terminal state management

    # region - Substatus generation
    def set_maintenance_window_exceeded(self, maintenance_windows_exceeded):
        self.__maintenance_window_exceeded = maintenance_windows_exceeded
        self.set_installation_substatus_json()

    def set_assessment_substatus_json(self, status=Constants.STATUS_TRANSITIONING, code=0):
        """ Prepare the assessment substatus json including the message containing assessment summary """
        self.composite_logger.log_debug("Setting assessment substatus. [Substatus={0}]".format(str(status)))

        # Wrap patches into assessment summary
        self.__assessment_summary_json = self.__new_assessment_summary_json(self.__assessment_packages, status, code)

        # Wrap assessment summary into assessment substatus
        self.__assessment_substatus_json = self.__new_substatus_json_for_operation(Constants.PATCH_ASSESSMENT_SUMMARY, status, code, json.dumps(self.__assessment_summary_json))

        # Update complete status on disk
        self.__write_complete_status_file()

    def __new_assessment_summary_json(self, assessment_packages_json, status, code):
        """ Called by: set_assessment_substatus_json
            Purpose: This composes the message inside the patch assessment summary substatus:
                Root --> Status --> Substatus [name: "PatchAssessmentSummary"] --> FormattedMessage --> **Message** """

        # Calculate summary
        critsec_patch_count = 0
        other_patch_count = 0
        for i in range(0, len(assessment_packages_json)):
            classifications = assessment_packages_json[i]['classifications']
            if "Critical" in classifications or "Security" in classifications:
                critsec_patch_count += 1
            else:
                other_patch_count += 1

        # discern started by - either pure auto-assessment or assessment data being included with configure patching with assessmentMode set to AutomaticByPlatform
        started_by = Constants.PatchAssessmentSummaryStartedBy.PLATFORM if (self.execution_config.exec_auto_assess_only or self.execution_config.include_assessment_with_configure_patching) else Constants.PatchAssessmentSummaryStartedBy.USER

        # Compose sub-status message
        substatus_message = {
            "assessmentActivityId": str(self.execution_config.activity_id),
            "rebootPending": self.is_reboot_pending,
            "criticalAndSecurityPatchCount": critsec_patch_count,
            "otherPatchCount": other_patch_count,
            "patches": assessment_packages_json,
            "startTime": str(self.execution_config.start_time),
            "lastModifiedTime": str(self.env_layer.datetime.timestamp()),
            "startedBy": str(started_by),
            "errors": self.__set_errors_json(self.__assessment_total_error_count, self.__assessment_errors)
        }

        if self.vm_cloud_type == Constants.VMCloudType.ARC:
            substatus_message["patchAssessmentStatus"] = code
            substatus_message["patchAssessmentStatusString"] = status
        return substatus_message

    def set_installation_substatus_json(self, status=Constants.STATUS_TRANSITIONING, code=0):
        """ Prepare the deployment substatus json including the message containing deployment summary """
        self.composite_logger.log_debug("Setting installation substatus. [Substatus={0}]".format(str(status)))

        # Wrap patches into installation summary
        self.__installation_summary_json = self.__new_installation_summary_json(self.__installation_packages)

        # Wrap deployment summary into installation substatus
        self.__installation_substatus_json = self.__new_substatus_json_for_operation(Constants.PATCH_INSTALLATION_SUMMARY, status, code, json.dumps(self.__installation_summary_json))

        # Update complete status on disk
        self.__write_complete_status_file()

    def __new_installation_summary_json(self, installation_packages_json):
        """ Called by: set_installation_substatus_json
            Purpose: This composes the message inside the patch installation summary substatus:
                Root --> Status --> Substatus [name: "PatchInstallationSummary"] --> FormattedMessage --> **Message** """

        # Calculate summary
        not_selected_patch_count = 0
        excluded_patch_count = 0
        pending_patch_count = 0
        installed_patch_count = 0
        failed_patch_count = 0
        for i in range(0, len(installation_packages_json)):
            patch_installation_state = installation_packages_json[i]['patchInstallationState']
            if patch_installation_state == Constants.NOT_SELECTED:
                not_selected_patch_count += 1
            elif patch_installation_state == Constants.EXCLUDED:
                excluded_patch_count += 1
            elif patch_installation_state == Constants.PENDING:
                pending_patch_count += 1
            elif patch_installation_state == Constants.INSTALLED:
                installed_patch_count += 1
            elif patch_installation_state == Constants.FAILED:
                failed_patch_count += 1
            else:
                self.composite_logger.log_error("Unknown patch state recorded: {0}".format(str(patch_installation_state)))

        # Reboot status refresh
        self.__refresh_installation_reboot_status()

        # Compose substatus message
        return {
            "installationActivityId": str(self.execution_config.activity_id),
            "rebootStatus": str(self.__installation_reboot_status),
            "maintenanceWindowExceeded": self.__maintenance_window_exceeded,
            "notSelectedPatchCount": not_selected_patch_count,
            "excludedPatchCount": excluded_patch_count,
            "pendingPatchCount": pending_patch_count,
            "installedPatchCount": installed_patch_count,
            "failedPatchCount": failed_patch_count,
            "patches": installation_packages_json,
            "startTime": str(self.execution_config.start_time),
            "lastModifiedTime": str(self.env_layer.datetime.timestamp()),
            "maintenanceRunId": str(self.execution_config.maintenance_run_id) if self.execution_config.maintenance_run_id is not None else '',
            "errors": self.__set_errors_json(self.__installation_total_error_count, self.__installation_errors)
        }

    def set_patch_metadata_for_healthstore_substatus_json(self, status=Constants.STATUS_SUCCESS, code=0, patch_version=Constants.PATCH_VERSION_UNKNOWN, report_to_healthstore=False, wait_after_update=False):
        """ Prepare the healthstore substatus json including message containing summary to be sent to healthstore """
        if self.execution_config.exec_auto_assess_only:
            raise Exception("Auto-assessment mode. Unexpected attempt to update healthstore status.")

        self.composite_logger.log_debug("Setting patch metadata for healthstore substatus. [Substatus={0}] [Report to HealthStore={1}]".format(str(status), str(report_to_healthstore)))

        # Wrap patch metadata into healthstore summary
        self.__metadata_for_healthstore_summary_json = self.__new_patch_metadata_for_healthstore_json(patch_version, report_to_healthstore)

        # Wrap healthstore summary into healthstore substatus
        self.__metadata_for_healthstore_substatus_json = self.__new_substatus_json_for_operation(Constants.PATCH_METADATA_FOR_HEALTHSTORE, status, code, json.dumps(self.__metadata_for_healthstore_summary_json))

        # Update complete status on disk
        self.__write_complete_status_file()

        # wait period required in cases where we need to ensure HealthStore reads the status from GA
        if wait_after_update:
            time.sleep(Constants.WAIT_TIME_AFTER_HEALTHSTORE_STATUS_UPDATE_IN_SECS)

    def __new_patch_metadata_for_healthstore_json(self, patch_version=Constants.PATCH_VERSION_UNKNOWN, report_to_healthstore=False):
        """ Called by: set_patch_metadata_for_healthstore_substatus_json
            Purpose: This composes the message inside the patch metadata for healthstore substatus:
                Root --> Status --> Substatus [name: "PatchMetadataForHealthStore"] --> FormattedMessage --> **Message** """

        # Compose substatus message
        return {
            "patchVersion": str(patch_version),
            "shouldReportToHealthStore": report_to_healthstore
        }

    def set_configure_patching_substatus_json(self, status=Constants.STATUS_TRANSITIONING, code=0,
                                              automatic_os_patch_state=Constants.AutomaticOSPatchStates.UNKNOWN,
                                              auto_assessment_state=Constants.AutoAssessmentStates.UNKNOWN):
        """ Prepare the configure patching substatus json including the message containing configure patching summary """
        if self.execution_config.exec_auto_assess_only:
            raise Exception("Auto-assessment mode. Unexpected attempt to update configure patching status.")

        self.composite_logger.log_debug("Setting configure patching substatus. [Substatus={0}]".format(str(status)))

        # Wrap default automatic OS patch state on the machine, at the time of this request, into configure patching summary
        self.__configure_patching_summary_json = self.__new_configure_patching_summary_json(automatic_os_patch_state, auto_assessment_state, status, code)

        # Wrap configure patching summary into configure patching substatus
        self.__configure_patching_substatus_json = self.__new_substatus_json_for_operation(Constants.CONFIGURE_PATCHING_SUMMARY, status, code, json.dumps(self.__configure_patching_summary_json))

        # Update complete status on disk
        self.__write_complete_status_file()

    def __new_configure_patching_summary_json(self, automatic_os_patch_state, auto_assessment_state, status, code):
        """ Called by: set_configure_patching_substatus_json
            Purpose: This composes the message inside the configure patching summary substatus:
                Root --> Status --> Substatus [name: "ConfigurePatchingSummary"] --> FormattedMessage --> **Message** """

        # Compose substatus message
        substatus_message = {
            "activityId": str(self.execution_config.activity_id),
            "startTime": str(self.execution_config.start_time),
            "lastModifiedTime": str(self.env_layer.datetime.timestamp()),
            "automaticOSPatchState": automatic_os_patch_state,
            "autoAssessmentStatus": {
                "autoAssessmentState": auto_assessment_state,
                "errors": self.__set_errors_json(self.__configure_patching_auto_assessment_error_count, self.__configure_patching_auto_assessment_errors)
            },
            "errors": self.__set_errors_json(self.__configure_patching_top_level_error_count, self.__configure_patching_errors)
        }
        if self.vm_cloud_type == Constants.VMCloudType.ARC:
            substatus_message["configurePatchStatus"] = code
            substatus_message["configurePatchStatusString"] = status
        return substatus_message

    @staticmethod
    def __new_substatus_json_for_operation(operation_name, status="Transitioning", code=0, message=json.dumps("{}")):
        """ Generic substatus for assessment, installation, configurepatching and healthstore metadata """
        return {
            "name": str(operation_name),
            "status": str(status).lower(),
            "code": code,
            "formattedMessage": {
                "lang": "en-US",
                "message": str(message)
            }
        }
    # endregion

    # region - Status generation
    def __reset_status_file(self):
        status_file_reset_content = json.dumps(self.__new_basic_status_json())
        # Create complete status template
        self.env_layer.file_system.write_with_retry(self.complete_status_file_path, '[{0}]'.format(status_file_reset_content), mode='w+')
        # Create agent-facing status template
        self.env_layer.file_system.write_with_retry(self.status_file_path, '[{0}]'.format(status_file_reset_content), mode='w+')

    def __new_basic_status_json(self):
        return {
            "version": 1.0,
            "timestampUTC": str(self.env_layer.datetime.timestamp()),
            "status": {
                "name": "Azure Patch Management",
                "operation": str(self.execution_config.operation),
                "status": "success",
                "code": 0,
                "formattedMessage": {
                    "lang": "en-US",
                    "message": ""
                },
                "substatus": []
            }
        }
    # endregion

    # region - Status file read/write
    @staticmethod
    def __json_try_get_key_value(json_body, key, default_value=""):
        """ Returns the value associated with the specified key in the json passed in. If not found, the specified default is returned. """
        try:
            return json.loads(json_body)[key]
        except KeyError:
            return default_value

    def load_status_file_components(self, initial_load=False):
        """ Loads currently persisted status data into memory.
        :param initial_load: If no status file exists AND initial_load is true, a default initial status file is created.
        :return: None
        """

        # Initializing records safely
        self.__installation_substatus_json = None
        self.__installation_summary_json = None
        self.__installation_packages = []
        self.__installation_errors = []

        self.__assessment_substatus_json = None
        self.__assessment_summary_json = None
        self.__assessment_packages = []
        self.__assessment_errors = []
        self.__assessment_packages_map = None

        self.__metadata_for_healthstore_substatus_json = None
        self.__metadata_for_healthstore_summary_json = None

        self.__configure_patching_substatus_json = None
        self.__configure_patching_summary_json = None
        self.__configure_patching_errors = []
        self.__configure_patching_auto_assessment_errors = []

        self.composite_logger.log_debug("Loading status file components [InitialLoad={0}].".format(str(initial_load)))

        # Verify the complete status file exists - if not, reset complete status file
        if os.path.isdir(self.complete_status_file_path):
            self.composite_logger.log_error("Core state file path returned a directory. Attempting to reset.")
            shutil.rmtree(self.complete_status_file_path)
        if not os.path.exists(self.complete_status_file_path) and initial_load:
            self.composite_logger.log_warning("Status file not found at initial load. Resetting status file to defaults.")
            self.__reset_status_file()
            return

        # Read the complete status file - raise exception on persistent failure
        # Remove old complete status files and retain latest version
        latest_complete_status_file_path = self.__get_latest_complete_status_file_path(self.execution_config.status_folder)
        status_file_data_raw = self.__read_complete_status_file_raw_data(latest_complete_status_file_path)

        # Load status data and sanity check structure - raise exception if data loss risk is detected on corrupt data
        try:
            status_file_data = status_file_data_raw
            if 'status' not in status_file_data or 'substatus' not in status_file_data['status']:
                self.composite_logger.log_error("Malformed status file. Resetting status file for safety.")
                self.__reset_status_file()
                return
        except Exception as error:
            self.composite_logger.log_error("Unable to load status file json. Error: {0}; Data: {1}".format(repr(error), str(status_file_data_raw)))
            raise

        # Load portions of data that need to be built on for next write - raise exception if corrupt data is encountered
        # todo: refactor
        self.__high_level_status_message = status_file_data['status']['formattedMessage']['message']
        for i in range(0, len(status_file_data['status']['substatus'])):
            name = status_file_data['status']['substatus'][i]['name']
            if name == Constants.PATCH_INSTALLATION_SUMMARY:     # if it exists, it must be to spec, or an exception will get thrown
                if self.execution_config.exec_auto_assess_only:
                    self.__installation_substatus_json = status_file_data['status']['substatus'][i]
                else:
                    message = status_file_data['status']['substatus'][i]['formattedMessage']['message']
                    self.__installation_summary_json = json.loads(message)
                    self.__installation_packages = self.__installation_summary_json['patches']
                    self.__maintenance_window_exceeded = bool(self.__installation_summary_json['maintenanceWindowExceeded'])
                    self.__installation_reboot_status = self.__installation_summary_json['rebootStatus']
                    errors = self.__installation_summary_json['errors']
                    if errors is not None and errors['details'] is not None:
                        self.__installation_errors = errors['details']
                        self.__installation_total_error_count = self.__get_total_error_count_from_prev_status(errors['message'])
            if name == Constants.PATCH_ASSESSMENT_SUMMARY:     # if it exists, it must be to spec, or an exception will get thrown
                message = status_file_data['status']['substatus'][i]['formattedMessage']['message']
                self.__assessment_summary_json = json.loads(message)
                # Reload patches into assessment ordered map for fast look up
                self.__assessment_packages_map = OrderedDict((package["patchId"], package) for package in self.__assessment_summary_json['patches'])
                self.__assessment_packages = list(self.__assessment_packages_map.values())
                errors = self.__assessment_summary_json['errors']
                if errors is not None and errors['details'] is not None:
                    self.__assessment_errors = errors['details']
                    self.__assessment_total_error_count = self.__get_total_error_count_from_prev_status(errors['message'])
            if name == Constants.PATCH_METADATA_FOR_HEALTHSTORE:     # if it exists, it must be to spec, or an exception will get thrown
                if self.execution_config.exec_auto_assess_only:
                    self.__metadata_for_healthstore_substatus_json = status_file_data['status']['substatus'][i]
                else:
                    message = status_file_data['status']['substatus'][i]['formattedMessage']['message']
                    self.__metadata_for_healthstore_summary_json = json.loads(message)
            if name == Constants.CONFIGURE_PATCHING_SUMMARY:     # if it exists, it must be to spec, or an exception will get thrown
                if self.execution_config.exec_auto_assess_only:
                    self.__configure_patching_substatus_json = status_file_data['status']['substatus'][i]
                else:
                    message = status_file_data['status']['substatus'][i]['formattedMessage']['message']
                    self.__configure_patching_summary_json = json.loads(message)
                    errors = self.__configure_patching_summary_json['errors']
                    if errors is not None and errors['details'] is not None:
                        self.__configure_patching_errors = errors['details']
                        self.__configure_patching_top_level_error_count = self.__get_total_error_count_from_prev_status(errors['message'])

    def __write_complete_status_file(self):
        """ Composes and writes the status file from **already up-to-date** in-memory data.
            This is usually the final call to compose and persist after an in-memory data update in a specialized method.
            Pseudo-composition (including steps prior):
            [__new_basic_status_json()]
                assessment_substatus_json == set_assessment_substatus_json()
                    __new_substatus_json_for_operation()
                    __new_assessment_summary_json() with external data --
                        assessment_packages
                        errors
                installation_substatus_json == set_installation_substatus_json
                    __new_substatus_json_for_operation
                    __new_installation_summary_json with external data --
                        installation_packages
                        maintenance_window_exceeded
                        __refresh_installation_reboot_status
                        errors
                patch_metadata_for_healthstore_json = set_patch_metadata_for_healthstore_substatus_json
                    __new_substatus_json_for_operation
                    __metadata_for_healthstore_summary_json with external data --
                        patchVersion
                        shouldReportToHealthStore
                configure_patching_substatus_json == set_configure_patching_substatus_json
                    __new_substatus_json_for_operation
                    __new_configure_patching_summary_json with external data --
                        automatic_os_patch_state
                        auto_assessment_status
                            auto_assessment_state
                            errors
                        errors
        :return: None
        """
        status_file_payload = self.__new_basic_status_json()
        status_file_payload['status']['formattedMessage']['message'] = str(self.__high_level_status_message)

        if self.__assessment_substatus_json is not None:
            status_file_payload['status']['substatus'].append(self.__assessment_substatus_json)
        if self.__installation_substatus_json is not None:
            status_file_payload['status']['substatus'].append(self.__installation_substatus_json)
        if self.__metadata_for_healthstore_substatus_json is not None:
            status_file_payload['status']['substatus'].append(self.__metadata_for_healthstore_substatus_json)
        if self.__configure_patching_substatus_json is not None:
            status_file_payload['status']['substatus'].append(self.__configure_patching_substatus_json)
        if os.path.isdir(self.complete_status_file_path):
            self.composite_logger.log_error("Core state file path returned a directory. Attempting to reset.")
            shutil.rmtree(self.complete_status_file_path)

        # Write complete status file <seq.no>.complete
        self.env_layer.file_system.write_with_retry_using_temp_file(self.complete_status_file_path, '[{0}]'.format(json.dumps(status_file_payload)), mode='w+')

        complete_status_file = self.__read_complete_status_file_raw_data(self.complete_status_file_path)

        # Write truncated status file
        self.__write_truncated_status_file(complete_status_file)
    # endregion

    # region - Error objects
    def set_current_operation(self, operation):
        if self.execution_config.exec_auto_assess_only and operation != Constants.ASSESSMENT:
            raise Exception("Status reporting for a non-assessment operation was attempted when executing in auto-assessment mode. [Operation={0}]".format(str(operation)))
        self.__current_operation = operation

    def get_current_operation(self):
        return self.__current_operation

    def __get_total_error_count_from_prev_status(self, error_message):
        try:
            return int(re.search('(.+?) error/s reported.', error_message).group(1))
        except AttributeError:
            self.composite_logger.log("Unable to fetch error count from error message reported in status. Attempted to read [Message={0}]".format(error_message))
            return 0

    def add_error_to_status(self, message, error_code=Constants.PatchOperationErrorCodes.DEFAULT_ERROR, current_operation_override_for_error=Constants.DEFAULT_UNSPECIFIED_VALUE):
        """ Add error to the respective error objects """
        if not message or Constants.ERROR_ADDED_TO_STATUS in message:
            return

        # Compose error detail
        error_detail = self.__set_error_detail(error_code, message)

        # determine if a current operation override has been requested
        current_operation = self.__current_operation if current_operation_override_for_error == Constants.DEFAULT_UNSPECIFIED_VALUE else current_operation_override_for_error

        if current_operation == Constants.ASSESSMENT:
            if self.__try_add_error(self.__assessment_errors, error_detail):
                self.__assessment_total_error_count += 1
                # retain previously set status and code for assessment substatus
                if self.__assessment_substatus_json is not None:
                    self.set_assessment_substatus_json(status=self.__assessment_substatus_json["status"], code=self.__assessment_substatus_json["code"])
                else:
                    self.set_assessment_substatus_json()
        elif current_operation == Constants.INSTALLATION:
            if self.__try_add_error(self.__installation_errors, error_detail):
                self.__installation_total_error_count += 1
                # retain previously set status and code for installation substatus
                if self.__installation_substatus_json is not None:
                    self.set_installation_substatus_json(status=self.__installation_substatus_json["status"], code=self.__installation_substatus_json["code"])
                else:
                    self.set_installation_substatus_json()
        elif current_operation == Constants.CONFIGURE_PATCHING or current_operation == Constants.CONFIGURE_PATCHING_AUTO_ASSESSMENT:
            if current_operation == Constants.CONFIGURE_PATCHING_AUTO_ASSESSMENT:
                if self.__try_add_error(self.__configure_patching_auto_assessment_errors, error_detail):
                    self.__configure_patching_auto_assessment_error_count += 1
            else:
                if self.__try_add_error(self.__configure_patching_errors, error_detail):
                    self.__configure_patching_top_level_error_count += 1

            # retain previously set status, code, patchMode and assessmentMode for configure patching substatus
            if self.__configure_patching_substatus_json is not None:
                automatic_os_patch_state = json.loads(self.__configure_patching_substatus_json["formattedMessage"]["message"])["automaticOSPatchState"]
                auto_assessment_status = self.__json_try_get_key_value(self.__configure_patching_substatus_json["formattedMessage"]["message"],"autoAssessmentStatus","{}")
                auto_assessment_state = self.__json_try_get_key_value(json.dumps(auto_assessment_status), "autoAssessmentState", Constants.AutoAssessmentStates.UNKNOWN)
                self.set_configure_patching_substatus_json(status=self.__configure_patching_substatus_json["status"], code=self.__configure_patching_substatus_json["code"],
                                                           automatic_os_patch_state=automatic_os_patch_state, auto_assessment_state=auto_assessment_state)
            else:
                self.set_configure_patching_substatus_json()
        else:
            return

    def __ensure_error_message_restriction_compliance(self, full_message):
        """ Removes line breaks, tabs and restricts message to a character limit """
        message_size_limit = Constants.STATUS_ERROR_MSG_SIZE_LIMIT_IN_CHARACTERS
        formatted_message = re.sub(r"\s+", " ", str(full_message))
        return formatted_message[:message_size_limit - 3] + '...' if len(formatted_message) > message_size_limit else formatted_message

    @staticmethod
    def __try_add_error(error_list, detail):
        """ Add formatted error object to given errors list.
            Returns True if a new error was added, False if an error was only updated or not added. """
        for error_detail in error_list:
            if error_detail["message"] in detail["message"]:
                # New error has more details than the existing error of same type
                # Remove existing error and add new one with more details to front of list
                error_list.remove(error_detail)
                error_list.insert(0, detail)
                return False
            elif detail["message"] in error_detail["message"]:
                # All details contained from new message in an existing message already
                return False

        if len(error_list) >= Constants.STATUS_ERROR_LIMIT:
            errors_to_remove = len(error_list) - Constants.STATUS_ERROR_LIMIT + 1
            for x in range(0, errors_to_remove):
                error_list.pop()
        error_list.insert(0, detail)
        return True

    def __set_errors_json(self, error_count_by_operation, errors_by_operation):
        """ Compose the error object json to be added in 'errors' in given operation's summary """
        message = "{0} error/s reported.".format(error_count_by_operation)
        message += " The latest {0} error/s are shared in detail. To view all errors, review this log file on the machine: {1}".format(len(errors_by_operation), self.__log_file_path) if error_count_by_operation > 0 else ""
        return {
            "code": Constants.PatchOperationTopLevelErrorCode.SUCCESS if error_count_by_operation == 0 else Constants.PatchOperationTopLevelErrorCode.ERROR,
            "details": errors_by_operation,
            "message": message
        }

    def __set_error_detail(self, error_code, message):
        formatted_message = self.__ensure_error_message_restriction_compliance(message)
        return {
            "code": str(error_code),
            "message": str(formatted_message)
        }
    # endregion

    # region - Patch Truncation
    def get_assessment_truncated_removed(self):
        return self.__assessment_truncated_removed

    def __write_truncated_status_file(self, status_file_payload):
        """ Truncate the substatus summary patch list when complete status file size is more than 126kb """
        complete_status_byte_size = self.__get_byte_size(status_file_payload)
        truncated_status_file = status_file_payload
        tombstone_truncated_map = {}

        if complete_status_byte_size > Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES:
            self.composite_logger.log_debug("Begin Truncation")
            errors_detail_list = []

            # Truncated assessment patch when operation is not installation
            if self.execution_config.operation != Constants.INSTALLATION and len(self.__assessment_packages) > 0:
                # Perform assessment truncation
                assessment_truncated_packages, truncated_packages_removed = self.__assessment_truncation_helper_func(self.__assessment_packages, Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)

                # Reduce assessment patch byte by escape char (\) byte
                assessment_quote_counts = self.__get_quote_count(assessment_truncated_packages)

                if (assessment_quote_counts + self.__get_byte_size(assessment_truncated_packages) > Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES):
                    assessment_truncated_packages, truncated_packages_quotes_removed = self.__assessment_truncation_helper_func(assessment_truncated_packages, Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES - assessment_quote_counts)
                    truncated_packages_removed = truncated_packages_removed + truncated_packages_quotes_removed

                self.__assessment_truncated_removed.append(self.__set_truncated_package_detail("Assessment", truncated_packages_removed))

            # Populate tombstone classifications map
            for package in truncated_packages_removed:
                classifications = package['classifications'][0]
                tombstone_truncated_map[classifications] = tombstone_truncated_map.get(classifications, 0) + 1

            # Add assessment tombstone record per classification except unclassified
            for tombstone_classification, tombstone_package_count in tombstone_truncated_map.items():
                if not tombstone_classification == Constants.PackageClassification.UNCLASSIFIED:
                    assessment_truncated_packages.append(self.__add_assessment_tombstone_record(tombstone_package_count, tombstone_classification))

            # Check for existing errors before recompose status file payload
            code = self.__assessment_summary_json['errors']['code']
            if code == Constants.PatchOperationTopLevelErrorCode.SUCCESS or code == Constants.PatchOperationTopLevelErrorCode.WARNING:
                truncated_status_file = self.__recompose_truncated_status_payload(truncated_status_file, assessment_truncated_packages, code, errors_detail_list)
                # Update operation status to warning
                truncated_status_file['status']['substatus'][0]['status'] = Constants.STATUS_WARNING.lower()
            else:
                # code == 1 (Error), add everything in the errors['detail'] to errors_detail_list
                errors_detail_list.extend(self.__assessment_summary_json['errors']['details'])
                truncated_status_file = self.__recompose_truncated_status_payload(truncated_status_file, assessment_truncated_packages, code, errors_detail_list)

            self.composite_logger.log_debug("Complete Truncation")

        # Write to status file
        self.env_layer.file_system.write_with_retry_using_temp_file(self.status_file_path, '[{0}]'.format(json.dumps(truncated_status_file)), mode='w+')

    def __assessment_truncation_helper_func(self, package_list, size_limit):
        """ Helper function to split patch list into two, then apply truncation """
        package_list_first_half, package_list_second_half = (package_list[:Constants.StatusTruncationConfig.MIN_TRUNCATED_PACKAGE_COUNT], package_list[Constants.StatusTruncationConfig.MIN_TRUNCATED_PACKAGE_COUNT:]) if len(package_list) > 5 else (package_list, [])
        capacity = size_limit - self.__get_byte_size(package_list_first_half)
        assessment_truncated_list, truncated_packages, _ = self.__apply_truncation(package_list_second_half, capacity)

        return package_list_first_half + assessment_truncated_list, truncated_packages

    def __apply_truncation(self, package_list, capacity):
        """ Binary search
        Instead of checking list[middel_index] >= target, check byte_size(list[:middle_index]),
        as byte_size[list[:i]] is monotonically increasing, i.e.
        byte_size[list[:1]] < byte_size[list[:2]] < byte_size[list[:3]] ...
        return truncated_list, truncated_packages_removed, and remaining size_limit
        """
        left_index = 0
        right_index = len(package_list) - 1

        if self.__get_byte_size(package_list) <= capacity:
            return package_list, [], capacity - self.__get_byte_size(package_list)

        while left_index < right_index:
            mid_index = left_index + int((right_index - left_index) / 2)
            if self.__get_byte_size(package_list[:mid_index]) >= capacity:
                right_index = mid_index
            else:
                left_index = mid_index + 1

        truncated_list = package_list[:left_index - 1]
        truncated_packages_removed = package_list[left_index - 1:]
        return truncated_list, truncated_packages_removed, capacity - self.__get_byte_size(truncated_list)

    def __read_complete_status_file_raw_data(self, file_path):
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(file_path, 'r') as file_handle:
                    status_file_data_raw = json.load(file_handle)[0]  # structure is array of 1
            except Exception as error:
                if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error(
                        "Unable to read status file (retries exhausted). Error: {0}.".format(repr(error)))
                    raise
        return status_file_data_raw

    def __get_latest_complete_status_file_path(self, status_folder_path):
        """ Get the latest status complete file and remove other .complete.status files """
        list_of_files = glob.glob(status_folder_path + '\\' + '*.complete.status')
        latest_file = max(list_of_files, key=lambda x: (os.path.getmtime(x), int(re.search(r'(\d+)\.complete.status', x).group(1)), x))
        self.composite_logger.log_debug("list of complete status files: {0}".format(list_of_files))

        # Remove older complete.status files
        for file in list_of_files:
            if file != latest_file:
                self.env_layer.file_system.delete_files_from_dir(file, '*.complete.status')

        return os.path.realpath(latest_file)

    def __set_truncated_package_detail(self, name, truncated_package_list):
        """ Compose truncated packages for logging """
        return {
            "name": str.capitalize(name),
            "truncated_packages": truncated_package_list
        }

    def __get_byte_size(self, val):
        """ Get the current byte size of val """
        return len(json.dumps(val).encode("utf-8"))

    def __get_quote_count(self, package_list):
        return sum(char == '"' for char in json.dumps(package_list)) if not len(package_list) == 0 else 0

    def __recompose_truncated_status_payload(self, truncated_status_file, new_patches, code, errors_detail_list):
        """ Recompose complete status file payload with new errors detail list, new errors message, new truncated patches, and Warning status  """
        error_message = Constants.StatusTruncationConfig.TRUNCATION_ERROR_MESSAGE
        truncated_error_detail = self.__set_error_detail(Constants.PatchOperationErrorCodes.TRUNCATION, error_message)
        errors_detail_list.insert(0, truncated_error_detail)

        # Max length of error details is set to 5
        if len(errors_detail_list) > Constants.STATUS_ERROR_LIMIT:
            errors_detail_list = errors_detail_list[:Constants.STATUS_ERROR_LIMIT]

        truncated_errors_json = self.__set_truncation_errors_json(code, errors_detail_list)

        # Update operation summary message
        message = self.__assessment_truncated_message(self.__assessment_summary_json, new_patches, truncated_errors_json)
        truncated_status_file['status']['substatus'][0]['formattedMessage']['message'] = json.dumps(message)

        return truncated_status_file

    def __assessment_truncated_message(self, assessment_message, assessment_truncated_list, truncated_error):
        """ Recompose truncated assessment substatus """
        return {
            "assessmentActivityId": assessment_message["assessmentActivityId"],
            "rebootPending": assessment_message["rebootPending"],
            "criticalAndSecurityPatchCount": assessment_message["criticalAndSecurityPatchCount"],
            "otherPatchCount": assessment_message["otherPatchCount"],
            "patches": assessment_truncated_list,
            "startTime": assessment_message["startTime"],
            "lastModifiedTime": assessment_message["lastModifiedTime"],
            "startedBy": assessment_message["startedBy"],
            "errors": truncated_error
        }

    def __set_truncation_errors_json(self, code, errors_by_operation):
        """ Compose the error object json to be added in 'errors' in given operation's summary """
        message = "{0} error/s reported.".format(len(errors_by_operation))
        message += " The latest {0} error/s are shared in detail. To view all errors, review this log file on the machine: {1}".format(len(errors_by_operation), self.__log_file_path)
        return {
            'code': Constants.PatchOperationTopLevelErrorCode.WARNING if not code == Constants.PatchOperationTopLevelErrorCode.ERROR else code,
            'details': errors_by_operation,
            'message': message
        }

    def __add_assessment_tombstone_record(self, tombstone_packages_count, tombstone_classification):
        """ Tombstone record for truncated assessment
            Classification: “Critical, Security, Other”
            Patch Name: “20 additional updates of classification ‘Classification’ reported.”
        """
        tombstone_name = str(tombstone_packages_count) + ' additional updates of classification ' + tombstone_classification + ' reported',
        return {
            'patchId': 'Truncated_patch_list_id',
            'name': tombstone_name,
            'version': '',
            'classifications': [tombstone_classification]
        }
    # endregion