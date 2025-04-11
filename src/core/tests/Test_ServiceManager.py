# Copyright 2025 Microsoft Corporation
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

from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor
from core.src.core_logic.ServiceManager import ServiceManager
from core.src.core_logic.ServiceManager import ServiceInfo


class TestServiceManager(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), legacy_mode=True)
        self.service_manager = ServiceManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer,ServiceInfo("AutoAssessment", "Auto assessment service", "path"))
        self.service_manager.service_name = "test_service"
        self.mock_systemd_service_unit_path = "/etc/systemd/system/{0}.service"

    def tearDown(self):
        self.runtime.stop()

    def mock_run_command_to_set_service_file_permission(self, cmd, no_output=False, chk_err=False):
        parts = cmd.split()
        if parts[1] == "chmod" and parts[2] == "644":
            return 0, "permissions set"
        else:
            raise Exception

    def mock_write_with_retry_valid(self, file_path_or_handle, data, mode='a+'):
        return

    def mock_invoke_systemctl(self, command, description):
        self.service_manager.invoke_systemctl_called = True
        if "start" in command:
            return 0, "Service started"
        elif "reload-or-restart" in command:
            return 0, "Reloading the service"
        elif "status" in command:
            return 0, "Getting the service status"
        elif "enable" in command or "is-enabled" in command:
            return 0, "Enabling the service or Checking Service is enabled"
        elif "disable" in command:
            return 0, "Disabling the service"
        elif "is-active" in command:
            return 0, "Checking if service is active"
        return 1, "Service not started"

    def test_create_service_unit_file(self):
        self.service_manager.env_layer.run_command_output = self.mock_run_command_to_set_service_file_permission
        self.service_manager.env_layer.file_system.write_with_retry = self.mock_write_with_retry_valid
        self.service_manager.create_service_unit_file(exec_start="/bin/bash " + self.service_manager.service_exec_path, desc="Microsoft Azure Linux Patch Extension - Auto Assessment")

    def test_start_service(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False

        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl

        # Act
        result = self.service_manager.start_service()

        # Assert
        self.assertTrue(result, "Service should be started")
        self.assertTrue(self.service_manager.invoke_systemctl_called)

    def test_reload_service(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False

        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl

        # Act
        result = self.service_manager.reload_service()

        # Assert
        self.assertTrue(result, "Reloading the service.")
        self.assertTrue(self.service_manager.invoke_systemctl_called)

    def test_stop_service(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False

        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl

        # Act
        result = self.service_manager.stop_service()

        # Assert
        self.assertFalse(result, "Service should not be started")
        self.assertTrue(self.service_manager.invoke_systemctl_called)

    def test_get_service_status(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False

        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl

        # Act
        result = self.service_manager.get_service_status()

        # Assert
        self.assertTrue(result, "Getting the service status")
        self.assertTrue(self.service_manager.invoke_systemctl_called)

    def test_enable_service(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False

        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl

        # Act
        result = self.service_manager.enable_service()

        # Assert
        self.assertTrue(result, "Enabling the service")
        self.assertTrue(self.service_manager.invoke_systemctl_called)

    def test_disable_service(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False

        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl

        # Act
        result = self.service_manager.disable_service()

        # Assert
        self.assertTrue(result, "Disabling the service")
        self.assertTrue(self.service_manager.invoke_systemctl_called)

    def test_is_service_active(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False

        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl

        # Act
        result = self.service_manager.is_service_active()

        # Assert
        self.assertTrue(result, "Checking if service is active")
        self.assertTrue(self.service_manager.invoke_systemctl_called)

    def test_is_service_enabled(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False

        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl

        # Act
        result = self.service_manager.is_service_enabled()

        # Assert
        self.assertTrue(result, "Checking if service is enabled")
        self.assertTrue(self.service_manager.invoke_systemctl_called)


if __name__ == '__main__':
    unittest.main()
