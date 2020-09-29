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
import shutil
import tempfile
import unittest
from extension.src.ActionHandler import ActionHandler
from extension.src.Constants import Constants
from extension.src.ProcessHandler import ProcessHandler
from extension.src.RuntimeContextHandler import RuntimeContextHandler
from extension.src.file_handlers.CoreStateHandler import CoreStateHandler
from extension.src.file_handlers.ExtConfigSettingsHandler import ExtConfigSettingsHandler
from extension.src.file_handlers.ExtEnvHandler import ExtEnvHandler
from extension.src.file_handlers.ExtOutputStatusHandler import ExtOutputStatusHandler
from extension.src.file_handlers.ExtStateHandler import ExtStateHandler
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestActionHandler(unittest.TestCase):
    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.runtime = RuntimeComposer()
        self.runtime_context_handler = RuntimeContextHandler(self.runtime.logger)
        self.ext_env_handler = ExtEnvHandler(self.runtime.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        self.ext_config_settings_handler = ExtConfigSettingsHandler(self.runtime.logger, self.runtime.json_file_handler, self.ext_env_handler.config_folder)
        self.core_state_handler = CoreStateHandler(self.ext_env_handler.config_folder, self.runtime.json_file_handler)
        self.ext_state_handler = ExtStateHandler(self.ext_env_handler.config_folder, self.runtime.utility, self.runtime.json_file_handler)

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def mock_get_all_versions(self, extension_pardir):
        return [extension_pardir + '/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.3',
                extension_pardir + '/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.5',
                extension_pardir + '/Microsoft.CPlat.Core.LinuxPatchExtension-1.1.9']

    def mock_get_all_versions_exception(self, extension_pardir):
        raise Exception

    def mock_process_previous_patch_operation_exception(self, core_state_handler, process_handler, prev_patch_max_end_time, core_state_content):
        raise Exception

    @staticmethod
    def create_latest_extension_dir(version, test_dir):
        latest_extension_version = version
        os.mkdir(os.path.join(test_dir, latest_extension_version))
        new_version_config_folder = os.path.join(test_dir, latest_extension_version, 'config')
        os.mkdir(new_version_config_folder)
        return new_version_config_folder

    def create_previous_extension_version(self, version, test_dir):
        os.mkdir(os.path.join(test_dir, version))
        previous_version_config_folder = os.path.join(test_dir, version, 'config')
        os.mkdir(previous_version_config_folder)
        self.runtime.create_temp_file(previous_version_config_folder, Constants.CORE_STATE_FILE, content='[test]')
        self.runtime.create_temp_file(previous_version_config_folder, Constants.EXT_STATE_FILE, content='test')
        self.runtime.create_temp_file(previous_version_config_folder, 'backup.bak', content='{"testkey": "testVal"}')
        self.runtime.create_temp_file(previous_version_config_folder, 'test.txt', content='{"testkey": "testVal"}')
        return previous_version_config_folder

    def test_update_command_success_with_multiple_version_combinations(self):
        # testing with versions 1.2.5, 1.2.3 and 1.1.9
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        # create extension dir for the latest and other extension versions, to be used in the test
        latest_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.2.5'
        new_version_config_folder = self.create_latest_extension_dir(latest_extension_version, test_dir)
        previous_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.2.3'
        previous_version_config_folder = self.create_previous_extension_version(previous_extension_version, test_dir)
        other_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.1.9'
        other_version_config_folder = self.create_previous_extension_version(other_extension_version, test_dir)

        status_folder = os.path.join(test_dir, "status")
        os.mkdir(status_folder)
        ext_output_status_handler = ExtOutputStatusHandler(self.runtime.logger, self.runtime.utility, self.runtime.json_file_handler, 'test/', 0, status_folder)
        process_handler = ProcessHandler(self.runtime.logger, ext_output_status_handler)
        action_handler = ActionHandler(self.runtime.logger, self.runtime.utility, self.runtime_context_handler, self.runtime.json_file_handler, self.ext_env_handler,
                                       self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, ext_output_status_handler, process_handler, "2020-09-02T13:40:54.8862542Z", 0)
        action_handler.ext_env_handler.config_folder = new_version_config_folder

        self.assertTrue(action_handler.update() == Constants.ExitCode.Okay)
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.CORE_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.EXT_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, 'backup.bak')))
        self.assertFalse(os.path.exists(os.path.join(new_version_config_folder, 'test.txt')))

        # verify status file
        status_json = ext_output_status_handler.read_file()
        parent_key = Constants.StatusFileFields.status
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_name], "Azure Patch Management")
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_operation], Constants.UPDATING_EXTENSION)
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_status], Constants.Status.Success.lower())

        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_update_command_success_with_patch_version_change(self):
        # testing with versions 1.6.99 and 1.6.100
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        # create extension dir for the latest and other extension versions, to be used in the test
        latest_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100'
        new_version_config_folder = self.create_latest_extension_dir(latest_extension_version, test_dir)
        previous_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.6.99'
        previous_version_config_folder = self.create_previous_extension_version(previous_extension_version, test_dir)

        status_folder = os.path.join(test_dir, "status")
        os.mkdir(status_folder)
        ext_output_status_handler = ExtOutputStatusHandler(self.runtime.logger, self.runtime.utility, self.runtime.json_file_handler, 'test/', 0, status_folder)
        process_handler = ProcessHandler(self.runtime.logger, ext_output_status_handler)
        action_handler = ActionHandler(self.runtime.logger, self.runtime.utility, self.runtime_context_handler, self.runtime.json_file_handler, self.ext_env_handler,
                                       self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, ext_output_status_handler, process_handler, "2020-09-02T13:40:54.8862542Z", 0)

        action_handler.ext_env_handler.config_folder = new_version_config_folder
        self.assertTrue(action_handler.update() == Constants.ExitCode.Okay)
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.CORE_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.EXT_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, 'backup.bak')))
        self.assertFalse(os.path.exists(os.path.join(new_version_config_folder, 'test.txt')))

        # verify status file
        status_json = ext_output_status_handler.read_file()
        parent_key = Constants.StatusFileFields.status
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_name], "Azure Patch Management")
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_operation], Constants.UPDATING_EXTENSION)
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_status], Constants.Status.Success.lower())

        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_update_command_success_with_minor_and_patch_version_change(self):
        # testing with versions 1.4.897 and 1.5.23
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        # create extension dir for the latest and other extension versions, to be used in the test
        latest_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.5.23'
        new_version_config_folder = self.create_latest_extension_dir(latest_extension_version, test_dir)
        previous_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.4.897'
        previous_version_config_folder = self.create_previous_extension_version(previous_extension_version, test_dir)

        status_folder = os.path.join(test_dir, "status")
        os.mkdir(status_folder)
        ext_output_status_handler = ExtOutputStatusHandler(self.runtime.logger, self.runtime.utility, self.runtime.json_file_handler, 'test/', 0, status_folder)
        process_handler = ProcessHandler(self.runtime.logger, ext_output_status_handler)
        action_handler = ActionHandler(self.runtime.logger, self.runtime.utility, self.runtime_context_handler, self.runtime.json_file_handler, self.ext_env_handler,
                                       self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, ext_output_status_handler, process_handler, "2020-09-02T13:40:54.8862542Z", 0)

        action_handler.ext_env_handler.config_folder = new_version_config_folder
        self.assertTrue(action_handler.update() == Constants.ExitCode.Okay)
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.CORE_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.EXT_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, 'backup.bak')))
        self.assertFalse(os.path.exists(os.path.join(new_version_config_folder, 'test.txt')))

        # verify status file
        status_json = ext_output_status_handler.read_file()
        parent_key = Constants.StatusFileFields.status
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_name], "Azure Patch Management")
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_operation], Constants.UPDATING_EXTENSION)
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_status], Constants.Status.Success.lower())

        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_update_command_success_with_major_version_change(self):
        # testing with versions 1.0.0 and 2.0.00
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        # create extension dir for the latest and other extension versions, to be used in the test
        latest_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-2.0.00'
        new_version_config_folder = self.create_latest_extension_dir(latest_extension_version, test_dir)
        previous_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.0.0'
        previous_version_config_folder = self.create_previous_extension_version(previous_extension_version, test_dir)

        status_folder = os.path.join(test_dir, "status")
        os.mkdir(status_folder)
        ext_output_status_handler = ExtOutputStatusHandler(self.runtime.logger, self.runtime.utility, self.runtime.json_file_handler, 'test/', 0, status_folder)
        process_handler = ProcessHandler(self.runtime.logger, ext_output_status_handler)
        action_handler = ActionHandler(self.runtime.logger, self.runtime.utility, self.runtime_context_handler, self.runtime.json_file_handler, self.ext_env_handler,
                                       self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, ext_output_status_handler, process_handler, "2020-09-02T13:40:54.8862542Z", 0)

        action_handler.ext_env_handler.config_folder = new_version_config_folder
        self.assertTrue(action_handler.update() == Constants.ExitCode.Okay)
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.CORE_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.EXT_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, 'backup.bak')))
        self.assertFalse(os.path.exists(os.path.join(new_version_config_folder, 'test.txt')))

        # verify status file
        status_json = ext_output_status_handler.read_file()
        parent_key = Constants.StatusFileFields.status
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_name], "Azure Patch Management")
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_operation], Constants.UPDATING_EXTENSION)
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_status], Constants.Status.Success.lower())

        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_update_command_fail_config_folder_not_found(self):
        # other versions not found
        # path to previous version artifacts not found
        # Create a temporary directory and dir for the latest version
        test_dir = tempfile.mkdtemp()
        status_folder = os.path.join(test_dir, "status")
        os.mkdir(status_folder)
        ext_output_status_handler = ExtOutputStatusHandler(self.runtime.logger, self.runtime.utility, self.runtime.json_file_handler, 'test/', 0, status_folder)
        process_handler = ProcessHandler(self.runtime.logger, ext_output_status_handler)
        action_handler = ActionHandler(self.runtime.logger, self.runtime.utility, self.runtime_context_handler, self.runtime.json_file_handler, self.ext_env_handler,
                                       self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, ext_output_status_handler, process_handler, "2020-09-02T13:40:54.8862542Z", 0)

        action_handler.ext_env_handler.config_folder = '/test/config'
        self.assertTrue(action_handler.update() == Constants.ExitCode.HandlerFailed)

        # verify status file
        status_json = ext_output_status_handler.read_file()
        parent_key = Constants.StatusFileFields.status
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_name], "Azure Patch Management")
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_operation], Constants.UPDATING_EXTENSION)
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_status], Constants.Status.Error.lower())

        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_update_command_fail_prev_version_artifacts_not_found(self):
        # path to previous version artifacts not found
        # Create a temporary directory and dir for the latest version
        test_dir = tempfile.mkdtemp()
        latest_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.2.5'
        os.mkdir(os.path.join(test_dir, latest_extension_version))
        new_version_config_folder = os.path.join(test_dir, latest_extension_version, 'config')
        os.mkdir(new_version_config_folder)
        status_folder = os.path.join(test_dir, "status")
        os.mkdir(status_folder)
        ext_output_status_handler = ExtOutputStatusHandler(self.runtime.logger, self.runtime.utility, self.runtime.json_file_handler, 'test/', 0, status_folder)
        process_handler = ProcessHandler(self.runtime.logger, ext_output_status_handler)
        action_handler = ActionHandler(self.runtime.logger, self.runtime.utility, self.runtime_context_handler, self.runtime.json_file_handler, self.ext_env_handler,
                                       self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, ext_output_status_handler, process_handler, "2020-09-02T13:40:54.8862542Z", 0)

        action_handler.ext_env_handler.config_folder = new_version_config_folder
        action_handler.get_all_versions = self.mock_get_all_versions
        self.assertTrue(action_handler.update() == Constants.ExitCode.HandlerFailed)

        # verify status file
        status_json = ext_output_status_handler.read_file()
        parent_key = Constants.StatusFileFields.status
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_name], "Azure Patch Management")
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_operation], Constants.UPDATING_EXTENSION)
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_status], Constants.Status.Error.lower())

        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_update_command_fail_exception_raised(self):
        # exception path
        test_dir = tempfile.mkdtemp()
        latest_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.2.5'
        os.mkdir(os.path.join(test_dir, latest_extension_version))
        new_version_config_folder = os.path.join(test_dir, latest_extension_version, 'config')
        os.mkdir(new_version_config_folder)
        status_folder = os.path.join(test_dir, "status")
        os.mkdir(status_folder)
        ext_output_status_handler = ExtOutputStatusHandler(self.runtime.logger, self.runtime.utility, self.runtime.json_file_handler, 'test/', 0, status_folder)
        process_handler = ProcessHandler(self.runtime.logger, ext_output_status_handler)
        action_handler = ActionHandler(self.runtime.logger, self.runtime.utility, self.runtime_context_handler, self.runtime.json_file_handler, self.ext_env_handler,
                                       self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, ext_output_status_handler, process_handler, "2020-09-02T13:40:54.8862542Z", 0)

        action_handler.ext_env_handler.config_folder = new_version_config_folder
        action_handler.get_all_versions = self.mock_get_all_versions_exception
        self.assertTrue(action_handler.update() == Constants.ExitCode.HandlerFailed)

        # verify status file
        status_json = ext_output_status_handler.read_file()
        parent_key = Constants.StatusFileFields.status
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_name], "Azure Patch Management")
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_operation], Constants.UPDATING_EXTENSION)
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_status], Constants.Status.Error.lower())

        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_disable_command_success(self):
        test_dir = tempfile.mkdtemp()
        config_folder = os.path.join(test_dir, "config")
        os.mkdir(config_folder)
        self.runtime.create_temp_file(config_folder, Constants.CORE_STATE_FILE, content='[test]')
        self.runtime.create_temp_file(config_folder, Constants.EXT_STATE_FILE, content='[test]')
        status_folder = os.path.join(test_dir, "status")
        os.mkdir(status_folder)
        ext_output_status_handler = ExtOutputStatusHandler(self.runtime.logger, self.runtime.utility, self.runtime.json_file_handler, 'test/', 0, status_folder)
        process_handler = ProcessHandler(self.runtime.logger, ext_output_status_handler)
        action_handler = ActionHandler(self.runtime.logger, self.runtime.utility, self.runtime_context_handler, self.runtime.json_file_handler, self.ext_env_handler,
                                       self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, ext_output_status_handler, process_handler, datetime.datetime.utcnow(), 0)

        self.assertTrue(action_handler.disable() == Constants.ExitCode.Okay)

        # verify status file
        status_json = ext_output_status_handler.read_file()
        parent_key = Constants.StatusFileFields.status
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_name], "Azure Patch Management")
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_operation], Constants.DISABLING_EXTENSION)
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_status], Constants.Status.Success.lower())

        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_disable_command_fail(self):
        self.runtime_context_handler.process_previous_patch_operation = self.mock_process_previous_patch_operation_exception

        test_dir = tempfile.mkdtemp()
        config_folder = os.path.join(test_dir, "config")
        os.mkdir(config_folder)
        self.runtime.create_temp_file(config_folder, Constants.CORE_STATE_FILE, content='[test]')
        self.runtime.create_temp_file(config_folder, Constants.EXT_STATE_FILE, content='[test]')
        status_folder = os.path.join(test_dir, "status")
        os.mkdir(status_folder)
        ext_output_status_handler = ExtOutputStatusHandler(self.runtime.logger, self.runtime.utility, self.runtime.json_file_handler, 'test/', 0, status_folder)
        process_handler = ProcessHandler(self.runtime.logger, ext_output_status_handler)
        action_handler = ActionHandler(self.runtime.logger, self.runtime.utility, self.runtime_context_handler, self.runtime.json_file_handler, self.ext_env_handler,
                                       self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, ext_output_status_handler, process_handler, datetime.datetime.utcnow(), 0)

        self.assertTrue(action_handler.disable() == Constants.ExitCode.HandlerFailed)

        # verify status file
        status_json = ext_output_status_handler.read_file()
        parent_key = Constants.StatusFileFields.status
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_name], "Azure Patch Management")
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_operation], Constants.DISABLING_EXTENSION)
        self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_status], Constants.Status.Error.lower())

        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_update_action_sequence_agent_follows(self):
        """ update sequence: disable on prev version, update on new version, uninstall on prev version, install on new version, enable on new version """
        pass
        # prev_seq_no = 0
        # current_seq_no = 1
        #
        # test_dir = tempfile.mkdtemp()
        # config_folder = os.path.join(test_dir, "config")
        # os.mkdir(config_folder)
        # self.runtime.create_temp_file(config_folder, Constants.CORE_STATE_FILE, content='[test]')
        # self.runtime.create_temp_file(config_folder, Constants.EXT_STATE_FILE, content='[test]')
        # status_folder = os.path.join(test_dir, "status")
        # os.mkdir(status_folder)
        #
        # # prev version context
        # prev_seq_ext_output_status_handler = ExtOutputStatusHandler(self.runtime.logger, self.runtime.utility, self.runtime.json_file_handler, 'test/', prev_seq_no, status_folder)
        # prev_seq_process_handler = ProcessHandler(self.runtime.logger, prev_seq_ext_output_status_handler)
        # prev_seq_action_handler = ActionHandler(self.runtime.logger, self.runtime.utility, self.runtime_context_handler, self.runtime.json_file_handler, self.ext_env_handler, self.ext_config_settings_handler,
        #                                         self.core_state_handler, self.ext_state_handler, prev_seq_ext_output_status_handler, prev_seq_process_handler, datetime.datetime.utcnow(), prev_seq_no)
        #
        # # current/new version context
        # current_seq_ext_output_status_handler = ExtOutputStatusHandler(self.runtime.logger, self.runtime.utility, self.runtime.json_file_handler, 'test/', current_seq_no, status_folder)
        # current_seq_process_handler = ProcessHandler(self.runtime.logger, current_seq_ext_output_status_handler)
        # current_seq_action_handler = ActionHandler(self.runtime.logger, self.runtime.utility, self.runtime_context_handler, self.runtime.json_file_handler, self.ext_env_handler, self.ext_config_settings_handler,
        #                                            self.core_state_handler, self.ext_state_handler, current_seq_ext_output_status_handler, current_seq_process_handler, datetime.datetime.utcnow(), prev_seq_no)
        #
        # # disable on prev version
        # self.assertTrue(prev_seq_action_handler.disable() == Constants.ExitCode.Okay)
        # # verify status file
        # status_json = prev_seq_ext_output_status_handler.read_file()
        # parent_key = Constants.StatusFileFields.status
        # self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_name], "Azure Patch Management")
        # self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_operation], Constants.DISABLING_EXTENSION)
        # self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_status], Constants.Status.Success.lower())
        #
        # # update on new version
        # self.assertTrue(current_seq_action_handler.update() == Constants.ExitCode.Okay)
        # # verify status file
        # status_json = current_seq_ext_output_status_handler.read_file()
        # parent_key = Constants.StatusFileFields.status
        # self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_name], "Azure Patch Management")
        # self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_operation], Constants.UPDATING_EXTENSION)
        # self.assertEqual(status_json[0][parent_key][Constants.StatusFileFields.status_status], Constants.Status.Success.lower())
