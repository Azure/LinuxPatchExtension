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

""" Unit test for FileLogger """
import shutil
import tempfile
import time
import unittest
from datetime import datetime
import os
from os import path

from extension.src.Constants import Constants
from extension.src.local_loggers.FileLogger import FileLogger
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestFileLogger(unittest.TestCase):

    # setup
    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------\n")
        self.test_dir = tempfile.mkdtemp()
        self.file_path = path.join(self.test_dir, 'test.log')
        self.file_logger = FileLogger(self.test_dir, 'test.log')

    # teardown
    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")
        shutil.rmtree(self.test_dir)

    def test_file_open(self):
        self.assertTrue(self.file_logger.log_file_handle is not None)
        self.file_logger.close()

    def test_write_file_not_found_exception(self):
        self.file_logger.close()
        self.file_logger.log_file_handle = None
        self.file_logger.write("Test log")
        self.assertRaises(Exception)

    def test_write(self):
        self.file_logger.write("Test log")
        self.file_logger.close()
        file_read = open(self.file_path, "r")
        self.assertTrue(file_read is not None)
        self.assertTrue("Test log" in file_read.readlines()[-1])
        file_read.close()

    def test_flush(self):
        self.file_logger.write("flush this")
        self.file_logger.flush()
        file_read = open(self.file_path, "r")
        self.assertTrue(file_read is not None)
        self.assertTrue("flush this" in file_read.readlines()[-1])
        file_read.close()
        self.file_logger.close()

    def test_close(self):
        self.file_logger.close()
        self.assertTrue(self.file_logger.log_file_handle is None)

    def test_delete_older_log_files_success(self):
        files = [
            {"name": '1.ext.log', "lastModified": '2019-07-20T12:12:14Z'},  # reverse sort order seqno: 1
            {"name": '121.ext.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 7
            {"name": '122.ext.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 8
            {"name": '123.ext.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 9
            {"name": '124.ext.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 10
            {"name": '125.ext.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 11
            {"name": '126.ext.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 12
            {"name": '127.ext.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 13
            {"name": 'test1.ext.log', "lastModified": '2017-07-21T12:12:14Z'},  # testing with the current log file, reverse sort order seqno: 14
            {"name": 'test2.ext.log', "lastModified": '2017-07-21T12:12:14Z'},  # testing with the current log file, reverse sort order seqno: 15
            {"name": 'tes3.ext.log', "lastModified": '2017-07-21T12:12:14Z'},  # testing with the current log file, reverse sort order seqno: 16
            {"name": 'test4.ext.log', "lastModified": '2017-07-21T12:12:14Z'},  # testing with the current log file, reverse sort order seqno: 17
            {"name": 'test5.ext.log', "lastModified": '2017-07-21T12:12:14Z'},  # testing with the current log file, reverse sort order seqno: 18
            {"name": '123.json', "lastModified": '2019-07-20T11:12:14Z'},
            {"name": '10.settings', "lastModified": '2019-07-20T10:12:14Z'},
            {"name": '111.txt', "lastModified": '2019-07-20T12:10:14Z'},
            {"name": '12.ext.log', "lastModified": '2019-07-02T12:12:14Z'},  # reverse sort order seqno: 6
            {"name": 'dir1', "lastModified": '2019-07-20T12:12:14Z'},
            {"name": '111111', "lastModified": '2019-07-20T12:12:14Z'},
            {"name": '2.ext.log', "lastModified": '2019-07-20T12:12:12Z'},  # reverse sort order seqno: 5
            {"name": '22.ext.log.log', "lastModified": '2019-07-20T12:12:14Z'},  # reverse sort order seqno: 2
            {"name": 'abc.123.ext.log', "lastModified": '2019-07-20T12:12:14Z'},  # reverse sort order seqno: 3
            {"name": '.ext.log', "lastModified": '2019-07-20T12:12:14Z'},  # reverse sort order seqno: 4

            {"name": '1.core.log', "lastModified": '2019-07-20T12:12:14Z'},  # reverse sort order seqno: 1
            {"name": '121.core.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 7
            {"name": '122.core.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 8
            {"name": '123.core.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 9
            {"name": '124.core.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 10
            {"name": '125.core.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 11
            {"name": '126.core.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 12
            {"name": '127.core.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 13
            {"name": 'test1.core.log', "lastModified": '2017-07-21T12:12:14Z'},  # testing with the current log file, reverse sort order seqno: 14
            {"name": 'test2.core.log', "lastModified": '2017-07-21T12:12:14Z'},  # testing with the current log file, reverse sort order seqno: 15
            {"name": 'tes3.core.log', "lastModified": '2017-07-21T12:12:14Z'},  # testing with the current log file, reverse sort order seqno: 16
            {"name": 'test4.core.log', "lastModified": '2017-07-21T12:12:14Z'},  # testing with the current log file, reverse sort order seqno: 17
            {"name": 'test5.core.log', "lastModified": '2017-07-21T12:12:14Z'},  # testing with the current log file, reverse sort order seqno: 18
            {"name": '123.json', "lastModified": '2019-07-20T11:12:14Z'},
            {"name": '10.settings', "lastModified": '2019-07-20T10:12:14Z'},
            {"name": '111.txt', "lastModified": '2019-07-20T12:10:14Z'},
            {"name": '12.core.log', "lastModified": '2019-07-02T12:12:14Z'},  # reverse sort order seqno: 6
            {"name": 'dir1', "lastModified": '2019-07-20T12:12:14Z'},
            {"name": '111111', "lastModified": '2019-07-20T12:12:14Z'},
            {"name": '2.core.log', "lastModified": '2019-07-20T12:12:12Z'},  # reverse sort order seqno: 5
            {"name": '22.core.log.log', "lastModified": '2019-07-20T12:12:14Z'},  # reverse sort order seqno: 2
            {"name": 'abc.123.core.log', "lastModified": '2019-07-20T12:12:14Z'},  # reverse sort order seqno: 3
            {"name": '.core.log', "lastModified": '2019-07-20T12:12:14Z'}  # reverse sort order seqno: 4
        ]

        for file in files:
            file_path = os.path.join(self.test_dir, file["name"])
            with open(file_path, 'w') as f:
                timestamp = time.mktime(datetime.strptime(file["lastModified"], Constants.UTC_DATETIME_FORMAT).timetuple())
                os.utime(file_path, (timestamp, timestamp))
                f.close()

        # modifying timestamp format of 127.log, to test with a diff time format
        file_path = os.path.join(self.test_dir, "127.log")
        with open(file_path, 'w') as f:
            timestamp = time.mktime(datetime.strptime("21-07-2017T12:12:14Z", '%d-%m-%YT%H:%M:%SZ').timetuple())
            os.utime(file_path, (timestamp, timestamp))
            f.close()

        self.file_logger.delete_older_log_files(self.test_dir)
        self.assertEqual(15, len(self.file_logger.get_all_log_files(self.test_dir, Constants.CORE_MODULE)))
        self.assertEqual(15, len(self.file_logger.get_all_log_files(self.test_dir, Constants.EXTENSION_MODULE)))
        self.file_logger.close()


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestFileLogger)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
