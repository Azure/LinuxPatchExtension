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
import time
import unittest
from datetime import datetime
from src.Constants import Constants
from src.RuntimeContextHandler import RuntimeContextHandler
from src.file_handlers.CoreStateHandler import CoreStateHandler
from src.EnableCommandHandler import EnableCommandHandler
from src.file_handlers.ExtConfigSettingsHandler import ExtConfigSettingsHandler
from src.file_handlers.ExtEnvHandler import ExtEnvHandler
from src.file_handlers.ExtOutputStatusHandler import ExtOutputStatusHandler
from src.file_handlers.ExtStateHandler import ExtStateHandler
from src.ProcessHandler import ProcessHandler
from tests.helpers.RuntimeComposer import RuntimeComposer
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestEnableCommandHandler(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        # create tempdir which will have all the required files
        self.temp_dir = tempfile.mkdtemp()
        runtime = RuntimeComposer()
        self.logger = runtime.logger
        self.utility = runtime.utility
        self.json_file_handler = runtime.json_file_handler
        self.runtime_context_handler = RuntimeContextHandler(self.logger)
        self.ext_env_handler = ExtEnvHandler(self.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        self.config_folder = self.ext_env_handler.config_folder
        self.ext_config_settings_handler = ExtConfigSettingsHandler(self.logger, self.json_file_handler, self.config_folder)
        self.core_state_handler = CoreStateHandler(self.config_folder, self.json_file_handler)
        self.ext_state_handler = ExtStateHandler(self.config_folder, self.utility, self.json_file_handler)
        self.ext_output_status_handler = ExtOutputStatusHandler(self.logger, self.utility, self.json_file_handler, "test.log", 1234, self.temp_dir)
        self.process_handler = ProcessHandler(self.logger, self.ext_output_status_handler)
        self.enable_command_handler = EnableCommandHandler(self.logger, self.utility, self.runtime_context_handler, self.ext_env_handler, self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, self.ext_output_status_handler, self.process_handler, datetime.utcnow(), 1234)
        self.constants = Constants
        self.start_daemon_backup = ProcessHandler.start_daemon
        ProcessHandler.start_daemon = self.mock_start_daemon_to_return_true

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")
        # reseting mocks to their original definition
        ProcessHandler.start_daemon = self.start_daemon_backup
        # delete tempdir
        shutil.rmtree(self.temp_dir)

    def mock_start_daemon_to_return_true(self, seq_no, config_settings, ext_env_handler):
        return True

    def mock_patch_complete_time_check_to_return_true(self, time_for_prev_patch_to_complete, core_state_last_heartbeat, core_state_handler):
        return True

    def test_enable_command_first_request(self):
        self.check_if_patch_completes_in_time_backup = RuntimeContextHandler.check_if_patch_completes_in_time
        RuntimeContextHandler.check_if_patch_completes_in_time = self.mock_patch_complete_time_check_to_return_true
        config_file_path, config_folder_path = self.setup_for_enable_handler(self.temp_dir)
        with self.assertRaises(SystemExit):
            self.enable_command_handler.execute_handler_action()
        self.assertTrue(os.path.exists(config_file_path))
        self.assertTrue(os.path.exists(os.path.join(config_folder_path, self.constants.EXT_STATE_FILE)))
        ext_state_json = self.json_file_handler.get_json_file_content(self.constants.EXT_STATE_FILE, config_folder_path)
        self.assertTrue(ext_state_json is not None)
        self.assertEqual(ext_state_json[self.constants.ExtStateFields.ext_seq][self.constants.ExtStateFields.ext_seq_number], 1234)
        RuntimeContextHandler.check_if_patch_completes_in_time = self.check_if_patch_completes_in_time_backup

    def test_process_reenable_when_previous_req_complete(self):
        config_file_path, config_folder_path = self.setup_for_enable_handler(self.temp_dir)
        shutil.copy(os.path.join("helpers", self.constants.EXT_STATE_FILE), config_folder_path)
        shutil.copy(os.path.join("helpers", self.constants.CORE_STATE_FILE), config_folder_path)
        prev_ext_state_json = self.json_file_handler.get_json_file_content(self.constants.EXT_STATE_FILE, config_folder_path)
        with self.assertRaises(SystemExit):
            self.enable_command_handler.execute_handler_action()

        ext_state_json = self.json_file_handler.get_json_file_content(self.constants.EXT_STATE_FILE, config_folder_path)
        self.assertEqual(prev_ext_state_json[self.constants.ExtStateFields.ext_seq][self.constants.ExtStateFields.ext_seq_number], ext_state_json[self.constants.ExtStateFields.ext_seq][self.constants.ExtStateFields.ext_seq_number])
        self.assertEqual(prev_ext_state_json[self.constants.ExtStateFields.ext_seq][self.constants.ExtStateFields.ext_seq_operation],
                         ext_state_json[self.constants.ExtStateFields.ext_seq][self.constants.ExtStateFields.ext_seq_operation])

    def test_process_enable_request(self):
        # setup to mock environment when enable is triggered with a different sequence number than the prev operation
        config_file_path, config_folder_path = self.setup_for_enable_handler(self.temp_dir)
        new_settings_file = self.create_helpers_for_enable_request(config_folder_path)

        prev_ext_state_json = self.json_file_handler.get_json_file_content(self.constants.EXT_STATE_FILE, config_folder_path)
        enable_command_handler = EnableCommandHandler(self.logger, self.utility, self.runtime_context_handler, self.ext_env_handler, self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, self.ext_output_status_handler, self.process_handler, datetime.utcnow(), 12)
        with self.assertRaises(SystemExit):
            enable_command_handler.execute_handler_action()
        ext_state_json = self.json_file_handler.get_json_file_content(self.constants.EXT_STATE_FILE, config_folder_path)
        self.assertNotEqual(prev_ext_state_json, ext_state_json)
        self.assertNotEqual(prev_ext_state_json[self.constants.ExtStateFields.ext_seq][self.constants.ExtStateFields.ext_seq_number],
                            ext_state_json[self.constants.ExtStateFields.ext_seq][self.constants.ExtStateFields.ext_seq_number])

    def test_process_nooperation_enable_request(self):
        # setup to mock environment when enable is triggered with a nooperation request
        config_file_path, config_folder_path = self.setup_for_enable_handler(self.temp_dir)
        new_settings_file = self.create_helpers_for_enable_request(config_folder_path)

        # update operation to 'NoOperation' since it is set to Assessment in the original helper file
        with open(new_settings_file, 'r+') as f:
            config_settings = json.load(f)
            config_settings[self.constants.RUNTIME_SETTINGS][0][self.constants.HANDLER_SETTINGS][self.constants.PUBLIC_SETTINGS][self.constants.ConfigPublicSettingsFields.operation] = self.constants.NOOPERATION
            f.seek(0)  # rewind
            json.dump(config_settings, f)
            f.truncate()
            f.close()

        prev_ext_state_json = self.json_file_handler.get_json_file_content(self.constants.EXT_STATE_FILE, config_folder_path)
        enable_command_handler = EnableCommandHandler(self.logger, self.utility, self.runtime_context_handler, self.ext_env_handler, self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, self.ext_output_status_handler, self.process_handler, datetime.utcnow(), 12)
        with self.assertRaises(SystemExit):
            enable_command_handler.execute_handler_action()
        ext_state_json = self.json_file_handler.get_json_file_content(self.constants.EXT_STATE_FILE, config_folder_path)
        core_state_json = self.json_file_handler.get_json_file_content(self.constants.CORE_STATE_FILE, config_folder_path, raise_if_not_found=False)
        self.assertTrue(core_state_json is None)
        self.assertNotEqual(prev_ext_state_json, ext_state_json)
        self.assertNotEqual(prev_ext_state_json[self.constants.ExtStateFields.ext_seq][self.constants.ExtStateFields.ext_seq_number], ext_state_json[self.constants.ExtStateFields.ext_seq][self.constants.ExtStateFields.ext_seq_number])

    def setup_for_enable_handler(self, dir_path):
        config_folder_name = self.config_folder
        status_folder_name = self.ext_env_handler.status_folder
        log_folder_name = self.ext_env_handler.log_folder

        # creating the required folder (e.g: config folder, log folder, status folder) under the temp directory
        config_folder_path = os.path.join(dir_path, config_folder_name)
        status_folder_path = os.path.join(dir_path, status_folder_name)
        log_folder_path = os.path.join(dir_path, log_folder_name)
        os.mkdir(config_folder_path)
        os.mkdir(status_folder_path)
        os.mkdir(log_folder_path)

        # copying a sample version of the <seqno>.settings file from the helpers folder to the temp directory
        shutil.copy(os.path.join("helpers", "1234.settings"), config_folder_path)
        config_file_path = os.path.join(config_folder_path, '1234.settings')

        # updating the timestamp because the backup logic fetches seq no from the handler configuration files/<seqno>.settings in config folder, if nothing is set in the env variable
        with open(config_file_path, 'a') as f:
            timestamp = time.mktime(datetime.strptime('2019-07-20T12:10:14Z', '%Y-%m-%dT%H:%M:%SZ').timetuple())
            os.utime(config_file_path, (timestamp, timestamp))
            f.close()

        self.ext_env_handler.config_folder = config_folder_path
        self.ext_env_handler.status_folder = status_folder_path
        self.ext_env_handler.log_folder = log_folder_path

        self.ext_config_settings_handler.config_folder = config_folder_path
        self.core_state_handler.dir_path = config_folder_path
        self.ext_state_handler.dir_path = config_folder_path

        return config_file_path, config_folder_path

    def create_helpers_for_enable_request(self, config_folder_path):
        """ Create config settings, CoreState and ExtState files needed for enable request """
        # create config settings, CoreState and ExtState files in tempdir using references from the respective files under helpers in tests dir
        shutil.copy(os.path.join("helpers", self.constants.EXT_STATE_FILE), config_folder_path)
        shutil.copy(os.path.join("helpers", self.constants.CORE_STATE_FILE), config_folder_path)
        new_settings_file = os.path.join(config_folder_path, "12.settings")
        shutil.copy(os.path.join("helpers", "1234.settings"), new_settings_file)

        # set the modified time of the config settings file in tempdir
        with open(new_settings_file, 'a') as f:
            timestamp = time.mktime(datetime.strptime('2019-07-21T12:10:14Z', '%Y-%m-%dT%H:%M:%SZ').timetuple())
            os.utime(new_settings_file, (timestamp, timestamp))
            f.close()

        return new_settings_file


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestEnableCommandHandler)
    unittest.TextTestRunner(verbosity=2).run(SUITE)

