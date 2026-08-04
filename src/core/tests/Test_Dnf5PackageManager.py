# Copyright 2026 Microsoft Corporation
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
import sys
import unittest

# Conditional import for StringIO
try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import StringIO  # Python 3

from core.tests.library.ArgumentComposer import ArgumentComposer
from core.src.bootstrap.Constants import Constants
from core.tests.library.RuntimeCompositor import RuntimeCompositor

class TestDnfPackageManager(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.DNF5)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def mock_write_with_retry_raise_exception(self, file_path_or_handle, data, mode='a+'):
        raise Exception

    def mock_run_command_output_check_update(self, cmd, no_output=False, chk_err=True):
        if "check-update" in cmd:
            return 0, ""
        return None

    def mock_run_command_output_no_reboot(self, cmd, no_output=False, chk_err=True):
        if "needs-restarting" in cmd:
            return 0, ("No core libraries or services have been updated since boot-up.\n"
                       "Reboot should not be necessary.\n")
        return 0, ""

    # region Utility Functions
    def __setup_config_and_invoke_revert_auto_os_to_system_default(self, package_manager, create_current_auto_os_config=True, create_backup_for_system_default_config=True, current_auto_os_update_config_value='', apply_updates_value="",
                                                                   download_updates_value="", enable_on_reboot_value=False, installation_state_value=False, set_installation_state=True):
        """ Sets up current auto OS update config, backup for system default config (if requested) and invoke revert to system default """
        # setup current auto OS update config
        if create_current_auto_os_config:
            self.__setup_current_auto_os_update_config(package_manager, current_auto_os_update_config_value)

        # setup backup for system default auto OS update config
        if create_backup_for_system_default_config:
            self.__setup_backup_for_system_default_OS_update_config(package_manager, apply_updates_value=apply_updates_value, download_updates_value=download_updates_value, enable_on_reboot_value=enable_on_reboot_value,
                                                                    installation_state_value=installation_state_value, set_installation_state=set_installation_state)
        package_manager.revert_auto_os_update_to_system_default()

    def __setup_current_auto_os_update_config(self, package_manager, config_value='',
                                              config_file_name="automatic.conf"):
        # setup current auto OS update config
        package_manager.dnf5_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, config_file_name)
        self.runtime.write_to_file(package_manager.dnf5_automatic_configuration_file_path, config_value)

    def __setup_backup_for_system_default_OS_update_config(self, package_manager, apply_updates_value="", download_updates_value="", enable_on_reboot_value=False, installation_state_value=False, set_installation_state=True):
        # setup backup for system default auto OS update config
        package_manager.image_default_patch_configuration_backup_path = os.path.join(self.runtime.execution_config.config_folder, Constants.IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH)
        backup_image_default_patch_configuration_json = {
            "dnf5-automatic": {
                "apply_updates": apply_updates_value,
                "download_updates": download_updates_value,
                "enable_on_reboot": enable_on_reboot_value
            }
        }
        if set_installation_state:
            backup_image_default_patch_configuration_json["dnf5-automatic"]["installation_state"] = installation_state_value
        self.runtime.write_to_file(package_manager.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(backup_image_default_patch_configuration_json)))

    @staticmethod
    def __capture_std_io():
        # arrange capture std IO
        captured_output = StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured_output
        return captured_output, original_stdout

    def __assert_std_io(self, captured_output, expected_output=''):
        output = captured_output.getvalue()
        self.assertIn(expected_output, output)

    def __assert_reverted_automatic_patch_configuration_settings(self, package_manager, config_exists=True, config_value_expected=''):
        if config_exists:
            reverted_dnf5_automatic_patch_configuration_settings = self.runtime.env_layer.file_system.read_with_retry(
                package_manager.dnf5_automatic_configuration_file_path)
            self.assertIsNotNone(reverted_dnf5_automatic_patch_configuration_settings)
        else:
            self.assertFalse(os.path.exists(package_manager.dnf5_automatic_configuration_file_path))
    # endregion

    def test_refresh_repo(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_manager.refresh_repo_safely()
        # When no updates available and exit code 0
        self.runtime.env_layer.run_command_output = self.mock_run_command_output_check_update
        package_manager.refresh_repo_safely()

    def test_disable_auto_os_updates_with_uninstalled_services(self):
        # no services are installed on the machine. expected o/p: function will complete successfully. Backup file will be created with default values, no auto OS update configuration settings will be updated as there are none
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        package_manager.disable_auto_os_update()
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertIsNotNone(image_default_patch_configuration_backup)

        # validating backup for dnf-automatic
        self.assertIn(package_manager.dnf5_auto_os_update_service, image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_download_updates_identifier_text], "")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_apply_updates_identifier_text], "")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_enable_on_reboot_identifier_text], False)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_installation_state_identifier_text], False)

    def test_disable_auto_os_updates_with_installed_services(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')

        package_manager.dnf5_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf5_automatic_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.dnf5_automatic_configuration_file_path, dnf5_automatic_os_patch_configuration_settings)

        package_manager.disable_auto_os_update()
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertIsNot(image_default_patch_configuration_backup, None)

        # validating backup for dnf-automatic
        self.assertIn(package_manager.dnf5_auto_os_update_service, image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_download_updates_identifier_text], "yes")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_apply_updates_identifier_text], "yes")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_enable_on_reboot_identifier_text], False)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_installation_state_identifier_text], True)

    def test_disable_auto_os_update_failure(self):
        package_manager = self.container.get('package_manager')

        self.assertRaises(Exception, package_manager.disable_auto_os_update)
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())

    def test_get_current_auto_os_patch_state_disabled(self):
        self.runtime.set_legacy_test_type('SadPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.DISABLED)

    def test_get_current_auto_os_patch_state_with_uninstalled_services(self):
        """Test get_current_auto_os_patch_state when dnf5-automatic is not installed"""
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state
        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.DISABLED)

    def test_get_current_auto_os_patch_state_with_installed_services_and_state_enabled(self):
        # with enable on reboot set to false
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state

        package_manager.dnf5_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf5_automatic_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.dnf5_automatic_configuration_file_path, dnf5_automatic_os_patch_configuration_settings)

        is_enabled = package_manager.is_service_set_to_enable_on_reboot(package_manager.enable_on_reboot_check_cmd)
        self.assertFalse(is_enabled)
        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.ENABLED)

        # with enable on reboot set to true
        self.runtime.set_legacy_test_type('AnotherSadPath')
        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state

        package_manager.dnf5_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf5_automatic_os_patch_configuration_settings = 'apply_updates = no\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.dnf5_automatic_configuration_file_path,
                                   dnf5_automatic_os_patch_configuration_settings)

        is_enabled = package_manager.is_service_set_to_enable_on_reboot(package_manager.enable_on_reboot_check_cmd)
        self.assertTrue(is_enabled)
        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()
        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.ENABLED)

    def test_get_current_auto_os_patch_state_with_installed_services_and_state_disabled(self):
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')

        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.DISABLED)

    def test_revert_auto_os_update_to_system_default_with_service_not_installed(self):
        """Test revert when dnf5-automatic is not installed - should be no-op"""
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')

        # Create backup with service marked as not installed
        package_manager.image_default_patch_configuration_backup_path = os.path.join(self.runtime.execution_config.config_folder, Constants.IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH)
        backup_config = {
            "dnf5-automatic": {
                "enable_on_reboot": False,
                "installation_state": False
            }
        }
        self.runtime.write_to_file(package_manager.image_default_patch_configuration_backup_path, json.dumps(backup_config))

        # Should complete without error even when service is not installed
        package_manager.revert_auto_os_update_to_system_default()

    def test_revert_auto_os_update_to_system_default(self):
        revert_success_testcase = {
            "legacy_type": 'HappyPath',
            "stdio": {
                "capture_output": False,
                "expected_output": None
            },
            "config": {
                "current_auto_update_config": {
                    "create_current_auto_os_config": True,
                    "current_auto_os_update_config_value": 'apply_updates = no\ndownload_updates = no\n'
                },
                "backup_system_default_config": {
                    "create_backup_for_system_default_config": True,
                    "apply_updates_value": "yes",
                    "download_updates_value": "yes",
                    "enable_on_reboot_value": True,
                    "installation_state_value": True,
                    "set_installation_state": True
                }
            },
            "assertions": {
                "config_value_expected": 'apply_updates = yes\ndownload_updates = yes\n',
                "config_exists": True
            }
        }

        revert_success_with_dnf_not_installed_testcase = {
            "legacy_type": 'SadPath',
            "stdio": {
                "capture_output": False,
                "expected_output": None
            },
            "config": {
                "current_auto_update_config": {
                    "create_current_auto_os_config": False,
                    "current_auto_os_update_config_value": ''
                },
                "backup_system_default_config": {
                    "create_backup_for_system_default_config": True,
                    "apply_updates_value": "",
                    "download_updates_value": "",
                    "enable_on_reboot_value": False,
                    "installation_state_value": False,
                    "set_installation_state": True
                }
            },
            "assertions": {
                "config_value_expected": "",
                "config_exists": False
            }
        }

        revert_success_with_dnf_installed_but_no_config_value_testcase = {
            "legacy_type": 'RevertToImageDefault',
            "stdio": {
                "capture_output": False,
                "expected_output": None
            },
            "config": {
                "current_auto_update_config": {
                    "create_current_auto_os_config": True,
                    "current_auto_os_update_config_value": 'test_value = yes\n'
                },
                "backup_system_default_config": {
                    "create_backup_for_system_default_config": True,
                    "apply_updates_value": "",
                    "download_updates_value": "",
                    "enable_on_reboot_value": False,
                    "installation_state_value": False,
                    "set_installation_state": True
                }
            },
            "assertions": {
                "config_value_expected": 'download_updates =\napply_updates = \n',
                "config_exists": True
            }
        }

        revert_success_backup_config_does_not_exist_testcase = {
            "legacy_type": 'RevertToImageDefault',
            "stdio": {
                "capture_output": True,
                "expected_output": "[DNF5] Since the backup is invalid or does not exist for current service, we won't be able to revert auto OS patch settings to their system default value. [Service=dnf5-automatic]"
            },
            "config": {
                "current_auto_update_config": {
                    "create_current_auto_os_config": True,
                    "current_auto_os_update_config_value": 'apply_updates = no\ndownload_updates = no\n'
                },
                "backup_system_default_config": {
                    "create_backup_for_system_default_config": False,
                    "apply_updates_value": "",
                    "download_updates_value": "",
                    "enable_on_reboot_value": False,
                    "installation_state_value": False,
                    "set_installation_state": True
                }
            },
            "assertions": {
                "config_value_expected": 'apply_updates = no\ndownload_updates = no\n',
                "config_exists": True
            }
        }

        revert_success_default_backup_config_invalid_testcase = {
            "legacy_type": 'RevertToImageDefault',
            "stdio": {
                "capture_output": True,
                "expected_output": "[DNF5] Since the backup is invalid or does not exist for current service, we won't be able to revert auto OS patch settings to their system default value. [Service=dnf5-automatic]"
            },
            "config": {
                "current_auto_update_config": {
                    "create_current_auto_os_config": True,
                    "current_auto_os_update_config_value": 'apply_updates = no\ndownload_updates = no\n'
                },
                "backup_system_default_config": {
                    "create_backup_for_system_default_config": True,
                    "apply_updates_value": "yes",
                    "download_updates_value": "yes",
                    "enable_on_reboot_value": True,
                    "installation_state_value": False,
                    "set_installation_state": False
                }
            },
            "assertions": {
                "config_value_expected": 'apply_updates = no\ndownload_updates = no\n',
                "config_exists": True
            }
        }

        all_testcases = [revert_success_testcase, revert_success_with_dnf_not_installed_testcase,
                         revert_success_with_dnf_installed_but_no_config_value_testcase,
                         revert_success_backup_config_does_not_exist_testcase,
                         revert_success_default_backup_config_invalid_testcase]

        for testcase in all_testcases:
            self.tearDown()
            self.setUp()
            captured_output, original_stdout = None, None
            if testcase["stdio"]["capture_output"]:
                # arrange capture std IO
                captured_output, original_stdout = self.__capture_std_io()

            self.runtime.set_legacy_test_type(testcase["legacy_type"])
            package_manager = self.container.get('package_manager')

            # setup current auto OS update config, backup for system default config and invoke revert to system default
            self.__setup_config_and_invoke_revert_auto_os_to_system_default(package_manager,
                                                                            create_current_auto_os_config=bool(testcase["config"]["current_auto_update_config"]["create_current_auto_os_config"]),
                                                                            current_auto_os_update_config_value=testcase["config"]["current_auto_update_config"]["current_auto_os_update_config_value"],
                                                                            create_backup_for_system_default_config=bool(testcase["config"]["backup_system_default_config"]["create_backup_for_system_default_config"]),
                                                                            apply_updates_value=testcase["config"]["backup_system_default_config"]["apply_updates_value"],
                                                                            download_updates_value=testcase["config"]["backup_system_default_config"]["download_updates_value"],
                                                                            enable_on_reboot_value=bool(testcase["config"]["backup_system_default_config"]["enable_on_reboot_value"]),
                                                                            installation_state_value=bool(testcase["config"]["backup_system_default_config"]["installation_state_value"]),
                                                                            set_installation_state=bool(testcase["config"]["backup_system_default_config"]["set_installation_state"]))
            # assert
            if testcase["stdio"]["capture_output"]:
                # restore sys.stdout output
                sys.stdout = original_stdout
                self.__assert_std_io(captured_output=captured_output,expected_output=testcase["stdio"]["expected_output"])
            self.__assert_reverted_automatic_patch_configuration_settings(package_manager, config_exists=bool(testcase["assertions"]["config_exists"]), config_value_expected=testcase["assertions"]["config_value_expected"])

    def test_dedupe_update_packages_to_get_latest_versions(self):
        packages = []
        package_versions = []

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        deduped_packages, deduped_package_versions = package_manager.dedupe_update_packages_to_get_latest_versions(
            packages, package_versions)
        self.assertEqual(deduped_packages, [])
        self.assertEqual(deduped_package_versions, [])

        packages = ['python3.x86_64', 'dracut.x86_64', 'libxml2.x86_64', 'azurelinux-release.noarch', 'python3.noarch',
                    'python3.x86_64', 'python3.x86_64', 'hypervvssd.x86_64', 'python3.x86_64', 'python3.x86_64']
        package_versions = ['3.12.3-1.azl3', '102-7.azl3 ', '2.11.5-1.azl3', '3.0-16.azl3', '3.12.9-2.azl3',
                            '3.12.9-1.azl3', '3.12.3-4.azl3', '6.6.78.1-1.azl3', '3.12.3-5.azl3', '3.12.3-5.azl3']
        deduped_packages, deduped_package_versions = package_manager.dedupe_update_packages_to_get_latest_versions(
            packages, package_versions)

        self.assertIsNotNone(deduped_packages)
        self.assertNotEqual(deduped_packages, [])
        self.assertIsNotNone(deduped_package_versions)
        self.assertNotEqual(deduped_package_versions, [])
        self.assertEqual(len(deduped_packages), 6)
        self.assertEqual(deduped_packages[0], 'python3.x86_64')
        self.assertEqual(deduped_package_versions[0], '3.12.9-1.azl3')

    def test_obsolete_packages_should_not_considered_in_available_updates(self):
        self.runtime.set_legacy_test_type('ObsoletePackages')
        package_manager = self.container.get('package_manager')

        # test for all available versions
        package_versions = package_manager.get_all_available_versions_of_package("python3")
        self.assertEqual(len(package_versions), 1)
        self.assertEqual(package_versions[0], '3.14.3-2.azl4~20260501')

    def test_install_package_failure(self):
        """Unit test for install package failure"""
        self.runtime.set_legacy_test_type('FailInstallPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)
        # test for unsuccessfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('hyperv-daemons-license.noarch','6.6.78.1-1.azl3',simulate=True),Constants.FAILED)

    def test_get_product_name(self):
        """Unit test for retrieving product Name"""
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)
        self.assertEqual(package_manager.get_product_name("bash.x86_64"), "bash.x86_64")
        self.assertEqual(package_manager.get_product_name("firefox.x86_64"), "firefox.x86_64")
        self.assertEqual(package_manager.get_product_name("test.noarch"), "test.noarch")
        self.assertEqual(package_manager.get_product_name("noextension"), "noextension")
        self.assertEqual(package_manager.get_product_name("noextension.ext"), "noextension.ext")

    def test_package_manager_no_updates(self):
        """Unit test for dnf5 package manager with no updates"""
        self.runtime.set_legacy_test_type('SadPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertEqual(len(available_updates), 0)
        self.assertEqual(len(package_versions), 0)

    def test_package_manager(self):
        """Unit test for dnf5 package manager"""
        self.runtime.set_legacy_test_type('HappyPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # Test: get_available_updates (do NOT assert exact count unless mock supports it)
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(available_updates), len(package_versions))

        cmd = package_manager.single_package_upgrade_simulation_cmd + "hyperv-daemons.x86_64"
        code, out = self.runtime.env_layer.run_command_output(cmd, False, False)
        size = package_manager.get_package_size(out)
        self.assertEqual(size, "135.09k")

        # test for get_package_size when size is not available
        cmd = package_manager.single_package_upgrade_cmd + "systemd"
        code, out = self.runtime.env_layer.run_command_output(cmd, False, False)
        size = package_manager.get_package_size(out)
        self.assertEqual(size, Constants.UNKNOWN_PACKAGE_SIZE)

        # Test: get_all_available_versions_of_package (ONLY python3 since mock exists)
        versions = package_manager.get_all_available_versions_of_package("python3")
        self.assertIsNotNone(versions)
        self.assertEqual(len(versions), 5)
        self.assertEqual(versions[0], '3.12.3-1.azl4~20260501')
        self.assertEqual(versions[1], '3.12.3-2.azl4~20260501')
        self.assertEqual(versions[2], '3.12.3-4.azl4~20260501')
        self.assertEqual(versions[3], '3.12.3-5.azl4~20260501')
        self.assertEqual(versions[4], '3.12.3-6.azl4~20260501')

        # Test exception handling scenarios
        self.runtime.stop()
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True,Constants.DNF5)

        self.container = self.runtime.container
        self.runtime.set_legacy_test_type('ExceptionPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # Exception test: get_available_updates
        try:
            package_manager.get_available_updates(package_filter)
        except Exception as exception:
            self.assertTrue(str(exception))
        else:
            self.assertFalse(True, "Exception did not occur and test failed.")

        # Exception test: get_dependent_list
        try:
            package_manager.get_dependent_list(["hyperv-daemons.x86_64"])
        except Exception as exception:
            self.assertTrue(str(exception))
        else:
            self.assertFalse(True, "Exception did not occur and test failed.")

        self.runtime.set_legacy_test_type('SuccessInstallPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)

        # Test: get_dependent_list
        dependent_list = package_manager.get_dependent_list(["hyperv-daemons.x86_64"])
        self.assertIsNotNone(dependent_list)

        self.runtime.set_legacy_test_type('AnotherSadPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        sad_dependent_list = package_manager.get_dependent_list(["openssl-999.999"])
        self.assertIsNotNone(sad_dependent_list)
        self.assertEqual(len(sad_dependent_list), 0)

    def test_install_package_success(self):
        """Unit test for install package success"""
        self.runtime.set_legacy_test_type('SuccessInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for successfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('rubygem-json.x86_64','2.13.2-2.azl4~20260501',simulate=True),Constants.INSTALLED)

    def test_inclusion_type_other(self):
        """Unit test for dnf5 package manager with inclusion and Classification = Other. All packages are considered are 'Security' since DNF does not have patch classification"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.OTHER]
        argument_composer.patches_to_include = ["ssh", "tcpdump"]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.DNF5)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(0, len(available_updates))
        self.assertEqual(0, len(package_versions))

    def test_update_image_default_patch_mode(self):
        package_manager = self.container.get('package_manager')
        package_manager.os_patch_configuration_settings_file_path = package_manager.dnf5_automatic_configuration_file_path = os.path.join(
            self.runtime.execution_config.config_folder, "automatic.conf")

        # disable apply_updates when enabled by default
        dnf5_automatic_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.dnf5_automatic_configuration_file_path,
                                   dnf5_automatic_os_patch_configuration_settings)

        package_manager.update_os_patch_configuration_sub_setting(
            package_manager.dnf5_automatic_apply_updates_identifier_text, "no",
            package_manager.dnf5_automatic_config_pattern_match_text)
        dnf5_automatic_os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(
            package_manager.os_patch_configuration_settings_file_path)
        self.assertIsNotNone(dnf5_automatic_os_patch_configuration_settings_file_path_read)
        self.assertIn('apply_updates = no', dnf5_automatic_os_patch_configuration_settings_file_path_read)
        self.assertIn('download_updates = yes' , dnf5_automatic_os_patch_configuration_settings_file_path_read)

        # disable download_updates when enabled by default
        dnf5_automatic_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path,
                                   dnf5_automatic_os_patch_configuration_settings)
        package_manager.update_os_patch_configuration_sub_setting(
            package_manager.dnf5_automatic_download_updates_identifier_text, "no",
            package_manager.dnf5_automatic_config_pattern_match_text)
        dnf5_automatic_os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(
            package_manager.os_patch_configuration_settings_file_path)
        self.assertIsNotNone(dnf5_automatic_os_patch_configuration_settings_file_path_read)
        self.assertIn('apply_updates = yes', dnf5_automatic_os_patch_configuration_settings_file_path_read)
        self.assertIn('download_updates = no', dnf5_automatic_os_patch_configuration_settings_file_path_read)

        # disable apply_updates when default patch mode settings file is empty
        dnf5_automatic_os_patch_configuration_settings = ''
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path,
                                   dnf5_automatic_os_patch_configuration_settings)
        package_manager.update_os_patch_configuration_sub_setting(
            package_manager.dnf5_automatic_apply_updates_identifier_text, "no",
            package_manager.dnf5_automatic_config_pattern_match_text)
        dnf5_automatic_os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(
            package_manager.os_patch_configuration_settings_file_path)
        self.assertIsNotNone(dnf5_automatic_os_patch_configuration_settings_file_path_read)
        self.assertNotIn('download_updates', dnf5_automatic_os_patch_configuration_settings_file_path_read)
        self.assertIn('apply_updates = no', dnf5_automatic_os_patch_configuration_settings_file_path_read)

    def test_disable_auto_os_update_on_reboot(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)
        command = "systemctl disable --now dnf5-automatic.timer"

        package_manager.disable_auto_update_on_reboot(command)

        self.runtime.set_legacy_test_type('AnotherSadPath')
        package_manager = self.container.get('package_manager')
        command = "systemctl enable --nows dnf-automatic.timer"
        self.assertRaises(Exception, package_manager.disable_auto_update_on_reboot, command)

    def test_enable_auto_os_update_on_reboot(self):
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        package_manager.enable_on_reboot_cmd = "systemctl enable --now dnf5-automatic.timer"
        self.assertRaises(Exception, package_manager.enable_auto_update_on_reboot)

    def test_is_reboot_pending(self):
        """Unit test for dnf5 package manager reboot detection"""
        # Restart required (needs-restarting returns code=1)
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.assertTrue(package_manager.is_reboot_pending())

        # Restart not required (needs-restarting returns code=0)
        self.runtime.set_legacy_test_type('SadPath')
        self.runtime.env_layer.run_output_command = self.mock_run_command_output_no_reboot
        self.assertFalse(package_manager.is_reboot_pending())

        # Exception Path
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_raise_exception
        self.assertRaises(Exception, package_manager.is_reboot_pending())

    def test_do_processes_require_restart(self):
        """Unit test for dnf5 package manager"""
        # Restart required
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)
        self.assertTrue(package_manager.is_reboot_pending())

        # Restart not required
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.assertFalse(package_manager.is_reboot_pending())

    def test_get_security_updates(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        security_packages, security_package_versions  = package_manager.get_security_updates()
        self.assertTrue(5, security_packages)
        self.assertTrue(5, security_package_versions)

    def test_update_os_patch_configuration_sub_setting_exception_handling(self):
        """Test exception handling when override file write fails"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        # Mock file_system.write_with_retry to raise exception
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_raise_exception
        self.assertRaises(Exception, package_manager.update_os_patch_configuration_sub_setting, )

    def test_backup_image_default_patch_configuration_if_not_exists_exception_handling(self):
        """Test exception handling when override file write fails"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        # Mock file_system.write_with_retry to raise exception
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_raise_exception
        self.assertRaises(Exception, package_manager.backup_image_default_patch_configuration_if_not_exists, )

    def test_get_package_install_expected_avg_time_in_seconds(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager.get_package_install_expected_avg_time_in_seconds(), 90)

    def test_no_op_methods(self):
        """Test all no-op methods execute without error"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')

        # These should all execute without raising exceptions
        package_manager.do_processes_require_restart()
        package_manager.set_max_patch_publish_date()
        package_manager.add_arch_dependencies(package_manager, "pkg", "1.0", [], [], [], [])
        package_manager.set_security_esm_package_status("op", [])
        package_manager.separate_out_esm_packages([], [])

if __name__ == '__main__':
    unittest.main()

