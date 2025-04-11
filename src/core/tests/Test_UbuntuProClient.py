# Copyright 2023 Microsoft Corporation
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
import sys
import types
import unittest

from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class MockSystemModules:
    def assign_sys_modules_with_mock_module(self, module_name, mock_module):
        # In this function, we are mocking the pro module. In Python 2, a module is checked before loading the submodule.
        # But Python3, sys.modules support the check for full string in one go (like a dictionary).
        # e.g., for module 'uaclient.api.u.pro.version.v1', in python 2, we need to mock import uaclient, uaclient.api, ... until the full string.
        # for python 3, only mocking the full string will suffice.
        # So, this function will be used when python2 is used to mock all the submodules.
        parts = module_name.split('.')
        for i in range(len(parts)):
            sub_module = ".".join(parts[:i + 1])
            sys.modules[sub_module] = mock_module

    def mock_unimport_module(self, module_name):
        # For unimport, in python3, it's just resetting the "module_name" value in the sys.modules dictionary to empty.
        # For python2, just resetting the first level will do. But for safety, we reset the whole submodules too.
        if sys.version_info[0] == 3:
            sys.modules[module_name] = ''
        else:
            self.assign_sys_modules_with_mock_module(module_name, '')


class MockVersionResult(MockSystemModules):
    def __init__(self, version='27.14.4~18.04.1'):
        self.installed_version = version

    def mock_version(self):
        return MockVersionResult()

    def mock_to_below_minimum_version(self):
        return MockVersionResult('27.13.4~18.04.1')

    def mock_version_raise_exception(self):
        raise

    def mock_pro_version(self):
        return MockVersionResult("34~18.004.01")

    def mock_import_uaclient_version_module(self, mock_name, method_name):
        if sys.version_info[0] == 3:
            sys.modules['uaclient.api.u.pro.version.v1'] = types.ModuleType('version_module')
            mock_method = getattr(self, method_name)
            setattr(sys.modules['uaclient.api.u.pro.version.v1'], mock_name, mock_method)
        else:   # Python 2 only
            import imp
            version_module = imp.new_module('version_module')
            mock_method = getattr(self, method_name)
            setattr(version_module, mock_name, mock_method)
            self.assign_sys_modules_with_mock_module('uaclient.api.u.pro.version.v1', version_module)

    def mock_unimport_uaclient_version_module(self):
        self.mock_unimport_module('uaclient.api.u.pro.version.v1')


class MockRebootRequiredResult(MockSystemModules):
    def __init__(self, reboot_required="yes"):
        self.reboot_required = reboot_required

    def mock_reboot_required_return_yes(self):
        return MockRebootRequiredResult()

    def mock_reboot_required_return_no(self):
        return MockRebootRequiredResult("no")

    def mock_reboot_required_raises_exception(self):
        raise

    def mock_import_uaclient_reboot_required_module(self, mock_name, method_name):
        if sys.version_info[0] == 3:
            sys.modules['uaclient.api.u.pro.security.status.reboot_required.v1'] = types.ModuleType('reboot_module')
            mock_method = getattr(self, method_name)
            setattr(sys.modules['uaclient.api.u.pro.security.status.reboot_required.v1'], mock_name, mock_method)
        else:
            reboot_module = imp.new_module('reboot_module')
            mock_method = getattr(self, method_name)
            setattr(reboot_module, mock_name, mock_method)
            self.assign_sys_modules_with_mock_module('uaclient.api.u.pro.security.status.reboot_required.v1', reboot_module)

    def mock_unimport_uaclient_reboot_required_module(self):
        self.mock_unimport_module('uaclient.api.u.pro.security.status.reboot_required.v1')


class UpdateInfo:
    def __init__(self, package, version, provided_by, origin):
        self.version = version
        self.provided_by = provided_by
        self.package = package
        self.origin = origin


