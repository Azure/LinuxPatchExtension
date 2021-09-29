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

import unittest
from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestZypperPackageManager(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.ZYPPER)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

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
        dependent_list = package_manager.get_dependent_list("man")
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
            package_manager.get_dependent_list("man")
        except Exception as exception:
            self.assertTrue(str(exception))
        else:
            self.assertFalse(1 != 2, 'Exception did not occur and test failed.')

    def test_do_processes_require_restart(self):

        # Restart required
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.assertTrue(package_manager.do_processes_require_restart())

        # Restart not required
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.assertFalse(package_manager.do_processes_require_restart())

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
        self.assertEquals(package_manager.install_update_and_dependencies('selinux-policy', '3.13.1-102.el7_3.16', simulate=True), Constants.INSTALLED)

    def test_install_package_failure(self):
        self.runtime.set_legacy_test_type('FailInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # test for unsuccessfully installing a package
        self.assertEquals(package_manager.install_update_and_dependencies('selinux-policy.noarch', '3.13.1-102.el7_3.16', simulate=True), Constants.FAILED)

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

    def test_env_var_set_get(self):
        zypp_lock_timeout_var_name = "ZYPP_LOCK_TIMEOUT"

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

if __name__ == '__main__':
    unittest.main()
