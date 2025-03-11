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

from core.src.core_logic.VersionComparator import VersionComparator


class TestVersionComparator(unittest.TestCase):

    def setUp(self):
        self.version_comparator = VersionComparator()

    def test_linux_version_comparator(self):
        # Test extract version logic on Extension package

        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25"), "1.2.25")
        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc"), "1.2.25")
        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25+abc.123"), "1.2.25")
        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc+def.123"), "1.2.25")
        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001"), "1.21.1001")
        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100"), "1.6.100")
        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-1.6.99"), "1.6.99")
        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-1.6"), "1.6")
        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-1.6."), "1.6")
        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-1.6.."), "1.6")
        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-1.6.abc"), "1.6")
        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-1.6abc"), "1.6")
        self.assertEqual(self.version_comparator.extract_version_nums("Users\Smith~123\AppData\tmp5a42j2ua\Microsoft.CPlat.Core.LinuxPatchExtension-a.b.c"), "")

        # Test extract version logic on Ubuntuproclient version
        self.assertEqual(self.version_comparator.extract_version_nums("27.~18.04.1"), "27")
        self.assertEqual(self.version_comparator.extract_version_nums("27.a+18.04.1"), "27")
        self.assertEqual(self.version_comparator.extract_version_nums("27abc-20.04"), "27")
        self.assertEqual(self.version_comparator.extract_version_nums("27~abc-20"), "27")
        self.assertEqual(self.version_comparator.extract_version_nums("27~25.1.2-18.04.1"), "27")

        self.assertEqual(self.version_comparator.extract_version_nums("27.1.~18.04.1"), "27.1")
        self.assertEqual(self.version_comparator.extract_version_nums("27.1.a+18.04.1"), "27.1")
        self.assertEqual(self.version_comparator.extract_version_nums("27.1abc-20.04"), "27.1")
        self.assertEqual(self.version_comparator.extract_version_nums("27.1!abc-20"), "27.1")

        self.assertEqual(self.version_comparator.extract_version_nums("27.13.4"), "27.13.4")
        self.assertEqual(self.version_comparator.extract_version_nums("27.13.4~18.04.1"), "27.13.4")
        self.assertEqual(self.version_comparator.extract_version_nums("27.13.4-ab+18.04.1"), "27.13.4")
        self.assertEqual(self.version_comparator.extract_version_nums("27.13.4abc-18.04.1"), "27.13.4")
        self.assertEqual(self.version_comparator.extract_version_nums("27.13.4!@abc"), "27.13.4")


        # Test compare versions logic Ubuntuproclient version
        test_extracted_v1 = self.version_comparator.extract_version_nums("27.13.4~18.04.1")
        test_extracted_v2 = self.version_comparator.extract_version_nums("27.13.4!27.1.2.3-ab+18.04.1")
        test_extracted_v3 = self.version_comparator.extract_version_nums("27.13.4~25.6aa#@bc")
        self.assertEqual(self.version_comparator.compare_version_nums(test_extracted_v1, "27.13.4"), 0) # equal
        self.assertEqual(self.version_comparator.compare_version_nums(test_extracted_v2, "27.13.3"), 1) # greater
        self.assertEqual(self.version_comparator.compare_version_nums(test_extracted_v3, "27.13.5"), -1) # less

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
        self.assertEqual(self.version_comparator.sort_versions_desc_order(unsorted_path_versions), expected_sorted_path_versions)


if __name__ == '__main__':
    unittest.main()

