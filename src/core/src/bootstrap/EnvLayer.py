from __future__ import print_function
import base64
import datetime
import json
import os
import platform
import subprocess
import sys
import time
from Constants import Constants


class EnvLayer(object):
    """ Environment related functions """

    def __init__(self, real_record_path=None, recorder_enabled=False, emulator_enabled=False):
        # Recorder / emulator storage
        self.__real_record_path = real_record_path
        self.__real_record_pointer_path = real_record_path + ".pt"
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
                                           emulator_root_path=os.path.dirname(self.__real_record_path))

    def get_package_manager(self):
        """ Detects package manager type """
        ret = None

        # choose default - almost surely one will match.
        for b in ('apt-get', 'yum', 'zypper'):
            code, out = self.run_command_output('which ' + b, False, False)
            if code is 0:
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

        def check_output(no_output, *popenargs, **kwargs):
            """
            Backport from subprocess module from python 2.7
            """
            if 'stdout' in kwargs:
                raise ValueError('stdout argument not allowed, it will be overridden.')
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
                print("Error: CalledProcessError.  Command result was: " + (e.output[:-1]).decode('utf8', 'ignore').encode("ascii", "ignore"), file=sys.stdout)
            if no_output:
                return e.return_code, None
            else:
                return e.return_code, e.output.decode('utf8', 'ignore').encode('ascii', 'ignore')
        except Exception as error:
            message = "Exception during cmd execution. [Exception={0}][Cmd={1}]".format(repr(error),str(cmd))
            print(message)
            raise message

        if no_output:
            return 0, None
        else:
            return 0, output.decode('utf8', 'ignore').encode('ascii', 'ignore')

    def check_sudo_status(self, raise_if_not_sudo=True):
        """ Checks if we can invoke sudo successfully. """
        try:
            print("Performing sudo status check... This should complete within 10 seconds.")
            return_code, output = self.run_command_output("timeout 10 sudo id && echo True || echo False", False, False)
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
                value = platform.linux_distribution()
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

        def open(self, file_path, mode):
            """ Provides a file handle to the file_path requested using implicit redirection where required """
            real_path = self.resolve_path(file_path)
            for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
                try:
                    return open(real_path, mode)
                except Exception as error:
                    if i <= Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                        time.sleep(i + 1)
                    else:
                        raise Exception("Unable to open {0} (retries exhausted). Error: {1}.".format(str(real_path), repr(error)))

        def __obtain_file_handle(self, file_path_or_handle, mode='a+'):
            """ Pass-through for handle. For path, resolution and handle open with retry. """
            is_path = False
            if isinstance(file_path_or_handle, str) or isinstance(file_path_or_handle, unicode):
                is_path = True
                file_path_or_handle = self.open(file_path_or_handle, mode)
            file_handle = file_path_or_handle
            return file_handle, is_path

        def read_with_retry(self, file_path_or_handle):
            """ Reads all content from a given file path in a single operation """
            operation = "FILE_READ"

            # only fully emulate non_exclusive_files from the real recording; exclusive files can be redirected and handled in emulator scenarios
            if not self.__emulator_enabled or (isinstance(file_path_or_handle, str) and os.path.basename(file_path_or_handle) not in self.__non_exclusive_files):
                file_handle, was_path = self.__obtain_file_handle(file_path_or_handle, 'r')
                value = file_handle.read()
                if was_path:  # what was passed in was not a file handle, so close the handle that was init here
                    file_handle.close()
                self.__write_record(operation, code=0, output=value, delay=0)
                return value
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
                    if i <= Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                        time.sleep(i + 1)
                    else:
                        raise Exception("Unable to write to {0} (retries exhausted). Error: {1}.".format(str(file_handle.name), repr(error)))

            if was_path: # what was passed in was not a file handle, so close the handle that was init here
                file_handle.close()

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
                value = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
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
        def utc_to_standard_datetime(utc_datetime):
            """ Converts string of format '"%Y-%m-%dT%H:%M:%SZ"' to datetime object """
            return datetime.datetime.strptime(utc_datetime.split(".")[0], "%Y-%m-%dT%H:%M:%S")
# endregion - DateTime emulator and extensions

# region - Core Emulator support functions
    def __write_record(self, operation, code, output, delay, timestamp=None):
        """ Writes a single operation record to disk if the recorder is enabled """
        if not self.__recorder_enabled or self.__real_record_handle is None:
            return

        try:
            record = {
                "timestamp": str(timestamp) if timestamp is not None else datetime.datetime.strptime(str(datetime.datetime.utcnow()).split(".")[0], "%Y-%m-%dT%H:%M:%SZ"), #WRONG
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
        self.file_system = self.FileSystem(False, False, self.__write_record, self.__read_record,
                                           emulator_root_path=os.path.dirname(self.__real_record_path))

    def set_legacy_test_settings(self, test_type, package_manager_name=Constants.DEFAULT_UNSPECIFIED_VALUE):
        if package_manager_name != Constants.DEFAULT_UNSPECIFIED_VALUE:
            self.legacy_package_manager_name = package_manager_name
        print("Setting legacy test settings... {0} - {1}".format(test_type, self.legacy_package_manager_name))
        self.legacy_test_type = test_type
# endregion - Legacy mode extensions
