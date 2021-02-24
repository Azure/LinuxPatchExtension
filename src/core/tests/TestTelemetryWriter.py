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

    def test_write_event(self):
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        telemetry_event_counter_in_first_test_event = None
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEquals(events[0]["TaskName"], "Test Task")
            text_found = re.search('TC=([0-9]+)', events[0]['Message'])
            telemetry_event_counter_in_first_test_event = text_found.group(1) if text_found else None
            f.close()

        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        telemetry_event_counter_in_second_test_event = None
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEquals(events[-1]["TaskName"], "Test Task2")
            text_found = re.search('TC=([0-9]+)', events[0]['Message'])
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
            self.assertEquals(len(events), 2)
            self.assertEquals(events[0]["TaskName"], "Test Task")
            self.assertEquals(events[1]["TaskName"], "Test Task2")
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
            self.assertEquals(events[0]["TaskName"], "Test Task")
            self.assertTrue(len(events[0]["Message"]) < len(message.encode('utf-8')))
            chars_dropped = len(message.encode('utf-8')) - Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_CHARS + Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_CHARS + Constants.TELEMETRY_EVENT_COUNTER_MSG_SIZE_LIMIT_IN_CHARS
            self.assertTrue("a"*(len(message.encode('utf-8')) - chars_dropped) + ". [{0} chars dropped]".format(chars_dropped) in events[0]["Message"])
            f.close()

    def test_write_event_size_limit(self):
        # will not write to telemetry if event size exceeds limit
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        old_events = os.listdir(self.runtime.telemetry_writer.events_folder_path)
        message = "a" * 3074
        task_name = "b" * 5000
        self.runtime.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, task_name)
        new_events = os.listdir(self.runtime.telemetry_writer.events_folder_path)
        self.assertEquals(old_events, new_events)
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertTrue(task_name not in events[0]['TaskName'])
            f.close()

    def test_write_to_new_file_if_event_file_limit_reached(self):
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        os_path_exists_backup = os.path.exists
        os.path.exists = self.mock_os_path_exists
        telemetry_get_event_file_size_backup = self.runtime.telemetry_writer.get_file_size
        self.runtime.telemetry_writer.get_file_size = self.mock_get_file_size

        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
        events = os.listdir(self.runtime.telemetry_writer.events_folder_path)
        self.assertTrue(len(events) > 1)
        os.path.exists = os_path_exists_backup
        self.runtime.telemetry_writer.get_file_size = telemetry_get_event_file_size_backup

    def test_delete_older_events(self):

        # deleting older event files before adding new one
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task3")
        old_events = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)]
        telemetry_dir_size_backup = Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS
        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = 1030
        telemetry_event_size_backup = Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = 1024

        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task4")
        new_events = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)]
        self.assertEquals(len(new_events), 1)
        self.assertTrue(old_events[0] not in new_events)
        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = telemetry_dir_size_backup
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = telemetry_event_size_backup

        # error while deleting event files where the directory size exceeds limit even after deletion attempts
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task3")
        old_events = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)]
        telemetry_dir_size_backup = Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS
        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = 500
        telemetry_event_size_backup = Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = 400
        os_remove_backup = os.remove
        os.remove = self.mock_os_remove

        self.assertRaises(Exception, lambda: self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task4"))

        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = telemetry_dir_size_backup
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = telemetry_event_size_backup
        os.remove = os_remove_backup

    def test_write_event_event_file_max_throttle_reached(self):
        event_file_max_throttle_backup = Constants.TELEMETRY_MAX_EVENT_FILE_THROTTLE_COUNT
        Constants.TELEMETRY_MAX_EVENT_FILE_THROTTLE_COUNT = 4
        self.runtime.telemetry_writer.event_file_count = 0
        self.runtime.telemetry_writer.start_time_for_event_file_throttle_check = datetime.datetime.utcnow()

        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task3")
        event_file_task3 = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, event_file_task3), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertTrue("Test Task3" in events[0]['TaskName'])
            f.close()

        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task4")
        event_file_task4 = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, event_file_task4), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertTrue("Test Task4" in events[0]['TaskName'])
            f.close()
        self.assertTrue(self.runtime.telemetry_writer.event_file_count == 1)

        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task5")
        self.assertTrue(self.runtime.telemetry_writer.event_file_count == 2)

        max_time_for_event_file_throttle_backup = Constants.TELEMETRY_MAX_TIME_IN_SECONDS_FOR_EVENT_FILE_THROTTLE
        Constants.TELEMETRY_MAX_TIME_IN_SECONDS_FOR_EVENT_FILE_THROTTLE = 0
        self.runtime.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task6")
        self.assertTrue(self.runtime.telemetry_writer.event_file_count == 1)
        Constants.TELEMETRY_MAX_TIME_IN_SECONDS_FOR_EVENT_FILE_THROTTLE = max_time_for_event_file_throttle_backup

        Constants.TELEMETRY_MAX_EVENT_FILE_THROTTLE_COUNT = event_file_max_throttle_backup


if __name__ == '__main__':
    unittest.main()
