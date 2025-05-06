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
import json
import os
import unittest
from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.LegacyEnvLayerExtensions import LegacyEnvLayerExtensions
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestYumPackageManager(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.YUM)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    #region Mocks
    def mock_do_processes_require_restart(self):
        raise Exception

    def mock_write_with_retry_raise_exception(self, file_path_or_handle, data, mode='a+'):
        raise Exception

    def mock_linux7_distribution_to_return_redhat(self):
        return ['Red Hat Enterprise Linux Server', '7', 'Maipo']

    def mock_linux8_distribution_to_return_redhat(self):
        return ['Red Hat Enterprise Linux Server', '8', 'Ootpa']
    
    def mock_centos_linux_distribution(self):
        return ['CentOS Linux', '7.9.2009', 'Core']
    
    def mock_get_all_updates(self, cached):
        return [], []
    
    def mock_get_security_updates(self):
        return [], []
    
    def mock_bad_run_command_output(self, cmd, no_output=False, chk_err=False):
        return 1, "bad cmd"
    #endregion Mocks

    def mock_do_processes_require_restart_raise_exception(self):
        raise Exception

    def test_package_manager_no_updates(self):
        """Unit test for yum package manager with no updates"""
        # Path change
        self.runtime.set_legacy_test_type('SadPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertEqual(len(available_updates), 0)
        self.assertEqual(len(package_versions), 0)

    def test_package_manager_unaligned_updates(self):
        """Unit test for yum package manager with multi-line updates"""
        # Path change
        self.runtime.set_legacy_test_type('UnalignedPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertEqual(len(available_updates), 6)
        self.assertEqual(len(package_versions), 6)

    def test_do_processes_require_restart(self):
        """Unit test for yum package manager"""

        # Restart required
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.assertTrue(package_manager.is_reboot_pending())

        # Restart not required
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.assertFalse(package_manager.is_reboot_pending())

        # Fake exception
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        backup_do_processes_require_restart = package_manager.do_processes_require_restart
        package_manager.do_processes_require_restart = self.mock_do_processes_require_restart
        self.assertTrue(package_manager.is_reboot_pending())    # returns true because the safe default if a failure occurs is 'true'
        package_manager.do_processes_require_restart = backup_do_processes_require_restart

    def test_package_manager(self):
        """Unit test for yum package manager"""
        self.runtime.set_legacy_test_type('HappyPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(available_updates), 5)
        self.assertEqual(len(package_versions), 5)
        self.assertEqual(available_updates[0], "selinux-policy.noarch")
        self.assertEqual(available_updates[1], "selinux-policy-targeted.noarch")
        self.assertEqual(package_versions[0], "3.13.1-102.el7_3.16")
        self.assertEqual(package_versions[1], "3.13.1-102.el7_3.16")

        # test for get_package_size
        cmd = package_manager.single_package_upgrade_cmd + "sudo"
        code, out = self.runtime.env_layer.run_command_output(cmd, False, False)
        size = package_manager.get_package_size(out)
        self.assertEqual(size, "735 k")

        # test for all available versions
        package_versions = package_manager.get_all_available_versions_of_package("kernel")
        self.assertEqual(len(package_versions), 7)
        self.assertEqual(package_versions[0], '3.10.0-862.el7')
        self.assertEqual(package_versions[1], '3.10.0-862.2.3.el7')
        self.assertEqual(package_versions[2], '3.10.0-862.3.2.el7')
        self.assertEqual(package_versions[3], '3.10.0-862.3.3.el7')
        self.assertEqual(package_versions[4], '3.10.0-862.6.3.el7')
        self.assertEqual(package_versions[5], '3.10.0-862.9.1.el7')
        self.assertEqual(package_versions[6], '3.10.0-862.11.6.el7')

        # test for get_dependent_list
        # legacy_test_type ='HappyPath'
        dependent_list = package_manager.get_dependent_list(["selinux-policy.noarch"])
        self.assertIsNotNone(dependent_list)
        self.assertEqual(len(dependent_list), 1)
        self.assertEqual(dependent_list[0], "selinux-policy-targeted.noarch")

        # test for get_dependent_list with 'install' instead of update
        dependent_list = package_manager.get_dependent_list(["kmod-kvdo.x86_64"])
        self.assertIsNotNone(dependent_list)
        self.assertEqual(len(dependent_list), 1)
        self.assertEqual(dependent_list[0], "kernel.x86_64")

        # test for epoch removal
        self.assertEqual(package_manager.get_package_version_without_epoch('2.02.177-4.el7'), '2.02.177-4.el7')
        self.assertEqual(package_manager.get_package_version_without_epoch('7:2.02.177-4.el7'), '2.02.177-4.el7')
        self.assertEqual(package_manager.get_package_version_without_epoch('7:2.02.177-4.el7_5:56'), '2.02.177-4.el7_5:56')
        self.assertEqual(package_manager.get_package_version_without_epoch(''), '')

        # test install cmd
        packages = ['kernel.x86_64', 'selinux-policy-targeted.noarch']
        package_versions = ['2.02.177-4.el7', '3.10.0-862.el7']
        cmd = package_manager.get_install_command('sudo yum -y install ', packages, package_versions)
        self.assertEqual(cmd, 'sudo yum -y install kernel-2.02.177-4.el7.x86_64 selinux-policy-targeted-3.10.0-862.el7.noarch')
        packages = ['kernel.x86_64']
        package_versions = ['2.02.177-4.el7']
        cmd = package_manager.get_install_command('sudo yum -y install ', packages, package_versions)
        self.assertEqual(cmd, 'sudo yum -y install kernel-2.02.177-4.el7.x86_64')
        packages = ['kernel.x86_64', 'kernel.i686']
        package_versions = ['2.02.177-4.el7', '2.02.177-4.el7']
        cmd = package_manager.get_install_command('sudo yum -y install ', packages, package_versions)
        self.assertEqual(cmd, 'sudo yum -y install kernel-2.02.177-4.el7.x86_64 kernel-2.02.177-4.el7.i686')

        self.runtime.set_legacy_test_type('ExceptionPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for get_available_updates
        # legacy_test_type ='Exception Path'
        try:
            package_manager.get_available_updates(package_filter)
        except Exception as exception:
            self.assertTrue(str(exception))
        else:
            self.assertFalse(1 != 2, 'Exception did not occur and test failed.')

        # test for get_dependent_list
        # legacy_test_type ='Exception Path'
        try:
            package_manager.get_dependent_list(["man"])
        except Exception as exception:
            self.assertTrue(str(exception))
        else:
            self.assertFalse(1 != 2, 'Exception did not occur and test failed.')

    def test_install_package_success(self):
        """Unit test for install package success"""
        self.runtime.set_legacy_test_type('HappyPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for successfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('selinux-policy.noarch', '3.13.1-102.el7_3.16', simulate=True), Constants.INSTALLED)

    def test_install_package_failure(self):
        """Unit test for install package failure"""
        self.runtime.set_legacy_test_type('FailInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for unsuccessfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('selinux-policy', '3.13.1-102.el7_3.16', simulate=True), Constants.FAILED)

    def test_install_package_obsoleted(self):
        """Unit test for install package failure"""
        self.runtime.set_legacy_test_type('FailInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for unsuccessfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('rdma.noarch', '7.3_4.7_rc2-6.el7_3', simulate=True), Constants.INSTALLED)

    def test_install_package_replaced(self):
        """Unit test for install package failure"""
        self.runtime.set_legacy_test_type('FailInstallPath')

        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for unsuccessfully installing a package
        self.assertEqual(package_manager.install_update_and_dependencies_and_get_status('python-rhsm.x86_64', '1.19.10-1.el7_4', simulate=True), Constants.INSTALLED)

    def test_get_product_name(self):
        """Unit test for retrieving product Name"""
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)
        print(package_manager.get_product_name("bash.x86_64"))
        self.assertEqual(package_manager.get_product_name("bash.x86_64"), "bash.x86_64")
        self.assertEqual(package_manager.get_product_name("firefox.x86_64"), "firefox.x86_64")
        self.assertEqual(package_manager.get_product_name("test.noarch"), "test.noarch")
        self.assertEqual(package_manager.get_product_name("noextension"), "noextension")
        self.assertEqual(package_manager.get_product_name("noextension.ext"), "noextension.ext")

    def test_get_product_name_without_arch(self):
        """Unit test for retrieving product Name"""
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)
        print(package_manager.get_product_name("bash.x86_64"))
        self.assertEqual(package_manager.get_product_name_without_arch("bash.x86_64"), "bash")
        self.assertEqual(package_manager.get_product_name_without_arch("firefox.x86_64"), "firefox")
        self.assertEqual(package_manager.get_product_name_without_arch("test.noarch"), "test")
        self.assertEqual(package_manager.get_product_name_without_arch("noextension"), "noextension")
        self.assertEqual(package_manager.get_product_name_without_arch("noextension.ext"), "noextension.ext")

    def test_inclusion_type_all(self):
        """Unit test for yum package manager Classification = all and IncludedPackageNameMasks not specified."""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.UNCLASSIFIED]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(available_updates), 5)
        self.assertEqual(len(package_versions), 5)
        self.assertEqual(available_updates[0], "selinux-policy.noarch")
        self.assertEqual(package_versions[0], "3.13.1-102.el7_3.16")
        self.assertEqual(available_updates[1], "selinux-policy-targeted.noarch")
        self.assertEqual(package_versions[1], "3.13.1-102.el7_3.16")
        self.assertEqual(available_updates[2], "libgcc.i686")
        self.assertEqual(package_versions[2], "4.8.5-28.el7")
        self.assertEqual(available_updates[3], "tar.x86_64")
        self.assertEqual(package_versions[3], "2:1.26-34.el7")
        self.assertEqual(available_updates[4], "tcpdump.x86_64")
        self.assertEqual(package_versions[4], "14:4.9.2-3.el7")

    def test_inclusion_type_critical(self):
        """Unit test for yum package manager with inclusion and Classification = Critical"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.CRITICAL]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        argument_composer.patches_to_include = ["ssh", "tar*"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(available_updates), 2)
        self.assertEqual(len(package_versions), 2)
        self.assertEqual(available_updates[0], "libgcc.i686")
        self.assertEqual(available_updates[1], "tar.x86_64")
        self.assertEqual(package_versions[0], "4.8.5-28.el7")
        self.assertEqual(package_versions[1], "2:1.26-34.el7")

    def test_inclusion_type_other(self):
        """Unit test for yum package manager with inclusion and Classification = Other"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.OTHER]
        argument_composer.patches_to_include = ["ssh", "tcpdump"]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(available_updates), 4)
        self.assertEqual(len(package_versions), 4)
        self.assertEqual(available_updates[0], "selinux-policy.noarch")
        self.assertEqual(package_versions[0], "3.13.1-102.el7_3.16")
        self.assertEqual(available_updates[1], "selinux-policy-targeted.noarch")
        self.assertEqual(package_versions[1], "3.13.1-102.el7_3.16")
        self.assertEqual(available_updates[2], "tar.x86_64")
        self.assertEqual(package_versions[2], "2:1.26-34.el7")
        self.assertEqual(available_updates[3], "tcpdump.x86_64")
        self.assertEqual(package_versions[3], "14:4.9.2-3.el7")

    def test_inclusion_only(self):
        """Unit test for yum package manager with inclusion only and NotSelected Classifications"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.UNCLASSIFIED]
        argument_composer.patches_to_include = ["ssh", "tar*"]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(available_updates), 1)
        self.assertEqual(len(package_versions), 1)
        self.assertEqual(available_updates[0], "tar.x86_64")
        self.assertEqual(package_versions[0], "2:1.26-34.el7")

    def test_inclusion_dependency_only(self):
        """Unit test for yum with test dependencies in Inclusion & NotSelected Classifications"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container. get('package_manager')
        self.assertIsNotNone(package_manager)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.UNCLASSIFIED]
        argument_composer.patches_to_include = ["ssh", "selinux-policy-targeted.noarch"]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(available_updates), 1)
        self.assertEqual(len(package_versions), 1)
        self.assertEqual(available_updates[0], "selinux-policy-targeted.noarch")
        self.assertEqual(package_versions[0], "3.13.1-102.el7_3.16")

    def test_inclusion_notexist(self):
        """Unit test for yum with Inclusion which does not exist & NotSelected Classifications"""
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.UNCLASSIFIED]
        argument_composer.patches_to_include = ["ssh"]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        # test for get_available_updates
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(available_updates), 0)
        self.assertEqual(len(package_versions), 0)

    def test_ssl_certificate_issue_type1_fix_success(self):
        self.runtime.set_legacy_test_type('SSLCertificateIssueType1HappyPathAfterFix')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        output = package_manager.invoke_package_manager(package_manager.yum_check)
        self.assertTrue(len(output) > 0)

    def test_ssl_certificate_issue_type1_fix_fail(self):
        self.runtime.set_legacy_test_type('SSLCertificateIssueType1SadPathAfterFix')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        self.assertRaises(Exception, package_manager.invoke_package_manager, package_manager.yum_check)

    def test_ssl_certificate_issue_type2_fix_success(self):
        self.runtime.set_legacy_test_type('SSLCertificateIssueType2HappyPathAfterFix')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        output = package_manager.invoke_package_manager(package_manager.yum_check)
        self.assertTrue(len(output) > 0)

    def test_ssl_certificate_issue_type2_fix_fail(self):
        self.runtime.set_legacy_test_type('SSLCertificateIssueType2SadPathAfterFix')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        self.assertRaises(Exception, package_manager.invoke_package_manager, package_manager.yum_check)

    def test_ssl_certificate_issue_type3_fix_success(self):
        self.runtime.set_legacy_test_type('SSLCertificateIssueType3HappyPathAfterFix')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        output = package_manager.invoke_package_manager(package_manager.yum_check)
        self.assertTrue(len(output) > 0)

    def test_ssl_certificate_issue_type3_fix_fail(self):
        self.runtime.set_legacy_test_type('SSLCertificateIssueType3SadPathAfterFix')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        self.assertRaises(Exception, package_manager.invoke_package_manager, package_manager.yum_check)

    def test_auto_issue_mitigation_should_raise_exception_if_error_repeats(self):
        self.runtime.set_legacy_test_type('IssueMitigationRetryExitAfterMultipleAttempts')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        self.assertRaises(Exception, package_manager.invoke_package_manager, package_manager.yum_check)

    def test_auto_issue_mitigation_should_raise_exception_if_retries_are_exhausted(self):
        self.runtime.set_legacy_test_type('IssueMitigationRetryExitAfterMultipleAttempts')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        with self.assertRaises(Exception):
            package_manager.try_mitigate_issues_if_any('testcmd', 0, 'Test out', retry_count = Constants.MAX_RETRY_ATTEMPTS_FOR_ERROR_MITIGATION + 1)

    def test_auto_issue_mitigation_when_error_repeats_raise_exception_disabled(self):
        expected_out = "Error: Failed to download metadata for repo 'rhui-rhel-8-for-x86_64-baseos-rhui-rpms': Cannot download repomd.xml: Cannot download repodata/repomd.xml: All mirrors were tried"
        self.runtime.set_legacy_test_type('IssueMitigationRetryExitAfterMultipleAttempts')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        code, out = package_manager.try_mitigate_issues_if_any('testcmd', 0, expected_out, raise_on_exception = False)

        self.assertEqual(out, expected_out)
        self.assertTrue(code >= 0)

    def test_auto_issue_mitigation_when_retries_are_exhausted_raise_exception_disabled(self):
        expected_out = "Error: Failed to download metadata for repo 'rhui-rhel-8-for-x86_64-baseos-rhui-rpms': Cannot download repomd.xml: Cannot download repodata/repomd.xml: All mirrors were tried"
        self.runtime.set_legacy_test_type('IssueMitigationRetryExitAfterMultipleAttempts')

        package_manager = self.container.get('package_manager')
        self.assertTrue(package_manager)

        code, out = package_manager.try_mitigate_issues_if_any('testcmd', 0, expected_out, retry_count = Constants.MAX_RETRY_ATTEMPTS_FOR_ERROR_MITIGATION + 1, raise_on_exception = False)

        self.assertEqual(out, expected_out)
        self.assertTrue(code >= 0)

    def test_disable_auto_os_updates_with_uninstalled_services(self):
        # no services are installed on the machine. expected o/p: function will complete successfully. Backup file will be created with default values, no auto OS update configuration settings will be updated as there are none
        self.runtime.set_legacy_test_type('SadPath')
        package_manager = self.container.get('package_manager')
        package_manager.disable_auto_os_update()
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)

        # validating backup for yum-cron
        self.assertTrue(Constants.YumAutoOSUpdateServices.YUM_CRON in image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.YUM_CRON][package_manager.yum_cron_download_updates_identifier_text], "")
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.YUM_CRON][package_manager.yum_cron_apply_updates_identifier_text], "")
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.YUM_CRON][package_manager.yum_cron_enable_on_reboot_identifier_text], False)
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.YUM_CRON][package_manager.yum_cron_installation_state_identifier_text], False)

        # validating backup for dnf-automatic
        self.assertTrue(Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC in image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC][package_manager.dnf_automatic_download_updates_identifier_text], "")
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC][package_manager.dnf_automatic_apply_updates_identifier_text], "")
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC][package_manager.dnf_automatic_enable_on_reboot_identifier_text], False)
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC][package_manager.dnf_automatic_installation_state_identifier_text], False)

        # validating backup for packagekit
        self.assertTrue(Constants.YumAutoOSUpdateServices.PACKAGEKIT in image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT][package_manager.packagekit_download_updates_identifier_text], "")
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT][package_manager.packagekit_apply_updates_identifier_text], "")
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT][package_manager.packagekit_enable_on_reboot_identifier_text], False)
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT][package_manager.packagekit_installation_state_identifier_text], False)

    def test_disable_auto_os_updates_with_installed_services(self):
        # all services are installed and contain valid configurations. expected o/p All services will be disabled and backup file should reflect default settings for all
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')

        package_manager.yum_cron_configuration_settings_file_path = os.path.join(self.runtime.execution_config.config_folder, "yum-cron.conf")
        yum_cron_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.yum_cron_configuration_settings_file_path, yum_cron_os_patch_configuration_settings)

        package_manager.dnf_automatic_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "automatic.conf")
        dnf_automatic_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.dnf_automatic_configuration_file_path, dnf_automatic_os_patch_configuration_settings)

        package_manager.packagekit_configuration_file_path = os.path.join(self.runtime.execution_config.config_folder, "PackageKit.conf")
        packagekit_os_patch_configuration_settings = 'WritePreparedUpdates = true\nGetPreparedUpdates = true\n'
        self.runtime.write_to_file(package_manager.packagekit_configuration_file_path, packagekit_os_patch_configuration_settings)

        package_manager.disable_auto_os_update()
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())
        image_default_patch_configuration_backup = json.loads(self.runtime.env_layer.file_system.read_with_retry(package_manager.image_default_patch_configuration_backup_path))
        self.assertTrue(image_default_patch_configuration_backup is not None)

        # validating backup for yum-cron
        self.assertTrue(Constants.YumAutoOSUpdateServices.YUM_CRON in image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.YUM_CRON][package_manager.yum_cron_download_updates_identifier_text], "yes")
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.YUM_CRON][package_manager.yum_cron_apply_updates_identifier_text], "yes")
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.YUM_CRON][package_manager.yum_cron_enable_on_reboot_identifier_text], True)
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.YUM_CRON][package_manager.yum_cron_installation_state_identifier_text], True)

        # validating backup for dnf-automatic
        self.assertTrue(Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC in image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC][package_manager.dnf_automatic_download_updates_identifier_text], "yes")
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC][package_manager.dnf_automatic_apply_updates_identifier_text], "yes")
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC][package_manager.dnf_automatic_enable_on_reboot_identifier_text], True)
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.DNF_AUTOMATIC][package_manager.dnf_automatic_installation_state_identifier_text], True)

        # validating backup for packagekit
        self.assertTrue(Constants.YumAutoOSUpdateServices.PACKAGEKIT in image_default_patch_configuration_backup)
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT][package_manager.packagekit_download_updates_identifier_text], "true")
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT][package_manager.packagekit_apply_updates_identifier_text], "true")
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT][package_manager.packagekit_enable_on_reboot_identifier_text], True)
        self.assertEqual(image_default_patch_configuration_backup[Constants.YumAutoOSUpdateServices.PACKAGEKIT][package_manager.packagekit_installation_state_identifier_text], True)

    def test_disable_auto_os_update_failure(self):
        # disable with non existing log file
        package_manager = self.container.get('package_manager')

        self.assertRaises(Exception, package_manager.disable_auto_os_update)
        self.assertTrue(package_manager.image_default_patch_configuration_backup_exists())

    def test_update_image_default_patch_mode(self):
        package_manager = self.container.get('package_manager')
        package_manager.os_patch_configuration_settings_file_path = package_manager.yum_cron_configuration_settings_file_path = os.path.join(self.runtime.execution_config.config_folder, "yum-cron.conf")

        # disable apply_udpates when enabled by default
        yum_cron_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.yum_cron_configuration_settings_file_path, yum_cron_os_patch_configuration_settings)

        package_manager.update_os_patch_configuration_sub_setting(package_manager.yum_cron_apply_updates_identifier_text, "no", package_manager.yum_cron_config_pattern_match_text)
        yum_cron_os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(package_manager.yum_cron_configuration_settings_file_path)
        self.assertTrue(yum_cron_os_patch_configuration_settings_file_path_read is not None)
        self.assertTrue('apply_updates = no' in yum_cron_os_patch_configuration_settings_file_path_read)
        self.assertTrue('download_updates = yes' in yum_cron_os_patch_configuration_settings_file_path_read)

        # disable download_updates when enabled by default
        yum_cron_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, yum_cron_os_patch_configuration_settings)
        package_manager.update_os_patch_configuration_sub_setting(package_manager.yum_cron_download_updates_identifier_text, "no", package_manager.yum_cron_config_pattern_match_text)
        yum_cron_os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(package_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(yum_cron_os_patch_configuration_settings_file_path_read is not None)
        self.assertTrue('apply_updates = yes' in yum_cron_os_patch_configuration_settings_file_path_read)
        self.assertTrue('download_updates = no' in yum_cron_os_patch_configuration_settings_file_path_read)

        # disable apply_updates when default patch mode settings file is empty
        yum_cron_os_patch_configuration_settings = ''
        self.runtime.write_to_file(package_manager.os_patch_configuration_settings_file_path, yum_cron_os_patch_configuration_settings)
        package_manager.update_os_patch_configuration_sub_setting(package_manager.yum_cron_apply_updates_identifier_text, "no", package_manager.yum_cron_config_pattern_match_text)
        yum_cron_os_patch_configuration_settings_file_path_read = self.runtime.env_layer.file_system.read_with_retry(package_manager.os_patch_configuration_settings_file_path)
        self.assertTrue(yum_cron_os_patch_configuration_settings_file_path_read is not None)
        self.assertTrue('download_updates' not in yum_cron_os_patch_configuration_settings_file_path_read)
        self.assertTrue('apply_updates = no' in yum_cron_os_patch_configuration_settings_file_path_read)

    def test_update_image_default_patch_mode_raises_exception(self):
        package_manager = self.container.get('package_manager')
        package_manager.yum_cron_configuration_settings_file_path = os.path.join(self.runtime.execution_config.config_folder, "yum-cron.conf")
        yum_cron_os_patch_configuration_settings = 'apply_updates = yes\ndownload_updates = yes\n'
        self.runtime.write_to_file(package_manager.yum_cron_configuration_settings_file_path, yum_cron_os_patch_configuration_settings)
        self.runtime.env_layer.file_system.write_with_retry = self.mock_write_with_retry_raise_exception
        self.assertRaises(Exception, package_manager.update_os_patch_configuration_sub_setting)

    def test_is_reboot_pending_return_true_when_exception_raised(self):
        package_manager = self.container.get('package_manager')
        backup_do_process_require_restart = package_manager.do_processes_require_restart
        package_manager.do_processes_require_restart = self.mock_do_processes_require_restart_raise_exception

        self.assertTrue(package_manager.is_reboot_pending())

        package_manager.do_processes_require_restart = backup_do_process_require_restart

    def test_obsolete_packages_should_not_considered_in_available_updates(self):
        self.runtime.set_legacy_test_type('ObsoletePackages')
        package_manager = self.container.get('package_manager')
        package_filter = self.container.get('package_filter')
        available_updates, package_versions = package_manager.get_available_updates(package_filter)
        self.assertEqual(len(available_updates), 1)
        self.assertEqual(len(package_versions), 1)
        self.assertTrue(available_updates[0] == "grub2-tools.x86_64")
        self.assertTrue(package_versions[0] == "1:2.02-142.el8")

    def test_rhel7_image_with_security_plugin(self):
        """Unit test for yum package manager rhel images below 8 and Classification = Security"""
        # mock linux_distribution
        backup_envlayer_platform_linux_distribution = LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution
        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = self.mock_linux7_distribution_to_return_redhat

        self.__assert_test_rhel8_image()

        # restore linux_distribution
        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = backup_envlayer_platform_linux_distribution

    def test_rhel8_image_higher_no_security_plugin(self):
        """Unit test for yum package manager rhel images >= 8 and Classification = Security"""
        # mock linux_distribution
        backup_envlayer_platform_linux_distribution = LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution
        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = self.mock_linux8_distribution_to_return_redhat

        self.__assert_test_rhel8_image()

        # restore linux_distribution
        LegacyEnvLayerExtensions.LegacyPlatform.linux_distribution = backup_envlayer_platform_linux_distribution

    def __assert_test_rhel8_image(self):
        self.runtime.set_legacy_test_type('HappyPath')
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        self.runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = [Constants.PackageClassification.SECURITY]
        argument_composer.patches_to_include = ["ssh", "tcpdump"]
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        self.runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.container = self.runtime.container

        package_filter = self.container.get('package_filter')
        self.assertIsNotNone(package_filter)

        available_updates, package_versions = package_manager.get_available_updates(package_filter)

        # test for get_available_updates
        self.assertIsNotNone(available_updates)
        self.assertIsNotNone(package_versions)
        self.assertEqual(len(available_updates), 2)
        self.assertEqual(len(package_versions), 2)
        self.assertEqual(available_updates[0], "libgcc.i686")
        self.assertEqual(package_versions[0], "4.8.5-28.el7")
        self.assertEqual(available_updates[1], "tcpdump.x86_64")
        self.assertEqual(package_versions[1], "14:4.9.2-3.el7")

    def test_get_dependent_list_yum_version_4(self):
        # Creating new RuntimeCompositor with test_type YumVersion4Dependency because there are some command runs in constructor of YumPackageManager
        # for which the sample output is in the test_type YumVersion4Dependency.
        self.runtime.stop()  # First stopping the existing runtime
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.YUM, test_type="YumVersion4Dependency")

        self.container = self.runtime.container
        package_manager = self.container.get('package_manager')
        dependent_list = package_manager.get_dependent_list(["iptables.x86_64"])
        self.assertEqual(len(dependent_list), 2)
        self.assertEqual(dependent_list[0], "iptables-ebtables.x86_64")
        self.assertEqual(dependent_list[1], "iptables-libs.x86_64")

    def test_get_dependent_list_yum_version_4_update_in_two_lines(self):
        # Creating new RuntimeCompositor with test_type YumVersion4Dependency because there are some command runs in constructor of YumPackageManager
        # for which the sample output is in the test_type YumVersion4Dependency.
        self.runtime.stop()  # First stopping the existing runtime
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.YUM, test_type="YumVersion4DependencyInTwoLines")

        self.container = self.runtime.container
        package_manager = self.container.get('package_manager')
        dependent_list = package_manager.get_dependent_list(["polkit.x86_64"])
        self.assertEqual(len(dependent_list), 1)
        self.assertEqual(dependent_list[0], "polkit-libs.x86_64")

    def test_get_dependent_list_yum_version_4_update_in_two_lines_with_unexpected_output(self):
        # This test is for adding code coverage for code handling unexpected output in the command for get dependencies.
        # There are two packages in the output and for the second package i.e. polkit-libs, the package name is not present. Only other package details are present.
        # So, there are 0 dependencies expected.

        # Creating new RuntimeCompositor with test_type YumVersion4Dependency because there are some command runs in constructor of YumPackageManager
        # for which the sample output is in the test_type YumVersion4Dependency.
        self.runtime.stop()  # First stopping the existing runtime
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.YUM, test_type="YumVersion4DependencyInTwoLinesWithUnexpectedOutput")

        self.container = self.runtime.container
        package_manager = self.container.get('package_manager')
        dependent_list = package_manager.get_dependent_list(["polkit.x86_64"])
        self.assertEqual(len(dependent_list), 0)

    def test_get_other_updates_exception(self):
        """ test get_other_updates throw exception path. """
        # Set up
        package_manager = self.runtime.container.get('package_manager')
        package_manager.get_all_updates = self.mock_get_all_updates
        package_manager.get_security_updates = self.mock_get_security_updates
        self.runtime.env_layer.platform.linux_distribution = self.mock_centos_linux_distribution
        
        # Act
        with self.assertRaises(Exception) as context:
            package_manager.get_other_updates()
            
        # Assert
        print(str(context.exception))
        self.assertTrue("Classification-based patching is only supported on YUM if the computer is independently configured to receive classification information." in str(context.exception))
        
    def test_install_updates_fail_safe(self):
        """Test install_updates_fail_safe """
        # Set up
        test_excluded_pkgs = ["kernel.x86_64", "kernel.i686", "tzdata.noarch"]
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        
        # Act
        result = package_manager.install_updates_fail_safe(test_excluded_pkgs)
        
        # Verify
        self.assertIsNone(result)
        
        self.runtime.stop()
        
    def test_get_product_arch(self):
        """ Test get_product_arch method to return pkg arch type."""
        # Set up
        test_pkg_name = "selinux-policy.noarch"
        package_manager = self.container.get('package_manager')
        self.assertIsNotNone(package_manager)
        
        # Act
        result = package_manager.get_product_arch(test_pkg_name)
        
        # verify
        self.assertEqual(".noarch", result)
        
        self.runtime.stop()
        
    def test_disable_auto_update_on_reboot_exception(self):
        """ test disable_auto_update_on_reboot throw exception path. """
        # Set up
        bad_disable_cmd = "systemctl disable yum-cron123"
        package_manager = self.runtime.container.get('package_manager')
        package_manager.env_layer.run_command_output = self.mock_bad_run_command_output
        
        # Act
        with self.assertRaises(Exception) as context:
            package_manager.disable_auto_update_on_reboot(bad_disable_cmd)
            
        # Assert
        print(str(context.exception))
        self.assertTrue("Unexpected return code (1) on command: systemctl disable yum-cron123" in str(context.exception))
    

if __name__ == '__main__':
    unittest.main()

