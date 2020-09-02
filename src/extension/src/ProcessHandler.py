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
import json
import os
import signal
import subprocess
import errno
import sys
import time

from extension.src.Constants import Constants


class ProcessHandler(object):
    def __init__(self, logger, ext_output_status_handler):
        self.logger = logger
        self.ext_output_status_handler = ext_output_status_handler

    def get_public_config_settings(self, config_settings):
        """ Fetches only public settings from given config_settings and returns them in json format """
        public_config_settings = {}
        public_settings_keys = Constants.ConfigPublicSettingsFields
        if config_settings is not None:
            public_config_settings.update({public_settings_keys.operation: config_settings.__getattribute__(public_settings_keys.operation),
                                           public_settings_keys.activity_id: config_settings.__getattribute__(public_settings_keys.activity_id),
                                           public_settings_keys.start_time: config_settings.__getattribute__(public_settings_keys.start_time),
                                           public_settings_keys.maximum_duration: config_settings.__getattribute__(public_settings_keys.maximum_duration),
                                           public_settings_keys.reboot_setting: config_settings.__getattribute__(public_settings_keys.reboot_setting),
                                           public_settings_keys.include_classifications: config_settings.__getattribute__(public_settings_keys.include_classifications),
                                           public_settings_keys.include_patches: config_settings.__getattribute__(public_settings_keys.include_patches),
                                           public_settings_keys.exclude_patches: config_settings.__getattribute__(public_settings_keys.exclude_patches),
                                           public_settings_keys.internal_settings: config_settings.__getattribute__(public_settings_keys.internal_settings),
                                           public_settings_keys.maintenance_run_id: config_settings.__getattribute__(public_settings_keys.maintenance_run_id)})
        return public_config_settings

    def get_env_settings(self, ext_env_handler):
        """ Fetches configs required by the core code from HandlerEnvironment file returns them in json format """
        env_settings = {}
        env_settings_keys = Constants.EnvSettingsFields
        if env_settings is not None:
            env_settings.update({env_settings_keys.log_folder: ext_env_handler.log_folder})
            env_settings.update({env_settings_keys.config_folder: ext_env_handler.config_folder})
            env_settings.update({env_settings_keys.status_folder: ext_env_handler.status_folder})
        return env_settings

    def start_daemon(self, seq_no, config_settings, ext_env_handler):
        """ Launches the core code in a separate independent process with required arguments and exits the current process immediately """
        exec_path = os.path.join(os.getcwd(), Constants.CORE_CODE_FILE_NAME)
        public_config_settings = base64.b64encode(json.dumps(self.get_public_config_settings(config_settings)).encode("utf-8")).decode("utf-8")
        env_settings = base64.b64encode(json.dumps(self.get_env_settings(ext_env_handler)).encode("utf-8")).decode("utf-8")

        args = " -sequenceNumber {0} -environmentSettings \'{1}\' -configSettings \'{2}\'".format(str(seq_no), env_settings, public_config_settings)

        # Verify the python version available on the machine to use
        self.logger.log("Python version: " + " ".join(sys.version.splitlines()))
        python_cmd = self.get_python_cmd()
        if python_cmd == Constants.PYTHON_NOT_FOUND:
            self.logger.log("Cannot execute patch operation due to error. [Error={0}]".format(Constants.PYTHON_NOT_FOUND))
            return

        command = [python_cmd + " " + exec_path + " " + args]
        self.logger.log("Launching process. [command={0}]".format(str(command)))
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.pid is not None:
            self.logger.log("New shell process launched successfully. [Process ID (PID)={0}]".format(str(process.pid)))
            # Wait for 5 seconds
            time.sleep(5)
            # if process is not running, log stdout and stderr
            if process.poll() is not None:
                self.logger.log("Process not running for [sequence={0}]".format(seq_no))
                self.logger.log("Stdout for the inactive process: [Output={0}]".format(str(process.stdout)))
                self.logger.log("Stderr for the inactive process: [Error={0}]".format(str(process.stderr)))
                return
            return process
        self.logger.log_error("Error launching process for given sequence. [sequence={0}]".format(seq_no))

    def get_python_cmd(self):
        command_to_check_for_python = "which python"
        command_to_check_for_python3 = "which python3"
        command_to_use_for_python = "python"
        command_to_use_for_python3 = "python3"

        # check if the machine contains python
        code_returned_for_python_check, output_for_python_check = self.run_command_output(command_to_check_for_python, False, False)
        if code_returned_for_python_check == 0 and command_to_use_for_python in str(output_for_python_check) and command_to_use_for_python3 not in str(output_for_python_check):
            return command_to_use_for_python

        # check if the machine contains python3
        code_returned_for_python3_check, output_for_python3_check = self.run_command_output(command_to_check_for_python3, False, False)
        if code_returned_for_python3_check == 0 and command_to_use_for_python3 in str(output_for_python3_check):
            return command_to_use_for_python3

        return Constants.PYTHON_NOT_FOUND

    def run_command_output(self, cmd, no_output=False, chk_err=False):
        code, output = self.__run_command_output_raw(cmd, no_output, chk_err)
        return code, output

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
            message = "Exception during cmd execution. [Exception={0}][Cmd={1}]".format(repr(error), str(cmd))
            print(message)
            raise message

        if no_output:
            return 0, None
        else:
            return 0, output.decode('utf8', 'ignore').encode('ascii', 'ignore')

    def identify_running_processes(self, process_ids):
        """ Returns a list of all currently active processes from the given list of process ids """
        running_process_ids = []
        for process_id in process_ids:
            if process_id != "":
                process_id = int(process_id)
                if self.is_process_running(process_id):
                    running_process_ids.append(process_id)
        self.logger.log("Processes still running from the previous request: [PIDs={0}]".format(str(running_process_ids)))
        return running_process_ids

    def is_process_running(self, pid):
        # check to see if the process is still alive
        try:
            # Sending signal 0 to a pid will raise an OSError exception if the pid is not running, and do nothing otherwise.
            os.kill(pid, 0)
            return True
        except OSError as error:
            if error.errno == errno.ESRCH:
                # ESRCH == No such process
                return False
            elif error.errno == errno.EPERM:
                # EPERM = No permission, which means there's a process to which access is denied
                return True
            else:
                # According to "man 2 kill" possible error values are (EINVAL, EPERM, ESRCH) Thus considering this as an error
                return False

    def kill_process(self, pid):
        try:
            if self.is_process_running(pid):
                self.logger.log("Terminating process: [PID={0}]".format(str(pid)))
                os.kill(pid, signal.SIGTERM)
        except OSError as error:
            self.logger.log_error("Error terminating process. [Process ID={0}] [Error={1}]".format(pid, repr(error)))
            self.ext_output_status_handler.add_error_to_status("Error terminating process. [Process ID={0}] [Error={1}]".format(pid, repr(error)), Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            if Constants.ERROR_ADDED_TO_STATUS not in repr(error):
                error.args = (error.args, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
            raise
