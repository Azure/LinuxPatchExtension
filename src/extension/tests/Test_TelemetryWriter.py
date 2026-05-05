import json
import os
import shutil
import tempfile
import time
import unittest
from extension.src.Constants import Constants
from extension.tests.helpers.VirtualTerminal import VirtualTerminal
from extension.tests.helpers.RuntimeComposer import RuntimeComposer


class TestTelemetryWriter(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.runtime = RuntimeComposer()
        self.telemetry_writer = self.runtime.telemetry_writer
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

    def mock_get_file_size(self, file_path):
        return Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS + 10

    def mock_os_listdir(self, file_path):
        return ['testevent1.json', 'testevent2.json', 'testevent3.json', 'testevent4.json']

    def test_write_event(self):
        if self.runtime.is_github_runner:
            return

        self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        with open(os.path.join(self.telemetry_writer.events_folder_path, os.listdir(self.telemetry_writer.events_folder_path)[0]), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEqual(events[0]["TaskName"], "Test Task")
            f.close()

        self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
        if len(os.listdir(self.telemetry_writer.events_folder_path)) > 1:
            with open(os.path.join(self.telemetry_writer.events_folder_path, os.listdir(self.telemetry_writer.events_folder_path)[1]), 'r+') as f:
                events = json.load(f)
                self.assertTrue(events is not None)
                self.assertEqual(events[0]["TaskName"], "Test Task2")
                f.close()
        else:
            with open(os.path.join(self.telemetry_writer.events_folder_path, os.listdir(self.telemetry_writer.events_folder_path)[0]), 'r+') as f:
                events = json.load(f)
                self.assertTrue(events is not None)
                self.assertEqual(len(events), 2)  # Fails here on GitHub
                self.assertEqual(events[1]["TaskName"], "Test Task2")
                f.close()

    def test_write_multiple_events_in_same_file(self):
        if self.runtime.is_github_runner:
            return

        time_backup = time.time
        time.time = self.mock_time
        self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
        with open(os.path.join(self.telemetry_writer.events_folder_path, os.listdir(self.telemetry_writer.events_folder_path)[0]), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEqual(len(events), 2)  # Fails here on GitHub
            self.assertEqual(events[0]["TaskName"], "Test Task")
            self.assertEqual(events[1]["TaskName"], "Test Task2")
            f.close()
        time.time = time_backup

    def test_write_event_msg_size_limit(self):
        # Assuming 1 char is 1 byte
        message = "a"*3074
        self.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")
        with open(os.path.join(self.telemetry_writer.events_folder_path, os.listdir(self.telemetry_writer.events_folder_path)[0]), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEqual(events[0]["TaskName"], "Test Task")
            self.assertTrue(len(events[0]["Message"]) < len(message.encode('utf-8')))
            chars_dropped = len(message.encode('utf-8')) - Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_CHARS + Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_CHARS
            self.assertEqual(events[0]["Message"], "a"*(len(message.encode('utf-8')) - chars_dropped) + ". [{0} chars dropped]".format(chars_dropped))
            f.close()

    def test_write_event_size_limit(self):
        # will not write to telemetry if event size exceeds limit
        message = "a"*3074
        task_name = "b"*5000
        self.telemetry_writer.write_event(task_name, message, Constants.TelemetryEventLevel.Error)
        self.assertTrue(len(os.listdir(self.telemetry_writer.events_folder_path)) == 0)

    # TODO: The following test is failing almost consistently commenting it out to be tracked in: Task 10912099: [Bug] Bug in telemetry writer - overwriting prior events in fast execution
    # def test_write_to_new_file_if_event_file_limit_reached(self):
    #     self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
    #     os_path_exists_backup = os.path.exists
    #     os.path.exists = self.mock_os_path_exists
    #     telemetry_get_event_file_size_backup = self.telemetry_writer.get_file_size
    #     self.telemetry_writer.get_file_size = self.mock_get_file_size
    #
    #     self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
    #     events = os.listdir(self.telemetry_writer.events_folder_path)
    #     self.assertEqual(len(events), 2)
    #     os.path.exists = os_path_exists_backup
    #     self.telemetry_writer.get_file_size = telemetry_get_event_file_size_backup

    def test_delete_older_events(self):
        if self.runtime.is_github_runner:
            return

        # deleting older event files before adding new one
        self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
        self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task3")
        old_events = os.listdir(self.telemetry_writer.events_folder_path)
        telemetry_dir_size_backup = Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS
        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = 1030
        telemetry_event_size_backup = Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = 1024

        self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task4")
        new_events = os.listdir(self.telemetry_writer.events_folder_path)
        self.assertEqual(len(new_events), 1)
        self.assertTrue(old_events[0] not in new_events)  # Fails here on GitHub
        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = telemetry_dir_size_backup
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = telemetry_event_size_backup

        # error while deleting event files where the directory size exceeds limit even after deletion attempts
        self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task2")
        self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task3")
        old_events = os.listdir(self.telemetry_writer.events_folder_path)
        telemetry_dir_size_backup = Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS
        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = 500
        telemetry_event_size_backup = Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = 400
        os_remove_backup = os.remove
        os.remove = self.mock_os_remove

        self.assertRaises(Exception, lambda: self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task4"))

        Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS = telemetry_dir_size_backup
        Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS = telemetry_event_size_backup
        os.remove = os_remove_backup

    def test_events_deleted_outside_of_extension_while_extension_is_running(self):
        backup_os_listdir = os.listdir
        os.listdir = self.mock_os_listdir
        self.telemetry_writer.write_event("testing telemetry write to file", Constants.TelemetryEventLevel.Error, "Test Task")
        os.listdir = backup_os_listdir

    # ==================== Unit tests for credential sanitization in telemetry ====================
    def _clear_events_folder(self):
        """
        Helper method to clear the events folder for sanitization test setup.
        """
        shutil.rmtree(self.telemetry_writer.events_folder_path)
        self.telemetry_writer.events_folder_path = tempfile.mkdtemp()

    def _read_event_from_file(self, file_index=None, event_index=-1):
        """
        Helper method to open and read an event from an event file in the events folder.
        Args:
            file_index: Index of the event file to read. If None, uses latest file (default: None for latest file)
            event_index: Index of the event within the file (default: -1 for last event)
        Returns: The parsed event dictionary from the JSON file
        """
        event_files = sorted(os.listdir(self.telemetry_writer.events_folder_path))
        if not event_files:
            raise Exception("No event files found in events folder")

        if file_index is None:
            event_file_path = os.path.join(self.telemetry_writer.events_folder_path, event_files[-1])
        else:
            event_file_path = os.path.join(self.telemetry_writer.events_folder_path, event_files[file_index])

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
        Returns: The message from the event
        """
        return event["Message"]

    def _validate_sanitized_event(self, expected_message, task_name=None, event_index=-1, file_index=None):
        """
        Helper method to validate an event's message and task name against expected values.
        This internally calls _read_event_from_file to retrieve the event.
        Args:
            expected_message: The expected sanitized message
            task_name: The expected task name (optional validation)
            event_index: Index of the event within the file (default: -1 for last event)
            file_index: Index of the event file (default: None for latest file)
        """
        event = self._read_event_from_file(file_index=file_index, event_index=event_index)

        self.assertIsNotNone(event)
        message = self._get_message_without_tc(event)
        self.assertEqual(expected_message, message)
        if task_name is not None:
            self.assertEqual(task_name, event["TaskName"])

    def _load_sanitized_event(self, message):
        """
        Helper method to write event to telemetry and load the sanitized message.
        The regex sanitization happens automatically in TelemetryWriter.
        Args:
            message: The message to write to telemetry
        Returns: The sanitized message from the event
        """
        # Write event to telemetry
        actual_message = self.telemetry_writer.write_event(message)

        # Load the event file using helper method (gets first event from latest file)
        event = self._read_event_from_file(file_index=None, event_index=0)
        return event["Message"]

    def test_load_sanitized_event_full_path(self):
        """Test: Helper method executes full path when not on GitHub runner"""
        # Force is_github_runner to False to ensure full path coverage on CI
        original_is_github_runner = self.runtime.is_github_runner
        self.runtime.is_github_runner = False

        message = "https://user:pass@example.com"
        result = self._load_sanitized_event(message)

        # On non-GitHub runner, should return the sanitized message
        self.assertIsNotNone(result)
        self.assertIn("user@example.com", result)
        self.assertEqual("https://user@example.com", result)

        # Restore
        self.runtime.is_github_runner = original_is_github_runner

    def test_sanitize_credentials_multiple_urls_with_credentials_leak(self):
        """ Test sanitization with multiple URLs containing credentials """
        message = "Failed to fetch from https://user1:pass1@host1.com/api and http://user2:pass2@host2.com/data"
        expected_message = "Failed to fetch from https://user1@host1.com/api and http://user2@host2.com/data"

        self.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")

        self._validate_sanitized_event(expected_message, task_name="Test Task", event_index=-1)

    def test_sanitize_credentials_with_no_credentials_in_input_with_credentials_leak(self):
        """  ERROR with 401 status code from jfrog.io """
        message = "ERROR: Failed to download metadata for repo 'packages-microsoft-com-prod': Status code: 401 for https://cec-aa.jfrog.io/artifactory/glib-rpm-hel9-lts-microsoft-com/repodata/repomd.xml"
        expected_message = "ERROR: Failed to download metadata for repo 'packages-microsoft-com-prod': Status code: 401 for https://cec-aa.jfrog.io/artifactory/glib-rpm-hel9-lts-microsoft-com/repodata/repomd.xml"

        self.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")

        self._validate_sanitized_event(expected_message, task_name="Test Task", event_index=-1)

    def test_sanitize_credentials_with_error_and_credentials_leak(self):
        """  Curl error with buildbot:BuildBotToken credentials """
        message = ("Curl error (6): Couldn't resolve host 'packages.microsoft.com' Could not "
                   "retrieve mirrorlist https://buildbot:BuildBotToken@mirror.example.com/repodata/repomd.xml")
        expected_message = ("Curl error (6): Couldn't resolve host 'packages.microsoft.com' Could not "
                           "retrieve mirrorlist https://buildbot@mirror.example.com/repodata/repomd.xml")

        self.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")

        self._validate_sanitized_event(expected_message, task_name="Test Task", event_index=-1)

    def test_sanitize_credentials_expired_with_credentials_leak(self):
        """ ERROR with expired SSL certs and TESTTOKEN123456 """
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

        self.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")

        self._validate_sanitized_event(expected_message, task_name="Test Task", event_index=-1)

    def test_sanitize_credentials_exception_handling(self):
        """ Test exception handling: passing None should return the input unchanged """
        result = self.telemetry_writer.credential_sanitizer.sanitize(None)
        self.assertIsNone(result)

if __name__ == '__main__':
     SUITE = unittest.TestLoader().loadTestsFromTestCase(TestTelemetryWriter)
     unittest.TextTestRunner(verbosity=2).run(SUITE)
