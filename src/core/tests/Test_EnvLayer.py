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
import platform
import unittest
from core.src.bootstrap.EnvLayer import EnvLayer
from core.src.bootstrap.Constants import Constants


class TestExecutionConfig(unittest.TestCase):
    def setUp(self):
        self.envlayer = EnvLayer()

    def tearDown(self):
        pass

    # region setup mocks
    def mock_platform_system(self):
        return 'Linux'

    def mock_linux_distribution(self):
        return ['test', 'test', 'test']

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
    # endregion

    def test_get_package_manager(self):
        self.backup_platform_system = platform.system()
        platform.system = self.mock_platform_system
        self.backup_linux_distribution = self.envlayer.platform.linux_distribution
        self.envlayer.platform.linux_distribution = self.mock_linux_distribution
        self.backup_run_command_output = self.envlayer.run_command_output

        test_input_output_table = [
            [self.mock_run_command_for_apt, self.mock_linux_distribution, Constants.APT],
            [self.mock_run_command_for_tdnf, self.mock_linux_distribution_to_return_azure_linux_3, Constants.TDNF],
            [self.mock_run_command_for_yum, self.mock_linux_distribution_to_return_azure_linux_3, None],  # check for Azure Linux machine which does not have tdnf
            [self.mock_run_command_for_tdnf, self.mock_linux_distribution_to_return_azure_linux_2, Constants.TDNF],
            [self.mock_run_command_for_yum, self.mock_linux_distribution, Constants.YUM],
            [self.mock_run_command_for_zypper, self.mock_linux_distribution, Constants.ZYPPER],
        ]

        for row in test_input_output_table:
            self.envlayer.run_command_output = row[0]
            self.envlayer.platform.linux_distribution = row[1]
            package_manager = self.envlayer.get_package_manager()
            self.assertTrue(package_manager is row[2])

        self.envlayer.run_command_output = self.backup_run_command_output
        self.envlayer.platform.linux_distribution = self.backup_linux_distribution
        platform.system = self.backup_platform_system
        
    def test_extract_linux_distribution_os_info_with_data(self):
        """ Test linux_distribution_images_details returning tuples of os info. """
        # set up mocks
        self.backup_platform_system = platform.system()
        platform.system = self.mock_platform_system
        self.backup_linux_distribution = self.envlayer.platform.linux_distribution
        self.envlayer.platform.linux_distribution = self.mock_linux_distribution
        
        # Act
        os_offer, os_version, os_name = self.envlayer.platform.extract_linux_distribution_os_info()
        
        # Verify
        self.assertEqual(os_offer, 'test')
        self.assertEqual(os_version, 'test')
        self.assertEqual(os_name, 'test')
        
        # Restore mocks
        self.envlayer.platform.linux_distribution = self.backup_linux_distribution
        platform.system = self.backup_platform_system
    
    def test_extract_linux_distribution_os_info_no_data(self):
        """ Test linux_distribution_images_details returning none. """
        # set up mocks
        self.backup_platform_system = platform.system()
        platform.system = self.mock_platform_system
        self.backup_linux_distribution = self.envlayer.platform.linux_distribution
        self.envlayer.platform.linux_distribution = lambda: None
        
        # Act
        os_offer, os_version, os_name = self.envlayer.platform.extract_linux_distribution_os_info()
        
        # Verify
        self.assertIsNone(os_offer, None)
        self.assertIsNone(os_version, None)
        self.assertIsNone(os_name, None)
        
        # Restore mocks
        self.envlayer.platform.linux_distribution = self.backup_linux_distribution
        platform.system = self.backup_platform_system
        

if __name__ == '__main__':
    unittest.main()
