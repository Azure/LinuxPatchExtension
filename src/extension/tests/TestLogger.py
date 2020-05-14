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

""" Unit test for Logger """
import shutil
import tempfile
import unittest
from os import path
from src.local_loggers.FileLogger import FileLogger
from src.local_loggers.Logger import Logger
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestLogger(unittest.TestCase):

    # setup
    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------\n")
        self.test_dir = tempfile.mkdtemp()
        self.file_path = path.join(self.test_dir, 'test.txt')
        self.file_logger = FileLogger(self.test_dir, 'test.txt')
        self.logger = Logger(self.file_logger)

    # teardown
    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")
        shutil.rmtree(self.test_dir)

    def test_log(self):
        self.logger.log("Test message")
        self.file_logger.close()
        file_read = open(self.file_path, "r")
        self.assertTrue(file_read is not None)
        self.assertTrue("Test message" in file_read.readlines()[-1])
        file_read.close()

    def test_log_verbose(self):
        self.logger.log_verbose("Test verbose message")
        self.file_logger.close()
        file_read = open(self.file_path, "r")
        self.assertTrue(file_read is not None)
        self.assertTrue(self.logger.VERBOSE + " Test verbose message" in file_read.readlines()[-1])
        file_read.close()

    def test_log_error(self):
        self.logger.log_error("Test error message")
        self.file_logger.close()
        file_read = open(self.file_path, "r")
        self.assertTrue(file_read is not None)
        self.assertTrue(self.logger.ERROR + " Test error message" in file_read.readlines()[-1])
        file_read.close()

    def test_log_warning(self):
        self.logger.log_warning("Test warning message")
        self.file_logger.close()
        file_read = open(self.file_path, "r")
        self.assertTrue(file_read is not None)
        self.assertTrue(self.logger.WARNING + " Test warning message" in file_read.readlines()[-1])
        file_read.close()

    def test_log_debug(self):
        self.logger.log_debug("Test debug message")
        self.file_logger.close()
        file_read = open(self.file_path, "r")
        self.assertTrue(file_read is not None)
        self.assertTrue(self.logger.DEBUG + " Test debug message" in file_read.readlines()[-1])
        file_read.close()

if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestLogger)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
