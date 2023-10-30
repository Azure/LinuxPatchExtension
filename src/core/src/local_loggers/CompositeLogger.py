# coding=utf-8
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

""" Composite Logger - Manages diverting different kinds of output to the right sinks for them with consistent formatting.  """
from __future__ import print_function
from core.src.bootstrap.Constants import Constants


class CompositeLogger(object):
    class MessageFormatType(Constants.EnumBackport):
        """ Keys represent standard formats used. Values are representational only - non-functional. """
        PIPED_SINGLE_LINE = "x | y | z",
        INDENTED_MULTI_LINE= "\n\tx \n\ty \n\tz",
        PIPED_MULTI_LINE = "\n| x\n| y\n| z"

    def __init__(self, env_layer=None, file_logger=None, current_env=None, telemetry_writer=None):
        self.env_layer = env_layer
        self.file_logger = file_logger
        self.telemetry_writer = telemetry_writer
        self.current_env = current_env

    # region Public Methods
    def log(self, message):
        """ Log an info message """
        self.__log(message, event_level=Constants.EventLevel.Info, buffer_msg=Constants.BufferMessage.FALSE, prefix=None)

    def log_error(self, message):
        """ Logs an error """
        self.__log(message, event_level=Constants.EventLevel.Error, buffer_msg=Constants.BufferMessage.FALSE, prefix="ERROR:")

    def log_warning(self, message):
        """ Logs a warning """
        self.__log(message, event_level=Constants.EventLevel.Warning, buffer_msg=Constants.BufferMessage.FALSE, prefix="WARNING:")

    def log_debug(self, message, buffer_msg=Constants.BufferMessage.FALSE):
        """ Logs debugging data """
        self.__log(message, event_level=Constants.EventLevel.Debug, buffer_msg=buffer_msg, prefix=None)

    def log_verbose(self, message):
        """ Logs optional debugging data (local file only) """
        """ Note: Use this for mature code. Use regular debug for new code before stabilization. """
        self.__file_logger_write(message, prefix="Verbose")

    def log_raw(self, message):
        """ Logs to file/stdout without any formatting """
        if self.current_env in (Constants.ExecEnv.DEV, Constants.ExecEnv.TEST):
            self.__stdout_write(message, prefix=None)
        else:
            self.file_logger.write(message)
    # endregion Public Methods

    # region TelemetryWriter-only logging
    def log_telemetry_module_error(self, message):
        """ Used exclusively by telemetry writer to log any errors raised within its operation """
        self.__file_logger_write(message, "TELEMETRY_ERROR:")

    def log_telemetry_module(self, message):
        """ Used exclusively by telemetry writer to log messages from its operation """
        self.__file_logger_write(message, "TELEMETRY_LOG:")
    # endregion TelemetryWriter-only logging

    # region Private Methods
    def __log(self, message, event_level, buffer_msg=Constants.BufferMessage.FALSE, prefix=None):
        """ Log an info message, and is also delegated handling error, warning and debug messages. """
        if self.current_env != Constants.ExecEnv.DEV:    # to avoid dev environment slow downs
            self.__telemetry_write(message, event_level, buffer_msg)

        if self.current_env in (Constants.ExecEnv.DEV, Constants.ExecEnv.TEST):
            self.__stdout_write(message, prefix)

        self.__file_logger_write(message, prefix, fail_silently=False)

    def __stdout_write(self, message, prefix):
        """ Writes logs to standard output """
        """ Format: [Prefix-if-any] Non-indented single line or Indented multi-line string """
        print(self.__message_format(message, include_timestamp=False, prefix=prefix, format_type=self.MessageFormatType.INDENTED_MULTI_LINE))

    def __file_logger_write(self, message, prefix, fail_silently=True):
        """ Writes logs to file when possible """
        """ Format: timestamp> [Prefix-if-any] Non-indented single line or Piped multi-line string """
        if self.file_logger is not None:
            message = self.__message_format(message, include_timestamp=True, prefix=prefix, format_type=self.MessageFormatType.PIPED_MULTI_LINE)
            self.file_logger.write("\n" + message, fail_silently)

    def __telemetry_write(self, message, event_level, buffer_msg):
        """ Writes telemetry when possible """
        """ Format: Single line or piped | single | line - TelemetryWriter handles the rest """
        if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None and self.current_env != Constants.ExecEnv.DEV:
            message = self.__message_format(message, include_timestamp=False, prefix=None, format_type=self.MessageFormatType.PIPED_SINGLE_LINE)     # only sanitize and strip
            if self.telemetry_writer is not None and self.telemetry_writer.events_folder_path is not None and self.current_env not in (Constants.ExecEnv.DEV, Constants.ExecEnv.TEST):
                self.telemetry_writer.write_event_with_buffer(message, event_level, buffer_msg)

    def __message_format(self, message, include_timestamp=True, prefix=None, format_type=None):
        """" Helps format the message for the desired logging sink """
        substring = Constants.ERROR_ADDED_TO_STATUS # remove internal message descriptor if any
        message = message.replace("[{0}]".format(substring), "") if substring in message else message

        if format_type == self.MessageFormatType.PIPED_SINGLE_LINE:
            message = (" | ".join(message.strip().splitlines())) if "\n" in message else message.strip()
        elif format_type == self.MessageFormatType.INDENTED_MULTI_LINE:
            message = ("\n" if message.startswith("\n") or "\n" in message.strip() else "") + ("\t" if ("\n" in message.strip()) else "") + ("\n\t".join(message.strip().splitlines())).strip()
        elif format_type == self.MessageFormatType.PIPED_MULTI_LINE:
            message = ("\n" if message.startswith("\n") or "\n" in message.strip() else "") + ("| " if ("\n" in message.strip()) else "") + ("\n| ".join(message.strip().splitlines())).strip()

        message = "{0}{1}{2}".format(str(self.env_layer.datetime.timestamp())+"> " if include_timestamp else "",
                                     "["+prefix+"] " if prefix is not None else "",
                                     message)
        return message
    # endregion Private Methods
