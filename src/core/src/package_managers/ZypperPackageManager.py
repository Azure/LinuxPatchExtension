"""ZypperPackageManager for SUSE"""
import re
from src.package_managers.PackageManager import PackageManager
from src.bootstrap.Constants import Constants


class ZypperPackageManager(PackageManager):
    """Implementation of SUSE package management operations"""

    def __init__(self, env_layer, composite_logger, telemetry_writer):
        super(ZypperPackageManager, self).__init__(env_layer, composite_logger, telemetry_writer)
        # Repo refresh
        self.repo_clean = 'sudo zypper clean -a'
        self.repo_refresh = 'sudo zypper refresh'

        # Support to get updates and their dependencies
        self.zypper_check = 'sudo LANG=en_US.UTF8 zypper list-updates'
        self.zypper_check_security = 'sudo LANG=en_US.UTF8 zypper list-patches --category security'
        self.single_package_check_versions = 'LANG=en_US.UTF8 zypper search -s <PACKAGE-NAME>'
        self.single_package_upgrade_simulation_cmd = 'sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run '
        self.zypper_install_security_patches_simulate = 'sudo LANG=en_US.UTF8 zypper --non-interactive patch --category security --dry-run'

        # Install update
        self.single_package_upgrade_cmd = 'sudo zypper --non-interactive update '
        self.zypper_install_security_patches = 'sudo zypper --non-interactive patch --category security'

        # Package manager exit code(s)
        self.zypper_exitcode_ok = 0
        self.zypper_exitcode_zypper_updated = 103

        # Support to check for processes requiring restart
        self.zypper_ps = "sudo zypper ps -s"

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.ZYPPER)

    def refresh_repo(self):
        self.composite_logger.log("Refreshing local repo...")
        # self.invoke_package_manager(self.repo_clean)  # purges local metadata for rebuild - addresses a possible customer environment error
        self.invoke_package_manager(self.repo_refresh)

    # region Get Available Updates
    def invoke_package_manager(self, command):
        """Get missing updates using the command input"""
        self.composite_logger.log_debug('\nInvoking package manager using: ' + command)
        code, out = self.env_layer.run_command_output(command, False, False)
        if code not in [self.zypper_exitcode_ok, self.zypper_exitcode_zypper_updated]:  # more known return codes should be added as appropriate
            self.composite_logger.log('[ERROR] Package manager was invoked using: ' + command)
            self.composite_logger.log_warning(" - Return code from package manager: " + str(code))
            self.composite_logger.log_warning(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.telemetry_writer.send_execution_error(command, code, out)
            raise Exception('Unexpected return code (' + str(code) + ') from package manager on command: ' + command)
        else:  # verbose diagnostic log
            self.composite_logger.log_debug("\n\n==[SUCCESS]===============================================================")
            self.composite_logger.log_debug(" - Return code from package manager: " + str(code))
            self.composite_logger.log_debug(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.composite_logger.log_debug("==========================================================================\n\n")

        if code == self.zypper_exitcode_zypper_updated:
            self.composite_logger.log_debug(" - Package manager update detected. Patch installation run will be repeated.")
            self.set_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, True)
        return out

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_debug("\nDiscovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug(" - Returning cached package data.")
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        out = self.invoke_package_manager(self.zypper_check)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)
        self.composite_logger.log_debug("Discovered " + str(len(self.all_updates_cached)) + " package entries.")
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates"""
        self.composite_logger.log_debug("\nDiscovering 'security' packages...")
        security_packages = []
        security_package_versions = []

        # Get all security packages
        out = self.invoke_package_manager(self.zypper_install_security_patches_simulate)
        packages_from_patch_data = self.extract_packages_from_patch_data(out)

        # Correlate and enrich with versions from all package data
        all_packages, all_package_versions = self.get_all_updates(True)

        for index, package in enumerate(all_packages):
            if package in packages_from_patch_data:
                security_packages.append(package)
                security_package_versions.append(all_package_versions[index])
                self.composite_logger.log_debug(" - " + str(package) + " [" + str(all_package_versions[index]) + "]")

        self.composite_logger.log_debug("Discovered " + str(len(security_packages)) + " 'security' package entries.\n")
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates"""
        self.composite_logger.log_debug("\nDiscovering 'other' packages...")
        other_packages = []
        other_package_versions = []

        # Get all security packages
        out = self.invoke_package_manager(self.zypper_install_security_patches_simulate)
        packages_from_patch_data = self.extract_packages_from_patch_data(out)

        # SPECIAL CONDITION IF ZYPPER UPDATE IS DETECTED - UNAVOIDABLE SECURITY UPDATE(S) WILL BE INSTALLED AND THE RUN REPEATED FOR 'OTHER".
        if self.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, True):
            self.composite_logger.log_warning("Important: Zypper-related security updates are necessary to continue - those will be installed first.")
            self.composite_logger.log_warning("Temporarily skipping 'other' package entry discovery due to Zypper-related security updates.\n")
            return self.get_security_updates()  # TO DO: in some cases, some misc security updates may sneak in - filter this (to do item)
            # also for above: also note that simply force updating only zypper does not solve the issue - tried

        # Subtract from all package data
        all_packages, all_package_versions = self.get_all_updates(True)

        for index, package in enumerate(all_packages):
            if package not in packages_from_patch_data:
                other_packages.append(package)
                other_package_versions.append(all_package_versions[index])
                self.composite_logger.log_debug(" - " + str(package) + " [" + str(all_package_versions[index]) + "]")

        self.composite_logger.log_debug("Discovered " + str(len(other_packages)) + " 'other' package entries.\n")
        return other_packages, other_package_versions
    # endregion

    # region Output Parser(s)
    def extract_packages_and_versions(self, output):
        """Returns packages and versions from given output"""

        # Sample output for the cmd 'zypper list-updates' is :
        # Loading repository data...
        # Reading installed packages...
        # S | Repository         | Name               | Current Version | Available Version | Arch
        # --+--------------------+--------------------+-----------------+-------------------+-------#
        # v | SLES12-SP2-Updates | kernel-default     | 4.4.38-93.1     | 4.4.49-92.11.1    | x86_64
        # v | SLES12-SP2-Updates | libgoa-1_0-0       | 3.20.4-7.2      | 3.20.5-9.6        | x86_64

        self.composite_logger.log_debug("\nExtracting package and version data...")
        packages = []
        versions = []

        lines = output.strip().split('\n')
        for line in lines:
            line_split = line.split(' | ')
            if len(line_split) == 6 and line_split[1].strip() != 'Repository':
                package = line_split[2].strip()
                packages.append(package)
                version = line_split[4].strip()
                versions.append(version)
                self.composite_logger.log_debug(" - Applicable line: " + line + ". Package: " + package + ". Version: " + version + ".")
            else:
                self.composite_logger.log_debug(" - Inapplicable line: " + line)

        return packages, versions

    def extract_packages_from_patch_data(self, output):
        """Returns packages (sometimes with version information embedded) from patch data"""
        self.composite_logger.log_debug("\nExtracting package entries from security patch data...")
        packages = []
        parser_seeing_packages_flag = False

        lines = output.strip().split('\n')
        for line in lines:
            if "Warning: One of the installed patches affects the package manager itself. Run this command once more to install any other needed patches." in line:
                self.composite_logger.log_debug(" - Package manager requires restart. Patch installation run will be repeated.")
                self.set_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, True)

            if not parser_seeing_packages_flag:
                if 'package is going to be installed' in line or 'package is going to be upgraded' in line or \
                        'packages are going to be installed:' in line or 'packages are going to be upgraded:' in line:
                    self.composite_logger.log_debug(" - Start marker line: " + line)
                    parser_seeing_packages_flag = True  # Start -- Next line contains information we need
                else:
                    self.composite_logger.log_debug(" - Inapplicable line: " + line)
                continue

            if not line or line.isspace():
                self.composite_logger.log_debug(" - End marker line: " + line)
                parser_seeing_packages_flag = False
                continue  # End -- We're past a package information block

            line_parts = line.strip().split(' ')
            self.composite_logger.log_debug(" - Package list line: " + line)
            for line_part in line_parts:
                packages.append(line_part)
                self.composite_logger.log_debug("    - Package: " + line_part)

        self.composite_logger.log_debug("\nExtracted " + str(len(packages)) + " prospective package entries from security patch data.\n")
        return packages
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
        """ Returns a list of all the available versions of a package that are not already installed """
        return self.get_all_available_versions_of_package_ex(package_name, include_installed=False, include_available=True)

    def is_package_version_installed(self, package_name, package_version):
        """ Returns true if the specific package version is installed """
        self.composite_logger.log_debug("\nCHECKING PACKAGE INSTALL STATUS FOR: " + str(package_name) + "(" + str(package_version) + ")")
        installed_package_versions = self.get_all_available_versions_of_package_ex(package_name, include_installed=True, include_available=False)
        for version in installed_package_versions:
            if version == package_version:
                self.composite_logger.log_debug(" - Installed version match found.")
                return True
            else:
                self.composite_logger.log_debug(" - Did not match: " + str(version))

        return False

    def get_all_available_versions_of_package_ex(self, package_name, include_installed=False, include_available=True):
        """ Returns a list of all the available versions of a package """
        # Sample output format
        # S | Name                    | Type       | Version      | Arch   | Repository
        # --+-------------------------+------------+--------------+--------+-------------------
        # v | bash                    | package    | 4.3-83.5.2   | x86_64 | SLES12-SP2-Updates

        package_versions = []

        self.composite_logger.log_debug("\nGetting all available versions of package '" + package_name + "' [Installed=" + str(include_installed) + ", Available=" + str(include_available) + "]...")
        cmd = self.single_package_check_versions.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        lines = output.strip().split('\n')

        packages_list_flag = False
        for line in lines:
            if not packages_list_flag:  # keep going until the packages list starts
                if not all(word in line for word in ["S", "Name", "Type", "Version", "Arch", "Repository"]):
                    self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                    continue
                else:
                    self.composite_logger.log_debug(" - Package list started: " + str(line))
                    packages_list_flag = True
                    continue

            package_details = line.split(' |')
            if len(package_details) != 6:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue
            else:
                self.composite_logger.log_debug(" - Applicable line: " + str(line))
                details_status = str(package_details[0].strip())
                details_name = str(package_details[1].strip())
                details_type = str(package_details[2].strip())
                details_version = str(package_details[3].strip())

                if details_name != package_name:
                    self.composite_logger.log_debug("    - Excluding as package name doesn't match exactly: " + details_name)
                    continue
                if details_type == "srcpackage":
                    self.composite_logger.log_debug("    - Excluding as package is of type 'srcpackage'.")
                    continue
                if (details_status == "i" or details_status == "i+") and not include_installed:  # exclude installed as (include_installed not selected)
                    self.composite_logger.log_debug("    - Excluding as package version is installed: " + details_version)
                    continue
                if (details_status != "i" and details_status != "i+") and not include_available:  # exclude available as (include_available not selected)
                    self.composite_logger.log_debug("    - Excluding as package version is available: " + details_version)
                    continue

                package_versions.append(details_version)

        return package_versions

    def get_dependent_list(self, package_name):
        # Sample output for the cmd
        # 'sudo  LANG=en_US.UTF8 zypper --non-interactive update --dry-run man' is :
        #
        # Refreshing service 'SMT-http_smt-azure_susecloud_net'.
        # Refreshing service 'cloud_update'.
        # Loading repository data...
        # Reading installed packages...
        # Resolving package dependencies...
        #
        # The following 16 NEW packages are going to be installed:
        #   cups-filters-ghostscript ghostscript ghostscript-fonts-other\
        # ghostscript-fonts-std  ghostscript-x11 groff-full libICE6 libjasper1 libjbig2 libjpeg8
        #  libnetpbm11 libSM6 libtiff5 libXt6 netpbm psutils
        #
        # The following package is going to be upgraded:
        #   man

        # 1 package to upgrade, 16 new.
        # Overall download size: 23.7 MiB. Already cached: 0 B. \
        # After the operation, additional 85.1 MiB will be used.
        # Continue? [y/n/? shows all options] (y): y

        self.composite_logger.log_debug("\nRESOLVING DEPENDENCIES USING COMMAND:: " + str(self.single_package_upgrade_simulation_cmd + package_name))
        dependent_updates = []

        output = self.invoke_package_manager(self.single_package_upgrade_simulation_cmd + package_name)
        lines = output.strip().split('\n')

        for line in lines:
            if line.find(" going to be ") < 0:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue

            updates_line = lines[lines.index(line) + 1]
            dependent_package_names = re.split(r'\s+', updates_line)
            for dependent_package_name in dependent_package_names:
                if len(dependent_package_name) != 0 and dependent_package_name != package_name:
                    self.composite_logger.log_debug(" - Dependency detected: " + dependent_package_name)
                    dependent_updates.append(dependent_package_name)

        self.composite_logger.log_debug(str(len(dependent_updates)) + " dependent updates were found for package '" + package_name + "'.")
        return dependent_updates

    def get_product_name(self, package_name):
        """Retrieve product name """
        return package_name

    def get_package_size(self, output):
        """Retrieve package size from installation output string"""
        # Sample output line:
        # Overall download size: 195.0 KiB. Already cached: 0 B. After the operation, additional 281.0 B will be used.
        try:
            if "Nothing to do." in output:
                return Constants.UNKNOWN_PACKAGE_SIZE
            search_txt = r'Overall download size:[ ](.*?)\.[ ]Already'
            search = re.compile(search_txt, re.M | re.S)
            pkg_list = search.findall(str(output))
            if len(pkg_list) == 0 or pkg_list[0] == "":
                return Constants.UNKNOWN_PACKAGE_SIZE
            return pkg_list[0]
        except Exception as error:
            self.composite_logger.log_debug(" - Could not get package size from output: " + repr(error))
            return Constants.UNKNOWN_PACKAGE_SIZE
    # endregion

    def do_processes_require_restart(self):
        """Signals whether processes require a restart due to updates"""
        output = self.invoke_package_manager(self.zypper_ps)
        lines = output.strip().split('\n')

        process_list_flag = False
        process_count = 0
        process_list_verbose = ""
        for line in lines:
            if not process_list_flag:  # keep going until the process list starts
                if not all(word in line for word in ["PID", "PPID", "UID", "User", "Command", "Service"]):
                    self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                    continue
                else:
                    self.composite_logger.log_debug(" - Process list started: " + str(line))
                    process_list_flag = True
                    continue

            process_details = line.split(' |')
            if len(process_details) < 6:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue
            else:
                self.composite_logger.log_debug(" - Applicable line: " + str(line))
                process_count += 1
                process_list_verbose += process_details[4].strip() + " (" + process_details[0].strip() + "), "  # process name and id

        self.composite_logger.log(" - Processes requiring restart (" + str(process_count) + "): [" + process_list_verbose + "<eol>]")
        return process_count != 0  # True if there were any
