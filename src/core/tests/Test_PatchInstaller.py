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
    def mock_try_update_certs_raise_exception(self):
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

    def mock_are_latest_certs_present_with_mokutil_check_returns_true(self):
        return True

    def mock_are_latest_certs_present_with_mokutil_check_returns_false(self):
        return False

    def mock_try_update_certs_returns_true(self):
        return True
    # endregion

    # region Utility functions (update cert tests)
    def _create_update_certs_runtime(self, enable_uefi_cert_update=True, health_store_id=None, operation=Constants.INSTALLATION, reboot_setting=None, package_manager_name=Constants.APT,
                                     enable_uefi_cert_update_for_auto_patching=None, enable_uefi_cert_update_for_all_patching=None, use_per_mode_uefi_cert_update_settings=False):

        argument_composer = ArgumentComposer()
        argument_composer.health_store_id = health_store_id
        argument_composer.operation = operation
        if reboot_setting is not None:
            argument_composer.reboot_setting = reboot_setting

        if not use_per_mode_uefi_cert_update_settings:
            enable_uefi_cert_update_for_auto_patching = bool(enable_uefi_cert_update)
            enable_uefi_cert_update_for_all_patching = bool(enable_uefi_cert_update)

        config_file_path = Constants.AzGPSPaths.UEFI_SETTINGS
        config_settings = {
            Constants.UEFISettings.ENABLED_BY: "TestSetup",
            Constants.UEFISettings.LAST_MODIFIED: "2026-04-21",
            Constants.UEFISettings.ENABLE_UEFI_CERT_UPDATE_FOR_AUTO_PATCHING: enable_uefi_cert_update_for_auto_patching,
            Constants.UEFISettings.ENABLE_UEFI_CERT_UPDATE_FOR_ALL_PATCHING: enable_uefi_cert_update_for_all_patching,
        }
        self.__write_config_settings_to_file(config_settings, config_file_path=config_file_path)
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, package_manager_name)
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
    def test_try_update_certificates__with_various_use_cases(self):
        """Test update certificate flow using consolidated use cases without losing scenario coverage."""

        use_cases = [
            # Use case 1: Feature flag is off
            {
                "name": "feature_flag_off",
                "enable_uefi_cert_update": False,
                "health_store_id": "pub_off_sku_2025.01.01",
                "operation": Constants.INSTALLATION,
                "reboot_setting": None,
                "expected_present": [],
                "expected_absent": ["Certificates may not have been updated"]
            },
            # Use case 2: try_update_certs should NOT be called when health_store_id is None (not a default patching operation)
            {
                "name": "not_default_patching_health_store_id_none",
                "enable_uefi_cert_update": True,
                "health_store_id": None,
                "operation": Constants.INSTALLATION,
                "reboot_setting": None,
                "expected_present": [],
                "expected_absent": ["Certificates may not have been updated"]
            },
            # Use case 3: try_update_certs should NOT be called when health_store_id is an empty string (not a default patching operation)
            {
                "name": "not_default_patching_health_store_id_empty",
                "enable_uefi_cert_update": True,
                "health_store_id": str(),
                "operation": Constants.INSTALLATION,
                "reboot_setting": None,
                "expected_present": [],
                "expected_absent": ["Certificates may not have been updated"]
            },
            # Use case 4: try_update_certs should NOT be called during Assessment (not a default patching operation)
            {
                "name": "not_default_patching_assessment_operation",
                "enable_uefi_cert_update": True,
                "health_store_id": None,
                "operation": Constants.ASSESSMENT,
                "reboot_setting": None,
                "expected_present": [],
                "expected_absent": ["Certificates may not have been updated"]
            },
            # Use case 5: try_update_certs SHOULD be called when this is default patching and all prerequisites are met
            {
                "name": "default_patching_prereqs_met_update_certs_returns_false",
                "enable_uefi_cert_update": True,
                "health_store_id": "pub_off_sku_2025.01.01",
                "operation": Constants.INSTALLATION,
                "reboot_setting": "IfRequired",
                "mock_should_reboot": self.mock_should_reboot_before_cert_update_returns_false,
                "mock_detect_confidential_vm": self.mock_detect_confidential_vm_returns_false,
                "mock_hibernation": self.mock_is_hibernation_enabled_for_cert_update_returns_false,
                "mock_latest_certs": self.mock_are_latest_certs_present_with_mokutil_check_returns_false,
                "expected_present": ["Certificates may not have been updated"],
                "expected_absent": []
            },
            # Use case 6: update_certs should NOT be called when reboot is required but reboot setting is 'Never'
            {
                "name": "reboot_required_but_reboot_setting_never",
                "enable_uefi_cert_update": True,
                "health_store_id": "pub_off_sku_2025.01.01",
                "operation": Constants.INSTALLATION,
                "reboot_setting": "Never",
                "mock_should_reboot": self.mock_should_reboot_before_cert_update_returns_true,
                "mock_detect_confidential_vm": self.mock_detect_confidential_vm_returns_false,
                "mock_hibernation": self.mock_is_hibernation_enabled_for_cert_update_returns_false,
                "mock_latest_certs": self.mock_are_latest_certs_present_with_mokutil_check_returns_false,
                "expected_present": ["reboot first"],
                "expected_absent": []
            },
            # Use case 7: update_certs should NOT be called when VM is a CVM
            {
                "name": "skip_when_confidential_vm",
                "enable_uefi_cert_update": True,
                "health_store_id": "pub_off_sku_2025.01.01",
                "operation": Constants.INSTALLATION,
                "reboot_setting": "IfRequired",
                "mock_should_reboot": self.mock_should_reboot_before_cert_update_returns_false,
                "mock_detect_confidential_vm_by_imds": self.mock_detect_confidential_vm_by_imds_returns_true,
                "expected_present": [],
                "expected_absent": ["Confidential VM", "Certificates may not have been updated"]
            },
            # Use case 8: update_certs should NOT be called when hibernation is enabled
            {
                "name": "hibernation_enabled",
                "enable_uefi_cert_update": True,
                "health_store_id": "pub_off_sku_2025.01.01",
                "operation": Constants.INSTALLATION,
                "reboot_setting": "IfRequired",
                "mock_should_reboot": self.mock_should_reboot_before_cert_update_returns_false,
                "mock_detect_confidential_vm": self.mock_detect_confidential_vm_returns_false,
                "mock_hibernation": self.mock_is_hibernation_enabled_for_cert_update_returns_true,
                "expected_present": ["Turn off hibernation"],
                "expected_absent": []
            },
            # Use case 9: update_certs should NOT be called when latest certs are already present
            {
                "name": "latest_certs_already_present",
                "enable_uefi_cert_update": True,
                "health_store_id": "pub_off_sku_2025.01.01",
                "operation": Constants.INSTALLATION,
                "reboot_setting": "IfRequired",
                "mock_should_reboot": self.mock_should_reboot_before_cert_update_returns_true,
                "mock_detect_confidential_vm": self.mock_detect_confidential_vm_returns_false,
                "mock_hibernation": self.mock_is_hibernation_enabled_for_cert_update_returns_false,
                "mock_latest_certs": self.mock_are_latest_certs_present_with_mokutil_check_returns_true,
                "expected_present": [],
                "expected_absent": ["Certificates may not have been updated"]
            },
            # Use case 10: exception from update_certs should be swallowed and recorded in status
            {
                "name": "update_certs_raises_exception_is_swallowed_and_reported",
                "enable_uefi_cert_update": True,
                "health_store_id": "pub_off_sku_2025.01.01",
                "operation": Constants.INSTALLATION,
                "reboot_setting": "IfRequired",
                "mock_should_reboot": self.mock_should_reboot_before_cert_update_returns_false,
                "mock_detect_confidential_vm": self.mock_detect_confidential_vm_returns_false,
                "mock_hibernation": self.mock_is_hibernation_enabled_for_cert_update_returns_false,
                "mock_latest_certs": self.mock_are_latest_certs_present_with_mokutil_check_returns_false,
                "mock_try_update_certs": self.mock_try_update_certs_raise_exception,
                "expected_present": ["attempting to update certificates"],
                "expected_absent": []
            },
            # Use case 11: if confidential-VM detection throws, cert update should be skipped without cert-update failure status
            {
                "name": "skip_when_detect_confidential_vm_raises_exception",
                "enable_uefi_cert_update": True,
                "health_store_id": "pub_off_sku_2025.01.01",
                "operation": Constants.INSTALLATION,
                "reboot_setting": None,
                "mock_detect_confidential_vm": self.mock_detect_confidential_vm_raises_exception,
                "expected_present": [],
                "expected_absent": ["Unable to determine whether the VM is a Confidential VM", "Certificates may not have been updated"]
            }
        ]

        for use_case in use_cases:
            runtime = self._create_update_certs_runtime(
                enable_uefi_cert_update=bool(use_case["enable_uefi_cert_update"]),
                health_store_id=use_case["health_store_id"],
                operation=use_case["operation"],
                reboot_setting=use_case["reboot_setting"]
            )

            backup_should_reboot = runtime.package_manager.is_reboot_required_before_cert_update
            backup_detect_confidential_vm = runtime.env_layer.detect_confidential_vm
            backup_detect_confidential_vm_by_imds = runtime.env_layer.detect_confidential_vm_by_imds
            backup_hibernation = runtime.package_manager.is_hibernation_enabled_for_cert_update
            backup_latest_certs = runtime.package_manager.are_latest_certs_present
            backup_try_update_certs = runtime.package_manager.try_update_certs

            if "mock_should_reboot" in use_case:
                runtime.package_manager.is_reboot_required_before_cert_update = use_case["mock_should_reboot"]
            if "mock_detect_confidential_vm" in use_case:
                runtime.env_layer.detect_confidential_vm = use_case["mock_detect_confidential_vm"]
            if "mock_detect_confidential_vm_by_imds" in use_case:
                runtime.env_layer.detect_confidential_vm_by_imds = use_case["mock_detect_confidential_vm_by_imds"]
            if "mock_hibernation" in use_case:
                runtime.package_manager.is_hibernation_enabled_for_cert_update = use_case["mock_hibernation"]
            if "mock_latest_certs" in use_case:
                runtime.package_manager.are_latest_certs_present = use_case["mock_latest_certs"]
            if "mock_try_update_certs" in use_case:
                runtime.package_manager.try_update_certs = use_case["mock_try_update_certs"]

            runtime.patch_installer.start_installation(simulate=True)
            error_messages = self._get_installation_error_messages(runtime)

            for expected_message in use_case["expected_present"]:
                self.assertTrue(
                    any(expected_message in message for message in error_messages),
                    "Expected '{0}' for use case '{1}'".format(expected_message, use_case["name"])
                )

            for forbidden_message in use_case["expected_absent"]:
                self.assertFalse(
                    any(forbidden_message in message for message in error_messages),
                    "Did not expect '{0}' for use case '{1}'".format(forbidden_message, use_case["name"])
                )

            runtime.package_manager.is_reboot_required_before_cert_update = backup_should_reboot
            runtime.env_layer.detect_confidential_vm = backup_detect_confidential_vm
            runtime.env_layer.detect_confidential_vm_by_imds = backup_detect_confidential_vm_by_imds
            runtime.package_manager.is_hibernation_enabled_for_cert_update = backup_hibernation
            runtime.package_manager.are_latest_certs_present = backup_latest_certs
            runtime.package_manager.try_update_certs = backup_try_update_certs
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
            backup_should_reboot_before_cert_update = runtime.package_manager.is_reboot_required_before_cert_update
            backup_start_reboot_if_required_and_time_available = runtime.patch_installer.reboot_manager.start_reboot_if_required_and_time_available

            original_force_reboot = runtime.package_manager.force_reboot
            runtime.package_manager.is_reboot_required_before_cert_update = mock_should_reboot
            if mock_start_reboot is not None:
                runtime.patch_installer.reboot_manager.start_reboot_if_required_and_time_available = mock_start_reboot

            self.assertEqual(runtime.patch_installer.ensure_pre_cert_update_reboot_completed(), expected_result, "Failed for use case with reboot_setting={0}, should_reboot={1}".format(reboot_setting, mock_should_reboot.__name__))
            self.assertEqual(runtime.status_handler.get_installation_reboot_status(), expected_reboot_status, "Unexpected reboot status for use case with reboot_setting={0}".format(reboot_setting))
            self.assertEqual(runtime.package_manager.force_reboot, original_force_reboot, "force_reboot was not restored for use case with reboot_setting={0}".format(reboot_setting))

            runtime.package_manager.is_reboot_required_before_cert_update = backup_should_reboot_before_cert_update
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
        latest_certs_check_uc1 = self.mock_are_latest_certs_present_with_mokutil_check_returns_true
        expected_result_uc1 = False
        expected_latest_cert_error_present_uc1 = False

        # Use case 2: Latest certs not present - cert update can continue.
        latest_certs_check_uc2 = self.mock_are_latest_certs_present_with_mokutil_check_returns_false
        expected_result_uc2 = True
        expected_latest_cert_error_present_uc2 = False

        test_input_output_table = [
            [latest_certs_check_uc1, expected_result_uc1, expected_latest_cert_error_present_uc1],
            [latest_certs_check_uc2, expected_result_uc2, expected_latest_cert_error_present_uc2],
        ]

        for row in test_input_output_table:
            mock_latest_cert_check, expected_result, expected_latest_cert_error_present = row

            runtime = self._create_update_certs_runtime(enable_uefi_cert_update=True, health_store_id="pub_off_sku_2025.01.01", reboot_setting='IfRequired')
            backup_are_latest_certs_present = runtime.package_manager.are_latest_certs_present_with_mokutil_check

            runtime.package_manager.are_latest_certs_present_with_mokutil_check = mock_latest_cert_check
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

            runtime.package_manager.are_latest_certs_present_with_mokutil_check = backup_are_latest_certs_present
            runtime.stop()
    # endregion

    # region Unit Tests for Certificate Update Allow/Deny Logic
    def test_cert_update_allow_deny_with_various_config_combinations(self):
        """Test cert update allow/deny across APT (default-allow) and non-APT (default-deny) package managers
        with various EnableUEFICertUpdateForAutoPatching / EnableUEFICertUpdateForAllPatching configuration combinations.
        When cert update is expected to proceed: try_update_certs returns False, producing a
        'Certificates may not have been updated' error to confirm it was reached.
        When cert update is expected to be blocked: try_update_certs raises an exception; the absence
        of that error in status confirms it was never called.

        APT cert update logic (new):
        - If EnableUEFICertUpdateForAllPatching=True (all patching enabled): allowed for any installation operation (auto or non-auto).
        - If EnableUEFICertUpdateForAutoPatching=False (auto explicitly disabled): blocked for auto (default) patching; non-default also falls through to blocked.
        - Default (no explicit config): allowed only for auto (default) patching (health_store_id is set).

        Non-APT cert update logic:
        - Allowed only when EnableUEFICertUpdateForAutoPatching=True and this is a default (auto) patching operation."""

        # Use case 1: APT - both config flags not set (None) during default (auto) patching - cert update proceeds by default
        name_uc1 = "APT_default_allow_auto_patching"
        package_manager_uc1 = Constants.APT
        health_store_id_uc1 = "pub_off_sku_2025.01.01"
        reboot_setting_uc1 = 'IfRequired'
        enable_auto_uc1 = None
        enable_all_uc1 = None
        mock_detect_cvm_uc1 = self.mock_detect_confidential_vm_returns_false
        mock_hibernation_uc1 = self.mock_is_hibernation_enabled_for_cert_update_returns_false
        mock_latest_certs_uc1 = self.mock_are_latest_certs_present_with_mokutil_check_returns_false
        mock_should_reboot_uc1 = self.mock_should_reboot_before_cert_update_returns_false
        mock_try_update_certs_uc1 = self.mock_update_certs_returns_false
        expected_cert_update_called_uc1 = True

        # Use case 2: APT - auto-patching explicitly disabled during non-default patching - cert update is blocked
        name_uc2 = "APT_auto_explicitly_disabled"
        package_manager_uc2 = Constants.APT
        health_store_id_uc2 = None
        reboot_setting_uc2 = None
        enable_auto_uc2 = False
        enable_all_uc2 = None
        mock_detect_cvm_uc2 = None
        mock_hibernation_uc2 = None
        mock_latest_certs_uc2 = None
        mock_should_reboot_uc2 = None
        mock_try_update_certs_uc2 = self.mock_try_update_certs_raise_exception
        expected_cert_update_called_uc2 = False

        # Use case 3: APT all patching explicitly enabled (all_patching=True) during default patching - cert update is allowed
        # EnableUEFICertUpdateForAllPatching=True takes precedence and allows cert update for any installation operation
        name_uc3 = "APT_all_patching_enabled_default_patching_allowed"
        package_manager_uc3 = Constants.APT
        health_store_id_uc3 = "pub_off_sku_2025.01.01"
        reboot_setting_uc3 = 'IfRequired'
        enable_auto_uc3 = False
        enable_all_uc3 = True
        mock_detect_cvm_uc3 = self.mock_detect_confidential_vm_returns_false
        mock_hibernation_uc3 = self.mock_is_hibernation_enabled_for_cert_update_returns_false
        mock_latest_certs_uc3 = self.mock_are_latest_certs_present_with_mokutil_check_returns_false
        mock_should_reboot_uc3 = self.mock_should_reboot_before_cert_update_returns_false
        mock_try_update_certs_uc3 = self.mock_update_certs_returns_false
        expected_cert_update_called_uc3 = True

        # Use case 4: APT all patching explicitly enabled (all_patching=True) during non-default patching - cert update is allowed
        name_uc4 = "APT_all_patching_enabled_non_default_patching_allowed"
        package_manager_uc4 = Constants.APT
        health_store_id_uc4 = None
        reboot_setting_uc4 = 'IfRequired'
        enable_auto_uc4 = False
        enable_all_uc4 = True
        mock_detect_cvm_uc4 = self.mock_detect_confidential_vm_returns_false
        mock_hibernation_uc4 = self.mock_is_hibernation_enabled_for_cert_update_returns_false
        mock_latest_certs_uc4 = self.mock_are_latest_certs_present_with_mokutil_check_returns_false
        mock_should_reboot_uc4 = self.mock_should_reboot_before_cert_update_returns_false
        mock_try_update_certs_uc4 = self.mock_update_certs_returns_false
        expected_cert_update_called_uc4 = True

        # Use case 5: Non-APT - both config flags not set (None) - cert update is blocked by default
        name_uc5 = "non_APT_default_deny"
        package_manager_uc5 = Constants.TDNF
        health_store_id_uc5 = "pub_off_sku_2025.01.01"
        reboot_setting_uc5 = None
        enable_auto_uc5 = None
        enable_all_uc5 = None
        mock_detect_cvm_uc5 = None
        mock_hibernation_uc5 = None
        mock_latest_certs_uc5 = None
        mock_should_reboot_uc5 = None
        mock_try_update_certs_uc5 = self.mock_try_update_certs_raise_exception
        expected_cert_update_called_uc5 = False

        # Use case 6: Non-APT - auto-patching explicitly enabled during default patching - cert update is allowed
        name_uc6 = "non_APT_auto_enabled_default_patching_allowed"
        package_manager_uc6 = Constants.TDNF
        health_store_id_uc6 = "pub_off_sku_2025.01.01"
        reboot_setting_uc6 = 'IfRequired'
        enable_auto_uc6 = True
        enable_all_uc6 = None
        mock_detect_cvm_uc6 = self.mock_detect_confidential_vm_returns_false
        mock_hibernation_uc6 = self.mock_is_hibernation_enabled_for_cert_update_returns_false
        mock_latest_certs_uc6 = self.mock_are_latest_certs_present_with_mokutil_check_returns_false
        mock_should_reboot_uc6 = self.mock_should_reboot_before_cert_update_returns_false
        mock_try_update_certs_uc6 = self.mock_update_certs_returns_false
        expected_cert_update_called_uc6 = True

        # Use case 7: Non-APT - auto-patching explicitly enabled during non-default patching (health_store_id is None) - cert update is blocked
        name_uc7 = "non_APT_auto_enabled_non_default_patching_blocked"
        package_manager_uc7 = Constants.TDNF
        health_store_id_uc7 = None
        reboot_setting_uc7 = None
        enable_auto_uc7 = True
        enable_all_uc7 = None
        mock_detect_cvm_uc7 = None
        mock_hibernation_uc7 = None
        mock_latest_certs_uc7 = None
        mock_should_reboot_uc7 = None
        mock_try_update_certs_uc7 = self.mock_try_update_certs_raise_exception
        expected_cert_update_called_uc7 = False

        # Use case 8: APT - both config flags not set (None) during non-default patching - cert update is blocked by default
        name_uc8 = "APT_default_deny_all_patching"
        package_manager_uc8 = Constants.APT
        health_store_id_uc8 = None
        reboot_setting_uc8 = None
        enable_auto_uc8 = None
        enable_all_uc8 = None
        mock_detect_cvm_uc8 = None
        mock_hibernation_uc8 = None
        mock_latest_certs_uc8 = None
        mock_should_reboot_uc8 = None
        mock_try_update_certs_uc8 = self.mock_try_update_certs_raise_exception
        expected_cert_update_called_uc8 = False

        test_input_output_table = [
            [name_uc1, package_manager_uc1, health_store_id_uc1, reboot_setting_uc1, enable_auto_uc1, enable_all_uc1, mock_detect_cvm_uc1, mock_hibernation_uc1, mock_latest_certs_uc1, mock_should_reboot_uc1, mock_try_update_certs_uc1, expected_cert_update_called_uc1],
            [name_uc2, package_manager_uc2, health_store_id_uc2, reboot_setting_uc2, enable_auto_uc2, enable_all_uc2, mock_detect_cvm_uc2, mock_hibernation_uc2, mock_latest_certs_uc2, mock_should_reboot_uc2, mock_try_update_certs_uc2, expected_cert_update_called_uc2],
            [name_uc3, package_manager_uc3, health_store_id_uc3, reboot_setting_uc3, enable_auto_uc3, enable_all_uc3, mock_detect_cvm_uc3, mock_hibernation_uc3, mock_latest_certs_uc3, mock_should_reboot_uc3, mock_try_update_certs_uc3, expected_cert_update_called_uc3],
            [name_uc4, package_manager_uc4, health_store_id_uc4, reboot_setting_uc4, enable_auto_uc4, enable_all_uc4, mock_detect_cvm_uc4, mock_hibernation_uc4, mock_latest_certs_uc4, mock_should_reboot_uc4, mock_try_update_certs_uc4, expected_cert_update_called_uc4],
            [name_uc5, package_manager_uc5, health_store_id_uc5, reboot_setting_uc5, enable_auto_uc5, enable_all_uc5, mock_detect_cvm_uc5, mock_hibernation_uc5, mock_latest_certs_uc5, mock_should_reboot_uc5, mock_try_update_certs_uc5, expected_cert_update_called_uc5],
            [name_uc6, package_manager_uc6, health_store_id_uc6, reboot_setting_uc6, enable_auto_uc6, enable_all_uc6, mock_detect_cvm_uc6, mock_hibernation_uc6, mock_latest_certs_uc6, mock_should_reboot_uc6, mock_try_update_certs_uc6, expected_cert_update_called_uc6],
            [name_uc7, package_manager_uc7, health_store_id_uc7, reboot_setting_uc7, enable_auto_uc7, enable_all_uc7, mock_detect_cvm_uc7, mock_hibernation_uc7, mock_latest_certs_uc7, mock_should_reboot_uc7, mock_try_update_certs_uc7, expected_cert_update_called_uc7],
            [name_uc8, package_manager_uc8, health_store_id_uc8, reboot_setting_uc8, enable_auto_uc8, enable_all_uc8, mock_detect_cvm_uc8, mock_hibernation_uc8, mock_latest_certs_uc8, mock_should_reboot_uc8, mock_try_update_certs_uc8, expected_cert_update_called_uc8],
        ]

        for row in test_input_output_table:
            name, package_manager, health_store_id, reboot_setting, enable_auto, enable_all, mock_detect_cvm, mock_hibernation, mock_latest_certs, mock_should_reboot, mock_try_update_certs, expected_cert_update_called = row

            runtime = self._create_update_certs_runtime(
                health_store_id=health_store_id,
                reboot_setting=reboot_setting,
                package_manager_name=package_manager,
                enable_uefi_cert_update_for_auto_patching=enable_auto,
                enable_uefi_cert_update_for_all_patching=enable_all,
                use_per_mode_uefi_cert_update_settings=True)
            runtime.status_handler.set_current_operation(Constants.INSTALLATION)
            runtime.status_handler.set_installation_substatus_json()

            backup_detect_cvm = runtime.env_layer.detect_confidential_vm
            backup_hibernation = runtime.package_manager.is_hibernation_enabled_for_cert_update
            backup_latest_certs = runtime.package_manager.are_latest_certs_present_with_mokutil_check
            backup_should_reboot = runtime.package_manager.is_reboot_required_before_cert_update
            backup_try_update_certs = runtime.package_manager.try_update_certs

            if mock_detect_cvm is not None:
                runtime.env_layer.detect_confidential_vm = mock_detect_cvm
            if mock_hibernation is not None:
                runtime.package_manager.is_hibernation_enabled_for_cert_update = mock_hibernation
            if mock_latest_certs is not None:
                runtime.package_manager.are_latest_certs_present_with_mokutil_check = mock_latest_certs
            if mock_should_reboot is not None:
                runtime.package_manager.is_reboot_required_before_cert_update = mock_should_reboot
            runtime.package_manager.try_update_certs = mock_try_update_certs

            runtime.patch_installer.try_update_certificates()

            error_messages = self._get_installation_error_messages(runtime)
            if expected_cert_update_called:
                self.assertTrue(any("Certificates may not have been updated" in msg for msg in error_messages),
                                "cert update should have proceeded for use case: {0}".format(name))
            else:
                self.assertFalse(any("attempting to update certificates" in msg for msg in error_messages),
                                 "cert update must not have been called for use case: {0}".format(name))

            runtime.env_layer.detect_confidential_vm = backup_detect_cvm
            runtime.package_manager.is_hibernation_enabled_for_cert_update = backup_hibernation
            runtime.package_manager.are_latest_certs_present_with_mokutil_check = backup_latest_certs
            runtime.package_manager.is_reboot_required_before_cert_update = backup_should_reboot
            runtime.package_manager.try_update_certs = backup_try_update_certs
            runtime.stop()
    # endregion

    def test_try_update_certificates__with_various_outcomes(self):
        """Test try_update_certificates outcomes: blocked early (allow check / prerequisites), update succeeds, update fails, update raises exception."""

        # Use case 1: cert update allowed, all prerequisites met, update succeeds - no cert error should be recorded
        name_uc1 = "allowed_prereqs_met_success"
        health_store_id_uc1 = "test_id"
        reboot_setting_uc1 = 'IfRequired'
        enable_auto_uc1 = None
        mock_detect_cvm_uc1 = self.mock_detect_confidential_vm_returns_false
        mock_hibernation_uc1 = self.mock_is_hibernation_enabled_for_cert_update_returns_false
        mock_latest_certs_uc1 = self.mock_are_latest_certs_present_with_mokutil_check_returns_false
        mock_should_reboot_uc1 = self.mock_should_reboot_before_cert_update_returns_false
        mock_try_update_certs_uc1 = self.mock_try_update_certs_returns_true
        expected_present_uc1 = []
        expected_absent_uc1 = ["Certificates may not have been updated", "attempting to update certificates"]

        # Use case 2: cert update not allowed (auto-patching explicitly disabled) - try_update_certs must not be reached
        name_uc2 = "not_allowed_auto_disabled"
        health_store_id_uc2 = "test_id"
        reboot_setting_uc2 = None
        enable_auto_uc2 = False
        mock_detect_cvm_uc2 = None
        mock_hibernation_uc2 = None
        mock_latest_certs_uc2 = None
        mock_should_reboot_uc2 = None
        mock_try_update_certs_uc2 = self.mock_try_update_certs_raise_exception
        expected_present_uc2 = []
        expected_absent_uc2 = ["attempting to update certificates"]

        # Use case 3: cert update allowed but prerequisites not met (VM is a CVM) - try_update_certs must not be reached
        name_uc3 = "prereqs_not_met_cvm_detected"
        health_store_id_uc3 = "test_id"
        reboot_setting_uc3 = 'IfRequired'
        enable_auto_uc3 = None
        mock_detect_cvm_uc3 = self.mock_detect_confidential_vm_by_imds_returns_true
        mock_hibernation_uc3 = None
        mock_latest_certs_uc3 = None
        mock_should_reboot_uc3 = None
        mock_try_update_certs_uc3 = self.mock_try_update_certs_raise_exception
        expected_present_uc3 = []
        expected_absent_uc3 = ["attempting to update certificates"]

        # Use case 4: cert update allowed, all prerequisites met, update returns False - cert error should be recorded
        name_uc4 = "allowed_prereqs_met_update_fails"
        health_store_id_uc4 = "test_id"
        reboot_setting_uc4 = 'IfRequired'
        enable_auto_uc4 = None
        mock_detect_cvm_uc4 = self.mock_detect_confidential_vm_returns_false
        mock_hibernation_uc4 = self.mock_is_hibernation_enabled_for_cert_update_returns_false
        mock_latest_certs_uc4 = self.mock_are_latest_certs_present_with_mokutil_check_returns_false
        mock_should_reboot_uc4 = self.mock_should_reboot_before_cert_update_returns_false
        mock_try_update_certs_uc4 = self.mock_update_certs_returns_false
        expected_present_uc4 = ["Certificates may not have been updated"]
        expected_absent_uc4 = []

        # Use case 5: cert update allowed, all prerequisites met, update raises exception - exception error should be recorded
        name_uc5 = "allowed_prereqs_met_update_raises_exception"
        health_store_id_uc5 = "test_id"
        reboot_setting_uc5 = 'IfRequired'
        enable_auto_uc5 = None
        mock_detect_cvm_uc5 = self.mock_detect_confidential_vm_returns_false
        mock_hibernation_uc5 = self.mock_is_hibernation_enabled_for_cert_update_returns_false
        mock_latest_certs_uc5 = self.mock_are_latest_certs_present_with_mokutil_check_returns_false
        mock_should_reboot_uc5 = self.mock_should_reboot_before_cert_update_returns_false
        mock_try_update_certs_uc5 = self.mock_try_update_certs_raise_exception
        expected_present_uc5 = ["attempting to update certificates"]
        expected_absent_uc5 = []

        test_input_output_table = [
            [name_uc1, health_store_id_uc1, reboot_setting_uc1, enable_auto_uc1, mock_detect_cvm_uc1, mock_hibernation_uc1, mock_latest_certs_uc1, mock_should_reboot_uc1, mock_try_update_certs_uc1, expected_present_uc1, expected_absent_uc1],
            [name_uc2, health_store_id_uc2, reboot_setting_uc2, enable_auto_uc2, mock_detect_cvm_uc2, mock_hibernation_uc2, mock_latest_certs_uc2, mock_should_reboot_uc2, mock_try_update_certs_uc2, expected_present_uc2, expected_absent_uc2],
            [name_uc3, health_store_id_uc3, reboot_setting_uc3, enable_auto_uc3, mock_detect_cvm_uc3, mock_hibernation_uc3, mock_latest_certs_uc3, mock_should_reboot_uc3, mock_try_update_certs_uc3, expected_present_uc3, expected_absent_uc3],
            [name_uc4, health_store_id_uc4, reboot_setting_uc4, enable_auto_uc4, mock_detect_cvm_uc4, mock_hibernation_uc4, mock_latest_certs_uc4, mock_should_reboot_uc4, mock_try_update_certs_uc4, expected_present_uc4, expected_absent_uc4],
            [name_uc5, health_store_id_uc5, reboot_setting_uc5, enable_auto_uc5, mock_detect_cvm_uc5, mock_hibernation_uc5, mock_latest_certs_uc5, mock_should_reboot_uc5, mock_try_update_certs_uc5, expected_present_uc5, expected_absent_uc5],
        ]

        for row in test_input_output_table:
            name, health_store_id, reboot_setting, enable_auto, mock_detect_cvm, mock_hibernation, mock_latest_certs, mock_should_reboot, mock_try_update_certs, expected_present, expected_absent = row

            runtime = self._create_update_certs_runtime(
                health_store_id=health_store_id,
                reboot_setting=reboot_setting,
                enable_uefi_cert_update_for_auto_patching=enable_auto,
                use_per_mode_uefi_cert_update_settings=True)
            runtime.status_handler.set_current_operation(Constants.INSTALLATION)
            runtime.status_handler.set_installation_substatus_json()

            backup_detect_cvm = runtime.env_layer.detect_confidential_vm
            backup_hibernation = runtime.package_manager.is_hibernation_enabled_for_cert_update
            backup_latest_certs = runtime.package_manager.are_latest_certs_present_with_mokutil_check
            backup_should_reboot = runtime.package_manager.is_reboot_required_before_cert_update
            backup_try_update_certs = runtime.package_manager.try_update_certs

            if mock_detect_cvm is not None:
                runtime.env_layer.detect_confidential_vm = mock_detect_cvm
            if mock_hibernation is not None:
                runtime.package_manager.is_hibernation_enabled_for_cert_update = mock_hibernation
            if mock_latest_certs is not None:
                runtime.package_manager.are_latest_certs_present_with_mokutil_check = mock_latest_certs
            if mock_should_reboot is not None:
                runtime.package_manager.is_reboot_required_before_cert_update = mock_should_reboot
            runtime.package_manager.try_update_certs = mock_try_update_certs

            runtime.patch_installer.try_update_certificates()

            error_messages = self._get_installation_error_messages(runtime)
            for expected_message in expected_present:
                self.assertTrue(any(expected_message in msg for msg in error_messages),
                                "Expected '{0}' for use case: {1}".format(expected_message, name))
            for absent_message in expected_absent:
                self.assertFalse(any(absent_message in msg for msg in error_messages),
                                 "Did not expect '{0}' for use case: {1}".format(absent_message, name))

            runtime.env_layer.detect_confidential_vm = backup_detect_cvm
            runtime.package_manager.is_hibernation_enabled_for_cert_update = backup_hibernation
            runtime.package_manager.are_latest_certs_present_with_mokutil_check = backup_latest_certs
            runtime.package_manager.is_reboot_required_before_cert_update = backup_should_reboot
            runtime.package_manager.try_update_certs = backup_try_update_certs
            runtime.stop()


if __name__ == '__main__':
    unittest.main()

