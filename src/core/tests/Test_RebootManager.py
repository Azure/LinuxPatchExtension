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

from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


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
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        reboot_manager = runtime.reboot_manager
        self.assertEqual(reboot_manager.is_setting(reboot_setting_in_code), True)
        runtime.stop()

    def test_reboot_setting_default_config(self):
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = ""
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
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
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        reboot_manager = runtime.reboot_manager
        self.assertEqual(reboot_manager.start_reboot_if_required_and_time_available(20), False)
        runtime.stop()

    def test_reboot_pending_with_reboot_setting_as_never(self):
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = 'Never'
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        reboot_manager = runtime.reboot_manager
        runtime.package_manager.force_reboot = True
        self.assertEqual(reboot_manager.start_reboot_if_required_and_time_available(20), False)
        runtime.stop()

    def test_reboot_always_time_available(self):
        reboot_setting_in_api = 'Always'
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = reboot_setting_in_api
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        reboot_manager = runtime.reboot_manager
        self.assertEqual(reboot_manager.start_reboot_if_required_and_time_available(20), True)
        runtime.stop()

    def test_reboot_always_runs_only_once_if_no_reboot_is_required(self):
        reboot_setting_in_api = 'Always'
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = reboot_setting_in_api
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        reboot_manager = runtime.reboot_manager

        # Validate single reboot scenario
        runtime.status_handler.is_reboot_pending = True
        self.assertEqual(reboot_manager.start_reboot_if_required_and_time_available(20), True)

        # mock completing the reboot once, with no reboot required
        runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.REQUIRED)
        runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        runtime.status_handler.is_reboot_pending = False
        runtime.status_handler.set_installation_reboot_status(Constants.RebootStatus.COMPLETED)

        # no further reboot should be required
        self.assertEqual(reboot_manager.start_reboot_if_required_and_time_available(20), False)
        runtime.stop()

    def test_reboot_always_time_not_available(self):
        reboot_setting_in_api = 'Always'
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = reboot_setting_in_api
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        reboot_manager = runtime.reboot_manager
        self.assertEqual(reboot_manager.start_reboot_if_required_and_time_available(10), False)
        runtime.stop()

    def test_reboot_if_required_no_reboot_pending(self):
        reboot_setting_in_api = 'IfRequired'
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = reboot_setting_in_api
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        reboot_manager = runtime.reboot_manager

        # Validate single reboot scenario
        runtime.status_handler.is_reboot_pending = False
        self.assertEqual(reboot_manager.start_reboot_if_required_and_time_available(20), False)
        runtime.stop()

    def test_start_reboot_raise_exception(self):
        reboot_setting_in_api = 'Always'
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = reboot_setting_in_api
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        Constants.REBOOT_WAIT_TIMEOUT_IN_MINUTES_MIN = -20

        with self.assertRaises(Exception) as context:
            runtime.use_original_rm_start_reboot()
            runtime.reboot_manager._RebootManager__start_reboot()

        # assert
        self.assertIn("Customer environment issue: Reboot failed to proceed on the machine in a timely manner. Please retry the operation.", repr(context.exception))
        self.assertEqual(context.exception.args[1], "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
        runtime.stop()

    def test_reboot_manager_start_reboot_bug_check(self):
        """ Branches code into a code path that should never execute """
        argument_composer = ArgumentComposer()
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        runtime.reboot_manager._RebootManager__reboot_setting = 'NotARealSetting'   # needs to be set like this to bypass code protections.
        self.assertEqual(runtime.reboot_manager.start_reboot_if_required_and_time_available(20), False)
        runtime.stop()

    def test_max_allowable_time_calculations(self):
        """ Test the max allowable time to reboot calculations """
        argument_composer = ArgumentComposer()
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)

        # shorten vars to aid test matrix readability
        min_timeout = Constants.REBOOT_WAIT_TIMEOUT_IN_MINUTES_MIN
        max_timeout = Constants.REBOOT_WAIT_TIMEOUT_IN_MINUTES_MAX
        ready_time = Constants.REBOOT_TO_MACHINE_READY_TIME_IN_MINUTES

        # declarative test case matrix
        input_output_matrix = [
            # [dataset number, total mw time available, expected_output]
            [0, 0, min_timeout],                                    # never less than min timeout

            # Boundary of min
            [1, min_timeout - 1, min_timeout],
            [2, min_timeout, min_timeout],
            [3, min_timeout + 1, min_timeout],
            [4, min_timeout + ready_time, min_timeout],
            [5, min_timeout + ready_time + 1, min_timeout + 1],     # only allowed to exceed min timeout if available time > min timeout + time allocated for machine to be ready

            # Boundary of max
            [6, max_timeout - 1, max_timeout - 1 - ready_time],     # ready time is always subtracted to get the max allowable time
            [7, max_timeout, max_timeout - ready_time],
            [8, max_timeout + 1, max_timeout - ready_time + 1],
            [9, max_timeout + ready_time - 1, max_timeout - 1],
            [10, max_timeout + ready_time + 1, max_timeout],
            [11, max_timeout + 100, max_timeout],                   # never exceeds max timeout
        ]

        for dataset in input_output_matrix:
            input_value = dataset[1]
            expected_output = dataset[2]
            self.assertEqual(runtime.reboot_manager._RebootManager__calc_max_allowable_time_to_reboot_in_minutes(input_value),
                             expected_output,
                             msg="Failed on dataset {0} with input {1} and expected output {2}.".format(dataset[0], input_value, expected_output))

        runtime.stop()


if __name__ == '__main__':
    unittest.main()
