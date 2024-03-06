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

"""Maintenance window management"""
import datetime
from datetime import timedelta
from core.src.bootstrap.Constants import Constants


class MaintenanceWindow(object):
    """Implements the maintenance window logic"""

    def __init__(self, env_layer, execution_config, composite_logger, status_handler):
        self.execution_config = execution_config
        self.duration = self.execution_config.duration
        self.start_time = self.execution_config.start_time
        self.composite_logger = composite_logger
        self.env_layer = env_layer
        self.status_handler = status_handler

    def get_remaining_time_in_minutes(self, current_time=None, log_to_stdout=False):
        """Calculate time remaining base on the given job start time"""
        try:
            if current_time is None:
                current_time = self.env_layer.datetime.datetime_utcnow()
            start_time = self.env_layer.datetime.utc_to_standard_datetime(self.start_time)
            dur = datetime.datetime.strptime(self.duration, "%H:%M:%S")
            dura = timedelta(hours=dur.hour, minutes=dur.minute, seconds=dur.second)
            total_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(dura)
            elapsed_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(current_time - start_time)
            remaining_time_in_minutes = max((total_time_in_minutes - elapsed_time_in_minutes), 0)

            log_line = "Maintenance Window Utilization: " + str(timedelta(seconds=int(elapsed_time_in_minutes*60))) + " / " + self.duration + "\
                        [Job start: " + str(start_time) + ", Current time: " + str(current_time.strftime("%Y-%m-%d %H:%M:%S")) + "]"
            if log_to_stdout:
                self.composite_logger.log(log_line)
            else:
                self.composite_logger.log_debug(log_line)
        except ValueError as error:
            error_msg = "Error calculating time remaining. Check patch operation input parameters."
            self.composite_logger.log_error("\n" + error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            if Constants.ERROR_ADDED_TO_STATUS not in repr(error):
                error.args = (error.args, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
            raise

        return remaining_time_in_minutes

    def is_package_install_time_available(self, remaining_time_in_minutes=None, number_of_packages_in_batch=1):
        """Check if time still available for package installation"""
        cutoff_time_in_minutes = 0

        # In the extreme case, all the package installations in the batch might take the maximum time. 
        # But calculating cutoff time based on max time to install packages for all the packages will make cutoff time very huge 
        # as it is very unlikely that all the package installations take maximum time.
        # Also, as the batch size increases, the expected time taken per package installation decreases due to batch patching.
        # So, for batch size less than or equal to 3, calculating cutoff time expecting all packages might take max time to install.
        # For larger batch size i.e. 4 or higher, expecting 3 package installations can take max time and rest can take average time to install.
        # It is safe assumption that only 3 packages will take max time to install. Even if more number of packages take max time to install then
        # due to batch patching in large batch size, the time taken to install a package decreases substantially and hence cutoff time should be enough
        # to install the batch of packages.
        # PACKAGE_INSTALL_EXPECTED_MAX_TIME is 5 minutes, PACKAGE_INSTALL_EXPECTED_AVG_TIME is 2 minutes
        # For different batch size, following would be cutoff:
        # Batch Size = 1, Cutoff = 5 * 1 = 5 minutes
        # Batch Size = 2, Cutoff = 5 * 2 = 10 minutes
        # Batch Size = 3, Cutoff = 5 * 3 = 15 minutes
        # Batch Size = 4, Cutoff = (5 * 3) + (2 * 1) = 17 minutes
        # Batch Size = 5, Cutoff = (5 * 3) + (2 * 2) = 19 minutes
        # Batch Size = 6, Cutoff = (5 * 3) + (2 * 3) = 21 minutes
        if number_of_packages_in_batch <= Constants.NUMBER_OF_PACKAGES_IN_BATCH_COULD_TAKE_MAX_TIME_TO_INSTALL:
            cutoff_time_in_minutes = Constants.PACKAGE_INSTALL_EXPECTED_MAX_TIME_IN_MINUTES * number_of_packages_in_batch
        else:
            cutoff_time_in_minutes = Constants.PACKAGE_INSTALL_EXPECTED_MAX_TIME_IN_MINUTES * Constants.NUMBER_OF_PACKAGES_IN_BATCH_COULD_TAKE_MAX_TIME_TO_INSTALL
            cutoff_time_in_minutes += Constants.PACKAGE_INSTALL_EXPECTED_AVG_TIME_IN_MINUTES * (number_of_packages_in_batch - Constants.NUMBER_OF_PACKAGES_IN_BATCH_COULD_TAKE_MAX_TIME_TO_INSTALL)

        if Constants.REBOOT_SETTINGS[self.execution_config.reboot_setting] != Constants.REBOOT_NEVER:
            cutoff_time_in_minutes = cutoff_time_in_minutes + Constants.REBOOT_BUFFER_IN_MINUTES

        if remaining_time_in_minutes is None:
            remaining_time_in_minutes = self.get_remaining_time_in_minutes()

        if remaining_time_in_minutes > cutoff_time_in_minutes:
            self.composite_logger.log_debug("Time Remaining: " + str(timedelta(seconds=int(remaining_time_in_minutes * 60))) + ", Cutoff time: " + str(timedelta(minutes=cutoff_time_in_minutes)))
            return True
        else:
            self.composite_logger.log_warning("Time Remaining: " + str(timedelta(seconds=int(remaining_time_in_minutes * 60))) + ", Cutoff time: " + str(timedelta(minutes=cutoff_time_in_minutes)) + " [Out of time!]")
            return False

    def get_percentage_maintenance_window_used(self):
        """Calculate percentage of maintenance window used"""
        try:
            current_time = self.env_layer.datetime.datetime_utcnow()
            start_time = self.env_layer.datetime.utc_to_standard_datetime(self.start_time)
            if current_time < start_time:
                raise Exception("Start time {0} is greater than current time {1}".format(str(start_time), str(current_time)))
            dur = datetime.datetime.strptime(self.duration, "%H:%M:%S")
            dura = timedelta(hours=dur.hour, minutes=dur.minute, seconds=dur.second)
            total_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(dura)
            elapsed_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(current_time - start_time)
            percent_maintenance_window_used = (elapsed_time_in_minutes / total_time_in_minutes) * 100
        except Exception as error:
            error_msg = "Error calculating percentage of maintenance window used."
            self.composite_logger.log_error("\n" + error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            if Constants.ERROR_ADDED_TO_STATUS not in repr(error):
                error.args = (error.args, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
            raise

        # Rounding off to one digit after decimal e.g. 14.514372666666667 will become 14.5
        percent_maintenance_window_used = round(percent_maintenance_window_used, 1)
        return percent_maintenance_window_used