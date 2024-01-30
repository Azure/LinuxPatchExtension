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

"""Mirrors all terminal output to a local file
If the log file language is set to 'Python' in Notepad++, with code as implemented below, useful collapsibility is obtained."""
import sys


class StdOutFileMirror(object):
    """Mirrors all terminal output to a local file"""

    def __init__(self, env_layer, file_logger):
        self.env_layer = env_layer
        self.terminal = sys.stdout  # preserve for recovery
        self.file_logger = file_logger
        self.encoding = 'UTF-8'
        splash = "\n,---.                        ,---.     |         |        ,-.-.                                        |    \n|---|,---,.   .,---.,---.    |---',---.|--- ,---.|---.    | | |,---.,---.,---.,---.,---.,-.-.,---.,---.|--- \n|   | .-' |   ||    |---'    |    ,---||    |    |   |    | | |,---||   |,---||   ||---'| | ||---'|   ||    \n`   ''---'`---'`    `---'    `    `---^`---'`---'`   '    ` ' '`---^`   '`---^`---|`---'` ' '`---'`   '`---'\n                                                                              `---'                         "

        if self.file_logger.log_file_handle is not None:
            sys.stdout = self
            sys.stdout.write("\n" +  str('-'*128) + splash + "\n" + str('-'*128))   # provoking an immediate failure if anything is wrong
        else:
            sys.stdout = self.terminal
            sys.stdout.write("WARNING: StdOutFileMirror - Skipping as FileLogger is not initialized")

    def write(self, message):
        self.terminal.write(message)  # enable standard job output

        if len(message.strip()) > 0:
            try:
                timestamp = self.env_layer.datetime.timestamp()
                self.file_logger.write("\n" + timestamp + "> " + message, fail_silently=False)  # also write to the file logger file
            except Exception as error:
                sys.stdout = self.terminal  # suppresses further job output mirror failures
                sys.stdout.write("WARNING: StdOutFileMirror - Error writing to log file: " + repr(error))

    def flush(self):
        pass

    def stop(self):
        sys.stdout = self.terminal
