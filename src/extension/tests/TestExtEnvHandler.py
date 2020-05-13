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

import os.path
import shutil
import tempfile
import unittest
from src.Constants import Constants
from src.file_handlers.ExtEnvHandler import ExtEnvHandler
from tests.helpers.RuntimeComposer import RuntimeComposer
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestExtEnvHandler(unittest.TestCase):
    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        tests_setup = RuntimeComposer()
        self.json_file_handler = tests_setup.json_file_handler
        self.env_settings_fields = Constants.EnvSettingsFields

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def test_file_read_success(self):
        ext_env_handler = ExtEnvHandler(self.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        self.assertTrue(ext_env_handler.log_folder is not None)
        self.assertEqual(ext_env_handler.log_folder, "mockLog")
        self.assertTrue(ext_env_handler.status_folder is not None)

    def test_file_read_failure(self):
        # empty file
        test_dir = tempfile.mkdtemp()
        file_name = "test_handler_env.json"
        with open(os.path.join(test_dir, file_name), 'w') as f:
            f.close()
        self.assertRaises(Exception, ExtEnvHandler, self.json_file_handler, handler_env_file=file_name, handler_env_file_path=test_dir)
        shutil.rmtree(test_dir)

        # invalid file content
        json_content = [{"key1": "value"}, {"key2": "value2"}]
        test_dir = tempfile.mkdtemp()
        file_name = "test_handler_env.json"
        with open(os.path.join(test_dir, file_name), 'w') as f:
            f.write(str(json_content))
            f.close()
        self.assertRaises(Exception, ExtEnvHandler, self.json_file_handler, handler_env_file=file_name, handler_env_file_path=test_dir)
        shutil.rmtree(test_dir)

        # invalid file content
        json_content = [{}]
        test_dir = tempfile.mkdtemp()
        file_name = "test_handler_env.json"
        with open(os.path.join(test_dir, file_name), 'w') as f:
            f.write(str(json_content))
            f.close()
        self.assertRaises(Exception, ExtEnvHandler, self.json_file_handler, handler_env_file=file_name, handler_env_file_path=test_dir)
        shutil.rmtree(test_dir)
