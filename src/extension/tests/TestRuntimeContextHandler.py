import collections
import datetime
import os
import unittest
from unittest import mock
from src.Constants import Constants
from src.RuntimeContextHandler import RuntimeContextHandler
from src.file_handlers.CoreStateHandler import CoreStateHandler
from src.file_handlers.JsonFileHandler import JsonFileHandler
from src.local_loggers.Logger import Logger
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestRuntimeContextHandler(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.logger = Logger()
        self.json_file_handler = JsonFileHandler(self.logger)
        self.runtime_context_handler = RuntimeContextHandler(self.logger)
        self.core_state_fields = Constants.CoreStateFields

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    @mock.patch('src.RuntimeContextHandler.time.sleep', autospec=True)
    def test_check_if_patch_completes_in_time(self, time_sleep):
        core_state_handler = CoreStateHandler(os.path.join(os.path.pardir, "tests", "helpers"), self.json_file_handler)
        time_for_prev_patch_to_complete = ""
        self.assertRaises(Exception, self.runtime_context_handler.check_if_patch_completes_in_time, time_for_prev_patch_to_complete, core_state_handler)

        time_for_prev_patch_to_complete = datetime.datetime.utcnow() + datetime.timedelta(hours=0, minutes=3)
        self.assertTrue(self.runtime_context_handler.check_if_patch_completes_in_time(time_for_prev_patch_to_complete, "2019-07-20T12:12:14Z",  core_state_handler))
        # time_sleep is called once while waiting for prev patch and once while reading core state file after wait to get the latest status, hence the count 2
        self.assertEqual(time_sleep.call_count, 2)

        time_sleep.call_count = 0
        datetime.datetime = MockDateTime
        time_for_prev_patch_to_complete = datetime.datetime.utcnow() + datetime.timedelta(hours=0, minutes=3)
        core_state_values = collections.namedtuple(Constants.CoreStateFields.parent_key, [self.core_state_fields.number, self.core_state_fields.action, self.core_state_fields.completed, self.core_state_fields.last_heartbeat, self.core_state_fields.process_ids])
        core_state_json = core_state_values(1234, "Assessment", "False", "2019-07-20T12:12:14Z", [])

        with mock.patch("tests.TestRuntimeContextHandler.CoreStateHandler.read_file", autospec=True, return_value=core_state_json):
            with mock.patch("src.RuntimeContextHandler.datetime.datetime.utcnow", autospec=True,
                            side_effect=[datetime.datetime(2019, 11, 1, 13, 24, 00),
                                         datetime.datetime(2019, 11, 1, 13, 25, 00),
                                         datetime.datetime(2019, 11, 1, 13, 26, 00),
                                         datetime.datetime(2019, 11, 1, 13, 27, 00)]):
                with mock.patch("src.RuntimeContextHandler.type", return_value=MockDateTime):
                    self.assertFalse(
                        self.runtime_context_handler.check_if_patch_completes_in_time(time_for_prev_patch_to_complete, "2019-07-20T12:12:14Z", core_state_handler))

class MockDateTime(datetime.datetime):
    @classmethod
    def utcnow(cls):
        return cls(2019, 11, 1, 13, 24, 00)

if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestRuntimeContextHandler)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
