import sys


class FileLogger(object):
    """Facilitates writing selected logs to a file"""

    def __init__(self, env_layer, log_file):
        self.env_layer = env_layer
        self.log_file = log_file
        self.log_failure_log_file = log_file + ".failure"
        self.log_file_handle = None
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
            with self.env_layer.file_system.open(self.log_failure_log_file, 'a+') as fail_log:
                timestamp = self.env_layer.datetime.timestamp()
                fail_log.write("\n" + timestamp + "> " + message)
        except Exception:
           pass

    def flush(self):
        if self.log_file_handle is not None:
            self.log_file_handle.flush()

    def close(self, message_at_close='<Log file was closed.>'):
        if self.log_file_handle is not None:
            if message_at_close is not None:
                self.write(str(message_at_close))
            self.log_file_handle.close()
