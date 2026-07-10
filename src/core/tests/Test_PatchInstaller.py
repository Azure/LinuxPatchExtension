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

    def mock_update_certs_returns_false(self):
        return False

    def mock_detect_confidential_vm_raises_exception(self):
        raise Exception("Simulated VM detection failure")

    def mock_detect_confidential_vm_by_imds_returns_true(self):
        return True, 'IMDS:ConfidentialVM'

    def mock_detect_confidential_vm_returns_false(self):
        return False, str()

    def mock_should_reboot_before_cert_update_returns_true(self):
        return True

    def mock_should_reboot_before_cert_update_returns_false(self):
        return False

    def mock_start_reboot_if_required_and_time_available_returns_false(self, current_time):
        return False

    def mock_start_reboot_if_required_and_time_available_raises_exception(self, current_time):
        raise Exception("Simulated reboot failure")

    def mock_is_hibernation_enabled_for_cert_update_returns_true(self):
        return True

    def mock_is_hibernation_enabled_for_cert_update_returns_false(self):
        return False

    def mock_is_hibernation_enabled_for_cert_update_raises_exception(self):
        raise Exception("Simulated hibernation detection failure")

    def mock_are_latest_certs_present_returns_true(self):
        return True

    def mock_are_latest_certs_present_returns_false(self):
        return False
    # endregion

    # region Utility functions (update cert tests)
    def _create_update_certs_runtime(self, enable_uefi_cert_update=True, health_store_id=None, operation=Constants.INSTALLATION, reboot_setting=None):
        argument_composer = ArgumentComposer()
        argument_composer.health_store_id = health_store_id
        argument_composer.operation = operation
        if reboot_setting is not None:
            argument_composer.reboot_setting = reboot_setting
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
        with open(config_file_path, "w+") as f:
            f.write(json.dumps(config_settings))

    @staticmethod
    def _get_installation_error_messages(runtime):
        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

        installation_substatus = [item for item in substatus_file_data if item["name"] == Constants.PATCH_INSTALLATION_SUMMARY][0]
        installation_message = json.loads(installation_substatus["formattedMessage"]["message"])
        error_details = installation_message["errors"]["details"]
        return [error["message"] for error in error_details]
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
        reboot_setting_usecase1 = None
        mock_should_reboot_usecase1 = None
        expected_error_message_usecase1 = None
        mock_detect_confidential_vm_usecase1 = None
        # hibernation check not reached (feature flag off, returns before prereq checks)

        # Use case 2: update_certs should NOT be called when health_store_id is None i.e. not a default patching operation
        enable_uefi_cert_update_usecase2 = True
        health_store_id_usecase2 = None
        operation_usecase2 = Constants.INSTALLATION
        reboot_setting_usecase2 = None
        mock_should_reboot_usecase2 = None
        expected_error_message_usecase2 = None
        mock_detect_confidential_vm_usecase2 = None
        # hibernation check not reached (not a default patching operation)

        # Use case 3: update_certs should NOT be called when health_store_id is an empty string i.e. not a default patching operation
        enable_uefi_cert_update_usecase3 = True
        health_store_id_usecase3 = str()
        operation_usecase3 = Constants.INSTALLATION
        reboot_setting_usecase3 = None
        mock_should_reboot_usecase3 = None
        expected_error_message_usecase3 = None
        mock_detect_confidential_vm_usecase3 = None
        # hibernation check not reached (not a default patching operation)

        # Use case 4: update_certs should NOT be called when operation is Assessment (not Installation). i.e. not default patching operation
        enable_uefi_cert_update_usecase4 = True
        health_store_id_usecase4 = None
        operation_usecase4 = Constants.ASSESSMENT
        reboot_setting_usecase4 = None
        mock_should_reboot_usecase4 = None
        expected_error_message_usecase4 = None
        mock_detect_confidential_vm_usecase4 = None
        # hibernation check not reached (not a default patching operation)

        # Use case 5: update_certs SHOULD be called only when this is default patching and all prerequisites are met.
        enable_uefi_cert_update_usecase5 = True
        health_store_id_usecase5 = "pub_off_sku_2025.01.01"
        operation_usecase5 = Constants.INSTALLATION
        reboot_setting_usecase5 = 'IfRequired'
        mock_should_reboot_usecase5 = self.mock_should_reboot_before_cert_update_returns_false
        expected_error_message_usecase5 = "Certificates may not have been updated"
        mock_detect_confidential_vm_usecase5 = self.mock_detect_confidential_vm_returns_false
        mock_hibernation_usecase5 = self.mock_is_hibernation_enabled_for_cert_update_returns_false  # explicitly disable hibernation so this prereq passes
        mock_latest_certs_usecase5 = self.mock_are_latest_certs_present_returns_false

        # Use case 6: update_certs should NOT be called when a reboot is required but the reboot setting is 'Never'
        enable_uefi_cert_update_usecase6 = True
        health_store_id_usecase6 = "pub_off_sku_2025.01.01"
        operation_usecase6 = Constants.INSTALLATION
        reboot_setting_usecase6 = 'Never'
        mock_should_reboot_usecase6 = self.mock_should_reboot_before_cert_update_returns_true
        expected_error_message_usecase6 = "reboot first"
        mock_detect_confidential_vm_usecase6 = self.mock_detect_confidential_vm_returns_false
        mock_hibernation_usecase6 = self.mock_is_hibernation_enabled_for_cert_update_returns_false
        mock_latest_certs_usecase6 = self.mock_are_latest_certs_present_returns_false

        # Use case 7: update_certs should NOT be called when VM is a CVM.
        enable_uefi_cert_update_usecase7 = True
        health_store_id_usecase7 = "pub_off_sku_2025.01.01"
        operation_usecase7 = Constants.INSTALLATION
        reboot_setting_usecase7 = 'IfRequired'
        mock_should_reboot_usecase7 = self.mock_should_reboot_before_cert_update_returns_false
        expected_error_message_usecase7 = None
        mock_detect_confidential_vm_usecase7 = self.mock_detect_confidential_vm_by_imds_returns_true
        mock_hibernation_usecase7 = None  # hibernation check not reached (CVM check fails first)
        mock_latest_certs_usecase7 = None

        # Use case 8: update_certs should NOT be called when hibernation is enabled.
        enable_uefi_cert_update_usecase8 = True
        health_store_id_usecase8 = "pub_off_sku_2025.01.01"
        operation_usecase8 = Constants.INSTALLATION
        reboot_setting_usecase8 = 'IfRequired'
        mock_should_reboot_usecase8 = self.mock_should_reboot_before_cert_update_returns_false
        expected_error_message_usecase8 = "Turn off hibernation"
        mock_detect_confidential_vm_usecase8 = self.mock_detect_confidential_vm_returns_false
        mock_hibernation_usecase8 = self.mock_is_hibernation_enabled_for_cert_update_returns_true
        mock_latest_certs_usecase8 = None  # latest cert check not reached when hibernation is enabled

        # Use case 9: update_certs should NOT be called when latest certs are already present.
        enable_uefi_cert_update_usecase9 = True
        health_store_id_usecase9 = "pub_off_sku_2025.01.01"
        operation_usecase9 = Constants.INSTALLATION
        reboot_setting_usecase9 = 'IfRequired'
        mock_should_reboot_usecase9 = self.mock_should_reboot_before_cert_update_returns_true
        expected_error_message_usecase9 = None
        mock_detect_confidential_vm_usecase9 = self.mock_detect_confidential_vm_returns_false
        mock_hibernation_usecase9 = self.mock_is_hibernation_enabled_for_cert_update_returns_false
        mock_latest_certs_usecase9 = self.mock_are_latest_certs_present_returns_true

        test_input_output_table = [
            [enable_uefi_cert_update_usecase1, health_store_id_usecase1, operation_usecase1, reboot_setting_usecase1, mock_should_reboot_usecase1, expected_error_message_usecase1, mock_detect_confidential_vm_usecase1, None, None],
            [enable_uefi_cert_update_usecase2, health_store_id_usecase2, operation_usecase2, reboot_setting_usecase2, mock_should_reboot_usecase2, expected_error_message_usecase2, mock_detect_confidential_vm_usecase2, None, None],
            [enable_uefi_cert_update_usecase3, health_store_id_usecase3, operation_usecase3, reboot_setting_usecase3, mock_should_reboot_usecase3, expected_error_message_usecase3, mock_detect_confidential_vm_usecase3, None, None],
            [enable_uefi_cert_update_usecase4, health_store_id_usecase4, operation_usecase4, reboot_setting_usecase4, mock_should_reboot_usecase4, expected_error_message_usecase4, mock_detect_confidential_vm_usecase4, None, None],
            [enable_uefi_cert_update_usecase5, health_store_id_usecase5, operation_usecase5, reboot_setting_usecase5, mock_should_reboot_usecase5, expected_error_message_usecase5, mock_detect_confidential_vm_usecase5, mock_hibernation_usecase5, mock_latest_certs_usecase5],
            [enable_uefi_cert_update_usecase6, health_store_id_usecase6, operation_usecase6, reboot_setting_usecase6, mock_should_reboot_usecase6, expected_error_message_usecase6, mock_detect_confidential_vm_usecase6, mock_hibernation_usecase6, mock_latest_certs_usecase6],
            [enable_uefi_cert_update_usecase7, health_store_id_usecase7, operation_usecase7, reboot_setting_usecase7, mock_should_reboot_usecase7, expected_error_message_usecase7, mock_detect_confidential_vm_usecase7, mock_hibernation_usecase7, mock_latest_certs_usecase7],
            [enable_uefi_cert_update_usecase8, health_store_id_usecase8, operation_usecase8, reboot_setting_usecase8, mock_should_reboot_usecase8, expected_error_message_usecase8, mock_detect_confidential_vm_usecase8, mock_hibernation_usecase8, mock_latest_certs_usecase8],
            [enable_uefi_cert_update_usecase9, health_store_id_usecase9, operation_usecase9, reboot_setting_usecase9, mock_should_reboot_usecase9, expected_error_message_usecase9, mock_detect_confidential_vm_usecase9, mock_hibernation_usecase9, mock_latest_certs_usecase9],
        ]

        for row in test_input_output_table:
            enable_uefi_cert_update_row, health_store_id_row, operation_row, reboot_setting_row, mock_should_reboot_row, expected_error_message_row, mock_detect_confidential_vm_row, mock_hibernation_row, mock_latest_certs_row = row

            runtime = self._create_update_certs_runtime(enable_uefi_cert_update=bool(enable_uefi_cert_update_row), health_store_id=health_store_id_row, operation=operation_row, reboot_setting=reboot_setting_row)

            backup_should_reboot_before_cert_update = runtime.package_manager.should_reboot_before_cert_update
            backup_detect_confidential_vm = runtime.env_layer.detect_confidential_vm
            backup_hibernation_check = runtime.package_manager.is_hibernation_enabled_for_cert_update
            backup_latest_certs_check = runtime.package_manager.are_latest_certs_present
            backup_update_certs = runtime.patch_installer.package_manager.update_certs
            if mock_should_reboot_row is not None:
                runtime.package_manager.should_reboot_before_cert_update = mock_should_reboot_row
            if mock_detect_confidential_vm_row is not None:
                runtime.env_layer.detect_confidential_vm = mock_detect_confidential_vm_row
            if mock_hibernation_row is not None:
                runtime.package_manager.is_hibernation_enabled_for_cert_update = mock_hibernation_row
            if mock_latest_certs_row is not None:
                runtime.package_manager.are_latest_certs_present = mock_latest_certs_row
            runtime.patch_installer.package_manager.update_certs = self.mock_update_certs_returns_false

            runtime.patch_installer.start_installation(simulate=True)
            error_messages = self._get_installation_error_messages(runtime)
            if expected_error_message_row is None:
                self.assertFalse(any("Certificates may not have been updated" in message for message in error_messages),
                                 "Did not expect certificate update failure status for row: {0}".format(row))
            else:
                self.assertTrue(any(expected_error_message_row in message for message in error_messages),
                                "Expected certificate-related status not found for row: {0}".format(row))

            runtime.package_manager.should_reboot_before_cert_update = backup_should_reboot_before_cert_update
            runtime.env_layer.detect_confidential_vm = backup_detect_confidential_vm
            runtime.package_manager.is_hibernation_enabled_for_cert_update = backup_hibernation_check
            runtime.package_manager.are_latest_certs_present = backup_latest_certs_check
            runtime.patch_installer.package_manager.update_certs = backup_update_certs
            runtime.stop()

    def test_try_update_certs_swallows_exception_from_update_certs(self):
        """An exception raised by update_certs should be swallowed and not propagate, but an error should be recorded in the installation status."""
        runtime = self._create_update_certs_runtime(enable_uefi_cert_update=True, health_store_id="pub_off_sku_2025.01.01", reboot_setting='IfRequired')
        backup_up_update_certs = runtime.patch_installer.package_manager.update_certs
        backup_should_reboot = runtime.package_manager.should_reboot_before_cert_update
        backup_detect_confidential_vm = runtime.env_layer.detect_confidential_vm
        backup_hibernation = runtime.package_manager.is_hibernation_enabled_for_cert_update
        backup_latest_certs = runtime.package_manager.are_latest_certs_present

        runtime.package_manager.should_reboot_before_cert_update = self.mock_should_reboot_before_cert_update_returns_false
        runtime.env_layer.detect_confidential_vm = self.mock_detect_confidential_vm_returns_false
        runtime.package_manager.is_hibernation_enabled_for_cert_update = self.mock_is_hibernation_enabled_for_cert_update_returns_false
        runtime.package_manager.are_latest_certs_present = self.mock_are_latest_certs_present_returns_false
        runtime.patch_installer.package_manager.update_certs = self.mock_update_certs_raise_exception

        runtime.patch_installer.start_installation(simulate=True)

        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

        installation_substatus = [item for item in substatus_file_data if item["name"] == Constants.PATCH_INSTALLATION_SUMMARY][0]
        installation_message = json.loads(installation_substatus["formattedMessage"]["message"])
        error_details = installation_message["errors"]["details"]
        is_cert_error_present = any("attempting to update certificates" in error["message"] for error in error_details)
        self.assertTrue(is_cert_error_present, "Expected certificate update failure error to be recorded in installation status.")

        runtime.patch_installer.package_manager.update_certs = backup_up_update_certs
        runtime.package_manager.should_reboot_before_cert_update = backup_should_reboot
        runtime.env_layer.detect_confidential_vm = backup_detect_confidential_vm
        runtime.package_manager.is_hibernation_enabled_for_cert_update = backup_hibernation
        runtime.package_manager.are_latest_certs_present = backup_latest_certs
        runtime.stop()

    def test_try_update_certs_adds_error_to_status_when_update_certs_returns_false(self):
        """When update_certs returns False, an error should be recorded in the installation status."""
        runtime = self._create_update_certs_runtime(enable_uefi_cert_update=True, health_store_id="pub_off_sku_2025.01.01", reboot_setting='IfRequired')
        backup_should_reboot = runtime.package_manager.should_reboot_before_cert_update
        backup_detect_confidential_vm = runtime.env_layer.detect_confidential_vm
        backup_hibernation = runtime.package_manager.is_hibernation_enabled_for_cert_update
        backup_latest_certs = runtime.package_manager.are_latest_certs_present
        backup_update_certs = runtime.patch_installer.package_manager.update_certs

        runtime.package_manager.should_reboot_before_cert_update = self.mock_should_reboot_before_cert_update_returns_false
        runtime.env_layer.detect_confidential_vm = self.mock_detect_confidential_vm_returns_false
        runtime.package_manager.is_hibernation_enabled_for_cert_update = self.mock_is_hibernation_enabled_for_cert_update_returns_false
        runtime.package_manager.are_latest_certs_present = self.mock_are_latest_certs_present_returns_false
        runtime.patch_installer.package_manager.update_certs = self.mock_update_certs_returns_false

        runtime.patch_installer.start_installation(simulate=True)

        with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
            substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

        installation_substatus = [item for item in substatus_file_data if item["name"] == Constants.PATCH_INSTALLATION_SUMMARY][0]
        installation_message = json.loads(installation_substatus["formattedMessage"]["message"])
        error_details = installation_message["errors"]["details"]
        is_cert_update_failure_present = any("Certificates may not have been updated" in error["message"] for error in error_details)
        self.assertTrue(is_cert_update_failure_present, "Expected a certificate update failure error to be recorded in the installation status.")

        runtime.package_manager.should_reboot_before_cert_update = backup_should_reboot
        runtime.env_layer.detect_confidential_vm = backup_detect_confidential_vm
        runtime.package_manager.is_hibernation_enabled_for_cert_update = backup_hibernation
        runtime.package_manager.are_latest_certs_present = backup_latest_certs
        runtime.patch_installer.package_manager.update_certs = backup_update_certs
        runtime.stop()

    def test_try_update_certificates_skips_confidential_vm(self):
        runtime = self._create_update_certs_runtime(enable_uefi_cert_update=True, health_store_id="pub_off_sku_2025.01.01")
        backup_detect_confidential_vm_by_imds = runtime.env_layer.detect_confidential_vm_by_imds
        backup_update_certs = runtime.patch_installer.package_manager.update_certs

        runtime.env_layer.detect_confidential_vm_by_imds = self.mock_detect_confidential_vm_by_imds_returns_true
        runtime.patch_installer.package_manager.update_certs = self.mock_update_certs_returns_false
        runtime.patch_installer.start_installation(simulate=True)
        error_messages = self._get_installation_error_messages(runtime)
        self.assertFalse(any("Confidential VM" in message for message in error_messages))
        self.assertFalse(any("Certificates may not have been updated" in message for message in error_messages))

        runtime.env_layer.detect_confidential_vm_by_imds = backup_detect_confidential_vm_by_imds
        runtime.patch_installer.package_manager.update_certs = backup_update_certs
        runtime.stop()

    def test_try_update_certificates_skips_when_detect_confidential_vm_raises_exception(self):
        runtime = self._create_update_certs_runtime(enable_uefi_cert_update=True, health_store_id="pub_off_sku_2025.01.01")
        backup_detect_confidential_vm = runtime.env_layer.detect_confidential_vm
        backup_update_certs = runtime.patch_installer.package_manager.update_certs

        runtime.env_layer.detect_confidential_vm = self.mock_detect_confidential_vm_raises_exception
        runtime.patch_installer.package_manager.update_certs = self.mock_update_certs_returns_false
        runtime.patch_installer.start_installation(simulate=True)
        error_messages = self._get_installation_error_messages(runtime)
        self.assertFalse(any("Unable to determine whether the VM is a Confidential VM" in message for message in error_messages))
        self.assertFalse(any("Certificates may not have been updated" in message for message in error_messages))

        runtime.env_layer.detect_confidential_vm = backup_detect_confidential_vm
        runtime.patch_installer.package_manager.update_certs = backup_update_certs
        runtime.stop()

    def test_can_continue_cert_update_after_reboot_check(self):
        """ Test all branches of can_continue_cert_update_after_reboot_check() """

        # Use case 1: Reboot required but reboot setting is 'Never' - should not reboot, should return False
        reboot_setting_uc1 = 'Never'
        mock_should_reboot_uc1 = self.mock_should_reboot_before_cert_update_returns_true
        mock_start_reboot_uc1 = None
        expected_result_uc1 = False
        expected_reboot_status_uc1 = Constants.RebootStatus.NOT_NEEDED

        # Use case 2: Reboot required and reboot setting allows it - reboot is initiated, should return False
        reboot_setting_uc2 = 'IfRequired'
        mock_should_reboot_uc2 = self.mock_should_reboot_before_cert_update_returns_true
        mock_start_reboot_uc2 = None
        expected_result_uc2 = False
        expected_reboot_status_uc2 = Constants.RebootStatus.STARTED

        # Use case 3: Reboot not required - cert update can continue, should return True
        reboot_setting_uc3 = 'IfRequired'
        mock_should_reboot_uc3 = self.mock_should_reboot_before_cert_update_returns_false
        mock_start_reboot_uc3 = None
        expected_result_uc3 = True
        expected_reboot_status_uc3 = Constants.RebootStatus.NOT_NEEDED

        # Use case 4: Reboot required but reboot could not be initiated (returns False) - should return False
        reboot_setting_uc4 = 'IfRequired'
        mock_should_reboot_uc4 = self.mock_should_reboot_before_cert_update_returns_true
        mock_start_reboot_uc4 = self.mock_start_reboot_if_required_and_time_available_returns_false
        expected_result_uc4 = False
        expected_reboot_status_uc4 = Constants.RebootStatus.NOT_NEEDED

        # Use case 5: Reboot required but reboot raises an exception - should return False
        reboot_setting_uc5 = 'IfRequired'
        mock_should_reboot_uc5 = self.mock_should_reboot_before_cert_update_returns_true
        mock_start_reboot_uc5 = self.mock_start_reboot_if_required_and_time_available_raises_exception
        expected_result_uc5 = False
        expected_reboot_status_uc5 = Constants.RebootStatus.NOT_NEEDED

        test_input_output_table = [
            [reboot_setting_uc1, mock_should_reboot_uc1, mock_start_reboot_uc1, expected_result_uc1, expected_reboot_status_uc1],
            [reboot_setting_uc2, mock_should_reboot_uc2, mock_start_reboot_uc2, expected_result_uc2, expected_reboot_status_uc2],
            [reboot_setting_uc3, mock_should_reboot_uc3, mock_start_reboot_uc3, expected_result_uc3, expected_reboot_status_uc3],
            [reboot_setting_uc4, mock_should_reboot_uc4, mock_start_reboot_uc4, expected_result_uc4, expected_reboot_status_uc4],
            [reboot_setting_uc5, mock_should_reboot_uc5, mock_start_reboot_uc5, expected_result_uc5, expected_reboot_status_uc5],
        ]

        for row in test_input_output_table:
            reboot_setting, mock_should_reboot, mock_start_reboot, expected_result, expected_reboot_status = row

            runtime = self._create_update_certs_runtime(enable_uefi_cert_update=True, health_store_id="pub_off_sku_2025.01.01", reboot_setting=reboot_setting)
            backup_should_reboot_before_cert_update = runtime.package_manager.should_reboot_before_cert_update
            backup_start_reboot_if_required_and_time_available = runtime.patch_installer.reboot_manager.start_reboot_if_required_and_time_available

            original_force_reboot = runtime.package_manager.force_reboot
            runtime.package_manager.should_reboot_before_cert_update = mock_should_reboot
            if mock_start_reboot is not None:
                runtime.patch_installer.reboot_manager.start_reboot_if_required_and_time_available = mock_start_reboot

            self.assertEqual(runtime.patch_installer.can_continue_cert_update_after_reboot_check(), expected_result, "Failed for use case with reboot_setting={0}, should_reboot={1}".format(reboot_setting, mock_should_reboot.__name__))
            self.assertEqual(runtime.status_handler.get_installation_reboot_status(), expected_reboot_status, "Unexpected reboot status for use case with reboot_setting={0}".format(reboot_setting))
            self.assertEqual(runtime.package_manager.force_reboot, original_force_reboot, "force_reboot was not restored for use case with reboot_setting={0}".format(reboot_setting))

            runtime.package_manager.should_reboot_before_cert_update = backup_should_reboot_before_cert_update
            runtime.patch_installer.reboot_manager.start_reboot_if_required_and_time_available = backup_start_reboot_if_required_and_time_available
            runtime.stop()

    def test_can_continue_cert_update_after_hibernation_check(self):
        """Test all branches of can_continue_cert_update_after_hibernation_check()."""

        # Use case 1: Hibernation enabled - cert update should not continue and an error should be recorded.
        hibernation_check_uc1 = self.mock_is_hibernation_enabled_for_cert_update_returns_true
        expected_result_uc1 = False
        expected_hibernation_error_present_uc1 = True

        # Use case 2: Hibernation disabled - cert update can continue.
        hibernation_check_uc2 = self.mock_is_hibernation_enabled_for_cert_update_returns_false
        expected_result_uc2 = True
        expected_hibernation_error_present_uc2 = False

        # Use case 3: Hibernation check throws - cert update should not continue and an error should be recorded.
        hibernation_check_uc3 = self.mock_is_hibernation_enabled_for_cert_update_raises_exception
        expected_result_uc3 = False
        expected_hibernation_error_present_uc3 = True

        test_input_output_table = [
            [hibernation_check_uc1, expected_result_uc1, expected_hibernation_error_present_uc1, "Turn off hibernation"],
            [hibernation_check_uc2, expected_result_uc2, expected_hibernation_error_present_uc2, ""],
            [hibernation_check_uc3, expected_result_uc3, expected_hibernation_error_present_uc3, "Unable to determine hibernation state"],
        ]

        for row in test_input_output_table:
            mock_hibernation_check, expected_result, expected_hibernation_error_present, expected_error_substring = row

            runtime = self._create_update_certs_runtime(enable_uefi_cert_update=True, health_store_id="pub_off_sku_2025.01.01", reboot_setting='IfRequired')
            backup_is_hibernation_enabled_for_cert_update = runtime.package_manager.is_hibernation_enabled_for_cert_update

            runtime.package_manager.is_hibernation_enabled_for_cert_update = mock_hibernation_check
            runtime.status_handler.set_current_operation(Constants.INSTALLATION)
            runtime.status_handler.set_installation_substatus_json()

            self.assertEqual(runtime.patch_installer.can_continue_cert_update_after_hibernation_check(), expected_result,
                             "Failed for hibernation check use case: {0}".format(mock_hibernation_check.__name__))

            with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
                substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

            installation_substatus = [item for item in substatus_file_data if item["name"] == Constants.PATCH_INSTALLATION_SUMMARY][0]
            installation_message = json.loads(installation_substatus["formattedMessage"]["message"])
            error_details = installation_message["errors"]["details"]
            is_hibernation_error_present = any(expected_error_substring in error["message"] for error in error_details)
            self.assertEqual(is_hibernation_error_present, expected_hibernation_error_present,
                             "Unexpected hibernation error status for use case: {0}".format(mock_hibernation_check.__name__))

            runtime.package_manager.is_hibernation_enabled_for_cert_update = backup_is_hibernation_enabled_for_cert_update
            runtime.stop()

    def test_can_continue_cert_update_after_latest_cert_check(self):
        """Test all branches of can_continue_cert_update_after_latest_cert_check()."""

        # Use case 1: Latest certs already present - cert update should not continue.
        latest_certs_check_uc1 = self.mock_are_latest_certs_present_returns_true
        expected_result_uc1 = False
        expected_latest_cert_error_present_uc1 = False

        # Use case 2: Latest certs not present - cert update can continue.
        latest_certs_check_uc2 = self.mock_are_latest_certs_present_returns_false
        expected_result_uc2 = True
        expected_latest_cert_error_present_uc2 = False

        # Use case 3: Latest cert check throws - cert update should not continue, but this is only warned/logged.
        latest_certs_check_uc3 = lambda: (_ for _ in ()).throw(Exception("Simulated latest cert detection failure"))
        expected_result_uc3 = False
        expected_latest_cert_error_present_uc3 = False

        test_input_output_table = [
            [latest_certs_check_uc1, expected_result_uc1, expected_latest_cert_error_present_uc1],
            [latest_certs_check_uc2, expected_result_uc2, expected_latest_cert_error_present_uc2],
            [latest_certs_check_uc3, expected_result_uc3, expected_latest_cert_error_present_uc3],
        ]

        for row in test_input_output_table:
            mock_latest_cert_check, expected_result, expected_latest_cert_error_present = row

            runtime = self._create_update_certs_runtime(enable_uefi_cert_update=True, health_store_id="pub_off_sku_2025.01.01", reboot_setting='IfRequired')
            backup_are_latest_certs_present = runtime.package_manager.are_latest_certs_present

            runtime.package_manager.are_latest_certs_present = mock_latest_cert_check
            runtime.status_handler.set_current_operation(Constants.INSTALLATION)
            runtime.status_handler.set_installation_substatus_json()

            self.assertEqual(runtime.patch_installer.can_continue_cert_update_after_latest_cert_check(), expected_result,
                             "Failed for latest cert check use case: {0}".format(getattr(mock_latest_cert_check, '__name__', 'lambda')))

            with runtime.env_layer.file_system.open(runtime.execution_config.status_file_path, 'r') as file_handle:
                substatus_file_data = json.load(file_handle)[0]["status"]["substatus"]

            installation_substatus = [item for item in substatus_file_data if item["name"] == Constants.PATCH_INSTALLATION_SUMMARY][0]
            installation_message = json.loads(installation_substatus["formattedMessage"]["message"])
            error_details = installation_message["errors"]["details"]
            is_latest_cert_error_present = any("latest certs" in error["message"].lower() for error in error_details)
            self.assertEqual(is_latest_cert_error_present, expected_latest_cert_error_present,
                             "Unexpected latest cert error status for use case: {0}".format(getattr(mock_latest_cert_check, '__name__', 'lambda')))

            runtime.package_manager.are_latest_certs_present = backup_are_latest_certs_present
            runtime.stop()
    # endregion


if __name__ == '__main__':
    unittest.main()
