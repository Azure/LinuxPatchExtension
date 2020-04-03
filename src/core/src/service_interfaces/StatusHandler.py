import datetime
import json
import os
import re
import shutil
import time
from src.bootstrap.Constants import Constants


class StatusHandler(object):
    """Class for managing the core code's lifecycle within the extension wrapper"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer):
        # Map supporting components for operation
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer    # not used immediately but need to know if there are issues persisting status
        self.status_file_path = self.execution_config.status_file_path
        self.__log_file_path = self.execution_config.log_file_path

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

        # Load the currently persisted status file into memory
        self.__load_status_file_components(initial_load=True)

        # Enable reboot completion status capture
        if self.__installation_reboot_status == Constants.RebootStatus.STARTED:
            self.set_installation_reboot_status(Constants.RebootStatus.COMPLETED)  # switching to completed after the reboot

        # ToDo: NOTE for PR review(Remove later): setting the default to False and not 'Unknown' as discussed earlier, as status file can only have false or true in json as per Agent team arch, this was there's no risk of failure due to incorrect status json
        # Tracker for reboot pending status, the value is updated externally(UpdateRun.py) whenever package is installed
        self.is_reboot_pending = False

        # Discovers OS name and version for package id composition
        self.__os_name_and_version = self.get_os_name_and_version()

        self.__current_operation = None

    # region - Package Data
    def reset_assessment_data(self):
        """ Externally available method to wipe out any assessment package records in memory. """
        self.__assessment_packages = []

    def set_package_assessment_status(self, package_names, package_versions, classification="Other", status="Available"):
        """ Externally available method to set assessment status for one or more packages of the **SAME classification and status** """
        self.composite_logger.log_debug("Setting package assessment status in bulk. [Count={0}]".format(str(len(package_names))))
        for package_name, package_version in zip(package_names, package_versions):
            patch_already_saved = False
            patch_id = self.__get_patch_id(package_name, package_version)
            for i in range(0, len(self.__assessment_packages)):
                if patch_id == self.__assessment_packages[i]['patchId']:
                    patch_already_saved = True
                    self.__assessment_packages[i]['classifications'] = [classification]
                    self.__assessment_packages[i]['patchState'] = status

            if patch_already_saved is False:
                record = {
                    "patchId": str(patch_id),
                    "name": str(package_name),
                    "version": str(package_version),
                    "classifications": [classification]
                    # "patchState": str(status) # Allows for capturing 'Installed' packages in addition to 'Available', when commented out, if spec changes
                }
                self.__assessment_packages.append(record)

        self.set_assessment_substatus_json()

    def set_package_install_status(self, package_names, package_versions, status="Pending", classification=None):
        """ Externally available method to set installation status for one or more packages of the **SAME classification and status** """
        self.composite_logger.log_debug("Setting package installation status in bulk. [Count={0}]".format(str(len(package_names))))
        for package_name, package_version in zip(package_names, package_versions):
            self.composite_logger.log_debug("Logging progress [Package: " + package_name + "; Status: " + status + "]")
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
                    classification = "Other"
                record = {
                    "patchId": str(patch_id),
                    "name": str(package_name),
                    "version": str(package_version),
                    "classifications": [classification],
                    "patchInstallationState": str(status)
                }
                self.__installation_packages.append(record)

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
        self.__write_status_file()

    def __refresh_installation_reboot_status(self):
        """ Discovers if the system needs a reboot. Never allows going back to NotNeeded (deliberate). ONLY called internally. """
        self.composite_logger.log_debug("Checking if reboot status needs to reflect machine reboot status.")
        if self.__installation_reboot_status in [Constants.RebootStatus.NOT_NEEDED, Constants.RebootStatus.COMPLETED]:
            # Checks only if it's a state transition we allow
            reboot_needed = self.is_reboot_pending
            if reboot_needed:
                self.composite_logger.log_debug("Machine reboot status has changed to 'Required'.")
                self.__installation_reboot_status = Constants.RebootStatus.REQUIRED

    def set_reboot_pending(self, is_reboot_pending, log_message):
        log_message = "Updating reboot pending status" if not log_message else log_message
        self.composite_logger.log_debug(log_message)
        self.is_reboot_pending = is_reboot_pending
    # endregion

    # region - Substatus generation
    def set_maintenance_window_exceeded(self, maintenance_windows_exceeded):
        self.__maintenance_window_exceeded = maintenance_windows_exceeded
        self.__write_status_file()

    def set_assessment_substatus_json(self, status=Constants.STATUS_TRANSITIONING, code=0):
        """ Prepare the assessment substatus json including the message containing assessment summary """
        self.composite_logger.log_debug("Setting assessment substatus. [Substatus={0}]".format(str(status)))

        # Wrap patches into assessment summary
        self.__assessment_summary_json = self.__new_assessment_summary_json(self.__assessment_packages)

        # Wrap assessment summary into assessment substatus
        self.__assessment_substatus_json = self.__new_substatus_json_for_operation(Constants.PATCH_ASSESSMENT_SUMMARY, status, code, json.dumps(self.__assessment_summary_json))

        # Update status on disk
        self.__write_status_file()

    def __new_assessment_summary_json(self, assessment_packages_json):
        """ Called by: set_assessment_substatus_json
            Purpose: This composes the message inside the patch installation summary substatus:
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

        # Compose substatus message
        return {
            "assessmentActivityId": str(self.execution_config.activity_id),
            "rebootPending": self.is_reboot_pending,
            "criticalAndSecurityPatchCount": critsec_patch_count,
            "otherPatchCount": other_patch_count,
            "patches": assessment_packages_json,
            "startTime": str(self.execution_config.start_time),
            "lastModifiedTime": str(self.env_layer.datetime.timestamp()),
            "errors": self.__set_errors_json(self.__assessment_total_error_count, self.__assessment_errors)
        }

    def set_installation_substatus_json(self, status=Constants.STATUS_TRANSITIONING, code=0):
        """ Prepare the deployment substatus json including the message containing deployment summary """
        self.composite_logger.log_debug("Setting installation substatus. [Substatus={0}]".format(str(status)))

        # Wrap patches into deployment summary
        self.__installation_summary_json = self.__new_installation_summary_json(self.__installation_packages)

        # Wrap deployment summary into deployment substatus
        self.__installation_substatus_json = self.__new_substatus_json_for_operation(Constants.PATCH_INSTALLATION_SUMMARY, status, code, json.dumps(self.__installation_summary_json))

        # Update status on disk
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
            "errors": self.__set_errors_json(self.__installation_total_error_count, self.__installation_errors)
        }

    @staticmethod
    def __new_substatus_json_for_operation(operation_name, status="Transitioning", code=0, message=json.dumps("{}")):
        """ Generic substatus for assessment and deployment """
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
        self.env_layer.file_system.write_with_retry(self.status_file_path, '[{0}]'.format(json.dumps(self.__new_basic_status_json())), mode='w+')

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
    def __load_status_file_components(self, initial_load=False):
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

        # Verify the status file exists - if not, reset status file
        if not os.path.exists(self.status_file_path) and initial_load:
            self.__reset_status_file()
            return

        # Read the status file - raise exception on persistent failure
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.status_file_path, 'r') as file_handle:
                    status_file_data_raw = json.load(file_handle)[0]    # structure is array of 1
            except Exception as error:
                if i <= Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to read status file (retries exhausted). Error: {0}.".format(repr(error)))
                    raise

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
        self.__high_level_status_message = status_file_data['status']['formattedMessage']['message']
        for i in range(0, len(status_file_data['status']['substatus'])):
            name = status_file_data['status']['substatus'][i]['name']
            if name == Constants.PATCH_INSTALLATION_SUMMARY:     # if it exists, it must be to spec, or an exception will get thrown
                message = status_file_data['status']['substatus'][i]['formattedMessage']['message']
                self.__installation_summary_json = json.loads(message)
                self.__installation_packages = self.__installation_summary_json['patches']
                self.__maintenance_window_exceeded = bool(self.__installation_summary_json['maintenanceWindowExceeded'])
                self.__installation_reboot_status = self.__installation_summary_json['rebootStatus']
                errors = self.__installation_summary_json['errors']
                if errors is not None and errors['details'] is not None:
                    self.__installation_errors = errors['details']
                    self.__installation_total_error_count = len(self.__installation_errors)
            if name == Constants.PATCH_ASSESSMENT_SUMMARY:     # if it exists, it must be to spec, or an exception will get thrown
                message = status_file_data['status']['substatus'][i]['formattedMessage']['message']
                self.__assessment_summary_json = json.loads(message)
                self.__assessment_packages = self.__assessment_summary_json['patches']
                errors = self.__assessment_summary_json['errors']
                if errors is not None and errors['details'] is not None:
                    self.__assessment_errors = errors['details']
                    self.__assessment_total_error_count = len(self.__assessment_errors)

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

        :return: None
        """
        status_file_payload = self.__new_basic_status_json()
        status_file_payload['status']['formattedMessage']['message'] = str(self.__high_level_status_message)

        if self.__assessment_substatus_json is not None:
            status_file_payload['status']['substatus'].append(self.__assessment_substatus_json)
        if self.__installation_substatus_json is not None:
            status_file_payload['status']['substatus'].append(self.__installation_substatus_json)

        if os.path.isdir(self.status_file_path):
            self.composite_logger.log_error("Core state file path returned a directory. Attempting to reset.")
            shutil.rmtree(self.status_file_path)

        self.env_layer.file_system.write_with_retry(self.status_file_path, '[{0}]'.format(json.dumps(status_file_payload)), mode='w+')
    # endregion

    # region - Error objects
    def set_current_operation(self, operation):
        self.__current_operation = operation

    def add_error_to_summary(self, message, error_code=Constants.PatchOperationErrorCodes.DEFAULT_ERROR):
        """ Add error to the respective error objects """
        if not message:
            return

        formatted_message = self.__format_message(message)
        # Compose error detail
        error_detail = {
            "code": str(error_code),
            "message": str(formatted_message)
        }

        if self.__current_operation == Constants.ASSESSMENT:
            self.__add_error(self.__assessment_errors, error_detail)
            self.__assessment_total_error_count += 1
            self.set_assessment_substatus_json()
        elif self.__current_operation == Constants.INSTALLATION:
            self.__add_error(self.__installation_errors, error_detail)
            self.__installation_total_error_count += 1
            self.set_installation_substatus_json()
        else:
            return

    def __format_message(self, full_message):
        """ Removes line breaks, tabs and restricts message to a character limit """
        message_size_limit = Constants.STATUS_ERROR_MSG_SIZE_LIMIT_IN_CHARACTERS
        formatted_message = re.sub(r"\s+", " ", str(full_message))
        return formatted_message[:message_size_limit] + '..' if len(formatted_message) > message_size_limit else formatted_message

    def __add_error(self, add_to, detail):
        """ Add formatted error object to given errors list """
        if len(add_to) > 0:
            errors_to_remove = Constants.STATUS_ERROR_LIMIT - len(add_to)
            for x in range(0, errors_to_remove):
                add_to.pop()
        add_to.insert(0, detail)

    def __set_errors_json(self, error_count_by_operation, errors_by_operation):
        """ Compose the error object json to be added in 'errors' in given operation's summary """
        return {
            "code": Constants.PatchOperationTopLevelErrorCode.success if error_count_by_operation == 0 else Constants.PatchOperationTopLevelErrorCode.error,
            "details": errors_by_operation,
            "message": "{0} error/s reported. The latest {1} error/s are shared in detail. To view all errors, review this log file on the machine:{2}".format(error_count_by_operation, len(errors_by_operation), self.__log_file_path)
        }
    # endregion
