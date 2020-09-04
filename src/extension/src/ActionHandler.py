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
import glob
import os
import shutil
from extension.src.Constants import Constants
from extension.src.EnableCommandHandler import EnableCommandHandler
from extension.src.InstallCommandHandler import InstallCommandHandler


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

        # config folder path is usually something like: /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-<version>/config
        try:
            self.logger.log("Extension is being updated to the latest version. Copying the required extension artifacts from previous version to the current one")
            new_version_config_folder = self.ext_env_handler.config_folder
            extension_pardir = os.path.abspath(os.path.join(new_version_config_folder, os.path.pardir, os.path.pardir))
            paths_to_all_versions = self.get_all_versions(extension_pardir)
            if len(paths_to_all_versions) <= 1:
                self.logger.log_error("No earlier versions found for the extension")
                return Constants.ExitCode.HandlerFailed

            self.logger.log("Sorting paths to all version specific extension artifacts on the machine in descending order on version and fetching the immediate previous version path...")
            paths_to_all_versions.sort(reverse=True)
            previous_version_path = paths_to_all_versions[1]
            if previous_version_path is None or previous_version_path == "" or not os.path.exists(previous_version_path):
                self.logger.log_error("Could not find path where previous extension version artifacts are stored. Cannot copy the required artifacts to the latest version")
                return Constants.ExitCode.HandlerFailed

            self.logger.log("Previous version path. [Path={0}]".format(str(previous_version_path)))
            for root, dirs, files in os.walk(previous_version_path):
                for file_name in files:
                    #ToDo: do we copy .settings file also?
                    if Constants.EXT_STATE_FILE in file_name or Constants.CORE_STATE_FILE in file_name or ".bak" in file_name:
                        file_path = os.path.join(root, file_name)
                        self.logger.log("Copying file. [Source={0}] [Destination={1}]".format(str(file_path), str(new_version_config_folder)))
                        shutil.copy(file_path, new_version_config_folder)
            self.logger.log("Extension updated")
            return Constants.ExitCode.Okay
        except Exception as error:
            self.logger.log_error("Error occurred during extension update. [Error={0}]".format(repr(error)))
            return Constants.ExitCode.HandlerFailed

    @staticmethod
    def get_all_versions(extension_pardir):
        return glob.glob(extension_pardir + '/*LinuxPatchExtension*')

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
