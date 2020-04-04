import datetime
import json
import re

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
    def __init__(self, logger, json_file_handler, log_file_path):
        self.logger = logger
        self.json_file_handler = json_file_handler
        self.__log_file_path = log_file_path
        self.file_ext = Constants.STATUS_FILE_EXTENSION
        self.file_keys = Constants.StatusFileFields
        self.status = Constants.Status

        # Internal in-memory representation of Patch NoOperation data
        self.__nooperation_errors = []
        self.__nooperation_total_error_count = 0  # All errors during assess, includes errors not in error objects due to size limit

        self.__current_operation = None

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
        if status_json != None and len(status_json) is not 0:
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
        except Exception as error:
            error_message = "Error in status file creation: " + repr(error)
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
            "errors": self.__set_errors_json(self.__nooperation_total_error_count, self.__nooperation_errors)
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

    # region - Error objects
    def set_current_operation(self, operation):
        self.__current_operation = operation

    def add_error_to_summary(self, message, error_code=Constants.PatchOperationErrorCodes.DEFAULT_ERROR):
        """ Add error to the respective error objects """
        if not message:
            return

        formatted_message = self.__ensure_error_message_restriction_compliance(message)
        # Compose error detail
        error_detail = {
            "code": str(error_code),
            "message": str(formatted_message)
        }

        if self.__current_operation == Constants.NOOPERATION:
            self.__add_error(self.__nooperation_errors, error_detail)
            self.__nooperation_total_error_count += 1
        else:
            return

    def __ensure_error_message_restriction_compliance(self, full_message):
        """ Removes line breaks, tabs and restricts message to a character limit """
        message_size_limit = Constants.STATUS_ERROR_MSG_SIZE_LIMIT_IN_CHARACTERS - 3
        formatted_message = re.sub(r"\s+", " ", str(full_message))
        return formatted_message[:message_size_limit] + '...' if len(formatted_message) > message_size_limit else formatted_message

    def __add_error(self, add_to, detail):
        """ Add formatted error object to given errors list """
        if len(add_to) >= Constants.STATUS_ERROR_LIMIT:
            errors_to_remove = len(add_to) - Constants.STATUS_ERROR_LIMIT + 1
            for x in range(0, errors_to_remove):
                add_to.pop()
        add_to.insert(0, detail)

    def __set_errors_json(self, error_count_by_operation, errors_by_operation):
        """ Compose the error object json to be added in 'errors' in given operation's summary """
        return {
            "code": Constants.PatchOperationTopLevelErrorCode.SUCCESS if error_count_by_operation == 0 else Constants.PatchOperationTopLevelErrorCode.ERROR,
            "details": errors_by_operation,
            "message": "{0} error/s reported. The latest {1} error/s are shared in detail. To view all errors, review this log file on the machine: {2}".format(error_count_by_operation, len(errors_by_operation), self.__log_file_path)
        }
    # endregion
