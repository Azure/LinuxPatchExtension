# Copyright 2024 Microsoft Corporation
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
import os.path
import re


class ExtVersionComparator(object):

    def sort_ext_paths_desc_order(self, ext_paths_with_versions):
        # type (list[str]) -> list[str]
        """
        Sort paths based on version numbers extracted from paths.
        Lpe input:
            ["/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.100"]
        Return:
            ["/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.100",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100"]

        Os Version input:
            ["32.101~18.01",
            "32.101.15~18",
            "34~18.04",
            "32~18.04.01",
            "32.1~18.04.01"]

        return:
            ["34~18.04",
            "32.101.15~18",
            "32.101~18.01",
            "32.1~18.04.01",
            "32~18.04.01"]
        """
        return sorted(ext_paths_with_versions, key=self.__version_key, reverse=True)

    @staticmethod
    def __extract_lpe_path_version_num(lpe_path):
        # type (str) -> str
        """
        Extract the version part from a given lpe path.
        Input	                                                                          Extracted Version
        /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25                  "1.2.25"
        /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.250                 "1.2.250"
        /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.2501               "1.21.2501"
        /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25.                 "1.2.25"
        /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25..                "1.2.25"
        /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25abc               "1.2.25"
        /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25.abc              "1.2.25"
        /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25+abc.123          "1.2.25"
        /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc+def.123      "1.2.25"
        /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-a.b.c                     ""
        """

        lpe_filename = os.path.basename(lpe_path)  # Microsoft.CPlat.Core.LinuxPatchExtension-x.x.xx
        lpe_version = re.search(r'(\d+(?:\.\d+)*)', lpe_filename)  # extract numbers with optional dot-separated parts
        return lpe_version.group(1).rstrip('.') if lpe_version else ""

    def __version_key(self, version_input):
        # type (str) -> (int)
        """ Extract version number from input and return int tuple.
        Input: "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100"
        Return: (1.6.100)

        os version input: "34~18.04"
        Return: (34)
        """
        version_numbers = self.__extract_lpe_path_version_num(lpe_path=version_input)
        return tuple(map(int, version_numbers.split('.'))) if version_numbers else (0, 0, 0)