class MockUpdatesResult(MockSystemModules):

    def __init__(self, updates = []):
        self.updates = updates

    def mock_update_list_with_all_update_types(self):
        return MockUpdatesResult(self.get_mock_updates_list_with_three_updates())

    def mock_update_list_with_one_esm_update(self):
        return MockUpdatesResult(self.get_mock_updates_list_with_one_esm_update())

    @staticmethod
    def get_mock_updates_list_with_three_updates():
        return [UpdateInfo(package='python3', provided_by='standard-security', origin='security.ubuntu.com', version='1.2.3-1ubuntu0.3'),
                UpdateInfo(package='apt', provided_by='standard-updates', origin='security.ubuntu.com', version='1.2.35'),
                UpdateInfo(package='cups', provided_by='esm-infra', origin='security.ubuntu.com', version='2.1.3-4ubuntu0.11+esm1')]

    @staticmethod
    def get_mock_updates_list_with_one_esm_update():
        return [UpdateInfo(package='git-man', provided_by='esm-infra', origin='security.ubuntu.com', version='1:2.17.1-1ubuntu0.15')]

    def mock_import_uaclient_update_module(self, mock_name, method_name):
        if sys.version_info[0] == 3:
            sys.modules['uaclient.api.u.pro.packages.updates.v1'] = types.ModuleType('update_module')
            mock_method = getattr(self, method_name)
            setattr(sys.modules['uaclient.api.u.pro.packages.updates.v1'], mock_name, mock_method)
        else:
            update_module = imp.new_module('update_module')
            mock_method = getattr(self, method_name)
            setattr(update_module, mock_name, mock_method)
            self.assign_sys_modules_with_mock_module('uaclient.api.u.pro.packages.updates.v1', update_module)

    def mock_unimport_uaclient_update_module(self):
        self.mock_unimport_module('uaclient.api.u.pro.packages.updates.v1')


