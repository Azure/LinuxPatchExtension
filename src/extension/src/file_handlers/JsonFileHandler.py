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

import json
import os
import time

from extension.src.Constants import Constants


class JsonFileHandler(object):
    def __init__(self, logger):
        self.logger = logger
        self.retry_count = Constants.MAX_IO_RETRIES

    def get_json_file_content(self, file, dir_path, raise_if_not_found=False):
        """ Returns content read from the given json file under the directory/path. Re-tries the operation a certain number of times and raises an exception if it still fails """
        file_path = os.path.join(dir_path, file)
        error_msg = ""
        self.logger.log("Reading file. [File={0}]".format(file))
        for retry in range(0, self.retry_count):
            try:
                time.sleep(retry)
                with open(file_path, 'r') as file_handle:
                    file_contents = file_handle.read()
                    return json.loads(file_contents)
            except ValueError as e:
                error_msg = "Incorrect file format. [File={0}] [Location={1}] [Exception={2}]".format(file, str(file_path), repr(e))
                self.logger.log_warning(error_msg)
            except Exception as e:
                error_msg = "Trial {0}: Could not read file. [File={1}] [Location={2}] [Exception={3}]".format(retry + 1, file, str(file_path), repr(e))
                self.logger.log_warning(error_msg)

        error_msg = "Failed to read file after {0} tries. [File={1}] [Location={2}] [Exception={3}]".format(self.retry_count, file, str(file_path), error_msg)
        self.logger.log_error(error_msg)
        if raise_if_not_found:
            raise Exception(error_msg)

    def get_json_config_value_safely(self, handler_json, key, parent_key, raise_if_not_found=True):
        """ Allows a update deployment configuration value to be queried safely with a fall-back default (optional). An exception will be raised if default_value is not explicitly set when called (considered by-design). """
        if handler_json is not None and len(handler_json) != 0:
            if key in handler_json[parent_key]:
                value = handler_json[parent_key][key]
                return value
            else:   # If it is not present
                if raise_if_not_found:
                    raise Exception("Value not found for given config. [Config={0}]".format(key))
        return None

    def write_to_json_file(self, dir_path, file, content):
        """ Retries create operation for a set number of times before failing """
        if os.path.exists(dir_path):
            file_path = os.path.join(dir_path, file)
            error_message = ""
            self.logger.log("Writing file. [File={0}]".format(file))
            for retry in range(0, self.retry_count):
                try:
                    time.sleep(retry)
                    with open(file_path, 'w') as json_file:
                        json.dump(content, json_file, default=self.json_default_converter)
                        return
                except Exception as error:
                    error_message = "Trial {0}: Could not write to file. [File={1}] [Location={2}] [Exception={3}]".format(retry+1, file, str(file_path), error)
                    self.logger.log_warning(error_message)

            error_msg = "Failed to write to file after {0} tries. [File={1}] [Location={2}] [Exception={3}]".format(self.retry_count, file, str(file_path), error_message)
            self.logger.log_error_and_raise_new_exception(error_msg, Exception)
        else:
            error_msg = "Directory Not Found: [Directory={0}]".format(dir_path)
            self.logger.log_error_and_raise_new_exception(error_msg, Exception)

    def json_default_converter(self, value):
        return value.__str__()
