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

"""The is Aptitude package manager implementation"""
import json
import os
import re
import shutil
import sys

from core.src.package_managers.PackageManager import PackageManager
from core.src.bootstrap.Constants import Constants
from core.src.package_managers.UbuntuProClient import UbuntuProClient


class AptitudePackageManager(PackageManager):
    """Implementation of Debian/Ubuntu based package management operations"""

    # For more details, try `man apt-get` on any Debian/Ubuntu based box.
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(AptitudePackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler)

        # Apt constants config
        self.APT_SOURCES_LIST_PATH = '/etc/apt/sources.list'
        self.APT_SOURCES_DIR_PATH = '/etc/apt/sources.list.d/'
        self.APT_SOURCES_DIR_LIST_EXT = 'list'
        self.APT_SOURCES_DIR_SRC_EXT = 'sources'

        # Support to get packages and their dependencies
        custom_source_timestamp = self.env_layer.datetime.timestamp().replace(":",".")
        self.custom_source_list_template = os.path.join(execution_config.temp_folder, 'azgps-src-{0}-<FORMULA>.list'.format(str(custom_source_timestamp)))
        self.custom_source_parts_dir_template = os.path.join(execution_config.temp_folder, 'azgps-src-{0}-<FORMULA>.d'.format(str(custom_source_timestamp)))
        self.current_source_parts_dir = self.current_source_list = self.current_source_formula = None
        self.current_source_parts_file_name = "azgps-src-parts.sources"

        # Repo refresh
        self.cmd_repo_refresh_template = 'sudo apt-get -q update <SOURCES>'
        self.cmd_dist_upgrade_simulation_template = 'LANG=en_US.UTF8 sudo apt-get -s dist-upgrade <SOURCES> '  # Dist-upgrade simulation template - <SOURCES> needs to be replaced before use; sudo is used as sometimes the sources list needs sudo to be readable

        # Accept EULA (End User License Agreement) as per the EULA settings set by user
        optional_accept_eula_in_cmd = "ACCEPT_EULA=Y" if execution_config.accept_package_eula else ""

        # Package evaluations
        self.cmd_single_package_check_versions_template = 'apt-cache madison <PACKAGE-NAME>'
        self.cmd_single_package_find_install_dpkg_template = 'sudo dpkg -s <PACKAGE-NAME>'
        self.cmd_single_package_find_install_apt_template = 'sudo apt list --installed <PACKAGE-NAME>'
        self.single_package_upgrade_simulation_cmd = '''DEBIAN_FRONTEND=noninteractive ''' + optional_accept_eula_in_cmd + ''' LANG=en_US.UTF8 apt-get -y --only-upgrade true -s install '''
        self.single_package_dependency_resolution_template = 'DEBIAN_FRONTEND=noninteractive ' + optional_accept_eula_in_cmd + ' LANG=en_US.UTF8 apt-get -y --only-upgrade true -s install <PACKAGE-NAME> '

        # Package installation
        # --only-upgrade: upgrade only single package (only if it is installed)
        self.single_package_upgrade_cmd = '''sudo DEBIAN_FRONTEND=noninteractive LANG=en_US.UTF8 ''' + optional_accept_eula_in_cmd + ''' apt-get -y --only-upgrade true install '''
        self.install_security_updates_azgps_coordinated_cmd = '''sudo DEBIAN_FRONTEND=noninteractive LANG=en_US.UTF8 ''' + optional_accept_eula_in_cmd + ''' apt-get -y --only-upgrade true dist-upgrade <SOURCES> '''

        # Package manager exit code(s)
        self.apt_exitcode_ok = 0

        # auto OS updates
        self.update_package_list = 'APT::Periodic::Update-Package-Lists'
        self.unattended_upgrade = 'APT::Periodic::Unattended-Upgrade'
        self.os_patch_configuration_settings_file_path = '/etc/apt/apt.conf.d/20auto-upgrades'
        self.update_package_list_value = ""
        self.unattended_upgrade_value = ""

        # Miscellaneous
        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'  # Avoid a config prompt
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.APT)
        self.STR_DPKG_WAS_INTERRUPTED = "E: dpkg was interrupted, you must manually run 'sudo dpkg --configure -a' to correct the problem."
        self.ESM_MARKER = "The following packages could receive security updates with UA Infra: ESM service enabled:"

        # Ubuntu Pro Client pre-requisite checks.
        self.__pro_client_prereq_met = False  # This flag will be used to determine if Ubuntu Pro Client can be used for querying reboot status or get packages list.
        self.ubuntu_pro_client = UbuntuProClient(env_layer, composite_logger)
        self.check_pro_client_prerequisites()

        self.ubuntu_pro_client_all_updates_cached = []
        self.ubuntu_pro_client_all_updates_versions_cached = []
        
        self.package_install_expected_avg_time_in_seconds = 90  # As per telemetry data, the average time to install package is around 81 seconds for apt.

    # region Sources Management
    def __get_custom_sources_to_spec(self, max_patch_published_date=str(), base_classification=str()):
        # type: (str, str) -> (str, str)
        """ Prepares the custom sources list for use in a command. Idempotent. """
        try:
            # basic input validation
            if max_patch_published_date != str() and len(max_patch_published_date) != 16:
                raise Exception("[APM] Invalid max patch published date received. [Value={0}]".format(str(max_patch_published_date)))
            if base_classification != str() and base_classification != Constants.PackageClassification.SECURITY:
                raise Exception("[APM] Invalid classification selection received. [Value={0}]".format(str(base_classification)))

            # utilize caching if data exists and cache is also in the desired state
            formula = "{0}-{1}".format(max_patch_published_date if max_patch_published_date != str() else "any", base_classification.lower() if base_classification != str() else "all")
            if self.current_source_formula == formula:
                return self.current_source_parts_dir, self.current_source_list     # no need to refresh repo as state should match

            # utilize caching with refresh repo if data exists but cache is not in the desired state
            self.current_source_formula = formula
            self.current_source_parts_dir = self.custom_source_parts_dir_template.replace("<FORMULA>", formula)
            self.current_source_list = self.custom_source_list_template.replace("<FORMULA>", formula)
            if os.path.exists(self.current_source_list) and os.path.isdir(self.current_source_parts_dir):
                self.refresh_repo(source_parts_dir=self.current_source_parts_dir, source_list=self.current_source_list)     # refresh repo as requested state has changed
                return self.current_source_parts_dir, self.current_source_list

            # Produce data for combination not seen previously in this execution - source list
            source_list_content = self.__read_one_line_style_list_format(self.APT_SOURCES_LIST_PATH, max_patch_published_date, base_classification) if os.path.exists(self.APT_SOURCES_LIST_PATH) else str()
            self.env_layer.file_system.write_with_retry(self.current_source_list, source_list_content, "w")
            self.composite_logger.log_verbose("[APM] Source list content written. [List={0}][Content={1}]".format(self.current_source_list, source_list_content))

            # Produce data for combination not seen previously in this execution - source parts
            source_parts_deb882_style_content, source_parts_list_content = self.__get_consolidated_source_parts_content(max_patch_published_date, base_classification)
            if len(source_parts_list_content) > 0:  # list(s) in source parts
                self.env_layer.file_system.write_with_retry(self.current_source_list, "\n" + source_parts_list_content, "a")
                self.composite_logger.log_verbose("[APM] Source parts list content appended. [List={0}][Content={1}]".format(self.current_source_list, source_parts_list_content))

            # Source parts debstyle882-only initialization
            current_source_parts_deb882_style_file = os.path.join(self.current_source_parts_dir, self.current_source_parts_file_name)
            if os.path.isdir(self.current_source_parts_dir):
                shutil.rmtree(self.current_source_parts_dir)

            # Create the folder and write to it only if there is debstyle882 content to be written
            if len(source_parts_deb882_style_content) > 0:
                os.makedirs(self.current_source_parts_dir)
                self.env_layer.file_system.write_with_retry(current_source_parts_deb882_style_file, source_parts_deb882_style_content, "w")
                self.composite_logger.log_verbose("[APM] Source parts debstyle882 content written. [Dir={0}][Content={1}]".format(current_source_parts_deb882_style_file, source_parts_deb882_style_content))

        except Exception as error:
            self.composite_logger.log_error("[APM] Error in modifying custom sources list. [Error={0}]".format(repr(error)))
            return str(), str()    # defaults code to safety

        # Refresh repo
        self.refresh_repo(source_parts_dir=self.current_source_parts_dir, source_list=self.current_source_list)

        return self.current_source_parts_dir, self.current_source_list

    def __get_consolidated_source_parts_content(self, max_patch_published_date, base_classification):
        # type: (str, str) -> (str, str)
        """ Consolidates all list and sources files into a consistent format single source list """
        # read basic sources list - exception being thrown are acceptable
        source_parts_list_content = str()
        source_parts_deb882_style_content = str()

        if os.path.isdir(self.APT_SOURCES_DIR_PATH):
            # process files in directory
            dir_path = self.APT_SOURCES_DIR_PATH
            for file_name in [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]:
                try:
                    file_path = os.path.join(dir_path, file_name)

                    if file_name.endswith(self.APT_SOURCES_DIR_LIST_EXT):  # .list type
                        source_parts_list_content += "\n" + self.__read_one_line_style_list_format(file_path, max_patch_published_date, base_classification)
                    elif file_name.endswith(self.APT_SOURCES_DIR_SRC_EXT):   # .sources type
                        source_parts_deb882_style_content += "\n" + self.__read_deb882_style_format(file_path, max_patch_published_date, base_classification)

                except Exception as error:      # does not throw to allow patching to happen with functioning sources
                    self.composite_logger.log_error("[APM] Error while processing consolidated sources list. [File={0}][Error={1}]".format(file_name, repr(error)))

        return source_parts_deb882_style_content.strip(), source_parts_list_content.strip()

    def __read_one_line_style_list_format(self, file_path, max_patch_published_date, base_classification):
        # type: (str, str, str) -> str
        # Reads a *.list file and returns only lines that are functionally required
        # Reference: tools/references/apt/sources.list
        self.composite_logger.log_verbose("[APM] Reading source list for consolidation. [FilePath={0}]".format(file_path))

        std_source_list_content = str()
        sources_content = self.env_layer.file_system.read_with_retry(file_path)
        self.composite_logger.log_verbose("[APM][Srclist] Input source list file. [FilePath={0}][Content={1}]".format(file_path, sources_content))
        sources_content_lines = sources_content.splitlines()

        for line in sources_content_lines:
            if len(line.strip()) != 0 and not line.strip().startswith("#"):
                if base_classification == Constants.PackageClassification.SECURITY and "security" not in line:
                    continue
                std_source_list_content += "\n" + self.__apply_max_patch_publish_date(sources_content=line, max_patch_publish_date=max_patch_published_date)

        self.composite_logger.log_verbose("[APM][Srclist] Output source list slice. [FilePath={0}][TransformedContent={1}]".format(file_path, std_source_list_content))
        return std_source_list_content.strip()

    def __read_deb882_style_format(self, file_path, max_patch_published_date, base_classification):
        # type: (str, str, str) -> str
        # Reference: tools/references/apt/sources.list.d/ubuntu.sources
        std_source_parts_content = str()
        stanza = str()

        try:
            source_parts_content = self.env_layer.file_system.read_with_retry(file_path) + "\n"
            self.composite_logger.log_verbose("[APM][Deb882] Input source parts file. [FilePath={0}][Content={1}]".format(file_path, source_parts_content))
            source_parts_content_lines = source_parts_content.splitlines()

            for line in source_parts_content_lines:
                if line.startswith("#"):    # comments
                    continue

                if len(line.strip()) == 0:  # stanza separating line
                    if stanza != str():
                        if base_classification == str() or (base_classification == Constants.PackageClassification.SECURITY and "security" in stanza):
                            std_source_parts_content += self.__apply_max_patch_publish_date(sources_content=stanza, max_patch_publish_date=max_patch_published_date) + '\n'
                        stanza = str()
                        continue

                stanza += line + '\n'

        except Exception as error:
            self.composite_logger.log_error("[APM][Deb882] Error while reading DEB882-style format. [File={0}][Error={1}]".format(file_path, repr(error)))

        self.composite_logger.log_verbose("[APM][Deb882] Output source parts slice. [FilePath={0}][TransformedContent={1}]".format(file_path, std_source_parts_content))
        return std_source_parts_content

    def __apply_max_patch_publish_date(self, sources_content, max_patch_publish_date):
        # type: (str, str) -> str
        if max_patch_publish_date is str():
            return sources_content

        candidates = ["://azure.archive.ubuntu.com/ubuntu/", "archive.ubuntu.com/ubuntu/", "security.ubuntu.com/ubuntu/", "://snapshot.ubuntu.com/ubuntu/"]
        target = "https://snapshot.ubuntu.com/ubuntu/{0}".format(max_patch_publish_date)
        matched = False

        for candidate in candidates:
            if candidate in sources_content:
                sources_content_split = sources_content.split(" ")
                for i in range(0, len(sources_content_split)):
                    if candidate in sources_content_split[i]:
                        sources_content = sources_content.replace(sources_content_split[i], target)
                        sources_content = sources_content.replace("http://snapshot.ubuntu.com/", "https://snapshot.ubuntu.com/")
                        matched = True

        if not matched:
            self.composite_logger.log_debug("[APM] Repo unsupported for snapshot. [RepoInfo={0}]".format(sources_content))

        return sources_content

    def refresh_repo(self, source_parts_dir=str(), source_list=str()):
        self.composite_logger.log("[APM] Refreshing local repo... [SourcePartsDir={0}][SourceList={1}]".format(source_parts_dir, source_list))
        self.invoke_package_manager(self.__generate_command_with_custom_sources(self.cmd_repo_refresh_template, source_parts_dir, source_list))

    @staticmethod
    def __generate_command_with_custom_sources(command_template, source_parts=str(), source_list=str()):
        # type: (str, str, str) -> str
        """ Prepares a standard command to use custom sources. Pre-requisite: Refresh repo post list change. """
        if source_parts == str() and source_list == str():
            return command_template.replace('<SOURCES>', str())
        else:
            return command_template.replace('<SOURCES>', ('-oDir::Etc::SourceParts={0}/ -oDir::Etc::SourceList={1}'.format(str(source_parts) if source_parts != str() else "/dev/null",
                                                                                                                          str(source_list) if source_list != str() else "/dev/null")))
    # endregion Sources Management

    # region Get Available Updates
    def invoke_package_manager_advanced(self, command, raise_on_exception=True):
        """Get missing updates using the command input"""
        self.composite_logger.log_verbose('[APM] Invoking package manager. [Command={0}]'.format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != self.apt_exitcode_ok and self.STR_DPKG_WAS_INTERRUPTED in out:
            self.composite_logger.log_error('[ERROR] YOU NEED TO TAKE ACTION TO PROCEED. The package manager on this machine is not in a healthy state, and '
                                            'Patch Management cannot proceed successfully. Before the next Patch Operation, please run the following '
                                            'command and perform any configuration steps necessary on the machine to return it to a healthy state: '
                                            'sudo dpkg --configure -a')
            self.telemetry_writer.write_execution_error(command, code, out)
            error_msg = 'Package manager on machine is not healthy. To fix, please run: sudo dpkg --configure -a'
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            if raise_on_exception:
                raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        elif code != self.apt_exitcode_ok:
            self.composite_logger.log_warning('[ERROR] Customer environment error. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
            error_msg = "Customer environment error: Investigate and resolve unexpected return code ({0}) from package manager on command: {1}".format(str(code), command)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            if raise_on_exception:
                raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
            # more known return codes should be added as appropriate
        else:  # verbose diagnostic log
            self.composite_logger.log_debug('[APM] Invoked package manager. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
        return out, code

    def invoke_apt_cache(self, command):
        """Invoke apt-cache using the command input"""
        self.composite_logger.log_verbose('[APM] Invoking apt-cache using: ' + command)
        code, out = self.env_layer.run_command_output(command, False, False)
        if code != 0:
            self.composite_logger.log_warning('[ERROR] Customer environment error. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
            error_msg = "Customer environment error: Investigate and resolve unexpected return code (\'{0}\') from package manager on command: {1}".format(str(code), command)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
            # more known return codes should be added as appropriate
        else:  # verbose diagnostic log
            self.composite_logger.log_verbose('[APM] Invoked apt-cache. [Command={0}][Code={1}][Output={2}]'.format(command, str(code), str(out)))
        return out

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        all_updates = []
        all_updates_versions = []
        ubuntu_pro_client_all_updates_query_success = False

        self.composite_logger.log_verbose("[APM] Discovering all packages...")
        # use Ubuntu Pro Client cached list when the conditions are met.
        if self.__pro_client_prereq_met and not len(self.ubuntu_pro_client_all_updates_cached) == 0:
            all_updates = self.ubuntu_pro_client_all_updates_cached
            all_updates_versions = self.ubuntu_pro_client_all_updates_versions_cached

        elif not self.__pro_client_prereq_met and not len(self.all_updates_cached) == 0:
            all_updates = self.all_updates_cached
            all_updates_versions = self.all_update_versions_cached

        if cached and not len(all_updates) == 0:
            self.composite_logger.log_debug("[APM] Get all updates : [Cached={0}][PackagesCount={1}]]".format(str(cached), len(all_updates)))
            return all_updates, all_updates_versions

        # when cached is False, query both default way and using Ubuntu Pro Client.
        source_parts, source_list = self.__get_custom_sources_to_spec(self.max_patch_publish_date, base_classification=str())
        cmd = self.__generate_command_with_custom_sources(command_template=self.cmd_dist_upgrade_simulation_template, source_parts=source_parts, source_list=source_list)
        out = self.invoke_package_manager(cmd)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)

        if self.__pro_client_prereq_met:
            ubuntu_pro_client_all_updates_query_success, self.ubuntu_pro_client_all_updates_cached, self.ubuntu_pro_client_all_updates_versions_cached = self.ubuntu_pro_client.get_all_updates()
            pro_client_missed_updates = list(set(self.all_updates_cached) - set(self.ubuntu_pro_client_all_updates_cached))
            all_updates_missed_updates = list(set(self.ubuntu_pro_client_all_updates_cached) - set(self.all_updates_cached))
            self.composite_logger.log_debug("[APM-Pro] Get all updates : [DefaultAllPackagesCount={0}][UbuntuProClientQuerySuccess={1}][UbuntuProClientAllPackagesCount={2}]"
                                            .format(len(self.all_updates_cached), ubuntu_pro_client_all_updates_query_success, len(self.ubuntu_pro_client_all_updates_cached)))
            if len(pro_client_missed_updates) > 0:       # not good, needs investigation
                self.composite_logger.log_debug("[APM-Pro][!] Pro Client missed updates found. [Count={0}][Updates={1}]".format(len(pro_client_missed_updates), pro_client_missed_updates))
            if len(all_updates_missed_updates) > 0:     # interesting, for review
                self.composite_logger.log_debug("[APM-Pro][*] Pro Client only updates found. [Count={0}][Updates={1}]".format(len(all_updates_missed_updates), all_updates_missed_updates))

        if ubuntu_pro_client_all_updates_query_success:     # this needs to be revisited based on logs above
            return self.ubuntu_pro_client_all_updates_cached, self.ubuntu_pro_client_all_updates_versions_cached
        else:
            return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates"""
        ubuntu_pro_client_security_updates_query_success = False
        ubuntu_pro_client_security_packages = []
        ubuntu_pro_client_security_package_versions = []

        # regular security updates check
        self.composite_logger.log_verbose("[APM] Discovering 'security' packages (default)...")
        source_parts, source_list = self.__get_custom_sources_to_spec(self.max_patch_publish_date, base_classification=Constants.PackageClassification.SECURITY)
        cmd = self.__generate_command_with_custom_sources(self.cmd_dist_upgrade_simulation_template, source_parts=source_parts, source_list=source_list)
        out = self.invoke_package_manager(cmd)
        security_packages, security_package_versions = self.extract_packages_and_versions(out)
        self.composite_logger.log_debug("[APM] Discovered 'security' packages (default). [Count={0}]".format(len(security_packages)))

        # Query pro client if prerequisites are met
        if self.__pro_client_prereq_met:
            self.refresh_repo()
            self.composite_logger.log_verbose("[APM-Pro][Sec] Discovering 'security' packages (pro client)...")
            ubuntu_pro_client_security_updates_query_success, ubuntu_pro_client_security_packages, ubuntu_pro_client_security_package_versions = self.ubuntu_pro_client.get_security_updates()

        # Only use non-pro client results if either pre-reqs are not met or if the query fails
        if not ubuntu_pro_client_security_updates_query_success:
            self.composite_logger.log_debug("[APM-Pro][Sec] Using non-Pro Client results only. [ProClientPreReq={0}][ProClientQuerySuccess={1}]".format(str(self.__pro_client_prereq_met), str(ubuntu_pro_client_security_updates_query_success)))
            return security_packages, security_package_versions

        # Pro-client works - Cross-examine the results of queries
        pro_client_missed_updates = list(set(security_packages) - set(ubuntu_pro_client_security_packages))
        sec_updates_missed_updates = list(set(ubuntu_pro_client_security_packages) - set(security_packages))
        self.composite_logger.log_verbose("[APM-Pro][Sec] Pro Client to default package count comparison. [DefaultSecurityPackagesCount={0}][UbuntuProClientSecurityPackagesCount={1}]".format(len(security_packages), len(ubuntu_pro_client_security_packages)))
        if len(pro_client_missed_updates) > 0:       # not good, needs investigation - incl. several pro client differences that are now known
            self.composite_logger.log_debug("[APM-Pro][Sec][!] Pro Client missed updates found. [Count={0}][Updates={1}]".format(len(pro_client_missed_updates), pro_client_missed_updates))
        if len(sec_updates_missed_updates) > 0:      # interesting, for review
            self.composite_logger.log_debug("[APM-Pro][Sec][*] Pro Client-only updates found. [Count={0}][Updates={1}]".format(len(sec_updates_missed_updates), sec_updates_missed_updates))

        # Use default security update list & versions as base, and adding pro client specific items on top
        complete_list = security_packages
        complete_version_list = security_package_versions   # default security update list (incl. versions) supersedes due to reliability
        if len(sec_updates_missed_updates) > 0:
            for index in range(len(ubuntu_pro_client_security_packages)):
                if ubuntu_pro_client_security_packages[index] in sec_updates_missed_updates:
                    complete_list.append(ubuntu_pro_client_security_packages[index])
                    complete_version_list.append(ubuntu_pro_client_security_package_versions[index])
            self.composite_logger.log_debug("[APM-Pro][Sec][!] Added Pro Client-only packages to full security package list. [CombinedCount={0}][ProClientOnlyCount={1}][DefaultSecOnlyCount={2}]".format(len(complete_list),len(sec_updates_missed_updates),len(pro_client_missed_updates)))

        return complete_list, complete_version_list

    def get_security_esm_updates(self):
        """Get missing security-esm updates."""
        ubuntu_pro_client_security_esm_updates_query_success = False
        ubuntu_pro_client_security_esm_packages = []
        ubuntu_pro_client_security_package_esm_versions = []

        if self.__pro_client_prereq_met:
            ubuntu_pro_client_security_esm_updates_query_success, ubuntu_pro_client_security_esm_packages, ubuntu_pro_client_security_package_esm_versions = self.ubuntu_pro_client.get_security_esm_updates()

        self.composite_logger.log_debug("[APM-Pro] Get Security ESM updates : [UbuntuProClientQuerySuccess={0}][UbuntuProClientSecurityEsmPackagesCount={1}]".format(ubuntu_pro_client_security_esm_updates_query_success, len(ubuntu_pro_client_security_esm_packages)))
        return ubuntu_pro_client_security_esm_updates_query_success, ubuntu_pro_client_security_esm_packages, ubuntu_pro_client_security_package_esm_versions

    def get_other_updates(self):
        """Get missing other updates"""
        ubuntu_pro_client_other_updates_query_success = False
        ubuntu_pro_client_other_packages = []
        ubuntu_pro_client_other_package_versions = []
        other_packages = []
        other_package_versions = []

        self.composite_logger.log_verbose("[APM] Discovering 'other' packages...")
        all_packages, all_package_versions = self.get_all_updates(True)
        security_packages, security_package_versions = self.get_security_updates()

        for index, package in enumerate(all_packages):
            if package not in security_packages:
                other_packages.append(package)
                other_package_versions.append(all_package_versions[index])

        if self.__pro_client_prereq_met:
            ubuntu_pro_client_other_updates_query_success, ubuntu_pro_client_other_packages, ubuntu_pro_client_other_package_versions = self.ubuntu_pro_client.get_other_updates()
            self.composite_logger.log_debug("[APM-Pro] Get Other Updates : [DefaultOtherPackagesCount={0}][UbuntuProClientQuerySuccess={1}][UbuntuProClientOtherPackagesCount={2}]".format(len(other_packages), ubuntu_pro_client_other_updates_query_success, len(ubuntu_pro_client_other_packages)))

        if ubuntu_pro_client_other_updates_query_success:
            return ubuntu_pro_client_other_packages, ubuntu_pro_client_other_package_versions
        else:
            return other_packages, other_package_versions

    def set_max_patch_publish_date(self, max_patch_publish_date=str()):
        self.composite_logger.log_debug("[APM] Setting max patch publish date. [Date={0}]".format(max_patch_publish_date))
        self.max_patch_publish_date = max_patch_publish_date
    # endregion

    # region Output Parser(s)
    def extract_packages_and_versions(self, output):
        # sample output format
        # Inst coreutils [8.25-2ubuntu2] (8.25-2ubuntu3~16.10 Ubuntu:16.10/yakkety-updates [amd64])
        # Inst python3-update-manager [1:16.10.7] (1:16.10.8 Ubuntu:16.10/yakkety-updates [all]) [update-manager-core:amd64 ]
        # Inst update-manager-core [1:16.10.7] (1:16.10.8 Ubuntu:16.10/yakkety-updates [all])

        self.composite_logger.log_verbose("[APM] Extracting package and version data...")
        packages = []
        versions = []

        search_text = r'Inst[ ](.*?)[ ].*?[(](.*?)[ ](.*?)[ ]\[(.*?)\]'
        search = re.compile(search_text, re.M | re.S)
        package_list = search.findall(str(output))

        for package in package_list:
            packages.append(package[0])
            versions.append(package[1])

        self.composite_logger.log_verbose("[APM] Extracted package and version data for " + str(len(packages)) + " packages [BASIC].")

        # Discovering ESM packages - Distro versions with extended security maintenance
        lines = output.strip().split('\n')
        esm_marker_found = False
        esm_packages = []
        for line_index in range(0, len(lines)-1):
            line = lines[line_index].strip()

            if not esm_marker_found:
                if self.ESM_MARKER in line:
                   esm_marker_found = True
                continue

            esm_packages = line.split()
            break

        for package in esm_packages:
            packages.append(package)
            versions.append(Constants.UA_ESM_REQUIRED)
        self.composite_logger.log_verbose("[APM] Extracted package and version data for " + str(len(packages)) + " packages [TOTAL].")

        return packages, versions
    # endregion
    # endregion

    # region Install Update
    def get_composite_package_identifier(self, package, package_version):
        return package + '=' + package_version

    def install_updates_fail_safe(self, excluded_packages):
        return

    def install_security_updates_azgps_coordinated(self):
        source_parts, source_list = self.__get_custom_sources_to_spec(self.max_patch_publish_date, base_classification=Constants.PackageClassification.SECURITY)
        command = self.__generate_command_with_custom_sources(self.install_security_updates_azgps_coordinated_cmd, source_parts=source_parts, source_list=source_list)
        out, code = self.invoke_package_manager_advanced(command, raise_on_exception=False)
        return code, out

    def meets_azgps_coordinated_requirements(self):
        return True
    # endregion

    # region Package Information
    def get_all_available_versions_of_package(self, package_name):
        """ Returns a list of all the available versions of a package """
        # Sample output format
        #      bash | 4.3-14ubuntu1.3 | http://us.archive.ubuntu.com/ubuntu xenial-updates/main amd64 Packages
        #      bash | 4.3-14ubuntu1.2 | http://security.ubuntu.com/ubuntu xenial-security/main amd64 Packages
        #      bash | 4.3-14ubuntu1 | http://us.archive.ubuntu.com/ubuntu xenial/main amd64 Packages

        package_versions = []

        cmd = self.cmd_single_package_check_versions_template.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_apt_cache(cmd)
        lines = output.strip().split('\n')

        for line in lines:
            package_details = line.split(' |')
            if len(package_details) == 3:
                self.composite_logger.log_verbose(" - Applicable line: " + str(line))
                package_versions.append(package_details[1].strip())
            else:
                self.composite_logger.log_verbose(" - Inapplicable line: " + str(line))

        return package_versions

    def is_package_version_installed(self, package_name, package_version):
        """ Returns true if the specific package version is installed """

        self.composite_logger.log_verbose("\nCHECKING PACKAGE INSTALL STATUS FOR: " + str(package_name) + " (" + str(package_version) + ")")

        # DEFAULT METHOD
        self.composite_logger.log_verbose(" - [1/2] Verifying install status with Dpkg.")
        cmd = self.cmd_single_package_find_install_dpkg_template.replace('<PACKAGE-NAME>', package_name)
        code, output = self.env_layer.run_command_output(cmd, False, False)
        lines = output.strip().split('\n')

        if code == 1:  # usually not found
            # Sample output format ------------------------------------------
            # dpkg-query: package 'mysql-client' is not installed and no information is available
            # Use dpkg --info (= dpkg-deb --info) to examine archive files,
            # and dpkg --contents (= dpkg-deb --contents) to list their contents.
            #  ------------------------------------------ -------------------
            self.composite_logger.log_verbose("    - Return code: 1. The package is likely NOT present on the system.")
            for line in lines:
                if 'not installed' in line and package_name in line:
                    self.composite_logger.log_verbose("    - Discovered to be not installed: " + str(line))
                    return False
                else:
                    self.composite_logger.log_verbose("    - Inapplicable line: " + str(line))

            self.telemetry_writer.write_event("[Installed check] Return code: 1. Unable to verify package not present on the system: " + str(output), Constants.TelemetryEventLevel.Verbose)
        elif code == 0:  # likely found
            # Sample output format ------------------------------------------
            # Package: mysql-server
            # Status: install ok installed
            # Priority: optional
            # Section: database
            # Installed-Size: 107
            # Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
            # Architecture: all
            # Source: mysql-5.7
            # Version: 5.7.25-0ubuntu0.16.04.2
            # Depends: mysql-server-5.7
            #  ------------------------------------------ --------------------
            self.composite_logger.log_verbose("    - Return code: 0. The package is likely present on the system.")
            composite_found_flag = 0
            for line in lines:
                if 'Package: ' in line:
                    if package_name in line:
                        composite_found_flag = composite_found_flag | 1
                    else:  # should never hit for the way this is invoked, hence telemetry
                        self.composite_logger.log_verbose("    - Did not match name: " + str(package_name) + " (" + str(line) + ")")
                        self.telemetry_writer.write_event("[Installed check] Name did not match: " + package_name + " (line=" + str(line) + ")(out=" + str(output) + ")", Constants.TelemetryEventLevel.Verbose)
                    continue
                if 'Version: ' in line:
                    if package_version in line:
                        composite_found_flag = composite_found_flag | 2
                    else:  # should never hit for the way this is invoked, hence telemetry
                        self.composite_logger.log_verbose("    - Did not match version: " + str(package_version) + " (" + str(line) + ")")
                        self.telemetry_writer.write_event("[Installed check] Version did not match: " + str(package_version) + " (line=" + str(line) + ")(out=" + str(output) + ")", Constants.TelemetryEventLevel.Verbose)
                    continue
                if 'Status: ' in line:
                    if 'install ok installed' in line:
                        composite_found_flag = composite_found_flag | 4
                    else:  # should never hit for the way this is invoked, hence telemetry
                        self.composite_logger.log_verbose("    - Did not match status: " + str(package_name) + " (" + str(line) + ")")
                        self.telemetry_writer.write_event("[Installed check] Status did not match: 'install ok installed' (line=" + str(line) + ")(out=" + str(output) + ")", Constants.TelemetryEventLevel.Verbose)
                    continue
                if composite_found_flag & 7 == 7:  # whenever this becomes true, the exact package version is installed
                    self.composite_logger.log_verbose("    - Package, Version and Status matched. Package is detected as 'Installed'.")
                    return True
                self.composite_logger.log_verbose("    - Inapplicable line: " + str(line))
            self.composite_logger.log_verbose("    - Install status check did NOT find the package installed: (composite_found_flag=" + str(composite_found_flag) + ")")
            self.telemetry_writer.write_event("Install status check did NOT find the package installed: (composite_found_flag=" + str(composite_found_flag) + ")(output=" + output + ")", Constants.TelemetryEventLevel.Verbose)
        else:  # This is not expected to execute. If it does, the details will show up in telemetry. Improve this code with that information.
            self.composite_logger.log_debug("    - Unexpected return code from dpkg: " + str(code) + ". Output: " + str(output))
            self.telemetry_writer.write_event("Unexpected return code from dpkg: Cmd=" + str(cmd) + ". Code=" + str(code) + ". Output=" + str(output), Constants.TelemetryEventLevel.Verbose)

        # SECONDARY METHOD - Fallback
        # Sample output format
        # Listing... Done
        # apt/xenial-updates,now 1.2.29 amd64 [installed]
        self.composite_logger.log_verbose(" - [2/2] Verifying install status with Apt.")
        cmd = self.cmd_single_package_find_install_apt_template.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        lines = output.strip().split('\n')

        for line in lines:
            package_details = line.split(' ')
            if len(package_details) < 4:
                self.composite_logger.log_verbose("    - Inapplicable line: " + str(line))
            else:
                self.composite_logger.log_verbose("    - Applicable line: " + str(line))
                discovered_package_name = package_details[0].split('/')[0]  # index out of bounds check is deliberately not being done
                if discovered_package_name != package_name:
                    self.composite_logger.log_verbose("      - Did not match name: " + discovered_package_name + " (" + package_name + ")")
                    continue
                if package_details[1] != package_version:
                    self.composite_logger.log_verbose("      - Did not match version: " + package_details[1] + " (" + str(package_details[1]) + ")")
                    continue
                if 'installed' not in package_details[3]:
                    self.composite_logger.log_verbose("      - Did not find status: " + str(package_details[3] + " (" + str(package_details[3]) + ")"))
                    continue
                self.composite_logger.log_verbose("      - Package version specified was determined to be installed.")
                self.telemetry_writer.write_event("[Installed check] Fallback code disagreed with dpkg.", Constants.TelemetryEventLevel.Verbose)
                return True

        self.composite_logger.log_verbose("   - Package version specified was determined to NOT be installed.")
        return False

    def get_dependent_list(self, packages):
        """Returns dependent List for the list of packages"""
        package_names = ""
        for index, package in enumerate(packages):
            if index != 0:
                package_names += ' '
            package_names += package

        cmd = self.single_package_dependency_resolution_template.replace('<PACKAGE-NAME>', package_names)

        self.composite_logger.log_verbose("\nRESOLVING DEPENDENCIES USING COMMAND: " + str(cmd))
        output = self.invoke_package_manager(cmd)

        dependencies, dependency_versions = self.extract_packages_and_versions(output)
        
        for package in packages:
            if package in dependencies:
                dependencies.remove(package)

        self.composite_logger.log_verbose(str(len(dependencies)) + " dependent packages were found for packages '" + str(packages) + "'.")
        return dependencies

    def get_product_name(self, package_name):
        """Retrieve product name """
        return package_name

    def get_package_size(self, output):
        """Retrieve package size from update output string"""
        # Sample line from output:
        # Need to get 0 B/433 kB of archives
        # or
        # Need to get 110 kB of archives.
        try:
            if "is already the newest version" in output:
                return Constants.UNKNOWN_PACKAGE_SIZE
            search_txt = r'Need to get[ ](.*?)[ ]B/(.*?)[ ]of'
            search = re.compile(search_txt, re.M | re.S)
            pkg_list = search.findall(str(output))
            if not pkg_list:
                search_txt = r'Need to get[ ](.*?)[ ]of'
                search = re.compile(search_txt, re.M | re.S)
                pkg_list = search.findall(str(output))
                if not pkg_list or pkg_list[0] == "":
                    return Constants.UNKNOWN_PACKAGE_SIZE
                return pkg_list[0]
            elif pkg_list[0][1] == "":
                return Constants.UNKNOWN_PACKAGE_SIZE
            return pkg_list[0][1]
        except Exception as error:
            self.composite_logger.log_debug(" - Could not get package size from output: " + repr(error))
            return Constants.UNKNOWN_PACKAGE_SIZE
    # endregion

    # region auto OS updates
    def get_current_auto_os_patch_state(self):
        """ Gets the current auto OS update patch state on the machine """
        self.composite_logger.log("[APM] Fetching the current automatic OS patch state on the machine...")
        if os.path.exists(self.os_patch_configuration_settings_file_path):
            self.__get_current_auto_os_updates_setting_on_machine()
        if not os.path.exists(self.os_patch_configuration_settings_file_path) or int(self.unattended_upgrade_value) == 0:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.DISABLED
        elif int(self.unattended_upgrade_value) == 1:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.ENABLED
        else:
            current_auto_os_patch_state = Constants.AutomaticOSPatchStates.UNKNOWN

        self.composite_logger.log_debug("[APM] Current Auto OS Patch State is [State={0}]".format(str(current_auto_os_patch_state)))
        return current_auto_os_patch_state

    def __get_current_auto_os_updates_setting_on_machine(self):
        """ Gets all the update settings related to auto OS updates currently set on the machine """
        try:
            image_default_patch_configuration = self.env_layer.file_system.read_with_retry(self.os_patch_configuration_settings_file_path)
            settings = image_default_patch_configuration.strip().split('\n')
            for setting in settings:
                if self.update_package_list in str(setting):
                    self.update_package_list_value = re.search(self.update_package_list + ' *"(.*?)".', str(setting)).group(1)
                if self.unattended_upgrade in str(setting):
                    self.unattended_upgrade_value = re.search(self.unattended_upgrade + ' *"(.*?)".', str(setting)).group(1)

            if self.update_package_list_value == "":
                self.composite_logger.log_debug("[APM] Machine did not have any value set for [Setting={0}]".format(str(self.update_package_list)))

            if self.unattended_upgrade_value == "":
                self.composite_logger.log_debug("[APM] Machine did not have any value set for [Setting={0}]".format(str(self.unattended_upgrade)))

        except Exception as error:
            raise Exception("[APM] Error occurred in fetching default auto OS updates from the machine. [Exception={0}]".format(repr(error)))

    def disable_auto_os_update(self):
        """ Disables auto OS updates on the machine only if they are enabled and logs the default settings the machine comes with """
        try:
            self.composite_logger.log_debug("[APM] Disabling auto OS updates if they are enabled")
            self.backup_image_default_patch_configuration_if_not_exists()
            self.update_os_patch_configuration_sub_setting(self.update_package_list, "0")
            self.update_os_patch_configuration_sub_setting(self.unattended_upgrade, "0")
            self.composite_logger.log("[APM] Successfully disabled auto OS updates")
        except Exception as error:
            self.composite_logger.log_error("[APM] Could not disable auto OS updates. [Error={0}]".format(repr(error)))
            raise

    def backup_image_default_patch_configuration_if_not_exists(self):
        """ Records the default system settings for auto OS updates within patch extension artifacts for future reference.
        We only log the default system settings a VM comes with, any subsequent updates will not be recorded"""
        try:
            image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()

            # verify if existing backup is valid if not, write to backup
            is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)
            if is_backup_valid:
                self.composite_logger.log_debug("[APM] Since extension has a valid backup, no need to log the current settings again. [Default Auto OS update settings={0}] [File path={1}]"
                                                .format(str(image_default_patch_configuration_backup), self.image_default_patch_configuration_backup_path))
            else:
                self.composite_logger.log_debug("[APM] Since the backup is invalid or does not exist, will add a new backup with the current auto OS update settings")
                self.__get_current_auto_os_updates_setting_on_machine()

                backup_image_default_patch_configuration_json = {
                    self.update_package_list: self.update_package_list_value,
                    self.unattended_upgrade: self.unattended_upgrade_value
                }

                self.composite_logger.log_debug("[APM] Logging default system configuration settings for auto OS updates. [Settings={0}] [Log file path={1}]"
                                                .format(str(backup_image_default_patch_configuration_json), self.image_default_patch_configuration_backup_path))
                self.env_layer.file_system.write_with_retry(self.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(backup_image_default_patch_configuration_json)), mode='w+')
        except Exception as error:
            error_message = "[APM] Exception during fetching and logging default auto update settings on the machine. [Exception={0}]".format(repr(error))
            self.composite_logger.log_error(error_message)
            self.status_handler.add_error_to_status(error_message, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def is_image_default_patch_configuration_backup_valid(self, image_default_patch_configuration_backup):
        if self.update_package_list in image_default_patch_configuration_backup and self.unattended_upgrade in image_default_patch_configuration_backup:
            self.composite_logger.log_debug("[APM] Extension already has a valid backup of the default system configuration settings for auto OS updates.")
            return True
        else:
            self.composite_logger.log_error("[APM] Extension does not have a valid backup of the default system configuration settings for auto OS updates.")
            return False

    def update_os_patch_configuration_sub_setting(self, patch_configuration_sub_setting, value="0", patch_configuration_sub_setting_pattern_to_match=""):
        """ Updates (or adds if it doesn't exist) the given patch_configuration_sub_setting with the given value in os_patch_configuration_settings_file """
        try:
            # note: adding space between the patch_configuration_sub_setting and value since, we will have to do that if we have to add a patch_configuration_sub_setting that did not exist before
            self.composite_logger.log("[APM] Updating system configuration settings for auto OS updates. [PatchConfigurationSubSetting={0}][Value={1}]".format(str(patch_configuration_sub_setting), value))

            if value == '':
                self.composite_logger.log_debug("[APM] We won't update the system configuration settings since new configuration value to update does not an acceptable value. [PatchConfigurationSubSetting={0}][ValueToUpdate={1}]"
                                                .format(str(patch_configuration_sub_setting), value))
                return

            os_patch_configuration_settings = self.env_layer.file_system.read_with_retry(self.os_patch_configuration_settings_file_path)
            patch_configuration_sub_setting_to_update = patch_configuration_sub_setting + ' "' + value + '";'
            patch_configuration_sub_setting_found_in_file = False
            updated_patch_configuration_sub_setting = ""
            settings = os_patch_configuration_settings.strip().split('\n')

            # update value of existing setting
            for i in range(len(settings)):
                if patch_configuration_sub_setting in settings[i]:
                    settings[i] = patch_configuration_sub_setting_to_update
                    patch_configuration_sub_setting_found_in_file = True
                updated_patch_configuration_sub_setting += settings[i] + "\n"

            # add setting to configuration file, since it doesn't exist
            if not patch_configuration_sub_setting_found_in_file:
                updated_patch_configuration_sub_setting += patch_configuration_sub_setting_to_update + "\n"

            self.env_layer.file_system.write_with_retry(self.os_patch_configuration_settings_file_path, '{0}'.format(updated_patch_configuration_sub_setting.lstrip()), mode='w+')
        except Exception as error:
            error_msg = "[APM] Error occurred while updating system configuration settings for auto OS updates. [Patch Configuration={0}] [Error={1}]".format(str(patch_configuration_sub_setting), repr(error))
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise

    def revert_auto_os_update_to_system_default(self):
        """ Reverts the auto OS update patch state on the machine to its system default value, if one exists in our backup file """
        # type () -> None
        self.composite_logger.log("[APM] Reverting the current automatic OS patch state on the machine to its system default value before patchmode was set to 'AutomaticByPlatform'")

        if not os.path.exists(self.os_patch_configuration_settings_file_path):
            self.composite_logger.log_debug("[APM] Automatic OS patch config file not found on the VM. We won't be able to revert auto OS patch settings to their system default values")
            return

        self.__get_current_auto_os_updates_setting_on_machine()
        self.composite_logger.log_debug("[APM] Logging current configuration settings for auto OS updates. [{0}={1}][{2}={3}]"
                                        .format(str(self.update_package_list), str(self.update_package_list_value), str(self.unattended_upgrade), str(self.unattended_upgrade_value)))

        image_default_patch_configuration_backup = self.__get_image_default_patch_configuration_backup()
        self.composite_logger.log_debug("[APM] Logging system default configuration settings for auto OS updates. [Settings={0}]".format(str(image_default_patch_configuration_backup)))
        is_backup_valid = self.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup)

        if is_backup_valid:
            self.update_os_patch_configuration_sub_setting(self.update_package_list, image_default_patch_configuration_backup[self.update_package_list])
            self.update_os_patch_configuration_sub_setting(self.unattended_upgrade, image_default_patch_configuration_backup[self.unattended_upgrade])
            self.composite_logger.log_debug("[APM] Successfully reverted auto OS updates to system default config")
        else:
            self.composite_logger.log_debug("[APM] Since the backup is invalid or does not exist, we won't be able to revert auto OS patch settings to their system default value")

    def __get_image_default_patch_configuration_backup(self):
        """ Get image_default_patch_configuration_backup file"""
        image_default_patch_configuration_backup = {}

        # read existing backup since it also contains backup from other update services. We need to preserve any existing data with backup file
        if self.image_default_patch_configuration_backup_exists():
            try:
                image_default_patch_configuration_backup = json.loads(self.env_layer.file_system.read_with_retry(self.image_default_patch_configuration_backup_path))
            except Exception as error:
                self.composite_logger.log_error("[APM] Unable to read backup for default patch state. [Exception={0}]".format(repr(error)))
        return image_default_patch_configuration_backup
    # endregion

    # region Reboot Management
    def do_processes_require_restart(self):
        """ Fulfilling base class contract """
        return False
    # endregion Reboot Management

    def is_reboot_pending(self):
        """ Checks if there is a pending reboot on the machine. """
        ubuntu_pro_client_check_success = False
        ubuntu_pro_client_reboot_status = False
        reported_reboot_status = False
        default_exception = None
        default_pending_file_exists = False
        default_pending_processes_exists = False

        # Default reboot check.
        try:
            default_pending_file_exists = os.path.isfile(self.REBOOT_PENDING_FILE_PATH)
            default_pending_processes_exists = self.do_processes_require_restart()
            reported_reboot_status = default_pending_file_exists or default_pending_processes_exists
        except Exception as error:
            default_exception = repr(error)
            reported_reboot_status = True  # defaults for safety

        # Ubuntu Pro Client reboot check.
        if self.__pro_client_prereq_met:
            ubuntu_pro_client_check_success, ubuntu_pro_client_reboot_status = self.ubuntu_pro_client.is_reboot_pending()

        if ubuntu_pro_client_check_success:  # Prefer Ubuntu Pro Client reboot status.
            reported_reboot_status = ubuntu_pro_client_reboot_status

        self.composite_logger.log_debug("[APM] Reboot required advanced debug flags: [DefaultPendingFileExists={0}][DefaultPendingProcessesExists={1}][UbuntuProClientCheckSuccessful={2}][UbuntuProClientRebootStatus={3}][ReportedRebootStatus={4}][DefaultException={5}]".format(default_pending_file_exists, default_pending_processes_exists, ubuntu_pro_client_check_success, ubuntu_pro_client_reboot_status, reported_reboot_status, default_exception))
        return reported_reboot_status

    def check_pro_client_prerequisites(self):
        exception_error = None
        try:
            if Constants.UbuntuProClientSettings.FEATURE_ENABLED and self.__get_os_major_version() <= Constants.UbuntuProClientSettings.MAX_OS_MAJOR_VERSION_SUPPORTED and self.__is_minimum_required_python_installed():
                self.ubuntu_pro_client.install_or_update_pro()
                self.__pro_client_prereq_met = self.ubuntu_pro_client.is_pro_working()
        except Exception as error:
            exception_error = repr(error)

        self.composite_logger.log_debug("[APM-Pro] Ubuntu Pro Client pre-requisite checks:[IsFeatureEnabled={0}][IsOSVersionCompatible={1}][IsPythonCompatible={2}][Error={3}]".format(Constants.UbuntuProClientSettings.FEATURE_ENABLED, self.__get_os_major_version() <= Constants.UbuntuProClientSettings.MAX_OS_MAJOR_VERSION_SUPPORTED, self.__is_minimum_required_python_installed(), exception_error))
        return self.__pro_client_prereq_met

    def set_security_esm_package_status(self, operation, packages):
        """Set the security-ESM classification for the esm packages."""
        security_esm_update_query_success, security_esm_updates, security_esm_updates_versions = self.get_security_esm_updates()
        if self.__pro_client_prereq_met and security_esm_update_query_success and len(security_esm_updates) > 0:
            self.telemetry_writer.write_event("[APM] Set Security-ESM package status:[Operation={0}][Updates={1}]".format(operation, str(security_esm_updates)), Constants.TelemetryEventLevel.Verbose)
            if operation == Constants.ASSESSMENT:
                self.status_handler.set_package_assessment_status(security_esm_updates, security_esm_updates_versions, Constants.PackageClassification.SECURITY_ESM)
                # If the Ubuntu Pro Client is not attached, set the error with the code UA_ESM_REQUIRED. This will be used in portal to mark the VM as unattached to pro.
                if not self.ubuntu_pro_client.is_ubuntu_pro_client_attached:
                    self.status_handler.add_error_to_status("{0} patches requires Ubuntu Pro for Infrastructure with Extended Security Maintenance".format(len(security_esm_updates)), Constants.PatchOperationErrorCodes.UA_ESM_REQUIRED)
            elif operation == Constants.INSTALLATION:
                if security_esm_update_query_success:
                    esm_packages_selected_to_install = [package for package in packages if package in security_esm_updates]
                    self.composite_logger.log_debug("[APM] Setting security ESM package status. [SelectedEsmPackagesCount={0}]".format(len(esm_packages_selected_to_install)))
                self.status_handler.set_package_install_status_classification(security_esm_updates, security_esm_updates_versions, Constants.PackageClassification.SECURITY_ESM)

    def __get_os_major_version(self):
        """get the OS major version"""
        # Sample output for linux_distribution():
        # ['Ubuntu', '20.04', 'focal']
        os_version = self.env_layer.platform.linux_distribution()[1]
        os_major_version = int(os_version.split('.')[0])
        return os_major_version

    def __is_minimum_required_python_installed(self):
        """check if python version is at least 3.5"""
        return sys.version_info >= Constants.UbuntuProClientSettings.MINIMUM_PYTHON_VERSION_REQUIRED

    def add_arch_dependencies(self, package_manager, package, version, packages, package_versions, package_and_dependencies, package_and_dependency_versions):
        """
        Add the packages with same name as that of input parameter package but with different architectures from packages list to the list package_and_dependencies.
        Only required for yum. No-op for apt and zypper.
        """
        return

    def separate_out_esm_packages(self, packages, package_versions):
        """
        Filter out packages from the list where the version matches the UA_ESM_REQUIRED string.
        """
        non_esm_packages = []
        non_esm_package_versions = []
        ua_esm_required_packages = []
        ua_esm_required_package_versions = []
        ua_esm_required_packages_found = False

        for pkg, version in zip(packages, package_versions):
            if version != Constants.UA_ESM_REQUIRED:
                non_esm_packages.append(pkg)
                non_esm_package_versions.append(version)
                continue

            # version is UA_ESM_REQUIRED.
            ua_esm_required_packages.append(pkg)
            ua_esm_required_package_versions.append(version)

        ua_esm_required_packages_found = len(ua_esm_required_packages) > 0
        if ua_esm_required_packages_found:
            self.status_handler.add_error_to_status("{0} patches requires Ubuntu Pro for Infrastructure with Extended Security Maintenance".format(len(ua_esm_required_packages)), Constants.PatchOperationErrorCodes.UA_ESM_REQUIRED) # Set the error status with the esm_package details. Will be used in portal.

        self.composite_logger.log_debug("[APM] Filter esm packages : [TotalPackagesCount={0}][EsmPackagesCount={1}]".format(len(packages), len(ua_esm_required_packages)))
        return non_esm_packages, non_esm_package_versions, ua_esm_required_packages, ua_esm_required_package_versions, ua_esm_required_packages_found

    def get_package_install_expected_avg_time_in_seconds(self):
        return self.package_install_expected_avg_time_in_seconds

