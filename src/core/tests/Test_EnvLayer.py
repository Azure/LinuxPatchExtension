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
import os
import platform
import sys
import unittest
# Conditional import for StringIO
try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import StringIO  # Python 3

from core.src.bootstrap.EnvLayer import EnvLayer
from core.src.bootstrap.Constants import Constants
from core.src.external_dependencies import distro


class TestExecutionConfig(unittest.TestCase):
    def setUp(self):
        self.envlayer = EnvLayer()

    def tearDown(self):
        pass

    # region setup mocks
    def mock_platform_system(self):
        return 'Linux'

    def mock_platform_system_windows(self):
        return 'Windows'

    def mock_linux_distribution(self):
        return ['test', 'test', 'test']

    def mock_linux_distribution_to_return_azure_linux_4(self):
        return ['Microsoft Azure Linux', '4.0', '']

    def mock_linux_distribution_to_return_azure_linux_3(self):
        return ['Microsoft Azure Linux', '3.0', '']

    def mock_linux_distribution_to_return_azure_linux_2(self):
        return ['Common Base Linux Mariner', '2.0', '']

    def mock_run_command_for_apt(self, cmd, no_output=False, chk_err=False):
        if cmd.find("which apt-get") > -1:
            return 0, ''
        return -1, ''

    def mock_run_command_for_yum(self, cmd, no_output=False, chk_err=False):
        if cmd.find("which yum") > -1:
            return 0, ''
        return -1, ''

    def mock_run_command_for_zypper(self, cmd, no_output=False, chk_err=False):
        if cmd.find("which zypper") > -1:
            return 0, ''
        return -1, ''

    def mock_run_command_for_tdnf(self, cmd, no_output=False, chk_err=False):
        if cmd.find("which tdnf") > -1:
            return 0, ''
        return -1, ''

    def mock_run_command_for_dnf5(self, cmd, no_output=False, chk_err=False):
        if "which dnf" in cmd:
            return 0, '/usr/bin/dnf'
        if "dnf --version" in cmd:
            return 0, 'dnf5 version 5.2.18.0'
        return -1, ''

    def mock_run_command_for_dnf_not_found(self, cmd, no_output=False, chk_err=False):
        return -1, ''

    def mock_run_command_for_dnf_wrong_version(self, cmd, no_output=False, chk_err=False):
        if "which dnf" in cmd:
            return 0, '/usr/bin/dnf'
        if "dnf --version" in cmd:
            return 0, 'dnf version 4.14.0'
        return -1, ''

    def mock_run_command_for_dnf_version_command_failure(self, cmd, no_output=False, chk_err=False):
        if "which dnf" in cmd:
            return 0, '/usr/bin/dnf'
        if "dnf --version" in cmd:
            return -1, 'dnf version command failure'
        return -1, ''

    def mock_distro_os_release_attr_return_azure_linux_4(self, attribute):
        return '4.0.0'

    def mock_distro_os_release_attr_return_azure_linux_3(self, attribute):
        return '3.0.0'

    def mock_distro_os_release_attr_return_azure_linux_2(self, attribute):
        return '2.9.0'

    def mock_distro_os_release_attr_return_none(self, attribute):
        return None

    def mock_linux_distribution_to_return_rhel_10(self):
        return ['Red Hat', '10.0', 'abc']

    def mock_distro_os_release_attr_return_rhel_10(self, attribute):
        return '10.0'

    def mock_run_command_output_fde_true(self, cmd, no_output=False, chk_err=False):
        return 0, 'test-vm,/dev/sda1,FDE=true,LUKS:/dev/sda1'

    def mock_run_command_output_fde_false(self, cmd, no_output=False, chk_err=False):
        return 0, 'test-vm,/dev/sda1,FDE=false,LUKS:/dev/sda1'

    def mock_run_command_output_imds_true(self, cmd, no_output=False, chk_err=False):
        return 0, '"securityProfile": { "encryptionAtHost": "false", "secureBootEnabled": "false", "securityType": "ConfidentialVM", "virtualTpmEnabled": "false"}'

    def mock_run_command_output_imds_false(self, cmd, no_output=False, chk_err=False):
        return 0, '{"compute":{"securityProfile":{"securityType":""}}}'

    def mock_detect_confidential_vm_by_fde_returns_true(self):
        return True, 'test-vm,/dev/sda1,FDE=true,LUKS:/dev/sda1'

    def mock_detect_confidential_vm_by_fde_returns_false(self):
        return False, str()

    def mock_detect_confidential_vm_by_imds_returns_true(self):
        return True, 'IMDS:ConfidentialVM'

    def mock_detect_confidential_vm_by_imds_returns_false(self):
        return False, str()

    def mock_file_system_read_with_retry_returns_empty(self, file_path_or_handle, raise_if_not_found=True):
        return str()

    def mock_os_path_isfile_returns_false(self, path):
        return False
    # endregion

    def test_get_package_manager(self):
        self.backup_platform_system = platform.system
        platform.system = self.mock_platform_system
        self.backup_linux_distribution = self.envlayer.platform.linux_distribution
        self.envlayer.platform.linux_distribution = self.mock_linux_distribution
        self.backup_run_command_output = self.envlayer.run_command_output
        self.backup_distro_os_release_attr = distro.os_release_attr

        test_input_output_table = [
            [self.mock_run_command_for_apt, self.mock_linux_distribution, Constants.APT, self.mock_distro_os_release_attr_return_none],
            [self.mock_run_command_for_dnf5, self.mock_linux_distribution_to_return_azure_linux_4, Constants.DNF5, self.mock_distro_os_release_attr_return_azure_linux_4],
            [self.mock_run_command_for_tdnf, self.mock_linux_distribution_to_return_azure_linux_3, Constants.TDNF, self.mock_distro_os_release_attr_return_azure_linux_3],
            [self.mock_run_command_for_yum, self.mock_linux_distribution_to_return_azure_linux_3, str(), self.mock_distro_os_release_attr_return_none],  # check for Azure Linux machine which does not have tdnf
            [self.mock_run_command_for_tdnf, self.mock_linux_distribution_to_return_azure_linux_2, Constants.TDNF, self.mock_distro_os_release_attr_return_azure_linux_2],
            [self.mock_run_command_for_yum, self.mock_linux_distribution, Constants.YUM, self.mock_distro_os_release_attr_return_none],
            [self.mock_run_command_for_zypper, self.mock_linux_distribution, Constants.ZYPPER, self.mock_distro_os_release_attr_return_none],
            [lambda cmd, no_output, chk_err: (-1, ''), self.mock_linux_distribution, str(), self.mock_distro_os_release_attr_return_none],    # no matches for any package manager
        ]

        for row in test_input_output_table:
            self.envlayer.run_command_output = row[0]
            self.envlayer.platform.linux_distribution = row[1]
            distro.os_release_attr = row[3]
            package_manager = self.envlayer.get_package_manager()
            self.assertEqual(package_manager, row[2])

        # test for Windows
        platform.system = self.mock_platform_system_windows
        self.assertEqual(self.envlayer.get_package_manager(), Constants.APT)

        # restore original methods
        self.envlayer.run_command_output = self.backup_run_command_output
        self.envlayer.platform.linux_distribution = self.backup_linux_distribution
        distro.os_release_attr = self.backup_distro_os_release_attr
        platform.system = self.backup_platform_system

    def test_is_distro_azure_linux_3(self):
        self.backup_envlayer_distro_os_release_attr = distro.os_release_attr

        test_input_output_table = [
            [self.mock_linux_distribution_to_return_azure_linux_3, self.mock_distro_os_release_attr_return_azure_linux_3, True],
            [self.mock_linux_distribution_to_return_azure_linux_2, self.mock_distro_os_release_attr_return_azure_linux_2, False],
            [self.mock_linux_distribution_to_return_azure_linux_3, self.mock_distro_os_release_attr_return_none, False]
        ]

        for row in test_input_output_table:
            distro_name = row[0]()[0]  # Extract distro name from tuple (first element)
            distro.os_release_attr = row[1]
            result = self.envlayer.is_distro_azure_linux_3(distro_name)
            self.assertEqual(result, row[2])

        # restore original methods
        distro.os_release_attr = self.backup_envlayer_distro_os_release_attr

    def test_is_distro_azure_linux_4(self):
        self.backup_envlayer_distro_os_release_attr = distro.os_release_attr

        test_input_output_table = [
            [self.mock_linux_distribution_to_return_azure_linux_4, self.mock_distro_os_release_attr_return_azure_linux_4, True],
            [self.mock_linux_distribution_to_return_azure_linux_4, self.mock_distro_os_release_attr_return_none, False],
        ]

        for row in test_input_output_table:
            distro_name = row[0]()[0]  # Extract distro name from tuple (first element)
            distro.os_release_attr = row[1]
            result = self.envlayer.is_distro_azure_linux_4(distro_name)
            self.assertEqual(result, row[2])

        # restore original methods
        distro.os_release_attr = self.backup_envlayer_distro_os_release_attr

    def test_get_package_manager_dnf5_error_cases(self):
        """Test dnf5 error cases in get_package_manager"""
        self.backup_platform_system = platform.system
        self.backup_linux_distribution = self.envlayer.platform.linux_distribution
        self.backup_run_command_output = self.envlayer.run_command_output
        self.backup_distro_os_release_attr = distro.os_release_attr

        platform.system = self.mock_platform_system
        self.envlayer.platform.linux_distribution = self.mock_linux_distribution_to_return_azure_linux_4
        distro.os_release_attr = self.mock_distro_os_release_attr_return_azure_linux_4

        test_input_output_table = [
            [self.mock_run_command_for_dnf_not_found, str()],
            [self.mock_run_command_for_dnf_wrong_version, str()],
            [self.mock_run_command_for_dnf_version_command_failure, str()]
        ]
          
        for row in test_input_output_table:
            self.envlayer.run_command_output = row[0]
            result = self.envlayer.get_package_manager()
            self.assertEqual(result, row[1])

        # restore original methods
        self.envlayer.run_command_output = self.backup_run_command_output
        self.envlayer.platform.linux_distribution = self.backup_linux_distribution
        distro.os_release_attr = self.backup_distro_os_release_attr
        platform.system = self.backup_platform_system
         
    def test_detect_confidential_vm_by_fde(self):
        backup_run_command_output = self.envlayer.run_command_output
        backup_read_with_retry = self.envlayer.file_system.read_with_retry
        backup_os_path_isfile = os.path.isfile

        test_input_output_table = [
            [self.mock_run_command_output_fde_true, backup_os_path_isfile, backup_read_with_retry, False, True, 'FDE=true'],
            [self.mock_run_command_output_fde_false, backup_os_path_isfile, backup_read_with_retry, False, False, str()],
            [self.mock_run_command_output_fde_true, backup_os_path_isfile, self.mock_file_system_read_with_retry_returns_empty, True, False, str()],
            [self.mock_run_command_output_fde_true, self.mock_os_path_isfile_returns_false, backup_read_with_retry, True, False, str()],
        ]

        for row in test_input_output_table:
            self.envlayer.run_command_output = row[0]
            os.path.isfile = row[1]
            self.envlayer.file_system.read_with_retry = row[2]
            expected_raises_exception = row[3]
            expected_is_confidential_vm = row[4]
            expected_detection_details = row[5]

            if expected_raises_exception:
                self.assertRaises(Exception, self.envlayer.detect_confidential_vm_by_fde)
            else:
                is_confidential_vm, detection_details = self.envlayer.detect_confidential_vm_by_fde()
                self.assertEqual(is_confidential_vm, expected_is_confidential_vm)
                self.assertIn(expected_detection_details, detection_details)

        self.envlayer.run_command_output = backup_run_command_output
        self.envlayer.file_system.read_with_retry = backup_read_with_retry
        os.path.isfile = backup_os_path_isfile

    def test_detect_confidential_vm_by_imds(self):
        backup_run_command_output = self.envlayer.run_command_output

        test_input_output_table = [
            [self.mock_run_command_output_imds_true, True, 'IMDS:ConfidentialVM'],
            [self.mock_run_command_output_imds_false, False, str()],
        ]

        for row in test_input_output_table:
            self.envlayer.run_command_output = row[0]
            is_confidential_vm, detection_details = self.envlayer.detect_confidential_vm_by_imds()
            self.assertEqual(is_confidential_vm, row[1])
            self.assertIn(row[2], detection_details)

        self.envlayer.run_command_output = backup_run_command_output

    def test_detect_confidential_vm(self):
        self.backup_platform_system = platform.system

        backup_detect_confidential_vm_by_fde = self.envlayer.detect_confidential_vm_by_fde
        backup_detect_confidential_vm_by_imds = self.envlayer.detect_confidential_vm_by_imds

        test_input_output_table = [
            ["Linux", self.mock_detect_confidential_vm_by_fde_returns_true, self.mock_detect_confidential_vm_by_imds_returns_true, True, 'IMDS:ConfidentialVM'],
            ["Linux", self.mock_detect_confidential_vm_by_fde_returns_true, self.mock_detect_confidential_vm_by_imds_returns_false, True, 'FDE=true'],
            ["Windows", self.mock_run_command_output_fde_true, self.mock_run_command_output_imds_true, False, str()],
            ["Linux", self.mock_detect_confidential_vm_by_fde_returns_false, self.mock_detect_confidential_vm_by_imds_returns_false, False, str()],
        ]

        for row in test_input_output_table:
            platform.system = self.mock_platform_system if row[0] == 'Linux' else self.mock_platform_system_windows
            self.envlayer.detect_confidential_vm_by_fde = row[1]
            self.envlayer.detect_confidential_vm_by_imds = row[2]
            is_confidential_vm, detection_details = self.envlayer.detect_confidential_vm()
            self.assertEqual(is_confidential_vm, row[3])
            self.assertIn(row[4], detection_details)

        # restore original methods
        platform.system = self.backup_platform_system
        self.envlayer.detect_confidential_vm_by_fde = backup_detect_confidential_vm_by_fde
        self.envlayer.detect_confidential_vm_by_imds = backup_detect_confidential_vm_by_imds

    def test_filesystem(self):
        # only validates if these invocable without exceptions
        backup_retry_count = Constants.MAX_FILE_OPERATION_RETRY_COUNT
        Constants.MAX_FILE_OPERATION_RETRY_COUNT = 2
        self.envlayer.file_system.read_with_retry("fake.path", raise_if_not_found=False)
        Constants.MAX_FILE_OPERATION_RETRY_COUNT = backup_retry_count

    def test_platform(self):
        # only validates if these invocable without exceptions
        self.envlayer.platform.linux_distribution()
        self.envlayer.platform.os_type()
        self.envlayer.platform.cpu_arch()
        self.envlayer.platform.vm_name()

    def test_get_package_manager_rhel10_not_supported(self):
        """Test for RHEL 10 log unsupported message"""
        self.backup_platform_system = platform.system
        self.backup_linux_distribution = self.envlayer.platform.linux_distribution
        self.backup_distro_os_release_attr = distro.os_release_attr

        platform.system = self.mock_platform_system
        test_input_output_table = [
            [self.mock_linux_distribution_to_return_rhel_10, self.mock_distro_os_release_attr_return_rhel_10, "Error: This distro is not yet supported in your region. Please review https://aka.ms/VMGuestPatchingCompatibility for more information. [Distro=Red Hat][Version=10.0][Code=abc]\n"],
        ]
        for row in test_input_output_table:
            captured_output = StringIO()
            original_output = sys.stdout
            sys.stdout = captured_output
            self.envlayer.platform.linux_distribution = row[0]
            distro.os_release_attr = row[1]

            result = self.envlayer.get_package_manager()
            sys.stdout = original_output
            self.assertEqual(row[2], captured_output.getvalue())
            self.assertEqual(result, "")

        # restore
        self.__restore_mocks()

    def test_mock_command_fallback_paths(self):
        """Test that mock commands return -1 for unexpected commands"""
        code, out = self.mock_run_command_for_apt('which apt')
        self.assertEqual(code, -1)

        code, out = self.mock_run_command_for_dnf5('which not-dnf')
        self.assertEqual(code, -1)

        code, out = self.mock_run_command_for_dnf_wrong_version('dnf --v')
        self.assertEqual(code, -1)

        code, out = self.mock_run_command_for_dnf_version_command_failure('dnf --v')
        self.assertEqual(code, -1)

        code, out = self.mock_run_command_for_tdnf('which not-tdnf')
        self.assertEqual(code, -1)

    def __restore_mocks(self):
        """Restore backed up mocks to their original state"""
        distro.os_release_attr = self.backup_distro_os_release_attr
        self.envlayer.platform.linux_distribution = self.backup_linux_distribution
        platform.system = self.backup_platform_system

if __name__ == '__main__':
    unittest.main()