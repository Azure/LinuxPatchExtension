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
        self.__teardown(runtime)

    def test_livepatch_config_when_file_does_not_exist(self):
        # livepatch in-VM customer config does not exist
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=False)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=dict(),
                                        expected_livepatch_requested=False, expected_livepatch_only_requested=False, expected_file_exists=False)
        self.__teardown(runtime)

    def test_livepatch_config_when_no_data_found_in_file(self):
        # livepatch in-VM customer config file exists but the file has no data
        livepatch_settings = None
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=dict(),
                                        expected_livepatch_requested=False, expected_livepatch_only_requested=False, expected_file_exists=True)
        self.__teardown(runtime)

    def test_livepatch_config_when_enable_livepatch_not_in_config(self):
        # EnableLivePatch not set in config
        livepatch_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21"
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=livepatch_settings,
                                        expected_livepatch_requested=False, expected_livepatch_only_requested=False, expected_file_exists=True)
        self.__teardown(runtime)

    def test_livepatch_config_when_enable_livepatch_not_set_as_boolean(self):
        livepatch_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableLivePatch": "test",
            "LivePatchOnly": "test"
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=livepatch_settings,
                                        expected_livepatch_requested=False, expected_livepatch_only_requested=False, expected_file_exists=True)
        self.__teardown(runtime)

    def test_livepatch_config_with_illformed_config(self):
        livepatch_settings = ["test unexpected config value"]
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=livepatch_settings,
                                        expected_livepatch_requested=False, expected_livepatch_only_requested=False, expected_file_exists=True)
        self.__teardown(runtime)

    def test_livepatch_config_when_file_read_raises_exception(self):
        livepatch_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableLivePatch": "test",
            "LivePatchOnly": "test"
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.backup_read_with_retry = runtime.env_layer.file_system.read_with_retry
        runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_raise_exception
        exec_config = ExecutionConfig(runtime.env_layer, runtime.composite_logger, str(runtime.argv))
        self.__assert_livepatch_configs(execution_config=exec_config, expected_livepatch_config_settings=dict(),
                                        expected_livepatch_requested=False, expected_livepatch_only_requested=False, expected_file_exists=True)
        runtime.env_layer.file_system.read_with_retry = self.backup_read_with_retry
        self.__teardown(runtime)

    def test_livepatch_config_file_with_livepatch_enabled_set_to_false(self):
        # Tests livepatch enable set with different non-true values

        # Value set to boolean False
        livepatch_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableLivePatch": False,
            "LivePatchOnly": False
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=livepatch_settings,
                                        expected_livepatch_requested=False, expected_livepatch_only_requested=False, expected_file_exists=True)
        self.__teardown(runtime)

        # Value set to random string
        livepatch_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableLivePatch": "3",
            "LivePatchOnly": "test"
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=livepatch_settings,
                                        expected_livepatch_requested=False, expected_livepatch_only_requested=False, expected_file_exists=True)
        self.__teardown(runtime)

        # LivepatchOnly set to true
        livepatch_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableLivePatch": False,
            "LivePatchOnly": True
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=livepatch_settings,
                                        expected_livepatch_requested=False, expected_livepatch_only_requested=True, expected_file_exists=True)
        self.__teardown(runtime)

    def test_livepatch_config_file_with_livepatch_enable_set_to_true(self):
        # Tests EnableLivePatch with all acceptable values of true

        # Value set to boolean True
        livepatch_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableLivePatch": True,
            "LivePatchOnly": False
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=livepatch_settings,
                                        expected_livepatch_requested=True, expected_livepatch_only_requested=False, expected_file_exists=True)
        self.__teardown(runtime)

        # Value set to string "True"
        livepatch_settings["EnableLivePatch"] = "True"
        livepatch_settings["LivePatchOnly"] = "True"
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=livepatch_settings,
                                        expected_livepatch_requested=True, expected_livepatch_only_requested=True, expected_file_exists=True)
        self.__teardown(runtime)

        # Value set to string "true"
        livepatch_settings["EnableLivePatch"] = "true"
        livepatch_settings["LivePatchOnly"] = "true"
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=livepatch_settings,
                                        expected_livepatch_requested=True, expected_livepatch_only_requested=True, expected_file_exists=True)
        self.__teardown(runtime)

        # Value set to string "1"
        livepatch_settings["EnableLivePatch"] = "1"
        livepatch_settings["LivePatchOnly"] = "1"
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=livepatch_settings,
                                        expected_livepatch_requested=True, expected_livepatch_only_requested=True, expected_file_exists=True)
        self.__teardown(runtime)

        # Value set to 1
        livepatch_settings["EnableLivePatch"] = 1
        livepatch_settings["LivePatchOnly"] = 1
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatch_settings=livepatch_settings)
        self.__assert_livepatch_configs(execution_config=execution_config, expected_livepatch_config_settings=livepatch_settings,
                                        expected_livepatch_requested=True, expected_livepatch_only_requested=True, expected_file_exists=True)
        self.__teardown(runtime)

    def __write_livepatch_settings_to_file(self, livepatch_settings):
        f = open(Constants.AzGPSPaths.LIVEPATCH_CUSTOMER_SETTINGS, "w+")
        f.write(json.dumps(livepatch_settings))
        f.close()

    def __setup_and_init_execution_config(self, write_to_file=False, livepatch_settings= None):
        argument_composer = ArgumentComposer()
        if write_to_file:
            self.__write_livepatch_settings_to_file(livepatch_settings)
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        return runtime, execution_config

    def __assert_livepatch_configs(self, execution_config, expected_livepatch_config_settings, expected_livepatch_requested, expected_livepatch_only_requested, expected_file_exists):
        self.assertEqual(execution_config.livepatch_customer_config_settings, expected_livepatch_config_settings)
        self.assertEqual(execution_config.is_livepatch_requested, expected_livepatch_requested)
        self.assertEqual(execution_config.is_livepatch_only_requested, expected_livepatch_only_requested)
        self.assertEqual(os.path.exists(Constants.AzGPSPaths.LIVEPATCH_CUSTOMER_SETTINGS), expected_file_exists)

    def __teardown(self, runtime):
        # remove the livepatch settings file if it exists after the test
        if os.path.exists(Constants.AzGPSPaths.LIVEPATCH_CUSTOMER_SETTINGS):
            os.remove(Constants.AzGPSPaths.LIVEPATCH_CUSTOMER_SETTINGS)
        runtime.stop()


if __name__ == '__main__':
    unittest.main()
