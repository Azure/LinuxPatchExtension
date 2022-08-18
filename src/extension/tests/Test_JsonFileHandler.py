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
import shutil
import tempfile
import unittest
from extension.src.Constants import Constants
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestJsonFileHandler(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        runtime = RuntimeComposer()
        self.json_file_handler = runtime.json_file_handler

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def mock_json_dump_with_exception(self):
        raise Exception

    def test_get_json_file_content_success(self):
        file = Constants.EXT_STATE_FILE
        dir_path = os.path.join(os.path.pardir, "tests", "helpers")
        json_content = self.json_file_handler.get_json_file_content(file, dir_path, raise_if_not_found=True)
        self.assertTrue(json_content is not None)

    def test_get_json_file_content_failure(self):
        file = Constants.EXT_STATE_FILE
        dir_path = os.path.join(os.path.pardir, "tests", "helper")
        self.assertRaises(Exception, self.json_file_handler.get_json_file_content, file, dir_path, raise_if_not_found=True)

    def test_create_file_success(self):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file = "test.json"
        content = {'testKey1': 'testVal1',
                   'testKey2': {'testsubKey1': 'testsubVal1'},
                   'testKey3': [{'testsubKey2': 'testsubVal2'}]}
        # create a file
        self.json_file_handler.write_to_json_file(test_dir, file, content)
        self.assertTrue(os.path.exists(os.path.join(test_dir, "test.json")))
        json_content = self.json_file_handler.get_json_file_content(file, test_dir, raise_if_not_found=False)
        self.assertTrue('testKey1' in json_content)
        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_create_file_failure(self):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file = "test.json"
        content = {'testKey1': 'testVal1',
                   'testKey2': {'testsubKey1': 'testsubVal1'},
                   'testKey3': [{'testsubKey2': 'testsubVal2'}]}
        self.assertRaises(Exception, self.json_file_handler.write_to_json_file, "test_dir", file, content)
        json_dump_backup = json.dump
        json.dump = self.mock_json_dump_with_exception
        self.assertRaises(Exception, self.json_file_handler.write_to_json_file, test_dir, file, content)
        json.dump = json_dump_backup
        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_get_json_config_value_safely(self):
        content = {'testKey1': 'testVal1',
                   'testKey2': {'testsubKey1': 'testsubVal1'},
                   'testKey3': [{'testsubKey2': 'testsubVal2'}]}

        self.assertTrue(self.json_file_handler.get_json_config_value_safely(None, 'testsubKey1', 'testKey2', raise_if_not_found=True) is None)
        self.assertEqual(self.json_file_handler.get_json_config_value_safely(content, 'testsubKey1', 'testKey2', raise_if_not_found=True), 'testsubVal1')
        self.assertRaises(Exception, self.json_file_handler.get_json_config_value_safely, content, 'testsubKey1', 'testKey3', raise_if_not_found=True)
        self.assertRaises(Exception, self.json_file_handler.get_json_config_value_safely, content, 'testsubKey2', 'testKey3', raise_if_not_found=True)
        self.assertTrue(self.json_file_handler.get_json_config_value_safely(content, 'testsubKey2', 'testKey3', raise_if_not_found=False) is None)
        self.assertRaises(Exception, self.json_file_handler.get_json_config_value_safely, content, 'testKey1', None, raise_if_not_found=True)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestJsonFileHandler)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
