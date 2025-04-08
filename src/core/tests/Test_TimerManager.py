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
        self.container = self.runtime.container

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

    def test_create_timer_unit_file(self):
        service_manager = TimerManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, ServiceInfo("AutoAssessment","Auto assessment service","path"))
        service_manager.env_layer.run_command_output = self.mock_run_command_to_set_service_file_permission
        service_manager.env_layer.file_system.write_with_retry = self.mock_write_with_retry_valid
        service_manager.create_timer_unit_file(desc="Microsoft Azure Linux Patch Extension - Auto Assessment Timer")


if __name__ == '__main__':
    unittest.main()
