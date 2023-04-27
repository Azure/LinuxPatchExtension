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

""" A patch assessment """
import datetime
import json
import os
import shutil
import time
from core.src.bootstrap.Constants import Constants
from core.src.core_logic.Stopwatch import Stopwatch


class PatchAssessor(object):
    """ Wrapper class of a single patch assessment """
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager, lifecycle_manager):
        self.env_layer = env_layer
        self.execution_config = execution_config

        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.status_handler = status_handler
        self.lifecycle_manager = lifecycle_manager
        self.package_manager = package_manager
        self.package_manager_name = self.package_manager.get_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY)
        self.assessment_state_file_path = os.path.join(self.execution_config.config_folder, Constants.ASSESSMENT_STATE_FILE)
        self.stopwatch = Stopwatch(self.env_layer, self.telemetry_writer, self.composite_logger)

    def start_assessment(self):
        """ Start a patch assessment """
        self.status_handler.set_current_operation(Constants.ASSESSMENT)
        self.raise_if_telemetry_unsupported()

        if self.execution_config.exec_auto_assess_only and not self.should_auto_assessment_run():
            self.composite_logger.log("\nAutomatic patch assessment not required at this time.\n")
            self.lifecycle_manager.lifecycle_status_check()
            return True

        self.composite_logger.log('\nStarting patch assessment...')
        self.write_assessment_state()   # success / failure does not matter, only that an attempt started

        self.stopwatch.start()

        self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_TRANSITIONING)
        self.composite_logger.log("\nMachine Id: " + self.env_layer.platform.node())
        self.composite_logger.log("Activity Id: " + self.execution_config.activity_id)
        self.composite_logger.log("Operation request time: " + self.execution_config.start_time)

        self.composite_logger.log("\n\nGetting available patches...")
        self.package_manager.refresh_repo()
        self.status_handler.reset_assessment_data()
        retry_count = 0

        for i in range(0, Constants.MAX_ASSESSMENT_RETRY_COUNT):
            try:
                if self.lifecycle_manager is not None:
                    self.lifecycle_manager.lifecycle_status_check()     # may terminate the code abruptly, as designed

                # All updates
                retry_count = retry_count + 1
                
                # All updates
                packages, package_versions = self.package_manager.get_all_updates()
                self.telemetry_writer.write_event("Full assessment: " + str(packages), Constants.TelemetryEventLevel.Verbose)
                self.status_handler.set_package_assessment_status(packages, package_versions)
                if self.lifecycle_manager is not None:
                    self.lifecycle_manager.lifecycle_status_check()     # may terminate the code abruptly, as designed
                sec_packages, sec_package_versions = self.package_manager.get_security_updates()

                # Tag security updates
                self.telemetry_writer.write_event("Security assessment: " + str(sec_packages), Constants.TelemetryEventLevel.Verbose)
                self.status_handler.set_package_assessment_status(sec_packages, sec_package_versions, "Security")

                if self.package_manager.get_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY) == Constants.APT:
                    security_esm_update_query_success, security_esm_updates, security_esm_updates_versions = self.package_manager.get_security_esm_updates()
                    if security_esm_update_query_success:
                        self.telemetry_writer.write_event("Security-ESM assessment: " + str(security_esm_updates), Constants.TelemetryEventLevel.Verbose)
                        self.status_handler.set_package_assessment_status(security_esm_updates, security_esm_updates_versions, "Security-ESM")

                # ensure reboot status is set
                reboot_pending = self.package_manager.is_reboot_pending()
                self.status_handler.set_reboot_pending(reboot_pending)

                self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)

            except Exception as error:
                if i < Constants.MAX_ASSESSMENT_RETRY_COUNT - 1:
                    error_msg = 'Retriable error retrieving available patches: ' + repr(error)
                    self.composite_logger.log_warning(error_msg)
                    self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                    time.sleep(2*(i + 1))
                else:
                    error_msg = 'Error retrieving available patches: ' + repr(error)
                    self.composite_logger.log_error(error_msg)
                    self.write_assessment_perf_logs(retry_count, Constants.TaskStatus.FAILED, error_msg)
                    self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                    if Constants.ERROR_ADDED_TO_STATUS not in repr(error):
                        error.args = (error.args, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
                    self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
                    raise

        self.write_assessment_perf_logs(retry_count, Constants.TaskStatus.SUCCEEDED, "")
        self.composite_logger.log("\nPatch assessment completed.\n")
        return True

    def write_assessment_perf_logs(self, retry_count, task_status, error_msg):
        assessment_perf_log = "[{0}={1}][{2}={3}][{4}={5}][{6}={7}][{8}={9}][{10}={11}]".format(
                               Constants.PerfLogTrackerParams.TASK, Constants.ASSESSMENT, Constants.PerfLogTrackerParams.TASK_STATUS, str(task_status),
                               Constants.PerfLogTrackerParams.ERROR_MSG, error_msg, Constants.PerfLogTrackerParams.PACKAGE_MANAGER, self.package_manager_name,
                               Constants.PerfLogTrackerParams.RETRY_COUNT, str(retry_count), Constants.PerfLogTrackerParams.MACHINE_INFO, self.telemetry_writer.machine_info)
        self.stopwatch.stop_and_write_telemetry(assessment_perf_log)

    def raise_if_telemetry_unsupported(self):
        if self.lifecycle_manager.get_vm_cloud_type() == Constants.VMCloudType.ARC and self.execution_config.operation not in [Constants.ASSESSMENT, Constants.INSTALLATION]:
            self.composite_logger.log("Skipping telemetry compatibility check for Arc cloud type when operation is not manual")
            return
        if not self.telemetry_writer.is_telemetry_supported():
            error_msg = "{0}".format(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG)
            self.composite_logger.log_error(error_msg)
            self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
            raise Exception(error_msg)

        self.composite_logger.log("{0}".format(Constants.TELEMETRY_COMPATIBLE_MSG))

    # region - Auto-assessment extensions
    def should_auto_assessment_run(self):
        # get last start time
        try:
            assessment_state = self.read_assessment_state()
            last_start_in_seconds_since_epoch = assessment_state['lastStartInSecondsSinceEpoch']
        except Exception as error:
            self.composite_logger.log_warning("No valid last start information available for auto-assessment.")
            return True

        # get minimum elapsed time required - difference between max allowed (passed down) and a safe buffer to prevent exceeding that
        maximum_assessment_interval_in_seconds = self.convert_iso8601_duration_to_total_seconds(self.execution_config.maximum_assessment_interval)
        maximum_assessment_interval_buffer_in_seconds = self.convert_iso8601_duration_to_total_seconds(Constants.AUTO_ASSESSMENT_INTERVAL_BUFFER)
        minimum_elapsed_time_required_in_seconds = maximum_assessment_interval_in_seconds - maximum_assessment_interval_buffer_in_seconds

        # check if required duration has passed
        elapsed_time_in_seconds = self.__get_seconds_since_epoch() - last_start_in_seconds_since_epoch
        if elapsed_time_in_seconds < 0:
            self.composite_logger.log_warning("Anomaly detected in system time now or during the last assessment run. Assessment will run anyway.")
            return True
        else:
            return elapsed_time_in_seconds >= minimum_elapsed_time_required_in_seconds

    def read_assessment_state(self):
        """ Reads the assessment state file. """
        self.composite_logger.log_debug("Reading assessment state...")
        if not os.path.exists(self.assessment_state_file_path) or not os.path.isfile(self.assessment_state_file_path):
            # Neutralizes directories
            if os.path.isdir(self.assessment_state_file_path):
                self.composite_logger.log_error("Assessment state file path returned a directory. Attempting to reset.")
                shutil.rmtree(self.assessment_state_file_path)
            # Writes a vanilla assessment statefile
            self.write_assessment_state(first_write=True)

        # Read (with retries for only IO Errors)
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.assessment_state_file_path, mode="r") as file_handle:
                    return json.load(file_handle)['assessmentState']
            except Exception as error:
                if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                    self.composite_logger.log_warning("Exception on assessment state read. [Exception={0}] [RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to read assessment state file (retries exhausted). [Exception={0}]".format(repr(error)))
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
        self.composite_logger.log_debug("Updating assessment state... ")

        # lastHeartbeat below is redundant, but is present for ease of debuggability
        assessment_state = {'number': self.execution_config.sequence_number,
                         # Set lastStartInSecondsSinceEpoch to 0 if file did not exist before (first write) to ensure it can run assessment when first created
                         'lastStartInSecondsSinceEpoch': self.__get_seconds_since_epoch() if not first_write else 0,
                         'lastHeartbeat': str(self.env_layer.datetime.timestamp()),
                         'processIds': [os.getpid()],
                         'autoAssessment': str(self.execution_config.exec_auto_assess_only)}
        assessment_state_payload = json.dumps({"assessmentState": assessment_state})

        if os.path.isdir(self.assessment_state_file_path):
            self.composite_logger.log_error("Assessment state file path returned a directory. Attempting to reset.")
            shutil.rmtree(self.assessment_state_file_path)

        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.assessment_state_file_path, 'w+') as file_handle:
                    file_handle.write(assessment_state_payload)
                    break
            except Exception as error:
                if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                    self.composite_logger.log_warning("Exception on assessment state update. [Exception={0}] [RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to write to assessment state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise

        self.composite_logger.log_debug("Completed updating assessment state.")

    @staticmethod
    def __get_seconds_since_epoch():
        return int((datetime.datetime.now() - datetime.datetime(1970, 1, 1)).total_seconds())

    def convert_iso8601_duration_to_total_seconds(self, duration):
        """
            No non-default period (Y,M,W,D) is supported. Time is supported (H,M,S).
        """
        remaining = str(duration)
        if 'PT' not in remaining:
            raise Exception("Unexpected duration format. [Duration={0}]".format(duration))

        discard, remaining = self.__extract_most_significant_unit_from_duration(remaining, 'PT')
        hours, remaining = self.__extract_most_significant_unit_from_duration(remaining, 'H')
        minutes, remaining = self.__extract_most_significant_unit_from_duration(remaining, 'M')
        seconds, remaining = self.__extract_most_significant_unit_from_duration(remaining, 'S')

        return datetime.timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds)).total_seconds()

    @staticmethod
    def __extract_most_significant_unit_from_duration(duration_portion, unit_delimiter):
        """ Internal helper function """
        duration_split = duration_portion.split(unit_delimiter)
        most_significant_unit = 0
        remaining_duration_portion = ''
        if len(duration_split) == 2:  # found and extracted
            most_significant_unit = duration_split[0]
            remaining_duration_portion = duration_split[1]
        elif len(duration_split) == 1:  # not found
            remaining_duration_portion = duration_split[0]

        return most_significant_unit, remaining_duration_portion
