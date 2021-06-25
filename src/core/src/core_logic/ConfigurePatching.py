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

""" Configure Patching """
from core.src.bootstrap.Constants import Constants


class ConfigurePatching(object):
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager):
        self.env_layer = env_layer
        self.execution_config = execution_config

        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.status_handler = status_handler

        self.package_manager = package_manager

    def start_configure_patching(self):
        """ Start configure patching """
        try:
            configure_patching_successful = False
            self.status_handler.set_current_operation(Constants.CONFIGURE_PATCHING)
            self.raise_if_agent_incompatible()
            self.composite_logger.log('\nStarting configure patching...')

            self.status_handler.set_configure_patching_substatus_json(status=Constants.STATUS_TRANSITIONING, automatic_os_patch_state=Constants.PATCH_STATE_UNKNOWN)
            self.composite_logger.log("\nMachine Id: " + self.env_layer.platform.node())
            self.composite_logger.log("Activity Id: " + self.execution_config.activity_id)
            self.composite_logger.log("Operation request time: " + self.execution_config.start_time)

            # get current auto os updates on the machine and log it in status file
            current_auto_os_patch_state = self.package_manager.get_current_auto_os_patch_state()
            self.status_handler.set_configure_patching_substatus_json(status=Constants.STATUS_TRANSITIONING, automatic_os_patch_state=current_auto_os_patch_state)

            # disable auto OS updates if VM is configured for platform updates only.
            # NOTE: this condition will be false for Assessment operations, since patchMode is not sent in the API request
            if current_auto_os_patch_state == Constants.PATCH_STATE_ENABLED and self.execution_config.patch_mode == Constants.AUTOMATIC_BY_PLATFORM:
                self.package_manager.disable_auto_os_update()

            # get current auto os updates on the machine and log it in status file
            current_auto_os_patch_state = self.package_manager.get_current_auto_os_patch_state()
            self.status_handler.set_configure_patching_substatus_json(status=Constants.STATUS_SUCCESS, automatic_os_patch_state=current_auto_os_patch_state)

        except Exception as error:
            error_msg = 'Error: ' + repr(error)
            self.composite_logger.log_error(error_msg)
            self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            if Constants.ERROR_ADDED_TO_STATUS not in repr(error):
                error.args = (error.args, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
            self.status_handler.set_configure_patching_substatus_json(status=Constants.STATUS_ERROR)
            configure_patching_successful = False

        configure_patching_successful = True
        self.composite_logger.log("\nConfigure patching completed.\n")
        return configure_patching_successful

    def raise_if_agent_incompatible(self):
        if not self.telemetry_writer.is_agent_compatible():
            error_msg = Constants.TELEMETRY_AT_AGENT_NOT_COMPATIBLE_ERROR_MSG
            self.composite_logger.log_error(error_msg)
            raise Exception(error_msg)

        self.composite_logger.log(Constants.TELEMETRY_AT_AGENT_COMPATIBLE_MSG)

