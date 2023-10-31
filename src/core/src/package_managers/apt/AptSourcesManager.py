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
from core.src.package_managers.SourcesManager import SourcesManager


class AptSourcesManager(SourcesManager):
    """ Helps with sources list management for Apt """
    def init(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler):
        super(SourcesManager, self).__init__(env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager_name=Constants.APT)
        pass

    def function_name(self):
        pass



# https://manpages.debian.org/jessie/apt/sources.list.5.en.html#:~:text=The%20source%20list%20%2Fetc%2Fapt%2Fsources.list%20is%20designed%20to%20support,by%20an%20equivalent%20command%20from%20another%20APT%20front-end%29.