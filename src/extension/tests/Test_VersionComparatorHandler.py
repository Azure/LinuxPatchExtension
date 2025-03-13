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

import unittest
from extension.src.VersionComparatorHandler import VersionComparatorHandler


class TestVersionComparatorHandler(unittest.TestCase):

    def setUp(self):
        self.version_comparator_handler = VersionComparatorHandler()

    def test_linux_extension_version_extract_comparator_handler(self):
        self.assertEqual(self.version_comparator_handler.extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25"), "1.2.25")
        self.assertEqual(self.version_comparator_handler.extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.250"), "1.2.250")
        self.assertEqual(self.version_comparator_handler.extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.2501"), "1.21.2501")
        self.assertEqual(self.version_comparator_handler.extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25."), "1.2.25")
        self.assertEqual(self.version_comparator_handler.extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25.."), "1.2.25")
        self.assertEqual(self.version_comparator_handler.extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25abc"), "1.2.25")
        self.assertEqual(self.version_comparator_handler.extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25.abc"), "1.2.25")
        self.assertEqual(self.version_comparator_handler.extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25+abc.123"), "1.2.25")
        self.assertEqual(self.version_comparator_handler.extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc+def.123"), "1.2.25")
        self.assertEqual(self.version_comparator_handler.extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-a.b.c"), "")

    def test_linux_extension_sort_comparator_handler(self):
        """Test sorting comparator on linux extension versions """
        unsorted_lpe_versions = [
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc+def.123",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.99",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.100",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.9",
        ]

        expected_sorted_lpe_versions = [
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.100",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.99",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.9",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc+def.123",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc"
        ]

        # validate sorted lpe versions
        self.assertEqual(self.version_comparator_handler.sort_versions_desc_order(unsorted_lpe_versions), expected_sorted_lpe_versions)

    def test_linux_os_version_extract_comparator_handler(self):
        """ Test extract version logic on Ubuntuproclient version """
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("34"), "34")
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("34~18"), "34")
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("34.~18.04"), "34")
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("34.a+18.04.1"), "34")
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("34abc-18.04"), "34")
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("abc34~18.04"), "34")
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("abc34~18.04.123"), "34")
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("34~25.1.2-18.04.1"), "34")

        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("34.1~18.04.1"), "34.1")
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("34.13.4"), "34.13.4")
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("34.13.4~18.04.1"), "34.13.4")
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("34.13.4-ab+18.04.1"), "34.13.4")
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("34.13.4abc-18.04.1"), "34.13.4")
        self.assertEqual(self.version_comparator_handler.extract_os_version_nums("abc.34.13.4!@abc"), "34.13.4")

    def test_os_version_sort_comparator_handler(self):
        """Test sorting comparator on linux os versions """
        unsorted_os_versions = [
            "32.101.~18.01",
            "32.101.15~18",
            "abc34~18.04",
            "32~18.04.01",
            "32.1~18.04.01"
        ]

        expected_sorted_os_versions = [
            "abc34~18.04",
            "32.101.15~18",
            "32.101.~18.01",
            "32.1~18.04.01",
            "32~18.04.01"
        ]

        self.assertEqual(self.version_comparator_handler.sort_versions_desc_order(unsorted_os_versions), expected_sorted_os_versions)

