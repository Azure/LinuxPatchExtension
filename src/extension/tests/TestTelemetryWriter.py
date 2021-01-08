import json
import os
import shutil
import tempfile
import time
import unittest

from extension.src.Constants import Constants
from extension.src.TelemetryWriter import TelemetryWriter
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestTelemetryWriter(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.telemetry_writer = TelemetryWriter()
        self.telemetry_writer.events_folder_path = tempfile.mkdtemp()

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")
        # shutil.rmtree(self.telemetry_writer.events_folder_path)

    def test_write_event(self):
        self.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        with open(os.path.join(self.telemetry_writer.events_folder_path, os.listdir(self.telemetry_writer.events_folder_path)[0]), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEquals(events[0]["TaskName"], "Test Task")
            f.close()

        self.telemetry_writer.write_event("Test Task2", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)

    def test_write_multiple_events_in_same_file(self):
        # todo
        self.telemetry_writer.write_event("Test Task", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)
        self.telemetry_writer.write_event("Test Task2", "testing telemetry write to file", Constants.TelemetryEventLevel.Error)

    def test_write_event_msg_size_limit(self):
        message = "a"*3074
        self.telemetry_writer.write_event("Test Task", message, Constants.TelemetryEventLevel.Error)
        with open(os.path.join(self.telemetry_writer.events_folder_path, os.listdir(self.telemetry_writer.events_folder_path)[0]), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEquals(events[0]["TaskName"], "Test Task")
            self.assertTrue(len(events[0]["Message"]) == 3072)
            self.assertEquals(events[0]["Message"], "a"*3069 + "...")
            f.close()

    def test_write_event_size_limit(self):
        message = "a"*3074
        task_name = "b"*5000
        self.telemetry_writer.write_event(task_name, message, Constants.TelemetryEventLevel.Error)
        self.assertTrue(len(os.listdir(self.telemetry_writer.events_folder_path)) == 0)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestTelemetryWriter)
    unittest.TextTestRunner(verbosity=2).run(SUITE)

