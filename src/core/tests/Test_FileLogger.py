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
        self.contents = ""
        self.closed = False
    
    def write(self, message):
        if self.raise_on_write:
            raise Exception("Mock write exception")
        self.contents += message
    
    def flush(self):
        pass

    def close(self):
        self.closed = True

    def fileno(self):
        return 1


class MockFileSystem:
    def open(self, file_path, mode):
        return MockFileHandle()


class MockEnvLayer:
    def __init__(self):
        self.file_system = MockFileSystem()
        self.datetime = self
    
    def timestampe(self):
        return "2025-01-01T00:00:00Z"


class TestFileLogger(unittest.TestCase):
    def setUp(self):
        self.mock_env_layer = MockEnvLayer()
        self.log_file = "test.log"
        self.file_logger = FileLogger(self.mock_env_layer, self.log_file)
    
    def test_write(self):
        message = "Test message"
        self.file_logger.write(message)
        self.assertEqual(self.file_logger.log_file_handle.contents, message)

    def test_no_truncation(self):
        message = "No truncation"
        result = self.file_logger.truncate_message(message)
        self.assertEqual(result, message)
    
    def test_write_truncated_message(self):
        message = "A" * (32 * 1024 * 1024 - 10) + "\nExtra line.\n"  # 32MB - 10 bytes to include newlines
        truncate_message = self.file_logger.truncate_message(message)
        self.file_logger.write(message)
        self.assertTrue(truncate_message.endswith("\n"))
        self.assertTrue(len(truncate_message) < (32 * 1024 * 1024 + 1))
        self.assertIn(truncate_message, self.file_logger.log_file_handle.contents)
        self.assertNotIn(message, self.file_logger.log_file_handle.contents)

    def test_write_silent_failure(self):
        self.file_logger.log_file_handle = MockFileHandle(raise_on_write=True)
        try:
            self.file_logger.write("Test message", fail_silently=True)
        except Exception:
            self.fail("raise an exception when fail_silently=True")

    def test_write_non_silent_failure(self):
        self.file_logger.log_file_handle = MockFileHandle(raise_on_write=True)

        with self.assertRaises(Exception) as context:
            self.file_logger.write("test message", fail_silently=False)

        self.assertIn("Fatal exception trying to write to log file", str(context.exception))


if __name__ == '__main__':
    unittest.main()