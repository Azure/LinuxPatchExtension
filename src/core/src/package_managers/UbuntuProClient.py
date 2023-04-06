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
from core.src.bootstrap.Constants import Constants


class UbuntuProClient:
    def __init__(self, env_layer, composite_logger):
        self.env_layer = env_layer
        self.composite_logger = composite_logger
        self.ubuntu_pro_client_install_cmd = 'sudo apt-get install ubuntu-advantage-tools -y'
        self.ubuntu_pro_client_query_updates_cmd = 'pro api u.pro.packages.updates.v1'
        self.ubuntu_pro_client_security_status_cmd = 'pro security-status --format=json'
        self.updates_result = None

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
        is_minimum_ubuntu_pro_version_installed = False
        try:
            from uaclient.api.u.pro.version.v1 import version
            from distutils.version import LooseVersion  # Importing this module here as there is conflict between "distutils.version" and "uaclient.api.u.pro.version.v1.version when 'LooseVersion' is called."
            version_result = version()
            ubuntu_pro_client_version = version_result.installed_version
            is_minimum_ubuntu_pro_version_installed = LooseVersion(ubuntu_pro_client_version) >= LooseVersion(Constants.UbuntuProClientSettings.MINIMUM_CLIENT_VERSION)
            if ubuntu_pro_client_version is not None and is_minimum_ubuntu_pro_version_installed:
                is_ubuntu_pro_client_working = True
                self.log_ubuntu_pro_client_attached()
        except Exception as error:
            ubuntu_pro_client_exception = repr(error)

        self.composite_logger.log_debug("Is Ubuntu Pro Client working debug flags: [Success={0}][UbuntuProClientVersion={1}][UbuntuProClientMinimumVersionInstalled={2}][Error={3}]".format(is_ubuntu_pro_client_working, ubuntu_pro_client_version, is_minimum_ubuntu_pro_version_installed, ubuntu_pro_client_exception))
        return is_ubuntu_pro_client_working

    def log_ubuntu_pro_client_attached(self):
        """log the attachment status of the machine."""
        ubuntu_pro_client_is_attached = False
        ubuntu_pro_client_exception = None
        try:
            code, output = self.env_layer.run_command_output(self.ubuntu_pro_client_security_status_cmd, False, False)
            if code == 0:
                ubuntu_pro_client_is_attached = json.loads(output)['summary']['ua']['attached']
        except Exception as error:
            ubuntu_pro_client_exception = repr(error)
        self.composite_logger.log_debug("Ubuntu Pro Client Attached status [IsAttached={0}][Exception={1}]".format(ubuntu_pro_client_is_attached, ubuntu_pro_client_exception))
        return ubuntu_pro_client_is_attached

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
            code, output = self.env_layer.run_command_output(self.ubuntu_pro_client_query_updates_cmd, False, False)
            if code == 0:
                self.ubuntu_pro_client_cmd_output = json.loads(output)["data"]["attributes"]["updates"]

            security_updates_query_success = True
            security_criteria_string = ["standard-security"]
            filtered_security_updates = [update for update in self.ubuntu_pro_client_cmd_output if
                                         update["provided_by"] in security_criteria_string]

            self.composite_logger.log_debug(
                "Ubuntu Pro Client get security updates : [SecurityUpdatesCount={0}]".format(
                    len(filtered_security_updates)))
            security_updates, security_updates_versions = self.extract_packages_and_versions(filtered_security_updates)
        except Exception as error:
            security_updates_exception = repr(error)

        self.composite_logger.log_debug(
            "Ubuntu Pro Client get security updates : [error={0}]".format(security_updates_exception))
        return security_updates_query_success, security_updates, security_updates_versions

    def get_security_esm_updates(self):
        """query Ubuntu Pro Client to get security-esm updates."""
        security_esm_updates_query_success = False
        security_esm_updates = []
        security_esm_updates_versions = []
        security_esm_updates_exception = None

        try:
            code, output = self.env_layer.run_command_output(self.ubuntu_pro_client_query_updates_cmd, False, False)
            if code == 0:
                self.ubuntu_pro_client_cmd_output = json.loads(output)["data"]["attributes"]["updates"]

            security_esm_updates_query_success = True
            security_esm_criteria_strings = ["esm-infra", "esm-apps"]
            filtered_security_esm_updates = [update for update in self.ubuntu_pro_client_cmd_output if
                                             update["provided_by"] in security_esm_criteria_strings]

            self.composite_logger.log_debug(
                "Ubuntu Pro Client get security-esm updates : [SecurityEsmUpdatesCount={0}]".format(
                    len(filtered_security_esm_updates)))
            security_esm_updates, security_esm_updates_versions = self.extract_packages_and_versions(
                filtered_security_esm_updates)
        except Exception as error:
            security_esm_updates_exception = repr(error)

        self.composite_logger.log_debug(
            "Ubuntu Pro Client get security-esm updates : [error={0}]".format(security_esm_updates_exception))
        return security_esm_updates_query_success, security_esm_updates, security_esm_updates_versions

    def get_all_updates(self):
        """query Ubuntu Pro Client to get all updates."""
        all_updates_query_success = False
        all_updates = []
        all_updates_versions = []
        all_update_exception = None
        ubuntu_pro_client_cmd_output = None

        try:
            # This is bug in pro client. This will be reverted once the bug is fixed. For now using command to fetch updates instead of api.
            # if self.updates_result is None:
            #     self.composite_logger.log_debug("Ubuntu Pro Client : [result None]")
            #     from uaclient.api.u.pro.packages.updates.v1 import updates
            #     self.updates_result = updates()

            code, output = self.env_layer.run_command_output(self.ubuntu_pro_client_query_updates_cmd, False, False)
            if code == 0:
                ubuntu_pro_client_cmd_output = json.loads(output)["data"]["attributes"]["updates"]

            all_updates_query_success = True
            all_updates, all_updates_versions = self.extract_packages_and_versions(ubuntu_pro_client_cmd_output)
        except Exception as error:
            all_update_exception = repr(error)

        self.composite_logger.log_debug("Ubuntu Pro Client get all updates: [AllUpdatesCount={0}][error={1}]".format(len(all_updates), all_update_exception))
        return all_updates_query_success, all_updates, all_updates_versions

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
