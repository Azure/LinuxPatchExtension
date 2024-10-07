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
import os.path
import unittest

from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestServiceManager(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True)

        self.runtime.service_manager.service_name = "test_service"
        self.mock_systemd_service_unit_path = "/etc/systemd/system/{0}.service"

        self.runtime.service_manager.stop_service_called = False
        self.runtime.service_manager.disable_service_called = False
        self.runtime.service_manager.systemctl_daemon_reload_called = False

        self.runtime.service_manager.stop_service = self.mock_stop_service
        self.runtime.service_manager.disable_service = self.mock_disable_service
        self.runtime.service_manager.systemctl_daemon_reload = self.mock_systemctl_daemon_reload

    def tearDown(self):
        self.runtime.stop()

    # mocks
    def mock_stop_service(self):
        self.runtime.service_manager.stop_service_called = True

    def mock_disable_service(self):
        self.runtime.service_manager.disable_service_called = True

    def mock_systemctl_daemon_reload(self):
        self.runtime.service_manager.systemctl_daemon_reload_called = True

    # end mocks

    def test_remove_service_path_exists(self):
        # Arrange
        original_path_exists = os.path.exists
        original_os_remove = os.remove
        os.path.exists = lambda path: True
        os.remove = lambda path: None

        # Act
        self.runtime.service_manager.remove_service()

        # Assert
        self.assertTrue(self.runtime.service_manager.stop_service)
        self.assertTrue(self.runtime.service_manager.disable_service)
        self.assertTrue(self.runtime.service_manager.systemctl_daemon_reload)

        # Restore
        os.path.exists = original_path_exists
        os.remove = original_os_remove

    def test_remove_service_path_does_not_exists(self):
        # Arrange
        original_path_exists = os.path.exists
        os.path.exists = lambda path: False

        # Act
        self.runtime.service_manager.remove_service()

        # Assert
        self.assertTrue(self.runtime.service_manager.stop_service)
        self.assertTrue(self.runtime.service_manager.disable_service)
        self.assertTrue(self.runtime.service_manager.systemctl_daemon_reload)

        # Restore
        os.path.exists = original_path_exists


if __name__ == '__main__':
    unittest.main()
