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

from __future__ import print_function
import getpass
import glob
import os
import re
import shutil
import subprocess
import sys
import time
from extension.src.Constants import Constants


class EnvLayer(object):
    """ Environment related functions """

    def __init__(self):
        # Discrete components
        self.file_system = self.FileSystem()

        # components for tty config
        self.etc_sudoers_file_path = "/etc/sudoers"
        self.etc_sudoers_linux_patch_extension_file_path = "/etc/sudoers.d/linuxpatchextension"
        self.require_tty_setting = "requiretty"

    def run_command_output(self, cmd, no_output=False, chk_err=False):
        code, output = self.__run_command_output_raw(cmd, no_output, chk_err)
        return code, output

    def __run_command_output_raw(self, cmd, no_output, chk_err=True):
        """
        Wrapper for subprocess.check_output. Execute 'cmd'.
        Returns return code and STDOUT, trapping expected exceptions.
        Reports exceptions to Error if chk_err parameter is True
        """

        def check_output(*popenargs, **kwargs):
            """
            Backport from subprocess module from python 2.7
            """
            if 'stdout' in kwargs:
                raise ValueError('stdout argument not allowed, it will be overridden.')

            no_output = False
            if type(popenargs[0]) is bool:
                no_output = popenargs[0]
                popenargs = popenargs[1:]

            if no_output is True:
                out_file = None
            else:
                out_file = subprocess.PIPE

            process = subprocess.Popen(stdout=out_file, *popenargs, **kwargs)
            output, unused_err = process.communicate()
            retcode = process.poll()

            if retcode:
                cmd = kwargs.get("args")
                if cmd is None:
                    cmd = popenargs[0]
                raise subprocess.CalledProcessError(retcode, cmd, output=output)
            return output

        # noinspection PyShadowingNames,PyShadowingNames
        class CalledProcessError(Exception):
            """Exception classes used by this module."""

            def __init__(self, return_code, cmd, output=None):
                self.return_code = return_code
                self.cmd = cmd
                self.output = output

            def __str__(self):
                return "Command '%s' returned non-zero exit status %d" \
                       % (self.cmd, self.return_code)

        subprocess.check_output = check_output
        subprocess.CalledProcessError = CalledProcessError
        try:
            output = subprocess.check_output(
                no_output, cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            if chk_err:
                print("Error: CalledProcessError.  Error Code is: " + str(e.returncode), file=sys.stdout)
                print("Error: CalledProcessError.  Command string was: " + e.cmd, file=sys.stdout)
                print("Error: CalledProcessError.  Command result was: " + self.__convert_process_output_to_ascii(e.output[:-1]), file=sys.stdout)
            if no_output:
                return e.return_code, None
            else:
                return e.return_code, self.__convert_process_output_to_ascii(e.output)
        except Exception as error:
            message = "Exception during cmd execution. [Exception={0}][Cmd={1}]".format(repr(error), str(cmd))
            print(message)
            raise message

        if no_output:
            return 0, None
        else:
            return 0, self.__convert_process_output_to_ascii(output)

    @staticmethod
    def __convert_process_output_to_ascii(output):
        major_version = EnvLayer.get_python_major_version()
        if major_version == 2:
            return output.decode('utf8', 'ignore').encode('ascii', 'ignore')
        elif major_version == 3:
            return output.decode('utf8', 'ignore')
        else:
            raise Exception("Unknown version of python encountered.")

    @staticmethod
    def get_python_major_version():
        if hasattr(sys.version_info, 'major'):
            return sys.version_info.major
        else:
            return sys.version_info[0]  # python 2.6 doesn't have attributes like 'major' within sys.version_info

    def is_tty_required(self):
        """ Checks if tty is set to required within the VM and will be applicable to the current user (either via a generic config or a user specific one) """
        if self.is_tty_required_in_sudoers():
            if self.is_tty_disabled_in_linux_patch_extension_sudoers():
                return False
            return True
        return False

    def is_tty_required_in_sudoers(self):
        """ Reads the default tty setting from /etc/sudoers """
        try:
            tty_set_to_required = False
            sudoers_default_configuration = self.file_system.read_with_retry(self.etc_sudoers_file_path)
            settings = sudoers_default_configuration.strip().split('\n')

            for setting in settings:
                if self.require_tty_setting not in str(setting):
                    continue

                if re.match(r'.*!' + self.require_tty_setting, setting):
                    setting_substr_without_requiretty = re.search(r'(.*)!' + self.require_tty_setting, setting).group(1).strip()
                    if self.is_tty_defaults_set(setting_substr_without_requiretty):
                        tty_set_to_required = False
                else:
                    setting_substr_without_requiretty = re.search(r'(.*)' + self.require_tty_setting, setting).group(1).strip()
                    if self.is_tty_defaults_set(setting_substr_without_requiretty):
                        tty_set_to_required = True

            return tty_set_to_required

        except Exception as error:
            print("Error occurred while fetching data from [FilePath={0}] [Exception={1}]".format(str(self.etc_sudoers_file_path), repr(error)))
            raise

    def is_tty_defaults_set(self, setting_substr_without_requiretty):
        """ Verifies if Defaults is set for current or all users in the given string """
        return setting_substr_without_requiretty[0] != "#" and ("Defaults:" + str(self.get_current_user()) == setting_substr_without_requiretty or 'Defaults' == setting_substr_without_requiretty)

    def is_tty_disabled_in_linux_patch_extension_sudoers(self):
        """ Checks whether !requiretty is set for current user in the custom sudoers file for the extension """
        try:
            if not os.path.isfile(self.etc_sudoers_linux_patch_extension_file_path):
                return False

            sudoers_default_configuration = self.file_system.read_with_retry(self.etc_sudoers_linux_patch_extension_file_path)
            settings = sudoers_default_configuration.strip().split('\n')
            for setting in settings:
                if self.require_tty_setting not in str(setting):
                    continue

                defaults_set_for = re.search('(.*)!' + self.require_tty_setting, setting).group(1).strip()
                if "Defaults:" + str(self.get_current_user()) == defaults_set_for:
                    return True
            return False
        except Exception as error:
            print("Error occurred while fetching data from [FilePath={0}] [Exception={1}]".format(str(self.etc_sudoers_file_path), repr(error)))
            raise

    @staticmethod
    def get_current_user():
        return getpass.getuser()

# region - File system
    class FileSystem(object):
        def __init__(self):
            self.retry_count = Constants.MAX_IO_RETRIES

        def open(self, file_path, mode):
            """ Provides a file handle to the file_path requested using implicit redirection where required """
            for i in range(0, self.retry_count):
                try:
                    return open(file_path, mode)
                except Exception as error:
                    if i < self.retry_count - 1:
                        time.sleep(i + 1)
                    else:
                        raise Exception("Unable to open {0} (retries exhausted). Error: {1}.".format(str(file_path), repr(error)))

        def __obtain_file_handle(self, file_path_or_handle, mode='a+'):
            """ Pass-through for handle. For path, resolution and handle open with retry. """
            is_path = False
            if isinstance(file_path_or_handle, str) or not(hasattr(file_path_or_handle, 'read') and hasattr(file_path_or_handle, 'write')):
                is_path = True
                file_path_or_handle = self.open(file_path_or_handle, mode)
            file_handle = file_path_or_handle
            return file_handle, is_path

        def read_with_retry(self, file_path_or_handle):
            """ Reads all content from a given file path in a single operation """

            if isinstance(file_path_or_handle, str):
                file_handle, was_path = self.__obtain_file_handle(file_path_or_handle, 'r')
                value = file_handle.read()
                if was_path:  # what was passed in was not a file handle, so close the handle that was init here
                    file_handle.close()
                return value
            return None

        def write_with_retry(self, file_path_or_handle, data, mode='a+'):
            """ Writes to a given real/emulated file path in a single operation """
            file_handle, was_path = self.__obtain_file_handle(file_path_or_handle, mode)

            for i in range(0, self.retry_count):
                try:
                    file_handle.write(str(data))
                    break
                except Exception as error:
                    if i < self.retry_count - 1:
                        time.sleep(i + 1)
                    else:
                        raise Exception("Unable to write to {0} (retries exhausted). Error: {1}.".format(str(file_handle.name), repr(error)))

            if was_path:  # what was passed in was not a file handle, so close the handle that was init here
                file_handle.close()

        @staticmethod
        def delete_files_from_dir(dir_name, file_identifier_list, raise_if_delete_failed=False):
            """ Clears all files from given dir. NOTE: Uses file_identifier_list to determine the content to delete """
            for file_identifier in file_identifier_list:
                files_to_delete = glob.glob(str(dir_name) + "/" + str(file_identifier))

                for file_to_delete in files_to_delete:
                    try:
                        os.remove(file_to_delete)
                    except Exception as error:
                        error_message = "Unable to delete files from directory [Dir={0}][File={1}][Error={2}][RaiseIfDeleteFailed={3}].".format(
                            str(dir_name), str(file_to_delete), repr(error), str(raise_if_delete_failed))
                        if raise_if_delete_failed:
                            raise Exception(error_message)
                        else:
                            print(error_message)
                            return None

        @staticmethod
        def remove_dir(dir_name, raise_if_delete_failed=False):
            """ Deletes given directory and all of it's contents """
            try:
                shutil.rmtree(dir_name)
            except Exception as error:
                error_message = "Unable to delete directory [Dir={0}][Error={1}][RaiseIfDeleteFailed={2}].".format(
                    str(dir_name),
                    repr(error),
                    str(raise_if_delete_failed))

                if raise_if_delete_failed:
                    raise Exception(error_message)
                else:
                    print(error_message)
                    return None

# endregion - File system
