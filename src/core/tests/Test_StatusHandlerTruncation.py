# Copyright 2023 Microsoft Corporation
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
import json
import os
import random
import sys
import string
import tempfile
import time
import unittest
from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestStatusHandlerTruncation(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True)
        self.container = self.runtime.container
        self.__expected_truncated_patch_count = 0

    def tearDown(self):
        self.__expected_truncated_patch_count = 0
        self.runtime.stop()

    def test_assessment_patches_under_size_limit_not_truncated(self):
        """ Perform no truncation on assessment patches.
        Before truncation: 500 assessment patches in status,
        completed status file byte size: 92kb
        Expected (After truncation): 500 assessment patches in status
        operation: Assessment,
        assessment substatus name: PatchAssessmentSummary,
        assessment substatus status: success,
        assessment errors code: 0 (success),
        assessment errors details count: 0,
        completed status file byte size: 92kb. """

        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count = 500
        self.__expected_truncated_patch_count = 500
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)
        self.runtime.status_handler.log_truncated_patches()

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, patch_count, is_under_internal_size_limit=True, is_truncated=False)

        # Assert no truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]

        self.assertEqual(len(json.dumps(substatus_file_data).encode('utf-8')), len(json.dumps(complete_substatus_file_data).encode('utf-8')))  # Assert both files have same bytes
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, patch_count, is_under_internal_size_limit=True, is_truncated=False)

        # Assert 'Count of patches removed from: [Assessment=xxx] [Installation=0] log message is called
        self.__assert_truncated_patches_removed(complete_substatus_file_data, patch_count_assessment=patch_count)

    def test_only_assessment_patches_over_size_limit_truncated(self):
        """ Perform truncation on very large assessment patches and checks for time performance concern.
        Before truncation: 100000 assessment patches in status
        complete status file byte size: 19,022kb,
        Expected (After truncation): 672 assessment patches in status
        operation: Assessment,
        assessment substatus name: PatchAssessmentSummary,
        assessment substatus status: warning,
        assessment errors code: 0 (success),
        assessment errors details count: 0,
        count of assessment patches removed: 99328,
        truncated status file byte size: 126kb. """

        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count = 100000
        self.__expected_truncated_patch_count = 672
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions, "Critical")
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)
        self.runtime.status_handler.log_truncated_patches()

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, patch_count)

        # Assert assessment truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)[0]

        # Assert truncated status file size
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING, patch_count, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert all assessment fields in the message json are equal in both status files
        self.__assert_assessment_truncated_msg_fields(complete_substatus_file_data, truncated_substatus_file_data)

        self.assertEqual(patch_count - self.__expected_truncated_patch_count, self.runtime.status_handler.get_num_assessment_patches_removed())

        # Assert 'Count of patches removed from: [Assessment=xxx] [Installation=0] log message is called
        self.__assert_truncated_patches_removed(truncated_substatus_file_data, patch_count_assessment=patch_count)

    def test_only_assessment_patches_over_size_limit_with_status_error_truncated(self):
        """ Perform truncation on assessment patches and substatus status is set to Error (not warning) due to per-existing patching errors
        Before truncation: 1000 assessment patches in status, 6 exceptions
        completed status file byte size: 188kb
        Expected (After truncation): 670 assessment patches in status
        operation: Assessment,
        assessment substatus name: PatchAssessmentSummary,
        assessment substatus status: error,
        assessment errors code: 1 (error),
        assessment errors details count: 5,
        count of assessment patches removed: 330,
        truncated status file byte size: 126kb. """

        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count = 1000
        self.__expected_truncated_patch_count = 670
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions, "Security")

        # Set up complete status file before exceptions
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        # Assert complete status file size > 128kb and no exceptions
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, 'transitioning', patch_count)

        # Set up complete status file with exception errors
        self.__add_multiple_exception_errors()
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
        self.runtime.status_handler.log_truncated_patches()

        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        # Assert complete status file with exception errors
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_ERROR, patch_count, errors_count=5, errors_code=Constants.PatchOperationTopLevelErrorCode.ERROR)

        # Assert assessment truncated status file with multi exception errors
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)[0]

        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_ERROR, patch_count,
            errors_count=5, errors_code=Constants.PatchOperationTopLevelErrorCode.ERROR, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert all assessment fields in the message json are equal in both status files
        self.__assert_assessment_truncated_msg_fields(complete_substatus_file_data, truncated_substatus_file_data)

        # Assert 'Count of patches removed from: [Assessment=xxx] [Installation=0] log message is called
        self.__assert_truncated_patches_removed(truncated_substatus_file_data, patch_count_assessment=patch_count)

    def test_only_installation_under_size_limit_not_truncated(self):
        """ Perform no truncation on installation patches.
        Before truncation: 500 installation patches in status
        completed status file byte size: 114kb,
        Expected (After truncation): 500 installation patches in status
        operation: Installation,
        installation substatus name: PatchInstallationSummary,
        installation substatus status: success,
        installation errors code: 0 (success),
        installation errors details count: 0,
        count of installation patches removed: 0,
        completed status file byte size: 114kb. """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        # Set up tmp file store all log/print message and set sys.stdout point to it.
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__create_tmp_file_for_log_and_set_stdout()

        patch_count = 500
        self.__expected_truncated_patch_count = 500
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)
        self.runtime.status_handler.log_truncated_patches()

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, patch_count, is_under_internal_size_limit=True, is_truncated=False)

        # Assert no truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]

        self.assertEqual(len(json.dumps(substatus_file_data).encode('utf-8')), len(json.dumps(complete_substatus_file_data).encode('utf-8')))  # Assert both files have same bytes
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, patch_count, is_under_internal_size_limit=True, is_truncated=False)

        # Assert 'Count of patches removed from: [Assessment=0] [Installation=0] log message is called
        self.__assert_truncated_patches_removed(substatus_file_data, patch_count_installation=patch_count)

        # Reset sys.stdout, close and delete tmp file
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__remove_tmp_file_reset_stdout()

    def test_only_installation_patches_over_size_limit_truncated(self):
        """ Perform truncation on very large installation patches and checks for time performance concern.
        Before truncation: 100000 installation patches in status
        complete status file byte size: 22,929kb,
        Expected (After truncation): 555 installation patches in status
        operation: Installation,
        installation substatus name: PatchInstallationSummary,
        installation substatus status: warning,
        installation errors code: 0 (success),
        installation errors details count: 0,
        count of installation patches removed: 99445,
        truncated status file byte size: 126kb. """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        # Set up tmp file store all log/print message and set sys.stdout point to it.
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__create_tmp_file_for_log_and_set_stdout()

        patch_count = 100000
        self.__expected_truncated_patch_count = 555
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)
        self.runtime.status_handler.log_truncated_patches()

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY,
            Constants.STATUS_SUCCESS, patch_count)

        # Assert installation truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)[0]

        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY,
            Constants.STATUS_WARNING, patch_count, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert all installation fields in the message json are equal in both status files
        self.__assert_installation_truncated_msg_fields(complete_substatus_file_data, truncated_substatus_file_data)

        # Assert 'Count of patches removed from: [Assessment=0] [Installation=xxx] log message is called
        self.__assert_truncated_patches_removed(truncated_substatus_file_data, patch_count_installation=patch_count)

        # Reset sys.stdout, close and delete tmp file
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__remove_tmp_file_reset_stdout()

    def test_only_installation_low_priority_patches_over_size_limit_truncated(self):
        """ Perform truncation on only installation with low priority patches (Pending, Exclude, Not_Selected), truncated status files have no Not_Selected patches.
        Before truncation: 1040 installation patches in status
        complete status file byte size: 235kb,
        Expected (After truncation): 559 installation patches in status
        operation: Installation,
        installation substatus name: PatchInstallationSummary,
        installation substatus status: warning,
        installation errors code: 0 (success),
        installation errors details count: 0,
        last complete status file installation patch state: Not_Selected
        first truncated installation patch state: Pending,
        last truncated installation patch state: Excluded,
        count of installation patches removed: 481,
        truncated status file byte size: 126kb. """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        # Set up tmp file store all log/print message and set sys.stdout point to it.
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__create_tmp_file_for_log_and_set_stdout()

        patch_count_pending = 400
        patch_count_exclude = 600
        patch_count_not_selected = 40
        self.__expected_truncated_patch_count = 559

        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_pending)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions)

        # random_char=random.choice(string.ascii_letters) ensure the packages are unique due to __set_up_packages_func remove duplicates
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_exclude, random_char=random.choice(string.ascii_letters))
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.EXCLUDED)

        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_not_selected, random_char=random.choice(string.ascii_letters))
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.NOT_SELECTED)

        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)
        self.runtime.status_handler.log_truncated_patches()

        patch_count = patch_count_pending + patch_count_exclude + patch_count_not_selected

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        # Assert last patch's installation state is Not_Selected
        installation_msg = self.__get_message_json_from_substatus(complete_substatus_file_data)
        self.assertEqual(installation_msg['patches'][-1]['patchInstallationState'], Constants.NOT_SELECTED)
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, patch_count)

        # Assert installation truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)[0]

        # Assert first patch's installation state is Pending, last patch's installation state is Excluded
        installation_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        self.assertEqual(installation_truncated_msg['patches'][0]['patchInstallationState'], Constants.PENDING)
        self.assertEqual(installation_truncated_msg['patches'][-1]['patchInstallationState'], Constants.EXCLUDED)

        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING, patch_count, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert all installation fields in the message json are equal in both status files
        self.__assert_installation_truncated_msg_fields(complete_substatus_file_data, truncated_substatus_file_data)

        # Assert 'Count of patches removed from: [Assessment=0] [Installation=xxx] log message is called
        self.__assert_truncated_patches_removed(truncated_substatus_file_data, patch_count_installation=patch_count)

        # Reset sys.stdout, close and delete tmp file
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__remove_tmp_file_reset_stdout()

    def test_only_installation_patches_over_size_limit_with_status_error_truncated(self):
        """ Perform truncation on installation patches and substatus status is set to Error (not warning) due to per-existing patching errors
        Before truncation: 800 installation patches in status, 6 exceptions
        completed status file byte size: 182kb,
        Expected (After truncation): 553 installation patches in status
        operation: Installation,
        installation substatus name: PatchInstallationSummary,
        installation substatus status: error,
        installation errors code: 1 (error),
        installation errors details count: 5,
        count of installation patches removed: 247,
        truncated status file byte size: 126kb. """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        # Set up tmp file store all log/print message and set sys.stdout point to it.
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__create_tmp_file_for_log_and_set_stdout()

        # set up for expected variables use in assertions
        self.__expected_truncated_patch_count = 553

        patch_count = 800
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)

        # Set up complete status file before exceptions
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        # Assert complete status file size > 128kb and no exception errors
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, 'transitioning', patch_count)

        # Set up complete status file with exception errors
        self.__add_multiple_exception_errors()
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)
        self.runtime.status_handler.log_truncated_patches()

        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        # Assert complete status file with multi exception errors
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, patch_count, errors_count=5, errors_code=Constants.PatchOperationTopLevelErrorCode.ERROR)

        # Assert installation truncated status file with multi exception errors
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)[0]

        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, patch_count,
            errors_count=5, errors_code=Constants.PatchOperationTopLevelErrorCode.ERROR, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert all installation fields in the message json are equal in both status files
        self.__assert_installation_truncated_msg_fields(complete_substatus_file_data, truncated_substatus_file_data)

        # Assert 'Count of patches removed from: [Assessment=0] [Installation=xxx] log message is called
        self.__assert_truncated_patches_removed(truncated_substatus_file_data, patch_count_installation=patch_count)

        # Reset sys.stdout, close and delete tmp file
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__remove_tmp_file_reset_stdout()

    def test_both_assessment_and_installation_over_size_limit_truncated(self):
        """ Perform truncation on assessment/installation patches.
        Before truncation: 700 assessment patches in status, 1200 installation patches in status
        complete status file byte size: 242kb,
        Expected (After truncation): 374 assessment patches in status, 250 installation patches in status
        operation: Installation,
        substatus name: [assessment=PatchAssessmentSummary][installation=PatchInstallationSummary],
        substatus status: [assessment=warning][installation=warning],
        errors code: [assessment=0 (success)][installation=0 (success)],
        errors details count: [assessment=0][installation=0],
        count of patches removed from log: [assessment=326[installation=950],
        truncated status file byte size: 126kb. """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        # Set up tmp file store all log/print message and set sys.stdout point to it.
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__create_tmp_file_for_log_and_set_stdout()

        patch_count_assessment = 700
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_assessment)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        patch_count_pending = 250
        patch_count_installed = 250
        patch_count_installation = patch_count_pending + patch_count_installed

        # random_char=random.choice(string.ascii_letters) ensure the packages are unique due to __set_up_packages_func remove duplicates
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_pending, random_char=random.choice(string.ascii_letters))
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions)

        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_installed)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)
        self.runtime.status_handler.log_truncated_patches()

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        # Assert assessment summary
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS,
            patch_count_assessment)

        # Assert installation summary
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS,
            patch_count_installation, substatus_index=1)

        # Assert truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)[0]

        # Assert assessment truncation
        self.__expected_truncated_patch_count = 374
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING, patch_count_assessment, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert all assessment fields in the message json are equal in both status files
        self.__assert_assessment_truncated_msg_fields(complete_substatus_file_data, truncated_substatus_file_data)

        # Assert installation truncation
        self.__expected_truncated_patch_count = 250
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING, patch_count_installation, substatus_index=1, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert all installation fields in the message json are equal in both status files
        self.__assert_installation_truncated_msg_fields(complete_substatus_file_data, truncated_substatus_file_data, substatus_index=1)

        # Assert 'Count of patches removed from: [Assessment=xxx] [Installation=xxx] log message is called
        self.__assert_truncated_patches_removed(truncated_substatus_file_data, patch_count_assessment=patch_count_assessment, patch_count_installation=patch_count_installation, substatus_index=1)

        # Reset sys.stdout, close and delete tmp file
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__remove_tmp_file_reset_stdout()

    def test_both_assessment_and_installation__keep_min_5_assessment_patches_truncated(self):
        """ Perform truncation on very large assessment / installation patches and checks for time performance concern. but keep min 5 assessment patches.
        Before truncation: 100000 assessment patches in status, 100000 installation patches in status
        complete status file byte size: 41,658kb,
        Expected (After truncation): 5 assessment patches in status, 549 installation patches in status
        operation: Installation,
        substatus name: [assessment=PatchAssessmentSummary][installation=PatchInstallationSummary],
        substatus status: [assessment=warning][installation=warning],
        errors code: [assessment=0 (success)][installation=0 (success)],
        errors details count: [assessment=0][installation=0],
        count of patches removed from log: [assessment=99995[installation=99451],
        truncated status file byte size: 126kb. """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        # Set up tmp file store all log/print message and set sys.stdout point to it.
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__create_tmp_file_for_log_and_set_stdout()

        patch_count_assessment = 100000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_assessment)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        patch_count_installation = 100000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_installation)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)
        self.runtime.status_handler.log_truncated_patches()
        
        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        # Assert assessment summary
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS,
            patch_count_assessment)

        # Assert installation summary
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS,
            patch_count_installation, substatus_index=1)

        # Assert truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)[0]

        # Assert assessment truncation
        self.__expected_truncated_patch_count = 5
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING, patch_count_assessment, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert all assessment fields in the message json are equal in both status files
        self.__assert_assessment_truncated_msg_fields(complete_substatus_file_data, truncated_substatus_file_data)

        # Assert installation truncation
        self.__expected_truncated_patch_count = 549
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING, patch_count_installation, substatus_index=1, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert all installation fields in the message json are equal in both status files
        self.__assert_installation_truncated_msg_fields(complete_substatus_file_data, truncated_substatus_file_data, substatus_index=1)
        
        # Assert 'Count of patches removed from: [Assessment=xxx] [Installation=xxx] log message is called
        self.__assert_truncated_patches_removed(truncated_substatus_file_data, patch_count_assessment=patch_count_assessment, patch_count_installation=patch_count_installation, substatus_index=1)

        # Reset sys.stdout, close and delete tmp file
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__remove_tmp_file_reset_stdout()

    def test_both_assessment_and_installation_with_status_error_truncated(self):
        """ Perform truncation on assessment / installation patches but installation substatus status is set to Error (not warning) due to per-existing patching errors
        Before truncation: 800 assessment patches in status, 800 installation patches in status with 6 exception errors
        complete status file byte size: > 128kb,
        Expected (After truncation): 5 assessment patches in status, 547 installation patches in status
        operation: Installation,
        substatus name: [assessment=PatchAssessmentSummary][installation=PatchInstallationSummary],
        substatus status: [assessment=warning][installation=error],
        errors code: [assessment=0 (success)][installation=1 (error)],
        errors details count: [assessment=0][installation=5],
        count of patches removed from log: [assessment=795][installation=253],
        truncated status file byte size: < 126kb """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        # Set up tmp file store all log/print message and set sys.stdout point to it.
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__create_tmp_file_for_log_and_set_stdout()

        patch_count_assessment = 800
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_assessment)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions, "Security")

        patch_count_installation = 1000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_installation)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Set up complete status file before errors
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        # Assert complete status file size > 128kb and no exceptions
        # Assert no assessment message errors
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, patch_count_assessment)

        # Assert no installation message errors
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, 'transitioning', patch_count_installation, substatus_index=1)

        # Set up complete status file with exception errors - installation
        self.__add_multiple_exception_errors()
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)
        self.runtime.status_handler.log_truncated_patches()

        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            complete_substatus_file_data = json.load(file_handle)[0]

        # Assert installation status file with multi error exceptions
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, patch_count_installation, errors_count=5, errors_code=Constants.PatchOperationTopLevelErrorCode.ERROR, substatus_index=1)

        # Assert truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)[0]

        # Assert assessment truncated
        self.__expected_truncated_patch_count = 5
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING, patch_count_assessment, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert all assessment fields in the message json are equal in both status files
        self.__assert_assessment_truncated_msg_fields(complete_substatus_file_data, truncated_substatus_file_data)

        # Assert installation truncated status file with multi exceptions
        self.__expected_truncated_patch_count = 547
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, patch_count_installation,
            errors_count=5, errors_code=Constants.PatchOperationTopLevelErrorCode.ERROR, substatus_index=1, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert all installation fields in the message json are equal in both status files
        self.__assert_installation_truncated_msg_fields(complete_substatus_file_data, truncated_substatus_file_data, substatus_index=1)

        # Assert 'Count of patches removed from: [Assessment=xxx] [Installation=xxx] log message is called
        self.__assert_truncated_patches_removed(truncated_substatus_file_data, patch_count_assessment=patch_count_assessment, patch_count_installation=patch_count_installation, substatus_index=1)

        # Reset sys.stdout, close and delete tmp file
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__remove_tmp_file_reset_stdout()

    def test_truncation_method_time_performance(self):
        """ Perform truncation on very large packages to
        assert truncation code logic time performance is only 30 secs more than current (no truncation) code logic"""

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        # Set up tmp file store all log/print message and set sys.stdout point to it.
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__create_tmp_file_for_log_and_set_stdout()


        # Start performance test prior truncation
        Constants.StatusTruncationConfig.TURN_ON_TRUNCATION = False
        start_time_no_truncation = time.time()
        for i in range(0, 301):
            test_packages, test_package_versions = self.__set_up_packages_func(500)
            self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
            self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)

        end_time_no_truncation = time.time()
        performance_time_no_truncation = end_time_no_truncation - start_time_no_truncation 
        performance_time_formatted_no_truncation = self.__convert_performance_time_to_date_time_format(performance_time_no_truncation )

        # Start truncation performance test
        Constants.StatusTruncationConfig.TURN_ON_TRUNCATION = True
        start_time_with_truncation = time.time()
        for i in range(0, 301):
            test_packages, test_package_versions = self.__set_up_packages_func(500)
            self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
            self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)

        end_time_with_truncation = time.time()
        performance_time_with_truncation = end_time_with_truncation - start_time_with_truncation
        performance_time_formatted_with_truncation = self.__convert_performance_time_to_date_time_format(performance_time_with_truncation)

        # Reset sys.stdout, close and delete tmp file
        # Note: sys log/print will not display in terminal, for debugging comment __remove_tmp_file_reset_stdout and check the tmp file
        self.__remove_tmp_file_reset_stdout()

        self.runtime.status_handler.composite_logger.log_debug('performance_time_formatted_no_truncation ' + performance_time_formatted_no_truncation )
        self.runtime.status_handler.composite_logger.log_debug('performance_time_formatted_with_truncation' + performance_time_formatted_with_truncation)
        self.assertTrue((performance_time_with_truncation - performance_time_no_truncation) < 30)

    # Setup functions for testing
    def __assert_patch_summary_from_status(self, substatus_file_data, operation, patch_summary, status, patch_count, errors_count=0,
            errors_code=Constants.PatchOperationTopLevelErrorCode.SUCCESS, substatus_index=0, complete_substatus_file_data=None, is_under_internal_size_limit=False, is_truncated=False):

        message = json.loads(substatus_file_data["status"]["substatus"][substatus_index]["formattedMessage"]["message"])
        status_file_patch_count = len(message["patches"])
        self.assertEqual(substatus_file_data["status"]["operation"], operation)

        if is_under_internal_size_limit:
            # Assert status file size < 126kb n 128kb
            substatus_file_in_bytes = len(json.dumps(substatus_file_data).encode('utf-8'))
            self.assertTrue(substatus_file_in_bytes < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
            self.assertTrue(substatus_file_in_bytes <= Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)

            if is_truncated:
                self.assertEqual(status_file_patch_count, self.__expected_truncated_patch_count)
                self.assertTrue(status_file_patch_count < patch_count)  # Assert length of truncated patches < patch_count post truncation
                self.assertTrue(substatus_file_in_bytes < len(json.dumps(complete_substatus_file_data).encode('utf-8')))  # Assert truncated status file size < completed status file size
        else:
            self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)  # Assert complete status file size > 128kb
            self.assertEqual(status_file_patch_count, patch_count)  # Assert length of message patches == patch_count prior truncation

        # Assert patch summary data
        substatus_file_data = substatus_file_data["status"]["substatus"][substatus_index]
        self.assertEqual(substatus_file_data["name"], patch_summary)
        self.assertEqual(substatus_file_data["status"], status.lower())
        # assert error
        self.assertEqual(message["errors"]["code"], errors_code)
        self.assertEqual(len(message["errors"]["details"]), errors_count)

        if errors_count > 0:
            self.assertEqual(message["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            self.assertEqual(message["errors"]["details"][1]["code"], Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)

    def __add_multiple_exception_errors(self):
        # Adding multiple exception errors
        self.runtime.status_handler.add_error_to_status("exception0", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception1", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception2", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception3", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception4", Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
        self.runtime.status_handler.add_error_to_status("exception5", Constants.PatchOperationErrorCodes.OPERATION_FAILED)

    def __assert_assessment_truncated_msg_fields(self, complete_substatus_file_data, truncated_substatus_file_data):
        assessment_msg = self.__get_message_json_from_substatus(complete_substatus_file_data)
        assessment_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)

        self.assertEqual(assessment_msg['assessmentActivityId'], assessment_truncated_msg['assessmentActivityId'])
        self.assertEqual(assessment_msg['rebootPending'], assessment_truncated_msg['rebootPending'])
        self.assertEqual(assessment_msg['criticalAndSecurityPatchCount'], assessment_truncated_msg['criticalAndSecurityPatchCount'])
        self.assertEqual(assessment_msg['otherPatchCount'], assessment_truncated_msg['otherPatchCount'])
        self.assertEqual(assessment_msg['startTime'], assessment_truncated_msg['startTime'])
        self.assertEqual(assessment_msg['lastModifiedTime'], assessment_truncated_msg['lastModifiedTime'])
        self.assertEqual(assessment_msg['startedBy'], assessment_truncated_msg['startedBy'])

    def __assert_installation_truncated_msg_fields(self, complete_substatus_file_data, truncated_substatus_file_data, substatus_index=0):
        installation_msg = self.__get_message_json_from_substatus(complete_substatus_file_data, substatus_index=substatus_index)
        installation_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data, substatus_index=substatus_index)

        self.assertEqual(installation_msg['installationActivityId'], installation_truncated_msg['installationActivityId'])
        self.assertEqual(installation_msg['rebootStatus'], installation_truncated_msg['rebootStatus'])
        self.assertEqual(installation_msg['maintenanceWindowExceeded'], installation_truncated_msg['maintenanceWindowExceeded'])
        self.assertEqual(installation_msg['notSelectedPatchCount'], installation_truncated_msg['notSelectedPatchCount'])
        self.assertEqual(installation_msg['excludedPatchCount'], installation_truncated_msg['excludedPatchCount'])
        self.assertEqual(installation_msg['pendingPatchCount'], installation_truncated_msg['pendingPatchCount'])
        self.assertEqual(installation_msg['installedPatchCount'], installation_truncated_msg['installedPatchCount'])
        self.assertEqual(installation_msg['failedPatchCount'], installation_truncated_msg['failedPatchCount'])
        self.assertEqual(installation_msg['startTime'], installation_truncated_msg['startTime'])
        self.assertEqual(installation_msg['lastModifiedTime'], installation_truncated_msg['lastModifiedTime'])
        self.assertEqual(installation_msg['maintenanceRunId'], installation_truncated_msg['maintenanceRunId'])

    def __get_message_json_from_substatus(self, substatus_file_data, substatus_index=0):
        return json.loads(substatus_file_data["status"]["substatus"][substatus_index]["formattedMessage"]["message"])

    def __convert_performance_time_to_date_time_format(self, performance_time):
        performance_time = abs(performance_time)

        # Calc days, hours, minutes, and seconds
        days, remainder = divmod(performance_time, 86400)  # 86400 seconds in a day
        hours, remainder = divmod(remainder, 3600)  # 3600 seconds in an hour
        minutes, seconds = divmod(remainder, 60)  # 60 seconds in a minute

        # Format the result
        formatted_time = "%d days, %d hours, %d minutes, %.6f seconds" % (int(days), int(hours), int(minutes), seconds)
        return formatted_time

    def __create_tmp_file_for_log_and_set_stdout(self):
        """ Redirect sys console output to a tmp file directory for asserting log message output """
        # Set up create tmp file for log and set sys.stdout to it
        self.temp_stdout = tempfile.NamedTemporaryFile(delete=False, mode="w+")
        # print('tmp file directory', self.temp_stdout.name)  # use for debugging get tmp file to see output message. DO NOT DELETE!
        self.saved_stdout = sys.stdout  # Save the original stdout
        sys.stdout = self.temp_stdout  # set it to the tmp file

    def __remove_tmp_file_reset_stdout(self):
        sys.stdout = self.saved_stdout  # redirect to original stdout
        self.temp_stdout.close()
        os.remove(self.temp_stdout.name)  # Remove the tmp file

    def __assert_truncated_patches_removed(self, substatus_file_data, patch_count_assessment=0, patch_count_installation=0, substatus_index=0):
        assessment_truncated_patches = 0 if patch_count_assessment == 0 else len(self.__get_message_json_from_substatus(substatus_file_data)['patches'])
        installation_truncated_patches = 0 if patch_count_installation == 0 else len(self.__get_message_json_from_substatus(substatus_file_data, substatus_index=substatus_index)['patches'])
        self.assertEqual(patch_count_assessment - assessment_truncated_patches, self.runtime.status_handler.get_num_assessment_patches_removed())
        self.assertEqual(patch_count_installation - installation_truncated_patches, self.runtime.status_handler.get_num_installation_patches_removed())

    def __set_up_packages_func(self, val, random_char=None):
        """ populate packages and versions for truncation """
        test_packages = []
        test_package_versions = []

        for i in range(0, val):
            test_packages.append('python-samba' + str(i))

            if random_char is not None:
                test_package_versions.append('2:4.4.5+dfsg-2ubuntu€' + random_char)
            else:
                test_package_versions.append('2:4.4.5+dfsg-2ubuntu€')

        return test_packages, test_package_versions

if __name__ == '__main__':
    unittest.main()
