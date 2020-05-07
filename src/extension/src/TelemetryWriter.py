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

import platform
from src.Constants import Constants


class TelemetryWriter(object):
    """Class for writing telemetry data to data transports"""

    def __init__(self):
        self.data_transports = []
        self.activity_id = None

        # Init state report
        self.send_ext_state_info('Started Linux patch extension execution.')
        self.send_machine_config_info()

    # region Primary payloads
    def send_ext_state_info(self, state_info):
        # Expected to send up only pivotal extension state changes
        return self.try_send_message(state_info, Constants.TelemetryExtState)

    def send_config_info(self, config_info, config_type='unknown'):
        # Configuration info
        payload_json = {
            'config_type': config_type,
            'config_value': config_info
        }
        return self.try_send_message(payload_json, Constants.TelemetryConfig)

    def send_error_info(self, error_info):
        # Expected to log significant errors or exceptions
        return self.try_send_message(error_info, Constants.TelemetryError)

    def send_debug_info(self, error_info):
        # Usually expected to instrument possibly problematic code
        return self.try_send_message(error_info, Constants.TelemetryDebug)

    def send_info(self, info):
        # Usually expected to be significant runbook output
        return self.try_send_message(info, Constants.TelemetryInfo)
    # endregion

    # Composed payload
    def send_machine_config_info(self):
        # Machine info
        machine_info = {
            'platform_name': str(platform.linux_distribution()[0]),
            'platform_version': str(platform.linux_distribution()[1]),
            'machine_arch': str(platform.machine())
        }
        return self.send_config_info(machine_info, 'machine_config')

    def send_execution_error(self, cmd, code, output):
        # Expected to log any errors from a cmd execution, including package manager execution errors
        error_payload = {
            'cmd': str(cmd),
            'code': str(code),
            'output': str(output)[0:3072]
        }
        return self.send_error_info(error_payload)
    # endregion

    # region Transport layer
    def try_send_message(self, message, category=Constants.TelemetryInfo):
        raise NotImplementedError

    def close_transports(self):
        """Close data transports"""
        raise NotImplementedError
    # endregion
