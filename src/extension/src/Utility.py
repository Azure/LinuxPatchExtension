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

import datetime
import os
import time
from extension.src.Constants import Constants
from extension.src.local_loggers.FileLogger import FileLogger


#TODO later: move utility to env Layer
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
                    self.logger.log_warning(error_msg)

            error_msg = "Failed to delete file after {0} tries. [File={1}] [Exception={2}]".format(self.retry_count, file, error_msg)
            self.logger.log_error(error_msg)
        else:
            error_msg = "File Not Found: [File={0}] in [path={1}]".format(file, dir_path)
            self.logger.log_error(error_msg)
        if raise_if_not_found:
            raise Exception(error_msg)

    def create_log_file(self, log_folder, file_name):
        """ Creates <file_name>.ext.log file under the path for logFolder provided in HandlerEnvironment """
        file_path = file_name + str(".ext") + Constants.LOG_FILE_EXTENSION
        if file_name is not None and os.path.exists(log_folder):
            self.logger.log("Creating log file. [File={0}]".format(file_path))
            return FileLogger(log_folder, file_path)
        else:
            self.logger.log_error("File creation error: [File={0}]".format(file_path))
            return None

    @staticmethod
    def get_datetime_from_str(date_str):
        return datetime.datetime.strptime(date_str, Constants.UTC_DATETIME_FORMAT)

    @staticmethod
    def get_str_from_datetime(date):
        return date.strftime(Constants.UTC_DATETIME_FORMAT)

