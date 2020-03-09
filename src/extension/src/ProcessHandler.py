import base64
import json
import os
import signal
import subprocess
import errno
from src.Constants import Constants


class ProcessHandler(object):
    def __init__(self, logger):
        self.logger = logger

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
                                           public_settings_keys.internal_settings: config_settings.__getattribute__(public_settings_keys.internal_settings)})
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
        """ Launches the core code in a separate independent process with required arguements and exits the current process immediately """
        exec_path = os.path.join(os.getcwd(), Constants.CORE_CODE_FILE_NAME)
        public_config_settings = base64.b64encode(json.dumps(self.get_public_config_settings(config_settings)).encode("utf-8")).decode("utf-8")
        env_settings = base64.b64encode(json.dumps(self.get_env_settings(ext_env_handler)).encode("utf-8")).decode("utf-8")

        args = " -sequenceNumber {0} -environmentSettings \'{1}\' -configSettings \'{2}\'".format(str(seq_no), env_settings, public_config_settings)
        command = ["python " + exec_path + " " + args]
        self.logger.log("Launching process. [command={0}]".format(str(command)))
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.pid is not None:
            self.logger.log("New shell process launched successfully. [Process ID (PID)={0}]".format(str(process.pid)))
            return process
        self.logger.log_error("Error launching process for given sequence. [sequence={0}]".format(seq_no))

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
            raise
