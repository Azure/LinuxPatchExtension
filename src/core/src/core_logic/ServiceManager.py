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

""" ServiceManager """
import os
from core.src.bootstrap.Constants import Constants


class ServiceManager(object):
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, service_info):
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer

        self.service_name = service_info.service_name
        self.service_desc = service_info.service_desc
        self.service_exec_path = service_info.service_exec_path

        self.__systemd_path = Constants.Paths.SYSTEMD_ROOT
        self.__systemd_service_unit_path = "/etc/systemd/system/{0}.service"

        self.service_start_cmd = "sudo systemctl start {0}.service"
        self.service_stop_cmd = "sudo systemctl stop {0}.service"
        self.service_reload_cmd = "sudo systemctl reload-or-restart {0}.service"
        self.service_enable_cmd = "sudo systemctl enable {0}.service"
        self.service_disable_cmd = "sudo systemctl disable {0}.service"
        self.service_is_enabled_cmd = "sudo systemctl is-enabled {0}.service"
        self.service_is_active_cmd = "sudo systemctl is-active {0}.service"

        self.systemctl_daemon_reload_cmd = "sudo systemctl daemon-reload"
        self.systemctl_version = "systemctl --version"

    def remove_service(self):
        service_path = self.__systemd_service_unit_path.format(self.service_name)
        if os.path.exists(service_path):
            self.stop_service()
            self.disable_service()
            os.remove(service_path)
            self.systemctl_daemon_reload()

    def create_and_set_service_idem(self):
        """ Idempotent creation and setting of the service associated with the service the class is instantiated with """
        self.remove_service()
        self.create_service_unit_file(exec_start="/bin/bash " + self.service_exec_path, desc=Constants.AUTO_ASSESSMENT_SERVICE_DESC)
        self.systemctl_daemon_reload()
        self.enable_service()
        self.start_service()

    # region - Service Management
    def start_service(self):
        code, out = self.__invoke_systemctl(self.service_start_cmd.format(self.service_name), "Starting the service.")
        return code == 0

    def stop_service(self):
        code, out = self.__invoke_systemctl(self.service_stop_cmd.format(self.service_name), "Stopping the service.")
        return code == 0

    def reload_service(self):
        code, out = self.__invoke_systemctl(self.service_reload_cmd.format(self.service_name), "Reloading the service.")
        return code == 0

    def get_service_status(self):
        # To do: Soft-check status if configuration is as expected
        # code, out = self.__invoke_systemctl(self.service_stop_cmd.format(self.service_name), "Stopping the service.")
        # return code == 0
        pass

    def enable_service(self):
        code, out = self.__invoke_systemctl(self.service_enable_cmd.format(self.service_name), "Enabling the service.")
        return code == 0

    def disable_service(self):
        code, out = self.__invoke_systemctl(self.service_enable_cmd.format(self.service_name), "Disabling the service.")
        return code == 0

    def is_service_active(self):
        """ Returns False if the service can't be verified active """
        code, out = self.__invoke_systemctl(self.service_is_active_cmd.format(self.service_name), "Checking if service is active.")
        return False if "inactive" in out else True if code == 0 else False

    def is_service_enabled(self):
        code, out = self.__invoke_systemctl(self.service_is_active_cmd.format(self.service_name), "Checking if service is enabled.")
        return False if "disabled" in out else True if code == 0 else False

    def systemctl_daemon_reload(self):
        """ Reloads daemon """
        code, out = self.__invoke_systemctl(self.systemctl_daemon_reload_cmd)
        return code == 0

    def __invoke_systemctl(self, command, action_description=None):
        """ Invokes systemctl with the specified command and standardized logging """
        self.composite_logger.log_debug('[Invoking systemctl] Action: ' + str(action_description) + '. Command: ' + command)
        code, out = self.env_layer.run_command_output(command, False, False)
        self.composite_logger.log_debug(" - Return code: " + str(code))
        self.composite_logger.log_debug(" - Output: \n|\t" + "\n|\t".join(out.splitlines()))
        return code, out
    # endregion

    # region - Service Unit Management
    def create_service_unit_file(self, exec_start, desc, after="network.target", service_type="notify", wanted_by="multi-user.target"):
        service_unit_content_template = "\n[Unit]" + \
                               "\nDescription={0}" + \
                               "\nAfter={1}\n" + \
                               "\n[Service]" + \
                               "\nType={2}" + \
                               "\nExecStart={3}\n" + \
                               "\n[Install]" + \
                               "\nWantedBy={4}"
        service_unit_content = service_unit_content_template.format(desc, after, service_type, exec_start, wanted_by)
        service_unit_path = self.__systemd_service_unit_path.format(self.service_name)
        self.env_layer.file_system.write_with_retry(service_unit_path, service_unit_content)
        self.env_layer.run_command_output("sudo chmod a+x " + service_unit_path)
    # endregion

    def systemd_exists(self):
        return os.path.exists(self.__systemd_path)

    def get_version(self):
        code, out = self.env_layer.run_command_output(self.systemctl_version)
        return out


class ServiceInfo(object):
    def __init__(self, service_name, service_desc, service_exec_path):
        self.service_name = service_name
        self.service_desc = service_desc
        self.service_exec_path = service_exec_path
