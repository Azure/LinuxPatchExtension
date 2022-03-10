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
import time
from core.src.bootstrap.Constants import Constants


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

    def start_assessment(self):
        """ Start a patch assessment """
        self.status_handler.set_current_operation(Constants.ASSESSMENT)
        self.raise_if_agent_incompatible()

        self.composite_logger.log('\nStarting patch assessment...')

        self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_TRANSITIONING)
        self.composite_logger.log("\nMachine Id: " + self.env_layer.platform.node())
        self.composite_logger.log("Activity Id: " + self.execution_config.activity_id)
        self.composite_logger.log("Operation request time: " + self.execution_config.start_time)

        self.composite_logger.log("\n\nGetting available patches...")
        self.package_manager.refresh_repo()
        self.status_handler.reset_assessment_data()

        for i in range(0, Constants.MAX_ASSESSMENT_RETRY_COUNT):
            try:
                if self.lifecycle_manager is not None:
                    self.lifecycle_manager.lifecycle_status_check()     # may terminate the code abruptly, as designed
                packages, package_versions = self.package_manager.get_all_updates()
                self.telemetry_writer.write_event("Full assessment: " + str(packages), Constants.TelemetryEventLevel.Verbose)
                self.status_handler.set_package_assessment_status(packages, package_versions)
                if self.lifecycle_manager is not None:
                    self.lifecycle_manager.lifecycle_status_check()     # may terminate the code abruptly, as designed
                sec_packages, sec_package_versions = self.package_manager.get_security_updates()
                self.telemetry_writer.write_event("Security assessment: " + str(sec_packages), Constants.TelemetryEventLevel.Verbose)
                self.status_handler.set_package_assessment_status(sec_packages, sec_package_versions, "Security")
                self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)
                break
            except Exception as error:
                if i < Constants.MAX_ASSESSMENT_RETRY_COUNT:
                    error_msg = 'Retryable error retrieving available patches: ' + repr(error)
                    self.composite_logger.log_warning(error_msg)
                    self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                    time.sleep(2*(i + 1))
                else:
                    error_msg = 'Error retrieving available patches: ' + repr(error)
                    self.composite_logger.log_error(error_msg)
                    self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                    if Constants.ERROR_ADDED_TO_STATUS not in repr(error):
                        error.args = (error.args, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
                    self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
                    raise

        self.composite_logger.log("\nPatch assessment completed.\n")
        return True

    def raise_if_agent_incompatible(self):
        if self.lifecycle_manager.get_vm_cloud_type() == Constants.VMCloudType.ARC and self.execution_config.operation not in [Constants.ASSESSMENT, Constants.INSTALLATION]:
            self.composite_logger.log("Skipping agent compatibility check for Arc cloud type when operation is not manual")
            return
        if not self.telemetry_writer.is_agent_compatible():
            error_msg = "{0} [{1}]".format(Constants.TELEMETRY_AT_AGENT_NOT_COMPATIBLE_ERROR_MSG, self.telemetry_writer.get_telemetry_diagnostics())
            self.composite_logger.log_error(error_msg)
            raise Exception(error_msg)

        self.composite_logger.log("{0} [{1}]".format(Constants.TELEMETRY_AT_AGENT_COMPATIBLE_MSG, self.telemetry_writer.get_telemetry_diagnostics()))

