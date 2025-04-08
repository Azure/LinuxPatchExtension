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

    def test_extract_version_from_os_version_nums(self):
        """ Test extract version logic on Ubuntuproclient version """
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("34"), "34")
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("34~18"), "34")
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("34.~18.04"), "34")
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("34.a+18.04.1"), "34")
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("34abc-18.04"), "34")
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("abc34~18.04"), "34")
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("abc34~18.04.123"), "34")
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("34~25.1.2-18.04.1"), "34")

        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("34.1~18.04.1"), "34.1")
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("34.13.4"), "34.13.4")
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("34.13.4~18.04.1"), "34.13.4")
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("34.13.4-ab+18.04.1"), "34.13.4")
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("34.13.4abc-18.04.1"), "34.13.4")
        self.assertEqual(self.version_comparator.extract_version_from_os_version_nums("abc.34.13.4!@abc"), "34.13.4")

    def test_linux_os_version_comparison(self):
        """ Test compare versions logic Ubuntuproclient version with existing vm version """
        test_extracted_good_version = self.version_comparator.extract_version_from_os_version_nums("34.13.4~18.04.1")  # return 34

        self.assertEqual(self.version_comparator.compare_versions(test_extracted_good_version, "34.13.4"), 0)  # equal  34.13.4 == 34.13.4
        self.assertEqual(self.version_comparator.compare_versions(test_extracted_good_version, "34.13.3"), 1)  # greater 34.13.4 > 34.13.3
        self.assertEqual(self.version_comparator.compare_versions(test_extracted_good_version, "34.13.5"), -1)  # less 34.13.4 < 34.13.5

        test_extracted_bad_version = self.version_comparator.extract_version_from_os_version_nums("abc~18.04.1")  # return ""
        self.assertEqual(self.version_comparator.compare_versions(test_extracted_bad_version, "34.13.4"), -1)  # less "" < 34.13.4


if __name__ == '__main__':
    unittest.main()
