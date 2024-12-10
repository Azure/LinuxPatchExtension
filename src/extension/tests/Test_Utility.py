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

import os
import shutil
import tempfile
import unittest
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestUtility(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.runtime = RuntimeComposer()
        self.utility = self.runtime.utility

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def mock_os_remove_to_return_exception(self, path):
        raise Exception

    def test_delete_file_success(self):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file_name = "test.json"
        file_path = os.path.join(test_dir, file_name)
        # create a file
        self.runtime.create_temp_file(test_dir, file_name, content=None)
        # delete file
        self.utility.delete_file(test_dir, "test.json")
        # once the file is deleted, parent directory is empty
        self.assertTrue(len(os.listdir(test_dir)) == 0)
        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_delete_file_failure(self):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()

        # FileNotFound
        self.assertRaises(Exception, self.utility.delete_file, test_dir, "test1.json")

        # delete on a directory
        file_path = os.path.join(test_dir, "test")
        # create a directory
        os.makedirs(file_path)
        self.assertRaises(Exception, self.utility.delete_file, test_dir, "test")

        # delete file
        file_name = "test.json"
        # create a file
        self.runtime.create_temp_file(test_dir, file_name, content=None)
        os_remove_backup = os.remove
        os.remove = self.mock_os_remove_to_return_exception
        self.assertRaises(Exception, self.utility.delete_file, test_dir, "test.json")
        os.remove = os_remove_backup

        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_extract_sorted_versions(self):
        # Test extract version logic
        self.assertEqual(self.utility.extract_version("Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25"), "1.2.25")
        self.assertEqual(self.utility.extract_version("Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc"), "1.2.25")
        self.assertEqual(self.utility.extract_version("Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25+abc.123"), "1.2.25")
        self.assertEqual(self.utility.extract_version("Microsoft.CPlat.Core.LinuxPatchExtension-1.2.25-abc+def.123"),"1.2.25")
        self.assertEqual(self.utility.extract_version("Microsoft.CPlat.Core.LinuxPatchExtension-1.21.1001"), "1.21.1001")
        self.assertEqual(self.utility.extract_version("Microsoft.CPlat.Core.LinuxPatchExtension-1.6.100"), "1.6.100")
        self.assertEqual(self.utility.extract_version("Microsoft.CPlat.Core.LinuxPatchExtension-1.6.99"), "1.6.99")
        self.assertEqual(self.utility.extract_version("Microsoft.CPlat.Core.LinuxPatchExtension-1.6."), "")
        self.assertEqual(self.utility.extract_version("Microsoft.CPlat.Core.LinuxPatchExtension-a.b.c"), "")

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
        self.assertEqual(self.utility.sort_versions_desc_order(unsorted_path_versions), expected_sorted_path_versions)


