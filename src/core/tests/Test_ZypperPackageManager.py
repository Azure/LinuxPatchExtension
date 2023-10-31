# Copyright 2020 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
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
import tempfile
import shutil
from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestZypperPackageManager(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.ZYPPER)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    #region Mocks
    def mock_read_with_retry_has_zypper_lock_var_5(self, file_path_or_handle, raise_if_not_found=True):
        return "ZYPP_LOCK_TIMEOUT=5"

    def mock_read_with_retry_has_zypper_lock_var_10(self, file_path_or_handle, raise_if_not_found=True):
        return "ZYPP_LOCK_TIMEOUT=10"

    def mock_read_with_retry_has_zypper_lock_var_10_multiline(self, file_path_or_handle, raise_if_not_found=True):
        return "TEST=5\nTEST2=12\nZYPP_LOCK_TIMEOUT=10\nTEST3=93832\n\n"

    def mock_read_with_retry_not_has_zypper_lock_multiline(self, file_path_or_handle, raise_if_not_found=True):
        return "TEST=5\nTEST2=12\nTEST3=93832"

    def mock_read_with_retry_has_zypper_lock_var_10_wrong_format(self, file_path_or_handle, raise_if_not_found=True):
        return "ZYPP_LOCK_TIMEOUT==10"

    def mock_read_with_retry_not_has_zypper_lock_var(self, file_path_or_handle, raise_if_not_found=True):
        return "ENVVAR=50"

    def mock_read_with_retry_raises_exception(self, file_path_or_handle, raise_if_not_found=True):
        raise Exception

    def mock_read_with_retry_returns_none(self, file_path_or_handle, raise_if_not_found=True):
        return None

    def mock_write_with_retry_valid(self, file_path_or_handle, data, mode='a+'):
        return

    def mock_write_with_retry_raises_exception(self, file_path_or_handle, data, mode='a+'):
        raise Exception

    def mock_write_with_retry_assert_not_exists(self, file_path_or_handle, data, mode='a+'):
        self.assertEqual(data.find("ZYPP_LOCK_TIMEOUT"), -1)

    def mock_write_with_retry_assert_is_5(self, file_path_or_handle, data, mode='a+'):
        self.assertNotEqual(data.find("ZYPP_LOCK_TIMEOUT=5"), -1)

    def mock_do_processes_require_restart_raise_exception(self):
        raise Exception

    def mock_do_processes_require_restart(self):
        raise Exception
    #endregion Mocks

    def test_package_manager_no_updates(self):
        """Unit test for zypper package manager with no updates"""
        # Path change
        self.runtime.set_legacy_test_type('SadPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertEqual(len(available_updates), 0)
        self.assertEqual(len(package_versions), 0)

    def test_package_manager(self):
        """Unit test for zypper package manager"""
        self.runtime.set_legacy_test_type('HappyPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for get_available_updates
        # legacy_test_type ='Happy Path'
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(available_updates), 3)
        self.assertEqual(len(package_versions), 3)
        self.assertEqual(available_updates[0], "kernel-default")
        self.assertEqual(available_updates[1], "libgcc")
        self.assertEqual(available_updates[2], "libgoa-1_0-0")
        self.assertEqual(package_versions[0], "4.4.49-92.11.1")
        self.assertEqual(package_versions[1], "5.60.7-8.1")
        self.assertEqual(package_versions[2], "3.20.5-9.6")

        # test for get_available_updates with security classification
        # legacy_test_type ='Happy Path'
        self.runtime.stop()
        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.SECURITY]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        self.container = self.runtime.container
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(available_updates), 1)
        self.assertEqual(len(package_versions), 1)

        # test for get_available_updates with other classification
        # legacy_test_type ='Happy Path'
        self.runtime.stop()
        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.OTHER]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        self.container = self.runtime.container
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(available_updates), 1)
        self.assertEqual(len(package_versions), 1)

        # test for get_package_size
        cmd = package_manager.single_package_upgrade_cmd + "sudo"
        code, out = self.runtime.env_layer.run_command_output(cmd, False, False)
        size = package_manager.get_package_size(out)
        self.assertEqual(size, "810.9 KiB")

        # test for get_dependent_list
        # legacy_test_type ='Happy Path'
        dependent_list = package_manager.get_dependent_list(["man"])
        self.assertIsNotNone(dependent_list)
        self.assertEqual(len(dependent_list), 16)

        self.runtime.stop()
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.ZYPPER)
        self.container = self.runtime.container
        self.runtime.set_legacy_test_type('ExceptionPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for get_available_updates
        # legacy_test_type ='Exception Path'
        try:
            package_manager.get_available_updates(package_filter)
        except Exception as exception:
            self.assertTrue(str(exception))
        else:
            self.assertFalse(1 != 2, 'Exception did not occur and test failed.')

        # test for get_dependent_list
        # legacy_test_type ='Exception Path'
        try:
            package_manager.get_dependent_list(["man"])
        except Exception as exception:
            self.assertTrue(str(exception))
        else:
            self.assertFalse(1 != 2, 'Exception did not occur and test failed.')

    def test_do_processes_require_restart(self):
        # Restart required
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.assertTrue(package_manager.is_reboot_pending())

        # Restart not required
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.assertFalse(package_manager.is_reboot_pending())

        # Fake exception
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        backup_do_processes_require_restart = package_manager.do_processes_require_restart
        package_manager.do_processes_require_restart = self.mock_do_processes_require_restart
        self.assertTrue(package_manager.is_reboot_pending())    # returns true because the safe default if a failure occurs is 'true'
        package_manager.do_processes_require_restart = backup_do_processes_require_restart

    def test_get_all_available_versions_of_package(self):
        self.runtime.set_legacy_test_type('HappyPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        package_versions = package_manager.get_all_available_versions_of_package("bash")
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(package_versions), 2)
        self.assertEqual(package_versions[0], '4.3-83.5.2')
        self.assertEqual(package_versions[1], '4.3-82.1')

    def test_install_package_success(self):
        self.runtime.set_legacy_test_type('HappyPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # test for successfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('selinux-policy', '3.13.1-102.el7_3.16', simulate=True), Constants.PackageStatus.INSTALLED)

    def test_install_package_failure(self):
        self.runtime.set_legacy_test_type('FailInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # test for unsuccessfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('selinux-policy.noarch', '3.13.1-102.el7_3.16', simulate=True), Constants.PackageStatus.FAILED)

    def test_get_process_tree_from_package_manager_output_success(self):
        self.runtime.set_legacy_test_type('HappyPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # Create example package manager message and include test pid
        package_manager_output = 'Output from package manager: | System management is locked by the application with pid 7914 (/usr/bin/zypper).'

        # Test to make sure a valid string was returned with process information
        self.assertIsNotNone(package_manager.get_process_tree_from_pid_in_output(package_manager_output))

    def test_get_process_tree_from_package_manager_output_failure_nonexistent_process(self):
        self.runtime.set_legacy_test_type('HappyPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # Create example package manager message and include pid that isn't expected in the output
        package_manager_output = 'Output from package manager: | System management is locked by the application with pid 9999 (/usr/bin/zypper).'

        # Test to make sure nothing was returned from an invalid process
        self.assertIsNone(package_manager.get_process_tree_from_pid_in_output(package_manager_output))

    def test_get_process_tree_from_package_manager_output_failure_no_pid(self):
        self.runtime.set_legacy_test_type('HappyPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # Create example package manager message
        package_manager_output = 'Example error message without a valid pid.'

        # Test to make sure nothing was returned from an error message that doesn't contain a pid
        self.assertIsNone(package_manager.get_process_tree_from_pid_in_output(package_manager_output))

    def test_get_process_tree_from_package_manager_output_failure_cmd_error_code(self):
        self.runtime.set_legacy_test_type('SadPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # Create example package manager message
        package_manager_output = 'Output from package manager: | System management is locked by the application with pid 7914 (/usr/bin/zypper).'

        # Test to make sure nothing was returned from a non-zero command output code
        self.assertIsNone(package_manager.get_process_tree_from_pid_in_output(package_manager_output))

    def test_get_process_tree_from_package_manager_output_failure_cmd_empty_output(self):
        self.runtime.set_legacy_test_type('UnalignedPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # Create example package manager message
        package_manager_output = 'Output from package manager: | System management is locked by the application with pid 7914 (/usr/bin/zypper).'

        # Test to make sure nothing was returned from an empty string from the command output
        self.assertIsNone(package_manager.get_process_tree_from_pid_in_output(package_manager_output))

    def test_env_var_set_get(self):
        zypp_lock_timeout_var_name = "ZYPP_LOCK_TIMEOUT"

        self.temp_dir = tempfile.mkdtemp()
        self.temp_env_file = self.temp_dir + "/" + "mockEnv"
        open(self.temp_env_file, 'w+').close() # create temp file
        self.runtime.env_layer.etc_environment_file_path = self.temp_env_file
        write_with_retry_backup = self.runtime.env_layer.file_system.write_with_retry

        def write_with_retry_fail(file_path_or_handle, data, mode='a+'):
            self.runtime.env_layer.file_system.open = lambda file_path, mode, raise_if_not_found: None
            write_with_retry_backup(file_path_or_handle, data, mode='a+')

        self.runtime.env_layer.file_system.write_with_retry = write_with_retry_fail
        self.assertRaises(Exception, self.runtime.env_layer.set_env_var(zypp_lock_timeout_var_name, "5"))
        self.runtime.env_layer.file_system.write_with_retry = write_with_retry_backup

        # normal case without preexisting var
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_not_has_zypper_lock_var
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_valid

        self.assertIsNone(self.runtime.env_layer.get_env_var(zypp_lock_timeout_var_name))
        self.runtime.env_layer.set_env_var(zypp_lock_timeout_var_name, 5)
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_has_zypper_lock_var_5
        self.runtime.env_layer.set_env_var(zypp_lock_timeout_var_name, None)
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_not_has_zypper_lock_var
        self.assertIsNone(self.runtime.env_layer.get_env_var(zypp_lock_timeout_var_name))

        # now with preexisting var
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_has_zypper_lock_var_5
        self.assertEqual(self.runtime.env_layer.get_env_var(zypp_lock_timeout_var_name), "5")
        self.runtime.env_layer.set_env_var(zypp_lock_timeout_var_name, 10)
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_has_zypper_lock_var_10
        self.assertEqual(self.runtime.env_layer.get_env_var(zypp_lock_timeout_var_name), "10")
        self.runtime.env_layer.set_env_var(zypp_lock_timeout_var_name, 5)
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_has_zypper_lock_var_5
        self.assertEqual(self.runtime.env_layer.get_env_var(zypp_lock_timeout_var_name), "5")

        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_has_zypper_lock_var_10_multiline
        self.assertEqual(self.runtime.env_layer.get_env_var(zypp_lock_timeout_var_name), "10")
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_not_has_zypper_lock_multiline
        self.assertEqual(self.runtime.env_layer.get_env_var(zypp_lock_timeout_var_name), None)

        # test write contents
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_not_has_zypper_lock_multiline
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_assert_is_5
        self.runtime.env_layer.set_env_var(zypp_lock_timeout_var_name, 5)
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_has_zypper_lock_var_10_multiline
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_assert_not_exists
        self.runtime.env_layer.set_env_var(zypp_lock_timeout_var_name, None)
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_has_zypper_lock_var_10_multiline
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_assert_is_5
        self.runtime.env_layer.set_env_var(zypp_lock_timeout_var_name, 5)

        # test exceptions
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_raises_exception
        self.assertRaises(Exception, lambda: self.runtime.env_layer.set_env_var(zypp_lock_timeout_var_name, 5, raise_if_not_success=True))
        self.assertRaises(Exception, lambda: self.runtime.env_layer.get_env_var(zypp_lock_timeout_var_name, raise_if_not_success=True))

        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_not_has_zypper_lock_var
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_raises_exception
        self.assertRaises(Exception, lambda: self.runtime.env_layer.set_env_var(zypp_lock_timeout_var_name, 5, raise_if_not_success=True))

        # test return nones
        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_returns_none
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_valid
        self.assertIsNone(self.runtime.env_layer.get_env_var(zypp_lock_timeout_var_name))
        self.runtime.env_layer.set_env_var(zypp_lock_timeout_var_name, 5)

        self.runtime.env_layer.file_system.read_with_retry = self.mock_read_with_retry_has_zypper_lock_var_10_wrong_format
        self.assertEqual(self.runtime.env_layer.get_env_var(zypp_lock_timeout_var_name), "=10")
        self.runtime.env_layer.set_env_var(zypp_lock_timeout_var_name, 5)

        shutil.rmtree(self.temp_dir)

    def test_disable_auto_os_updates_with_uninstalled_services(self):
        # no services are installed on the machine. expected o/p: function will complete successfully. Backup file will be created with default values, no auto OS update configuration settings will be updated as there are none
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        package_manager.patch_mode_manager.disable_auto_os_update()
        self.assertTrue(package_manager.patch_mode_manager.image_default_patch_configuration_backup_exists())
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)

        # validating backup for yast2-online-update-configuration
        self.assertTrue(package_manager.patch_mode_manager.ZypperAutoOSUpdateServices.YAST2_ONLINE_UPDATE_CONFIGURATION in image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.patch_mode_manager.ZypperAutoOSUpdateServices.YAST2_ONLINE_UPDATE_CONFIGURATION][package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.APPLY_UPDATES_IDENTIFIER_TEXT], "")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.patch_mode_manager.ZypperAutoOSUpdateServices.YAST2_ONLINE_UPDATE_CONFIGURATION][package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.INSTALLATION_STATE_IDENTIFIER_TEXT], False)

    def test_disable_auto_os_updates_with_installed_services(self):
        # all services are installed and contain valid configurations. expected o/p All services will be disabled and backup file should reflect default settings for all
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')

        package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.OS_PATCH_CONFIGURATION_SETTINGS_FILE_PATH = os.path.join(self.runtime.execution_config.config_folder, "automatic_online_update")
        yast2_online_update_configuration_os_patch_configuration_settings = 'AOU_ENABLE_CRONJOB="true"'
        self.runtime.write_to_file(package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.OS_PATCH_CONFIGURATION_SETTINGS_FILE_PATH, yast2_online_update_configuration_os_patch_configuration_settings)

        package_manager.patch_mode_manager.disable_auto_os_update()
        self.assertTrue(package_manager.patch_mode_manager.image_default_patch_configuration_backup_exists())
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)

        # validating backup for yast2-online-update-configuration
        self.assertTrue(package_manager.patch_mode_manager.ZypperAutoOSUpdateServices.YAST2_ONLINE_UPDATE_CONFIGURATION in image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.patch_mode_manager.ZypperAutoOSUpdateServices.YAST2_ONLINE_UPDATE_CONFIGURATION][package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.APPLY_UPDATES_IDENTIFIER_TEXT], "true")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.patch_mode_manager.ZypperAutoOSUpdateServices.YAST2_ONLINE_UPDATE_CONFIGURATION][package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.INSTALLATION_STATE_IDENTIFIER_TEXT], True)

    def test_update_image_default_patch_mode(self):
        package_manager = self.container.get('package_manager')
        package_manager.patch_mode_manager.os_patch_configuration_settings_file_path = package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.OS_PATCH_CONFIGURATION_SETTINGS_FILE_PATH = os.path.join(self.runtime.execution_config.config_folder, "automatic_online_update")

        # disable apply_updates when enabled by default
        yast2_online_update_configuration_os_patch_configuration_settings = 'AOU_ENABLE_CRONJOB="true"'
        self.runtime.write_to_file(package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.OS_PATCH_CONFIGURATION_SETTINGS_FILE_PATH, yast2_online_update_configuration_os_patch_configuration_settings)

        package_manager.patch_mode_manager.update_os_patch_configuration_sub_setting(package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.APPLY_UPDATES_IDENTIFIER_TEXT, "false", package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.AUTO_UPDATE_CONFIG_PATTERN_MATCH_TEXT)
        yast2_online_update_configuration_os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.OS_PATCH_CONFIGURATION_SETTINGS_FILE_PATH)
        self.assertTrue(yast2_online_update_configuration_os_patch_configuration_settings_file_path_read is not None)
        self.assertTrue('AOU_ENABLE_CRONJOB="false"' in yast2_online_update_configuration_os_patch_configuration_settings_file_path_read)

        # disable apply_updates when default patch mode settings file is empty
        yast2_online_update_configuration_os_patch_configuration_settings = ''
        self.runtime.write_to_file(package_manager.patch_mode_manager.os_patch_configuration_settings_file_path, yast2_online_update_configuration_os_patch_configuration_settings)
        package_manager.patch_mode_manager.update_os_patch_configuration_sub_setting(package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.APPLY_UPDATES_IDENTIFIER_TEXT, "false", package_manager.patch_mode_manager.YastOnlineUpdateConfigurationConstants.AUTO_UPDATE_CONFIG_PATTERN_MATCH_TEXT)
        yast2_online_update_configuration_os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(package_manager.patch_mode_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(yast2_online_update_configuration_os_patch_configuration_settings_file_path_read is not None)
        self.assertTrue('AOU_ENABLE_CRONJOB="false"' in yast2_online_update_configuration_os_patch_configuration_settings_file_path_read)

    def is_string_in_status_file(self, str_to_find):
        with open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            file_contents = json.loads(file_handle.read())
            return str_to_find in str(file_contents)

    def test_package_manager_with_retries(self):
        package_manager = self.container.get('package_manager')
        # Setting operation to assessment to add all errors under assessment substatus
        self.runtime.status_handler.set_current_operation(Constants.Op.ASSESSMENT)

        # Wrap count in a mutable container to modify in mocked method to keep track of retries
        counter = [0]
        backup_mocked_method = package_manager.env_layer.run_command_output

        def mock_run_command_output(cmd, no_output=False, chk_err=False):
            # Only check for refresh cmd - otherwise, it may pick up other commands like ps tree
            if cmd == 'sudo zypper refresh':
                counter[0] += 1
                if counter[0] == package_manager.package_manager_max_retries - 1:
                    # Right before it runs out of retries, allow it to succeed
                    self.runtime.set_legacy_test_type('HappyPath')
            return backup_mocked_method(cmd, no_output, chk_err)

        package_manager.env_layer.run_command_output = mock_run_command_output

        # Case 1: SadPath to HappyPath (retry a few times and then success)

        # SadPath uses return code 7
        self.runtime.set_legacy_test_type('SadPath')

        # Invoke with retries should NOT raise an exception here
        try:
            package_manager.invoke_package_manager('sudo zypper refresh')
        except Exception as error:
            self.fail(repr(error))

        # Should reach max retries - 1 and then succeed, per the code above
        self.assertEqual(counter[0], package_manager.package_manager_max_retries - 1)
        self.assertFalse(self.is_string_in_status_file("Unexpected return code from package manager. [Code=4][Command=sudo zypper refresh]"))

        # Case 2: UnalignedPath to HappyPath (retry a few times and then success)
        counter = [0]

        # UnalignedPath uses return code 4
        self.runtime.set_legacy_test_type('UnalignedPath')

        # Invoke with retries should raise an exception here
        try:
            package_manager.invoke_package_manager('sudo zypper refresh')
        except Exception as error:
            self.fail(repr(error))

        # Should reach max retries - 1 and then succeed, per the code above
        self.assertEqual(counter[0], package_manager.package_manager_max_retries - 1)
        self.assertTrue(self.is_string_in_status_file('Unexpected return code from package manager. [Code=7][Command=sudo zypper refresh]'))

        # Case 3: NonexistentErrorCodePath to HappyPath (should not retry since error code is not supported)
        counter = [0]

        # UnalignedPath uses return code 7
        self.runtime.set_legacy_test_type('NonexistentErrorCodePath')

        # Invoke with retries should raise an exception here
        try:
            package_manager.invoke_package_manager('sudo zypper refresh')
            self.fail('Package manager should fail without retrying')
        except Exception as error:
            self.assertEqual(counter[0], 1)  # invoke should only be called once
            self.assertTrue(self.is_string_in_status_file('Unexpected return code from package manager. [Code=999999][Command=sudo zypper refresh]'))
            #self.assertTrue('Unexpected return code from package manager. [Code=999999][Command=sudo zypper refresh]' in repr(error))

        # Case 4: SadPath (retry and ultimately fail)
        # Set counter to max retries already so it does not hit the condition to enable HappyPath
        counter = [package_manager.package_manager_max_retries]

        # SadPath uses return code 7
        self.runtime.set_legacy_test_type('SadPath')

        # Invoke with retries should raise an exception here
        try:
            package_manager.invoke_package_manager('sudo zypper refresh')
        except Exception as error:
            # Should reach max retries * 2 and fail (since it started at max retries)
            self.assertEqual(counter[0], package_manager.package_manager_max_retries * 2)
            self.assertTrue(self.is_string_in_status_file('Unexpected return code from package manager. [Code=7][Command=sudo zypper refresh]'))
            self.assertTrue('Unexpected return code from package manager. [Code=7][Command=sudo zypper refresh]' in repr(error))

        package_manager.env_layer.run_command_output = backup_mocked_method

    def test_package_manager_no_repos(self):
        package_manager = self.container.get('package_manager')
        # Setting operation to assessment to add all errors under assessment substatus
        self.runtime.status_handler.set_current_operation(Constants.Op.ASSESSMENT)
        cmd_to_run = 'sudo zypper refresh'

        # Wrap count in a mutable container to modify in mocked method to keep track of retries
        counter = [0]
        backup_mocked_method = package_manager.env_layer.run_command_output

        def mock_run_command_output(cmd, no_output=False, chk_err=False):
            # Only check for refresh services cmd
            if cmd == 'sudo zypper refresh --services':
                # After refreshing, allow it to succeed
                self.runtime.set_legacy_test_type('HappyPath')
            elif cmd == 'sudo zypper refresh':
                counter[0] += 1
            return backup_mocked_method(cmd, no_output, chk_err)

        package_manager.env_layer.run_command_output = mock_run_command_output

        # Case 1: AnotherSadPath to HappyPath (no repos defined -> repos defined)

        # AnotherSadPath uses return code 6
        self.runtime.set_legacy_test_type('AnotherSadPath')

        # Invoke should not raise an exception here
        try:
            package_manager.invoke_package_manager(cmd_to_run)
        except Exception as error:
            self.fail(repr(error))

        # Should try twice: once fail, fix repos, then try again and succeed
        self.assertEqual(counter[0], 2)
        self.assertFalse(self.is_string_in_status_file('Unexpected return code (6) from package manager on command'))

        # Case 2: AnotherSadPath (no repos defined -> still no repos defined)
        counter = [0]

        # AnotherSadPath uses return code 6
        self.runtime.set_legacy_test_type('AnotherSadPath')

        def mock_run_command_output(cmd, no_output=False, chk_err=False):
            # Only count the number of command invocations and do not change to HappyPath
            if cmd == 'sudo zypper refresh':
                counter[0] += 1
            return backup_mocked_method(cmd, no_output, chk_err)

        package_manager.env_layer.run_command_output = mock_run_command_output

        # Invoke should raise an exception here
        try:
            package_manager.invoke_package_manager(cmd_to_run)
        except Exception as error:
            # Should try twice - once to fail and refresh repo, twice to ultimately fail with same error code (non-retryable)
            self.assertEqual(counter[0], 2)
            self.assertTrue(self.is_string_in_status_file("Unexpected return code from package manager. [Code=6][Command=sudo zypper refresh --services]"))
            self.assertTrue("Unexpected return code from package manager. [Code=6][Command=sudo zypper refresh]" in repr(error))

        package_manager.env_layer.run_command_output = backup_mocked_method

    def test_package_manager_exit_err_commit(self):
        package_manager = self.container.get('package_manager')
        self.runtime.status_handler.set_current_operation(Constants.Op.INSTALLATION)

        # Test command modifications with --replacefiles
        cmd_to_run = 'sudo zypper --non-interactive update samba-libs=4.15.4+git.327.37e0a40d45f-3.57.1'
        replacefiles_cmd_to_run = 'sudo zypper --non-interactive update --replacefiles samba-libs=4.15.4+git.327.37e0a40d45f-3.57.1'
        self.assertEqual(replacefiles_cmd_to_run, package_manager.modify_upgrade_or_patch_command_to_replacefiles(cmd_to_run))
        cmd_to_run += " --dry-run"
        self.assertEqual(None, package_manager.modify_upgrade_or_patch_command_to_replacefiles(cmd_to_run))
        self.assertEqual(None, package_manager.modify_upgrade_or_patch_command_to_replacefiles(replacefiles_cmd_to_run))
        cmd_to_run = 'sudo zypper --non-interactive patch --category security'
        replacefiles_cmd_to_run = 'sudo zypper --non-interactive patch --category security --replacefiles'
        self.assertEqual(replacefiles_cmd_to_run, package_manager.modify_upgrade_or_patch_command_to_replacefiles(cmd_to_run))

        # Wrap count in a mutable container to modify in mocked method to keep track of calls
        counter = [0]
        replacefiles_counter = [0]
        backup_mocked_method = package_manager.env_layer.run_command_output

        def mock_run_command_output(cmd, no_output=False, chk_err=False):
            # Only check for refresh services cmd
            if cmd == 'sudo zypper --non-interactive update --replacefiles samba-libs=4.15.4+git.327.37e0a40d45f-3.57.1':
                # After refreshing, allow it to succeed
                replacefiles_counter[0] += 1
                self.runtime.set_legacy_test_type('HappyPath')
            elif cmd == 'sudo zypper --non-interactive update samba-libs=4.15.4+git.327.37e0a40d45f-3.57.1':
                counter[0] += 1
            return backup_mocked_method(cmd, no_output, chk_err)

        package_manager.env_layer.run_command_output = mock_run_command_output

        # AnotherSadPath uses return code 8
        self.runtime.set_legacy_test_type('AnotherSadPath')

        cmd_to_run = 'sudo zypper --non-interactive update samba-libs=4.15.4+git.327.37e0a40d45f-3.57.1'
        package_manager.invoke_package_manager(cmd_to_run)
        self.assertEqual(counter[0], 1)
        self.assertEqual(replacefiles_counter[0], 1)
        self.assertFalse(self.is_string_in_status_file('Unexpected return code (8) from package manager on command'))

        package_manager.env_layer.run_command_output = backup_mocked_method

    def test_package_manager_exit_reboot_required(self):
        # AnotherSadPath returns code 102 for this command
        package_manager = self.container.get('package_manager')
        self.runtime.status_handler.set_current_operation(Constants.Op.INSTALLATION)
        self.runtime.set_legacy_test_type('AnotherSadPath')

        cmd = "sudo LANG=en_US.UTF8 zypper --non-interactive patch --category security --dry-run"
        package_manager.invoke_package_manager(cmd)
        self.assertFalse(package_manager.force_reboot)

        # AnotherSadPath returns code 102 on this command, but should actually set reboot flag
        cmd = "sudo LANG=en_US.UTF8 zypper --non-interactive patch --category security"
        package_manager.invoke_package_manager(cmd)
        self.assertTrue(package_manager.force_reboot)

    def test_package_manager_exit_repeat_operation(self):
        # SadPath returns code 103 for this command
        package_manager = self.container.get('package_manager')
        self.runtime.status_handler.set_current_operation(Constants.Op.INSTALLATION)
        self.runtime.set_legacy_test_type('SadPath')

        # Should not set reboot flag (as it is a dry run)
        cmd = "sudo LANG=en_US.UTF8 zypper --non-interactive patch --category security --dry-run"
        package_manager.invoke_package_manager(cmd)
        self.assertFalse(package_manager.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, False))

        # Should set reboot flag
        cmd = "sudo LANG=en_US.UTF8 zypper --non-interactive patch --category security"
        package_manager.invoke_package_manager(cmd)
        self.assertTrue(package_manager.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, False))

    def test_is_reboot_pending_return_true_when_exception_raised(self):
        package_manager = self.container.get('package_manager')
        backup_do_process_require_restart = package_manager.do_processes_require_restart
        package_manager.do_processes_require_restart = self.mock_do_processes_require_restart_raise_exception

        self.assertTrue(package_manager.is_reboot_pending())

        package_manager.do_processes_require_restart = backup_do_process_require_restart


if __name__ == '__main__':
    unittest.main()


