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

from core.src.bootstrap.Constants import Constants
from core.src.package_managers.HealthManager import HealthManager


class ZypperHealthManager(HealthManager):
    """ Helps with attempting automatic environment health restoration for zypper where feasible to improve operation success rates """
    def init(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(HealthManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager_name=Constants.APT)
        pass

    def function_name(self):
        pass

    # region Handling known errors
    def try_mitigate_issues_if_any(self, command, code, out):
        """ Attempt to fix the errors occurred while executing a command. Repeat check until no issues found """
        pass

    def check_known_issues_and_attempt_fix(self, output):
        """ Checks if issue falls into known issues and attempts to mitigate """
        return True
    # endregion