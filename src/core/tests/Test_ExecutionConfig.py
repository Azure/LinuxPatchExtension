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

    def test_uefi_config_when_no_data_found_in_file(self):
        # UEFI in-VM customer config file exists but the file has no data
        uefi_settings = None
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=True, expected_enable_uefi_cert_update=False)
        self.__teardown(runtime)

    def test_uefi_config_when_enable_uefi_cert_update_not_in_config(self):
        # EnableUEFICertUpdate not set in config
        uefi_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21"
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=True, expected_enable_uefi_cert_update=False)
        self.__teardown(runtime)

    def test_uefi_config_when_enable_uefi_cert_update_not_set_as_boolean(self):
        uefi_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": "test"
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=True, expected_enable_uefi_cert_update=False)
        self.__teardown(runtime)

    def test_uefi_config_with_illformed_config(self):
        uefi_settings = ["test unexpected config value"]
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=True, expected_enable_uefi_cert_update=False)
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

    def test_uefi_config_file_with_enable_uefi_cert_update_set_to_false(self):
        # Tests UEFI cert update enable set with different non-true values

        # Value set to boolean False
        uefi_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": False
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=True, expected_enable_uefi_cert_update=False)
        self.__teardown(runtime)

        # Value set to random string
        uefi_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": "3"
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=True, expected_enable_uefi_cert_update=False)
        self.__teardown(runtime)

    def test_uefi_config_file_with_enable_uefi_cert_update_set_to_true(self):
        # Tests EnableUEFICertUpdate with all acceptable values of true

        # Value set to boolean True
        uefi_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": True
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=True, expected_enable_uefi_cert_update=True)
        self.__teardown(runtime)

        # Value set to string "True"
        uefi_settings["EnableUEFICertUpdate"] = "True"
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=True, expected_enable_uefi_cert_update=True)
        self.__teardown(runtime)

        # Value set to string "true"
        uefi_settings["EnableUEFICertUpdate"] = "true"
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=True, expected_enable_uefi_cert_update=True)
        self.__teardown(runtime)

        # Value set to string "1"
        uefi_settings["EnableUEFICertUpdate"] = "1"
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=True, expected_enable_uefi_cert_update=True)
        self.__teardown(runtime)

        # Value set to 1
        uefi_settings["EnableUEFICertUpdate"] = 1
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, config="UEFI", config_settings=uefi_settings)
        self.__assert_uefi_configs(execution_config=execution_config, expected_file_exists=True, expected_enable_uefi_cert_update=True)
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
        f = open(config_file_path, "w+")
        f.write(json.dumps(config_settings))
        f.close()

    @staticmethod
    def __teardown(runtime):
        # remove the uefi settings file if it exists after the test
        if os.path.exists(Constants.AzGPSPaths.UEFI_SETTINGS):
            os.remove(Constants.AzGPSPaths.UEFI_SETTINGS)
        runtime.stop()


if __name__ == '__main__':
    unittest.main()
