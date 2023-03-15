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
import json


class UbuntuProClient:
    def __init__(self, env_layer, composite_logger):
        self.env_layer = env_layer
        self.composite_logger = composite_logger
        self.ubuntu_pro_client_install_cmd = 'sudo apt-get install ubuntu-advantage-tools -y'
        self.ubuntu_pro_client_query_updates_cmd = 'pro api u.pro.packages.updates.v1'
        self.updates_result = None
        self.ubuntu_pro_client_cmd_output = None

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

    def extract_packages_and_versions(self, updates):
        extracted_updates = []
        extracted_updates_versions = []
            
        for update in updates:
            extracted_updates.append(update["package"])
            extracted_updates_versions.append(update["version"])
        
        return extracted_updates, extracted_updates_versions

    def get_security_updates(self):
        """query Ubuntu Pro Client to get security updates."""
        security_updates_query_success = False
        security_updates = []
        security_updates_versions = []
        security_updates_exception = None

        try:
            # if self.updates_result is None:
            #     self.composite_logger.log_debug("Ubuntu Pro Client : [result None]")
            #     from uaclient.api.u.pro.packages.updates.v1 import updates
            #     self.updates_result = updates()
            code, output = self.env_layer.run_command_output(self.ubuntu_pro_client_query_updates_cmd, False, False)
            if code == 0:
                self.ubuntu_pro_client_cmd_output = json.loads(output)["data"]["attributes"]["updates"]

            security_updates_query_success = True
            security_criteria_string = ["standard-security"]
            filtered_security_updates = [update for update in self.ubuntu_pro_client_cmd_output if update["provided_by"] in security_criteria_string]

            self.composite_logger.log_debug("Ubuntu Pro Client get security updates : [SecurityUpdatesCount={0}]".format(len(filtered_security_updates)))
            security_updates, security_updates_versions = self.extract_packages_and_versions(filtered_security_updates)
        except Exception as error:
            security_updates_exception = repr(error)

        self.composite_logger.log_debug("Ubuntu Pro Client get security updates : [error={0}]".format(security_updates_exception))
        return security_updates_query_success, security_updates, security_updates_versions

    def get_security_esm_updates(self):
        """query Ubuntu Pro Client to get security-esm updates."""
        security_esm_updates_query_success = False
        security_esm_updates = []
        security_esm_updates_versions = []
        security_esm_updates_exception = None

        try:
            # if self.updates_result is None:
            #     self.composite_logger.log_debug("Ubuntu Pro Client : [result None]")
            #     from uaclient.api.u.pro.packages.updates.v1 import updates
            #     self.updates_result = updates()
            code, output = self.env_layer.run_command_output(self.ubuntu_pro_client_query_updates_cmd, False, False)
            if code == 0:
                self.ubuntu_pro_client_cmd_output = json.loads(output)["data"]["attributes"]["updates"]

            security_esm_updates_query_success = True
            security_esm_criteria_strings = ["esm-infra", "esm-apps"]
            filtered_security_esm_updates = [update for update in self.ubuntu_pro_client_cmd_output if update["provided_by"] in security_esm_criteria_strings]

            self.composite_logger.log_debug("Ubuntu Pro Client get security-esm updates : [SecurityEsmUpdatesCount={0}]".format(len(filtered_security_esm_updates)))
            security_esm_updates, security_esm_updates_versions = self.extract_packages_and_versions(filtered_security_esm_updates)
        except Exception as error:
            security_esm_updates_exception = repr(error)

        self.composite_logger.log_debug("Ubuntu Pro Client get security-esm updates : [error={0}]".format(security_esm_updates_exception))
        return security_esm_updates_query_success, security_esm_updates, security_esm_updates_versions

    def get_all_updates(self):
        """query Ubuntu Pro Client to get all updates."""
        all_updates_query_success = False
        all_updates = []
        all_updates_versions = []
        all_update_exception = None

        try:
            # if self.updates_result is None:
            #     self.composite_logger.log_debug("Ubuntu Pro Client : [result None]")
            #     from uaclient.api.u.pro.packages.updates.v1 import updates
            #     self.updates_result = updates()
            code, output = self.env_layer.run_command_output(self.ubuntu_pro_client_query_updates_cmd, False, False)
            if code == 0:
                self.ubuntu_pro_client_cmd_output = json.loads(output)["data"]["attributes"]["updates"]

            all_updates_query_success = True
            all_updates, all_updates_versions = self.extract_packages_and_versions(self.ubuntu_pro_client_cmd_output)
        except Exception as error:
            all_update_exception = repr(error)

        self.composite_logger.log_debug("Ubuntu Pro Client get all updates: [error = {0}]".format(all_update_exception))
        return all_updates_query_success, all_updates, all_updates_versions

    def get_other_updates(self):
        """query Ubuntu Pro Client to get other updates."""
        other_updates_query_success = False
        other_updates = []
        other_updates_versions = []
        other_update_exception = None
        try:
            # if self.updates_result is None:
            #     self.composite_logger.log_debug("Ubuntu Pro Client : [result None]")
            #     from uaclient.api.u.pro.packages.updates.v1 import updates
            #     self.updates_result = updates()
            code, output = self.env_layer.run_command_output(self.ubuntu_pro_client_query_updates_cmd, False, False)
            if code == 0:
                self.ubuntu_pro_client_cmd_output = json.loads(output)["data"]["attributes"]["updates"]

            other_updates_query_success = True
            other_criteria_strings = ["standard-updates"]
            filtered_other_updates = [update for update in self.ubuntu_pro_client_cmd_output if update["provided_by"] in other_criteria_strings]
            other_updates, other_updates_versions = self.extract_packages_and_versions(filtered_other_updates)
        except Exception as error:
            other_update_exception = repr(error)

        self.composite_logger.log_debug("Ubuntu Pro Client get other updates: [error = {0}]".format(other_update_exception))
        return other_updates_query_success, other_updates, other_updates_versions

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
