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
import re


class VersionComparator(object):

    def compare_version_nums(self, version_a, version_b):
        # type (str, str) -> int
        """ Compare two versions with handling numeric and string parts, return -1 (less), +1 (greater), 0 (equal) """

        parse_version_a = self.__parse_version(version_a)
        parse_version_b = self.__parse_version(version_b)

        for v1, v2 in zip(parse_version_a, parse_version_b):
            for sub_v1, sub_v2 in zip(v1, v2):
                if sub_v1 < sub_v2:
                    return -1  # less
                elif sub_v1 > sub_v2:
                    return 1  # greater

        # If equal 27.13.4 vs 27.13.4, return 0
        return (len(parse_version_a) > len(parse_version_b)) - (len(parse_version_a) < len(parse_version_b))

    def extract_lpe_path_version_num(self, lpe_path):
        # type (str) -> str
        """
        Extract the version part from a given lpe path.
        Input	                                   Extracted Version
        LinuxPatchExtension-1.2.25                  "1.2.25"
        LinuxPatchExtension-1.2.250                 "1.2.250"
        LinuxPatchExtension-1.21.2501               "1.21.2501"
        LinuxPatchExtension-1.2.25.                 "1.2.25"
        LinuxPatchExtension-1.2.25..                "1.2.25"
        LinuxPatchExtension-1.2.25abc               "1.2.25"
        LinuxPatchExtension-1.2.25.abc              "1.2.25"
        LinuxPatchExtension-1.2.25+abc.123          "1.2.25"
        LinuxPatchExtension-1.2.25-abc+def.123      "1.2.25"
        LinuxPatchExtension-a.b.c                     ""
        """
        match = re.search(r'LinuxPatchExtension-(\d+(?:\.\d+)*)', lpe_path)  # extract numbers with optional dot-separated parts
        return match.group(1).rstrip('.') if match else ""

    def extract_os_version_nums(self, os_version):
        # type (str) -> str
        """
        Extract the version part from a given os version.
        Input os version	                        Extracted Version
        34                                          34
        34~18                                       34
        34.~18.04                                   34
        34.a+18.04.1                                34
        34abc-18.04                                 34
        abc34~18.04                                 34
        abc34~18.04.123                             34
        34~25.1.2-18.04.1                           34
        34.1~18.04.1                                34.1
        34.13.4                                     34.13.4
        34.13.4~18.04.1                             34.13.4
        34.13.4-ab+18.04.1                          34.13.4
        34.13.4abc-18.04.1                          34.13.4
        abc.34.13.4!@abc                            34.13.4
        """
        match = re.search(r'(\d+(?:\.\d+)*)', os_version)  # extract numbers with optional dot-separated parts
        return match.group(1) if match else str()

    def sort_versions_desc_order(self, paths):
        # type (list[str]) -> list[str]
        """
        Sort paths based on version numbers extracted from paths.
        Lpe input:
            ["Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.21.100"]
        Return:
            ["Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.21.100",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100"]

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
        return sorted(paths, key=self.__version_key, reverse=True)

    def __version_key(self, path):
        # type (str) -> (int)
        """ Extract version number from input and return int tuple.
        Lpe input: "Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100"
        Return: (1.6.100)

        os version input: "34~18.04"
        Return: (34)
        """
        if "LinuxPatchExtension" in path:
            version_numbers = self.extract_lpe_path_version_num(lpe_path = path)
        else:
            version_numbers = self.extract_os_version_nums(os_version=path)

        return tuple(map(int, version_numbers.split('.'))) if version_numbers else (0, 0, 0)

    def __split_version_components(self, version):
        # type (str) -> [any]
        """ Split a version into numeric and non-numeric into components list: 27.13.4~18.04.1 -> [27][14][4]"""
        return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', version) if x]

    def __parse_version(self, version_components):
        # type (str) -> [[any]]
        """ Parse the split version list into list [27][14][4] -> [[27], [14], [4]]"""
        return [self.__split_version_components(x) for x in version_components.split(".")]


