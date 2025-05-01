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
import re
import unittest
import sys

from library.ExtStatusAsserter import ExtStatusAsserter

# Conditional import for StringIO
try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import StringIO  # Python 3

from core.src.CoreMain import CoreMain
from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestConfigurePatchingProcessor(unittest.TestCase):
    def setUp(self):
        # Had to move runtime init and stop to individual test functions, since every test uses a different maintenance_run_id which has to be set before runtime init
        # self.argument_composer = ArgumentComposer().get_composed_arguments()
        # self.runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.ZYPPER)
        # self.container = self.runtime.container
        self.mock_package_manager_get_current_auto_os_patch_state_returns_unknown_call_count = 0  # used to vary behavior of the mock

    def tearDown(self):
        # self.runtime.stop()
        pass

    # region Mocks
    def mock_package_manager_get_current_auto_os_patch_state_returns_unknown(self):
        if self.mock_package_manager_get_current_auto_os_patch_state_returns_unknown_call_count == 0:
            self.mock_package_manager_get_current_auto_os_patch_state_returns_unknown_call_count = 1
            return Constants.AutomaticOSPatchStates.DISABLED
        else:
            return Constants.AutomaticOSPatchStates.UNKNOWN

    def mock_get_current_auto_os_patch_state(self):
        raise Exception("Mocked Exception")
    # endregion Mocks

    def test_operation_success_for_configure_patching_request_for_apt_with_default_updates_config(self):
        # create and adjust arguments
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        argument_composer.assessment_mode = Constants.AssessmentModes.IMAGE_DEFAULT

        # create and patch runtime
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.package_manager.get_current_auto_os_patch_state = runtime.backup_get_current_auto_os_patch_state
        runtime.package_manager.os_patch_configuration_settings_file_path = os.path.join(runtime.execution_config.config_folder, "20auto-upgrades")
        runtime.set_legacy_test_type('HappyPath')

        # mock os patch configuration
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        runtime.write_to_file(runtime.package_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)

        # execute Core
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file for configure patching patch mode
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

        # check status file for configure patching patch state (and including for 'Platform' initiated assessment data)
        self.assertTrue(runtime.package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        message = json.loads(substatus_file_data[0]["formattedMessage"]["message"])
        self.assertTrue(message["startedBy"], Constants.PatchAssessmentSummaryStartedBy.PLATFORM)
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)

        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.DISABLED)

        # stop test runtime
        runtime.stop()

    def test_operation_success_for_configure_patching_request_for_apt_without_default_updates_config(self):
        # default auto OS updates config file not found on the machine
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.package_manager.get_current_auto_os_patch_state = runtime.backup_get_current_auto_os_patch_state
        runtime.set_legacy_test_type('HappyPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)   # assessment is now part of the CP flow
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

    def test_operation_success_for_installation_request_with_configure_patching(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.INSTALLATION
        argument_composer.maintenance_run_id = "9/28/2020 02:00:00 PM +00:00"
        argument_composer.health_store_id = "pub_off_sku_2020.09.23"
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.package_manager.get_current_auto_os_patch_state = runtime.backup_get_current_auto_os_patch_state
        runtime.package_manager.os_patch_configuration_settings_file_path = os.path.join(runtime.execution_config.config_folder, "20auto-upgrades")
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        runtime.write_to_file(runtime.package_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # assert
        self.assertTrue(runtime.package_manager.image_default_patch_configuration_backup_exists())
        image_default_patch_configuration_backup = json.loads(runtime.env_layer.file_system.read_with_retry(runtime.package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Update-Package-Lists'] == "1")
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Unattended-Upgrade'] == "1")
        os_patch_configuration_settings = runtime.env_layer.file_system.read_with_retry(runtime.package_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(os_patch_configuration_settings is not None)
        self.assertTrue('APT::Periodic::Update-Package-Lists "0"' in os_patch_configuration_settings)
        self.assertTrue('APT::Periodic::Unattended-Upgrade "0"' in os_patch_configuration_settings)

        # check status file
        ext_status_asserter = ExtStatusAsserter(runtime.execution_config.status_file_path, runtime.env_layer)
        ext_status_asserter.assert_status_file_substatuses()
        ext_status_asserter.assert_installation_summary_has_patch("python-samba", Constants.PackageClassification.SECURITY, "python-samba_2:4.4.5+dfsg-2ubuntu5.4")
        ext_status_asserter.assert_installation_summary_has_patch("samba-common-bin", Constants.PackageClassification.SECURITY)
        ext_status_asserter.assert_installation_summary_has_patch("samba-libs", Constants.PackageClassification.SECURITY)
        ext_status_asserter.assert_healthstore_status_info(patch_version="pub_off_sku_2020.09.23", should_report=True)
        runtime.stop()

    def test_operation_fail_for_configure_patching_telemetry_not_supported(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        argument_composer.events_folder = None
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(env_settings=dict(telemetrySupported=False)), True, Constants.APT)
        runtime.set_legacy_test_type('HappyPath')
        runtime.configure_patching_processor.start_configure_patching()

        # check status file
        ext_status_asserter = ExtStatusAsserter(runtime.execution_config.status_file_path, runtime.env_layer)
        ext_status_asserter.assert_status_file_substatuses(substatus_expectations={
            Constants.CONFIGURE_PATCHING_SUMMARY: Constants.STATUS_SUCCESS
        })

        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 1)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)

        if runtime.vm_cloud_type == Constants.VMCloudType.AZURE:
            self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_ERROR.lower())
            self.assertTrue(len(json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"]), 1)
            self.assertTrue(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[0]["formattedMessage"]["message"])["errors"]["details"][0]["message"])
            self.assertTrue(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG in json.loads(substatus_file_data[0]["formattedMessage"]["message"])["autoAssessmentStatus"]["errors"]["details"][0]["message"])
            self.assertTrue(Constants.STATUS_ERROR in json.loads(substatus_file_data[0]["formattedMessage"]["message"])["autoAssessmentStatus"]["autoAssessmentState"])
        else:
            self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        runtime.stop()

    def test_patch_mode_set_failure_for_configure_patching(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        argument_composer.assessment_mode = "LetsThrowAnException"
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.package_manager.get_current_auto_os_patch_state = runtime.backup_get_current_auto_os_patch_state
        runtime.set_legacy_test_type('HappyPath')

        # mock swap
        backup_package_manager_get_current_auto_os_patch_state = runtime.package_manager.get_current_auto_os_patch_state
        runtime.package_manager.get_current_auto_os_patch_state = self.mock_package_manager_get_current_auto_os_patch_state_returns_unknown

        # Execute main
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)   # assessment is now part of the CP flow
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_ERROR.lower())

        #restore
        runtime.package_manager.get_current_auto_os_patch_state = backup_package_manager_get_current_auto_os_patch_state

        runtime.stop()

    def test_configure_patching_with_assessment_mode_by_platform(self):

        # create and adjust arguments
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.IMAGE_DEFAULT
        argument_composer.assessment_mode = Constants.AssessmentModes.AUTOMATIC_BY_PLATFORM

        # create and patch runtime
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.package_manager.get_current_auto_os_patch_state = runtime.backup_get_current_auto_os_patch_state
        runtime.package_manager.os_patch_configuration_settings_file_path = os.path.join(runtime.execution_config.config_folder, "20auto-upgrades")
        runtime.set_legacy_test_type('HappyPath')

        # mock os patch configuration
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        runtime.write_to_file(runtime.package_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)

        # execute Core
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file for configure patching patch mode
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

        # check status file for configure patching patch state
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.ENABLED)  # no change is made on Auto OS updates for patch mode 'ImageDefault'
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())

        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.ENABLED)  # auto assessment is enabled

        # stop test runtime
        runtime.stop()

    def test_configure_patching_with_patch_mode_and_assessment_mode_by_platform(self):

        # create and adjust arguments
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        argument_composer.assessment_mode = Constants.AssessmentModes.AUTOMATIC_BY_PLATFORM

        # create and patch runtime
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.package_manager.get_current_auto_os_patch_state = runtime.backup_get_current_auto_os_patch_state
        runtime.package_manager.os_patch_configuration_settings_file_path = os.path.join(runtime.execution_config.config_folder, "20auto-upgrades")
        runtime.set_legacy_test_type('HappyPath')

        # mock os patch configuration
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        runtime.write_to_file(runtime.package_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)

        # execute Core
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file for configure patching patch mode
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

        # check status file for configure patching patch state
        self.assertTrue(runtime.package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[1]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.STATUS_SUCCESS.lower())
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)  # auto OS updates are disabled on patch mode 'AutomaticByPlatform'
        self.assertTrue(substatus_file_data[0]["name"] == Constants.PATCH_ASSESSMENT_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_SUCCESS.lower())

        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.ENABLED)  # auto assessment is enabled

        # stop test runtime
        runtime.stop()

    def test_configure_patching_raise_exception_auto_os_patch_state(self):
        # arrange capture std IO
        captured_output = StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured_output

        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        argument_composer.assessment_mode = Constants.AssessmentModes.AUTOMATIC_BY_PLATFORM
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.package_manager.get_current_auto_os_patch_state = runtime.backup_get_current_auto_os_patch_state
        runtime.set_legacy_test_type('HappyPath')

        # mock swap
        backup_package_manager_get_current_auto_os_patch_state = runtime.package_manager.get_current_auto_os_patch_state
        runtime.package_manager.get_current_auto_os_patch_state = self.mock_get_current_auto_os_patch_state

        runtime.configure_patching_processor.start_configure_patching()

        # restore sdt.out ouptput
        sys.stdout = original_stdout

        # assert
        output = captured_output.getvalue()
        self.assertIn("Error while processing patch mode configuration", output)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertEqual(len(substatus_file_data), 1)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.CONFIGURE_PATCHING_SUMMARY)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.STATUS_TRANSITIONING.lower())

        # restore
        runtime.package_manager.get_current_auto_os_patch_state = backup_package_manager_get_current_auto_os_patch_state

        runtime.stop()

    def test_configure_patching_raise_exception_auto_assessment_systemd(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        argument_composer.assessment_mode = Constants.AssessmentModes.AUTOMATIC_BY_PLATFORM
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type('HappyPath')

        # mock swap service manager
        back_up_auto_assess_service_manager = runtime.configure_patching_processor.auto_assess_service_manager.systemd_exists
        runtime.configure_patching_processor.auto_assess_service_manager.systemd_exists = lambda: False
        self.assertRaises(Exception, runtime.configure_patching_processor.start_configure_patching())
        runtime.configure_patching_processor.auto_assess_service_manager.systemd_exists = back_up_auto_assess_service_manager

        # mock swap legacy timer manager
        back_up_auto_assess_timer_manager_legacy = runtime.configure_patching_processor.auto_assess_timer_manager_legacy
        runtime.configure_patching_processor.auto_assess_timer_manager_legacy = object()
        self.assertRaises(Exception, runtime.configure_patching_processor.start_configure_patching())
        runtime.configure_patching_processor.auto_assess_timer_manager = back_up_auto_assess_timer_manager_legacy

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
