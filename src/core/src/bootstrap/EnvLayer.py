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
import base64
import datetime
import glob
import json
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

    def __init__(self, real_record_path=None, recorder_enabled=False, emulator_enabled=False):
        # Recorder / emulator storage
        self.__real_record_path = real_record_path
        self.__real_record_pointer_path = real_record_path + ".pt" if real_record_path is not None else None
        self.__real_record_handle = None
        self.__real_record_pointer = 0

        # Recorder / emulator state section
        self.__recorder_enabled = recorder_enabled                                  # dumps black box recordings
        self.__emulator_enabled = False if recorder_enabled else emulator_enabled   # only one can be enabled at a time

        # Recorder / emulator initialization
        if self.__recorder_enabled:
            self.__record_writer_init()
        elif self.__emulator_enabled:
            self.__record_reader_init()

        # Discrete components
        self.platform = self.Platform(recorder_enabled, emulator_enabled, self.__write_record, self.__read_record)
        self.datetime = self.DateTime(recorder_enabled, emulator_enabled, self.__write_record, self.__read_record)
        self.file_system = self.FileSystem(recorder_enabled, emulator_enabled, self.__write_record, self.__read_record,
                                           emulator_root_path=os.path.dirname(self.__real_record_path) if self.__real_record_path is not None else self.__real_record_path)

        # Constant paths
        self.etc_environment_file_path = "/etc/environment"

    def get_package_manager(self):
        """ Detects package manager type """
        ret = None

        distro_name = self.platform.linux_distribution()[0]
        if distro_name == Constants.AZURE_LINUX or distro_name == Constants.COMMON_BASE_LINUX_MARINER:
            code, out = self.run_command_output('which tdnf', False, False)
            if code == 0:
                ret = Constants.TDNF
            else:
                print("Error: Expected package manager tdnf not found on this Azure Linux VM")
        else:
            # choose default - almost surely one will match.
            for b in ('apt-get', 'yum', 'zypper'):
                code, out = self.run_command_output('which ' + b, False, False)
                if code == 0:
                    ret = b
                    if ret == 'apt-get':
                        ret = Constants.APT
                        break
                    if ret == 'yum':
                        ret = Constants.YUM
                        break
                    if ret == 'zypper':
                        ret = Constants.ZYPPER
                        break

        if ret is None and platform.system() == 'Windows':
            ret = Constants.APT

        return ret

    def set_env_var(self, var_name, var_value=None, raise_if_not_success=False):
        """ Sets an environment variable with var_name and var_value in /etc/environment. If it already exists, it is overwriten. """
        try:
            environment_vars = self.file_system.read_with_retry(self.etc_environment_file_path)
            if environment_vars is None:
                print("Error occurred while setting environment variable: File not found. [Variable={0}] [Value={1}] [Path={2}]".format(str(var_name), str(var_value), self.etc_environment_file_path))
                return

            environment_vars_lines = environment_vars.strip().split("\n")

            if var_value is None:
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
            print("Error occurred while setting environment variable [Variable={0}] [Value={1}] [Exception={2}]".format(str(var_name), str(var_value), repr(error)))
            if raise_if_not_success:
                raise

    def get_env_var(self, var_name, raise_if_not_success=False):
        """ Returns the value of an environment variable with var_name in /etc/environment. Returns None if it does not exist. """
        try:
            environment_vars = self.file_system.read_with_retry(self.etc_environment_file_path)
            if environment_vars is None:
                print("Error occurred while getting environment variable: File not found. [Variable={0}] [Path={1}]".format(str(var_name), self.etc_environment_file_path))
                return None

            # get specific environment variable value
            regex = re.compile('{0}=.+'.format(var_name))
            search = regex.search(environment_vars)
            if search is None:
                return None

            group = search.group()
            return group[group.index("=")+1:]

        except Exception as error:
            print("Error occurred while getting environment variable [Variable={0}] [Exception={1}]".format(str(var_name), repr(error)))
            if raise_if_not_success:
                raise

    def run_command_output(self, cmd, no_output=False, chk_err=False):
        operation = "RUN_CMD_OUT"
        if not self.__emulator_enabled:
            start = time.time()
            code, output = self.__run_command_output_raw(cmd, no_output, chk_err)
            self.__write_record(operation, code, output, delay=(time.time()-start))
            return code, output
        else:
            return self.__read_record(operation)

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
            output = subprocess.check_output(no_output, cmd, stderr=subprocess.STDOUT, shell=True)
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
            message = "Exception during cmd execution. [Exception={0}][Cmd={1}]".format(repr(error),str(cmd))
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

    def reboot_machine(self, reboot_cmd):
        operation = "REBOOT_MACHINE"
        if not self.__emulator_enabled:
            self.__write_record(operation, 0, '', delay=0)
            subprocess.Popen(reboot_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            self.__read_record(operation)   # will throw if it's not the expected operation
            raise Exception(Constants.EnvLayer.PRIVILEGED_OP_REBOOT)

    def exit(self, code):
        operation = "EXIT_EXECUTION"
        if not self.__emulator_enabled:
            self.__write_record(operation, code, '', delay=0)
            exit(code)
        else:
            self.__read_record(operation)   # will throw if it's not the expected operation
            raise Exception(Constants.EnvLayer.PRIVILEGED_OP_EXIT + str(code))

    @staticmethod
    def get_python_major_version():
        if hasattr(sys.version_info, 'major'):
            return sys.version_info.major
        else:
            return sys.version_info[0]  # python 2.6 doesn't have attributes like 'major' within sys.version_info

# region - Platform emulation and extensions
    class Platform(object):
        def __init__(self, recorder_enabled=True, emulator_enabled=False, write_record_delegate=None, read_record_delegate=None):
            self.__recorder_enabled = recorder_enabled
            self.__emulator_enabled = False if recorder_enabled else emulator_enabled
            self.__write_record = write_record_delegate
            self.__read_record = read_record_delegate

        def linux_distribution(self):
            operation = "PLATFORM_LINUX_DISTRIBUTION"
            if not self.__emulator_enabled:
                major_version = EnvLayer.get_python_major_version()

                if major_version == 2:
                    value = platform.linux_distribution()
                else:
                    value = distro.linux_distribution()

                if self.__recorder_enabled:
                    self.__write_record(operation, code=0, output=str(value))
                return value
            else:
                code, output = self.__read_record(operation)
                return eval(output)

        def system(self):   # OS Type
            operation = "PLATFORM_SYSTEM"
            if not self.__emulator_enabled:
                value = platform.system()
                if self.__recorder_enabled:
                    self.__write_record(operation, code=0, output=str(value))
                return value
            else:
                code, output = self.__read_record(operation)
                return output

        def machine(self):  # architecture
            operation = "PLATFORM_MACHINE"
            if not self.__emulator_enabled:
                value = platform.machine()
                if self.__recorder_enabled:
                    self.__write_record(operation, code=0, output=str(value))
                return value
            else:
                code, output = self.__read_record(operation)
                return output

        def node(self):     # machine name
            operation = "PLATFORM_NODE"
            if not self.__emulator_enabled:
                value = platform.node()
                if self.__recorder_enabled:
                    self.__write_record(operation, code=0, output=str(value))
                return value
            else:
                code, output = self.__read_record(operation)
                return output
# endregion - Platform emulation and extensions

# region - File system emulation and extensions
    class FileSystem(object):
        def __init__(self, recorder_enabled=True, emulator_enabled=False, write_record_delegate=None, read_record_delegate=None, emulator_root_path=None):
            self.__recorder_enabled = recorder_enabled
            self.__emulator_enabled = False if recorder_enabled else emulator_enabled
            self.__write_record = write_record_delegate
            self.__read_record = read_record_delegate
            self.__emulator_enabled = emulator_enabled
            self.__emulator_root_path = emulator_root_path

            # file-names of files that other processes may changes the contents of
            self.__non_exclusive_files = [Constants.EXT_STATE_FILE]

        def resolve_path(self, requested_path):
            """ Resolves any paths used with desired file system paths """
            if self.__emulator_enabled and self.__emulator_root_path is not None and self.__emulator_root_path not in requested_path:
                return os.path.join(self.__emulator_root_path, os.path.normpath(requested_path))
            else:
                return requested_path

        def open(self, file_path, mode, raise_if_not_found=True):
            """ Provides a file handle to the file_path requested using implicit redirection where required """
            real_path = self.resolve_path(file_path)
            for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
                try:
                    return open(real_path, mode)
                except Exception as error:
                    if i < Constants.MAX_FILE_OPERATION_RETRY_COUNT - 1:
                        time.sleep(i + 1)
                    else:
                        error_message = "Unable to open file (retries exhausted). [File={0}][Error={1}][RaiseIfNotFound={2}].".format(str(real_path), repr(error), str(raise_if_not_found))
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
            operation = "FILE_READ"

            # only fully emulate non_exclusive_files from the real recording; exclusive files can be redirected and handled in emulator scenarios
            if not self.__emulator_enabled or (isinstance(file_path_or_handle, str) and os.path.basename(file_path_or_handle) not in self.__non_exclusive_files):
                file_handle, was_path = self.__obtain_file_handle(file_path_or_handle, 'r', raise_if_not_found)
                for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
                    try:
                        value = file_handle.read()
                        if was_path:  # what was passed in was not a file handle, so close the handle that was init here
                            file_handle.close()
                        self.__write_record(operation, code=0, output=value, delay=0)
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
            else:
                code, output = self.__read_record(operation)
                return output

        def write_with_retry(self, file_path_or_handle, data, mode='a+'):
            """ Writes to a given real/emulated file path in a single operation """
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
# endregion - File system emulation and extensions

# region - DateTime emulation and extensions
    class DateTime(object):
        def __init__(self, recorder_enabled=True, emulator_enabled=False, write_record_delegate=None, read_record_delegate=None):
            self.__recorder_enabled = recorder_enabled
            self.__emulator_enabled = False if recorder_enabled else emulator_enabled
            self.__write_record = write_record_delegate
            self.__read_record = read_record_delegate

        def time(self):
            operation = "DATETIME_TIME"
            if not self.__emulator_enabled:
                value = time.time()
                self.__write_record(operation, code=0, output=value, delay=0)
                return value
            else:
                code, output = self.__read_record(operation)
                return int(output)

        def datetime_utcnow(self):
            operation = "DATETIME_UTCNOW"
            if not self.__emulator_enabled:
                value = datetime.datetime.utcnow()
                self.__write_record(operation, code=0, output=str(value), delay=0)
                return value
            else:
                code, output = self.__read_record(operation)
                return datetime.datetime.strptime(str(output), "%Y-%m-%d %H:%M:%S.%f")

        def timestamp(self):
            operation = "DATETIME_TIMESTAMP"
            if not self.__emulator_enabled:
                value = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                self.__write_record(operation, code=0, output=value, delay=0)
                return value
            else:
                code, output = self.__read_record(operation)
                return output

        # --------------------------------------------------------------------------------------------------------------
        # Static library functions
        # --------------------------------------------------------------------------------------------------------------
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

# region - Core Emulator support functions
    def __write_record(self, operation, code, output, delay, timestamp=None):
        """ Writes a single operation record to disk if the recorder is enabled """
        if not self.__recorder_enabled or self.__real_record_handle is None:
            return

        try:
            record = {
                "timestamp": str(timestamp) if timestamp is not None else datetime.datetime.strptime(str(datetime.datetime.utcnow()).split(".")[0], Constants.UTC_DATETIME_FORMAT), #WRONG
                "operation": str(operation),
                "code": int(code),
                "output": base64.b64encode(str(output)),
                "delay": float(delay)
            }
            self.__real_record_handle.write('\n{0}'.format(json.dumps(record)))
        except Exception:
            print("EnvLayer: Unable to write real record to disk.")

    def __record_writer_init(self):
        """ Initializes the record writer handle """
        self.__real_record_handle = open(self.__real_record_path, 'a+')

    def __read_record(self, expected_operation):
        """ Returns code, output for a given operation if it matches """
        if self.__real_record_handle is None:
            raise Exception("Invalid real record handle.")

        # Get single record
        real_record_raw = self.__real_record_handle.readline().rstrip()
        real_record = json.loads(real_record_raw)

        # Load data from record
        timestamp = real_record['timestamp']
        operation = real_record['operation']
        code = int(real_record['code'])
        output = base64.b64decode(real_record['output'])
        delay = float(real_record['delay'])
        print("Real record read: {0}: {1} >> code({2}) - output.len({3} - {4})".format(timestamp, operation, str(code), str(len(output)), str(self.__real_record_pointer+1)))

        # Verify operation
        if real_record['operation'] != expected_operation:
            raise Exception("Execution deviation detected. Add adaptations for operation expected: {0}. Operation data found for: {1}.".format(expected_operation, real_record['operation']))

        # Advance and persist pointer
        self.__real_record_pointer += 1
        with open(self.__real_record_pointer_path, 'w') as file_handle:
            file_handle.write(str(self.__real_record_pointer))

        # Return data
        time.sleep(delay)
        return code, output

    def __record_reader_init(self):
        """ Seeks the real record pointer to the expected location """
        # Initialize record pointer
        if not os.path.exists(self.__real_record_pointer_path):
            self.__real_record_pointer = 0
        else:
            with open(self.__real_record_pointer_path, 'r') as file_handle:
                self.__real_record_pointer = int(file_handle.read().rstrip())  # no safety checks as there's no good recovery

        # Have the handle seek to the desired position
        self.__real_record_handle = open(self.__real_record_pointer_path, 'r')
        for x in range(1, self.__real_record_pointer):
            self.__real_record_handle.readline()
# endregion - Core Emulator support functions

# region - Legacy mode extensions
    def set_legacy_test_mode(self):
        print("Switching env layer to legacy test mode...")
        self.datetime = self.DateTime(False, False, self.__write_record, self.__read_record)
        self.file_system = self.FileSystem(False, False, self.__write_record, self.__read_record, emulator_root_path=os.path.dirname(self.__real_record_path))
# endregion - Legacy mode extensions
