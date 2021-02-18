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
        runtime_context_handler = RuntimeContextHandler(self.runtime.logger)
        ext_env_handler = ExtEnvHandler(self.runtime.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        ext_config_settings_handler = ExtConfigSettingsHandler(self.runtime.logger, self.runtime.json_file_handler, ext_env_handler.config_folder)
        core_state_handler = CoreStateHandler(ext_env_handler.config_folder, self.runtime.json_file_handler)
        ext_state_handler = ExtStateHandler(ext_env_handler.config_folder, self.runtime.utility, self.runtime.json_file_handler)
        ext_output_status_handler = ExtOutputStatusHandler(self.runtime.logger, self.runtime.utility, self.runtime.json_file_handler, ext_env_handler.status_folder)
        process_handler = ProcessHandler(self.runtime.logger, ext_output_status_handler)
        self.action_handler = ActionHandler(self.runtime.logger, self.runtime.utility, runtime_context_handler, self.runtime.json_file_handler, ext_env_handler,
                                            ext_config_settings_handler, core_state_handler, ext_state_handler, ext_output_status_handler, process_handler, "2020-09-02T13:40:54.8862542Z")

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def mock_get_all_versions(self, extension_pardir):
        return [extension_pardir + '/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.3',
                extension_pardir + '/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.5',
                extension_pardir + '/Microsoft.CPlat.Core.LinuxPatchExtension-1.1.9']

    def mock_get_all_versions_exception(self, extension_pardir):
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

    def test_update_command_success(self):
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
        self.action_handler.ext_env_handler.config_folder = new_version_config_folder
        self.assertTrue(self.action_handler.update() == Constants.ExitCode.Okay)
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.CORE_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.EXT_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, 'backup.bak')))
        self.assertFalse(os.path.exists(os.path.join(new_version_config_folder, 'test.txt')))
        # Remove the directory after the test
        shutil.rmtree(test_dir)

        # testing with versions 1.6.99 and 1.6.100
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        # create extension dir for the latest and other extension versions, to be used in the test
        latest_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100'
        new_version_config_folder = self.create_latest_extension_dir(latest_extension_version, test_dir)
        previous_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.6.99'
        previous_version_config_folder = self.create_previous_extension_version(previous_extension_version, test_dir)
        self.action_handler.ext_env_handler.config_folder = new_version_config_folder
        self.assertTrue(self.action_handler.update() == Constants.ExitCode.Okay)
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.CORE_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.EXT_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, 'backup.bak')))
        self.assertFalse(os.path.exists(os.path.join(new_version_config_folder, 'test.txt')))
        # Remove the directory after the test
        shutil.rmtree(test_dir)

        # testing with versions 1.4.897 and 1.5.23
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        # create extension dir for the latest and other extension versions, to be used in the test
        latest_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.5.23'
        new_version_config_folder = self.create_latest_extension_dir(latest_extension_version, test_dir)
        previous_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.4.897'
        previous_version_config_folder = self.create_previous_extension_version(previous_extension_version, test_dir)
        self.action_handler.ext_env_handler.config_folder = new_version_config_folder
        self.assertTrue(self.action_handler.update() == Constants.ExitCode.Okay)
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.CORE_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.EXT_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, 'backup.bak')))
        self.assertFalse(os.path.exists(os.path.join(new_version_config_folder, 'test.txt')))
        # Remove the directory after the test
        shutil.rmtree(test_dir)

        # testing with versions 1.0.0 and 2.0.00
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        # create extension dir for the latest and other extension versions, to be used in the test
        latest_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-2.0.00'
        new_version_config_folder = self.create_latest_extension_dir(latest_extension_version, test_dir)
        previous_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.0.0'
        previous_version_config_folder = self.create_previous_extension_version(previous_extension_version, test_dir)
        self.action_handler.ext_env_handler.config_folder = new_version_config_folder
        self.assertTrue(self.action_handler.update() == Constants.ExitCode.Okay)
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.CORE_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, Constants.EXT_STATE_FILE)))
        self.assertTrue(os.path.exists(os.path.join(new_version_config_folder, 'backup.bak')))
        self.assertFalse(os.path.exists(os.path.join(new_version_config_folder, 'test.txt')))
        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_update_command_fail(self):
        # other versions not found
        self.action_handler.ext_env_handler.config_folder = '/test/config'
        self.assertTrue(self.action_handler.update() == Constants.ExitCode.HandlerFailed)

        # path to previous version artifacts not found
        # Create a temporary directory and dir for the latest version
        test_dir = tempfile.mkdtemp()
        latest_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.2.5'
        os.mkdir(os.path.join(test_dir, latest_extension_version))
        new_version_config_folder = os.path.join(test_dir, latest_extension_version, 'config')
        os.mkdir(new_version_config_folder)
        self.action_handler.ext_env_handler.config_folder = new_version_config_folder
        self.action_handler.get_all_versions = self.mock_get_all_versions
        self.assertTrue(self.action_handler.update() == Constants.ExitCode.HandlerFailed)
        # Remove the directory after the test
        shutil.rmtree(test_dir)

        # exception path
        test_dir = tempfile.mkdtemp()
        latest_extension_version = 'Microsoft.CPlat.Core.LinuxPatchExtension-1.2.5'
        os.mkdir(os.path.join(test_dir, latest_extension_version))
        new_version_config_folder = os.path.join(test_dir, latest_extension_version, 'config')
        os.mkdir(new_version_config_folder)
        self.action_handler.ext_env_handler.config_folder = new_version_config_folder
        self.action_handler.get_all_versions = self.mock_get_all_versions_exception
        self.assertTrue(self.action_handler.update() == Constants.ExitCode.HandlerFailed)
        # Remove the directory after the test
        shutil.rmtree(test_dir)

