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
from core.src.bootstrap.Constants import Constants


class CompositeLogger(object):
    """ Manages diverting different kinds of output to the right sinks for them. """

    def __init__(self, env_layer=None, file_logger=None, current_env=None, telemetry_writer=None):
        self.env_layer = env_layer
        self.file_logger = file_logger
        self.telemetry_writer = telemetry_writer  # Although telemetry_writer is an independent entity, it is used within composite_logger for ease of sending all logs to telemetry
        self.ERROR = "ERROR:"
        self.WARNING = "WARNING:"
        self.DEBUG = "DEBUG:"
        self.VERBOSE = "VERBOSE:"
        self.TELEMETRY_ERROR = "TELEMETRY_ERROR:"
        self.TELEMETRY_LOG = "TELEMETRY_LOG:"
        self.current_env = current_env
        self.NEWLINE_REPLACE_CHAR = " "

    def log(self, message, message_type=Constants.TelemetryEventLevel.Informational):
        """log output"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = message.strip()
        if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None and self.current_env != Constants.DEV:  # turned off for dev environment as it severely slows down execution
            self.telemetry_writer.write_event(message, message_type)
        if self.current_env in (Constants.DEV, Constants.TEST):
            for line in message.splitlines():  # allows the extended file logger to strip unnecessary white space
                print(line)
        elif self.file_logger is not None:
            timestamp = self.env_layer.datetime.timestamp()
            self.file_logger.write("\n" + timestamp + "> " + message.strip(), fail_silently=False)

    def log_error(self, message):
        """log errors"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = self.ERROR + (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        self.log(message, message_type=Constants.TelemetryEventLevel.Error)

    def log_warning(self, message):
        """log warning"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = self.WARNING + (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        self.log(message, message_type=Constants.TelemetryEventLevel.Warning)

    def log_debug(self, message):
        """log debug"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = message.strip()
        if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None and self.current_env not in (Constants.DEV, Constants.TEST):
            self.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Verbose)
        if self.current_env in (Constants.DEV, Constants.TEST):
            self.log(self.current_env + ": " + str(self.env_layer.datetime.datetime_utcnow()) + ": " + message, Constants.TelemetryEventLevel.Verbose)  # send to standard output if dev or test env
        elif self.file_logger is not None:
            self.file_logger.write("\n\t" + self.DEBUG + " " + "\n\t".join(message.splitlines()).strip())

    def log_verbose(self, message):
        """log verbose"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
            self.telemetry_writer.write_event(message, Constants.TelemetryEventLevel.Verbose)
        if self.file_logger is not None:
            self.file_logger.write("\n\t" + self.VERBOSE + " " + "\n\t".join(message.strip().splitlines()).strip())

    def log_telemetry_module_error(self, message):
        """Used exclusively by telemetry writer to log any errors raised within it's operation"""
        message = (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        if self.file_logger is not None:
            timestamp = self.env_layer.datetime.timestamp()
            self.file_logger.write("\n" + timestamp + "> " + self.TELEMETRY_ERROR + message.strip(), fail_silently=False)
        else:
            print(self.TELEMETRY_ERROR + " " + message)

    def log_telemetry_module(self, message):
        """Used exclusively by telemetry writer to log messages from it's operation"""
        message = (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        if self.file_logger is not None:
            timestamp = self.env_layer.datetime.timestamp()
            self.file_logger.write("\n" + timestamp + "> " + self.TELEMETRY_LOG + message.strip(), fail_silently=False)
        else:
            print(self.TELEMETRY_LOG + " " + message)

    @staticmethod
    def __remove_substring_from_message(message, substring=Constants.ERROR_ADDED_TO_STATUS):
        """Remove substring from a string"""
        if substring in message:
            message = message.replace("[{0}]".format(Constants.ERROR_ADDED_TO_STATUS), "")
        return message

