# Copyright 2023 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
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
        STARTED_ALREADY = "[SW] Start attempted on already-started stopwatch."      # bug in call-stack if logged
        NOT_STARTED = "[SW] Stop attempted on non-started stopwatch."               # bug in call-stack if logged
        NOT_STOPPED = "[SW] Stopwatch is not stopped."
        STOPPED_ALREADY = "[SW] Stop attempted on already-stopped stopwatch."       # bug in call-stack if logged

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
            self.__set_task_details("")
            self.composite_logger.log_debug("[SW] Stopwatch destroyed in unexpected state. " + self.task_details)   # bug or some other issue in call-stack

    def start(self):
        """ Start the stopwatch and sets start_time. Resets other fields. """
        if self.start_time is not None:
            self.composite_logger.log_debug(str(Stopwatch.StopwatchException.STARTED_ALREADY))
        self.start_time = self.env_layer.datetime.datetime_utcnow()
        self.end_time = None
        self.time_taken_in_secs = None
        self.task_details = None

    def stop(self):
        """ Stop the stopwatch and set end_time. Create new end_time even if end_time is already set """
        if self.end_time is not None:
            self.composite_logger.log_debug(str(Stopwatch.StopwatchException.STOPPED_ALREADY))
        self.end_time = self.env_layer.datetime.datetime_utcnow()
        if self.start_time is None:
            self.composite_logger.log_debug(str(Stopwatch.StopwatchException.NOT_STARTED))
            self.start_time = self.end_time

        self.time_taken_in_secs = self.env_layer.datetime.total_seconds_from_time_delta_round_to_one_decimal_digit(self.end_time - self.start_time)

    def stop_and_write_telemetry(self, message):
        """ Stop the stopwatch, set end_time and write details in telemetry. Create new end_time even if end_time is already set """
        self.stop()
        self.__set_task_details(message)
        self.composite_logger.log("Stopwatch details: " + self.task_details)     # needs to change to "[SW] Stopwatch terminal log. " + self.task_details || not changing yet to avoid disruption to querying

    def write_telemetry_for_stopwatch(self, message):
        """ Write stopwatch details in telemetry. Use the existing end_time if it is already set otherwise set new end_time """
        if self.end_time is None:
            self.composite_logger.log_verbose(str(Stopwatch.StopwatchException.NOT_STOPPED))
            self.end_time = self.env_layer.datetime.datetime_utcnow()
        if self.start_time is None:
            self.composite_logger.log_debug(str(Stopwatch.StopwatchException.NOT_STARTED))
            self.start_time = self.end_time
        self.time_taken_in_secs = self.env_layer.datetime.total_seconds_from_time_delta_round_to_one_decimal_digit(self.end_time - self.start_time)
        self.__set_task_details(message)
        self.composite_logger.log("Stopwatch details: " + str(self.task_details))  # needs to change to "[SW] Stopwatch intermediate log. " + self.task_details || not changing yet to avoid disruption to querying

    def __set_task_details(self, message):
        self.task_details = "[{0}={1}][{2}={3}][{4}={5}][{6}={7}]".format(Constants.PerfLogTrackerParams.MESSAGE, str(message), Constants.PerfLogTrackerParams.TIME_TAKEN_IN_SECS, str(self.time_taken_in_secs), 
                                                                                Constants.PerfLogTrackerParams.START_TIME, str(self.start_time), Constants.PerfLogTrackerParams.END_TIME, str(self.end_time))

