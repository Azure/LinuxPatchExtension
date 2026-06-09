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
import math
import os
import sys
import unittest
from core.src.bootstrap.Constants import Constants
from core.tests.Test_UbuntuProClient import MockUpdatesResult, MockVersionResult
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor

class TestPatchInstaller(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # region Mocks
    def mock_update_certs_raise_exception(self):
        raise Exception("Simulated cert update failure")
    # endregion

    # region Utility functions (update cert tests)
    def _create_update_certs_runtime(self, enable_uefi_cert_update=True, health_store_id=None, operation=Constants.INSTALLATION):
        argument_composer = ArgumentComposer()
        argument_composer.health_store_id = health_store_id
        argument_composer.operation = operation
        config_file_path = Constants.AzGPSPaths.UEFI_SETTINGS
        config_settings = {
            "EnabledBy": "TestSetup",
            "LastModified": "2026-04-21",
            "EnableUEFICertUpdate": True if enable_uefi_cert_update else False,
        }
        self.__write_config_settings_to_file(config_settings, config_file_path=config_file_path)
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        return runtime

    @staticmethod
    def __write_config_settings_to_file(config_settings, config_file_path):
        f = open(config_file_path, "w+")
        f.write(json.dumps(config_settings))
        f.close()

    @staticmethod
    def _track_method_call(obj, method_name):
        call_count = []
        setattr(obj, method_name, lambda: call_count.append(True))
        return call_count
    # endregion

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
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(2, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_yum_install_success_not_enough_time_for_batch_patching(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=50)
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
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=50)
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
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(2, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
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
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(3, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_apt_install_skips_esm_packages(self):
        obj = MockUpdatesResult()
        obj.mock_import_uaclient_update_module('updates', 'mock_update_list_with_one_esm_update')
        version_obj = MockVersionResult()
        version_obj.mock_import_uaclient_version_module('version', 'mock_version')
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('UA_ESM_Required')
        backup_package_manager_ubuntu_pro_client_attached = runtime.package_manager.ubuntu_pro_client.is_ubuntu_pro_client_attached
        runtime.package_manager.ubuntu_pro_client.is_ubuntu_pro_client_attached = False

        # esm package should be skipped.
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(
            runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(0, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

        runtime.package_manager.ubuntu_pro_client.is_ubuntu_pro_client_attached = backup_package_manager_ubuntu_pro_client_attached
        obj.mock_unimport_uaclient_update_module()
        version_obj.mock_unimport_uaclient_version_module()

    def test_patch_installer_for_azgps_coordinated(self):
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = "PT235M"
        argument_composer.health_store_id = "pub_offer_sku_2024.04.01"
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.package_manager.current_source_list = os.path.join(argument_composer.temp_folder, "temp2.list")
        # Path change
        runtime.set_legacy_test_type('HappyPath')
        self.assertTrue(runtime.patch_installer.start_installation())
        self.assertEqual(runtime.execution_config.max_patch_publish_date, "20240401T000000Z")
        self.assertEqual(runtime.package_manager.max_patch_publish_date,"20240401T000000Z")  # supported and conditions met
        runtime.stop()

        argument_composer.maximum_duration = "PT30M"
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type('HappyPath')
        self.assertFalse(runtime.patch_installer.start_installation())                 # failure is in unrelated patch installation batch processing
        self.assertEqual(runtime.execution_config.max_patch_publish_date, "20240401T000000Z")
        self.assertEqual(runtime.package_manager.max_patch_publish_date, "")    # reason: not enough time to use

        runtime.package_manager.max_patch_publish_date = "Wrong"
        runtime.package_manager.get_security_updates()      # exercises an exception path on bad data without throwing an exception (graceful degradation to security)
        runtime.stop()

        argument_composer.maximum_duration = "PT235M"
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        runtime.set_legacy_test_type('HappyPath')
        runtime.package_manager.install_security_updates_azgps_coordinated = lambda: (1, "Failed")
        self.assertFalse(runtime.patch_installer.start_installation())
        self.assertEqual(runtime.execution_config.max_patch_publish_date, "20240401T000000Z")
        self.assertEqual(runtime.package_manager.max_patch_publish_date, "")    # reason: the strict SDP is forced to fail with the lambda above
        runtime.stop()

        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        runtime.set_legacy_test_type('HappyPath')
        self.assertTrue(runtime.patch_installer.start_installation())
        self.assertEqual(runtime.execution_config.max_patch_publish_date, "20240401T000000Z")
        self.assertEqual(runtime.package_manager.max_patch_publish_date, "")    # unsupported in Yum
        runtime.stop()

        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.ZYPPER)
        runtime.set_legacy_test_type('HappyPath')
        self.assertFalse(runtime.patch_installer.start_installation())                 # failure is in unrelated patch installation batch processing
        self.assertEqual(runtime.execution_config.max_patch_publish_date, "20240401T000000Z")
        self.assertEqual(runtime.package_manager.max_patch_publish_date, "")    # unsupported in Zypper
        runtime.stop()

    def test_mark_status_completed_esm_required(self):
        obj = MockUpdatesResult()
        obj.mock_import_uaclient_update_module('updates', 'mock_update_list_with_one_esm_update')
        version_obj = MockVersionResult()
        version_obj.mock_import_uaclient_version_module('version', 'mock_version')
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('UA_ESM_Required')
        backup_package_manager_ubuntu_pro_client_attached = runtime.package_manager.ubuntu_pro_client.is_ubuntu_pro_client_attached
        runtime.package_manager.ubuntu_pro_client.is_ubuntu_pro_client_attached = False

        runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        runtime.patch_installer.mark_installation_completed()
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

        self.assertEqual('warning', substatus_file_data[0]['status'])

        runtime.stop()
        runtime.package_manager.ubuntu_pro_client.is_ubuntu_pro_client_attached = backup_package_manager_ubuntu_pro_client_attached
        obj.mock_unimport_uaclient_update_module()
        version_obj.mock_unimport_uaclient_version_module()

    def test_apt_install_success_not_enough_time_for_batch_patching(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=50)
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
        td = datetime.timedelta(hours=0, minutes=42)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('DependencyInstallSuccessfully')
        # As all the packages should get installed using batch patching, get_remaining_packages_to_install should return 0 packages
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(7, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_dependency_install_failed(self):
        # exclusion list contains grub-efi-amd64-bin
        # grub-efi-amd64-signed is dependent on grub-efi-amd64-bin, so grub-efi-amd64-signed should also get excluded
        # so, out of 7 packages, only 5 packages are installed and 2 are excluded
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=42)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('DependencyInstallFailed')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(5, installed_update_count)
        self.assertFalse(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_not_enough_time_for_batch_patching_dependency_installed_successfully(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=50)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = 'Never'
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('DependencyInstallSuccessfully')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(7, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_not_enough_time_for_batch_patching_dependency_install_failed(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=50)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.reboot_setting = 'Never'
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('DependencyInstallFailed')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(5, installed_update_count)
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
        all_packages, all_packages_version = runtime.package_manager.get_available_updates(runtime.package_filter)
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
        runtime.patch_installer.include_dependencies(runtime.package_manager, packages_in_batch, package_versions_in_batch, all_packages, all_packages_version, packages, package_versions, package_and_dependencies, package_and_dependency_versions)
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
        all_packages, all_packages_version = runtime.package_manager.get_available_updates(runtime.package_filter)
        packages = list(all_packages)
        package_versions = list(all_packages_version)
        packages_in_batch = ["selinux-policy.noarch"]
        package_versions_in_batch = ["3.13.1-102.el7_3.16"]
        package_and_dependencies = list(packages_in_batch)
        package_and_dependency_versions = list(package_versions_in_batch)
        runtime.patch_installer.include_dependencies(runtime.package_manager, packages_in_batch, package_versions_in_batch, all_packages, all_packages_version, packages, package_versions, package_and_dependencies, package_and_dependency_versions)
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
        all_packages, all_packages_version = runtime.package_manager.get_available_updates(runtime.package_filter)
        packages = list(all_packages)
        package_versions = list(all_packages_version)
        packages_in_batch = ["libgcc"]
        package_versions_in_batch = ["5.60.7-8.1"]
        package_and_dependencies = list(packages_in_batch)
        package_and_dependency_versions = list(package_versions_in_batch)
        runtime.patch_installer.include_dependencies(runtime.package_manager, packages_in_batch, package_versions_in_batch, all_packages, all_packages_version, packages, package_versions, package_and_dependencies, package_and_dependency_versions)
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
        # so, out of 7 packages, only 5 packages are installed and 2 are excluded
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
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(5, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_dependent_package_excluded_and_not_enough_time_for_batch_patching(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=50)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.patches_to_exclude = ["grub-efi-amd64-bin"]
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.APT)
        # Path change
        runtime.set_legacy_test_type('DependencyInstallSuccessfully')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(5, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_arch_dependency_install_success(self):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=42)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        # Path change
        runtime.set_legacy_test_type('ArchDependency')
        # As all the packages should get installed using batch patching, get_remaining_packages_to_install should return 0 packages
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(7, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
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

    def test_healthstore_writes(self):
        self.healthstore_writes_helper("HealthStoreId", None, False, expected_patch_version="HealthStoreId")
        self.healthstore_writes_helper("HealthStoreId", "MaintenanceRunId", False, expected_patch_version="HealthStoreId")
        self.healthstore_writes_helper("pub_offer_sku_2020.10.20", None, False, expected_patch_version="pub_offer_sku_2020.10.20")

    def healthstore_writes_helper(self, health_store_id, maintenance_run_id, is_force_reboot, expected_patch_version):
        current_time = datetime.datetime.utcnow()
        td = datetime.timedelta(hours=0, minutes=20)
        job_start_time = (current_time - td).strftime("%Y-%m-%dT%H:%M:%S.9999Z")
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = 'PT1H'
        argument_composer.start_time = job_start_time
        argument_composer.health_store_id = health_store_id
        argument_composer.maintenance_run_id = maintenance_run_id
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)

        if is_force_reboot:
            runtime.package_manager.force_reboot = True

        runtime.set_legacy_test_type('SuccessInstallPath')
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(
            runtime.maintenance_window, runtime.package_manager, simulate=True)
        runtime.patch_installer.mark_installation_completed()

        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

        if is_force_reboot:
            self.assertEqual('warning', substatus_file_data[0]['status'])
        else:
            self.assertEqual('success', substatus_file_data[0]['status'])

        self.assertEqual(True, json.loads(substatus_file_data[1]['formattedMessage']['message'])['shouldReportToHealthStore'])
        self.assertEqual(expected_patch_version, json.loads(substatus_file_data[1]['formattedMessage']['message'])['patchVersion'])
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

    def test_raise_if_min_python_version_not_met(self):
        runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), legacy_mode=True)
        original_version = sys.version_info
        sys.version_info = (2, 6)
        # Assert that an exception is raised
        with self.assertRaises(Exception) as context:
            runtime.patch_installer.start_installation()
        self.assertEqual(str(context.exception), Constants.PYTHON_NOT_COMPATIBLE_ERROR_MSG.format(sys.version_info))

        # reset sys.version to original
        sys.version_info = original_version
        runtime.stop()

    def test_get_max_batch_size(self):
        argument_composer = ArgumentComposer()
        argument_composer.maximum_duration = "PT1H"
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)
        calculated_max_batch_size = runtime.patch_installer.get_max_batch_size(runtime.maintenance_window, runtime.package_manager)

        # Deriving the expected max batch size below and checking if it is same as calculated max batch size.
        expected_max_batch_size = 0

        available_time_to_install_packages_in_minutes = 60
        available_time_to_install_packages_in_minutes = available_time_to_install_packages_in_minutes - Constants.PackageBatchConfig.BUFFER_TIME_FOR_BATCH_PATCHING_START_IN_MINUTES

        if available_time_to_install_packages_in_minutes > Constants.PACKAGE_INSTALL_EXPECTED_MAX_TIME_IN_MINUTES:
            available_time_to_install_packages = available_time_to_install_packages_in_minutes - Constants.PACKAGE_INSTALL_EXPECTED_MAX_TIME_IN_MINUTES
            expected_max_batch_size += 1

            # Remaining packages take average expected time to install.
            package_install_expected_avg_time_in_minutes = runtime.package_manager.get_package_install_expected_avg_time_in_seconds() / 60.0
            expected_max_batch_size += int(
                math.floor(available_time_to_install_packages / package_install_expected_avg_time_in_minutes))

        self.assertEqual(calculated_max_batch_size, expected_max_batch_size)
        runtime.stop()

    # region test update certs
    def test_try_update_certificates_for_default_patching(self):
        """ Test update certificates code path depending on different configurations """

        # Use case 1: Feature flag is off
        enable_uefi_cert_update_usecase1 = False
        health_store_id_usecase1 = "pub_off_sku_2025.01.01"
        operation_usecase1 = Constants.INSTALLATION
        method_to_track_usecase1 = 'try_update_certificates_for_default_patching'
        is_package_manager_method_usecase1 = False
        number_of_times_method_called_usecase1 = 0

        # Use case 2: update_certs should NOT be called when health_store_id is None i.e. not a default patching operation
        enable_uefi_cert_update_usecase2 = True
        health_store_id_usecase2 = None
        operation_usecase2 = Constants.INSTALLATION
        method_to_track_usecase2 = 'update_certs'
        is_package_manager_method_usecase2 = True
        number_of_times_method_called_usecase2= 0

        # Use case 3: """update_certs should NOT be called when health_store_id is an empty string i.e. not a default patching operation
        enable_uefi_cert_update_usecase3 = True
        health_store_id_usecase3 = str()
        operation_usecase3 = Constants.INSTALLATION
        method_to_track_usecase3 = 'update_certs'
        is_package_manager_method_usecase3 = True
        number_of_times_method_called_usecase3 = 0

        # Use case 4: update_certs should NOT be called when operation is Assessment (not Installation). i.e. not default patching operation
        enable_uefi_cert_update_usecase4 = True
        health_store_id_usecase4 = None
        operation_usecase4 = Constants.ASSESSMENT
        method_to_track_usecase4 = 'update_certs'
        is_package_manager_method_usecase4 = True
        number_of_times_method_called_usecase4 = 0

        # Use case 5: update_certs SHOULD be called when feature flag is on, health_store_id is set, and operation is Installation (for default patching)
        enable_uefi_cert_update_usecase5 = True
        health_store_id_usecase5 = "pub_off_sku_2025.01.01"
        operation_usecase5 = Constants.INSTALLATION
        method_to_track_usecase5 = 'update_certs'
        is_package_manager_method_usecase5 = True
        number_of_times_method_called_usecase5 = 1

        test_input_output_table = [
            [enable_uefi_cert_update_usecase1, health_store_id_usecase1, operation_usecase1, method_to_track_usecase1, is_package_manager_method_usecase1, number_of_times_method_called_usecase1],
            [enable_uefi_cert_update_usecase2, health_store_id_usecase2, operation_usecase2, method_to_track_usecase2, is_package_manager_method_usecase2, number_of_times_method_called_usecase2],
            [enable_uefi_cert_update_usecase3, health_store_id_usecase3, operation_usecase3, method_to_track_usecase3, is_package_manager_method_usecase3, number_of_times_method_called_usecase3],
            [enable_uefi_cert_update_usecase4, health_store_id_usecase4, operation_usecase4, method_to_track_usecase4, is_package_manager_method_usecase4, number_of_times_method_called_usecase4],
            [enable_uefi_cert_update_usecase5, health_store_id_usecase5, operation_usecase5, method_to_track_usecase5, is_package_manager_method_usecase5, number_of_times_method_called_usecase5],
        ]

        for row in test_input_output_table:
            runtime = self._create_update_certs_runtime(enable_uefi_cert_update=bool(row[0]), health_store_id=row[1], operation=row[2])
            method_called = self._track_method_call(runtime.patch_installer.package_manager if row[4] == True else runtime.patch_installer, row[3])
            runtime.patch_installer.start_installation(simulate=True)
            self.assertEqual(len(method_called), row[5], "Failed for row: {row}")
            runtime.stop()

    def test_try_update_certs_swallows_exception_from_update_certs(self):
        """An exception raised by update_certs should be swallowed and not propagate."""
        runtime = self._create_update_certs_runtime(enable_uefi_cert_update=True, health_store_id="pub_off_sku_2025.01.01")
        backup_up_update_certs = runtime.patch_installer.package_manager.update_certs

        runtime.patch_installer.package_manager.update_certs = self.mock_update_certs_raise_exception
        runtime.patch_installer.start_installation(simulate=True)

        runtime.patch_installer.package_manager.update_certs = backup_up_update_certs
        runtime.stop()
    # endregion


if __name__ == '__main__':
    unittest.main()
