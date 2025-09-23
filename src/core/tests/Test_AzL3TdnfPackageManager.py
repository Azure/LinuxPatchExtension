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
import json
import os
import unittest
# Conditional import for StringIO
try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import StringIO  # Python 3

from core.src.bootstrap.Constants import Constants
from core.tests.library.LegacyEnvLayerExtensions import LegacyEnvLayerExtensions
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor
from core.src.external_dependencies import distro


class TestAzL3TdnfPackageManager(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.TDNF)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    # region Mocks
    def mock_linux_distribution_to_return_azure_linux(self):
        return ['Microsoft Azure Linux', '3.0', '']

    def mock_linux_distribution_to_return_azure_linux_2(self):
        return ['Common Base Linux Mariner', '2.0', '']

    def mock_run_command_output_return_tdnf_3(self, cmd, no_output=False, chk_err=True):
        """ Mock for run_command_output to return tdnf 3 """
        return 0, "3.5.8-3\n"

    def mock_run_command_output_return_1(self, cmd, no_output=False, chk_err=True):
        """ Mock for run_command_output to return None """
        return 1, "No output available\n"

    def mock_run_command_output_return_0(self, cmd, no_output=False, chk_err=True):
        return 0, "Successfully executed command\n"

    def mock_get_tdnf_version_return_tdnf_3_5_8_3(self):
        return "3.5.8-3.azl3"

    def mock_get_tdnf_version_return_tdnf_4_0(self):
        return "4.0.0-1.azl3"

    def mock_get_tdnf_version_return_tdnf_2_5(self):
        return "2.5.0-1.cm2"

    def mock_get_tdnf_version_return_tdnf_3_5_8_2(self):
        return "3.5.8-2.azl3"

    def mock_get_tdnf_version_return_tdnf_3_5_8_6_cm2(self):
        return "3.5.8-6.cm2"

    def mock_get_tdnf_version_return_None(self):
        return None

    def mock_distro_os_release_attr_return_azure_linux_3(self, attribute):
        return '3.0.0'

    def mock_distro_os_release_attr_return_azure_linux_2(self, attribute):
        return '2.9.0'
    # endregion

    def test_all_classification_selected_for_auto_patching_request(self):
        """Unit test for tdnf package manager for auto patching request where all classifications are selected since Azure Linux does not have classifications"""
        backup_envlayer_platform_linux_distribution = LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution
        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = self.mock_linux_distribution_to_return_azure_linux

        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.SECURITY, Constants.PackageClassification.CRITICAL]
        argument_composer.health_store_id = "pub_off_sku_2025.03.24"
        argument_composer.operation = Constants.INSTALLATION
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.TDNF)
        self.container = self.runtime.container

        execution_config = self.container.get('execution_config')
        self.assertTrue(execution_config.included_classifications_list is not None)
        self.assertTrue(execution_config.included_classifications_list == [Constants.PackageClassification.CRITICAL, Constants.PackageClassification.SECURITY, Constants.PackageClassification.OTHER])

        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = backup_envlayer_platform_linux_distribution

    def test_set_max_patch_publish_date(self):
        """Unit test for tdnf package manager set_max_patch_publish_date method"""
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        input_output_table_for_successful_cases = [
            ["20240702T000000Z", "1719878400"],
            ["", ""]
        ]
        for row in input_output_table_for_successful_cases:
            package_manager.set_max_patch_publish_date(row[0])
            self.assertEqual(package_manager.max_patch_publish_date, row[1])

        # posix time computation throws an exception if the date is not in the correct format
        self.assertRaises(ValueError, package_manager.set_max_patch_publish_date, "2024-07-02T00:00:00Z")

    def test_get_tdnf_version(self):
        """Unit test for tdnf package manager get_tdnf_version method"""
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.backup_run_command_output = self.runtime.env_layer.run_command_output

        test_input_output_table = [
            [self.mock_run_command_output_return_tdnf_3, "3.5.8-3"],
            [self.mock_run_command_output_return_1, None],
        ]

        for row in test_input_output_table:
            self.runtime.env_layer.run_command_output = row[0]
            version = package_manager.get_tdnf_version()
            self.assertEqual(version, row[1])

        self.runtime.env_layer.run_command_output = self.backup_run_command_output

    def test_is_mininum_tdnf_version_for_strict_sdp_installed(self):
        """Unit test for tdnf package manager is_minimum_tdnf_version method"""
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        self.backup_get_tdnf_version = package_manager.get_tdnf_version

        test_input_output_table = [
            [self.mock_get_tdnf_version_return_None, False],
            [self.mock_get_tdnf_version_return_tdnf_2_5, False],
            [self.mock_get_tdnf_version_return_tdnf_3_5_8_2, False],
            [self.mock_get_tdnf_version_return_tdnf_3_5_8_6_cm2, False],
            [self.mock_get_tdnf_version_return_tdnf_3_5_8_3, True],
            [self.mock_get_tdnf_version_return_tdnf_4_0, True]
        ]

        for row in test_input_output_table:
            package_manager.get_tdnf_version = row[0]
            result = package_manager.is_minimum_tdnf_version_for_strict_sdp_installed()
            self.assertEqual(result, row[1])

        package_manager.get_tdnf_version = self.backup_get_tdnf_version

    def test_try_tdnf_update_to_meet_strict_sdp_requirements(self):
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        self.backup_run_command_output = self.runtime.env_layer.run_command_output

        input_output_table = [
            [self.mock_run_command_output_return_0, True],
            [self.mock_run_command_output_return_1, False],
        ]

        for row in input_output_table:
            self.runtime.env_layer.run_command_output = row[0]
            result = package_manager.try_tdnf_update_to_meet_strict_sdp_requirements()
            self.assertEqual(result, row[1])

        self.runtime.env_layer.run_command_output = self.backup_run_command_output

    def test_try_meet_azgps_coordinated_requirements(self):
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        # backup methods
        self.backup_linux_distribution = self.runtime.env_layer.platform.linux_distribution
        self.backup_distro_os_release_attr = distro.os_release_attr
        self.backup_get_tdnf_version = package_manager.get_tdnf_version
        self.backup_run_command_output = self.runtime.env_layer.run_command_output

        """ test cases:
                    1. Azure Linux 3 with tdnf version > 3.5.8-3
                    2. Azure Linux 3 with tdnf version = 3.5.8-3
                    3. Azure Linux 3 with tdnf version < 3.5.8-3, will be updated to 3.5.8-3 successfully
                    4. Azure Linux 3 with tdnf version < 3.5.8-3, will not be updated to 3.5.8-3
                    5. Azure Linux 2"""
        test_input_output_table = [
            [self.mock_linux_distribution_to_return_azure_linux, self.mock_distro_os_release_attr_return_azure_linux_3, self.mock_get_tdnf_version_return_tdnf_4_0, self.backup_run_command_output, True],
            [self.mock_linux_distribution_to_return_azure_linux, self.mock_distro_os_release_attr_return_azure_linux_3, self.mock_get_tdnf_version_return_tdnf_3_5_8_3, self.backup_run_command_output, True],
            [self.mock_linux_distribution_to_return_azure_linux, self.mock_distro_os_release_attr_return_azure_linux_3, self.mock_get_tdnf_version_return_tdnf_2_5, self.mock_run_command_output_return_0, True],
            [self.mock_linux_distribution_to_return_azure_linux, self.mock_distro_os_release_attr_return_azure_linux_3, self.mock_get_tdnf_version_return_tdnf_2_5, self.mock_run_command_output_return_1, False],
            [self.mock_linux_distribution_to_return_azure_linux_2, self.mock_distro_os_release_attr_return_azure_linux_2, self.backup_distro_os_release_attr, self.backup_run_command_output, False]
        ]

        for row in test_input_output_table:
            # set test case values
            self.runtime.env_layer.platform.linux_distribution = row[0]
            distro.os_release_attr = row[1]
            package_manager.get_tdnf_version = row[2]
            self.runtime.env_layer.run_command_output = row[3]

            # run test case
            result = package_manager.try_meet_azgps_coordinated_requirements()
            self.assertEqual(result, row[4])

        # restore original methods
        self.runtime.env_layer.platform.linux_distribution = self.backup_linux_distribution
        distro.os_release_attr = self.backup_distro_os_release_attr
        package_manager.get_tdnf_version = self.backup_get_tdnf_version
        self.runtime.env_layer.run_command_output = self.backup_run_command_output


if __name__ == '__main__':
    unittest.main()

