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
from core.src.core_logic.TimerManager import TimerManager
from core.src.core_logic.ServiceManager import ServiceInfo

class TestTimerManager(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), legacy_mode=True)
        self.service_manager = TimerManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, ServiceInfo("AutoAssessment","Auto assessment service","path"))
        self.service_manager.service_name = "test_service"
        self.mock_systemd_timer_unit_path = "/etc/systemd/system/{0}.timer"

    def tearDown(self):
        self.runtime.stop()

    def mock_run_command_to_set_service_file_permission(self, cmd, no_output=False, chk_err=False):
        parts = cmd.split()
        if parts[1] == "chmod" and parts[2] == "644":
            return 0, "permissions set"

    def mock_write_with_retry_valid(self, file_path_or_handle, data, mode='a+'):
        return

    def mock_invoke_systemctl(self, command, description):
        self.service_manager.invoke_systemctl_called = True
        if "start" in command and "restart" not in command:
            return 0, "Timer started"
        elif "stop" in command:
            return 0, "Timer stopped"
        elif "reload-or-restart" in command:
            return 0, "Reloading the timer"
        elif "status" in command:
            return 0, "Getting the timer status"
        elif "enable" in command or "is-enable" in command:
            return 0, "Enabling the timer or checking timer is enabled"
        elif "disable" in command:
            return 0, "Disable the timer"
        elif "is-active" in command:
            return 0, "Checking if timer is active"

    def test_create_timer_unit_file(self):
        self.service_manager.env_layer.run_command_output = self.mock_run_command_to_set_service_file_permission
        self.service_manager.env_layer.file_system.write_with_retry = self.mock_write_with_retry_valid
        self.service_manager.create_timer_unit_file(desc="Microsoft Azure Linux Patch Extension - Auto Assessment Timer")

    def test_start_timer(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False
        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl

        # Act
        result = self.service_manager.start_timer()

        # Assert
        self.assertTrue(result, "Timer should be started")
        self.assertTrue(self.service_manager.invoke_systemctl_called)

    def test_stop_timer(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False
        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl

        # Act
        result = self.service_manager.stop_timer()

        # Assert
        self.assertTrue(result, "Timer should be stopped")
        self.assertTrue(self.service_manager.invoke_systemctl_called)
        
    def test_reload_timer(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False
        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl
        
        # Act
        result = self.service_manager.reload_timer()
        
        # Assert
        self.assertTrue(result, "Reload timer")
        self.assertTrue(self.service_manager.invoke_systemctl_called)
        
    def test_enable_timer(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False
        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl
        
        # Act
        result = self.service_manager.enable_timer()
        
        # Assert
        self.assertTrue(result, "Timer should be enabled")
        self.assertTrue(self.service_manager.invoke_systemctl_called)
    
    def test_disable_timer(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False
        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl
        
        # Act
        result = self.service_manager.disable_timer()
        
        # Assert
        self.assertTrue(result, "Timer should be disabled")
        self.assertTrue(self.service_manager.invoke_systemctl_called)
    
    def test_get_timer_status(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False
        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl
        
        # Act
        result = self.service_manager.get_timer_status()
        
        # Assert
        self.assertTrue(result, "Get timer status")
        self.assertTrue(self.service_manager.invoke_systemctl_called)
    
    def test_timer_is_enable(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False
        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl
        
        # Act
        result = self.service_manager.is_timer_enabled()
        
        # Assert
        self.assertTrue(result, "Check if timer is enable")
        self.assertTrue(self.service_manager.invoke_systemctl_called)
    
    def test_timer_is_active(self):
        # Set method calls
        self.service_manager.invoke_systemctl_called = False
        self.service_manager.invoke_systemctl = self.mock_invoke_systemctl
        
        # Act
        result = self.service_manager.is_timer_active()
        
        # Assert
        self.assertTrue(result, "Check if timer is active")
        self.assertTrue(self.service_manager.invoke_systemctl_called)


if __name__ == '__main__':
    unittest.main()
