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
import re
import time
import unittest

from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestTelemetryWriter(unittest.TestCase):

    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True)
        self.container = self.runtime.container
        self.runtime.composite_logger.telemetry_writer.events_folder_path = self.runtime.execution_config.events_folder
        self.runtime.composite_logger.telemetry_writer.set_operation_id(self.runtime.execution_config.activity_id)

    def tearDown(self):
        self.runtime.stop()

    def mock_time(self):
        return 1234

    def mock_os_remove(self, filepath):
        raise Exception("File could not be deleted")

    def mock_os_path_exists(self, filepath):
        return True

    def mock_get_file_size(self, file_path):
        return Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES + 10

    def test_write_event(self):
        self.runtime.composite_logger.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.composite_logger.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.composite_logger.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEquals(events[-1]["TaskName"], "Test Task")
            f.close()

        self.runtime.composite_logger.telemetry_writer.write_event("Test Task2", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)

    def test_write_multiple_events_in_same_file(self):
        time_backup = time.time
        time.time = self.mock_time
        self.runtime.composite_logger.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        self.runtime.composite_logger.telemetry_writer.write_event("Test Task2", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.composite_logger.telemetry_writer.events_folder_path) if re.search('^'+str(self.mock_time())+'0+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.composite_logger.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
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
        self.runtime.composite_logger.telemetry_writer.write_event("Test Task", message, Constants.TelemetryEventLevel.Error)
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.composite_logger.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.composite_logger.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEquals(events[0]["TaskName"], "Test Task")
            self.assertTrue(len(events[0]["Message"]) < len(message.encode('utf-8')))
            bytes_dropped = len(message.encode('utf-8')) - Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_BYTES + Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_BYTES
            self.assertEquals(events[0]["Message"], "a"*(len(message.encode('utf-8')) - bytes_dropped) + ". [{0} bytes dropped]".format(bytes_dropped))
            f.close()

    def test_write_event_size_limit(self):
        # will not write to telemetry if event size exceeds limit
        self.runtime.composite_logger.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        old_events = os.listdir(self.runtime.composite_logger.telemetry_writer.events_folder_path)
        message = "a"*3074
        task_name = "b"*5000
        self.runtime.composite_logger.telemetry_writer.write_event(task_name, message, Constants.TelemetryEventLevel.Error)
        new_events = os.listdir(self.runtime.composite_logger.telemetry_writer.events_folder_path)
        self.assertEquals(old_events, new_events)
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.composite_logger.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.composite_logger.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertTrue(task_name not in events[0]['TaskName'])
            f.close()

    def test_write_to_new_file_if_event_file_limit_reached(self):
        self.runtime.composite_logger.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        os_path_exists_backup = os.path.exists
        os.path.exists = self.mock_os_path_exists
        telemetry_get_event_file_size_backup = self.runtime.composite_logger.telemetry_writer.get_file_size
        self.runtime.composite_logger.telemetry_writer.get_file_size = self.mock_get_file_size

        self.runtime.composite_logger.telemetry_writer.write_event("Test Task2", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        events = os.listdir(self.runtime.composite_logger.telemetry_writer.events_folder_path)
        self.assertTrue(len(events) > 1)
        os.path.exists = os_path_exists_backup
        self.runtime.composite_logger.telemetry_writer.get_file_size = telemetry_get_event_file_size_backup

    def test_delete_older_events(self):

        # deleting older event files before adding new one
        self.runtime.composite_logger.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        self.runtime.composite_logger.telemetry_writer.write_event("Test Task2", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        self.runtime.composite_logger.telemetry_writer.write_event("Test Task3", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        old_events = [pos_json for pos_json in os.listdir(self.runtime.composite_logger.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)]
        telemetry_dir_size_backup = Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES
        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES = 1030
        telemetry_event_size_backup = Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES = 1024

        self.runtime.composite_logger.telemetry_writer.write_event("Test Task4", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        new_events = [pos_json for pos_json in os.listdir(self.runtime.composite_logger.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)]
        self.assertEquals(len(new_events), 1)
        self.assertTrue(old_events[0] not in new_events)
        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES = telemetry_dir_size_backup
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES = telemetry_event_size_backup

        # error while deleting event files where the directory size exceeds limit even after deletion attempts
        self.runtime.composite_logger.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        self.runtime.composite_logger.telemetry_writer.write_event("Test Task2", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        self.runtime.composite_logger.telemetry_writer.write_event("Test Task3", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        old_events = [pos_json for pos_json in os.listdir(self.runtime.composite_logger.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)]
        telemetry_dir_size_backup = Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES
        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES = 500
        telemetry_event_size_backup = Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES = 400
        os_remove_backup = os.remove
        os.remove = self.mock_os_remove

        self.assertRaises(Exception, lambda: self.runtime.composite_logger.telemetry_writer.write_event("Test Task4", "testing telemetry write to file", Constants.TelemetryEventLevel.Error))

        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES = telemetry_dir_size_backup
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES = telemetry_event_size_backup
        os.remove = os_remove_backup


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestTelemetryWriter)
    unittest.TextTestRunner(verbosity=2).run(SUITE)


