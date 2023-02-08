# Copyright 2023 Microsoft Corporation
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

"""The is Ubuntu pro client implementation"""


class UbuntuProClient:
    def __init__(self, env_layer, composite_logger):
        self.env_layer = env_layer
        self.composite_logger = composite_logger

    def install_or_update_pro(self):
        """install/update pro(ubuntu-advantage-tools) to the latest version only if python3 is already installed."""
        pass

    def is_pro_working(self):
        """check if pro version api returns the version without any errors/warnings."""
        return False

    def get_security_updates(self):
        pass

    def get_all_updates(self):
        pass

    def get_other_updates(self):
        pass

    def is_reboot_pending(self):
        """query pro api to get the reboot status"""
        return True, False
