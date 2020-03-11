import os.path
import unittest
from unittest import mock
from src.Constants import Constants
from src.file_handlers.JsonFileHandler import JsonFileHandler
from src.file_handlers.ExtEnvHandler import ExtEnvHandler
from src.local_loggers.Logger import Logger
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestExtEnvHandler(unittest.TestCase):
    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.logger = Logger()
        self.json_file_handler = JsonFileHandler(self.logger)
        self.env_settings_fields = Constants.EnvSettingsFields

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def test_file_read_success(self):
        ext_env_handler = ExtEnvHandler(self.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        self.assertIsNotNone(ext_env_handler.log_folder)
        self.assertEqual(ext_env_handler.log_folder, "mockLog")
        self.assertIsNotNone(ext_env_handler.status_folder)

    @mock.patch('tests.TestExtEnvHandler.JsonFileHandler.get_json_file_content', autospec=True)
    def test_file_read_failure(self, mock_response):
        mock_response.return_value = None
        handler_env_file_path = os.path.join(os.path.pardir, "tests", "helpers")
        ext_env_handler = ExtEnvHandler(self.json_file_handler, handler_env_file_path=handler_env_file_path)
        self.assertIsNone(ext_env_handler.handler_environment_json)
        self.assertFalse(hasattr(ext_env_handler, 'config_folder'))
        self.assertFalse(hasattr(ext_env_handler, 'log_folder'))

        mock_response.return_value = [{"key1": "value"}, {"key2": "value2"}]
        self.assertRaises(Exception, ExtEnvHandler, self.json_file_handler, handler_env_file_path=handler_env_file_path)

        mock_response.return_value = [{}]
        self.assertRaises(Exception, ExtEnvHandler, self.json_file_handler, handler_env_file_path=handler_env_file_path)