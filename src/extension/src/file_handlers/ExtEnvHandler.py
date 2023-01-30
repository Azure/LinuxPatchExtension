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
import glob
import os

from extension.src.Constants import Constants

'''
Structure of the file this class deals with: HandlerEnvironment.json
[{
 "version": 1.0,
 "handlerEnvironment": {
 "logFolder": "<your log folder location>",
 "configFolder": "<your config folder location - config settings come from here>",
 "statusFolder": "<your status folder location>",
 "heartbeatFile": "<your heartbeat file location>",
 "deploymentid": "<deployment id for the vm>",
 "rolename": "<role name for the vm>",
 "instance": "<instance name for the vm>"
 }
}]
'''


class ExtEnvHandler(object):
    """ Responsible for all operations with HandlerEnvironment.json file and other environment config """
    def __init__(self, logger, env_layer, json_file_handler, handler_env_file=Constants.HANDLER_ENVIRONMENT_FILE, handler_env_file_path=Constants.HANDLER_ENVIRONMENT_FILE_PATH):
        self.logger = logger
        self.env_layer = env_layer
        json_file_handler = json_file_handler
        self.env_settings_all_keys = Constants.EnvSettingsFields

        self.handler_environment_json = json_file_handler.get_json_file_content(handler_env_file, handler_env_file_path, raise_if_not_found=True)
        if self.handler_environment_json is not None:
            self.log_folder = self.get_ext_env_config_value_safely(self.env_settings_all_keys.log_folder)
            self.config_folder = self.get_ext_env_config_value_safely(self.env_settings_all_keys.config_folder)
            self.status_folder = self.get_ext_env_config_value_safely(self.env_settings_all_keys.status_folder)
            self.events_folder = self.get_ext_env_config_value_safely(self.env_settings_all_keys.events_folder, raise_if_not_found=False)
            if self.events_folder is None:
                self.events_folder = self.get_ext_env_config_value_safely(self.env_settings_all_keys.events_folder_preview, raise_if_not_found=False)

            self.temp_folder = self.get_temp_folder()

        self.telemetry_supported = False

    def get_ext_env_config_value_safely(self, key, raise_if_not_found=True):
        """ Allows a update deployment configuration value to be queried safely with a fall-back default (optional).
        An exception will be raised if default_value is not explicitly set when called (considered by-design). """
        config_type = self.env_settings_all_keys.settings_parent_key
        if self.handler_environment_json is not None and len(self.handler_environment_json) != 0:
            if key in self.handler_environment_json[0][config_type]:
                value = self.handler_environment_json[0][config_type][key]
                return value
            else:   # If it is not present
                if raise_if_not_found:
                    raise Exception("Value not found for given config. [Config={0}]".format(key))
                else:
                    return None
        return None

    def get_temp_folder(self):
        """ Returns path to the temp folder, if one exists. If not, creates a temp folder and returns it's path """
        par_dir = os.path.dirname(self.config_folder)
        temp_folder_path = os.path.join(par_dir, Constants.TEMP_FOLDER_DIR_NAME)
        if not os.path.exists(par_dir):
            raise Exception("Parent directory for all extension artifacts such as config folder, status folder, etc. not found at [{0}].".format(repr(par_dir)))

        if not os.path.exists(temp_folder_path):
            os.mkdir(temp_folder_path)
        return temp_folder_path

    def delete_temp_folder_contents(self, raise_if_delete_failed=False):
        """ Clears all artifacts from temp_folder."""
        # clean up temp folder after all operation execution is finished from Core
        if self.env_layer is not None \
                and self.temp_folder is not None \
                and os.path.exists(self.temp_folder):
            self.logger.log_debug("Deleting all files of certain format from temp folder [FileFormat={0}][TempFolderLocation={1}]".format("*", str(self.temp_folder)))
            self.env_layer.file_system.delete_files_from_dir(self.temp_folder, ["*"], raise_if_delete_failed=raise_if_delete_failed)
        else:
            self.logger.log_debug("Temp folder not found")

    def delete_temp_folder(self, raise_if_delete_failed=False):
        """ Deletes temp_folder and all of it's contents """
        if self.env_layer is not None \
                and self.temp_folder is not None \
                and os.path.exists(self.temp_folder):
            self.logger.log_debug("Deleting all files of certain format from temp folder [FileFormat={0}][TempFolderLocation={1}]".format("*", str(self.temp_folder)))
            self.env_layer.file_system.remove_dir(self.temp_folder, raise_if_delete_failed=raise_if_delete_failed)
        else:
            self.logger.log_debug("Temp folder not found")

    def log_temp_folder_details(self):
        """ Computes size of temp folder from all files in it. NOTE: Does not include dirs within temp folder for this calculation """
        # todo: Do we need to compute size from all inner dirs also? Or should we restrict tmp folder to only have files?
        if self.temp_folder is not None and os.path.exists(self.temp_folder):
            size = 0
            file_count = 0
            for path, dirs, files in os.walk(self.temp_folder):
                for f in files:
                    fp = os.path.join(path, f)
                    size += os.stat(fp).st_size
                    file_count += 1
            self.logger.log_debug("Temp folder details: [Location={0}][TotalSizeOfAllFiles={1}][TotalNumberOfFiles-{2}]".format(str(self.temp_folder), str(size), str(file_count)))
        else:
            self.logger.log_debug("Temp folder not found")
