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
import collections
import copy
import glob
import json
import os
import re
import shutil
import time
from core.src.bootstrap.Constants import Constants


class StatusHandler(object):
    """Class for managing the core code's lifecycle within the extension wrapper"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, vm_cloud_type):
        # Map supporting components for operation
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer    # not used immediately but need to know if there are issues persisting status
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
        self.__installation_packages_map = collections.OrderedDict()
        self.__installation_substatus_msg_copy = None  # store copy of message json for truncation and avoid reference modification
        self.__installation_patches_copy = []  # store copy of installation patches for truncation and avoid reference modification
        self.__installation_patches_removed = []  # store truncated patches for tombstone and logging

        # Internal in-memory representation of Patch Assessment data
        self.__assessment_substatus_json = None
        self.__assessment_summary_json = None
        self.__assessment_packages = []
        self.__assessment_errors = []
        self.__assessment_total_error_count = 0  # All errors during assess, includes errors not in error objects due to size limit
        self.__assessment_packages_map = collections.OrderedDict()
        self.__assessment_substatus_msg_copy = None  # store copy of message json for truncation and avoid reference modification
        self.__assessment_patches_copy = []    # store copy of assessment patches for truncation and avoid reference modification
        self.__assessment_patches_removed = []   # store truncated patches for tombstone and logging

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
        self.__assessment_packages_map = collections.OrderedDict()
        self.__assessment_patches_copy = []    # Reset the assessment patch copy
        self.__assessment_substatus_msg_copy = None  # Reset the message json
        self.__assessment_patches_removed = []   # Reset list

    def set_package_assessment_status(self, package_names, package_versions, classification="Other", status="Available"):
        """ Externally available method to set assessment status for one or more packages of the **SAME classification and status** """
        self.composite_logger.log_debug("Setting package assessment status in bulk. [Count={0}]".format(str(len(package_names))))

        for package_name, package_version in zip(package_names, package_versions):
            patch_already_saved = False
            patch_id = self.__get_patch_id(package_name, package_version)

            # Match patch_id in map and update existing patch's classification i.e from other -> security
            if len(self.__assessment_packages_map) > 0 and patch_id in self.__assessment_packages_map:
                self.__assessment_packages_map.setdefault(patch_id, {})['classifications'] = [classification]
                # self.__assessment_packages_map.setdefault(patch_id, {})['patchState'] = status
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
            # Match patch_id in map and update existing patch's classification i.e from None -> security and update pending status
            if len(self.__installation_packages_map) > 0 and patch_id in self.__installation_packages_map:
                if classification is not None:
                    self.__installation_packages_map.setdefault(patch_id, {})['classifications'] = [classification]
                self.__installation_packages_map.setdefault(patch_id, {})['patchInstallationState'] = status
                patch_already_saved = True

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
                # Add new patch to ordered map
                self.__installation_packages_map[patch_id] = record

            package_install_status_summary += "[P={0},V={1}] ".format(str(package_name), str(package_version))

        self.composite_logger.log_debug("Package install status summary [Status= " + status + "] : " + package_install_status_summary)
        self.__installation_packages = list(self.__installation_packages_map.values())
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
            # Match patch_id in map and update existing patch's classification i.e from None -> security
            if len(self.__installation_packages_map) > 0 and patch_id in self.__installation_packages_map:
                self.__installation_packages_map.setdefault(patch_id, {})['classifications'] = [classification]
                classification_matching_package_found = True

            package_classification_summary += "[P={0},V={1},C={2}] ".format(str(package_name), str(package_version), str(classification if classification is not None and classification_matching_package_found else "-"))

        self.composite_logger.log_debug("Package install status summary (classification): " + package_classification_summary)
        self.__installation_packages = list(self.__installation_packages_map.values())
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
        self.__write_status_file()

    def __new_assessment_summary_json(self, assessment_packages_json, status, code):
        """ Called by: set_assessment_substatus_json
            Purpose: This composes the message inside the patch assessment summary substatus:
                Root --> Status --> Substatus [name: "PatchAssessmentSummary"] --> FormattedMessage --> **Message** """

        # Calculate summary
        critsec_patch_count = 0
        other_patch_count = 0
        for i in range(0, len(assessment_packages_json)):
            classifications = assessment_packages_json[i]['classifications']
            if "Critical" in classifications or "Security" in classifications or "Security-ESM" in classifications:
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
        self.__write_status_file()

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
        self.__write_status_file()

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
        self.__write_status_file()

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
        self.__installation_packages_map = collections.OrderedDict()
        self.__installation_substatus_msg_copy = None
        self.__installation_patches_copy = []
        self.__installation_patches_removed = []

        self.__assessment_substatus_json = None
        self.__assessment_summary_json = None
        self.__assessment_packages = []
        self.__assessment_errors = []
        self.__assessment_packages_map = collections.OrderedDict()
        self.__assessment_substatus_msg_copy = None
        self.__assessment_patches_copy = []
        self.__assessment_patches_removed = []

        self.__metadata_for_healthstore_substatus_json = None
        self.__metadata_for_healthstore_summary_json = None

        self.__configure_patching_substatus_json = None
        self.__configure_patching_summary_json = None
        self.__configure_patching_errors = []
        self.__configure_patching_auto_assessment_errors = []

        self.composite_logger.log_debug("Loading status file components [InitialLoad={0}].".format(str(initial_load)))

        # Retain 10 complete status files, and remove older files
        self.__removed_older_complete_status_files(self.execution_config.status_folder)

        # Verify the status file exists - if not, reset status file
        if not os.path.exists(self.complete_status_file_path) and initial_load:
            self.composite_logger.log_warning("Status file not found at initial load. Resetting status file to defaults.")
            self.__reset_status_file()
            return

        # Load status data and sanity check structure - raise exception if data loss risk is detected on corrupt data
        complete_status_file_data = self.__load_complete_status_file_data(self.complete_status_file_path)
        if 'status' not in complete_status_file_data or 'substatus' not in complete_status_file_data['status']:
            self.composite_logger.log_error("Malformed status file. Resetting status file for safety.")
            self.__reset_status_file()
            return

        # Load portions of data that need to be built on for next write - raise exception if corrupt data is encountered
        # todo: refactor
        self.__high_level_status_message = complete_status_file_data['status']['formattedMessage']['message']
        for i in range(0, len(complete_status_file_data['status']['substatus'])):
            name = complete_status_file_data['status']['substatus'][i]['name']
            if name == Constants.PATCH_INSTALLATION_SUMMARY:     # if it exists, it must be to spec, or an exception will get thrown
                if self.execution_config.exec_auto_assess_only:
                    self.__installation_substatus_json = complete_status_file_data['status']['substatus'][i]
                else:
                    self.__installation_summary_json = self.__get_substatus_message(complete_status_file_data, i)
                    # Reload patches into installation ordered map for fast look up
                    self.__installation_packages_map = collections.OrderedDict((package["patchId"], package) for package in self.__installation_summary_json['patches'])
                    self.__installation_packages = list(self.__installation_packages_map.values())
                    self.__maintenance_window_exceeded = bool(self.__installation_summary_json['maintenanceWindowExceeded'])
                    self.__installation_reboot_status = self.__installation_summary_json['rebootStatus']
                    errors = self.__installation_summary_json['errors']
                    if errors is not None and errors['details'] is not None:
                        self.__installation_errors = errors['details']
                        self.__installation_total_error_count = self.__get_total_error_count_from_prev_status(errors['message'])
            if name == Constants.PATCH_ASSESSMENT_SUMMARY:     # if it exists, it must be to spec, or an exception will get thrown
                self.__assessment_summary_json = self.__get_substatus_message(complete_status_file_data, i)
                # Reload patches into assessment ordered map for fast look up
                self.__assessment_packages_map = collections.OrderedDict((package["patchId"], package) for package in self.__assessment_summary_json['patches'])
                self.__assessment_packages = list(self.__assessment_packages_map.values())
                errors = self.__assessment_summary_json['errors']
                if errors is not None and errors['details'] is not None:
                    self.__assessment_errors = errors['details']
                    self.__assessment_total_error_count = self.__get_total_error_count_from_prev_status(errors['message'])
            if name == Constants.PATCH_METADATA_FOR_HEALTHSTORE:     # if it exists, it must be to spec, or an exception will get thrown
                if self.execution_config.exec_auto_assess_only:
                    self.__metadata_for_healthstore_substatus_json = complete_status_file_data['status']['substatus'][i]
                else:
                    self.__metadata_for_healthstore_summary_json = self.__get_substatus_message(complete_status_file_data, i)
            if name == Constants.CONFIGURE_PATCHING_SUMMARY:     # if it exists, it must be to spec, or an exception will get thrown
                if self.execution_config.exec_auto_assess_only:
                    self.__configure_patching_substatus_json = complete_status_file_data['status']['substatus'][i]
                else:
                    self.__configure_patching_summary_json = self.__get_substatus_message(complete_status_file_data, i)
                    errors = self.__configure_patching_summary_json['errors']
                    if errors is not None and errors['details'] is not None:
                        self.__configure_patching_errors = errors['details']
                        self.__configure_patching_top_level_error_count = self.__get_total_error_count_from_prev_status(errors['message'])

    def __get_substatus_message(self, status_file_data, index):
        return json.loads(status_file_data['status']['substatus'][index]['formattedMessage']['message'])

    def __load_complete_status_file_data(self, file_path):
        # Read the status file - raise exception on persistent failure
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(file_path, 'r') as file_handle:
                    complete_status_file_data = json.load(file_handle)[0]    # structure is array of 1
            except Exception as error:
                if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to read status file (retries exhausted). Error: {0}.".format(repr(error)))
                    raise
        return complete_status_file_data

    def __write_status_file(self):
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
        complete_status_payload = self.__new_basic_status_json()
        complete_status_payload['status']['formattedMessage']['message'] = str(self.__high_level_status_message)

        if self.__assessment_substatus_json is not None:
            complete_status_payload['status']['substatus'].append(self.__assessment_substatus_json)
        if self.__installation_substatus_json is not None:
            complete_status_payload['status']['substatus'].append(self.__installation_substatus_json)
        if self.__metadata_for_healthstore_substatus_json is not None:
            complete_status_payload['status']['substatus'].append(self.__metadata_for_healthstore_substatus_json)
        if self.__configure_patching_substatus_json is not None:
            complete_status_payload['status']['substatus'].append(self.__configure_patching_substatus_json)
        if os.path.isdir(self.complete_status_file_path):
            self.composite_logger.log_error("Core state file path returned a directory. Attempting to reset.")
            shutil.rmtree(self.complete_status_file_path)

        # Write complete status file <seq.no>.complete.status
        status_file_payload_json_dumps = json.dumps(complete_status_payload)
        self.env_layer.file_system.write_with_retry_using_temp_file(self.complete_status_file_path, '[{0}]'.format(status_file_payload_json_dumps), mode='w+')

        if Constants.StatusTruncationConfig.TURN_ON_TRUNCATION:
            self.composite_logger.log_verbose("Perform truncation on status file if applicable")
            status_file_payload_json_dumps = self.__get_status_payload_with_truncated_patches(status_file_payload_json_dumps)

        # Write status file <seq.no>.status
        self.env_layer.file_system.write_with_retry_using_temp_file(self.status_file_path, '[{0}]'.format(status_file_payload_json_dumps), mode='w+')
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

    def __set_errors_json(self, error_count_by_operation, errors_by_operation, is_status_truncated=False):
        """ Compose the error object json to be added in 'errors' in given operation's summary """
        code = Constants.PatchOperationTopLevelErrorCode.SUCCESS if error_count_by_operation == 0 else Constants.PatchOperationTopLevelErrorCode.ERROR

        if error_count_by_operation == 1 and errors_by_operation[0]['code'] == Constants.PatchOperationErrorCodes.INFORMATIONAL:    # special-casing for single informational messages
            message = errors_by_operation[0]['message']
            errors_by_operation = []
        else:
            # Update msg error code to warning for truncation
            if is_status_truncated:
                error_count_by_operation += 1  # add 1 because of truncation creates a new error detail object
                code = Constants.PatchOperationTopLevelErrorCode.WARNING if code != Constants.PatchOperationTopLevelErrorCode.ERROR else Constants.PatchOperationTopLevelErrorCode.ERROR

            message = "{0} error/s reported.".format(error_count_by_operation)
            message += " The latest {0} error/s are shared in detail. To view all errors, review this log file on the machine: {1}".format(len(errors_by_operation), self.__log_file_path) if error_count_by_operation > 0 else ""

        return {
            "code": code,
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
    def get_num_assessment_patches_removed(self):
        return len(self.__assessment_patches_removed)

    def get_num_installation_patches_removed(self):
        return len(self.__installation_patches_removed)

    def log_truncated_patches(self):
        """ log details of all the removed patches from status """
        self.composite_logger.log_debug("Count of patches removed from: [Assessment={0}] [Installation={1}]".format(self.get_num_assessment_patches_removed(), self.get_num_installation_patches_removed()))

    def __get_status_payload_with_truncated_patches(self, status_file_payload_json_dumps):
        """ Get truncated status file payload when status file byte size is more than 126kb """
        status_file_size_in_bytes = self.__calc_status_size_on_disk(status_file_payload_json_dumps)  # calc complete_status_file_payload_json byte size on disk

        if status_file_size_in_bytes > Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES:  # perform truncation complete_status_file byte size > 126kb
            truncated_status_file = self.__create_truncated_status_file(status_file_size_in_bytes, status_file_payload_json_dumps)
            status_file_payload_json_dumps = json.dumps(truncated_status_file)
        return status_file_payload_json_dumps

    def __create_truncated_status_file(self, status_file_size_in_bytes, complete_status_file_payload_json):
        """ Truncate substatus message patches when complete status file size is greater than 126kb """
        self.composite_logger.log_verbose("Begin patches truncation: [StatusFileSizeInBytes={0}] [InternalFileSizeLimitInBytes={1}]".format(str(status_file_size_in_bytes), str(Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)))

        truncated_status_file = json.loads(complete_status_file_payload_json)  # reload payload into python object
        low_pri_index = None
        assessment_substatus_index, assessment_substatus_status = self.__get_substatus_index_and_status(Constants.PATCH_ASSESSMENT_SUMMARY, truncated_status_file['status']['substatus'])
        installation_substatus_index, installation_substatus_status = self.__get_substatus_index_and_status(Constants.PATCH_INSTALLATION_SUMMARY, truncated_status_file['status']['substatus'])

        if assessment_substatus_index is not None:      # If assessment data exists
            self.__assessment_substatus_msg_copy = self.__get_substatus_message(truncated_status_file, assessment_substatus_index)
            self.__assessment_patches_copy = self.__assessment_substatus_msg_copy['patches']

        if installation_substatus_index is not None:    # If installation data exists
            self.__installation_substatus_msg_copy = self.__get_substatus_message(truncated_status_file, installation_substatus_index)
            self.__installation_patches_copy = self.__installation_substatus_msg_copy['patches']
            low_pri_index = self.__get_installation_low_pri_index(self.__installation_patches_copy)

        status_file_without_patches_size_in_bytes = self.__size_of_constant_status_data(copy.deepcopy(truncated_status_file), assessment_substatus_index, installation_substatus_index)  # Deepcopy, fully copies the object to avoid reference modifications

        max_allowed_patches_size_in_bytes = Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES - status_file_without_patches_size_in_bytes
        self.composite_logger.log_verbose("Status file limits evaluated. [FileSizeWithoutPatchesInBytes={0}] [MaxAllowedPatchesSizeInBytes={1}]".format(str(status_file_without_patches_size_in_bytes), str(max_allowed_patches_size_in_bytes)))

        while status_file_size_in_bytes > Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES:
            # Start truncation process
            patches_retained_in_assessment, self.__assessment_patches_removed, patches_retained_in_installation, self.__installation_patches_removed = \
                self.__start_truncation_process(self.__assessment_patches_copy, self.__installation_patches_copy, max_allowed_patches_size_in_bytes, low_pri_index)

            if len(self.__assessment_patches_removed) > 0:
                self.composite_logger.log_verbose("Recomposing truncated status payload: [Substatus={0}]".format(Constants.PATCH_ASSESSMENT_SUMMARY))
                truncated_status_file = self.__recompose_truncated_status_file(truncated_status_file=truncated_status_file, truncated_patches=patches_retained_in_assessment, count_total_errors=self.__assessment_total_error_count, substatus_message=self.__assessment_substatus_msg_copy, substatus_status=assessment_substatus_status, substatus_index=assessment_substatus_index)

            if len(self.__installation_patches_removed) > 0:
                self.composite_logger.log_verbose("Recomposing truncated status payload: [Substatus={0}]".format(Constants.PATCH_INSTALLATION_SUMMARY))
                truncated_status_file = self.__recompose_truncated_status_file(truncated_status_file=truncated_status_file, truncated_patches=patches_retained_in_installation, count_total_errors=self.__installation_total_error_count, substatus_message=self.__installation_substatus_msg_copy, substatus_status=installation_substatus_status, substatus_index=installation_substatus_index)

            status_file_size_in_bytes = self.__calc_status_size_on_disk(json.dumps(truncated_status_file))
            status_file_agent_size_diff = status_file_size_in_bytes - Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES
            max_allowed_patches_size_in_bytes -= status_file_agent_size_diff   # Reduce the max packages byte size by new error and new escape chars byte size

        self.composite_logger.log_verbose("End patches truncation: [TruncatedStatusFileSizeInBytes={0}] [InternalFileSizeLimitInBytes={1}]".format(str(status_file_size_in_bytes), str(Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)))
        return truncated_status_file

    def __split_assessment_patches(self, assessment_patches):
        """ Split assessment patches into 2 parts. MIN_ASSESSMENT_PATCHES_TO_RETAIN count as one part and remaining as the other """
        min_patches_count = Constants.StatusTruncationConfig.MIN_ASSESSMENT_PATCHES_TO_RETAIN
        min_assessment_patches_to_retain, remaining_assessment_patches = (assessment_patches[:min_patches_count], assessment_patches[min_patches_count:]) \
            if len(assessment_patches) > min_patches_count else (assessment_patches, [])
        return min_assessment_patches_to_retain, remaining_assessment_patches

    def __start_truncation_process(self, assessment_patches, installation_patches, max_allowed_patches_size_in_bytes, low_pri_index=None):
        """ Function truncates patches from assessment and installation substatus's while always retaining a required minimum count of assessment patches """
        installation_low_pri = []
        installation_high_pri = installation_patches
        # Cut assessment patches into [:5], [5:]
        min_assessment_patches_to_retain, remaining_assessment_patches = self.__split_assessment_patches(assessment_patches)

        if len(min_assessment_patches_to_retain) > 0:
            max_allowed_patches_size_in_bytes = max_allowed_patches_size_in_bytes - self.__calc_patches_payload_size_on_disk(min_assessment_patches_to_retain)

        # Split installation patches into high priority (Failed, Installed) and low priority (Pending, Excluded, Not_Selected)
        if low_pri_index is not None:
            installation_high_pri = installation_patches[:low_pri_index]
            installation_low_pri = installation_patches[low_pri_index:]

        patches_retained_in_install_high_pri, patches_removed_from_install_high_pri, remaining_patches_size_available_in_bytes = self.__truncate_patches(installation_high_pri, max_allowed_patches_size_in_bytes)
        patches_retained_in_assessment, patches_removed_from_assessment, remaining_patches_size_available_in_bytes = self.__truncate_patches(remaining_assessment_patches, remaining_patches_size_available_in_bytes)
        patches_retained_in_install_low_pri, patches_removed_from_install_low_pri, remaining_patches_size_available_in_bytes = self.__truncate_patches(installation_low_pri, remaining_patches_size_available_in_bytes)
        self.composite_logger.log_verbose("Remaining patches size available in bytes after truncation: [RemainingPatchListSizeInBytes={0}]".format(remaining_patches_size_available_in_bytes))

        truncated_installation_patches = patches_retained_in_install_high_pri + patches_retained_in_install_low_pri
        patches_removed_from_installation = patches_removed_from_install_high_pri + patches_removed_from_install_low_pri
        truncated_assessment_patches = min_assessment_patches_to_retain + patches_retained_in_assessment

        return truncated_assessment_patches, patches_removed_from_assessment, truncated_installation_patches, patches_removed_from_installation

    def __get_installation_low_pri_index(self, priority_sorted_installation_patches):
        """" Get the first index of Pending, Excluded, or Not_Selected from installation patches """
        for low_pri_index, patch in enumerate(priority_sorted_installation_patches):
            if patch['patchInstallationState'] in (Constants.PENDING, Constants.EXCLUDED, Constants.NOT_SELECTED):
                return low_pri_index
        return None

    def __truncate_patches(self, patches, max_allowed_patches_size_in_bytes):
        """ Binary search
        Instead of checking patches[mid_index] >= target, check byte_size(patches[:mid_index]),
        as byte_size[patches[:i]] is monotonically increasing, i.e.
        byte_size[patches[:1]] < byte_size[patches[:2]] < byte_size[patches[:3]] ...
        return truncated_patches, patches_removed_from_patches, and remaining max_patches_byte_size
        """
        left_index = 0
        right_index = len(patches) - 1

        # no truncation on empty list, return [],[]
        if len(patches) == 0:
            return [], [], max_allowed_patches_size_in_bytes
        # if patches byte size <= max list patches byte size, then returns it (no truncation needed)
        if self.__calc_patches_payload_size_on_disk(patches) <= max_allowed_patches_size_in_bytes:
            return patches, [], max_allowed_patches_size_in_bytes - self.__calc_patches_payload_size_on_disk(patches)
        # if first element byte size > max patches byte size, then add patches to patches_removed
        if self.__calc_patches_payload_size_on_disk(patches[0]) > max_allowed_patches_size_in_bytes:
            return [], patches, max_allowed_patches_size_in_bytes

        while left_index < right_index:
            mid_index = left_index + int((right_index - left_index) / 2)
            if self.__calc_patches_payload_size_on_disk(patches[:mid_index]) >= max_allowed_patches_size_in_bytes:
                right_index = mid_index
            else:
                left_index = mid_index + 1

        truncated_patches = patches[:left_index - 1]
        patches_removed = patches[left_index - 1:]
        truncated_patches_size_in_bytes = self.__calc_patches_payload_size_on_disk(truncated_patches)
        return truncated_patches, patches_removed, max_allowed_patches_size_in_bytes - truncated_patches_size_in_bytes

    def __removed_older_complete_status_files(self, status_folder):
        """ Retain 10 latest status complete file and remove other .complete.status files """
        files_removed = []
        all_complete_status_files = glob.glob(os.path.join(status_folder, '*.complete.status'))    # Glob return empty list if no file matched pattern
        if len(all_complete_status_files) <= Constants.MAX_COMPLETE_STATUS_FILES_TO_RETAIN:
            return

        all_complete_status_files.sort(key=os.path.getmtime, reverse=True)
        for complete_status_file in all_complete_status_files[Constants.MAX_COMPLETE_STATUS_FILES_TO_RETAIN:]:
            try:
                if os.path.exists(complete_status_file):
                    os.remove(complete_status_file)
                    files_removed.append(complete_status_file)
            except Exception as e:
                self.composite_logger.log_debug("Error deleting complete status file. [File={0} [Exception={1}]]".format(repr(complete_status_file), repr(e)))

        self.composite_logger.log_debug("Cleaned up older complete status files: {0}".format(files_removed))

    def __calc_status_size_on_disk(self, status_file_dumps):
        """ Calculate status file size in bytes on disk """
        return len(status_file_dumps.encode("utf-8"))

    def __calc_patches_payload_size_on_disk(self, patches):
        """ Calculate patches size in bytes accounting for escape chars """
        first_json_dump = json.dumps(patches)
        return len(json.dumps(first_json_dump).encode("utf-8"))

    def __size_of_constant_status_data(self, status_payload_json, assessment_status_index, installation_status_index):
        """ Get the size in bytes of the status payload without patches data """
        status_file_no_list_data = status_payload_json
        if assessment_status_index is not None:
            assessment_msg_without_patches = self.__update_patches_and_errors_in_substatus(substatus_msg=self.__assessment_substatus_msg_copy, substatus_msg_patches=[])
            status_file_no_list_data['status']['substatus'][assessment_status_index]['formattedMessage']['message'] = json.dumps(assessment_msg_without_patches)

        if installation_status_index is not None:
            installation_msg_without_patches = self.__update_patches_and_errors_in_substatus(substatus_msg=self.__installation_substatus_msg_copy, substatus_msg_patches=[])
            status_file_no_list_data['status']['substatus'][installation_status_index]['formattedMessage']['message'] = json.dumps(installation_msg_without_patches)
        return self.__calc_status_size_on_disk(json.dumps(status_file_no_list_data))

    def __get_substatus_index_and_status(self, substatus_list_name, substatus_list):
        """ Gets the index of an operation substatus in the overall extension status for further operations """
        for substatus_index, substatus_data in enumerate(substatus_list):
            if substatus_data['name'] == substatus_list_name:
                return substatus_index, substatus_data['status']
        return None, None

    def __recompose_truncated_status_file(self, truncated_status_file, truncated_patches, count_total_errors, substatus_message, substatus_status, substatus_index):
        """ Recompose status file with truncated patches """
        error_code, errors_details_list = self.__get_errors_from_substatus(substatus_msg=substatus_message)

        # Check for existing errors before recompose
        if error_code != Constants.PatchOperationTopLevelErrorCode.ERROR and substatus_status != 'transitioning':
            self.composite_logger.log_verbose("Patches in substatus have been truncated hence updating status to [status={0}] [PreviousErrorCode={1}]".format(Constants.STATUS_WARNING, str(error_code)))
            truncated_status_file['status']['substatus'][substatus_index]['status'] = Constants.STATUS_WARNING.lower()      # Update substatus status to warning

        truncated_msg_errors = self.__recompose_truncated_substatus_msg_errors(errors_details_list, count_total_errors)

        self.composite_logger.log_verbose("Recompose truncated substatus")
        truncated_substatus_message = self.__update_patches_and_errors_in_substatus(substatus_msg=substatus_message, substatus_msg_patches=truncated_patches, substatus_msg_errors=truncated_msg_errors)

        truncated_status_file['status']['substatus'][substatus_index]['formattedMessage']['message'] = json.dumps(truncated_substatus_message)
        return truncated_status_file

    def __recompose_truncated_substatus_msg_errors(self, errors_details_list, count_total_errors):
        """ Recompose truncated substatus message errors json """
        truncated_error_detail = self.__set_error_detail(Constants.PatchOperationErrorCodes.TRUNCATION, Constants.StatusTruncationConfig.TRUNCATION_WARNING_MESSAGE)  # Reuse the errors object set up
        self.__try_add_error(errors_details_list, truncated_error_detail)  # add new truncated error detail to beginning in errors details list
        truncated_errors_json = self.__set_errors_json(count_total_errors, errors_details_list, is_status_truncated=True)

        return truncated_errors_json

    def __update_patches_and_errors_in_substatus(self, substatus_msg, substatus_msg_patches, substatus_msg_errors=None):
        """ update the substatus message patches and errors and return a new modified substatus message """
        substatus_msg['patches'] = substatus_msg_patches
        if substatus_msg_errors:
            substatus_msg['errors'] = substatus_msg_errors

        return substatus_msg

    def __get_errors_from_substatus(self, substatus_msg):
        """ Get errors code and errors details from substatus message json """
        return substatus_msg['errors']['code'], substatus_msg['errors']['details']
    # endregion

