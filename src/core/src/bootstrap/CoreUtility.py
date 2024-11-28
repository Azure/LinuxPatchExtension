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
import re


class CoreUtility(object):

    @staticmethod
    def compare_version(version_a, version_b):
        """ Compare two versions with handling numeric and string parts, return -1 (less), +1 (greater), 0 (equal) """

        def split_version_components(version):
            """ Split a version into numeric and non-numeric into components list: 27.13.4~18.04.1 -> [27][14][4]"""
            #return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', version) if x]
            return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', version) if x]

        def parse_version(version_components):
            """ Parse the split version list into list [27][14][4] -> [[27], [14], [4]]"""
            return [split_version_components(x) for x in version_components.split(".")]

        parse_version_a = parse_version(version_a)
        parse_version_b = parse_version(version_b)

        for v1, v2 in zip(parse_version_a, parse_version_b):
            for sub_v1, sub_v2 in zip(v1, v2):
                if sub_v1 < sub_v2:
                    return -1 # less
                elif sub_v1 > sub_v2:
                    return 1  # greater

        # If equal 27.13.4 vs 27.13.4, return 0
        return (len(parse_version_a) > len(parse_version_b)) - (len(parse_version_a) - len(parse_version_b))

    @staticmethod
    def extract_version(path):
        """
        Extract the version part from a given path.
        Input: /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.5/config
        Return: 1.2.5
        """
        match = re.search(r'([\d]+\.[\d]+\.[\d]+)', path)
        return match.group(1) if match else ""

    @staticmethod
    def sort_versions(paths):
        """
        Sort paths based on version numbers extracted from paths.
        Input:
            ["Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.21.100"]
        Return:
            ["Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.21.100",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100"]
        """

        def version_key(path):
            version_numbers = CoreUtility.extract_version(path)
            return tuple(map(int, version_numbers.split('.'))) if version_numbers else (0, 0, 0)

        return sorted(paths, key=version_key, reverse=True)



