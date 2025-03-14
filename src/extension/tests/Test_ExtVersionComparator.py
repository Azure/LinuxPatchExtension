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
from extension.src.ExtVersionComparator import ExtVersionComparator


class TestVersionComparator(unittest.TestCase):

    def setUp(self):
        self.ext_version_comparator = ExtVersionComparator()

    def test_linux_extension_version_extract_comparator(self):
        self.assertEqual(self.ext_version_comparator._ExtVersionComparator__extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25"), "1.2.25")
        self.assertEqual(self.ext_version_comparator._ExtVersionComparator__extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.250"), "1.2.250")
        self.assertEqual(self.ext_version_comparator._ExtVersionComparator__extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.2501"), "1.21.2501")
        self.assertEqual(self.ext_version_comparator._ExtVersionComparator__extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25."), "1.2.25")
        self.assertEqual(self.ext_version_comparator._ExtVersionComparator__extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25.."), "1.2.25")
        self.assertEqual(self.ext_version_comparator._ExtVersionComparator__extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25abc"), "1.2.25")
        self.assertEqual(self.ext_version_comparator._ExtVersionComparator__extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25.abc"), "1.2.25")
        self.assertEqual(self.ext_version_comparator._ExtVersionComparator__extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25+abc.123"), "1.2.25")
        self.assertEqual(self.ext_version_comparator._ExtVersionComparator__extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc+def.123"), "1.2.25")
        self.assertEqual(self.ext_version_comparator._ExtVersionComparator__extract_lpe_path_version_num("/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-a.b.c"), "")

    def test_linux_extension_sort_comparator(self):
        """Test sorting comparator on linux extension versions """
        unsorted_lpe_versions = [
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc+def.123",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.99",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.100",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1000",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.99",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.9",
        ]

        expected_sorted_lpe_versions = [
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1000",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.100",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.21.99",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.99",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.9",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc+def.123",
            "/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc"
        ]

        # validate sorted lpe versions
        self.assertEqual(self.ext_version_comparator.sort_ext_paths_desc_order(unsorted_lpe_versions), expected_sorted_lpe_versions)
