# Copyright 2020 Microsoft Corporation
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

"""Maintenance window management"""
import datetime
from datetime import timedelta
from core.src.bootstrap.Constants import Constants

# do not instantiate directly - these are exclusively for type hinting support
from core.src.bootstrap.EnvLayer import EnvLayer
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.src.local_loggers.CompositeLogger import CompositeLogger
from core.src.service_interfaces.StatusHandler import StatusHandler


class MaintenanceWindow(object):
    """Implements the maintenance window logic"""

    def __init__(self, env_layer, execution_config, composite_logger, status_handler):
        #  type: (EnvLayer, ExecutionConfig, CompositeLogger, StatusHandler) -> None
        self.execution_config = execution_config
        self.duration = self.execution_config.duration
        self.start_time = self.execution_config.start_time
        self.composite_logger = composite_logger
        self.env_layer = env_layer
        self.status_handler = status_handler

    def get_remaining_time_in_minutes(self, current_time=None):
        # type: (str) -> int
        """ Calculate time remaining base on the given job start time """
        try:
            current_time = self.env_layer.datetime.datetime_utcnow() if current_time is None else current_time
            local_start_time, elapsed_time_in_minutes, remaining_time_in_minutes, total_time_in_minutes = self.__get_start_elapsed_remaining_and_total_time_in_minutes(current_time)
            self.composite_logger.log_verbose("[MW] Maintenance Window utilization. [ElapsedTime={0}][MaxDuration={1}][LocalStartTime={2}][CurrentTime={3}]".format(str(timedelta(seconds=int(elapsed_time_in_minutes*60))), self.duration, str(local_start_time), str(current_time.strftime("%Y-%m-%d %H:%M:%S"))))
        except ValueError as error:
            message = "Error calculating maintenance window time remaining. Check patch operation input parameters. [Error={0}]".format(repr(error))
            self.status_handler.add_error_to_status_and_log_error(message, raise_exception=True, error_code=Constants.PatchOperationErrorCodes.SV_MAINTENANCE_WINDOW_ERROR)
            raise   # redundant for IDE hinting

        return remaining_time_in_minutes

    def get_maintenance_window_used_as_percentage(self):
        # type: () -> int
        """ Calculate percentage of maintenance window used. Not customer facing. """
        percent_maintenance_window_used = -1
        try:
            local_start_time, elapsed_time_in_minutes, remaining_time_in_minutes, total_time_in_minutes = self.__get_start_elapsed_remaining_and_total_time_in_minutes()
            percent_maintenance_window_used = (elapsed_time_in_minutes / total_time_in_minutes) * 100
        except Exception as error:
            self.composite_logger.log_warning("[MW] Error calculating percentage of maintenance window used. [Error={0}]".format(repr(error)))

        return int(percent_maintenance_window_used)

    def is_package_install_time_available(self, remaining_time_in_minutes=None, number_of_packages_in_batch=1):
        # type: (int, int) -> bool
        """ Check if time still available for package installation """
        cutoff_time_in_minutes = Constants.Config.PACKAGE_INSTALL_EXPECTED_MAX_TIME_IN_MINUTES * number_of_packages_in_batch

        if self.execution_config.reboot_setting != Constants.RebootSettings.NEVER:
            cutoff_time_in_minutes = cutoff_time_in_minutes + Constants.Config.REBOOT_BUFFER_IN_MINUTES

        if remaining_time_in_minutes is None:
            remaining_time_in_minutes = self.get_remaining_time_in_minutes()

        if remaining_time_in_minutes > cutoff_time_in_minutes:
            self.composite_logger.log_verbose("[MW] Sufficient package install time available. [TimeRemaining={0}][CutoffTime={1}][PackagesInBatch={2}]".format(str(timedelta(seconds=int(remaining_time_in_minutes * 60))), str(timedelta(minutes=cutoff_time_in_minutes)), str(number_of_packages_in_batch)))
            return True
        else:
            self.composite_logger.log_warning("[MW] Insufficient time to install additional packages. [TimeRemaining={0}][CutoffTime={1}][PackagesInBatch={2}]".format(str(timedelta(seconds=int(remaining_time_in_minutes * 60))), str(timedelta(minutes=cutoff_time_in_minutes)), str(number_of_packages_in_batch)))
            return False

    def __get_start_elapsed_remaining_and_total_time_in_minutes(self, current_time=None):
        # type: (str) -> (str, int, int , int)
        """ Core maintenance window calculations. Current time format: "%Y-%m-%d %H:%M:%S.%f" """
        current_time = self.env_layer.datetime.datetime_utcnow() if current_time is None else current_time
        local_start_time = self.env_layer.datetime.utc_to_standard_datetime(self.start_time)
        dur = datetime.datetime.strptime(self.duration, "%H:%M:%S")
        dura = timedelta(hours=dur.hour, minutes=dur.minute, seconds=dur.second)
        total_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(dura)
        elapsed_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(current_time - local_start_time)
        remaining_time_in_minutes = max((total_time_in_minutes - elapsed_time_in_minutes), 0)

        return local_start_time, elapsed_time_in_minutes, remaining_time_in_minutes, total_time_in_minutes

