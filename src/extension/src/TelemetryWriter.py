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

    def __init__(self):
        self.events_folder_path = None
        self.operation_id = ""

    def __new_event_json(self, task_name, event_level, message):
        return {
            "Version": Constants.EXT_VERSION,
            "Timestamp": str((datetime.datetime.utcnow()).strftime("%Y-%m-%dT%H:%M:%SZ")),
            "TaskName": task_name,
            "EventLevel": event_level,
            "Message": self.__ensure_message_restriction_compliance(message),
            "EventPid": "",
            "EventTid": "",
            "OperationId": self.operation_id  # we can provide activity id from config settings here, but currently we only read settings file for enable command
        }

    @staticmethod
    def __ensure_message_restriction_compliance(full_message):
        """ Removes line breaks, tabs and restricts message to a character limit """
        message_size_limit = Constants.TELEMETRY_MSG_SIZE_LIMIT_IN_CHARACTERS
        formatted_message = re.sub(r"\s+", " ", str(full_message))
        return formatted_message[:message_size_limit - 3] + '...' if len(formatted_message) > message_size_limit else formatted_message

    def write_event(self, task_name, message, event_level=Constants.TelemetryEventLevel.Informational):
        # create event json
        # check if event size complies with restriction i.e. 6k
        # write event to events file
        if os.path.getsize(self.events_folder_path) >= Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARACTERS:
            self.__delete_older_events()

        event = self.__new_event_json(task_name, event_level, message)
        if len(json.dumps(event)) > Constants.TELEMETRY_EVENT_SIZE_LIMIT_IN_CHARACTERS:
            print("Cannot send data to telemetry as it exceeded the acceptable data size. [Data not sent={0}]".format(json.dumps(message)))
        else:
            self.write_using_temp_file(self.events_folder_path, event)

    def __delete_older_events(self):
        """ Delete older events until the atleast one new event file can be added as per the size restrictions """
        try:
            if os.path.getsize(self.events_folder_path) < Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARACTERS - Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARACTERS:
                print("Not deleting any existing event files as the event directory does not exceed max limit. At least one new event file can be added.")
                return

            print("Events directory size exceeds maximum limit. Deleting older event files until at least one new event file can be added.")
            event_files = [os.path.join(self.events_folder_path, event_file) for event_file in os.listdir(self.events_folder_path) if (event_file.lower().endswith(".json"))]
            event_files.sort(key=os.path.getmtime, reverse=True)

            for event_file in event_files:
                try:
                    if os.path.getsize(self.events_folder_path) < Constants.TELEMETRY_DIR_SIZE_LIMIT_IN_CHARACTERS - Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARACTERS:
                        print("Not deleting any more event files as the event directory has sufficient space to add at least one new event file")
                        break

                    if os.path.exists(event_file):
                        os.remove(event_file)
                        print("Deleted [File={0}]".format(repr(event_file)))
                except Exception as e:
                    print("Error deleting event file. [File={0}] [Exception={1}]".format(repr(event_file), repr(e)))

        except Exception as err:
            print("Error deleting older event files. [EventsFolderPath={0}] [Exception={1}]".format(repr(self.events_folder_path), repr(err)))

    @staticmethod
    def write_using_temp_file(folder_path, data, mode='w'):
        """ Writes to a temp file in a single operation and then moves/overrides the original file with the temp """
        file_path = os.path.join(folder_path, str(int(round(time.time() * 1000))) + ".json")
        prev_events = []
        try:
            if os.path.exists(file_path):

                # if file_size exceeds max limit, sleep for 1 second, so the event can be written to a new file
                file_size = os.path.getsize(file_path)
                if file_size >= Constants.TELEMETRY_EVENT_FILE_SIZE_LIMIT_IN_CHARACTERS:
                    time.sleep(1)
                    file_path = os.path.join(folder_path, str(int(round(time.time() * 1000))) + ".json")

                with open(file_path, 'r') as file_handle:
                    file_contents = file_handle.read()
                    prev_events = json.loads(file_contents)
            prev_events.append(data)
            with tempfile.NamedTemporaryFile(mode, dir=os.path.dirname(file_path), delete=False) as tf:
                json.dump(prev_events, tf, default=data.__str__())
                tempname = tf.name
            shutil.move(tempname, file_path)
        except Exception as error:
            raise Exception("Unable to write to {0}. Error: {1}.".format(str(file_path), repr(error)))

    def set_operation_id(self, operation_id):
        self.operation_id = operation_id

