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
import imp
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
    def __init__(self, version='27.13.5~18.04.1'):
        self.installed_version = version

    def mock_version(self):
        return MockVersionResult()

    def mock_version_raise_exception(self):
        raise

    def mock_import_uaclient_version_module(self, mock_name, method_name):
        if sys.version_info[0] == 3:
            sys.modules['uaclient.api.u.pro.version.v1'] = types.ModuleType('version_module')
            mock_method = getattr(self, method_name)
            setattr(sys.modules['uaclient.api.u.pro.version.v1'], mock_name, mock_method)
        else:
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


class TestUbuntuProClient(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.APT)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def mock_run_command_output_raise_exception(self, cmd="", output=False, chk_err=False):
        raise

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

    def test_is_pro_working_failure(self):
        obj = MockVersionResult()
        obj.mock_import_uaclient_version_module('version', 'mock_version_raise_exception')

        package_manager = self.container.get('package_manager')
        self.assertFalse(package_manager.ubuntu_pro_client.is_pro_working())

        obj.mock_unimport_uaclient_version_module()

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

    def test_get_security_updates_is_None(self):
        package_manager = self.container.get('package_manager')
        self.assertIsNone(package_manager.ubuntu_pro_client.get_security_updates())

    def test_get_all_updates_is_None(self):
        package_manager = self.container.get('package_manager')
        self.assertIsNone(package_manager.ubuntu_pro_client.get_all_updates())

    def test_get_other_updates_is_None(self):
        package_manager = self.container.get('package_manager')
        self.assertIsNone(package_manager.ubuntu_pro_client.get_other_updates())


if __name__ == '__main__':
    unittest.main()
