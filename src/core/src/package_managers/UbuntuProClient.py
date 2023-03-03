# Copyright 2023 Microsoft Corporation
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
# Requires Python 3.5+

"""This is the Ubuntu Pro Client implementation"""


class UbuntuProClient:
    def __init__(self, env_layer, composite_logger):
        self.env_layer = env_layer
        self.composite_logger = composite_logger
        self.ubuntu_pro_client_install_cmd = 'sudo apt-get install ubuntu-advantage-tools -y'

    def install_or_update_pro(self):
        """install/update pro(ubuntu-advantage-tools) to the latest version"""
        try:
            # Install Ubuntu Pro Client.
            code, output = self.env_layer.run_command_output(self.ubuntu_pro_client_install_cmd, False, False)
            if code == 0:
                self.composite_logger.log_debug("Ubuntu Pro Client installation successful.")
                return True
            else:
                self.composite_logger.log_debug("Ubuntu Pro Client installation failed.")
                return False
        except Exception as error:
            self.composite_logger.log_debug("Exception in installing Ubuntu Pro Client installation " + repr(error))
            return False

    def is_pro_working(self):
        """check if pro version api returns the version without any errors/warnings."""
        try:
            from uaclient.api.u.pro.version.v1 import version
            version_result = version()
            self.composite_logger.log_debug("Ubuntu Pro Client version: " + version_result.installed_version)
            return True

        except Exception as error:
            self.composite_logger.log_debug("Exception in querying pro version api " + repr(error))
            return False

    def get_security_updates(self):
        pass

    def get_all_updates(self):
        pass

    def get_other_updates(self):
        pass

    def is_reboot_pending(self):
        """query pro api to get the reboot status"""
        try:
            from uaclient.api.u.pro.security.status.reboot_required.v1 import reboot_required
            result = reboot_required()

            # Check if the reboot_required is yes. the values "yes-kernel-livepatches-applied"/"no" are considered as reboot not required.
            if result.reboot_required == "yes":
                return True, True
            else:
                return True, False
        except Exception as error:
            self.composite_logger.log_debug("Exception in Ubuntu Pro Client api reboot status: " + repr(error))
            return False, False
