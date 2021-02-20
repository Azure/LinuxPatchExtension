import os
import time
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
        time.sleep = self.mock_sleep

    def mock_sleep(self, seconds):
        pass

    def create_temp_file(self, test_dir, file_name, content=None):
        with open(os.path.join(test_dir, file_name), 'w') as f:
            if content is not None:
                f.write(content)

