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

    def compare_versions(self, version_a, version_b):
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

    @staticmethod
    def extract_version_from_os_version_nums(os_version):
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
        version_num = re.search(r'(\d+(?:\.\d+)*)', os_version)  # extract numbers with optional dot-separated parts
        return version_num.group(1) if version_num else str()

    def __version_key(self, version_input):
        # type (str) -> (int)
        """ Extract version number from input and return int tuple.
        os version input: "34~18.04"
        Return: (34)
        """
        version_numbers = self.extract_version_from_os_version_nums(os_version=version_input)
        return tuple(map(int, version_numbers.split('.'))) if version_numbers else (0, 0, 0)

    def __parse_version(self, version_components):
        # type (str) -> [[any]]
        """ Parse the split version list into list [27][14][4] -> [[27], [14], [4]] """
        return [self.__split_version_components(x) for x in version_components.split(".")]

    @staticmethod
    def __split_version_components(version):
        # type (str) -> [any]
        """ Splits a version into numeric and non-numeric into components list: 27.13.4~18.04.1 -> [27][14][4] """
        return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', version) if x]
