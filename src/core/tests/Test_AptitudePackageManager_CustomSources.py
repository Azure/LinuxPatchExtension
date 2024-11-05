# Copyright 2024 Microsoft Corporation
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
import shutil
import unittest
from os import makedirs

from core.src.bootstrap.Constants import Constants
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.tests.Test_UbuntuProClient import MockVersionResult, MockRebootRequiredResult, MockUpdatesResult
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.LegacyEnvLayerExtensions import LegacyEnvLayerExtensions
from core.tests.library.RuntimeCompositor import RuntimeCompositor
from core.src.package_managers import AptitudePackageManager, UbuntuProClient


class TestAptitudePackageManager_CustomSource(unittest.TestCase):
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

    def test_sources_list_and_parts_combinations(self):
        # EULA accepted in settings and commands updated accordingly
        self.__lib_test_custom_sources_with(include_sources_list=True)

    def __lib_test_custom_sources_with(self, include_sources_list=True, include_source_parts_list=True, include_source_parts_debstyle=True):
        mock_sources_path = self.__prep_scratch_with_sources(include_sources_list, include_source_parts_list, include_source_parts_debstyle)

        package_manager = AptitudePackageManager.AptitudePackageManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.status_handler)
        self.__adapt_package_manager_for_mock_sources(package_manager, mock_sources_path)

        sources_dir, sources_list = package_manager._AptitudePackageManager__get_custom_sources_to_spec("20240401T160000Z", "Security")

        self.__clear_mock_sources_path(mock_sources_path)

    def __prep_scratch_with_sources(self, include_sources_list=True, include_source_parts_list=True, include_source_parts_debstyle=True):
        # type: (bool, bool, bool) -> str
        timestamp = self.runtime.env_layer.datetime.timestamp().replace(":", ".")
        mock_sources_path = os.path.join(self.runtime.scratch_path, "apt-src-" + timestamp)
        os.makedirs(mock_sources_path)
        os.makedirs(os.path.join(mock_sources_path, "sources.list.d"))

        if include_sources_list:
            self.runtime.env_layer.file_system.write_with_retry(os.path.join(mock_sources_path, "sources.list"),
                                                                data=self.__get_sources_data_one_line_style_def(), mode="w")
        if include_source_parts_list:
            self.runtime.env_layer.file_system.write_with_retry(os.path.join(mock_sources_path, "sources.list.d", "azgps-src.list"),
                                                                data=self.__get_sources_data_one_line_style_ext(), mode="w")
        if include_source_parts_debstyle:
            self.runtime.env_layer.file_system.write_with_retry(os.path.join(mock_sources_path, "sources.list.d", "azgps-src.sources"),
                                                                data=self.__get_sources_data_debstyle(), mode="w")

        return mock_sources_path

    @staticmethod
    def __clear_mock_sources_path(mock_sources_path):
        # type: (str) -> None
        shutil.rmtree(mock_sources_path)

    @staticmethod
    def __adapt_package_manager_for_mock_sources(package_manager, mock_sources_path):
        package_manager.APT_SOURCES_LIST_PATH = os.path.join(mock_sources_path, "sources.list")
        package_manager.APT_SOURCES_LIST_DIR_PATH = os.path.join(mock_sources_path, "sources.list.d")

    @staticmethod
    def __get_sources_data_one_line_style_def():
        return "deb http://azure.archive.ubuntu.com/ubuntu/ focal-security main restricted\n" + \
                "deb http://azure.archive.ubuntu.com/ubuntu/ focal-security universe\n" + \
                "deb http://azure.archive.ubuntu.com/ubuntu/ focal-security multiverse\n"

    @staticmethod
    def __get_sources_data_one_line_style_ext():
        return "deb http://us.archive.ubuntu.com/ubuntu/ focal-backports main restricted universe multiverse\n" + \
                "deb http://in.archive.ubuntu.com/ubuntu/ focal multiverse\n"

    @staticmethod
    def __get_sources_data_debstyle():
        return "## See the sources.list(5) manual page for further settings. \n" + \
                "Types: deb \n" + \
                "URIs: http://azure.archive.ubuntu.com/ubuntu/ \n" + \
                "Suites: noble noble-updates noble-backports \n" + \
                "Components: main universe restricted multiverse \n" + \
                "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg \n" + \
                "\n" + \
                "## Ubuntu security updates. Aside from URIs and Suites, \n" + \
                "## this should mirror your choices in the previous section. \n" + \
                "Types: deb \n" + \
                "URIs: http://azure.archive.ubuntu.com/ubuntu/ \n" + \
                "Suites: noble-security \n" + \
                "Components: main universe restricted multiverse \n" + \
                "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg \n"

if __name__ == '__main__':
    unittest.main()
