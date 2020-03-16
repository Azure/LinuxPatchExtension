"""Mirrors all terminal output to a local file
If the log file language is set to 'Python' in Notepad++, with code as implemented below, useful collapsibility is obtained."""
import sys

class StdOutFileMirror(object):
    """Mirrors all terminal output to a local file"""

    def __init__(self, env_layer, file_logger):
        self.env_layer = env_layer
        self.terminal = sys.stdout  # preserve for recovery
        self.file_logger = file_logger

        if self.file_logger.log_file_handle is not None:
            sys.stdout = self
            sys.stdout.write(str('-'*128))   # provoking an immediate failure if anything is wrong
        else:
            sys.stdout = self.terminal
            sys.stdout.write("WARNING: StdOutFileMirror - Skipping as FileLogger is not initialized")

    def write(self, message):
        self.terminal.write(message)  # enable standard job output

        if len(message.strip()) > 0:
            try:
                timestamp = self.env_layer.datetime.timestamp()
                self.file_logger.write("\n" + timestamp + "> " + message, fail_silently=False)  # also write to the file logger file
            except Exception as error:
                sys.stdout = self.terminal  # suppresses further job output mirror failures
                sys.stdout.write("WARNING: StdOutFileMirror - Error writing to log file: " + repr(error))

    def flush(self):
        pass

    def stop(self):
        sys.stdout = self.terminal
