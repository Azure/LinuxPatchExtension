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
from core.src.core_logic.Stopwatch import Stopwatch

class TestPatchInstaller(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

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
        installed_update_count, update_run_successful, maintenance_window_exceeded = runtime.patch_installer.install_updates(runtime.maintenance_window, runtime.package_manager, simulate=True)
        self.assertEqual(3, installed_update_count)
        self.assertTrue(update_run_successful)
        self.assertFalse(maintenance_window_exceeded)
        runtime.stop()

    def test_healthstore_writes(self):
        self.healthstore_writes_helper("HealthStoreId", None, False, expected_patch_version="HealthStoreId")
        self.healthstore_writes_helper("HealthStoreId", "MaintenanceRunId", False, expected_patch_version="HealthStoreId")
        self.healthstore_writes_helper(None, "MaintenanceRunId", False, expected_patch_version="MaintenanceRunId")
        self.healthstore_writes_helper(None, "09/16/2021 08:24:42 AM +00:00", False, expected_patch_version="2021.09.16")
        self.healthstore_writes_helper("09/16/2021 08:24:42 AM +00:00", None, False, expected_patch_version="2021.09.16")
        self.healthstore_writes_helper("09/16/2021 08:24:42 AM +00:00", "09/17/2021 08:24:42 AM +00:00", False, expected_patch_version="2021.09.16")
        self.healthstore_writes_helper("09/16/2021 08:24:42 AM +00:00", "<some-guid>", False, expected_patch_version="2021.09.16")
        self.healthstore_writes_helper("09/16/2021 08:24:42 AM +00:00", "<some-guid>", True, expected_patch_version="2021.09.16")

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


if __name__ == '__main__':
    unittest.main()
