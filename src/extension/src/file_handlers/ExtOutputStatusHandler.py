import datetime
import json

from src.Constants import Constants

'''
<SequenceNumber>.status
For the extension wrapper, the status structure is simply the following (no substatuses):
[{
    "version": 1.0,
    "timestampUTC": "2019-07-20T12:12:14Z",
    "status": {
        "name": "Azure Patch Management",
        "operation": "Assessment / Deployment / NoOperation",
        "status": "transitioning / error / success / warning",
        "code": 0,
        "formattedMessage": {
                        "lang": "en-US",
                        "message": "<Message>"
        }
    }
}]
'''


class ExtOutputStatusHandler(object):
    """ Responsible for managing <sequence number>.status file in the status folder path given in HandlerEnvironment.json """
    def __init__(self, logger, json_file_handler):
        self.logger = logger
        self.json_file_handler = json_file_handler
        self.file_ext = Constants.STATUS_FILE_EXTENSION
        self.file_keys = Constants.StatusFileFields
        self.status = Constants.Status

    def write_status_file(self, seq_no, dir_path, operation, substatus_json, status=Constants.Status.Transitioning.lower()):
        self.logger.log("Writing status file to provide patch management data for [Sequence={0}]".format(str(seq_no)))
        file_name = str(seq_no) + self.file_ext
        content = [{
            self.file_keys.version: "1.0",
            self.file_keys.timestamp_utc: str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")),
            self.file_keys.status: {
                self.file_keys.status_name: "Azure Patch Management",
                self.file_keys.status_operation: str(operation),
                self.file_keys.status_status: status.lower(),
                self.file_keys.status_code: 0,
                self.file_keys.status_formatted_message: {
                    self.file_keys.status_formatted_message_lang: "en-US",
                    self.file_keys.status_formatted_message_message: ""
                },
                self.file_keys.status_substatus: substatus_json
            }
        }]
        self.json_file_handler.write_to_json_file(dir_path, file_name, content)

    def read_file(self, seq_no, dir_path):
        file_name = str(seq_no) + self.file_ext
        status_json = self.json_file_handler.get_json_file_content(file_name, dir_path)
        if status_json is None:
            return None
        return status_json

    def update_key_value_safely(self, status_json, key, value_to_update, parent_key=None):
        if status_json is not None and len(status_json) is not 0:
            if parent_key is None:
                status_json[0].update({key: value_to_update})
            else:
                if parent_key in status_json[0]:
                    status_json[0].get(parent_key).update({key: value_to_update})
                else:
                    self.logger.log_error("Error updating config value in status file. [Config={0}]".format(key))

    def update_file(self, seq_no, dir_path):
        """ Reseting status=Transitioning and code=0 with latest timestamp, while retaining all other values"""
        try:
            file_name = str(seq_no) + self.file_ext
            self.logger.log("Updating file. [File={0}]".format(file_name))
            status_json = self.read_file(str(seq_no), dir_path)

            if status_json is None:
                self.logger.log_error("Error processing file. [File={0}]".format(file_name))
                return
            self.update_key_value_safely(status_json, self.file_keys.status_status, self.status.Transitioning.lower(), self.file_keys.status_status)
            self.update_key_value_safely(status_json, self.file_keys.status_code, 0, self.file_keys.status_status)
            self.update_key_value_safely(status_json, self.file_keys.timestamp_utc, str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")))
            self.json_file_handler.write_to_json_file(dir_path, file_name, status_json)
        except IOError:
            error_message = "Error in status file creation"
            self.logger.log_error(error_message)
            raise

    def set_nooperation_substatus_json(self, seq_no, dir_path, operation, activity_id, start_time, status=Constants.Status.Transitioning, code=0):
        """ Prepare the nooperation substatus json including the message containing nooperation summary """
        # Wrap patches into nooperation summary
        nooperation_summary_json = self.new_nooperation_summary_json(activity_id, start_time)

        # Wrap nooperation summary into nooperation substatus
        nooperation_substatus_json = self.new_substatus_json_for_operation(Constants.PATCH_NOOPERATION_SUMMARY, status, code, json.dumps(nooperation_summary_json))

        # Update status on disk
        self.write_status_file(seq_no, dir_path, operation, nooperation_substatus_json, status)

    def new_nooperation_summary_json(self, activity_id, start_time):
        """ This is the message inside the nooperation substatus """
        # Compose substatus message
        return {
            "activityId": str(activity_id),
            "startTime": str(start_time),
            "lastModifiedTime": str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")),
            "errors": ""  # TODO: Implement this to spec
        }

    def new_substatus_json_for_operation(self, operation_name, status="Transitioning", code=0, message=json.dumps("{}")):
        """ Generic substatus for nooperation """
        # NOTE: Todo Function is same for assessment and install, can be generalized later
        return {
            "name": str(operation_name),
            "status": str(status).lower(),
            "code": code,
            "formattedMessage": {
                "lang": "en-US",
                "message": str(message)
            }
        }
