# Copyright 2023 Microsoft Corporation
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

from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor
from core.src.core_logic.Stopwatch import Stopwatch


class TestStopwatch(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), legacy_mode=True)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def test_start(self):
        stopwatch = Stopwatch(self.runtime.env_layer, self.runtime.telemetry_writer, self.runtime.composite_logger)
        self.assertTrue(stopwatch.start_time is None)
        self.assertTrue(stopwatch.end_time is None)
        self.assertTrue(stopwatch.time_taken is None)
        self.assertTrue(stopwatch.task_details is None)
        stopwatch.start()
        self.assertTrue(stopwatch.start_time is not None)
        self.assertTrue(stopwatch.end_time is None)
        self.assertTrue(stopwatch.time_taken is None)
        self.assertTrue(stopwatch.task_details is None)

    def test_stop(self):
        stopwatch = Stopwatch(self.runtime.env_layer, self.runtime.telemetry_writer, self.runtime.composite_logger)
        self.assertTrue(stopwatch.start_time is None)
        self.assertTrue(stopwatch.end_time is None)
        self.assertTrue(stopwatch.time_taken is None)
        self.assertTrue(stopwatch.task_details is None)
        stopwatch.start()
        self.assertTrue(stopwatch.start_time is not None)
        self.assertTrue(stopwatch.end_time is None)
        self.assertTrue(stopwatch.time_taken is None)
        self.assertTrue(stopwatch.task_details is None)
        stopwatch.stop()
        self.assertTrue(stopwatch.start_time is not None)
        self.assertTrue(stopwatch.end_time is not None)
        self.assertTrue(stopwatch.time_taken is not None)
        self.assertTrue(stopwatch.task_details is None)

    def test_stop_and_write_telemetry(self):
        stopwatch = Stopwatch(self.runtime.env_layer, self.runtime.telemetry_writer, self.runtime.composite_logger)
        self.assertTrue(stopwatch.start_time is None)
        self.assertTrue(stopwatch.end_time is None)
        self.assertTrue(stopwatch.time_taken is None)
        self.assertTrue(stopwatch.task_details is None)
        stopwatch.start()
        self.assertTrue(stopwatch.start_time is not None)
        self.assertTrue(stopwatch.end_time is None)
        self.assertTrue(stopwatch.time_taken is None)
        self.assertTrue(stopwatch.task_details is None)
        stopwatch.stop_and_write_telemetry("test")
        self.assertTrue(stopwatch.start_time is not None)
        self.assertTrue(stopwatch.end_time is not None)
        self.assertTrue(stopwatch.time_taken is not None)
        self.assertTrue(stopwatch.task_details is not None)

    def test_set_task_details(self):
        stopwatch = Stopwatch(self.runtime.env_layer, self.runtime.telemetry_writer, self.runtime.composite_logger)
        self.assertTrue(stopwatch.start_time is None)
        self.assertTrue(stopwatch.end_time is None)
        self.assertTrue(stopwatch.time_taken is None)
        self.assertTrue(stopwatch.task_details is None)
        stopwatch.start()
        self.assertTrue(stopwatch.start_time is not None)
        self.assertTrue(stopwatch.end_time is None)
        self.assertTrue(stopwatch.time_taken is None)
        self.assertTrue(stopwatch.task_details is None)
        stopwatch.stop()
        self.assertTrue(stopwatch.start_time is not None)
        self.assertTrue(stopwatch.end_time is not None)
        self.assertTrue(stopwatch.time_taken is not None)
        self.assertTrue(stopwatch.task_details is None)
        stopwatch.set_task_details("test")
        self.assertTrue(stopwatch.task_details is not None)

    # test start Stopwatch twice
    def test_started_already(self):
        stopwatch = Stopwatch(self.runtime.env_layer, self.runtime.telemetry_writer, self.runtime.composite_logger)
        stopwatch.start()
        start1 = stopwatch.start_time
        stopwatch.start()
        start2 = stopwatch.start_time
        self.assertTrue(start1 <= start2)
        self.assertTrue(stopwatch.end_time is None)
        self.assertTrue(stopwatch.time_taken is None)
        self.assertTrue(stopwatch.task_details is None)

    # test stop Stopwatch when it was never started
    def test_not_started(self):
        stopwatch = Stopwatch(self.runtime.env_layer, self.runtime.telemetry_writer, self.runtime.composite_logger)
        stopwatch.stop()
        self.assertTrue(stopwatch.start_time is not None)
        self.assertTrue(stopwatch.start_time == stopwatch.end_time)
        self.assertTrue(stopwatch.time_taken == 0)
        self.assertTrue(stopwatch.task_details is None)

    # test stop Stopwatch twice
    def test_stopped_already(self):
        stopwatch = Stopwatch(self.runtime.env_layer, self.runtime.telemetry_writer, self.runtime.composite_logger)
        stopwatch.start()
        stopwatch.stop()
        start_time1 = stopwatch.start_time
        end_time1 = stopwatch.end_time
        time_taken1 = stopwatch.time_taken
        stopwatch.stop()
        start_time2 = stopwatch.start_time
        end_time2 = stopwatch.end_time
        time_taken2 = stopwatch.time_taken
        self.assertTrue(start_time1 == start_time2)
        self.assertTrue(end_time1 <= end_time2)
        self.assertTrue(time_taken1 <= time_taken2)
        

    def test_write_telemetry_for_stopwatch(self):
        stopwatch = Stopwatch(self.runtime.env_layer, self.runtime.telemetry_writer, self.runtime.composite_logger)
        stopwatch.write_telemetry_for_stopwatch("test")
        self.assertTrue(stopwatch.start_time is not None)
        self.assertTrue(stopwatch.end_time is not None)
        self.assertTrue(stopwatch.time_taken is not None)
        self.assertTrue(stopwatch.task_details is not None)
        self.assertTrue(stopwatch.start_time <= stopwatch.end_time)
        self.assertTrue(stopwatch.time_taken >= 0)


if __name__ == '__main__':
    unittest.main()
