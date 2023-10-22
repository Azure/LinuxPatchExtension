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
        self.__installation_substatus_msg_copy = None
        self.__installation_packages_copy = []

        # Internal in-memory representation of Patch Assessment data
        self.__assessment_substatus_json = None
        self.__assessment_summary_json = None
        self.__assessment_packages = []
        self.__assessment_errors = []
        self.__assessment_total_error_count = 0  # All errors during assess, includes errors not in error objects due to size limit
        self.__assessment_packages_map = collections.OrderedDict()
        self.__assessment_substatus_msg_copy = None
        self.__assessment_packages_copy = []

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

        # Internal in-memory representation of Truncated Patching data
        self.__internal_file_capacity = Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES

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
        self.__assessment_packages_copy = []
        self.__assessment_substatus_msg_copy = None

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

        # Compose substatus message
        errors = self.__set_errors_json(self.__assessment_total_error_count, self.__assessment_errors)

        substatus_message = self.__compose_assessment_substatus_msg(
            activity_id=self.execution_config.activity_id, reboot_pending=self.is_reboot_pending, crit_patch_count=critsec_patch_count,
            other_patch_count=other_patch_count, packages=assessment_packages_json, start_time=self.execution_config.start_time,
            last_modified_time=self.env_layer.datetime.timestamp(), started_by=started_by, errors=errors)

        if self.vm_cloud_type == Constants.VMCloudType.ARC:
            substatus_message["patchAssessmentStatus"] = code
            substatus_message["patchAssessmentStatusString"] = status

        return substatus_message

    def __compose_assessment_substatus_msg(self, activity_id, reboot_pending, crit_patch_count, other_patch_count, packages, start_time, last_modified_time, started_by, errors):
        return {
            "assessmentActivityId": str(activity_id),
            "rebootPending": reboot_pending,
            "criticalAndSecurityPatchCount": crit_patch_count,
            "otherPatchCount": other_patch_count,
            "patches": packages,
            "startTime": str(start_time),
            "lastModifiedTime": str(last_modified_time),
            "startedBy": str(started_by),
            "errors": errors
        }

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
        maintenance_run_id = self.execution_config.maintenance_run_id if self.execution_config.maintenance_run_id is not None else ''
        errors = self.__set_errors_json(self.__installation_total_error_count, self.__installation_errors)
        substatus_message = self.__compose_installation_substatus_msg(activity_id=self.execution_config.activity_id, reboot_status=self.__installation_reboot_status,
            maintenance_window=self.__maintenance_window_exceeded, not_selected=not_selected_patch_count, excluded=excluded_patch_count,
            pending=pending_patch_count, installed=installed_patch_count, failed=failed_patch_count,
            packages=installation_packages_json, start_time=self.execution_config.start_time,
            last_modified_time=self.env_layer.datetime.timestamp(), maintenance_id=maintenance_run_id, errors=errors)

        return substatus_message

    def __compose_installation_substatus_msg(self, activity_id, reboot_status, maintenance_window, not_selected, excluded, pending, installed, failed, packages, start_time, last_modified_time, maintenance_id, errors):
        return {
            "installationActivityId": str(activity_id),
            "rebootStatus": str(reboot_status),
            "maintenanceWindowExceeded": maintenance_window,
            "notSelectedPatchCount": not_selected,
            "excludedPatchCount": excluded,
            "pendingPatchCount": pending,
            "installedPatchCount": installed,
            "failedPatchCount": failed,
            "patches": packages,
            "startTime": str(start_time),
            "lastModifiedTime": str(last_modified_time),
            "maintenanceRunId": str(maintenance_id),
            "errors": errors
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
        self.__installation_packages_copy = []

        self.__assessment_substatus_json = None
        self.__assessment_summary_json = None
        self.__assessment_packages = []
        self.__assessment_errors = []
        self.__assessment_packages_map = collections.OrderedDict()
        self.__assessment_substatus_msg_copy = None
        self.__assessment_packages_copy = []

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

    def __get_substatus_message(self, status_file_data, substatus_index):
        """ Get the substatus payload message by index """
        return json.loads(status_file_data['status']['substatus'][substatus_index]['formattedMessage']['message'])

    def __load_complete_status_file_data(self, file_path):
        # Read the status file - raise exception on persistent failure
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(file_path, 'r') as file_handle:
                    complete_status_file_data = json.load(file_handle)[0]  # structure is array of 1
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
            status_file_payload_json_dumps = self.__check_file_size_and_timestamp_for_truncation(status_file_payload_json_dumps)

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

    def __set_errors_json(self, error_count_by_operation, errors_by_operation, truncated=False):
        """ Compose the error object json to be added in 'errors' in given operation's summary """
        success_code = Constants.PatchOperationTopLevelErrorCode.SUCCESS
        error_code = Constants.PatchOperationTopLevelErrorCode.ERROR
        error_count = error_count_by_operation
        code = success_code if error_count_by_operation == 0 else error_code

        # Update the errors json to include truncation detail
        if truncated:
            error_count += 1    # add 1 because of truncation
            code = Constants.PatchOperationTopLevelErrorCode.WARNING if code != error_code else error_code

        message = "{0} error/s reported.".format(error_count)
        message += " The latest {0} error/s are shared in detail. To view all errors, review this log file on the machine: {1}".format(len(errors_by_operation), self.__log_file_path) if error_count > 0 else ""
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
    def __check_file_size_and_timestamp_for_truncation(self, status_file_payload_json_dumps):
        status_file_size_in_bytes = self.__calc_status_size_on_disk(status_file_payload_json_dumps)  # calc complete_status_file_payload byte size on disk

        if status_file_size_in_bytes > self.__internal_file_capacity:  # perform truncation complete_status_file byte size > 126kb
            truncated_status_file = self.__create_truncated_status_file(status_file_size_in_bytes, status_file_payload_json_dumps)
            status_file_payload_json_dumps = json.dumps(truncated_status_file)

        return status_file_payload_json_dumps

    def __create_truncated_status_file(self, status_file_size_in_bytes, complete_status_file_payload):
        """ Truncate substatus message patch list when complete status file size is more than 126kb """
        """
            __create_truncated_status_file(self, status_file_size_in_bytes, complete_status_file_payload):

                truncated_status_file = json.loads(complete_status_file_payload)
                low_pri_index = None
                _index = self.__get_substatus_index()
                status_file_without_package_list_size  = __calc_package_payload_size_on_disk(size_of_constant_status_data(complete_status_file_payload))
                size_of_max_packages_allowed_in_status = 126kb - status_file_without_package_list_size 
                
                if assessment_index is not none:
                    _substatus_msg_copy = __get_substatus_message(truncated_status_file, _index)
                    _packages_copy = _substatus_msg_copy['patches']

                if installation_index is not none:
                    _substatus_msg_copy = __get_substatus_message(truncated_status_file, _index)
                    _packages_copy = _substatus_msg_copy['patches']
                    low_pri_index = __get_installation_low_pri_index()

                    while status_file_size_in_bytes > 126kb:
                        __apply_truncation_process()
                            __split_assessment_list()
                                __apply_truncation()
                                
                        __recompose_truncated_status_file()                                    
                            __get_current_complete_status_errors()
                            __recompose_truncated_substatus_msg()
                                __recompose_substatus_msg_errors()
                                __create_assessment_tombstone_list()
                                    __create_assessment_tombstone()
                                __recreate_assessment_summary_json()
                       
                        __recompose_truncated_status_file()                                    
                            __get_current_complete_status_errors()
                            __recompose_truncated_substatus_msg()
                                __recompose_substatus_msg_errors()
                                __create_installation_tombstone
                                __recreate_installation_summary_json()
                                
                        status_file_size_in_bytes, status_file_agent_size_diff = __get_new_size_in_bytes_after_truncation(truncated_status_file)
                        size_of_max_packages_allowed_in_status -= status_file_agent_size_diff  
        """
        self.composite_logger.log_debug("Begin package list truncation")
        truncated_status_file = json.loads(complete_status_file_payload)  # reload payload into python object
        low_pri_index = None
        assessment_substatus_index = self.__get_substatus_index(Constants.PATCH_ASSESSMENT_SUMMARY, truncated_status_file['status']['substatus'])
        installation_substatus_index = self.__get_substatus_index(Constants.PATCH_INSTALLATION_SUMMARY, truncated_status_file['status']['substatus'])

        if assessment_substatus_index is not None:      # If assessment data exists
            self.__assessment_substatus_msg_copy = self.__get_substatus_message(truncated_status_file, assessment_substatus_index)
            self.__assessment_packages_copy = self.__assessment_substatus_msg_copy['patches']

        if installation_substatus_index is not None:    # If installation data exists
            self.__installation_substatus_msg_copy = self.__get_substatus_message(truncated_status_file, installation_substatus_index)
            self.__installation_packages_copy = self.__installation_substatus_msg_copy['patches']
            low_pri_index = self.__get_installation_low_pri_index(self.__installation_packages_copy)

        status_file_without_package_list_size = self.size_of_constant_status_data(copy.deepcopy(truncated_status_file), assessment_substatus_index, installation_substatus_index)  # Deepcopy fully copy the object avoid reference modification
        size_of_max_packages_allowed_in_status = self.__internal_file_capacity - status_file_without_package_list_size

        while status_file_size_in_bytes > self.__internal_file_capacity:
            # Start truncation process
            packages_retained_in_assessment, packages_removed_from_assessment, packages_retained_in_installation, packages_removed_from_installation = \
                self.__apply_truncation_process(self.__assessment_packages_copy, self.__installation_packages_copy, size_of_max_packages_allowed_in_status, low_pri_index)

            if len(packages_removed_from_assessment) > 0:
                # Recompose truncated status file payload (assessment)
                truncated_status_file = self.__recompose_truncated_status_file(truncated_status_file=truncated_status_file, truncated_package_list=packages_retained_in_assessment,
                    count_total_errors=self.__assessment_total_error_count, truncated_substatus_msg=self.__assessment_substatus_msg_copy, substatus_index=assessment_substatus_index)

            if len(packages_removed_from_installation) > 0:
                # Recompose truncated status file payload (installation)
                truncated_status_file = self.__recompose_truncated_status_file(truncated_status_file=truncated_status_file, truncated_package_list=packages_retained_in_installation,
                    count_total_errors=self.__installation_total_error_count, truncated_substatus_msg=self.__installation_substatus_msg_copy, substatus_index=installation_substatus_index)

            status_file_size_in_bytes, status_file_agent_size_diff = self.__get_new_size_in_bytes_after_truncation(truncated_status_file)
            size_of_max_packages_allowed_in_status -= status_file_agent_size_diff   # Reduce the max packages byte size by tombstone, new error, and escape chars byte size

        self.__is_file_truncated = True  # Set true flag status file needs to remain truncated
        self.composite_logger.log_debug("End package list truncation")

        return truncated_status_file

    def __get_new_size_in_bytes_after_truncation(self, truncated_status_file):
        """ Get new size in bytes for status_file,and difference of status file - 126kb """
        status_file_size_in_bytes = self.__calc_status_size_on_disk(json.dumps(truncated_status_file))
        status_file_agent_size_diff = status_file_size_in_bytes - self.__internal_file_capacity

        return status_file_size_in_bytes, status_file_agent_size_diff

    def __split_assessment_list(self, assessment_packages):
        """ Split package list, keep 5 minimum packages, and remaining packages for truncation """
        min_packages_count = Constants.StatusTruncationConfig.MIN_ASSESSMENT_PACKAGE_TO_RETAIN
        min_assessment_patches_to_retain, assessment_patches_eligible_for_truncation = (assessment_packages[:min_packages_count], assessment_packages[min_packages_count:]) \
            if len(assessment_packages) > min_packages_count else (assessment_packages, [])

        return min_assessment_patches_to_retain, assessment_patches_eligible_for_truncation

    def __apply_truncation_process(self, assessment_packages, installation_packages, max_package_list_capacity, low_pri_index=None):
        """ Truncation function call split assessment method and apply truncation on assessment and installation packages """
        installation_low_pri = []
        installation_high_pri = installation_packages
        # Cut assessment list into [:5], [5:]
        min_assessment_patches_to_retain, assessment_patches_eligible_for_truncation = self.__split_assessment_list(assessment_packages)

        if len(min_assessment_patches_to_retain) > 0:
            max_package_list_capacity = max_package_list_capacity - self.__calc_package_payload_size_on_disk(min_assessment_patches_to_retain)

        # Apply high priority (Failed, Installed) and low priority (Pending, Excluded, Not_Selected) installation logic, and keep min 5 assessment packages
        if low_pri_index:
            installation_high_pri = installation_packages[:low_pri_index]
            installation_low_pri = installation_packages[low_pri_index:]

        packages_retained_in_install_high_pri, packages_removed_from_inst_high_pri, remaining_list_capacity = self.__apply_truncation(installation_high_pri, max_package_list_capacity)
        packages_retained_in_assessment, packages_removed_from_assessment, remaining_list_capacity = self.__apply_truncation(assessment_patches_eligible_for_truncation, remaining_list_capacity)
        packages_retained_in_install_low_pri, packages_removed_from_inst_low_pri, _ = self.__apply_truncation(installation_low_pri, remaining_list_capacity)

        truncated_installation_list = packages_retained_in_install_high_pri + packages_retained_in_install_low_pri
        packages_removed_from_installation = packages_removed_from_inst_high_pri + packages_removed_from_inst_low_pri
        truncated_assessment_list = min_assessment_patches_to_retain + packages_retained_in_assessment

        return truncated_assessment_list, packages_removed_from_assessment, truncated_installation_list, packages_removed_from_installation

    def __get_installation_low_pri_index(self, priority_sorted_installation_packages):
        """" Get the first index of Pending, Excluded, or Not_Selected installation packages """
        for index, package in enumerate(priority_sorted_installation_packages):
            package_state = package['patchInstallationState']
            if Constants.PENDING in package_state or Constants.EXCLUDED in package_state or Constants.NOT_SELECTED in package_state:
                return index

        return None

    def __apply_truncation(self, package_list, capacity):
        """ Binary search
        Instead of checking list[middel_index] >= target, check byte_size(list[:middle_index]),
        as byte_size[list[:i]] is monotonically increasing, i.e.
        byte_size[list[:1]] < byte_size[list[:2]] < byte_size[list[:3]] ...
        return truncated_list, packages_removed_from_list, and remaining max_package_list_capacity
        """
        left_index = 0
        right_index = len(package_list) - 1

        # Empty list after 2xjson.dumps have 4-5 bytes, no truncation, keep list capacity as it is
        if len(package_list) == 0:
            return [], [], capacity
        # check if package list byte size <= list capacity, then returns it (no truncation needed)
        if self.__calc_package_payload_size_on_disk(package_list) <= capacity:
            return package_list, [], capacity - self.__calc_package_payload_size_on_disk(package_list)
        # Check if first element byte size in the list > remaining list capacity, then add package_list to packages_removed_from_list
        if self.__calc_package_payload_size_on_disk(package_list[0]) > capacity:
            return [], package_list, capacity

        while left_index < right_index:
            mid_index = left_index + int((right_index - left_index) / 2)
            if self.__calc_package_payload_size_on_disk(package_list[:mid_index]) >= capacity:
                right_index = mid_index
            else:
                left_index = mid_index + 1

        truncated_list = package_list[:left_index - 1]
        packages_removed_from_list = package_list[left_index - 1:]
        truncated_list_byte_size = self.__calc_package_payload_size_on_disk(truncated_list)

        return truncated_list, packages_removed_from_list, capacity - truncated_list_byte_size

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

    def __calc_package_payload_size_on_disk(self, package_list):
        """ Calculate final package list size in bytes (because of escape chars) """
        first_json_dump = json.dumps(package_list)

        return len(json.dumps(first_json_dump).encode("utf-8"))

    def size_of_constant_status_data(self, complete_status_file_payload, assessment_status_index, installation_status_index):
        """ Get the size in bytes of the complete_status_file without packages data  """
        status_file_no_list_data = complete_status_file_payload
        if assessment_status_index is not None:
            assessment_msg_without_packages = self.__update_substatus_msg(substatus_msg=self.__assessment_substatus_msg_copy, substatus_msg_patches=[])
            status_file_no_list_data['status']['substatus'][assessment_status_index]['formattedMessage']['message'] = json.dumps(assessment_msg_without_packages)

        if installation_status_index is not None:
            installation_msg_without_packages = self.__update_substatus_msg(substatus_msg=self.__installation_substatus_msg_copy, substatus_msg_patches=[])
            status_file_no_list_data['status']['substatus'][installation_status_index]['formattedMessage']['message'] = json.dumps(installation_msg_without_packages)

        return self.__calc_status_size_on_disk(json.dumps(status_file_no_list_data))

    def __get_substatus_index(self, substatus_list_name, substatus_list):
        """" Get substatus index from the current substatus """
        for substatus_index, substatus_name in enumerate(substatus_list):
            if substatus_name['name'] == substatus_list_name:
                return substatus_index

        return None

    def __recompose_truncated_status_file(self, truncated_status_file, truncated_package_list, count_total_errors, truncated_substatus_msg, substatus_index):
        """ Recompose final truncated status file version """
        truncated_detail_list = []
        code, errors_details = self.__get_current_complete_status_errors(substatus_msg=truncated_substatus_msg)

        # Check for existing errors before recompose
        if code != Constants.PatchOperationTopLevelErrorCode.ERROR:
            truncated_status_file['status']['substatus'][substatus_index]['status'] = Constants.STATUS_WARNING.lower()      # Update substatus status to warning
        else:
            truncated_detail_list.extend(errors_details)

        truncated_msg_errors = self.__recompose_substatus_msg_errors(truncated_detail_list, count_total_errors)    # Recompose substatus msg errors
        truncated_substatus_msg = self.__update_substatus_msg(substatus_msg=truncated_substatus_msg, substatus_msg_patches=truncated_package_list, substatus_msg_errors=truncated_msg_errors)
        truncated_status_file['status']['substatus'][substatus_index]['formattedMessage']['message'] = json.dumps(truncated_substatus_msg)

        return truncated_status_file

    def __recompose_substatus_msg_errors(self, truncation_detail_list, count_total_errors):
        """ Recompose truncated substatus errors json """
        error_msg = Constants.StatusTruncationConfig.TRUNCATION_WARNING_MESSAGE
        truncated_error_detail = self.__set_error_detail(Constants.PatchOperationErrorCodes.TRUNCATION, error_msg)  # Reuse the errors object set up
        self.__try_add_error(truncation_detail_list, truncated_error_detail)
        truncated_errors_json = self.__set_errors_json(count_total_errors, truncation_detail_list, True)    # True for truncated

        return truncated_errors_json

    def __update_substatus_msg(self, substatus_msg, substatus_msg_patches, substatus_msg_errors=None):
        substatus_msg['patches'] = substatus_msg_patches
        if substatus_msg_errors:
            substatus_msg['errors'] = substatus_msg_errors

        return substatus_msg

    def __get_current_complete_status_errors(self, substatus_msg):
        """ Get the complete status file errors code and errors details """
        return substatus_msg['errors']['code'], substatus_msg['errors']['details']
    # endregion

