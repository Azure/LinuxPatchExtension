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
import os
import shutil
import time
import unittest
from unittest import expectedFailure

from core.src.bootstrap.Constants import Constants
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.LegacyEnvLayerExtensions import LegacyEnvLayerExtensions
from core.tests.library.RuntimeCompositor import RuntimeCompositor
from core.src.package_managers import AptitudePackageManager


class TestAptitudePackageManager_CustomSources(unittest.TestCase):
    def setUp(self):
        self.argument_composer = ArgumentComposer().get_composed_arguments()
        self.runtime = RuntimeCompositor(self.argument_composer, True, Constants.APT)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def test_sources_list_and_parts_combinations(self):
        # EULA accepted in settings and commands updated accordingly
        self.__lib_test_custom_sources_with(include_sources_list=True, include_source_parts_list=False,
                                            include_source_parts_debstyle=True,
                                            include_max_patch_publish_date="")

        for include_sources_list in [True, False]:
            for include_source_parts_list in [True, False]:
                for include_source_parts_debstyle in [True, False]:
                    for include_max_patch_publish_date in [str(), "20240401T160000Z"]:
                        time.sleep(1000)
                        print("\n\nTesting combination: [SourcesList={0}][SourcePartsList={1}][SourcePartsDebstyle={2}][PublishDate={3}]".format(
                            include_sources_list, include_source_parts_list, include_source_parts_debstyle, include_max_patch_publish_date))
                        self.__lib_test_custom_sources_with(include_sources_list=include_sources_list,
                                                            include_source_parts_list=include_source_parts_list,
                                                            include_source_parts_debstyle=include_source_parts_debstyle,
                                                            include_max_patch_publish_date=include_max_patch_publish_date)

    def __lib_test_custom_sources_with(self, include_sources_list=False, include_source_parts_list=False, include_source_parts_debstyle=False,
                                       include_max_patch_publish_date=str()):
        mock_sources_path = self.__prep_scratch_with_sources(include_sources_list, include_source_parts_list, include_source_parts_debstyle)

        package_manager = AptitudePackageManager.AptitudePackageManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.status_handler)
        self.__adapt_package_manager_for_mock_sources(package_manager, mock_sources_path)

        # All
        expected_debstyle_entry_count = 2 if include_source_parts_debstyle else 0
        expected_sources_list_entry_count = (4 if include_sources_list else 0) + (3 if include_source_parts_list else 0)
        sources_dir, sources_list = package_manager._AptitudePackageManager__get_custom_sources_to_spec(include_max_patch_publish_date)
        self.__check_custom_sources(sources_dir, sources_list,
                                    sources_debstyle_expected=include_source_parts_debstyle,
                                    sources_list_expected=include_sources_list,
                                    security_only=False,
                                    sources_debstyle_entry_count=expected_debstyle_entry_count,
                                    sources_list_entry_count=expected_sources_list_entry_count,
                                    max_patch_publish_date=include_max_patch_publish_date)

        # Security
        expected_debstyle_entry_count = 1 if include_source_parts_debstyle else 0
        expected_sources_list_entry_count = (1 if include_sources_list else 0) + (1 if include_source_parts_list else 0)
        sources_dir, sources_list = package_manager._AptitudePackageManager__get_custom_sources_to_spec(include_max_patch_publish_date, "Security")
        self.__check_custom_sources(sources_dir, sources_list,
                                    sources_debstyle_expected=include_source_parts_debstyle,
                                    sources_list_expected=include_sources_list,
                                    security_only=True,
                                    sources_debstyle_entry_count=expected_debstyle_entry_count,
                                    sources_list_entry_count=expected_sources_list_entry_count,
                                    max_patch_publish_date=include_max_patch_publish_date)

        self.__clear_mock_sources_path(mock_sources_path)

    def __check_custom_sources(self, sources_dir, sources_list, sources_debstyle_expected=False, sources_list_expected=False,
                               security_only=False, sources_debstyle_entry_count=-1, sources_list_entry_count=-1,
                               max_patch_publish_date=str()):
        if sources_debstyle_expected:
            self.assertTrue(os.path.isdir(sources_dir))
            source_parts_file = os.path.join(sources_dir, "azgps-src-parts.sources")
            self.assertTrue(os.path.exists(source_parts_file))
            with self.runtime.env_layer.file_system.open(source_parts_file, 'r') as file_handle:
                data = file_handle.read().split("\n\n")
                self.assertEqual(len(data), sources_debstyle_entry_count)
                for entry in data:
                    if security_only:
                        self.assertTrue("security" in entry)
                    if max_patch_publish_date != str():
                        self.assertTrue(max_patch_publish_date in entry)
        else:
            pass
            #self.assertFalse(os.path.isdir(sources_dir))

        if sources_list_expected:
            self.assertTrue(os.path.exists(sources_list))
            with self.runtime.env_layer.file_system.open(sources_list, 'r') as file_handle:
                data = file_handle.readlines()
                self.assertEqual(len(data), sources_list_entry_count)
                for entry in data:
                    if security_only:
                        self.assertTrue("security" in entry)
                    if max_patch_publish_date != str():
                        self.assertTrue(max_patch_publish_date in entry)
        else:
            self.assertFalse(os.path.exists(sources_list))



    # region - Mock sources preparation and clean up
    def __prep_scratch_with_sources(self, include_sources_list=True, include_source_parts_list=True, include_source_parts_debstyle=True):
        # type: (bool, bool, bool) -> str
        # Prepares the file system with input test data
        timestamp = self.runtime.env_layer.datetime.timestamp().replace(":", ".")
        mock_sources_path = os.path.join(self.runtime.scratch_path, "apt-src-" + timestamp)
        if os.path.isdir(mock_sources_path):
            shutil.rmtree(mock_sources_path)
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
        # Clears out the input test data
        shutil.rmtree(mock_sources_path)

    @staticmethod
    def __adapt_package_manager_for_mock_sources(package_manager, mock_sources_path):
        # type: (object, str) -> None
        # Modifies the package manager internals to the mock input data sources
        package_manager.APT_SOURCES_LIST_PATH = os.path.join(mock_sources_path, "sources.list")
        package_manager.APT_SOURCES_LIST_DIR_PATH = os.path.join(mock_sources_path, "sources.list.d")

    @staticmethod
    def __get_sources_data_one_line_style_def():
        return "deb http://azure.archive.ubuntu.com/ubuntu/ focal main restricted\n" + \
                "deb http://azure.archive.ubuntu.com/ubuntu/ focal-security main restricted\n" + \
                "deb http://azure.archive.ubuntu.com/ubuntu/ focal universe\n" + \
                "deb http://azure.archive.ubuntu.com/ubuntu/ focal multiverse\n"

    @staticmethod
    def __get_sources_data_one_line_style_ext():
        return "deb http://us.archive.ubuntu.com/ubuntu/ focal-backports main restricted universe multiverse\n" + \
                "deb http://azure.archive.ubuntu.com/ubuntu/ focal-security universe\n" + \
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
    # endregion

if __name__ == '__main__':
    unittest.main()
