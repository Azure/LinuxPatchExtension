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

    def test_linux_version_comparator_handler(self):
        # Test extract version logic
        self.assertEqual(self.version_comparator_handler.extract_version_nums("Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25"), "1.2.25")
        self.assertEqual(self.version_comparator_handler.extract_version_nums("Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc"), "1.2.25")
        self.assertEqual(self.version_comparator_handler.extract_version_nums("Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25+abc.123"), "1.2.25")
        self.assertEqual(self.version_comparator_handler.extract_version_nums("Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc+def.123"), "1.2.25")
        self.assertEqual(self.version_comparator_handler.extract_version_nums("Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001"), "1.21.1001")
        self.assertEqual(self.version_comparator_handler.extract_version_nums("Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100"), "1.6.100")
        self.assertEqual(self.version_comparator_handler.extract_version_nums("Microsoft.CPlat.Core.LinuxPatchExtension-1.6.99"), "1.6.99")
        self.assertEqual(self.version_comparator_handler.extract_version_nums("Microsoft.CPlat.Core.LinuxPatchExtension-1.6."), "")
        self.assertEqual(self.version_comparator_handler.extract_version_nums("Microsoft.CPlat.Core.LinuxPatchExtension-a.b.c"), "")

        # Test sort versions logic
        unsorted_path_versions = [
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc+def.123",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.6.99",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.21.100",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc",
        ]

        expected_sorted_path_versions = [
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.21.100",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.6.99",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc+def.123",
            "Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc"
        ]

        # valid versions
        self.assertEqual(self.version_comparator_handler.sort_versions_desc_order(unsorted_path_versions), expected_sorted_path_versions)
