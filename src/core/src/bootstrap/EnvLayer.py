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
import datetime
import glob
import os
import re
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from core.src.bootstrap.Constants import Constants
from core.src.external_dependencies import distro


class EnvLayer(object):
    """ Environment related functions """

    def __init__(self):
        # Discrete components
        self.platform = self.Platform()
        self.datetime = self.DateTime()
        self.file_system = self.FileSystem()

        # Constant paths
        self.etc_environment_file_path = "/etc/environment"

    def get_package_manager(self):
        # type: () -> str
        """ Detects package manager type """
        if self.platform.linux_distribution()[0] == Constants.AZURE_LINUX:
            code, out = self.run_command_output('which tdnf', False, False)
            if code == 0:
                return Constants.TDNF
            else:
                print("Error: Expected package manager tdnf not found on this Azure Linux VM.")
                return str()

        # choose default package manager
        package_manager_map = (('apt-get', Constants.APT),
                               ('yum', Constants.YUM),
                               ('zypper', Constants.ZYPPER))
        for entry in package_manager_map:
            code, out = self.run_command_output('which ' + entry[0], False, False)
            if code == 0:
                return entry[1]

        return str() if platform.system() != 'Windows' else Constants.APT

    def set_env_var(self, var_name, var_value=str(), raise_if_not_success=False):
        # type: (str, str, bool) -> None
        """ Sets an environment variable with var_name and var_value in /etc/environment. If it already exists, it is overwritten. """
        try:
            environment_vars = self.file_system.read_with_retry(self.etc_environment_file_path)
            if environment_vars is None:
                print("Error occurred while setting environment variable: File not found. [Variable={0}][Value={1}][Path={2}]".format(str(var_name), str(var_value), self.etc_environment_file_path))
                return

            environment_vars_lines = environment_vars.strip().split("\n")

            if var_value is str():
                # remove environment variable
                regex = re.compile('{0}=.+'.format(var_name))
                search = regex.search(environment_vars)
                if search is None:
                    return

                group = search.group()
                environment_vars = environment_vars.replace(group, '').replace("\n\n", "\n")
                self.file_system.write_with_retry(self.etc_environment_file_path, environment_vars, "w")
                return

            formatted_env_var = "{0}={1}".format(var_name, str(var_value))
            if var_name not in environment_vars:
                self.file_system.write_with_retry(self.etc_environment_file_path, "\n" + formatted_env_var)
            else:
                # Update the value of the existing setting
                for env_var in environment_vars_lines:
                    if var_name not in str(env_var):
                        continue

                    environment_vars = environment_vars.replace(str(env_var), formatted_env_var)
                    break

                self.file_system.write_with_retry(self.etc_environment_file_path, environment_vars, 'w')

        except Exception as error:
            print("Error occurred while setting environment variable [Variable={0}][Value={1}][Exception={2}]".format(str(var_name), str(var_value), repr(error)))
            if raise_if_not_success:
                raise

    def get_env_var(self, var_name, raise_if_not_success=False):
        # type: (str, bool) -> any
        """ Returns the value of an environment variable with var_name in /etc/environment. Returns None if it does not exist. """
        try:
            environment_vars = self.file_system.read_with_retry(self.etc_environment_file_path)
            if environment_vars is None:
                print("Error occurred while getting environment variable: File not found. [Variable={0}][Path={1}]".format(str(var_name), self.etc_environment_file_path))
                return None

            # get specific environment variable value
            regex = re.compile('{0}=.+'.format(var_name))
            search = regex.search(environment_vars)
            if search is None:
                return None

            group = search.group()
            return group[group.index("=")+1:]

        except Exception as error:
            print("Error occurred while getting environment variable [Variable={0}][Exception={1}]".format(str(var_name), repr(error)))
            if raise_if_not_success:
                raise

    def run_command_output(self, cmd, no_output, chk_err=True):
        # type: (str, bool, bool) -> (int, any)
        """ Wrapper for subprocess.check_output. Execute 'cmd'. Returns return code and STDOUT, trapping expected exceptions. Reports exceptions to Error if chk_err parameter is True """

        def check_output(*popenargs, **kwargs):
            """ Backport from subprocess module from python 2.7 """
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
            output = subprocess.check_output(no_output, cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            if chk_err:
                print("Error: CalledProcessError. [Code={0}][Command={1}][Result={2}]".format(str(e.returncode), e.cmd, self.__convert_process_output_to_ascii(e.output[:-1])), file=sys.stdout)
            if no_output:
                return e.return_code, None
            else:
                return e.return_code, self.__convert_process_output_to_ascii(e.output)
        except Exception as error:
            raise "Exception during cmd execution. [Exception={0}][Cmd={1}]".format(repr(error), str(cmd))

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
    def reboot_machine(reboot_cmd):
        subprocess.Popen(reboot_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    @staticmethod
    def exit(code):
        exit(code)

    @staticmethod
    def get_python_major_version():
        # type: () -> int
        if hasattr(sys.version_info, 'major'):
            return sys.version_info.major
        else:
            return sys.version_info[0]  # python 2.6 doesn't have attributes like 'major' within sys.version_info

# region - Platform extensions
    class Platform(object):
        @staticmethod
        def linux_distribution():
            return platform.linux_distribution() if (EnvLayer.get_python_major_version() == 2) else distro.linux_distribution()

        @staticmethod
        def os_type():   # OS Type
            return platform.system()

        @staticmethod
        def cpu_arch():  # architecture
            return platform.machine()

        @staticmethod
        def vm_name():     # machine name
            return platform.node()
# endregion - Platform extensions

# region - File system extensions
    class FileSystem(object):
        def __init__(self):
            # file-names of files that other processes may change the contents of
            self.__non_exclusive_files = [Constants.EXT_STATE_FILE]

        @staticmethod
        def open(file_path, mode, raise_if_not_found=True):
            """ Provides a file handle to the file_path requested using implicit redirection where required """
            for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
                try:
                    return open(file_path, mode)
                except Exception as error:
                    if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                        time.sleep(i + 1)
                    else:
                        error_message = "Unable to open file (retries exhausted). [File={0}][Error={1}][RaiseIfNotFound={2}].".format(str(file_path), repr(error), str(raise_if_not_found))
                        if raise_if_not_found:
                            raise Exception(error_message)
                        else:
                            print(error_message)
                            return None

        def __obtain_file_handle(self, file_path_or_handle, mode='a+', raise_if_not_found=True):
            """ Pass-through for handle. For path, resolution and handle open with retry. """
            is_path = False
            if isinstance(file_path_or_handle, str) or not(hasattr(file_path_or_handle, 'read') and hasattr(file_path_or_handle, 'write')):
                is_path = True
                file_path_or_handle = self.open(file_path_or_handle, mode, raise_if_not_found)
            file_handle = file_path_or_handle
            return file_handle, is_path

        def read_with_retry(self, file_path_or_handle, raise_if_not_found=True):
            """ Reads all content from a given file path in a single operation """
            file_handle, was_path = self.__obtain_file_handle(file_path_or_handle, 'r', raise_if_not_found)
            for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
                try:
                    value = file_handle.read()
                    if was_path:  # what was passed in was not a file handle, so close the handle that was init here
                        file_handle.close()
                    return value
                except Exception as error:
                    if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                        time.sleep(i + 1)
                    else:
                        error_message = "Unable to read file (retries exhausted). [File={0}][Error={1}][RaiseIfNotFound={2}].".format(str(file_path_or_handle), repr(error), str(raise_if_not_found))
                        if raise_if_not_found:
                            raise Exception(error_message)
                        else:
                            print(error_message)
                            return None

        def write_with_retry(self, file_path_or_handle, data, mode='a+'):
            """ Writes to a file path in a single operation """
            file_handle, was_path = self.__obtain_file_handle(file_path_or_handle, mode)

            for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
                try:
                    file_handle.write(str(data))
                    break
                except Exception as error:
                    if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                        time.sleep(i + 1)
                    else:
                        raise Exception("Unable to write to {0} (retries exhausted). Error: {1}.".format(str(file_handle.name), repr(error)))

            if was_path:  # what was passed in was not a file handle, so close the handle that was init here
                file_handle.close()

        @staticmethod
        def write_with_retry_using_temp_file(file_path, data, mode='w'):
            """ Writes to a temp file in a single operation and then moves/overrides the original file with the temp """
            for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
                try:
                    with tempfile.NamedTemporaryFile(mode, dir=os.path.dirname(file_path), delete=False) as tf:
                        tf.write(str(data))
                        tempname = tf.name
                    shutil.move(tempname, file_path)
                    break
                except Exception as error:
                    if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                        time.sleep(i + 1)
                    else:
                        raise Exception("Unable to write to {0} (retries exhausted). Error: {1}.".format(str(file_path), repr(error)))

        @staticmethod
        def delete_from_dir(dir_name, identifier_list, raise_if_delete_failed=False):
            """ Clears all files/dirs from given dir. NOTE: Uses identifier_list to determine the content to delete """
            for identifier in identifier_list:
                items_to_delete = glob.glob(os.path.join(str(dir_name), str(identifier)))

                for item_to_delete in items_to_delete:
                    try:
                        if os.path.isdir(item_to_delete):
                            shutil.rmtree(item_to_delete)
                        else:
                            os.remove(item_to_delete)
                    except Exception as error:
                        error_message = "Unable to delete item from directory [Dir={0}][Item={1}][Error={2}][RaiseIfDeleteFailed={3}].".format(
                            str(dir_name), str(item_to_delete), repr(error), str(raise_if_delete_failed))

                        if raise_if_delete_failed:
                            raise Exception(error_message)
                        else:
                            print(error_message)
                            continue
# endregion - File system extensions

# region - DateTime extensions
    class DateTime(object):
        @staticmethod
        def time():
            return time.time()

        @staticmethod
        def datetime_utcnow():
            return datetime.datetime.utcnow()

        @staticmethod
        def timestamp():
            return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        @staticmethod
        def total_minutes_from_time_delta(time_delta):
            return ((time_delta.microseconds + (time_delta.seconds + time_delta.days * 24 * 3600) * 10 ** 6) / 10.0 ** 6) / 60

        @staticmethod
        def total_seconds_from_time_delta(time_delta):
            return (time_delta.microseconds + (time_delta.seconds + time_delta.days * 24 * 3600) * 10 ** 6) / 10.0 ** 6

        @staticmethod
        def total_seconds_from_time_delta_round_to_one_decimal_digit(time_delta):
            """ 
            Converts the input time in datetime.timedelta format to seconds in float format
            
            Parameters:
            time_delta (datetime.timedelta): time in datetime.timedelta format e.g. 0:00:00.219000
            
            Returns:
            time in seconds round of to one decimal digit (float): e.g. 0.2 seconds
            """
            return round(EnvLayer.DateTime.total_seconds_from_time_delta(time_delta), 1)

        @staticmethod
        def utc_to_standard_datetime(utc_datetime):
            """ Converts string of format '"%Y-%m-%dT%H:%M:%SZ"' to datetime object """
            return datetime.datetime.strptime(utc_datetime.split(".")[0], "%Y-%m-%dT%H:%M:%S")

        @staticmethod
        def standard_datetime_to_utc(std_datetime):
            """ Converts datetime object to string of format '"%Y-%m-%dT%H:%M:%SZ"' """
            return std_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
# endregion - DateTime emulator and extensions
