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
import time
from distutils.version import LooseVersion

from extension.src.Constants import Constants
from extension.src.EnableCommandHandler import EnableCommandHandler
from extension.src.InstallCommandHandler import InstallCommandHandler
from extension.src.local_loggers.StdOutFileMirror import StdOutFileMirror


class ActionHandler(object):
    """Responsible for identifying the action to perform based on the user input"""
    def __init__(self, logger, utility, runtime_context_handler, json_file_handler, ext_env_handler, ext_config_settings_handler, core_state_handler, ext_state_handler, ext_output_status_handler, process_handler, cmd_exec_start_time):
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
        self.stdout_file_mirror = None
        self.file_logger = None

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

    def setup_file_logger(self, action):
        if self.file_logger is not None or self.stdout_file_mirror is not None:
            self.logger.log_error("Log file handles from the previous operation were not closed correctly. Closing them and initializing new ones for this operation.")
            self.close_file_logger()

        log_file_name = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S") + "_" + str(action)
        self.file_logger = self.utility.create_log_file(self.ext_env_handler.log_folder, log_file_name)
        if self.file_logger is not None:
            self.logger.file_logger = self.file_logger
            self.stdout_file_mirror = StdOutFileMirror(self.file_logger)

    def close_file_logger(self):
        if self.stdout_file_mirror is not None:
            self.stdout_file_mirror.stop()
        if self.file_logger is not None:
            self.file_logger.close()

    def install(self):
        try:
            self.setup_file_logger(action=Constants.INSTALL)
            self.logger.log("Extension installation started")
            install_command_handler = InstallCommandHandler(self.logger, self.ext_env_handler)
            return install_command_handler.execute_handler_action()

        except Exception as error:
            self.logger.log_error("Error occurred during extension install. [Error={0}]".format(repr(error)))
            return Constants.ExitCode.HandlerFailed

        finally:
            self.close_file_logger()

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
            self.setup_file_logger(action=Constants.UPDATE)
            self.logger.log("Extension is being updated to the latest version. Copying the required extension artifacts from preceding version to the current one")

            # fetch all earlier extension versions available on the machine
            new_version_config_folder = self.ext_env_handler.config_folder
            extension_pardir = os.path.abspath(os.path.join(new_version_config_folder, os.path.pardir, os.path.pardir))
            self.logger.log("Parent directory for all extension version artifacts [Directory={0}]".format(str(extension_pardir)))
            paths_to_all_versions = self.get_all_versions(extension_pardir)
            self.logger.log("List of all extension versions found on the machine. [All Versions={0}]".format(paths_to_all_versions))
            if len(paths_to_all_versions) <= 1:
                # Extension Update action called when
                # a) artifacts for the preceding version do not exist on the machine, or
                # b) after all artifacts from the preceding versions have been deleted
                self.logger.log_error("No earlier versions for the extension found on the machine. So, could not copy any references to the current version.")
                return Constants.ExitCode.HandlerFailed

            # identify the version preceding current
            self.logger.log("Fetching the extension version preceding current from all available versions...")
            paths_to_all_versions.sort(reverse=True, key=LooseVersion)
            preceding_version_path = paths_to_all_versions[1]
            if preceding_version_path is None or preceding_version_path == "" or not os.path.exists(preceding_version_path):
                self.logger.log_error("Could not find path where preceding extension version artifacts are stored. Hence, cannot copy the required artifacts to the latest version. "
                                      "[Preceding extension version path={0}]".format(str(preceding_version_path)))
                return Constants.ExitCode.HandlerFailed
            self.logger.log("Preceding version path. [Path={0}]".format(str(preceding_version_path)))

            # copy all required files from preceding version to current
            self.copy_config_files(preceding_version_path, new_version_config_folder)

            self.logger.log("All update actions from extension handler completed.")
            return Constants.ExitCode.Okay

        except Exception as error:
            self.logger.log_error("Error occurred during extension update. [Error={0}]".format(repr(error)))
            return Constants.ExitCode.HandlerFailed

        finally:
            self.close_file_logger()

    @staticmethod
    def get_all_versions(extension_pardir):
        return glob.glob(extension_pardir + '/*LinuxPatchExtension*')

    def copy_config_files(self, src, dst, raise_if_not_copied=False):
        """ Copies files, required by the extension, from the given config/src folder """
        self.logger.log("Copying only the files required by the extension for current and future operations. Any other files created by the Guest agent or extension, such as configuration settings, handlerstate, etc, that are not required in future, will not be copied.")

        # get all the required files to be copied from parent dir
        files_to_copy = []
        for root, dirs, files in os.walk(src):
            for file_name in files:
                if Constants.EXT_STATE_FILE not in file_name and Constants.CORE_STATE_FILE not in file_name and ".bak" not in file_name:
                    continue
                file_path = os.path.join(root, file_name)
                files_to_copy.append(file_path)
        self.logger.log("List of files to be copied from preceding extension version to the current: [Files to be copied={0}]".format(str(files_to_copy)))

        # copy each file
        for file_to_copy in files_to_copy:
            for i in range(0, Constants.MAX_IO_RETRIES):
                try:
                    self.logger.log("Copying file. [Source={0}] [Destination={1}]".format(str(file_to_copy), str(dst)))
                    shutil.copy(file_to_copy, dst)
                    break
                except Exception as error:
                    if i < Constants.MAX_IO_RETRIES:
                        time.sleep(i + 1)
                    else:
                        error_msg = "Failed to copy file after {0} tries. [Source={1}] [Destination={2}] [Exception={3}]".format(Constants.MAX_IO_RETRIES, str(file_to_copy), str(dst), repr(error))
                        self.logger.log_error(error_msg)
                        if raise_if_not_copied:
                            raise Exception(error_msg)

        self.logger.log("All required files from the preceding extension version were copied to current one")

    def uninstall(self):
        try:
            self.setup_file_logger(action=Constants.UNINSTALL)
            self.logger.log("Extension uninstalled")
            return Constants.ExitCode.Okay

        except Exception as error:
            self.logger.log_error("Error occurred during extension uninstall. [Error={0}]".format(repr(error)))
            return Constants.ExitCode.HandlerFailed

        finally:
            self.close_file_logger()

    def enable(self):
        try:
            self.setup_file_logger(action=Constants.ENABLE)
            self.logger.log("Enable triggered on extension")
            enable_command_handler = EnableCommandHandler(self.logger, self.utility, self.runtime_context_handler, self.ext_env_handler, self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, self.ext_output_status_handler, self.process_handler, self.cmd_exec_start_time)
            return enable_command_handler.execute_handler_action()

        except Exception as error:
            self.logger.log_error("Error occurred during extension enable. [Error={0}]".format(repr(error)))
            return Constants.ExitCode.HandlerFailed
        finally:
            self.close_file_logger()

    def disable(self):
        try:
            self.setup_file_logger(action=Constants.DISABLE)
            self.logger.log("Disable triggered on extension")
            prev_patch_max_end_time = self.cmd_exec_start_time + datetime.timedelta(hours=0, minutes=Constants.DISABLE_MAX_RUNTIME)
            self.runtime_context_handler.process_previous_patch_operation(self.core_state_handler, self.process_handler, prev_patch_max_end_time, core_state_content=None)
            self.logger.log("Extension disabled successfully")
            return Constants.ExitCode.Okay

        except Exception as error:
            self.logger.log_error("Error occurred during extension disable. [Error={0}]".format(repr(error)))
            return Constants.ExitCode.HandlerFailed
        finally:
            self.close_file_logger()

    def reset(self):
        try:
            self.setup_file_logger(action=Constants.RESET)
            self.logger.log("Reset triggered on extension, deleting CoreState and ExtState files")
            self.utility.delete_file(self.core_state_handler.dir_path, self.core_state_handler.file, raise_if_not_found=False)
            self.utility.delete_file(self.ext_state_handler.dir_path, self.ext_state_handler.file, raise_if_not_found=False)
            return Constants.ExitCode.Okay

        except Exception as error:
            self.logger.log_error("Error occurred during extension reset. [Error={0}]".format(repr(error)))
            return Constants.ExitCode.HandlerFailed
        finally:
            self.close_file_logger()

