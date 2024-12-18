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

from core.src.core_logic.VersionComparator import VersionComparator
from core.src.bootstrap.Constants import Constants


class UbuntuProClient:
    def __init__(self, env_layer, composite_logger):
        self.env_layer = env_layer
        self.composite_logger = composite_logger
        self.ubuntu_pro_client_install_cmd = 'sudo apt-get install ubuntu-advantage-tools -y'
        self.ubuntu_pro_client_security_status_cmd = 'pro security-status --format=json'
        self.security_esm_criteria_strings = ["esm-infra", "esm-apps"]
        self.is_ubuntu_pro_client_attached = False
        self.version_comparator = VersionComparator()

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
            version_result = version()
            ubuntu_pro_client_version = version_result.installed_version

            # extract version from pro_client_verison 27.13.4~18.04.1 -> 27.13.4
            extracted_ubuntu_pro_client_version = self.version_comparator.extract_version_nums(ubuntu_pro_client_version)

            self.composite_logger.log_debug("Ubuntu Pro Client current version: [ClientVersion={0}]".format(str(extracted_ubuntu_pro_client_version)))

            # use custom comparator output 0 (equal), -1 (less), +1 (greater)
            is_minimum_ubuntu_pro_version_installed = self.version_comparator.compare_version_nums(extracted_ubuntu_pro_client_version, Constants.UbuntuProClientSettings.MINIMUM_CLIENT_VERSION) >= 0

            if ubuntu_pro_client_version is not None and is_minimum_ubuntu_pro_version_installed:
                is_ubuntu_pro_client_working = True
                self.is_ubuntu_pro_client_attached = self.log_ubuntu_pro_client_attached()
        except Exception as error:
            ubuntu_pro_client_exception = repr(error)

        self.composite_logger.log_debug("Is Ubuntu Pro Client working debug flags: [Success={0}][UbuntuProClientVersion={1}][UbuntuProClientMinimumVersionInstalled={2}][IsAttached={3}][Error={4}]".format(is_ubuntu_pro_client_working, ubuntu_pro_client_version, is_minimum_ubuntu_pro_version_installed, self.is_ubuntu_pro_client_attached, ubuntu_pro_client_exception))
        return is_ubuntu_pro_client_working

    def log_ubuntu_pro_client_attached(self):
        """log the attachment status of the machine."""
        is_ubuntu_pro_client_attached = False
        try:
            code, output = self.env_layer.run_command_output(self.ubuntu_pro_client_security_status_cmd, False, False)
            if code == 0:
                is_ubuntu_pro_client_attached = json.loads(output)['summary']['ua']['attached']
        except Exception as error:
            ubuntu_pro_client_exception = repr(error)
            self.composite_logger.log_debug("Ubuntu Pro Client Attached Exception: [Exception={0}]".format(ubuntu_pro_client_exception))
        return is_ubuntu_pro_client_attached

    def extract_packages_and_versions(self, updates):
        extracted_updates = []
        extracted_updates_versions = []

        for update in updates:
            extracted_updates.append(update.package)
            if not self.is_ubuntu_pro_client_attached and update.provided_by in self.security_esm_criteria_strings:
                extracted_updates_versions.append(Constants.UA_ESM_REQUIRED)
            else:
                extracted_updates_versions.append(update.version)
        return extracted_updates, extracted_updates_versions

    def get_filtered_updates(self, filter_criteria):
        """query Ubuntu Pro Client to get filtered updates."""
        updates_query_success = False
        updates = []
        versions = []
        updates_exception = None
        try:
            ubuntu_pro_client_updates = self.get_ubuntu_pro_client_updates()
            updates_query_success = True
            if len(filter_criteria) > 0:  # Filter the updates only when the criteria strings are passed.
                filtered_updates = [update for update in ubuntu_pro_client_updates if update.provided_by in filter_criteria]
            else:
                filtered_updates = ubuntu_pro_client_updates
            updates, versions = self.extract_packages_and_versions(filtered_updates)
        except Exception as error:
            updates_exception = repr(error)

        return updates_query_success, updates_exception, updates, versions

    def get_security_updates(self):
        """query Ubuntu Pro Client to get security updates."""
        security_criteria = ["standard-security"]
        security_updates_query_success, security_updates_exception, security_updates, security_updates_versions = self.get_filtered_updates(security_criteria)

        self.composite_logger.log_debug("Ubuntu Pro Client get security updates : [SecurityUpdatesCount={0}][error={1}]".format(len(security_updates), security_updates_exception))
        return security_updates_query_success, security_updates, security_updates_versions

    def get_security_esm_updates(self):
        """query Ubuntu Pro Client to get security-esm updates."""
        security_esm_updates_query_success, security_esm_updates_exception, security_esm_updates, security_esm_updates_versions = self.get_filtered_updates(self.security_esm_criteria_strings)

        self.composite_logger.log_debug("Ubuntu Pro Client get security-esm updates : [SecurityEsmUpdatesCount={0}][error={1}]".format(len(security_esm_updates),security_esm_updates_exception))
        return security_esm_updates_query_success, security_esm_updates, security_esm_updates_versions

    def get_all_updates(self):
        """query Ubuntu Pro Client to get all updates."""
        filter_criteria = []
        all_updates_query_success, all_updates_exception, all_updates, all_updates_versions = self.get_filtered_updates(filter_criteria)

        self.composite_logger.log_debug("Ubuntu Pro Client get all updates: [AllUpdatesCount={0}][error={1}]".format(len(all_updates), all_updates_exception))
        return all_updates_query_success, all_updates, all_updates_versions

    def get_ubuntu_pro_client_updates(self):
        from uaclient.api.u.pro.packages.updates.v1 import updates
        return updates().updates

    def get_other_updates(self):
        """query Ubuntu Pro Client to get other updates."""
        other_criteria = ["standard-updates"]
        other_updates_query_success, other_update_exception, other_updates, other_updates_versions = self.get_filtered_updates(other_criteria)

        self.composite_logger.log_debug("Ubuntu Pro Client get other updates: [OtherUpdatesCount={0}][error = {1}]".format(len(other_updates), other_update_exception))
        return other_updates_query_success, other_updates, other_updates_versions

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