class TestUbuntuProClient(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.APT)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def mock_run_command_output_raise_exception(self, cmd="", output=False, chk_err=False):
        raise Exception

    def mock_get_ubuntu_pro_client_updates_raise_exception(self):
        raise Exception

    def test_install_or_update_pro_success(self):
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager.ubuntu_pro_client.install_or_update_pro())

    def test_install_or_update_pro_failure(self):
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertFalse(package_manager.ubuntu_pro_client.install_or_update_pro())

    def test_install_or_update_pro_exception(self):
        package_manager = self.container.get('package_manager')
        backup_run_command_output = package_manager.env_layer.run_command_output
        package_manager.env_layer.run_command_output = self.mock_run_command_output_raise_exception

        self.assertFalse(package_manager.ubuntu_pro_client.install_or_update_pro())

        package_manager.env_layer.run_command_output = backup_run_command_output

    def test_is_pro_working_success(self):
        obj = MockVersionResult()
        obj.mock_import_uaclient_version_module('version', 'mock_version')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager.ubuntu_pro_client.is_pro_working())

        obj.mock_unimport_uaclient_version_module()

    def test_is_actual_pro_version_working_success(self):
        obj = MockVersionResult()
        obj.mock_import_uaclient_version_module('version', 'mock_pro_version')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager.ubuntu_pro_client.is_pro_working())

        obj.mock_unimport_uaclient_version_module()

    def test_is_pro_working_failure_when_minimum_version_required_is_false(self):
        obj = MockVersionResult()
        obj.mock_import_uaclient_version_module('version', 'mock_to_below_minimum_version')

        package_manager = self.container.get('package_manager')
        self.assertFalse(package_manager.ubuntu_pro_client.is_pro_working())

        obj.mock_unimport_uaclient_version_module()

    def test_is_pro_working_failure(self):
        obj = MockVersionResult()
        obj.mock_import_uaclient_version_module('version', 'mock_version_raise_exception')

        package_manager = self.container.get('package_manager')
        self.assertFalse(package_manager.ubuntu_pro_client.is_pro_working())

        obj.mock_unimport_uaclient_version_module()

    def test_log_ubuntu_pro_client_attached_true(self):
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager.ubuntu_pro_client.log_ubuntu_pro_client_attached())

    def test_log_ubuntu_pro_client_attached_false(self):
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertFalse(package_manager.ubuntu_pro_client.log_ubuntu_pro_client_attached())

    def test_log_ubuntu_pro_client_attached_raises_exception(self):
        package_manager = self.container.get('package_manager')
        backup_run_command_output = package_manager.env_layer.run_command_output
        package_manager.env_layer.run_command_output = self.mock_run_command_output_raise_exception

        self.assertFalse(package_manager.ubuntu_pro_client.log_ubuntu_pro_client_attached())

        package_manager.env_layer.run_command_output = backup_run_command_output

    def test_extract_packages_and_versions_returns_zero_for_empty_updates(self):
        package_manager = self.container.get('package_manager')
        empty_updates = []
        updates, version = package_manager.ubuntu_pro_client.extract_packages_and_versions(empty_updates)
        self.assertTrue(len(updates) == 0)
        self.assertTrue(len(version) == 0)

    def test_extract_packages_and_versions_returns_correct_number_of_updates(self):
        package_manager = self.container.get('package_manager')
        mock_updates = MockUpdatesResult.get_mock_updates_list_with_three_updates()
        updates, versions = package_manager.ubuntu_pro_client.extract_packages_and_versions(mock_updates)
        self.assertTrue(len(updates) == len(mock_updates))
        self.assertTrue(len(versions) == len(mock_updates))

    def test_extract_packages_and_versions_returns_correct_esm_package_count(self):
        package_manager = self.container.get('package_manager')
        mock_updates = MockUpdatesResult.get_mock_updates_list_with_three_updates()
        updates, versions = package_manager.ubuntu_pro_client.extract_packages_and_versions(mock_updates)
        expected_count = 0
        actual_count = 0
        for update in mock_updates:
            if update.provided_by == 'esm-infra':
                expected_count += 1

        for version in versions:
            if version == Constants.UA_ESM_REQUIRED:
                actual_count += 1

        self.assertEqual(expected_count, actual_count)

    def test_is_reboot_pending_success(self):
        obj = MockRebootRequiredResult()
        obj.mock_import_uaclient_reboot_required_module('reboot_required', 'mock_reboot_required_return_yes')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager.ubuntu_pro_client.is_reboot_pending()[0])
        self.assertTrue(package_manager.ubuntu_pro_client.is_reboot_pending()[1])

        obj.mock_unimport_uaclient_reboot_required_module()

    def test_is_reboot_pending_failure(self):
        obj = MockRebootRequiredResult()
        obj.mock_import_uaclient_reboot_required_module('reboot_required', 'mock_reboot_required_return_no')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager.ubuntu_pro_client.is_reboot_pending()[0])
        self.assertFalse(package_manager.ubuntu_pro_client.is_reboot_pending()[1])

        obj.mock_unimport_uaclient_reboot_required_module()

    def test_is_reboot_pending_exception(self):
        obj = MockRebootRequiredResult()
        obj.mock_import_uaclient_reboot_required_module('reboot_required', 'mock_reboot_required_raises_exception')

        package_manager = self.container.get('package_manager')
        self.assertFalse(package_manager.ubuntu_pro_client.is_reboot_pending()[0])
        self.assertFalse(package_manager.ubuntu_pro_client.is_reboot_pending()[1])

        obj.mock_unimport_uaclient_reboot_required_module()

    def test_get_security_updates_success(self):
        obj = MockUpdatesResult()
        obj.mock_import_uaclient_update_module('updates', 'mock_update_list_with_all_update_types')
        package_manager = self.container.get('package_manager')

        query_success, updates, versions = package_manager.ubuntu_pro_client.get_security_updates()

        self.assertTrue(query_success)
        self.assertEqual(len(updates), 1)
        self.assertEqual(len(versions), 1)

        obj.mock_unimport_uaclient_update_module()

    def test_get_security_updates_exception(self):
        obj = MockUpdatesResult()
        obj.mock_import_uaclient_update_module('updates', 'mock_update_list_with_all_update_types')
        package_manager = self.container.get('package_manager')
        backup_get_ubuntu_pro_client_updates = package_manager.ubuntu_pro_client.get_ubuntu_pro_client_updates
        package_manager.ubuntu_pro_client.get_ubuntu_pro_client_updates = self.mock_get_ubuntu_pro_client_updates_raise_exception

        query_success, updates, versions = package_manager.ubuntu_pro_client.get_security_updates()
        self.assertFalse(query_success)
        self.assertEqual(len(updates), 0)
        self.assertEqual(len(versions), 0)

        package_manager.ubuntu_pro_client.get_ubuntu_pro_client_updates = backup_get_ubuntu_pro_client_updates
        obj.mock_unimport_uaclient_update_module()

    def test_get_security_esm_updates_success(self):
        obj = MockUpdatesResult()
        obj.mock_import_uaclient_update_module('updates', 'mock_update_list_with_all_update_types')
        package_manager = self.container.get('package_manager')

        query_success, updates, versions = package_manager.ubuntu_pro_client.get_security_esm_updates()

        self.assertTrue(query_success)
        self.assertEqual(len(updates), 1)
        self.assertEqual(len(versions), 1)
        obj.mock_unimport_uaclient_update_module()

    def test_get_security_esm_updates_exception(self):
        obj = MockUpdatesResult()
        obj.mock_import_uaclient_update_module('updates', 'mock_update_list_with_all_update_types')
        package_manager = self.container.get('package_manager')
        backup_get_ubuntu_pro_client_updates = package_manager.ubuntu_pro_client.get_ubuntu_pro_client_updates
        package_manager.ubuntu_pro_client.get_ubuntu_pro_client_updates = self.mock_get_ubuntu_pro_client_updates_raise_exception

        query_success, updates, versions = package_manager.ubuntu_pro_client.get_security_esm_updates()
        self.assertFalse(query_success)
        self.assertEqual(len(updates), 0)
        self.assertEqual(len(versions), 0)

        package_manager.ubuntu_pro_client.get_ubuntu_pro_client_updates = backup_get_ubuntu_pro_client_updates
        obj.mock_unimport_uaclient_update_module()

    def test_get_all_updates_success(self):
        obj = MockUpdatesResult()
        obj.mock_import_uaclient_update_module('updates', 'mock_update_list_with_all_update_types')
        package_manager = self.container.get('package_manager')

        query_success, updates, versions = package_manager.ubuntu_pro_client.get_all_updates()

        self.assertTrue(query_success)
        self.assertEqual(len(updates), 3)
        self.assertEqual(len(versions), 3)

        obj.mock_unimport_uaclient_update_module()

    def test_get_all_updates_exception(self):
        obj = MockUpdatesResult()
        obj.mock_import_uaclient_update_module('updates', 'mock_update_list_with_all_update_types')
        package_manager = self.container.get('package_manager')
        backup_get_ubuntu_pro_client_updates = package_manager.ubuntu_pro_client.get_ubuntu_pro_client_updates
        package_manager.ubuntu_pro_client.get_ubuntu_pro_client_updates = self.mock_get_ubuntu_pro_client_updates_raise_exception

        query_success, updates, versions = package_manager.ubuntu_pro_client.get_all_updates()
        self.assertFalse(query_success)
        self.assertEqual(len(updates), 0)
        self.assertEqual(len(versions), 0)

        package_manager.ubuntu_pro_client.get_ubuntu_pro_client_updates = backup_get_ubuntu_pro_client_updates
        obj.mock_unimport_uaclient_update_module()

    def test_get_other_updates_success(self):
        obj = MockUpdatesResult()
        obj.mock_import_uaclient_update_module('updates', 'mock_update_list_with_all_update_types')
        package_manager = self.container.get('package_manager')

        query_success, updates, versions = package_manager.ubuntu_pro_client.get_other_updates()

        self.assertTrue(query_success)
        self.assertEqual(len(updates), 1)
        self.assertEqual(len(versions), 1)

        obj.mock_unimport_uaclient_update_module()

    def test_get_other_updates_exception(self):
        obj = MockUpdatesResult()
        obj.mock_import_uaclient_update_module('updates', 'mock_update_list_with_all_update_types')
        package_manager = self.container.get('package_manager')
        backup_get_ubuntu_pro_client_updates = package_manager.ubuntu_pro_client.get_ubuntu_pro_client_updates
        package_manager.ubuntu_pro_client.get_ubuntu_pro_client_updates = self.mock_get_ubuntu_pro_client_updates_raise_exception

        query_success, updates, versions = package_manager.ubuntu_pro_client.get_other_updates()
        self.assertFalse(query_success)
        self.assertEqual(len(updates), 0)
        self.assertEqual(len(versions), 0)

        package_manager.ubuntu_pro_client.get_ubuntu_pro_client_updates = backup_get_ubuntu_pro_client_updates
        obj.mock_unimport_uaclient_update_module()

if __name__ == '__main__':
    unittest.main()
