# Copyright 2023 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.7+
import time
from core.src.bootstrap.Constants import Constants
from core.src.core_logic.Stopwatch import Stopwatch
from abc import ABCMeta, abstractmethod

# do not instantiate directly - these are exclusively for type hinting support
from core.src.bootstrap.EnvLayer import EnvLayer
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.src.local_loggers.CompositeLogger import CompositeLogger
from core.src.service_interfaces.TelemetryWriter import TelemetryWriter
from core.src.service_interfaces.StatusHandler import StatusHandler
from core.src.package_managers.PackageManager import PackageManager
from core.src.service_interfaces.lifecycle_managers.LifecycleManager import LifecycleManager


class PatchOperator(object):
    """ Base class for all first-class patch operations (ConfigurePatchingProcessor, PatchAssessor, PatchInstaller) """

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager, lifecycle_manager, operation_name):
        # type: (EnvLayer, ExecutionConfig, CompositeLogger, TelemetryWriter, StatusHandler, PackageManager, LifecycleManager, str) -> None
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.lifecycle_manager = lifecycle_manager
        self.status_handler = status_handler
        self.package_manager = package_manager

        self.__operation_name = operation_name

        # operation state caching
        self.operation_successful = True    # starts true until negated
        self.operation_status = Constants.Status.TRANSITIONING
        self.operation_exception_error = None
        self.additional_operation_specific_perf_logs = str()

        # operation stopwatch instance
        self.stopwatch = Stopwatch(self.env_layer, self.telemetry_writer, self.composite_logger)

    __metaclass__ = ABCMeta  # For Python 3.0+, it changes to class Abstract(metaclass=ABCMeta)

    def set_operation_internal_state(self, operation_successful, operation_status, operation_exception_error=str(), additional_operation_specific_perf_logs=str()):
        # type: (bool, Constants.Status, str, str) -> None
        """ Allows for concise internal operation state caching """
        self.operation_successful = operation_successful
        self.operation_status = operation_status
        self.operation_exception_error = operation_exception_error if operation_exception_error != str() else None
        self.additional_operation_specific_perf_logs = additional_operation_specific_perf_logs

    def reset_operation_internal_state(self):
        # type: () -> None
        """ Resets the operation state as though it never ran - primarily meant for assessment """
        self.set_operation_internal_state(operation_successful=True, operation_status=Constants.Status.TRANSITIONING, operation_exception_error=str(), additional_operation_specific_perf_logs=str())

    def start_operation_with_retries(self):
        # type: () -> bool
        """ [External call] Initiates retry-based execution on core operations """
        if not self.should_operation_run():
            return True

        self.composite_logger.log("\nSTARTING PATCH OPERATION... [Operation={0}][ActivityId={1}][StartTime={2}]".format(self.__operation_name, self.execution_config.activity_id,str(self.execution_config.start_time)))

        self.status_handler.set_current_operation(self.__operation_name)
        self.set_operation_status(status=Constants.Status.TRANSITIONING)
        self.stopwatch.start()

        for i in range(0, Constants.MAX_PATCH_OPERATION_RETRY_COUNT):
            try:
                self.lifecycle_manager.lifecycle_status_check()     # keep checking if operation interrupt needs to happen
                self.start_retryable_operation_unit()
                self.set_operation_internal_state(operation_successful=True, operation_status=Constants.Status.SUCCESS, operation_exception_error=str())
                self.write_operation_perf_logs(retry_count=i)
                break   # avoid retries for success
            except Exception as error:
                if Constants.EnvLayer.PRIVILEGED_OP_MARKER in repr(error):  # Privileged operation handling for non-production use
                    self.composite_logger.log_debug('[PO] Privileged operation request intercepted: ' + repr(error))
                    raise

                if i < Constants.MAX_PATCH_OPERATION_RETRY_COUNT - 1:
                    self.composite_logger.log_verbose("Retryable error in patch operation. [Operation={0}][Error={1}]".format(self.__operation_name, repr(error)))
                    time.sleep(2 * (i + 1))
                else:
                    self.set_operation_internal_state(operation_successful=False, operation_status=Constants.Status.ERROR, operation_exception_error=repr(error))
                    self.write_operation_perf_logs(retry_count=i)
                    self.process_operation_terminal_exception(error)

        self.composite_logger.log("COMPLETED PATCH OPERATION. [Operation={0}][ActivityId={1}]".format(self.__operation_name, self.execution_config.activity_id))
        return self.operation_successful

    def write_operation_perf_logs(self, retry_count=0):
        # type: (int) -> None
        """ Generic operation perf logs with expandability - to be only called once per operation """
        operation_perf_logs = "[{0}={1}][{2}={3}][{4}={5}][{6}={7}][{8}={9}][{10}={11}]{12}".format(
            # Core operation information
            Constants.PerfLogTrackerParams.TASK, self.__operation_name,
            Constants.PerfLogTrackerParams.TASK_STATUS, str(self.operation_status),
            Constants.PerfLogTrackerParams.RETRY_COUNT, str(retry_count),
            Constants.PerfLogTrackerParams.ERROR_MSG, str(self.operation_exception_error),

            # Correlation information
            Constants.PerfLogTrackerParams.PACKAGE_MANAGER, self.package_manager.package_manager_name,
            Constants.PerfLogTrackerParams.MACHINE_INFO, self.telemetry_writer.machine_info,

            # Unique operation information, if any
            self.additional_operation_specific_perf_logs)     # non-generic entries that are not common to all operations

        self.stopwatch.stop_and_write_telemetry(operation_perf_logs)

    @abstractmethod
    def should_operation_run(self):
        # type: () -> bool
        """ Performs evaluation of if the specific operation should be running at all """
        pass

    @abstractmethod
    def start_retryable_operation_unit(self):
        # type: () -> None
        """ Idempotent operation unit of execution that can be retried """
        pass

    @abstractmethod
    def process_operation_terminal_exception(self, error):
        # type: (str) -> None
        """ Handling of any exception that occurs in the last retry attempt """
        pass

    @abstractmethod
    def set_final_operation_status(self):
        # type: () -> None
        """ Ensures that the operation status is set to a terminal state """
        pass

    @abstractmethod
    def set_operation_status(self, status=Constants.Status.TRANSITIONING, error=Constants.DEFAULT_UNSPECIFIED_VALUE):
        # type: (Constants.Status, str) -> None
        """ Abstracts away specificities in setting operation status """
        pass

