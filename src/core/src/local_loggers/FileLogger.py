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
import os
import sys


class FileLogger(object):
    """Facilitates writing selected logs to a file"""

    def __init__(self, env_layer, log_file):
        self.env_layer = env_layer
        self.log_file = log_file
        self.log_failure_log_file = log_file + ".failure"
        self.log_file_handle = None
        self.max_msg_size = 32 * 1024 * 1024
        try:
            self.log_file_handle = self.env_layer.file_system.open(self.log_file, "a+")
        except Exception as error:
            failure_message = "FileLogger - Error opening '" + self.log_file + "': " + repr(error)
            sys.stdout.write(failure_message)
            self.write_irrecoverable_exception(failure_message)
            raise

    def __del__(self):
        self.close()

    def write(self, message, fail_silently=True):
        try:
            if len(message) > self.max_msg_size:
                message = self.__truncate_message(message=message, max_size=self.max_msg_size)
            if self.log_file_handle is not None:
                self.log_file_handle.write(message)
        except Exception as error:
            # DO NOT write any errors here to stdout
            failure_message = "Fatal exception trying to write to log file: " + repr(error) + ". Attempted message: " + str(message)
            if not fail_silently:
                self.write_irrecoverable_exception(message)
                raise Exception(failure_message)

    def write_irrecoverable_exception(self, message):
        """ A best-effort attempt to write out errors where writing to the primary log file was interrupted"""
        try:
            if len(message) > self.max_msg_size:
                message = self.__truncate_message(message=message, max_size=self.max_msg_size)
            with self.env_layer.file_system.open(self.log_failure_log_file, 'a+') as fail_log:
                timestamp = self.env_layer.datetime.timestamp()
                fail_log.write("\n" + timestamp + "> " + message)
        except Exception:
            pass

    def flush(self):
        if self.log_file_handle is not None:
            self.log_file_handle.flush()
            os.fsync(self.log_file_handle.fileno())

    def close(self, message_at_close='<Log file was closed.>'):
        if self.log_file_handle is not None:
            if message_at_close is not None:
                self.write(str(message_at_close))
            self.log_file_handle.close()
            self.log_file_handle = None     # Not having this can cause 'I/O exception on closed file' exceptions

    def __truncate_message(self, message, max_size):
        # type(str, int) -> str
        """ Truncate message to a max size in bytes (32MB) at a safe point (end of the line avoid json serialization error) """
        truncated_message = message[:max_size]
        last_newline_index = truncated_message.rfind("\n")

        if last_newline_index != -1:
            return truncated_message[:last_newline_index + 1]

        return truncated_message

