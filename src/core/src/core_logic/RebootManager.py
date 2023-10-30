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

"""Reboot management"""
import time
from core.src.bootstrap.Constants import Constants


class RebootManager(object):
    """Implements the reboot management logic"""
    def __init__(self, env_layer, execution_config, composite_logger, status_handler, package_manager, default_reboot_setting=Constants.RebootSettings.IF_REQUIRED):
        self.execution_config = execution_config

        self.composite_logger = composite_logger
        self.package_manager = package_manager
        self.status_handler = status_handler
        self.env_layer = env_layer

        self.minutes_to_shutdown = str((Constants.Config.REBOOT_BUFFER_IN_MINUTES - 5) if (Constants.Config.REBOOT_BUFFER_IN_MINUTES > 5) else Constants.Config.REBOOT_BUFFER_IN_MINUTES)  # give at least 5 minutes for a reboot unless the buffer is configured to be lower than that
        self.reboot_cmd = 'sudo shutdown -r '
        self.maintenance_window_exceeded_flag = False

        self.reboot_setting = self.sanitize_reboot_setting(self.execution_config.reboot_setting, default_reboot_setting)

    @staticmethod
    def is_reboot_time_available(current_time_available):
        """ Check if time still available for system reboot """
        return current_time_available >= Constants.Config.REBOOT_BUFFER_IN_MINUTES

    # REBOOT SETTING
    # ==============
    def sanitize_reboot_setting(self, reboot_setting_selected, default_reboot_setting):
        """ Ensures that the value obtained is one we know what to do with. """
        reboot_setting_selected = reboot_setting_selected.lower()

        for setting in (Constants.RebootSettings.NEVER, Constants.RebootSettings.IF_REQUIRED, Constants.RebootSettings.ALWAYS):
            if reboot_setting_selected == setting.lower():
                return setting

        self.status_handler.add_error_to_status_and_log_error(Constants.Errors.INVALID_REBOOT_SETTING.format(str(reboot_setting_selected), str(default_reboot_setting)))
        return default_reboot_setting

    def is_setting(self, setting_to_check):
        return self.reboot_setting == setting_to_check

    # REBOOT ACTION
    # =============
    def start_reboot(self, message="Azure Guest Patching Service initiated a reboot after a patch installation run."):
        """ Perform a system reboot """
        self.composite_logger.log("\nThe machine is set to reboot in " + self.minutes_to_shutdown + " minutes.")

        self.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        reboot_init_time = self.env_layer.datetime.datetime_utcnow()
        self.env_layer.reboot_machine(self.reboot_cmd + self.minutes_to_shutdown + ' ' + message)

        # Wait for timeout
        max_allowable_time_to_reboot_in_minutes = int(self.minutes_to_shutdown) + Constants.Config.REBOOT_WAIT_TIMEOUT_IN_MINUTES
        while 1:
            current_time = self.env_layer.datetime.datetime_utcnow()
            elapsed_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(current_time - reboot_init_time)
            if elapsed_time_in_minutes >= max_allowable_time_to_reboot_in_minutes:
                self.status_handler.set_installation_reboot_status(Constants.RebootStatus.FAILED)
                error_msg = "Reboot failed to proceed on the machine in a timely manner."
                self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
            else:
                self.composite_logger.file_logger.flush()
                self.composite_logger.log_verbose("Waiting for machine reboot. [ElapsedTimeInMinutes={0}][MaxTimeInMinutes={1}]".format(str(elapsed_time_in_minutes), str(max_allowable_time_to_reboot_in_minutes)))
                self.composite_logger.file_logger.flush()
                time.sleep(60)

    def start_reboot_if_required_and_time_available(self, current_time_available):
        """ Starts a reboot if required. Happens only at the end of the run if required. """
        self.composite_logger.log_verbose("[RM] Starting reboot if required and time available.")
        reboot_pending = self.is_reboot_pending()

        # return false if never
        if self.reboot_setting == Constants.RebootSettings.NEVER:
            if reboot_pending:
                self.status_handler.add_error_to_status_and_log_warning(message="Required reboot blocked by customer configuration. [RebootPending={0}][RebootSetting={1}]".format(str(reboot_pending), Constants.RebootSettings.NEVER))
            return False

        # return if system doesn't require it (and only reboot if it does)
        if self.reboot_setting == Constants.RebootSettings.IF_REQUIRED and not reboot_pending:
            self.composite_logger.log(" - There was no reboot pending detected. Reboot is being skipped as it's not required, as per patch installation configuration (" + str(Constants.RebootSettings.IF_REQUIRED) + ").")
            return False

        # prevent repeated reboots
        if self.reboot_setting == Constants.RebootSettings.ALWAYS and not reboot_pending and self.status_handler.get_installation_reboot_status() == Constants.RebootStatus.COMPLETED:
            self.composite_logger.log(" - At least one reboot has occurred, and there's no reboot pending, so the conditions for the 'Reboot Always' setting is fulfilled and reboot won't be repeated.")
            return False

        # attempt to reboot is enough time is available
        if self.reboot_setting == Constants.RebootSettings.ALWAYS or (self.reboot_setting == Constants.RebootSettings.IF_REQUIRED and reboot_pending):
            if self.is_reboot_time_available(current_time_available):
                self.composite_logger.log(' - Reboot is being scheduled, as per patch installation configuration (' + str(self.reboot_setting) + ').')
                self.composite_logger.log(" - Reboot-pending status: " + str(reboot_pending))
                self.start_reboot()
                return True
            else:
                error_msg = ' - There is not enough time to schedule a reboot as per patch installation configuration (' + str(self.reboot_setting) + '). Reboot-pending status: ' + str(reboot_pending)
                self.composite_logger.log_error(error_msg)
                self.status_handler.add_error_to_status("Reboot Management" + str(error_msg), Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                self.maintenance_window_exceeded_flag = True
                return False

    def is_reboot_pending(self):
        return self.package_manager.is_reboot_pending() or self.package_manager.force_reboot or (self.status_handler and self.status_handler.is_reboot_pending)

