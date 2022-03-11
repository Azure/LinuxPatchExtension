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
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["name"], "samba-common-bin")
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["patches"][1]["patchInstallationState"], Constants.INSTALLED)

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

        # Adding a long error that will not be truncated (special case)
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        long_error_message = "{0} [Diagnostic-code: 2.2.49.2/2.6.0.2/0/1/0]".format(Constants.TELEMETRY_AT_AGENT_NOT_COMPATIBLE_ERROR_MSG)
        self.assertTrue(len(long_error_message) > Constants.STATUS_ERROR_MSG_SIZE_LIMIT_IN_CHARACTERS)
        self.runtime.status_handler.add_error_to_status(long_error_message, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        substatus_file_data = []
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][1]
        self.assertNotEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"], None)
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["code"], 1)
        self.assertEqual(len(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]), 2)
        message = json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"][0]["message"]
        self.assertTrue(len(message) > Constants.STATUS_ERROR_MSG_SIZE_LIMIT_IN_CHARACTERS)
        self.assertEqual(message, long_error_message)

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
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertTrue(len(substatus_file_data) == 1)

        # for autopatching request, with reboot not started
        self.runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.COMPLETED)
        self.runtime.execution_config.maintenance_run_id = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        status_handler = StatusHandler(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.vm_cloud_type)
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
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


if __name__ == '__main__':
    unittest.main()
