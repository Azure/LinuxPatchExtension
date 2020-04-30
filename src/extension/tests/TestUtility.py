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
import shutil
import tempfile
import unittest
from unittest import mock
from src.Constants import Constants
from src.file_handlers.JsonFileHandler import JsonFileHandler
from src.file_handlers.CoreStateHandler import CoreStateHandler
from src.local_loggers.Logger import Logger
from src.Utility import Utility
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestUtility(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.logger = Logger()
        self.utility = Utility(self.logger)
        self.json_file_handler = JsonFileHandler(self.logger)

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    @mock.patch('src.Utility.time.sleep', autospec=True)
    def test_delete_file_success(self, time_sleep):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file_path = os.path.join(test_dir, "test.json")
        # create a file
        test_file_handler = open(file_path, 'w')
        test_file_handler.close()
        # delete file
        self.utility.delete_file(test_dir, "test.json")
        # once the file is deleted, os.path.exists on the ful file path will return False
        self.assertFalse(os.path.exists(file_path))
        time_sleep.assert_called_once()
        # Remove the directory after the test
        shutil.rmtree(test_dir)

    @mock.patch('src.Utility.time.sleep', autospec=True)
    def test_delete_file_failure(self, time_sleep):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file_path = os.path.join(test_dir, "test.json")
        # create a file
        test_file_handler = open(file_path, 'w')
        test_file_handler.close()

        # FileNotFound
        self.assertRaises(Exception, self.utility.delete_file, test_dir, "test1.json")

        # test with a directory
        file_path = os.path.join(test_dir, "test")
        # create a directory
        os.makedirs(file_path)
        self.assertRaises(Exception, self.utility.delete_file, test_dir, "test")

        with mock.patch('src.Utility.os.remove', autospec=True) as mock_remove:
            # 1st delete trial failed
            mock_remove.side_effect = [OSError, None]
            self.utility.delete_file(test_dir, "test.json")
            self.assertEqual(time_sleep.call_count, 2)
            self.assertEqual(mock_remove.call_count, 2)

            # 2nd delete trial failed
            time_sleep.call_count = 0
            mock_remove.call_count = 0
            mock_remove.side_effect = [OSError, OSError, None]
            self.utility.delete_file(test_dir, "test.json")
            self.assertEqual(time_sleep.call_count, 3)
            self.assertEqual(mock_remove.call_count, 3)

            # 3rd delete trial failed
            time_sleep.call_count = 0
            mock_remove.call_count = 0
            mock_remove.side_effect = [OSError, Exception, OSError, None]
            self.utility.delete_file(test_dir, "test.json")
            self.assertEqual(time_sleep.call_count, 4)
            self.assertEqual(mock_remove.call_count, 4)

            # 4th delete trial failed
            time_sleep.call_count = 0
            mock_remove.call_count = 0
            mock_remove.side_effect = [OSError, Exception, OSError, OSError, None]
            self.utility.delete_file(test_dir, "test.json")
            self.assertEqual(time_sleep.call_count, 5)
            self.assertEqual(mock_remove.call_count, 5)

            # All delete trial failed
            time_sleep.call_count = 0
            mock_remove.call_count = 0
            mock_remove.side_effect = [OSError, Exception, OSError, OSError, OSError]
            self.assertRaises(Exception, self.utility.delete_file, test_dir, "test.json")
            self.assertEqual(time_sleep.call_count, 5)
            self.assertEqual(mock_remove.call_count, 5)

        # Remove the directory after the test
        shutil.rmtree(test_dir)
