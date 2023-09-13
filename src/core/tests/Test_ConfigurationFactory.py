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
import json
import os
import unittest
from core.src.bootstrap.Bootstrapper import Bootstrapper
from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestConfigurationFactory(unittest.TestCase):
    def setUp(self):
        self.argument_composer = ArgumentComposer().get_composed_arguments()
        self.runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.ZYPPER)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def mock_read_with_retry_raise_exception(self):
        raise Exception

    def test_get_prod_config_correctly(self):
        bootstrapper = Bootstrapper(self.argument_composer, capture_stdout=False)
        config_factory = bootstrapper.configuration_factory
        self.assertTrue(config_factory)

        config = config_factory.get_configuration(Constants.PROD, Constants.YUM)

        self.assertEqual(config['package_manager_name'], Constants.YUM)
        self.assertEqual(config['config_env'], Constants.PROD)

    def test_get_test_config_correctly(self):
        bootstrapper = Bootstrapper(self.argument_composer, capture_stdout=False)
        config_factory = bootstrapper.configuration_factory
        self.assertTrue(config_factory)
        config = config_factory.get_configuration(Constants.TEST, Constants.APT)

        self.assertEqual(config['package_manager_name'], Constants.APT)
        self.assertEqual(config['config_env'], Constants.TEST)

    def test_get_dev_config_correctly(self):
        bootstrapper = Bootstrapper(self.argument_composer, capture_stdout=False)
        config_factory = bootstrapper.configuration_factory
        self.assertTrue(config_factory)

        config = config_factory.get_configuration(Constants.DEV, Constants.APT)

        self.assertEqual(config['package_manager_name'], Constants.APT)
        self.assertEqual(config['config_env'], Constants.DEV)

    def test_eula_acceptance_file_read_success(self):
        self.runtime.stop()

        # Accept EULA set to true
        eula_settings = {
            "AcceptEULAForAllPatches": True,
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, True)
        runtime.stop()

        # Accept EULA set to false
        eula_settings = {
            "AcceptEULAForAllPatches": False,
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        runtime.stop()

    def test_eula_acceptance_file_read_when_no_data_found(self):
        self.runtime.stop()

        # EULA file does not exist
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        self.assertFalse(os.path.exists(Constants.AzGPSPaths.EULA_SETTINGS))
        runtime.stop()

        # EULA settings set to None
        eula_settings = None
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        self.assertTrue(os.path.exists(Constants.AzGPSPaths.EULA_SETTINGS))
        runtime.stop()

        # AcceptEULAForAllPatches not set in config
        eula_settings = {
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        self.assertTrue(os.path.exists(Constants.AzGPSPaths.EULA_SETTINGS))
        runtime.stop()

        # AcceptEULAForAllPatches not set to a boolean
        eula_settings = {
            "AcceptEULAForAllPatches": "test",
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        self.assertTrue(os.path.exists(Constants.AzGPSPaths.EULA_SETTINGS))
        runtime.stop()

        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        self.backup_read_with_retry = runtime.env_layer.file_system.read_with_retry
        runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_raise_exception
        self.assertTrue(os.path.exists(Constants.AzGPSPaths.EULA_SETTINGS))
        self.assertRaises(Exception, container.get('execution_config'))
        runtime.stop()


if __name__ == '__main__':
    unittest.main()
