import json
import os
import shutil
import tempfile
import unittest
from unittest import mock
from src.Constants import Constants
from src.file_handlers.JsonFileHandler import JsonFileHandler
from src.file_handlers.ExtOutputStatusHandler import ExtOutputStatusHandler
from src.local_loggers.Logger import Logger
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestExtOutputStatusHandler(unittest.TestCase):
    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.logger = Logger()
        self.json_file_handler = JsonFileHandler(self.logger)
        self.status_file_fields = Constants.StatusFileFields
        self.status = Constants.Status

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def test_create_status_file(self):
        file_name = "test"
        dir_path = tempfile.mkdtemp()
        operation = "Assessment"
        ext_status_handler = ExtOutputStatusHandler(self.logger, self.json_file_handler)
        ext_status_handler.write_status_file(file_name, dir_path, operation, [], self.status.Transitioning.lower())

        with open(dir_path + "\\" + file_name + ext_status_handler.file_ext) as status_file:
            content = json.load(status_file)
            parent_key = self.status_file_fields.status
            self.assertIsNotNone(content)
            self.assertEqual(content[0][parent_key][self.status_file_fields.status_name], "Azure Patch Management")
            self.assertEqual(content[0][parent_key][self.status_file_fields.status_operation], operation)
            self.assertEqual(content[0][parent_key][self.status_file_fields.status_status], self.status.Transitioning.lower())
        shutil.rmtree(dir_path)

    def test_read_file(self):
        file_name = "test"
        dir_path = tempfile.mkdtemp()
        operation = "Assessment"

        ext_status_handler = ExtOutputStatusHandler(self.logger, self.json_file_handler)
        ext_status_handler.write_status_file(file_name, dir_path, operation, [], self.status.Transitioning.lower())
        status_json = ext_status_handler.read_file(file_name, dir_path)
        parent_key = self.status_file_fields.status
        self.assertEqual(status_json[0][parent_key][self.status_file_fields.status_name], "Azure Patch Management")
        self.assertEqual(status_json[0][parent_key][self.status_file_fields.status_operation], operation)
        self.assertEqual(status_json[0][parent_key][self.status_file_fields.status_status], self.status.Transitioning.lower())
        shutil.rmtree(dir_path)

    @mock.patch('src.file_handlers.JsonFileHandler.time.sleep', autospec=True)
    def test_update_file(self, time_sleep):
        file_name = "test"
        dir_path = tempfile.mkdtemp()
        operation = "Assessment"

        ext_status_handler = ExtOutputStatusHandler(self.logger, self.json_file_handler)
        ext_status_handler.write_status_file(file_name, dir_path, operation, [], self.status.Success.lower())
        status_json = ext_status_handler.read_file(file_name, dir_path)
        prev_timestamp = status_json[0][self.status_file_fields.timestamp_utc]
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
        updated_status_json = ext_status_handler.read_file(file_name, dir_path)
        self.assertEqual(updated_status_json[0][self.status_file_fields.status][self.status_file_fields.status_status], self.status.Transitioning.lower())
        shutil.rmtree(dir_path)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestExtOutputStatusHandler)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
