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

"""Mirrors all terminal output to a local file
If the log file language is set to 'Python' in Notepad++, with code as implemented below, useful collapsibility is obtained."""
import sys
import zlib
from bootstrap.Constants import Constants


class StdOutFileMirror(object):
    """Mirrors all terminal output to a local file"""

    def __init__(self, env_layer, file_logger, capture_stdout, current_env):
        capture_stdout = capture_stdout is True and current_env == Constants.ExecEnv.PROD
        self.env_layer = env_layer
        self.terminal = sys.stdout  # preserve for recovery
        self.file_logger = file_logger
        splash = 'x\x9c\xc5Tm\x8b\xdb0\x0c\xfe\xde_!\xf2%\x0cRw\x1b\x8c\xed6\x18\x84\x83\xc1F5\n\x07\x85B87\x89\x9d\\X\xe2\\\xd3d\xac\xa3\xdco\x9fd\xe7\xada\xdfOm\\I\xd6\xa3G\x8aD\xd7\xeb\xd7\x96\xd5\n&Q\t,D\xe4\x9f<\xcfKr\x05p\xfc\x88H:\x9e\x04\xb9\xd1yg\xe0/\x88\x9fo\xa1j\xe7[\xe5\x88|"Z\x15E\x80\xdf\xd9\xf6\x0e\xb7L!dugT\xdc\x16\xb5\x89K\x08\xffv\x8d\x86\xfb\xda\x1e\xd5s\xd7j\xd8\x95q\x9b\xd5M\x05u\x96\xe9\xa60\xf9\xc4\x1e\xec\x1f)\xb3\xa5\xe1\x12q\x0f\n\xfd\xfe\xee8\xb2\x07x\xc7\x15$b\xd9%\x0be\x86\xb4\xac;\xb56T\xc3o\xa2\x8b\xdb\xf4\t06q\xae+mZ\xa8\r\xec\xf1\x0c\x1b:\x1f\x1e\x82\x91<@\xdb\x17\xabD\x19\x12\xb7c\x9b\x04\xb1\xaa\x14qs1\x07\xc4\x9f\xa7\xff\x14\xd0>\xc5\xad\x7f\x86\xac+\xcb\x0b\x14\xa6\xd5y\x13\xb7Z\xb1Z\xd3\xa5\x86\xb2\xc8tzIKM\xed\x8f\xdcaRU\xd5\tCg05\xf4\xef\x81\xa7\xf5\xcd\x9f\x95"\xfaY\xdc\x96\xe6\x84\xdb\x8a\x8d\xb2\x8d\x01\xf1\xfd\xd2\xfa\x99I+8\xeb\x94\xe6\x10@\xa3\xcb"N\xca\x8b\x18\xa8C\xbfGn\x07\xe6\x80\x92\xf7\xaf\x16\xa7\x89[\xc5\xad\x95B\x07\x16!\x86\xc2\xfd\x92\x12\xf2\xdb\xa9\xecrx\xdc\x8d\xda\xd1b\x88\x1f\x88[\x97k\xe7\x1d\xc8\xad\xbcE\xc9v:\xb4\x03\xb0-L\xf7\xc7vp.L\xaa\xe1\xfd\xdbw\x1f\x04\xdc\xcf\'9^\xdc\x89\xd9\xbaK9Wdo\x8e^\xe7q\x8f\\\x02\xe4<p\x91oJ7\x0f\x19\xbc\x8e\x7f\x13\xf1\x01W\xa0\xefU\xca7|\xb8\x0b\x90\xc7\xd1M\xa6$\x93m\x12\x1b\xe7\x90W\x0e\xa4\xc5&\xd7\x95C#:,\x12z\x88\x05[@\xe4x\x86pK\xbfyy\x89(\x0e")m\r\x11\xdfX~\xf2|\xed\xdd\xec\x11\xac\r\xf4#\xd2B\xa4\x0c\xfa:\xe9\x13]\x1d\x92\x87:\x82mb\x88l\x02\x17\xce\xed\xaf^\xfb\x0fo\xbd\xfe\x07uY;e' if current_env == Constants.ExecEnv.PROD else "x\x9c\x8b\x0e\xf6w\xf3\x8dU\x00\x91\n\x19\x89\xc5\nI\xa9\xa9y\n\x99y\x99%\x99\x899\x99U\xa9)z\x00\xb4Q\x0b="

        if self.file_logger.log_file_handle is not None and capture_stdout:
            sys.stdout = self
            sys.stdout.write(zlib.decompress(splash).decode())   # provoking an immediate failure if anything is wrong
        else:
            sys.stdout = self.terminal
            sys.stdout.write("[SOFM][Terminal-only] Stdout not captured. [FileLoggerReady={0}][CaptureStdout={1}]".format(str(self.file_logger.log_file_handle is not None),str(capture_stdout)))

    def write(self, message):
        self.terminal.write(message)  # enable standard output

        if len(message.strip()) > 0:
            try:
                timestamp = self.env_layer.datetime.timestamp()
                self.file_logger.write("\n" + timestamp + "> " + message, fail_silently=False)  # also write to the file logger file
            except Exception as error:
                sys.stdout = self.terminal  # suppresses further job output mirror failures
                sys.stdout.write("[SOFM][Terminal-only] Error writing to log file. [Error={0}]".format(repr(error)))

    def flush(self):
        pass

    def stop(self):
        sys.stdout = self.terminal

