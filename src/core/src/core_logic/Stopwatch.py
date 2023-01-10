# Copyright 2023 Microsoft Corporation
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

from core.src.bootstrap.Constants import Constants

class Stopwatch(object):
    """Implements the stopwatch logic"""

    def __init__(self, env_layer, telemetry_writer, composite_logger):
        self.env_layer = env_layer
        self.telemetry_writer = telemetry_writer
        self.composite_logger = composite_logger
        self.start_time = None
        self.end_time = None

    def __del__(self):
        # call stop only if end_time is None otherwise stop() is already called.
        if (self.end_time == None):
            self.stop()
            self.task_details = {Constants.LogStrings.START_TIME: str(self.start_time), Constants.LogStrings.END_TIME: str(self.end_time), Constants.LogStrings.TIME_TAKEN: str(self.time_taken),
                                 Constants.LogStrings.MACHINE_INFO: self.telemetry_writer.machine_info, Constants.LogStrings.MESSAGE: ""}
            self.composite_logger.log(str(self.task_details))

    def start(self):
        if (self.start_time != None):
            raise Exception(Constants.STARTED_ALREADY)
        self.start_time = self.env_layer.datetime.datetime_utcnow()

    def stop(self):
        if (self.end_time != None):
            raise Exception(Constants.STOPPED_ALREADY)
        self.end_time = self.env_layer.datetime.datetime_utcnow()
        self.time_taken = self.env_layer.datetime.total_minutes_from_time_delta(self.end_time - self.start_time)

    def stop_and_write_telemetry(self, message):
        if (self.end_time != None):
            raise Exception(Constants.STOPPED_ALREADY)
        self.stop()
        self.task_details = {Constants.LogStrings.START_TIME: str(self.start_time), Constants.LogStrings.END_TIME: str(self.end_time), Constants.LogStrings.TIME_TAKEN: str(self.time_taken),
                             Constants.LogStrings.MACHINE_INFO: self.telemetry_writer.machine_info, Constants.LogStrings.MESSAGE: str(message)}
        self.composite_logger.log(str(self.task_details))