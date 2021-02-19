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

from extension.src.Constants import Constants


class TelemetryWriter(object):
    """Class for writing telemetry data to events"""

    def __init__(self, logger):
        self.logger = logger
        self.events_folder_path = None
        self.operation_id = ""

    def __new_event_json(self, event_level, message, task_name):
        return {
            "Version": Constants.EXT_VERSION,
            "Timestamp": str((datetime.datetime.utcnow()).strftime(Constants.UTC_DATETIME_FORMAT)),
            "TaskName": task_name,
            "EventLevel": event_level,
            "Message": self.__ensure_message_restriction_compliance(message),
            "EventPid": "",
            "EventTid": "",
            "OperationId": self.operation_id  # we can provide activity id from config settings here, but currently we only read settings file for enable command
        }

    def __ensure_message_restriction_compliance(self, full_message):
        """ Removes line breaks, tabs and restricts message to a byte limit """
        message_size_limit_in_bytes = Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_BYTES
        formatted_message = re.sub(r"\s+", " ", str(full_message))

        if len(formatted_message.encode('utf-8')) > message_size_limit_in_bytes:
            self.logger.log_telemetry("Data sent to telemetry will be truncated as it exceeds size limit. [Message={0}]".format(str(formatted_message)))
            formatted_message = formatted_message.encode('utf-8')
            bytes_dropped = len(formatted_message) - message_size_limit_in_bytes + Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_BYTES
            return formatted_message[:message_size_limit_in_bytes - Constants.TELEMETRY_BUFFER_FOR_DROPPED_COUNT_MSG_IN_BYTES].decode('utf-8') + '. [{0} bytes dropped]'.format(bytes_dropped)

        return formatted_message

    def write_event(self, message, event_level=Constants.TelemetryEventLevel.Informational, task_name=Constants.TELEMETRY_TASK_NAME):
        """ Creates and writes event to event file after validating none of the telemetry size restrictions are breached """
        if self.events_folder_path is None or not os.path.exists(self.events_folder_path):
            return

        self.__delete_older_events()

        event = self.__new_event_json(event_level, message, task_name)
        if len(json.dumps(event)) > Constants.TELEMETRY_EVENT_SIZE_LIMIT_IN_BYTES:
            self.logger.log_telemetry_error("Cannot send data to telemetry as it exceeded the acceptable data size. [Data not sent={0}]".format(json.dumps(message)))
            # print("Cannot send data to telemetry as it exceeded the acceptable data size. [Data not sent={0}]".format(json.dumps(message)))
        else:
            self.write_event_using_temp_file(self.events_folder_path, event)

    def __delete_older_events(self):
        """ Delete older events until the at least one new event file can be added as per the size restrictions """
        if self.__get_events_dir_size() < Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES - Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES:
            # Not deleting any existing event files as the event directory does not exceed max limit. At least one new event file can be added. Not printing this statement as it will add repetitive logs
            return

        self.logger.log_telemetry("Events directory size exceeds maximum limit. Deleting older event files until at least one new event file can be added.")
        event_files = [os.path.join(self.events_folder_path, event_file) for event_file in os.listdir(self.events_folder_path) if (event_file.lower().endswith(".json"))]
        event_files.sort(key=os.path.getmtime, reverse=True)

        for event_file in event_files:
            try:
                if self.__get_events_dir_size() < Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_BYTES - Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_BYTES:
                    # Not deleting any more event files as the event directory has sufficient space to add at least one new event file. Not printing this statement as it will add repetitive logs
                    break

                if os.path.exists(event_file):
                    os.remove(event_file)
                    self.logger.log_telemetry("Deleted event file. [File={0}]".format(repr(event_file)))
            except Exception as e:
                self.logger.log_telemetry_error("Error deleting event file. [File={0}] [Exception={1}]".format(repr(event_file), repr(e)))

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

    def set_operation_id(self, operation_id):
        self.operation_id = operation_id

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

