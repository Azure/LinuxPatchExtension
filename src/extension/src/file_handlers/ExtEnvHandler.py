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
    """ Responsible for all operations with HandlerEnvironment.json file """
    def __init__(self, json_file_handler, handler_env_file=Constants.HANDLER_ENVIRONMENT_FILE, handler_env_file_path=Constants.HANDLER_ENVIRONMENT_FILE_PATH):
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
