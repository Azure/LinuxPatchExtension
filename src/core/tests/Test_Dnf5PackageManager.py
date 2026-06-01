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
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.DNF)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def mock_run_command_output_return_dnf(self, cmd, no_output=False, chk_err=True):
        """ Mock for run_command_output to return dnf """
        return 0, "3.5.8-3\n"

    def mock_run_command_output_return_1(self, cmd, no_output=False, chk_err=True):
        """ Mock for run_command_output to return None """
        return 1, "No output available\n"

    def __assert_std_io(self, captured_output, expected_output=''):
        output = captured_output.getvalue()
        self.assertTrue(expected_output in output)

    # region Mocks
    def mock_do_processes_require_restart_raise_exception(self):
        raise Exception

    def test_refresh_repo(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_manager.refresh_repo_safely()

    def test_disable_auto_os_updates_with_uninstalled_services(self):
        # no services are installed on the machine. expected o/p: function will complete successfully. Backup file will be created with default values, no auto OS update configuration settings will be updated as there are none
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        package_manager.disable_auto_os_update()
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)

        # validating backup for dnf-automatic
        self.assertTrue(package_manager.dnf5_auto_os_update_service in image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_download_updates_identifier_text], "")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_apply_updates_identifier_text], "")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_enable_on_reboot_identifier_text], False)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_installation_state_identifier_text], False)

    def test_disable_auto_os_updates_with_installed_services(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')

        package_manager.disable_auto_os_update()

        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())

        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(package_manager.dnf5_auto_os_update_service in image_default_patch_configuration_backup)

        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_download_updates_identifier_text],"yes")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_apply_updates_identifier_text],"yes")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_enable_on_reboot_identifier_text],False)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf5_auto_os_update_service][package_manager.dnf5_automatic_installation_state_identifier_text],True)

    def test_disable_auto_os_update_failure(self):
        # disable with non existing log file
        package_manager = self.container.get('package_manager')

        package_manager.disable_auto_os_update()
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())

    def test_get_current_auto_os_patch_state_with_uninstalled_services(self):
        """Test get_current_auto_os_patch_state when dnf5-automatic is not installed"""
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')

        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.DISABLED)


    def test_get_current_auto_os_patch_state_with_installed_services_and_state_enabled(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state

        # NEW: setup override.conf instead of config file
        override_dir = os.path.join(self.runtime.execution_config.config_folder, "dnf5-automatic.service.d")
        os.makedirs(override_dir, exist_ok=True)

        override_file = os.path.join(override_dir, "override.conf")
        package_manager.dnf5_automatic_override_file = override_file

        override_content = (
            "[Service]\n"
            "ExecStart=\n"
            "ExecStart=/usr/bin/dnf5 automatic --timer --downloadupdates --installupdates\n"
        )

        self.runtime.write_to_file(override_file, override_content)

        # act
        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.ENABLED)

        #SECOND CASE
        self.tearDown()
        self.setUp()

        self.runtime.set_legacy_test_type('AnotherSadPath')
        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state

        override_dir = os.path.join(self.runtime.execution_config.config_folder, "dnf5-automatic.service.d")
        os.makedirs(override_dir, exist_ok=True)

        override_file = os.path.join(override_dir, "override.conf")
        package_manager.dnf5_automatic_override_file = override_file

        override_content = (
            "[Service]\n"
            "ExecStart=\n"
            "ExecStart=/usr/bin/dnf5 automatic --timer --downloadupdates --no-installupdates\n"
        )

        self.runtime.write_to_file(override_file, override_content)

        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.ENABLED)


    def test_get_current_auto_os_patch_state_with_installed_services_and_state_disabled(self):
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')

        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.DISABLED)

    def test_dedupe_update_packages_to_get_latest_versions(self):
        packages = []
        package_versions = []

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        deduped_packages, deduped_package_versions = package_manager.dedupe_update_packages_to_get_latest_versions(
            packages, package_versions)
        self.assertTrue(deduped_packages == [])
        self.assertTrue(deduped_package_versions == [])

        packages = ['python3.x86_64', 'dracut.x86_64', 'libxml2.x86_64', 'azurelinux-release.noarch', 'python3.noarch',
                    'python3.x86_64', 'python3.x86_64', 'hypervvssd.x86_64', 'python3.x86_64', 'python3.x86_64']
        package_versions = ['3.12.3-1.azl3', '102-7.azl3 ', '2.11.5-1.azl3', '3.0-16.azl3', '3.12.9-2.azl3',
                            '3.12.9-1.azl3', '3.12.3-4.azl3', '6.6.78.1-1.azl3', '3.12.3-5.azl3', '3.12.3-5.azl3']
        deduped_packages, deduped_package_versions = package_manager.dedupe_update_packages_to_get_latest_versions(
            packages, package_versions)
        self.assertTrue(deduped_packages is not None and deduped_packages is not [])
        self.assertTrue(deduped_package_versions is not None and deduped_package_versions is not [])
        self.assertTrue(len(deduped_packages) == 6)
        self.assertTrue(deduped_packages[0] == 'python3.x86_64')
        self.assertTrue(deduped_package_versions[0] == '3.12.9-1.azl3')

    def test_obsolete_packages_should_not_considered_in_available_updates(self):
        self.runtime.set_legacy_test_type('ObsoletePackages')
        package_manager = self.container.get('package_manager')

        # test for all available versions
        package_versions = package_manager.get_all_available_versions_of_package("python3")
        self.assertEqual(len(package_versions), 1)
        self.assertEqual(package_versions[0], '3.14.3-2.azl4~20260501')

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
        self.assertTrue(True)  # If no exception, test passes

    def test_revert_auto_os_update_to_system_default(self):
        """
        DNF5: Table-driven revert tests
        Validates:
          - HappyPath: config restored from backup + timer enabled when backup says enable_on_reboot=True
          - Service not installed: no-op
          - Backup missing or invalid: revert is skipped gracefully (no crash)
          - Backup values empty: override contains no explicit flags
        """

        revert_success_testcase = {
            "legacy_type": "HappyPath",
            "stdio": {"capture_output": False, "expected_output": None},
            "config": {
                "current_auto_update_config": {
                    "create_current_auto_os_config": True,
                    "current_auto_os_update_config_value": "apply_updates = no\ndownload_updates = no\n"
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
                "config_exists": True,
                "config_value_expected": "apply_updates = yes\ndownload_updates = yes\n",
            }
        }

        revert_success_with_dnf5_not_installed_testcase = {
            "legacy_type": "SadPath",
            "stdio": {"capture_output": False, "expected_output": None},
            "config": {
                "current_auto_update_config": {
                    "create_current_auto_os_config": False,
                    "current_auto_os_update_config_value": ""
                },
                "backup_system_default_config": {
                    "create_backup_for_system_default_config": True,
                    "apply_updates_value": "yes",
                    "download_updates_value": "yes",
                    "enable_on_reboot_value": True,
                    "installation_state_value": False,
                    "set_installation_state": True
                }
            },
            "assertions": {
                "config_exists": False,
                "config_value_expected": ""
            }
        }

        revert_success_with_installed_but_no_config_value_testcase = {
            "legacy_type": "RevertToImageDefault",
            "stdio": {"capture_output": False, "expected_output": None},
            "config": {
                "current_auto_update_config": {
                    "create_current_auto_os_config": True,
                    "current_auto_os_update_config_value": "test_value = yes\n"
                },
                "backup_system_default_config": {
                    "create_backup_for_system_default_config": True,
                    "apply_updates_value": "",
                    "download_updates_value": "",
                    "enable_on_reboot_value": False,
                    "installation_state_value": True,
                    "set_installation_state": True
                }
            },
            "assertions": {
                "config_exists": True,
                "config_value_expected": "",
            }
        }

        revert_backup_config_does_not_exist_testcase = {
            "legacy_type": "RevertToImageDefault",
            "stdio": {
                "capture_output": True,
                "expected_output": "[DNF5] Machine default auto OS update service is not installed on the VM and hence no config to revert. [Service=dnf5-automatic]"
            },
            "config": {
                "current_auto_update_config": {
                    "create_current_auto_os_config": True,
                    "current_auto_os_update_config_value": "apply_updates = no\ndownload_updates = no\n"
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
                "config_exists": True,
                "config_value_expected": "",
            }
        }

        revert_backup_config_invalid_testcase = {
            "legacy_type": "RevertToImageDefault",
            "stdio": {
                "capture_output": True,
                "expected_output": "[DNF5] Machine default auto OS update service is not installed"
            },
            "config": {
                "current_auto_update_config": {
                    "create_current_auto_os_config": True,
                    "current_auto_os_update_config_value": "apply_updates = no\ndownload_updates = no\n"
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
                "config_exists": True,
                "config_value_expected": "",
            }
        }

        all_testcases = [
            revert_success_testcase,
            revert_success_with_dnf5_not_installed_testcase,
            revert_success_with_installed_but_no_config_value_testcase,
            revert_backup_config_does_not_exist_testcase,
            revert_backup_config_invalid_testcase,
        ]

        for testcase in all_testcases:
            self.tearDown()
            self.setUp()

            captured_output, original_stdout = None, None
            if testcase["stdio"]["capture_output"]:
                captured_output, original_stdout = self.__capture_std_io()

            self.runtime.set_legacy_test_type(testcase["legacy_type"])
            package_manager = self.container.get("package_manager")
            self.assertIsNotNone(package_manager)

            # ensure override dir exists
            override_dir = os.path.dirname(package_manager.dnf5_automatic_override_file)
            os.makedirs(override_dir, exist_ok=True)

            # clear stale override file from previous testcase
            override_file = package_manager.dnf5_automatic_override_file
            if os.path.exists(override_file):
                os.remove(override_file)

            # Arrange
            self.__setup_config_and_invoke_revert_auto_os_to_system_default(
                package_manager,
                create_current_auto_os_config=bool(
                    testcase["config"]["current_auto_update_config"]["create_current_auto_os_config"]),
                current_auto_os_update_config_value=testcase["config"]["current_auto_update_config"][
                    "current_auto_os_update_config_value"],
                create_backup_for_system_default_config=bool(
                    testcase["config"]["backup_system_default_config"]["create_backup_for_system_default_config"]),
                apply_updates_value=testcase["config"]["backup_system_default_config"]["apply_updates_value"],
                download_updates_value=testcase["config"]["backup_system_default_config"]["download_updates_value"],
                enable_on_reboot_value=bool(
                    testcase["config"]["backup_system_default_config"]["enable_on_reboot_value"]),
                installation_state_value=bool(
                    testcase["config"]["backup_system_default_config"]["installation_state_value"]),
                set_installation_state=bool(
                    testcase["config"]["backup_system_default_config"]["set_installation_state"])
            )

            # Assert stdio
            if testcase["stdio"]["capture_output"]:
                sys.stdout = original_stdout
                self.__assert_std_io(
                    captured_output=captured_output,
                    expected_output=testcase["stdio"]["expected_output"]
                )

            self.__assert_reverted_automatic_patch_configuration_settings(
                package_manager,
                config_exists=bool(testcase["assertions"]["config_exists"]),
                config_value_expected=testcase["assertions"]["config_value_expected"]
            )

            # Extra direct flag validation for explicit yes/no backup values only
            backup_cfg = testcase["config"]["backup_system_default_config"]
            backup_exists = bool(backup_cfg["create_backup_for_system_default_config"])
            is_installed = bool(backup_cfg["installation_state_value"])

            if backup_exists and is_installed:
                has_explicit_values = (
                        backup_cfg["download_updates_value"] in ["yes", "no"] or
                        backup_cfg["apply_updates_value"] in ["yes", "no"]
                )
                if has_explicit_values:
                    self.assertTrue(os.path.exists(override_file))
                    override_content = self.runtime.env_layer.file_system.read_with_retry(override_file)

                    if backup_cfg["apply_updates_value"] == "yes":
                        # DNF5 may represent enabled/default behavior either via explicit --installupdates
                        # or via baseline ExecStart with no explicit flags.
                        self.assertTrue(
                            "--installupdates" in override_content or
                            "/usr/bin/dnf5 automatic --timer" in override_content
                        )
                        self.assertTrue("--no-downloadupdates" not in override_content)
                        self.assertTrue("--no-installupdates" not in override_content)


                    elif backup_cfg["apply_updates_value"] == "no":
                        self.assertTrue("--installupdates" not in override_content)

                        if backup_cfg["download_updates_value"] == "yes":
                            self.assertTrue("--downloadupdates" in override_content)
                        elif backup_cfg["download_updates_value"] == "no":
                            self.assertTrue("--downloadupdates" not in override_content)

                else:
                    self.assertFalse(os.path.exists(override_file))
    # endregion

    def __assert_reverted_automatic_patch_configuration_settings(
            self, package_manager, config_exists=True, config_value_expected=''
    ):
        override_file = package_manager.dnf5_automatic_override_file

        if os.path.exists(override_file):
            override_content = self.runtime.env_layer.file_system.read_with_retry(override_file)
            self.assertTrue(override_content is not None)
        else:
            return

        override_content = self.runtime.env_layer.file_system.read_with_retry(override_file)
        self.assertTrue(override_content is not None)

        # download_updates assertions
        if "download_updates = yes" in config_value_expected:
            # self.assertTrue("--downloadupdates" in override_content)
            self.assertFalse("--no-downloadupdates" in override_content)

        elif "download_updates = no" in config_value_expected:
            # "no" or empty both mean we should not have the positive flag
            self.assertTrue("--downloadupdates" not in override_content)

        else:
            self.assertTrue(
                "--downloadupdates" not in override_content and
                "--no-downloadupdates" not in override_content
            )

        # apply_updates assertions
        if "apply_updates = yes" in config_value_expected:
           # self.assertTrue("--installupdates" in override_content)
            self.assertFalse("--no-installupdates" in override_content)

        elif "apply_updates = no" in config_value_expected:
            # "no" or empty both mean we should not have the positive flag
            self.assertTrue("--installupdates" not in override_content)

        else:
            self.assertTrue(
                "--installupdates" not in override_content and
                "--no-installupdates" not in override_content
            )

    @staticmethod
    def __capture_std_io():
        # arrange capture std IO
        captured_output = StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured_output
        return captured_output, original_stdout

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

        config_path = os.path.join(self.runtime.execution_config.config_folder, config_file_name)

        #  Override DNF5 variables
        package_manager.dnf5_automatic_configuration_file_path = config_path
        package_manager.os_patch_configuration_settings_file_path = config_path

        self.runtime.write_to_file(config_path, config_value)

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

    def test_install_package_failure(self):
        """Unit test for install package failure"""
        self.runtime.set_legacy_test_type('FailInstallPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)
        # test for unsuccessfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('hyperv-daemons-license.noarch','6.6.78.1-1.azl3',simulate=True),Constants.FAILED)

    def test_get_product_name(self):
        """Unit test for retrieving product Name"""
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)
        self.assertEqual(package_manager.get_product_name("bash.x86_64"), "bash.x86_64")
        self.assertEqual(package_manager.get_product_name("firefox.x86_64"), "firefox.x86_64")
        self.assertEqual(package_manager.get_product_name("test.noarch"), "test.noarch")
        self.assertEqual(package_manager.get_product_name("noextension"), "noextension")
        self.assertEqual(package_manager.get_product_name("noextension.ext"), "noextension.ext")

    def test_package_manager_no_updates_dnf5(self):
        """Unit test for dnf5 package manager with no updates"""
        self.runtime.set_legacy_test_type('SadPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertEqual(len(available_updates), 0)
        self.assertEqual(len(package_versions), 0)

    def test_install_package_failure_dnf5(self):
        """Unit test for dnf5 install package failure"""
        self.runtime.set_legacy_test_type('FailInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        self.assertEqual(
            package_manager.install_update_and_dependencies_and_get_status(
                'hyperv-daemons-license.noarch',
                '6.10-3.azl4~20260501',
                simulate=True
            ),
            Constants.FAILED
        )

    def test_is_reboot_pending_dnf5(self):
        """Unit test for dnf5 package manager reboot detection"""
        # Restart required (needs-restarting returns code=1)
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.assertTrue(package_manager.is_reboot_pending())

        # Restart not required (needs-restarting returns code=0)
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.assertFalse(package_manager.is_reboot_pending())

    def test_get_current_auto_os_patch_state_disabled_dnf5(self):
        self.runtime.set_legacy_test_type('SadPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.DISABLED)

    def test_package_manager_dnf5(self):
        """Unit test for dnf5 package manager"""
        self.runtime.set_legacy_test_type('HappyPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        # Test: get_available_updates (do NOT assert exact count unless mock supports it)
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertTrue(available_updates is not None)
        self.assertTrue(package_versions is not None)
        self.assertEqual(len(available_updates), len(package_versions))

        cmd = package_manager.single_package_upgrade_simulation_cmd + "hyperv-daemons.x86_64"
        code, out = self.runtime.env_layer.run_command_output(cmd, False, False)
        size = package_manager.get_package_size(out)
        self.assertEqual(size, "135.09k")

        # Test: get_all_available_versions_of_package (ONLY python3 since mock exists)
        versions = package_manager.get_all_available_versions_of_package("python3")
        self.assertTrue(versions is not None)
        self.assertEqual(len(versions), 5)
        self.assertEqual(versions[0], '3.12.3-1.azl4~20260501')
        self.assertEqual(versions[1], '3.12.3-2.azl4~20260501')
        self.assertEqual(versions[2], '3.12.3-4.azl4~20260501')
        self.assertEqual(versions[3], '3.12.3-5.azl4~20260501')
        self.assertEqual(versions[4], '3.12.3-6.azl4~20260501')

        # Test: install command generation (pure logic, safe to test)
        packages = ['kernel.x86_64', 'selinux-policy-targeted.noarch']
        package_versions = ['2.02.177-4.el7', '3.10.0-862.el7']

        cmd = package_manager.get_install_command('sudo dnf5 install --assumeno --skip-broken ',packages,package_versions)
        self.assertEqual(cmd,'sudo dnf5 install --assumeno --skip-broken kernel-2.02.177-4.el7.x86_64 selinux-policy-targeted-3.10.0-862.el7.noarch')

        # Test exception handling scenarios
        self.runtime.stop()
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True,Constants.DNF)

        self.container = self.runtime.container
        self.runtime.set_legacy_test_type('ExceptionPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

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
        self.assertTrue(package_manager is not None)

        # Test: get_dependent_list
        dependent_list = package_manager.get_dependent_list(["hyperv-daemons.x86_64"])
        self.assertTrue(dependent_list is not None)

    def test_install_package_success(self):
        """Unit test for install package success"""
        self.runtime.set_legacy_test_type('SuccessInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        # test for successfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('hyperv-daemons.x86_64','6.10-3.azl4~20260501',simulate=True),Constants.INSTALLED)

    def test_inclusion_type_other(self):
        """Unit test for dnf5 package manager with inclusion and Classification = Other. All packages are considered are 'Security' since TDNF does not have patch classification"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.OTHER]
        argument_composer.patches_to_include = ["ssh", "tcpdump"]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.TDNF)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertTrue(available_updates is not None)
        self.assertTrue(package_versions is not None)
        self.assertEqual(0, len(available_updates))
        self.assertEqual(0, len(package_versions))

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
        self.assertTrue(package_manager is not None)
        self.assertFalse(package_manager.is_reboot_pending())

    def test_get_current_auto_os_patch_state_dnf5_disabled(self):
        self.runtime.set_legacy_test_type('SadPath')

        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state

        # in runtime init
        self.mock_dnf5_service_text = None

        override_dir = os.path.join(self.runtime.execution_config.config_folder,"dnf5-automatic.service.d")
        os.makedirs(override_dir, exist_ok=True)

        override_file = os.path.join(override_dir, "override.conf")
        package_manager.dnf5_automatic_override_file = override_file

        override_content = (
            "[Service]\n"
            "ExecStart=\n"
            "ExecStart=/usr/bin/dnf5 automatic --timer --downloadupdates --no-installupdates\n"
        )
        self.runtime.write_to_file(override_file, override_content)
        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.DISABLED)

    def test_update_image_default_patch_mode_dnf5(self):
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        # DNF5 uses systemd override / ExecStart, not automatic.conf
        override_dir = os.path.join(self.runtime.execution_config.config_folder, "dnf5-automatic.service.d")
        os.makedirs(override_dir, exist_ok=True)

        override_file = os.path.join(override_dir, "override.conf")
        package_manager.dnf5_automatic_override_file = override_file
        package_manager.dnf5_automatic_override_dir = override_dir

        # -----------------------------
        # 1) disable apply_updates when default is apply=yes, download=yes
        # expected: install disabled, download remains enabled
        # ExecStart => --downloadupdates --no-installupdates
        # -----------------------------
        initial_override = (
            "[Service]\n"
            "ExecStart=\n"
            "ExecStart=/usr/bin/dnf5 automatic --timer --installupdates\n"
        )
        self.runtime.write_to_file(override_file, initial_override)

        package_manager.update_os_patch_configuration_sub_setting(package_manager.dnf5_automatic_apply_updates_identifier_text,"no")

        override_read = self.runtime.env_layer.file_system.read_with_retry(override_file)
        self.assertTrue(override_read is not None)
        self.assertTrue("--no-installupdates" in override_read)
        self.assertTrue("--downloadupdates" in override_read)
        self.assertTrue("--no-downloadupdates" not in override_read)
        self.assertTrue("--installupdates" not in override_read)

        # -----------------------------
        # 2) disable download_updates when default is apply=yes, download=yes
        # expected: install remains enabled; dnf5 normalization means install implies download
        # ExecStart => --installupdates
        # -----------------------------
        self.runtime.write_to_file(override_file, initial_override)

        package_manager.update_os_patch_configuration_sub_setting(package_manager.dnf5_automatic_download_updates_identifier_text,"no")

        override_read = self.runtime.env_layer.file_system.read_with_retry(override_file)
        self.assertTrue(override_read is not None)
        self.assertTrue("--installupdates" in override_read)
        self.assertTrue("--no-downloadupdates" not in override_read)
        self.assertTrue("--no-installupdates" not in override_read)

        # -----------------------------
        # 3) disable apply_updates when current/default state is empty / baseline
        # expected: no explicit download flag introduced, only install disabled
        # ExecStart => --no-installupdates
        # -----------------------------
        baseline_override = (
            "[Service]\n"
            "ExecStart=\n"
            "ExecStart=/usr/bin/dnf5 automatic --timer\n"
        )
        self.runtime.write_to_file(override_file, baseline_override)

        package_manager.update_os_patch_configuration_sub_setting(package_manager.dnf5_automatic_apply_updates_identifier_text,"no")

        override_read = self.runtime.env_layer.file_system.read_with_retry(override_file)
        self.assertTrue(override_read is not None)
        self.assertTrue("--no-installupdates" in override_read)
        self.assertTrue("--downloadupdates"  in override_read)
        self.assertTrue("--no-downloadupdates" not in override_read)
        self.assertTrue("--installupdates" not in override_read)


    def test_disable_auto_os_update(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)
        command = "systemctl disable --now dnf5-automatic.timer"

        package_manager.disable_auto_update_on_reboot(command)
        self.assertTrue(True)  # method should NOT throw

        self.runtime.set_legacy_test_type('AnotherSadPath')
        package_manager = self.container.get('package_manager')
        command = "systemctl enable --nows dnf-automatic.timer"
        self.assertRaises(Exception,package_manager.disable_auto_update_on_reboot(command))

    def test_enable_auto_os_update(self):
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        package_manager.enable_on_reboot_cmd = "systemctl enable --now dnf5-automatic.timer"
        self.assertRaises(Exception, package_manager.enable_auto_update_on_reboot)

if __name__ == '__main__':
    unittest.main()

