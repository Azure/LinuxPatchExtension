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

""" A patch assessment """
import datetime
import json
import os
import shutil
import time
from core.src.bootstrap.Constants import Constants
from core_logic.patch_operators.PatchOperator import PatchOperator
from core.src.core_logic.Stopwatch import Stopwatch

# do not instantiate directly - these are exclusively for type hinting support
from core.src.bootstrap.EnvLayer import EnvLayer
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.src.local_loggers.CompositeLogger import CompositeLogger
from core.src.service_interfaces.TelemetryWriter import TelemetryWriter
from core.src.service_interfaces.StatusHandler import StatusHandler
from core.src.package_managers.PackageManager import PackageManager
from core.src.service_interfaces.lifecycle_managers.LifecycleManager import LifecycleManager


class PatchAssessor(PatchOperator):
    """ Wrapper class of a single patch assessment """
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager, lifecycle_manager):
        # type: (EnvLayer, ExecutionConfig, CompositeLogger, TelemetryWriter, StatusHandler, PackageManager, LifecycleManager) -> None
        super(PatchAssessor, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager, lifecycle_manager, operation_name=Constants.Op.ASSESSMENT)
        self.package_manager_name = self.package_manager.package_manager_name
        self.assessment_state_file_path = os.path.join(self.execution_config.config_folder, Constants.StateFiles.ASSESSMENT)
        self.stopwatch = Stopwatch(self.env_layer, self.telemetry_writer, self.composite_logger)

    # region - PatchOperator interface implementations
    def should_operation_run(self):
        """ [Interface implementation] Performs evaluation of if the specific operation should be running at all """
        if (not self.execution_config.exec_auto_assess_only) or (self.execution_config.exec_auto_assess_only and self.should_auto_assessment_run()):
            return True     # regular assessment or (auto-assessment that is eligible to run)

        self.composite_logger.log_debug("[PA] Skipping automatic patch assessment... [ShouldAutoAssessmentRun=False]\n")
        self.lifecycle_manager.lifecycle_status_check()
        return False

    def start_retryable_operation_unit(self):
        """ [Interface implementation] The core retryable actions for patch operation """
        self.operation_successful = True
        self.operation_exception_error = None

        self.write_assessment_state()  # success / failure does not matter, only that an attempt started
        self.package_manager.refresh_repo()
        self.status_handler.reset_assessment_data()

        if self.lifecycle_manager is not None:
            self.lifecycle_manager.lifecycle_status_check()  # may terminate the code abruptly, as designed

        # All updates
        packages, package_versions = self.package_manager.get_all_updates()
        self.telemetry_writer.write_event("Full assessment: " + str(packages), Constants.EventLevel.Verbose)
        self.status_handler.set_package_assessment_status(packages, package_versions)
        if self.lifecycle_manager is not None:
            self.lifecycle_manager.lifecycle_status_check()  # may terminate the code abruptly, as designed
        sec_packages, sec_package_versions = self.package_manager.get_security_updates()

        # Tag security updates
        self.telemetry_writer.write_event("Security assessment: " + str(sec_packages), Constants.EventLevel.Verbose)
        self.status_handler.set_package_assessment_status(sec_packages, sec_package_versions, Constants.PackageClassification.SECURITY)

        # Set the security-esm packages in status.
        self.package_manager.set_security_esm_package_status(Constants.Op.ASSESSMENT, packages=[])

        # ensure reboot status is set
        reboot_pending = self.package_manager.is_reboot_pending()
        self.status_handler.set_reboot_pending(reboot_pending)

        self.status_handler.set_assessment_substatus_json(status=Constants.Status.SUCCESS)
        self.set_final_operation_status()

    def process_operation_terminal_exception(self, error):
        """ [Interface implementation] Exception handling post all retries for the patch operation """
        error_msg = "Error completing patch assessment. [Error={0}]".format(repr(error))
        self.operation_successful = False
        self.operation_exception_error = error_msg
        self.status_handler.set_assessment_substatus_json(status=Constants.Status.ERROR)
        self.status_handler.add_error_to_status_and_log_error(message=error_msg, raise_exception=False)

    def set_final_operation_status(self):
        """ [Interface implementation] Business logic to write the final status (implicitly covering external dependencies from external callers) """
        """ Writes the final overall status after any pre-requisite operation is also in a terminal state - currently this is only assessment """
        overall_status = Constants.Status.SUCCESS if self.operation_successful else Constants.Status.ERROR
        self.set_operation_status(status=overall_status, error=self.operation_exception_error)

    def set_operation_status(self, status=Constants.Status.TRANSITIONING, error=None):
        """ [Interface implementation] Generic operation status setter """
        self.operation_status = status
        if error is not None:
            self.status_handler.add_error_to_status_and_log_error(message="Error in patch assessment operation. [Error={0}]".format(repr(error)), raise_exception=False)
        self.status_handler.set_assessment_substatus_json(status=status)
    # endregion - PatchOperator interface implementations

    # region - Auto-assessment extensions
    def should_auto_assessment_run(self):
        """ Checks if enough time has passed since the last run """
        try:
            assessment_state = self.read_assessment_state()
            last_start_in_seconds_since_epoch = assessment_state['lastStartInSecondsSinceEpoch']    # get last start time
        except Exception as error:
            self.composite_logger.log_warning("[PA] No valid last start information available for auto-assessment.")
            return True

        # get minimum elapsed time required - difference between max allowed (passed down) and a safe buffer to prevent exceeding that
        maximum_assessment_interval_in_seconds = self.convert_iso8601_duration_to_total_seconds(self.execution_config.maximum_assessment_interval)
        maximum_assessment_interval_buffer_in_seconds = self.convert_iso8601_duration_to_total_seconds(Constants.AUTO_ASSESSMENT_INTERVAL_BUFFER)
        minimum_elapsed_time_required_in_seconds = maximum_assessment_interval_in_seconds - maximum_assessment_interval_buffer_in_seconds

        # check if required duration has passed
        elapsed_time_in_seconds = self.__get_seconds_since_epoch() - last_start_in_seconds_since_epoch
        if elapsed_time_in_seconds < 0:
            self.composite_logger.log_warning("[PA] Anomaly detected in system time now or during the last assessment run. Assessment will run anyway.")
            return True
        else:
            return elapsed_time_in_seconds >= minimum_elapsed_time_required_in_seconds

    def read_assessment_state(self):
        """ Reads the assessment state file. """
        self.composite_logger.log_verbose("[PA] Reading assessment state...")
        if not os.path.exists(self.assessment_state_file_path) or not os.path.isfile(self.assessment_state_file_path):
            # Neutralizes directories
            if os.path.isdir(self.assessment_state_file_path):
                self.composite_logger.log_debug("[PA] Assessment state file path returned a directory. Attempting to reset.")
                shutil.rmtree(self.assessment_state_file_path)
            # Writes a vanilla assessment state file
            self.write_assessment_state(first_write=True)

        # Read (with retries for only IO Errors)
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.assessment_state_file_path, mode="r") as file_handle:
                    return json.load(file_handle)['assessmentState']
            except Exception as error:
                if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                    self.composite_logger.log_verbose("[PA] Exception on assessment state read. [Exception={0}][RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("[PA] Unable to read assessment state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise

    def write_assessment_state(self, first_write=False):
        """
        AssessmentState.json sample structure:
        {
            "number": "<sequence number>",
            "lastStartInSecondsSinceEpoch": "<number>",
            "lastHeartbeat": "<timestamp>",
            "processIds": ["", ...],
            "autoAssessment": "<true/false>"
        }
        """
        self.composite_logger.log_verbose("[PA] Updating assessment state... ")

        # lastHeartbeat below is redundant, but is present for ease of debuggability
        assessment_state = {'number': self.execution_config.sequence_number,
                            'lastStartInSecondsSinceEpoch': self.__get_seconds_since_epoch() if not first_write else 0,  # Set lastStartInSecondsSinceEpoch to 0 if file did not exist before (first write) to ensure it can run assessment when first created
                            'lastHeartbeat': str(self.env_layer.datetime.timestamp()),
                            'processIds': [os.getpid()],
                            'autoAssessment': str(self.execution_config.exec_auto_assess_only)}
        assessment_state_payload = json.dumps({"assessmentState": assessment_state})

        if os.path.isdir(self.assessment_state_file_path):
            self.composite_logger.log_debug("[PA] Assessment state file path returned a directory. Attempting to reset.")
            shutil.rmtree(self.assessment_state_file_path)

        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.assessment_state_file_path, 'w+') as file_handle:
                    file_handle.write(assessment_state_payload)
                    break
            except Exception as error:
                if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                    self.composite_logger.log_verbose("[PA] Exception on assessment state update. [Exception={0}][RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("[PA] Unable to write to assessment state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise

        self.composite_logger.log_verbose("[PA] Completed updating assessment state.")

    @staticmethod
    def __get_seconds_since_epoch():
        return int((datetime.datetime.now() - datetime.datetime(1970, 1, 1)).total_seconds())

    @staticmethod
    def convert_iso8601_duration_to_total_seconds(duration):
        """ No non-default period (Y,M,W,D) is supported. Time is supported (H,M,S). """
        remaining = str(duration)
        if 'PT' not in remaining:
            raise Exception("Unexpected duration format. [Duration={0}]".format(duration))

        def __extract_most_significant_unit_from_duration(duration_portion, unit_delimiter):
            duration_split = duration_portion.split(unit_delimiter)
            duration_split_len = len(duration_split)
            most_significant_unit = 0 if duration_split_len != 2 else duration_split[0]
            remaining_duration_portion = '' if duration_split_len == 0 else duration_split[duration_split_len - 1]
            return most_significant_unit, remaining_duration_portion

        discard, remaining = __extract_most_significant_unit_from_duration(remaining, 'PT')
        hours, remaining = __extract_most_significant_unit_from_duration(remaining, 'H')
        minutes, remaining = __extract_most_significant_unit_from_duration(remaining, 'M')
        seconds, remaining = __extract_most_significant_unit_from_duration(remaining, 'S')

        return datetime.timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds)).total_seconds()

