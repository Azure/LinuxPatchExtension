# Copyright 2020 Microsoft Corporation
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

class VirtualTerminal(object):
    class TerminalColors(object):
        SUCCESS = '\033[92m'
        WARNING = '\033[93m'
        ERROR = '\033[91m'
        HIGHLIGHT = '\033[95m'
        LOWLIGHT = '\033[96m'
        DARK = '\033[0;94m'
        RESET = '\033[0m'

    def __init__(self, enable_virtual_terminal=True):
        self.enabled = True if enable_virtual_terminal else False  # forcing boolean

    def print_success(self, message):
        if self.enabled:
            print(self.TerminalColors.SUCCESS + message + self.TerminalColors.RESET)
        else:
            print(message)

    def print_warning(self, message):
        if self.enabled:
            print(self.TerminalColors.WARNING + message + self.TerminalColors.RESET)
        else:
            print(message)

    def print_error(self, message):
        if self.enabled:
            print(self.TerminalColors.ERROR + message + self.TerminalColors.RESET)
        else:
            print(message)

    def print_highlight(self, message):
        if self.enabled:
            print(self.TerminalColors.HIGHLIGHT + message + self.TerminalColors.RESET)
        else:
            print(message)

    def print_lowlight(self, message):
        if self.enabled:
            print(self.TerminalColors.LOWLIGHT + message + self.TerminalColors.RESET)
        else:
            print(message)

    def print_dark(self, message):
        if self.enabled:
            print(self.TerminalColors.DARK + message + self.TerminalColors.RESET)
        else:
            print(message)
