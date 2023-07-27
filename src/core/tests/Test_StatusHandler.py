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
import os
import random
import unittest
from core.src.bootstrap.Constants import Constants
from core.src.service_interfaces.StatusHandler import StatusHandler
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestStatusHandler(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def test_set_package_assessment_status(self):
        # startedBy should be set to User in status for Assessment
        packages, package_versions = self.runtime.package_manager.get_all_updates()
        self.runtime.status_handler.set_package_assessment_status(packages, package_versions)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), 3)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["name"], "python-samba")
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["name"], "samba-common-bin")
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["name"], "samba-libs")
        self.assertTrue("python-samba_2:4.4.5+dfsg-2ubuntu5.4" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["startedBy"], Constants.PatchAssessmentSummaryStartedBy.USER)

    def test_set_package_assessment_status_for_auto_assessment(self):
        # startedBy should be set to Platform in status for Auto Assessment
        self.runtime.execution_config.exec_auto_assess_only = True
        packages, package_versions = self.runtime.package_manager.get_all_updates()
        self.runtime.status_handler.set_package_assessment_status(packages, package_versions)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), 3)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["name"], "python-samba")
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["name"], "samba-common-bin")
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["name"], "samba-libs")
        self.assertTrue("python-samba_2:4.4.5+dfsg-2ubuntu5.4" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["startedBy"], Constants.PatchAssessmentSummaryStartedBy.PLATFORM)

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

    def test_set_package_install_status_extended(self):
        packages, package_versions = self.runtime.package_manager.get_all_updates()
        self.runtime.status_handler.set_package_install_status(packages, package_versions)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["name"], "samba-common-bin")
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["patchInstallationState"], Constants.PENDING)
        self.runtime.status_handler.set_package_install_status("samba-common-bin", "2:4.4.5+dfsg-2ubuntu5.4", Constants.INSTALLED)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["name"], "samba-common-bin")
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["patchInstallationState"], Constants.INSTALLED)

    def test_set_package_install_status_classification(self):
        packages, package_versions = self.runtime.package_manager.get_all_updates()
        self.runtime.status_handler.set_package_install_status(packages, package_versions)
        sec_packages, sec_package_versions = self.runtime.package_manager.get_security_updates()
        self.runtime.status_handler.set_package_install_status_classification(sec_packages, sec_package_versions, "Security")
        substatus_file_data = []
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), 3)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["name"], "python-samba")
        self.assertTrue("Security" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["name"], "samba-common-bin")
        self.assertTrue("Security" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["name"], "samba-libs")
        self.assertTrue("python-samba_2:4.4.5+dfsg-2ubuntu5.4" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue("Security" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["classifications"]))

    def test_set_package_install_status_classification_not_set(self):
        packages, package_versions = self.runtime.package_manager.get_all_updates()
        self.runtime.status_handler.set_package_install_status(packages, package_versions)
        sec_packages, sec_package_versions = self.runtime.package_manager.get_security_updates()
        self.runtime.status_handler.set_package_install_status_classification(sec_packages, sec_package_versions)
        substatus_file_data = []
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), 3)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["name"], "python-samba")
        self.assertTrue("Other" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["name"], "samba-common-bin")
        self.assertTrue("Other" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["name"], "samba-libs")
        self.assertTrue("python-samba_2:4.4.5+dfsg-2ubuntu5.4" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue("Other" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["classifications"]))

    def test_set_package_install_unknown_patch_state_recorded(self):
        packages, package_versions = self.runtime.package_manager.get_all_updates()
        self.runtime.status_handler.set_package_install_status(packages, package_versions, Constants.AVAILABLE)

        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), 3)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["name"], "python-samba")
        self.assertTrue("Other" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertEqual("Available", str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["patchInstallationState"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["name"], "samba-common-bin")
        self.assertTrue("Other" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["name"], "samba-libs")
        self.assertTrue("python-samba_2:4.4.5+dfsg-2ubuntu5.4" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue("Other" in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["classifications"]))

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

        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

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

        self.assertEqual("Success".lower(), str(substatus_file_data["status"]).lower())
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

    def test_add_duplicate_error(self):
        # Setting operation to assessment to add all errors under assessment substatus
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        # Unexpected input
        self.runtime.status_handler.add_error_to_status(None)
        self.runtime.status_handler.set_assessment_substatus_json()
        substatus_file_data = []
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)

        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Adding multiple, duplicate exceptions
        self.runtime.status_handler.add_error_to_status("exception1", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception1", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception2", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception2", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception2: extra details", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception2", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception6", Constants.PatchOperationErrorCodes.OPERATION_FAILED)

        substatus_file_data = []
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]

        self.assertEqual("Success".lower(), str(substatus_file_data["status"]).lower())
        self.assertNotEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"], None)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], 1)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 3)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.OPERATION_FAILED)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][1]["code"], Constants.PatchOperationErrorCodes.DEFAULT_ERROR)

    def test_add_error_fail(self):
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        import tempfile
        tempfile_backup = tempfile.NamedTemporaryFile
        tempfile.NamedTemporaryFile = None

        # Error within retries for writing temporary file
        error_raised = False
        try:
            self.runtime.status_handler.add_error_to_status("test")
        except Exception as error:
            error_raised = True
            self.assertTrue("retries exhausted" in str(error))

        self.assertTrue(error_raised)
        tempfile.NamedTemporaryFile = tempfile_backup

    def test_status_file_initial_load(self):
        # for non autopatching request, with Reboot started
        self.runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        status_handler = StatusHandler(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.vm_cloud_type)
        self.assertTrue(status_handler is not None)

        # for autopatching request, with reboot started
        self.runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        self.runtime.status_handler.set_patch_metadata_for_healthstore_substatus_json()
        self.runtime.execution_config.maintenance_run_id = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        status_handler = StatusHandler(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.vm_cloud_type)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertTrue(len(substatus_file_data) == 1)

        # for autopatching request, with reboot not started
        self.runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.COMPLETED)
        self.runtime.execution_config.maintenance_run_id = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        status_handler = StatusHandler(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.vm_cloud_type)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertTrue(status_handler is not None)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["shouldReportToHealthStore"], False)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patchVersion"], Constants.PATCH_VERSION_UNKNOWN)
        self.assertEqual(substatus_file_data["status"].lower(), Constants.STATUS_SUCCESS.lower())

        # fail to load status file
        self.runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        backup_file_system_open = self.runtime.env_layer.file_system.open
        self.runtime.env_layer.file_system.open = None
        status_handler_failed = False
        try:
            status_handler = StatusHandler(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.vm_cloud_type)
        except Exception as error:
            status_handler_failed = True

        self.assertTrue(status_handler_failed)
        self.runtime.env_layer.file_system.open = backup_file_system_open

    def test_set_patch_metadata_for_healthstore_substatus_json(self):
        # setting healthstore properties
        self.runtime.status_handler.set_patch_metadata_for_healthstore_substatus_json(status=Constants.STATUS_SUCCESS, patch_version="2020-07-08", report_to_healthstore=True, wait_after_update=True)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["shouldReportToHealthStore"], True)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patchVersion"], "2020-07-08")
        self.assertEqual(substatus_file_data["status"].lower(), Constants.STATUS_SUCCESS.lower())

        # using default values
        self.runtime.status_handler.set_patch_metadata_for_healthstore_substatus_json()
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["shouldReportToHealthStore"], False)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patchVersion"], Constants.PATCH_VERSION_UNKNOWN)
        self.assertEqual(substatus_file_data["status"].lower(), Constants.STATUS_SUCCESS.lower())

    def get_status_handler_substatus_maintenance_run_id(self):
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
            return json.loads(substatus_file_data[0]['formattedMessage']['message'])['maintenanceRunId']

    def test_status_file_maintenance_run_id(self):
        # Testing None/empty values for maintenance run id
        self.runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        status_handler = StatusHandler(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.vm_cloud_type)
        self.assertTrue(status_handler is not None)

        # Expect datetime string
        expected_maintenance_run_id = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        self.runtime.execution_config.maintenance_run_id = expected_maintenance_run_id
        self.runtime.status_handler.set_installation_substatus_json()
        self.assertEqual(expected_maintenance_run_id, self.get_status_handler_substatus_maintenance_run_id())

        # Expect empty string
        expected_maintenance_run_id = ''
        self.runtime.execution_config.maintenance_run_id = expected_maintenance_run_id  # Give empty string, expect empty string
        self.runtime.status_handler.set_installation_substatus_json()
        self.assertEqual(expected_maintenance_run_id, self.get_status_handler_substatus_maintenance_run_id())

        self.runtime.execution_config.maintenance_run_id = None  # Give None, expect empty string
        self.runtime.status_handler.set_installation_substatus_json()
        self.assertEqual(expected_maintenance_run_id, self.get_status_handler_substatus_maintenance_run_id())

    def test_sequence_number_changed_termination_auto_assess_only(self):
        self.runtime.execution_config.exec_auto_assess_only = True
        self.runtime.status_handler.report_sequence_number_changed_termination()
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
            self.assertTrue(substatus_file_data["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
            formatted_message = json.loads(substatus_file_data['formattedMessage']['message'])
            self.assertTrue(formatted_message["errors"]["details"][0]["code"] == Constants.PatchOperationErrorCodes.NEWER_OPERATION_SUPERSEDED)
            self.assertEqual(formatted_message["startedBy"], Constants.PatchAssessmentSummaryStartedBy.PLATFORM)

    def test_sequence_number_changed_termination_configuration_only(self):
        self.runtime.execution_config.operation = Constants.CONFIGURE_PATCHING
        self.runtime.status_handler.set_current_operation(Constants.CONFIGURE_PATCHING)

        self.runtime.status_handler.report_sequence_number_changed_termination()
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
            self.assertTrue(substatus_file_data["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
            self.assertEqual(substatus_file_data["status"], Constants.STATUS_ERROR.lower())
            formatted_message = json.loads(substatus_file_data['formattedMessage']['message'])
            self.assertTrue(formatted_message["errors"]["details"][0]["code"] == Constants.PatchOperationErrorCodes.NEWER_OPERATION_SUPERSEDED)

    def test_sequence_number_changed_termination_installation(self):
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        self.runtime.status_handler.report_sequence_number_changed_termination()
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
            self.assertTrue(substatus_file_data["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
            self.assertEqual(substatus_file_data["status"], Constants.STATUS_ERROR.lower())
            formatted_message = json.loads(substatus_file_data['formattedMessage']['message'])
            self.assertTrue(formatted_message["errors"]["details"][0]["code"] == Constants.PatchOperationErrorCodes.NEWER_OPERATION_SUPERSEDED)

    def test_set_patch_metadata_for_healthstore_substatus_json_auto_assess_transitioning(self):
        self.runtime.execution_config.exec_auto_assess_only = True
        self.assertRaises(Exception,
                          lambda: self.runtime.status_handler.set_patch_metadata_for_healthstore_substatus_json())

    def test_set_configure_patching_substatus_json_auto_assess_transitioning(self):
        self.runtime.execution_config.exec_auto_assess_only = True
        self.assertRaises(Exception,
                          lambda: self.runtime.status_handler.set_configure_patching_substatus_json())

    def test_set_current_operation_auto_assess_non_assessment(self):
        self.runtime.execution_config.exec_auto_assess_only = True
        self.assertRaises(Exception,
                          lambda: self.runtime.status_handler.set_current_operation(Constants.INSTALLATION))

    def test_sort_packages_by_classification_and_state(self):
        with self.runtime.env_layer.file_system.open("../../extension/tests/helpers/PatchOrderAssessmentSummary.json", 'r') as file_handle:
            assessment_patches = json.load(file_handle)["patches"]
            assessment_patches_sorted = self.runtime.status_handler.sort_packages_by_classification_and_state(assessment_patches)
            #                                                                           + Classifications    | Patch State +
            #                                                                           |--------------------|-------------|
            self.assertEqual(assessment_patches_sorted[0]["name"], "test-package-1")  # | Critical           |             |
            self.assertEqual(assessment_patches_sorted[1]["name"], "test-package-4")  # | Security, Critical |             |
            self.assertEqual(assessment_patches_sorted[2]["name"], "test-package-5")  # | Critical, Other    |             |
            self.assertEqual(assessment_patches_sorted[3]["name"], "test-package-3")  # | Other, Security    |             |
            self.assertEqual(assessment_patches_sorted[4]["name"], "test-package-7")  # | Security           |             |
            self.assertEqual(assessment_patches_sorted[5]["name"], "test-package-2")  # | Other              |             |
            self.assertEqual(assessment_patches_sorted[6]["name"], "test-package-6")  # | Unclassified       |             |

        with self.runtime.env_layer.file_system.open("../../extension/tests/helpers/PatchOrderInstallationSummary.json", 'r') as file_handle:
            installation_patches = json.load(file_handle)["patches"]
            installation_patches_sorted = self.runtime.status_handler.sort_packages_by_classification_and_state(installation_patches)
            #                                                                              + Classifications    | Patch State +
            #                                                                              |--------------------|-------------|
            self.assertEqual(installation_patches_sorted[0]["name"], "test-package-12")  # | Critical, Security | Failed      |
            self.assertEqual(installation_patches_sorted[1]["name"], "test-package-14")  # | Critical           | Installed   |
            self.assertEqual(installation_patches_sorted[2]["name"], "test-package-13")  # | Critical           | Available   |
            self.assertEqual(installation_patches_sorted[3]["name"], "test-package-8")  #  | Security, Critical | Excluded    |

            self.assertEqual(installation_patches_sorted[4]["name"], "test-package-6")  #  | Security           | Failed      |
            self.assertEqual(installation_patches_sorted[5]["name"], "test-package-11")  # | Security           | Installed   |
            self.assertEqual(installation_patches_sorted[6]["name"], "test-package-10")  # | Security           | Available   |
            self.assertEqual(installation_patches_sorted[7]["name"], "test-package-9")  #  | Security           | Pending     |
            self.assertEqual(installation_patches_sorted[8]["name"], "test-package-7")  #  | Security           | NotSelected |


            self.assertEqual(installation_patches_sorted[9]["name"], "test-package-5")  #  | Other              | Installed   |
            self.assertEqual(installation_patches_sorted[10]["name"], "test-package-4")  # | Other              | Available   |
            self.assertEqual(installation_patches_sorted[11]["name"], "test-package-3")  # | Other              | Pending     |
            self.assertEqual(installation_patches_sorted[12]["name"], "test-package-2")  # | Other              | Excluded    |
            self.assertEqual(installation_patches_sorted[13]["name"], "test-package-1")  # | Other              | NotSelected |

    def test_if_status_file_resets_on_load_if_malformed(self):
        # Mock complete status file with malformed json
        sample_json = '[{"version": 1.0, "timestampUTC": "2023-05-13T07:38:07Z", "statusx": {"name": "Azure Patch Management", "operation": "Installation", "status": "success", "code": 0, "formattedMessage": {"lang": "en-US", "message": ""}, "substatusx": []}}]'
        file_path = self.runtime.execution_config.status_folder
        example_file1 = os.path.join(file_path, '123.complete.status')
        self.runtime.execution_config.complete_status_file_path = example_file1

        with open(example_file1, 'w') as f:
            f.write(sample_json)

        status_handler = StatusHandler(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.vm_cloud_type)
        # Mock complete status file with malformed json and being called in the load_status_file_components, and it will recreate a good complete_status_file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]
        self.assertEqual(substatus_file_data["status"]["name"], "Azure Patch Management")
        self.assertEqual(substatus_file_data["status"]["operation"], "Installation")
        self.assertIsNotNone(substatus_file_data["status"]["substatus"])
        self.assertEqual(len(substatus_file_data["status"]["substatus"]), 0)
        self.runtime.env_layer.file_system.delete_files_from_dir(example_file1, "*.complete.status")

    def test_if_complete_status_path_is_dir(self):
        self.runtime.execution_config.status_file_path = self.runtime.execution_config.status_folder
        self.assertRaises(Exception, self.runtime.status_handler.load_status_file_components(initial_load=True))

    def test_assessment_packages_map(self):
        patch_count_for_test = 5
        expected_patch_id = 'python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04'

        status_handler = StatusHandler(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.vm_cloud_type)
        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_test)
        status_handler.set_package_assessment_status(test_packages, test_package_versions, 'Critical')

        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]

        self.assertTrue(substatus_file_data["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        formatted_message = json.loads(substatus_file_data['formattedMessage']['message'])
        self.assertEqual(len(formatted_message['patches']), patch_count_for_test)
        self.assertEqual(formatted_message['patches'][0]['classifications'], ['Critical'])
        self.assertEqual(formatted_message['patches'][0]['name'], 'python-samba0')
        self.assertEqual(formatted_message['patches'][0]['patchId'], expected_patch_id)

    def test_installation_packages_map(self):
        patch_id_other = 'python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04'
        expected_value_other = {'version': '2:4.4.5+dfsg-2ubuntu5.4', 'classifications': ['Other'], 'name': 'python-samba0',
                          'patchId': 'python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04', 'patchInstallationState': 'Installed'}

        patch_id_critical = 'python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04'
        expected_value_critical = {'version': '2:4.4.5+dfsg-2ubuntu5.4', 'classifications': ['Critical'], 'name': 'python-samba0',
                          'patchId': 'python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04', 'patchInstallationState': 'Installed'}
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count_for_test = 50
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_test)

        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, 'Installed', 'Other')
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]

        formatted_message = json.loads(substatus_file_data['formattedMessage']['message'])
        self.assertEqual(len(formatted_message['patches']), patch_count_for_test)
        self.assertEqual(formatted_message['patches'][0]['classifications'], ['Other'])
        self.assertEqual(formatted_message['patches'][0]['patchId'], patch_id_other)
        self.assertEqual(formatted_message['patches'][0], expected_value_other)
        self.assertEqual(formatted_message['patches'][0]['name'], 'python-samba0')

        # Update the classification from Other to Critical
        self.runtime.status_handler.set_package_install_status_classification(test_packages, test_package_versions, 'Critical')
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]

        formatted_message = json.loads(substatus_file_data['formattedMessage']['message'])
        self.assertEqual(len(formatted_message['patches']), patch_count_for_test)
        self.assertEqual(formatted_message['patches'][0]['classifications'], ['Critical'])
        self.assertEqual(formatted_message['patches'][0]['patchId'], patch_id_critical)
        self.assertEqual(formatted_message['patches'][0], expected_value_critical)
        self.assertEqual(formatted_message['patches'][0]['name'], 'python-samba0')

    def test_load_status_and_set_package_install_status(self):
        patch_count_for_test = 5
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_test)
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
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), patch_count_for_test)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["name"], "python-samba0")
        self.assertTrue('Critical' in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["name"], "python-samba1")
        self.assertEqual('Critical', str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["classifications"][0]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["name"], "python-samba2")
        self.assertEqual('python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04', str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue('Critical' in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["classifications"]))

        # Test for set_package_install_status_classification
        self.runtime.status_handler.set_package_install_status_classification(test_packages, test_package_versions, "Critical")
        with self.runtime.env_layer.file_system.open(self.runtime.status_handler.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), patch_count_for_test)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["name"], "python-samba0")
        self.assertTrue('Critical' in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["name"], "python-samba1")
        self.assertEqual('Critical', str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["classifications"][0]))
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["name"], "python-samba2")
        self.assertEqual('python-samba0_2:4.4.5+dfsg-2ubuntu5.4_Ubuntu_16.04',
            str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue('Critical' in str(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][2]["classifications"]))
        self.runtime.env_layer.file_system.delete_files_from_dir(self.runtime.status_handler.status_file_path, '*.complete.status')

    def test_latest_complete_status_file(self):
        """ Create dummy files in status folder and check if the complete_status_file_path is the latest file and delete those dummy files """
        file_path = self.runtime.execution_config.status_folder
        example_file1 = os.path.join(file_path, '101.complete.status')
        example_file2 = os.path.join(file_path, '102.complete.status')
        example_file3 = os.path.join(file_path, '103.complete.status')
        example_file4 = os.path.join(file_path, '104.complete.status')
        example_file5 = os.path.join(file_path, '105.complete.status')
        example_file15 = os.path.join(file_path, '115.complete.status')

        for i in range(1, 16):
            with open(os.path.join(file_path, str(i + 100) + '.complete.status'), 'w') as f:
                f.write("test" + str(i))

        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)
        packages, package_versions = self.runtime.package_manager.get_all_updates()
        self.runtime.status_handler.set_package_assessment_status(packages, package_versions)
        self.runtime.status_handler.load_status_file_components(initial_load=True)

        # remove 5 oldest
        self.assertFalse(os.path.isfile(example_file1))
        self.assertFalse(os.path.isfile(example_file2))
        self.assertFalse(os.path.isfile(example_file3))
        self.assertFalse(os.path.isfile(example_file4))
        self.assertFalse(os.path.isfile(example_file5))
        self.assertTrue(os.path.isfile(example_file15))
        self.assertTrue(os.path.isfile(self.runtime.execution_config.complete_status_file_path))
        self.runtime.env_layer.file_system.delete_files_from_dir(file_path, '*.complete.status')

    def test_write_truncated_status_file_under_capacity(self):
        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count_for_test = 500
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_test)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Test Complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertEqual(substatus_file_data[0]["status"]["operation"], Constants.ASSESSMENT)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_SUCCESS.lower())
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), patch_count_for_test)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)

        # Test Truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)
        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertNotEqual(substatus_file_data["status"], Constants.STATUS_WARNING.lower())
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), patch_count_for_test)
        status_file_patches = json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]
        self.assertNotEqual(status_file_patches[-1]['patchId'], "Truncated_patch_list_id")
        self.assertTrue('Truncated_patch_list_id' not in status_file_patches[-1]['name'])
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], 0)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)
        self.assertFalse("review this log file on the machine" in json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["message"])
        self.assertEqual(len(self.runtime.status_handler._StatusHandler__assessment_packages_removed), 0)

    def test_write_truncated_status_file_assessment_over_capacity(self):
        """ Test truncation logic will apply to assessment when it is over the size limit """
        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count_for_test = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_test)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions)
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Test Complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.INTERNAL_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertEqual(substatus_file_data[0]["status"]["operation"], Constants.ASSESSMENT)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_SUCCESS.lower())
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), patch_count_for_test)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)

        # Test Truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)
        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)

        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_WARNING.lower())
        message_patches = json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]
        self.assertEqual(message_patches[-1]['patchId'], "Truncated_patch_list_id")
        self.assertTrue("additional updates of classification" in message_patches[-1]['name'][0])
        self.assertTrue(len(message_patches) < patch_count_for_test + 1)   # 1 tombstone
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], Constants.PatchOperationTopLevelErrorCode.WARNING)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.TRUNCATION)
        self.assertTrue("review this log file on the machine" in json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["message"])

    def test_write_truncated_status_file_assessment_over_capacity_with_quotes(self):
        """ Test truncation logic will apply to assessment, the 2 times json.dumps() will escape " adding \, adding 1 additional byte check if total byte size over the size limit """
        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count_for_test = 100000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_test)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions, "Critical")
        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

        # Test Complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertEqual(substatus_file_data[0]["status"]["operation"], Constants.ASSESSMENT)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_SUCCESS.lower())
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), patch_count_for_test)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)

        # Test Truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)
        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_WARNING.lower())
        message_patches = json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]
        self.assertTrue(len(message_patches) < patch_count_for_test + 1)     # 1 tombstone
        self.assertEqual(message_patches[-1]['patchId'], "Truncated_patch_list_id")
        self.assertTrue("additional updates of classification" in message_patches[-1]['name'][0])
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], Constants.PatchOperationTopLevelErrorCode.WARNING)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.TRUNCATION)
        self.assertTrue("review this log file on the machine" in json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["message"])

    def test_write_truncated_status_file_assessment_over_capacity_with_error(self):
        """ Test truncation logic will apply to assessment with errors over the size limit """
        self.runtime.execution_config.operation = Constants.ASSESSMENT
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)

        patch_count_for_test = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_test)
        self.runtime.status_handler.set_package_assessment_status(test_packages, test_package_versions, "Security")

        # Test Complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)

        self.runtime.status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)

        # Adding multiple exceptions
        self.runtime.status_handler.add_error_to_status("exception1", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception2", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception3", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception4", Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
        self.runtime.status_handler.add_error_to_status("exception5", Constants.PatchOperationErrorCodes.OPERATION_FAILED)

        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data["status"] != Constants.STATUS_SUCCESS.lower())
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), patch_count_for_test)
        self.assertNotEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"], None)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], Constants.PatchOperationTopLevelErrorCode.ERROR)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 5)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.OPERATION_FAILED)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][1]["code"], Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["message"], "exception5")

        # Test Truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_ERROR.lower())
        message_patches = json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]
        self.assertEqual(message_patches[-1]['patchId'], "Truncated_patch_list_id")
        self.assertTrue("additional updates of classification" in message_patches[-1]['name'][0])
        self.assertTrue(len(message_patches) < patch_count_for_test + 1)        # 1 tombstone
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], Constants.PatchOperationTopLevelErrorCode.ERROR)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 5)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.TRUNCATION)
        self.assertTrue('6 error/s reported. The latest 5 error/s are shared in detail.' in json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["message"])

    def test_write_truncated_status_file_installation_over_capacity(self):
        """ Test truncation logic will apply to installation over the size limit """
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count_for_test = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_test)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Test Complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertEqual(substatus_file_data[0]["status"]["operation"], Constants.INSTALLATION)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_SUCCESS.lower())
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), patch_count_for_test)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)

        # Test Truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_WARNING.lower())
        message_patches = json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]
        self.assertEqual(message_patches[-1]['patchId'], "Truncated_patch_list_id")
        self.assertEqual(message_patches[-1]['name'], "Truncated_patch_list")
        self.assertTrue(len(message_patches) < patch_count_for_test + 1)        # 1 tombstone
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], Constants.PatchOperationTopLevelErrorCode.WARNING)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.TRUNCATION)
        self.assertTrue('1 error/s reported. The latest 1 error/s are shared in detail.' in json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["message"])

    def test_write_truncated_status_file_installation_low_pri_over_capacity(self):
        """ Test truncation logic will apply to installation over the size limit """
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count_for_test = random.randint(780, 1100)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_test)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.PENDING)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Test Complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertEqual(substatus_file_data[0]["status"]["operation"], Constants.INSTALLATION)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_SUCCESS.lower())
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), patch_count_for_test)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)

        # Test Truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_WARNING.lower())
        message_patches = json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]
        self.assertEqual(message_patches[-1]['patchId'], "Truncated_patch_list_id")
        self.assertEqual(message_patches[-1]['name'], "Truncated_patch_list")
        self.assertEqual(message_patches[-1]['patchInstallationState'], 'NotSelected')
        self.assertTrue(len(message_patches) < patch_count_for_test + 1)       # 1 tombstone
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], Constants.PatchOperationTopLevelErrorCode.WARNING)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.TRUNCATION)
        self.assertTrue('1 error/s reported. The latest 1 error/s are shared in detail.' in json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["message"])

    def test_write_truncated_status_file_installation_over_capacity_with_quotes(self):
        """ Test truncation logic will apply to installation, the 2 times json.dumps() will escape " adding \, adding 1 additional byte check if total byte size over the size limit """
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count_for_test = 100000
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_test)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)
        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Test Complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        self.assertEqual(substatus_file_data[0]["status"]["operation"], Constants.INSTALLATION)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_SUCCESS.lower())
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), patch_count_for_test)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)

        # Test Truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_WARNING.lower())
        message_patches = json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]
        self.assertEqual(message_patches[-1]['patchId'], "Truncated_patch_list_id")
        self.assertEqual(message_patches[-1]['name'], "Truncated_patch_list")
        self.assertEqual(message_patches[-1]['patchInstallationState'], 'NotSelected')
        self.assertTrue(len(message_patches) < patch_count_for_test + 1)       # 1 tombstone
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], Constants.PatchOperationTopLevelErrorCode.WARNING)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.TRUNCATION)
        self.assertTrue('1 error/s reported. The latest 1 error/s are shared in detail.' in json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["message"])

    def test_write_truncated_status_file_installation_over_capacity_with_error(self):
        """ Test truncation logic will apply to installation with errors over the size limit """
        self.runtime.execution_config.operation = Constants.INSTALLATION
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)

        patch_count_for_test = random.randint(780, 1000)
        test_packages, test_package_versions = self.__set_up_packages_func(patch_count_for_test)
        self.runtime.status_handler.set_package_install_status(test_packages, test_package_versions, Constants.INSTALLED)

        # Test Complete status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][0]
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 0)

        self.runtime.status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)

        # Adding multiple exceptions
        self.runtime.status_handler.add_error_to_status("exception0", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception1", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception2", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception3", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        self.runtime.status_handler.add_error_to_status("exception4", Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
        self.runtime.status_handler.add_error_to_status("exception5", Constants.PatchOperationErrorCodes.OPERATION_FAILED)

        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.complete_status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) > Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data["status"] == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]), patch_count_for_test)
        self.assertNotEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"], None)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], 1)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 5)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.OPERATION_FAILED)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][1]["code"], Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["message"], "exception5")

        # Test Truncated status file
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)

        self.assertTrue(len(json.dumps(substatus_file_data)) < Constants.StatusTruncationConfig.AGENT_STATUS_FILE_SIZE_LIMIT_IN_BYTES)
        substatus_file_data = substatus_file_data[0]["status"]["substatus"][0]
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(substatus_file_data["status"], Constants.STATUS_ERROR.lower())
        message_patches = json.loads(substatus_file_data["formattedMessage"]["message"])["patches"]
        self.assertEqual(message_patches[-1]['patchId'], "Truncated_patch_list_id")
        self.assertEqual(message_patches[-1]['name'], "Truncated_patch_list")
        self.assertTrue(len(message_patches) < patch_count_for_test + 1)        # 1 tombstone
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], Constants.PatchOperationTopLevelErrorCode.ERROR)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 5)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.TRUNCATION)
        # 1 truncation error
        self.assertTrue("7 error/s reported. The latest 5 error/s are shared in detail" in json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["message"])

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
