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
import sys
import unittest
# Conditional import for StringIO
try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import StringIO  # Python 3

from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestBootstrapper(unittest.TestCase):
    # def __init__(self, methodName: str = "runTest"):
    #     super().__init__(methodName)
    
    def setUp(self):
        self.sudo_check_status_attempts = 0
        Constants.SET_CHECK_SUDO_STATUS_TRUE = False  # override check_sudo_status in RuntimeCompositor
        argument_composer = ArgumentComposer()
        argument_composer.operation = Constants.ASSESSMENT
        self.argv = argument_composer.get_composed_arguments()
        self.runtime = RuntimeCompositor(self.argv, legacy_mode=True, package_manager_name=Constants.APT)

    def tearDown(self):
        self.sudo_check_status_attempts = 0
        Constants.SET_CHECK_SUDO_STATUS_TRUE = True
        self.runtime.stop()

    # regions mock
    def mock_false_run_command_output(self, command, no_output=False, chk_err=True):
        """Mock a failed sudo check status command output to test multiple attempts logic."""
        # Mock failure to trigger multiple attempts logic in check_sudo_status
        return (1, "[sudo] password for user:\nFalse")

    def mock_insufficient_run_command_output(self, command, no_output=False, chk_err=True):
        """Mock an insufficient output line in sudo check status command output."""
        # Mock failure to trigger multiple attempts logic in check_sudo_status
        return (1, "[sudo] password for user:")

    def mock_unexpected_output_run_command_output(self, command, no_output=False, chk_err=True):
        """Mock an unexpected output line in sudo check status command output."""
        # Mock failure to trigger multiple attempts logic in check_sudo_status
        return (1, "[sudo] password for user:\nUnexpectedOutput")

    def mock_run_command_output_with_attempts(self, command, no_output=False, chk_err=True):
        """Mock 3 failed sudo check status attempts followed by a success on the 4th attempts."""
        self.sudo_check_status_attempts += 1

        # Mock failure on the first two attempts
        if self.sudo_check_status_attempts <= 2:
            return (1, "[sudo] password for user:\nFalse")

        # Mock success (True) on the 3rd attempt
        elif self.sudo_check_status_attempts == 3:
            return (0, "uid=0(root) gid=0(root) groups=0(root)\nTrue")
    
    def mock_get_arguments_configuration(self, argv):
        raise Exception("EXCEPTION during patch management core bootstrap:")
    
    def mock_os_path_exists(self, path):
        return True

    def mock_os_path_getsize(self, path):
        return Constants.MAX_AUTO_ASSESSMENT_LOGFILE_SIZE_IN_BYTES + 1

    def mock_os_remove(self, path):
        raise Exception("Mocked exception in os.remove")
    # end regions mock

    def test_check_sudo_status_all_attempts_failed(self):
        # Set raise_if_not_sudo=False to test the `return False` all attempts failed
        self.runtime.env_layer.run_command_output = self.mock_false_run_command_output

        result = self.runtime.bootstrapper.check_sudo_status_with_attempts(raise_if_not_sudo=False)

        # Verify check_sudo_status_with_attempts is False
        self.assertEqual(result, None, "Expected check_sudo_status_with_attempts to return None after all attempts failed")

    def test_check_sudo_status_throw_exception(self):
        # Set raise_if_not_sudo=True to throw exception) after all retries
        self.runtime.env_layer.run_command_output = self.mock_false_run_command_output
        with self.assertRaises(Exception) as context:
            self.runtime.bootstrapper.check_sudo_status_with_attempts(raise_if_not_sudo=True)

        # Verify exception msg contains the expected failure text
        self.assertTrue("Unable to invoke sudo successfully" in str(context.exception))

    def test_check_sudo_status_insufficient_output_lines(self):
        # Test insufficient output lines to raise exception after all retries
        self.runtime.env_layer.run_command_output = self.mock_insufficient_run_command_output

        with self.assertRaises(Exception) as context:
            self.runtime.bootstrapper.check_sudo_status_with_attempts()

        # Verify exception msg contains the expected failure text
        self.assertTrue("Unexpected sudo check result" in str(context.exception))

    def test_check_sudo_status_unexpected_output_lines(self):
        # Test unexpected output with neither false or true to raise exception after all retries
        self.runtime.env_layer.run_command_output = self.mock_unexpected_output_run_command_output

        with self.assertRaises(Exception) as context:
            self.runtime.bootstrapper.check_sudo_status_with_attempts()

        # Verify exception msg contains the expected failure text
        self.assertTrue("Unexpected sudo check result" in str(context.exception))

    def test_check_sudo_status_succeeds_on_third_attempt(self):
        # Test check sudo status after 2 failed attempts followed by success (true)
        self.runtime.env_layer.run_command_output = self.mock_run_command_output_with_attempts

        # Attempt to check sudo status, succeed (true) on the 3rd attempt
        result = self.runtime.bootstrapper.check_sudo_status_with_attempts(raise_if_not_sudo=True)

        # Verify the result is success (True)
        self.assertTrue(result, "Expected check_sudo_status to succeed on the 3rd attempts")

        # Verify 3 attempts were made
        self.assertEqual(self.sudo_check_status_attempts, 3, "Expected exactly 3 attempts in check_sudo_status")
        
    def test_build_out_container_throw_exception(self):
        # Test build_out_container throws exception when no container name is provided
        
        # Save original methods
        original_get_arguments_configuration = self.runtime.bootstrapper.configuration_factory.get_arguments_configuration
        
        # Mock
        self.runtime.bootstrapper.configuration_factory.get_arguments_configuration = self.mock_get_arguments_configuration
        
        # Verify exception
        with self.assertRaises(Exception) as context:
            self.runtime.bootstrapper.build_out_container()
            
        # Restore original methods
        self.runtime.bootstrapper.configuration_factory.get_arguments_configuration = original_get_arguments_configuration
        self.runtime.stop()
        
    def test_reset_auto_assessment_log_file_if_needed_raise_exception(self):
        # Arrange, Capture stdout
        captured_output = StringIO()
        original_output = sys.stdout
        sys.stdout = captured_output  # Redirect stdout to the StringIO object
        
        # Save original methods
        self.runtime.bootstrapper.auto_assessment_only = True
        original_path_exists = os.path.exists
        original_path_getsize = os.path.getsize
        original_os_remove = os.remove
        
        # Mock
        os.path.exists = self.mock_os_path_exists
        os.path.getsize = self.mock_os_path_getsize
        os.remove = self.mock_os_remove
        
        self.runtime.bootstrapper.reset_auto_assessment_log_file_if_needed()
        
        # Restore stdout
        sys.stdout = original_output
        
        # Assert
        output = captured_output.getvalue()
        self.assertIn("INFO: Error while checking/removing auto-assessment log file.", output)  # Verify the log output contains the expected text
        
        # Restore original methods
        os.path.exists = original_path_exists
        os.path.getsize = original_path_getsize
        os.remove = original_os_remove
        self.runtime.stop()
        
        
if __name__ == '__main__':
    unittest.main()
