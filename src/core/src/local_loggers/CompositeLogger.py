from __future__ import print_function
import os
from src.bootstrap.Constants import Constants


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
        for line in message.splitlines():  # allows the extended file logger to strip unnecessary white space
            print(line)

    def log_error(self, message):
        """log errors"""
        message = self.ERROR + (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        self.log(message)

    def log_warning(self, message):
        """log warning"""
        message = self.WARNING + (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        self.log(message)

    def log_debug(self, message):
        """log debug"""
        message = message.strip()
        if self.current_env in (Constants.DEV, Constants.TEST):
            self.log(self.current_env + ": " + message)  # send to standard output if dev or test env
        elif self.file_logger is not None:
            self.file_logger.write("\n\t" + self.DEBUG + " " + "\n\t".join(message.splitlines()).strip())

    def log_verbose(self, message):
        """log verbose"""
        if self.file_logger is not None:
            self.file_logger.write("\n\t" + self.VERBOSE + " " + "\n\t".join(message.strip().splitlines()).strip())
