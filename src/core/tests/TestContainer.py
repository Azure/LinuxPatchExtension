import unittest
from src.bootstrap.Constants import Constants
from tests.library.ArgumentComposer import ArgumentComposer
from tests.library.RuntimeCompositor import RuntimeCompositor


class TestContainer(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, package_manager_name=Constants.ZYPPER)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def test_get_unsupported_service(self):
        """Try get a registered service"""
        try:
            self.container.get('unsupported_service')
        except KeyError as ex:
            self.assertEqual('No component for: unsupported_service', ex.message)


if __name__ == '__main__':
    unittest.main()
