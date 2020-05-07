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

import datetime
import unittest
from tests.library.ArgumentComposer import ArgumentComposer
from tests.library.RuntimeCompositor import RuntimeCompositor


class TestMaintenanceWindow(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_RemainingTime(self):
        argument_composer = ArgumentComposer()
        argument_composer.start_time = "2017-02-15T18:15:12.9828835Z"
        argument_composer.maximum_duration = "PT1H"
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)

        current_time = datetime.datetime.strptime('2017-02-15 18:30:20', "%Y-%m-%d %H:%M:%S")
        remaining_time = runtime.maintenance_window.get_remaining_time_in_minutes(current_time)

        self.assertEqual(int(remaining_time), 44)
        runtime.stop()

    def test_iso8601_duration_to_timedelta_str_conversion(self):
        runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True)
        self.assertEqual("2:00:00", runtime.execution_config._ExecutionConfig__convert_iso8601_duration_to_timedelta_str("PT2H"))
        self.assertEqual("0:03:00", runtime.execution_config._ExecutionConfig__convert_iso8601_duration_to_timedelta_str("PT3M"))
        self.assertEqual("0:00:40", runtime.execution_config._ExecutionConfig__convert_iso8601_duration_to_timedelta_str("PT40S"))
        self.assertEqual("0:03:40", runtime.execution_config._ExecutionConfig__convert_iso8601_duration_to_timedelta_str("PT3M40S"))
        self.assertEqual("12:03:40", runtime.execution_config._ExecutionConfig__convert_iso8601_duration_to_timedelta_str("PT12H3M40S"))
        self.assertEqual("1:00:40", runtime.execution_config._ExecutionConfig__convert_iso8601_duration_to_timedelta_str("PT1H40S"))
        with self.assertRaises(Exception):
            runtime.env_layer.datetime.convert_iso8601_duration_to_timedelta_str("P1DT12H3M40S")
        runtime.stop()

    def test_RemainingTime_after_duration_complete(self):
        argument_composer = ArgumentComposer()
        argument_composer.start_time = "2017-02-15T18:15:12.9828835Z"
        argument_composer.maximum_duration = "PT1H"
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)

        current_time = datetime.datetime.strptime('2017-02-15 19:16:20', "%Y-%m-%d %H:%M:%S")
        remaining_time = runtime.maintenance_window.get_remaining_time_in_minutes(current_time)

        self.assertEqual(int(remaining_time), 0)
        runtime.stop()

    def test_check_available_time(self):
        argument_composer = ArgumentComposer()
        argument_composer.start_time = (datetime.datetime.utcnow() - datetime.timedelta(minutes=39)).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer.maximum_duration = "PT1H"
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)
        self.assertEqual(runtime.maintenance_window.is_package_install_time_available(), True)
        runtime.stop()

    def test_check_available_time_after_duration_complete(self):
        argument_composer = ArgumentComposer()
        argument_composer.start_time = (datetime.datetime.utcnow() - datetime.timedelta(hours=1, minutes=2)).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer.maximum_duration = "PT1H"
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)
        self.assertEqual(runtime.maintenance_window.is_package_install_time_available(), False)
        runtime.stop()

if __name__ == '__main__':
    unittest.main()
