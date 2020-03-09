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
        self.assertIsNotNone(file_read)
        self.assertIn("Test message", file_read.readlines()[-1])
        file_read.close()

    def test_log_verbose(self):
        self.logger.log_verbose("Test verbose message")
        self.file_logger.close()
        file_read = open(self.file_path, "r")
        self.assertIsNotNone(file_read)
        self.assertIn(self.logger.VERBOSE + " Test verbose message", file_read.readlines()[-1])
        file_read.close()

    def test_log_error(self):
        self.logger.log_error("Test error message")
        self.file_logger.close()
        file_read = open(self.file_path, "r")
        self.assertIsNotNone(file_read)
        self.assertIn(self.logger.ERROR + " Test error message", file_read.readlines()[-1])
        file_read.close()

    def test_log_warning(self):
        self.logger.log_warning("Test warning message")
        self.file_logger.close()
        file_read = open(self.file_path, "r")
        self.assertIsNotNone(file_read)
        self.assertIn(self.logger.WARNING + " Test warning message", file_read.readlines()[-1])
        file_read.close()

    def test_log_debug(self):
        self.logger.log_debug("Test debug message")
        self.file_logger.close()
        file_read = open(self.file_path, "r")
        self.assertIsNotNone(file_read)
        self.assertIn(self.logger.DEBUG + " Test debug message", file_read.readlines()[-1])
        file_read.close()

if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestLogger)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
