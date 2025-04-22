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

        self.substatus_index_count = 0
        self.configure_patching_substatus_index = self.patch_assessment_substatus_index = self.patch_installation_substatus_index =  self.healthstore_substatus_index = None
        self.__populate_substatus_indices()

    def __read_status_file(self, status_file_path):
        with self.__env_layer.file_system.open(status_file_path, 'r') as file_handle:
            return json.load(file_handle)[0]["status"]["substatus"]

    def __populate_substatus_indices(self):
        for index, substatus in enumerate(self.__substatus_file_data):
            if substatus["name"] == Constants.CONFIGURE_PATCHING_SUMMARY:
                self.configure_patching_substatus_index = index
            elif substatus["name"] == Constants.PATCH_ASSESSMENT_SUMMARY:
                self.patch_assessment_substatus_index = index
            elif substatus["name"] == Constants.PATCH_INSTALLATION_SUMMARY:
                self.patch_installation_substatus_index = index
            elif substatus["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE:
                self.healthstore_substatus_index = index

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
            if key == Constants.CONFIGURE_PATCHING_SUMMARY and self.__substatus_file_data[self.configure_patching_substatus_index]['status'].lower() != value.lower():
                raise AssertionError("Substatus expectations do not match for {0}.".format(key))
            elif key == Constants.PATCH_ASSESSMENT_SUMMARY and self.__substatus_file_data[self.patch_assessment_substatus_index]['status'].lower() != value.lower():
                raise AssertionError("Substatus expectations do not match for {0}.".format(key))
            elif key == Constants.PATCH_INSTALLATION_SUMMARY and self.__substatus_file_data[self.patch_installation_substatus_index]['status'].lower() != value.lower():
                raise AssertionError("Substatus expectations do not match for {0}.".format(key))
            elif key == Constants.PATCH_METADATA_FOR_HEALTHSTORE and self.__substatus_file_data[self.healthstore_substatus_index]['status'].lower() != value.lower():
                raise AssertionError("Substatus expectations do not match for {0}.".format(key))

    def assert_assessment_summary_has_patch(self, patch_name, classification=None, patchId=None):
        """Check if the assessment summary has a specific patch"""
        if self.patch_assessment_substatus_index is None:
            raise AssertionError("Patch assessment substatus index not found.")

        assessment_summary = self.__substatus_file_data[self.patch_assessment_substatus_index]
        assessment_summary_patches = json.loads(assessment_summary["formattedMessage"]["message"])["patches"]

        for patch in assessment_summary_patches:
            if patch["name"] == patch_name:
                if classification and classification not in patch["classifications"]:
                    raise AssertionError("Classification '{classification}' does not match expected value.")
                if patchId and patch["patchId"] != patchId:
                    raise AssertionError("Patch ID '{patchId}' does not match expected value.")
                return True

        raise AssertionError("Patch '{patch_name}' not found in assessment summary.")

    def assert_installation_summary_has_patch(self, patch_name, classification=None, patchId=None):
        """Check if the installation summary has a specific patch"""
        if self.patch_assessment_substatus_index is None:
            raise AssertionError("Patch assessment substatus index not found.")

        installation_summary = self.__substatus_file_data[self.patch_assessment_substatus_index]
        installation_summary_patches = json.loads(installation_summary["formattedMessage"]["message"])["patches"]

        for patch in installation_summary_patches:
            if patch["name"] == patch_name:
                if classification and classification not in patch["classifications"]:
                    raise AssertionError("Classification '{classification}' does not match expected value.")
                if patchId and patchId not in str(patch["patchId"]):
                    raise AssertionError("Patch ID '{patchId}' does not match expected value.")
                return True

        raise AssertionError("Patch '{patch_name}' not found in assessment summary.")

    def assert_healthstore_status_info(self, patch_version, should_report=True):
        """Check if the healthstore patch version is as expected"""
        if self.healthstore_substatus_index is None:
            raise AssertionError("Healthstore substatus index not found.")

        healthstore_summary = json.loads(self.__substatus_file_data[self.healthstore_substatus_index]["formattedMessage"]["message"])

        if should_report and healthstore_summary["shouldReportToHealthStore"] != True:
            raise AssertionError("Healthstore summary should report to healthstore.")

        if patch_version != healthstore_summary["patchVersion"]:
            raise AssertionError("Healthstore summary patch version does not match expected value.")
