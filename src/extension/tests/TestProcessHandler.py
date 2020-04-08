import os
import unittest
from unittest.mock import patch
from src.Constants import Constants
from src.file_handlers.ExtOutputStatusHandler import ExtOutputStatusHandler
from src.file_handlers.JsonFileHandler import JsonFileHandler
from src.file_handlers.ExtConfigSettingsHandler import ExtConfigSettingsHandler
from src.file_handlers.ExtEnvHandler import ExtEnvHandler
from src.local_loggers.Logger import Logger
from src.ProcessHandler import ProcessHandler
from src.Utility import Utility
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestProcessHandler(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.logger = Logger()
        self.utility = Utility(self.logger)
        self.json_file_handler = JsonFileHandler(self.logger)
        seq_no = 1234
        dir_path = os.path.join(os.path.pardir, "tests", "helpers")
        self.ext_output_status_handler = ExtOutputStatusHandler(self.logger, self.utility, self.json_file_handler, "test.log", seq_no, dir_path)

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def test_get_public_config_settings(self):
        ext_config_settings_handler = ExtConfigSettingsHandler(self.logger, self.json_file_handler, os.path.join(os.path.pardir, "tests", "helpers"))
        seq_no = "1234"
        config_settings = ext_config_settings_handler.read_file(seq_no)
        process_handler = ProcessHandler(self.logger, self.ext_output_status_handler)
        public_config_settings = process_handler.get_public_config_settings(config_settings)
        self.assertIsNotNone(public_config_settings)
        self.assertEqual(public_config_settings.get(Constants.ConfigPublicSettingsFields.operation), "Deployment")

    def test_get_env_settings(self):
        handler_env_file_path = os.path.join(os.path.pardir, "tests", "helpers")
        ext_env_handler = ExtEnvHandler(self.json_file_handler, handler_env_file_path=handler_env_file_path)
        process_handler = ProcessHandler(self.logger, self.ext_output_status_handler)
        env_settings = process_handler.get_env_settings(ext_env_handler)
        self.assertIsNotNone(env_settings)
        self.assertEqual(env_settings.get(Constants.EnvSettingsFields.log_folder), "mockLog")

    @patch('src.ProcessHandler.os.kill', autospec=True)
    @patch('tests.TestProcessHandler.ProcessHandler.is_process_running', autospec=True, return_value=True)
    def test_kill_process(self, is_process_running, os_kill):
        pid = 123
        os_kill.side_effect = OSError
        process_handler = ProcessHandler(self.logger, self.ext_output_status_handler)
        self.assertRaises(OSError, process_handler.kill_process, pid)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestProcessHandler)
    unittest.TextTestRunner(verbosity=2).run(SUITE)

