# -*- coding: utf-8 -*-
# Copyright 2024 Microsoft Corporation
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
import random
import string
import time
import unittest

from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestStatusHandlerTruncation(unittest.TestCase):

    class TimePerformanceUTConfig(Constants.EnumBackport):
        MIN_OPERATION_ITERATIONS = 0
        MAX_OPERATION_ITERATIONS = 30
        NUMBER_OF_PATCHES = 350
        EXPECTED_TRUNCATION_TIME_LIMIT_IN_SEC = 30

    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True)
        self.container = self.runtime.container
        self.__test_scenario = None
        self.__patch_count_assessment = 0
        self.__patch_count_installation = 0

    def tearDown(self):
        self.__test_scenario = None
        self.__patch_count_assessment = 0
        self.__patch_count_installation = 0
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

        self.__test_scenario = 'assessment_only'
        self.__patch_count_assessment = 500

        self.__set_up_status_file(run='assessment', config_operation=Constants.ASSESSMENT, patch_count=self.__patch_count_assessment, status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_assessment, is_under_internal_size_limit=True, is_truncated=False)

        # Assert no truncated status file
        substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        self.assertEqual(len(json.dumps(substatus_file_data).encode('utf-8')), len(json.dumps(complete_substatus_file_data).encode('utf-8')))  # Assert both files have same bytes
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_assessment, is_under_internal_size_limit=True, is_truncated=False)

    def test_only_assessment_patches_over_size_limit_truncated(self):
        """ Perform truncation on very large assessment patches and checks for time performance concern.
        Before truncation: 100000 assessment patches in status
        complete status file byte size: 19,022kb,
        Expected (After truncation): ~671 assessment patches in status
        operation: Assessment,
        assessment substatus name: PatchAssessmentSummary,
        assessment substatus status: warning,
        assessment errors code: 2 (warning),
        assessment errors details count: 1,
        assessment errors details code: [PACKAGE_LIST_TRUNCATED]
        count of assessment patches removed: 99329,
        truncated status file byte size: 126kb. """

        self.__test_scenario = 'assessment_only'
        self.__patch_count_assessment = 100000

        self.__set_up_status_file(run='assessment', config_operation=Constants.ASSESSMENT, patch_count=self.__patch_count_assessment, status=Constants.STATUS_SUCCESS, classification='Critical')

        # Assert complete status file
        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_assessment)

        # Assert assessment truncated status file
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        # Assert truncated status file size
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING, self.__patch_count_assessment, errors_count=1, errors_code=Constants.PatchOperationTopLevelErrorCode.WARNING, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

    def test_only_assessment_patches_over_size_limit_with_status_error_truncated(self):
        """ Perform truncation on assessment patches and substatus status is set to Error (not warning) due to per-existing patching errors
        Before truncation: 1000 assessment patches in status, 6 exceptions
        completed status file byte size: 188kb
        Expected (After truncation): ~669 assessment patches in status
        operation: Assessment,
        assessment substatus name: PatchAssessmentSummary,
        assessment substatus status: error,
        assessment errors code: 1 (error),
        assessment errors details count: 5,
        assessment errors details code: [PACKAGE_LIST_TRUNCATED, OPERATION_FAILED]
        count of assessment patches removed: 331,
        truncated status file byte size: 126kb. """

        self.__test_scenario = 'assessment_only'
        self.__patch_count_assessment = 1000

        self.__set_up_status_file(run='assessment', config_operation=Constants.ASSESSMENT, patch_count=self.__patch_count_assessment, classification='Security')

        # Set up complete status file before exceptions
        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        # Assert complete status file size > 128kb and no exceptions
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, 'transitioning', self.__patch_count_assessment)

        # Assert status file < 126kb and substatus status remain 'transitioning'
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, 'transitioning', self.__patch_count_assessment, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Set up complete status file with exception errors
        self.__add_multiple_exception_errors()
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
        self.runtime.status_handler.log_truncated_patches()

        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        # Assert complete status file with exception errors
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_ERROR, self.__patch_count_assessment, errors_count=5, errors_code=Constants.PatchOperationTopLevelErrorCode.ERROR)

        # Assert assessment truncated status file with multi exception errors
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_ERROR, self.__patch_count_assessment, errors_count=5, errors_code=Constants.PatchOperationTopLevelErrorCode.ERROR, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

    def test_only_assessment_patches_over_size_limit_with_informational_msg_truncated(self):
        """ Perform truncation on assessment patches and substatus status is set to warning with truncated message
        Before truncation: 1000 assessment patches in status, 1 informational message
        completed status file byte size: 188kb
        Expected (After truncation): ~669 assessment patches in status
        operation: Assessment,
        assessment substatus name: PatchAssessmentSummary,
        assessment substatus status: warning,
        assessment errors code: 2 (warning),
        assessment errors details count: 1,
        assessment errors details code: [PACKAGE_LIST_TRUNCATED]
        count of assessment patches removed: 331,
        truncated status file byte size: 126kb. """

        self.__test_scenario = 'assessment_only'
        self.__patch_count_assessment = 1000

        self.__set_up_status_file(run='assessment', config_operation=Constants.ASSESSMENT, patch_count=self.__patch_count_assessment, classification='Security')

        # Set up complete status file with informational message
        self.runtime.status_handler.add_error_to_status("informational", Constants.PatchOperationErrorCodes.INFORMATIONAL)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)
        self.runtime.status_handler.log_truncated_patches()

        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        # Assert complete status file with informational message
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_assessment)

        # Assert assessment truncated status file with multi exception errors
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING, self.__patch_count_assessment, errors_count=1, errors_code=Constants.PatchOperationTopLevelErrorCode.WARNING, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

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

        self.__test_scenario = 'installation_only'
        self.__patch_count_installation = 500

        self.__set_up_status_file(run='installation', config_operation=Constants.INSTALLATION, patch_count=self.__patch_count_installation, status=Constants.STATUS_SUCCESS, package_status=Constants.INSTALLED)

        # Assert complete status file
        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_installation, is_under_internal_size_limit=True, is_truncated=False)

        # Assert no truncated status file
        substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        self.assertEqual(len(json.dumps(substatus_file_data).encode('utf-8')), len(json.dumps(complete_substatus_file_data).encode('utf-8')))  # Assert both files have same bytes
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_installation, is_under_internal_size_limit=True, is_truncated=False)

    def test_only_installation_patches_over_size_limit_truncated(self):
        """ Perform truncation on very large installation patches and checks for time performance concern.
        Before truncation: 100000 installation patches in status
        complete status file byte size: 22,929kb,
        Expected (After truncation): ~554 installation patches in status
        operation: Installation,
        installation substatus name: PatchInstallationSummary,
        installation substatus status: warning,
        installation errors code: 2 (warning),
        installation errors details count: 1,
        installation errors details code: [PACKAGE_LIST_TRUNCATED]
        count of installation patches removed: 99446,
        truncated status file byte size: 126kb. """

        self.__test_scenario = 'installation_only'
        self.__patch_count_installation = 100000

        self.__set_up_status_file(run='installation', config_operation=Constants.INSTALLATION, patch_count=self.__patch_count_installation, status=Constants.STATUS_SUCCESS, package_status=Constants.INSTALLED)

        # Assert complete status file
        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_installation)

        # Assert installation truncated status file
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING, self.__patch_count_installation, errors_count=1, errors_code=Constants.PatchOperationTopLevelErrorCode.WARNING, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

    def test_only_installation_low_priority_patches_over_size_limit_truncated(self):
        """ Perform truncation on only installation with low priority patches (Pending, Exclude, Not_Selected), truncated status files have no Not_Selected patches.
        Before truncation: 1040 installation patches in status
        complete status file byte size: 235kb,
        Expected (After truncation): ~558 installation patches in status
        operation: Installation,
        installation substatus name: PatchInstallationSummary,
        installation substatus status: warning,
        installation errors code: 2 (warning),
        installation errors details count: 1,
        installation errors details code: [PACKAGE_LIST_TRUNCATED]
        last complete status file installation patch state: Not_Selected
        first truncated installation patch state: Pending,
        last truncated installation patch state: Excluded,
        count of installation patches removed: 482,
        truncated status file byte size: 126kb. """

        self.__test_scenario = 'installation_only'
        patch_count_pending = 400
        patch_count_exclude = 600
        patch_count_not_selected = 40

        # random_char=random.choice(string.ascii_letters) ensure the packages are unique due to __set_up_patches_func remove duplicates
        self.__run_installation_package_set_up(patch_count_exclude, Constants.EXCLUDED, random_char=random.choice(string.ascii_letters))
        self.__run_installation_package_set_up(patch_count_not_selected, Constants.NOT_SELECTED, random_char=random.choice(string.ascii_letters))
        self.__set_up_status_file(run='installation', config_operation=Constants.INSTALLATION, patch_count=patch_count_pending, status=Constants.STATUS_SUCCESS, package_status=Constants.PENDING)

        self.__patch_count_installation = patch_count_pending + patch_count_exclude + patch_count_not_selected

        # Assert complete status file
        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        # Assert last patch's installation state is Not_Selected
        installation_msg = self.__get_message_json_from_substatus(complete_substatus_file_data)
        self.assertEqual(installation_msg['patches'][-1]['patchInstallationState'], Constants.NOT_SELECTED)
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_installation)

        # Assert installation truncated status file
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        # Assert first patch's installation state is Pending, last patch's installation state is Excluded
        installation_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data)
        self.assertEqual(installation_truncated_msg['patches'][0]['patchInstallationState'], Constants.PENDING)
        self.assertEqual(installation_truncated_msg['patches'][-1]['patchInstallationState'], Constants.EXCLUDED)

        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING, self.__patch_count_installation, errors_count=1, errors_code=Constants.PatchOperationTopLevelErrorCode.WARNING, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

    def test_only_installation_patches_over_size_limit_with_status_error_truncated(self):
        """ Perform truncation on installation patches and substatus status is set to Error (not warning) due to per-existing patching errors
        Before truncation: 800 installation patches in status, 6 exceptions
        completed status file byte size: 182kb,
        Expected (After truncation): ~553 installation patches in status
        operation: Installation,
        installation substatus name: PatchInstallationSummary,
        installation substatus status: error,
        installation errors code: 1 (error),
        installation errors details count: 5,
        installation errors details code: [PACKAGE_LIST_TRUNCATED, OPERATION_FAILED]
        count of installation patches removed: 247,
        truncated status file byte size: 126kb. """

        self.__test_scenario = 'installation_only'
        self.__patch_count_installation = 800

        self.__set_up_status_file(run='installation', config_operation=Constants.INSTALLATION, patch_count=self.__patch_count_installation, package_status=Constants.INSTALLED)

        # Set up complete status file before exceptions
        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        # Assert complete status file size > 128kb and no exception errors
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, 'transitioning', self.__patch_count_installation)

        # Assert status file < 126kb and substatus status remain 'transitioning'
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, 'transitioning', self.__patch_count_installation, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Set up complete status file with exception errors
        self.__add_multiple_exception_errors()
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)
        self.runtime.status_handler.log_truncated_patches()

        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        # Assert complete status file with multi exception errors
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, self.__patch_count_installation, errors_count=5, errors_code=Constants.PatchOperationTopLevelErrorCode.ERROR)

        # Assert installation truncated status file with multi exception errors
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, self.__patch_count_installation, errors_count=5, errors_code=Constants.PatchOperationTopLevelErrorCode.ERROR, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

    def test_only_installation_patches_over_size_limit_with_informational_msg_truncated(self):
        """ Perform truncation on installation patches and substatus status is set to warning with truncated message
        Before truncation: 800 installation patches in status with 1 informational message
        completed status file byte size: 182kb,
        Expected (After truncation): ~554 installation patches in status
        operation: Installation,
        installation substatus name: PatchInstallationSummary,
        installation substatus status: warning,
        installation errors code: 2 (warning),
        installation errors details count: 5,
        installation errors details code: [PACKAGE_LIST_TRUNCATED]
        count of installation patches removed: 246,
        truncated status file byte size: 126kb. """

        self.__test_scenario = 'installation_only'
        self.__patch_count_installation = 800

        self.__set_up_status_file(run='installation', config_operation=Constants.INSTALLATION, patch_count=self.__patch_count_installation, package_status=Constants.INSTALLED)

        # Set up complete status file with informational message
        self.runtime.status_handler.add_error_to_status("informational", Constants.PatchOperationErrorCodes.INFORMATIONAL)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)
        self.runtime.status_handler.log_truncated_patches()

        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        # Assert complete status file with informational message
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_installation)

        # Assert installation truncated status file informational message
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING, self.__patch_count_installation, errors_count=1, errors_code=Constants.PatchOperationTopLevelErrorCode.WARNING, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

    def test_both_assessment_and_installation_over_size_limit_truncated(self):
        """ Perform truncation on assessment/installation patches.
        Before truncation: 700 assessment patches in status, 500 installation patches in status
        complete status file byte size: 242kb,
        Expected (After truncation): ~370 assessment patches in status, ~250 installation patches in status
        operation: Installation,
        substatus name: [assessment=PatchAssessmentSummary][installation=PatchInstallationSummary],
        substatus status: [assessment=warning][installation=warning],
        errors code: [assessment=2 (warning)][installation=2 (warning)],
        errors details count: [assessment=1][installation=1],
        errors details code: [assessment=[PACKAGE_LIST_TRUNCATED]][installation=[PACKAGE_LIST_TRUNCATED]],
        count of patches removed from log: [assessment=330[installation=950],
        truncated status file byte size: 126kb. """

        self.__test_scenario = 'both'
        self.__patch_count_assessment = 700
        patch_count_pending = 250
        patch_count_installed = 250
        self.__patch_count_installation = patch_count_pending + patch_count_installed

        self.__set_up_status_file(run='assessment', config_operation=Constants.INSTALLATION, patch_count=self.__patch_count_assessment, status=Constants.STATUS_SUCCESS)
        self.__run_installation_package_set_up(patch_count_pending, Constants.PENDING, random_char=random.choice(string.ascii_letters))  # random_char=random.choice(string.ascii_letters) ensure the packages are unique due to __set_up_patches_func remove duplicates
        self.__set_up_status_file(run='installation', config_operation=Constants.INSTALLATION, patch_count=patch_count_installed, status=Constants.STATUS_SUCCESS, package_status=Constants.INSTALLED)

        # Assert complete status file
        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        # Assert assessment summary
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_assessment)

        # Assert installation summary
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_installation, installation_substatus_index=1)

        # Assert truncated status file
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        # Assert assessment truncation
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING, self.__patch_count_assessment, errors_count=1, errors_code=Constants.PatchOperationTopLevelErrorCode.WARNING, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert installation truncation
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING, self.__patch_count_installation, errors_count=1, errors_code=Constants.PatchOperationTopLevelErrorCode.WARNING, installation_substatus_index=1, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

    def test_both_assessment_and_installation__keep_min_5_assessment_patches_truncated(self):
        """ Perform truncation on very large assessment / installation patches and checks for time performance concern. but keep min 5 assessment patches.
        Before truncation: 100000 assessment patches in status, 100000 installation patches in status
        complete status file byte size: 41,658kb,
        Expected (After truncation): ~5 assessment patches in status, ~546 installation patches in status
        operation: Installation,
        substatus name: [assessment=PatchAssessmentSummary][installation=PatchInstallationSummary],
        substatus status: [assessment=warning][installation=warning],
        errors code: [assessment=2 (warning)][installation=2 (warning)],
        errors details count: [assessment=1][installation=1],
        errors details code: [assessment=[PACKAGE_LIST_TRUNCATED]][installation=[PACKAGE_LIST_TRUNCATED]],
        count of patches removed from log: [assessment=99995[installation=99454],
        truncated status file byte size: 126kb. """

        self.__test_scenario = 'both'
        self.__patch_count_assessment = 100000
        self.__patch_count_installation = 100000

        self.__set_up_status_file(run='assessment', config_operation=Constants.INSTALLATION, patch_count=self.__patch_count_assessment, status=Constants.STATUS_SUCCESS)
        self.__set_up_status_file(run='installation', config_operation=Constants.INSTALLATION, patch_count=self.__patch_count_installation, status=Constants.STATUS_SUCCESS, package_status=Constants.INSTALLED)

        # Assert complete status file
        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        # Assert assessment summary
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_assessment)

        # Assert installation summary
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS,
            self.__patch_count_installation, installation_substatus_index=1)

        # Assert truncated status file
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        # Assert assessment truncation
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING, self.__patch_count_assessment, errors_count=1, errors_code=Constants.PatchOperationTopLevelErrorCode.WARNING, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert installation truncation
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING, self.__patch_count_installation, errors_count=1, errors_code=Constants.PatchOperationTopLevelErrorCode.WARNING, installation_substatus_index=1, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

    def test_both_assessment_and_installation_with_status_error_truncated(self):
        """ Perform truncation on assessment / installation patches but installation substatus status is set to Error (not warning) due to per-existing patching errors
        Before truncation: 800 assessment patches in status, 800 installation patches in status with 6 exception errors
        complete status file byte size: > 128kb,
        Expected (After truncation): ~5 assessment patches in status, ~545 installation patches in status
        operation: Installation,
        substatus name: [assessment=PatchAssessmentSummary][installation=PatchInstallationSummary],
        substatus status: [assessment=warning][installation=error],
        errors code: [assessment=2 (warning)][installation=1 (error)],
        errors details count: [assessment=1][installation=5],
        errors details code: [assessment=[PACKAGE_LIST_TRUNCATED]][installation=[PACKAGE_LIST_TRUNCATED, OPERATION_FAILED]],
        count of patches removed from log: [assessment=795][installation=455],
        truncated status file byte size: < 126kb """

        self.__test_scenario = 'both'
        self.__patch_count_assessment = 800
        self.__patch_count_installation = 1000

        self.__set_up_status_file(run='assessment', config_operation=Constants.INSTALLATION, patch_count=self.__patch_count_assessment, status=Constants.STATUS_SUCCESS, package_status='Security')
        self.__set_up_status_file(run='installation', config_operation=Constants.INSTALLATION, patch_count=self.__patch_count_installation, package_status=Constants.INSTALLED)

        # Set up complete status file before errors
        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        # Assert complete status file size > 128kb and no exceptions
        # Assert no assessment message errors
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_assessment)

        # Assert no installation message errors
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, 'transitioning', self.__patch_count_installation, installation_substatus_index=1)

        # Assert status file < 126kb and substatus status remain 'transitioning'
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, 'transitioning', self.__patch_count_installation, installation_substatus_index=1, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Set up complete status file with exception errors - installation
        self.__add_multiple_exception_errors()
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)
        self.runtime.status_handler.log_truncated_patches()

        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        # Assert installation status file with multi error exceptions
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, self.__patch_count_installation, errors_count=5, errors_code=Constants.PatchOperationTopLevelErrorCode.ERROR, installation_substatus_index=1)

        # Assert truncated status file
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        # Assert assessment truncated
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING, self.__patch_count_assessment, errors_count=1, errors_code=Constants.PatchOperationTopLevelErrorCode.WARNING, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert installation truncated status file with multi exceptions
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, self.__patch_count_installation,
            errors_count=5, errors_code=Constants.PatchOperationTopLevelErrorCode.ERROR, installation_substatus_index=1, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

    def test_both_assessment_and_installation_with_informational_truncated(self):
        """ Perform truncation on assessment / installation status set to warning with truncated message
        Before truncation: 800 assessment patches in status, 800 installation patches in status with 1 informational message
        complete status file byte size: > 128kb,
        Expected (After truncation): ~5 assessment patches in status, ~546 installation patches in status
        operation: Installation,
        substatus name: [assessment=PatchAssessmentSummary][installation=PatchInstallationSummary],
        substatus status: [assessment=warning][installation=warning],
        errors code: [assessment=2 (warning)][installation=2 (warning)],
        errors details count: [assessment=1][installation=1],
        errors details code: [assessment=[PACKAGE_LIST_TRUNCATED]][installation=[PACKAGE_LIST_TRUNCATED]],
        count of patches removed from log: [assessment=795][installation=454],
        truncated status file byte size: < 126kb """

        self.__test_scenario = 'both'
        self.__patch_count_assessment = 800
        self.__patch_count_installation = 1000

        self.__set_up_status_file(run='assessment', config_operation=Constants.INSTALLATION, patch_count=self.__patch_count_assessment, status=Constants.STATUS_SUCCESS, package_status='Security')
        self.__set_up_status_file(run='installation', config_operation=Constants.INSTALLATION, patch_count=self.__patch_count_installation, package_status=Constants.INSTALLED)

        # Set up complete status file with informational message
        self.runtime.status_handler.add_error_to_status("informational", Constants.PatchOperationErrorCodes.INFORMATIONAL)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)
        self.runtime.status_handler.log_truncated_patches()

        complete_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.complete_status_file_path)

        # Assert installation status file informational message
        self.__assert_patch_summary_from_status(complete_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, self.__patch_count_installation, installation_substatus_index=1)

        # Assert truncated status file
        truncated_substatus_file_data = self.__get_substatus_file_json(self.runtime.execution_config.status_file_path)

        # Assert assessment truncated
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING, self.__patch_count_assessment, errors_count=1, errors_code=Constants.PatchOperationTopLevelErrorCode.WARNING, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

        # Assert installation truncated status file with multi exceptions
        self.__assert_patch_summary_from_status(truncated_substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING, self.__patch_count_installation,
            errors_count=1, errors_code=Constants.PatchOperationTopLevelErrorCode.WARNING, installation_substatus_index=1, complete_substatus_file_data=complete_substatus_file_data, is_under_internal_size_limit=True, is_truncated=True)

    def test_truncation_method_time_performance(self):
        """ Comparing truncation code performance on prior and post on 750 packages with frequency of 30
        assert truncation code logic time performance is 30 secs more than current (prior truncation) logic """

        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        # Start performance test prior truncation
        Constants.StatusTruncationConfig.TURN_ON_TRUNCATION = False
        test_patches, test_patches_version = self.__set_up_patches_func(TestStatusHandlerTruncation.TimePerformanceUTConfig.NUMBER_OF_PATCHES)
        start_time_no_truncation = time.time()
        for i in range(TestStatusHandlerTruncation.TimePerformanceUTConfig.MIN_OPERATION_ITERATIONS, TestStatusHandlerTruncation.TimePerformanceUTConfig.MAX_OPERATION_ITERATIONS):
            self.runtime.status_handler.set_package_assessment_status(test_patches, test_patches_version)
            self.runtime.status_handler.set_package_install_status(test_patches, test_patches_version, Constants.INSTALLED)

        end_time_no_truncation = time.time()
        performance_time_no_truncation = end_time_no_truncation - start_time_no_truncation 

        # Start truncation performance test
        Constants.StatusTruncationConfig.TURN_ON_TRUNCATION = True
        start_time_with_truncation = time.time()
        for i in range(TestStatusHandlerTruncation.TimePerformanceUTConfig.MIN_OPERATION_ITERATIONS, TestStatusHandlerTruncation.TimePerformanceUTConfig.MAX_OPERATION_ITERATIONS):
            self.runtime.status_handler.set_package_assessment_status(test_patches, test_patches_version)
            self.runtime.status_handler.set_package_install_status(test_patches, test_patches_version, Constants.INSTALLED)

        end_time_with_truncation = time.time()
        performance_time_with_truncation = end_time_with_truncation - start_time_with_truncation
        performance_time_formatted_no_truncation = self.__convert_performance_time_to_date_time_format(performance_time_no_truncation)
        performance_time_formatted_with_truncation = self.__convert_performance_time_to_date_time_format(performance_time_with_truncation)

        self.runtime.status_handler.composite_logger.log_debug('performance_time_formatted_no_truncation ' + performance_time_formatted_no_truncation )
        self.runtime.status_handler.composite_logger.log_debug('performance_time_formatted_with_truncation ' + performance_time_formatted_with_truncation)
        self.assertTrue((performance_time_with_truncation - performance_time_no_truncation) < TestStatusHandlerTruncation.TimePerformanceUTConfig.EXPECTED_TRUNCATION_TIME_LIMIT_IN_SEC)

    # Setup functions for testing
    def __assert_patch_summary_from_status(self, substatus_file_data, operation, patch_summary, status, patch_count, errors_count=0,
            errors_code=Constants.PatchOperationTopLevelErrorCode.SUCCESS, installation_substatus_index=0, complete_substatus_file_data=None, is_under_internal_size_limit=False, is_truncated=False):

        substatus_summary_data = substatus_file_data["status"]["substatus"][installation_substatus_index]
        message = json.loads(substatus_summary_data["formattedMessage"]["message"])
        status_file_patch_count = len(message["patches"])

        # Assert patch summary data
        self.assertEqual(substatus_file_data["status"]["operation"], operation)
        self.assertEqual(substatus_summary_data["name"], patch_summary)
        self.assertEqual(substatus_summary_data["status"], status.lower())

        if is_under_internal_size_limit:
            # Assert status file size < 126kb n 128kb
            substatus_file_in_bytes = len(json.dumps(substatus_file_data).encode('utf-8'))
            self.assertTrue(substatus_file_in_bytes < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
            self.assertTrue(substatus_file_in_bytes <= Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)

            if is_truncated:
                self.assertTrue(status_file_patch_count < patch_count)  # Assert length of truncated patches < patch_count post truncation
                self.assertTrue(substatus_file_in_bytes < len(json.dumps(complete_substatus_file_data).encode('utf-8')))  # Assert truncated status file size < completed status file size

                if errors_count > 0:
                    self.assertTrue(any(Constants.PatchOperationErrorCodes.TRUNCATION in details['code'] for details in message["errors"]["details"]))
                    self.assertTrue(any(Constants.StatusTruncationConfig.TRUNCATION_WARNING_MESSAGE in details['message'] for details in message["errors"]["details"]))
                    self.assertTrue('The latest ' + str(errors_count) + ' error/s are shared in detail. To view all errors, review this log file on the machine' in message["errors"]["message"])

                if self.__test_scenario == 'assessment_only':
                    self.assertEqual(status_file_patch_count, patch_count - self.runtime.status_handler.get_num_assessment_patches_removed())
                    self.assertEqual(patch_count - status_file_patch_count, self.runtime.status_handler.get_num_assessment_patches_removed())  # Assert # assessment removed packages
                    self.__assert_assessment_truncated_msg_fields(complete_substatus_file_data, substatus_file_data)  # Assert all assessment fields in the message json are equal in both status files

                if self.__test_scenario == 'installation_only':
                    self.assertEqual(status_file_patch_count, patch_count - self.runtime.status_handler.get_num_installation_patches_removed())
                    self.assertEqual(patch_count - status_file_patch_count, self.runtime.status_handler.get_num_installation_patches_removed())  # Assert # installation removed packages
                    self.__assert_installation_truncated_msg_fields(complete_substatus_file_data, substatus_file_data)  # Assert all installation fields in the message json are equal in both status files

                if self.__test_scenario == 'both':
                    status_file_assessment_count = len(json.loads(substatus_file_data["status"]["substatus"][0]["formattedMessage"]["message"])["patches"])
                    status_file_installation_count = len(json.loads(substatus_file_data["status"]["substatus"][1]["formattedMessage"]["message"])["patches"])
                    self.assertEqual(status_file_assessment_count, self.__patch_count_assessment - self.runtime.status_handler.get_num_assessment_patches_removed())
                    self.assertEqual(status_file_installation_count, self.__patch_count_installation - self.runtime.status_handler.get_num_installation_patches_removed())
                    self.assertEqual(self.__patch_count_assessment - status_file_assessment_count, self.runtime.status_handler.get_num_assessment_patches_removed())  # Assert # assessment removed packages
                    self.assertEqual(self.__patch_count_installation - status_file_installation_count, self.runtime.status_handler.get_num_installation_patches_removed())  # Assert # installation removed packages

        else:
            self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)  # Assert complete status file size > 128kb
            self.assertEqual(status_file_patch_count, patch_count)  # Assert length of message patches == patch_count prior truncation

        # assert error
        self.assertEqual(message["errors"]["code"], errors_code)
        self.assertEqual(len(message["errors"]["details"]), errors_count)

        if errors_code == Constants.PatchOperationTopLevelErrorCode.ERROR:
            self.assertTrue(any(Constants.PatchOperationErrorCodes.OPERATION_FAILED in details['code'] for details in message["errors"]["details"]))
            self.assertTrue(any(Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE in details['code'] for details in message["errors"]["details"]))

    def __add_multiple_exception_errors(self):
        # Adding multiple exception errors
        self.runtime.status_handler.add_error_to_status("exception0", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception1", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception2", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("informational", Constants.PatchOperationErrorCodes.INFORMATIONAL)
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

    def __assert_installation_truncated_msg_fields(self, complete_substatus_file_data, truncated_substatus_file_data, installation_substatus_index=0):
        installation_msg = self.__get_message_json_from_substatus(complete_substatus_file_data, installation_substatus_index=installation_substatus_index)
        installation_truncated_msg = self.__get_message_json_from_substatus(truncated_substatus_file_data, installation_substatus_index=installation_substatus_index)

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

    def __set_up_status_file(self, run, config_operation, patch_count, status='transitioning', classification='Other', package_status='Available'):
        self.runtime.execution_config.operation = config_operation
        self.runtime.status_handler.set_current_operation(config_operation)

        if run == 'assessment':
            test_patches, test_patches_version = self.__set_up_patches_func(patch_count)
            self.runtime.status_handler.set_package_assessment_status(test_patches, test_patches_version, classification=classification, status=package_status)

            if status != 'transitioning':
                self.runtime.status_handler.set_assessment_substatus_json(status=status)

        if run == 'installation':
            self.__run_installation_package_set_up(patch_count, package_status)

            if status != 'transitioning':
                self.runtime.status_handler.set_installation_substatus_json(status=status)

        self.runtime.status_handler.log_truncated_patches()

    def __run_installation_package_set_up(self, patch_count, package_status, random_char=None):
        test_patches, test_patches_version = self.__set_up_patches_func(patch_count, random_char=random_char)
        self.runtime.status_handler.set_package_install_status(test_patches, test_patches_version, package_status)

    def __get_substatus_file_json(self, status_file_path):
        with self.runtime.env_layer.file_system.open(status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]
        return substatus_file_data

    def __get_message_json_from_substatus(self, substatus_file_data, installation_substatus_index=0):
        return json.loads(substatus_file_data["status"]["substatus"][installation_substatus_index]["formattedMessage"]["message"])

    def __convert_performance_time_to_date_time_format(self, performance_time):
        performance_time = abs(performance_time)

        # Calc days, hours, minutes, and seconds
        days, remainder = divmod(performance_time, 86400)  # 86400 seconds in a day
        hours, remainder = divmod(remainder, 3600)  # 3600 seconds in an hour
        minutes, seconds = divmod(remainder, 60)  # 60 seconds in a minute

        # Format the result
        formatted_time = "%d days, %d hours, %d minutes, %.6f seconds" % (int(days), int(hours), int(minutes), seconds)
        return formatted_time

    def __set_up_patches_func(self, val, random_char=None):
        """ populate packages and versions for truncation """
        test_patches_list = []
        test_patches_version_list = []

        for i in range(0, val):
            test_patches_list.append('python-samba' + str(i))

            if random_char is not None:
                test_patches_version_list.append('2:4.4.5+dfsg-2ubuntu€' + random_char)
            else:
                test_patches_version_list.append('2:4.4.5+dfsg-2ubuntu€')

        return test_patches_list, test_patches_version_list


if __name__ == '__main__':
    unittest.main()

