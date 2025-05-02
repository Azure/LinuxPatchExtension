# Copyright 2025 Microsoft Corporation
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
import json

from core.src.bootstrap.Constants import Constants


class ExtStatusAsserter(object):
    def __init__(self, status_file_path, env_layer):
        self.__status_file_path = status_file_path
        self.__env_layer = env_layer

        self.__substatus_file_data = self.__read_status_file(self.__status_file_path)
        self.__substatus_high_level_summary = None
        self.__load_substatus_high_level_summary(self.__substatus_file_data)

    # region Data structure helpers
    @staticmethod
    def __get_high_level_summary_template():
        # type: () -> dict
        """ Internal template for in-memory representation of substatus elements """
        return {
            Constants.CONFIGURE_PATCHING_SUMMARY: {"index": -1, "status": None},
            Constants.PATCH_ASSESSMENT_SUMMARY: {"index": -1, "status": None},
            Constants.PATCH_INSTALLATION_SUMMARY: {"index": -1, "status": None},
            Constants.PATCH_METADATA_FOR_HEALTHSTORE: {"index": -1, "status": None},
        }

    def __get_substatus_index_with_assert(self, operation):
        # type: (str) -> int
        """ Get the index of the substatus """
        if operation not in self.__substatus_high_level_summary:
            raise KeyError("Unknown operation: {0}".format(operation))

        substatus_index = self.__substatus_high_level_summary[operation]["index"]
        if substatus_index == -1:
            raise AssertionError("Substatus index not found for operation: {0}".format(operation))

        return substatus_index

    @staticmethod
    def get_default_substatus_expectations():
        # type: () -> dict
        """ Get the default substatus expectations """
        return {
            Constants.CONFIGURE_PATCHING_SUMMARY: Constants.STATUS_SUCCESS,
            Constants.PATCH_ASSESSMENT_SUMMARY: Constants.STATUS_SUCCESS,
            Constants.PATCH_INSTALLATION_SUMMARY: Constants.STATUS_SUCCESS,
            Constants.PATCH_METADATA_FOR_HEALTHSTORE: Constants.STATUS_SUCCESS,
        }
    # endregion

    # region Data loaders
    def __read_status_file(self, status_file_path):
        # type: (str) -> dict
        with self.__env_layer.file_system.open(status_file_path, 'r') as file_handle:
            return json.load(file_handle)[0]["status"]["substatus"]

    def __load_substatus_high_level_summary(self, substatus_file_data):
        # type: (dict) -> None
        """ Makes one-time inferences about the structure of the status file """
        self.__substatus_high_level_summary = self.__get_high_level_summary_template()

        for index, substatus in enumerate(substatus_file_data):
            summary_name = substatus["name"]
            if summary_name in self.__substatus_high_level_summary:
                self.configure_patching_substatus_index = index
                self.__substatus_high_level_summary[summary_name]["index"] = index
                self.__substatus_high_level_summary[summary_name]["status"] = substatus["status"]
            else:
                raise KeyError("Unknown substatus: {0}".format(substatus["name"]))
    # endregion

    # region Data Navigators
    def __get_substatus_message_as_dict(self, operation):
        # type: (str) -> dict
        """ Get the substatus message as a dictionary """
        substatus_index = self.__get_substatus_index_with_assert(operation)
        return json.loads(self.__substatus_file_data[substatus_index]["formattedMessage"]["message"])
    # endregion

    # region Public Assertion methods
    def assert_status_file_substatus(self, operation, expected_status):
        # type: (str, str) -> None
        """ Check if the status file has a specific substatus """
        substatus_index = self.__get_substatus_index_with_assert(operation)

        actual_status = self.__substatus_file_data[substatus_index]["status"].lower()
        if actual_status != expected_status.lower():
            raise AssertionError("Substatus expectations do not match for {0}. Expected: {1}, Actual: {2}".format(operation, expected_status, actual_status))

    def assert_status_file_substatuses(self, substatus_expectations=None):
        # type: (dict) -> None
        """ Batch check the status file for substatus expectations """
        if substatus_expectations is None:
            substatus_expectations = self.get_default_substatus_expectations()

        for key, value in substatus_expectations.items():
            self.assert_status_file_substatus(key, value)

    def assert_operation_summary_has_patch(self, operation, patch_name, classification=None, patch_id=None):
        # type: (str, str, str, str) -> bool
        """ Check if the defined operation summary has a specific patch """
        substatus_message = self.__get_substatus_message_as_dict(operation)
        summary_patches = substatus_message["patches"]

        for patch in summary_patches:
            if patch["name"] == patch_name:
                if classification and classification not in patch["classifications"]:
                    raise AssertionError("Classification '{0}' does not match expected value '{1}' for patch '{2}'.".format(classification, str(patch["classifications"]), patch_name))
                if patch_id and patch_id not in str(patch["patchId"]):
                    raise AssertionError("Patch ID '{0}' does not match expected value '{1}' for patch '{2}'.".format(patch_id, str(patch["patch_id"]), patch_name))
                return True

        raise AssertionError("Patch '{0}' not found in '{1}' summary.".format(patch_name, operation))

    def assert_operation_summary_has_error(self, operation, error_message, sub_level_for_configure_patching_only=None):
        # type: (str, str, str) -> bool
        """ Check if the defined operation summary has a specific error """
        substatus_message = self.__get_substatus_message_as_dict(operation)

        if sub_level_for_configure_patching_only not in [None, "autoAssessmentStatus", "patchModeStatus"]:
            raise ValueError("sub_level_for_configure_patching_only must be None, 'autoAssessmentStatus', or 'patchModeStatus'.")

        if operation == Constants.CONFIGURE_PATCHING_SUMMARY and sub_level_for_configure_patching_only:
            error_detail_list = substatus_message[sub_level_for_configure_patching_only]["errors"]["details"]
        else:
            error_detail_list = substatus_message["errors"]["details"]

        for error in error_detail_list:
            if error_message in error["message"]:
                return True
        raise AssertionError("Error '{0}' not found in '{1}' summary.".format(error_message, operation))

    def assert_operation_summary_has_started_by(self, operation, started_by):
        # type: (str, str) -> None
        """ Check if the defined operation summary has a specific started by """
        substatus_message = self.__get_substatus_message_as_dict(operation)
        if substatus_message["startedBy"] != started_by:
            raise AssertionError("Started by '{0}' does not match expected value '{1}' for operation '{2}.".format(substatus_message["startedBy"], started_by, operation))

    def assert_configure_patching_patch_mode_state(self, expected_state):
        # type: (str) -> None
        """ Check if the patch mode state is as expected """
        substatus_message = self.__get_substatus_message_as_dict(Constants.CONFIGURE_PATCHING_SUMMARY)
        if substatus_message["automaticOSPatchState"] != expected_state:
            raise AssertionError("Patch mode state '{0}' does not match expected value '{1}'.".format(substatus_message["automaticOSPatchState"], expected_state))

    def assert_configure_patching_auto_assessment_state(self, expected_state):
        # type: (str) -> None
        """ Check if the auto-assessment state is as expected """
        substatus_message = self.__get_substatus_message_as_dict(Constants.CONFIGURE_PATCHING_SUMMARY)
        if substatus_message["autoAssessmentStatus"]["autoAssessmentState"] != expected_state:
            raise AssertionError("Auto-assessment state '{0}' does not match expected value '{1}'.".format(substatus_message["autoAssessmentStatus"]["state"], expected_state))

    def assert_healthstore_status_info(self, patch_version, should_report=True):
        # type: (str, bool) -> None
        """Check if the healthstore patch version is as expected"""
        healthstore_summary = self.__get_substatus_message_as_dict(Constants.PATCH_METADATA_FOR_HEALTHSTORE)

        if should_report and healthstore_summary["shouldReportToHealthStore"] != True:
            raise AssertionError("Healthstore summary should report to healthstore.")

        if patch_version != healthstore_summary["patchVersion"]:
            raise AssertionError("Healthstore summary patch version '{0}' does not match expected value {1}.".format(str(healthstore_summary["patchVersion"]), patch_version))
    # endregion
