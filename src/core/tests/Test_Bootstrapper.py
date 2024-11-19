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
import unittest

from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestBootstrapper(unittest.TestCase):
    def setUp(self):
        self.sudo_check_status_attempts = 0
        Constants.SET_CHECK_SUDO_STATUS_TRUE = False
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
        """Mock a failed sudo check status command output to test retry logic."""
        # Mock failure to trigger retry logic in check_sudo_status
        return (1, "[sudo] password for user:\nFalse")

    def mock_insufficient_run_command_output(self, command, no_output=False, chk_err=True):
        """Mock a insufficient output line in sudo check status command output."""
        # Mock failure to trigger retry logic in check_sudo_status
        return (1, "[sudo] password for user:")

    def mock_unexpected_output_run_command_output(self, command, no_output=False, chk_err=True):
        """Mock a insufficient output line in sudo check status command output."""
        # Mock failure to trigger retry logic in check_sudo_status
        return (1, "[sudo] password for user:\nUnexpectedOutput")

    def mock_retry_run_command_output(self, command, no_output=False, chk_err=True):
        """Mock 3 failed sudo check status attempts followed by a success on the 4th attempt."""
        self.sudo_check_status_attempts += 1

        # Mock failure on the first two attempts
        if self.sudo_check_status_attempts <= 2:
            return (1, "[sudo] password for user:\nFalse")

        # Mock success (True) on the 3rd attempt
        elif self.sudo_check_status_attempts == 3:
            return (0, "uid=0(root) gid=0(root) groups=0(root)\nTrue")
    # end regions mock

    def test_check_sudo_status_all_attempts_failed(self):
        # Set raise_if_not_sudo=False to test the `return False` all attempts failed
        self.runtime.env_layer.run_command_output = self.mock_false_run_command_output
        result = self.runtime.bootstrapper.check_sudo_status_with_retry(raise_if_not_sudo=False)
        self.assertFalse(result, "Expected check_sudo_status to return False after all attempts failed")

    def test_check_sudo_status_throw_exception(self):
        # Set raise_if_not_sudo=True to throw exception) after all retries
        self.runtime.env_layer.run_command_output = self.mock_false_run_command_output
        with self.assertRaises(Exception) as context:
            self.runtime.bootstrapper.check_sudo_status_with_retry(raise_if_not_sudo=True)

        # Verify exception msg contains the expected failure text
        self.assertTrue("Unable to invoke sudo successfully" in str(context.exception))

    def test_check_sudo_status_insufficient_output_lines(self):
        # Test insufficient output lines to raise exception after all retries
        self.runtime.env_layer.run_command_output = self.mock_insufficient_run_command_output

        with self.assertRaises(Exception) as context:
            self.runtime.bootstrapper.check_sudo_status_with_retry()

        # Verify exception msg contains the expected failure text
        self.assertTrue("Unexpected sudo check result" in str(context.exception))

    def test_check_sudo_status_unexpected_output_lines(self):
        # Test unexpected output with neither false or true to raise exception after all retries
        self.runtime.env_layer.run_command_output = self.mock_unexpected_output_run_command_output

        with self.assertRaises(Exception) as context:
            self.runtime.bootstrapper.check_sudo_status_with_retry()

        # Verify exception msg contains the expected failure text
        self.assertTrue("Unexpected sudo check result" in str(context.exception))

    def test_check_sudo_status_succeeds_on_third_attempt(self):
        # Test retry logic in check sudo status after 2 failed attempts followed by success (true)
        self.runtime.env_layer.run_command_output = self.mock_retry_run_command_output

        # Attempt to check sudo status, succeed (true) on the 3rd attempt
        result = self.runtime.bootstrapper.check_sudo_status_with_retry(raise_if_not_sudo=True)

        # Verify the result is success (True)
        self.assertTrue(result, "Expected check_sudo_status to succeed on the 3rd attempts")

        # Verify 3 attempts were made
        self.assertEqual(self.sudo_check_status_attempts, 3, "Expected exactly 3 attempts in check_sudo_status")


if __name__ == '__main__':
    unittest.main()
