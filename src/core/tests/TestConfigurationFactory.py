import unittest

from src.bootstrap.Bootstrapper import Bootstrapper
from src.bootstrap.Constants import Constants
from tests.library.ArgumentComposer import ArgumentComposer
from tests.library.RuntimeCompositor import RuntimeCompositor


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
