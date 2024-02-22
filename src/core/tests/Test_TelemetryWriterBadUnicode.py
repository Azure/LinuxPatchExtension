# -*- coding: utf-8 -*-
# Copyright 2024 Microsoft Corporation
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
import json
import os
import re
import unittest

from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestTelemetryWriterBadUnicode(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True)

    def tearDown(self):
        self.runtime.stop()

    def test_write_event_msg_size_limit_char_with_actual_unicode_str(self):
        """ Perform 1 byte truncation on unicode str that is more than 1 byte, use decode('utf-8', errors='replace') to replace bad unicode with a good 1 byte char (�) """
        message = u"a€bc"*3074  # €(\xe2\x82\xac) is 3 bytes char can be written in windows console w/o encoding
        self.__assert_write_event_msg_size_limit_char(message)

    def test_write_event_msg_size_limit_char_with_unicode_point(self):
        """ Perform 1 byte truncation on unicode code point str that is more than 1 byte, use decode('utf-8', errors='replace') to replace bad unicode with a good 1 byte char (�) """
        message = u"a\u20acbc"*3074  # unicode code point €(\xe2\x82\xac) is 3 bytes char can be written in windows console w/o encoding
        self.__assert_write_event_msg_size_limit_char(message)

    def __assert_write_event_msg_size_limit_char(self, message):
        self.runtime.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error, "Test Task")
        latest_event_file = [pos_json for pos_json in os.listdir(self.runtime.telemetry_writer.events_folder_path) if re.search('^[0-9]+.json$', pos_json)][-1]
        with open(os.path.join(self.runtime.telemetry_writer.events_folder_path, latest_event_file), 'r+') as f:
            events = json.load(f)
            self.assertTrue(events is not None)
            self.assertEqual(events[-1]["TaskName"], "Test Task")
            self.assertTrue(len(events[-1]["Message"]) < len(message.encode('utf-8')))
            chars_dropped = len(message.encode('utf-8')) - Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_CHARS + Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_CHARS + Constants.TELEMETRY_EVENT_COUNTER_MSG_SIZE_LIMIT_IN_CHARS
            self.assertTrue(u"a\u20acbc" in events[-1]["Message"])
            self.assertTrue(u"a\u20acb c" * (len(message) + 1 - chars_dropped) + ". [{0} chars dropped]".format(chars_dropped) in events[-1]["Message"])  # len(message) + 1 due to bad unicode will be replaced by �
            f.close()


if __name__ == '__main__':
    unittest.main()

