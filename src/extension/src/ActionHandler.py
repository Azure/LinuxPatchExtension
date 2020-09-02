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

import datetime
from src.Constants import Constants
from src.EnableCommandHandler import EnableCommandHandler
from src.InstallCommandHandler import InstallCommandHandler


class ActionHandler(object):
    """Responsible for identifying the action to perform based on the user input"""
    def __init__(self, logger, utility, runtime_context_handler, json_file_handler, ext_env_handler, ext_config_settings_handler, core_state_handler, ext_state_handler, ext_output_status_handler, process_handler, cmd_exec_start_time, seq_no):
        self.logger = logger
        self.utility = utility
        self.runtime_context_handler = runtime_context_handler
        self.json_file_handler = json_file_handler
        self.ext_env_handler = ext_env_handler
        self.ext_config_settings_handler = ext_config_settings_handler
        self.core_state_handler = core_state_handler
        self.ext_state_handler = ext_state_handler
        self.ext_output_status_handler = ext_output_status_handler
        self.process_handler = process_handler
        self.cmd_exec_start_time = cmd_exec_start_time
        self.seq_no = seq_no

    def determine_operation(self, command):
        switcher = {
            "-install": self.install,
            "-uninstall": self.uninstall,
            "-disable": self.disable,
            "-enable": self.enable,
            "-update": self.update,
            "-reset": self.reset
        }
        try:
            return switcher[command]()
        except KeyError as e:
            raise e

    def install(self):
        self.logger.log("Extension installation started")
        install_command_handler = InstallCommandHandler(self.logger, self.ext_env_handler)
        return install_command_handler.execute_handler_action()

    def update(self):
        """ as per the extension user guide, upon update request, Azure agent calls
         1. disable on the prev version
         2. update on the new version
         3. uninstall on the prev version
         4. install (if updateMode is UpdateWithInstall)
         5. enable on the new version
         on uninstall the agent deletes removes configuration files"""
        # todo: in the test run verify if CoreState.json, ExtState.json and the .status files are deleted, if yes, move them to a separate location

        self.logger.log("Extension updated")
        return Constants.ExitCode.Okay

    def uninstall(self):
        # ToDo: verify if the agent deletes config files. And find out from the extension/agent team if we need to delete older logs
        self.logger.log("Extension uninstalled")
        return Constants.ExitCode.Okay

    def enable(self):
        self.logger.log("Enable triggered on extension")
        enable_command_handler = EnableCommandHandler(self.logger, self.utility, self.runtime_context_handler, self.ext_env_handler, self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, self.ext_output_status_handler, self.process_handler, self.cmd_exec_start_time, self.seq_no)
        return enable_command_handler.execute_handler_action()

    def disable(self):
        self.logger.log("Disable triggered on extension")
        prev_patch_max_end_time = self.cmd_exec_start_time + datetime.timedelta(hours=0, minutes=Constants.DISABLE_MAX_RUNTIME)
        self.runtime_context_handler.process_previous_patch_operation(self.core_state_handler, self.process_handler, prev_patch_max_end_time, core_state_content=None)
        self.logger.log("Extension disabled successfully")
        return Constants.ExitCode.Okay

    def reset(self):
        #ToDo: do we have to delete log and status files? and raise error if delete fails?
        self.logger.log("Reset triggered on extension, deleting CoreState and ExtState files")
        self.utility.delete_file(self.core_state_handler.dir_path, self.core_state_handler.file, raise_if_not_found=False)
        self.utility.delete_file(self.ext_state_handler.dir_path, self.ext_state_handler.file, raise_if_not_found=False)
        return Constants.ExitCode.Okay
