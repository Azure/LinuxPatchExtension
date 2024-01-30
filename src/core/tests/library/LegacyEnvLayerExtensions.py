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
import os
import sys
from core.src.bootstrap.Constants import Constants


class LegacyEnvLayerExtensions():
    def __init__(self, package_manager_name):
        self.legacy_package_manager_name = package_manager_name
        self.legacy_test_type = "HappyPath"
        self.temp_folder_path = ""

    class LegacyPlatform(object):
        def linux_distribution(self):
            return ['Ubuntu', '16.04', 'Xenial']

        @staticmethod
        def system():   # OS Type
            return 'Linux'

        @staticmethod
        def machine():  # architecture
            return 'x86_64'

        @staticmethod
        def node():     # machine name
            return 'LegacyTestVM'

    def get_package_manager(self):
        """return passed in package manager name"""
        return self.legacy_package_manager_name

    def set_temp_folder_path(self, temp_folder_path):
        self.temp_folder_path = temp_folder_path

    @staticmethod
    def get_python_major_version():
        if hasattr(sys.version_info, 'major'):
            return sys.version_info.major
        else:
            return sys.version_info[0]  # python 2.6 doesn't have attributes like 'major' within sys.version_info

    # To be deprecated over time
    def run_command_output(self, cmd, no_output=False, chk_err=True):
        if no_output:
            return 0, None
        else:
            output = ''
            code = 0

            if self.legacy_test_type == 'HappyPath':
                if cmd.find("cat /proc/cpuinfo | grep name") > -1:
                    code = 0
                    output = "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz"
                elif self.legacy_package_manager_name is Constants.ZYPPER:
                    if cmd.find("list-updates") > -1:
                        code = 0
                        output = " Refreshing service 'cloud_update'.\n" + \
                                 " Loading repository data...\n" + \
                                 " Reading installed packages..\n" + \
                                 "S | Repository         | Name               | Current Version | Available Version | Arch\n" + \
                                 "--+--------------------+--------------------+-----------------+-------------------+-------#\n" + \
                                 "v | SLES12-SP2-Updates | kernel-default     | 4.4.38-93.1     | 4.4.49-92.11.1    | x86_64\n" + \
                                 "v | SLES12-SP2-Updates | libgcc             | 6.45.3-4.1      | 5.60.7-8.1        | x86_64\n" + \
                                 "v | SLES12-SP2-Updates | libgoa-1_0-0       | 3.20.4-7.2      | 3.20.5-9.6        | x86_64\n" + \
                                 "v | SLES12-SP2-Updates | libgoa-2_0-0       | 3.20.4-7.2      | 3.20.5-9.6       \n" + \
                                 "v | SLES12-SP2-Updates | libgoa-3_0-0       \n"
                    elif cmd.find("--category security") > -1 and cmd.find("--dry-run") > -1:
                        code = 0
                        output = "Refreshing service 'SUSE_Linux_Enterprise_Server_12_SP2_x86_64'.\n" + \
                                 "Retrieving repository 'SLES12-SP2-Updates' metadata ...............................[done]\n" + \
                                 "Building repository 'SLES12-SP2-Updates' cache ....................................[done]\n" + \
                                 "Loading repository data...\n" + \
                                 "Reading installed packages...\n" + \
                                 "Patch 'SUSE-SLE-SERVER-12-SP2-2018-471-1' is not in the specified category.\n" + \
                                 "Patch 'SUSE-SLE-SERVER-12-SP2-2018-21-1' is not in the specified category.\n" + \
                                 "Resolving package dependencies...\n" + \
                                 "\n" + \
                                 "The following NEW patch is going to be installed:\n" + \
                                 "  SUSE-SLE-SERVER-12-SP2-2017-1252\n" + \
                                 "\n" + \
                                 "The following 4 packages are going to be upgraded:\n" + \
                                 "  kernel-default libzypp zypper zypper-log\n" + \
                                 "\n" + \
                                 "4 packages to upgrade.\n" + \
                                 "Overall download size: 3.8 MiB. Already cached: 0 B. After the operation, additional 655.7 KiB will be used.\n" + \
                                 "Continue? [y/n/? shows all options] (y): y\n" + \
                                 "Warning: One of installed patches affects the package manager itself. Run this command once more to install any other needed patches."
                    elif cmd.find("LANG=en_US.UTF8 zypper search -s selinux-policy") > -1:
                        code = 0
                        output = "Loading repository data...\n" + \
                                 "Reading installed packages...\n" + \
                                 "\n" + \
                                 "S  | Name                   | Type       | Version             | Arch   | Repository\n" + \
                                 "---+------------------------+------------+---------------------+--------+-------------------\n" + \
                                 " i | selinux-policy         | package    | 3.13.1-102.el7_3.16 | noarch | SLES12-SP2-Updates\n"
                    elif cmd.find("dry-run") > -1:
                        code = 0
                        output = " Refreshing service 'SMT-http_smt-azure_susecloud_net'.\n" + \
                                 " Refreshing service 'cloud_update'.\n" + \
                                 " Loading repository data...\n" + \
                                 " Reading installed packages...\n" + \
                                 " Resolving package dependencies...\n" + \
                                 "\n" + \
                                 " The following 16 NEW packages are going to be installed:\n" + \
                                 "   cups-filters-ghostscript ghostscript ghostscript-fonts-other " + \
                                 "ghostscript-fonts-std  ghostscript-x11 " + \
                                 "groff-full libICE6 libjasper1 libjbig2 " + \
                                 "libjpeg8 libnetpbm11 libSM6 libtiff5 libXt6 netpbm psutils\n" + \
                                 "\n" + \
                                 " The following package is going to be upgraded:\n" + \
                                 "   man\n" + \
                                 "\n" + \
                                 " 1 package to upgrade, 16 new.\n" + \
                                 " Overall download size: 23.7 MiB. Already cached: 0 B. \n" + \
                                 " After the operation, additional 85.1 MiB will be used.\n" + \
                                 " Continue? [y/n/? shows all options] (y): y\n"
                    elif cmd.find("sudo zypper --non-interactive update sudo") > -1:
                        code = 0
                        output = "Refreshing service 'SMT-http_smt-azure_susecloud_net'.\n" + \
                                 "Refreshing service 'cloud_update'.\n" + \
                                 "Loading repository data...\n" + \
                                 "Reading installed packages...\n" + \
                                 "Resolving package dependencies...\n" + \
                                 "The following package is going to be upgraded:\n" + \
                                 "sudo\n" + \
                                 "1 package to upgrade.\n" + \
                                 "Overall download size: 810.9 KiB. Already cached: 0 B. " + \
                                 "No additional space will be used or freed after the operation.\n" + \
                                 "Continue? [y/n/? shows all options] (y): y\n" + \
                                 "Retrieving package sudo-1.8.10p3-2.11.1.x86_64                        " + \
                                 "             (1/1), 810.9 KiB (  3.1 MiB unpacked)\n" + \
                                 "Retrieving: sudo-1.8.10p3-2.11.1.x86_64.rpm .........................." + \
                                 "............................................[done]\n" + \
                                 "Checking for file conflicts: ........................................." + \
                                 "............................................[done]\n" + \
                                 "(1/1) Installing: sudo-1.8.10p3-2.11.1.x86_64 ........................" + \
                                 "............................................[done]\n" + \
                                 "There are some running programs that might use files deleted by recent " + \
                                 "upgrade. You may wish to check and restart some of them. " + \
                                 "Run 'zypper ps -s' to list these programs."
                    elif cmd.find("zypper search -s bash") > -1:
                        code = 0
                        output = "Loading repository data....\n" + \
                                 "Reading installed packages....\n" + \
                                 ".\n" + \
                                 "S | Name                    | Type       | Version      | Arch   | Repository.\n" + \
                                 "--+-------------------------+------------+--------------+--------+-------------------.\n" + \
                                 "v | bash                    | package    | 4.3-83.5.2   | x86_64 | SLES12-SP2-Updates.\n" + \
                                 "v | bash                    | package    | 4.3-82.1     | x86_64 | SLES12-SP2-Updates.\n" + \
                                 "i | bash                    | package    | 4.3-78.39    | x86_64 | SLES12-SP2-Pool.\n" + \
                                 "i | bash                    | package    | 4.3-78.39    | x86_64 | SLES12-SP2-12.2-0.\n" + \
                                 "  | bash                    | srcpackage | 4.3-83.5.2   | noarch | SLES12-SP2-Updates.\n" + \
                                 "  | bash                    | srcpackage | 4.3-78.39    | noarch | SLES12-SP2-12.2-0.\n" + \
                                 "i | bash-doc                | package    | 4.3-78.39    | noarch | SLES12-SP2-Pool.\n" + \
                                 "i | bash-doc                | package    | 4.3-78.39    | noarch | SLES12-SP2-12.2-0.\n" + \
                                 "v | systemd-bash-completion | package    | 228-150.35.1 | noarch | SLES12-SP2-Updates.\n" + \
                                 "v | systemd-bash-completion | package    | 228-150.32.1 | noarch | SLES12-SP2-Updates.\n" + \
                                 "i | systemd-bash-completion | package    | 228-117.12   | noarch | SLES12-SP2-Pool.\n" + \
                                 "i | systemd-bash-completion | package    | 228-117.12   | noarch | SLES12-SP2-12.2-0.\n"
                    elif cmd.find("sudo zypper ps -s") > -1:
                        code = 0
                        output = "The following running processes use deleted files:\n" + \
                                 "\n" + \
                                 "PID    | PPID  | UID  | User           | Command                     | Service\n" + \
                                 "-------+-------+------+----------------+-----------------------------+-----------------\n" + \
                                 "509    | 1     | 0    | root           | systemd-journald (deleted)  | systemd-journald\n" + \
                                 "537    | 1     | 0    | root           | haveged                     | haveged\n" + \
                                 "994    | 1     | 499  | messagebus     | dbus-daemon (deleted)       | dbus\n" + \
                                 "1037   | 1     | 0    | root           | rsyslogd                    | rsyslog\n" + \
                                 "1038   | 1     | 0    | root           | hv_vss_daemon               | hv_vss_daemon\n" + \
                                 "1047   | 1     | 0    | root           | systemd-logind (deleted)    | systemd-logind\n" + \
                                 "1058   | 1     | 0    | root           | agetty (deleted)            | getty@tty1\n" + \
                                 "1146   | 1     | 0    | root           | gdm                         | display-manager\n" + \
                                 "1170   | 1146  | 0    | root           | gdm-simple-slave            | display-manager\n" + \
                                 "1201   | 1170  | 0    | root           | Xorg (deleted)              | display-manager\n" + \
                                 "1203   | 1     | 0    | root           | accounts-daemon             | accounts-daemon\n" + \
                                 "1209   | 1     | 497  | polkitd        | polkitd                     | polkit\n" + \
                                 "1229   | 1     | 0    | root           | wickedd-dhcp4               | wickedd-dhcp4\n" + \
                                 "1230   | 1     | 0    | root           | wickedd-auto4               | wickedd-auto4\n" + \
                                 "1231   | 1     | 0    | root           | wickedd-dhcp6               | wickedd-dhcp6\n" + \
                                 "1240   | 1     | 0    | root           | wickedd                     | wickedd\n" + \
                                 "1243   | 1     | 0    | root           | wickedd-nanny               | wickedd-nanny\n" + \
                                 "1300   | 1170  | 0    | root           | gdm-session-worker          |\n" + \
                                 "2187   | 1     | 0    | root           | omiserver                   | omid\n" + \
                                 "2357   | 1     | 0    | root           | master                      | postfix\n" + \
                                 "2360   | 2357  | 51   | postfix        | qmgr                        | postfix\n" + \
                                 "2385   | 1     | 0    | root           | cron                        | cron\n" + \
                                 "5165   | 38186 | 0    | root           | sshd                        |\n" + \
                                 "5219   | 2187  | 0    | root           | omiagent                    | omid\n" + \
                                 "23698  | 1     | 481  | nxautomation   | systemd (deleted)           |\n" + \
                                 "23703  | 0     | 481  | nxautomation   | systemd (deleted)           |\n" + \
                                 "27732  | 1     | 0    | root           | sshd (deleted)              |\n" + \
                                 "27736  | 1     | 0    | root           | systemd (deleted)           |\n" + \
                                 "27740  | 0     | 0    | root           | systemd (deleted)           |\n" + \
                                 "27743  | 27732 | 0    | root           | sftp-server (deleted)       |\n" + \
                                 "30600  | 1     | 481  | nxautomation   | python2.7                   |\n" + \
                                 "30623  | 1     | 481  | nxautomation   | python2.7                   |\n" + \
                                 "38186  | 1     | 0    | root           | sshd                        | sshd\n" + \
                                 "117533 | 38186 | 0    | root           | sshd                        |\n" + \
                                 "120274 | 38186 | 0    | root           | sshd                        |\n" + \
                                 "\n" + \
                                 "You may wish to restart these processes.\n" + \
                                 "See 'man zypper' for information about the meaning of values in the above table.\n"
                    elif cmd.find('ps --forest -o pid,cmd -g $(ps -o sid= -p') > -1:
                        code = 0
                        output = "PID CMD\n" + \
                                 "7736 /bin/bash\n" + \
                                 "7912  \_ python3 package_test.py\n" + \
                                 "7913  |   \_ sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run bind-utils\n" + \
                                 "7914  |       \_ zypper --non-interactive update --dry-run bind-utils\n" + \
                                 "7982  |           \_ /usr/bin/python3 /usr/lib/zypp/plugins/urlresolver/susecloud\n" + \
                                 "7984  |               \_ /usr/bin/python3 /usr/bin/azuremetadata --api latest --subscriptionId --billingTag --attestedData --signature\n" + \
                                 "7986  \_ python3 package_test.py\n" + \
                                 "8298      \_ sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run grub2-i386-pc\n"
                    elif cmd.find('sudo zypper refresh --services') > -1:
                        code = 0
                        output = "Refreshing service \'Web_and_Scripting_Module_x86_64\'." + \
                                 "All services have been refreshed."
                    elif cmd.find('sudo zypper refresh') > -1:
                        code = 0
                        output = "Retrieving repository 'SLE-Module-Basesystem15-SP3-Pool' metadata ................................................................[done]\n" + \
                                 "Building repository 'SLE-Module-Basesystem15-SP3-Pool' cache .....................................................................[done]\n" + \
                                 "All repositories have been refreshed."
                    elif cmd.find('sudo zypper --non-interactive update --replacefiles'):
                        code = 0
                        output = "Refreshing service 'Advanced_Systems_Management_Module_x86_64'.\n" + \
                                 "Loading repository data...\n" + \
                                 "Reading installed packages...\n" + \
                                 "Resolving package dependencies...\n" + \
                                 "The following 5 items are locked and will not be changed by any action:\n" + \
                                 " Installed:\n" + \
                                 "  auoms azsec-clamav azsec-monitor azure-security qualys-command-line-agent\n" + \
                                 "The following 3 packages are going to be upgraded:\n" + \
                                 "  samba-client-libs samba-libs samba-libs-python3\n" + \
                                 "3 packages to upgrade.\n" + \
                                 "Overall download size: 6.0 MiB. Already cached: 0 B. No additional space will be used or freed after the operation.\n" + \
                                 "Continue? [y/n/...? shows all options] (y): y\n" + \
                                 "Retrieving package samba-client-libs-4.15.4+git.331.61fc89677dd-3.60.1.x86_64                (1/3),   5.2 MiB ( 21.0 MiB unpacked)\n" + \
                                 "Retrieving: samba-client-libs-4.15.4+git.331.61fc89677dd-3.60.1.x86_64.rpm .................................................[done]\n" + \
                                 "Retrieving package samba-libs-python3-4.15.4+git.331.61fc89677dd-3.60.1.x86_64               (2/3), 367.5 KiB (290.3 KiB unpacked)\n" + \
                                 "Retrieving: samba-libs-python3-4.15.4+git.331.61fc89677dd-3.60.1.x86_64.rpm ................................................[done]\n" + \
                                 "Retrieving package samba-libs-4.15.4+git.331.61fc89677dd-3.60.1.x86_64                       (3/3), 441.7 KiB (544.9 KiB unpacked)\n" + \
                                 "Retrieving: samba-libs-4.15.4+git.331.61fc89677dd-3.60.1.x86_64.rpm ........................................................[done]\n" + \
                                 "Checking for file conflicts: ...............................................................................................[done]\n" + \
                                 "(1/3) Installing: samba-client-libs-4.15.4+git.331.61fc89677dd-3.60.1.x86_64 ...............................................[done]\n" + \
                                 "(2/3) Installing: samba-libs-python3-4.15.4+git.331.61fc89677dd-3.60.1.x86_64 ..............................................[done]\n" + \
                                 "(3/3) Installing: samba-libs-4.15.4+git.331.61fc89677dd-3.60.1.x86_64 ......................................................[done]"
                elif self.legacy_package_manager_name is Constants.YUM:
                    if cmd.find("--security check-update") > -1:
                        code = 100
                        output = "\n" + \
                                 "libgcc.i686                                      " + \
                                 "4.8.5-28.el7                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n"
                    elif cmd.find("check-update") > -1:
                        code = 100
                        output = "\n" + \
                                 "selinux-policy.noarch                                              " + \
                                 "3.13.1-102.el7_3.16                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n" + \
                                 "selinux-policy-targeted.noarch                                     " + \
                                 "3.13.1-102.el7_3.16                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n" + \
                                 "libgcc.i686                                      " + \
                                 "4.8.5-28.el7                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n" + \
                                 "tar.x86_64                                                " + \
                                 "2:1.26-34.el7                           " + \
                                 "rhui-rhel-7-server-rhui-rpms\n" + \
                                 "tcpdump.x86_64                                            " + \
                                 "14:4.9.2-3.el7                          " + \
                                 "rhui-rhel-7-server-rhui-rpms\n"
                    elif cmd.find("assumeno selinux-policy") > -1:
                        code = 1
                        output = " Resolving Dependencies\n" + \
                                 " --> Running transaction check\n" + \
                                 " ---> Package selinux-policy.noarch 0:3.13.1-102.el7_3.15 " + \
                                 "will be updated\n" + \
                                 " --> Processing Dependency: selinux-policy = 3.13.1-102.el7_3.15 " + \
                                 "for package: selinux-policy-targeted-3.13.1-102.el7_3.15.noarch\n" + \
                                 " --> Processing Dependency: selinux-policy = 3.13.1-102.el7_3.15 " + \
                                 "for package: selinux-policy-targeted-3.13.1-102.el7_3.15.noarch\n" + \
                                 " ---> Package selinux-policy.noarch 0:3.13.1-102.el7_3.16 will be " + \
                                 "an update\n" + \
                                 " --> Running transaction check\n" + \
                                 " ---> Package selinux-policy-targeted.noarch 0:3.13.1-102.el7_3.15 " + \
                                 "will be updated\n" + \
                                 " ---> Package selinux-policy-targeted.noarch 0:3.13.1-102.el7_3.16 " + \
                                 "will be an update\n" + \
                                 " --> Finished Dependency Resolution\n"
                    elif cmd.find("sudo yum -y install sudo") > -1:
                        code = 0
                        output = "Loaded plugins: langpacks, product-id, search-disabled-repos\n" + \
                                 "Resolving Dependencies\n" + \
                                 "--> Running transaction check\n" + \
                                 "---> Package sudo.x86_64 0:1.8.6p7-21.el7_3 will be updated\n" + \
                                 "---> Package sudo.x86_64 0:1.8.6p7-22.el7_3 will be an update\n" + \
                                 "--> Finished Dependency Resolution\n\n\n" + \
                                 "Dependencies Resolved\n\n" + \
                                 "========================================================================================================================\n" + \
                                 " Package           Arch                Version                          Repository                                 Size\n" + \
                                 "========================================================================================================================\n" + \
                                 "Updating:\n" + \
                                 " sudo              x86_64              1.8.6p7-22.el7_3                 rhui-rhel-7-server-rhui-rpms              735 k\n" + \
                                 "Transaction Summary\n" + \
                                 "========================================================================================================================\n" + \
                                 "Upgrade  1 Package\n" + \
                                 "Total download size: 735 k\n" + \
                                 "Downloading packages:\n" + \
                                 "Delta RPMs disabled because /usr/bin/applydeltarpm not installed.\n" + \
                                 "sudo-1.8.6p7-22.el7_3.x86_64.rpm                                                                 | 735 kB  00:00:00\n" + \
                                 "Running transaction check\n" + \
                                 "Running transaction test\n" + \
                                 "Transaction test succeeded\n" + \
                                 "Running transaction\n" + \
                                 "  Updating   : sudo-1.8.6p7-22.el7_3.x86_64                                                                         1/2\n" + \
                                 "  Cleanup    : sudo-1.8.6p7-21.el7_3.x86_64                                                                         2/2\n" + \
                                 "  Verifying  : sudo-1.8.6p7-22.el7_3.x86_64                                                                         1/2\n" + \
                                 "  Verifying  : sudo-1.8.6p7-21.el7_3.x86_64                                                                         2/2\n" + \
                                 "Updated:\n" + \
                                 "  sudo.x86_64 0:1.8.6p7-22.el7_3\n" + \
                                 "Complete!\n"
                    elif cmd.find(" sudo yum install --assumeno kmod-kvdo") > -1:
                        code = 0
                        output = "Loaded plugins: langpacks, product-id, search-disabled-repos\n" + \
                                 "Resolving Dependencies\n" + \
                                 "--> Running transaction check\n" + \
                                 "---> Package kmod-kvdo.x86_64 0:6.1.0.153-15.el7 will be updated\n" + \
                                 "---> Package kmod-kvdo.x86_64 0:6.1.0.171-17.el7_5 will be an update\n" + \
                                 "--> Processing Dependency: kernel(dm_get_device) = 0x602cd186 for package: kmod-kvdo-6.1.0.171-17.el7_5.x86_64\n" + \
                                 "--> Processing Dependency: kernel(dm_put_device) = 0xe484e3b5 for package: kmod-kvdo-6.1.0.171-17.el7_5.x86_64\n" + \
                                 "--> Processing Dependency: kernel(dm_register_target) = 0xd3f9ecc7 for package: kmod-kvdo-6.1.0.171-17.el7_5.x86_64\n" + \
                                 "--> Processing Dependency: kernel(dm_unregister_target) = 0x35ba4186 for package: kmod-kvdo-6.1.0.171-17.el7_5.x86_64\n" + \
                                 "--> Running transaction check\n" + \
                                 "---> Package kernel.x86_64 0:3.10.0-862.9.1.el7 will be installed\n" + \
                                 "--> Finished Dependency Resolution\n" + \
                                 "\n" + \
                                 "Dependencies Resolved\n" + \
                                 "\n" + \
                                 "================================================================================\n" + \
                                 " Package     Arch     Version              Repository                      Size\n" + \
                                 "================================================================================\n" + \
                                 "Installing:\n" + \
                                 " kernel      x86_64   3.10.0-862.9.1.el7   rhui-rhel-7-server-rhui-rpms    46 M\n" + \
                                 "Updating:\n" + \
                                 " kmod-kvdo   x86_64   6.1.0.171-17.el7_5   rhui-rhel-7-server-rhui-rpms   348 k\n" + \
                                 "\n" + \
                                 "Transaction Summary\n" + \
                                 "================================================================================\n" + \
                                 "Install  1 Package\n" + \
                                 "Upgrade  1 Package\n" + \
                                 "\n" + \
                                 "Total download size: 46 M\n" + \
                                 "Exiting on user command\n"
                    elif cmd.find("yum list available kernel --showduplicates") > -1:
                        code = 0
                        output = "Loaded plugins: fastestmirror\n" + \
                                 "Loading mirror speeds from cached hostfile\n" + \
                                 "* base: mirrors.xtom.com\n" + \
                                 "* extras: mirrors.xtom.com\n" + \
                                 "* updates: mirrors.xtom.com\n" + \
                                 "Available Packages\n" + \
                                 "kernel.x86_64                                                                                    3.10.0-862.el7                                                                                         base\n" + \
                                 "kernel.x86_64                                                                                    3.10.0-862.2.3.el7                                                                                     updates\n" + \
                                 "kernel.x86_64                                                                                    3.10.0-862.3.2.el7                                                                                     updates\n" + \
                                 "kernel.x86_64                                                                                    3.10.0-862.3.3.el7                                                                                     updates\n" + \
                                 "kernel.x86_64                                                                                    3.10.0-862.6.3.el7                                                                                     updates\n" + \
                                 "kernel.x86_64                                                                                    3.10.0-862.9.1.el7                                                                                     updates\n" + \
                                 "kernel.x86_64                                                                                    3.10.0-862.11.6.el7                                                                                    updates"
                    elif cmd.find("list installed") > -1:
                        code = 0
                        package = cmd.replace('sudo yum list installed ', '')
                        whitelisted_versions = [
                            '3.13.1-102.el7_3.16', '4.8.5-28.el7', '2:1.26-34.el7', '14:4.9.2-3.el7']  # any list of versions you want to work for *any* package
                        output = "Loaded plugins: product-id, search-disabled-repos, subscription-manager\n" + \
                                 "Installed Packages\n"
                        template = "<PACKAGE>                                                                                     <VERSION>                                                                                      @anaconda/7.3\n"
                        for version in whitelisted_versions:
                            entry = template.replace('<PACKAGE>', package)
                            entry = entry.replace('<VERSION>', version)
                            output += entry
                    elif cmd.find("needs-restarting -r") > -1:
                        code = 0
                        output = "Core libraries or services have been updated:\n" + \
                                 "  kernel -> 3.10.0-957.1.3.el7\n" + \
                                 "  glibc -> 2.17-260.el7\n" + \
                                 "  dbus -> 1:1.10.24-12.el7\n" + \
                                 "  linux-firmware -> 20180911-69.git85c5d90.el7\n" + \
                                 "  openssl-libs -> 1:1.0.2k-16.el7\n" + \
                                 "  systemd -> 219-62.el7\n" + \
                                 "  gnutls -> 3.3.29-8.el7\n" + \
                                 "\n" + \
                                 "Reboot is required to ensure that your system benefits from these updates.\n" + \
                                 "\n" + \
                                 "More information:\n" + \
                                 "https://access.redhat.com/solutions/27943\n"
                    elif cmd.find("sudo yum ps") > -1:
                        code = 0
                        output = "Loaded plugins: langpacks, product-id, ps, search-disabled-repos\n" + \
                                 "pid proc                  CPU      RSS      State uptime\n" + \
                                 "1:NetworkManager-1.10.2-14.el7_5.x86_64\n" + \
                                 "5446 NetworkManager       0:00   8.0 MB   Sleeping: *16:40\n" + \
                                 "5642 dhclient             0:00    15 MB   Sleeping: *16:39\n" + \
                                 "1:dbus-1.10.24-7.el7.x86_64\n" + \
                                 "767 dbus-daemon          0:00   2.2 MB   Sleeping: *17:01\n" + \
                                 "12:dhclient-4.2.5-68.el7_5.1.x86_64\n" + \
                                 "5642 dhclient             0:00    15 MB   Sleeping: *16:39\n" + \
                                 "kernel-3.10.0-862.3.3.el7.x86_64\n" + \
                                 "0 <kernel>             0:00      0 B    Running: *17:18\n" + \
                                 "libstoragemgmt-1.6.1-2.el7.x86_64\n" + \
                                 "756 lsmd                 0:00   804 kB   Sleeping: *17:01\n" + \
                                 "openssh-server-7.4p1-16.el7.x86_64\n" + \
                                 "9770 sftp-server          0:00   2.1 MB   Sleeping: *14:36\n" + \
                                 "13721 sshd                 0:00   4.2 MB   Sleeping:  03:53\n" + \
                                 "systemd-219-57.el7.x86_64\n" + \
                                 "1 systemd              0:07   6.4 MB   Sleeping: *17:18\n" + \
                                 "605 systemd-journal      0:01   6.0 MB   Sleeping: *17:05\n" + \
                                 "791 systemd-logind       0:00   1.7 MB   Sleeping: *17:00\n" + \
                                 "10354 systemd-udevd        0:00   4.3 MB   Sleeping: *05:07\n" + \
                                 "util-linux-2.23.2-52.el7.x86_64\n" + \
                                 "803 agetty               0:00   848 kB   Sleeping: *17:00\n" + \
                                 "       804 agetty               0:00   868 kB   Sleeping: *17:00\n"
                    elif cmd.find("systemctl list-unit-files --type=service") > -1:
                        code = 0
                        output = 'Auto update service installed'
                    elif cmd.find("systemctl is-enabled ") > -1:
                        code = 0
                        output = 'enabled'
                    elif cmd.find("systemctl disable ") > -1:
                        code = 0
                        output = 'Auto update service disabled'
                elif self.legacy_package_manager_name is Constants.APT:
                    if cmd.find("dist-upgrade") > -1:
                        code = 0
                        output = "Inst python-samba [2:4.4.5+dfsg-2ubuntu5.2]" + \
                                 " (2:4.4.5+dfsg-2ubuntu5.4 " + \
                                 "Ubuntu:16.10/yakkety-updates, " + \
                                 "Ubuntu:16.10/yakkety-security [amd64]) []\n" + \
                                 "Inst samba-common-bin [2:4.4.5+dfsg-2ubuntu5.2] " + \
                                 "(2:4.4.5+dfsg-2ubuntu5.4 " + \
                                 "Ubuntu:16.10/yakkety-updates, " + \
                                 "Ubuntu:16.10/yakkety-security [amd64]) []\n" + \
                                 "Inst samba-libs [2:4.4.5+dfsg-2ubuntu5.2] (2:4.4.5+dfsg-2ubuntu5.4 " + \
                                 "Ubuntu:16.10/yakkety-updates, Ubuntu:16.10/yakkety-security [amd64]) []\n"
                    elif cmd.find("grep -hR security /etc/apt/sources.list") > -1 or cmd.find("grep -hR \"\" /etc/apt/sources.list") > -1:
                        code = 0
                        output = ("deb-src http://azure.archive.ubuntu.com/ubuntu/ jammy-security main restricted\n"
                                 "deb-src http://azure.archive.ubuntu.com/ubuntu/ jammy-security universe\n"
                                 "deb-src http://azure.archive.ubuntu.com/ubuntu/ jammy-security multiverse\n"
                                 "deb-src https://snapshot.ubuntu.com/ubuntu/20240301T000000Z jammy-security universe")
                        self.write_to_file(os.path.join(self.temp_folder_path, "temp2.list"), output)
                    elif cmd.find("--only-upgrade true -s install") > -1 or cmd.find("apt-get -y --only-upgrade true upgrade") > -1:
                        code = 0
                        output = "NOTE: This is only a simulation!\n" + \
                                 "      apt-get needs root privileges for real execution.\n" + \
                                 "      Keep also in mind that locking is deactivated,\n" + \
                                 "      so don't depend on the relevance " + \
                                 "to the real current situation!\n" + \
                                 "Reading package lists... Done\n" + \
                                 "Building dependency tree\n" + \
                                 "Reading state information... Done\n" + \
                                 "The following packages were automatically " + \
                                 "installed and are no longer required:\n" + \
                                 "  fgetty os-prober\n" + \
                                 "Use 'apt-get autoremove' to remove them.\n" + \
                                 "The following extra packages will be installed:\n" + \
                                 "  vim-common vim-runtime vim-tiny\n" + \
                                 "Suggested packages:\n" + \
                                 "  ctags vim-doc vim-scripts indent\n" + \
                                 "The following packages will be upgraded:\n" + \
                                 "  vim vim-common vim-runtime vim-tiny\n" + \
                                 "4 upgraded, 0 newly installed, 0 to remove and 92 not upgraded.\n" + \
                                 "Inst vim [2:7.4.052-1ubuntu3] (2:7.4.052-1ubuntu3.1 " + \
                                 "Ubuntu:14.04/trusty-updates [amd64]) []\n" + \
                                 "Inst vim-tiny [2:7.4.052-1ubuntu3] (2:7.4.052-1ubuntu3.1" + \
                                 " Ubuntu:14.04/trusty-updates [amd64]) []\n" + \
                                 "Inst vim-runtime [2:7.4.052-1ubuntu3] (2:7.4.052-1ubuntu3.1" + \
                                 " Ubuntu:14.04/trusty-updates [all]) []\n" + \
                                 "Inst vim-common [2:7.4.052-1ubuntu3] (2:7.4.052-1ubuntu3.1" + \
                                 " Ubuntu:14.04/trusty-updates [amd64])\n" + \
                                 "Conf vim-common (2:7.4.052    self.assertEqual(len(dependent_list), 16)-1ubuntu3.1" + \
                                 " Ubuntu:14.04/trusty-updates [amd64])\n" + \
                                 "Conf vim-runtime (2:7.4.052-1ubuntu3.1" + \
                                 " Ubuntu:14.04/trusty-updates [all])\n" + \
                                 "Conf vim (2:7.4.052-1ubuntu3.1 Ubuntu:14.04/trusty-updates [amd64])\n" + \
                                 "Conf vim-tiny (2:7.4.052-1ubuntu3.1" + \
                                 " Ubuntu:14.04/trusty-updates [amd64])\n"
                    elif cmd.find('apt-get -y --only-upgrade true install zlib1g') > -1:
                        code = 0
                        output = "Reading package lists...\n" + \
                                 "Building dependency tree...\n" + \
                                 "Reading state information...\n" + \
                                 "The following packages were automatically installed and are no longer required:\n" + \
                                 "  linux-headers-4.8.0-36 linux-headers-4.8.0-36-generic\n" + \
                                 "  linux-image-4.8.0-36-generic linux-image-extra-4.8.0-36-generic snap-confine\n" + \
                                 "Use 'sudo apt autoremove' to remove them.\n" + \
                                 "The following packages will be upgraded:\n" + \
                                 "  zlib1g\ndpkg-preconfigure: unable to re-open stdin: No such file or directory\n" + \
                                 "1 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\n" + \
                                 "Need to get 0 B/51.2 kB of archives.\n" + \
                                 "After this operation, 1,024 B disk space will be freed.\n" + \
                                 "(Reading database ... \r(Reading database ... 5%\r(Reading database ... 10%\r(Reading database ... 15%\r" + \
                                 "(Reading database ... 20%\r(Reading database ... 25%\r(Reading database ... 30%\r(Reading database ... 35%\r" + \
                                 "(Reading database ... 40%\r(Reading database ... 45%\r(Reading database ... 50%\r(Reading database ... 55%\r" + \
                                 "(Reading database ... 60%\r(Reading database ... 65%\r(Reading database ... 70%\r(Reading database ... 75%\r" + \
                                 "(Reading database ... 80%\r(Reading database ... 85%\r(Reading database ... 90%\r(Reading database ... 95%\r" + \
                                 "(Reading database ... 100%\r(Reading database ... 287938 files and directories currently installed.)\r\n" + \
                                 "Preparing to unpack .../zlib1g_1%3a1.2.8.dfsg-2ubuntu4.1_amd64.deb ...\r\n" + \
                                 "Unpacking zlib1g:amd64 (1:1.2.8.dfsg-2ubuntu4.1) over (1:1.2.8.dfsg-2ubuntu4) ...\r\n" + \
                                 "Processing triggers for libc-bin (2.23-0ubuntu7) ...\r\n" + \
                                 "Setting up zlib1g:amd64 (1:1.2.8.dfsg-2ubuntu4.1) ...\r\n" + \
                                 "Processing triggers for libc-bin (2.23-0ubuntu7) ...\r\n"
                    elif cmd.find('apt-cache madison bash') > -1:
                        code = 0
                        output = "      bash | 4.3-14ubuntu1.3 | http://us.archive.ubuntu.com/ubuntu xenial-updates/main amd64 Packages\n" + \
                                 "      bash | 4.3-14ubuntu1.2 | http://security.ubuntu.com/ubuntu xenial-security/main amd64 Packages\n" + \
                                 "      bash | 4.3-14ubuntu1 | http://us.archive.ubuntu.com/ubuntu xenial/main amd64 Packages"
                    elif cmd.find('sudo apt-get install ubuntu-advantage-tools -y') > -1:
                        code = 0
                    elif cmd.find('pro security-status --format=json') > -1:
                        code = 0
                        output = "{\"summary\":{\"ua\":{\"attached\":true}}}"
            elif self.legacy_test_type == 'SadPath':
                if cmd.find("cat /proc/cpuinfo | grep name") > -1:
                    code = 0
                    output = "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz"
                elif self.legacy_package_manager_name is Constants.APT:
                    if cmd.find('sudo apt-get install ubuntu-advantage-tools -y') > -1:
                        code = 1
                    elif cmd.find('pro security-status --format=json') > -1:
                        code = 0
                        output = "{\"summary\":{\"ua\":{\"attached\":false}}}"
                elif self.legacy_package_manager_name is Constants.YUM:
                    if cmd.find("microcode_ctl") > -1:
                        code = 1
                        output = "Loaded plugins: langpacks, product-id, search-disabled-repos" + \
                                 "No package microcode_ctl-2:2.1-29.16.el7_5 available." + \
                                 "Error: Nothing to do"
                    elif cmd.find("sudo yum ps") > -1:
                        code = 0
                        output = "Loaded plugins: enabled_repos_upload, package_upload, product-id, ps, search-\n" + \
                                 "              : disabled-repos, subscription-manager\n" + \
                                 "This system is not registered with an entitlement server. You can use subscription-manager to register.\n" + \
                                 "       pid proc                  CPU      RSS      State uptime\n" + \
                                 "ps\n" + \
                                 "Uploading Enabled Repositories Report\n" + \
                                 "Cannot upload enabled repos report, is this client registered?"
                    else:
                        code = 0
                        output = ''
                elif self.legacy_package_manager_name is Constants.ZYPPER:
                    output = ''
                    if cmd.find('ps --forest -o pid,cmd -g $(ps -o sid= -p') > -1:
                        output = 'test'
                        code = 1
                    elif cmd.find('sudo zypper refresh') > -1:
                        code = 7
                        output = 'System management is locked by the application with pid 7914 (/usr/bin/zypper).'
                    elif cmd.find('sudo LANG=en_US.UTF8 zypper --non-interactive patch --category security') > -1:
                        code = 103
                        output = ''
                elif cmd.find("systemctl") > -1:
                    code = 1
                    output = ''
            elif self.legacy_test_type == 'UnalignedPath':
                if cmd.find("cat /proc/cpuinfo | grep name") > -1:
                    code = 0
                    output = "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz"
                elif self.legacy_package_manager_name is Constants.APT:
                    code = 100
                    output = ''
                elif self.legacy_package_manager_name is Constants.YUM:
                    code = 100
                    output = 'NetworkManager-config-server.x86_64       1:1.4.0-20.el7_3     \n' + \
                             'rhui-rhel-7-server-rhui-rpms\n' + \
                             'device-mapper-event-libs.x86_64       7:1.02.135-1.el7_3.5\n' + \
                             ' rhui-rhel-7-server-rhui-rpms\n' + \
                             'python-rhsm-certificates.x86_64\n' + \
                             '1.17.10-1.el7_3      rhui-rhel-7-server-rhui-rpms\n' + \
                             'kernel.x86_64                                    3.10.0-693.1.1.el7                         rhui-rhel-7-server-rhui-rpms error-updating\n' + \
                             'kernel-tools.x86_64                              3.10.0-693.1.1.el7                         \n' + \
                             'error-updating rhui-rhel-7-server-rhui-rpms\n' + \
                             'kernel-tools-libs.x86_64                        3.10.0-693.1.1.el7                         rhui-rhel-7-server-rhui-rpms\n' + \
                             'Obsoleting Updates\n' + \
                             'nss-softokn-freebl.i686   3.28.3-8.el7_4  rhui-rhel-7-server-rhui-rpms\n' + \
                             'python-perf.x86_64                               3.10.0-693.1.1.el7                         rhui-rhel-7-server-rhui-rpms\n'
                elif self.legacy_package_manager_name is Constants.ZYPPER:
                    code = 100
                    output = ''
                    if cmd.find('ps --forest -o pid,cmd -g $(ps -o sid= -p') > -1:
                        output = ''
                        code = 0
                    elif cmd.find('sudo zypper refresh') > -1:
                        code = 4
                        output = 'System management is locked by the application with pid 7914 (/usr/bin/zypper).'
            elif self.legacy_test_type == 'NonexistentErrorCodePath':
                if self.legacy_package_manager_name is Constants.ZYPPER:
                    if cmd.find('sudo zypper refresh') > -1:
                        code = 999999
                        output = 'Unexpected return code (100) from package manager on command: LANG=en_US.UTF8 sudo apt-get -s dist-upgrade'
            elif self.legacy_test_type == 'AnotherSadPath':
                if self.legacy_package_manager_name is Constants.ZYPPER:
                    if cmd.find('sudo zypper refresh') > -1:
                        code = 6
                        output = 'Warning: There are no enabled repositories defined. | Use \'zypper addrepo\' or \'zypper modifyrepo\' commands to add or enable repositories.'
                    elif cmd.find('sudo zypper --non-interactive update samba-libs=4.15.4+git.327.37e0a40d45f-3.57.1') > -1:
                        code = 8
                        output = ''
                    elif cmd.find('sudo LANG=en_US.UTF8 zypper --non-interactive patch --category security') > -1:
                        code = 102
                        output = ''
            elif self.legacy_test_type == 'ExceptionPath':
                code = -1
                output = ''
            elif self.legacy_test_type == 'SuccessInstallPath':
                if cmd.find("cat /proc/cpuinfo | grep name") > -1:
                    code = 0
                    output = "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz"
                elif self.legacy_package_manager_name is Constants.YUM:
                    if cmd.find("check-update") > -1:
                        code = 100
                        output = "\n" + \
                                 "selinux-policy.noarch                                              " + \
                                 "3.13.1-102.el7_3.16                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n" + \
                                 "selinux-policy-targeted.noarch                                     " + \
                                 "3.13.1-102.el7_3.16                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n"
                    elif cmd.find("list installed") > -1:
                        code = 0
                        package = cmd.replace('sudo yum list installed ', '')
                        whitelisted_versions = [
                            '3.13.1-102.el7_3.16']  # any list of versions you want to work for *any* package
                        output = "Loaded plugins: product-id, search-disabled-repos, subscription-manager\n" + \
                                 "Installed Packages\n"
                        template = "<PACKAGE>                                                                                     <VERSION>                                                                                      @anaconda/7.3\n"
                        for version in whitelisted_versions:
                            entry = template.replace('<PACKAGE>', package)
                            entry = entry.replace('<VERSION>', version)
                            output += entry
                    elif cmd.find("simulate-install") > -1 or cmd.find(
                            "apt-get -y --only-upgrade true -s install") > -1 or cmd.find(
                        "LANG=en_US.UTF8 sudo yum install --assumeno") > -1 or cmd.find(
                        "sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run") > -1:
                        code = 0
                        output = "Package sucessfully installed!"
                elif self.legacy_package_manager_name is Constants.ZYPPER:
                    if cmd.find("list-updates") > -1:
                        code = 0
                        output = " Refreshing service 'cloud_update'.\n" + \
                                 " Loading repository data...\n" + \
                                 " Reading installed packages..\n" + \
                                 "S | Repository         | Name               | \
                        Current Version | Available Version | Arch\n" + \
                                 "--+--------------------+--------------------+--\
                        ---------------+-------------------+-------#\n" + \
                                 "v | SLES12-SP2-Updates | kernel-default     \
                        | 4.4.38-93.1     | 4.4.49-92.11.1    | x86_64\n" + \
                                 "v | SLES12-SP2-Updates | libgoa-1_0-0       \
                        | 3.20.4-7.2      | 3.20.5-9.6        | x86_64\n" + \
                                 "v | SLES12-SP2-Updates | libgoa-2_0-0       \
                        | 3.20.4-7.2      | 3.20.5-9.6       \n" + \
                                 "v | SLES12-SP2-Updates | libgoa-3_0-0       \n"
                    elif cmd.find("LANG=en_US.UTF8 zypper search -s") > -1: # acts as a catch all so it's more robust than it should be
                        code = 0
                        output = "Loading repository data...\n" + \
                                 "Reading installed packages...\n" + \
                                 "\n" + \
                                 "S  | Name                   | Type       | Version             | Arch   | Repository\n" + \
                                 "---+------------------------+------------+---------------------+--------+-------------------\n" + \
                                 " i | selinux-policy         | package    | 3.13.1-102.el7_3.16 | noarch | SLES12-SP2-Updates\n" + \
                                 " i | libgoa-1_0-0           | package    | 3.20.5-9.6               | noarch | SLES12-SP2-Updates\n" + \
                                 " i | kernel-default         | package    | 4.4.49-92.11.1      | noarch | SLES12-SP2-Updates\n"
                    elif cmd.find("simulate-install") > -1 or cmd.find(
                            "apt-get -y --only-upgrade true -s install") > -1 or cmd.find(
                        "LANG=en_US.UTF8 sudo yum install --assumeno") > -1 or cmd.find(
                        "sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run") > -1:
                        code = 0
                        output = "Package sucessfully installed!"
                elif self.legacy_package_manager_name is Constants.APT:
                    if cmd.find("dist-upgrade") > -1:
                        code = 0
                        output = "Inst python-samba [2:4.4.5+dfsg-2ubuntu5.2]" + \
                                 " (2:4.4.5+dfsg-2ubuntu5.4 " + \
                                 "Ubuntu:16.10/yakkety-updates, " + \
                                 "Ubuntu:16.10/yakkety-security [amd64]) []\n" + \
                                 "Inst samba-common-bin [2:4.4.5+dfsg-2ubuntu5.2] " + \
                                 "(2:4.4.5+dfsg-2ubuntu5.4 " + \
                                 "Ubuntu:16.10/yakkety-updates, " + \
                                 "Ubuntu:16.10/yakkety-security [amd64]) []\n" + \
                                 "Inst samba-libs [2:4.4.5+dfsg-2ubuntu5.2] (2:4.4.5+dfsg-2ubuntu5.4 " + \
                                 "Ubuntu:16.10/yakkety-updates, Ubuntu:16.10/yakkety-security [amd64]) []\n"
                    elif cmd.find("sudo dpkg -s mysql-server") > -1:
                        code = 0
                        output = "Package: mysql-server\n" + \
                                 "Status: install ok installed\n" + \
                                 "Priority: optional\n" + \
                                 "Section: database\n" + \
                                 "Installed-Size: 107\n" + \
                                 "Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>\n" + \
                                 "Architecture: all\n" + \
                                 "Source: mysql-5.7\n" + \
                                 "Version: 5.7.25-0ubuntu0.16.04.2\n" + \
                                 "Depends: mysql-server-5.7\n" + \
                                 "Description: MySQL database server (metapackage depending on the latest version)\n" + \
                                  "This is an empty package that depends on the current 'best' version of\n" + \
                                  "mysql-server (currently mysql-server-5.7), as determined by the MySQL\n" + \
                                  "maintainers. Install this package if in doubt about which MySQL\n" + \
                                  "version you need. That will install the version recommended by the\n" + \
                                  "package maintainers.\n" + \
                                  ".\n" + \
                                  "MySQL is a fast, stable and true multi-user, multi-threaded SQL database\n" + \
                                  "server. SQL (Structured Query Language) is the most popular database query\n" + \
                                  "language in the world. The main goals of MySQL are speed, robustness and\n" + \
                                  "ease of use.\n" + \
                                 "Homepage: http://dev.mysql.com/\n" + \
                                 "Original-Maintainer: Debian MySQL Maintainers <pkg-mysql-maint@lists.alioth.debian.org>"
                    elif cmd.find("sudo dpkg -s mysql-client") > -1:
                        code = 1
                        output = "dpkg-query: package 'mysql-client' is not installed and no information is available\n" + \
                                 "Use dpkg --info (= dpkg-deb --info) to examine archive files,\n" + \
                                 "and dpkg --contents (= dpkg-deb --contents) to list their contents."
                    elif cmd.find("sudo apt list --installed selinux-policy") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "selinux-policy.noarch/now 3.13.1-102.el7_3.16 amd64 [installed,upgradable to: 33.13.1-105.el7_3.17]"
                    elif cmd.find("sudo apt list --installed python-samba") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "python-samba/now 2:4.4.5+dfsg-2ubuntu5.4 amd64 [installed,upgradable to: 2:4.5.2+dfsg-2ubuntu5.4]"
                    elif cmd.find("sudo apt list --installed samba-common-bin") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "samba-common-bin/now 2:4.4.5+dfsg-2ubuntu5.4 amd64 [installed,upgradable to: 2:4.5.2+dfsg-2ubuntu5.4]"
                    elif cmd.find("sudo apt list --installed samba-libs") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "samba-libs/now 2:4.4.5+dfsg-2ubuntu5.4 amd64 [installed,upgradable to: 2:4.5.2+dfsg-2ubuntu5.4]"
                    elif cmd.find("simulate-install") > -1 or cmd.find(
                            "apt-get -y --only-upgrade true -s install") > -1 or cmd.find(
                        "LANG=en_US.UTF8 sudo yum install --assumeno") > -1 or cmd.find(
                        "sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run") > -1:
                        code = 0
                        output = "Package sucessfully installed!"
            elif self.legacy_test_type == 'FailInstallPath':
                if cmd.find("cat /proc/cpuinfo | grep name") > -1:
                    code = 0
                    output = "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz\n" + \
                             "model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz"
                elif self.legacy_package_manager_name is Constants.YUM:
                    if cmd.find("check-update") > -1:
                        code = 100
                        output = "\n" + \
                                 "selinux-policy.noarch                                              " + \
                                 "3.13.1-102.el7_3.16                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n" + \
                                 "selinux-policy-targeted.noarch                                     " + \
                                 "3.13.1-102.el7_3.16                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n"
                    elif cmd.find("rdma-7.3_4.7_rc2-6.el7_3.noarch") > -1:
                        code = 0
                        output = "Loaded plugins: product-id, search-disabled-repos, subscription-manager" + \
                                 "Package rdma-7.3_4.7_rc2-6.el7_3.noarch is obsoleted by rdma-core-17.2-3.el7.x86_64 which is already installed" + \
                                 "Nothing to do"
                    elif cmd.find("python-rhsm-1.19.10-1.el7_4.x86_64") > -1:
                        code = 0
                        output = "Loaded plugins: product-id, search-disabled-repos, subscription-manager\n" + \
                                 "Resolving Dependencies\n" + \
                                 "--> Running transaction check\n" + \
                                 "---> Package python-rhsm.x86_64 0:1.17.9-1.el7 will be obsoleted\n" + \
                                 "---> Package subscription-manager-rhsm.x86_64 0:1.21.10-3.el7_6 will be obsoleting\n" + \
                                 "--> Processing Dependency: subscription-manager-rhsm-certificates = 1.21.10-3.el7_6 for package: subscription-manager-rhsm-1.21.10-3.el7_6.x86_64\n" + \
                                 "--> Processing Dependency: python-six for package: subscription-manager-rhsm-1.21.10-3.el7_6.x86_64\n" + \
                                 "--> Running transaction check\n" + \
                                 "---> Package python-rhsm-certificates.x86_64 0:1.17.9-1.el7 will be obsoleted\n" + \
                                 "---> Package python-six.noarch 0:1.9.0-2.el7 will be installed\n" + \
                                 "---> Package subscription-manager-rhsm-certificates.x86_64 0:1.21.10-3.el7_6 will be obsoleting\n" + \
                                 "--> Finished Dependency Resolution\n" + \
                                 "\n" + \
                                 "Dependencies Resolved\n" + \
                                 "\n" + \
                                 "================================================================================\n" + \
                                 "Package                        Arch   Version         Repository          Size\n" + \
                                 "================================================================================\n" + \
                                 "Installing:\n" + \
                                 "subscription-manager-rhsm      x86_64 1.21.10-3.el7_6 rhel-7-server-rpms 297 k\n" + \
                                 "replacing  python-rhsm.x86_64 1.17.9-1.el7\n" + \
                                 "subscription-manager-rhsm-certificates\n" + \
                                 "x86_64 1.21.10-3.el7_6 rhel-7-server-rpms 212 k\n" + \
                                 "replacing  python-rhsm-certificates.x86_64 1.17.9-1.el7\n" + \
                                 "Installing for dependencies:\n" + \
                                 "python-six                     noarch 1.9.0-2.el7     rhel-7-server-rpms  29 k\n" + \
                                 "\n" + \
                                 "Transaction Summary\n" + \
                                 "================================================================================\n" + \
                                 "Install  2 Packages (+1 Dependent package)\n" + \
                                 "\n" + \
                                 "Total download size: 538 k\n" + \
                                 "Downloading packages:\n" + \
                                 "--------------------------------------------------------------------------------\n" + \
                                 "Total                                              523 kB/s | 538 kB  00:01     \n" + \
                                 "Running transaction check\n" + \
                                 "Running transaction test\n" + \
                                 "Transaction test succeeded\n" + \
                                 "Running transaction\n" + \
                                 "Installing : python-six-1.9.0-2.el7.noarch                                1/5 \n" + \
                                 "Installing : subscription-manager-rhsm-certificates-1.21.10-3.el7_6.x86   2/5 \n" + \
                                 "Installing : subscription-manager-rhsm-1.21.10-3.el7_6.x86_64             3/5 \n" + \
                                 "Erasing    : python-rhsm-1.17.9-1.el7.x86_64                              4/5 \n" + \
                                 "Erasing    : python-rhsm-certificates-1.17.9-1.el7.x86_64                 5/5 \n" + \
                                 "Verifying  : subscription-manager-rhsm-certificates-1.21.10-3.el7_6.x86   1/5 \n" + \
                                 "Verifying  : python-six-1.9.0-2.el7.noarch                                2/5 \n" + \
                                 "Verifying  : subscription-manager-rhsm-1.21.10-3.el7_6.x86_64             3/5 \n" + \
                                 "Verifying  : python-rhsm-1.17.9-1.el7.x86_64                              4/5 \n" + \
                                 "Verifying  : python-rhsm-certificates-1.17.9-1.el7.x86_64                 5/5 \n" + \
                                 "\n" + \
                                 "Installed:\n" + \
                                 "subscription-manager-rhsm.x86_64 0:1.21.10-3.el7_6                            \n" + \
                                 "subscription-manager-rhsm-certificates.x86_64 0:1.21.10-3.el7_6               \n" + \
                                 "\n" + \
                                 "Dependency Installed:\n" + \
                                 "python-six.noarch 0:1.9.0-2.el7                                               \n" + \
                                 "\n" + \
                                 "Replaced:\n" + \
                                 "python-rhsm.x86_64 0:1.17.9-1.el7                                             \n" + \
                                 "python-rhsm-certificates.x86_64 0:1.17.9-1.el7                                \n" + \
                                 "\n" + \
                                 "Complete!"
                    elif cmd.find("simulate-install") > -1 or cmd.find(
                            "apt-get -y --only-upgrade true -s install") > -1 or cmd.find(
                        "LANG=en_US.UTF8 sudo yum install --assumeno") > -1 or cmd.find(
                        "sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run") > -1:
                        code = 100
                        output = "Failed to install package"
                elif self.legacy_package_manager_name is Constants.ZYPPER:
                    if cmd.find("list-updates") > -1:
                        code = 0
                        output = " Refreshing service 'cloud_update'.\n" + \
                                 " Loading repository data...\n" + \
                                 " Reading installed packages..\n" + \
                                 "S | Repository         | Name               | \
                        Current Version | Available Version | Arch\n" + \
                                 "--+--------------------+--------------------+--\
                        ---------------+-------------------+-------#\n" + \
                                 "v | SLES12-SP2-Updates | kernel-default     \
                        | 4.4.38-93.1     | 4.4.49-92.11.1    | x86_64\n" + \
                                 "v | SLES12-SP2-Updates | libgoa-1_0-0       \
                        | 3.20.4-7.2      | 3.20.5-9.6        | x86_64\n" + \
                                 "v | SLES12-SP2-Updates | libgoa-2_0-0       \
                        | 3.20.4-7.2      | 3.20.5-9.6       \n" + \
                                 "v | SLES12-SP2-Updates | libgoa-3_0-0       \n"
                    elif cmd.find("zypper --non-interactive update --dry-run kernel-default") > -1 or \
                            cmd.find("zypper --non-interactive update --dry-run libgoa-1_0-0") > -1:
                        code = 0
                        output = ""  # irrelevant
                    elif cmd.find("simulate-install") > -1 or cmd.find(
                            "apt-get -y --only-upgrade true -s install") > -1 or cmd.find(
                        "LANG=en_US.UTF8 sudo yum install --assumeno") > -1 or cmd.find(
                        "sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run") > -1:
                        code = 100
                        output = "Failed to install package"
                elif self.legacy_package_manager_name is Constants.APT:
                    if cmd.find("dist-upgrade") > -1:
                        code = 0
                        output = "Inst python-samba [2:4.4.5+dfsg-2ubuntu5.2]" + \
                                 " (2:4.4.5+dfsg-2ubuntu5.4 " + \
                                 "Ubuntu:16.10/yakkety-updates, " + \
                                 "Ubuntu:16.10/yakkety-security [amd64]) []\n" + \
                                 "Inst samba-common-bin [2:4.4.5+dfsg-2ubuntu5.2] " + \
                                 "(2:4.4.5+dfsg-2ubuntu5.4 " + \
                                 "Ubuntu:16.10/yakkety-updates, " + \
                                 "Ubuntu:16.10/yakkety-security [amd64]) []\n" + \
                                 "Inst samba-libs [2:4.4.5+dfsg-2ubuntu5.2] (2:4.4.5+dfsg-2ubuntu5.4 " + \
                                 "Ubuntu:16.10/yakkety-updates, Ubuntu:16.10/yakkety-security [amd64]) []\n"
                    elif cmd.find("--only-upgrade") > -1 and cmd.find("iucode-tool=1.5.1-1ubuntu0.1") > -1:
                        code = 0
                        output = "Reading package lists...\n" + \
                                 "Building dependency tree...\n" + \
                                 "Reading state information...\n" + \
                                 "Skipping iucode-tool, it is not installed and only upgrades are requested.\n" + \
                                 "The following packages were automatically installed and are no longer required:\n" + \
                                 "  linux-headers-4.4.0-98 linux-headers-4.4.0-98-generic\n" + \
                                 "  linux-image-4.4.0-98-generic linux-image-extra-4.4.0-98-generic\n" + \
                                 "Use 'sudo apt autoremove' to remove them.\n" + \
                                 "0 upgraded, 0 newly installed, 0 to remove and 46 not upgraded."
                    elif cmd.find("simulate-install") > -1 or cmd.find(
                            "apt-get -y --only-upgrade true -s install") > -1 or cmd.find(
                        "LANG=en_US.UTF8 sudo yum install --assumeno") > -1 or cmd.find(
                        "sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run") > -1:
                        code = 100
                        output = "Failed to install package"
                    elif cmd.find("force-dpkg-failure") > -1:
                        code = 100
                        output = "E: dpkg was interrupted, you must manually run 'sudo dpkg --configure -a' to correct the problem."
            elif self.legacy_test_type == 'SSLCertificateIssueType1HappyPathAfterFix':
                if self.legacy_package_manager_name is Constants.YUM:
                    if cmd.find("yum update -y --disablerepo='*' --enablerepo='*microsoft*'") > -1:
                        code = 0
                        output = "Loaded plugins: langpacks, product-id, search-disabled-repos " \
                                 "Updated:" \
                                 "rhui-azure-rhel7.noarch 0:2.2-222" \
                                 "Complete!"
                        self.legacy_test_type = "HappyPath"
                    else:
                        code = 0
                        output = 'https://rhui-1.microsoft.com/pulp/repos//content/dist/rhel/rhui/server/7/7Server/x86_64/dotnet/1/os/repodata/repomd.xml: [Errno 14] curl#58 - "SSL peer rejected your certificate as expired."'
            elif self.legacy_test_type == 'SSLCertificateIssueType1SadPathAfterFix':
                if self.legacy_package_manager_name is Constants.YUM:
                    if cmd.find("yum update -y --disablerepo='*' --enablerepo='*microsoft*'") > -1:
                        code = 1
                        output = "Update not successful"
                    else:
                        code = 0
                        output = 'https://rhui-1.microsoft.com/pulp/repos//content/dist/rhel/rhui/server/7/7Server/x86_64/dotnet/1/os/repodata/repomd.xml: [Errno 14] curl#58 - "SSL peer rejected your certificate as expired."'
            elif self.legacy_test_type == 'SSLCertificateIssueType2HappyPathAfterFix':
                if self.legacy_package_manager_name is Constants.YUM:
                    if cmd.find("yum update -y --disablerepo='*' --enablerepo='*microsoft*'") > -1:
                        code = 0
                        output = "Loaded plugins: langpacks, product-id, search-disabled-repos " \
                                 "Updated:" \
                                 "rhui-azure-rhel7.noarch 0:2.2-222" \
                                 "Complete!"
                        self.legacy_test_type = "HappyPath"
                    else:
                        code = 0
                        output = "Error: Failed to download metadata for repo 'rhui-rhel-8-for-x86_64-baseos-rhui-rpms': Cannot download repomd.xml: Cannot download repodata/repomd.xml: All mirrors were tried"
            elif self.legacy_test_type == 'SSLCertificateIssueType2SadPathAfterFix':
                if self.legacy_package_manager_name is Constants.YUM:
                    if cmd.find("yum update -y --disablerepo='*' --enablerepo='*microsoft*'") > -1:
                        code = 1
                        output = "Update not successful"
                    else:
                        code = 0
                        output = "Error: Failed to download metadata for repo 'rhui-rhel-8-for-x86_64-baseos-rhui-rpms': Cannot download repomd.xml: Cannot download repodata/repomd.xml: All mirrors were tried"
            elif self.legacy_test_type == 'SSLCertificateIssueType3HappyPathAfterFix':
                if self.legacy_package_manager_name is Constants.YUM:
                    if cmd.find("yum update -y --disablerepo='*' --enablerepo='*microsoft*'") > -1:
                        code = 0
                        output = "Loaded plugins: langpacks, product-id, search-disabled-repos " \
                                 "Updated:" \
                                 "rhui-azure-rhel7.noarch 0:2.2-222" \
                                 "Complete!"
                        self.legacy_test_type = "HappyPath"
                    else:
                        code = 0
                        output = "Error: Cannot retrieve repository metadata (repomd.xml) for repository: addons. Please verify its path and try again"
            elif self.legacy_test_type == 'SSLCertificateIssueType3SadPathAfterFix':
                if self.legacy_package_manager_name is Constants.YUM:
                    if cmd.find("yum update -y --disablerepo='*' --enablerepo='*microsoft*'") > -1:
                        code = 1
                        output = "Update not successful"
                    else:
                        code = 0
                        output = "Error: Cannot retrieve repository metadata (repomd.xml) for repository: addons. Please verify its path and try again"
            elif self.legacy_test_type == 'DependencyInstallSuccessfully':
                if self.legacy_package_manager_name is Constants.APT:
                    # Total 7 packages: git-man, git, grub-efi-amd64-signed, testPkg1, testPkg2, testPkg3 and grub-efi-amd64-bin
                    # grub-efi-amd64-signed is dependent on grub-efi-amd64-bin
                    # All packages installs successfully
                    if cmd.find("dist-upgrade") > -1:
                        code = 0
                        output = "Inst git-man [1:2.17.1-1ubuntu0.15] (1:2.17.1-1ubuntu0.16 Ubuntu:18.04/bionic-updates, " \
                                 "Ubuntu:18.04/bionic-security [all])" \
                                 "Inst git [1:2.17.1-1ubuntu0.15] (1:2.17.1-1ubuntu0.16 Ubuntu:18.04/bionic-updates, " \
                                 "Ubuntu:18.04/bionic-security [amd64])" \
                                 "Inst grub-efi-amd64-signed [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst testPkg1 [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst testPkg2 [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst testPkg3 [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst grub-efi-amd64-bin [2.06-2ubuntu14] " \
                                 "(2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64])"
                    elif cmd.find("apt-get -y --only-upgrade true -s install git-man git grub-efi-amd64-signed testPkg1 testPkg2 testPkg3") > -1:
                        code = 0
                        output = "Inst git-man [1:2.17.1-1ubuntu0.15] (1:2.17.1-1ubuntu0.16 Ubuntu:18.04/bionic-updates, " \
                                 "Ubuntu:18.04/bionic-security [all])" \
                                 "Inst git [1:2.17.1-1ubuntu0.15] (1:2.17.1-1ubuntu0.16 Ubuntu:18.04/bionic-updates, " \
                                 "Ubuntu:18.04/bionic-security [amd64])" \
                                 "Inst grub-efi-amd64-signed [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst testPkg1 [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst testPkg2 [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst testPkg3 [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst grub-efi-amd64-bin [2.06-2ubuntu14] " \
                                 "(2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64])"
                    elif cmd.find("apt-get -y --only-upgrade true -s install grub-efi-amd64-signed") > -1:
                        code = 0
                        output = "Inst grub-efi-amd64-signed [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst grub-efi-amd64-bin [2.06-2ubuntu14] " \
                                 "(2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64])"
                    elif cmd.find("sudo apt list --installed git-man") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "git-man/bionic-updates,bionic-security,now 1:2.17.1-1ubuntu0.16 all [installed,automatic]"
                    elif cmd.find("sudo apt list --installed git") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "git/bionic-updates,bionic-security,now 1:2.17.1-1ubuntu0.16 amd64 [installed,automatic]"
                    elif cmd.find("sudo apt list --installed grub-efi-amd64-signed") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "grub-efi-amd64-signed/bionic-updates,now 1.187.3~18.04.1+2.06-2ubuntu14.1 amd64 [installed]"
                    elif cmd.find("sudo apt list --installed testPkg1") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "testPkg1/bionic-updates,now 1.187.3~18.04.1+2.06-2ubuntu14.1 amd64 [installed]"
                    elif cmd.find("sudo apt list --installed testPkg2") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "testPkg2/bionic-updates,now 1.187.3~18.04.1+2.06-2ubuntu14.1 amd64 [installed]"
                    elif cmd.find("sudo apt list --installed testPkg3") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "testPkg3/bionic-updates,now 1.187.3~18.04.1+2.06-2ubuntu14.1 amd64 [installed]"
                    elif cmd.find("sudo apt list --installed grub-efi-amd64-bin") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "grub-efi-amd64-bin/bionic-updates,now 2.06-2ubuntu14.1 amd64 [installed]"
                    elif cmd.find("simulate-install") > -1 or cmd.find(
                            "apt-get -y --only-upgrade true -s install") > -1 or cmd.find(
                        "LANG=en_US.UTF8 sudo yum install --assumeno") > -1 or cmd.find(
                        "sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run") > -1:
                        code = 0
                        output = "Package sucessfully installed!"
            elif self.legacy_test_type == 'DependencyInstallFailed':
                if self.legacy_package_manager_name is Constants.APT:
                    # Total 7 packages: git-man, git, grub-efi-amd64-signed, testPkg1, testPkg2, testPkg3 and grub-efi-amd64-bin
                    # grub-efi-amd64-signed is dependent on grub-efi-amd64-bin
                    # Installation of grub-efi-amd64-bin fails and as grub-efi-amd64-signed is dependent, it also failed 
                    # Rest all packages install successfully
                    if cmd.find("dist-upgrade") > -1:
                        code = 0
                        output = "Inst git-man [1:2.17.1-1ubuntu0.15] (1:2.17.1-1ubuntu0.16 Ubuntu:18.04/bionic-updates, " \
                                 "Ubuntu:18.04/bionic-security [all])" \
                                 "Inst git [1:2.17.1-1ubuntu0.15] (1:2.17.1-1ubuntu0.16 Ubuntu:18.04/bionic-updates, " \
                                 "Ubuntu:18.04/bionic-security [amd64])" \
                                 "Inst grub-efi-amd64-signed [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst testPkg1 [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst testPkg2 [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst testPkg3 [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst grub-efi-amd64-bin [2.06-2ubuntu14] " \
                                 "(2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64])"
                    elif cmd.find("apt-get -y --only-upgrade true -s install git-man git grub-efi-amd64-signed") > -1:
                        code = 0
                        output = "Inst git-man [1:2.17.1-1ubuntu0.15] (1:2.17.1-1ubuntu0.16 Ubuntu:18.04/bionic-updates, " \
                                 "Ubuntu:18.04/bionic-security [all])" \
                                 "Inst git [1:2.17.1-1ubuntu0.15] (1:2.17.1-1ubuntu0.16 Ubuntu:18.04/bionic-updates, " \
                                 "Ubuntu:18.04/bionic-security [amd64])" \
                                 "Inst grub-efi-amd64-signed [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst grub-efi-amd64-bin [2.06-2ubuntu14] " \
                                 "(2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64])"
                    elif cmd.find("apt-get -y --only-upgrade true -s install grub-efi-amd64-signed") > -1:
                        code = 0
                        output = "Inst grub-efi-amd64-signed [1.187.2~18.04.1+2.06-2ubuntu14] " \
                                 "(1.187.3~18.04.1+2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64]) []" \
                                 "Inst grub-efi-amd64-bin [2.06-2ubuntu14] " \
                                 "(2.06-2ubuntu14.1 Ubuntu:18.04/bionic-updates [amd64])"
                    elif cmd.find("sudo apt list --installed git-man") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "git-man/bionic-updates,bionic-security,now 1:2.17.1-1ubuntu0.16 all [installed,automatic]"
                    elif cmd.find("sudo apt list --installed git") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "git/bionic-updates,bionic-security,now 1:2.17.1-1ubuntu0.16 amd64 [installed,automatic]"
                    elif cmd.find("sudo apt list --installed grub-efi-amd64-signed") > -1:
                        code = 0
                        output = "Listing... Done\n"
                    elif cmd.find("sudo apt list --installed testPkg1") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "testPkg1/bionic-updates,now 1.187.3~18.04.1+2.06-2ubuntu14.1 amd64 [installed]"
                    elif cmd.find("sudo apt list --installed testPkg2") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "testPkg2/bionic-updates,now 1.187.3~18.04.1+2.06-2ubuntu14.1 amd64 [installed]"
                    elif cmd.find("sudo apt list --installed testPkg3") > -1:
                        code = 0
                        output = "Listing... Done\n" + \
                                 "testPkg3/bionic-updates,now 1.187.3~18.04.1+2.06-2ubuntu14.1 amd64 [installed]"
                    elif cmd.find("sudo apt list --installed grub-efi-amd64-bin") > -1:
                        code = 0
                        output = "Listing... Done\n"
                    elif cmd.find("simulate-install") > -1 or cmd.find(
                            "apt-get -y --only-upgrade true -s install") > -1 or cmd.find(
                        "LANG=en_US.UTF8 sudo yum install --assumeno") > -1 or cmd.find(
                        "sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run") > -1:
                        code = 0
                        output = "Package sucessfully installed!"
            elif self.legacy_test_type == 'UA_ESM_Required':
                if self.legacy_package_manager_name is Constants.APT:
                    if cmd.find("dist-upgrade") > -1:
                        code = 0
                        output = "Inst cups [1:2.17.1-1ubuntu0.15] (UA_ESM_Required Ubuntu:18.04/bionic-updates, " \
                                 "Ubuntu:18.04/bionic-updates [all])"
                    elif cmd.find("sudo dpkg -s python3") > -1:
                        code = 0
                        output = "Package: python3\n" + \
                                 "Status: install ok installed\n" + \
                                 "Priority: optional\n" + \
                                 "Section: database\n" + \
                                 "Installed-Size: 107\n" + \
                                 "Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>\n" + \
                                 "Architecture: all\n" + \
                                 "Source: python3\n" + \
                                 "Version: 1:2.17.1-1ubuntu0.16\n" + \
                                 "Description: " + \
                                  "Homepage: http://dev.python3.com/\n"
                    elif cmd.find("sudo dpkg -s apt") > -1:
                        code = 0
                        output = "Package: apt\n" + \
                                 "Status: install ok installed\n" + \
                                 "Priority: optional\n" + \
                                 "Section: database\n" + \
                                 "Installed-Size: 107\n" + \
                                 "Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>\n" + \
                                 "Architecture: all\n" + \
                                 "Source: apt\n" + \
                                 "Version: 2.06-2ubuntu14.1\n" + \
                                 "Description: " + \
                                  "Homepage: http://dev.apt.com/\n"
            elif self.legacy_test_type == 'ArchDependency':
                if self.legacy_package_manager_name is Constants.YUM:
                    if cmd.find("check-update") > -1:
                        code = 100
                        output = "\n" + \
                                 "selinux-policy.noarch                                              " + \
                                 "3.13.1-102.el7_3.16                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n" + \
                                 "selinux-policy-targeted.noarch                                     " + \
                                 "3.13.1-102.el7_3.16                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n" + \
                                 "libgcc.i686                                      " + \
                                 "4.8.5-28.el7                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n" + \
                                 "testPkg1.i686                                      " + \
                                 "4.8.5-28.el7                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n" + \
                                 "testPkg2.i686                                      " + \
                                 "4.8.5-28.el7                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n" + \
                                 "testPkg3.i686                                      " + \
                                 "4.8.5-28.el7                                      " + \
                                 "rhui-rhel-7-server-rhui-rpms\n" + \
                                 "libgcc.x86_64                                                " + \
                                 "4.8.5-28.el7                           " + \
                                 "rhui-rhel-7-server-rhui-rpms\n"
                    elif cmd.find("list installed") > -1:
                        code = 0
                        package = cmd.replace('sudo yum list installed ', '')
                        whitelisted_versions = [
                            '3.13.1-102.el7_3.16', '4.8.5-28.el7']  # any list of versions you want to work for *any* package
                        output = "Loaded plugins: product-id, search-disabled-repos, subscription-manager\n" + \
                                 "Installed Packages\n"
                        template = "<PACKAGE>                                                                                     <VERSION>                                                                                      @anaconda/7.3\n"
                        for version in whitelisted_versions:
                            entry = template.replace('<PACKAGE>', package)
                            entry = entry.replace('<VERSION>', version)
                            output += entry
            elif self.legacy_test_type == 'ObsoletePackages':
                if self.legacy_package_manager_name is Constants.YUM:
                    if cmd.find("check-update") > -1:
                        code = 100
                        output = "\n" + \
                                 "grub2-tools.x86_64                                              " + \
                                 "1:2.02-142.el8                                      " + \
                                 "rhel-8-baseos-rhui-rpms\n" + \
                                 "Obsoleting Packages\n" + \
                                 "grub2-tools.x86_64                                     " + \
                                 "1:2.02-123.el8_6.8                                      " + \
                                 "rhel-8-baseos-rhui-rpms\n" + \
                                 "    grub2-tools.x86_64                                      " + \
                                 "1:2.02-123.el8                                      " + \
                                 "@System\n"

            major_version = self.get_python_major_version()
            if major_version == 2:
                return code, output.decode('utf8', 'ignore').encode('ascii', 'ignore')
            elif major_version == 3:
                return code, output.encode('ascii', 'ignore').decode('ascii', 'ignore')
            else:
                raise Exception("Unknown version of python encountered.")

    @staticmethod
    def write_to_file(path, data):
        with open(path, "w+") as file_handle:
            file_handle.write(data)
