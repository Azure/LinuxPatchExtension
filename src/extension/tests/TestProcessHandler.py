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
import unittest
from src.Constants import Constants
from src.file_handlers.ExtOutputStatusHandler import ExtOutputStatusHandler
from src.file_handlers.ExtConfigSettingsHandler import ExtConfigSettingsHandler
from src.file_handlers.ExtEnvHandler import ExtEnvHandler
from src.ProcessHandler import ProcessHandler
from tests.helpers.RuntimeComposer import RuntimeComposer
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestProcessHandler(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        runtime = RuntimeComposer()
        self.logger = runtime.logger
        self.utility = runtime.utility
        self.json_file_handler = runtime.json_file_handler
        seq_no = 1234
        dir_path = os.path.join(os.path.pardir, "tests", "helpers")
        self.ext_output_status_handler = ExtOutputStatusHandler(self.logger, self.utility, self.json_file_handler, "test.log", seq_no, dir_path)

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def mock_is_process_running_to_return_true(self, pid):
        return True

    def mock_os_kill_to_raise_exception(self, pid, sig):
        raise OSError

    def test_get_public_config_settings(self):
        ext_config_settings_handler = ExtConfigSettingsHandler(self.logger, self.json_file_handler, os.path.join(os.path.pardir, "tests", "helpers"))
        seq_no = "1234"
        config_settings = ext_config_settings_handler.read_file(seq_no)
        process_handler = ProcessHandler(self.logger, self.ext_output_status_handler)
        public_config_settings = process_handler.get_public_config_settings(config_settings)
        self.assertTrue(public_config_settings is not None)
        self.assertEqual(public_config_settings.get(Constants.ConfigPublicSettingsFields.operation), "Deployment")

    def test_get_env_settings(self):
        handler_env_file_path = os.path.join(os.path.pardir, "tests", "helpers")
        ext_env_handler = ExtEnvHandler(self.json_file_handler, handler_env_file_path=handler_env_file_path)
        process_handler = ProcessHandler(self.logger, self.ext_output_status_handler)
        env_settings = process_handler.get_env_settings(ext_env_handler)
        self.assertTrue(env_settings is not None)
        self.assertEqual(env_settings.get(Constants.EnvSettingsFields.log_folder), "mockLog")

    def test_kill_process(self):
        # setting mocks
        is_process_running_backup = ProcessHandler.is_process_running
        ProcessHandler.is_process_running = self.mock_is_process_running_to_return_true
        os_kill_backup = os.kill
        os.kill = self.mock_os_kill_to_raise_exception

        # error in terminating process
        pid = 123
        process_handler = ProcessHandler(self.logger, self.ext_output_status_handler)
        self.assertRaises(OSError, process_handler.kill_process, pid)

        # reseting mocks
        ProcessHandler.is_process_running = is_process_running_backup
        os.kill = os_kill_backup

if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestProcessHandler)
    unittest.TextTestRunner(verbosity=2).run(SUITE)

