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

import collections
import datetime
import os
import unittest
from extension.src.Constants import Constants
from extension.src.RuntimeContextHandler import RuntimeContextHandler
from extension.src.file_handlers.CoreStateHandler import CoreStateHandler
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestRuntimeContextHandler(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        runtime = RuntimeComposer()
        self.json_file_handler = runtime.json_file_handler
        self.runtime_context_handler = RuntimeContextHandler(runtime.logger)
        self.core_state_fields = Constants.CoreStateFields

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def test_check_if_patch_completes_in_time(self):
        core_state_handler = CoreStateHandler(os.path.join(os.path.pardir, "tests", "helpers"), self.json_file_handler)
        # Unable to identify wait time
        time_for_prev_patch_to_complete = ""
        self.assertRaises(Exception, self.runtime_context_handler.check_if_patch_completes_in_time, time_for_prev_patch_to_complete, core_state_handler)

        # patch complete
        time_for_prev_patch_to_complete = datetime.datetime.utcnow() + datetime.timedelta(hours=0, minutes=3)
        self.assertTrue(self.runtime_context_handler.check_if_patch_completes_in_time(time_for_prev_patch_to_complete, "2019-07-20T12:12:14Z",  core_state_handler))

        # patch still incomplete after wait
        time_for_prev_patch_to_complete = datetime.datetime.utcnow() + datetime.timedelta(hours=0, minutes=0, seconds=0.01)
        core_state_read_backup = CoreStateHandler.read_file
        CoreStateHandler.read_file = self.mock_read_core_state_operation_incomplete
        print(type(time_for_prev_patch_to_complete))
        self.assertFalse(
                self.runtime_context_handler.check_if_patch_completes_in_time(time_for_prev_patch_to_complete, "2019-07-20T12:12:14Z", core_state_handler))

        CoreStateHandler.read_file = core_state_read_backup

    def mock_read_core_state_operation_incomplete(self):
        core_state_values = collections.namedtuple(Constants.CoreStateFields.parent_key, [self.core_state_fields.number, self.core_state_fields.action, self.core_state_fields.completed, self.core_state_fields.last_heartbeat, self.core_state_fields.process_ids])
        core_state_json = core_state_values(1234, "Assessment", "False", "2019-07-20T12:12:14Z", [])
        return core_state_json


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestRuntimeContextHandler)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
