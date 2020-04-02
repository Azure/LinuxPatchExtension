import datetime
import json
import os

from tests.library.ArgumentComposer import ArgumentComposer

from src.bootstrap.Bootstrapper import Bootstrapper
from src.bootstrap.Constants import Constants


class RuntimeCompositor(object):
    def __init__(self, argv=Constants.DEFAULT_UNSPECIFIED_VALUE):
        # Init data
        self.current_env = Constants.DEV
        os.putenv(Constants.LPE_ENV_VARIABLE, self.current_env)
        self.argv = argv if argv != Constants.DEFAULT_UNSPECIFIED_VALUE else ArgumentComposer().get_composed_arguments()

        # Adapted bootstrapper
        bootstrapper = Bootstrapper(self.argv)
        bootstrapper.stdout_file_mirror.stop()

        # Core components
        container = bootstrapper.build_out_container()
        self.file_logger = bootstrapper.file_logger
        self.composite_logger = bootstrapper.composite_logger
        self.lifecycle_manager, self.telemetry_writer, self.status_handler = bootstrapper.build_core_components(container)
        self.execution_config = container.get('execution_config')

        # Extension handler dependency
        self.write_ext_state_file(self.lifecycle_manager.ext_state_file_path, self.execution_config.sequence_number, datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), self.execution_config.operation)

    @staticmethod
    def write_ext_state_file(path, sequence_number, achieve_enable_by, operation):
        data = {
            "number":sequence_number,
            "achieveEnableBy": achieve_enable_by,
            "operation": operation
        }

        with open(path, "w+") as file_handle:
            file_handle.write(json.dumps(data))

