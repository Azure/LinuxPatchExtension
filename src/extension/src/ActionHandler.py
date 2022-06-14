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
from os import path

from extension.src.Constants import Constants
from extension.src.EnableCommandHandler import EnableCommandHandler
from extension.src.InstallCommandHandler import InstallCommandHandler
from extension.src.local_loggers.StdOutFileMirror import StdOutFileMirror


class ActionHandler(object):
    """Responsible for identifying the action to perform based on the user input"""
    def __init__(self, logger, env_layer, telemetry_writer, utility, runtime_context_handler, json_file_handler, env_health_manager, ext_env_handler, ext_config_settings_handler, core_state_handler, ext_state_handler, ext_output_status_handler, process_handler, cmd_exec_start_time):
        self.logger = logger
        self.env_layer = env_layer
        self.telemetry_writer = telemetry_writer
        self.utility = utility
        self.runtime_context_handler = runtime_context_handler
        self.json_file_handler = json_file_handler
        self.env_health_manager = env_health_manager
        self.ext_env_handler = ext_env_handler
        self.ext_config_settings_handler = ext_config_settings_handler
        self.core_state_handler = core_state_handler
        self.ext_state_handler = ext_state_handler
        self.ext_output_status_handler = ext_output_status_handler
        self.process_handler = process_handler
        self.cmd_exec_start_time = cmd_exec_start_time
        self.stdout_file_mirror = None
        self.file_logger = None
        self.operation_id_substitute_for_all_actions_in_telemetry = str((datetime.datetime.utcnow()).strftime(Constants.UTC_DATETIME_FORMAT))

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

    def setup(self, action, log_message):
        self.setup_file_logger(action)
        self.setup_telemetry()
        self.logger.log(log_message)
        if action == Constants.ENABLE:
            self.write_basic_status()

    def write_basic_status(self):
        """ Writes a basic status file if one for the same sequence number does not exist """
        try:
            # read seq no, if not found, log error and return, as this code opportunistically tries to write status file as early as possible
            seq_no = self.ext_config_settings_handler.get_seq_no_from_env_var()
            if seq_no is None:
                self.logger.log_error("Since sequence number for current operation was not found, handler could not write an initial/basic status file")
                return

            # check if a status file for this sequence exists, if yes, do nothing
            if not os.path.exists(os.path.join(self.ext_env_handler.status_folder, str(seq_no) + Constants.STATUS_FILE_EXTENSION)):
                config_settings = self.ext_config_settings_handler.read_file(seq_no)

                # set activity_id in telemetry
                if self.telemetry_writer is not None:
                    self.telemetry_writer.set_operation_id(config_settings.__getattribute__(Constants.ConfigPublicSettingsFields.activity_id))

                operation = config_settings.__getattribute__(Constants.ConfigPublicSettingsFields.operation)
                # create status file with basic status
                self.ext_output_status_handler.write_status_file(operation, seq_no)

        except Exception as error:
            self.logger.log_error("Exception occurred while writing basic status. [Exception={0}]".format(repr(error)))

    def setup_file_logger(self, action):
        if self.file_logger is not None or self.stdout_file_mirror is not None:
            self.logger.log_error("Log file handles from the previous operation were not closed correctly. Closing them and initializing new ones for this operation.")
            self.tear_down()

        log_file_name = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S") + "_" + str(action)
        self.file_logger = self.utility.create_log_file(self.ext_env_handler.log_folder, log_file_name)
        if self.file_logger is not None:
            self.logger.file_logger = self.file_logger
            self.stdout_file_mirror = StdOutFileMirror(self.file_logger)

    def tear_down(self):
        if self.stdout_file_mirror is not None:
            self.stdout_file_mirror.stop()
        if self.file_logger is not None:
            self.file_logger.close()
            self.file_logger = None

    def setup_telemetry(self):
        """ Init telemetry if agent is compatible (events_folder is specified).
            Otherwise, error since guest agent does not support telemetry. """
        events_folder = self.ext_env_handler.events_folder
        self.telemetry_writer.events_folder_path = events_folder

        # If events folder is given but does not exist, create it before checking for is_telemetry_supported
        events_folder_previously_existed = True
        if events_folder is not None and not os.path.exists(events_folder):
            os.mkdir(events_folder)
            self.logger.log(
                "Events folder path found in HandlerEnvironment but does not exist on disk. Creating now. [Path={0}][AgentVersion={1}]".format(
                    str(events_folder), str(self.telemetry_writer.get_agent_version())))
            events_folder_previously_existed = False

        if self.telemetry_writer.is_telemetry_supported():
            # Guest agent fully supports telemetry

            # As this is a common function used by all handler actions, setting operation_id such that it will be the same timestamp for all handler actions, which can be used for identifying all events for an operation.
            # NOTE: Enable handler action will set operation_id to activity_id from config settings. And the same will be used in Core.
            self.telemetry_writer.set_operation_id(self.operation_id_substitute_for_all_actions_in_telemetry)
            self.__log_telemetry_info(telemetry_supported=True, events_folder_previously_existed=events_folder_previously_existed)
        else:
            # This line only logs to file since events_folder_path is not set in telemetry_writer
            self.__log_telemetry_info(telemetry_supported=False)

    def __log_telemetry_info(self, telemetry_supported, events_folder_previously_existed=False):
        """ Logs detailed information about telemetry and logs an error if telemetry is not supported. """
        events_folder = self.ext_env_handler.events_folder
        events_folder_str = str(events_folder) if events_folder is not None else ""
        agent_env_var_code = self.telemetry_writer.agent_env_var_code
        telemetry_info = "[EventsFolder={0}][EventsFolderExistedPreviously={1}][EnvVarCode={2}]".format(
            events_folder_str, str(events_folder_previously_existed), str(agent_env_var_code))

        if agent_env_var_code == Constants.AgentEnvVarStatusCode.AGENT_ENABLED:
            telemetry_info += "[AgentVer={0}][GoalStateVer={1}]".format(self.telemetry_writer.get_agent_version(), self.telemetry_writer.get_goal_state_agent_version())
        else:
            telemetry_info += "[AgentVer=Unknown][GoalStateVer=Unknown]"

        if telemetry_supported is True:
            self.logger.log("{0} {1}".format(Constants.TELEMETRY_AT_AGENT_COMPATIBLE_MSG, telemetry_info))
        else:
            error_msg = "{0} {1}".format(Constants.TELEMETRY_AT_AGENT_NOT_COMPATIBLE_ERROR_MSG, telemetry_info)
            self.logger.log_error(error_msg)

    def install(self):
        try:
            self.setup(action=Constants.INSTALL, log_message="Extension installation started")
            install_command_handler = InstallCommandHandler(self.logger, self.ext_env_handler)
            return install_command_handler.execute_handler_action()

        except Exception as error:
            self.logger.log_error("Error occurred during extension install. [Error={0}]".format(repr(error)))
            return Constants.ExitCode.HandlerFailed

        finally:
            self.tear_down()

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
            self.setup(action=Constants.UPDATE, log_message="Extension is being updated to the latest version. Copying the required extension artifacts from preceding version to the current one")

            # fetch all earlier extension versions available on the machine
            new_version_config_folder = self.ext_env_handler.config_folder
            extension_pardir = os.path.abspath(os.path.join(new_version_config_folder, os.path.pardir, os.path.pardir))
            self.logger.log("Parent directory for all extension version artifacts [Directory={0}]".format(str(extension_pardir)))
            paths_to_all_versions = self.filter_files_from_versions(self.get_all_versions(extension_pardir))
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
            self.tear_down()

    @staticmethod
    def get_all_versions(extension_pardir):
        return glob.glob(extension_pardir + '/*LinuxPatchExtension*')

    @staticmethod
    def filter_files_from_versions(paths_to_all_versions):
        return [p for p in paths_to_all_versions if path.isdir(p)]

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
            self.setup(action=Constants.UNINSTALL, log_message="Extension uninstalled")
            return Constants.ExitCode.Okay

        except Exception as error:
            self.logger.log_error("Error occurred during extension uninstall. [Error={0}]".format(repr(error)))
            return Constants.ExitCode.HandlerFailed

        finally:
            self.tear_down()

    def enable(self):
        try:
            self.setup(action=Constants.ENABLE, log_message="Enable triggered on extension")
            enable_command_handler = EnableCommandHandler(self.logger, self.telemetry_writer, self.utility, self.env_health_manager, self.runtime_context_handler, self.ext_env_handler, self.ext_config_settings_handler, self.core_state_handler, self.ext_state_handler, self.ext_output_status_handler, self.process_handler, self.cmd_exec_start_time)
            return enable_command_handler.execute_handler_action()

        except Exception as error:
            self.logger.log_error("Error occurred during extension enable. [Error={0}]".format(repr(error)))
            return Constants.ExitCode.HandlerFailed
        finally:
            self.tear_down()

    def disable(self):
        try:
            self.setup(action=Constants.DISABLE, log_message="Disable triggered on extension")
            prev_patch_max_end_time = self.cmd_exec_start_time + datetime.timedelta(hours=0, minutes=Constants.DISABLE_MAX_RUNTIME)
            self.runtime_context_handler.process_previous_patch_operation(self.core_state_handler, self.process_handler, prev_patch_max_end_time, core_state_content=None)

            # For the Linux Patch Extension lifecycle, disable comes in as a temporary part of the extension update flow. (Uninstall, with no further action, is not part of this extension's lifecycle)
            # In this flow, it's best to temporarily block Core invocation in auto-assessment while keeping the separation of concerns in place between Ext and Core.
            # The new extension version will take over the flow as needed, and lifecycle management has also blocked execution, so disablement here is best effort.
            try:
                exec_dir = os.path.dirname(os.path.realpath(__file__))
                auto_assess_sh_path = os.path.join(exec_dir, Constants.CORE_AUTO_ASSESS_SH_FILE_NAME)
                self.logger.log_debug("Discovered auto_assess_sh_path. [Path={0}]".format(auto_assess_sh_path))
                if os.path.exists(auto_assess_sh_path):
                    os.remove(auto_assess_sh_path)
                auto_assess_sh_data = "#!/usr/bin/env bash" + \
                                      "\r\n# Copyright 2021 Microsoft Corporation" + \
                                      "\r\n printf \"Auto-assessment was paused by the Azure Linux Patch Extension.\""
                self.env_layer.file_system.write_with_retry(auto_assess_sh_path, auto_assess_sh_data)
                self.env_layer.run_command_output("chmod a+x " + auto_assess_sh_path)
            except Exception as error:
                self.logger.log_error("Error occurred during auto-assessment disable. [Error={0}]".format(repr(error)))
            # End of temporary auto-assessment disablement

            self.logger.log("Extension disabled successfully")
            return Constants.ExitCode.Okay

        except Exception as error:
            self.logger.log_error("Error occurred during extension disable. [Error={0}]".format(repr(error)))
            return Constants.ExitCode.HandlerFailed
        finally:
            self.tear_down()

    def reset(self):
        try:
            self.setup(action=Constants.RESET, log_message="Reset triggered on extension, deleting CoreState and ExtState files")
            self.utility.delete_file(self.core_state_handler.dir_path, self.core_state_handler.file, raise_if_not_found=False)
            self.utility.delete_file(self.ext_state_handler.dir_path, self.ext_state_handler.file, raise_if_not_found=False)
            return Constants.ExitCode.Okay

        except Exception as error:
            self.logger.log_error("Error occurred during extension reset. [Error={0}]".format(repr(error)))
            return Constants.ExitCode.HandlerFailed
        finally:
            self.tear_down()

