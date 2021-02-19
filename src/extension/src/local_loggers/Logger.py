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

from __future__ import print_function
import os
from extension.src.Constants import Constants


class Logger(object):
    # def __init__(self, file_logger=None, current_env=None, telemetry_writer=None):
    def __init__(self, file_logger=None, current_env=None):
        self.file_logger = file_logger
        self.ERROR = "ERROR:"
        self.WARNING = "WARNING:"
        self.DEBUG = "DEBUG:"
        self.VERBOSE = "VERBOSE:"
        self.TELEMETRY_ERROR = "TELEMETRY_ERROR:"
        self.TELEMETRY_LOG = "TELEMETRY_LOG:"
        self.current_env = current_env
        self.NEWLINE_REPLACE_CHAR = " "
        # self.telemetry_writer = telemetry_writer
        # self.telemetry_task = "HandlerLog"
        # self.telemetry_msg_truncated_note = " This message will be truncated in telemetry as it exceeds the size limit."

    def log(self, message):
        """log output"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        # if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
        #     self.telemetry_writer.write_event(self.telemetry_task, message, Constants.TelemetryEventLevel.Informational)
        #     message = self.__add_telemetry_error_note(message)
        for line in message.splitlines():  # allows the extended file logger to strip unnecessary white space
            if self.file_logger is not None:
                self.file_logger.write("\n" + line)
            else:
                print(line)

    def log_error(self, message):
        """log errors"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        # if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
        #     self.telemetry_writer.write_event(self.telemetry_task, message, Constants.TelemetryEventLevel.Error)
        #     message = self.__add_telemetry_error_note(message)
        if self.file_logger is not None:
            self.file_logger.write("\n" + self.ERROR + " " + message)
        else:
            print(self.ERROR + " " + message)

    def log_error_and_raise_new_exception(self, message, exception):
        """log errors and raise exception passed in as an arg"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        self.log_error(repr(message))
        raise exception(message)

    def log_warning(self, message):
        """log warning"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        # if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
        #     self.telemetry_writer.write_event(self.telemetry_task, message, Constants.TelemetryEventLevel.Warning)
        #     message = self.__add_telemetry_error_note(message)
        if self.file_logger is not None:
            self.file_logger.write("\n" + self.WARNING + " " + message)
        else:
            print(self.WARNING + " " + message)

    def log_debug(self, message):
        """log debug"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = message.strip()
        # if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
        #     self.telemetry_writer.write_event(self.telemetry_task, message, Constants.TelemetryEventLevel.Verbose)
        #     message = self.__add_telemetry_error_note(message)
        if self.current_env in (Constants.DEV, Constants.TEST):
            print(self.current_env + ": " + message)  # send to standard output if dev or test env
        if self.file_logger is not None:
            self.file_logger.write("\n" + self.DEBUG + " " + "\n\t".join(message.splitlines()).strip())

    def log_verbose(self, message):
        """log verbose"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        # if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
        #     self.telemetry_writer.write_event(self.telemetry_task, message, Constants.TelemetryEventLevel.Verbose)
        #     message = self.__add_telemetry_error_note(message)
        if self.file_logger is not None:
            self.file_logger.write("\n" + self.VERBOSE + " " + "\n\t".join(message.strip().splitlines()).strip())

    def log_telemetry_error(self, message):
        """Log telemetry error"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        if self.file_logger is not None:
            self.file_logger.write("\n" + self.TELEMETRY_ERROR + " " + message)
        else:
            print(self.TELEMETRY_ERROR + " " + message)

    def log_telemetry(self, message):
        """Log telemetry"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        if self.file_logger is not None:
            self.file_logger.write("\n" + self.TELEMETRY_LOG + " " + message)
        else:
            print(self.TELEMETRY_LOG + " " + message)

    @staticmethod
    def __remove_substring_from_message(message, substring=Constants.ERROR_ADDED_TO_STATUS):
        """Remove substring from a string"""
        if substring in message:
            message = message.replace("[{0}]".format(Constants.ERROR_ADDED_TO_STATUS), "")
        return message

    # def __add_telemetry_error_note(self, message):
    #     """ Adding telemetry error messages to the original message, so as to log telemetry errors in other logs """
    #     if len(message.encode('utf-8')) > Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_BYTES:
    #         message = message + self.telemetry_msg_truncated_note
    #     return message

