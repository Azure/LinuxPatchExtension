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

""" TimerManager """
import os
from core.src.bootstrap.Constants import Constants
from core.src.core_logic.SystemctlManager import SystemctlManager


class TimerManager(SystemctlManager):
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, service_info):
        super(TimerManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, service_info)
        self.__systemd_timer_unit_path = "/etc/systemd/system/{0}.timer"

        self.timer_start_cmd = "sudo systemctl start {0}.timer"
        self.timer_stop_cmd = "sudo systemctl stop {0}.timer"
        self.timer_reload_cmd = "sudo systemctl reload-or-restart {0}.timer"
        self.timer_enable_cmd = "sudo systemctl enable {0}.timer"
        self.timer_disable_cmd = "sudo systemctl disable {0}.timer"
        self.timer_status_cmd = "sudo systemctl status {0}.timer"
        self.timer_is_enabled_cmd = "sudo systemctl is-enabled {0}.timer"
        self.timer_is_active_cmd = "sudo systemctl is-active {0}.timer"

    # region - Time Creation / Removal
    def remove_timer(self):
        timer_path = self.__systemd_timer_unit_path.format(self.service_name)
        if os.path.exists(timer_path):
            self.disable_timer()
            self.stop_timer()
            os.remove(timer_path)
            self.systemctl_daemon_reload()

    def create_and_set_timer_idem(self):
        """ Idempotent creation and setting of the timer associated with the service the class is instantiated with """
        self.get_timer_status()
        self.remove_timer()
        interval_unix_timespan = self.__convert_iso8601_interval_to_unix_timespan(self.execution_config.maximum_assessment_interval)
        self.create_timer_unit_file(Constants.AUTO_ASSESSMENT_SERVICE_DESC, interval_unix_timespan)
        self.systemctl_daemon_reload()
        self.enable_timer()
        self.start_timer()
        self.get_timer_status()

    @staticmethod
    def __convert_iso8601_interval_to_unix_timespan(interval):
        """
            Supports only a subset of the spec as applicable to patch management.
            No non-default period (Y,M,W,D) is supported. Time is supported (H,M,S).
            Can throw exceptions - expected to handled as appropriate in calling code.
            E.g.: Input-->Output -- PT3H-->3h, PT5H7M6S-->5h7m6s
        """
        if 'PT' not in interval:
            raise Exception("Unexpected interval format. [Duration={0}]".format(interval))
        return interval.replace('PT', '').replace('H', 'h').replace('M', 'm').replace('S', 's')
    # endregion

    # region - Timer Management
    def start_timer(self):
        code, out = self.invoke_systemctl(self.timer_start_cmd.format(self.service_name), "Starting the timer.")
        return code == 0

    def stop_timer(self):
        code, out = self.invoke_systemctl(self.timer_stop_cmd.format(self.service_name), "Stopping the timer.")
        return code == 0

    def reload_timer(self):
        code, out = self.invoke_systemctl(self.timer_reload_cmd.format(self.service_name), "Reloading the timer.")
        return code == 0

    def get_timer_status(self):
        code, out = self.invoke_systemctl(self.timer_status_cmd.format(self.service_name), "Getting the timer status.")
        return code == 0

    def enable_timer(self):
        code, out = self.invoke_systemctl(self.timer_enable_cmd.format(self.service_name), "Enabling the timer.")
        return code == 0

    def disable_timer(self):
        code, out = self.invoke_systemctl(self.timer_disable_cmd.format(self.service_name), "Disabling the timer.")
        return code == 0

    def is_timer_active(self):
        code, out = self.invoke_systemctl(self.timer_is_active_cmd.format(self.service_name), "Checking if timer is active.")
        return False if "inactive" in out else True if code == 0 else False

    def is_timer_enabled(self):
        code, out = self.invoke_systemctl(self.timer_is_enabled_cmd.format(self.service_name), "Checking if timer is enabled.")
        return False if "disabled" in out else True if code == 0 else False
    # endregion

    # region - Timer Unit Management
    def create_timer_unit_file(self, desc, on_unit_active_sec="3h", on_boot_sec="15m"):
        timer_unit_content_template = "\n[Unit]" + \
                               "\nDescription={0}\n" + \
                               "\n[Timer]" + \
                               "\nOnBootSec={1}" + \
                               "\nOnUnitActiveSec={2}\n" + \
                               "\n[Install]" + \
                               "\nWantedBy=timers.target"

        timer_unit_content = timer_unit_content_template.format(desc, on_boot_sec, on_unit_active_sec)
        timer_unit_path = self.__systemd_timer_unit_path.format(self.service_name)
        self.env_layer.file_system.write_with_retry(timer_unit_path, timer_unit_content)
        self.env_layer.run_command_output("sudo chmod a+x " + timer_unit_path)
    # endregion