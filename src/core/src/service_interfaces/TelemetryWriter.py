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

import json
from core.src.bootstrap.Constants import Constants


class TelemetryWriter(object):
    """Class for writing telemetry data to data transports"""

    def __init__(self, env_layer, execution_config):
        self.data_transports = []
        self.env_layer = env_layer
        self.activity_id = execution_config.activity_id

        # Init state report
        self.send_runbook_state_info('Started Linux patch runbook.')
        self.send_machine_config_info()
        self.send_config_info(execution_config.config_settings, 'execution_config')

    # region Primary payloads
    def send_runbook_state_info(self, state_info):
        # Expected to send up only pivotal runbook state changes
        return self.try_send_message(state_info, Constants.TELEMETRY_OPERATION_STATE)

    def send_config_info(self, config_info, config_type='unknown'):
        # Configuration info
        payload_json = {
            'config_type': config_type,
            'config_value': config_info
        }
        return self.try_send_message(payload_json, Constants.TELEMETRY_CONFIG)

    def send_package_info(self, package_name, package_ver, package_size, install_dur, install_result, code_path, install_cmd, output=''):
        # Package information compiled after the package is attempted to be installed
        max_output_length = 3072
        errors = ""

        # primary payload
        message = {'package_name': str(package_name), 'package_version': str(package_ver),
                   'package_size': str(package_size), 'install_duration': str(install_dur),
                   'install_result': str(install_result), 'code_path': code_path,
                   'install_cmd': str(install_cmd), 'output': str(output)[0:max_output_length]}
        errors += self.try_send_message(message, Constants.TELEMETRY_PACKAGE)

        # additional message payloads for output continuation only if we need it for specific troubleshooting
        if len(output) > max_output_length:
            for i in range(1, int(len(output)/max_output_length) + 1):
                message = {'install_cmd': str(install_cmd), 'output_continuation': str(output)[(max_output_length*i):(max_output_length*(i+1))]}
                errors += self.try_send_message(message, Constants.TELEMETRY_PACKAGE)

        return errors  # if any. Nobody consumes this at the time of this writing.

    def send_error_info(self, error_info):
        # Expected to log significant errors or exceptions
        return self.try_send_message(error_info, Constants.TELEMETRY_ERROR)

    def send_debug_info(self, error_info):
        # Usually expected to instrument possibly problematic code
        return self.try_send_message(error_info, Constants.TELEMETRY_DEBUG)

    def send_info(self, info):
        # Usually expected to be significant runbook output
        return self.try_send_message(info, Constants.TELEMETRY_INFO)
    # endregion

    # Composed payload
    def send_machine_config_info(self):
        # Machine info - sent only once at the start of the run
        machine_info = {
            'platform_name': str(self.env_layer.platform.linux_distribution()[0]),
            'platform_version': str(self.env_layer.platform.linux_distribution()[1]),
            'machine_cpu': self.get_machine_processor(),
            'machine_arch': str(self.env_layer.platform.machine()),
            'disk_type': self.get_disk_type()
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
    def try_send_message(self, message, category=Constants.TELEMETRY_INFO):
        """ Tries to send a message immediately. Returns None if successful. Error message if not."""
        try:
            payload = {'activity_id': str(self.activity_id), 'category': str(category), 'ver': "[%runbook_sub_ver%]", 'message': message}
            payload = json.dumps(payload)[0:4095]
            for transport in self.data_transports:
                transport.write(payload)
            return ""  # for consistency
        except Exception as error:
            return repr(error)  # if the caller cares

    def close_transports(self):
        """Close data transports"""
        self.send_runbook_state_info('Closing telemetry channel(s).')
        for transport in self.data_transports:
            transport.close()
    # endregion

    # region Machine config retrieval methods
    def get_machine_processor(self):
        """Retrieve machine processor info"""
        cmd = "cat /proc/cpuinfo | grep name"
        code, out = self.env_layer.run_command_output(cmd, False, False)

        if out == "" or "not recognized as an internal or external command" in out:
            return "No information found"
        # Example output:
        # model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz
        lines = out.split("\n")
        return lines[0].split(":")[1].lstrip()

    def get_disk_type(self):
        """ Retrieve disk info """
        cmd = "cat /sys/block/sda/queue/rotational"
        code, out = self.env_layer.run_command_output(cmd, False, False)
        if "1" in out:
            return "Hard drive"
        elif "0" in out:
            return "SSD"
        else:
            return "Unknown"
    # end region
