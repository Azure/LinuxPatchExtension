# Copyright 2026 Microsoft Corporation
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
import unittest

from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestPackageManagerErrorFormatting(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.TDNF)
        self.package_manager = self.runtime.container.get('package_manager')

    def tearDown(self):
        self.runtime.stop()

    def test_prefers_actionable_output_line(self):
        output = "Loading repository data\nUnable to download repository metadata\nCommand exited"

        message = self.package_manager.format_package_manager_failure_message(1, output)

        self.assertEqual(message, "TDNF failed with exit code 1: Unable to download repository metadata")

    def test_uses_last_output_line_when_no_error_marker_exists(self):
        output = "Loading repository data\nRepository metadata is unavailable"

        message = self.package_manager.format_package_manager_failure_message(2, output)

        self.assertEqual(message, "TDNF failed with exit code 2: Repository metadata is unavailable")

    def test_redacts_sensitive_output_and_honors_status_limit(self):
        output = ("Failed to fetch https://user:password@packages.example/repo?"
                  "token=secret&sig=signature Authorization: Bearer bearer-secret " + ("x" * 200))

        message = self.package_manager.format_package_manager_failure_message(3, output)

        self.assertNotIn("password", message)
        self.assertNotIn("secret", message)
        self.assertNotIn("signature", message)
        self.assertLessEqual(len(message), Constants.STATUS_ERROR_MSG_SIZE_LIMIT_IN_CHARACTERS)
        self.assertTrue(message.endswith("..."))

    def test_redacts_token_only_url_credentials(self):
        output = "Failed to fetch https://secret-token@packages.example/repo"

        message = self.package_manager.format_package_manager_failure_message(3, output)

        self.assertEqual(message, "TDNF failed with exit code 3: Failed to fetch https://***@packages.example/repo")

    def test_empty_output_directs_customer_to_extension_logs(self):
        message = self.package_manager.format_package_manager_failure_message(4, "")

        self.assertEqual(message, "TDNF failed with exit code 4. Review extension logs for details.")

    def test_invoke_package_manager_writes_customer_summary_to_status(self):
        self.runtime.status_handler.set_current_operation(Constants.ASSESSMENT)
        self.runtime.env_layer.run_command_output = lambda cmd, no_output=False, chk_err=True: (5, "Preparing transaction\nError: package dependency conflict")

        self.package_manager.invoke_package_manager_advanced("sudo tdnf update", raise_on_exception=False)

        with open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            status = json.load(file_handle)
        summary = json.loads(status[0]["status"]["substatus"][0]["formattedMessage"]["message"])
        self.assertEqual(summary["errors"]["details"][0]["message"], "TDNF failed with exit code 5: Error: package dependency conflict")


if __name__ == '__main__':
    unittest.main()
