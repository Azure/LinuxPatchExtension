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
        run_command_exception = None
        run_command_success = False
        try:
            # Install Ubuntu Pro Client.
            code, output = self.env_layer.run_command_output(self.ubuntu_pro_client_install_cmd, False, False)
            if code == 0:
                run_command_success = True
        except Exception as error:
            run_command_exception = repr(error)
        self.composite_logger.log_debug("Ubuntu Pro Client installation: [InstallationSuccess={0}][Error={1}]".format(run_command_success, run_command_exception))
        return run_command_success

    def is_pro_working(self):
        """check if pro version api returns the version without any errors/warnings."""
        ubuntu_pro_client_exception = None
        is_ubuntu_pro_client_working = False
        ubuntu_pro_client_version = None
        try:
            from uaclient.api.u.pro.version.v1 import version
            version_result = version()
            ubuntu_pro_client_version = version_result.installed_version
            if ubuntu_pro_client_version is not None:
                is_ubuntu_pro_client_working = True
        except Exception as error:
            ubuntu_pro_client_exception = repr(error)

        self.composite_logger.log_debug("Ubuntu Pro Client working: [Success={0}][UbuntuProClientVersion={1}][Error={2}]".format(is_ubuntu_pro_client_working, ubuntu_pro_client_version, ubuntu_pro_client_exception))
        return is_ubuntu_pro_client_working

    def get_security_updates(self):
        pass

    def get_all_updates(self):
        pass

    def get_other_updates(self):
        pass

    def is_reboot_pending(self):
        """query pro api to get the reboot status"""
        ubuntu_pro_client_api_success = False
        ubuntu_pro_client_reboot_required = False
        ubuntu_pro_client_exception = None
        try:
            from uaclient.api.u.pro.security.status.reboot_required.v1 import reboot_required
            result = reboot_required()
            ubuntu_pro_client_api_success = True

            # Check if the reboot_required is yes. the values "yes-kernel-livepatches-applied"/"no" are considered as reboot not required.
            if result.reboot_required == "yes":
                ubuntu_pro_client_reboot_required = True
            else:
                ubuntu_pro_client_reboot_required = False
        except Exception as error:
            ubuntu_pro_client_api_success = False
            ubuntu_pro_client_exception = repr(error)

        self.composite_logger.log_debug("Ubuntu Pro Client Reboot Required: [UbuntuProClientSuccess={0}][RebootRequiredFlag={1}][Error={2}]".format(ubuntu_pro_client_api_success, ubuntu_pro_client_reboot_required, ubuntu_pro_client_exception))
        return ubuntu_pro_client_api_success, ubuntu_pro_client_reboot_required
