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
import glob
import json
import random
import time
import unittest
import tempfile
import os
import sys
from core.src.bootstrap.Constants import Constants
from core.src.service_interfaces.StatusHandler import StatusHandler
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestStatusHandlerTruncation(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def __mock_os_remove(self, file_to_remove):
        raise Exception("File could not be deleted")

    def test_if_status_file_resets_on_load_if_malformed(self):
        # Mock complete status file with malformed json
        sample_json = '[{"version": 1.0, "timestampUTC": "2023-05-13T07:38:07Z", "statusx": {"name": "Azure Patch Management", "operation": "Installation", "status": "success", "code": 0, "formattedMessage": {"lang": "en-US", "message": ""}, "substatusx": []}}]'
        file_path = self.runtime.execution_config.status_folder
        example_file1 = os.path.join(file_path, '123.complete.status')
        self.runtime.execution_config.complete_status_file_path = example_file1

        with open(example_file1, 'w') as f:
            f.write(sample_json)

        # Mock complete status file with malformed json and being called in the load_status_file_components, and it will recreate a good complete_status_file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]
        self.assertEqual(substatus_file_data["status"]["name"], "Azure Patch Management")
        self.assertEqual(substatus_file_data["status"]["operation"], "Installation")
        self.assertIsNotNone(substatus_file_data["status"]["substatus"])
        self.assertEqual(len(substatus_file_data["status"]["substatus"]), 0)
        self.runtime.env_layer.file_system.delete_files_from_dir(example_file1, "*.complete.status")

    def test_if_complete_and_status_path_is_dir(self):
        self.old_complete_status_path = self.runtime.execution_config.complete_status_file_path
        self.runtime.execution_config.complete_status_file_path = self.runtime.execution_config.status_folder
        self.runtime.status_handler.load_status_file_components(initial_load=True)
        self.assertTrue(os.path.isfile(os.path.join(self.runtime.execution_config.status_folder, '1.complete.status')))

        self.old_status_path = self.runtime.execution_config.status_file_path
        self.runtime.execution_config.status_file_path = self.runtime.execution_config.status_folder
        self.runtime.status_handler.load_status_file_components(initial_load=True)
        self.assertTrue(os.path.isfile(os.path.join(self.runtime.execution_config.status_folder, '1.status')))

        # reset the status path
        self.runtime.execution_config.complete_status_file_path = self.old_complete_status_path
        self.runtime.execution_config.status_file_path = self.old_status_path

    def test_remove_old_complete_status_files(self):
        """ Create dummy files in status folder and check if the complete_status_file_path is the latest file and delete those dummy files """
        # Set up create temp file for log and set sys.stdout to it
        self.__create_temp_file_and_set_stdout()

        file_path = self.runtime.execution_config.status_folder
        for i in range(1, 15):
            with open(os.path.join(file_path, str(i + 100) + '.complete.status'), 'w') as f:
                f.write("test" + str(i))

        packages, package_versions = self.runtime.package_manager.get_all_updates()
        self.runtime.status_handler.set_package_assessment_status(packages, package_versions)
        self.runtime.status_handler.load_status_file_components(initial_load=True)

        # remove 10 complete status files
        count_status_files = glob.glob(os.path.join(file_path, '*.complete.status'))
        self.assertEqual(10, len(count_status_files))
        self.assertTrue(os.path.isfile(self.runtime.execution_config.complete_status_file_path))
        self.runtime.env_layer.file_system.delete_files_from_dir(file_path, '*.complete.status')
        self.assertFalse(os.path.isfile(os.path.join(file_path, '1.complete_status')))
        self.__read_temp_log_and_assert("Cleaned up older complete status files")

        # Reset sys.stdout, close and delete tmp
        self.__remove_temp_file_reset_stdout()

    def test_remove_old_complete_status_files_throws_exception(self):
        # Set up create temp file for log and set sys.stdout to it
        self.__create_temp_file_and_set_stdout()

        file_path = self.runtime.execution_config.status_folder
        for i in range(1, 16):
            with open(os.path.join(file_path, str(i + 100) + '.complete.status'), 'w') as f:
                f.write("test" + str(i))

        self.backup_os_remove = os.remove
        os.remove = self.__mock_os_remove
        self.assertRaises(Exception, self.runtime.status_handler.load_status_file_components(initial_load=True))
        self.__read_temp_log_and_assert("Error deleting complete status file")

        # reset os.remove() mock and remove *complete.status files
        os.remove = self.backup_os_remove
        self.runtime.env_layer.file_system.delete_files_from_dir(file_path, '*.complete.status')
        self.assertFalse(os.path.isfile(os.path.join(file_path, '1.complete_status')))

        # Reset sys.stdout, close and delete tmp
        self.__remove_temp_file_reset_stdout()

    def test_assessment_packages_map(self):
        patch_count = 5
        expected_patch_id = 'python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04'
        expected_value_critical = {'version': '2:4.4.5+dfsg-2ubuntu5.4', 'classifications': ['Critical'], 'name': 'python-samba0',
                                   'patchId': 'python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04'}

        status_handler = StatusHandler(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.vm_cloud_type)
        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        status_handler.set_package_assessment_status(test_packages, test_package_versions, 'Critical')

        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]

        self.__assert_packages_map(substatus_file_data, Constants.PATCH_ASSESSMENT_SUMMARY, patch_count, expected_patch_id, expected_value_critical, 'Critical')

    def test_installation_packages_map(self):
        patch_id_other = 'python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04'
        expected_value_other = {'version': '2:4.4.5+dfsg-2ubuntu5.4', 'classifications': ['Other'], 'name': 'python-samba0',
                          'patchId': 'python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04', 'patchInstallationState': 'Installed'}

        patch_id_critical = 'python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04'
        expected_value_critical = {'version': '2:4.4.5+dfsg-2ubuntu5.4', 'classifications': ['Critical'], 'name': 'python-samba0',
                          'patchId': 'python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04', 'patchInstallationState': 'Installed'}
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count = 50
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)

        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, 'Installed', 'Other')
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]

        # Assert Other classifications
        self.__assert_packages_map(substatus_file_data, Constants.PATCH_INSTALLATION_SUMMARY, patch_count, patch_id_other, expected_value_other, 'Other')

        # Update the classification from Other to Critical
        self.runtime.status_handler.set_package_install_status_classification(test_packages, test_package_versions, 'Critical')
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]

        self.__assert_packages_map(substatus_file_data, Constants.PATCH_INSTALLATION_SUMMARY, patch_count, patch_id_critical,
            expected_value_critical, 'Critical')

    def test_load_status_and_set_package_install_status(self):
        patch_count = 5
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        file_path = self.runtime.execution_config.status_folder
        example_file1 = os.path.join(file_path, '123.complete.status')
        sample_json = [{"version": 1.0, "timestampUTC": "2023-06-17T02:06:19Z", "status": {"name": "Azure Patch Management", "operation": "Installation", "status": "success", "code": 0, "formattedMessage": {"lang": "en-US", "message": ""}, "substatus": [{"name": "PatchInstallationSummary", "status": "transitioning", "code": 0, "formattedMessage": {"lang": "en-US", "message": "{\"installationActivityId\": \"c365ab46-a12a-4388-853b-5240a0702124\", \"rebootStatus\": \"NotNeeded\", \"maintenanceWindowExceeded\": false, \"notSelectedPatchCount\": 0, \"excludedPatchCount\": 0, \"pendingPatchCount\": 0, \"installedPatchCount\": 5, \"failedPatchCount\": 0, \"patches\": [{\"patchId\": \"python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04\", \"name\": \"python-samba0\", \"version\": \"2:4.4.5+dfsg-2ubuntu5.4\", \"classifications\": [\"Other\"], \"patchInstallationState\": \"Pending\"}, {\"patchId\": \"python-samba1_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04\", \"name\": \"python-samba1\", \"version\": \"2:4.4.5+dfsg-2ubuntu5.4\", \"classifications\": [\"Security\"], \"patchInstallationState\": \"Failed\"}, {\"patchId\": \"python-samba2_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04\", \"name\": \"python-samba2\", \"version\": \"2:4.4.5+dfsg-2ubuntu5.4\", \"classifications\": [\"Other\"], \"patchInstallationState\": \"Not_Selected\"}, {\"patchId\": \"python-samba3_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04\", \"name\": \"python-samba3\", \"version\": \"2:4.4.5+dfsg-2ubuntu5.4\", \"classifications\": [\"Other\"], \"patchInstallationState\": \"Pending\"}, {\"patchId\": \"python-samba4_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04\", \"name\": \"python-samba4\", \"version\": \"2:4.4.5+dfsg-2ubuntu5.4\", \"classifications\": [\"Unclassified\"], \"patchInstallationState\": \"Failed\"}], \"startTime\": \"2023-06-17T02:06:19.480634Z\", \"lastModifiedTime\": \"2023-06-17T02:06:19Z\", \"maintenanceRunId\": \"\", \"errors\": {\"code\": 0, \"details\": [], \"message\": \"0 error/s reported.\"}}"}}]}}]
        with open(example_file1, 'w') as f:
            f.write(json.dumps(sample_json))
        self.runtime.status_handler.status_file_path = example_file1
        self.runtime.status_handler.load_status_file_components(initial_load=True)

        # Test for set_package_install_status
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, 'Installed', 'Critical')
        with self.runtime.env_layer.file_system.open(self.runtime.status_handler.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]

        self.__assert_installation_set_packages_methods(substatus_file_data, Constants.PATCH_INSTALLATION_SUMMARY, patch_count)

        # Test for set_package_install_status_classification
        self.runtime.status_handler.set_package_install_status_classification(test_packages, test_package_versions, "Critical")
        with self.runtime.env_layer.file_system.open(self.runtime.status_handler.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]

        self.__assert_installation_set_packages_methods(substatus_file_data, Constants.PATCH_INSTALLATION_SUMMARY, patch_count)

        # Clean up complete.status files
        self.runtime.env_layer.file_system.delete_files_from_dir(self.runtime.status_handler.status_file_path, '*.complete.status')

    def test_assessment_status_file_truncation_under_size_limit(self):
        """ Perform no truncation on assessment packages list """
        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count = 500
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert Complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert no truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        message = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])
        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertEqual(substatus_file_data[0]["status"]["substatus"][0]["name"], Constants.PATCH_ASSESSMENT_SUMMARY,)
        self.assertEqual(substatus_file_data[0]["status"]["substatus"][0]["status"], Constants.STATUS_SUCCESS.lower())
        self.assertEqual(len(message["patches"]), patch_count)
        self.assertNotEqual(message["patches"][-1]['patchId'], "Truncated_patch_list_id")
        self.assertTrue('Truncated_patch_list_id' not in message["patches"][-1]['name'])
        self.assertEqual(message["errors"]["code"], 0)
        self.assertEqual(len(message["errors"]["details"]), 0)
        self.assertFalse("review this log file on the machine" in message)

    def test_assessment_status_file_truncation_over_size_limit(self):
        """ Perform truncation on only assessment packages list """
        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert assessment truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(len(message_patches) < patch_count)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING)

        # Assert truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=0)

    def test_assessment_status_file_truncation_over_large_size_limit_for_extra_chars(self):
        """ Perform truncation on large assessment package list, the 2 times json.dumps() will escape " adding \, adding 1 additional byte check if total byte size over the size limit """
        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count = 100000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions, "Critical")
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert assessment truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        self.assertTrue(len(message_patches) < patch_count)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.ASSESSMENT, Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_WARNING)

        # Assert truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=0)

    def test_assessment_status_file_truncation_over_size_limit_with_errors(self):
        """ Perform truncation on only assessment packages list with multiple errors """
        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions, "Security")

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)

        # Assert complete status file
        self.__assert_complete_status_errors(Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_ERROR, patch_count)

        # Assert assessment truncated status file with multi errors
        self.__assert_truncated_status_multi_errors(Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_ERROR, error_count=5)

    def test_installation_status_file_truncation_over_size_limit(self):
        """ Perform truncation on only installation packages list """
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert installation truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(len(message_patches) < patch_count)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING)

        # Assert truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=0)

    def test_installation_status_file_truncation_over_size_limit_low_priority_packages(self):
        """ Perform truncation on only installation low priority (Pending, Excluded, Not_Selected) packages list """
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count = random.randint(780, 1100)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.PENDING)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert installation truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(len(message_patches) < patch_count)

        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING)

        # Assert truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=0)

    def test_installation_status_file_truncation_over_large_size_limit_with_extra_chars(self):
        """ Perform truncation on only large installation packages list, the 2 times json.dumps() will escape " adding \, adding 1 additional byte check if total byte size over the size limit """
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count = 100000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS)
        self.__asert_message_json_from_status(substatus_file_data[0]["status"]["substatus"][0], patch_count, error_count=0)

        # Assert installation truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        message_patches = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])["patches"]
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(len(message_patches) < patch_count)
        self.__assert_patch_summary_from_status(substatus_file_data, Constants.INSTALLATION, Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_WARNING)

        # Assert truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=0)

    def test_installation_status_file_truncation_over_size_limit_with_error(self):
        """ Perform truncation on only installation packages list with multiple errors """
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)

        # Assert complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)

        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)

        # Assert complete status file
        self.__assert_complete_status_errors(Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, patch_count)

        # Assert installation truncated status file with multi errors
        self.__assert_truncated_status_multi_errors(Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_ERROR, error_count=5)

    def test_truncation_method_time_performance(self):
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        self.__create_temp_file_and_set_stdout()    # set tmp file for storing sys.stout()

        # Start no truncation performance test
        Constants.StatusTruncationConfig.TURN_ON_TRUNCATION = False
        no_truncate_start_time = time.time()
        for i in range(0, 301):
            test_packages, test_package_versions = self.__set_up_packages_func(500)
            self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
            self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)

        no_truncate_end_time = time.time()
        no_truncate_performance_time = no_truncate_end_time - no_truncate_start_time
        no_truncate_performance_time_formatted = self.__convert_test_performance_to_date_time(no_truncate_performance_time)

        # Start truncation performance test
        Constants.StatusTruncationConfig.TURN_ON_TRUNCATION = True
        truncate_start_time = time.time()
        for i in range(0, 301):
            test_packages, test_package_versions = self.__set_up_packages_func(500)
            self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
            self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)

        truncate_end_time = time.time()
        truncate_performance_time = truncate_end_time - truncate_start_time
        truncate_performance_time_formatted = self.__convert_test_performance_to_date_time(truncate_performance_time)

        self.__remove_temp_file_reset_stdout()  # remove and reset tmp file for storing sys.stout()

        self.runtime.status_handler.composite_logger.log_debug('no_truncate_performance_time_formatted' + no_truncate_performance_time_formatted)
        self.runtime.status_handler.composite_logger.log_debug('truncate_performance_time_formatted' + truncate_performance_time_formatted)
        self.assertTrue(no_truncate_performance_time < truncate_performance_time)

    # Setup functions for testing
    def __assert_packages_map(self, substatus_file_data, patch_summary, patch_count, expected_patch_id, expected_patch_value, classification):
        formatted_message = json.loads(substatus_file_data['formattedMessage']['message'])
        self.assertTrue(substatus_file_data["name"] == patch_summary)
        self.assertEqual(len(formatted_message['patches']), patch_count)
        self.assertEqual(formatted_message['patches'][0]['patchId'], expected_patch_id)
        self.assertEqual(formatted_message['patches'][0]['name'], 'python-samba0')
        self.assertEqual(formatted_message['patches'][0], expected_patch_value)
        self.assertEqual(formatted_message['patches'][0]['classifications'], [classification])

    def __assert_installation_set_packages_methods(self, substatus_file_data, patch_summary, patch_count):
        self.assertEqual(substatus_file_data["name"], patch_summary)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), patch_count)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["name"], "python-samba0")
        self.assertTrue('Critical' in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["name"], "python-samba1")
        self.assertEqual('Critical', str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["classifications"][0]))
        self.assertEqual('Installed', str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["patchInstallationState"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["name"], "python-samba2")
        self.assertEqual('python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04', str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue('Critical' in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["classifications"]))
        self.runtime.env_layer.file_system.delete_files_from_dir(self.runtime.status_handler.status_file_path, '*.complete.status')

    def __assert_patch_summary_from_status(self, substatus_file_data, operation, patch_summary, status):
        self.assertEqual(substatus_file_data[0]["status"]["operation"], operation)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], patch_summary)
        self.assertEqual(substatus_file_data["status"], status.lower())

    def __asert_message_json_from_status(self, substatus_file_data, patch_count, error_count=0):
        message = json.loads(substatus_file_data["formattedMessage"]["message"])
        self.assertEqual(len(message["patches"]), patch_count)
        self.assertEqual(message["errors"]["code"], Constants.PatchOperationTopLevelErrorCode.SUCCESS)
        self.assertEqual(len(message["errors"]["details"]), error_count)

    def __assert_truncated_assessment_tombstone(self, message_patches):
        # assert tombstone
        self.assertEqual(message_patches[-1]['patchId'], "Truncated_patch_list_id")
        self.assertTrue("additional updates of classification" in message_patches[-1]['name'][0])
        self.assertEqual(message_patches[-1]['classifications'], ['Other'])

    def __assert_truncated_installation_tombstone(self, message_patches):
        # assert tombstone
        self.assertEqual(message_patches[-1]['patchId'], "Truncated_patch_list_id")
        self.assertEqual(message_patches[-1]['name'][0], "Truncated_patch_list_id")
        self.assertEqual(message_patches[-1]['classifications'], ['Other'])

    def __assert_truncated_error(self, substatus_file_data, error_count):
        # assert error
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), error_count)

    def __assert_complete_status_errors(self, patch_summary, status, patch_count):
        # Adding multiple exceptions
        self.runtime.status_handler.add_error_to_status("exception0", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception1", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception2", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception3", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception4", Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
        self.runtime.status_handler.add_error_to_status("exception5", Constants.PatchOperationErrorCodes.OPERATION_FAILED)

        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        message = json.loads(substatus_file_data[0]["status"]["substatus"][0]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data[0]["status"]["substatus"][0]["name"], patch_summary)
        self.assertEqual(substatus_file_data[0]["status"]["substatus"][0]["status"], status.lower())
        self.assertEqual(len(message["patches"]), patch_count)
        self.assertNotEqual(message["errors"], None)
        self.assertEqual(message["errors"]["code"], Constants.PatchOperationTopLevelErrorCode.ERROR)
        self.assertEqual(len(message["errors"]["details"]), 5)
        self.assertEqual(message["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.OPERATION_FAILED)
        self.assertEqual(message["errors"]["details"][1]["code"], Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
        self.assertEqual(message["errors"]["details"][0]["message"], "exception5")

    def __assert_truncated_status_multi_errors(self, patch_summary, status, error_count):
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        substatus_file_data_byte_size = len(json.dumps(substatus_file_data))
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.AGENT_FACING_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(substatus_file_data_byte_size < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertEqual(substatus_file_data[0]["status"]["substatus"][0]["name"], patch_summary)
        self.assertEqual(substatus_file_data[0]["status"]["substatus"][0]["status"], status.lower())

        # assert truncated error
        self.__assert_truncated_error(substatus_file_data[0]["status"]["substatus"][0], error_count=error_count)

    def __convert_test_performance_to_date_time(self, performance_time):
        performance_time = abs(performance_time)

        # Calc days, hours, minutes, and seconds
        days, remainder = divmod(performance_time, 86400)  # 86400 seconds in a day
        hours, remainder = divmod(remainder, 3600)  # 3600 seconds in an hour
        minutes, seconds = divmod(remainder, 60)  # 60 seconds in a minute

        # Format the result
        formatted_time = "%d days, %d hours, %d minutes, %.6f seconds" % (int(days), int(hours), int(minutes), seconds)
        return formatted_time

    # Setup functions for writing log to temp and read output
    def __create_temp_file_and_set_stdout(self):
        # Set up create temp file for log and set sys.stdout to it
        self.temp_stdout = tempfile.NamedTemporaryFile(delete=False, mode="w+")
        self.saved_stdout = sys.stdout  # Save the original stdout
        sys.stdout = self.temp_stdout   # set it to the temporary file

    def __remove_temp_file_reset_stdout(self):
        sys.stdout = self.saved_stdout  # redirect to original stdout
        self.temp_stdout.close()
        os.remove(self.temp_stdout.name)    # Remove the temporary file

    def __read_temp_log_and_assert(self, expected_string):
        self.temp_stdout.flush()
        with open(self.temp_stdout.name, 'r') as temp_file:
            captured_log_output = temp_file.read()
            self.assertIn(expected_string, captured_log_output)

    # Setup functions to populate packages and versions for truncation
    def __set_up_packages_func(self, val):
        test_packages = []
        test_package_versions = []

        for i in range(0, val):
            test_packages.append('python-samba' + str(i))
            test_package_versions.append('2:4.4.5+dfsg-2ubuntu5.4')

        return test_packages, test_package_versions

if __name__ == '__main__':
    unittest.main()
