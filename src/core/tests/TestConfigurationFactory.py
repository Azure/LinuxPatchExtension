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

import unittest
from core.src.bootstrap.Bootstrapper import Bootstrapper
from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestContainer(unittest.TestCase):
    def setUp(self):
        self.argument_composer = ArgumentComposer().get_composed_arguments()
        self.runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.ZYPPER)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

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


if __name__ == '__main__':
    unittest.main()
