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
import unittest
from os import mkdir

from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor
from core.src.package_managers import AptitudePackageManager


class TestAptitudePackageManagerCustomSources(unittest.TestCase):
    def setUp(self):
        self.argument_composer = ArgumentComposer().get_composed_arguments()
        self.runtime = RuntimeCompositor(self.argument_composer, True, Constants.APT)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def test_custom_source_invocation_for_security(self):
        def get_custom_sources_to_spec_for_sec(max_patch_published_date=str(), base_classification=str()):
            assert max_patch_published_date is str()
            assert base_classification == Constants.PackageClassification.SECURITY
            return str(), str()

        def get_custom_sources_to_spec_for_sec_date(max_patch_published_date=str(), base_classification=str()):
            assert max_patch_published_date == "2025-03-12T00:00:00Z"
            assert base_classification == Constants.PackageClassification.SECURITY
            return str(), str()

        package_manager = AptitudePackageManager.AptitudePackageManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.status_handler)
        package_manager._AptitudePackageManager__get_custom_sources_to_spec = get_custom_sources_to_spec_for_sec
        package_manager.get_security_updates()
        package_manager.install_security_updates_azgps_coordinated()

        package_manager._AptitudePackageManager__get_custom_sources_to_spec = get_custom_sources_to_spec_for_sec_date
        package_manager.set_max_patch_publish_date("2025-03-12T00:00:00Z")
        package_manager.install_security_updates_azgps_coordinated()

    def test_bad_custom_sources_to_spec_invocation(self):
        package_manager = AptitudePackageManager.AptitudePackageManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.status_handler)
        sources_dir, sources_list = package_manager._AptitudePackageManager__get_custom_sources_to_spec(base_classification="other")    # invalid call
        self.assertEqual(sources_list, str())
        self.assertEqual(sources_dir, str())

    def test_force_defensive_exception_handling_coverage(self):
        package_manager = AptitudePackageManager.AptitudePackageManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.status_handler)
        package_manager._AptitudePackageManager__read_deb882_style_format("fake-path.list", "some-date", "security")

        package_manager = AptitudePackageManager.AptitudePackageManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.status_handler)
        tmp_path = os.path.join(self.runtime.scratch_path, "tmp")
        mock_sources_path = self.__prep_scratch_with_sources(include_sources_list=True)
        self.__adapt_package_manager_for_mock_sources(package_manager, mock_sources_path)
        package_manager._AptitudePackageManager__read_one_line_style_list_format = None
        package_manager._AptitudePackageManager__get_consolidated_source_parts_content("some-date", "security")

    def test_default_refresh_invalidates_snapshot_sources_cache(self):
        # A default-sources refresh deletes snapshot lists on disk, so the next snapshot-sourced call must refresh again
        package_manager, mock_sources_path, commands = self.__get_package_manager_with_command_tracking()
        package_manager.set_max_patch_publish_date("20240401T160000Z")

        package_manager._AptitudePackageManager__get_custom_sources_to_spec("20240401T160000Z", "Security")
        self.assertEqual(self.__count_custom_source_refreshes(commands), 1)
        self.assertEqual(package_manager.current_source_formula, "20240401T160000Z-security")
        package_manager._AptitudePackageManager__get_custom_sources_to_spec("20240401T160000Z", "Security")
        self.assertEqual(self.__count_custom_source_refreshes(commands), 1)     # cache hit, no refresh

        package_manager.refresh_repo()      # default sources refresh
        self.assertIsNone(package_manager.current_source_formula)

        package_manager._AptitudePackageManager__get_custom_sources_to_spec("20240401T160000Z", "Security")
        self.assertEqual(self.__count_custom_source_refreshes(commands), 2)     # snapshot lists re-fetched
        self.assertEqual(package_manager.current_source_formula, "20240401T160000Z-security")
        self.__clear_mock_sources_path(mock_sources_path)

    def test_default_refresh_retains_sources_cache_without_snapshot_date(self):
        # Without a snapshot date, custom sources point to the same repos as default sources, so lists survive and caching is retained
        package_manager, mock_sources_path, commands = self.__get_package_manager_with_command_tracking()

        package_manager._AptitudePackageManager__get_custom_sources_to_spec(str(), "Security")
        self.assertEqual(self.__count_custom_source_refreshes(commands), 1)

        package_manager.refresh_repo()
        self.assertEqual(package_manager.current_source_formula, "any-security")

        package_manager._AptitudePackageManager__get_custom_sources_to_spec(str(), "Security")
        self.assertEqual(self.__count_custom_source_refreshes(commands), 1)     # cache hit, no refresh
        self.__clear_mock_sources_path(mock_sources_path)

    def test_strict_sdp_install_refetches_snapshot_lists_after_pro_client_refresh(self):
        # Reproduces the strict SDP sequence: snapshot security discovery -> pro client default refresh -> snapshot security install
        package_manager, mock_sources_path, commands = self.__get_package_manager_with_command_tracking()
        package_manager.set_max_patch_publish_date("20240401T160000Z")
        package_manager._AptitudePackageManager__pro_client_prereq_met = True
        package_manager.ubuntu_pro_client.get_security_updates = lambda: (False, [], [])

        package_manager.get_security_updates()
        code, out = package_manager.install_security_updates_azgps_coordinated()
        self.assertEqual(code, 0)

        install_commands = [i for i, cmd in enumerate(commands) if "dist-upgrade" in cmd and "-s dist-upgrade" not in cmd]
        default_refreshes = [i for i, cmd in enumerate(commands) if "apt-get -q update" in cmd and "SourceParts" not in cmd]
        snapshot_refreshes = [i for i, cmd in enumerate(commands) if "apt-get -q update" in cmd and "SourceParts" in cmd]
        self.assertEqual(len(install_commands), 1)
        self.assertEqual(len(default_refreshes), 1)     # pro client prerequisite refresh
        self.assertEqual(len(snapshot_refreshes), 2)    # discovery + re-fetch before install
        self.assertLess(default_refreshes[0], snapshot_refreshes[-1])       # snapshot lists refreshed after default refresh...
        self.assertLess(snapshot_refreshes[-1], install_commands[0])        # ...and before install
        self.assertIn("20240401T160000Z-security", commands[install_commands[0]])
        self.__clear_mock_sources_path(mock_sources_path)

    def test_get_all_updates_ignores_pro_client_results_under_strict_sdp(self):
        # Pro Client does not honor snapshot sources, so default (snapshot-sourced) results must be used when a max patch publish date is set
        package_manager, mock_sources_path, commands = self.__get_package_manager_with_command_tracking()
        package_manager._AptitudePackageManager__pro_client_prereq_met = True
        package_manager.ubuntu_pro_client.get_all_updates = lambda: (True, ["pro-only-pkg"], ["9.9"])
        package_manager.extract_packages_and_versions = lambda output: (["curl", "libcurl4t64"], ["2.0", "2.0"])

        package_manager.set_max_patch_publish_date("20240401T160000Z")
        self.assertEqual(package_manager.get_all_updates(cached=False), (["curl", "libcurl4t64"], ["2.0", "2.0"]))
        self.assertEqual(package_manager.get_all_updates(cached=True), (["curl", "libcurl4t64"], ["2.0", "2.0"]))

        package_manager.set_max_patch_publish_date()    # regular (non strict SDP) behavior is unchanged
        self.assertEqual(package_manager.get_all_updates(cached=False), (["pro-only-pkg"], ["9.9"]))
        self.assertEqual(package_manager.get_all_updates(cached=True), (["pro-only-pkg"], ["9.9"]))
        self.__clear_mock_sources_path(mock_sources_path)

    def test_sources_list_and_parts_combinations(self):
        # Tests 32 combinations of source configuration on disk and desired manipulations + caching
        for include_sources_list in [True, False]:
            for include_source_parts_list in [True, False]:
                for include_source_parts_debstyle in [True, False]:
                    for include_max_patch_publish_date in [str(), "20240401T160000Z"]:
                        print("\n\nTesting combination: [SourcesList={0}][SourcePartsList={1}][SourcePartsDebstyle={2}][PublishDate={3}]".format(
                            include_sources_list, include_source_parts_list, include_source_parts_debstyle, include_max_patch_publish_date))
                        self.__lib_test_custom_sources_with(include_sources_list=include_sources_list,
                                                            include_source_parts_list=include_source_parts_list,
                                                            include_source_parts_debstyle=include_source_parts_debstyle,
                                                            include_max_patch_publish_date=include_max_patch_publish_date)

    def __lib_test_custom_sources_with(self, include_sources_list=False, include_source_parts_list=False, include_source_parts_debstyle=False,
                                       include_max_patch_publish_date=str()):
        # type: (bool, bool, bool, str) -> None
        # Provides the base unit for testing various source configurations and assertions on the outcomes

        # Prepare the file system for the test
        tmp_path = os.path.join(self.runtime.scratch_path, "tmp")
        mock_sources_path = self.__prep_scratch_with_sources(include_sources_list, include_source_parts_list, include_source_parts_debstyle)

        # Instantiate the package manager, and redirect sources in the test environment
        package_manager = AptitudePackageManager.AptitudePackageManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.status_handler)
        self.__adapt_package_manager_for_mock_sources(package_manager, mock_sources_path)

        # Checks swapping and caching: All -> Security -> All -> All
        for i in range(3):
            # All
            expected_debstyle_entry_count = 3 if include_source_parts_debstyle else 0   # 3 entries in the debstyle mock(incl. fips-updates)
            expected_sources_list_entry_count = (4 if include_sources_list else 0) + (6 if include_source_parts_list else 0)    # 4 in regular file, 6 in mock folder (incl. fips-updates)
            sources_dir, sources_list = package_manager._AptitudePackageManager__get_custom_sources_to_spec(include_max_patch_publish_date)
            self.__check_custom_sources(sources_dir, sources_list,
                                        sources_debstyle_expected=include_source_parts_debstyle,
                                        sources_list_expected=include_sources_list,
                                        security_only=False,
                                        sources_debstyle_entry_count=expected_debstyle_entry_count,
                                        sources_list_entry_count=expected_sources_list_entry_count,
                                        max_patch_publish_date=include_max_patch_publish_date)

            # caching combinatorial exercise
            if i >= 1:
                continue

            # Security
            expected_debstyle_entry_count = 2 if include_source_parts_debstyle else 0   # 2 security entries in the debstyle mock (security + fips-updates)
            expected_sources_list_entry_count = (1 if include_sources_list else 0) + (2 if include_source_parts_list else 0)    # 1 security entry in regular file, 2 security entries in mock folder (security + fips-updates)
            sources_dir, sources_list = package_manager._AptitudePackageManager__get_custom_sources_to_spec(include_max_patch_publish_date, "Security")
            self.__check_custom_sources(sources_dir, sources_list,
                                        sources_debstyle_expected=include_source_parts_debstyle,
                                        sources_list_expected=include_sources_list,
                                        security_only=True,
                                        sources_debstyle_entry_count=expected_debstyle_entry_count,
                                        sources_list_entry_count=expected_sources_list_entry_count,
                                        max_patch_publish_date=include_max_patch_publish_date)

        # Clean up file system after the test
        self.__clear_mock_sources_path(mock_sources_path)
        shutil.rmtree(tmp_path)
        mkdir(tmp_path)

    def __check_custom_sources(self, sources_dir, sources_list, sources_debstyle_expected=False, sources_list_expected=False,
                               security_only=False, sources_debstyle_entry_count=-1, sources_list_entry_count=-1,
                               max_patch_publish_date=str()):
        # type: (str, str, bool, bool, bool, int, int, str) -> None
        # Selectively checks assertions and conditions based on the test scenario

        if sources_debstyle_expected:
            self.assertTrue(os.path.isdir(sources_dir))
            source_parts_file = os.path.join(sources_dir, "azgps-src-parts.sources")
            self.assertTrue(os.path.exists(source_parts_file))
            with self.runtime.env_layer.file_system.open(source_parts_file, 'r') as file_handle:
                data = file_handle.read().split("\n\n")
                self.assertEqual(len(data), sources_debstyle_entry_count)
                for entry in data:
                    if security_only:
                        self.assertTrue("security" in entry or "fips-updates" in entry)
                    if max_patch_publish_date != str() and "fips-updates" not in entry:  # exception for unsupported repo:
                        self.assertTrue(max_patch_publish_date in entry)
        else:
            self.assertFalse(os.path.isdir(sources_dir))

        if sources_list_expected:
            self.assertTrue(os.path.exists(sources_list))
            with self.runtime.env_layer.file_system.open(sources_list, 'r') as file_handle:
                data = file_handle.readlines()
                self.assertEqual(len(data), sources_list_entry_count)
                for entry in data:
                    if security_only:
                        self.assertTrue("security" in entry or "fips-updates" in entry)
                    if max_patch_publish_date != str() and "ppa" not in entry and "fips-updates" not in entry:  # exception for unsupported repo
                        self.assertTrue(max_patch_publish_date in entry)

    # region - Mock sources preparation and clean up
    def __prep_scratch_with_sources(self, include_sources_list=True, include_source_parts_list=True, include_source_parts_debstyle=True):
        # type: (bool, bool, bool) -> str
        # Prepares the file system with input test sources data
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
        package_manager.APT_SOURCES_DIR_PATH = os.path.join(mock_sources_path, "sources.list.d")

    def __get_package_manager_with_command_tracking(self):
        # type: () -> (object, str, list)
        # Returns a package manager wired to mock sources, with every package manager command captured instead of executed
        commands = []
        mock_sources_path = self.__prep_scratch_with_sources(include_sources_list=True, include_source_parts_list=False, include_source_parts_debstyle=True)
        package_manager = AptitudePackageManager.AptitudePackageManager(self.runtime.env_layer, self.runtime.execution_config, self.runtime.composite_logger, self.runtime.telemetry_writer, self.runtime.status_handler)
        self.__adapt_package_manager_for_mock_sources(package_manager, mock_sources_path)

        def mock_invoke_package_manager_advanced(command, raise_on_exception=True):
            commands.append(command)
            return str(), 0

        package_manager.invoke_package_manager_advanced = mock_invoke_package_manager_advanced
        return package_manager, mock_sources_path, commands

    @staticmethod
    def __count_custom_source_refreshes(commands):
        # type: (list) -> int
        # Counts repo refreshes that were scoped to custom (snapshot) sources
        return len([cmd for cmd in commands if "apt-get -q update" in cmd and "SourceParts" in cmd])

    @staticmethod
    def __get_sources_data_one_line_style_def():
        return "deb http://azure.archive.ubuntu.com/ubuntu/ focal main restricted\n" + \
                "deb http://azure.archive.ubuntu.com/ubuntu/ focal-security main restricted\n" + \
                "deb http://azure.archive.ubuntu.com/ubuntu/ focal universe\n" + \
                "deb http://azure.archive.ubuntu.com/ubuntu/ focal multiverse\n"

    @staticmethod
    def __get_sources_data_one_line_style_ext():
        return "deb http://us.archive.ubuntu.com/ubuntu/ focal-backports main restricted universe multiverse\n" + \
                "deb http://ppa.launchpad.net/upubuntu-com/web/ubuntu focal main\n" + \
                "deb http://azure.archive.ubuntu.com/ubuntu/ focal-security universe\n" + \
                "deb http://in.archive.ubuntu.com/ubuntu/ focal multiverse\n" + \
                "deb http://cn.archive.ubuntu.com/ubuntu/ focal main\n" + \
                "deb https://esm.ubuntu.com/fips-updates/ubuntu jammy-updates main\n"

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
                "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg \n" + \
                "\n" + \
                "Types: deb \n" + \
                "URIs: https://esm.ubuntu.com/fips-updates/ubuntu \n" + \
                "Suites: jammy-updates \n" + \
                "Components: main \n" + \
                "Signed-By: /usr/share/keyrings/ubuntu-pro-fips-updates.gpg \n"
    # endregion

if __name__ == '__main__':
    unittest.main()
