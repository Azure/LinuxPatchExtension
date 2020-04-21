import unittest
from src.bootstrap.Constants import Constants
from tests.library.ArgumentComposer import ArgumentComposer
from tests.library.RuntimeCompositor import RuntimeCompositor


class TestRebootManager(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_reboot_settings(self):
        self.test_reboot_setting('Never', Constants.REBOOT_NEVER)
        self.test_reboot_setting('IfRequired', Constants.REBOOT_IF_REQUIRED)
        self.test_reboot_setting('Always', Constants.REBOOT_ALWAYS)

    def test_reboot_setting(self, reboot_setting_in_api='Never', reboot_setting_in_code=Constants.REBOOT_NEVER):
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = reboot_setting_in_api
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), Constants.YUM, True)
        reboot_manager = runtime.reboot_manager
        self.assertEqual(reboot_manager.is_setting(reboot_setting_in_code), True)
        runtime.stop()

    def test_reboot_setting_default_config(self):
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = ""
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), Constants.YUM, True)
        reboot_manager = runtime.reboot_manager
        self.assertEqual(reboot_manager.is_setting(Constants.REBOOT_IF_REQUIRED), True)
        runtime.stop()

    def test_reboot_time_available(self):
        runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True)
        reboot_manager = runtime.reboot_manager
        self.assertEqual(reboot_manager.is_reboot_time_available(20), True)
        self.assertEqual(reboot_manager.is_reboot_time_available(15), True)
        self.assertEqual(reboot_manager.is_reboot_time_available(14), False)
        runtime.stop()

    def test_reboot_never(self):
        reboot_setting_in_api = 'Never'
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = reboot_setting_in_api
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), Constants.YUM, True)
        reboot_manager = runtime.reboot_manager
        self.assertEqual(reboot_manager.start_reboot_if_required_and_time_available(20), False)
        runtime.stop()

    def test_reboot_always_time_available(self):
        reboot_setting_in_api = 'Always'
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = reboot_setting_in_api
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), Constants.YUM, True)
        reboot_manager = runtime.reboot_manager
        self.assertEqual(reboot_manager.start_reboot_if_required_and_time_available(20), True)
        runtime.stop()

    def test_reboot_always_time_not_available(self):
        reboot_setting_in_api = 'Always'
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = reboot_setting_in_api
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), Constants.YUM, True)
        reboot_manager = runtime.reboot_manager
        self.assertEqual(reboot_manager.start_reboot_if_required_and_time_available(10), False)
        runtime.stop()


if __name__ == '__main__':
    unittest.main()
