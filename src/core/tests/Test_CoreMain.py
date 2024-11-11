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
import glob
import json
import os
import re
import shutil
import unittest
import uuid

from core.src.CoreMain import CoreMain
from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.LegacyEnvLayerExtensions import LegacyEnvLayerExtensions
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

    def mock_linux_distribution_to_return_centos(self):
        return ['CentOS Linux', '7.9.2009', 'Core']

    def mock_linux_distribution_to_return_redhat(self):
        return ['Red Hat Enterprise Linux Server', '7.5', 'Maipo']

    def mock_os_remove(self, file_to_remove):
        raise Exception("File could not be deleted")

    def mock_os_path_exists(self, patch_to_validate):
        return False

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
        self.assertEqual(len(substatus_file_data), 3)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertTrue(substatus_file_data[2]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
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
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertTrue(substatus_file_data_patch_metadata_summary["patchVersion"], Constants.PATCH_VERSION_UNKNOWN)
        self.assertFalse(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
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
        self.assertEqual(len(substatus_file_data), 3)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[2]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

    def test_operation_success_for_autopatching_request(self):
        # test with valid datetime string for maintenance run id
        argument_composer = ArgumentComposer()
        maintenance_run_id = "9/30/2020 02:00:00 PM +00:00"
        argument_composer.maintenance_run_id = str(maintenance_run_id)
        argument_composer.health_store_id = str("2020.09.28")
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        Constants.MAX_FILE_OPERATION_RETRY_COUNT = 2    # to retain retry coverage in at least one test
        Constants.MAX_IMDS_CONNECTION_RETRY_COUNT = 2   # to retain retry coverage in at least one test
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], "2020.09.28")
        self.assertTrue(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

    def test_operation_success_for_autopatching_request_with_security_classification(self):
        # test with valid datetime string for maintenance run id
        argument_composer = ArgumentComposer()
        maintenance_run_id = "9/30/2020 02:00:00 PM +00:00"
        classifications_to_include = ["Security", "Critical"]
        argument_composer.maintenance_run_id = str(maintenance_run_id)
        argument_composer.health_store_id = str("2020.09.28")
        argument_composer.classifications_to_include = classifications_to_include
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type("SuccessInstallPath")
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["name"], "python-samba")
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["name"], "samba-common-bin")
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["name"], "samba-libs")
        self.assertTrue("python-samba_2:4.4.5+dfsg-2ubuntu5.4" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["classifications"]))
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], "2020.09.28")
        self.assertTrue(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

    def test_health_store_id_reporting(self):
        # test with empty string for healthstoreid
        argument_composer = ArgumentComposer()
        health_store_id = "pub_offer_sku_wrong_123"
        argument_composer.health_store_id = health_store_id
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())       # "invalid" maintenance ids are okay in the new contract
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], health_store_id)
        self.assertTrue(runtime.execution_config.max_patch_publish_date is str())
        self.assertTrue(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

        # test with healthstoreid
        argument_composer = ArgumentComposer()
        health_store_id = "publ_off_sku_2024.04.01"
        argument_composer.health_store_id = health_store_id
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], health_store_id)
        self.assertEqual(runtime.execution_config.max_patch_publish_date, "20240401T000000Z")
        self.assertTrue(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
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
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
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
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"]), 3)
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

    def test_assessment_operation_fail_due_to_no_telemetry(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        argument_composer.events_folder = None
        composed_arguments = argument_composer.get_composed_arguments(dict(telemetrySupported=False))
        runtime = RuntimeCompositor(composed_arguments, True, Constants.ZYPPER)
        runtime.set_legacy_test_type('HappyPath')
        CoreMain(composed_arguments)

        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertTrue(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertTrue(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        runtime.stop()

    def test_installation_operation_fail_due_to_telemetry_unsupported_no_events_folder(self):
        # events_folder is None
        argument_composer = ArgumentComposer()
        argument_composer.maintenance_run_id = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        argument_composer.events_folder = None
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertTrue(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertFalse(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        self.assertTrue("Installation failed due to assessment failure. Please refer the error details in assessment substatus" in json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[3]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertTrue(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[3]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        runtime.stop()

    def test_installation_operation_fail_due_to_no_telemetry(self):
        # telemetry not supported
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.INSTALLATION
        argument_composer.maintenance_run_id = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(env_settings={"telemetrySupported": False}), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('SuccessInstallPath')
        # Skip assessment because it will always raise an exception at raise_if_telemetry_unsupported
        # and will never raise an exception in installation's raise_if_telemetry_unsupported
        runtime.patch_assessor.start_assessment = lambda: ()
        CoreMain(argument_composer.get_composed_arguments())

        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"]), 2)
        self.assertFalse(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        self.assertTrue("Installation failed due to assessment failure. Please refer the error details in assessment substatus" in json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[3]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertTrue(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[3]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        runtime.stop()

    def test_assessment_operation_fail_on_arc_due_to_no_telemetry(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        argument_composer.events_folder = None
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER, Constants.VMCloudType.ARC)
        runtime.set_legacy_test_type('HappyPath')
        CoreMain(argument_composer.get_composed_arguments())

        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertTrue(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertTrue(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        runtime.stop()

    def test_installation_operation_fail_on_arc_due_to_no_telemetry(self):
        # testing on auto patching request
        argument_composer = ArgumentComposer()
        argument_composer.maintenance_run_id = str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        argument_composer.events_folder = None
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER,Constants.VMCloudType.ARC)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertTrue(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertFalse(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        self.assertTrue("Installation failed due to assessment failure. Please refer the error details in assessment substatus" in json.loads(substatus_file_data[1]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertEqual(len(json.loads(substatus_file_data[3]["formattedMessage"]["message"])["errors"]["details"]), 1)
        self.assertTrue(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[3]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
        runtime.stop()

    def test_install_all_packages_for_centos_autopatching(self):
        """Unit test for auto patching request on CentOS, should install all patches irrespective of classification"""

        backup_envlayer_platform_linux_distribution = LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution
        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = self.mock_linux_distribution_to_return_centos

        argument_composer = ArgumentComposer()
        maintenance_run_id = "9/28/2020 02:00:00 PM +00:00"
        classifications_to_include = ["Security", "Critical"]
        argument_composer.maintenance_run_id = str(maintenance_run_id)
        argument_composer.health_store_id = str("pub_off_sku_2020.09.29")
        argument_composer.classifications_to_include = classifications_to_include
        argument_composer.reboot_setting = 'Always'
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        runtime.set_legacy_test_type("HappyPath")
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["installedPatchCount"] == 5)
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["name"], "selinux-policy.noarch")
        self.assertTrue("Other" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["classifications"]))
        self.assertTrue("Installed" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["patchInstallationState"])
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["name"], "selinux-policy-targeted.noarch")
        self.assertTrue("Other" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["classifications"]))
        self.assertTrue("Installed" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["patchInstallationState"])
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["name"], "libgcc.i686")
        self.assertTrue("libgcc.i686_4.8.5-28.el7_CentOS Linux_7.9.2009" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertTrue("Installed" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["patchInstallationState"])
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], "pub_off_sku_2020.09.29")
        self.assertTrue(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = backup_envlayer_platform_linux_distribution

    def test_install_all_packages_for_centos_autopatching_as_warning_with_never_reboot(self):
        """Unit test for auto patching request on CentOS, should install all patches irrespective of classification,
            installation status is set to warning when reboot_setting is never_reboot
        """

        backup_envlayer_platform_linux_distribution = LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution
        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = self.mock_linux_distribution_to_return_centos

        argument_composer = ArgumentComposer()
        maintenance_run_id = "9/30/2020 02:00:00 PM +00:00"
        classifications_to_include = ["Security", "Critical"]
        argument_composer.maintenance_run_id = str(maintenance_run_id)
        argument_composer.health_store_id = str("2020.09.28")
        argument_composer.classifications_to_include = classifications_to_include
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        runtime.set_legacy_test_type("HappyPath")
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_WARNING.lower())
        self.assertTrue(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["installedPatchCount"] == 5)
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["name"], "selinux-policy.noarch")
        self.assertTrue("Other" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["classifications"]))
        self.assertTrue("Installed" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["patchInstallationState"])
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["name"], "selinux-policy-targeted.noarch")
        self.assertTrue("Other" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["classifications"]))
        self.assertTrue("Installed" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["patchInstallationState"])
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["name"], "libgcc.i686")
        self.assertTrue("libgcc.i686_4.8.5-28.el7_CentOS Linux_7.9.2009" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertTrue("Installed" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["patchInstallationState"])
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], "2020.09.28")
        self.assertTrue(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = backup_envlayer_platform_linux_distribution

    def test_install_only_critical_and_security_packages_for_redhat_autopatching(self):
        """Unit test for auto patching request on Redhat, should install only critical and security patches"""

        backup_envlayer_platform_linux_distribution = LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution
        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = self.mock_linux_distribution_to_return_redhat

        argument_composer = ArgumentComposer()
        maintenance_run_id = "9/30/2020 02:00:00 PM +00:00"
        classifications_to_include = ["Security", "Critical"]
        argument_composer.maintenance_run_id = str(maintenance_run_id)
        argument_composer.health_store_id = str("2020.09.28")
        argument_composer.classifications_to_include = classifications_to_include
        argument_composer.reboot_setting = 'Always'
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        runtime.set_legacy_test_type("HappyPath")
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["installedPatchCount"] == 1)
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["name"], "selinux-policy.noarch")
        self.assertTrue("Other" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["classifications"]))
        self.assertTrue("NotSelected" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["patchInstallationState"])
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["name"], "selinux-policy-targeted.noarch")
        self.assertTrue("Other" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["classifications"]))
        self.assertTrue("NotSelected" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["patchInstallationState"])
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][3]["name"], "tar.x86_64")
        self.assertTrue("Other" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][3]["classifications"]))
        self.assertTrue("NotSelected" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][3]["patchInstallationState"])
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][4]["name"], "tcpdump.x86_64")
        self.assertTrue("Other" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][4]["classifications"]))
        self.assertTrue("NotSelected" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][4]["patchInstallationState"])
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["name"], "libgcc.i686")
        self.assertTrue("libgcc.i686_4.8.5-28.el7_Red Hat Enterprise Linux Server_7.5" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertTrue("Installed" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["patchInstallationState"])
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], "2020.09.28")
        self.assertTrue(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = backup_envlayer_platform_linux_distribution

    def test_install_only_critical_and_security_packages_for_redhat_autopatching_warning_with_never_reboot(self):
        """Unit test for auto patching request on Redhat, should install only critical and security patches,
            installation status is set to warning when reboot_setting is never_reboot
        """
        backup_envlayer_platform_linux_distribution = LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution
        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = self.mock_linux_distribution_to_return_redhat

        argument_composer = ArgumentComposer()
        maintenance_run_id = "9/30/2020 02:00:00 PM +00:00"
        classifications_to_include = ["Security", "Critical"]
        argument_composer.maintenance_run_id = str(maintenance_run_id)
        argument_composer.health_store_id = str("2020.09.28")
        argument_composer.classifications_to_include = classifications_to_include
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        runtime.set_legacy_test_type("HappyPath")
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_WARNING.lower())
        self.assertTrue(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["installedPatchCount"] == 1)
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["name"], "selinux-policy.noarch")
        self.assertTrue("Other" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["classifications"]))
        self.assertTrue("NotSelected" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["patchInstallationState"])
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["name"], "selinux-policy-targeted.noarch")
        self.assertTrue("Other" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["classifications"]))
        self.assertTrue("NotSelected" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["patchInstallationState"])
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][3]["name"], "tar.x86_64")
        self.assertTrue("Other" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][3]["classifications"]))
        self.assertTrue("NotSelected" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][3]["patchInstallationState"])
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][4]["name"], "tcpdump.x86_64")
        self.assertTrue("Other" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][4]["classifications"]))
        self.assertTrue("NotSelected" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][4]["patchInstallationState"])
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["name"], "libgcc.i686")
        self.assertTrue("libgcc.i686_4.8.5-28.el7_Red Hat Enterprise Linux Server_7.5" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertTrue("Installed" == json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["patchInstallationState"])
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], "2020.09.28")
        self.assertTrue(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = backup_envlayer_platform_linux_distribution

    # test with both assessment mode and patch mode set in configure patching or install patches or assess patches or auto assessment
    def test_auto_assessment_success_with_configure_patching_in_prev_operation_on_same_sequence(self):
        """Unit test for auto assessment request with configure patching completed on the sequence before. Result: should retain prev substatus and update only PatchAssessmentSummary"""
        # operation #1: ConfigurePatching
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        argument_composer.assessment_mode = Constants.AssessmentModes.AUTOMATIC_BY_PLATFORM
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type("SuccessInstallPath")
        CoreMain(argument_composer.get_composed_arguments())
        # check telemetry events
        self.__check_telemetry_events(runtime)
        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            status_file_data = json.load(file_handle)[0]["status"]
        self.assertTrue(status_file_data["operation"] == Constants.CONFIGURE_PATCHING)
        substatus_file_data = status_file_data["substatus"]
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check status file for configure patching auto updates state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)  # auto OS updates are disabled in RuntimeCompositor
        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.ENABLED)  # auto assessment is enabled

        # operation #2: Auto Assessment
        argument_composer.activity_id = str(uuid.uuid4())
        argument_composer.included_classifications_list = self.included_package_name_mask_list = self.excluded_package_name_mask_list = []
        argument_composer.maintenance_run_id = None
        argument_composer.start_time = runtime.env_layer.datetime.standard_datetime_to_utc(datetime.datetime.utcnow())
        argument_composer.duration = Constants.AUTO_ASSESSMENT_MAXIMUM_DURATION
        argument_composer.reboot_setting = Constants.REBOOT_NEVER
        argument_composer.patch_mode = None
        argument_composer.exec_auto_assess_only = True
        runtime.execution_config.exec_auto_assess_only = True
        CoreMain(argument_composer.get_composed_arguments())
        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            status_file_data = json.load(file_handle)[0]["status"]
        # verifying the original operation name is preserved
        self.assertTrue(status_file_data["operation"] == Constants.CONFIGURE_PATCHING)
        substatus_file_data = status_file_data["substatus"]
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check started by set to 'Platform'
        self.assertTrue(json.loads(substatus_file_data[0]["formattedMessage"]["message"])['startedBy'], Constants.PatchAssessmentSummaryStartedBy.PLATFORM)
        # verifying the older operation summary is preserved
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)  # auto OS updates are disabled in RuntimeCompositor
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.ENABLED)  # auto assessment is enabled

        runtime.stop()

    # test with both assessment mode and patch mode set in configure patching or install patches or assess patches or auto assessment
    def test_auto_assessment_success_on_arc_with_configure_patching_in_prev_operation_on_same_sequence(self):
        """Unit test for auto assessment request with configure patching completed on the sequence before. Result: should retain prev substatus and update only PatchAssessmentSummary"""
        # operation #1: ConfigurePatching
        # Here it should skip agent compatibility check as operation is configure patching [ not assessment or installation]
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        argument_composer.assessment_mode = Constants.AssessmentModes.AUTOMATIC_BY_PLATFORM
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT, Constants.VMCloudType.ARC)
        runtime.set_legacy_test_type("SuccessInstallPath")
        CoreMain(argument_composer.get_composed_arguments())
        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            status_file_data = json.load(file_handle)[0]["status"]
        self.assertTrue(status_file_data["operation"] == Constants.CONFIGURE_PATCHING)
        substatus_file_data = status_file_data["substatus"]
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check status file for configure patching auto updates state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)  # auto OS updates are disabled in RuntimeCompositor
        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.ENABLED)  # auto assessment is enabled

        # operation #2: Auto Assessment
        argument_composer.activity_id = str(uuid.uuid4())
        argument_composer.included_classifications_list = self.included_package_name_mask_list = self.excluded_package_name_mask_list = []
        argument_composer.maintenance_run_id = None
        argument_composer.start_time = runtime.env_layer.datetime.standard_datetime_to_utc(datetime.datetime.utcnow())
        argument_composer.duration = Constants.AUTO_ASSESSMENT_MAXIMUM_DURATION
        argument_composer.reboot_setting = Constants.REBOOT_NEVER
        argument_composer.patch_mode = None
        argument_composer.exec_auto_assess_only = True
        runtime.execution_config.exec_auto_assess_only = True
        CoreMain(argument_composer.get_composed_arguments())
        # check telemetry events
        self.__check_telemetry_events(runtime)
        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            status_file_data = json.load(file_handle)[0]["status"]
        # verifying the original operation name is preserved
        self.assertTrue(status_file_data["operation"] == Constants.CONFIGURE_PATCHING)
        substatus_file_data = status_file_data["substatus"]
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check started by set to 'Platform'
        self.assertTrue(json.loads(substatus_file_data[0]["formattedMessage"]["message"])['startedBy'], Constants.PatchAssessmentSummaryStartedBy.PLATFORM)
        # verifying the older operation summary is preserved
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)  # auto OS updates are disabled in RuntimeCompositor
        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.ENABLED)  # auto assessment is enabled

        runtime.stop()

    def test_auto_assessment_success_with_assessment_in_prev_operation_on_same_sequence(self):
        """Unit test for auto assessment request with assessment completed on the sequence before. Result: should contain PatchAssessmentSummary with an updated timestamp and ConfigurePatchingSummary from the first Assessment operation"""
        # operation #1: Assessment
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type("SuccessInstallPath")
        CoreMain(argument_composer.get_composed_arguments())
        # check telemetry events
        self.__check_telemetry_events(runtime)
        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            status_file_data = json.load(file_handle)[0]["status"]
        self.assertTrue(status_file_data["operation"] == Constants.ASSESSMENT)
        substatus_file_data = status_file_data["substatus"]
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check started by set to 'User'
        self.assertTrue(json.loads(substatus_file_data[0]["formattedMessage"]["message"])['startedBy'], Constants.PatchAssessmentSummaryStartedBy.USER)
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check status file for configure patching auto updates state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)  # auto OS updates are disabled in RuntimeCompositor
        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.UNKNOWN)  # Configure patching for auto assessment did not execute since assessmentMode was not in input

        # operation #2: Auto Assessment
        argument_composer.activity_id = str(uuid.uuid4())
        argument_composer.included_classifications_list = self.included_package_name_mask_list = self.excluded_package_name_mask_list = []
        argument_composer.maintenance_run_id = None
        argument_composer.start_time = runtime.env_layer.datetime.standard_datetime_to_utc(datetime.datetime.utcnow())
        argument_composer.duration = Constants.AUTO_ASSESSMENT_MAXIMUM_DURATION
        argument_composer.reboot_setting = Constants.REBOOT_NEVER
        argument_composer.patch_mode = None
        argument_composer.exec_auto_assess_only = True
        runtime.execution_config.exec_auto_assess_only = True
        CoreMain(argument_composer.get_composed_arguments())
        # check telemetry events
        self.__check_telemetry_events(runtime)
        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            status_file_data = json.load(file_handle)[0]["status"]

        # verifying the original operation name is preserved
        self.assertTrue(status_file_data["operation"] == Constants.ASSESSMENT)
        substatus_file_data = status_file_data["substatus"]
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check started by set to 'Platform'
        self.assertTrue(json.loads(substatus_file_data[0]["formattedMessage"]["message"])['startedBy'], Constants.PatchAssessmentSummaryStartedBy.PLATFORM)
        # verifying the older operation summary is preserved
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check status file for configure patching auto updates state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)  # auto OS updates are disabled in RuntimeCompositor
        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.UNKNOWN)  # Configure patching for auto assessment did not execute since assessmentMode was not in input

        runtime.stop()

    def test_auto_assessment_success_with_installation_in_prev_operation_on_same_sequence(self):
        """Unit test for auto assessment request with installation (Auto Patching) completed on the sequence before.
        Result: should contain PatchAssessmentSummary with an updated timestamp after auto assessment, and retain PatchInstallationSummary, ConfigurePatchingSummary and PatchMetadatForHealthStoreSummary from the installation(Auto Patching) operation"""
        # operation #1: Installation
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.INSTALLATION
        argument_composer.maintenance_run_id = "8/27/2021 02:00:00 PM +00:00"
        argument_composer.classifications_to_include = ["Security", "Critical"]
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type("SuccessInstallPath")
        CoreMain(argument_composer.get_composed_arguments())
        # check telemetry events
        self.__check_telemetry_events(runtime)
        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            status_file_data = json.load(file_handle)[0]["status"]
        self.assertTrue(status_file_data["operation"] == Constants.INSTALLATION)
        substatus_file_data = status_file_data["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check started by set to 'User'
        self.assertTrue(json.loads(substatus_file_data[0]["formattedMessage"]["message"])['startedBy'], Constants.PatchAssessmentSummaryStartedBy.USER)
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        last_modified_time_from_installation_substatus_after_user_initiated_installation = json.loads(substatus_file_data[1]["formattedMessage"]["message"])["lastModifiedTime"]
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check status file for configure patching auto updates state
        message = json.loads(substatus_file_data[3]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)  # auto OS updates are disabled in RuntimeCompositor, this is tested in Test-ConfigurePatchingProcessor
        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[3]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.UNKNOWN)  # Configure patching for auto assessment did not execute since assessmentMode was not in input

        # operation #2: Auto Assessment
        argument_composer.activity_id = str(uuid.uuid4())
        argument_composer.included_classifications_list = self.included_package_name_mask_list = self.excluded_package_name_mask_list = []
        argument_composer.maintenance_run_id = None
        argument_composer.start_time = runtime.env_layer.datetime.standard_datetime_to_utc(datetime.datetime.utcnow())
        argument_composer.duration = Constants.AUTO_ASSESSMENT_MAXIMUM_DURATION
        argument_composer.reboot_setting = Constants.REBOOT_NEVER
        argument_composer.patch_mode = None
        argument_composer.exec_auto_assess_only = True
        runtime.execution_config.exec_auto_assess_only = True
        CoreMain(argument_composer.get_composed_arguments())
        # check telemetry events
        self.__check_telemetry_events(runtime)
        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            status_file_data = json.load(file_handle)[0]["status"]

        # verifying the original operation name is preserved
        self.assertTrue(status_file_data["operation"] == Constants.INSTALLATION)
        substatus_file_data = status_file_data["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check started by set to 'Platform'
        self.assertTrue(json.loads(substatus_file_data[0]["formattedMessage"]["message"])['startedBy'], Constants.PatchAssessmentSummaryStartedBy.PLATFORM)
        # verifying the older operation summary is preserved
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # validate lastModifiedTime in InstallationSummary is preserved from the user initiated installation operation
        last_modified_time_from_installation_substatus_after_platform_initiated_assessment = json.loads(substatus_file_data[1]["formattedMessage"]["message"])["lastModifiedTime"]
        self.assertEqual(last_modified_time_from_installation_substatus_after_user_initiated_installation, last_modified_time_from_installation_substatus_after_platform_initiated_assessment)
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check status file for configure patching auto updates state
        message = json.loads(substatus_file_data[3]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)  # auto OS updates are disabled in RuntimeCompositor
        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[3]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.UNKNOWN)  # Configure patching for auto assessment did not execute since assessmentMode was not in input

        runtime.stop()

    def test_auto_assessment_resets_maintenance_run_id_and_health_store_id_to_None(self):
        # operation #1: Installation
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.INSTALLATION
        argument_composer.maintenance_run_id = "8/27/2021 02:00:00 PM +00:00"
        argument_composer.health_store_id = "8/28/2021 02:00:00 PM +00:00"
        argument_composer.classifications_to_include = ["Security", "Critical"]
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type("SuccessInstallPath")
        CoreMain(argument_composer.get_composed_arguments())
        # check telemetry events
        self.__check_telemetry_events(runtime)
        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            status_file_data = json.load(file_handle)[0]["status"]
        self.assertTrue(status_file_data["operation"] == Constants.INSTALLATION)
        substatus_file_data = status_file_data["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check started by set to 'User'
        self.assertTrue(json.loads(substatus_file_data[0]["formattedMessage"]["message"])['startedBy'], Constants.PatchAssessmentSummaryStartedBy.USER)
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        last_modified_time_from_installation_substatus_after_user_initiated_installation = json.loads(substatus_file_data[1]["formattedMessage"]["message"])["lastModifiedTime"]
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check status file for configure patching auto updates state
        message = json.loads(substatus_file_data[3]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)  # auto OS updates are disabled in RuntimeCompositor, this is tested in Test-ConfigurePatchingProcessor
        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[3]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.UNKNOWN)  # Configure patching for auto assessment did not execute since assessmentMode was not in input

        # operation #2: Auto Assessment
        runtime.stop()
        argument_composer.maintenance_run_id = "8/27/2021 02:00:00 PM +00:00"
        argument_composer.health_store_id = "8/28/2021 02:00:00 PM +00:00"
        argument_composer.exec_auto_assess_only = True
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check values of health_store_id and maintenance_run_id
        self.assertEquals(runtime.execution_config.health_store_id, None)
        self.assertEquals(runtime.execution_config.maintenance_run_id, None)

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(status_file_data["operation"] == Constants.INSTALLATION)
        substatus_file_data = status_file_data["substatus"]
        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check started by set to 'Platform'
        self.assertTrue(json.loads(substatus_file_data[0]["formattedMessage"]["message"])['startedBy'], Constants.PatchAssessmentSummaryStartedBy.PLATFORM)
        # verifying the older operation summary is preserved
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # validate lastModifiedTime in InstallationSummary is preserved from the user initiated installation operation
        last_modified_time_from_installation_substatus_after_platform_initiated_assessment = json.loads(substatus_file_data[1]["formattedMessage"]["message"])["lastModifiedTime"]
        self.assertEqual(last_modified_time_from_installation_substatus_after_user_initiated_installation, last_modified_time_from_installation_substatus_after_platform_initiated_assessment)
        self.assertTrue(substatus_file_data[2]["name"] == Constants.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[3]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        # check status file for configure patching auto updates state
        message = json.loads(substatus_file_data[3]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)  # auto OS updates are disabled in RuntimeCompositor
        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[3]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.UNKNOWN)  # Configure patching for auto assessment did not execute since assessmentMode was not in input

        runtime.stop()

    def test_assessment_operation_fail_after_package_manager_reboot(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('ExceptionPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # mock rebooting
        runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.REQUIRED)
        runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        runtime.status_handler.is_reboot_pending = False
        runtime.package_manager.force_reboot = False
        runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.COMPLETED)

        # run coremain again
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 3)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_TRANSITIONING.lower())
        self.assertTrue(substatus_file_data[2]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

    def test_assessment_operation_success_after_package_manager_reboot(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('ExceptionPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # mock rebooting
        runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.REQUIRED)
        runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        runtime.status_handler.is_reboot_pending = False
        runtime.package_manager.force_reboot = False
        runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.COMPLETED)

        # run coremain again, but with success path this time
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 3)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.PATCH_INSTALLATION_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_TRANSITIONING.lower())
        self.assertTrue(substatus_file_data[2]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

    def test_assessment_superseded(self):
        """Unit test for an assessment request that gets superseded by a newer operation..
        Result: Assessment should terminate with a superseded error message."""
        # Step 1: Run assessment normally to generate 0.status and ExtState.json
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
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())

        scratch_path = os.path.join(os.path.curdir, "scratch")

        # Step 2: Set 1.status to Transitioning
        with open(os.path.join(scratch_path, "status", "1.status"), 'r+') as f:
            status = json.load(f)
            status[0]["status"]["status"] = "transitioning"
            status[0]["status"]["substatus"][0]["status"] = "transitioning"
            f.seek(0)  # rewind
            json.dump(status, f)
            f.truncate()
            f.close()

        # Step 3: Update sequence number in ExtState.json to mock a new incoming request
        runtime.write_ext_state_file(runtime.lifecycle_manager.ext_state_file_path, "2",
                                  datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                                  runtime.execution_config.operation)

        raised_exit_exception = False
        # Step 4: Run Assessment again with sequence number 1 to mock an older request that should automatically terminate and report operation superseded
        try:
            CoreMain(argument_composer.get_composed_arguments())
        except SystemExit as error:
            # Should raise a SystemExit exception
            raised_exit_exception = True

        self.assertTrue(raised_exit_exception)

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_ERROR.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(Constants.PatchOperationErrorCodes.NEWER_OPERATION_SUPERSEDED in substatus_file_data[0]["formattedMessage"]["message"])

        runtime.stop()

    def test_temp_folder_created_during_execution_config_init(self):
        # temp_folder is set with a path in environment settings but the dir does not exist
        argument_composer = ArgumentComposer()
        shutil.rmtree(argument_composer.temp_folder)
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # validate temp_folder is created
        self.assertTrue(runtime.execution_config.temp_folder is not None)
        self.assertTrue(os.path.exists(runtime.execution_config.temp_folder))
        runtime.stop()

        # temp_folder is set to None in ExecutionConfig with a valid config_folder location
        argument_composer = ArgumentComposer()
        shutil.rmtree(argument_composer.temp_folder)
        argument_composer.temp_folder = None
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # validate temp_folder is created
        self.assertTrue(runtime.execution_config.temp_folder is not None)
        self.assertTrue(os.path.exists(runtime.execution_config.temp_folder))
        runtime.stop()

        # temp_folder is set to None in ExecutionConfig with an invalid config_folder location, throws exception
        argument_composer = ArgumentComposer()
        shutil.rmtree(argument_composer.temp_folder)
        argument_composer.temp_folder = None
        argument_composer.operation = Constants.ASSESSMENT
        # mock path exists check to return False on config_folder exists check
        backup_os_path_exists = os.path.exists
        os.path.exists = self.mock_os_path_exists
        self.assertRaises(Exception, lambda: RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT))
        # validate temp_folder is not created
        self.assertFalse(os.path.exists(os.path.join(os.path.curdir, "scratch", "tmp")))
        os.path.exists = backup_os_path_exists
        runtime.stop()

    def test_delete_temp_folder_contents_success(self):
        argument_composer = ArgumentComposer()
        self.assertTrue(argument_composer.temp_folder is not None)
        self.assertEqual(argument_composer.temp_folder, os.path.abspath(os.path.join(os.path.curdir, "scratch", "tmp")))

        # delete temp content
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type('HappyPath')
        CoreMain(argument_composer.get_composed_arguments())

        # validate files are deleted
        self.assertTrue(argument_composer.temp_folder is not None)
        files_matched = glob.glob(str(argument_composer.temp_folder) + "/" + str(Constants.TEMP_FOLDER_CLEANUP_ARTIFACT_LIST))
        self.assertTrue(len(files_matched) == 0)
        runtime.stop()

    def test_delete_temp_folder_contents_when_none_exists(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        shutil.rmtree(runtime.execution_config.temp_folder)

        # attempt to delete temp content
        runtime.env_layer.file_system.delete_files_from_dir(runtime.execution_config.temp_folder, Constants.TEMP_FOLDER_CLEANUP_ARTIFACT_LIST)

        # validate files are deleted
        self.assertTrue(runtime.execution_config.temp_folder is not None)
        files_matched = glob.glob(str(runtime.execution_config.temp_folder) + "/" + str(Constants.TEMP_FOLDER_CLEANUP_ARTIFACT_LIST))
        self.assertTrue(len(files_matched) == 0)
        runtime.stop()

    def test_delete_temp_folder_contents_failure(self):
        argument_composer = ArgumentComposer()
        self.assertTrue(argument_composer.temp_folder is not None)
        self.assertEqual(argument_composer.temp_folder, os.path.abspath(os.path.join(os.path.curdir, "scratch", "tmp")))

        # mock os.remove()
        self.backup_os_remove = os.remove
        os.remove = self.mock_os_remove

        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)

        # delete temp content attempt #1, throws exception
        self.assertRaises(Exception, lambda: runtime.env_layer.file_system.delete_files_from_dir(runtime.execution_config.temp_folder, Constants.TEMP_FOLDER_CLEANUP_ARTIFACT_LIST, raise_if_delete_failed=True))
        self.assertTrue(os.path.isfile(os.path.join(runtime.execution_config.temp_folder, "temp1.list")))

        # delete temp content attempt #2, does not throws exception
        runtime.env_layer.file_system.delete_files_from_dir(runtime.execution_config.temp_folder, Constants.TEMP_FOLDER_CLEANUP_ARTIFACT_LIST)
        self.assertTrue(os.path.isfile(os.path.join(runtime.execution_config.temp_folder, "temp1.list")))

        # reset os.remove() mock
        os.remove = self.backup_os_remove
        runtime.stop()

    def test_check_sudo_status_all_attempts_failed(self):
        # Set raise_if_not_sudo=False to test the `return False` all attempts failed
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), legacy_mode=True, package_manager_name=Constants.APT,
            set_mock_sudo_status='Always_False')

        result = runtime.bootstrapper.check_sudo_status(raise_if_not_sudo=False)
        self.assertFalse(result, "Expected check_sudo_status to return False after all attempts failed")
        runtime.stop()

    def test_check_sudo_status_throw_exception(self):
        # Set raise_if_not_sudo=True to throw exception
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), legacy_mode=True, package_manager_name=Constants.APT,
            set_mock_sudo_status='Always_False')

        # Run check_sudo_status and expect an exception after all retries
        with self.assertRaises(Exception) as context:
            runtime.bootstrapper.check_sudo_status(raise_if_not_sudo=True)

        # Verify exception msg contains the expected failure text
        self.assertTrue("Unable to invoke sudo successfully" in str(context.exception))
        runtime.stop()

    def test_check_sudo_status_insufficient_output_lines(self):
        # Set raise_if_not_sudo=True to throw exception
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), legacy_mode=True, package_manager_name=Constants.APT,
            set_mock_sudo_status='insufficient_output_lines')

        # Run check_sudo_status and expect an exception after all retries
        with self.assertRaises(Exception) as context:
            runtime.bootstrapper.check_sudo_status()

        # Verify exception msg contains the expected failure text
        self.assertTrue("Unexpected sudo check result" in str(context.exception))
        runtime.stop()

    def test_check_sudo_status_unexpected_output_lines(self):
        # Set raise_if_not_sudo=True to throw exception
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), legacy_mode=True, package_manager_name=Constants.APT,
            set_mock_sudo_status='unexpected_output')

        # Run check_sudo_status and expect an exception after all retries
        with self.assertRaises(Exception) as context:
            runtime.bootstrapper.check_sudo_status()

        # Verify exception msg contains the expected failure text
        self.assertTrue("Unexpected sudo check result" in str(context.exception))
        runtime.stop()

    def test_check_sudo_status_succeeds_on_third_attempt(self):
        # Test retry logic in check sudo status after 2 failed attempts followed by success (true)
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), legacy_mode=True, package_manager_name=Constants.APT,
            set_mock_sudo_status='Retry_True')

        # Attempt to check sudo status, succeed (true) on the 3rd attempt
        result = runtime.bootstrapper.check_sudo_status(raise_if_not_sudo=True)

        # Verify the result is success (True)
        self.assertTrue(result, "Expected check_sudo_status to succeed on the 3rd attempts")

        # Verify 3 attempts were made
        self.assertEqual(runtime.sudo_check_status_attempts, 3, "Expected exactly 3 attempts in check_sudo_status")
        runtime.stop()

    def __check_telemetry_events(self, runtime):
        all_events = os.listdir(runtime.telemetry_writer.events_folder_path)
        self.assertTrue(len(all_events) > 0)
        latest_event_file = [pos_json for pos_json in os.listdir(runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertTrue('Core' in events[0]['TaskName'])
            f.close()


if __name__ == '__main__':
    unittest.main()

