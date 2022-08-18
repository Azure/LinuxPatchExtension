import os
import tempfile
import time
import uuid

from extension.src.Constants import Constants
from extension.src.EnvLayer import EnvLayer
from extension.src.EnvHealthManager import EnvHealthManager
from extension.src.TelemetryWriter import TelemetryWriter
from extension.src.Utility import Utility
from extension.src.file_handlers.JsonFileHandler import JsonFileHandler
from extension.src.local_loggers.Logger import Logger


class RuntimeComposer(object):
    def __init__(self):
        self.backup_os_getenv = os.getenv
        os.getenv = self.getenv_telemetry_enabled
        self.logger = Logger()
        self.utility = Utility(self.logger)
        self.json_file_handler = JsonFileHandler(self.logger)
        self.env_layer = EnvLayer()
        self.env_health_manager = EnvHealthManager(self.env_layer)
        self.telemetry_writer = TelemetryWriter(self.logger, self.env_layer)
        time.sleep = self.mock_sleep
        self.env_layer.is_tty_required = self.mock_is_tty_required
        self.env_health_manager.check_sudo_status = self.mock_check_sudo_status

        if os.getenv('RUNNER_TEMP', None) is not None:
            def mkdtemp_runner():
                temp_path = os.path.join(os.getenv('RUNNER_TEMP'), str(uuid.uuid4()))
                os.mkdir(temp_path)
                return temp_path
            tempfile.mkdtemp = mkdtemp_runner

        print("CWD: {0}".format(os.getcwd()))

    def mock_sleep(self, seconds):
        pass

    def mock_is_tty_required(self):
        return False

    def mock_check_sudo_status(self, raise_if_not_sudo=True):
        return True

    def create_temp_file(self, test_dir, file_name, content=None):
        with open(os.path.join(test_dir, file_name), 'w') as f:
            if content is not None:
                f.write(content)

    def getenv_telemetry_enabled(self, key, value=None):
        """ Overrides get_env_var method to enable telemetry by default for all tests """
        value = self.backup_os_getenv(key, value)
        if key == Constants.AZURE_GUEST_AGENT_EXTENSION_SUPPORTED_FEATURES_ENV_VAR:
            # Default to supported telemetry so test cases pass. This can be overridden on a per-test basis for testing
            return '[{"Key": "ExtensionTelemetryPipeline", "Value": "1.0"}]'
        else:
            return value
