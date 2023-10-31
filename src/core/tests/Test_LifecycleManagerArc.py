# Copyright 2020 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.7+

import os
import unittest
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor
from core.src.bootstrap.Constants import Constants

# Retaining Azure unit tests here as they are still valid scenarios for arc as well. In addition to that added tests for arc scenarios
#  ARC core file path not found, unable to read core file , exit when arc process is still running, continue when arc process is completed

class TestLifecycleManagerArc(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer(Constants.CloudType.ARC).get_composed_arguments(), True, Constants.APT, Constants.CloudType.ARC)
        self.container = self.runtime.container
        self.lifecycle_manager = self.runtime.lifecycle_manager

    def tearDown(self):
        self.runtime.stop()

    def test_lifestyle_status_check(self):
        # No change in Extension sequence number
        self.lifecycle_manager.lifecycle_status_check()

        # Extension sequence number changed
        old_core_sequence_json = self.lifecycle_manager.read_core_sequence()
        self.runtime.execution_config.sequence_number = 2
        with self.assertRaises(SystemExit):
            self.lifecycle_manager.lifecycle_status_check()
        new_core_sequence_json = self.lifecycle_manager.read_core_sequence()
        self.assertNotEqual(old_core_sequence_json["completed"], new_core_sequence_json["completed"])

    def test_read_extension_sequence_fail(self):
        old_ext_state_file_path = self.lifecycle_manager.ext_state_file_path

        # File not found at location
        self.lifecycle_manager.ext_state_file_path = "dummy"
        self.assertRaises(Exception, self.lifecycle_manager.read_extension_sequence)

        # file open throws exception
        self.lifecycle_manager.ext_state_file_path = old_ext_state_file_path
        self.runtime.env_layer.file_system.open = self.mock_file_open_throw_exception
        ext_state_json = self.assertRaises(Exception, self.lifecycle_manager.read_extension_sequence)
        self.assertEqual(ext_state_json, None)

    def test_read_extension_sequence_success(self):
        ext_state_json = self.lifecycle_manager.read_extension_sequence()
        self.assertTrue(ext_state_json is not None)
        self.assertTrue("achieveEnableBy" in str(ext_state_json))

    def test_read_core_sequence_fail(self):
        # file open throws exception
        self.runtime.env_layer.file_system.open = self.mock_file_open_throw_exception
        core_sequence_json = self.assertRaises(Exception, self.lifecycle_manager.read_core_sequence)
        self.assertEqual(core_sequence_json, None)

    def test_read_core_sequence_success(self):
        old_core_state_file_path = self.lifecycle_manager.core_state_file_path

        # file path is dir
        if os.path.exists(self.lifecycle_manager.core_state_file_path) and os.path.isfile(self.lifecycle_manager.core_state_file_path):
            os.remove(self.lifecycle_manager.core_state_file_path)
        dummy_folder = os.path.join(self.runtime.execution_config.config_folder, "CoreExt_lifecycle_manager_test")
        os.mkdir(dummy_folder)
        self.lifecycle_manager.core_state_file_path = dummy_folder
        core_sequence_json = self.lifecycle_manager.read_core_sequence()
        self.assertTrue(core_sequence_json is not None)
        self.assertTrue("processIds" in str(core_sequence_json))
        os.remove(self.lifecycle_manager.core_state_file_path)
        self.lifecycle_manager.core_state_file_path = old_core_state_file_path

        # file not found at location
        if os.path.exists(self.lifecycle_manager.core_state_file_path) and os.path.isfile(self.lifecycle_manager.core_state_file_path):
            os.remove(self.lifecycle_manager.core_state_file_path)
        core_sequence_json = self.lifecycle_manager.read_core_sequence()
        self.assertTrue(core_sequence_json is not None)
        self.assertTrue("processIds" in str(core_sequence_json))
        os.remove(self.lifecycle_manager.core_state_file_path)

    def test_update_core_sequence_fail(self):
        # file open throws exception
        self.runtime.env_layer.file_system.open = self.mock_file_open_throw_exception
        core_sequence_json = self.lifecycle_manager.update_core_sequence()
        self.assertEqual(core_sequence_json, None)

    def test_update_core_sequence_success(self):    # failing test - needs to be corrected with Arc code changes
        old_core_state_file_path = self.lifecycle_manager.core_state_file_path

        # file path is dir
        if os.path.exists(self.lifecycle_manager.core_state_file_path) and os.path.isfile(self.lifecycle_manager.core_state_file_path):
            os.remove(self.lifecycle_manager.core_state_file_path)
        dummy_folder = os.path.join(self.runtime.execution_config.config_folder, "CoreExt_lifecycle_manager_test")
        os.mkdir(dummy_folder)
        self.lifecycle_manager.core_state_file_path = dummy_folder
        self.lifecycle_manager.read_only_mode = False
        self.lifecycle_manager.update_core_sequence()
        self.assertTrue(os.path.exists(self.lifecycle_manager.core_state_file_path) and os.path.isfile(self.lifecycle_manager.core_state_file_path))
        core_sequence_json = self.lifecycle_manager.read_core_sequence()
        self.assertTrue(core_sequence_json is not None)
        self.assertTrue("processIds" in str(core_sequence_json))
        os.remove(self.lifecycle_manager.core_state_file_path)
        self.lifecycle_manager.core_state_file_path = old_core_state_file_path

        # file doesn't already exist
        if os.path.exists(self.lifecycle_manager.core_state_file_path) and os.path.isfile(self.lifecycle_manager.core_state_file_path):
            os.remove(self.lifecycle_manager.core_state_file_path)
        self.lifecycle_manager.update_core_sequence()
        self.assertTrue(os.path.exists(self.lifecycle_manager.core_state_file_path) and os.path.isfile(self.lifecycle_manager.core_state_file_path))
        core_sequence_json = self.lifecycle_manager.read_core_sequence()
        self.assertTrue(core_sequence_json is not None)
        self.assertTrue("processIds" in str(core_sequence_json))

        # file already exists
        old_core_sequence_json = self.lifecycle_manager.read_core_sequence()
        self.lifecycle_manager.update_core_sequence(completed=True)
        new_core_sequence_json = self.lifecycle_manager.read_core_sequence()
        self.assertNotEqual(old_core_sequence_json["completed"], new_core_sequence_json["completed"])
        os.remove(self.lifecycle_manager.core_state_file_path)

    def test_read_arc_core_sequence_fail(self):     # failing test - needs to be corrected with Arc code changes
        old_core_state_file_path = self.lifecycle_manager.core_state_file_path
        # File not found at location
        self.lifecycle_manager.arc_core_state_file_path = "dummy"
        self.lifecycle_manager.read_only_mode = False
        ext_state_json = self.lifecycle_manager.read_arc_core_sequence()
        self.assertEqual(ext_state_json['completed'], 'True')

        self.lifecycle_manager.arc_core_state_file_path = old_core_state_file_path
        self.lifecycle_manager.update_core_sequence(completed=True)
        # file open throws exception
        self.runtime.env_layer.file_system.open = self.mock_file_open_throw_exception
        self.assertRaises(Exception, self.lifecycle_manager.read_arc_core_sequence)

    def test_read_arc_core_sequence_success(self):  # failing test - needs to be corrected with Arc code changes
        self.lifecycle_manager.arc_core_state_file_path = self.lifecycle_manager.core_state_file_path
        self.lifecycle_manager.read_only_mode = False
        self.lifecycle_manager.update_core_sequence(completed=True)
        # Completed True Case
        arc_core_state = self.lifecycle_manager.read_arc_core_sequence()
        self.assertEqual(arc_core_state['completed'], 'True')

        # Completed False Case
        self.lifecycle_manager.update_core_sequence(completed=False)
        arc_core_state = self.lifecycle_manager.read_arc_core_sequence()
        self.assertEqual(arc_core_state['completed'], 'False')
        os.remove(self.lifecycle_manager.core_state_file_path)

    def mock_file_open_throw_exception(self, file_path, mode):
        raise Exception("Mock file read exception")

    def mock_get_arc_core_file_path(self):
        return self.lifecycle_manager.core_state_file_path


if __name__ == '__main__':
    unittest.main()