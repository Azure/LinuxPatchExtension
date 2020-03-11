import os
import unittest
from unittest import mock
from unittest.mock import patch
from src.InstallCommandHandler import InstallCommandHandler
from src.file_handlers.ExtEnvHandler import ExtEnvHandler
from src.file_handlers.JsonFileHandler import JsonFileHandler
from src.local_loggers.Logger import Logger
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestInstallCommandHandler(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.logger = Logger()
        self.json_file_handler = JsonFileHandler(self.logger)

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    @patch('tests.TestInstallCommandHandler.JsonFileHandler.get_json_file_content')
    def test_validate_os_type_is_linux(self, mock_ext_env_handler):
        mock_ext_env_handler.return_value = None
        ext_env_handler = ExtEnvHandler(self.json_file_handler)
        install_command_handler = InstallCommandHandler(self.logger, ext_env_handler)
        with mock.patch('src.InstallCommandHandler.sys.platform', 'linux'):
            self.assertTrue(install_command_handler.validate_os_type())

    @patch('tests.TestInstallCommandHandler.JsonFileHandler.get_json_file_content')
    def test_validate_os_type_not_linux(self, mock_ext_env_handler):
        mock_ext_env_handler.return_value = None
        ext_env_handler = ExtEnvHandler(self.json_file_handler)
        install_command_handler = InstallCommandHandler(self.logger, ext_env_handler)
        with mock.patch('src.InstallCommandHandler.sys.platform', 'win32'):
            self.assertRaises(Exception, install_command_handler.validate_os_type)

    def test_validate_environment(self):
        config_type = 'handlerEnvironment'

        # file has no content
        handler_environment = None
        with mock.patch('tests.TestInstallCommandHandler.JsonFileHandler.get_json_file_content', return_value=handler_environment):
            ext_env_handler = ExtEnvHandler(self.json_file_handler)
            install_command_handler = InstallCommandHandler(self.logger, ext_env_handler)
            self.assertRaises(Exception, install_command_handler.validate_environment)

        # Validating datatype for fields in HandlerEnvironment
        handler_environment = []
        handler_environment_dict = {}
        handler_environment.append(handler_environment_dict)
        install_command_handler = InstallCommandHandler(self.logger, handler_environment)
        self.verify_key(handler_environment[0], 'version', 1.0, 'abc', True, Exception, install_command_handler.validate_environment)
        self.verify_key(handler_environment[0], 'version', 1.0, '', True, Exception, install_command_handler.validate_environment)
        self.verify_key(handler_environment[0], 'handlerEnvironment', {}, 'abc', True, Exception, install_command_handler.validate_environment)
        self.verify_key(handler_environment[0][config_type], 'logFolder', 'test', 1.0, True, Exception, install_command_handler.validate_environment)
        self.verify_key(handler_environment[0][config_type], 'configFolder', 'test', 1.0, True, Exception, install_command_handler.validate_environment)
        self.verify_key(handler_environment[0][config_type], 'statusFolder', 'test', 1.0, True, Exception, install_command_handler.validate_environment)

        # Validating HandlerEnvironment.json file
        ext_env_handler = ExtEnvHandler(self.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        install_command_handler = InstallCommandHandler(self.logger, ext_env_handler)
        install_command_handler.validate_environment()

    def verify_key(self, config_type, key, expected_value, incorrect_value, is_required, exception_type, function_name):
        # removing key value pair from handler if it exists
        config_type.pop(key, None)
        # required key not in config
        if (is_required):
            self.assertRaises(exception_type, function_name)
        # key not of expected type
        config_type[key] = incorrect_value
        self.assertRaises(exception_type, function_name)
        config_type[key] = expected_value

    @patch('src.InstallCommandHandler.InstallCommandHandler.validate_os_type')
    @patch('src.InstallCommandHandler.InstallCommandHandler.validate_environment')
    @patch('tests.TestInstallCommandHandler.JsonFileHandler.get_json_file_content')
    def test_all_validate_methods_called_from_install_handler(self, mock_os_type, mock_validate_environment, mock_ext_env_handler):
        ext_env_handler = ExtEnvHandler(self.json_file_handler)
        install_command_handler = InstallCommandHandler(self.logger, ext_env_handler)
        install_command_handler.execute_handler_action()
        self.assertTrue(mock_os_type.called)
        self.assertTrue(mock_validate_environment.called)

if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestInstallCommandHandler)
    unittest.TextTestRunner(verbosity=2).run(SUITE)