# Copyright 2020 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
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

    #region Mocks
    def mock_package_manager_get_current_auto_os_patch_state_returns_unknown(self):
        if self.mock_package_manager_get_current_auto_os_patch_state_returns_unknown_call_count == 0:
            self.mock_package_manager_get_current_auto_os_patch_state_returns_unknown_call_count = 1
            return Constants.AutomaticOSPatchStates.DISABLED
        else:
            return Constants.AutomaticOSPatchStates.UNKNOWN
    #endregion Mocks

    def test_operation_success_for_configure_patching_request_for_apt_with_default_updates_config(self):
        # create and adjust arguments
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.Op.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        argument_composer.assessment_mode = Constants.AssessmentModes.IMAGE_DEFAULT

        # create and patch runtime
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.package_manager.get_current_auto_os_patch_state = runtime.backup_get_current_auto_os_patch_state
        runtime.package_manager.patch_mode_manager.os_patch_configuration_settings_file_path = os.path.join(runtime.execution_config.config_folder, "20auto-upgrades")
        runtime.set_legacy_test_type('HappyPath')

        # mock os patch configuration
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        runtime.write_to_file(runtime.package_manager.patch_mode_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)

        # execute Core
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file for configure patching patch mode
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

        # check status file for configure patching patch state (and including for 'Platform' initiated assessment data)
        self.assertTrue(runtime.package_manager.patch_mode_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.OpSummary.ASSESSMENT)
        message = json.loads(substatus_file_data[0]["formattedMessage"]["message"])
        self.assertTrue(message["startedBy"], Constants.PatchAssessmentSummaryStartedBy.PLATFORM)
        self.assertTrue(substatus_file_data[1]["name"] == Constants.OpSummary.CONFIGURE_PATCHING)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.Status.SUCCESS.lower())
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
        argument_composer.operation = Constants.Op.CONFIGURE_PATCHING
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
        self.assertTrue(substatus_file_data[0]["name"] == Constants.OpSummary.ASSESSMENT)   # assessment is now part of the CP flow
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.Status.SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.OpSummary.CONFIGURE_PATCHING)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.Status.SUCCESS.lower())
        runtime.stop()

    def test_operation_success_for_installation_request_with_configure_patching(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.Op.INSTALLATION
        argument_composer.maintenance_run_id = "9/28/2020 02:00:00 PM +00:00"
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.package_manager.get_current_auto_os_patch_state = runtime.backup_get_current_auto_os_patch_state
        runtime.package_manager.patch_mode_manager.os_patch_configuration_settings_file_path = os.path.join(runtime.execution_config.config_folder, "20auto-upgrades")
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        runtime.write_to_file(runtime.package_manager.patch_mode_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)
        runtime.set_legacy_test_type('SuccessInstallPath')
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]
        self.assertTrue(runtime.package_manager.patch_mode_manager.image_default_patch_configuration_backup_exists())
        image_default_patch_configuration_backup = json.loads(runtime.env_layer.file_system.read_with_retry(runtime.package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Update-Package-Lists'] == "1")
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Unattended-Upgrade'] == "1")
        os_patch_configuration_settings = runtime.env_layer.file_system.read_with_retry(runtime.package_manager.patch_mode_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(os_patch_configuration_settings is not None)
        self.assertTrue('APT::Periodic::Update-Package-Lists "0"' in os_patch_configuration_settings)
        self.assertTrue('APT::Periodic::Unattended-Upgrade "0"' in os_patch_configuration_settings)
        self.assertTrue(substatus_file_data[3]["name"] == Constants.OpSummary.CONFIGURE_PATCHING)
        self.assertTrue(substatus_file_data[3]["status"].lower() == Constants.Status.SUCCESS.lower())

        self.assertEqual(len(substatus_file_data), 4)
        self.assertTrue(substatus_file_data[0]["name"] == Constants.OpSummary.ASSESSMENT)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.Status.SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.OpSummary.INSTALLATION)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.Status.SUCCESS.lower())
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["name"], "python-samba")
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["name"], "samba-common-bin")
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][1]["classifications"]))
        self.assertEqual(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["name"], "samba-libs")
        self.assertTrue("python-samba_2:4.4.5+dfsg-2ubuntu5.4" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][0]["patchId"]))
        self.assertTrue("Security" in str(json.loads(substatus_file_data[1]["formattedMessage"]["message"])["patches"][2]["classifications"]))
        self.assertTrue(substatus_file_data[2]["name"] == Constants.OpSummary.PATCH_METADATA_FOR_HEALTHSTORE)
        self.assertTrue(substatus_file_data[2]["status"].lower() == Constants.Status.SUCCESS.lower())
        substatus_file_data_patch_metadata_summary = json.loads(substatus_file_data[2]["formattedMessage"]["message"])
        self.assertEqual(substatus_file_data_patch_metadata_summary["patchVersion"], "2020.09.28")
        self.assertTrue(substatus_file_data_patch_metadata_summary["shouldReportToHealthStore"])
        runtime.stop()

    def test_patch_mode_set_failure_for_configure_patching(self):
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.Op.CONFIGURE_PATCHING
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
        self.assertEqual(2, len(substatus_file_data))
        self.assertTrue(substatus_file_data[0]["name"] == Constants.OpSummary.ASSESSMENT)   # assessment is now part of the CP flow
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.Status.SUCCESS.lower())
        self.assertTrue(substatus_file_data[1]["name"] == Constants.OpSummary.CONFIGURE_PATCHING)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.Status.ERROR.lower())

        #restore
        runtime.package_manager.get_current_auto_os_patch_state = backup_package_manager_get_current_auto_os_patch_state

        runtime.stop()

    def test_configure_patching_with_assessment_mode_by_platform(self):

        # create and adjust arguments
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.Op.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.IMAGE_DEFAULT
        argument_composer.assessment_mode = Constants.AssessmentModes.AUTOMATIC_BY_PLATFORM

        # create and patch runtime
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.package_manager.get_current_auto_os_patch_state = runtime.backup_get_current_auto_os_patch_state
        runtime.package_manager.patch_mode_manager.os_patch_configuration_settings_file_path = os.path.join(runtime.execution_config.config_folder, "20auto-upgrades")
        runtime.set_legacy_test_type('HappyPath')

        # mock os patch configuration
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        runtime.write_to_file(runtime.package_manager.patch_mode_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)

        # execute Core
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file for configure patching patch mode
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

        # check status file for configure patching patch state
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[1]["name"] == Constants.OpSummary.CONFIGURE_PATCHING)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.Status.SUCCESS.lower())
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.ENABLED)  # no change is made on Auto OS updates for patch mode 'ImageDefault'
        self.assertTrue(substatus_file_data[0]["name"] == Constants.OpSummary.ASSESSMENT)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.Status.SUCCESS.lower())

        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.ENABLED)  # auto assessment is enabled

        # stop test runtime
        runtime.stop()

    def test_configure_patching_with_patch_mode_and_assessment_mode_by_platform(self):

        # create and adjust arguments
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.Op.CONFIGURE_PATCHING
        argument_composer.patch_mode = Constants.PatchModes.AUTOMATIC_BY_PLATFORM
        argument_composer.assessment_mode = Constants.AssessmentModes.AUTOMATIC_BY_PLATFORM

        # create and patch runtime
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.package_manager.get_current_auto_os_patch_state = runtime.backup_get_current_auto_os_patch_state
        runtime.package_manager.patch_mode_manager.os_patch_configuration_settings_file_path = os.path.join(runtime.execution_config.config_folder, "20auto-upgrades")
        runtime.set_legacy_test_type('HappyPath')

        # mock os patch configuration
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        runtime.write_to_file(runtime.package_manager.patch_mode_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)

        # execute Core
        CoreMain(argument_composer.get_composed_arguments())

        # check telemetry events
        self.__check_telemetry_events(runtime)

        # check status file for configure patching patch mode
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

        # check status file for configure patching patch state
        self.assertTrue(runtime.package_manager.patch_mode_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(len(substatus_file_data), 2)
        self.assertTrue(substatus_file_data[1]["name"] == Constants.OpSummary.CONFIGURE_PATCHING)
        self.assertTrue(substatus_file_data[1]["status"].lower() == Constants.Status.SUCCESS.lower())
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["automaticOSPatchState"], Constants.AutomaticOSPatchStates.DISABLED)  # auto OS updates are disabled on patch mode 'AutomaticByPlatform'
        self.assertTrue(substatus_file_data[0]["name"] == Constants.OpSummary.ASSESSMENT)
        self.assertTrue(substatus_file_data[0]["status"].lower() == Constants.Status.SUCCESS.lower())

        # check status file for configure patching assessment state
        message = json.loads(substatus_file_data[1]["formattedMessage"]["message"])
        self.assertEqual(message["autoAssessmentStatus"]["autoAssessmentState"], Constants.AutoAssessmentStates.ENABLED)  # auto assessment is enabled

        # stop test runtime
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
