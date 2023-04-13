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

import datetime
import json
import unittest
from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor

class TestPatchInstaller(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def mock_get_remaining_packages_to_install(self, package_manager):
        return [], []

    def test_yum_install_updates_maintenance_window_exceeded(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=1, minutes=2)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        # Path change
        runtime.set_legacy_test_type('FailInstallPath')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(0, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertTrue(maintenance_window_exceeded)
        runtime.stop()

    def test_yum_install_success(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        # Path change
        runtime.set_legacy_test_type('SuccessInstallPath')
        # As all the packages should get installed using batch patching, get_remaining_packages_to_install should return 0 packages
        backup_get_remaining_packages_to_install = runtime.patch_installer.get_remaining_packages_to_install
        runtime.patch_installer.get_remaining_packages_to_install = self.mock_get_remaining_packages_to_install
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(2, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.patch_installer.get_remaining_packages_to_install = backup_get_remaining_packages_to_install
        runtime.stop()

    def test_yum_install_success_not_enough_time_for_batch_patching(self):
        # total packages to install is 2, reboot_setting is 'Never', so cutoff time for batch = 2*5 = 10
        # window size is 60 minutes, let time remain = 9 minutes so that not enough time to install in batch
        # So td = 60-9 = 51
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=51)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = 'Never'
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        # Path change
        runtime.set_legacy_test_type('SuccessInstallPath')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(2, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_yum_install_fail(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        # Path change
        runtime.set_legacy_test_type('FailInstallPath')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(0, installed_update_count)
        self.assertFalse(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_zypper_install_updates_maintenance_window_exceeded(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=1, minutes=2)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        # Path change
        runtime.set_legacy_test_type('FailInstallPath')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(0, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertTrue(maintenance_window_exceeded)
        runtime.stop()

    def test_zypper_install_success_not_enough_time_for_batch_patching(self):
        # total packages to install is 2, reboot_setting is 'Never', so cutoff time for batch = 2*5 = 10
        # window size is 60 minutes, let time remain = 9 minutes so that not enough time to install in batch
        # So td = 60-9 = 51
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=51)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        # Path change
        runtime.set_legacy_test_type('SuccessInstallPath')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(2, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_zypper_install_success(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        # Path change
        runtime.set_legacy_test_type('SuccessInstallPath')
        # As all the packages should get installed using batch patching, get_remaining_packages_to_install should return 0 packages
        backup_get_remaining_packages_to_install = runtime.patch_installer.get_remaining_packages_to_install
        runtime.patch_installer.get_remaining_packages_to_install = self.mock_get_remaining_packages_to_install
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(2, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.patch_installer.get_remaining_packages_to_install = backup_get_remaining_packages_to_install
        runtime.stop()

    def test_zypper_install_fail(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        # Path change
        runtime.set_legacy_test_type('FailInstallPath')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(0, installed_update_count)
        self.assertFalse(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_apt_install_updates_maintenance_window_exceeded(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=1, minutes=2)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('FailInstallPath')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(0, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertTrue(maintenance_window_exceeded)
        runtime.stop()

    def test_apt_install_success(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('SuccessInstallPath')
        # As all the packages should get installed using batch patching, get_remaining_packages_to_install should return 0 packages
        backup_get_remaining_packages_to_install = runtime.patch_installer.get_remaining_packages_to_install
        runtime.patch_installer.get_remaining_packages_to_install = self.mock_get_remaining_packages_to_install
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(3, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.patch_installer.get_remaining_packages_to_install = backup_get_remaining_packages_to_install
        runtime.stop()

    def test_apt_install_success_not_enough_time_for_batch_patching(self):
        # total packages to install is 3, reboot_setting is 'Never', so cutoff time for batch = 3*5 = 15
        # window size is 60 minutes, let time remain = 14 minutes so that not enough time to install in batch
        # So td = 60-14 = 46
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=46)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('SuccessInstallPath')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(3, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_dependency_installed_successfully(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('DependencyInstallSuccessfully')
        # As all the packages should get installed using batch patching, get_remaining_packages_to_install should return 0 packages
        backup_get_remaining_packages_to_install = runtime.patch_installer.get_remaining_packages_to_install
        runtime.patch_installer.get_remaining_packages_to_install = self.mock_get_remaining_packages_to_install
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(4, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.patch_installer.get_remaining_packages_to_install = backup_get_remaining_packages_to_install
        runtime.stop()

    def test_dependency_install_failed(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('DependencyInstallFailed')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(2, installed_update_count)
        self.assertFalse(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_not_enough_time_for_batch_patching_dependency_installed_successfully(self):
        # total packages to install is 3, reboot_setting is 'Never', so cutoff time for batch = 3*5 = 15
        # window size is 60 minutes, let time remain = 14 minutes so that not enough time to install in batch
        # So td = 60-14 = 46
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=46)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = 'Never'
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('DependencyInstallSuccessfully')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(4, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_not_enough_time_for_batch_patching_dependency_install_failed(self):
        # total packages to install is 3, reboot_setting is 'Never', so cutoff time for batch = 3*5 = 15
        # window size is 60 minutes, let time remain = 14 minutes so that not enough time to install in batch
        # So td = 60-14 = 46
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=46)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = 'Never'
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('DependencyInstallFailed')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(2, installed_update_count)
        self.assertFalse(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_include_dependency_apt(self):
        # all_packages contains: git-man, git, grub-efi-amd64-signed and grub-efi-amd64-bin
        # All the classifications selected and hence all packages to install
        # Batch contains packages git-man, git and grub-efi-amd64-signed
        # grub-efi-amd64-signed is dependent on grub-efi-amd64-bin so include_dependencies should add grub-efi-amd64-bin in package_and_dependencies
        argument_composer = ArgumentComposer()
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('DependencyInstallFailed')
        all_packages, all_packages_version = runtime.patch_installer.get_remaining_packages_to_install(runtime.package_manager)
        packages = list(all_packages)
        package_versions = list(all_packages_version)
        packages_in_batch = packages[0:3]
        package_versions_in_batch = package_versions[0:3]
        package_and_dependencies = list(packages_in_batch)
        package_and_dependency_versions = list(package_versions_in_batch)
        self.assertEqual(3, len(package_and_dependencies))
        self.assertEqual(3, len(package_and_dependency_versions))
        self.assertTrue("git-man" in package_and_dependencies)
        self.assertTrue("git" in package_and_dependencies)
        self.assertTrue("grub-efi-amd64-signed" in package_and_dependencies)
        self.assertTrue("grub-efi-amd64-bin" not in package_and_dependencies)
        runtime.patch_installer.include_dependencies(runtime.package_manager, packages_in_batch, all_packages, packages, package_versions, package_and_dependencies, package_and_dependency_versions)
        self.assertEqual(4, len(package_and_dependencies))
        self.assertEqual(4, len(package_and_dependency_versions))
        self.assertTrue("git-man" in package_and_dependencies)
        self.assertTrue("git" in package_and_dependencies)
        self.assertTrue("grub-efi-amd64-signed" in package_and_dependencies)
        self.assertTrue("grub-efi-amd64-bin" in package_and_dependencies)
        runtime.stop()

    def test_include_dependency_yum(self):
        # all_packages contains: selinux-policy.noarch, selinux-policy-targeted.noarch, libgcc.i686, tar.x86_64 and tcpdump.x86_64
        # All the classifications selected and hence all packages to install
        # Batch contains the package selinux-policy.noarch
        # selinux-policy.noarch is dependent on selinux-policy-targeted.noarch so include_dependencies should add selinux-policy-targeted.noarch in package_and_dependencies
        argument_composer = ArgumentComposer()
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        # Path change
        runtime.set_legacy_test_type('HappyPath')
        all_packages, all_packages_version = runtime.patch_installer.get_remaining_packages_to_install(runtime.package_manager)
        packages = list(all_packages)
        package_versions = list(all_packages_version)
        packages_in_batch = ["selinux-policy.noarch"]
        package_versions_in_batch = ["3.13.1-102.el7_3.16"]
        package_and_dependencies = list(packages_in_batch)
        package_and_dependency_versions = list(package_versions_in_batch)
        runtime.patch_installer.include_dependencies(runtime.package_manager, packages_in_batch, all_packages, packages, package_versions, package_and_dependencies, package_and_dependency_versions)
        self.assertEqual(2, len(package_and_dependencies))
        self.assertEqual(2, len(package_and_dependency_versions))
        self.assertTrue(package_and_dependencies[0] == "selinux-policy.noarch")
        self.assertTrue(package_and_dependency_versions[0] == "3.13.1-102.el7_3.16")
        self.assertTrue(package_and_dependencies[1] == "selinux-policy-targeted.noarch")
        self.assertTrue(package_and_dependency_versions[1] == "3.13.1-102.el7_3.16")
        runtime.stop()

    def test_include_dependency_zypper(self):
        # all_packages contains: kernel-default, libgcc and libgoa-1_0-0
        # All the classifications selected and hence all packages to install
        # Batch contains the package libgcc
        # libgcc is not dependent on any package so include_dependencies should not add any package in package_and_dependencies
        argument_composer = ArgumentComposer()
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        # Path change
        runtime.set_legacy_test_type('HappyPath')
        all_packages, all_packages_version = runtime.patch_installer.get_remaining_packages_to_install(runtime.package_manager)
        packages = list(all_packages)
        package_versions = list(all_packages_version)
        packages_in_batch = ["libgcc"]
        package_versions_in_batch = ["5.60.7-8.1"]
        package_and_dependencies = list(packages_in_batch)
        package_and_dependency_versions = list(package_versions_in_batch)
        runtime.patch_installer.include_dependencies(runtime.package_manager, packages_in_batch, all_packages, packages, package_versions, package_and_dependencies, package_and_dependency_versions)
        self.assertEqual(1, len(package_and_dependencies))
        self.assertEqual(1, len(package_and_dependency_versions))
        self.assertTrue(package_and_dependencies[0] == "libgcc")
        self.assertTrue(package_and_dependency_versions[0] == "5.60.7-8.1")
        runtime.stop()

    def test_skip_package_version_UA_ESM_REQUIRED(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('UA_ESM_Required')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(0, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_dependent_package_excluded(self):
        # exclusion list contains grub-efi-amd64-bin
        # grub-efi-amd64-signed is dependent on grub-efi-amd64-bin, so grub-efi-amd64-signed should also get excluded
        # so, out of 4 packages, only 2 packages are installed and 2 are excluded
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.patches_to_exclude = ["grub-efi-amd64-bin"]
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('DependencyInstallSuccessfully')
        # As all the packages should get installed using batch patching, get_remaining_packages_to_install should return 0 packages
        backup_get_remaining_packages_to_install = runtime.patch_installer.get_remaining_packages_to_install
        runtime.patch_installer.get_remaining_packages_to_install = self.mock_get_remaining_packages_to_install
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(2, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.patch_installer.get_remaining_packages_to_install = backup_get_remaining_packages_to_install
        runtime.stop()

    def test_dependent_package_excluded_and_not_enough_time_for_batch_patching(self):
        # exclusion list contains grub-efi-amd64-bin
        # grub-efi-amd64-signed is dependent on grub-efi-amd64-bin, so grub-efi-amd64-signed should also get excluded
        # so, out of 4 packages, only 2 packages are installed and 2 are excluded.
        # total packages to install is 2, reboot_setting is 'Never', so cutoff time for batch = 2*5 = 10
        # window size is 60 minutes, let time remain = 9 minutes so that not enough time to install in batch
        # So td = 60-9 = 51
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=51)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.patches_to_exclude = ["grub-efi-amd64-bin"]
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('DependencyInstallSuccessfully')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(2, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_arch_dependency_install_success(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        # Path change
        runtime.set_legacy_test_type('ArchDependency')
        # As all the packages should get installed using batch patching, get_remaining_packages_to_install should return 0 packages
        backup_get_remaining_packages_to_install = runtime.patch_installer.get_remaining_packages_to_install
        runtime.patch_installer.get_remaining_packages_to_install = self.mock_get_remaining_packages_to_install
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(4, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.patch_installer.get_remaining_packages_to_install = backup_get_remaining_packages_to_install
        runtime.stop()

    def test_no_updates_to_install(self):
        # Verify that if there are no updates available then also install_updates method runs successfully
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        # Path change. There is no path as NoUpdatesToInstall so the command to get available updates will return empty string
        runtime.set_legacy_test_type('NoUpdatesToInstall')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(0, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_get_remaining_packages_to_install(self):
        argument_composer = ArgumentComposer()
        # including 3 packages. excluding 1 package.
        # But grub-efi-amd64-signed is dependent on grub-efi-amd64-bin so grub-efi-amd64-signed is also excluded
        argument_composer.patches_to_include = ["git-man", "git", "grub-efi-amd64-signed"]
        argument_composer.patches_to_exclude = ["grub-efi-amd64-bin"]
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change.
        runtime.set_legacy_test_type('DependencyInstallSuccessfully')
        packages, packages_versions = runtime.patch_installer.get_remaining_packages_to_install(runtime.package_manager)
        self.assertTrue(len(packages) == 2)
        self.assertTrue(len(packages_versions) == 2)
        self.assertTrue( "git-man" in packages)
        self.assertTrue( "git" in packages)
        runtime.stop()

    def test_healthstore_writes(self):
        self.healthstore_writes_helper("HealthStoreId", None, expected_patch_version="HealthStoreId")
        self.healthstore_writes_helper("HealthStoreId", "MaintenanceRunId", expected_patch_version="HealthStoreId")
        self.healthstore_writes_helper(None, "MaintenanceRunId", expected_patch_version="MaintenanceRunId")
        self.healthstore_writes_helper(None, "09/16/2021 08:24:42 AM +00:00", expected_patch_version="2021.09.16")
        self.healthstore_writes_helper("09/16/2021 08:24:42 AM +00:00", None, expected_patch_version="2021.09.16")
        self.healthstore_writes_helper("09/16/2021 08:24:42 AM +00:00", "09/17/2021 08:24:42 AM +00:00", expected_patch_version="2021.09.16")
        self.healthstore_writes_helper("09/16/2021 08:24:42 AM +00:00", "<some-guid>", expected_patch_version="2021.09.16")

    def healthstore_writes_helper(self, health_store_id, maintenance_run_id, expected_patch_version):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        argument_composer.health_store_id = health_store_id
        argument_composer.maintenance_run_id = maintenance_run_id
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)

        runtime.set_legacy_test_type('SuccessInstallPath')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(
            runtime.maintenance_window, runtime.package_manager, simulate=True)
        runtime.patch_installer.mark_installation_completed()

        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"][1]

        self.assertEqual(True, json.loads(substatus_file_data['formattedMessage']['message'])['shouldReportToHealthStore'])
        self.assertEqual(expected_patch_version, json.loads(substatus_file_data['formattedMessage']['message'])['patchVersion'])
        runtime.stop()

    def test_raise_if_telemetry_unsupported(self):
        # Constants.VMCloudType.ARC
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=1, minutes=2)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(env_settings={"telemetrySupported": True}), True, Constants.YUM)
        runtime.set_legacy_test_type('SuccessInstallPath')
        runtime.patch_installer.raise_if_telemetry_unsupported()
        runtime.stop()

        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(env_settings={"telemetrySupported": False}), True, Constants.YUM)
        runtime.set_legacy_test_type('SuccessInstallPath')
        self.assertRaises(Exception, runtime.patch_installer.raise_if_telemetry_unsupported)
        runtime.stop()

        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(env_settings={"telemetrySupported": True}), True, Constants.YUM)
        runtime.set_legacy_test_type('SuccessInstallPath')
        runtime.patch_installer.lifecycle_manager.get_vm_cloud_type = lambda: Constants.VMCloudType.ARC
        runtime.patch_installer.raise_if_telemetry_unsupported()
        runtime.stop()

        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(env_settings={"telemetrySupported": False}), True, Constants.YUM)
        runtime.set_legacy_test_type('SuccessInstallPath')
        runtime.patch_installer.lifecycle_manager.get_vm_cloud_type = lambda: Constants.VMCloudType.ARC
        self.assertRaises(Exception, runtime.patch_installer.raise_if_telemetry_unsupported)
        runtime.stop()

        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(env_settings={"telemetrySupported": True}), True, Constants.YUM)
        runtime.set_legacy_test_type('SuccessInstallPath')
        runtime.patch_installer.lifecycle_manager.get_vm_cloud_type = lambda: Constants.VMCloudType.ARC
        runtime.patch_installer.execution_config.operation = Constants.CONFIGURE_PATCHING
        runtime.patch_installer.raise_if_telemetry_unsupported()
        runtime.stop()

        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(env_settings={"telemetrySupported": False}), True, Constants.YUM)
        runtime.set_legacy_test_type('SuccessInstallPath')
        runtime.patch_installer.lifecycle_manager.get_vm_cloud_type = lambda: Constants.VMCloudType.ARC
        runtime.patch_installer.execution_config.operation = Constants.CONFIGURE_PATCHING
        # Should not raise an exception because it is an ARC VM and it is not installation or assessment
        runtime.patch_installer.raise_if_telemetry_unsupported()
        runtime.stop()

        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(env_settings={"telemetrySupported": True}), True, Constants.YUM)
        runtime.set_legacy_test_type('SuccessInstallPath')
        runtime.patch_installer.execution_config.operation = Constants.CONFIGURE_PATCHING
        runtime.patch_installer.raise_if_telemetry_unsupported()
        runtime.stop()

    def test_write_installer_perf_logs(self):
        runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), legacy_mode=True)
        runtime.patch_installer.start_installation(simulate=True)
        self.assertTrue(runtime.patch_installer.stopwatch.start_time is not None)
        self.assertTrue(runtime.patch_installer.stopwatch.end_time is not None)
        self.assertTrue(runtime.patch_installer.stopwatch.time_taken_in_secs is not None)
        self.assertTrue(runtime.patch_installer.stopwatch.task_details is not None)
        self.assertTrue(runtime.patch_installer.stopwatch.start_time <= runtime.patch_installer.stopwatch.end_time)
        self.assertTrue(runtime.patch_installer.stopwatch.time_taken_in_secs >= 0)
        task_info = "{0}={1}".format(str(Constants.PerfLogTrackerParams.TASK), str(Constants.INSTALLATION))
        self.assertTrue(task_info in str(runtime.patch_installer.stopwatch.task_details))
        task_status = "{0}={1}".format(str(Constants.PerfLogTrackerParams.TASK_STATUS), str(Constants.TaskStatus.SUCCEEDED))
        self.assertTrue(task_status in str(runtime.patch_installer.stopwatch.task_details))
        err_msg = "{0}=".format(str(Constants.PerfLogTrackerParams.ERROR_MSG))
        self.assertTrue(err_msg in str(runtime.patch_installer.stopwatch.task_details))
        runtime.stop()

    def test_stopwatch_properties_patch_install_fail(self):
        runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), legacy_mode=True)
        runtime.set_legacy_test_type('FailInstallPath')
        self.assertRaises(Exception, runtime.patch_installer.start_installation)
        self.assertTrue(runtime.patch_installer.stopwatch.start_time is not None)
        self.assertTrue(runtime.patch_installer.stopwatch.end_time is None)
        self.assertTrue(runtime.patch_installer.stopwatch.time_taken_in_secs is None)
        self.assertTrue(runtime.patch_installer.stopwatch.task_details is None)
        runtime.stop()

    def test_write_installer_perf_logs_runs_successfully_if_exception_in_get_percentage_maintenance_window_used(self):
        # Testing the catch Exception in the method write_installer_perf_logs
        # ZeroDivisionError Exception should be thrown by the function get_percentage_maintenance_window_used because denominator will be zero if maximum_duration is zero
        # This will cover the catch exception code
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = "PT0H"
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), legacy_mode=True)
        self.assertTrue(runtime.patch_installer.write_installer_perf_logs(True, 1, 1, runtime.maintenance_window, False, Constants.TaskStatus.SUCCEEDED, ""))
        runtime.stop()


if __name__ == '__main__':
    unittest.main()
