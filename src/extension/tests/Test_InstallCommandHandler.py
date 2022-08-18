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
import sys
import unittest
from extension.src.Constants import Constants
from extension.src.InstallCommandHandler import InstallCommandHandler
from extension.src.file_handlers.ExtEnvHandler import ExtEnvHandler
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestInstallCommandHandler(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        runtime = RuntimeComposer()
        self.logger = runtime.logger
        self.telemetry_writer = runtime.telemetry_writer
        self.logger.telemetry_writer = self.telemetry_writer
        self.json_file_handler = runtime.json_file_handler
        self.get_json_file_content_backup = self.json_file_handler.get_json_file_content
        self.json_file_handler.get_json_file_content = self.mock_get_json_file_content_to_return_none

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")
        # reseting mocks
        self.json_file_handler.get_json_file_content = self.get_json_file_content_backup

    def mock_get_json_file_content_to_return_none(self, file_name, dir_path, raise_if_not_found=False):
        return None

    def test_validate_os_type_is_linux(self):
        ext_env_handler = ExtEnvHandler(self.json_file_handler)
        install_command_handler = InstallCommandHandler(self.logger, ext_env_handler)
        sys.platform = 'linux'
        self.assertTrue(install_command_handler.validate_os_type())

    def test_validate_os_type_not_linux(self):
        ext_env_handler = ExtEnvHandler(self.json_file_handler)
        install_command_handler = InstallCommandHandler(self.logger, ext_env_handler)
        sys.platform = 'win32'
        self.assertRaises(Exception, install_command_handler.validate_os_type)

    def test_validate_environment(self):
        config_type = 'handlerEnvironment'

        # file has no content
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
        # reseting mock to original func def
        self.json_file_handler.get_json_file_content = self.get_json_file_content_backup
        ext_env_handler = ExtEnvHandler(self.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        install_command_handler = InstallCommandHandler(self.logger, ext_env_handler)
        install_command_handler.validate_environment()

    def verify_key(self, config_type, key, expected_value, incorrect_value, is_required, exception_type, function_name):
        # removing key value pair from handler if it exists
        config_type.pop(key, None)
        # required key not in config
        if is_required:
            self.assertRaises(exception_type, function_name)
        # key not of expected type
        config_type[key] = incorrect_value
        self.assertRaises(exception_type, function_name)
        config_type[key] = expected_value

    def test_execute_action_handler(self):
        sys.platform = 'linux'
        # reseting mock to original func def
        self.json_file_handler.get_json_file_content = self.get_json_file_content_backup
        ext_env_handler = ExtEnvHandler(self.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        install_command_handler = InstallCommandHandler(self.logger, ext_env_handler)
        self.assertEqual(install_command_handler.execute_handler_action(), Constants.ExitCode.Okay)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestInstallCommandHandler)
    unittest.TextTestRunner(verbosity=2).run(SUITE)

