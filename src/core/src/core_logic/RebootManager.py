"""Reboot management"""
import datetime
import subprocess
import time
from src.bootstrap.Constants import Constants


class RebootManager(object):
    """Implements the reboot management logic"""
    def __init__(self, env_layer, execution_config, composite_logger, status_handler, package_manager, default_reboot_setting='IfRequired'):
        self.execution_config = execution_config

        self.composite_logger = composite_logger
        self.package_manager = package_manager
        self.status_handler = status_handler
        self.env_layer = env_layer

        self.minutes_to_shutdown = str((Constants.REBOOT_BUFFER_IN_MINUTES - 5) if (Constants.REBOOT_BUFFER_IN_MINUTES > 5) else Constants.REBOOT_BUFFER_IN_MINUTES)  # give at least 5 minutes for a reboot unless the buffer is configured to be lower than that
        self.reboot_cmd = 'sudo shutdown -r '
        self.maintenance_window_exceeded_flag = False

        self.reboot_setting = self.sanitize_reboot_setting(self.execution_config.reboot_setting, default_reboot_setting)

    @staticmethod
    def is_reboot_time_available(current_time_available):
        """ Check if time still available for system reboot """
        return current_time_available >= Constants.REBOOT_BUFFER_IN_MINUTES

    # REBOOT SETTING
    # ==============
    def sanitize_reboot_setting(self, reboot_setting_key, default_reboot_setting):
        """ Ensures that the value obtained is one we know what to do with. """
        reboot_setting = Constants.REBOOT_SETTINGS[default_reboot_setting]

        try:
            reboot_setting = Constants.REBOOT_SETTINGS[reboot_setting_key]
        except KeyError:
            error_msg = 'Invalid reboot setting detected in update configuration: ' + str(reboot_setting_key)
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            self.composite_logger.log_warning('Defaulting reboot setting to: ' + str(default_reboot_setting))
        finally:
            return reboot_setting

    def is_setting(self, setting_to_check):
        return self.reboot_setting == setting_to_check

    # REBOOT ACTION
    # =============
    def start_reboot(self, message="Azure Patch Management initiated a reboot after a patch installation run."):
        """ Perform a system reboot """
        self.composite_logger.log("\nThe machine is set to reboot in " + self.minutes_to_shutdown + " minutes.")

        self.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        reboot_init_time = self.env_layer.datetime.datetime_utcnow()
        self.env_layer.reboot_machine(self.reboot_cmd + self.minutes_to_shutdown + ' ' + message)

        # Wait for timeout
        max_allowable_time_to_reboot_in_minutes = int(self.minutes_to_shutdown) + Constants.REBOOT_WAIT_TIMEOUT_IN_MINUTES
        while 1:
            current_time = self.env_layer.datetime.datetime_utcnow()
            elapsed_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(current_time - reboot_init_time)
            if elapsed_time_in_minutes >= max_allowable_time_to_reboot_in_minutes:
                self.status_handler.set_installation_reboot_status(Constants.RebootStatus.FAILED)
                error_msg = "Reboot failed to proceed on the machine in a timely manner."
                self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                error_msg += " [{0}]".format(Constants.ERROR_ADDED_TO_STATUS)
                raise Exception(error_msg)
            else:
                self.composite_logger.log_debug("Waiting for machine reboot. [ElapsedTimeInMinutes={0}] [MaxTimeInMinutes={1}]".format(str(elapsed_time_in_minutes), str(max_allowable_time_to_reboot_in_minutes)))
                time.sleep(60)

    def start_reboot_if_required_and_time_available(self, current_time_available):
        """ Starts a reboot if required. Happens only at the end of the run if required. """
        self.composite_logger.log("\nReboot Management")
        reboot_pending = False if not self.status_handler else self.status_handler.is_reboot_pending

        # return if never
        if self.reboot_setting == Constants.REBOOT_NEVER:
            if reboot_pending:
                self.composite_logger.log_warning(' - There is a reboot pending, but reboot is blocked, as per patch installation configuration. (' + str(Constants.REBOOT_NEVER) + ')')
            else:
                self.composite_logger.log_warning(' - There is no reboot pending, and reboot is blocked regardless, as per patch installation configuration (' + str(Constants.REBOOT_NEVER) + ').')
            return False

        # return if system doesn't require it (and only reboot if it does)
        if self.reboot_setting == Constants.REBOOT_IF_REQUIRED and not reboot_pending:
            self.composite_logger.log(" - There was no reboot pending detected. Reboot is being skipped as it's not required, as per patch installation configuration (" + str(Constants.REBOOT_IF_REQUIRED) + ").")
            return False

        # attempt to reboot is enough time is available
        if self.reboot_setting == Constants.REBOOT_ALWAYS or (self.reboot_setting == Constants.REBOOT_IF_REQUIRED and reboot_pending):
            if self.is_reboot_time_available(current_time_available):
                self.composite_logger.log(' - Reboot is being scheduled, as per patch installation configuration (' + str(self.reboot_setting) + ').')
                self.composite_logger.log(" - Reboot-pending status: " + str(reboot_pending))
                self.start_reboot()
                return True
            else:
                self.composite_logger.log_error(' - There is not enough time to schedule a reboot as per patch installation configuration (' + str(self.reboot_setting) + '). Reboot-pending status: ' + str(reboot_pending))
                self.maintenance_window_exceeded_flag = True
                return False
