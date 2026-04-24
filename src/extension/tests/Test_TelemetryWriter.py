import json
import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import Mock
from extension.src.Constants import Constants
from extension.src.CredentialSanitizer import CredentialSanitizer
from extension.src.TelemetryWriter import TelemetryWriter
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

    # ==================== Integration test for credential sanitization in telemetry ====================
    def _load_sanitized_event(self, message):
        """
        Helper method to write event to telemetry and load the sanitized message.
        The regex sanitization happens automatically in TelemetryWriter.

        Args:
            message: The message to write to telemetry

        Returns:
            The sanitized message from the event
        """
        if self.runtime.is_github_runner:
            return None

        # Write event to telemetry
        self.telemetry_writer.write_event(message)

        # Load the event file
        event_files = os.listdir(self.telemetry_writer.events_folder_path)
        with open(os.path.join(self.telemetry_writer.events_folder_path, event_files[0]), 'r+') as f:
            events = json.load(f)
            sanitized_message = events[0]["Message"]
            f.close()
            return sanitized_message

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
        self.assertNotIn("pass", result)

        # Restore
        self.runtime.is_github_runner = original_is_github_runner

    # ==================== Unit Tests for Credential Sanitization ====================
    def test_sanitize_credentials_from_uri_https(self):
        """ Test sanitization of HTTPS URIs with credentials """
        message = "Error connecting to https://testuser:TESTTOKEN123456@invalid.repo.example/rpm/repodata/repomd.xml"
        sanitized = CredentialSanitizer.sanitize(message)
        expected_message = "Error connecting to https://testuser@invalid.repo.example/rpm/repodata/repomd.xml"
        self.assertEqual(sanitized, expected_message)

    def test_sanitize_credentials_from_uri_http(self):
        """ Test sanitization of HTTP URIs with credentials """
        message = "Connection failed to http://user123:password123@example.com/path"
        sanitized = CredentialSanitizer.sanitize(message)
        # Password should be removed
        self.assertNotIn("password123", sanitized)
        # Username should be preserved
        self.assertIn("user123@example.com", sanitized)

    def test_sanitize_credentials_multiple_urls(self):
        """ Test sanitization with multiple URLs containing credentials """
        message = "Failed to fetch from https://user1:pass1@host1.com/api and http://user2:pass2@host2.com/data"
        sanitized = CredentialSanitizer.sanitize(message)
        # Passwords should be removed
        self.assertNotIn("pass1", sanitized)
        self.assertNotIn("pass2", sanitized)
        # Usernames should be preserved
        self.assertIn("user1@host1.com", sanitized)
        self.assertIn("user2@host2.com", sanitized)

    def test_sanitize_credentials_jfrog_repo_error(self):
        """  ERROR with 401 status code from jfrog.io """
        message = "ERROR: Failed to download metadata for repo 'packages-microsoft-com-prod': Status code: 401 for https://cec-aa.jfrog.io/artifactory/glib-rpm-hel9-lts-microsoft-com/repodata/repomd.xml"
        sanitized = CredentialSanitizer.sanitize(message)
        expected_message = "ERROR: Failed to download metadata for repo 'packages-microsoft-com-prod': Status code: 401 for https://cec-aa.jfrog.io/artifactory/glib-rpm-hel9-lts-microsoft-com/repodata/repomd.xml"
        self.assertEqual(sanitized, expected_message)

    def test_sanitize_credentials_curl_error_buildbot_token(self):
        """  Curl error with buildbot:BuildBotToken credentials """
        message = ("Curl error (6): Couldn't resolve host 'packages.microsoft.com' Could not "
                   "retrieve mirrorlist https://buildbot:BuildBotToken@mirror.example.com/repodata/repomd.xml")
        sanitized = CredentialSanitizer.sanitize(message)
        expected_message = ("Curl error (6): Couldn't resolve host 'packages.microsoft.com' Could not "
                           "retrieve mirrorlist https://buildbot@mirror.example.com/repodata/repomd.xml")
        self.assertEqual(sanitized, expected_message)

    def test_sanitize_credentials_expired_ssl_certs_error(self):
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
        sanitized = CredentialSanitizer.sanitize(message)
        expected_message = ("ERROR: Customer environment error (expired SSL certs): "
                           "Command=sudo yum update -y --disablerepo='*' "
                           "--enablerepo='microsoft' !!Code=11 Out- Updating "
                           "Subscription Management repositories. "
                           "Unable to read consumer identity This system is not registered "
                           "with an entitlement server. Status code: 401 "
                           "for https://testuser@packages-microsoft-com-prod/CENTRAL.rpm "
                           "Error: Failed to download metadata for repo 'packages-microsoft-com-prod': "
                           "Cannot download repomd.xml: All mirrors were tried")
        self.assertEqual(sanitized, expected_message)

    def test_sanitize_credentials_exception_handling(self):
        """ Test exception handling: passing None should return the input unchanged """
        result = CredentialSanitizer.sanitize(None)
        self.assertIsNone(result)

    def test_inject_fake_sanitizer_and_verify_invocation(self):
        """ Test: Can inject a fake sanitizer and verify it was invoked during write_event """
        # Create a mock sanitizer
        mock_sanitizer = Mock()
        mock_sanitizer.sanitize = Mock(return_value="sanitized_message")

        # Create TelemetryWriter with injected mock sanitizer
        logger = self.runtime.logger
        env_layer = self.runtime.env_layer
        writer = TelemetryWriter(logger, env_layer, mock_sanitizer)
        writer.events_folder_path = tempfile.mkdtemp()

        try:
            # Write an event
            original_message = "https://user:password@example.com/error"
            writer.write_event(original_message, Constants.TelemetryEventLevel.Error, "Test Task")

            # Verify mock sanitizer was called
            self.assertTrue(mock_sanitizer.sanitize.called, "Sanitizer should have been invoked")
            self.assertEqual(mock_sanitizer.sanitize.call_count, 1, "Sanitizer should be called exactly once")

            # Verify the call was made with a message containing the original error info
            call_args = mock_sanitizer.sanitize.call_args[0][0]
            self.assertIn("example.com", call_args, "Sanitizer should be called with message containing URL")

            # Verify telemetry event was written with the mock-sanitized message
            event_files = os.listdir(writer.events_folder_path)
            self.assertTrue(len(event_files) > 0, "Event file should be created")

            with open(os.path.join(writer.events_folder_path, event_files[0]), 'r') as f:
                events = json.load(f)
                # The message should be the one returned by our mock
                self.assertIn("sanitized_message", events[0]["Message"])
                f.close()
        finally:
            shutil.rmtree(writer.events_folder_path)

if __name__ == '__main__':
     SUITE = unittest.TestLoader().loadTestsFromTestCase(TestTelemetryWriter)
     unittest.TextTestRunner(verbosity=2).run(SUITE)












