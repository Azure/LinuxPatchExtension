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
import json
import unittest
from src.bootstrap.Constants import Constants
from src.service_interfaces.StatusHandler import StatusHandler
from tests.library.ArgumentComposer import ArgumentComposer
from tests.library.RuntimeCompositor import RuntimeCompositor


class TestStatusHandler(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def test_set_package_assessment_status(self):
        packages, package_versions = self.runtime.package_manager.get_all_updates()
        self.runtime.status_handler.set_package_assessment_status(packages, package_versions)
        substatus_file_data = []
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), 3)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["name"], "python-samba")
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["name"], "samba-common-bin")
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["name"], "samba-libs")
        self.assertTrue("python-samba_2:4.4.5+dfsg-2ubuntu5.4" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["patchId"]))

    def test_set_package_install_status(self):
        packages, package_versions = self.runtime.package_manager.get_all_updates()
        self.runtime.status_handler.set_package_install_status(packages, package_versions)
        substatus_file_data = []
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), 3)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["name"], "python-samba")
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["name"], "samba-common-bin")
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["name"], "samba-libs")
        self.assertTrue("python-samba_2:4.4.5+dfsg-2ubuntu5.4" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["patchInstallationState"], "Pending")

    def test_set_installation_reboot_status(self):
        self.assertRaises(Exception, self.runtime.status_handler.set_installation_reboot_status, "INVALID_STATUS")

        # Reboot status not updated as it fails state transition validation
        self.runtime.status_handler.set_installation_substatus_json()
        self.runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.COMPLETED)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["rebootStatus"], Constants.RebootStatus.NOT_NEEDED)

        self.runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.REQUIRED)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["rebootStatus"], Constants.RebootStatus.REQUIRED)

    def test_set_maintenance_window_exceeded(self):
        self.runtime.status_handler.set_installation_substatus_json()
        self.runtime.status_handler.set_maintenance_window_exceeded(True)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertTrue(json.loads(substatus_file_data["formattedMessage"]["message"])["maintenanceWindowExceeded"])

    def test_add_error(self):
        # Setting operation to assessment to add all errors under assessment substatus
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        # Unexpected input
        self.runtime.status_handler.add_error_to_status(None)
        self.runtime.status_handler.set_assessment_substatus_json()
        substatus_file_data = []
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)

        # Adding multiple exceptions
        self.runtime.status_handler.add_error_to_status("exception1", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception2", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception3", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception4", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception5", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception6", Constants.PatchOperationErrorCodes.OPERATION_FAILED)

        # Trying to add existing error
        self.runtime.status_handler.add_error_to_status("Adding same exception " + Constants.ERROR_ADDED_TO_STATUS, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)

        # Test message restrictions
        self.runtime.status_handler.add_error_to_status("a"*130, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)

        substatus_file_data = []
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]

        self.assertNotEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"], None)
        self.assertTrue("Adding same exception" not in str(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]))
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], 1)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 5)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][1]["code"], Constants.PatchOperationErrorCodes.OPERATION_FAILED)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["message"], "a"*125 + "...")

        # Adding installation error
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        self.runtime.status_handler.add_error_to_status("installexception1", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        substatus_file_data = []
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][1]
        self.assertNotEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"], None)
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], 1)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 1)

    def test_status_file_initial_load(self):
        # for non autopatching request, with Reboot started
        self.runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        status_handler = StatusHandler(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer)
        self.assertTrue(status_handler is not None)

        # for autopatching request, with reboot started
        self.runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        self.runtime.execution_config.patch_rollout_id = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        status_handler = StatusHandler(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][1]
        self.assertTrue(status_handler is not None)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["shouldReportToHealthStore"], False)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patchVersion"], Constants.PATCH_VERSION_UNKNOWN)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_SUCCESS.lower())

        # for autopatching request, with reboot not started
        self.runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.COMPLETED)
        self.runtime.execution_config.patch_rollout_id = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        status_handler = StatusHandler(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertTrue(status_handler is not None)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["shouldReportToHealthStore"], False)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patchVersion"], Constants.PATCH_VERSION_UNKNOWN)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_SUCCESS.lower())

    def test_set_patch_metadata_for_health_store_substatus_json(self):
        # setting health store properties
        self.runtime.status_handler.set_patch_metadata_for_health_store_substatus_json(status=Constants.STATUS_SUCCESS, patch_version="2020-07-08", report_to_health_store=True, wait_after_update=True)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["shouldReportToHealthStore"], True)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patchVersion"], "2020-07-08")
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_SUCCESS.lower())

        # using default values
        self.runtime.status_handler.set_patch_metadata_for_health_store_substatus_json()
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["shouldReportToHealthStore"], False)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patchVersion"], Constants.PATCH_VERSION_UNKNOWN)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_SUCCESS.lower())


if __name__ == '__main__':
    unittest.main()
