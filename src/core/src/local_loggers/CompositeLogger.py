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

    def __init__(self, env_layer=None, file_logger=None, telemetry_writer=None, current_env=None):
        self.env_layer = env_layer
        self.file_logger = file_logger
        self.telemetry_writer = telemetry_writer
        self.ERROR = "ERROR:"
        self.WARNING = "WARNING:"
        self.DEBUG = "DEBUG:"
        self.VERBOSE = "VERBOSE:"
        self.current_env = current_env
        self.NEWLINE_REPLACE_CHAR = " "
        self.telemetry_task = "ExtensionCoreLog"
        self.telemetry_msg_truncated_note = " This message will be truncated in telemetry as it exceeds the size limit."

    def log(self, message, message_type=Constants.TelemetryEventLevel.Informational):
        """log output"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = message.strip()
        if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
            self.telemetry_writer.write_event(self.telemetry_task, message, message_type)
            message = self.__add_telemetry_error_note(message)
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
            self.telemetry_writer.write_event(self.telemetry_task, message, Constants.TelemetryEventLevel.Verbose)
            message = self.__add_telemetry_error_note(message)

        if self.current_env in (Constants.DEV, Constants.TEST):
            self.log(self.current_env + ": " + message, Constants.TelemetryEventLevel.Verbose)  # send to standard output if dev or test env
        elif self.file_logger is not None:
            self.file_logger.write("\n\t" + self.DEBUG + " " + "\n\t".join(message.splitlines()).strip())

    def log_verbose(self, message):
        """log verbose"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None:
            self.telemetry_writer.write_event(self.telemetry_task, message, Constants.TelemetryEventLevel.Verbose)
            message = self.__add_telemetry_error_note(message)

        if self.file_logger is not None:
            self.file_logger.write("\n\t" + self.VERBOSE + " " + "\n\t".join(message.strip().splitlines()).strip())

    @staticmethod
    def __remove_substring_from_message(message, substring=Constants.ERROR_ADDED_TO_STATUS):
        """Remove substring from a string"""
        if substring in message:
            message = message.replace("[{0}]".format(Constants.ERROR_ADDED_TO_STATUS), "")
        return message

    def __add_telemetry_error_note(self, message):
        """ Adding telemetry error messages to the original message, so as to log telemetry errors in other logs """
        if len(message.encode('utf-8')) > Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_BYTES:
            message = message + self.telemetry_msg_truncated_note
        return message

