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
from unittest.mock import patch, Mock
from core.src.core_logic.ServiceManager import ServiceManager


class TestServiceManager(unittest.TestCase):
    def setUp(self):
        # Create a mock environment layer, execution config, logger, and telemetry writer
        self.mock_env_layer = Mock()
        self.mock_execution_config = Mock()
        self.mock_composite_logger = Mock()
        self.mock_telemetry_writer = Mock()
        self.mock_service_info = Mock()

        # Create an instance of ServiceManager with the necessary attributes
        self.service_manager = ServiceManager(
            env_layer=self.mock_env_layer,
            execution_config=self.mock_execution_config,
            composite_logger=self.mock_composite_logger,
            telemetry_writer=self.mock_telemetry_writer,
            service_info=self.mock_service_info
        )
        self.service_manager.service_name = "test_service"
        self.mock_systemd_service_unit_path = "/etc/systemd/system/{0}.service"

    @patch('os.path.exists')
    @patch('os.remove')
    @patch.object(ServiceManager, 'stop_service')
    @patch.object(ServiceManager, 'disable_service')
    @patch.object(ServiceManager, 'systemctl_daemon_reload')
    def test_remove_service(self, mock_reload, mock_disable, mock_stop, mock_remove, mock_exists):
        # Arrange
        mock_exists.return_value = True

        # Act
        self.service_manager.remove_service()

        # Assert
        service_path = self.mock_systemd_service_unit_path.format(self.service_manager.service_name)
        mock_exists.assert_called_once_with(service_path)
        mock_stop.assert_called_once()
        mock_disable.assert_called_once()
        mock_remove.assert_called_once_with(service_path)
        mock_reload.assert_called_once()


if __name__ == '__main__':
    unittest.main()
