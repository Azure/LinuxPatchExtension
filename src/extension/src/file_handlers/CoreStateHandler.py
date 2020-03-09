"""
CoreState.json sample structure:
{
    "coreSequence": {
        "number":  3,
        "action": "<Assessment/Deployment>",
        "completed": "<true/false>",
        "lastHeartbeat": "<timestamp-in-UTC>",
        "processIds": ["", ...]
    }
}
"""
import collections
from src.Constants import Constants


class CoreStateHandler(object):
    """ Responsible for managing CoreState.json file """
    def __init__(self, dir_path, json_file_handler):
        self.dir_path = dir_path
        self.file = Constants.CORE_STATE_FILE
        self.json_file_handler = json_file_handler
        self.core_state_fields = Constants.CoreStateFields

    def read_file(self):
        """ Fetches config from CoreState.json. Returns None if no content/file found """
        core_state_json = self.json_file_handler.get_json_file_content(self.file, self.dir_path, raise_if_not_found=False)
        parent_key = self.core_state_fields.parent_key
        core_state_values = collections.namedtuple(parent_key, [self.core_state_fields.number, self.core_state_fields.action, self.core_state_fields.completed, self.core_state_fields.last_heartbeat, self.core_state_fields.process_ids])
        if core_state_json is not None:
            seq_no = self.json_file_handler.get_json_config_value_safely(core_state_json, self.core_state_fields.number, parent_key)
            action = self.json_file_handler.get_json_config_value_safely(core_state_json, self.core_state_fields.action, parent_key)
            completed = self.json_file_handler.get_json_config_value_safely(core_state_json, self.core_state_fields.completed, parent_key)
            last_heartbeat = self.json_file_handler.get_json_config_value_safely(core_state_json, self.core_state_fields.last_heartbeat, parent_key)
            process_ids = self.json_file_handler.get_json_config_value_safely(core_state_json, self.core_state_fields.process_ids, parent_key)
            return core_state_values(seq_no, action, completed, last_heartbeat, process_ids)

