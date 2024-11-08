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
import os
import socket
import tempfile
import time
import uuid

from core.src.service_interfaces.TelemetryWriter import TelemetryWriter
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.LegacyEnvLayerExtensions import LegacyEnvLayerExtensions
from core.src.bootstrap.Bootstrapper import Bootstrapper
from core.src.bootstrap.Constants import Constants

# Todo: find a different way to import these
try:
    import urllib2 as urlreq   # Python 2.x
except:
    import urllib.request as urlreq   # Python 3.x

try:
    from StringIO import StringIO # for Python 2
except ImportError:
    from io import StringIO # for Python 3


class RuntimeCompositor(object):
    def __init__(self, argv=Constants.DEFAULT_UNSPECIFIED_VALUE, legacy_mode=False, package_manager_name=Constants.APT, vm_cloud_type=Constants.VMCloudType.AZURE, set_mock_sudo_status='Always_True'):
        # Init data
        self.original_rm_start_reboot = None
        self.set_mock_sudo_status = set_mock_sudo_status
        self.sudo_check_status_attempts = 0
        self.current_env = Constants.DEV
        os.environ[Constants.LPE_ENV_VARIABLE] = self.current_env
        self.argv = argv if argv != Constants.DEFAULT_UNSPECIFIED_VALUE else ArgumentComposer().get_composed_arguments()
        self.vm_cloud_type = vm_cloud_type
        Constants.SystemPaths.SYSTEMD_ROOT = os.getcwd() # mocking to pass a basic systemd check in Windows
        self.is_github_runner = os.getenv('RUNNER_TEMP', None) is not None

        # speed up test execution
        Constants.MAX_FILE_OPERATION_RETRY_COUNT = 1
        Constants.MAX_IMDS_CONNECTION_RETRY_COUNT = 1
        Constants.WAIT_TIME_AFTER_HEALTHSTORE_STATUS_UPDATE_IN_SECS = 0

        if self.is_github_runner:
            def mkdtemp_runner():
                temp_path = os.path.join(os.getenv('RUNNER_TEMP'), str(uuid.uuid4()))
                os.mkdir(temp_path)
                return temp_path
            tempfile.mkdtemp = mkdtemp_runner

        # Overriding time.sleep and urlopen to avoid delays in test execution
        self.backup_time_sleep = time.sleep
        time.sleep = self.mock_sleep
        self.backup_url_open = urlreq.urlopen
        urlreq.urlopen = self.mock_urlopen

        # Adapted bootstrapper
        self.bootstrapper = Bootstrapper(self.argv, capture_stdout=False)

        # Reconfigure env layer for legacy mode tests
        self.env_layer = self.bootstrapper.env_layer

        # Overriding sudo status check
        if self.set_mock_sudo_status == 'Always_True':
            self.bootstrapper.check_sudo_status = self.check_sudo_status
        elif self.set_mock_sudo_status == 'Always_False':
            self.bootstrapper.run_command_output = self.mock_failed_run_command_output
        elif self.set_mock_sudo_status == 'Retry_True':
            self.bootstrapper.run_command_output = self.mock_retry_run_command_output

        if legacy_mode:
            self.legacy_env_layer_extensions = LegacyEnvLayerExtensions(package_manager_name)
            self.reconfigure_env_layer_to_legacy_mode()

        # Core components
        self.container = self.bootstrapper.build_out_container()
        self.file_logger = self.bootstrapper.file_logger
        self.composite_logger = self.bootstrapper.composite_logger

        # re-initializing telemetry_writer, outside of Bootstrapper, to correctly set the env_layer configured for tests
        self.telemetry_writer = TelemetryWriter(self.env_layer, self.composite_logger, self.bootstrapper.telemetry_writer.events_folder_path, self.bootstrapper.telemetry_supported)
        self.bootstrapper.telemetry_writer = self.telemetry_writer
        self.bootstrapper.composite_logger.telemetry_writer = self.telemetry_writer

        self.lifecycle_manager, self.status_handler = self.bootstrapper.build_core_components(self.container)

        # Business logic components
        self.execution_config = self.container.get('execution_config')
        self.legacy_env_layer_extensions.set_temp_folder_path(self.execution_config.temp_folder)
        self.package_manager = self.container.get('package_manager')
        self.backup_get_current_auto_os_patch_state = None
        self.reconfigure_package_manager()
        self.configure_patching_processor = self.container.get('configure_patching_processor')
        self.reboot_manager = self.container.get('reboot_manager')
        self.reconfigure_reboot_manager()
        self.package_filter = self.container.get('package_filter')
        self.patch_assessor = self.container.get('patch_assessor')
        self.patch_installer = self.container.get('patch_installer')
        self.maintenance_window = self.container.get('maintenance_window')
        self.vm_cloud_type = self.bootstrapper.configuration_factory.vm_cloud_type
        # Extension handler dependency
        self.write_ext_state_file(self.lifecycle_manager.ext_state_file_path, self.execution_config.sequence_number, datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), self.execution_config.operation)

        # Write file to temp dir
        self.write_to_file(os.path.join(self.execution_config.temp_folder, "temp1.list"), "test temp file")

        # Mock service and timer creation and removal used for Auto Assessment
        self.backup_create_and_set_service_idem = self.configure_patching_processor.auto_assess_service_manager.create_and_set_service_idem
        self.configure_patching_processor.auto_assess_service_manager.create_and_set_service_idem = self.mock_create_and_set_service_idem
        self.backup_mock_create_and_set_timer_idem = self.configure_patching_processor.auto_assess_timer_manager.create_and_set_timer_idem
        self.configure_patching_processor.auto_assess_timer_manager.create_and_set_timer_idem = self.mock_create_and_set_timer_idem
        self.backup_remove_service = self.configure_patching_processor.auto_assess_service_manager.remove_service
        self.configure_patching_processor.auto_assess_service_manager.remove_service = self.mock_remove_service
        self.backup_remove_timer = self.configure_patching_processor.auto_assess_timer_manager.remove_timer
        self.configure_patching_processor.auto_assess_timer_manager.remove_timer = self.mock_remove_timer

    def stop(self):
        self.file_logger.close(message_at_close="<Runtime stopped>")
        self.container.reset()

    @staticmethod
    def write_ext_state_file(path, sequence_number, achieve_enable_by, operation):
        data = {
            "extensionSequence": {
                "number": sequence_number,
                "achieveEnableBy": achieve_enable_by,
                "operation": operation
            }
        }
        with open(path, "w+") as file_handle:
            file_handle.write(json.dumps(data))

    def set_legacy_test_type(self, test_type):
        self.legacy_env_layer_extensions.legacy_test_type = test_type

    def reconfigure_env_layer_to_legacy_mode(self):
        self.env_layer.get_package_manager = self.legacy_env_layer_extensions.get_package_manager
        self.env_layer.platform = self.legacy_env_layer_extensions.LegacyPlatform()
        self.env_layer.set_legacy_test_mode()
        self.env_layer.run_command_output = self.legacy_env_layer_extensions.run_command_output
        if os.name == 'nt':
            self.env_layer.etc_environment_file_path = os.getcwd()

    def reconfigure_reboot_manager(self):
        # Preserve the original reboot manager start_reboot method
        self.original_rm_start_reboot = self.reboot_manager.start_reboot

        # Reassign start_reboot to a new mock method
        self.reboot_manager.start_reboot = self.start_reboot

    def start_reboot(self, message="Test initiated reboot mock"):
        self.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)

    def use_original_rm_start_reboot(self):
        self.reboot_manager.start_reboot = self.original_rm_start_reboot

    def reconfigure_package_manager(self):
        self.backup_get_current_auto_os_patch_state = self.package_manager.get_current_auto_os_patch_state
        self.package_manager.get_current_auto_os_patch_state = self.get_current_auto_os_patch_state

    def mock_sleep(self, seconds):
        pass

    def check_sudo_status(self, raise_if_not_sudo=True):
        return True

    def mock_failed_run_command_output(self, command, no_output=False, chk_err=True):
        """Mock a failed sudo check status command output to test retry logic."""
        # Mock failure to trigger retry logic in check_sudo_status
        return (1, "[sudo] password for user:\nFalse")

    def mock_retry_run_command_output(self, command, no_output=False, chk_err=True):
        """Mock 2 failed sudo check status attempts followed by a success on the 3rd attempt."""
        self.sudo_check_status_attempts += 1

        # Mock failure on the first two attempts
        if self.sudo_check_status_attempts <= 2:
            return (1, "[sudo] password for user:\nFalse")

        # Mock success (True) on the 3rd attempt
        elif self.sudo_check_status_attempts == 3:
            return (0, "uid=0(root) gid=0(root) groups=0(root)\nTrue")

    def get_current_auto_os_patch_state(self):
        return Constants.AutomaticOSPatchStates.DISABLED

    def mock_urlopen(self, url, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, cafile=None, capath=None, cadefault=False, context=None):
        if self.vm_cloud_type == Constants.VMCloudType.AZURE:
            resp = urlreq.addinfourl(StringIO("mock file"), "mock message", "mockurl")
            resp.code = 200
            resp.msg = "OK"
            return resp
        else:
            raise Exception

    def mock_create_and_set_service_idem(self):
        pass

    def mock_create_and_set_timer_idem(self):
        pass

    def mock_remove_service(self):
        pass

    def mock_remove_timer(self):
        pass

    @staticmethod
    def write_to_file(path, data):
        with open(path, "w+") as file_handle:
            file_handle.write(data)
