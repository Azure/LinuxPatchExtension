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

from core.src.bootstrap.Constants import Constants
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestExecutionConfig(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # region Mocks
    def mock_read_with_retry_raise_exception(self):
        raise Exception
    # endregion

    def test_get_max_patch_publish_date(self):
        test_input_output_table = [
            ["pub_off_sku_2020.09.29", "20200929T000000Z"],
            ["pu_b_off_sk_u_2020.09.29", "20200929T000000Z"],
            [str(), str()],
            ["pub_off_sku_20.09.29", str()],
            ["pub_off_sku_2020.9.29", str()],
            ["pub_off_sk_u2020.09.29", str()],
            ["x_2020.09.29", "20200929T000000Z"]  # theoretically okay
        ]

        argument_composer = ArgumentComposer()
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        for row in test_input_output_table:
            self.assertEqual(runtime.execution_config._ExecutionConfig__get_max_patch_publish_date(row[0]), row[1])
        runtime.stop()

    def test_uefi_config_when_file_does_not_exist(self):
        # UEFI in-VM customer config does not exist
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=False, config="UEFI")
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=False,
                                  expected_enable_auto_patching=None, expected_enable_non_auto_patching=None)
        self.__teardown(runtime)

    def test_uefi_config_when_file_read_raises_exception(self):
        uefi_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUefiCertUpdateForAutoPatching": True
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.backup_read_with_retry = runtime.env_layer.file_system.read_with_retry
        runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_raise_exception
        exec_config = ExecutionConfig(runtime.env_layer, runtime.composite_logger, str(runtime.argv))
        self.__assert_uefi_configs(execution_config=exec_config, expected_file_exists=True,
                                  expected_enable_auto_patching=None, expected_enable_non_auto_patching=None)
        runtime.env_layer.file_system.read_with_retry = self.backup_read_with_retry
        self.__teardown(runtime)


    def __assert_uefi_configs(self, execution_config, expected_file_exists, expected_enable_auto_patching, expected_enable_non_auto_patching):
        self.assertEqual(os.path.exists(Constants.AzGPSPaths.UEFI_SETTINGS), expected_file_exists)
        self.assertEqual(execution_config.enable_uefi_cert_update_for_auto_patching, expected_enable_auto_patching)
        self.assertEqual(execution_config.enable_uefi_cert_update_for_non_auto_patching, expected_enable_non_auto_patching)

    def __setup_and_init_execution_config(self, write_to_file=False, config=None, config_settings=None):
        argument_composer = ArgumentComposer()
        config_file_path = None
        if config is not None and config == "UEFI":
            config_file_path = Constants.AzGPSPaths.UEFI_SETTINGS

        if write_to_file:
            self.__write_config_settings_to_file(config_settings, config_file_path=config_file_path)
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        return runtime, execution_config

    @staticmethod
    def __write_config_settings_to_file(config_settings, config_file_path):
        with open(config_file_path, "w+") as f:
            f.write(json.dumps(config_settings))

    @staticmethod
    def __teardown(runtime):
        # remove the uefi settings file if it exists after the test
        if os.path.exists(Constants.AzGPSPaths.UEFI_SETTINGS):
            os.remove(Constants.AzGPSPaths.UEFI_SETTINGS)
        runtime.stop()

    def test_is_cert_update_for_auto_patching_explicitly_enabled(self):
        """Tests is_cert_update_for_auto_patching_explicitly_enabled() returns True only for explicitly set truthy values.
        None (not set) should return False - absence of config is not the same as being explicitly enabled.
        Only boolean True, string 'True'/'true'/'1', and integer 1 should return True (per __is_truthy logic)."""
        runtime, execution_config = self.__setup_and_init_execution_config()

        # [value for enable_uefi_cert_update_for_auto_patching, expected_result from is_cert_update_for_auto_patching_explicitly_enabled]
        test_cases = [
            # Not set - not explicitly enabled
            [None,    False],
            # Truthy values - explicitly enabled
            [True,    True],
            ["True",  True],
            ["true",  True],
            ["1",     True],
            [1,       True],
            # Falsy/invalid values - not explicitly enabled
            [False,   False],
            ["False", False],
            ["false", False],
            ["0",     False],
            [0,       False],
            ["3",     False],
            ["test",  False],
            [3.1,     False],
        ]

        for value, expected in test_cases:
            execution_config.enable_uefi_cert_update_for_auto_patching = value
            self.assertEqual(execution_config.is_cert_update_for_auto_patching_explicitly_enabled(), expected,
                             msg="Failed for enable_uefi_cert_update_for_auto_patching={0}".format(repr(value)))

        self.__teardown(runtime)

    def test_is_cert_update_for_auto_patching_explicitly_disabled(self):
        """Tests is_cert_update_for_auto_patching_explicitly_disabled() returns True only for explicitly set falsy values.
        None (not set) should return False - absence of config means not explicitly disabled.
        Truthy values (True, 'True', '1', 1) should also return False - they are explicitly enabled, not disabled.
        Only explicitly set non-truthy values (False, 'test', 3.1, etc.) should return True."""
        runtime, execution_config = self.__setup_and_init_execution_config()

        # [value for enable_uefi_cert_update_for_auto_patching, expected_result for is_cert_update_for_auto_patching_explicitly_disabled]
        test_cases = [
            # Not set - not explicitly disabled
            [None,    False],
            # Truthy values - not disabled (they are enabled)
            [True,    False],
            ["True",  False],
            ["true",  False],
            ["1",     False],
            [1,       False],
            # Explicitly set to falsy - explicitly disabled
            [False,   True],
            ["False", True],
            ["false", True],
            ["0",     True],
            [0,       True],
            ["3",     True],
            ["test",  True],
            [3.1,     True],
        ]

        for value, expected in test_cases:
            execution_config.enable_uefi_cert_update_for_auto_patching = value
            self.assertEqual(execution_config.is_cert_update_for_auto_patching_explicitly_disabled(), expected,
                             msg="Failed for enable_uefi_cert_update_for_auto_patching={0}".format(repr(value)))

        self.__teardown(runtime)

    def test_is_cert_update_for_non_auto_patching_explicitly_enabled(self):
        """Tests is_cert_update_for_non_auto_patching_explicitly_enabled() returns True only for explicitly set truthy values.
        Follows the same truthy evaluation rules as the auto patching equivalent."""
        runtime, execution_config = self.__setup_and_init_execution_config()

        # [value for enable_uefi_cert_update_for_non_auto_patching, expected_result for is_cert_update_for_non_auto_patching_explicitly_enabled]
        test_cases = [
            # Not set - not explicitly enabled
            [None,    False],
            # Truthy values - explicitly enabled
            [True,    True],
            ["True",  True],
            ["true",  True],
            ["1",     True],
            [1,       True],
            # Falsy/invalid values - not explicitly enabled
            [False,   False],
            ["False", False],
            ["false", False],
            ["0",     False],
            [0,       False],
            ["3",     False],
            ["test",  False],
            [3.1,     False],
        ]

        for value, expected in test_cases:
            execution_config.enable_uefi_cert_update_for_non_auto_patching = value
            self.assertEqual(execution_config.is_cert_update_for_non_auto_patching_explicitly_enabled(), expected,
                             msg="Failed for enable_uefi_cert_update_for_non_auto_patching={0}".format(repr(value)))

        self.__teardown(runtime)


if __name__ == '__main__':
    unittest.main()
