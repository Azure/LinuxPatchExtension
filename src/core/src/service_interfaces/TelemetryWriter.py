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
import datetime
import json
import os
import re
import shutil
import tempfile
import time

from core.src.bootstrap.Constants import Constants


class TelemetryWriter(object):
    """Class for writing telemetry data to data transports"""

    def __init__(self, composite_logger, env_layer):
        self.composite_logger = composite_logger
        self.env_layer = env_layer
        self.events_folder_path = None
        self.__execution_config = None
        self.__is_telemetry_startup = False  # to avoid re-sending startup events to telemetry

    def write_telemetry_startup_events(self):
        self.write_event('Started Linux patch core operation.', Constants.TelemetryEventLevel.Informational)
        self.write_machine_config_info()
        self.write_config_info(self.__execution_config.config_settings, 'execution_config')

    def write_config_info(self, config_info, config_type='unknown'):
        # Configuration info
        payload_json = {
            'config_type': config_type,
            'config_value': config_info
        }
        return self.write_event(payload_json, Constants.TelemetryEventLevel.Informational)

    def write_package_info(self, package_name, package_ver, package_size, install_dur, install_result, code_path, install_cmd, output=''):
        # Package information compiled after the package is attempted to be installed
        max_output_length = 1024

        # primary payload
        message = {'package_name': str(package_name), 'package_version': str(package_ver),
                   'package_size': str(package_size), 'install_duration': str(install_dur),
                   'install_result': str(install_result), 'code_path': code_path,
                   'install_cmd': str(install_cmd), 'output': str(output)[0:max_output_length]}
        self.write_event(message, Constants.TelemetryEventLevel.Informational)

        # additional message payloads for output continuation only if we need it for specific troubleshooting
        if len(output) > max_output_length:
            for i in range(1, int(len(output)/max_output_length) + 1):
                message = {'install_cmd': str(install_cmd), 'output_continuation': str(output)[(max_output_length*i):(max_output_length*(i+1))]}
                self.write_event(message, Constants.TelemetryEventLevel.Informational)

    # Composed payload
    def write_machine_config_info(self):
        # Machine info - sent only once at the start of the run
        machine_info = {
            'platform_name': str(self.env_layer.platform.linux_distribution()[0]),
            'platform_version': str(self.env_layer.platform.linux_distribution()[1]),
            'machine_cpu': self.get_machine_processor(),
            'machine_arch': str(self.env_layer.platform.machine()),
            'disk_type': self.get_disk_type()
        }
        return self.write_config_info(machine_info, 'machine_config')

    def write_execution_error(self, cmd, code, output):
        # Expected to log any errors from a cmd execution, including package manager execution errors
        error_payload = {
            'cmd': str(cmd),
            'code': str(code),
            'output': str(output)[0:3072]
        }
        return self.write_event(error_payload, Constants.TelemetryEventLevel.Error)
    # endregion

    # region Machine config retrieval methods
    def get_machine_processor(self):
        """Retrieve machine processor info"""
        cmd = "cat /proc/cpuinfo | grep name"
        code, out = self.env_layer.run_command_output(cmd, False, False)

        if out == "" or "not recognized as an internal or external command" in out:
            return "No information found"
        # Example output:
        # model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz
        lines = out.split("\n")
        return lines[0].split(":")[1].lstrip()

    def get_disk_type(self):
        """ Retrieve disk info """
        cmd = "cat /sys/block/sda/queue/rotational"
        code, out = self.env_layer.run_command_output(cmd, False, False)
        if "1" in out:
            return "Hard drive"
        elif "0" in out:
            return "SSD"
        else:
            return "Unknown"
    # end region

    def __new_event_json(self, event_level, message, task_name):
        return {
            "Version": Constants.EXT_VERSION,
            "Timestamp": str(datetime.datetime.utcnow()),
            "TaskName": task_name,
            "EventLevel": event_level,
            "Message": self.__ensure_message_restriction_compliance(message),
            "EventPid": "",
            "EventTid": "",
            "OperationId": "" if self.__execution_config is None else self.__execution_config.activity_id  # activity id from from config settings
        }

    def __ensure_message_restriction_compliance(self, full_message):
        """ Removes line breaks, tabs and restricts message to a byte limit """
        message_size_limit_in_bytes = Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_BYTES
        formatted_message = re.sub(r"\s+", " ", str(full_message))

        if len(formatted_message.encode('utf-8')) > message_size_limit_in_bytes:
            self.composite_logger.log_telemetry_module("Data sent to telemetry will be truncated as it exceeds size limit. [Message={0}]".format(str(formatted_message)))
            formatted_message = formatted_message.encode('utf-8')
            bytes_dropped = len(formatted_message) - message_size_limit_in_bytes + Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_BYTES
            return formatted_message[:message_size_limit_in_bytes - Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_BYTES].decode('utf-8') + '. [{0} bytes dropped]'.format(bytes_dropped)

        return formatted_message

    def write_event(self, message, event_level=Constants.TelemetryEventLevel.Informational, task_name=Constants.TELEMETRY_TASK_NAME):
        """ Creates and writes event to event file after validating none of the telemetry size restrictions are breached """
        if self.events_folder_path is None or not os.path.exists(self.events_folder_path) or not Constants.TELEMETRY_ENABLED_AT_EXTENSION:
            return

        self.__delete_older_events()

        event = self.__new_event_json(event_level, message, task_name)
        if len(json.dumps(event)) > Constants.TELEMETRY_EVENT_SIZE_LIMIT_IN_BYTES:
            self.composite_logger.log_telemetry_module_error("Cannot send data to telemetry as it exceeded the acceptable data size. [Data not sent={0}]".format(json.dumps(message)))
        else:
            self.write_event_using_temp_file(self.events_folder_path, event)

    def __delete_older_events(self):
        """ Delete older events until the at least one new event file can be added as per the size restrictions """
        if self.__get_events_dir_size() < Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES - Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES:
            # Not deleting any existing event files as the event directory does not exceed max limit. At least one new event file can be added. Not printing this statement as it will add repetitive logs
            return

        self.composite_logger.log_telemetry_module("Events directory size exceeds maximum limit. Deleting older event files until at least one new event file can be added.")
        event_files = [os.path.join(self.events_folder_path, event_file) for event_file in os.listdir(self.events_folder_path) if (event_file.lower().endswith(".json"))]
        event_files.sort(key=os.path.getmtime, reverse=True)

        for event_file in event_files:
            try:
                if self.__get_events_dir_size() < Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES - Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES:
                    # Not deleting any more event files as the event directory has sufficient space to add at least one new event file. Not printing this statement as it will add repetitive logs
                    break

                if os.path.exists(event_file):
                    os.remove(event_file)
                    self.composite_logger.log_telemetry_module("Deleted event file. [File={0}]".format(repr(event_file)))
            except Exception as e:
                self.composite_logger.log_telemetry_module_error("Error deleting event file. [File={0}] [Exception={1}]".format(repr(event_file), repr(e)))

        if self.__get_events_dir_size() >= Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES:
            raise Exception("Older event files were not deleted. Current event will not be sent to telemetry as events directory size exceeds maximum limit")

    def write_event_using_temp_file(self, folder_path, data, mode='w'):
        """ Writes to a temp file in a single operation and then moves/overrides the original file with the temp """
        file_path = self.__get_event_file_path(folder_path)
        prev_events = []
        try:
            if os.path.exists(file_path):
                file_size = self.get_file_size(file_path)
                # if file_size exceeds max limit, sleep for 1 second, so the event can be written to a new file since the event file name is a timestamp
                if file_size >= Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES:
                    time.sleep(1)
                    file_path = self.__get_event_file_path(folder_path)
                else:
                    prev_events = self.__fetch_events_from_previous_file(file_path)

            prev_events.append(data)
            with tempfile.NamedTemporaryFile(mode, dir=os.path.dirname(file_path), delete=False) as tf:
                json.dump(prev_events, tf, default=data.__str__())
                tempname = tf.name
            shutil.move(tempname, file_path)
        except Exception as error:
            raise Exception("Unable to write to telemetry. [Event File={0}] [Error={1}].".format(str(file_path), repr(error)))

    def setup_telemetry(self, execution_config):
        self.__execution_config = execution_config
        self.events_folder_path = self.__execution_config.events_folder

    def __get_events_dir_size(self):
        return sum([os.path.getsize(os.path.join(self.events_folder_path, f)) for f in os.listdir(self.events_folder_path) if os.path.isfile(os.path.join(self.events_folder_path, f))])

    @staticmethod
    def __get_event_file_path(folder_path):
        return os.path.join(folder_path, str(int(round(time.time() * 1000))) + ".json")

    @staticmethod
    def get_file_size(file_path):
        return os.path.getsize(file_path)

    @staticmethod
    def __fetch_events_from_previous_file(file_path):
        with open(file_path, 'r') as file_handle:
            file_contents = file_handle.read()
            return json.loads(file_contents)

    def startup_telemetry_if_agent_compatible(self):
        """ Verifies if telemetry is available. Stops execution if not available. Sends startup events if telemetry is available """

        if self.events_folder_path is None:
            error_msg = "The minimum Azure Linux Agent version prerequisite for Linux patching was not met. Please update the Azure Linux Agent on this machine."
            self.composite_logger.log_telemetry_module_error(error_msg)
            raise Exception(error_msg)

        self.composite_logger.log_telemetry_module("The minimum Azure Linux Agent version prerequisite for Linux patching was met.")
        if not self.__is_telemetry_startup:
            self.write_telemetry_startup_events()
            self.__is_telemetry_startup = True
        else:
            self.composite_logger.log_telemetry_module("Telemetry startup was completed in an earlier instance, please check older telemetry events")

