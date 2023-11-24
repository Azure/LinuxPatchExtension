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
import glob
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

    def tearDown(self):
        self.runtime.stop()

    def test_assessment_patches_under_size_limit_not_truncated(self):
        """ Perform no truncation on assessment patches.
        Expecting:
        assessment substatus status: success,
        no assessment tombstone records,
        assessment errors code: 0 (success),
        assessment errors details code: 0 (success). """

        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count = 500
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__assert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert no truncated status file
        self.__assert_no_truncation_status_file(Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, patch_count)

    def test_only_assessment_patches_over_size_limit_truncated(self):
        """ Perform truncation on assessment patches.
        Expecting:
        assessment substatus status: warning,
        assessment tombstone records,
        assessment errors code: 2 (warning),
        assessment errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists. """

        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        assessment_msg = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, is_under_agent_size_limit=False)
        self.__assert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert assessment truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)

        assessment_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        # Assert length of truncated patches < length of complete status file patches
        self.assertTrue(len(assessment_truncated_msg["patches"]) < patch_count)
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING)

        # Assert truncated error
        self.__assert_truncated_error(truncated_substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # Assert all assessment fields in the message json are equal in both status files
        self.__assert_assessment_truncated_msg_fields(assessment_msg, assessment_truncated_msg)

    def test_only_assessment_patches_large_size_limit_truncated(self):
        """ Perform truncation on very large assessment patches for time performance.
        Expecting:
        assessment substatus status: warning,
        assessment tombstone records,
        assessment errors code: 2 (warning),
        assessment errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists. """

        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count = 100000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions, "Critical")
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        assessment_msg = self.__get_message_json_from_substatus(substatus_file_data)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, is_under_agent_size_limit=False)
        self.__assert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert assessment truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)

        # Assert truncated status file size
        assessment_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        self.assertTrue(len(assessment_truncated_msg["patches"]) < patch_count)
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING)

        # Assert truncated error
        self.__assert_truncated_error(truncated_substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # Assert all assessment fields in the message json are equal in both status files
        self.__assert_assessment_truncated_msg_fields(assessment_msg, assessment_truncated_msg)

    def test_only_assessment_patches_over_size_limit_with_exceptions_truncated(self):
        """ Perform truncation on assessment patches with multiple exceptions to ensure __try_add_error is working as expected and
        error code is 1, not 2 (warning)
        Expecting:
        assessment substatus status: error,
        assessment tombstone records,
        assessment errors code: 1 (error),
        assessment errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists. """

        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions, "Security")

        # Set up complete status file before exceptions
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        # Assert complete status file size > 128kb and no exceptions
        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        message = self.__get_message_json_from_substatus(substatus_file_data)
        self.assertEqual(len(message["errors"]["details"]), 0)

        # Set up complete status file after exceptions
        self.__add_multiple_exception_errors()
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)

        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        # Assert complete status file after exceptions
        self.__assert_status_file_data_multi_exceptions(substatus_file_data, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_ERROR, patch_count,
            count_errors_detail=5)

        # Assert assessment truncated status file with multi exceptions
        self.__assert_truncated_status_multi_errors(Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_ERROR, patch_count, error_count=5)

    def test_only_installation_under_size_limit_not_truncated(self):
        """ Perform no truncation on installation patches.
        Expecting:
        installation substatus status: success,
        no installation tombstone records,
        installation errors code: 0 (success),
        installation errors details code: 0 (success). """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count = 500
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, substatus_index=0)
        self.__assert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert no truncated status file
        self.__assert_no_truncation_status_file(Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, patch_count)

    def test_only_installation_patches_over_size_limit_truncated(self):
        """ Perform truncation on installation patches.
        Expecting:
        installation substatus status: warning,
        installation tombstone records,
        installation errors code: 2 (warning),
        installation errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists. """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        installation_msg = self.__get_message_json_from_substatus(substatus_file_data)

        # Assert complete status file
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS,
            substatus_index=0, is_under_agent_size_limit=False)
        self.__assert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert installation truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)

        installation_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        # Assert truncated patches < length of complete status file patches
        self.assertTrue(len(installation_truncated_msg["patches"]) < patch_count)
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING)

        # Assert truncated error
        self.__assert_truncated_error(truncated_substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # Assert all installation fields in the message json are equal in both status files
        self.__assert_installation_truncated_msg_fields(installation_msg, installation_truncated_msg)

    def test_only_installation_low_priority_patches_over_size_limit_truncated(self):
        """ Perform truncation on only installation with low priority patches (Pending, Exclude, Not_Selected).
        Expecting:
        installation substatus status: warning,
        installation tombstone records,
        installation errors code: 2 (warning),
        installation errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists. """
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count_pending = random.randint(1, 400)
        patch_count_exclude = random.randint(1, 100)
        patch_count_not_selected = random.randint(780, 1000)

        # random_char=random.choice(string.ascii_letters) ensure the packages are unique
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_pending)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions)

        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_exclude, random_char=random.choice(string.ascii_letters))
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.EXCLUDED)

        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_not_selected, random_char=random.choice(string.ascii_letters))
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.NOT_SELECTED)

        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        patch_count = patch_count_pending + patch_count_exclude + patch_count_not_selected

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        installation_msg = self.__get_message_json_from_substatus(substatus_file_data)

        # Assert complete status file
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS,
            substatus_index=0, is_under_agent_size_limit=False)
        self.__assert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert installation truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)

        installation_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        # Assert length of truncated patches < length of complete status file patches
        self.assertTrue(len(installation_truncated_msg["patches"]) < patch_count)
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING)

        # Assert truncated error
        self.__assert_truncated_error(truncated_substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # Assert all installation fields in the message json are equal in both status files
        self.__assert_installation_truncated_msg_fields(installation_msg, installation_truncated_msg)

    def test_only_installation_patches_large_size_limit_truncated(self):
        """ Perform truncation on very large installation patches for time performance.
        Expecting:
        installation substatus status: warning,
        installation tombstone records,
        installation errors code: 2 (warning),
        installation errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists. """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count = 100000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        installation_msg = self.__get_message_json_from_substatus(substatus_file_data)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS,
            substatus_index=0, is_under_agent_size_limit=False)
        self.__assert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert installation truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)

        installation_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        # Assert length of truncated patches < length of complete status file patches
        self.assertTrue(len(installation_truncated_msg["patches"]) < patch_count)
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING)

        # Assert truncated error
        self.__assert_truncated_error(truncated_substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # Assert all installation fields in the message json are equal in both status files
        self.__assert_installation_truncated_msg_fields(installation_msg, installation_truncated_msg)

    def test_only_installation_patches_over_size_limit_with_exceptions_truncated(self):
        """ Perform truncation on installation patches with multiple exceptions to ensure __try_add_error is working as expected and
        error code is 1, not 2 (warning)
        Expecting:
        installation substatus status: error,
        installation tombstone records,
        installation errors code: 1 (error),
        installation errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists. """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)

        # Set up complete status file before exceptions
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        # Assert complete status file size > 128kb and no exceptions
        self.assertTrue(len(json.dumps(substatus_file_data[0]["status"]["substatus"][0])) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        message = self.__get_message_json_from_substatus(substatus_file_data)
        self.assertEqual(len(message["errors"]["details"]), 0)

        # Set up complete status file after exceptions
        self.__add_multiple_exception_errors()
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)

        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)
        self.__assert_status_file_data_multi_exceptions(substatus_file_data, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, patch_count,
            count_errors_detail=5)

        # Assert installation truncated status file with multi exceptions
        self.__assert_truncated_status_multi_errors(Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, patch_count, error_count=5)

    def test_both_assessment_and_installation_over_size_limit_truncated(self):
        """ Perform truncation on very large assessment patches for time performance.
        Expecting:
        assessment substatus status: warning,
        assessment tombstone records,
        assessment errors code: 2 (warning),
        assessment errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists.

        Perform truncation on very large installation patches for time performance.
        Expecting:
        installation substatus status: warning,
        installation tombstone records,
        installation errors code: 2 (warning),
        installation errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists. """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count_for_assessment = 100000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_assessment)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        patch_count_for_installation = 100000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_installation)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)

        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)
        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        installation_msg = self.__get_message_json_from_substatus(substatus_file_data, substatus_index=1)
        # Assert assessment summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, is_under_agent_size_limit=False)
        self.__assert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count_for_assessment, error_count=0)

        # Assert installation summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS,
            substatus_index=1, is_under_agent_size_limit=False)
        self.__assert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][1], patch_count_for_installation, error_count=0)

        # Assert truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)

        assessment_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        installation_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data, substatus_index=1)

        # Assert length of truncated patches < length of complete status file patches
        self.assertTrue(len(assessment_truncated_msg["patches"]) + len(installation_truncated_msg["patches"]) < patch_count_for_assessment + patch_count_for_installation)

        # Assert assessment truncation
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY,
            Constants.STATUS_WARNING)

        # Assert assessment truncated error
        self.__assert_truncated_error(truncated_substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # Assert installation truncation
        installation_truncated_substatus = truncated_substatus_file_data[0]["status"]["substatus"][1]
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY,
            Constants.STATUS_WARNING, substatus_index=1)

        # Assert installation truncated error
        self.__assert_truncated_error(installation_truncated_substatus, error_count=0)

        # Assert all installation fields in the message json are equal in both status files
        self.__assert_installation_truncated_msg_fields(installation_msg, installation_truncated_msg)

    def test_keep_min_5_assessment_both_assessment_and_installation_truncated(self):
        """ Perform truncation on assessment patches.
        Expecting:
        assessment substatus status: warning,
        assessment tombstone records, but keep 5 packages
        assessment errors code: 2 (warning),
        assessment errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists.

        Perform truncation on installation patches.
        Expecting:
        installation substatus status: warning,
        installation tombstone records,
        installation errors code: 2 (warning),
        installation errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists. """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count_for_assessment = 7
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_assessment)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        patch_count_for_installation = 1000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_installation)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        assessment_msg = self.__get_message_json_from_substatus(substatus_file_data)
        installation_msg = self.__get_message_json_from_substatus(substatus_file_data, substatus_index=1)

        # Assert assessment summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, is_under_agent_size_limit=False)
        self.__assert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count_for_assessment, error_count=0)

        # Assert installation summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS,
            substatus_index=1, is_under_agent_size_limit=False)
        self.__assert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][1], patch_count_for_installation, error_count=0)

        # Assert truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)

        assessment_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        installation_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data, substatus_index=1)

        # Assert length of truncated patches < length of complete status file patches
        self.assertTrue(len(assessment_truncated_msg["patches"]) + len(installation_truncated_msg["patches"]) < patch_count_for_assessment + patch_count_for_installation)

        # Assert assessment truncation, keep min 5
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY,
            Constants.STATUS_WARNING)

        # Assert assessment truncated error
        self.__assert_truncated_error(truncated_substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # Assert all assessment fields in the message json are equal in both status files
        self.__assert_assessment_truncated_msg_fields(assessment_msg, assessment_truncated_msg)

        # Assert installation truncation
        installation_truncated_substatus = truncated_substatus_file_data[0]["status"]["substatus"][1]
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY,
            Constants.STATUS_WARNING, substatus_index=1)

        # Assert installation truncated error
        self.__assert_truncated_error(installation_truncated_substatus, error_count=0)

        # Assert all installation fields in the message json are equal in both status files
        self.__assert_installation_truncated_msg_fields(installation_msg, installation_truncated_msg)

    def test_exceptions_both_assessment_and_installation_truncated(self):
        """ Perform truncation on assessment patches with multiple errors to ensure __try_add_error is working as expected.
        Expecting:
        assessment substatus status: error,
        assessment tombstone records,
        assessment errors code: 1 (error),
        assessment errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists.

        Perform truncation on installation patches with multiple errors to ensure __try_add_error is working as expected.
        Expecting:
        installation substatus status: error,
        installation tombstone records,
        installation errors code: 1 (error),
        installation errors details code: patches were truncated to limit reporting data volume. In-VM logs contain complete lists. """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count_assessment = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_assessment)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions, "Security")

        patch_count_installation = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_installation)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Set up complete status file before errors
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        # Assert complete status file size > 128kb and no error
        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        # Assert no assessment message errors
        self.assertEqual(len(json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["errors"]["details"]), 0)
        # Assert no installation message errors
        self.assertEqual(len(json.loads(substatus_file_data[0]["status"]["substatus"][1]["formattedMessage"]["message"])["errors"]["details"]), 0)

        # Set up complete status file after errors - installation
        self.__add_multiple_exception_errors()
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)

        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        assessment_msg_with_errors = self.__get_message_json_from_substatus(substatus_file_data)
        installation_msg_with_errors = self.__get_message_json_from_substatus(substatus_file_data, substatus_index=1)

        # Assert installation status file with multi error exceptions
        self.__assert_status_file_data_multi_exceptions(substatus_file_data, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, patch_count_installation,
            count_errors_detail=5, substatus_index=1)

        # Assert assessment truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)

        # Assert length of truncated patches < length of completed patches
        assessment_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        installation_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data, substatus_index=1)
        self.assertTrue(len(assessment_truncated_msg["patches"]) + len(installation_truncated_msg["patches"]) < patch_count_assessment + patch_count_installation)

        # Assert assessment truncated
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY,
            Constants.STATUS_WARNING)

        # Assert truncated error
        self.__assert_truncated_error(truncated_substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # Assert all assessment fields in the message json are equal in both status files
        self.__assert_assessment_truncated_msg_fields(assessment_msg_with_errors, assessment_truncated_msg)

        # Assert installation truncated status file with multi errors
        self.__assert_truncated_status_multi_errors(Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, patch_count_installation, error_count=5,
            substatus_index=1)

        # Assert all installation fields in the message json are equal in both status files
        self.__assert_installation_truncated_msg_fields(installation_msg_with_errors, installation_truncated_msg)

    def test_log_truncated_patches_assert_not_truncated(self):
        """ Assert no truncation is performed on assessment/installation patches.
        Expecting
        'Count of patches removed from: [Assessment=0] [Installation=0] log message is called
        """

        # Set up temp file stor all log information and set sys.stdout point to it
        self.__create_tmp_file_for_log_and_set_stdout()

        # Assert no truncation log output
        patch_count = 500
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        self.runtime.status_handler.log_truncated_patches()
        self.__read_tmp_log_and_assert("Count of patches removed from: [Assessment=0] [Installation=0]")

        # Reset sys.stdout, close and delete tmp
        self.__remove_tmp_file_reset_stdout()

    def test_log_truncated_patches_assert_assessment_patches_truncated(self):
        """ Assert truncation is performed on assessment patches.
        Expecting
        'Count of patches removed from: [Assessment=xxx] [Installation=0] log message is called'
        """

        # Set up create temp file for log and set sys.stdout to it
        self.__create_tmp_file_for_log_and_set_stdout()

        # Assert assessment truncation log output
        patch_count = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.log_truncated_patches()

        # Truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)

        assessment_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        assessment_truncated_log = "Count of patches removed from: [Assessment="+str(patch_count - len(assessment_truncated_msg['patches']))+"]"+" [Installation=0]"
        self.__read_tmp_log_and_assert(assessment_truncated_log)

        # Reset sys.stdout, close and delete tmp
        self.__remove_tmp_file_reset_stdout()

    def test_log_truncated_patches_assert_installation_truncated(self):
        """ Assert truncation is performed on installation patches.
        Expecting
        'Count of patches removed from: [Assessment=0] [Installation=xxx] log message is called'
        """

        # Set up create temp file for log and set sys.stdout to it
        self.__create_tmp_file_for_log_and_set_stdout()

        # Assert installation truncation log output
        patch_count = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)
        self.runtime.status_handler.log_truncated_patches()

        # Truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)

        installation_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        installation_truncated_log = "Count of patches removed from: [Assessment=0]"+" [Installation="+str(patch_count - len(installation_truncated_msg['patches']))+"]"
        self.__read_tmp_log_and_assert(installation_truncated_log)

        # Reset sys.stdout, close and delete tmp
        self.__remove_tmp_file_reset_stdout()

    def test_log_truncated_patches_assert_both_assessment_installation_truncated(self):
        """ Assert truncation is performed on assessment and installation patches.
        Expecting
        'Count of patches removed from: [Assessment=xxx] [Installation=xxx] log message is called'
        """

        # Set up create temp file for log and set sys.stdout to it
        self.__create_tmp_file_for_log_and_set_stdout()

        # Assert assessment truncation log output
        patch_count_assessment = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_assessment)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert installation truncation log output
        patch_count_installation = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_installation)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)
        self.runtime.status_handler.log_truncated_patches()

        # Truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)

        assessment_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        installation_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data, substatus_index=1)
        both_truncated_log = "Count of patches removed from: [Assessment="+str(patch_count_assessment - len(assessment_truncated_msg['patches']))+"]"+" [Installation="+str(patch_count_installation - len(installation_truncated_msg['patches']))+"]"
        self.__read_tmp_log_and_assert(both_truncated_log)

        # Reset sys.stdout, close and delete tmp
        self.__remove_tmp_file_reset_stdout()

    def test_truncation_method_time_performance(self):
        """ Perform truncation on very large packages to
        assert truncation code logic time performance is only 30 secs more than current (no truncation) code logic"""

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        self.__create_tmp_file_for_log_and_set_stdout()  # set tmp file for storing sys.stout()

        # Start no truncation performance test
        Constants.StatusTruncationConfig.TURN_ON_TRUNCATION = False
        no_truncate_start_time = time.time()
        for i in range(0, 301):
            test_packages, test_package_versions = self.__set_up_packages_func(500)
            self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
            self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)

        no_truncate_end_time = time.time()
        no_truncate_performance_time = no_truncate_end_time - no_truncate_start_time
        no_truncate_performance_time_formatted = self.__convert_performance_time_to_date_time_format(no_truncate_performance_time)

        # Start truncation performance test
        Constants.StatusTruncationConfig.TURN_ON_TRUNCATION = True
        truncate_start_time = time.time()
        for i in range(0, 301):
            test_packages, test_package_versions = self.__set_up_packages_func(500)
            self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
            self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)

        truncate_end_time = time.time()
        truncate_performance_time = truncate_end_time - truncate_start_time
        truncate_performance_time_formatted = self.__convert_performance_time_to_date_time_format(truncate_performance_time)

        self.__remove_tmp_file_reset_stdout()  # remove and reset tmp file for storing sys.stout()

        self.runtime.status_handler.composite_logger.log_debug('no_truncate_performance_time_formatted' + no_truncate_performance_time_formatted)
        self.runtime.status_handler.composite_logger.log_debug('truncate_performance_time_formatted' + truncate_performance_time_formatted)
        self.assertTrue((truncate_performance_time - no_truncate_performance_time) < 30)

    # Setup functions for testing
    def __assert_packages_map(self, substatus_file_data, patch_summary, patch_count, expected_patch_id, expected_patch_value, classification):
        message = json.loads(substatus_file_data['formattedMessage']['message'])
        self.assertEqual(substatus_file_data["name"], patch_summary)
        self.assertEqual(len(message['patches']), patch_count)
        self.assertEqual(message['patches'][0]['patchId'], expected_patch_id)
        self.assertEqual(message['patches'][0]['name'], 'python-samba0')
        self.assertEqual(message['patches'][0], expected_patch_value)
        self.assertEqual(message['patches'][0]['classifications'], [classification])

    def __assert_installation_set_packages_methods(self, substatus_file_data, patch_summary, patch_count):
        message = json.loads(substatus_file_data["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data["name"], patch_summary)
        self.assertEqual(len(message["patches"]), patch_count)
        self.assertEqual(message["patches"][0]["name"], "python-samba0")
        self.assertTrue('Critical' in str(message["patches"][0]["classifications"]))
        self.assertEqual(message["patches"][1]["name"], "python-samba1")
        self.assertEqual('Critical', str(message["patches"][1]["classifications"][0]))
        self.assertEqual('Installed', str(message["patches"][1]["patchInstallationState"]))
        self.assertEqual(message["patches"][2]["name"], "python-samba2")
        self.assertEqual('python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04', str(message["patches"][0]["patchId"]))
        self.assertTrue('Critical' in str(message["patches"][2]["classifications"]))

        # Clean up complete.status files
        self.runtime.env_layer.file_system.delete_files_from_dir(self.runtime.status_handler.status_file_path, '*.complete.status')

    def __assert_no_truncation_status_file(self, patch_summary, status, patch_count):
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        message = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])
        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertEqual(substatus_file_data[0]["status"]["substatus"][0]["name"], patch_summary)
        self.assertEqual(substatus_file_data[0]["status"]["substatus"][0]["status"], status.lower())
        self.assertEqual(len(message["patches"]), patch_count)
        self.assertNotEqual(message["patches"][-1]['patchId'], "Truncated_patch_list_id")
        self.assertTrue('Truncated_patch_list_id' not in message["patches"][-1]['name'])
        self.assertEqual(message["errors"]["code"], 0)
        self.assertEqual(len(message["errors"]["details"]), 0)
        self.assertFalse("review this log file on the machine" in message)

    def __assert_patch_summary_from_status(self, substatus_file_data, operation, patch_summary, status, substatus_index=0, is_under_agent_size_limit=True):
        self.assertEqual(substatus_file_data[0]["status"]["operation"], operation)

        if is_under_agent_size_limit:
            # Assert status file size < 128kb n 126kb
            truncated_substatus_file_byte_size = len(json.dumps(substatus_file_data))
            self.assertTrue(truncated_substatus_file_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
            self.assertTrue(truncated_substatus_file_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        else:
            # Assert complete status file size > 128kb
            self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)

        substatus_file_data = substatus_file_data[0]["status"]["substatus"][substatus_index]
        self.assertEqual(substatus_file_data["name"], patch_summary)
        self.assertEqual(substatus_file_data["status"], status.lower())

    def __assert_message_json_from_status(self, substatus_file_data, patch_count, error_count=0):
        message = json.loads(substatus_file_data["formattedMessage"]["message"])
        self.assertEqual(patch_count, len(message["patches"]))
        self.assertEqual(Constants.PatchOperationTopLevelErrorCode.SUCCESS, message["errors"]["code"])
        self.assertEqual(error_count, len(message["errors"]["details"]))

    def __assert_truncated_error(self, substatus_file_data, error_count):
        # assert error
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), error_count)

    def __add_multiple_exception_errors(self):
        # Adding multiple exceptions
        self.runtime.status_handler.add_error_to_status("exception0", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception1", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception2", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception3", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception4", Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
        self.runtime.status_handler.add_error_to_status("exception5", Constants.PatchOperationErrorCodes.OPERATION_FAILED)

    def __assert_status_file_data_multi_exceptions(self, substatus_file_data, patch_summary, status, patch_count, count_errors_detail=0, substatus_index=0):
        message = self.__get_message_json_from_substatus(substatus_file_data, substatus_index=substatus_index)
        self.assertEqual(substatus_file_data[0]["status"]["substatus"][substatus_index]["name"], patch_summary)
        self.assertEqual(substatus_file_data[0]["status"]["substatus"][substatus_index]["status"], status.lower())
        self.assertEqual(len(message["patches"]), patch_count)
        self.assertNotEqual(message["errors"], None)
        self.assertEqual(message["errors"]["code"], Constants.PatchOperationTopLevelErrorCode.ERROR)
        self.assertEqual(len(message["errors"]["details"]), count_errors_detail)
        self.assertEqual(message["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.OPERATION_FAILED)
        self.assertEqual(message["errors"]["details"][1]["code"], Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
        self.assertEqual(message["errors"]["details"][0]["message"], "exception5")

    def __assert_truncated_status_multi_errors(self, patch_summary, status, patch_count, error_count, substatus_index=0):
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            truncated_substatus_file_data = json.load(file_handle)

        truncated_substatus_file_byte_size = len(json.dumps(truncated_substatus_file_data))
        message = self.__get_message_json_from_substatus(truncated_substatus_file_data, substatus_index=substatus_index)
        # Assert truncated status file size < 128kb n 126kb and length of truncated patches < length of complete status file patches
        self.assertTrue(truncated_substatus_file_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(truncated_substatus_file_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertEqual(truncated_substatus_file_data[0]["status"]["substatus"][substatus_index]["name"], patch_summary)
        self.assertEqual(truncated_substatus_file_data[0]["status"]["substatus"][substatus_index]["status"], status.lower())
        self.assertTrue(len(message["patches"]) < patch_count)

        # assert truncated error
        self.__assert_truncated_error(truncated_substatus_file_data[0]["status"]["substatus"][substatus_index], error_count=error_count)

    def __assert_assessment_truncated_msg_fields(self, assessment_msg, truncated_assessment_msg):
        self.assertEqual(assessment_msg['assessmentActivityId'], truncated_assessment_msg['assessmentActivityId'])
        self.assertEqual(assessment_msg['rebootPending'], truncated_assessment_msg['rebootPending'])
        self.assertEqual(assessment_msg['criticalAndSecurityPatchCount'], truncated_assessment_msg['criticalAndSecurityPatchCount'])
        self.assertEqual(assessment_msg['otherPatchCount'], truncated_assessment_msg['otherPatchCount'])
        self.assertEqual(assessment_msg['startTime'], truncated_assessment_msg['startTime'])
        self.assertEqual(assessment_msg['lastModifiedTime'], truncated_assessment_msg['lastModifiedTime'])
        self.assertEqual(assessment_msg['startedBy'], truncated_assessment_msg['startedBy'])

    def __assert_installation_truncated_msg_fields(self, installation_msg, truncated_installation_msg):
        self.assertEqual(installation_msg['installationActivityId'], truncated_installation_msg['installationActivityId'])
        self.assertEqual(installation_msg['rebootStatus'], truncated_installation_msg['rebootStatus'])
        self.assertEqual(installation_msg['maintenanceWindowExceeded'], truncated_installation_msg['maintenanceWindowExceeded'])
        self.assertEqual(installation_msg['notSelectedPatchCount'], truncated_installation_msg['notSelectedPatchCount'])
        self.assertEqual(installation_msg['excludedPatchCount'], truncated_installation_msg['excludedPatchCount'])
        self.assertEqual(installation_msg['pendingPatchCount'], truncated_installation_msg['pendingPatchCount'])
        self.assertEqual(installation_msg['installedPatchCount'], truncated_installation_msg['installedPatchCount'])
        self.assertEqual(installation_msg['failedPatchCount'], truncated_installation_msg['failedPatchCount'])
        self.assertEqual(installation_msg['startTime'], truncated_installation_msg['startTime'])
        self.assertEqual(installation_msg['lastModifiedTime'], truncated_installation_msg['lastModifiedTime'])
        self.assertEqual(installation_msg['maintenanceRunId'], truncated_installation_msg['maintenanceRunId'])

    def __get_message_json_from_substatus(self, substatus_file_data, substatus_index=0):
        return json.loads(substatus_file_data[0]["status"]["substatus"][substatus_index]["formattedMessage"]["message"])

    def __convert_performance_time_to_date_time_format(self, performance_time):
        performance_time = abs(performance_time)

        # Calc days, hours, minutes, and seconds
        days, remainder = divmod(performance_time, 86400)  # 86400 seconds in a day
        hours, remainder = divmod(remainder, 3600)  # 3600 seconds in an hour
        minutes, seconds = divmod(remainder, 60)  # 60 seconds in a minute

        # Format the result
        formatted_time = "%d days, %d hours, %d minutes, %.6f seconds" % (int(days), int(hours), int(minutes), seconds)
        return formatted_time

    # Setup functions for writing log to temp and read output
    def __create_tmp_file_for_log_and_set_stdout(self):
        # Set up create temp file for log and set sys.stdout to it
        self.temp_stdout = tempfile.NamedTemporaryFile(delete=False, mode="w+")
        self.saved_stdout = sys.stdout  # Save the original stdout
        sys.stdout = self.temp_stdout  # set it to the temporary file

    def __remove_tmp_file_reset_stdout(self):
        sys.stdout = self.saved_stdout  # redirect to original stdout
        self.temp_stdout.close()
        os.remove(self.temp_stdout.name)  # Remove the temporary file

    def __read_tmp_log_and_assert(self, expected_string):
        self.temp_stdout.flush()
        with open(self.temp_stdout.name, 'r') as temp_file:
            captured_log_output = temp_file.read()
            self.assertIn(expected_string, captured_log_output)

    # Setup functions to populate packages and versions for truncation
    def __set_up_packages_func(self, val, random_char=None):
        test_packages = []
        test_package_versions = []

        for i in range(0, val):
            test_packages.append('python-samba' + str(i))

            if random_char is not None:
                test_package_versions.append('2:4.4.5+dfsg-2ubuntu5.4' + random_char)
            else:
                test_package_versions.append('2:4.4.5+dfsg-2ubuntu5.4')
        return test_packages, test_package_versions

if __name__ == '__main__':
    unittest.main()
