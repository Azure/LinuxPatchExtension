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
import json
import os
import random
import re
import unittest
from core.src.CoreMain import CoreMain
from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestCoreMainTruncation(unittest.TestCase):
    def setUp(self):
        # Had to move runtime init and stop to individual test functions, since every test uses a different maintenance_run_id which has to be set before runtime init
        # self.argument_composer = ArgumentComposer().get_composed_arguments()
        # self.runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.ZYPPER)
        # self.container = self.runtime.container
        pass

    def tearDown(self):
        # self.runtime.stop()
        pass

    def test_assessment_operation_truncation_under_size_limit(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('HappyPath')
        CoreMain(argument_composer.get_composed_arguments())

        # Check telemetry events
        self.__check_telemetry_events(runtime)

        # HappyPath has already added 3 packages under assessment, we are adding more (anywhere between 200-432) which will still keep the status file size under AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES, thereby no truncation will take place
        # {\"patchId\": \"kernel-default_4.4.49-92.11.1_Ubuntu_16.04\", \"name\": \"kernel-default\", \"version\": \"4.4.49-92.11.1\", \"classifications\": [\"Security\"]},
        # {\"patchId\": \"libgcc_5.60.7-8.1_Ubuntu_16.04\", \"name\": \"libgcc\", \"version\": \"5.60.7-8.1\", \"classifications\": [\"Other\"]},
        # {\"patchId\": \"libgoa-1_0-0_3.20.5-9.6_Ubuntu_16.04\", \"name\": \"libgoa-1_0-0\", \"version\": \"3.20.5-9.6\", \"classifications\": [\"Other\"]}
        patch_count = random.randint(200, 432)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with runtime.env_layer.file_system.open(runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count+3, error_count=0)

        # Assert truncated status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        message = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])
        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertEqual(substatus_file_data[0]["status"]["substatus"][0]["name"], Constants.PATCH_ASSESSMENT_SUMMARY,)
        self.assertEqual(substatus_file_data[0]["status"]["substatus"][0]["status"], Constants.STATUS_SUCCESS.lower())
        self.assertEqual(len(message["patches"]), patch_count + 3)
        self.assertNotEqual(message["patches"][-1]['patchId'], "Truncated_patch_list_id")
        self.assertTrue('Truncated_patch_list_id' not in message["patches"][-1]['name'])
        self.assertEqual(message["errors"]["code"], 0)
        self.assertEqual(len(message["errors"]["details"]), 0)
        self.assertFalse("review this log file on the machine" in message)
        runtime.stop()

    def test_assessment_operation_truncation_over_size_limit(self):
        """ Perform truncation on assessment packages list, setting substatus status to warning and
        error code to 1 (warning) with Constants.StatusTruncationConfig.TRUNCATION_WARNING_MESSAGE """
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('HappyPath')
        CoreMain(argument_composer.get_composed_arguments())

        # Check telemetry events
        self.__check_telemetry_events(runtime)

        # HappyPath has already added 3 packages under assessment, we are adding more (anywhere between 780-1000) which will make the status file size over AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES, thereby truncation will take place
        # {\"patchId\": \"kernel-default_4.4.49-92.11.1_Ubuntu_16.04\", \"name\": \"kernel-default\", \"version\": \"4.4.49-92.11.1\", \"classifications\": [\"Security\"]},
        # {\"patchId\": \"libgcc_5.60.7-8.1_Ubuntu_16.04\", \"name\": \"libgcc\", \"version\": \"5.60.7-8.1\", \"classifications\": [\"Other\"]},
        # {\"patchId\": \"libgoa-1_0-0_3.20.5-9.6_Ubuntu_16.04\", \"name\": \"libgoa-1_0-0\", \"version\": \"3.20.5-9.6\", \"classifications\": [\"Other\"]}

        patch_count = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions, "Critical")
        runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with runtime.env_layer.file_system.open(runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count + 3, error_count=0)

        # Assert assessment truncated status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(len(message_patches) < patch_count + 3)

        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING)

        # Assert assessment truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=0)
        runtime.stop()

    def test_assessment_operation_truncation_large_size_limit_for_extra_chars(self):
        """ Perform truncation large assessment packages list, setting substatus status to warning and
        error code to 1 (warning) with Constants.StatusTruncationConfig.TRUNCATION_WARNING_MESSAGE """
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('HappyPath')
        CoreMain(argument_composer.get_composed_arguments())

        # Check telemetry events
        self.__check_telemetry_events(runtime)

        # # HappyPath has already added 3 packages under assessment, we are adding more (anywhere between 99997) which will make the status file size over AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES, thereby truncation will take place
        # {\"patchId\": \"kernel-default_4.4.49-92.11.1_Ubuntu_16.04\", \"name\": \"kernel-default\", \"version\": \"4.4.49-92.11.1\", \"classifications\": [\"Security\"]},
        # {\"patchId\": \"libgcc_5.60.7-8.1_Ubuntu_16.04\", \"name\": \"libgcc\", \"version\": \"5.60.7-8.1\", \"classifications\": [\"Other\"]},
        # {\"patchId\": \"libgoa-1_0-0_3.20.5-9.6_Ubuntu_16.04\", \"name\": \"libgoa-1_0-0\", \"version\": \"3.20.5-9.6\", \"classifications\": [\"Other\"]}

        patch_count = 99997
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions, "Security")
        runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with runtime.env_layer.file_system.open(runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count + 3, error_count=0)

        # Assert assessment truncated status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(len(message_patches) < patch_count + 3)

        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING)

        # Assert assessment truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=0)
        runtime.stop()

    def test_installation_operation_truncation_over_size_limit(self):
        """ Perform truncation on assessment packages list and installation packages list, setting both substatus status to warning and
        error code to 1 (warning) with Constants.StatusTruncationConfig.TRUNCATION_WARNING_MESSAGE """
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.INSTALLATION
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # Check telemetry events
        self.__check_telemetry_events(runtime)

        # SuccessInstallPath add 2 additional packages
        # {\"patchId\": \"kernel-default_4.4.49-92.11.1_Ubuntu_16.04\", \"name\": \"kernel-default\", \"version\": \"4.4.49-92.11.1\", \"classifications\": [\"Other\"]},
        #  {\"patchId\": \"libgoa-1_0-0_3.20.5-9.6_Ubuntu_16.04\", \"name\": \"libgoa-1_0-0\", \"version\": \"3.20.5-9.6\", \"classifications\": [\"Other\"]}

        patch_count_for_assessment = random.randint(798, 1100)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_assessment)
        runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        patch_count_for_installation = random.randint(500, 1100)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_installation)
        runtime.status_handler.set_package_install_status(test_packages, test_package_versions)
        runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with runtime.env_layer.file_system.open(runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        # Assert assessment summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count_for_assessment + 2, error_count=0)

        assessment_msg = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])

        # Assert installation summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][1], patch_count_for_installation + 2, error_count=0)

        installation_msg = json.loads(substatus_file_data[0]["status"]["substatus"][1]["formattedMessage"]["message"])

        # Assert truncated status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        assessment_message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        installation_message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][1]["formattedMessage"]["message"])["patches"]

        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(len(assessment_message_patches) + len(installation_message_patches) < patch_count_for_assessment + 2 + patch_count_for_installation + 2)
        # Assert assessment truncation
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING)

        # Assert assessment truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # validate all assessment other fields in the message object are equal in both status files
        truncated_assessment_msg = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])
        self.assertEqual(assessment_msg['assessmentActivityId'], truncated_assessment_msg['assessmentActivityId'])
        self.assertEqual(assessment_msg['rebootPending'], truncated_assessment_msg['rebootPending'])
        self.assertEqual(assessment_msg['criticalAndSecurityPatchCount'], truncated_assessment_msg['criticalAndSecurityPatchCount'])
        self.assertEqual(assessment_msg['otherPatchCount'], truncated_assessment_msg['otherPatchCount'])
        self.assertEqual(assessment_msg['startTime'], truncated_assessment_msg['startTime'])
        self.assertEqual(assessment_msg['lastModifiedTime'], truncated_assessment_msg['lastModifiedTime'])
        self.assertEqual(assessment_msg['startedBy'], truncated_assessment_msg['startedBy'])

        # Assert installation truncation
        installation_truncated_substatus = substatus_file_data[0]["status"]["substatus"][1]
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING)

        # Assert installation truncated error
        self.__assert_truncated_error(installation_truncated_substatus, error_count=0)

        # validate all installation other fields in the message object are equal in both status files
        truncated_installation_msg = json.loads(installation_truncated_substatus["formattedMessage"]["message"])
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
        runtime.stop()

    def test_installation_operation_keep_min_5_assessment_size_limit(self):
        """ Perform truncation installation packages list, keep 5 assessment packages, setting installation substatus status to warning and
        error code to 1 (warning) with Constants.StatusTruncationConfig.TRUNCATION_WARNING_MESSAGE """
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.INSTALLATION
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # SuccessInstallPath add 2 additional packages
        # {\"patchId\": \"kernel-default_4.4.49-92.11.1_Ubuntu_16.04\", \"name\": \"kernel-default\", \"version\": \"4.4.49-92.11.1\", \"classifications\": [\"Other\"]},
        #  {\"patchId\": \"libgoa-1_0-0_3.20.5-9.6_Ubuntu_16.04\", \"name\": \"libgoa-1_0-0\", \"version\": \"3.20.5-9.6\", \"classifications\": [\"Other\"]}

        patch_count_for_assessment = 3
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_assessment)
        runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        patch_count_for_installation = 1000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_installation)
        runtime.status_handler.set_package_install_status(test_packages, test_package_versions)
        runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Test Complete status file
        with runtime.env_layer.file_system.open(runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        # Assert assessment summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count_for_assessment + 2, error_count=0)

        # Assert installation summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][1], patch_count_for_installation + 2, error_count=0)

        # Assert truncated status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        assessment_message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        installation_message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][1]["formattedMessage"]["message"])["patches"]

        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue((len(assessment_message_patches) + len(installation_message_patches)) < (patch_count_for_assessment + 2 + patch_count_for_installation + 2))

        # Assert assessment truncation keep 5
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count_for_assessment + 2, error_count=0)

        # Assert installation truncation
        installation_truncated_substatus = substatus_file_data[0]["status"]["substatus"][1]
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING)

        # Assert installation tombstone
        # self.__assert_truncated_installation_tombstone(installation_message_patches)
        # Assert installation truncated error
        self.__assert_truncated_error(installation_truncated_substatus, error_count=0)
        runtime.stop()

    def test_installation_operation_truncation_with_only_install_packages_over_size_limit(self):
        """ Perform truncation on assessment packages list and installation packages with only install status, setting both substatus status to warning and
        error code to 1 (warning) with Constants.StatusTruncationConfig.TRUNCATION_WARNING_MESSAGE """
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.INSTALLATION
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # SuccessInstallPath add 2 additional packages
        # {\"patchId\": \"kernel-default_4.4.49-92.11.1_Ubuntu_16.04\", \"name\": \"kernel-default\", \"version\": \"4.4.49-92.11.1\", \"classifications\": [\"Other\"]},
        #  {\"patchId\": \"libgoa-1_0-0_3.20.5-9.6_Ubuntu_16.04\", \"name\": \"libgoa-1_0-0\", \"version\": \"3.20.5-9.6\", \"classifications\": [\"Other\"]}

        patch_count_for_assessment = 7
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_assessment)
        runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        patch_count_for_installation = 1000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_installation)
        runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with runtime.env_layer.file_system.open(runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        # Assert assessment summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count_for_assessment + 2, error_count=0)

        # Assert installation summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][1], patch_count_for_installation + 2, error_count=0)

        # Assert truncated status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        assessment_message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        installation_message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][1]["formattedMessage"]["message"])["patches"]

        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue((len(assessment_message_patches) + len(installation_message_patches)) < (patch_count_for_assessment + 2 + patch_count_for_installation + 2))

        # Assert assessment truncation
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING)

        # Assert assessment truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # Assert installation truncation
        installation_truncated_substatus = substatus_file_data[0]["status"]["substatus"][1]
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING)

        # Assert installation truncated error
        self.__assert_truncated_error(installation_truncated_substatus, error_count=0)
        runtime.stop()

    def test_installation_operation_truncation_over_size_limit_success_path(self):
        """ Perform truncation on large assessment packages list and installatio pacakges list, setting both substatus status to warning and
        error code to 1 (warning) with Constants.StatusTruncationConfig.TRUNCATION_WARNING_MESSAGE """
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.INSTALLATION
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # SuccessInstallPath add 2 additional packages
        # {\"patchId\": \"kernel-default_4.4.49-92.11.1_Ubuntu_16.04\", \"name\": \"kernel-default\", \"version\": \"4.4.49-92.11.1\", \"classifications\": [\"Other\"]},
        #  {\"patchId\": \"libgoa-1_0-0_3.20.5-9.6_Ubuntu_16.04\", \"name\": \"libgoa-1_0-0\", \"version\": \"3.20.5-9.6\", \"classifications\": [\"Other\"]}

        patch_count_for_assessment = 19998
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_assessment)
        runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        patch_count_for_installation = 9998
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_installation)
        runtime.status_handler.set_package_install_status(test_packages, test_package_versions)
        runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with runtime.env_layer.file_system.open(runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)

        # Assert assessment summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count_for_assessment + 2, error_count=0)

        # Assert installation summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][1], patch_count_for_installation + 2, error_count=0)

        # Assert truncated status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        assessment_message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        installation_message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][1]["formattedMessage"]["message"])["patches"]

        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue((len(assessment_message_patches) + len(installation_message_patches)) < (patch_count_for_assessment + 2 + patch_count_for_installation + 2))

        # Assert assessment truncation
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING)

        # Assert assessment truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # Assert installation truncation
        installation_truncated_substatus = substatus_file_data[0]["status"]["substatus"][1]
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING)

        # Assert installation truncated error
        self.__assert_truncated_error(installation_truncated_substatus, error_count=0)
        runtime.stop()

    def test_installation_operation_truncation_both_over_size_limit_happy_path(self):
        """ Perform truncation on assessment packages list and installatio package list, setting assessment substatus status to warning and
        error code to 1 (warning) with Constants.StatusTruncationConfig.TRUNCATION_WARNING_MESSAGE
        keep installation substatus status as error and
        error code to 2 (error)
        """
        argument_composer = ArgumentComposer()
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('HappyPath')
        CoreMain(argument_composer.get_composed_arguments())

        patch_count_for_assessment = random.randint(950, 1200)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_assessment)
        runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        patch_count_for_installation = random.randint(875, 1200)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_installation)
        runtime.status_handler.set_package_install_status(test_packages, test_package_versions)
        runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)

        # Check telemetry events
        self.__check_telemetry_events(runtime)

        # HappyPath has already added 3 packages under assessment, we are adding more (anywhere between 875-1200) which will make the status file size over AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES, thereby truncation will take place,
        # HappyPath contains failed, pending, installed packages for installation
        # {\"patchId\": \"kernel-default_4.4.49-92.11.1_Ubuntu_16.04\", \"name\": \"kernel-default\", \"version\": \"4.4.49-92.11.1\", \"classifications\": [\"Security\"]},
        # {\"patchId\": \"libgcc_5.60.7-8.1_Ubuntu_16.04\", \"name\": \"libgcc\", \"version\": \"5.60.7-8.1\", \"classifications\": [\"Other\"]},
        # {\"patchId\": \"libgoa-1_0-0_3.20.5-9.6_Ubuntu_16.04\", \"name\": \"libgoa-1_0-0\", \"version\": \"3.20.5-9.6\", \"classifications\": [\"Other\"]}

        # Assert Complete status file
        with runtime.env_layer.file_system.open(runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        # Assert assessment summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count_for_assessment + 3, error_count=0)

        # Assert installation summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][1], patch_count_for_installation + 3, error_code=Constants.PatchOperationTopLevelErrorCode.ERROR, error_count=1)

        # Assert truncated status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        assessment_message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        installation_message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][1]["formattedMessage"]["message"])["patches"]

        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(len(assessment_message_patches) + len(installation_message_patches) < patch_count_for_assessment + 3 + patch_count_for_installation + 3)
        # Assert assessment truncation
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING)

        # Assert assessment truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # Assert installation truncation
        installation_truncated_substatus = substatus_file_data[0]["status"]["substatus"][1]
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR)

        # Assert installation truncated error
        self.__assert_truncated_error(installation_truncated_substatus, error_count=1)
        runtime.stop()

    def test_installation_operation_truncation_with_errors_over_size_limit(self):
        """ Perform truncation on assessment packages list and installation packages list, setting assessment substatus status to warning and
        error code to 1 (warning) with Constants.StatusTruncationConfig.TRUNCATION_WARNING_MESSAGE
        keep installation substatus status as error and
        error code to 2 (error)
        """
        argument_composer = ArgumentComposer()
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('FailInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # Test code add 2 additional packages
        # {\"patchId\": \"kernel-default_4.4.49-92.11.1_Ubuntu_16.04\", \"name\": \"kernel-default\", \"version\": \"4.4.49-92.11.1\", \"classifications\": [\"Security\"]},

        patch_count_for_assessment = 598
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_assessment)
        runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)

        runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        patch_count_for_installation = 318
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_installation)
        runtime.status_handler.set_package_install_status(test_packages, test_package_versions)

        # Adding multiple exceptions
        runtime.status_handler.add_error_to_status("exception0", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        runtime.status_handler.add_error_to_status("exception1", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        runtime.status_handler.add_error_to_status("exception2", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        runtime.status_handler.add_error_to_status("exception3", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        runtime.status_handler.add_error_to_status("exception4", Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
        runtime.status_handler.add_error_to_status("exception5", Constants.PatchOperationErrorCodes.OPERATION_FAILED)

        runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)

        # Assert Complete status file
        with runtime.env_layer.file_system.open(runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)

        # Assert assessment summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count_for_assessment + 2, error_count=0)

        # Assert installation summary
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][1], patch_count_for_installation + 2, error_code=Constants.PatchOperationTopLevelErrorCode.ERROR, error_count=5)

        # Assert truncated status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        assessment_message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        installation_message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][1]["formattedMessage"]["message"])["patches"]

        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)

        # Assert assessment truncation
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        # Assert assessment no truncation
        self.assertEqual(len(assessment_message_patches), patch_count_for_assessment + 2)
        # Assert assessment truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=0)

        # Test installation truncation
        self.assertTrue(len(installation_message_patches) < patch_count_for_installation + 2)
        installation_truncated_substatus = substatus_file_data[0]["status"]["substatus"][1]
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR)

        # Assert installation truncated error
        self.__assert_truncated_error(installation_truncated_substatus, error_count=5)
        runtime.stop()

    # Setup functions for testing
    def __check_telemetry_events(self, runtime):
        all_events = os.listdir(runtime.telemetry_writer.events_folder_path)
        self.assertTrue(len(all_events) > 0)
        latest_event_file = [pos_json for pos_json in os.listdir(runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertTrue('Core' in events[0]['TaskName'])
            f.close()

    def __assert_patch_summary_from_status(self, substatus_file_data, operation, patch_summary, status):
        self.assertEqual(substatus_file_data[0]["status"]["operation"], operation)

        if patch_summary == Constants.PATCH_ASSESSMENT_SUMMARY:
            substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        else:
            substatus_file_data = substatus_file_data[0]["status"]["substatus"][1]

        self.assertEqual(substatus_file_data["name"], patch_summary)
        self.assertEqual(substatus_file_data["status"], status.lower())

    def __asert_message_json_from_status(self, substatus_file_data, patch_count, error_code=Constants.PatchOperationTopLevelErrorCode.SUCCESS, error_count=0):
        message = json.loads(substatus_file_data["formattedMessage"]["message"])
        self.assertEqual(len(message["patches"]), patch_count)
        self.assertEqual(message["errors"]["code"], error_code)
        self.assertEqual(len(message["errors"]["details"]), error_count)

    def __assert_truncated_assessment_tombstone(self, message_patches):
        # assert tombstone, 3 types of tombstones Critical Security Other
        self.assertEqual(message_patches[-1]['patchId'], "Truncated_patch_list_id")
        self.assertEqual(message_patches[-2]['patchId'], "Truncated_patch_list_id")
        self.assertEqual(message_patches[-3]['patchId'], "Truncated_patch_list_id")
        self.assertEqual(message_patches[-1]['classifications'], ['Other'])
        self.assertEqual(message_patches[-2]['classifications'], ['Security'])
        self.assertEqual(message_patches[-3]['classifications'], ['Critical'])
        self.assertTrue("additional updates of classification" in message_patches[-1]['name'][0])

    def __assert_truncated_installation_tombstone(self, message_patches):
        # tombstone record
        self.assertEqual(len(message_patches), 3)      # 1 tombstone
        self.assertEqual(message_patches[-1]['name'], 'Truncated_patch_list_id')
        self.assertEqual(message_patches[-1]['patchId'], 'Truncated_patch_list_id')
        self.assertEqual(message_patches[-1]['classifications'][0], 'Other')
        self.assertNotEqual(message_patches[-2]['patchId'][0], 'Truncated_patch_list_id')

    def __assert_truncated_error(self, substatus_file_data, error_count):
        # assert error
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), error_count)

    def __set_up_packages_func(self, val):
        test_packages = []
        test_package_versions = []

        for i in range(0, val):
            test_packages.append('python-samba' + str(i))
            test_package_versions.append('2:4.4.5+dfsg-2ubuntu5.4')

        return test_packages, test_package_versions

if __name__ == '__main__':
    unittest.main()