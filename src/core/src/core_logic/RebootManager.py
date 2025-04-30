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

""" Reboot management """
import time

from core.src.bootstrap.Constants import Constants


class RebootManager(object):
    """ Implements the reboot management logic """
    def __init__(self, env_layer, execution_config, composite_logger, status_handler, package_manager, default_reboot_setting=Constants.REBOOT_IF_REQUIRED):
        self.execution_config = execution_config

        self.composite_logger = composite_logger
        self.package_manager = package_manager
        self.status_handler = status_handler
        self.env_layer = env_layer

        self.__reboot_cmd = 'sudo shutdown -r '
        self.__maintenance_window_exceeded_flag = False   # flag to indicate if the maintenance window was exceeded **separately** at reboot manager

        self.__reboot_setting_sanitized = self.sanitize_reboot_setting(self.execution_config.reboot_setting, default_reboot_setting)

    # region - Reboot condition reporters
    @staticmethod
    def is_reboot_time_available(current_time_available):
        # type: (int) -> bool
        """ Check if time still available for system reboot """
        return current_time_available >= Constants.REBOOT_BUFFER_IN_MINUTES

    def is_reboot_pending(self):
        # type: () -> bool
        """ Check if a reboot is pending either from the package manager or the status handler """
        return self.package_manager.force_reboot or (self.status_handler and self.status_handler.is_reboot_pending)

    def has_maintenance_window_exceeded_at_reboot_manager(self):
        # type: () -> bool
        """ Check if the maintenance window was exceeded at reboot manager """
        return self.__maintenance_window_exceeded_flag

    def get_reboot_setting_sanitized(self):
        # type: () -> str
        """ Get the sanitized reboot setting """
        return self.__reboot_setting_sanitized
    # endregion

    # region - Reboot setting helpers
    def sanitize_reboot_setting(self, reboot_setting_key, default_reboot_setting):
        # type: (str, str) -> str
        """ Ensures that the value obtained is one we know what to do with. """
        reboot_setting = Constants.REBOOT_SETTINGS[default_reboot_setting]

        try:
            reboot_setting = Constants.REBOOT_SETTINGS[reboot_setting_key]
        except KeyError:
            error_msg = '[RM] Invalid reboot setting detected. [InvalidSetting={0}][DefaultFallback={1}]'.format(str(reboot_setting_key), str(default_reboot_setting))
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
        finally:
            return reboot_setting

    def is_setting(self, setting_to_check):
        # type: (str) -> bool
        return self.__reboot_setting_sanitized == setting_to_check
    # endregion

    # region - Reboot action methods
    def start_reboot_if_required_and_time_available(self, current_time_available):
        # type: (int) -> any
        """ Starts a reboot if required. Happens only at the end of the run if required. """
        reboot_pending = self.is_reboot_pending()

        # Log a special-case message if the package manager is forcing a reboot that's not normally visible on the machine (encoded into is_reboot_pending())
        if self.package_manager.force_reboot:
            self.composite_logger.log("[RM] A reboot is pending as the package manager required it.")

        # No-op - return false if config says never reboot
        if self.__reboot_setting_sanitized == Constants.REBOOT_NEVER:
            if reboot_pending:
                self.composite_logger.log_warning('[RM][!] Reboot is pending but BLOCKED by the customer configuration ({0}).'.format(str(Constants.REBOOT_NEVER)))
            else:
                self.composite_logger.log_debug('[RM] No reboot pending, and reboot is blocked regardless by the customer configuration ({0}).'.format(str(Constants.REBOOT_NEVER)))
            return False

        # No-op - return if system doesn't require it (and only reboot if it does)
        if self.__reboot_setting_sanitized == Constants.REBOOT_IF_REQUIRED and not reboot_pending:
            self.composite_logger.log_debug("[RM] No reboot pending detected. Reboot skipped as per customer configuration ({0}).".format(str(Constants.REBOOT_IF_REQUIRED)))
            return False

        # No-op - prevent repeated reboots
        if self.__reboot_setting_sanitized == Constants.REBOOT_ALWAYS and not reboot_pending and self.status_handler.get_installation_reboot_status() == Constants.RebootStatus.COMPLETED:
            self.composite_logger.log_debug("[RM] At least one reboot has occurred, and there's no reboot pending, so the conditions for the 'Reboot Always' setting is fulfilled and reboot won't be repeated.")
            return False

        # Try to reboot - if enough time is available
        if self.__reboot_setting_sanitized == Constants.REBOOT_ALWAYS or (self.__reboot_setting_sanitized == Constants.REBOOT_IF_REQUIRED and reboot_pending):
            if self.is_reboot_time_available(current_time_available):
                self.composite_logger.log_debug('[RM] Reboot is being scheduled, as per customer configuration ({0}). [RebootPending={1}][CurrentTimeAvailable={2}]'.format(str(self.__reboot_setting_sanitized), str(reboot_pending), str(current_time_available)))
                self.__start_reboot(maintenance_window_available_time_in_minutes=current_time_available)
                return True
            else:
                # Maintenance window will be marked exceeded as reboot is required and not enough time is available
                error_msg = '[RM][!] Insufficient time to schedule a required reboot ({0}). [RebootPending={1}][CurrentTimeAvailable={2}]'.format(str(self.__reboot_setting_sanitized), str(reboot_pending), str(current_time_available))
                self.composite_logger.log_error(error_msg)
                self.status_handler.add_error_to_status(str(error_msg), Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                self.__maintenance_window_exceeded_flag = True
                return False

        # No-op - This code should never be reached. If seen, it indicates a bug in the code.
        self.composite_logger.log_error('[RM] Bug-check: Unexpected code branch reached. [RebootSetting={0}][RebootPending={1}]'.format(str(self.__reboot_setting_sanitized), str(reboot_pending)))
        return False

    def __start_reboot(self, message="Azure VM Guest Patching initiated a reboot as part of an 'InstallPatches' operation.", maintenance_window_available_time_in_minutes=0):
        # type: (str, int) -> None
        """ Performs a controlled system reboot with a system-wide notification broadcast. """
        self.composite_logger.log("[RM] The machine is set to reboot in " + str(Constants.REBOOT_NOTIFY_WINDOW_IN_MINUTES) + " minutes.")
        self.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        reboot_init_time = self.env_layer.datetime.datetime_utcnow()

        # Reboot after system-wide notification broadcast - no new logins will be allowed after this point.
        self.env_layer.reboot_machine(self.__reboot_cmd + str(Constants.REBOOT_NOTIFY_WINDOW_IN_MINUTES) + ' ' + message)

        # Safety net - if the machine doesn't reboot, we need to fail the operation.
        max_allowable_time_to_reboot_in_minutes = self.__calc_max_allowable_time_to_reboot_in_minutes(maintenance_window_available_time_in_minutes)
        while 1:
            current_time = self.env_layer.datetime.datetime_utcnow()
            elapsed_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(current_time - reboot_init_time)

            # Keep logging to indicate machine hasn't rebooted yet. If successful, this will be the last log we see from this process.
            if elapsed_time_in_minutes < max_allowable_time_to_reboot_in_minutes:
                self.__reboot_wait_pulse(int(elapsed_time_in_minutes), int(max_allowable_time_to_reboot_in_minutes),
                                         maintenance_window_allowable_limit_remaining_in_minutes = int(maintenance_window_available_time_in_minutes - elapsed_time_in_minutes))
                continue

            # If we get here, the machine has not rebooted in the time we expected. We need to fail the operation.
            # This may be because of the following reasons:
            # 1. The machine is not responding to the reboot command because of a customer environment issue. (customer should retry after a forcing a control-plane reboot)
            # 2. The reboot command was externally interrupted during the broadcast period. (customer should retry after a forcing a control-plane reboot)
            # 3. The time required to handle changes prior to reboot is greater than the time we've allocated. (action on AzGPS if seen at scale in Azure)
            self.status_handler.set_installation_reboot_status(Constants.RebootStatus.FAILED)
            error_msg = "Customer environment issue: Reboot failed to proceed on the machine in a timely manner. Please retry the operation."
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

    def __reboot_wait_pulse(self, elapsed_time_in_minutes, max_allowable_time_to_reboot_in_minutes, maintenance_window_allowable_limit_remaining):
        # type: (int, int, int) -> None
        self.composite_logger.log("[RM] Waiting for machine reboot. [ElapsedTimeInMinutes={0}][MaxTimeInMinutes={1}][MWAllowableLimitRemainingInMins={2}]"
                                  .format(str(elapsed_time_in_minutes), str(max_allowable_time_to_reboot_in_minutes), str(maintenance_window_allowable_limit_remaining)))
        self.composite_logger.file_logger.flush()
        self.status_handler.set_installation_substatus_json()   # keep refreshing to minimize the chance of service-side timeout
        time.sleep(Constants.REBOOT_WAIT_PULSE_INTERVAL_IN_SECONDS)

    @staticmethod
    def __calc_max_allowable_time_to_reboot_in_minutes(maintenance_window_available_time_in_minutes):
        # type: (int) -> int
        """ Calculates the maximum amount of time to wait before considering the reboot attempt a failure. """

        # remove the reboot to machine ready time from the available time
        available_time = maintenance_window_available_time_in_minutes - Constants.REBOOT_TO_MACHINE_READY_TIME_IN_MINUTES

        if available_time >= Constants.REBOOT_WAIT_TIMEOUT_IN_MINUTES_MAX:
            # If the maintenance window is greater than the max, we can use the max.
            return Constants.REBOOT_WAIT_TIMEOUT_IN_MINUTES_MAX
        else:
            # Otherwise, we use the greater of the time available or the minimum wait timeout allowable.
            return max(available_time, Constants.REBOOT_WAIT_TIMEOUT_IN_MINUTES_MIN)
    # endregion
