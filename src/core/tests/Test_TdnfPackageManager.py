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
from core.src.bootstrap.Constants import Constants
from core.src.package_managers import TdnfPackageManager
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.LegacyEnvLayerExtensions import LegacyEnvLayerExtensions
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
        self.assertEqual(8, len(available_updates))
        self.assertEqual(8, len(package_versions))
        self.assertEqual("azurelinux-release.noarch", available_updates[0])
        self.assertEqual("azurelinux-repos-ms-oss.noarch", available_updates[1])
        self.assertEqual("3.0-16.azl3", package_versions[0])
        self.assertEqual("3.0-3.azl3", package_versions[1])

        # test for get_package_size
        cmd = package_manager.single_package_upgrade_cmd + "curl"
        code, out = self.runtime.env_layer.run_command_output(cmd, False, False)
        size = package_manager.get_package_size(out)
        self.assertEqual(size, "661.34k")

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
        self.assertEqual(8, len(available_updates))
        self.assertEqual(8, len(package_versions))
        self.assertEqual("azurelinux-release.noarch", available_updates[0])
        self.assertEqual("3.0-16.azl3", package_versions[0])
        self.assertEqual("azurelinux-repos-ms-oss.noarch", available_updates[1])
        self.assertEqual("3.0-3.azl3", package_versions[1])
        self.assertEqual("libseccomp.x86_64", available_updates[2])
        self.assertEqual("2.5.4-1.azl3", package_versions[2])
        self.assertEqual("libxml2.x86_64", available_updates[3])
        self.assertEqual("2.11.5-1.azl3", package_versions[3])
        self.assertEqual("dracut.x86_64", available_updates[4])
        self.assertEqual("102-7.azl3", package_versions[4])
        self.assertEqual("hyperv-daemons-license.noarch", available_updates[5])
        self.assertEqual("6.6.78.1-1.azl3", package_versions[5])
        self.assertEqual("hypervvssd.x86_64", available_updates[6])
        self.assertEqual("6.6.78.1-1.azl3", package_versions[6])
        self.assertEqual("hypervkvpd.x86_64", available_updates[7])
        self.assertEqual("6.6.78.1-1.azl3", package_versions[7])

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
        self.assertEqual(8, len(available_updates))
        self.assertEqual(8, len(package_versions))
        self.assertEqual("azurelinux-release.noarch", available_updates[0])
        self.assertEqual("3.0-16.azl3", package_versions[0])
        self.assertEqual("azurelinux-repos-ms-oss.noarch", available_updates[1])
        self.assertEqual("3.0-3.azl3", package_versions[1])
        self.assertEqual("libseccomp.x86_64", available_updates[2])
        self.assertEqual("2.5.4-1.azl3", package_versions[2])
        self.assertEqual("libxml2.x86_64", available_updates[3])
        self.assertEqual("2.11.5-1.azl3", package_versions[3])
        self.assertEqual("dracut.x86_64", available_updates[4])
        self.assertEqual("102-7.azl3", package_versions[4])
        self.assertEqual("hyperv-daemons-license.noarch", available_updates[5])
        self.assertEqual("6.6.78.1-1.azl3", package_versions[5])
        self.assertEqual("hypervvssd.x86_64", available_updates[6])
        self.assertEqual("6.6.78.1-1.azl3", package_versions[6])
        self.assertEqual("hypervkvpd.x86_64", available_updates[7])
        self.assertEqual("6.6.78.1-1.azl3", package_versions[7])

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
        """Unit test for yum with Inclusion which does not exist & NotSelected Classifications"""
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


if __name__ == '__main__':
    unittest.main()

