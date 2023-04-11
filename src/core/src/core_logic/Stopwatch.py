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
        NOT_STOPPED = "Stopwatch is not stoppped"
        STOPPED_ALREADY = "Stopwatch is already stoppped"

    def __init__(self, env_layer, telemetry_writer, composite_logger):
        self.env_layer = env_layer
        self.telemetry_writer = telemetry_writer
        self.composite_logger = composite_logger
        self.start_time = None
        self.end_time = None
        self.time_taken_in_secs = None
        self.task_details = None

    def __del__(self):
        # if start_time is None that means Stopwatch is not started and hence no need to log
        # call stop only if end_time is None otherwise stop() is already called.
        if self.start_time is not None and self.end_time is None:
            self.stop()
            self.set_task_details("")
            self.composite_logger.log("Stopwatch details before instance is destroyed: " + self.task_details)

    def start(self):
        if self.start_time is not None:
            self.composite_logger.log_debug(str(Stopwatch.StopwatchException.STARTED_ALREADY))
        self.start_time = self.env_layer.datetime.datetime_utcnow()
        self.end_time = None
        self.time_taken_in_secs = None
        self.task_details = None

    # Stop the stopwatch and set end_time. Create new end_time even if end_time is already set
    def stop(self):
        if self.end_time is not None:
            self.composite_logger.log_debug(str(Stopwatch.StopwatchException.STOPPED_ALREADY))
        self.end_time = self.env_layer.datetime.datetime_utcnow()
        if self.start_time is None:
            self.composite_logger.log_debug(str(Stopwatch.StopwatchException.NOT_STARTED))
            self.start_time = self.end_time

        self.time_taken_in_secs = self.env_layer.datetime.total_seconds_from_time_delta(self.end_time - self.start_time)

        # Rounding off to one digit after decimal e.g. 14.574372666666667 will become 14.6
        self.time_taken_in_secs = round(self.time_taken_in_secs, 1)

    # Stop the stopwatch, set end_time and write details in telemetry. Create new end_time even if end_time is already set
    def stop_and_write_telemetry(self, message):
        self.stop()
        self.set_task_details(message)
        self.composite_logger.log("Stopwatch details: " + self.task_details)

    # Write stopwatch details in telemetry. Use the existing end_time if it is already set otherwise set new end_time
    def write_telemetry_for_stopwatch(self, message):
        if self.end_time is None:
            self.composite_logger.log_debug(str(Stopwatch.StopwatchException.NOT_STOPPED))
            self.end_time = self.env_layer.datetime.datetime_utcnow()
        if self.start_time is None:
            self.composite_logger.log_debug(str(Stopwatch.StopwatchException.NOT_STARTED))
            self.start_time = self.end_time
        self.time_taken = self.env_layer.datetime.total_minutes_from_time_delta(self.end_time - self.start_time)
        self.set_task_details(message)
        self.composite_logger.log("Stopwatch details: " + str(self.task_details))

    def set_task_details(self, message):
        self.task_details = "[{0}={1}][{2}={3}][{4}={5}][{6}={7}]".format(Constants.PerfLogTrackerParams.MESSAGE, str(message), Constants.PerfLogTrackerParams.TIME_TAKEN_IN_SECS, str(self.time_taken_in_secs), 
                             Constants.PerfLogTrackerParams.START_TIME, str(self.start_time), Constants.PerfLogTrackerParams.END_TIME, str(self.end_time))
