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
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=False, expected_enable_uefi_cert_update=False)
        self.__teardown(runtime)

    def test_uefi_config_when_file_read_raises_exception(self):
        uefi_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": "test"
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.backup_read_with_retry = runtime.env_layer.file_system.read_with_retry
        runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_raise_exception
        exec_config = ExecutionConfig(runtime.env_layer, runtime.composite_logger, str(runtime.argv))
        self.__assert_uefi_configs(execution_config=exec_config, expected_file_exists=True, expected_enable_uefi_cert_update=False)
        runtime.env_layer.file_system.read_with_retry = self.backup_read_with_retry
        self.__teardown(runtime)

    def test_uefi_config_file_with_enable_uefi_cert_update(self):
        # Tests UEFI cert update enable set with different values based in uefi config

        # Use Case 1: No UEFI config found on VM
        uefi_settings_update_cert_when_no_uefi_config = None
        expected_file_status_when_no_uefi_config = True
        expected_enable_uefi_when_no_uefi_config = False

        # Use Case 2: UEFI settings are illformed
        uefi_settings_update_cert_when_enable_not_in_config = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21"
        }
        expected_file_status_when_enable_not_in_config = True
        expected_enable_uefi_when_enable_not_in_config = False

        # Use Case 3: UEFI settings are illformed
        uefi_settings_update_cert_illformed_config = ["test unexpected config value"]
        expected_file_status_when_illformed_config = True
        expected_enable_uefi_when_illformed_config = False

        # Use Case 4: Value set to boolean False
        uefi_settings_update_cert_false = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": False
        }
        expected_file_status_when_update_cert_false = True
        expected_enable_uefi_when_update_cert_false = False

        # Use Case 5: Value set to random string
        uefi_settings_when_update_cert_is_str = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": "3"
        }
        expected_file_status_when_update_cert_is_str = True
        expected_enable_uefi_when_update_cert_is_str = False

        # Use Case 6: Value set to random string test 2
        uefi_settings_when_update_cert_is_str_test2 = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": "test"
        }
        expected_file_status_when_update_cert_is_str_test2 = True
        expected_enable_uefi_when_update_cert_is_str_test2 = False

        # Use Case 7: Value set to float
        uefi_settings_when_update_cert_is_float = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": 3.1
        }
        expected_file_status_when_update_cert_is_float = True
        expected_enable_uefi_when_update_cert_is_float = False

        # Tests EnableUEFICertUpdate with all acceptable values of true
        # Use Case 8: Value set to boolean True
        uefi_settings_when_update_cert_true = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": True
        }
        expected_file_status_when_update_cert_true = True
        expected_enable_uefi_when_update_cert_true = True

        # Use Case 9: Value set to boolean True
        uefi_settings_when_update_cert_true_str = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": "True"
        }
        expected_file_status_when_update_cert_true_str = True
        expected_enable_uefi_when_update_cert_true_str = True

        # Use Case 10: Value set to boolean True
        uefi_settings_when_update_cert_true_str_lower_case = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": "true"
        }
        expected_file_status_when_update_cert_true_str_lower_case = True
        expected_enable_uefi_when_update_cert_true_str_lower_case = True

        # Use Case 11: Value set to boolean True
        uefi_settings_when_update_cert_true_numericstr = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": "1"
        }
        expected_file_status_when_update_cert_true_numericstr = True
        expected_enable_uefi_when_update_cert_true_numericstr = True

        # Use Case 12: Value set to boolean True
        uefi_settings_when_update_cert_true_numeric = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": 1
        }
        expected_file_status_when_update_cert_true_numeric = True
        expected_enable_uefi_when_update_cert_true_numeric = True

        test_input_output_table = [
            [uefi_settings_update_cert_when_no_uefi_config, expected_file_status_when_no_uefi_config, expected_enable_uefi_when_no_uefi_config],
            [uefi_settings_update_cert_when_enable_not_in_config, expected_file_status_when_enable_not_in_config, expected_enable_uefi_when_enable_not_in_config],
            [uefi_settings_update_cert_illformed_config, expected_file_status_when_illformed_config, expected_enable_uefi_when_illformed_config],
            [uefi_settings_update_cert_false, expected_file_status_when_update_cert_false, expected_enable_uefi_when_update_cert_false],
            [uefi_settings_when_update_cert_is_str, expected_file_status_when_update_cert_is_str, expected_enable_uefi_when_update_cert_is_str],
            [uefi_settings_when_update_cert_is_str_test2, expected_file_status_when_update_cert_is_str_test2, expected_enable_uefi_when_update_cert_is_str_test2],
            [uefi_settings_when_update_cert_is_float, expected_file_status_when_update_cert_is_float, expected_enable_uefi_when_update_cert_is_float],
            [uefi_settings_when_update_cert_true, expected_file_status_when_update_cert_true, expected_enable_uefi_when_update_cert_true],
            [uefi_settings_when_update_cert_true_str, expected_file_status_when_update_cert_true_str, expected_enable_uefi_when_update_cert_true_str],
            [uefi_settings_when_update_cert_true_str_lower_case, expected_file_status_when_update_cert_true_str_lower_case, expected_enable_uefi_when_update_cert_true_str_lower_case],
            [uefi_settings_when_update_cert_true_numericstr, expected_file_status_when_update_cert_true_numericstr, expected_enable_uefi_when_update_cert_true_numericstr],
            [uefi_settings_when_update_cert_true_numeric, expected_file_status_when_update_cert_true_numeric, expected_enable_uefi_when_update_cert_true_numeric]
        ]

        for row in test_input_output_table:
            runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=row[0])
            self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=row[1], expected_enable_uefi_cert_update=row[2])
            self.__teardown(runtime)

    def __assert_uefi_configs(self, execution_config, expected_file_exists, expected_enable_uefi_cert_update):
        self.assertEqual(os.path.exists(Constants.AzGPSPaths.UEFI_SETTINGS), expected_file_exists)
        self.assertEqual(execution_config.enable_uefi_cert_update, expected_enable_uefi_cert_update)

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


if __name__ == '__main__':
    unittest.main()
