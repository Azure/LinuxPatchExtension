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

    class StopwatchException(Constants.EnumBackport):
        # Stopwatch exception strings
        STARTED_ALREADY = "Stopwatch is already started"
        NOT_STARTED = "Stopwatch is not started"
        STOPPED_ALREADY = "Stopwatch is already stoppped"

    def __init__(self, env_layer, telemetry_writer, composite_logger):
        self.env_layer = env_layer
        self.telemetry_writer = telemetry_writer
        self.composite_logger = composite_logger
        self.start_time = None
        self.end_time = None
        self.time_taken = None
        self.task_details = None

    def __del__(self):
        # if start_time is None that means Stopwatch is not started and hence no need to log
        # call stop only if end_time is None otherwise stop() is already called.
        if self.start_time is not None and self.end_time is None:
            self.stop()
            self.set_task_details("")
            self.composite_logger.log("Stopwatch details before instance is destroyed: " + str(self.task_details))

    def start(self):
        if self.start_time is not None:
            self.composite_logger.log_debug(str(Stopwatch.StopwatchException.STARTED_ALREADY))
        self.start_time = self.env_layer.datetime.datetime_utcnow()
        self.end_time = None
        self.time_taken = None
        self.task_details = None

    def stop(self):
        if self.end_time is not None:
            self.composite_logger.log_debug(str(Stopwatch.StopwatchException.STOPPED_ALREADY))
        self.end_time = self.env_layer.datetime.datetime_utcnow()
        if self.start_time is None:
            self.composite_logger.log_debug(str(Stopwatch.StopwatchException.NOT_STARTED))
            self.start_time = self.end_time

        self.time_taken = self.env_layer.datetime.total_minutes_from_time_delta(self.end_time - self.start_time)

    def stop_and_write_telemetry(self, message):
        self.stop()
        self.set_task_details(message)
        self.composite_logger.log("Stopwatch details: " + str(self.task_details))

    def set_task_details(self, message):
        self.task_details = {Constants.PerfLogTrackerParams.START_TIME: str(self.start_time), Constants.PerfLogTrackerParams.END_TIME: str(self.end_time), Constants.PerfLogTrackerParams.TIME_TAKEN: str(self.time_taken),
                             Constants.PerfLogTrackerParams.MACHINE_INFO: self.telemetry_writer.machine_info, Constants.PerfLogTrackerParams.MESSAGE: str(message)}