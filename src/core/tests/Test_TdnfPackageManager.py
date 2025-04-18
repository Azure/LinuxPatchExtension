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


class TestTdnfPackageManager(unittest.TestCase):
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

    def mock_write_with_retry_raise_exception(self, file_path_or_handle, data, mode='a+'):
        raise Exception
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
        """Unit test for tdnf package manager with inclusion and Classification = Critical. Returns no packages since classifications are not available in Azure Linux"""
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
        self.assertTrue(available_updates == [])
        self.assertTrue(package_versions == [])

    def test_inclusion_type_other(self):
        """Unit test for tdnf package manager with inclusion and Classification = Other. All packages are considered are 'Other' since AzLinux does not have patch classification"""
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

    def test_revert_auto_os_update_to_system_default_success_with_dnf_automatic(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')

        # setup current auto OS update config
        package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf_automatic_os_patch_configuration_settings = 'apply_updates = no\ndownload_updates = no\n'
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, dnf_automatic_os_patch_configuration_settings)

        # setup backup for system default auto OS update config
        package_manager.image_default_patch_configuration_backup_path = os.path.join(self.runtime.execution_config.config_folder, Constants.IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH)
        backup_image_default_patch_configuration_json = {
            "dnf-automatic": {
                "apply_updates": "yes",
                "download_updates": "yes",
                "enable_on_reboot": True,
                "installation_state": True
            }
        }
        self.runtime.write_to_file(package_manager.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(backup_image_default_patch_configuration_json)))

        package_manager.revert_auto_os_update_to_system_default()
        reverted_dnf_automatic_patch_configuration_settings = self.runtime.env_layer.file_system.read_with_retry(package_manager.dnf_automatic_configuration_file_path)
        self.assertTrue(reverted_dnf_automatic_patch_configuration_settings is not None)
        self.assertTrue('download_updates = yes' in reverted_dnf_automatic_patch_configuration_settings)
        self.assertTrue('apply_updates = yes' in reverted_dnf_automatic_patch_configuration_settings)

    def test_revert_auto_os_update_to_system_default_success_with_dnf_automatic_not_installed(self):
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')

        # setup backup for system default auto OS update config
        package_manager.image_default_patch_configuration_backup_path = os.path.join(self.runtime.execution_config.config_folder, Constants.IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH)
        backup_image_default_patch_configuration_json = {
            "dnf-automatic": {
                "apply_updates": "",
                "download_updates": "",
                "enable_on_reboot": False,
                "installation_state": False
            },
        }
        self.runtime.write_to_file(package_manager.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(backup_image_default_patch_configuration_json)))

        package_manager.revert_auto_os_update_to_system_default()
        self.assertFalse(os.path.exists(package_manager.dnf_automatic_configuration_file_path))

    def test_revert_auto_os_update_to_system_default_success_with_dnf_automatic_installed_but_no_config_value(self):
        self.runtime.set_legacy_test_type('RevertToImageDefault')
        package_manager = self.container.get('package_manager')

        # setup current auto OS update config
        package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf_automatic_os_patch_configuration_settings = 'test_value = yes\n'
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, dnf_automatic_os_patch_configuration_settings)

        # setup backup for system default auto OS update config
        package_manager.image_default_patch_configuration_backup_path = os.path.join(self.runtime.execution_config.config_folder, Constants.IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH)
        backup_image_default_patch_configuration_json = {
            "dnf-automatic": {
                "apply_updates": "",
                "download_updates": "",
                "enable_on_reboot": False,
                "installation_state": True
            },
        }
        self.runtime.write_to_file(package_manager.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(backup_image_default_patch_configuration_json)))

        package_manager.revert_auto_os_update_to_system_default()
        reverted_dnf_automatic_patch_configuration_settings = self.runtime.env_layer.file_system.read_with_retry(package_manager.dnf_automatic_configuration_file_path)
        self.assertTrue(reverted_dnf_automatic_patch_configuration_settings is not None)
        self.assertTrue('download_updates =\n' in reverted_dnf_automatic_patch_configuration_settings)
        self.assertTrue('apply_updates = \n' in reverted_dnf_automatic_patch_configuration_settings)

    def test_revert_auto_os_update_to_system_default_backup_config_does_not_exist(self):
        # arrange capture std IO
        captured_output = StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured_output

        self.runtime.set_legacy_test_type('RevertToImageDefault')
        package_manager = self.container.get('package_manager')

        # setup current auto OS update config
        package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf_automatic_os_patch_configuration_settings = 'apply_updates = no\ndownload_updates = no\n'
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, dnf_automatic_os_patch_configuration_settings)

        # backup for system default auto OS update config is NOT setup

        package_manager.revert_auto_os_update_to_system_default()
        # restore sys.stdout output
        sys.stdout = original_stdout

        # assert
        output = captured_output.getvalue()
        self.assertTrue("[TDNF] Since the backup is invalid or does not exist for current service, we won't be able to revert auto OS patch settings to their system default value. [Service=dnf-automatic]" in output)
        reverted_dnf_automatic_patch_configuration_settings = self.runtime.env_layer.file_system.read_with_retry(package_manager.dnf_automatic_configuration_file_path)
        self.assertTrue(reverted_dnf_automatic_patch_configuration_settings is not None)
        self.assertTrue('download_updates = no' in reverted_dnf_automatic_patch_configuration_settings)
        self.assertTrue('apply_updates = no' in reverted_dnf_automatic_patch_configuration_settings)

    def test_revert_auto_os_update_to_system_default_backup_config_invalid(self):
        # arrange capture std IO
        captured_output = StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured_output

        self.runtime.set_legacy_test_type('RevertToImageDefault')
        package_manager = self.container.get('package_manager')

        # setup current auto OS update config
        package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf_automatic_os_patch_configuration_settings = 'apply_updates = no\ndownload_updates = no\n'
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, dnf_automatic_os_patch_configuration_settings)

        # setup backup for system default auto OS update config
        package_manager.image_default_patch_configuration_backup_path = os.path.join(self.runtime.execution_config.config_folder, Constants.IMAGE_DEFAULT_PATCH_CONFIGURATION_BACKUP_PATH)
        backup_image_default_patch_configuration_json = {
            "dnf-automatic": {
                "apply_updates": "yes",
                "download_updates": "yes",
                "enable_on_reboot": True
            }
        }
        self.runtime.write_to_file(package_manager.image_default_patch_configuration_backup_path, '{0}'.format(json.dumps(backup_image_default_patch_configuration_json)))

        package_manager.revert_auto_os_update_to_system_default()
        # restore sys.stdout output
        sys.stdout = original_stdout

        # assert
        output = captured_output.getvalue()
        self.assertTrue("[TDNF] Since the backup is invalid or does not exist for current service, we won't be able to revert auto OS patch settings to their system default value. [Service=dnf-automatic]" in output)
        reverted_dnf_automatic_patch_configuration_settings = self.runtime.env_layer.file_system.read_with_retry(package_manager.dnf_automatic_configuration_file_path)
        self.assertTrue(reverted_dnf_automatic_patch_configuration_settings is not None)
        self.assertTrue('download_updates = no' in reverted_dnf_automatic_patch_configuration_settings)
        self.assertTrue('apply_updates = no' in reverted_dnf_automatic_patch_configuration_settings)


if __name__ == '__main__':
    unittest.main()

