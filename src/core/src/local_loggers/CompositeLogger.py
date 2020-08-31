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

    def __init__(self, file_logger=None, current_env=None):
        self.file_logger = file_logger
        self.ERROR = "ERROR:"
        self.WARNING = "WARNING:"
        self.DEBUG = "DEBUG:"
        self.VERBOSE = "VERBOSE:"
        self.current_env = current_env
        self.NEWLINE_REPLACE_CHAR = " "

    @staticmethod
    def log(message):
        """log output"""
        message = CompositeLogger.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        for line in message.splitlines():  # allows the extended file logger to strip unnecessary white space
            print(line)

    def log_error(self, message):
        """log errors"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = self.ERROR + (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        self.log(message)

    def log_warning(self, message):
        """log warning"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = self.WARNING + (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        self.log(message)

    def log_debug(self, message):
        """log debug"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        message = message.strip()
        if self.current_env in (Constants.DEV, Constants.TEST):
            self.log(self.current_env + ": " + message)  # send to standard output if dev or test env
        elif self.file_logger is not None:
            self.file_logger.write("\n\t" + self.DEBUG + " " + "\n\t".join(message.splitlines()).strip())

    def log_verbose(self, message):
        """log verbose"""
        message = self.__remove_substring_from_message(message, Constants.ERROR_ADDED_TO_STATUS)
        if self.file_logger is not None:
            self.file_logger.write("\n\t" + self.VERBOSE + " " + "\n\t".join(message.strip().splitlines()).strip())

    @staticmethod
    def __remove_substring_from_message(message, substring=Constants.ERROR_ADDED_TO_STATUS):
        """Remove substring from a string"""
        if substring in message:
            message = message.replace("[{0}]".format(Constants.ERROR_ADDED_TO_STATUS), "")
        return message

