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

    def test_livepatching_config_when_file_does_not_exist(self):
        # livepatching InVM customer config does not exist
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=False)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=dict(),
                                           expected_livepatching_enabled=False, expected_livepatching_only=False, expected_file_exists=False)
        self.__teardown(runtime)

    def test_livepatching_config_when_no_data_found_in_file(self):
        # livepatching config file exists but the file has no data
        livepatching_settings = None
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=dict(),
                                           expected_livepatching_enabled=False, expected_livepatching_only=False, expected_file_exists=True)
        self.__teardown(runtime)

    def test_livepatching_config_when_enable_livepatching_not_in_config(self):
        # EnableLivePatching not set in config
        livepatching_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21"
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=livepatching_settings,
                                           expected_livepatching_enabled=False, expected_livepatching_only=False, expected_file_exists=True)
        self.__teardown(runtime)

    def test_livepatching_config_when_enable_livepatching_not_set_as_boolean(self):
        livepatching_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableLivePatching": "test",
            "LivePatchOnly": "test"
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=livepatching_settings,
                                           expected_livepatching_enabled=False, expected_livepatching_only=False, expected_file_exists=True)
        self.__teardown(runtime)

    def test_livepatching_config_with_illformed_livepatching_config(self):
        livepatching_settings = ["test unexpected config value"]
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=livepatching_settings,
                                           expected_livepatching_enabled=False, expected_livepatching_only=False, expected_file_exists=True)
        self.__teardown(runtime)

    def test_livepatching_config_when_file_read_raises_exception(self):
        livepatching_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableLivePatching": "test",
            "LivePatchOnly": "test"
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.backup_read_with_retry = runtime.env_layer.file_system.read_with_retry
        runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_raise_exception
        exec_config = ExecutionConfig(runtime.env_layer, runtime.composite_logger, str(runtime.argv))
        self.__assert_livepatching_configs(execution_config=exec_config, expected_livepatching_config_settings=dict(),
                                           expected_livepatching_enabled=False, expected_livepatching_only=False, expected_file_exists=True)
        runtime.env_layer.file_system.read_with_retry = self.backup_read_with_retry
        self.__teardown(runtime)

    def test_livepatching_config_file_with_livepatching_enabled_set_to_false(self):
        # Tests livepatching enabled with different non-true values

        # Value set to boolean False
        livepatching_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableLivePatching": False,
            "LivePatchOnly": False
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=livepatching_settings,
                                           expected_livepatching_enabled=False, expected_livepatching_only=False, expected_file_exists=True)
        self.__teardown(runtime)

        # Value set to random string
        livepatching_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableLivePatching": "3",
            "LivePatchOnly": "test"
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=livepatching_settings,
                                           expected_livepatching_enabled=False, expected_livepatching_only=False, expected_file_exists=True)
        self.__teardown(runtime)

        # LivepatchOnly set to true
        livepatching_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableLivePatching": False,
            "LivePatchOnly": True
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=livepatching_settings,
                                           expected_livepatching_enabled=False, expected_livepatching_only=True, expected_file_exists=True)
        self.__teardown(runtime)

    def test_livepatching_config_file_with_livepatching_enabled_set_to_true(self):
        # Tests livepatching enabled with all acceptable values of true

        # Value set to boolean True
        livepatching_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableLivePatching": True,
            "LivePatchOnly": False
        }
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=livepatching_settings,
                                           expected_livepatching_enabled=True, expected_livepatching_only=False, expected_file_exists=True)
        self.__teardown(runtime)

        # Value set to string "True"
        livepatching_settings["EnableLivePatching"] = "True"
        livepatching_settings["LivePatchOnly"] = "True"
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=livepatching_settings,
                                           expected_livepatching_enabled=True, expected_livepatching_only=True, expected_file_exists=True)
        self.__teardown(runtime)

        # Value set to string "true"
        livepatching_settings["EnableLivePatching"] = "true"
        livepatching_settings["LivePatchOnly"] = "true"
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=livepatching_settings,
                                           expected_livepatching_enabled=True, expected_livepatching_only=True, expected_file_exists=True)
        self.__teardown(runtime)

        # Value set to string "1"
        livepatching_settings["EnableLivePatching"] = "1"
        livepatching_settings["LivePatchOnly"] = "1"
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=livepatching_settings,
                                           expected_livepatching_enabled=True, expected_livepatching_only=True, expected_file_exists=True)
        self.__teardown(runtime)

        # Value set to 1
        livepatching_settings["EnableLivePatching"] = 1
        livepatching_settings["LivePatchOnly"] = 1
        runtime, execution_config = self.__setup_and_init_execution_config(write_to_file=True, livepatching_settings=livepatching_settings)
        self.__assert_livepatching_configs(execution_config=execution_config, expected_livepatching_config_settings=livepatching_settings,
                                           expected_livepatching_enabled=True, expected_livepatching_only=True, expected_file_exists=True)
        self.__teardown(runtime)

    def __write_livepatching_settings_to_file(self, livepatching_settings):
        f = open(Constants.AzGPSPaths.LIVEPATCHING_SETTINGS, "w+")
        f.write(json.dumps(livepatching_settings))
        f.close()

    def __setup_and_init_execution_config(self, write_to_file=False, livepatching_settings= None):
        argument_composer = ArgumentComposer()
        if write_to_file:
            self.__write_livepatching_settings_to_file(livepatching_settings)
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        return runtime, execution_config

    def __assert_livepatching_configs(self, execution_config, expected_livepatching_config_settings, expected_livepatching_enabled, expected_livepatching_only, expected_file_exists):
        self.assertEqual(execution_config.livepatching_config_settings, expected_livepatching_config_settings)
        self.assertEqual(execution_config.livepatching_enabled, expected_livepatching_enabled)
        self.assertEqual(execution_config.livepatch_only, expected_livepatching_only)
        self.assertEqual(os.path.exists(Constants.AzGPSPaths.LIVEPATCHING_SETTINGS), expected_file_exists)

    def __teardown(self, runtime):
        # remove the livepatching settings file if it exists after the test
        if os.path.exists(Constants.AzGPSPaths.LIVEPATCHING_SETTINGS):
            os.remove(Constants.AzGPSPaths.LIVEPATCHING_SETTINGS)
        runtime.stop()


if __name__ == '__main__':
    unittest.main()
