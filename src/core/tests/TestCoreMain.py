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
import re
import unittest
from core.src.CoreMain import CoreMain
from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestCoreMain(unittest.TestCase):
    def setUp(self):
        # Had to move runtime init and stop to individual test functions, since every test uses a different maintenance_run_id which has to be set before runtime init
        # self.argument_composer = ArgumentComposer().get_composed_arguments()
        # self.runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.ZYPPER)
        # self.container = self.runtime.container
        pass

    def tearDown(self):
        # self.runtime.stop()
        pass

    def test_operation_fail_for_non_autopatching_request(self):
        # Test for non auto patching request
        argument_composer = ArgumentComposer()
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('FailInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEquals(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"] == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"] == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"]), 1)
        runtime.stop()

    def test_operation_fail_for_autopatching_request(self):
        argument_composer = ArgumentComposer()
        argument_composer.maintenance_run_id = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('FailInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEquals(len(substatus_file_data), 3)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"] == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"] == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"] == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertTrue(substatus_file_data_patch_metadata_summary["patchVersion"], Constants.PATCH_VERSION_UNKNOWN)
        self.assertFalse(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        runtime.stop()

    def test_operation_success_for_non_autopatching_request(self):
        argument_composer = ArgumentComposer()
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEquals(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"] == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"] == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

    def test_operation_success_for_autopatching_request(self):
        # test with valid datetime string for maintenance run id
        argument_composer = ArgumentComposer()
        maintenance_run_id = "9/28/2020 02:00:00 PM +00:00"
        argument_composer.maintenance_run_id = str(maintenance_run_id)
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEquals(len(substatus_file_data), 3)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"] == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"] == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"] == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], "2020.09.28")
        self.assertTrue(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        runtime.stop()

    def test_operation_success_for_autopatching_request_with_security_classification(self):
        # test with valid datetime string for maintenance run id
        argument_composer = ArgumentComposer()
        maintenance_run_id = "9/28/2020 02:00:00 PM +00:00"
        classifications_to_include = ["Security", "Critical"]
        argument_composer.maintenance_run_id = str(maintenance_run_id)
        argument_composer.classifications_to_include = classifications_to_include
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type("SuccessInstallPath")
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEquals(len(substatus_file_data), 3)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"] == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"] == Constants.STATUS_SUCCESS.lower())
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["name"], "python-samba")
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["name"], "samba-common-bin")
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["name"], "samba-libs")
        self.assertTrue("python-samba_2:4.4.5+dfsg-2ubuntu5.4" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["classifications"]))
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"] == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], "2020.09.28")
        self.assertTrue(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        runtime.stop()

    def test_invalid_maintenance_run_id(self):
        # test with empty string for maintenence run id
        argument_composer = ArgumentComposer()
        maintenance_run_id = ""
        argument_composer.maintenance_run_id = maintenance_run_id
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEquals(len(substatus_file_data), 3)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"] == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"] == Constants.STATUS_ERROR.lower())
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"] == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], Constants.PATCH_VERSION_UNKNOWN)
        self.assertFalse(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        runtime.stop()

        # todo: This will become a valid success operation run once the temp fix for maintenanceRunId is removed
        # test with a random string for maintenance run id
        argument_composer = ArgumentComposer()
        maintenance_run_id = "test"
        argument_composer.maintenance_run_id = maintenance_run_id
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEquals(len(substatus_file_data), 3)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"] == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"] == Constants.STATUS_ERROR.lower())
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"] == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], Constants.PATCH_VERSION_UNKNOWN)
        self.assertFalse(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        runtime.stop()

    def test_assessment_operation_success(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('HappyPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEquals(len(substatus_file_data), 1)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"] == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

    def test_assessment_operation_fail(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('ExceptionPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEquals(len(substatus_file_data), 1)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"] == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"]), 2)
        runtime.stop()

    def test_assessment_operation_fail_due_to_no_telemetry(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        argument_composer.events_folder = None
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('HappyPath')
        CoreMain(argument_composer.get_composed_arguments())

        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEquals(len(substatus_file_data), 1)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"] == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertTrue("The minimum Azure Linux Agent version prerequisite for Linux patching was not met" in json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        runtime.stop()

    def test_installation_operation_fail_due_to_no_telemetry(self):
        # testing on auto patching request
        argument_composer = ArgumentComposer()
        argument_composer.maintenance_run_id = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        argument_composer.events_folder = None
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEquals(len(substatus_file_data), 3)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"] == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertTrue("The minimum Azure Linux Agent version prerequisite for Linux patching was not met" in json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"] == Constants.STATUS_ERROR.lower())
        runtime.stop()

    def test_operation_success_for_configure_patching_request(self):
        #todo: update test with a proper patch setting file
        pass
        # argument_composer = ArgumentComposer()
        # argument_composer.operation = Constants.CONFIGURE_PATCHING
        # argument_composer.patch_mode = Constants.AUTOMATIC_BY_PLATFORM
        # runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # runtime.set_legacy_test_type('HappyPath')
        # CoreMain(argument_composer.get_composed_arguments())
        #
        # # check telemetry events
        # self.__check_telemetry_events(runtime)
        #
        # # check status file
        # with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
        #     substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        # self.assertEquals(len(substatus_file_data), 1)
        # self.assertTrue(substatus_file_data[0]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        # self.assertTrue(substatus_file_data[0]["status"] == Constants.STATUS_SUCCESS.lower())
        # runtime.stop()

    def test_operation_fail_for_configure_patching_request(self):
        # todo
        pass

    def __check_telemetry_events(self, runtime):
        all_events = os.listdir(runtime.telemetry_writer.events_folder_path)
        self.assertTrue(len(all_events) > 0)
        latest_event_file = [pos_json for pos_json in os.listdir(runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertTrue('ExtensionCoreLog' in events[0]['TaskName'])
            f.close()


if __name__ == '__main__':
    unittest.main()
