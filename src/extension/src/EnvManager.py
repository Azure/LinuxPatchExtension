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


class EnvManager(object):

    def __init__(self, env_layer):
        self.env_layer = env_layer

    def check_sudo_status(self, raise_if_not_sudo=True):
        """ Checks if we can invoke sudo successfully. """
        try:
            print("Performing sudo status check... This should complete within 10 seconds.")
            return_code, output = self.env_layer.run_command_output("timeout 10 sudo id && echo True || echo False", False, False)
            # output should look like either this (bad):
            #   [sudo] password for username:
            #   False
            # or this (good):
            #   uid=0(root) gid=0(root) groups=0(root)
            #   True

            output_lines = output.splitlines()
            if len(output_lines) < 2:
                raise Exception("Unexpected sudo check result. Output: " + " ".join(output.split("\n")))

            if output_lines[1] == "True":
                return True
            elif output_lines[1] == "False":
                if raise_if_not_sudo:
                    raise Exception("Unable to invoke sudo successfully. Output: " + " ".join(output.split("\n")))
                return False
            else:
                raise Exception("Unexpected sudo check result. Output: " + " ".join(output.split("\n")))
        except Exception as exception:
            print("Sudo status check failed. Please ensure the computer is configured correctly for sudo invocation. " +
                  "Exception details: " + str(exception))
            if raise_if_not_sudo:
                raise

    def ensure_tty_not_required(self):
        """ Checks current tty settings in /etc/sudoers and disables it within the current user context, if required. Sudo commands don't execute if tty is required. """
        try:
            tty_required = self.env_layer.is_tty_required()
            if tty_required:
                self.disable_tty_for_current_user()
        except Exception as error:
            # todo: raise error?
            print("Error occurred while ensuring tty is disabled. [Error={0}]".format(repr(error)))

    def disable_tty_for_current_user(self):
        """ Sets requiretty to False in the custom sudoers file for linuxpatchextension"""
        try:
            disable_tty_for_current_user_config = "Defaults:" + self.env_layer.get_current_user() + " !" + self.env_layer.require_tty_setting + "\n"
            print("Disabling tty for current user in custom sudoers for the extension [FileName={0}] [ConfigAdded={1}]".format(str(self.env_layer.etc_sudoers_linux_patch_extension_file_path), disable_tty_for_current_user_config))
            self.env_layer.file_system.write_with_retry(self.env_layer.etc_sudoers_linux_patch_extension_file_path, disable_tty_for_current_user_config, mode='w+')
            print("tty for current user disabled")
        except Exception as error:
            print("Error occurred while disabling tty for current user. [FileName={0}] [Error={1}]".format(str(self.env_layer.etc_sudoers_linux_patch_extension_file_path), repr(error)))
            raise

