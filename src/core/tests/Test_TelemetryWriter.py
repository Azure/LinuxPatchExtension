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
import json
import os
import re
import time
import unittest
from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestTelemetryWriter(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True)

    def tearDown(self):
        self.runtime.stop()

    def mock_time(self):
        return 1234

    def mock_os_remove(self, filepath):
        raise Exception("File could not be deleted")

    def mock_os_path_exists(self, filepath):
        return True

    def mock_get_file_size(self, file_path):
        return Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS + 10

    def mock_os_listdir(self, file_path):
        return ['testevent1.json', 'testevent2.json', 'testevent3.json', 'testevent4.json']

    def test_write_event(self):
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        telemetry_event_counter_in_first_test_event = None
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEqual(events[-1]["TaskName"], "Test Task")
            text_found = re.search('TC=([0-9]+)', events[-1]['Message'])
            telemetry_event_counter_in_first_test_event = text_found.group(1) if text_found else None
            f.close()

        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        telemetry_event_counter_in_second_test_event = None
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEqual(events[-1]["TaskName"], "Test Task2")
            text_found = re.search('TC=([0-9]+)', events[-1]['Message'])
            telemetry_event_counter_in_second_test_event = text_found.group(1) if text_found else None
            f.close()

        self.assertTrue(telemetry_event_counter_in_first_test_event is not None)
        self.assertTrue(telemetry_event_counter_in_second_test_event is not None)
        self.assertTrue(int(telemetry_event_counter_in_second_test_event) - int(telemetry_event_counter_in_first_test_event) == 1)

    def test_write_multiple_events_in_same_file(self):
        time_backup = time.time
        time.time = self.mock_time
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^' + str(self.mock_time()) + '0+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEqual(events[-2]["TaskName"], "Test Task")
            self.assertEqual(events[-1]["TaskName"], "Test Task2")
            f.close()
        time.time = time_backup

    def test_write_event_msg_size_limit(self):
        # Assuming 1 char is 1 byte
        message = "a"*3074
        self.runtime.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEqual(events[-1]["TaskName"], "Test Task")
            self.assertTrue(len(events[-1]["Message"]) < len(message.encode('utf-8')))
            chars_dropped = len(message.encode('utf-8')) - Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_CHARS + Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_CHARS + Constants.TELEMETRY_EVENT_COUNTER_MSG_SIZE_LIMIT_IN_CHARS
            self.assertTrue("a"*(len(message.encode('utf-8')) - chars_dropped) + ". [{0} chars dropped]".format(chars_dropped) in events[-1]["Message"])
            f.close()

    # TODO: The following 3 tests cause widespread test suite failures (on master), so leaving it out. And tracking in: Task 10912099: [Bug] Bug in telemetry writer - overwriting prior events in fast execution
    # def test_write_event_size_limit(self):
    #     # will not write to telemetry if event size exceeds limit
    #     self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
    #     old_events = os.listdir(self.runtime.telemetry_writer.events_folder_path)
    #     message = "a" * 3074
    #     task_name = "b" * 5000
    #     self.runtime.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, task_name)
    #     new_events = os.listdir(self.runtime.telemetry_writer.events_folder_path)
    #     self.assertEqual(old_events, new_events)
    #     latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
    #     with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
    #         events = json.load(f)
    #         self.assertTrue(events is not None)
    #         self.assertTrue(task_name not in events[-1]['TaskName'])
    #         f.close()
    #
    # def test_write_to_new_file_if_event_file_limit_reached(self):
    #     self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
    #     first_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
    #     os_path_exists_backup = os.path.exists
    #     os.path.exists = self.mock_os_path_exists
    #     telemetry_get_event_file_size_backup = self.runtime.telemetry_writer.get_file_size
    #     self.runtime.telemetry_writer.get_file_size = self.mock_get_file_size
    #
    #     # forcing wait of 1 sec to ensure new file is created, since we have mocked time.sleep in RuntimeComposer
    #     time.sleep = self.runtime.backup_time_sleep
    #
    #     self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
    #     event_files = os.listdir(self.runtime.telemetry_writer.events_folder_path)
    #     self.assertTrue(len(event_files) > 1)
    #     second_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
    #     self.assertFalse(first_event_file == second_event_file)
    #     os.path.exists = os_path_exists_backup
    #     self.runtime.telemetry_writer.get_file_size = telemetry_get_event_file_size_backup
    #
    # def test_delete_older_events(self):
    #     # deleting older event files before adding new one
    #     self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
    #     self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
    #     self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task3")
    #     old_event_files = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)]
    #     telemetry_dir_size_backup = Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS
    #     Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = 1030
    #     telemetry_event_size_backup = Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS
    #     Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = 1024
    #
    #     self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task4")
    #     new_event_files = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)]
    #     self.assertEqual(len(new_event_files), 1)
    #     self.assertTrue(old_event_files[0] not in new_event_files and old_event_files[1] not in new_event_files and old_event_files[2] not in new_event_files)
    #     Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = telemetry_dir_size_backup
    #     Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = telemetry_event_size_backup
    #
    #     # error while deleting event files where the directory size exceeds limit even after deletion attempts
    #     self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
    #     self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
    #     self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task3")
    #     old_event_files = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)]
    #     telemetry_dir_size_backup = Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS
    #     Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = 500
    #     telemetry_event_size_backup = Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS
    #     Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = 400
    #     os_remove_backup = os.remove
    #     os.remove = self.mock_os_remove
    #
    #     self.assertRaises(Exception, lambda: self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task4"))
    #
    #     Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = telemetry_dir_size_backup
    #     Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = telemetry_event_size_backup
    #     os.remove = os_remove_backup

    def test_write_event_max_event_count_throttle_reached(self):
        event_count_max_throttle_backup = Constants.TELEMETRY_MAX_EVENT_COUNT_THROTTLE
        Constants.TELEMETRY_MAX_EVENT_COUNT_THROTTLE = 5
        self.runtime.telemetry_writer.event_count = 1
        self.runtime.telemetry_writer.start_time_for_event_count_throttle_check = datetime.datetime.utcnow()

        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task3")
        event_file_task3 = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, event_file_task3), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertTrue("Test Task3" in events[-1]['TaskName'])
            f.close()

        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task4")
        event_file_task4 = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, event_file_task4), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertTrue("Test Task4" in events[-1]['TaskName'])
            f.close()
        self.assertTrue(self.runtime.telemetry_writer.event_count == 2)

        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task5")
        self.assertTrue(self.runtime.telemetry_writer.event_count == 3)

        max_time_for_event_count_throttle_backup = Constants.TELEMETRY_MAX_TIME_IN_SECONDS_FOR_EVENT_COUNT_THROTTLE
        Constants.TELEMETRY_MAX_TIME_IN_SECONDS_FOR_EVENT_COUNT_THROTTLE = 0
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task6")
        self.assertTrue(self.runtime.telemetry_writer.event_count == 2)
        Constants.TELEMETRY_MAX_TIME_IN_SECONDS_FOR_EVENT_COUNT_THROTTLE = max_time_for_event_count_throttle_backup

        Constants.TELEMETRY_MAX_EVENT_COUNT_THROTTLE = event_count_max_throttle_backup

    def test_events_deleted_outside_of_extension_while_extension_is_running(self):
        backup_os_listdir = os.listdir
        os.listdir = self.mock_os_listdir
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        os.listdir = backup_os_listdir

    def test_agent_version_info(self):
        # Case 1: HappyPath - WALinuxAgent is installed and version information is returned
        self.runtime.set_legacy_test_type('HappyPath')
        self.assertEqual(self.runtime.telemetry_writer.get_agent_version(), '2.2.49.2')
        self.assertEqual(self.runtime.telemetry_writer.get_goal_state_agent_version(), '2.6.0.2')

        # Case 2: SadPath - WALinuxAgent is not installed
        self.runtime.set_legacy_test_type('SadPath')
        self.assertTrue(self.runtime.telemetry_writer.get_agent_version() is None)
        self.assertTrue(self.runtime.telemetry_writer.get_goal_state_agent_version() is None)

    def test_agent_not_supported_env_var_telemetry_key_not_exists(self):
        backup_os_getenv = os.getenv

        def mock_os_getenv(key, default=None):
            value = backup_os_getenv(key, default)
            if key == Constants.AZURE_GUEST_AGENT_EXTENSION_SUPPORTED_FEATURES_ENV_VAR:
                return '[]'
            else:
                return value

        os.getenv = mock_os_getenv
        self.assertEqual("Diagnostic-code: 2.2.49.2/2.6.0.2/1/0/2", self.runtime.telemetry_writer.get_telemetry_diagnostics())
        os.getenv = backup_os_getenv

    def test_agent_not_supported_env_var_supported_features_not_exists(self):
        backup_os_getenv = os.getenv

        def mock_os_getenv(key, default=None):
            value = backup_os_getenv(key, default)
            if key == Constants.AZURE_GUEST_AGENT_EXTENSION_SUPPORTED_FEATURES_ENV_VAR:
                return None
            else:
                return value

        os.getenv = mock_os_getenv
        self.assertEqual("Diagnostic-code: 2.2.49.2/2.6.0.2/1/0/1", self.runtime.telemetry_writer.get_telemetry_diagnostics())
        os.getenv = backup_os_getenv


if __name__ == '__main__':
    unittest.main()
