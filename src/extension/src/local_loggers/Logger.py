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
    def __init__(self, file_logger=None, current_env=None, telemetry_writer=None):
        self.file_logger = file_logger
        self.telemetry_writer = telemetry_writer  # Although telemetry_writer is an independent entity, it is used within logger for ease of sending all logs to telemetry
        self.ERROR = "ERROR:"
        self.WARNING = "WARNING:"
        self.DEBUG = "DEBUG:"
        self.VERBOSE = "VERBOSE:"
        self.TELEMETRY_ERROR = "TELEMETRY_ERROR:"
        self.TELEMETRY_LOG = "TELEMETRY_LOG:"
        self.current_env = current_env
        self.NEWLINE_REPLACE_CHAR = " "

    def log(self, message):
        """log output"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
            self.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Informational)
        for line in message.splitlines():  # allows the extended file logger to strip unnecessary white space
            if self.file_logger is not None:
                self.file_logger.write("\n" + line)
            else:
                print(line)

    def log_error(self, message):
        """log errors"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
            self.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Error)
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
        if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
            self.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Warning)
        if self.file_logger is not None:
            self.file_logger.write("\n" + self.WARNING + " " + message)
        else:
            print(self.WARNING + " " + message)

    def log_debug(self, message):
        """log debug"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = message.strip()
        if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
            self.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Verbose)
        if self.current_env in (Constants.DEV, Constants.TEST):
            print(self.current_env + ": " + message)  # send to standard output if dev or test env
        if self.file_logger is not None:
            self.file_logger.write("\n" + self.DEBUG + " " + "\n\t".join(message.splitlines()).strip())

    def log_verbose(self, message):
        """log verbose"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
            self.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Verbose)
        if self.file_logger is not None:
            self.file_logger.write("\n" + self.VERBOSE + " " + "\n\t".join(message.strip().splitlines()).strip())

    def log_telemetry_module_error(self, message):
        """Used exclusively by telemetry writer to log any errors raised within it's operation"""
        message = (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        if self.file_logger is not None:
            self.file_logger.write("\n" + self.TELEMETRY_ERROR + " " + message)
        else:
            print(self.TELEMETRY_ERROR + " " + message)

    def log_telemetry_module(self, message):
        """Used exclusively by telemetry writer to log messages from it's operation"""
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

