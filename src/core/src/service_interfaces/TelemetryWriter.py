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

    def __init__(self, env_layer, composite_logger, events_folder_path):
        self.env_layer = env_layer
        self.composite_logger = composite_logger
        self.__is_agent_compatible = False
        self.__operation_id = str(datetime.datetime.utcnow())
        self.events_folder_path = None
        self.__telemetry_event_counter = 1  # will be added at the end of each event sent to telemetry to assist in tracing and identifying event/message loss in telemetry
        self.start_time_for_event_count_throttle_check = datetime.datetime.utcnow()
        self.event_count = 1

        if events_folder_path is not None and os.path.exists(events_folder_path):
            self.events_folder_path = events_folder_path
            self.__is_agent_compatible = True

        self.write_event('Started Linux patch core operation.', Constants.TelemetryEventLevel.Informational)
        self.write_machine_config_info()

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
            'output': str(output)
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
            "OperationId": self.__operation_id  # activity id from from config settings
        }

    def __ensure_message_restriction_compliance(self, full_message):
        """ Removes line breaks, tabs and restricts message to a char limit.
        In case a message is truncated due to size restrictions, adds the count of chars dropped at the end.
        Adds a telemetry event counter at the end of every event, irrespective of truncation, which can be used in debugging operation flow. """

        message_size_limit_in_chars = Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_CHARS
        formatted_message = re.sub(r"\s+", " ", str(full_message))

        if len(formatted_message.encode('utf-8')) + Constants.TELEMETRY_EVENT_COUNTER_MSG_SIZE_LIMIT_IN_CHARS > message_size_limit_in_chars:
            self.composite_logger.log_telemetry_module("Data sent to telemetry will be truncated as it exceeds size limit. [Message={0}]".format(str(formatted_message)))
            formatted_message = formatted_message.encode('utf-8')
            chars_dropped = len(formatted_message) - message_size_limit_in_chars + Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_CHARS + Constants.TELEMETRY_EVENT_COUNTER_MSG_SIZE_LIMIT_IN_CHARS
            formatted_message = formatted_message[:message_size_limit_in_chars - Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_CHARS - Constants.TELEMETRY_EVENT_COUNTER_MSG_SIZE_LIMIT_IN_CHARS].decode('utf-8') + '. [{0} chars dropped]'.format(chars_dropped)

        formatted_message += " [TC={0}]".format(self.__telemetry_event_counter)
        return formatted_message

    def write_event(self, message, event_level=Constants.TelemetryEventLevel.Informational, task_name=Constants.TELEMETRY_TASK_NAME, is_event_file_throttling_needed=True):
        """ Creates and writes event to event file after validating none of the telemetry size restrictions are breached
        NOTE: is_event_file_throttling_needed is used to determine if event file throtting is required and as such should always be True.
        The only scenario where this is False is when throttling is taking place and we write to telemetry about it. i.e. only from within __throttle_telemetry_writes_if_required()"""
        try:
            if not self.is_agent_compatible() or not Constants.TELEMETRY_ENABLED_AT_EXTENSION:
                return

            # ensure file throttle limit is reached
            self.__throttle_telemetry_writes_if_required(is_event_file_throttling_needed)

            self.__delete_older_events_if_dir_size_limit_not_met()

            event = self.__new_event_json(event_level, message, task_name)
            if len(json.dumps(event)) > Constants.TELEMETRY_EVENT_SIZE_LIMIT_IN_CHARS:
                self.composite_logger.log_telemetry_module_error("Cannot send data to telemetry as it exceeded the acceptable data size. [Data not sent={0}]".format(json.dumps(message)))
            else:
                file_path, all_events = self.__get_file_and_content_to_write(self.events_folder_path, event)
                self.__write_event_using_temp_file(file_path, all_events)
        except Exception:
            raise Exception("Internal reporting error. Execution could not complete.")

    def __delete_older_events_if_dir_size_limit_not_met(self):
        """ Delete older events until the at least one new event file can be added as per the size restrictions """
        if self.__get_events_dir_size() < Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS - Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS:
            # Not deleting any existing event files as the event directory does not exceed max limit. At least one new event file can be added. Not printing this statement as it will add repetitive logs
            return

        self.composite_logger.log_telemetry_module("Events directory size exceeds maximum limit. Deleting older event files until at least one new event file can be added.")
        event_files = [os.path.join(self.events_folder_path, event_file) for event_file in os.listdir(self.events_folder_path) if (event_file.lower().endswith(".json"))]
        event_files.sort(key=os.path.getmtime, reverse=True)

        for event_file in event_files:
            try:
                if self.__get_events_dir_size() < Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS - Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS:
                    # Not deleting any more event files as the event directory has sufficient space to add at least one new event file. Not printing this statement as it will add repetitive logs
                    break

                if os.path.exists(event_file):
                    os.remove(event_file)
                    self.composite_logger.log_telemetry_module("Deleted event file. [File={0}]".format(repr(event_file)))
            except Exception as e:
                self.composite_logger.log_telemetry_module_error("Error deleting event file. [File={0}] [Exception={1}]".format(repr(event_file), repr(e)))

        if self.__get_events_dir_size() >= Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARS:
            self.composite_logger.log_telemetry_module_error("Older event files were not deleted. Current event will not be sent to telemetry as events directory size exceeds maximum limit")
            raise

    def __get_file_and_content_to_write(self, folder_path, data):
        """ Identifies the file where the event is to be written can be an existing event file or a new one depending upon the size restrictions. If event is to be written to an existing file, fetches retains it's content """
        file_path = self.__get_event_file_path(folder_path)
        all_events = []
        if os.path.exists(file_path):
            file_size = self.get_file_size(file_path)
            # if file_size exceeds max limit, sleep for 1 second, so the event can be written to a new file since the event file name is a timestamp
            if file_size >= Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARS:
                time.sleep(1)
                file_path = self.__get_event_file_path(folder_path)
            else:
                all_events = self.__fetch_events_from_previous_file(file_path)  # fetches existing content within the file
        all_events.append(data)
        return file_path, all_events

    def __throttle_telemetry_writes_if_required(self, is_event_file_throttling_needed=True):
        """ Ensures the # of event files that can be written per time unit restriction is met. Returns False if the any updates are required after the restriction enforcement. For eg: file_name is a timestamp and should be modified if a wait is added here """
        if not is_event_file_throttling_needed:
            return

        if (datetime.datetime.utcnow() - self.start_time_for_event_count_throttle_check).total_seconds() < Constants.TELEMETRY_MAX_TIME_IN_SECONDS_FOR_EVENT_COUNT_THROTTLE:
            # If event count limit reached before time period, wait out the remaining time. Checking against one less than max limit to allow room for writing a throttling msg to telemetry
            if self.event_count >= Constants.TELEMETRY_MAX_EVENT_COUNT_THROTTLE - 1:
                end_time_for_event_count_throttle_check = self.start_time_for_event_count_throttle_check + datetime.timedelta(seconds=Constants.TELEMETRY_MAX_TIME_IN_SECONDS_FOR_EVENT_COUNT_THROTTLE)
                time_to_wait_in_secs = (end_time_for_event_count_throttle_check - datetime.datetime.utcnow()).total_seconds()
                event_write_throttled_msg = "Max telemetry event file limit reached. Extension will wait until a telemetry event file can be written again. [WaitTimeInSecs={0}]".format(str(time_to_wait_in_secs))
                self.composite_logger.log_telemetry_module(event_write_throttled_msg)
                self.write_event(message=event_write_throttled_msg, event_level=Constants.TelemetryEventLevel.Informational, is_event_file_throttling_needed=False)
                time.sleep(time_to_wait_in_secs)
                self.start_time_for_event_count_throttle_check = datetime.datetime.utcnow()
                self.event_count = 1

        else:
            self.start_time_for_event_count_throttle_check = datetime.datetime.utcnow()
            self.event_count = 1

    def __write_event_using_temp_file(self, file_path, all_events, mode='w'):
        """ Writes to a temp file in a single operation and then moves/overrides the original file with the temp """
        try:
            with tempfile.NamedTemporaryFile(mode, dir=os.path.dirname(file_path), delete=False) as tf:
                json.dump(all_events, tf, default=all_events.__str__())
                tempname = tf.name
            shutil.move(tempname, file_path)
            self.__telemetry_event_counter += 1
            self.event_count += 1
        except Exception as error:
            self.composite_logger.log_telemetry_module_error("Unable to write to telemetry. [Event File={0}] [Error={1}].".format(str(file_path), repr(error)))
            raise

    def __get_events_dir_size(self):
        """ Returns total size, in bytes, of the events folder """
        total_dir_size = 0
        for f in os.listdir(self.events_folder_path):
            if os.path.isfile(os.path.join(self.events_folder_path, f)):
                total_dir_size += os.path.getsize(os.path.join(self.events_folder_path, f))
        return total_dir_size

    @staticmethod
    def __get_event_file_path(folder_path):
        """ Returns the filename, generated from current timestamp in seconds, to be used to write an event. Eg: 1614111606855.json"""
        return os.path.join(folder_path, str(int(round(time.time() * 1000))) + ".json")

    @staticmethod
    def get_file_size(file_path):
        """ Returns the size of a file. Extracted out for mocking in unit test """
        return os.path.getsize(file_path)

    @staticmethod
    def __fetch_events_from_previous_file(file_path):
        """ Fetch contents from the file """
        with open(file_path, 'r') as file_handle:
            file_contents = file_handle.read()
            return json.loads(file_contents)

    def set_operation_id(self, operation_id):
        self.__operation_id = operation_id

    def is_agent_compatible(self):
        """ Verifies if telemetry is available. Stops execution if not available. """
        return self.__is_agent_compatible

