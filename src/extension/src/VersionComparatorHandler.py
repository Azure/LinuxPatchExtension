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


class VersionComparatorHandler(object):

    def extract_version_nums(self, path):
        # type (str) -> (str)
        """
        Extract the version part from a given path.
        Path	                    Extracted Version
        /var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.5/config "1.2.5"
        "abc-1.2.3-alpha"	        "1.2.3"
        "xyz-34~20.04"	            "34"
        "some-27.14-ubuntu"	        "27.14"
        "random-5.0.1+build"	    "5.0.1"
        "abc"	                    ""
        """
        # extract lpe version
        if "LinuxPatchExtension" in path:
            match = re.search(r'LinuxPatchExtension-(\d+(?:\.\d+)*)', path) # extract numbers with optional dot-separated parts
            return match.group(1).rstrip('.') if match else ""

        # extract os version
        match = re.search(r'(\d+(?:\.\d+)*)', path)  # extract numbers with optional dot-separated parts
        return match.group(1) if match else str()

    def sort_versions_desc_order(self, paths):
        # type (list[str]) -> list[str]
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
        return sorted(paths, key=self.__version_key,reverse=True)

    def __version_key(self, path):
        # type (str) -> (int)
        """ Extract version number from input and return int tuple.
        Input: "Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100"
        Return: (1.6.100)
        """
        version_numbers = self.extract_version_nums(path)

        return tuple(map(int, version_numbers.split('.'))) if version_numbers else (0, 0, 0)
