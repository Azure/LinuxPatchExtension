# Copyright 2021 Microsoft Corporation
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

""" SystemctlManager """
import os
from core.src.bootstrap.Constants import Constants


class SystemctlManager(object):
    """ Base class functionality for Systemctl consumers """
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, service_info):
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer

        self.service_name = service_info.service_name
        self.service_desc = service_info.service_desc
        self.service_exec_path = service_info.service_exec_path

        self.__systemd_path = Constants.Paths.SYSTEMD_ROOT
        self.systemctl_daemon_reload_cmd = "sudo systemctl daemon-reload"
        self.systemctl_version = "systemctl --version"

    def systemd_exists(self):
        return os.path.exists(self.__systemd_path)

    def get_version(self):
        code, out = self.env_layer.run_command_output(self.systemctl_version)
        return out if "command not found" not in out else "Not found"

    def systemctl_daemon_reload(self):
        """ Reloads daemon """
        code, out = self.invoke_systemctl(self.systemctl_daemon_reload_cmd, "Reloading daemon.")
        return code == 0

    def invoke_systemctl(self, command, action_description=None):
        """ Invokes systemctl with the specified command and standardized logging """
        self.composite_logger.log('[Invoking systemctl] Action: ' + str(action_description) + ' Command: ' + command)
        self.composite_logger.file_logger.flush()
        code, out = self.env_layer.run_command_output(command, False, False)
        out = ("\n|\t" + "\n|\t".join(out.splitlines())) if out.strip() != "" else "None"
        self.composite_logger.log_debug(" - Return code: " + str(code) + ". Output: " + out)
        self.composite_logger.file_logger.flush()
        return code, out
