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

    def __read_status_file(self, status_file_path):
        # type: (str) -> dict
        with self.__env_layer.file_system.open(status_file_path, 'r') as file_handle:
            return json.load(file_handle)[0]["status"]["substatus"]

    @staticmethod
    def __get_high_level_summary_template():
        # type: () -> dict
        return {
            Constants.CONFIGURE_PATCHING_SUMMARY: {"index": -1, "status": None},
            Constants.PATCH_ASSESSMENT_SUMMARY: {"index": -1, "status": None},
            Constants.PATCH_INSTALLATION_SUMMARY: {"index": -1, "status": None},
            Constants.PATCH_METADATA_FOR_HEALTHSTORE: {"index": -1, "status": None},
        }

    def __load_substatus_high_level_summary(self, substatus_file_data):
        # type: (dict) -> None
        self.__substatus_high_level_summary = self.__get_high_level_summary_template()

        for index, substatus in enumerate(substatus_file_data):
            summary_name = substatus["name"]
            if summary_name in self.__substatus_high_level_summary:
                self.configure_patching_substatus_index = index
                self.__substatus_high_level_summary[summary_name]["index"] = index
                self.__substatus_high_level_summary[summary_name]["status"] = substatus["status"]
            else:
                raise KeyError("Unknown substatus: {0}".format(substatus["name"]))

    def assert_status_file_substatuses(self, operation, expected_status):
        """Check if the status file has a specific substatus"""
        if operation not in self.__substatus_high_level_summary:
            raise KeyError("Unknown operation: {0}".format(operation))

        substatus_index = self.__substatus_high_level_summary[operation]["index"]
        if substatus_index == -1:
            raise AssertionError("Substatus index not found for operation: {0}".format(operation))

        actual_status = self.__substatus_file_data[substatus_index]["status"].lower()
        if actual_status != expected_status.lower():
            raise AssertionError("Substatus expectations do not match for {0}. Expected: {1}, Actual: {2}".format(operation, expected_status, actual_status))

    @staticmethod
    def get_default_substatus_expectations():
        """Get the default substatus expectations"""
        return {
            Constants.CONFIGURE_PATCHING_SUMMARY: Constants.STATUS_SUCCESS,
            Constants.PATCH_ASSESSMENT_SUMMARY: Constants.STATUS_SUCCESS,
            Constants.PATCH_INSTALLATION_SUMMARY: Constants.STATUS_SUCCESS,
            Constants.PATCH_METADATA_FOR_HEALTHSTORE: Constants.STATUS_SUCCESS,
        }

    def assert_status_file_substatuses(self, substatus_expectations=None):
        """Check if the status file has a specific substatus"""
        if substatus_expectations is None:
            substatus_expectations = self.get_default_substatus_expectations()

        for key, value in substatus_expectations.items():
            if self.__substatus_high_level_summary[key]["index"] == -1:
                raise AssertionError("Expected substatus not found: {0}".format(key))
            if self.__substatus_high_level_summary[key]["status"] != value:
                raise AssertionError("Substatus expectations do not match for {0}. Expected: {1}, Actual: {2}".format(key, value, self.__substatus_high_level_summary[key]["status"]))

    def assert_summary_has_patch(self, operation, patch_name, classification=None, patchId=None):
        """ Check if the defined operation summary has a specific patch """
        substatus_index = self.__substatus_high_level_summary[operation]["index"]
        if substatus_index == -1:
            raise AssertionError("Substatus index not found for operation: {0}".format(operation))

        summary = self.__substatus_file_data[substatus_index]
        summary_patches = json.loads(summary["formattedMessage"]["message"])["patches"]

        for patch in summary_patches:
            if patch["name"] == patch_name:
                if classification and classification not in patch["classifications"]:
                    raise AssertionError("Classification '{0}' does not match expected value '{1}' for patch '{2}'.".format(classification, str(patch["classifications"]), patch_name))
                if patchId and patchId != str(patch["patchId"]):
                    raise AssertionError("Patch ID '{0}' does not match expected value '{1}' for patch '{2}'.".format(patchId, str(patch["patchId"]), patch_name))
                return True

        raise AssertionError("Patch '{0}' not found in '{1}' summary.".format(patch_name, operation))

    def assert_healthstore_status_info(self, patch_version, should_report=True):
        """Check if the healthstore patch version is as expected"""
        if self.healthstore_substatus_index is None:
            raise AssertionError("Healthstore substatus index not found.")

        healthstore_summary = json.loads(self.__substatus_file_data[self.healthstore_substatus_index]["formattedMessage"]["message"])

        if should_report and healthstore_summary["shouldReportToHealthStore"] != True:
            raise AssertionError("Healthstore summary should report to healthstore.")

        if patch_version != healthstore_summary["patchVersion"]:
            raise AssertionError("Healthstore summary patch version '{0}' does not match expected value {1}.".format(str(healthstore_summary["patchVersion"]), patch_version))
