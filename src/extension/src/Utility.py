import datetime
import os
import time
from src.Constants import Constants
from src.local_loggers.FileLogger import FileLogger


class Utility(object):
    def __init__(self, logger):
        self.logger = logger
        self.retry_count = Constants.MAX_IO_RETRIES

    def delete_file(self, dir_path, file, raise_if_not_found=True):
        """ Retries delete operation for a set number of times before failing """
        self.logger.log("Deleting file. [File={0}]".format(file))
        file_path = os.path.join(dir_path, file)
        error_msg = ""
        if os.path.exists(file_path) and os.path.isfile(file_path):
            for retry in range(0, self.retry_count):
                try:
                    time.sleep(retry)
                    os.remove(file_path)
                    return True
                except Exception as e:
                    error_msg = "Trial {0}: Could not delete file. [File={1}] [Exception={2}]".format(retry+1, file, repr(e))
                    self.logger.log_error(error_msg)
            error_msg = "Failed to delete file after {0} tries. [File={1}] [Exception={2}]".format(self.retry_count, file, error_msg)
            self.logger.log_error(error_msg)
        else:
            error_msg = "File Not Found: [File={0}] in [path={1}]".format(file, dir_path)
            self.logger.log_error(error_msg)
        if raise_if_not_found:
            raise Exception(error_msg)

    def create_log_file(self, log_folder, seq_no):
        """ Creates <sequencenumber>.ext.log file under the path for logFolder provided in HandlerEnvironment """
        file_path = str(seq_no) + str(".ext") + Constants.LOG_FILE_EXTENSION
        if seq_no is not None and os.path.exists(log_folder):
            self.logger.log("Creating log file. [File={0}]".format(file_path))
            return FileLogger(log_folder, file_path)
        else:
            self.logger.log_error("File creation error: [File={0}]".format(file_path))
            return None

    def get_datetime_from_str(self, date_str):
        return datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")

    def get_str_from_datetime(self, date):
        return date.strftime("%Y-%m-%dT%H:%M:%SZ")
