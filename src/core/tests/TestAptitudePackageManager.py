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
import json
import os
import unittest
from src.bootstrap.Constants import Constants
from tests.library.ArgumentComposer import ArgumentComposer
from tests.library.RuntimeCompositor import RuntimeCompositor


class TestAptitudePackageManager(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.APT)
        self.container = self.runtime.container
        self.valid_auto_os_update_settings = 'APT::Periodic::Update-Package-Lists "1";' + \
                                             'APT::Periodic::Unattended-Upgrade "1";'

    def tearDown(self):
        self.runtime.stop()

    def mock_get_current_auto_os_update_settings(self):
        return self.valid_auto_os_update_settings

    def mock_read_with_retry_raise_exception(self):
        raise Exception

    def test_package_manager_no_updates(self):
        """Unit test for aptitude package manager with no updates"""
        self.runtime.set_legacy_test_type('SadPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertEqual(len(available_updates), 0)
        self.assertEqual(len(package_versions), 0)

    def test_package_manager(self):
        """Unit test for apt package manager"""
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for get_available_update
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertEqual(len(available_updates), 3)
        self.assertEqual(len(package_versions), 3)
        self.assertEqual(available_updates[0], "python-samba")
        self.assertEqual(available_updates[1], "samba-common-bin")
        self.assertEqual(available_updates[2], "samba-libs")
        self.assertEqual(package_versions[0], "2:4.4.5+dfsg-2ubuntu5.4")
        self.assertEqual(package_versions[1], "2:4.4.5+dfsg-2ubuntu5.4")
        self.assertEqual(package_versions[2], "2:4.4.5+dfsg-2ubuntu5.4")

        # test for get_package_size
        cmd = package_manager.single_package_upgrade_cmd + "zlib1g"
        code, out = self.runtime.env_layer.run_command_output(cmd, False, False)
        size = package_manager.get_package_size(out)
        self.assertEqual(size, "51.2 kB")

        # test for all available versions of package
        package_versions = package_manager.get_all_available_versions_of_package("bash")
        self.assertEqual(len(package_versions), 3)
        self.assertEqual(package_versions[0], '4.3-14ubuntu1.3')
        self.assertEqual(package_versions[1], '4.3-14ubuntu1.2')
        self.assertEqual(package_versions[2], '4.3-14ubuntu1')

    def test_install_package_success(self):
        self.runtime.set_legacy_test_type('SuccessInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # test for successfully installing a package
        self.assertEquals(package_manager.install_update_and_dependencies('selinux-policy.noarch', '3.13.1-102.el7_3.16', simulate=True), Constants.INSTALLED)  # needs to be fixed

    def test_is_installed_check_with_dpkg(self):
        self.runtime.set_legacy_test_type('SuccessInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # test for successfully installing a package
        self.assertEquals(package_manager.is_package_version_installed('mysql-server', '5.7.25-0ubuntu0.16.04.2'), True)
        self.assertEquals(package_manager.is_package_version_installed('mysql-client', '5.7.25-0ubuntu0.16.04.2'), False)

    def test_install_package_failure(self):
        self.runtime.set_legacy_test_type('FailInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # test for unsuccessfully installing a package
        self.assertEquals(package_manager.install_update_and_dependencies('selinux-policy.noarch', '3.13.1-102.el7_3.16', simulate=True), Constants.FAILED)
        self.assertRaises(Exception, lambda: package_manager.invoke_package_manager('sudo apt-get -y --only-upgrade true install force-dpkg-failure'))

    def test_install_package_only_upgrades(self):
        self.runtime.set_legacy_test_type('FailInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # test for unsuccessfully installing a package
        self.assertEquals(package_manager.install_update_and_dependencies('iucode-tool', '1.5.1-1ubuntu0.1', simulate=True), Constants.PENDING)

    def test_get_current_auto_os_update_settings_success(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        current_auto_os_update_settings = package_manager.get_current_auto_os_update_settings()
        self.assertTrue(current_auto_os_update_settings is not None)

    def test_get_current_auto_os_update_settings_fail(self):
        package_manager = self.container.get('package_manager')

        self.runtime.set_legacy_test_type('SadPath')
        current_auto_os_update_settings = package_manager.get_current_auto_os_update_settings()
        self.assertTrue(current_auto_os_update_settings is "")

        self.runtime.set_legacy_test_type('ExceptionPath')
        self.assertRaises(Exception, package_manager.get_current_auto_os_update_settings)

    def test_disable_auto_os_update_success(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        package_manager.disable_auto_os_update()
        self.assertTrue(package_manager.image_default_patch_mode_backup_exists())
        image_default_patch_mode_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_mode_backup_path))
        self.assertTrue(image_default_patch_mode_backup is not None)
        self.assertTrue(image_default_patch_mode_backup['APT::Periodic::Update-Package-Lists'] == "1")
        self.assertTrue(image_default_patch_mode_backup['APT::Periodic::Unattended-Upgrade'] == "1")

    def test_disable_auto_os_update_failure(self):
        # disable with non existing log file
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')

        package_manager.disable_auto_os_update()
        self.assertFalse(package_manager.image_default_patch_mode_backup_exists())
        image_default_patch_mode_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_mode_backup_path))
        self.assertTrue(image_default_patch_mode_backup is not None)
        self.assertTrue(image_default_patch_mode_backup['APT::Periodic::Update-Package-Lists'] == "")
        self.assertTrue(image_default_patch_mode_backup['APT::Periodic::Unattended-Upgrade'] == "")

        # disable with existing log file
        current_auto_os_update_settings = {
            'APT::Periodic::Update-Package-Lists': "1",
            'APT::Periodic::Unattended-Upgrade': "1"
        }
        self.runtime.env_layer.file_system.write_with_retry(package_manager.image_default_patch_mode_backup_path, '{0}'.format(json.dumps(current_auto_os_update_settings)), mode='w+')
        package_manager.disable_auto_os_update()
        self.assertTrue(package_manager.image_default_patch_mode_backup_exists())
        image_default_patch_mode_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_mode_backup_path))
        self.assertTrue(image_default_patch_mode_backup is not None)
        self.assertTrue(image_default_patch_mode_backup['APT::Periodic::Update-Package-Lists'] == "1")
        self.assertTrue(image_default_patch_mode_backup['APT::Periodic::Unattended-Upgrade'] == "1")

    def test_disable_auto_os_update_exception(self):
        # disable cmd raises exception
        self.runtime.set_legacy_test_type('ExceptionPath')
        package_manager = self.container.get('package_manager')

        get_current_auto_os_update_settings_backup = package_manager.get_current_auto_os_update_settings
        package_manager.get_current_auto_os_update_settings = self.mock_get_current_auto_os_update_settings
        package_manager.disable_auto_os_update()
        self.assertTrue(package_manager.image_default_patch_mode_backup_exists())
        image_default_patch_mode_backup = self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_mode_backup_path)
        self.assertTrue(image_default_patch_mode_backup is not None)

        package_manager.get_current_auto_os_update_settings = get_current_auto_os_update_settings_backup

    def test_image_default_patch_mode_backup_exists(self):
        package_manager = self.container.get('package_manager')

        # log with valid auto OS update settings exists
        # current_auto_os_update_settings = self.valid_auto_os_update_settings
        current_auto_os_update_settings = {
            'APT::Periodic::Update-Package-Lists': "1",
            'APT::Periodic::Unattended-Upgrade': "1"
        }
        self.runtime.env_layer.file_system.write_with_retry(package_manager.image_default_patch_mode_backup_path, '{0}'.format(json.dumps(current_auto_os_update_settings)), mode='w+')
        self.assertTrue(package_manager.image_default_patch_mode_backup_exists())

        # log with invalid or no auto OS update settings exists
        current_auto_os_update_settings = '[]'
        self.runtime.env_layer.file_system.write_with_retry(package_manager.image_default_patch_mode_backup_path, '[{0}]'.format(current_auto_os_update_settings), mode='w+')
        self.assertFalse(package_manager.image_default_patch_mode_backup_exists())

    def test_image_default_patch_mode_backup_does_not_exist(self):
        package_manager = self.container.get('package_manager')
        read_with_retry_backup = self.runtime.env_layer.file_system.read_with_retry
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_raise_exception

        # ensure valid log file exists
        current_auto_os_update_settings = self.valid_auto_os_update_settings
        self.runtime.env_layer.file_system.write_with_retry(package_manager.image_default_patch_mode_backup_path, '[{0}]'.format(current_auto_os_update_settings), mode='w+')
        self.assertFalse(package_manager.image_default_patch_mode_backup_exists())
        self.runtime.env_layer.file_system.read_with_retry = read_with_retry_backup

        # file does not exist
        package_manager.image_default_patch_mode_backup_path = "tests"
        self.assertFalse(package_manager.image_default_patch_mode_backup_exists())

    def test_overwrite_existing_image_default_patch_mode_backup(self):
        package_manager = self.container.get('package_manager')
        current_auto_os_update_settings = self.valid_auto_os_update_settings
        self.runtime.env_layer.file_system.write_with_retry(package_manager.image_default_patch_mode_backup_path, '[{0}]'.format(current_auto_os_update_settings), mode='w+')
        package_manager.backup_image_default_patch_mode()
        image_default_patch_mode_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_mode_backup_path))
        self.assertTrue(image_default_patch_mode_backup is not None)
        self.assertTrue(image_default_patch_mode_backup['APT::Periodic::Update-Package-Lists'] == "1")
        self.assertTrue(image_default_patch_mode_backup['APT::Periodic::Unattended-Upgrade'] == "1")

    def test_backup_image_default_patch_mode(self):
        package_manager = self.container.get('package_manager')

        # current_auto_os_update_settings is None, nothing logged
        self.runtime.set_legacy_test_type('ExceptionPath')
        self.assertRaises(Exception, package_manager.backup_image_default_patch_mode)
        self.assertFalse(os.path.exists(package_manager.image_default_patch_mode_backup_path))

        # current_auto_os_update_settings not None, write to log
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager.backup_image_default_patch_mode()
        image_default_patch_mode_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_mode_backup_path))
        self.assertTrue(image_default_patch_mode_backup is not None)
        self.assertTrue(image_default_patch_mode_backup['APT::Periodic::Update-Package-Lists'] == "1")
        self.assertTrue(image_default_patch_mode_backup['APT::Periodic::Unattended-Upgrade'] == "1")


if __name__ == '__main__':
    unittest.main()
