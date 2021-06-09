import os
import time

from extension.src.EnvLayer import EnvLayer
from extension.src.EnvManager import EnvManager
from extension.src.TelemetryWriter import TelemetryWriter
from extension.src.Utility import Utility
from extension.src.file_handlers.JsonFileHandler import JsonFileHandler
from extension.src.local_loggers.Logger import Logger


class RuntimeComposer(object):
    def __init__(self):
        self.logger = Logger()
        self.telemetry_writer = TelemetryWriter(self.logger)
        self.utility = Utility(self.logger)
        self.json_file_handler = JsonFileHandler(self.logger)
        self.env_layer = EnvLayer()
        self.env_manager = EnvManager(self.env_layer)
        time.sleep = self.mock_sleep
        self.env_layer.is_tty_required = self.mock_is_tty_required
        self.env_manager.check_sudo_status = self.mock_check_sudo_status

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

