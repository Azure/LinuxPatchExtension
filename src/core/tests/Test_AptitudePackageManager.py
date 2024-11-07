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
from core.src.bootstrap.Constants import Constants
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.tests.Test_UbuntuProClient import MockVersionResult, MockRebootRequiredResult, MockUpdatesResult
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.LegacyEnvLayerExtensions import LegacyEnvLayerExtensions
from core.tests.library.RuntimeCompositor import RuntimeCompositor
from core.src.package_managers import AptitudePackageManager, UbuntuProClient


class TestAptitudePackageManager(unittest.TestCase):
    def setUp(self):
        self.argument_composer = ArgumentComposer().get_composed_arguments()
        self.runtime = RuntimeCompositor(self.argument_composer, True, Constants.APT)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    #region Mocks
    def mock_read_with_retry_raise_exception(self):
        raise Exception

    def mock_write_with_retry_raise_exception(self, file_path_or_handle, data, mode='a+'):
        raise Exception

    def mock_linux_distribution_to_return_ubuntu_focal(self):
        return ['Ubuntu', '20.04', 'focal']

    def mock_is_pro_working_return_true(self):
        return True

    def mock_minimum_required_python_installed_return_true(self):
        return True

    def mock_install_or_update_pro_raise_exception(self):
        raise Exception

    def mock_do_processes_require_restart_raises_exception(self):
        raise Exception

    def mock_is_reboot_pending_returns_False(self):
        return False, False

    def mock_os_path_isfile_raise_exception(self, file):
        raise Exception

    def mock_get_security_updates_return_empty_list(self):
        return [], []

    # endregion Mocks

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
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('selinux-policy.noarch', '3.13.1-102.el7_3.16', simulate=True), Constants.INSTALLED)  # needs to be fixed

    def test_is_installed_check_with_dpkg(self):
        self.runtime.set_legacy_test_type('SuccessInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # test for successfully installing a package
        self.assertEqual(package_manager.is_package_version_installed('mysql-server', '5.7.25-0ubuntu0.16.04.2'), True)
        self.assertEqual(package_manager.is_package_version_installed('mysql-client', '5.7.25-0ubuntu0.16.04.2'), False)

    def test_install_package_failure(self):
        self.runtime.set_legacy_test_type('FailInstallPath')

        package_manager = self.container.get('package_manager')
        self.runtime.status_handler.set_current_operation(Constants.INSTALLATION)
        self.assertIsNotNone(package_manager)

        # test for unsuccessfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('selinux-policy.noarch', '3.13.1-102.el7_3.16', simulate=True), Constants.FAILED)
        self.assertRaises(Exception, lambda: package_manager.invoke_package_manager('sudo apt-get -y --only-upgrade true install force-dpkg-failure'))

        # ensure that error message appears in substatus properly
        substatus_file_data = []
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            status = json.load(file_handle)
            self.assertEqual(status[0]["status"]["status"].lower(), Constants.STATUS_SUCCESS.lower())
            substatus_file_data = status[0]["status"]["substatus"][0]

        error_msg = 'Package manager on machine is not healthy. To fix, please run: sudo dpkg --configure -a'
        self.assertNotEqual(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"], None)
        self.assertTrue(error_msg in str(json.loads(substatus_file_data["formattedMessage"]["message"])["errors"]["details"]))
        self.assertEqual(substatus_file_data["name"], Constants.PATCH_INSTALLATION_SUMMARY)

    def test_reboot_always_runs_only_once_if_no_reboot_is_required(self):
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = 'IfRequired'
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        reboot_manager = runtime.reboot_manager

        # mock swap
        backup_os_path_isfile = os.path.isfile
        os.path.isfile = self.mock_os_path_isfile_raise_exception

        # reboot will happen due to exception in evaluating if it is required (defaults to true)
        runtime.status_handler.is_reboot_pending = False
        self.assertEqual(runtime.package_manager.is_reboot_pending(), True)

        # restore
        os.path.isfile = backup_os_path_isfile

    def test_install_package_only_upgrades(self):
        self.runtime.set_legacy_test_type('FailInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # test for unsuccessfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('iucode-tool', '1.5.1-1ubuntu0.1', True), Constants.PENDING)

    def test_disable_auto_os_update_with_two_patch_modes_enabled_success(self):
        package_manager = self.container.get('package_manager')
        package_manager.os_patch_configuration_settings_file_path = os.path.join(self.runtime.execution_config.config_folder, "20auto-upgrades")

        # disable with both update package lists and unattended upgrades enabled on the system
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)
        package_manager.disable_auto_os_update()
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Update-Package-Lists'] == "1")
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Unattended-Upgrade'] == "1")
        os_patch_configuration_settings = self.runtime.env_layer.file_system.read_with_retry(package_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(os_patch_configuration_settings is not None)
        self.assertTrue('APT::Periodic::Update-Package-Lists "0"' in os_patch_configuration_settings)
        self.assertTrue('APT::Periodic::Unattended-Upgrade "0"' in os_patch_configuration_settings)

    def test_disable_auto_os_update_with_one_patch_mode_enabled_success(self):
        package_manager = self.container.get('package_manager')
        package_manager.os_patch_configuration_settings_file_path = os.path.join(self.runtime.execution_config.config_folder, "20auto-upgrades")

        # disable with only one patch mode enabled on the system
        os_patch_configuration_settings = 'APT::Periodic::Unattended-Upgrade "1";\n'
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)
        package_manager.disable_auto_os_update()
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Update-Package-Lists'] == "")
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Unattended-Upgrade'] == "1")
        os_patch_configuration_settings = self.runtime.env_layer.file_system.read_with_retry(package_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(os_patch_configuration_settings is not None)
        self.assertTrue('APT::Periodic::Update-Package-Lists "0"' in os_patch_configuration_settings)
        self.assertTrue('APT::Periodic::Unattended-Upgrade "0"' in os_patch_configuration_settings)

    def test_get_current_auto_os_updates_with_no_os_patch_configuration_settings_file(self):
        # os_patch_configuration_settings_file does not exist, hence current os patch state is marked as Disabled
        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state

        self.assertTrue(package_manager.get_current_auto_os_patch_state() == Constants.AutomaticOSPatchStates.DISABLED)

        package_manager.get_current_auto_os_patch_state = self.runtime.get_current_auto_os_patch_state

    def test_disable_auto_os_update_failure(self):
        # disable with non existing log file
        package_manager = self.container.get('package_manager')

        self.assertRaises(Exception, package_manager.disable_auto_os_update)
        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertTrue(not os.path.exists(package_manager.os_patch_configuration_settings_file_path))

        # disable with existing log file
        package_manager = self.container.get('package_manager')
        package_manager.os_patch_configuration_settings_file_path = os.path.join(self.runtime.execution_config.config_folder, "20auto-upgrades")
        os_patch_mode_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, os_patch_mode_settings)
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_raise_exception
        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())

    def test_image_default_patch_mode_backup_exists(self):
        package_manager = self.container.get('package_manager')

        # valid patch mode backup
        image_default_patch_configuration_backup = {
            'APT::Periodic::Update-Package-Lists': "1",
            'APT::Periodic::Unattended-Upgrade': "1"
        }
        self.runtime.env_layer.file_system.write_with_retry(package_manager.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(image_default_patch_configuration_backup)), mode='w+')
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())
        self.assertTrue(package_manager.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup))

        # invalid mode backup
        image_default_patch_configuration_backup = '[]'
        self.runtime.env_layer.file_system.write_with_retry(package_manager.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(image_default_patch_configuration_backup)), mode='w+')
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())
        self.assertFalse(package_manager.is_image_default_patch_configuration_backup_valid(image_default_patch_configuration_backup))

    def test_image_default_patch_mode_backup_does_not_exist(self):
        package_manager = self.container.get('package_manager')

        # file does not exist
        package_manager.image_default_patch_mode_backup_path = "tests"
        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())

    def test_is_image_default_patch_mode_backup_valid_true(self):
        package_manager = self.container.get('package_manager')
        # with both valid patch mode settings
        image_default_patch_mode_backup = {
            'APT::Periodic::Update-Package-Lists': "1",
            'APT::Periodic::Unattended-Upgrade': "1"
        }
        self.assertTrue(package_manager.is_image_default_patch_configuration_backup_valid(image_default_patch_mode_backup))

    def test_is_image_default_patch_mode_backup_valid_false(self):
        package_manager = self.container.get('package_manager')
        # invalid patch mode settings
        image_default_patch_mode_backup = {
            'test': "1",
        }
        self.assertFalse(package_manager.is_image_default_patch_configuration_backup_valid(image_default_patch_mode_backup))

        # with one valid patch mode setting
        image_default_patch_mode_backup = {
            'APT::Periodic::Update-Package-Lists': "1",
            'test': "1"
        }
        self.assertFalse(package_manager.is_image_default_patch_configuration_backup_valid(image_default_patch_mode_backup))

    def test_overwrite_existing_image_default_patch_mode_backup(self):
        package_manager = self.container.get('package_manager')
        image_default_patch_configuration_backup = {
            "APT::Periodic::Update-Package-Lists": "0",
            "APT::Periodic::Unattended-Upgrade": "1"
        }
        self.runtime.env_layer.file_system.write_with_retry(package_manager.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(image_default_patch_configuration_backup)), mode='w+')
        package_manager.backup_image_default_patch_configuration_if_not_exists()
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Update-Package-Lists'] == "0")
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Unattended-Upgrade'] == "1")

    def test_backup_image_default_patch_mode_with_default_patch_mode_set(self):
        package_manager = self.container.get('package_manager')
        package_manager.os_patch_configuration_settings_file_path = os.path.join(self.runtime.execution_config.config_folder, "20auto-upgrades")

        # default system patch mode is set, write to log
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)
        package_manager.backup_image_default_patch_configuration_if_not_exists()
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Update-Package-Lists'] == "1")
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Unattended-Upgrade'] == "1")

    def test_backup_image_default_patch_mode_overwrite_backup_if_original_backup_was_invalid(self):
        package_manager = self.container.get('package_manager')
        package_manager.os_patch_configuration_settings_file_path = os.path.join(self.runtime.execution_config.config_folder, "20auto-upgrades")

        # backup file exists but the content is invalid, function should overwrite the file with valid content
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)

        existing_image_default_backup_configuration = '[]'
        self.runtime.write_to_file(package_manager.image_default_patch_configuration_backup_path, existing_image_default_backup_configuration)
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())
        self.assertFalse(package_manager.is_image_default_patch_configuration_backup_valid(existing_image_default_backup_configuration))

        package_manager.backup_image_default_patch_configuration_if_not_exists()
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Update-Package-Lists'] == "1")
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Unattended-Upgrade'] == "1")

    def test_backup_image_default_patch_mode_with_default_patch_mode_not_set(self):
        package_manager = self.container.get('package_manager')
        package_manager.os_patch_configuration_settings_file_path = os.path.join(self.runtime.execution_config.config_folder, "20auto-upgrades")
        # default system patch mode is not set, write empty values to log
        os_patch_mode_settings = ''
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, os_patch_mode_settings)
        package_manager.backup_image_default_patch_configuration_if_not_exists()
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Update-Package-Lists'] == "")
        self.assertTrue(image_default_patch_configuration_backup['APT::Periodic::Unattended-Upgrade'] == "")

    def test_backup_image_default_patch_mode_raises_exception(self):
        package_manager = self.container.get('package_manager')
        package_manager.os_patch_configuration_settings_file_path = os.path.join(self.runtime.execution_config.config_folder, "20auto-upgrades")
        # default system patch mode is set, write to log
        os_patch_mode_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, os_patch_mode_settings)
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_raise_exception
        self.assertRaises(Exception, package_manager.backup_image_default_patch_configuration_if_not_exists)

    def test_update_image_default_patch_mode(self):
        package_manager = self.container.get('package_manager')
        package_manager.os_patch_configuration_settings_file_path = os.path.join(self.runtime.execution_config.config_folder, "20auto-upgrades")

        # disable update package lists when enabled by default
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)
        package_manager.update_os_patch_configuration_sub_setting('APT::Periodic::Update-Package-Lists', "0")
        os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(package_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(os_patch_configuration_settings_file_path_read is not None)
        self.assertTrue('APT::Periodic::Update-Package-Lists "0"' in os_patch_configuration_settings_file_path_read)
        self.assertTrue('APT::Periodic::Unattended-Upgrade "1"' in os_patch_configuration_settings_file_path_read)

        # disable unattended upgrades when enabled by default
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)
        package_manager.update_os_patch_configuration_sub_setting('APT::Periodic::Unattended-Upgrade', "0")
        os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(package_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(os_patch_configuration_settings_file_path_read is not None)
        self.assertTrue('APT::Periodic::Update-Package-Lists "1"' in os_patch_configuration_settings_file_path_read)
        self.assertTrue('APT::Periodic::Unattended-Upgrade "0"' in os_patch_configuration_settings_file_path_read)

        # disable unattended upgrades when default patch mode settings file is empty
        os_patch_configuration_settings = ''
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)
        package_manager.update_os_patch_configuration_sub_setting('APT::Periodic::Unattended-Upgrade', "0")
        os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(package_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(os_patch_configuration_settings_file_path_read is not None)
        self.assertTrue('APT::Periodic::Update-Package-Lists' not in os_patch_configuration_settings_file_path_read)
        self.assertTrue('APT::Periodic::Unattended-Upgrade "0"' in os_patch_configuration_settings_file_path_read)

        # disable unattended upgrades when it does not exist in default patch mode settings file
        os_patch_configuration_settings = 'APT::Periodic::Update-Package-Lists "1";\n'
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, os_patch_configuration_settings)
        package_manager.update_os_patch_configuration_sub_setting('APT::Periodic::Unattended-Upgrade', "0")
        os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(package_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(os_patch_configuration_settings_file_path_read is not None)
        self.assertTrue('APT::Periodic::Update-Package-Lists "1"' in os_patch_configuration_settings_file_path_read)
        self.assertTrue('APT::Periodic::Unattended-Upgrade "0"' in os_patch_configuration_settings_file_path_read)

    def test_update_image_default_patch_mode_raises_exception(self):
        package_manager = self.container.get('package_manager')
        package_manager.image_default_patch_mode_file_path = os.path.join(self.runtime.execution_config.config_folder, "20auto-upgrades")
        # default system patch mode is set, write to log
        image_default_patch_mode = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n'
        self.runtime.write_to_file(package_manager.image_default_patch_mode_file_path, image_default_patch_mode)
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_raise_exception
        self.assertRaises(Exception, package_manager.update_os_patch_configuration_sub_setting)

    def test_is_reboot_pending_prerequisite_not_met_should_return_false(self):
        package_manager = self.container.get('package_manager')
        package_manager._AptitudePackageManager__pro_client_prereq_met = False

        self.assertFalse(package_manager.is_reboot_pending())

    def test_is_reboot_pending_prerequisite_met_should_return_true(self):
        reboot_mock = MockRebootRequiredResult()
        reboot_mock.mock_import_uaclient_reboot_required_module('reboot_required', 'mock_reboot_required_return_yes')
        package_manager = self.container.get('package_manager')
        package_manager._AptitudePackageManager__pro_client_prereq_met = True

        self.assertTrue(package_manager.is_reboot_pending())

        reboot_mock.mock_unimport_uaclient_reboot_required_module()

    def test_is_pro_client_prereq_met_should_return_false_for_unsupported_os_version(self):
        package_manager = self.container.get('package_manager')
        backup_envlayer_platform_linux_distribution = LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution
        backup_package_manager_ubuntu_pro_client_is_pro_working = package_manager.ubuntu_pro_client.is_pro_working
        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = self.mock_linux_distribution_to_return_ubuntu_focal
        package_manager.ubuntu_pro_client.is_pro_working = self.mock_is_pro_working_return_true

        self.assertFalse(package_manager.check_pro_client_prerequisites())

        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = backup_envlayer_platform_linux_distribution
        package_manager.ubuntu_pro_client.is_pro_working = backup_package_manager_ubuntu_pro_client_is_pro_working

    def test_is_pro_client_prereq_met_should_return_true_for_supported_os_version(self):
        package_manager = self.container.get('package_manager')
        backup_package_manager_ubuntu_pro_client_is_pro_working = package_manager.ubuntu_pro_client.is_pro_working
        package_manager.ubuntu_pro_client.is_pro_working = self.mock_is_pro_working_return_true
        backup_package_manager_is_minimum_required_python_installed = package_manager._AptitudePackageManager__is_minimum_required_python_installed
        package_manager._AptitudePackageManager__is_minimum_required_python_installed = self.mock_minimum_required_python_installed_return_true

        self.assertTrue(package_manager.check_pro_client_prerequisites())

        package_manager.ubuntu_pro_client.is_pro_working = backup_package_manager_ubuntu_pro_client_is_pro_working
        package_manager._AptitudePackageManager__is_minimum_required_python_installed = backup_package_manager_is_minimum_required_python_installed

    def test_package_manager_instance_created_even_when_exception_thrown_in_pro(self):
        package_manager = self.container.get('package_manager')
        execution_config = self.container.get('execution_config')
        backup_package_manager_ubuntu_pro_client_install_or_update_pro = UbuntuProClient.UbuntuProClient.install_or_update_pro
        UbuntuProClient.UbuntuProClient.install_or_update_pro = self.mock_install_or_update_pro_raise_exception

        obj = AptitudePackageManager.AptitudePackageManager(package_manager.env_layer, execution_config, package_manager.composite_logger, package_manager.telemetry_writer, package_manager.status_handler)

        self.assertIsNotNone(obj)
        self.assertIsNotNone(obj.ubuntu_pro_client)

        UbuntuProClient.UbuntuProClient.install_or_update_pro = backup_package_manager_ubuntu_pro_client_install_or_update_pro

    def test_get_other_updates_success(self):
        obj = MockVersionResult()
        obj.mock_import_uaclient_version_module('version', 'mock_version')
        updates_obj = MockUpdatesResult()
        updates_obj.mock_import_uaclient_update_module('updates', 'mock_update_list_with_all_update_types')
        runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type('UA_ESM_Required')

        backup_AptitudePackageManager__pro_client_prereq_met = runtime.package_manager._AptitudePackageManager__pro_client_prereq_met
        runtime.package_manager._AptitudePackageManager__pro_client_prereq_met = True

        packages, versions = runtime.package_manager.get_other_updates()
        self.assertEqual(1, len(packages))

        runtime.package_manager._AptitudePackageManager__pro_client_prereq_met = backup_AptitudePackageManager__pro_client_prereq_met
        obj.mock_unimport_uaclient_version_module()
        updates_obj.mock_unimport_uaclient_update_module()

    def test_get_other_updates_without_pro_success(self):
        runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type('UA_ESM_Required')
        backup_package_manager_get_security_updates = runtime.package_manager.get_security_updates
        runtime.package_manager.get_security_updates = self.mock_get_security_updates_return_empty_list

        packages, versions = runtime.package_manager.get_other_updates()
        self.assertEqual(1, len(packages))

        runtime.package_manager.get_security_updates = backup_package_manager_get_security_updates

    def test_set_security_esm_package_status_assessment(self):
        obj = MockVersionResult()
        obj.mock_import_uaclient_version_module('version', 'mock_version')
        updates_obj = MockUpdatesResult()
        updates_obj.mock_import_uaclient_update_module('updates', 'mock_update_list_with_all_update_types')
        runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type('UA_ESM_Required')
        backup_aptitudepackagemanager__pro_client_prereq_met = runtime.package_manager._AptitudePackageManager__pro_client_prereq_met
        runtime.package_manager._AptitudePackageManager__pro_client_prereq_met = True

        runtime.patch_assessor.start_assessment()
        status = ""
        error_set = False
        with self.runtime.env_layer.file_system.open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            status = json.load(file_handle)
            self.assertEqual(status[0]["status"]["status"].lower(), Constants.STATUS_SUCCESS.lower())
            self.assertEqual(status[0]["status"]["substatus"][0]["name"], "PatchAssessmentSummary")

        # Parse the assessment data to check if we have logged the error details for esm_required.
        assessment_data = status[0]["status"]["substatus"][0]["formattedMessage"]["message"]
        error_list = json.loads(assessment_data)["errors"]["details"]
        for error in error_list:
            if error["code"] == Constants.PatchOperationErrorCodes.UA_ESM_REQUIRED:
                error_set = True
                break
        self.assertTrue(error_set)

        runtime.package_manager._AptitudePackageManager__pro_client_prereq_met = backup_aptitudepackagemanager__pro_client_prereq_met
        obj.mock_unimport_uaclient_version_module()
        updates_obj.mock_unimport_uaclient_update_module()

    def test_is_reboot_pending_pro_client_success(self):
        reboot_mock = MockRebootRequiredResult()
        reboot_mock.mock_import_uaclient_reboot_required_module('reboot_required', 'mock_reboot_required_return_no')
        runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.APT)
        backup_AptitudePackageManager__pro_client_prereq_met = runtime.package_manager._AptitudePackageManager__pro_client_prereq_met
        runtime.package_manager._AptitudePackageManager__pro_client_prereq_met = True
        self.assertFalse(runtime.package_manager.is_reboot_pending())

        runtime.package_manager._AptitudePackageManager__pro_client_prereq_met = backup_AptitudePackageManager__pro_client_prereq_met
        reboot_mock.mock_unimport_uaclient_reboot_required_module()

    def test_is_reboot_pending_test_mismatch(self):
        reboot_mock = MockRebootRequiredResult()
        reboot_mock.mock_import_uaclient_reboot_required_module('reboot_required', 'mock_reboot_required_return_yes')
        runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.APT)
        backup__AptitudePackageManager__pro_client_prereq_met = runtime.package_manager._AptitudePackageManager__pro_client_prereq_met
        runtime.package_manager._AptitudePackageManager__pro_client_prereq_met = True

        # test should return true as we fall back to Ubuntu Pro Client api`s result.
        self.assertTrue(runtime.package_manager.is_reboot_pending())

        reboot_mock.mock_unimport_uaclient_reboot_required_module()
        runtime.package_manager._AptitudePackageManager__pro_client_prereq_met = backup__AptitudePackageManager__pro_client_prereq_met

    def test_is_reboot_pending_test_raises_exception(self):
        runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.APT)
        backup_package_manager_do_processes_require_restart = runtime.package_manager.do_processes_require_restart
        runtime.package_manager.do_processes_require_restart = self.mock_do_processes_require_restart_raises_exception
        backup_package_manager_is_reboot_pending = runtime.package_manager.ubuntu_pro_client.is_reboot_pending
        runtime.package_manager.ubuntu_pro_client.is_reboot_pending = self.mock_is_reboot_pending_returns_False
        backup__AptitudePackageManager__pro_client_prereq_met = runtime.package_manager._AptitudePackageManager__pro_client_prereq_met
        runtime.package_manager._AptitudePackageManager__pro_client_prereq_met = True

        # test returns true because, we return True if there is exception.
        self.assertTrue(runtime.package_manager.is_reboot_pending())

        runtime.package_manager.do_processes_require_restart = backup_package_manager_do_processes_require_restart
        runtime.package_manager.ubuntu_pro_client.is_reboot_pending = backup_package_manager_is_reboot_pending
        runtime.package_manager._AptitudePackageManager__pro_client_prereq_met = backup__AptitudePackageManager__pro_client_prereq_met

    def test_check_pro_client_prerequisites_should_return_false(self):
        package_manager = self.container.get('package_manager')
        backup_envlayer_platform_linux_distribution = LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution
        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = self.mock_linux_distribution_to_return_ubuntu_focal
        backup_ubuntu_pro_client_is_pro_working = package_manager.ubuntu_pro_client.is_pro_working
        package_manager.ubuntu_pro_client.is_pro_working = self.mock_is_pro_working_return_true

        self.assertFalse(package_manager.check_pro_client_prerequisites())

        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = backup_envlayer_platform_linux_distribution
        package_manager.ubuntu_pro_client.is_pro_working = backup_ubuntu_pro_client_is_pro_working

    def test_eula_accepted_for_patches(self):
        # EULA accepted in settings and commands updated accordingly
        self.runtime.execution_config.accept_package_eula = True
        package_manager_for_test = AptitudePackageManager.AptitudePackageManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.status_handler)
        self.assertTrue("ACCEPT_EULA=Y" in package_manager_for_test.single_package_upgrade_simulation_cmd)
        self.assertTrue("ACCEPT_EULA=Y" in package_manager_for_test.single_package_dependency_resolution_template)
        self.assertTrue("ACCEPT_EULA=Y" in package_manager_for_test.single_package_upgrade_cmd)

    def test_eula_not_accepted_for_patches(self):
        # EULA accepted in settings and commands updated accordingly
        self.runtime.execution_config.accept_package_eula = False
        package_manager_for_test = AptitudePackageManager.AptitudePackageManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.status_handler)
        self.assertTrue("ACCEPT_EULA=Y" not in package_manager_for_test.single_package_upgrade_simulation_cmd)
        self.assertTrue("ACCEPT_EULA=Y" not in package_manager_for_test.single_package_dependency_resolution_template)
        self.assertTrue("ACCEPT_EULA=Y" not in package_manager_for_test.single_package_upgrade_cmd)

    def test_maxpatchpublishdate_mitigation_mode(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.runtime.stop()

        # classic happy path mode
        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.CRITICAL]
        argument_composer.patches_to_include = ["AzGPS_Mitigation_Mode_No_SLA", "MaxPatchPublishDate=20250101T010203Z", "*kernel*"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        execution_config = self.runtime.container.get('execution_config')
        self.assertEqual(execution_config.max_patch_publish_date, "20250101T010203Z")
        self.assertEqual(len(execution_config.included_package_name_mask_list), 1) # inclusion list is sanitized
        self.runtime.stop()

        # retains valid inclusions while honoring mitigation mode entries
        argument_composer = ArgumentComposer()
        argument_composer.patches_to_include = ["*kernel*", "MaxPatchPublishDate=20250101T010203Z", "AzGPS_Mitigation_Mode_No_SLA"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        execution_config = self.runtime.container.get('execution_config')
        self.assertEqual(execution_config.max_patch_publish_date, "20250101T010203Z")
        self.assertEqual(len(execution_config.included_package_name_mask_list), 1)  # inclusion list is sanitized
        self.runtime.stop()

        # missing required disclaimer entry
        argument_composer = ArgumentComposer()
        argument_composer.patches_to_include = ["MaxPatchPublishDate=20250101T010203Z", "*firefox=1.1"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        execution_config = self.runtime.container.get('execution_config')
        self.assertEqual(execution_config.max_patch_publish_date, "")   # because no mitigation mode
        self.assertEqual(len(execution_config.included_package_name_mask_list), 2)  # addition is ignored for removal
        self.runtime.stop()

        # badly formatted date
        argument_composer = ArgumentComposer()
        argument_composer.patches_to_include = ["*firefox*", "MaxPatchPublishDate=20250101010203Z", "AzGPS_Mitigation_Mode_No_SLA", "*kernel*"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        execution_config = self.runtime.container.get('execution_config')
        self.assertEqual(execution_config.max_patch_publish_date, "")
        self.assertEqual(len(execution_config.included_package_name_mask_list), 4)
        self.runtime.stop()

    def test_eula_acceptance_file_read_success(self):
        self.runtime.stop()

        # Accept EULA set to true
        eula_settings = {
            "AcceptEULAForAllPatches": True,
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, True)
        runtime.stop()

        # Accept EULA set to false
        eula_settings = {
            "AcceptEULAForAllPatches": False,
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        runtime.stop()

        # Accept EULA set to true in a string i.e. 'true'
        eula_settings = {
            "AcceptEULAForAllPatches": 'true',
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, True)
        runtime.stop()

        # Accept EULA set to true in a string i.e. 'True'
        eula_settings = {
            "AcceptEULAForAllPatches": 'True',
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, True)
        runtime.stop()

        # Accept EULA set to true in a string i.e. 'False'
        eula_settings = {
            "AcceptEULAForAllPatches": 'False',
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        runtime.stop()

        # Accept EULA set to true in a string i.e. 'false'
        eula_settings = {
            "AcceptEULAForAllPatches": 'false',
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        runtime.stop()

        # Accept EULA set as '0'
        eula_settings = {
            "AcceptEULAForAllPatches": '0',
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        runtime.stop()

        # Accept EULA set as 0
        eula_settings = {
            "AcceptEULAForAllPatches": 0,
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        runtime.stop()

        # Accept EULA set as 1
        eula_settings = {
            "AcceptEULAForAllPatches": 1,
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, True)
        runtime.stop()

        # Accept EULA set as '1'
        eula_settings = {
            "AcceptEULAForAllPatches": '1',
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, True)
        runtime.stop()

    def test_eula_acceptance_file_read_when_no_data_found(self):
        self.runtime.stop()

        # EULA file does not exist
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        self.assertFalse(os.path.exists(Constants.AzGPSPaths.EULA_SETTINGS))
        runtime.stop()

        # EULA settings set to None
        eula_settings = None
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        self.assertTrue(os.path.exists(Constants.AzGPSPaths.EULA_SETTINGS))
        runtime.stop()

        # AcceptEULAForAllPatches not set in config
        eula_settings = {
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        self.assertTrue(os.path.exists(Constants.AzGPSPaths.EULA_SETTINGS))
        runtime.stop()

        # AcceptEULAForAllPatches not set to a boolean
        eula_settings = {
            "AcceptEULAForAllPatches": "test",
            "AcceptedBy": "TestSetup",
            "LastModified": "2023-08-29"
        }
        f = open(Constants.AzGPSPaths.EULA_SETTINGS, "w+")
        f.write(json.dumps(eula_settings))
        f.close()
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        container = runtime.container
        execution_config = container.get('execution_config')
        self.assertEqual(execution_config.accept_package_eula, False)
        self.assertTrue(os.path.exists(Constants.AzGPSPaths.EULA_SETTINGS))
        runtime.stop()

        # EULA not accepted for cases where file read raises an Exception
        runtime = RuntimeCompositor(self.argument_composer, True, package_manager_name=Constants.APT)
        self.backup_read_with_retry = runtime.env_layer.file_system.read_with_retry
        runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_raise_exception
        exec_config = ExecutionConfig(runtime.env_layer, runtime.composite_logger, str(self.argument_composer))
        self.assertTrue(os.path.exists(Constants.AzGPSPaths.EULA_SETTINGS))
        self.assertEqual(exec_config.accept_package_eula, False)
        runtime.stop()


if __name__ == '__main__':
    unittest.main()
