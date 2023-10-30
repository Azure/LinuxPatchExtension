# Copyright 2020 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
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
import sys
import uuid

from core.src.package_managers.PackageManager import PackageManager
from core.src.bootstrap.Constants import Constants
from package_managers.apt.UbuntuProClient import UbuntuProClient

# do not instantiate directly - these are exclusively for type hinting support
from core.src.bootstrap.EnvLayer import EnvLayer
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.src.local_loggers.CompositeLogger import CompositeLogger
from core.src.service_interfaces.TelemetryWriter import TelemetryWriter
from core.src.service_interfaces.StatusHandler import StatusHandler
from core.src.package_managers.PatchModeManager import PatchModeManager
from core.src.package_managers.SourcesManager import SourcesManager
from core.src.package_managers.HealthManager import HealthManager


class AptPackageManager(PackageManager):
    """Implementation of Debian/Ubuntu based package management operations"""

    # For more details, try `man apt-get` on any Debian/Ubuntu based box.
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, patch_mode_manager, sources_manager, health_manager, package_manager_name):
        # type: (EnvLayer, ExecutionConfig, CompositeLogger, TelemetryWriter, StatusHandler, PatchModeManager, SourcesManager, HealthManager, str) -> None
        super(AptPackageManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler, patch_mode_manager, sources_manager, health_manager, package_manager_name)

        security_list_guid = str(uuid.uuid4())

        # Accept EULA (End User License Agreement) as per the EULA settings set by user
        optional_accept_eula_in_cmd = "ACCEPT_EULA=Y" if execution_config.accept_package_eula else ""

        # Repo refresh
        self.repo_refresh = 'sudo apt-get -q update'

        # Support to get updates and their dependencies
        self.security_sources_list = os.path.join(execution_config.temp_folder, 'msft-patch-security-{0}.list'.format(security_list_guid))
        self.prep_security_sources_list_cmd = 'sudo grep -hR security /etc/apt/sources.list /etc/apt/sources.list.d/ > ' + os.path.normpath(self.security_sources_list)
        self.dist_upgrade_simulation_cmd_template = 'LANG=en_US.UTF8 sudo apt-get -s dist-upgrade <SOURCES> '  # Dist-upgrade simulation template - <SOURCES> needs to be replaced before use; sudo is used as sometimes the sources list needs sudo to be readable
        self.single_package_check_versions = 'apt-cache madison <PACKAGE-NAME>'
        self.single_package_find_installed_dpkg = 'sudo dpkg -s <PACKAGE-NAME>'
        self.single_package_find_installed_apt = 'sudo apt list --installed <PACKAGE-NAME>'
        self.single_package_upgrade_simulation_cmd = '''DEBIAN_FRONTEND=noninteractive ''' + optional_accept_eula_in_cmd + ''' apt-get -y --only-upgrade true -s install '''
        self.single_package_dependency_resolution_template = 'DEBIAN_FRONTEND=noninteractive ' + optional_accept_eula_in_cmd + ' LANG=en_US.UTF8 apt-get -y --only-upgrade true -s install <PACKAGE-NAME> '

        # Install update
        # --only-upgrade: upgrade only single package (only if it is installed)
        self.single_package_upgrade_cmd = '''sudo DEBIAN_FRONTEND=noninteractive ''' + optional_accept_eula_in_cmd + ''' apt-get -y --only-upgrade true install '''

        # Package manager exit code(s)
        self.apt_exitcode_ok = 0

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

    def refresh_repo(self):
        self.composite_logger.log_verbose("[APM] Refreshing local repo.")
        self.invoke_package_manager(self.repo_refresh)

    # region Get Available Updates
    def invoke_package_manager_advanced(self, command, raise_on_exception=True):
        """Get missing updates using the command input"""
        self.composite_logger.log_verbose('[APM] Invoking package manager. [Command={0}]'.format(command))
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != self.apt_exitcode_ok and self.STR_DPKG_WAS_INTERRUPTED in out:
            self.composite_logger.log_error("[ERROR] YOU NEED TO TAKE ACTION TO PROCEED. The package manager on this machine is not in a healthy state, and Azure Guest Patching Service cannot proceed successfully. Before the next Patch Operation, please run the following command and perform any configuration steps necessary on the machine to return it to a healthy state: 'sudo dpkg --configure -a'")
            self.status_handler.add_error_to_status_and_log_error(message="Package manager on machine is not healthy. To fix, please run: sudo dpkg --configure -a",
                                                                  raise_exception=bool(raise_on_exception), error_code=Constants.PatchOperationErrorCodes.CL_PACKAGE_MANAGER_FAILURE)
        elif code != self.apt_exitcode_ok:
            self.composite_logger.log_error("[APM] Package Manager ERROR. [Command={0}][Code={1}][Output={2}]".format(command, str(code), str(out)))
            self.status_handler.add_error_to_status_and_log_error(message="Unexpected return code from package manager. [Code={0}][Command={1}]".format(str(code), command),
                                                                  raise_exception=bool(raise_on_exception), error_code=Constants.PatchOperationErrorCodes.CL_PACKAGE_MANAGER_FAILURE)
        else:
            self.composite_logger.log_verbose("[APM] Package Manager SUCCESS. [Command={0}][Code={1}][Output={2}]".format(command, str(code), str(out)))

        return out, code

    def invoke_apt_cache(self, command):
        """Invoke apt-cache using the command input"""
        self.composite_logger.log_verbose('[APM] Invoking apt-cache using: ' + command)
        code, out = self.env_layer.run_command_output(command, False, False)
        if code != 0:
            self.composite_logger.log_error("[APM] apt-cache ERROR. [Command={0}][Code={1}][Output={2}]".format(command, str(code), str(out)))
            self.status_handler.add_error_to_status_and_log_error(message="Unexpected return code from apt-cache. [Code={0}][Command={1}]".format(str(code), command),
                                                                  raise_exception=True, error_code=Constants.PatchOperationErrorCodes.CL_PACKAGE_MANAGER_FAILURE)
        else:  # verbose diagnostic log
            self.composite_logger.log_verbose("[APM] apt-cache SUCCESS. [Command={0}][Code={1}][Output={2}]".format(command, str(code), str(out)))

        return out

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        all_updates = []
        all_updates_versions = []
        ubuntu_pro_client_all_updates_query_success = False

        self.composite_logger.log_debug("\nDiscovering all packages...")
        # use Ubuntu Pro Client cached list when the conditions are met.
        if self.__pro_client_prereq_met and not len(self.ubuntu_pro_client_all_updates_cached) == 0:
            all_updates = self.ubuntu_pro_client_all_updates_cached
            all_updates_versions = self.ubuntu_pro_client_all_updates_versions_cached

        elif not self.__pro_client_prereq_met and not len(self.all_updates_cached) == 0:
            all_updates = self.all_updates_cached
            all_updates_versions = self.all_update_versions_cached

        if cached and not len(all_updates) == 0:
            self.composite_logger.log_debug("Get all updates : [Cached={0}][PackagesCount={1}]]".format(cached, len(all_updates)))
            return all_updates, all_updates_versions

        # when cached is False, query both default way and using Ubuntu Pro Client.
        cmd = self.dist_upgrade_simulation_cmd_template.replace('<SOURCES>', '')
        out = self.invoke_package_manager(cmd)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)

        if self.__pro_client_prereq_met:
            ubuntu_pro_client_all_updates_query_success, self.ubuntu_pro_client_all_updates_cached, self.ubuntu_pro_client_all_updates_versions_cached = self.ubuntu_pro_client.get_all_updates()

        self.composite_logger.log_debug("Get all updates : [DefaultAllPackagesCount={0}][UbuntuProClientQuerySuccess={1}][UbuntuProClientAllPackagesCount={2}]".format(len(self.all_updates_cached), ubuntu_pro_client_all_updates_query_success, len(self.ubuntu_pro_client_all_updates_cached)))

        # Get the list of updates that are present in only one of the two lists.
        different_updates = list(set(self.all_updates_cached) - set(self.ubuntu_pro_client_all_updates_cached)) + list(set(self.ubuntu_pro_client_all_updates_cached) - set(self.all_updates_cached))
        self.composite_logger.log_debug("Get all updates : [DifferentUpdatesCount={0}][Updates={1}]".format(len(different_updates), different_updates))

        # Prefer Ubuntu Pro Client output when available.
        if ubuntu_pro_client_all_updates_query_success:
            return self.ubuntu_pro_client_all_updates_cached, self.ubuntu_pro_client_all_updates_versions_cached
        else:
            return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates"""
        ubuntu_pro_client_security_updates_query_success = False
        ubuntu_pro_client_security_packages = []
        ubuntu_pro_client_security_package_versions = []

        self.composite_logger.log("\nDiscovering 'security' packages...")
        code, out = self.env_layer.run_command_output(self.prep_security_sources_list_cmd, False, False)
        if code != 0:
            self.composite_logger.log_warning(" - SLP:: Return code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))

        cmd = self.dist_upgrade_simulation_cmd_template.replace('<SOURCES>', '-oDir::Etc::Sourcelist=' + self.security_sources_list)
        out = self.invoke_package_manager(cmd)
        security_packages, security_package_versions = self.extract_packages_and_versions(out)

        if self.__pro_client_prereq_met:
            ubuntu_pro_client_security_updates_query_success, ubuntu_pro_client_security_packages, ubuntu_pro_client_security_package_versions = self.ubuntu_pro_client.get_security_updates()

        self.composite_logger.log_debug("Get Security Updates : [DefaultSecurityPackagesCount={0}][UbuntuProClientQuerySuccess={1}][UbuntuProClientSecurityPackagesCount={2}]".format(len(security_packages), ubuntu_pro_client_security_updates_query_success, len(ubuntu_pro_client_security_packages)))

        if ubuntu_pro_client_security_updates_query_success:
            return ubuntu_pro_client_security_packages, ubuntu_pro_client_security_package_versions
        else:
            return security_packages, security_package_versions

    def get_security_esm_updates(self):
        """Get missing security-esm updates."""
        ubuntu_pro_client_security_esm_updates_query_success = False
        ubuntu_pro_client_security_esm_packages = []
        ubuntu_pro_client_security_package_esm_versions = []

        if self.__pro_client_prereq_met:
            ubuntu_pro_client_security_esm_updates_query_success, ubuntu_pro_client_security_esm_packages, ubuntu_pro_client_security_package_esm_versions = self.ubuntu_pro_client.get_security_esm_updates()

        self.composite_logger.log_debug("Get Security ESM updates : [UbuntuProClientQuerySuccess={0}][UbuntuProClientSecurityEsmPackagesCount={1}]".format(ubuntu_pro_client_security_esm_updates_query_success, len(ubuntu_pro_client_security_esm_packages)))
        return ubuntu_pro_client_security_esm_updates_query_success, ubuntu_pro_client_security_esm_packages, ubuntu_pro_client_security_package_esm_versions

    def get_other_updates(self):
        """Get missing other updates"""
        ubuntu_pro_client_other_updates_query_success = False
        ubuntu_pro_client_other_packages = []
        ubuntu_pro_client_other_package_versions = []
        other_packages = []
        other_package_versions = []

        self.composite_logger.log("\nDiscovering 'other' packages...")
        all_packages, all_package_versions = self.get_all_updates(True)
        security_packages, security_package_versions = self.get_security_updates()

        for index, package in enumerate(all_packages):
            if package not in security_packages:
                other_packages.append(package)
                other_package_versions.append(all_package_versions[index])

        if self.__pro_client_prereq_met:
            ubuntu_pro_client_other_updates_query_success, ubuntu_pro_client_other_packages, ubuntu_pro_client_other_package_versions = self.ubuntu_pro_client.get_other_updates()

        self.composite_logger.log_debug("Get Other Updates : [DefaultOtherPackagesCount={0}][UbuntuProClientQuerySuccess={1}][UbuntuProClientOtherPackagesCount={2}]".format(len(other_packages), ubuntu_pro_client_other_updates_query_success, len(ubuntu_pro_client_other_packages)))

        if ubuntu_pro_client_other_updates_query_success:
            return ubuntu_pro_client_other_packages, ubuntu_pro_client_other_package_versions
        else:
            return other_packages, other_package_versions
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
    # endregion

    # region Package Information
    def get_all_available_versions_of_package(self, package_name):
        """ Returns a list of all the available versions of a package """
        # Sample output format
        #      bash | 4.3-14ubuntu1.3 | http://us.archive.ubuntu.com/ubuntu xenial-updates/main amd64 Packages
        #      bash | 4.3-14ubuntu1.2 | http://security.ubuntu.com/ubuntu xenial-security/main amd64 Packages
        #      bash | 4.3-14ubuntu1 | http://us.archive.ubuntu.com/ubuntu xenial/main amd64 Packages

        package_versions = []
        debug_log = str()

        cmd = self.single_package_check_versions.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_apt_cache(cmd)
        lines = output.strip().split('\n')

        for line in lines:
            package_details = line.split(' |')
            if len(package_details) == 3:
                debug_log += "[A] {0}\n".format(str(line))  # applicable
                package_versions.append(package_details[1].strip())
            else:
                debug_log += "[N] {0}\n".format(str(line))  # not applicable

        self.composite_logger.log_debug("[APM] Debug log on get all available versions of package: {0}".format(debug_log))
        return package_versions

    def is_package_version_installed(self, package_name, package_version):
        """ Returns true if the specific package version is installed """

        self.composite_logger.log_debug("\nCHECKING PACKAGE INSTALL STATUS FOR: " + str(package_name) + " (" + str(package_version) + ")")

        # DEFAULT METHOD
        self.composite_logger.log_debug(" - [1/2] Verifying install status with Dpkg.")
        cmd = self.single_package_find_installed_dpkg.replace('<PACKAGE-NAME>', package_name)
        code, output = self.env_layer.run_command_output(cmd, False, False)
        lines = output.strip().split('\n')

        if code == 1:  # usually not found
            # Sample output format ------------------------------------------
            # dpkg-query: package 'mysql-client' is not installed and no information is available
            # Use dpkg --info (= dpkg-deb --info) to examine archive files,
            # and dpkg --contents (= dpkg-deb --contents) to list their contents.
            #  ------------------------------------------ -------------------
            self.composite_logger.log_debug("    - Return code: 1. The package is likely NOT present on the system.")
            for line in lines:
                if 'not installed' in line and package_name in line:
                    self.composite_logger.log_debug("    - Discovered to be not installed: " + str(line))
                    return False
                else:
                    self.composite_logger.log_debug("    - Inapplicable line: " + str(line))

            self.telemetry_writer.write_event("[Installed check] Return code: 1. Unable to verify package not present on the system: " + str(output), Constants.EventLevel.Verbose)
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
            self.composite_logger.log_debug("    - Return code: 0. The package is likely present on the system.")
            composite_found_flag = 0
            for line in lines:
                if 'Package: ' in line:
                    if package_name in line:
                        composite_found_flag = composite_found_flag | 1
                    else:  # should never hit for the way this is invoked, hence telemetry
                        self.composite_logger.log_debug("    - Did not match name: " + str(package_name) + " (" + str(line) + ")")
                        self.telemetry_writer.write_event("[Installed check] Name did not match: " + package_name + " (line=" + str(line) + ")(out=" + str(output) + ")", Constants.EventLevel.Verbose)
                    continue
                if 'Version: ' in line:
                    if package_version in line:
                        composite_found_flag = composite_found_flag | 2
                    else:  # should never hit for the way this is invoked, hence telemetry
                        self.composite_logger.log_debug("    - Did not match version: " + str(package_version) + " (" + str(line) + ")")
                        self.telemetry_writer.write_event("[Installed check] Version did not match: " + str(package_version) + " (line=" + str(line) + ")(out=" + str(output) + ")", Constants.EventLevel.Verbose)
                    continue
                if 'Status: ' in line:
                    if 'install ok installed' in line:
                        composite_found_flag = composite_found_flag | 4
                    else:  # should never hit for the way this is invoked, hence telemetry
                        self.composite_logger.log_debug("    - Did not match status: " + str(package_name) + " (" + str(line) + ")")
                        self.telemetry_writer.write_event("[Installed check] Status did not match: 'install ok installed' (line=" + str(line) + ")(out=" + str(output) + ")", Constants.EventLevel.Verbose)
                    continue
                if composite_found_flag & 7 == 7:  # whenever this becomes true, the exact package version is installed
                    self.composite_logger.log_debug("    - Package, Version and Status matched. Package is detected as 'Installed'.")
                    return True
                self.composite_logger.log_debug("    - Inapplicable line: " + str(line))
            self.composite_logger.log_debug("    - Install status check did NOT find the package installed: (composite_found_flag=" + str(composite_found_flag) + ")")
            self.telemetry_writer.write_event("Install status check did NOT find the package installed: (composite_found_flag=" + str(composite_found_flag) + ")(output=" + output + ")", Constants.EventLevel.Verbose)
        else:  # This is not expected to execute. If it does, the details will show up in telemetry. Improve this code with that information.
            self.composite_logger.log_debug("    - Unexpected return code from dpkg: " + str(code) + ". Output: " + str(output))
            self.telemetry_writer.write_event("Unexpected return code from dpkg: Cmd=" + str(cmd) + ". Code=" + str(code) + ". Output=" + str(output), Constants.EventLevel.Verbose)

        # SECONDARY METHOD - Fallback
        # Sample output format
        # Listing... Done
        # apt/xenial-updates,now 1.2.29 amd64 [installed]
        self.composite_logger.log_debug(" - [2/2] Verifying install status with Apt.")
        cmd = self.single_package_find_installed_apt.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        lines = output.strip().split('\n')

        for line in lines:
            package_details = line.split(' ')
            if len(package_details) < 4:
                self.composite_logger.log_debug("    - Inapplicable line: " + str(line))
            else:
                self.composite_logger.log_debug("    - Applicable line: " + str(line))
                discovered_package_name = package_details[0].split('/')[0]  # index out of bounds check is deliberately not being done
                if discovered_package_name != package_name:
                    self.composite_logger.log_debug("      - Did not match name: " + discovered_package_name + " (" + package_name + ")")
                    continue
                if package_details[1] != package_version:
                    self.composite_logger.log_debug("      - Did not match version: " + package_details[1] + " (" + str(package_details[1]) + ")")
                    continue
                if 'installed' not in package_details[3]:
                    self.composite_logger.log_debug("      - Did not find status: " + str(package_details[3] + " (" + str(package_details[3]) + ")"))
                    continue
                self.composite_logger.log_debug("      - Package version specified was determined to be installed.")
                self.telemetry_writer.write_event("[Installed check] Fallback code disagreed with dpkg.", Constants.EventLevel.Verbose)
                return True

        self.composite_logger.log_debug("   - Package version specified was determined to NOT be installed.")
        return False

    def get_dependent_list(self, packages):
        """Returns dependent List for the list of packages"""
        package_names = ""
        for index, package in enumerate(packages):
            if index != 0:
                package_names += ' '
            package_names += package

        cmd = self.single_package_dependency_resolution_template.replace('<PACKAGE-NAME>', package_names)

        self.composite_logger.log_debug("\nRESOLVING DEPENDENCIES USING COMMAND: " + str(cmd))
        output = self.invoke_package_manager(cmd)

        dependencies, dependency_versions = self.extract_packages_and_versions(output)
        
        for package in packages:
            if package in dependencies:
                dependencies.remove(package)

        self.composite_logger.log_debug(str(len(dependencies)) + " dependent packages were found for packages '" + str(packages) + "'.")
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

        self.composite_logger.log_debug("Reboot required advanced debug flags:[DefaultPendingFileExists={0}][DefaultPendingProcessesExists={1}][UbuntuProClientCheckSuccessful={2}][UbuntuProClientRebootStatus={3}][ReportedRebootStatus={4}][DefaultException={5}]".format(default_pending_file_exists, default_pending_processes_exists, ubuntu_pro_client_check_success, ubuntu_pro_client_reboot_status, reported_reboot_status, default_exception))
        return reported_reboot_status

    def check_pro_client_prerequisites(self):
        exception_error = None
        try:
            if Constants.UbuntuProClientSettings.FEATURE_ENABLED and self.__get_os_major_version() <= Constants.UbuntuProClientSettings.MAX_OS_MAJOR_VERSION_SUPPORTED and self.__is_minimum_required_python_installed():
                self.ubuntu_pro_client.install_or_update_pro()
                self.__pro_client_prereq_met = self.ubuntu_pro_client.is_pro_working()
        except Exception as error:
            exception_error = repr(error)

        self.composite_logger.log_debug("Ubuntu Pro Client pre-requisite checks:[IsFeatureEnabled={0}][IsOSVersionCompatible={1}][IsPythonCompatible={2}][Error={3}]".format(Constants.UbuntuProClientSettings.FEATURE_ENABLED, self.__get_os_major_version() <= Constants.UbuntuProClientSettings.MAX_OS_MAJOR_VERSION_SUPPORTED, self.__is_minimum_required_python_installed(), exception_error))
        return self.__pro_client_prereq_met

    def set_security_esm_package_status(self, operation, packages):
        """Set the security-ESM classification for the esm packages."""
        security_esm_update_query_success, security_esm_updates, security_esm_updates_versions = self.get_security_esm_updates()
        if self.__pro_client_prereq_met and security_esm_update_query_success and len(security_esm_updates) > 0:
            self.telemetry_writer.write_event("set Security-ESM package status:[Operation={0}][Updates={1}]".format(operation, str(security_esm_updates)), Constants.EventLevel.Verbose)
            if operation == Constants.Op.ASSESSMENT:
                self.status_handler.set_package_assessment_status(security_esm_updates, security_esm_updates_versions, Constants.PackageClassification.SECURITY_ESM)
                # If the Ubuntu Pro Client is not attached, set the error with the code UA_ESM_REQUIRED. This will be used in portal to mark the VM as unattached to pro.
                if not self.ubuntu_pro_client.is_ubuntu_pro_client_attached:
                    self.status_handler.add_error_to_status("{0} patches requires Ubuntu Pro for Infrastructure with Extended Security Maintenance".format(len(security_esm_updates)), Constants.PatchOperationErrorCodes.UA_ESM_REQUIRED)
            elif operation == Constants.Op.INSTALLATION:
                if security_esm_update_query_success:
                    esm_packages_selected_to_install = [package for package in packages if package in security_esm_updates]
                    self.composite_logger.log_debug("Setting security ESM package status. [SelectedEsmPackagesCount={0}]".format(len(esm_packages_selected_to_install)))
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

    def add_arch_dependencies(self, package_manager, package, packages, package_versions, package_and_dependencies, package_and_dependency_versions):
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

        self.composite_logger.log_debug("Filter esm packages : [TotalPackagesCount={0}][EsmPackagesCount={1}]".format(len(packages), len(ua_esm_required_packages)))
        return non_esm_packages, non_esm_package_versions, ua_esm_required_packages, ua_esm_required_package_versions, ua_esm_required_packages_found

