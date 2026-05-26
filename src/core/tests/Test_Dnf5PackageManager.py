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

if __name__ == '__main__':
    unittest.main()

