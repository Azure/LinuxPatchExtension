import os
import shutil
import tempfile
import unittest
from unittest import mock
from src.Constants import Constants
from src.file_handlers.JsonFileHandler import JsonFileHandler
from src.file_handlers.CoreStateHandler import CoreStateHandler
from src.local_loggers.Logger import Logger
from src.Utility import Utility
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestCoreStateHandler(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.logger = Logger()
        self.utility = Utility(self.logger)
        self.json_file_handler = JsonFileHandler(self.logger)
        self.core_state_fields = Constants.CoreStateFields

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def test_file_exists(self):
        core_state_handler = CoreStateHandler(os.path.join(os.path.pardir, "tests", "helpers"), self.json_file_handler)
        self.assertIsNotNone(core_state_handler.read_file())

    @mock.patch('src.file_handlers.JsonFileHandler.time.sleep', autospec=True)
    def test_file_does_not_exists(self, time_sleep):
        core_state_handler = CoreStateHandler(os.path.join(os.path.pardir, "tests", "helper"), self.json_file_handler)
        core_state_json = core_state_handler.read_file()
        self.assertIsNone(core_state_json)
        self.assertFalse(hasattr(core_state_json, self.core_state_fields.number))
        self.assertFalse(hasattr(core_state_json, self.core_state_fields.last_heartbeat))
        self.assertEqual(time_sleep.call_count, 5)

    def test_file_empty(self):
        core_state_handler = CoreStateHandler(os.path.join(os.path.pardir, "tests", "helpers"), self.json_file_handler)
        with mock.patch('tests.TestCoreStateHandler.JsonFileHandler.get_json_file_content', return_value=None, autospec=True):
            core_state_json = core_state_handler.read_file()
            self.assertIsNone(core_state_json)
            self.assertFalse(hasattr(core_state_json, self.core_state_fields.number))

        with mock.patch('tests.TestCoreStateHandler.JsonFileHandler.get_json_file_content', return_value={}, autospec=True):
            core_state_json = core_state_handler.read_file()
            self.assertTrue(hasattr(core_state_json, self.core_state_fields.number))
            self.assertTrue(hasattr(core_state_json, self.core_state_fields.action))
            self.assertIsNone(core_state_json.number)
            self.assertIsNone(core_state_json.action)

    @mock.patch('tests.TestCoreStateHandler.JsonFileHandler.get_json_file_content', autospec=True)
    def test_key_not_in_file(self, mock_core_state_json):
        mock_core_state_json.return_value = None
        parent_key = self.core_state_fields.parent_key
        core_state_json = {
            parent_key: {
                "test_no": 1
            }
        }
        core_state_handler = CoreStateHandler("test_path", self.json_file_handler)
        core_state_handler.read_file()
        seq_no = self.core_state_fields.number
        self.assertIsNone(core_state_handler.json_file_handler.get_json_config_value_safely(core_state_json, seq_no, parent_key, False))

    def test_success_file_read(self):
        core_state_handler = CoreStateHandler(os.path.join(os.path.pardir, "tests", "helpers"), self.json_file_handler)
        core_state_json = core_state_handler.read_file()
        self.assertIsNotNone(core_state_json.number)
        self.assertIsNotNone(core_state_json.completed)
        self.assertEqual(core_state_json.action, "Assessment")
        self.assertEqual(core_state_json.number, 1234)

    def test_delete_file_failure(self):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file_path = os.path.join(test_dir, Constants.EXT_STATE_FILE)
        # create a file
        test_file_handler = open(file_path, 'w')
        test_file_handler.close()
        # delete file
        core_state_handler = CoreStateHandler("test", self.json_file_handler)
        self.assertRaises(Exception, self.utility.delete_file, core_state_handler.dir_path, core_state_handler.file)
        self.assertTrue(os.path.exists(file_path))
        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_delete_file_success(self):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file_path = os.path.join(test_dir, Constants.CORE_STATE_FILE)
        # create a file
        test_file_handler = open(file_path, 'w')
        test_file_handler.close()
        # delete file
        core_state_handler = CoreStateHandler(test_dir, self.json_file_handler)
        self.utility.delete_file(core_state_handler.dir_path, core_state_handler.file)
        self.assertFalse(os.path.exists(file_path))
        # Remove the directory after the test
        shutil.rmtree(test_dir)





