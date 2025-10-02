# Copyright 2025 Microsoft Corporation
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

"""AzL3TdnfPackageManager for Azure Linux"""
import json
import re

from core.src.core_logic.VersionComparator import VersionComparator
from core.src.package_managers.TdnfPackageManager import TdnfPackageManager
from core.src.bootstrap.Constants import Constants


class AzL3TdnfPackageManager(TdnfPackageManager):
    """Implementation of Azure Linux package management operations"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(AzL3TdnfPackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)

        # Install update
        self.install_security_updates_azgps_coordinated_cmd = 'sudo tdnf -y upgrade --skip-broken'

        # Strict SDP specializations
        self.TDNF_MINIMUM_VERSION_FOR_STRICT_SDP = "3.5.8-3.azl3"  # minimum version of tdnf required to support Strict SDP in Azure Linux

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.TDNF)
        self.version_comparator = VersionComparator()

        # if an Auto Patching request comes in on an Azure Linux machine with Security and/or Critical classifications selected, we need to install all patches, since classifications aren't available in Azure Linux repository
        installation_included_classifications = [] if execution_config.included_classifications_list is None else execution_config.included_classifications_list
        if execution_config.health_store_id is not str() and execution_config.operation.lower() == Constants.INSTALLATION.lower() \
                and (env_layer.is_distro_azure_linux(str(env_layer.platform.linux_distribution()))) \
                and 'Critical' in installation_included_classifications and 'Security' in installation_included_classifications:
            self.composite_logger.log_debug("Updating classifications list to install all patches for the Auto Patching request since classification based patching is not available on Azure Linux machines")
            execution_config.included_classifications_list = [Constants.PackageClassification.CRITICAL, Constants.PackageClassification.SECURITY, Constants.PackageClassification.OTHER]

    # region Get Available Updates
    # region Classification-based (incl. All) update check
    def set_max_patch_publish_date(self, max_patch_publish_date=str()):
        """Set the max patch publish date in POSIX time for strict SDP"""
        self.max_patch_publish_date = str(self.env_layer.datetime.datetime_string_to_posix_time(max_patch_publish_date, '%Y%m%dT%H%M%SZ')) if max_patch_publish_date != str() else max_patch_publish_date
        self.composite_logger.log_debug("[AzL3TDNF] Set max patch publish date in posix time for Strict SDP. [MaxPatchPublishDate={0}][MaxPatchPublishDatePosixTime={1}]".format(str(max_patch_publish_date), str(self.max_patch_publish_date)))
    # endregion
    # endregion

    # region Install Updates
    def install_updates_fail_safe(self, excluded_packages):
        return

    def install_security_updates_azgps_coordinated(self):
        """Install security updates in Azure Linux following strict SDP"""
        command = self.add_additional_parameters_as_required_to_cmd(self.install_security_updates_azgps_coordinated_cmd)
        out, code = self.invoke_package_manager_advanced(command, raise_on_exception=False)
        return code, out

    def try_meet_azgps_coordinated_requirements(self):
        # type: () -> bool
        """ Check if the system meets the requirements for Azure Linux strict safe deployment and attempt to update TDNF if necessary """
        self.composite_logger.log_debug("[AzL3TDNF] Checking if system meets Azure Linux security updates requirements...")
        # Check if the system is Azure Linux 3.0 or beyond
        if not self.env_layer.is_distro_azure_linux_3_or_beyond():
            self.composite_logger.log_error("[AzL3TDNF] The system does not meet minimum Azure Linux requirement of 3.0 or above for strict safe deployment. Defaulting to regular upgrades.")
            self.set_max_patch_publish_date()  # fall-back
            return False
        else:
            if self.is_minimum_tdnf_version_for_strict_sdp_installed():
                self.composite_logger.log_debug("[AzL3TDNF] Minimum tdnf version for strict safe deployment is installed.")
                return True
            else:
                if not self.try_tdnf_update_to_meet_strict_sdp_requirements():
                    error_msg = "Failed to meet minimum TDNF version requirement for strict safe deployment. Defaulting to regular upgrades."
                    self.composite_logger.log_error(error_msg + "[Error={0}]".format(repr(error_msg)))
                    self.status_handler.add_error_to_status(error_msg)
                    self.set_max_patch_publish_date()  # fall-back
                    return False
                return True

    def is_minimum_tdnf_version_for_strict_sdp_installed(self):
        # type: () -> bool
        """Check if  at least the minimum required version of TDNF is installed"""
        self.composite_logger.log_debug("[AzL3TDNF] Checking if minimum TDNF version required for strict safe deployment is installed...")
        tdnf_version = self.get_tdnf_version()
        minimum_tdnf_version_for_strict_sdp = self.TDNF_MINIMUM_VERSION_FOR_STRICT_SDP
        distro_from_minimum_tdnf_version_for_strict_sdp = re.match(r".*-\d+\.([a-zA-Z0-9]+)$", minimum_tdnf_version_for_strict_sdp).group(1)
        if tdnf_version is None:
            self.composite_logger.log_error("[AzL3TDNF] Failed to get TDNF version. Cannot proceed with strict safe deployment. Defaulting to regular upgrades.")
            return False
        elif re.match(r".*-\d+\.([a-zA-Z0-9]+)$", tdnf_version).group(1) != distro_from_minimum_tdnf_version_for_strict_sdp:
            self.composite_logger.log_warning("[AzL3TDNF] TDNF version installed is not from the same Azure Linux distribution as the minimum required version for strict SDP. [InstalledVersion={0}][MinimumRequiredVersion={1}]".format(tdnf_version, self.TDNF_MINIMUM_VERSION_FOR_STRICT_SDP))
            return False
        elif not self.version_comparator.compare_versions(tdnf_version, minimum_tdnf_version_for_strict_sdp) >= 0:
            self.composite_logger.log_warning("[AzL3TDNF] TDNF version installed is less than the minimum required version for strict SDP. [InstalledVersion={0}][MinimumRequiredVersion={1}]".format(tdnf_version, self.TDNF_MINIMUM_VERSION_FOR_STRICT_SDP))
            return False
        return True

    def try_tdnf_update_to_meet_strict_sdp_requirements(self):
        # type: () -> bool
        """Attempt to update TDNF to meet the minimum version required for strict SDP"""
        self.composite_logger.log_debug("[AzL3TDNF] Attempting to update TDNF to meet strict safe deployment requirements...")
        cmd = "sudo tdnf -y install tdnf-" + self.TDNF_MINIMUM_VERSION_FOR_STRICT_SDP
        code, output = self.env_layer.run_command_output(cmd, no_output=True, chk_err=False)
        if code == 0:
            self.composite_logger.log_debug("[AzL3TDNF] Successfully updated TDNF for Strict SDP. [Command={0}][Code={1}]".format(cmd, code))
            return True
        else:
            self.composite_logger.log_error("[AzL3TDNF] Failed to update TDNF for Strict SDP. [Command={0}][Code={1}][Output={2}]".format(cmd, code, output))
            return False
    # endregion

