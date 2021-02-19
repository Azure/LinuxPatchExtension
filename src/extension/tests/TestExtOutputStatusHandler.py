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
from extension.src.file_handlers.ExtOutputStatusHandler import ExtOutputStatusHandler
from extension.src.local_loggers.FileLogger import FileLogger
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestExtOutputStatusHandler(unittest.TestCase):
    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.runtime = RuntimeComposer()
        self.logger = self.runtime.logger
        self.telemetry_writer = self.runtime.telemetry_writer
        self.utility = self.runtime.utility
        self.json_file_handler = self.runtime.json_file_handler
        self.status_file_fields = Constants.StatusFileFields
        self.status = Constants.Status

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def test_create_status_file(self):
        file_name = "test"
        dir_path = tempfile.mkdtemp()
        operation = "Assessment"
        ext_status_handler = ExtOutputStatusHandler(self.logger, self.telemetry_writer, self.utility, self.json_file_handler, dir_path)
        ext_status_handler.write_status_file(operation, file_name, self.status.Transitioning.lower())

        with open(dir_path + "\\" + file_name + ext_status_handler.file_ext) as status_file:
            content = json.load(status_file)
            parent_key = self.status_file_fields.status
            self.assertTrue(content is not None)
            self.assertEqual(content[0][parent_key][self.status_file_fields.status_name], "Azure Patch Management")
            self.assertEqual(content[0][parent_key][self.status_file_fields.status_operation], operation)
            self.assertEqual(content[0][parent_key][self.status_file_fields.status_status], self.status.Transitioning.lower())
        shutil.rmtree(dir_path)

    def test_read_file(self):
        file_name = "test"
        dir_path = tempfile.mkdtemp()
        operation = "Assessment"

        ext_output_status_handler = ExtOutputStatusHandler(self.logger, self.telemetry_writer, self.utility, self.json_file_handler, dir_path)
        ext_output_status_handler.write_status_file(operation, file_name, self.status.Transitioning.lower())
        status_json = ext_output_status_handler.read_file(file_name)
        parent_key = self.status_file_fields.status
        self.assertEqual(status_json[0][parent_key][self.status_file_fields.status_name], "Azure Patch Management")
        self.assertEqual(status_json[0][parent_key][self.status_file_fields.status_operation], operation)
        self.assertEqual(status_json[0][parent_key][self.status_file_fields.status_status], self.status.Transitioning.lower())
        shutil.rmtree(dir_path)

    def test_update_file(self):
        file_name = "test"
        dir_path = tempfile.mkdtemp()
        operation = "Assessment"

        ext_status_handler = ExtOutputStatusHandler(self.logger, self.telemetry_writer, self.utility, self.json_file_handler, dir_path)
        ext_status_handler.write_status_file(operation, file_name, self.status.Success.lower())
        stat_file_name = os.stat(os.path.join(dir_path, file_name + ".status"))
        prev_modified_time = stat_file_name.st_mtime

        ext_status_handler.update_file("test1", dir_path)
        stat_file_name = os.stat(os.path.join(dir_path, file_name + ".status"))
        modified_time = stat_file_name.st_mtime
        self.assertEqual(prev_modified_time, modified_time)

        ext_status_handler.update_file(file_name, dir_path)
        stat_file_name = os.stat(os.path.join(dir_path, file_name + ".status"))
        modified_time = stat_file_name.st_mtime
        self.assertNotEqual(prev_modified_time, modified_time)
        updated_status_json = ext_status_handler.read_file(file_name)
        self.assertEqual(updated_status_json[0][self.status_file_fields.status][self.status_file_fields.status_status], self.status.Transitioning.lower())
        shutil.rmtree(dir_path)

    def test_add_error_to_status(self):
        file_name = "test"
        dir_path = tempfile.mkdtemp()
        ext_output_status_handler = ExtOutputStatusHandler(self.logger, self.telemetry_writer, self.utility, self.json_file_handler, dir_path)
        ext_output_status_handler.set_current_operation(Constants.NOOPERATION)
        self.logger.file_logger = FileLogger(dir_path, "test.log")
        ext_output_status_handler.read_file(file_name)
        # Unexpected input
        self.assertTrue(ext_output_status_handler.add_error_to_status(None) is None)

        ext_output_status_handler.add_error_to_status("Adding test exception", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        ext_output_status_handler.set_nooperation_substatus_json(Constants.NOOPERATION, activity_id="", start_time="", seq_no=file_name, status=self.status.Success.lower())
        updated_status_json = ext_output_status_handler.read_file(file_name)
        self.assertEqual(updated_status_json[0][self.status_file_fields.status][self.status_file_fields.status_substatus][0][self.status_file_fields.status_name], Constants.PATCH_NOOPERATION_SUMMARY)
        self.assertNotEqual(json.loads(updated_status_json[0]["status"]["substatus"][0]["formattedMessage"]["message"])["errors"], None)
        self.assertEqual(json.loads(updated_status_json[0]["status"]["substatus"][0]["formattedMessage"]["message"])["errors"]["code"], 1)
        self.assertEqual(json.loads(updated_status_json[0]["status"]["substatus"][0]["formattedMessage"]["message"])["errors"]["details"][0]["code"], Constants.PatchOperationErrorCodes.DEFAULT_ERROR)

        ext_output_status_handler.add_error_to_status("exception1", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        ext_output_status_handler.add_error_to_status("exception2", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        ext_output_status_handler.add_error_to_status("exception3", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        ext_output_status_handler.add_error_to_status("exception4", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        ext_output_status_handler.add_error_to_status("exception5", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        ext_output_status_handler.add_error_to_status("exception6", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        ext_output_status_handler.set_nooperation_substatus_json(Constants.NOOPERATION, activity_id="", start_time="", seq_no=file_name, status=self.status.Success.lower())
        updated_status_json = ext_output_status_handler.read_file(file_name)
        self.assertEqual(updated_status_json[0][self.status_file_fields.status][self.status_file_fields.status_substatus][0][self.status_file_fields.status_name], Constants.PATCH_NOOPERATION_SUMMARY)
        self.assertNotEqual(json.loads(updated_status_json[0]["status"]["substatus"][0]["formattedMessage"]["message"])["errors"], None)
        self.assertEqual(json.loads(updated_status_json[0]["status"]["substatus"][0]["formattedMessage"]["message"])["errors"]["code"], 1)
        self.assertTrue(len(json.loads(updated_status_json[0]["status"]["substatus"][0]["formattedMessage"]["message"])["errors"]["details"]), 5)
        self.logger.file_logger.close()
        shutil.rmtree(dir_path)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestExtOutputStatusHandler)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
