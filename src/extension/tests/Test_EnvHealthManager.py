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
import glob
import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime
from extension.src.Constants import Constants
from extension.src.EnvLayer import EnvLayer
from extension.src.EnvHealthManager import EnvHealthManager
from extension.src.RuntimeContextHandler import RuntimeContextHandler
from extension.src.file_handlers.CoreStateHandler import CoreStateHandler
from extension.src.EnableCommandHandler import EnableCommandHandler
from extension.src.file_handlers.ExtConfigSettingsHandler import ExtConfigSettingsHandler
from extension.src.file_handlers.ExtEnvHandler import ExtEnvHandler
from extension.src.file_handlers.ExtOutputStatusHandler import ExtOutputStatusHandler
from extension.src.file_handlers.ExtStateHandler import ExtStateHandler
from extension.src.ProcessHandler import ProcessHandler
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestEnvManager(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup TestEnvManager runner -----------------")
        # create tempdir which will have all the required files
        self.temp_dir = tempfile.mkdtemp()
        self.env_layer = EnvLayer()
        self.env_health_manager = EnvHealthManager(self.env_layer)

        # Overriding time.sleep to avoid delays in test execution
        time.sleep = self.mock_sleep

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down TestEnvManager runner -----------------")
        # delete tempdir
        shutil.rmtree(self.temp_dir)

    def mock_sleep(self, seconds):
        pass

    def test_ensure_tty_not_required_when_not_preset_in_sudoers(self):
        mock_sudoers_file_path, mock_etc_sudoers_linux_patch_extension_file_path, backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path = self.__ensure_tty_not_required_test_setup()
        # when requiretty is not present in /etc/sudoers
        mock_sudoers_content = "test"
        self.write_to_file(mock_sudoers_file_path, mock_sudoers_content)
        self.env_layer.etc_sudoers_file_path = mock_sudoers_file_path
        self.env_layer.etc_sudoers_linux_patch_extension_file_path = mock_etc_sudoers_linux_patch_extension_file_path

        self.assertFalse(self.env_layer.is_tty_required_in_sudoers())
        self.assertFalse(self.env_layer.is_tty_disabled_in_linux_patch_extension_sudoers())
        self.assertFalse(self.env_layer.is_tty_required())

        self.env_health_manager.ensure_tty_not_required()
        self.assertFalse(os.path.exists(self.env_layer.etc_sudoers_linux_patch_extension_file_path))
        # wrap up
        self.__wrap_up_ensure_tty_not_required_test(backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path)

    def test_ensure_tty_not_required_when_set_to_required_for_all_in_sudoers(self):
        mock_sudoers_file_path, mock_etc_sudoers_linux_patch_extension_file_path, backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path = self.__ensure_tty_not_required_test_setup()
        # only Defaults requiretty present in /etc/sudoers
        mock_sudoers_content = "Defaults requiretty"
        self.write_to_file(mock_sudoers_file_path, mock_sudoers_content)
        self.env_layer.etc_sudoers_file_path = mock_sudoers_file_path
        self.env_layer.etc_sudoers_linux_patch_extension_file_path = mock_etc_sudoers_linux_patch_extension_file_path

        self.assertTrue(self.env_layer.is_tty_required_in_sudoers())
        self.assertFalse(self.env_layer.is_tty_disabled_in_linux_patch_extension_sudoers())
        self.assertTrue(self.env_layer.is_tty_required())

        self.env_health_manager.ensure_tty_not_required()
        etc_sudoers_linux_patch_extension_configuration = self.env_layer.file_system.read_with_retry(self.env_layer.etc_sudoers_linux_patch_extension_file_path)
        settings = etc_sudoers_linux_patch_extension_configuration.strip().split('\n')
        self.assertTrue("Defaults:" + self.env_layer.get_current_user() + " !requiretty" in settings)
        # wrap up
        self.__wrap_up_ensure_tty_not_required_test(backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path)

    def test_ensure_tty_not_required_when_set_to_required_for_currentuser_in_sudoers(self):
        mock_sudoers_file_path, mock_etc_sudoers_linux_patch_extension_file_path, backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path = self.__ensure_tty_not_required_test_setup()
        # only Defaults:currentuser requiretty present in /etc/sudoers
        mock_sudoers_content = "Defaults:" + self.env_layer.get_current_user() + " requiretty"
        self.write_to_file(mock_sudoers_file_path, mock_sudoers_content)
        self.env_layer.etc_sudoers_file_path = mock_sudoers_file_path
        self.env_layer.etc_sudoers_linux_patch_extension_file_path = mock_etc_sudoers_linux_patch_extension_file_path

        self.assertTrue(self.env_layer.is_tty_required_in_sudoers())
        self.assertFalse(self.env_layer.is_tty_disabled_in_linux_patch_extension_sudoers())
        self.assertTrue(self.env_layer.is_tty_required())

        self.env_health_manager.ensure_tty_not_required()
        etc_sudoers_linux_patch_extension_configuration = self.env_layer.file_system.read_with_retry(self.env_layer.etc_sudoers_linux_patch_extension_file_path)
        settings = etc_sudoers_linux_patch_extension_configuration.strip().split('\n')
        self.assertTrue("Defaults:" + self.env_layer.get_current_user() + " !requiretty" in settings)
        # wrap up
        self.__wrap_up_ensure_tty_not_required_test(backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path)

    def test_ensure_tty_not_required_when_set_to_not_required_for_all_and_currentuser(self):
        mock_sudoers_file_path, mock_etc_sudoers_linux_patch_extension_file_path, backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path = self.__ensure_tty_not_required_test_setup()
        # In /etc/sudoers: Defaults !requiretty and Defaults:currentuser !requiretty
        mock_sudoers_content = "Defaults:" + self.env_layer.get_current_user() + " !requiretty" + "\n" + "Defaults !requiretty"
        self.write_to_file(mock_sudoers_file_path, mock_sudoers_content)
        self.env_layer.etc_sudoers_file_path = mock_sudoers_file_path
        self.env_layer.etc_sudoers_linux_patch_extension_file_path = mock_etc_sudoers_linux_patch_extension_file_path

        self.assertFalse(self.env_layer.is_tty_required_in_sudoers())
        self.assertFalse(self.env_layer.is_tty_disabled_in_linux_patch_extension_sudoers())
        self.assertFalse(self.env_layer.is_tty_required())

        self.env_health_manager.ensure_tty_not_required()
        self.assertFalse(os.path.exists(self.env_layer.etc_sudoers_linux_patch_extension_file_path))
        # wrap up
        self.__wrap_up_ensure_tty_not_required_test(backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path)

    def test_ensure_tty_not_required_when_set_to_required_for_currentuser_and_not_required_for_all(self):
        mock_sudoers_file_path, mock_etc_sudoers_linux_patch_extension_file_path, backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path = self.__ensure_tty_not_required_test_setup()
        # In /etc/sudoers: Defaults:currentuser requiretty and Defaults !requiretty
        mock_sudoers_content = "Defaults:" + self.env_layer.get_current_user() + " requiretty" + "\n" + "Defaults !requiretty"
        self.write_to_file(mock_sudoers_file_path, mock_sudoers_content)
        self.env_layer.etc_sudoers_file_path = mock_sudoers_file_path
        self.env_layer.etc_sudoers_linux_patch_extension_file_path = mock_etc_sudoers_linux_patch_extension_file_path

        self.assertFalse(self.env_layer.is_tty_required_in_sudoers())
        self.assertFalse(self.env_layer.is_tty_disabled_in_linux_patch_extension_sudoers())
        self.assertFalse(self.env_layer.is_tty_required())

        self.env_health_manager.ensure_tty_not_required()
        self.assertFalse(os.path.exists(self.env_layer.etc_sudoers_linux_patch_extension_file_path))
        # wrap up
        self.__wrap_up_ensure_tty_not_required_test(backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path)

    def test_ensure_tty_not_required_when_set_to_not_required_for_all_and_required_for_currentuser(self):
        mock_sudoers_file_path, mock_etc_sudoers_linux_patch_extension_file_path, backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path = self.__ensure_tty_not_required_test_setup()
        # In /etc/sudoers: Defaults !requiretty and Defaults:currentuser requiretty
        mock_sudoers_content = "Defaults !requiretty" + "\n" + "Defaults:" + self.env_layer.get_current_user() + " requiretty"
        self.write_to_file(mock_sudoers_file_path, mock_sudoers_content)
        self.env_layer.etc_sudoers_file_path = mock_sudoers_file_path
        self.env_layer.etc_sudoers_linux_patch_extension_file_path = mock_etc_sudoers_linux_patch_extension_file_path

        self.assertTrue(self.env_layer.is_tty_required_in_sudoers())
        self.assertFalse(self.env_layer.is_tty_disabled_in_linux_patch_extension_sudoers())
        self.assertTrue(self.env_layer.is_tty_required())

        self.env_health_manager.ensure_tty_not_required()
        etc_sudoers_linux_patch_extension_configuration = self.env_layer.file_system.read_with_retry(self.env_layer.etc_sudoers_linux_patch_extension_file_path)
        settings = etc_sudoers_linux_patch_extension_configuration.strip().split('\n')
        self.assertTrue("Defaults:" + self.env_layer.get_current_user() + " !requiretty" in settings)
        # wrap up
        self.__wrap_up_ensure_tty_not_required_test(backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path)

    def test_ensure_tty_not_required_when_set_to_required_for_all_and_not_required_for_currentuser(self):
        mock_sudoers_file_path, mock_etc_sudoers_linux_patch_extension_file_path, backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path = self.__ensure_tty_not_required_test_setup()
        # In /etc/sudoers: Defaults requiretty and Defaults:currentuser !requiretty
        mock_sudoers_content = "Defaults requiretty" + "\n" + "Defaults:" + self.env_layer.get_current_user() + " !requiretty"
        self.write_to_file(mock_sudoers_file_path, mock_sudoers_content)
        self.env_layer.etc_sudoers_file_path = mock_sudoers_file_path
        self.env_layer.etc_sudoers_linux_patch_extension_file_path = mock_etc_sudoers_linux_patch_extension_file_path

        self.assertFalse(self.env_layer.is_tty_required_in_sudoers())
        self.assertFalse(self.env_layer.is_tty_disabled_in_linux_patch_extension_sudoers())
        self.assertFalse(self.env_layer.is_tty_required())

        self.env_health_manager.ensure_tty_not_required()
        self.assertFalse(os.path.exists(self.env_layer.etc_sudoers_linux_patch_extension_file_path))
        # wrap up
        self.__wrap_up_ensure_tty_not_required_test(backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path)

    def test_ensure_tty_not_required_when_tty_set_to_required_in_default_sudoers_and_tty_set_to_not_required_in_custom_sudoers_file_for_extension(self):
        mock_sudoers_file_path, mock_etc_sudoers_linux_patch_extension_file_path, backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path = self.__ensure_tty_not_required_test_setup()
        # Defaults set to required and /etc/sudoers.d/linuxpatchextension already set
        mock_sudoers_content = "Defaults requiretty" + "\n" + "Defaults:" + self.env_layer.get_current_user() + " requiretty"
        self.write_to_file(mock_sudoers_file_path, mock_sudoers_content)
        self.env_layer.etc_sudoers_file_path = mock_sudoers_file_path
        mock_etc_sudoers_linux_patch_extension_content = "Defaults:" + self.env_layer.get_current_user() + " !requiretty" + "\n"
        self.write_to_file(mock_etc_sudoers_linux_patch_extension_file_path, mock_etc_sudoers_linux_patch_extension_content)
        self.env_layer.etc_sudoers_linux_patch_extension_file_path = mock_etc_sudoers_linux_patch_extension_file_path

        self.assertTrue(self.env_layer.is_tty_required_in_sudoers())
        self.assertTrue(self.env_layer.is_tty_disabled_in_linux_patch_extension_sudoers())
        self.assertFalse(self.env_layer.is_tty_required())

        self.env_health_manager.ensure_tty_not_required()
        etc_sudoers_linux_patch_extension_configuration = self.env_layer.file_system.read_with_retry(self.env_layer.etc_sudoers_linux_patch_extension_file_path)
        settings = etc_sudoers_linux_patch_extension_configuration.strip().split('\n')
        self.assertTrue("Defaults:" + self.env_layer.get_current_user() + " !requiretty" in settings)
        # wrap up
        self.__wrap_up_ensure_tty_not_required_test(backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path)

    def test_read_with_retry_fail(self):
        open = None
        has_error = False
        try:
            self.env_layer.file_system.read_with_retry(self.env_layer.etc_sudoers_linux_patch_extension_file_path)
        except Exception as error:
            has_error = True

        self.assertTrue(has_error)

    def test_write_with_retry_fail(self):
        self.env_layer.file_system.open = lambda file_path, mode: None
        has_error = False
        try:
            self.env_layer.file_system.write_with_retry(self.env_layer.etc_sudoers_linux_patch_extension_file_path, "test")
        except Exception as error:
            has_error = True
            
        self.assertTrue(has_error)

    def __ensure_tty_not_required_test_setup(self):
        mock_sudoers_file_path = os.path.join(self.temp_dir, "etc-sudoers")
        backup_etc_sudoers_file_path = self.env_layer.etc_sudoers_file_path
        mock_etc_sudoers_linux_patch_extension_file_path = os.path.join(self.temp_dir, "etc-sudoers.d-linuxpatchextension")
        backup_etc_sudoers_linux_patch_extension_file_path = self.env_layer.etc_sudoers_linux_patch_extension_file_path

        return mock_sudoers_file_path, mock_etc_sudoers_linux_patch_extension_file_path, backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path

    def __wrap_up_ensure_tty_not_required_test(self, backup_etc_sudoers_file_path, backup_etc_sudoers_linux_patch_extension_file_path):
        self.env_layer.etc_sudoers_file_path = backup_etc_sudoers_file_path
        self.env_layer.etc_sudoers_linux_patch_extension_file_path = backup_etc_sudoers_linux_patch_extension_file_path

    @staticmethod
    def write_to_file(path, data):
        with open(path, "w+") as file_handle:
            file_handle.write(data)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestEnvManager)
    unittest.TextTestRunner(verbosity=2).run(SUITE)