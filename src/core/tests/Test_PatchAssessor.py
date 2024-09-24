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
import json
import os
import sys
import unittest

from core.src.bootstrap.Constants import Constants
from core.src.service_interfaces.TelemetryWriter import TelemetryWriter
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestPatchAssessor(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), legacy_mode=True)
        self.container = self.runtime.container
        self.original_version_info = sys.version_info

    def tearDown(self):
        sys.version_info = self.original_version_info
        self.runtime.stop()

    def test_assessment_success(self):
        self.assertTrue(self.runtime.patch_assessor.start_assessment())

    def test_assessment_fail(self):
        self.runtime.set_legacy_test_type('UnalignedPath')
        self.assertRaises(Exception, self.runtime.patch_assessor.start_assessment)

    def test_get_all_updates_fail(self):
        self.runtime.set_legacy_test_type('UnalignedPath')
        self.assertRaises(Exception, self.runtime.package_manager.get_all_updates)

    def test_get_all_security_updates_fail(self):
        self.runtime.set_legacy_test_type('UnalignedPath')
        self.assertRaises(Exception, self.runtime.package_manager.get_security_updates)

    def test_assessment_fail_with_status_update(self):
        self.runtime.package_manager.refresh_repo = self.mock_refresh_repo
        self.runtime.set_legacy_test_type('UnalignedPath')
        self.assertRaises(Exception, self.runtime.patch_assessor.start_assessment)
        with open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            file_contents = json.loads(file_handle.read())
            self.assertTrue('Unexpected return code (100) from package manager on command: LANG=en_US.UTF8 sudo apt-get -s dist-upgrade' in str(file_contents))

    def test_assessment_telemetry_fail(self):
        backup_telemetry_writer = self.runtime.telemetry_writer
        telemetry_writer = TelemetryWriter(self.runtime.env_layer, self.runtime.composite_logger, events_folder_path=None, telemetry_supported=False)
        self.runtime.patch_assessor.telemetry_writer = telemetry_writer
        self.assertRaises(Exception, self.runtime.patch_assessor.start_assessment)
        telemetry_writer = TelemetryWriter(self.runtime.env_layer, self.runtime.composite_logger, events_folder_path="events", telemetry_supported=False)
        self.runtime.patch_assessor.telemetry_writer = telemetry_writer
        self.assertRaises(Exception, self.runtime.patch_assessor.start_assessment)
        telemetry_writer = TelemetryWriter(self.runtime.env_layer, self.runtime.composite_logger, events_folder_path=None, telemetry_supported=True)
        self.runtime.patch_assessor.telemetry_writer = telemetry_writer
        self.assertRaises(Exception, self.runtime.patch_assessor.start_assessment)
        self.runtime.patch_assessor.telemetry_writer = backup_telemetry_writer

    def test_assessment_state_file(self):
        # read_assessment_state creates a vanilla assessment state file if none exists
        assessment_state = self.runtime.patch_assessor.read_assessment_state()
        with open(self.runtime.patch_assessor.assessment_state_file_path, 'r') as file_handle:
            assessment_state_from_file = json.loads(file_handle.read())["assessmentState"]
            self.assessment_state_equals(assessment_state, assessment_state_from_file)

        # write and test again
        self.runtime.patch_assessor.write_assessment_state()
        assessment_state = self.runtime.patch_assessor.read_assessment_state()
        with open(self.runtime.patch_assessor.assessment_state_file_path, 'r') as file_handle:
            assessment_state_from_file = json.loads(file_handle.read())["assessmentState"]
            self.assessment_state_equals(assessment_state, assessment_state_from_file)

        # Assessment state file is a directory
        if os.path.exists(self.runtime.patch_assessor.assessment_state_file_path):
            os.remove(self.runtime.patch_assessor.assessment_state_file_path)

        # Attempt to read when it does not exist - should create default assessment state file
        os.mkdir(self.runtime.patch_assessor.assessment_state_file_path)
        self.assertTrue(self.runtime.patch_assessor.read_assessment_state() is not None)

        if os.path.exists(self.runtime.patch_assessor.assessment_state_file_path):
            os.remove(self.runtime.patch_assessor.assessment_state_file_path)

        os.mkdir(self.runtime.patch_assessor.assessment_state_file_path)
        # Attempt to write when it does not exist - should also create default assessment state file
        self.runtime.patch_assessor.write_assessment_state()
        self.assertTrue(self.runtime.patch_assessor.read_assessment_state() is not None)

        # Opening file throws exception
        backup_open = self.runtime.patch_assessor.env_layer.file_system.open
        self.runtime.patch_assessor.env_layer.file_system.open = lambda: self.raise_ex()
        self.assertRaises(Exception, self.runtime.patch_assessor.read_assessment_state)
        self.assertRaises(Exception, self.runtime.patch_assessor.write_assessment_state)
        self.runtime.patch_assessor.env_layer.file_system.open = backup_open

    def assessment_state_equals(self, state1, state2):
        self.assertEqual(state1["processIds"][0], state2["processIds"][0])
        self.assertEqual(state1["lastHeartbeat"], state2["lastHeartbeat"])
        self.assertEqual(state1["number"], state2["number"])
        self.assertEqual(state1["autoAssessment"], state2["autoAssessment"])
        self.assertEqual(state1["lastStartInSecondsSinceEpoch"], state2["lastStartInSecondsSinceEpoch"])

    def test_should_auto_assessment_run(self):
        # First file write (since it does not exist on read) so it should succeed since last assessment time is 0
        self.runtime.patch_assessor.read_assessment_state()
        self.assertTrue(self.runtime.patch_assessor.should_auto_assessment_run())

        # Second file write, should fail now since minimum delay between assessments hasn't been met
        self.runtime.patch_assessor.write_assessment_state()
        self.assertFalse(self.runtime.patch_assessor.should_auto_assessment_run())

        # It has been minimum delay time since last run
        assessment_state = self.runtime.patch_assessor.read_assessment_state()
        min_auto_assess_interval_in_seconds = self.runtime.patch_assessor.convert_iso8601_duration_to_total_seconds(self.runtime.execution_config.maximum_assessment_interval)
        assessment_state["lastStartInSecondsSinceEpoch"] -= min_auto_assess_interval_in_seconds
        with open(self.runtime.patch_assessor.assessment_state_file_path, 'w+') as file_handle:
            file_handle.write(json.dumps({"assessmentState": assessment_state}))
        self.assertTrue(self.runtime.patch_assessor.should_auto_assessment_run())

        # Time is in the future, so run assessment and correct anomaly
        self.runtime.patch_assessor.write_assessment_state()
        assessment_state["lastStartInSecondsSinceEpoch"] += 5000000
        with open(self.runtime.patch_assessor.assessment_state_file_path, 'w+') as file_handle:
            file_handle.write(json.dumps({"assessmentState": assessment_state}))
        self.assertTrue(self.runtime.patch_assessor.should_auto_assessment_run())

        # Test exception case: exception is caught and assessment should run
        self.runtime.patch_assessor.read_assessment_state = lambda: self.raise_ex()
        self.assertTrue(self.runtime.patch_assessor.should_auto_assessment_run())

    def test_convert_iso8601_duration_to_total_seconds(self):
        self.assertEqual(self.runtime.patch_assessor.convert_iso8601_duration_to_total_seconds('PT6H'), 21600)
        self.assertEqual(self.runtime.patch_assessor.convert_iso8601_duration_to_total_seconds('PT6H5M'), 21900)
        self.assertEqual(self.runtime.patch_assessor.convert_iso8601_duration_to_total_seconds('PT6H5M14S'), 21914)
        self.assertRaises(Exception, lambda: self.runtime.patch_assessor.convert_iso8601_duration_to_total_seconds('6H5M14S'))
        self.assertRaises(Exception, lambda: self.runtime.patch_assessor.convert_iso8601_duration_to_total_seconds(''))

    def test_write_assessment_perf_logs(self):
        self.runtime.patch_assessor.start_assessment()
        self.assertTrue(self.runtime.patch_assessor.stopwatch.start_time is not None)
        self.assertTrue(self.runtime.patch_assessor.stopwatch.end_time is not None)
        self.assertTrue(self.runtime.patch_assessor.stopwatch.time_taken_in_secs is not None)
        self.assertTrue(self.runtime.patch_assessor.stopwatch.task_details is not None)
        self.assertTrue(self.runtime.patch_assessor.stopwatch.start_time <= self.runtime.patch_assessor.stopwatch.end_time)
        self.assertTrue(self.runtime.patch_assessor.stopwatch.time_taken_in_secs >= 0)
        task_info = "{0}={1}".format(str(Constants.PerfLogTrackerParams.TASK), str(Constants.ASSESSMENT))
        self.assertTrue(task_info in str(self.runtime.patch_assessor.stopwatch.task_details))
        task_status = "{0}={1}".format(str(Constants.PerfLogTrackerParams.TASK_STATUS), str(Constants.TaskStatus.SUCCEEDED))
        self.assertTrue(task_status in str(self.runtime.patch_assessor.stopwatch.task_details))
        err_msg = "{0}=".format(str(Constants.PerfLogTrackerParams.ERROR_MSG))
        self.assertTrue(err_msg in str(self.runtime.patch_assessor.stopwatch.task_details))

    def test_stopwatch_properties_assessment_fail(self):
        self.runtime.set_legacy_test_type('UnalignedPath')
        self.assertRaises(Exception, self.runtime.patch_assessor.start_assessment)
        self.assertTrue(self.runtime.patch_assessor.stopwatch.start_time is not None)
        self.assertTrue(self.runtime.patch_assessor.stopwatch.end_time is not None)
        self.assertTrue(self.runtime.patch_assessor.stopwatch.time_taken_in_secs is not None)
        self.assertTrue(self.runtime.patch_assessor.stopwatch.task_details is not None)

    def test_raise_if_min_python_version_not_met(self):
        sys.version_info = (2, 6)
        # Assert that an exception is raised
        with self.assertRaises(Exception) as context:
            self.runtime.patch_assessor.start_assessment()
        self.assertEqual(str(context.exception), Constants.PYTHON_NOT_COMPATIBLE_ERROR_MSG.format(sys.version_info))

    def test_raise_add_error_to_status(self):
        self.runtime.package_manager.get_all_updates = lambda: self.raise_ex()
        
        with self.assertRaises(Exception) as context:
            self.runtime.patch_assessor.start_assessment()
            
        self.assertIn(Constants.ERROR_ADDED_TO_STATUS, repr(context.exception))
        self.assertEqual(context.exception.args[1], "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

    def raise_ex(self):
        raise Exception()
    
    def mock_refresh_repo(self):
        pass


if __name__ == '__main__':
    unittest.main()
