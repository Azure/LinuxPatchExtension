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
from extension.src.Constants import Constants
from extension.src.file_handlers.CoreStateHandler import CoreStateHandler
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestCoreStateHandler(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup TestCoreStateHandler runner -----------------")
        self.runtime = RuntimeComposer()
        self.utility = self.runtime.utility
        self.json_file_handler = self.runtime.json_file_handler
        self.core_state_fields = Constants.CoreStateFields

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down TestCoreStateHandler runner -----------------")

    def test_file_exists(self):
        core_state_handler = CoreStateHandler(os.path.join(os.path.pardir, "tests", "helpers"), self.json_file_handler)
        self.assertTrue(core_state_handler.read_file() is not None)

    def test_file_does_not_exists(self):
        core_state_handler = CoreStateHandler(os.path.join(os.path.pardir, "tests", "helper"), self.json_file_handler)
        core_state_json = core_state_handler.read_file()
        self.assertTrue(core_state_handler.read_file() is None)
        self.assertFalse(hasattr(core_state_json, self.core_state_fields.number))
        self.assertFalse(hasattr(core_state_json, self.core_state_fields.last_heartbeat))

    def test_file_empty(self):
        test_dir = tempfile.mkdtemp()
        file_name = Constants.CORE_STATE_FILE

        # test on empty file
        self.runtime.create_temp_file(test_dir, file_name, content=None)
        core_state_handler = CoreStateHandler(os.path.join(test_dir), self.json_file_handler)
        core_state_json = core_state_handler.read_file()
        self.assertTrue(core_state_json is None)
        self.assertFalse(hasattr(core_state_json, self.core_state_fields.number))

        # test on file with empty JSON
        self.runtime.create_temp_file(test_dir, file_name, "{}")
        core_state_json = core_state_handler.read_file()
        self.assertTrue(hasattr(core_state_json, self.core_state_fields.number))
        self.assertTrue(hasattr(core_state_json, self.core_state_fields.action))
        self.assertTrue(core_state_json.number is None)
        self.assertTrue(core_state_json.action is None)

        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_key_not_in_file(self):
        parent_key = self.core_state_fields.parent_key
        core_state_json = {
            parent_key: {
                "test_no": 1
            }
        }
        test_dir = tempfile.mkdtemp()
        file_name = Constants.CORE_STATE_FILE
        self.runtime.create_temp_file(test_dir, file_name, "{}")
        core_state_handler = CoreStateHandler(os.path.join(test_dir), self.json_file_handler)
        core_state_handler.read_file()
        seq_no = self.core_state_fields.number
        self.assertTrue(core_state_handler.json_file_handler.get_json_config_value_safely(core_state_json, seq_no, parent_key, False) is None)
        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_success_file_read(self):
        core_state_handler = CoreStateHandler(os.path.join(os.path.pardir, "tests", "helpers"), self.json_file_handler)
        core_state_json = core_state_handler.read_file()
        self.assertTrue(core_state_json.number is not None)
        self.assertTrue(core_state_json.completed is not None)
        self.assertEqual(core_state_json.action, "Assessment")
        self.assertEqual(core_state_json.number, 1234)

    def test_delete_file_failure(self):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file_name = Constants.EXT_STATE_FILE
        file_path = os.path.join(test_dir, file_name)
        # create a file
        self.runtime.create_temp_file(test_dir, file_name, content=None)
        # delete file
        core_state_handler = CoreStateHandler("test", self.json_file_handler)
        self.assertRaises(Exception, self.utility.delete_file, core_state_handler.dir_path, core_state_handler.file)
        self.assertTrue(os.path.exists(file_path))
        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_delete_file_success(self):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file_name = Constants.CORE_STATE_FILE
        file_path = os.path.join(test_dir, file_name)
        # create a file
        self.runtime.create_temp_file(test_dir, file_name, content=None)
        # delete file
        core_state_handler = CoreStateHandler(test_dir, self.json_file_handler)
        self.utility.delete_file(core_state_handler.dir_path, core_state_handler.file)
        self.assertFalse(os.path.exists(file_path))
        # Remove the directory after the test
        shutil.rmtree(test_dir)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestCoreStateHandler)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
