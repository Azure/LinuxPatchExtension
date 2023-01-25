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
import os.path
import shutil
import tempfile
import unittest
from extension.src.Constants import Constants
from extension.src.file_handlers.ExtEnvHandler import ExtEnvHandler
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestExtEnvHandler(unittest.TestCase):
    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.runtime = RuntimeComposer()
        self.json_file_handler = self.runtime.json_file_handler
        self.env_settings_fields = Constants.EnvSettingsFields

        self.backup_pathexists = os.path.exists
        os.path.exists = self.mock_os_pathexists

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")
        os.path.exists = self.backup_pathexists

    def mock_os_pathexists(self, path):
        return True

    def test_file_read_success(self):
        ext_env_handler = ExtEnvHandler(self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        self.assertTrue(ext_env_handler.log_folder is not None)
        self.assertEqual(ext_env_handler.log_folder, "mockLog")
        self.assertTrue(ext_env_handler.status_folder is not None)
        self.assertTrue(ext_env_handler.temp_folder is not None)
        self.assertEqual(ext_env_handler.temp_folder, "tmp")

    def test_file_read_failure(self):
        # empty file
        test_dir = tempfile.mkdtemp()
        file_name = "test_handler_env.json"
        self.runtime.create_temp_file(test_dir, file_name, content=None)
        self.assertRaises(Exception, ExtEnvHandler, self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file=file_name, handler_env_file_path=test_dir)
        shutil.rmtree(test_dir)

        # invalid file content
        json_content = [{"key1": "value"}, {"key2": "value2"}]
        test_dir = tempfile.mkdtemp()
        file_name = "test_handler_env.json"
        self.runtime.create_temp_file(test_dir, file_name, str(json_content))
        self.assertRaises(Exception, ExtEnvHandler, self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file=file_name, handler_env_file_path=test_dir)
        shutil.rmtree(test_dir)

        # invalid file content
        json_content = [{}]
        test_dir = tempfile.mkdtemp()
        file_name = "test_handler_env.json"
        self.runtime.create_temp_file(test_dir, file_name, str(json_content))
        self.assertRaises(Exception, ExtEnvHandler, self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file=file_name, handler_env_file_path=test_dir)
        shutil.rmtree(test_dir)

    def test_read_event_folder_preview(self):
        ext_env_settings = [{
            Constants.EnvSettingsFields.version: "1.0",
            Constants.EnvSettingsFields.settings_parent_key: {
                Constants.EnvSettingsFields.log_folder: "testLog",
                Constants.EnvSettingsFields.config_folder: "testConfig",
                Constants.EnvSettingsFields.status_folder: "testStatus",
                Constants.EnvSettingsFields.events_folder_preview: "testEventsPreview"
            }
        }]
        test_dir = tempfile.mkdtemp()
        file_name = Constants.HANDLER_ENVIRONMENT_FILE
        self.runtime.create_temp_file(test_dir, file_name, content=json.dumps(ext_env_settings))
        ext_env_handler = ExtEnvHandler(self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file_path=test_dir)
        self.assertTrue(ext_env_handler.log_folder is not None)
        self.assertEqual(ext_env_handler.events_folder, "testEventsPreview")
        shutil.rmtree(test_dir)

    def test_temp_folder_creation_success(self):
        # Reset os.pathexists that was mocked in setup()
        os.path.exists = self.backup_pathexists

        test_dir = tempfile.mkdtemp()
        ext_env_settings = [{
            Constants.EnvSettingsFields.version: "1.0",
            Constants.EnvSettingsFields.settings_parent_key: {
                Constants.EnvSettingsFields.log_folder: os.path.join(test_dir, "testLog"),
                Constants.EnvSettingsFields.config_folder: os.path.join(test_dir, "testConfig"),
                Constants.EnvSettingsFields.status_folder: os.path.join(test_dir, "testStatus"),
                Constants.EnvSettingsFields.events_folder_preview: os.path.join(test_dir, "testEventsPreview")
            }
        }]
        file_name = Constants.HANDLER_ENVIRONMENT_FILE
        self.runtime.create_temp_file(test_dir, file_name, content=json.dumps(ext_env_settings))
        ext_env_handler = ExtEnvHandler(self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file_path=test_dir)
        self.assertTrue(ext_env_handler.config_folder is not None)
        self.assertTrue(ext_env_handler.temp_folder is not None)
        self.assertEqual(ext_env_handler.temp_folder, os.path.join(test_dir, "tmp"))
        shutil.rmtree(test_dir)

