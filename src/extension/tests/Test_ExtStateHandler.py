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
import os
import shutil
import tempfile
import unittest
from extension.src.Constants import Constants
from extension.src.file_handlers.ExtStateHandler import ExtStateHandler
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestExtStateHandler(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.runtime = RuntimeComposer()
        self.logger = self.runtime.logger
        self.utility = self.runtime.utility
        self.json_file_handler = self.runtime.json_file_handler
        self.ext_state_fields = Constants.ExtStateFields

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def test_create_file(self):
        test_dir = tempfile.mkdtemp()
        ext_state_handler = ExtStateHandler(test_dir, self.utility, self.json_file_handler)
        ext_state_handler.create_file(1, "Assessment", datetime.datetime.utcnow())
        self.assertTrue(os.path.exists(os.path.join(test_dir, Constants.EXT_STATE_FILE)))
        self.utility.delete_file(ext_state_handler.dir_path, ext_state_handler.file)
        shutil.rmtree(test_dir)

    def test_read_file(self):
        ext_state_handler = ExtStateHandler(os.path.join(os.path.pardir, "tests", "helpers"), self.utility, self.json_file_handler)
        ext_state_values = ext_state_handler.read_file()
        self.assertTrue(ext_state_values.__getattribute__(self.ext_state_fields.ext_seq_number) is not None)
        self.assertEqual(ext_state_values.__getattribute__(self.ext_state_fields.ext_seq_number), 1234)
        self.assertTrue(ext_state_values.__getattribute__(self.ext_state_fields.ext_seq_achieve_enable_by) is not None)
        self.assertTrue(ext_state_values.__getattribute__(self.ext_state_fields.ext_seq_operation) is not None)
        self.assertEqual(ext_state_values.__getattribute__(self.ext_state_fields.ext_seq_operation), "Installation")

    def test_read_file_no_content(self):
        ext_state_handler = ExtStateHandler(os.path.join(os.path.pardir, "tests", "helper"), self.utility, self.json_file_handler)
        ext_state_values = ext_state_handler.read_file()
        self.assertTrue(ext_state_values is not None)
        self.assertTrue(ext_state_values.__getattribute__(self.ext_state_fields.ext_seq_number) is None)
        self.assertTrue(ext_state_values.__getattribute__(self.ext_state_fields.ext_seq_achieve_enable_by) is None)
        self.assertTrue(ext_state_values.__getattribute__(self.ext_state_fields.ext_seq_operation) is None)

    def test_delete_file_failure(self):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file_name = Constants.EXT_STATE_FILE
        file_path = os.path.join(test_dir, file_name)
        # create a file
        self.runtime.create_temp_file(test_dir, file_name, content=None)
        # delete file
        ext_state_handler = ExtStateHandler('test', self.utility, self.json_file_handler)
        self.assertRaises(Exception, self.utility.delete_file, ext_state_handler.dir_path, ext_state_handler.file)
        self.assertTrue(os.path.exists(file_path))
        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_delete_file_success(self):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file_name = Constants.EXT_STATE_FILE
        file_path = os.path.join(test_dir, file_name)
        # create a file
        self.runtime.create_temp_file(test_dir, file_name, content=None)
        # delete file
        ext_state_handler = ExtStateHandler(test_dir, self.utility, self.json_file_handler)
        self.utility.delete_file(ext_state_handler.dir_path, ext_state_handler.file)
        self.assertFalse(os.path.exists(file_path))
        # Remove the directory after the test
        shutil.rmtree(test_dir)

