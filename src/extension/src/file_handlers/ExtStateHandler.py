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

import collections
from extension.src.Constants import Constants


class ExtStateHandler(object):
    """ Responsible for managing ExtState.json file """
    def __init__(self, dir_path, utility, json_file_handler):
        self.dir_path = dir_path
        self.file = Constants.EXT_STATE_FILE
        self.utility = utility
        self.json_file_handler = json_file_handler
        self.ext_fields = Constants.ExtStateFields

    def create_file(self, sequence_number, operation, prev_patch_max_end_time):
        """ Creates ExtState.json file using the config provided in Handler Configuration  """
        parent_key = self.ext_fields.ext_seq
        ext_state = {parent_key: {}}
        ext_state[parent_key][self.ext_fields.ext_seq_number] = sequence_number
        ext_state[parent_key][self.ext_fields.ext_seq_achieve_enable_by] = self.utility.get_str_from_datetime(prev_patch_max_end_time)
        ext_state[parent_key][self.ext_fields.ext_seq_operation] = operation
        self.json_file_handler.write_to_json_file(self.dir_path, self.file, ext_state)

    def read_file(self):
        """ Returns the config values in the file """
        parent_key = self.ext_fields.ext_seq
        ext_state_values = collections.namedtuple(parent_key, [self.ext_fields.ext_seq_number, self.ext_fields.ext_seq_achieve_enable_by, self.ext_fields.ext_seq_operation])
        seq_no = None
        achieve_enable_by = None
        operation_type = None
        ext_state_json = self.json_file_handler.get_json_file_content(self.file, self.dir_path, raise_if_not_found=False)
        if ext_state_json is not None:
            seq_no = self.json_file_handler.get_json_config_value_safely(ext_state_json, self.ext_fields.ext_seq_number, parent_key)
            achieve_enable_by = self.json_file_handler.get_json_config_value_safely(ext_state_json, self.ext_fields.ext_seq_achieve_enable_by, parent_key)
            operation_type = self.json_file_handler.get_json_config_value_safely(ext_state_json, self.ext_fields.ext_seq_operation, parent_key)
        return ext_state_values(seq_no, achieve_enable_by, operation_type)
