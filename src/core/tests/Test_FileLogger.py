# Copyright 2025 Microsoft Corporation
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
import unittest
from core.src.local_loggers.FileLogger import FileLogger


class MockFileHandle:
    def __init__(self, raise_on_write=False):
        self.raise_on_write = raise_on_write
        self.flushed = False
        self.fileno_called = False
        self.contents = ""
        self.closed = False
    
    def write(self, message):
        if self.raise_on_write:
            raise Exception("Mock write exception")
        self.contents += message
    
    def flush(self):
        self.flushed = True

    def fileno(self):
        self.fileno_called = True
        return 1  # mock file

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class MockFileSystem:
    def __init__(self):
        self.files = {}

    def open(self, file_path, mode):
        if "error" in file_path:
            raise Exception("Mock file open error")

        if file_path not in self.files:
            self.files[file_path] = MockFileHandle()

        return self.files[file_path]


class MockEnvLayer:
    def __init__(self):
        self.file_system = MockFileSystem()
        self.datetime = self
    
    def timestamp(self):
        return "2025-01-01T00:00:00Z"


class TestFileLogger(unittest.TestCase):
    def setUp(self):
        self.mock_env_layer = MockEnvLayer()
        self.log_file = "test.log"
        self.file_logger = FileLogger(self.mock_env_layer, self.log_file)

    def test_init_failure(self):
        """ Test when initiation object file open throws exception """
        self.mock_env_layer.file_system.open = lambda *args, **kwargs: (_ for _ in ()).throw(Exception("Mock file open error"))
        with self.assertRaises(Exception) as context:
            FileLogger(self.mock_env_layer, "error_log.log")

        self.assertIn("Mock file open error", str(context.exception))
    
    def test_write(self):
        """ Test FileLogger write()  """
        message = "Test message"
        self.file_logger.write(message)
        self.assertEqual(self.file_logger.log_file_handle.contents, message)

    def test_write_message_no_truncation(self):
        """ Test FileLogger truncate_message() no truncation"""
        message = "No truncation"
        result = self.file_logger.truncate_message(message)
        self.assertEqual(result, message)

    def test_write_message_apply_truncation(self):
        """ Test FileLogger truncate_message() truncation apply  """
        msg_max_size = len("A" * (32 * 1024 * 1024))  # 32 MB
        message = "A" * (32 * 1024 * 1024 + 1)  # 33MB
        truncate_message = self.file_logger.truncate_message(message)
        self.assertEqual(len(truncate_message), msg_max_size)
    
    def test_write_message_with_newline(self):
        """ Test FileLogger truncate_message() truncation apply with newline """
        message = "A" * (32 * 1024 * 1024 - 10) + "\nExtra line.\n"  # 32MB with newlines
        truncate_message = self.file_logger.truncate_message(message)
        self.file_logger.write(message)
        self.assertTrue(truncate_message.endswith("\n"))
        self.assertTrue(len(truncate_message) < (32 * 1024 * 1024 + 1))
        self.assertIn(truncate_message, self.file_logger.log_file_handle.contents)
        self.assertNotIn(message, self.file_logger.log_file_handle.contents)

    def test_write_false_silent_failure(self):
        """ Test FileLogger write(), throws exception raise_on_write is true """
        self.file_logger.log_file_handle = MockFileHandle(raise_on_write=True)

        with self.assertRaises(Exception) as context:
            self.file_logger.write("test message", fail_silently=False)

        self.assertIn("Fatal exception trying to write to log file", str(context.exception))

    def test_write_irrecoverable_exception(self):
        """ Test FileLogger write_irrecoverable_exception write failure log """
        message = "test message"
        self.file_logger.write_irrecoverable_exception(message)

        self.assertIn(self.file_logger.log_failure_log_file, self.mock_env_layer.file_system.files)

        failure_log = self.mock_env_layer.file_system.files[self.file_logger.log_failure_log_file]
        expected_output = "\n2025-01-01T00:00:00Z> test message"

        self.assertIn(expected_output, failure_log.contents)

    def test_write_irrecoverable_exception_failure(self):
        """ Test FileLogger write_irrecoverable_exception exception raised """
        self.file_logger.log_failure_log_file = "error_failure_log.log"
        message = "test message"

        self.file_logger.write_irrecoverable_exception(message)

        self.assertNotIn("error_failure_log.log", self.mock_env_layer.file_system.files)

    def test_flush_success(self):
        """ Test FileLogger flush() and fileno() are called"""
        self.file_logger.flush()

        self.assertTrue(self.file_logger.log_file_handle.flushed)
        self.assertTrue(self.file_logger.log_file_handle.fileno_called)


if __name__ == '__main__':
    unittest.main()
