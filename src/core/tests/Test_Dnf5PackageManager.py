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
import unittest

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

    def test_refresh_repo(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_manager.refresh_repo_safely()

    def test_disable_auto_os_updates_with_uninstalled_services(self):
        """Test disable_auto_os_update when dnf5-automatic is not installed"""
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')

        # Should complete without error even when service is not installed
        package_manager.disable_auto_os_update()

    def test_get_current_auto_os_patch_state_with_uninstalled_services(self):
        """Test get_current_auto_os_patch_state when dnf5-automatic is not installed"""
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')

        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.DISABLED)

    def test_get_current_auto_os_patch_state_with_installed_services_and_state_enabled(self):
        """Test get_current_auto_os_patch_state for DNF when service is installed and enabled"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state

        # Mock the systemctl cat output with enabled flags
        systemctl_cat_output = '''[Unit]
                                Description=Run dnf5 automatic updates
                                After=network-online.target
                            
                                [Timer]
                                OnBootSec=1h
                                OnUnitActiveSec=24h
                                AccuracySec=1h
                                Persistent=true
                            
                                [Install]
                                WantedBy=timers.target
                            
                                [Service]
                                Type=oneshot
                                ExecStart=/usr/bin/dnf5 automatic --timer
                                StandardOutput=journal
                                StandardError=journal
                                '''

        # Mock the run_command_output for systemctl cat
        backup_run_command_output = self.runtime.env_layer.run_command_output

        def mock_systemctl_cat(cmd, no_output=False, chk_err=False):
            if 'rpm -qa | grep dnf5-plugin-automatic' in cmd:
                return 0, 'dnf5-plugin-automatic-xyz'

                # Mock timer enabled
            elif 'systemctl is-enabled dnf5-automatic.timer' in cmd:
                return 0, 'enabled'

                # Mock service file
            elif 'systemctl cat dnf5-automatic' in cmd:
                return 0, systemctl_cat_output

            return backup_run_command_output(cmd, no_output, chk_err)

        self.runtime.env_layer.run_command_output = mock_systemctl_cat

        try:
            current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()
            self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.ENABLED)
        finally:
            self.runtime.env_layer.run_command_output = backup_run_command_output

    def test_get_current_auto_os_patch_state_with_installed_services_and_state_disabled(self):
        """Test get_current_auto_os_patch_state when dnf5-automatic is installed but disabled"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        # Restore original implementation so package manager logic (rpm + systemctl checks) runs
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state

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
        self.assertTrue(True)  # If no exception, test passes

    def test_revert_auto_os_update_to_system_default_with_enable_on_reboot_true(self):
        """Test revert when service should be enabled on reboot"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')

        # Create backup with service marked as installed and should be enabled on reboot
        package_manager.image_default_patch_configuration_backup_path = os.path.join(self.runtime.execution_config.config_folder, Constants.IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH)
        backup_config = {
            "dnf5-automatic": {
                "enable_on_reboot": True,
                "installation_state": True
            }
        }
        self.runtime.write_to_file(package_manager.image_default_patch_configuration_backup_path, json.dumps(backup_config))

        # Mock run_command_output to simulate service installed and systemctl commands working
        backup_run_command_output = self.runtime.env_layer.run_command_output

        def mock_commands(cmd, no_output=False, chk_err=False):
            if 'rpm -qa | grep dnf5-plugin-automatic' in cmd:
                return 0, 'dnf5-plugin-automatic-xyz'
            elif 'systemctl is-enabled dnf5-automatic.timer' in cmd:
                return 0, 'disabled'  # Currently disabled, will be enabled by revert
            elif 'systemctl enable --now dnf5-automatic.timer' in cmd:
                return 0, ''  # Enable succeeds
            elif 'systemctl cat dnf5-automatic' in cmd:
                return 0, '[Service]\nExecStart=/usr/bin/dnf5 automatic --timer\n'
            return backup_run_command_output(cmd, no_output, chk_err)

        self.runtime.env_layer.run_command_output = mock_commands

        try:
            package_manager.revert_auto_os_update_to_system_default()
            # Verify it completed without error
            self.assertTrue(True)
        finally:
            self.runtime.env_layer.run_command_output = backup_run_command_output

    def test_revert_auto_os_update_to_system_default_with_enable_on_reboot_false(self):
        """Test revert when service should be disabled on reboot"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')

        # Create backup with service marked as installed but should be disabled on reboot
        package_manager.image_default_patch_configuration_backup_path = os.path.join(self.runtime.execution_config.config_folder, Constants.IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH)
        backup_config = {
            "dnf5-automatic": {
                "enable_on_reboot": False,
                "installation_state": True
            }
        }
        self.runtime.write_to_file(package_manager.image_default_patch_configuration_backup_path, json.dumps(backup_config))

        # Mock run_command_output to simulate service installed but currently enabled
        backup_run_command_output = self.runtime.env_layer.run_command_output

        def mock_commands(cmd, no_output=False, chk_err=False):
            if 'rpm -qa | grep dnf5-plugin-automatic' in cmd:
                return 0, 'dnf5-plugin-automatic-xyz'
            elif 'systemctl is-enabled dnf5-automatic.timer' in cmd:
                return 0, 'enabled'  # Currently enabled, will be disabled by revert
            elif 'systemctl disable --now dnf5-automatic.timer' in cmd:
                return 0, ''  # Disable succeeds
            elif 'systemctl cat dnf5-automatic' in cmd:
                return 0, '[Service]\nExecStart=/usr/bin/dnf5 automatic --timer\n'
            return backup_run_command_output(cmd, no_output, chk_err)

        self.runtime.env_layer.run_command_output = mock_commands

        try:
            package_manager.revert_auto_os_update_to_system_default()
            # Verify it completed without error
            self.assertTrue(True)
        finally:
            self.runtime.env_layer.run_command_output = backup_run_command_output


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

        # Test: get_package_size (using EXISTING install mock)
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

        # Test: get_dependent_list
        dependent_list = package_manager.get_dependent_list(["hyperv-daemons.x86_64"])
        self.assertTrue(dependent_list is not None)

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


if __name__ == '__main__':
    unittest.main()

