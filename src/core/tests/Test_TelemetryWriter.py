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

    def test_write_event_msg_size_limit_char_more_than_1_bytes(self):
        """ Perform 1 byte truncation on char that is more than 1 byte, use decode('utf-8', errors='replace') to replace bad unicode with a good 1 byte char (\uFFFD) """

        message = "a\u20acbc" * 3074  # (\xe2\x82\xac) is 3 bytes char can be written in windows console w/o encoding
        min_msg_limit_in_bytes = Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_CHARS - Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_CHARS - Constants.TELEMETRY_EVENT_COUNTER_MSG_SIZE_LIMIT_IN_CHARS
        max_msg_limit_in_bytes = Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_CHARS
        self.runtime.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEqual(events[-1]["TaskName"], "Test Task")
            self.assertTrue(len(events[-1]["Message"]) < len(message.encode('utf-8')))
            self.assertTrue("a\u20acbc" in events[-1]["Message"])
            self.assertTrue(len(events[-1]["Message"].encode('utf-8')) > min_msg_limit_in_bytes)
            self.assertTrue(len(events[-1]["Message"].encode('utf-8')) < max_msg_limit_in_bytes)

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

    def test_write_event_with_buffer_true_and_then_flush(self):
        self.runtime.telemetry_writer.write_event_with_buffer("Message 1", Constants.TelemetryEventLevel.Verbose,
                                                              Constants.BufferMessage.TRUE)
        self.runtime.telemetry_writer.write_event_with_buffer("Message 2", Constants.TelemetryEventLevel.Verbose,
                                                              Constants.BufferMessage.TRUE)
        self.runtime.telemetry_writer.write_event_with_buffer("Message 3", Constants.TelemetryEventLevel.Verbose,
                                                              Constants.BufferMessage.FLUSH)

        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if
                             re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            text_found = re.search('TC=([0-9]+)', events[-1]['Message'])
            f.close()
            self.assertTrue(text_found.string.startswith("Message 1 | Message 2 | Message 3"))

    def test_write_event_with_buffer_only_flush(self):
        self.runtime.telemetry_writer.write_event_with_buffer("Message 1", Constants.TelemetryEventLevel.Verbose,
                                                              Constants.BufferMessage.FLUSH)

        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if
                             re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            text_found = re.search('TC=([0-9]+)', events[-1]['Message'])
            f.close()
            self.assertTrue(text_found.string.startswith("Message 1"))

    def test_write_event_with_buffer_false(self):
        self.runtime.telemetry_writer.write_event_with_buffer("Message 1", Constants.TelemetryEventLevel.Verbose,
                                                              Constants.BufferMessage.FALSE)

        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if
                             re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            text_found = re.search('TC=([0-9]+)', events[-1]['Message'])
            f.close()
            self.assertTrue(text_found.string.startswith("Message 1"))

    def test_write_event_with_buffer_true_and_then_flush_but_different_telemetry_event_level(self):
        self.runtime.telemetry_writer.write_event_with_buffer("Message 1", Constants.TelemetryEventLevel.Verbose,
                                                              Constants.BufferMessage.TRUE)

        self.runtime.telemetry_writer.write_event_with_buffer("Message 2", Constants.TelemetryEventLevel.Informational,
                                                              Constants.BufferMessage.FLUSH)

        # As the messages are with different TelemetryEventLevel, they will be written separately
        # even though flush is used.
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if
                             re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            text_found = re.search('TC=([0-9]+)', events[-1]['Message'])
            f.close()
            self.assertTrue(text_found.string.startswith("Message 2"))

    def test_write_event_with_buffer_true_and_empty_string_and_then_flush_with_non_empty_string(self):
        self.runtime.telemetry_writer.write_event_with_buffer("", Constants.TelemetryEventLevel.Verbose,
                                                              Constants.BufferMessage.TRUE)

        self.runtime.telemetry_writer.write_event_with_buffer("Message 1", Constants.TelemetryEventLevel.Verbose,
                                                              Constants.BufferMessage.FLUSH)

        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if
                             re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            text_found = re.search('TC=([0-9]+)', events[-1]['Message'])
            f.close()
            self.assertTrue(text_found.string.startswith("Message 1"))

    # ==================== Unit Tests for Credential Sanitization ====================
    # ==================== Helper functions for Credential Sanitization Tests ====================
    def _clear_events_folder(self):
        """
        Helper method to clear the events folder for sanitization test setup.
        Removes all existing JSON event files.
        """
        for f in os.listdir(self.runtime.telemetry_writer.events_folder_path):
            if f.endswith('.json'):
                os.remove(os.path.join(self.runtime.telemetry_writer.events_folder_path, f))

    def _read_event_from_file(self, file_index=None, event_index=-1):
        """
        Helper method to open and read an event from an event file in the events folder.
        Args:
            file_index: Index of the event file to read. If None, uses latest file
            event_index: Index of the event within the file (default: -1 for last event)
        Returns: The parsed event dictionary from the JSON file
        """
        event_files = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)]
        if not event_files:
            raise Exception("No event files found in events folder")

        if file_index is None:
            event_file_path = os.path.join(self.runtime.telemetry_writer.events_folder_path, event_files[-1])
        else:
            event_file_path = os.path.join(self.runtime.telemetry_writer.events_folder_path, event_files[file_index])

        with open(event_file_path, 'r+') as f:
            events = json.load(f)
            f.close()
            if not events:
                raise Exception("No events found in event file")
            return events[event_index]

    def _get_message_without_tc(self, event):
        """
        Helper method to extract the message without the TC (telemetry counter) portion.
        Args:
            event: The event dictionary
        Returns: The message portion before " [TC=" marker
        """
        return event["Message"][:event["Message"].rfind(" [TC=")]

    def _validate_sanitized_event(self, expected_message, task_name=None, event_index=-1, file_index=None):
        """
        Helper method to validate an event's message and task name against expected values.
        Args:
            expected_message: The expected sanitized message (without TC counter)
            task_name: The expected task name (optional validation)
            event_index: Index of the event within the file (default: -1 for last event)
            file_index: Index of the event file (default: None for latest file)
        """
        event = self._read_event_from_file(file_index=file_index, event_index=event_index)

        self.assertIsNotNone(event)
        message_without_tc = self._get_message_without_tc(event)
        self.assertEqual(expected_message, message_without_tc)
        if task_name is not None:
            self.assertEqual(task_name, event["TaskName"])

    # ==================== Credential Sanitization Test Cases ====================
    def test_sanitize_credentials_from_uri_https_with_credentials_leak(self):
        """ Test sanitization of HTTPS URIs with credentials """
        self._clear_events_folder()
        self.assertEqual(len([f for f in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', f)]), 0)

        message = "Error connecting to https://testuser:TESTTOKEN123456@invalid.repo.example/rpm/repodata/repomd.xml"
        expected_message = "Error connecting to https://testuser@invalid.repo.example/rpm/repodata/repomd.xml"

        self.runtime.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")

        # Validate exactly one event file was created
        event_files_count = len([f for f in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', f)])
        self.assertEqual(event_files_count, 1)

        # Validate using helper
        self._validate_sanitized_event(expected_message, task_name="Test Task")

    def test_sanitize_credentials_from_uri_http_with_credentials_leak(self):
        """ Test sanitization of HTTP URIs with credentials """
        message = "Connection failed to http://user123:password123@example.com/path"
        expected_message = "Connection failed to http://user123@example.com/path"

        self.runtime.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")

        self._validate_sanitized_event(expected_message, task_name="Test Task")

    def test_sanitize_credentials_multiple_urls_with_credentials_leak(self):
        """ Test sanitization with multiple URLs containing credentials """
        message = "Failed to fetch from https://user1:pass1@host1.com/api and http://user2:pass2@host2.com/data"
        expected_message = "Failed to fetch from https://user1@host1.com/api and http://user2@host2.com/data"

        self.runtime.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")

        self._validate_sanitized_event(expected_message, task_name="Test Task")

    def test_sanitize_credentials_with_error_and_no_credentials(self):
        """  ERROR with 401 status code from jfrog.io """
        message = "ERROR: Failed to download metadata for repo 'packages-microsoft-com-prod': Status code: 401 for https://cec-aa.jfrog.io/artifactory/glib-rpm-hel9-lts-microsoft-com/repodata/repomd.xml"
        expected_message = "ERROR: Failed to download metadata for repo 'packages-microsoft-com-prod': Status code: 401 for https://cec-aa.jfrog.io/artifactory/glib-rpm-hel9-lts-microsoft-com/repodata/repomd.xml"

        self.runtime.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")

        self._validate_sanitized_event(expected_message, task_name="Test Task")

    def test_sanitize_credentials_with_error_and_credentials_leak(self):
        """  Curl error with buildbot:BuildBotToken credentials """
        message = ("Curl error (6): Couldn't resolve host 'packages.microsoft.com' Could not "
                   "retrieve mirrorlist https://buildbot:BuildBotToken@mirror.example.com/repodata/repomd.xml")
        expected_message = ("Curl error (6): Couldn't resolve host 'packages.microsoft.com' Could not "
                           "retrieve mirrorlist https://buildbot@mirror.example.com/repodata/repomd.xml")

        self.runtime.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")
        self._validate_sanitized_event(expected_message, task_name="Test Task")

    def test_sanitize_credentials_with_credentials_leak(self):
        """ ERROR with expired SSL certs and TESTTOKEN123456 """
        self._clear_events_folder()
        self.assertEqual(len([f for f in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', f)]), 0)

        message = ("ERROR: Customer environment error (expired SSL certs): "
                   "Command=sudo yum update -y --disablerepo='*' "
                   "--enablerepo='microsoft' !!Code=11 Out- Updating "
                   "Subscription Management repositories. "
                   "Unable to read consumer identity This system is not registered "
                   "with an entitlement server. Status code: 401 "
                   "for https://testuser:TESTTOKEN123456@packages-microsoft-com-prod/CENTRAL.rpm "
                   "Error: Failed to download metadata for repo 'packages-microsoft-com-prod': "
                   "Cannot download repomd.xml: All mirrors were tried")
        expected_message = ("ERROR: Customer environment error (expired SSL certs): "
                           "Command=sudo yum update -y --disablerepo='*' "
                           "--enablerepo='microsoft' !!Code=11 Out- Updating "
                           "Subscription Management repositories. "
                           "Unable to read consumer identity This system is not registered "
                           "with an entitlement server. Status code: 401 "
                           "for https://testuser@packages-microsoft-com-prod/CENTRAL.rpm "
                           "Error: Failed to download metadata for repo 'packages-microsoft-com-prod': "
                           "Cannot download repomd.xml: All mirrors were tried")

        self.runtime.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")

        # Validate exactly one event file was created
        event_files_count = len([f for f in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', f)])
        self.assertEqual(event_files_count, 1)
        self._validate_sanitized_event(expected_message, task_name="Test Task")

    def test_sanitize_credentials_exception_handling(self):
        """ Test exception handling: passing None should return the input unchanged """
        result = self.runtime.telemetry_writer.credential_sanitizer.sanitize(None)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()

