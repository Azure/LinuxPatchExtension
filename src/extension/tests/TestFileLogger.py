""" Unit test for FileLogger """
import shutil
import tempfile
import time
import unittest
from datetime import datetime
import os
from os import path
from src.local_loggers.FileLogger import FileLogger
from tests.helpers.VirtualTerminal import VirtualTerminal


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
        self.assertIsNotNone(self.file_logger.log_file_handle)
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
        self.assertIsNotNone(file_read)
        self.assertIn("Test log", file_read.readlines()[-1])
        file_read.close()

    def test_flush(self):
        self.file_logger.write("flush this")
        self.file_logger.flush()
        file_read = open(self.file_path, "r")
        self.assertIsNotNone(file_read)
        self.assertIn("flush this", file_read.readlines()[-1])
        file_read.close()
        self.file_logger.close()

    def test_close(self):
        self.file_logger.close()
        self.assertTrue(self.file_logger.log_file_handle.closed)
        # with self.assertRaises(ValueError):
        #     self.file_logger.write("write in closed file")

    def test_delete_older_log_files_success(self):
        files = [
            {"name": '1.ext.log', "lastModified": '2019-07-20T12:12:14Z'},  # reverse sort order seqno: 1
            {"name": '121.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 7
            {"name": '122.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 8
            {"name": '123.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 9
            {"name": '124.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 10
            {"name": '125.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 11
            {"name": '126.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 12
            {"name": '127.log', "lastModified": '2017-07-21T12:12:14Z'},  # reverse sort order seqno: 13
            {"name": 'test.log', "lastModified": '2017-07-21T12:12:14Z'},  # testing with the current log file, reverse sort order seqno: 14
            {"name": '123.json', "lastModified": '2019-07-20T11:12:14Z'},
            {"name": '10.settings', "lastModified": '2019-07-20T10:12:14Z'},
            {"name": '111.txt', "lastModified": '2019-07-20T12:10:14Z'},
            {"name": '12.core.log', "lastModified": '2019-07-02T12:12:14Z'},  # reverse sort order seqno: 6
            {"name": 'dir1', "lastModified": '2019-07-20T12:12:14Z'},
            {"name": '111111', "lastModified": '2019-07-20T12:12:14Z'},
            {"name": '2.core.log', "lastModified": '2019-07-20T12:12:12Z'},  # reverse sort order seqno: 5
            {"name": '22.log.log', "lastModified": '2019-07-20T12:12:14Z'},  # reverse sort order seqno: 2
            {"name": 'abc.123.log', "lastModified": '2019-07-20T12:12:14Z'},  # reverse sort order seqno: 3
            {"name": '.log', "lastModified": '2019-07-20T12:12:14Z'}  # reverse sort order seqno: 4
        ]

        for file in files:
            file_path = os.path.join(self.test_dir, file["name"])
            with open(file_path, 'w') as f:
                timestamp = time.mktime(datetime.strptime(file["lastModified"], '%Y-%m-%dT%H:%M:%S%z').timetuple())
                os.utime(file_path, (timestamp, timestamp))
                f.close()

        # modifying timestamp format of 127.log, to test with a diff time format
        file_path = os.path.join(self.test_dir, "127.log")
        with open(file_path, 'w') as f:
            timestamp = time.mktime(datetime.strptime("21-07-2017T12:12:14Z", '%d-%m-%YT%H:%M:%S%z').timetuple())
            os.utime(file_path, (timestamp, timestamp))
            f.close()

        self.file_logger.delete_older_log_files(self.test_dir)
        self.assertEqual(11, len(self.file_logger.get_all_log_files(self.test_dir)))
        self.file_logger.close()


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestFileLogger)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
