import json
import os
import shutil
import tempfile
import time
import unittest

from extension.src.Constants import Constants
from extension.src.TelemetryWriter import TelemetryWriter
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestTelemetryWriter(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.telemetry_writer = TelemetryWriter()
        self.telemetry_writer.events_folder_path = tempfile.mkdtemp()

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")
        shutil.rmtree(self.telemetry_writer.events_folder_path)

    def mock_time(self):
        return 1234

    def mock_os_remove(self, filepath):
        raise Exception("File could not be deleted")

    def mock_os_path_exists(self, filepath):
        return True

    def test_write_event(self):
        self.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        with open(os.path.join(self.telemetry_writer.events_folder_path, os.listdir(self.telemetry_writer.events_folder_path)[0]), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEquals(events[0]["TaskName"], "Test Task")
            f.close()

        self.telemetry_writer.write_event("Test Task2", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)

    def test_write_multiple_events_in_same_file(self):
        time_backup = time.time
        time.time = self.mock_time
        self.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        self.telemetry_writer.write_event("Test Task2", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        with open(os.path.join(self.telemetry_writer.events_folder_path, os.listdir(self.telemetry_writer.events_folder_path)[0]), 'r+') as f:
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
        self.telemetry_writer.write_event("Test Task", message, Constants.TelemetryEventLevel.Error)
        with open(os.path.join(self.telemetry_writer.events_folder_path, os.listdir(self.telemetry_writer.events_folder_path)[0]), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEquals(events[0]["TaskName"], "Test Task")
            self.assertTrue(len(events[0]["Message"]) < len(message.encode('utf-8')))
            bytes_dropped = len(message.encode('utf-8')) - Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_BYTES + Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_BYTES
            self.assertEquals(events[0]["Message"], "a"*(len(message.encode('utf-8')) - bytes_dropped) + ". [{0} bytes dropped]".format(bytes_dropped))
            f.close()

    def test_write_event_size_limit(self):
        # will not write to telemetry if event size exceeds limit
        message = "a"*3074
        task_name = "b"*5000
        self.telemetry_writer.write_event(task_name, message, Constants.TelemetryEventLevel.Error)
        self.assertTrue(len(os.listdir(self.telemetry_writer.events_folder_path)) == 0)

    # def test_write_to_new_file_if_event_file_limit_reached(self):
    #     # todo
    #     self.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
    #     os_path_exists_backup = os.path.exists
    #     os.path.exists = self.mock_os_path_exists
    #     telemetry_event_file_size_backup = Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES
    #     Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES = 1
    #     self.telemetry_writer.write_event("Test Task2", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
    #     events = os.listdir(self.telemetry_writer.events_folder_path)
    #     self.assertEquals(len(events), 2)
    #     os.path.exists = os_path_exists_backup
    #     Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES = telemetry_event_file_size_backup

    def test_delete_older_events(self):

        # deleting older event files before adding new one
        self.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        self.telemetry_writer.write_event("Test Task2", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        self.telemetry_writer.write_event("Test Task3", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        old_events = os.listdir(self.telemetry_writer.events_folder_path)
        telemetry_dir_size_backup = Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES
        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES = 1030
        telemetry_event_size_backup = Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES = 1024

        self.telemetry_writer.write_event("Test Task4", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        new_events = os.listdir(self.telemetry_writer.events_folder_path)
        self.assertEquals(len(new_events), 1)
        self.assertTrue(old_events[0] not in new_events)
        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES = telemetry_dir_size_backup
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES = telemetry_event_size_backup

        # error while deleting event files where the directory size exceeds limit even after deletion attempts
        self.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        self.telemetry_writer.write_event("Test Task2", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        self.telemetry_writer.write_event("Test Task3", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        old_events = os.listdir(self.telemetry_writer.events_folder_path)
        telemetry_dir_size_backup = Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES
        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES = 500
        telemetry_event_size_backup = Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES = 400
        os_remove_backup = os.remove
        os.remove = self.mock_os_remove

        self.assertRaises(Exception, lambda: self.telemetry_writer.write_event("Test Task4", "testing telemetry write to file", Constants.TelemetryEventLevel.Error))

        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES = telemetry_dir_size_backup
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES = telemetry_event_size_backup
        os.remove = os_remove_backup


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestTelemetryWriter)
    unittest.TextTestRunner(verbosity=2).run(SUITE)

