"""The is Aptitude package manager implementation"""
import os
import re
from src.package_managers.PackageManager import PackageManager
from src.bootstrap.Constants import Constants


class AptitudePackageManager(PackageManager):
    """Implementation of Debian/Ubuntu based package management operations"""

    # For more details, try `man apt-get` on any Debian/Ubuntu based box.
    def __init__(self, env_layer, composite_logger, telemetry_writer):
        super(AptitudePackageManager, self).__init__(env_layer, composite_logger, telemetry_writer)
        # Repo refresh
        self.repo_refresh = 'sudo apt-get -q update'

        # Support to get updates and their dependencies
        self.security_sources_list = '/tmp/az-update-security.list'
        self.prep_security_sources_list_cmd = 'sudo grep security /etc/apt/sources.list > ' + self.security_sources_list
        self.dist_upgrade_simulation_cmd_template = 'LANG=en_US.UTF8 sudo apt-get -s dist-upgrade <SOURCES> '  # Dist-upgrade simulation template - <SOURCES> needs to be replaced before use; sudo is used as sometimes the sources list needs sudo to be readable
        self.single_package_check_versions = 'apt-cache madison <PACKAGE-NAME>'
        self.single_package_find_installed_dpkg = 'sudo dpkg -s <PACKAGE-NAME>'
        self.single_package_find_installed_apt = 'sudo apt list --installed <PACKAGE-NAME>'
        self.single_package_upgrade_simulation_cmd = '''DEBIAN_FRONTEND=noninteractive apt-get -y --only-upgrade true -s install '''
        self.single_package_dependency_resolution_template = 'DEBIAN_FRONTEND=noninteractive LANG=en_US.UTF8 apt-get -y --only-upgrade true -s install <PACKAGE-NAME> '

        # Install update
        # --only-upgrade: upgrade only single package (only if it is installed)
        self.single_package_upgrade_cmd = '''sudo DEBIAN_FRONTEND=noninteractive apt-get -y --only-upgrade true install '''

        # Package manager exit code(s)
        self.apt_exitcode_ok = 0

        # Miscellaneous
        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'  # Avoid a config prompt
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.APT)
        self.STR_DPKG_WAS_INTERRUPTED = "E: dpkg was interrupted, you must manually run 'sudo dpkg --configure -a' to correct the problem."

    def refresh_repo(self):
        self.composite_logger.log("\nRefreshing local repo...")
        self.invoke_package_manager(self.repo_refresh)

    # region Get Available Updates
    def invoke_package_manager(self, command):
        """Get missing updates using the command input"""
        self.composite_logger.log_debug('\nInvoking package manager using: ' + command)
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != self.apt_exitcode_ok and self.STR_DPKG_WAS_INTERRUPTED in out:
            self.composite_logger.log_error('[ERROR] YOU NEED TO TAKE ACTION TO PROCEED. The package manager on this machine is not in a healthy state, and '
                                            'Patch Management cannot proceed successfully. Before the next Patch Operation, please run the following '
                                            'command and perform any configuration steps necessary on the machine to return it to a healthy state: '
                                            'sudo dpkg --configure -a')
            self.telemetry_writer.send_execution_error(command, code, out)
            raise Exception('Package manager on machine is not healthy. To fix, please run: sudo dpkg --configure -a')
        elif code != self.apt_exitcode_ok:
            self.composite_logger.log('[ERROR] Package manager was invoked using: ' + command)
            self.composite_logger.log_warning(" - Return code from package manager: " + str(code))
            self.composite_logger.log_warning(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.telemetry_writer.send_execution_error(command, code, out)
            raise Exception('Unexpected return code (' + str(code) + ') from package manager on command: ' + command)
            # more known return codes should be added as appropriate
        else:  # verbose diagnostic log
            self.composite_logger.log_debug("\n\n==[SUCCESS]===============================================================")
            self.composite_logger.log_debug(" - Return code from package manager: " + str(code))
            self.composite_logger.log_debug(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.composite_logger.log_debug("==========================================================================\n\n")
        return out

    def invoke_apt_cache(self, command):
        """Invoke apt-cache using the command input"""
        self.composite_logger.log_debug('Invoking apt-cache using: ' + command)
        code, out = self.env_layer.run_command_output(command, False, False)
        if code != 0:
            self.composite_logger.log('[ERROR] apt-cache was invoked using: ' + command)
            self.composite_logger.log_warning(" - Return code from apt-cache: " + str(code))
            self.composite_logger.log_warning(" - Output from apt-cache: \n|\t" + "\n|\t".join(out.splitlines()))
            raise Exception('Unexpected return code (' + str(code) + ') from apt-cache on command: ' + command)
            # more known return codes should be added as appropriate
        else:  # verbose diagnostic log
            self.composite_logger.log_debug("\n\n==[SUCCESS]===============================================================")
            self.composite_logger.log_debug(" - Return code from apt-cache: " + str(code))
            self.composite_logger.log_debug(" - Output from apt-cache: \n|\t" + "\n|\t".join(out.splitlines()))
            self.composite_logger.log_debug("==========================================================================\n\n")
        return out

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_debug("\nDiscovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug(" - Returning cached package data.")
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        cmd = self.dist_upgrade_simulation_cmd_template.replace('<SOURCES>', '')
        out = self.invoke_package_manager(cmd)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)

        self.composite_logger.log_debug("Discovered " + str(len(self.all_updates_cached)) + " package entries.")
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates"""
        self.composite_logger.log("\nDiscovering 'security' packages...")
        code, out = self.env_layer.run_command_output(self.prep_security_sources_list_cmd, False, False)
        if code != 0:
            self.composite_logger.log_warning(" - SLP:: Return code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))

        cmd = self.dist_upgrade_simulation_cmd_template.replace('<SOURCES>', '-oDir::Etc::Sourcelist=' + self.security_sources_list)
        out = self.invoke_package_manager(cmd)
        security_packages, security_package_versions = self.extract_packages_and_versions(out)

        self.composite_logger.log("Discovered " + str(len(security_packages)) + " 'security' package entries.")
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates"""
        self.composite_logger.log("\nDiscovering 'other' packages...")
        other_packages = []
        other_package_versions = []

        all_packages, all_package_versions = self.get_all_updates(True)
        security_packages, security_package_versions = self.get_security_updates()

        for index, package in enumerate(all_packages):
            if package not in security_packages:
                other_packages.append(package)
                other_package_versions.append(all_package_versions[index])

        self.composite_logger.log("Discovered " + str(len(other_packages)) + " 'other' package entries.")
        return other_packages, other_package_versions
    # endregion

    # region Output Parser(s)
    def extract_packages_and_versions(self, output):
        # sample output format
        # Inst coreutils [8.25-2ubuntu2] (8.25-2ubuntu3~16.10 Ubuntu:16.10/yakkety-updates [amd64])
        # Inst python3-update-manager [1:16.10.7] (1:16.10.8 Ubuntu:16.10/yakkety-updates [all]) [update-manager-core:amd64 ]
        # Inst update-manager-core [1:16.10.7] (1:16.10.8 Ubuntu:16.10/yakkety-updates [all])

        self.composite_logger.log_debug("\nExtracting package and version data...")
        packages = []
        versions = []

        search_text = r'Inst[ ](.*?)[ ].*?[(](.*?)[ ](.*?)[ ]\[(.*?)\]'
        search = re.compile(search_text, re.M | re.S)
        package_list = search.findall(str(output))

        for package in package_list:
            packages.append(package[0])
            versions.append(package[1])

        self.composite_logger.log_debug("Extracted package and version data for " + str(len(packages)) + " packages.")
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

        cmd = self.single_package_check_versions.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_apt_cache(cmd)
        lines = output.strip().split('\n')

        for line in lines:
            package_details = line.split(' |')
            if len(package_details) == 3:
                self.composite_logger.log_debug(" - Applicable line: " + str(line))
                package_versions.append(package_details[1].strip())
            else:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))

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

            self.telemetry_writer.send_debug_info("[Installed check] Return code: 1. Unable to verify package not present on the system: " + str(output))
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
                        self.telemetry_writer.send_debug_info("[Installed check] Name did not match: " + package_name + " (line=" + str(line) + ")(out=" + str(output) + ")")
                    continue
                if 'Version: ' in line:
                    if package_version in line:
                        composite_found_flag = composite_found_flag | 2
                    else:  # should never hit for the way this is invoked, hence telemetry
                        self.composite_logger.log_debug("    - Did not match version: " + str(package_version) + " (" + str(line) + ")")
                        self.telemetry_writer.send_debug_info("[Installed check] Version did not match: " + str(package_version) + " (line=" + str(line) + ")(out=" + str(output) + ")")
                    continue
                if 'Status: ' in line:
                    if 'install ok installed' in line:
                        composite_found_flag = composite_found_flag | 4
                    else:  # should never hit for the way this is invoked, hence telemetry
                        self.composite_logger.log_debug("    - Did not match status: " + str(package_name) + " (" + str(line) + ")")
                        self.telemetry_writer.send_debug_info("[Installed check] Status did not match: 'install ok installed' (line=" + str(line) + ")(out=" + str(output) + ")")
                    continue
                if composite_found_flag & 7 == 7:  # whenever this becomes true, the exact package version is installed
                    self.composite_logger.log_debug("    - Package, Version and Status matched. Package is detected as 'Installed'.")
                    return True
                self.composite_logger.log_debug("    - Inapplicable line: " + str(line))
            self.composite_logger.log_debug("    - Install status check did NOT find the package installed: (composite_found_flag=" + str(composite_found_flag) + ")")
            self.telemetry_writer.send_debug_info("Install status check did NOT find the package installed: (composite_found_flag=" + str(composite_found_flag) + ")(output=" + output + ")")
        else:  # This is not expected to execute. If it does, the details will show up in telemetry. Improve this code with that information.
            self.composite_logger.log_debug("    - Unexpected return code from dpkg: " + str(code) + ". Output: " + str(output))
            self.telemetry_writer.send_debug_info("Unexpected return code from dpkg: Cmd=" + str(cmd) + ". Code=" + str(code) + ". Output=" + str(output))

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
                self.telemetry_writer.send_debug_info("[Installed check] Fallback code disagreed with dpkg.")
                return True

        self.composite_logger.log_debug("   - Package version specified was determined to NOT be installed.")
        return False

    def get_dependent_list(self, package_name):
        """Returns dependent List of the package"""
        cmd = self.single_package_dependency_resolution_template.replace('<PACKAGE-NAME>', package_name)

        self.composite_logger.log_debug("\nRESOLVING DEPENDENCIES USING COMMAND: " + str(cmd))
        output = self.invoke_package_manager(cmd)

        packages, package_versions = self.extract_packages_and_versions(output)
        if package_name in packages:
            packages.remove(package_name)

        self.composite_logger.log_debug(str(len(packages)) + " dependent updates were found for package '" + package_name + "'.")
        return packages

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

    def do_processes_require_restart(self):
        """Defaulting this for Apt"""
        return False
