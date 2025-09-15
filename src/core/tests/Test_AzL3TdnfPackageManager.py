# Copyright 2025 Microsoft Corporation
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
import sys
# Conditional import for StringIO
try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import StringIO  # Python 3

from core.src.bootstrap.Constants import Constants
from core.tests.library.LegacyEnvLayerExtensions import LegacyEnvLayerExtensions
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor
from core.src.external_dependencies import distro


class TestAzL3TdnfPackageManager(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.TDNF)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    # region Mocks
    def mock_do_processes_require_restart_raise_exception(self):
        raise Exception

    def mock_linux_distribution_to_return_azure_linux(self):
        return ['Microsoft Azure Linux', '3.0', '']

    def mock_linux_distribution_to_return_azure_linux_2(self):
        return ['Common Base Linux Mariner', '2.0', '']

    def mock_write_with_retry_raise_exception(self, file_path_or_handle, data, mode='a+'):
        raise Exception

    def mock_run_command_output_return_tdnf_3(self, cmd, no_output=False, chk_err=True):
        """ Mock for run_command_output to return tdnf 3 """
        return 0, "3.5.8-3\n"

    def mock_run_command_output_return_1(self, cmd, no_output=False, chk_err=True):
        """ Mock for run_command_output to return None """
        return 1, "No output available\n"

    def mock_run_command_output_return_0(self, cmd, no_output=False, chk_err=True):
        return 0, "Successfully executed command\n"

    def mock_get_tdnf_version_return_tdnf_3_5_8_3(self):
        return "3.5.8-3.azl3"

    def mock_get_tdnf_version_return_tdnf_4_0(self):
        return "4.0.0-1.azl3"

    def mock_get_tdnf_version_return_tdnf_2_5(self):
        return "2.5.0-1.cm2"

    def mock_get_tdnf_version_return_tdnf_3_5_8_2(self):
        return "3.5.8-2.azl3"

    def mock_get_tdnf_version_return_tdnf_3_5_8_6_cm2(self):
        return "3.5.8-6.cm2"

    def mock_get_tdnf_version_return_None(self):
        return None

    def mock_distro_os_release_attr_return_azure_linux_3(self, attribute):
        return '3.0.0'

    def mock_distro_os_release_attr_return_azure_linux_2(self, attribute):
        return '2.9.0'
    # endregion

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

    def __setup_current_auto_os_update_config(self, package_manager, config_value='', config_file_name="automatic.conf"):
        # setup current auto OS update config
        package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, config_file_name)
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, config_value)

    def __setup_backup_for_system_default_OS_update_config(self, package_manager, apply_updates_value="", download_updates_value="", enable_on_reboot_value=False, installation_state_value=False, set_installation_state=True):
        # setup backup for system default auto OS update config
        package_manager.image_default_patch_configuration_backup_path = os.path.join(self.runtime.execution_config.config_folder, Constants.IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH)
        backup_image_default_patch_configuration_json = {
            "dnf-automatic": {
                "apply_updates": apply_updates_value,
                "download_updates": download_updates_value,
                "enable_on_reboot": enable_on_reboot_value
            }
        }
        if set_installation_state:
            backup_image_default_patch_configuration_json["dnf-automatic"]["installation_state"] = installation_state_value
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
        self.assertTrue(expected_output in output)

    def __assert_reverted_automatic_patch_configuration_settings(self, package_manager, config_exists=True, config_value_expected=''):
        if config_exists:
            reverted_dnf_automatic_patch_configuration_settings = self.runtime.env_layer.file_system.read_with_retry(package_manager.dnf_automatic_configuration_file_path)
            self.assertTrue(reverted_dnf_automatic_patch_configuration_settings is not None)
            self.assertTrue(config_value_expected in reverted_dnf_automatic_patch_configuration_settings)
        else:
            self.assertFalse(os.path.exists(package_manager.dnf_automatic_configuration_file_path))
    # endregion

    def test_do_processes_require_restart(self):
        """Unit test for tdnf package manager"""
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

        # Fake exception
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        backup_do_processes_require_restart = package_manager.do_processes_require_restart
        package_manager.do_processes_require_restart = self.mock_do_processes_require_restart_raise_exception
        self.assertTrue(package_manager.is_reboot_pending())  # returns true because the safe default if a failure occurs is 'true'
        package_manager.do_processes_require_restart = backup_do_processes_require_restart

    def test_package_manager_no_updates(self):
        """Unit test for tdnf package manager with no updates"""
        # Path change
        self.runtime.set_legacy_test_type('SadPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertEqual(len(available_updates), 0)
        self.assertEqual(len(package_versions), 0)

    def test_package_manager_unaligned_updates(self):
        # Path change
        self.runtime.set_legacy_test_type('UnalignedPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        try:
            package_manager.get_available_updates(package_filter)
        except Exception as exception:
            self.assertTrue(str(exception))
        else:
            self.assertFalse(1 != 2, 'Exception did not occur and test failed.')

    def test_package_manager(self):
        """Unit test for tdnf package manager"""
        self.runtime.set_legacy_test_type('HappyPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertTrue(available_updates is not None)
        self.assertTrue(package_versions is not None)
        self.assertEqual(9, len(available_updates))
        self.assertEqual(9, len(package_versions))
        self.assertEqual("azurelinux-release.noarch", available_updates[0])
        self.assertEqual("azurelinux-repos-ms-oss.noarch", available_updates[1])
        self.assertEqual("3.0-16.azl3", package_versions[0])
        self.assertEqual("3.0-3.azl3", package_versions[1])

        # test for get_package_size when size is available
        cmd = package_manager.single_package_upgrade_cmd + "curl"
        code, out = self.runtime.env_layer.run_command_output(cmd, False, False)
        size = package_manager.get_package_size(out)
        self.assertEqual(size, "661.34k")

        # test for get_package_size when size is not available
        cmd = package_manager.single_package_upgrade_cmd + "systemd"
        code, out = self.runtime.env_layer.run_command_output(cmd, False, False)
        size = package_manager.get_package_size(out)
        self.assertEqual(size, Constants.UNKNOWN_PACKAGE_SIZE)

        # test for all available versions
        package_versions = package_manager.get_all_available_versions_of_package("python3")
        self.assertEqual(len(package_versions), 6)
        self.assertEqual(package_versions[0], '3.12.3-1.azl3')
        self.assertEqual(package_versions[1], '3.12.3-2.azl3')
        self.assertEqual(package_versions[2], '3.12.3-4.azl3')
        self.assertEqual(package_versions[3], '3.12.3-5.azl3')
        self.assertEqual(package_versions[4], '3.12.3-6.azl3')
        self.assertEqual(package_versions[5], '3.12.9-1.azl3')

        # test for get_dependent_list
        dependent_list = package_manager.get_dependent_list(["hyperv-daemons.x86_64"])
        self.assertTrue(dependent_list is not None)
        self.assertEqual(len(dependent_list), 4)
        self.assertEqual(dependent_list[0], "hyperv-daemons-license.noarch")
        self.assertEqual(dependent_list[1], "hypervvssd.x86_64")
        self.assertEqual(dependent_list[2], "hypervkvpd.x86_64")
        self.assertEqual(dependent_list[3], "hypervfcopyd.x86_64")

        # test install cmd
        packages = ['kernel.x86_64', 'selinux-policy-targeted.noarch']
        package_versions = ['2.02.177-4.el7', '3.10.0-862.el7']
        cmd = package_manager.get_install_command('sudo tdnf -y install --skip-broken ', packages, package_versions)
        self.assertEqual(cmd, 'sudo tdnf -y install --skip-broken kernel-2.02.177-4.el7.x86_64 selinux-policy-targeted-3.10.0-862.el7.noarch')
        packages = ['kernel.x86_64']
        package_versions = ['2.02.177-4.el7']
        cmd = package_manager.get_install_command('sudo tdnf -y install --skip-broken ', packages, package_versions)
        self.assertEqual(cmd, 'sudo tdnf -y install --skip-broken kernel-2.02.177-4.el7.x86_64')
        packages = ['kernel.x86_64', 'kernel.i686']
        package_versions = ['2.02.177-4.el7', '2.02.177-4.el7']
        cmd = package_manager.get_install_command('sudo tdnf -y install --skip-broken ', packages, package_versions)
        self.assertEqual(cmd, 'sudo tdnf -y install --skip-broken kernel-2.02.177-4.el7.x86_64 kernel-2.02.177-4.el7.i686')

        self.runtime.stop()
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.TDNF)
        self.container = self.runtime.container
        self.runtime.set_legacy_test_type('ExceptionPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)
        # test for get_available_updates
        try:
            package_manager.get_available_updates(package_filter)
        except Exception as exception:
            self.assertTrue(str(exception))
        else:
            self.assertFalse(1 != 2, 'Exception did not occur and test failed.')

        # test for get_dependent_list
        try:
            package_manager.get_dependent_list(["man"])
        except Exception as exception:
            self.assertTrue(str(exception))
        else:
            self.assertFalse(1 != 2, 'Exception did not occur and test failed.')

    def test_install_package_success(self):
        """Unit test for install package success"""
        self.runtime.set_legacy_test_type('SuccessInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        # test for successfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('hyperv-daemons-license.noarch', '6.6.78.1-1.azl3', simulate=True), Constants.INSTALLED)

    def test_install_package_failure(self):
        """Unit test for install package failure"""
        self.runtime.set_legacy_test_type('FailInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        # test for unsuccessfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('hyperv-daemons-license.noarch', '6.6.78.1-1.azl3', simulate=True), Constants.FAILED)

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

    def test_get_product_name_without_arch(self):
        """Unit test for retrieving product Name"""
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)
        self.assertEqual(package_manager.get_product_name_without_arch("bash.x86_64"), "bash")
        self.assertEqual(package_manager.get_product_name_without_arch("firefox.x86_64"), "firefox")
        self.assertEqual(package_manager.get_product_name_without_arch("test.noarch"), "test")
        self.assertEqual(package_manager.get_product_name_without_arch("noextension"), "noextension")
        self.assertEqual(package_manager.get_product_name_without_arch("noextension.ext"), "noextension.ext")

    def test_get_product_arch(self):
        """Unit test for retrieving product arch"""
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)
        self.assertEqual(package_manager.get_product_arch("bash.x86_64"), ".x86_64")
        self.assertEqual(package_manager.get_product_arch("firefox.x86_64"), ".x86_64")
        self.assertEqual(package_manager.get_product_arch("test.noarch"), ".noarch")
        self.assertEqual(package_manager.get_product_arch("noextension"), None)
        self.assertEqual(package_manager.get_product_arch("noextension.ext"), None)

    def test_inclusion_type_all(self):
        """Unit test for tdnf package manager Classification = all and IncludedPackageNameMasks not specified."""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.UNCLASSIFIED]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.TDNF)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertTrue(available_updates is not None)
        self.assertTrue(package_versions is not None)
        self.assertEqual(9, len(available_updates))
        self.assertEqual(9, len(package_versions))
        self.assertEqual("azurelinux-release.noarch", available_updates[0])
        self.assertEqual("3.0-16.azl3", package_versions[0])
        self.assertEqual("azurelinux-repos-ms-oss.noarch", available_updates[1])
        self.assertEqual("3.0-3.azl3", package_versions[1])
        self.assertEqual("libseccomp.x86_64", available_updates[2])
        self.assertEqual("2.5.4-1.azl3", package_versions[2])
        self.assertEqual("python3.x86_64", available_updates[3])
        self.assertEqual("3.12.3-6.azl3", package_versions[3])
        self.assertEqual("libxml2.x86_64", available_updates[4])
        self.assertEqual("2.11.5-1.azl3", package_versions[4])
        self.assertEqual("dracut.x86_64", available_updates[5])
        self.assertEqual("102-7.azl3", package_versions[5])
        self.assertEqual("hyperv-daemons-license.noarch", available_updates[6])
        self.assertEqual("6.6.78.1-1.azl3", package_versions[6])
        self.assertEqual("hypervvssd.x86_64", available_updates[7])
        self.assertEqual("6.6.78.1-1.azl3", package_versions[7])
        self.assertEqual("hypervkvpd.x86_64", available_updates[8])
        self.assertEqual("6.6.78.1-1.azl3", package_versions[8])

    def test_inclusion_type_critical(self):
        """Unit test for tdnf package manager with inclusion and Classification = Critical. Returns all packages since classifications are not available in Azure Linux, hence everything is considered as Critical."""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.CRITICAL]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        argument_composer.patches_to_include = ["ssh", "tar*"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.TDNF)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertEqual(9, len(available_updates))
        self.assertEqual(9, len(package_versions))

    def test_inclusion_type_other(self):
        """Unit test for tdnf package manager with inclusion and Classification = Other. All packages are considered are 'Security' since TDNF does not have patch classification"""
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

    def test_inclusion_only(self):
        """Unit test for tdnf package manager with inclusion only and NotSelected Classifications"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.UNCLASSIFIED]
        argument_composer.patches_to_include = ["azurelinux-release.noarch", "lib*"]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.TDNF)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertTrue(available_updates is not None)
        self.assertTrue(package_versions is not None)
        self.assertEqual(3, len(available_updates))
        self.assertEqual(3, len(package_versions))
        self.assertEqual("azurelinux-release.noarch", available_updates[0])
        self.assertEqual("3.0-16.azl3", package_versions[0])
        self.assertEqual("libseccomp.x86_64", available_updates[1])
        self.assertEqual("2.5.4-1.azl3", package_versions[1])
        self.assertEqual("libxml2.x86_64", available_updates[2])
        self.assertEqual("2.11.5-1.azl3", package_versions[2])

    def test_inclusion_dependency_only(self):
        """Unit test for tdnf with test dependencies in Inclusion & NotSelected Classifications"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.UNCLASSIFIED]
        argument_composer.patches_to_include = ["ssh", "hypervvssd.x86_64"]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.TDNF)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertTrue(available_updates is not None)
        self.assertTrue(package_versions is not None)
        self.assertEqual(len(available_updates), 1)
        self.assertEqual(len(package_versions), 1)
        self.assertEqual(available_updates[0], "hypervvssd.x86_64")
        self.assertEqual(package_versions[0], "6.6.78.1-1.azl3")

    def test_inclusion_notexist(self):
        """Unit test for tdnf with Inclusion which does not exist & NotSelected Classifications"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.UNCLASSIFIED]
        argument_composer.patches_to_include = ["ssh"]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.TDNF)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')
        self.assertTrue(package_filter is not None)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertTrue(available_updates is not None)
        self.assertTrue(package_versions is not None)
        self.assertEqual(len(available_updates), 0)
        self.assertEqual(len(package_versions), 0)

    def test_dedupe_update_packages_to_get_latest_versions(self):
        packages = []
        package_versions = []

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        deduped_packages, deduped_package_versions = package_manager.dedupe_update_packages_to_get_latest_versions(packages, package_versions)
        self.assertTrue(deduped_packages == [])
        self.assertTrue(deduped_package_versions == [])

        packages = ['python3.x86_64', 'dracut.x86_64', 'libxml2.x86_64', 'azurelinux-release.noarch', 'python3.noarch', 'python3.x86_64', 'python3.x86_64', 'hypervvssd.x86_64', 'python3.x86_64', 'python3.x86_64']
        package_versions = ['3.12.3-1.azl3', '102-7.azl3 ', '2.11.5-1.azl3', '3.0-16.azl3', '3.12.9-2.azl3', '3.12.9-1.azl3', '3.12.3-4.azl3', '6.6.78.1-1.azl3', '3.12.3-5.azl3', '3.12.3-5.azl3']
        deduped_packages, deduped_package_versions = package_manager.dedupe_update_packages_to_get_latest_versions(packages, package_versions)
        self.assertTrue(deduped_packages is not None and deduped_packages is not [])
        self.assertTrue(deduped_package_versions is not None and deduped_package_versions is not [])
        self.assertTrue(len(deduped_packages) == 6)
        self.assertTrue(deduped_packages[0] == 'python3.x86_64')
        self.assertTrue(deduped_package_versions[0] == '3.12.9-1.azl3')

    def test_obsolete_packages_should_not_considered_in_available_updates(self):
        self.runtime.set_legacy_test_type('ObsoletePackages')
        package_manager = self.container.get('package_manager')
        package_filter = self.container.get('package_filter')

        # test for all available versions
        package_versions = package_manager.get_all_available_versions_of_package("python3")
        self.assertEqual(len(package_versions), 6)
        self.assertEqual(package_versions[0], '3.12.3-1.azl3')
        self.assertEqual(package_versions[1], '3.12.3-2.azl3')
        self.assertEqual(package_versions[2], '3.12.3-4.azl3')
        self.assertEqual(package_versions[3], '3.12.3-5.azl3')
        self.assertEqual(package_versions[4], '3.12.3-6.azl3')
        self.assertEqual(package_versions[5], '3.12.9-1.azl3')

    def test_all_classification_selected_for_auto_patching_request(self):
        """Unit test for tdnf package manager for auto patching request where all classifications are selected since Azure Linux does not have classifications"""
        backup_envlayer_platform_linux_distribution = LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution
        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = self.mock_linux_distribution_to_return_azure_linux

        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.SECURITY, Constants.PackageClassification.CRITICAL]
        argument_composer.health_store_id = "pub_off_sku_2025.03.24"
        argument_composer.operation = Constants.INSTALLATION
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.TDNF)
        self.container = self.runtime.container

        execution_config = self.container.get('execution_config')
        self.assertTrue(execution_config.included_classifications_list is not None)
        self.assertTrue(execution_config.included_classifications_list == [Constants.PackageClassification.CRITICAL, Constants.PackageClassification.SECURITY, Constants.PackageClassification.OTHER])

        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = backup_envlayer_platform_linux_distribution

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
        self.assertTrue(package_manager.dnf_auto_os_update_service in image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf_auto_os_update_service][package_manager.dnf_automatic_download_updates_identifier_text], "")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf_auto_os_update_service][package_manager.dnf_automatic_apply_updates_identifier_text], "")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf_auto_os_update_service][package_manager.dnf_automatic_enable_on_reboot_identifier_text], False)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf_auto_os_update_service][package_manager.dnf_automatic_installation_state_identifier_text], False)

    def test_disable_auto_os_updates_with_installed_services(self):
        # all services are installed and contain valid configurations. expected o/p All services will be disabled and backup file should reflect default settings for all
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')

        package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf_automatic_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, dnf_automatic_os_patch_configuration_settings)

        package_manager.disable_auto_os_update()
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)

        # validating backup for dnf-automatic
        self.assertTrue(package_manager.dnf_auto_os_update_service in image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf_auto_os_update_service][package_manager.dnf_automatic_download_updates_identifier_text], "yes")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf_auto_os_update_service][package_manager.dnf_automatic_apply_updates_identifier_text], "yes")
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf_auto_os_update_service][package_manager.dnf_automatic_enable_on_reboot_identifier_text], False)
        self.assertEqual(image_default_patch_configuration_backup[package_manager.dnf_auto_os_update_service][package_manager.dnf_automatic_installation_state_identifier_text], True)

    def test_disable_auto_os_update_failure(self):
        # disable with non existing log file
        package_manager = self.container.get('package_manager')

        self.assertRaises(Exception, package_manager.disable_auto_os_update)
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())

    def test_update_image_default_patch_mode(self):
        package_manager = self.container.get('package_manager')
        package_manager.os_patch_configuration_settings_file_path = package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")

        # disable apply_updates when enabled by default
        dnf_automatic_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, dnf_automatic_os_patch_configuration_settings)

        package_manager.update_os_patch_configuration_sub_setting(package_manager.dnf_automatic_apply_updates_identifier_text, "no", package_manager.dnf_automatic_config_pattern_match_text)
        dnf_automatic_os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(package_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(dnf_automatic_os_patch_configuration_settings_file_path_read is not None)
        self.assertTrue('apply_updates = no' in dnf_automatic_os_patch_configuration_settings_file_path_read)
        self.assertTrue('download_updates = yes' in dnf_automatic_os_patch_configuration_settings_file_path_read)

        # disable download_updates when enabled by default
        dnf_automatic_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, dnf_automatic_os_patch_configuration_settings)
        package_manager.update_os_patch_configuration_sub_setting(package_manager.dnf_automatic_download_updates_identifier_text, "no", package_manager.dnf_automatic_config_pattern_match_text)
        dnf_automatic_os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(package_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(dnf_automatic_os_patch_configuration_settings_file_path_read is not None)
        self.assertTrue('apply_updates = yes' in dnf_automatic_os_patch_configuration_settings_file_path_read)
        self.assertTrue('download_updates = no' in dnf_automatic_os_patch_configuration_settings_file_path_read)

        # disable apply_updates when default patch mode settings file is empty
        dnf_automatic_os_patch_configuration_settings = ''
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, dnf_automatic_os_patch_configuration_settings)
        package_manager.update_os_patch_configuration_sub_setting(package_manager.dnf_automatic_apply_updates_identifier_text, "no", package_manager.dnf_automatic_config_pattern_match_text)
        dnf_automatic_os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(package_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(dnf_automatic_os_patch_configuration_settings_file_path_read is not None)
        self.assertTrue('download_updates' not in dnf_automatic_os_patch_configuration_settings_file_path_read)
        self.assertTrue('apply_updates = no' in dnf_automatic_os_patch_configuration_settings_file_path_read)

    def test_update_image_default_patch_mode_raises_exception(self):
        package_manager = self.container.get('package_manager')
        package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf_automatic_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, dnf_automatic_os_patch_configuration_settings)
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_raise_exception
        self.assertRaises(Exception, package_manager.update_os_patch_configuration_sub_setting)

    def test_get_current_auto_os_patch_state_with_uninstalled_services(self):
        # no services are installed on the machine. expected o/p: function will complete successfully, backup file is not created and function returns current_auto_os_patch_state as disabled
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state
        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.DISABLED)

    def test_get_current_auto_os_patch_state_with_installed_services_and_state_disabled(self):
        # dnf-automatic is installed on the machine. expected o/p: function will complete successfully, backup file is NOT created and function returns current_auto_os_patch_state as disabled
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state

        package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf_automatic_os_patch_configuration_settings = 'apply_updates = no\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, dnf_automatic_os_patch_configuration_settings)

        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.DISABLED)

    def test_get_current_auto_os_patch_state_with_installed_services_and_state_enabled(self):
        # dnf-automatic is installed on the machine. expected o/p: function will complete successfully, backup file is NOT created and function returns current_auto_os_patch_state as enabled

        # with enable on reboot set to false
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state

        package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf_automatic_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, dnf_automatic_os_patch_configuration_settings)

        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.ENABLED)

        # with enable on reboot set to true
        self.runtime.set_legacy_test_type('AnotherSadPath')
        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state

        package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf_automatic_os_patch_configuration_settings = 'apply_updates = no\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, dnf_automatic_os_patch_configuration_settings)

        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.ENABLED)

    def test_get_current_auto_os_patch_state_with_installed_services_and_state_unknown(self):
        # dnf-automatic is installed on the machine. expected o/p: function will complete successfully, backup file is NOT created and function returns current_auto_os_patch_state as unknown

        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        package_manager.get_current_auto_os_patch_state = self.runtime.backup_get_current_auto_os_patch_state

        package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf_automatic_os_patch_configuration_settings = 'apply_updates = abc\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, dnf_automatic_os_patch_configuration_settings)

        current_auto_os_patch_state = package_manager.get_current_auto_os_patch_state()

        self.assertFalse(package_manager.image_default_patch_configuration_backup_exists())
        self.assertEqual(current_auto_os_patch_state, Constants.AutomaticOSPatchStates.UNKNOWN)

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
                "expected_output": "[TDNF] Since the backup is invalid or does not exist for current service, we won't be able to revert auto OS patch settings to their system default value. [Service=dnf-automatic]"
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
                "expected_output": "[TDNF] Since the backup is invalid or does not exist for current service, we won't be able to revert auto OS patch settings to their system default value. [Service=dnf-automatic]"
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

        all_testcases = [revert_success_testcase, revert_success_with_dnf_not_installed_testcase, revert_success_with_dnf_installed_but_no_config_value_testcase, revert_success_backup_config_does_not_exist_testcase, revert_success_default_backup_config_invalid_testcase]

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
                self.__assert_std_io(captured_output=captured_output, expected_output=testcase["stdio"]["expected_output"])
            self.__assert_reverted_automatic_patch_configuration_settings(package_manager, config_exists=bool(testcase["assertions"]["config_exists"]), config_value_expected=testcase["assertions"]["config_value_expected"])

    def test_set_max_patch_publish_date(self):
        """Unit test for tdnf package manager set_max_patch_publish_date method"""
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        input_output_table_for_successful_cases = [
            ["20240702T000000Z", "1719878400"],
            ["", ""]
        ]
        for row in input_output_table_for_successful_cases:
            package_manager.set_max_patch_publish_date(row[0])
            self.assertEqual(package_manager.max_patch_publish_date, row[1])

        # posix time computation throws an exception if the date is not in the correct format
        self.assertRaises(ValueError, package_manager.set_max_patch_publish_date, "2024-07-02T00:00:00Z")

    def test_get_tdnf_version(self):
        """Unit test for tdnf package manager get_tdnf_version method"""
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)
        self.backup_run_command_output = self.runtime.env_layer.run_command_output

        test_input_output_table = [
            [self.mock_run_command_output_return_tdnf_3, "3.5.8-3"],
            [self.mock_run_command_output_return_1, None],
        ]

        for row in test_input_output_table:
            self.runtime.env_layer.run_command_output = row[0]
            version = package_manager.get_tdnf_version()
            self.assertEqual(version, row[1])

        self.runtime.env_layer.run_command_output = self.backup_run_command_output

    def test_is_mininum_tdnf_version_for_strict_sdp_installed(self):
        """Unit test for tdnf package manager is_minimum_tdnf_version method"""
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        self.backup_get_tdnf_version = package_manager.get_tdnf_version

        test_input_output_table = [
            [self.mock_get_tdnf_version_return_None, False],
            [self.mock_get_tdnf_version_return_tdnf_2_5, False],
            [self.mock_get_tdnf_version_return_tdnf_3_5_8_2, False],
            [self.mock_get_tdnf_version_return_tdnf_3_5_8_6_cm2, False],
            [self.mock_get_tdnf_version_return_tdnf_3_5_8_3, True],
            [self.mock_get_tdnf_version_return_tdnf_4_0, True]
        ]

        for row in test_input_output_table:
            package_manager.get_tdnf_version = row[0]
            result = package_manager.is_minimum_tdnf_version_for_strict_sdp_installed()
            self.assertEqual(result, row[1])

        package_manager.get_tdnf_version = self.backup_get_tdnf_version

    def test_try_tdnf_update_to_meet_strict_sdp_requirements(self):
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        self.backup_run_command_output = self.runtime.env_layer.run_command_output

        input_output_table = [
            [self.mock_run_command_output_return_0, True],
            [self.mock_run_command_output_return_1, False],
        ]

        for row in input_output_table:
            self.runtime.env_layer.run_command_output = row[0]
            result = package_manager.try_tdnf_update_to_meet_strict_sdp_requirements()
            self.assertEqual(result, row[1])

        self.runtime.env_layer.run_command_output = self.backup_run_command_output

    def test_try_meet_azgps_coordinated_requirements(self):
        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager is not None)

        # backup methods
        self.backup_linux_distribution = self.runtime.env_layer.platform.linux_distribution
        self.backup_distro_os_release_attr = distro.os_release_attr
        self.backup_get_tdnf_version = package_manager.get_tdnf_version
        self.backup_run_command_output = self.runtime.env_layer.run_command_output

        """ test cases:
                    1. Azure Linux 3 with tdnf version > 3.5.8-3
                    2. Azure Linux 3 with tdnf version = 3.5.8-3
                    3. Azure Linux 3 with tdnf version < 3.5.8-3, will be updated to 3.5.8-3 successfully
                    4. Azure Linux 3 with tdnf version < 3.5.8-3, will not be updated to 3.5.8-3
                    5. Azure Linux 2"""
        test_input_output_table = [
            [self.mock_linux_distribution_to_return_azure_linux, self.mock_distro_os_release_attr_return_azure_linux_3, self.mock_get_tdnf_version_return_tdnf_4_0, self.backup_run_command_output, True],
            [self.mock_linux_distribution_to_return_azure_linux, self.mock_distro_os_release_attr_return_azure_linux_3, self.mock_get_tdnf_version_return_tdnf_3_5_8_3, self.backup_run_command_output, True],
            [self.mock_linux_distribution_to_return_azure_linux, self.mock_distro_os_release_attr_return_azure_linux_3, self.mock_get_tdnf_version_return_tdnf_2_5, self.mock_run_command_output_return_0, True],
            [self.mock_linux_distribution_to_return_azure_linux, self.mock_distro_os_release_attr_return_azure_linux_3, self.mock_get_tdnf_version_return_tdnf_2_5, self.mock_run_command_output_return_1, False],
            [self.mock_linux_distribution_to_return_azure_linux_2, self.mock_distro_os_release_attr_return_azure_linux_2, self.backup_distro_os_release_attr, self.backup_run_command_output, False]
        ]

        for row in test_input_output_table:
            # set test case values
            self.runtime.env_layer.platform.linux_distribution = row[0]
            distro.os_release_attr = row[1]
            package_manager.get_tdnf_version = row[2]
            self.runtime.env_layer.run_command_output = row[3]

            # run test case
            result = package_manager.try_meet_azgps_coordinated_requirements()
            self.assertEqual(result, row[4])

        # restore original methods
        self.runtime.env_layer.platform.linux_distribution = self.backup_linux_distribution
        distro.os_release_attr = self.backup_distro_os_release_attr
        package_manager.get_tdnf_version = self.backup_get_tdnf_version
        self.runtime.env_layer.run_command_output = self.backup_run_command_output


if __name__ == '__main__':
    unittest.main()

