# Copyright 2025 Microsoft Corporation
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
import json
import os
import unittest
from core.src.bootstrap.Constants import Constants
from core.src.package_managers import TdnfPackageManager
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.LegacyEnvLayerExtensions import LegacyEnvLayerExtensions
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestTdnfPackageManager(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.TDNF)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    # region Mocks
    def mock_do_processes_require_restart_raise_exception(self):
        raise Exception
    # endregion

    def test_do_processes_require_restart(self):
        """Unit test for tdnf package manager"""
        # Restart required
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)
        self.assertTrue(package_manager.is_reboot_pending())

        # Restart not required
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.assertFalse(package_manager.is_reboot_pending())

        # Fake exception
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        backup_do_processes_require_restart = package_manager.do_processes_require_restart
        package_manager.do_processes_require_restart = self.mock_do_processes_require_restart_raise_exception
        self.assertTrue(package_manager.is_reboot_pending())    # returns true because the safe default if a failure occurs is 'true'
        package_manager.do_processes_require_restart = backup_do_processes_require_restart

    def test_package_manager_no_updates(self):
        """Unit test for tdnf package manager with no updates"""
        # Path change
        self.runtime.set_legacy_test_type('SadPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertEqual(len(available_updates), 0)
        self.assertEqual(len(package_versions), 0)

    def test_package_manager_unaligned_updates(self):
        """Unit test for tdnf package manager with multi-line updates"""
        # Path change
        self.runtime.set_legacy_test_type('UnalignedPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertEqual(4, len(available_updates))
        self.assertEqual(4, len(package_versions))

    def test_package_manager(self):
        """Unit test for tdnf package manager"""
        self.runtime.set_legacy_test_type('HappyPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertTrue(available_updates is not None)
        self.assertTrue(package_versions is not None)
        self.assertEqual(5, len(available_updates))
        self.assertEqual(5, len(package_versions))
        self.assertEqual("azurelinux-release.noarch", available_updates[0])
        self.assertEqual("azurelinux-repos-ms-oss.noarch", available_updates[1])
        self.assertEqual("3.0-16.azl3", package_versions[0])
        self.assertEqual("3.0-3.azl3", package_versions[1])

if __name__ == '__main__':
    unittest.main()

