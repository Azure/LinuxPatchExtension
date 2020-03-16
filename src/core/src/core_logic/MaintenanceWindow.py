"""Maintenance window management"""
import datetime
from datetime import timedelta
from src.bootstrap.Constants import Constants


class MaintenanceWindow(object):
    """Implements the maintenance window logic"""

    def __init__(self, env_layer, execution_config, composite_logger):
        self.execution_config = execution_config
        self.duration = self.execution_config.duration
        self.start_time = self.execution_config.start_time
        self.composite_logger = composite_logger
        self.env_layer = env_layer

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
        except ValueError:
            self.composite_logger.log_error("\nError calculating time remaining. Check patch operation input parameters.")
            raise

        return remaining_time_in_minutes

    def is_package_install_time_available(self, remaining_time_in_minutes=None):
        """Check if time still available for package installation"""
        cutoff_time_in_minutes = Constants.REBOOT_BUFFER_IN_MINUTES + Constants.PACKAGE_INSTALL_EXPECTED_MAX_TIME_IN_MINUTES
        if remaining_time_in_minutes is None:
            remaining_time_in_minutes = self.get_remaining_time_in_minutes()

        if remaining_time_in_minutes > cutoff_time_in_minutes:
            self.composite_logger.log_debug("Time Remaining: " + str(timedelta(seconds=int(remaining_time_in_minutes * 60))) + ", Cutoff time: " + str(timedelta(minutes=cutoff_time_in_minutes)))
            return True
        else:
            self.composite_logger.log_warning("Time Remaining: " + str(timedelta(seconds=int(remaining_time_in_minutes * 60))) + ", Cutoff time: " + str(timedelta(minutes=cutoff_time_in_minutes)) + " [Out of time!]")
            return False
