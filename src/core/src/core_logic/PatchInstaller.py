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

""" The patch install orchestrator """
import datetime
import math
import sys
import time

from core.src.bootstrap.Constants import Constants
from core.src.core_logic.Stopwatch import Stopwatch

class PatchInstaller(object):
    """" Wrapper class for a single patch installation operation """
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, lifecycle_manager, package_manager, package_filter, maintenance_window, reboot_manager):
        self.env_layer = env_layer
        self.execution_config = execution_config

        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.status_handler = status_handler
        self.lifecycle_manager = lifecycle_manager

        self.package_manager = package_manager
        self.package_manager_name = self.package_manager.get_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY)
        self.package_filter = package_filter
        self.maintenance_window = maintenance_window
        self.reboot_manager = reboot_manager

        self.last_still_needed_packages = None  # Used for 'Installed' status records
        self.last_still_needed_package_versions = None
        self.progress_template = "[Time available: {0} | A: {1}, S: {2}, F: {3} | D: {4}]\t {5}"

        self.attempted_parent_package_install_count = 0
        self.successful_parent_package_install_count = 0
        self.failed_parent_package_install_count = 0
        self.skipped_esm_packages = []
        self.skipped_esm_package_versions = []
        self.esm_packages_found_without_attach = False  # Flag used to record if esm packages excluded as ubuntu vm not attached.

        self.stopwatch = Stopwatch(self.env_layer, self.telemetry_writer, self.composite_logger)

        self.__enable_installation_warning_status = False

    def start_installation(self, simulate=False):
        """ Kick off a patch installation run """
        self.status_handler.set_current_operation(Constants.INSTALLATION)
        self.raise_if_telemetry_unsupported()
        self.raise_if_min_python_version_not_met()

        self.composite_logger.log('\nStarting patch installation...')

        self.stopwatch.start()

        self.composite_logger.log("\nMachine Id: " + self.env_layer.platform.node())
        self.composite_logger.log("Activity Id: " + self.execution_config.activity_id)
        self.composite_logger.log("Operation request time: " + self.execution_config.start_time + ",               Maintenance Window Duration: " + self.execution_config.duration)

        maintenance_window = self.maintenance_window
        package_manager = self.package_manager
        reboot_manager = self.reboot_manager

        # Early reboot if reboot is allowed by settings and required by the machine
        reboot_pending = self.package_manager.is_reboot_pending()
        self.status_handler.set_reboot_pending(reboot_pending)
        if reboot_pending:
            if reboot_manager.is_setting(Constants.REBOOT_NEVER):
                self.composite_logger.log_warning("/!\\ There was a pending reboot on the machine before any package installations started.\n" +
                                                  "    Consider re-running the patch installation after a reboot if any packages fail to install due to this.")
            else:
                self.composite_logger.log_debug("Attempting to reboot the machine prior to patch installation as there is a reboot pending...")
                reboot_manager.start_reboot_if_required_and_time_available(maintenance_window.get_remaining_time_in_minutes(None, False))

        if self.execution_config.max_patch_publish_date != str():
            self.package_manager.set_max_patch_publish_date(self.execution_config.max_patch_publish_date)

        if self.package_manager.max_patch_publish_date != str():
            """ Strict SDP with the package manager that supports it """
            installed_update_count, update_run_successful, maintenance_window_exceeded = self.install_updates_azgps_coordinated(maintenance_window, package_manager, simulate)
            package_manager.set_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, bool(not update_run_successful))
            if update_run_successful:
                self.composite_logger.log_debug(Constants.INFO_STRICT_SDP_SUCCESS.format(self.execution_config.max_patch_publish_date))
                self.status_handler.add_error_to_status(Constants.INFO_STRICT_SDP_SUCCESS.format(self.execution_config.max_patch_publish_date), error_code=Constants.PatchOperationErrorCodes.INFORMATIONAL)
        else:
            """ Regular patch installation flow - non-AzGPS-coordinated and (AzGPS-coordinated without strict SDP)"""
            installed_update_count, update_run_successful, maintenance_window_exceeded = self.install_updates(maintenance_window, package_manager, simulate)

        retry_count = 1
        # Repeat patch installation if flagged as required and time is available
        if not maintenance_window_exceeded and package_manager.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, False):
            self.composite_logger.log("\nInstalled update count (first round): " + str(installed_update_count))
            self.composite_logger.log("\nPatch installation run will be repeated as the package manager recommended it --------------------------------------------->")
            package_manager.set_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, False)  # Resetting
            new_installed_update_count, update_run_successful, maintenance_window_exceeded = self.install_updates(maintenance_window, package_manager, simulate)
            installed_update_count += new_installed_update_count
            retry_count = retry_count + 1

            if package_manager.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, False):  # We should not see this again
                error_msg = "Unexpected repeated package manager update occurred. Please re-run the update deployment."
                self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.PACKAGE_MANAGER_FAILURE)
                self.write_installer_perf_logs(update_run_successful, installed_update_count, retry_count, maintenance_window, maintenance_window_exceeded, Constants.TaskStatus.FAILED, error_msg)
                raise Exception(error_msg, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))

        self.composite_logger.log("\nInstalled update count: " + str(installed_update_count) + " (including dependencies)")

        self.write_installer_perf_logs(update_run_successful, installed_update_count, retry_count, maintenance_window, maintenance_window_exceeded, Constants.TaskStatus.SUCCEEDED, "")

        # Reboot as per setting and environment state
        reboot_manager.start_reboot_if_required_and_time_available(maintenance_window.get_remaining_time_in_minutes(None, False))
        maintenance_window_exceeded = maintenance_window_exceeded or reboot_manager.maintenance_window_exceeded_flag

        # Combining maintenance
        overall_patch_installation_successful = bool(update_run_successful and not maintenance_window_exceeded)
        # NOTE: Not updating installation substatus at this point because we need to wait for the implicit/second assessment to complete first, as per CRP's instructions

        return overall_patch_installation_successful

    def write_installer_perf_logs(self, patch_operation_successful, installed_patch_count, retry_count, maintenance_window, maintenance_window_exceeded, task_status, error_msg):
        perc_maintenance_window_used = -1

        try:
            perc_maintenance_window_used = maintenance_window.get_percentage_maintenance_window_used()
        except Exception as error:
            self.composite_logger.log_debug("Error in writing patch installation performance logs. Error is: " + repr(error))

        patch_installation_perf_log = "[{0}={1}][{2}={3}][{4}={5}][{6}={7}][{8}={9}][{10}={11}][{12}={13}][{14}={15}][{16}={17}][{18}={19}][{20}={21}]".format(
                                       Constants.PerfLogTrackerParams.TASK, Constants.INSTALLATION, Constants.PerfLogTrackerParams.TASK_STATUS, str(task_status), Constants.PerfLogTrackerParams.ERROR_MSG, error_msg,
                                       Constants.PerfLogTrackerParams.PACKAGE_MANAGER, self.package_manager_name, Constants.PerfLogTrackerParams.PATCH_OPERATION_SUCCESSFUL, str(patch_operation_successful),
                                       Constants.PerfLogTrackerParams.INSTALLED_PATCH_COUNT, str(installed_patch_count), Constants.PerfLogTrackerParams.RETRY_COUNT, str(retry_count),
                                       Constants.PerfLogTrackerParams.MAINTENANCE_WINDOW, str(maintenance_window.duration), Constants.PerfLogTrackerParams.MAINTENANCE_WINDOW_USED_PERCENT, str(perc_maintenance_window_used),
                                       Constants.PerfLogTrackerParams.MAINTENANCE_WINDOW_EXCEEDED, str(maintenance_window_exceeded), Constants.PerfLogTrackerParams.MACHINE_INFO, self.telemetry_writer.machine_info)
        self.stopwatch.stop_and_write_telemetry(patch_installation_perf_log)
        return True

    def raise_if_telemetry_unsupported(self):
        if self.lifecycle_manager.get_vm_cloud_type() == Constants.VMCloudType.ARC and self.execution_config.operation not in [Constants.ASSESSMENT, Constants.INSTALLATION]:
            self.composite_logger.log("Skipping telemetry compatibility check for Arc cloud type when operation is not manual")
            return
        if not self.telemetry_writer.is_telemetry_supported():
            error_msg = "{0}".format(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG)
            self.composite_logger.log_error(error_msg)
            raise Exception(error_msg)

        self.composite_logger.log("{0}".format(Constants.TELEMETRY_COMPATIBLE_MSG))

    def raise_if_min_python_version_not_met(self):
        if sys.version_info < (2, 7):
            error_msg = Constants.PYTHON_NOT_COMPATIBLE_ERROR_MSG.format(sys.version_info)
            self.composite_logger.log_error(error_msg)
            self.status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)
            raise Exception(error_msg)

    def install_updates_azgps_coordinated(self, maintenance_window, package_manager, simulate=False):
        """ Special-casing installation as it meets the following criteria:
            - Maintenance window is always guaranteed to be nearly 4 hours (235 minutes). Customer-facing maintenance windows are much larger (system limitation).
            - Barring reboot, the core Azure customer-base moving to coordinated, unattended upgrades is currently on a 24x7 MW.
            - Built in service-level retries and management of outcomes. Reboot will only happen within the core maintenance window (and won't be delayed).
            - Corner-case transient failures are immaterial to the overall functioning of AzGPS coordinated upgrades (eventual consistency).
            - Only security updates (no other configuration) - simplistic execution flow; no advanced evaluation is desired or necessary.
        """
        installed_update_count = 0  # includes dependencies
        patch_installation_successful = True
        maintenance_window_exceeded = False
        remaining_time = maintenance_window.get_remaining_time_in_minutes()

        try:
            all_packages, all_package_versions = package_manager.get_all_updates(cached=False)
            packages, package_versions = package_manager.get_security_updates()
            self.last_still_needed_packages = list(all_packages)
            self.last_still_needed_package_versions = list(all_package_versions)

            not_included_packages, not_included_package_versions = self.get_not_included_updates(package_manager, packages)
            packages, package_versions, self.skipped_esm_packages, self.skipped_esm_package_versions, self.esm_packages_found_without_attach = package_manager.separate_out_esm_packages(packages, package_versions)

            self.status_handler.set_package_install_status(not_included_packages, not_included_package_versions, Constants.NOT_SELECTED)
            self.status_handler.set_package_install_status(packages, package_versions, Constants.PENDING)
            self.status_handler.set_package_install_status(self.skipped_esm_packages, self.skipped_esm_package_versions, Constants.FAILED)

            self.status_handler.set_package_install_status_classification(packages, package_versions, classification="Security")
            package_manager.set_security_esm_package_status(Constants.INSTALLATION, packages)

            installed_update_count = 0  # includes dependencies
            patch_installation_successful = True
            maintenance_window_exceeded = False

            install_result = Constants.FAILED
            for i in range(0, Constants.MAX_INSTALLATION_RETRY_COUNT):
                code, out = package_manager.install_security_updates_azgps_coordinated()
                installed_update_count += self.perform_status_reconciliation_conditionally(package_manager)

                remaining_time = maintenance_window.get_remaining_time_in_minutes()
                if remaining_time < 120:
                    raise Exception("Not enough safety-buffer to continue strict safe deployment.")

                if code != 0:   # will need to be modified for other package managers
                    if i < Constants.MAX_INSTALLATION_RETRY_COUNT - 1:
                        time.sleep(i * 5)
                        self.composite_logger.log_warning("[PI][AzGPS-Coordinated] Non-zero return. Retrying. [RetryCount={0}][TimeRemainingInMins={1}][Code={2}][Output={3}]".format(str(i), str(remaining_time), str(code), out))
                    else:
                        raise Exception("AzGPS Strict SDP retries exhausted. [RetryCount={0}]".format(str(i)))
                else:
                    patch_installation_successful = True
                    break
        except Exception as error:
            error_msg = "AzGPS strict safe deployment to target date hit a failure. Defaulting to regular upgrades. [MaxPatchPublishDate={0}]".format(self.execution_config.max_patch_publish_date)
            self.composite_logger.log_error(error_msg + "[Error={0}]".format(repr(error)))
            self.status_handler.add_error_to_status(error_msg)
            self.package_manager.set_max_patch_publish_date()   # fall-back
            patch_installation_successful = False

        return installed_update_count, patch_installation_successful, maintenance_window_exceeded

    def install_updates(self, maintenance_window, package_manager, simulate=False):
        """wrapper function of installing updates"""
        self.composite_logger.log("\n\nGetting available updates...")
        package_manager.refresh_repo()

        packages, package_versions = package_manager.get_available_updates(self.package_filter)  # Initial, ignoring exclusions
        self.telemetry_writer.write_event("Initial package list: " + str(packages), Constants.TelemetryEventLevel.Verbose)

        not_included_packages, not_included_package_versions = self.get_not_included_updates(package_manager, packages)
        self.telemetry_writer.write_event("Not Included package list: " + str(not_included_packages), Constants.TelemetryEventLevel.Verbose)

        excluded_packages, excluded_package_versions = self.get_excluded_updates(package_manager, packages, package_versions)
        self.telemetry_writer.write_event("Excluded package list: " + str(excluded_packages), Constants.TelemetryEventLevel.Verbose)

        packages, package_versions = self.filter_out_excluded_updates(packages, package_versions, excluded_packages)  # honoring exclusions

        # For ubuntu VMs, filter out esm_packages, if the VM is not attached.
        # These packages will already be marked with version as 'UA_ESM_REQUIRED'.
        # Esm packages will not be dependent packages to non-esm packages. This is confirmed by Canonical. So, once these are removed from processing, we need not worry about handling it in our batch / sequential patch processing logic.
        # Adding this after filtering excluded packages, so we don`t un-intentionally mark excluded esm-package status as failed.
        packages, package_versions, self.skipped_esm_packages, self.skipped_esm_package_versions, self.esm_packages_found_without_attach = package_manager.separate_out_esm_packages(packages, package_versions)

        self.telemetry_writer.write_event("Final package list: " + str(packages), Constants.TelemetryEventLevel.Verbose)

        # Set initial statuses
        if not package_manager.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, False):  # 'Not included' list is not accurate when a repeat is required
            self.status_handler.set_package_install_status(not_included_packages, not_included_package_versions, Constants.NOT_SELECTED)
        self.status_handler.set_package_install_status(excluded_packages, excluded_package_versions, Constants.EXCLUDED)
        self.status_handler.set_package_install_status(packages, package_versions, Constants.PENDING)
        self.status_handler.set_package_install_status(self.skipped_esm_packages, self.skipped_esm_package_versions, Constants.FAILED)
        self.composite_logger.log("\nList of packages to be updated: \n" + str(packages))

        sec_packages, sec_package_versions = self.package_manager.get_security_updates()
        self.telemetry_writer.write_event("Security packages out of the final package list: " + str(sec_packages), Constants.TelemetryEventLevel.Verbose)
        self.status_handler.set_package_install_status_classification(sec_packages, sec_package_versions, classification="Security")

        # Set the security-esm package status.
        package_manager.set_security_esm_package_status(Constants.INSTALLATION, packages)

        self.composite_logger.log("\nNote: Packages that are neither included nor excluded may still be installed if an included package has a dependency on it.")
        # We will see this as packages going from NotSelected --> Installed. We could remove them preemptively from not_included_packages, but we're explicitly choosing not to.

        self.composite_logger.log("[Progress Legend: (A)ttempted, (S)ucceeded, (F)ailed, (D)ependencies est.* (Important: Dependencies are excluded in all other counts)]")
        installed_update_count = 0  # includes dependencies

        patch_installation_successful = True
        maintenance_window_exceeded = False
        all_packages, all_package_versions = package_manager.get_all_updates(cached=False)
        self.telemetry_writer.write_event("All available packages list: " + str(all_packages), Constants.TelemetryEventLevel.Verbose)
        self.last_still_needed_packages = list(all_packages)
        self.last_still_needed_package_versions = list(all_package_versions)

        packages, package_versions, install_update_count_in_batch_patching, patch_installation_successful = self.batch_patching(all_packages, all_package_versions,
                                                                                                                packages, package_versions, maintenance_window,
                                                                                                                package_manager)

        installed_update_count = install_update_count_in_batch_patching
        attempted_parent_package_install_count_in_batch_patching = self.attempted_parent_package_install_count
        successful_parent_package_install_count_in_batch_patching = self.successful_parent_package_install_count

        if len(packages) == 0:
            if not patch_installation_successful and not maintenance_window_exceeded and self.__check_if_all_packages_installed:
                self.log_final_warning_metric(maintenance_window, installed_update_count)
                self.__enable_installation_warning_status = True
            else:
                self.log_final_metrics(maintenance_window, patch_installation_successful, maintenance_window_exceeded, installed_update_count)

            return installed_update_count, patch_installation_successful, maintenance_window_exceeded
        else:
            progress_status = self.progress_template.format(str(datetime.timedelta(minutes=maintenance_window.get_remaining_time_in_minutes())), str(self.attempted_parent_package_install_count), str(self.successful_parent_package_install_count), str(self.failed_parent_package_install_count), str(installed_update_count - self.successful_parent_package_install_count),
                                                        "Following packages are not attempted or failed in batch installation: " + str(packages))
            self.composite_logger.log(progress_status)

        stopwatch_for_sequential_install_process = Stopwatch(self.env_layer, self.telemetry_writer, self.composite_logger)
        stopwatch_for_sequential_install_process.start()

        for package, version in zip(packages, package_versions):
            if package not in self.last_still_needed_packages:
                self.composite_logger.log("The following package is already installed, it could have been installed as dependent package of some other package: " + package)
                self.attempted_parent_package_install_count += 1
                self.successful_parent_package_install_count += 1
                continue

            single_package_install_stopwatch = Stopwatch(self.env_layer, self.telemetry_writer, self.composite_logger)
            single_package_install_stopwatch.start()
            # Extension state check
            if self.lifecycle_manager is not None:
                self.lifecycle_manager.lifecycle_status_check()     # may terminate the code abruptly, as designed

            # maintenance window check
            remaining_time = maintenance_window.get_remaining_time_in_minutes()
            if maintenance_window.is_package_install_time_available(package_manager, remaining_time, number_of_packages_in_batch=1) is False:
                error_msg = "Stopped patch installation as it is past the maintenance window cutoff time."
                self.composite_logger.log_error("\n" + error_msg)
                self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                maintenance_window_exceeded = True
                self.status_handler.set_maintenance_window_exceeded(True)
                break

            # point in time status
            progress_status = self.progress_template.format(str(datetime.timedelta(minutes=remaining_time)), str(self.attempted_parent_package_install_count), str(self.successful_parent_package_install_count), str(self.failed_parent_package_install_count), str(installed_update_count - self.successful_parent_package_install_count),
                                                            "Processing package: " + str(package) + " (" + str(version) + ")")

            self.composite_logger.log(progress_status)

            # include all dependencies (with specified versions) explicitly
            # package_and_dependencies initially contains only one package. The dependencies are added in the list by method include_dependencies
            package_and_dependencies = [package]
            package_and_dependency_versions = [version]

            self.include_dependencies(package_manager, [package], [version], all_packages, all_package_versions, packages, package_versions, package_and_dependencies, package_and_dependency_versions)

            # parent package install (+ dependencies) and parent package result management
            install_result = package_manager.install_update_and_dependencies_and_get_status(package_and_dependencies, package_and_dependency_versions, simulate)

            # Update reboot pending status in status_handler
            self.status_handler.set_reboot_pending(self.package_manager.is_reboot_pending())

            if install_result == Constants.FAILED:
                self.status_handler.set_package_install_status(package_manager.get_product_name(str(package_and_dependencies[0])), str(package_and_dependency_versions[0]), Constants.FAILED)
                self.failed_parent_package_install_count += 1
                patch_installation_successful = False
            elif install_result == Constants.INSTALLED:
                self.status_handler.set_package_install_status(package_manager.get_product_name(str(package_and_dependencies[0])), str(package_and_dependency_versions[0]), Constants.INSTALLED)
                self.successful_parent_package_install_count += 1
                if package in self.last_still_needed_packages:
                    index = self.last_still_needed_packages.index(package)
                    self.last_still_needed_packages.pop(index)
                    self.last_still_needed_package_versions.pop(index)
                    installed_update_count += 1
            self.attempted_parent_package_install_count += 1

            number_of_dependencies_installed = 0
            number_of_dependencies_failed = 0
            # dependency package result management
            for dependency, dependency_version in zip(package_and_dependencies, package_and_dependency_versions):
                if dependency not in self.last_still_needed_packages or dependency == package:
                    continue

                if package_manager.is_package_version_installed(dependency, dependency_version):
                    self.composite_logger.log_debug(" - Marking dependency as succeeded: " + str(dependency) + "(" + str(dependency_version) + ")")
                    self.status_handler.set_package_install_status(package_manager.get_product_name(str(dependency)), str(dependency_version), Constants.INSTALLED)
                    index = self.last_still_needed_packages.index(dependency)
                    self.last_still_needed_packages.pop(index)
                    self.last_still_needed_package_versions.pop(index)
                    installed_update_count += 1
                    number_of_dependencies_installed += 1
                else:
                    # status is not logged by design here, in case you were wondering if that's a bug
                    message = " - [Info] Dependency appears to have failed to install (note: it *may* be retried): " + str(dependency) + "(" + str(dependency_version) + ")"
                    self.composite_logger.log_debug(message)
                    number_of_dependencies_failed += 1

            # dependency package result management fallback (not reliable enough to be used as primary, and will be removed; remember to retain last_still_needed refresh when you do that)
            installed_update_count += self.perform_status_reconciliation_conditionally(package_manager, condition=(self.attempted_parent_package_install_count % Constants.PACKAGE_STATUS_REFRESH_RATE_IN_SECONDS == 0))  # reconcile status after every 10 attempted installs

            package_install_perf_log = "[{0}={1}][{2}={3}][{4}={5}][{6}={7}][{8}={9}][{10}={11}][{12}={13}][{14}={15}]".format(Constants.PerfLogTrackerParams.TASK, "InstallPackage",
                                       "PackageName", package, "PackageVersion", version, "PackageAndDependencies", str(package_and_dependencies),"PackageAndDependencyVersions", str(package_and_dependency_versions),
                                       "PackageInstallResult", str(install_result), "NumberOfDependenciesInstalled", str(number_of_dependencies_installed), "NumberOfDependenciesFailed", str(number_of_dependencies_failed))

            single_package_install_stopwatch.stop_and_write_telemetry(str(package_install_perf_log))

        self.composite_logger.log_debug("\nPerforming final system state reconciliation...")
        installed_update_count += self.perform_status_reconciliation_conditionally(package_manager, True)

        if not patch_installation_successful and not maintenance_window_exceeded and self.__check_if_all_packages_installed():
            self.log_final_warning_metric(maintenance_window, installed_update_count)
            self.__enable_installation_warning_status = True
        else:
            self.log_final_metrics(maintenance_window, patch_installation_successful, maintenance_window_exceeded, installed_update_count)

        install_update_count_in_sequential_patching = installed_update_count - install_update_count_in_batch_patching
        attempted_parent_package_install_count_in_sequential_patching = self.attempted_parent_package_install_count - attempted_parent_package_install_count_in_batch_patching
        successful_parent_package_install_count_in_sequential_patching = self.successful_parent_package_install_count - successful_parent_package_install_count_in_batch_patching
        failed_parent_package_install_count_after_sequential_patching = self.failed_parent_package_install_count

        sequential_processing_perf_log = "[{0}={1}][{2}={3}][{4}={5}][{6}={7}][{8}={9}]".format(Constants.PerfLogTrackerParams.TASK, "InstallPackagesSequentially", "InstalledPackagesCountInSequentialProcessing",
                                         install_update_count_in_sequential_patching, "AttemptedParentPackageInstallCount", attempted_parent_package_install_count_in_sequential_patching,
                                         "SuccessfulParentPackageInstallCount", successful_parent_package_install_count_in_sequential_patching, "FailedParentPackageInstallCount",
                                         failed_parent_package_install_count_after_sequential_patching)

        stopwatch_for_sequential_install_process.stop_and_write_telemetry(sequential_processing_perf_log)

        return installed_update_count, patch_installation_successful, maintenance_window_exceeded

    def log_final_metrics(self, maintenance_window, patch_installation_successful, maintenance_window_exceeded, installed_update_count):
        """
        logs the final metrics.

        Parameters:
        maintenance_window (MaintenanceWindow): Maintenance window for the job.
        patch_installation_successful (bool): Whether patch installation succeeded.
        maintenance_window_exceeded (bool): Whether maintenance window exceeded.
        installed_update_count (int): Number of updates installed.
        """

        self.__log_progress_status(maintenance_window, installed_update_count)

        if not patch_installation_successful or maintenance_window_exceeded:
            message = "\n\nOperation status was marked as failed because: "
            message += "[X] a failure occurred during the operation  " if not patch_installation_successful else ""
            message += "[X] maintenance window exceeded " if maintenance_window_exceeded else ""
            self.status_handler.add_error_to_status(message, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            self.composite_logger.log_error(message)

    def log_final_warning_metric(self, maintenance_window, installed_update_count):
        """
        logs the final metrics for warning installation status.
        """

        self.__log_progress_status(maintenance_window, installed_update_count)

        message = "\n\nAll supposed package(s) are installed."
        self.status_handler.add_error_to_status(message, Constants.PatchOperationErrorCodes.PACKAGES_RETRY_SUCCEEDED)
        self.composite_logger.log_error(message)

    def include_dependencies(self, package_manager, packages_in_batch, package_versions_in_batch, all_packages, all_package_versions, packages, package_versions, package_and_dependencies, package_and_dependency_versions):
        """
        Add dependent packages in the list of packages to install i.e. package_and_dependencies.

        Parameters:
        package_manager (PackageManager): Package manager used.
        packages_in_batch (List of strings): List of packages to be installed in the current batch.
        all_packages (List of strings): List of all available packages to install.
        all_package_versions (List of strings): Versions of packages in all_packages.
        packages (List of strings): List of all packages selected by user to install.
        package_versions (List of strings): Versions of packages in packages list.
        package_and_dependencies (List of strings): List of packages selected by user along with packages they are dependent on. The input package_and_dependencies
                                                    does not contain dependent packages. The dependent packages are added in the list in this function.
        package_and_dependency_versions (List of strings): Versions of packages in package_and_dependencies. Input list does not contain versions of the dependent packages.
                                                           The version of dependent packages are added in the list in this function.
        """
        dependencies = package_manager.get_dependent_list(package_and_dependencies)

        for dependency in dependencies:
            if dependency not in all_packages:
                continue
            package_and_dependencies.append(dependency)
            version = all_package_versions[all_packages.index(dependency)] if dependency in all_packages else Constants.DEFAULT_UNSPECIFIED_VALUE
            package_and_dependency_versions.append(version)

        for package, version in zip(packages_in_batch, package_versions_in_batch):
            package_manager.add_arch_dependencies(package_manager, package, version, packages, package_versions, package_and_dependencies, package_and_dependency_versions)

        package_and_dependencies, package_and_dependency_versions = package_manager.dedupe_update_packages(package_and_dependencies, package_and_dependency_versions)

        self.composite_logger.log("Packages including dependencies are: " + str(package_and_dependencies))

    def batch_patching(self, all_packages, all_package_versions, packages, package_versions, maintenance_window, package_manager):
        stopwatch_for_batch_install_process = Stopwatch(self.env_layer, self.telemetry_writer, self.composite_logger)
        stopwatch_for_batch_install_process.start()

        total_packages_to_install_count = len(packages)
        maintenance_window_batch_cutoff_reached = False
        max_batch_size_for_packages = self.get_max_batch_size(maintenance_window, package_manager)
        installed_update_count_in_batch_patching = 0
        patch_installation_successful_in_batch_patching = True

        for phase in range(Constants.PackageBatchConfig.MAX_PHASES_FOR_BATCH_PATCHING):
            if len(packages) == 0:
                break

            if max_batch_size_for_packages <= 0:
                maintenance_window_batch_cutoff_reached = True
                break

            stopwatch_for_phase = Stopwatch(self.env_layer, self.telemetry_writer, self.composite_logger)
            stopwatch_for_phase.start()

            installed_update_count, patch_installation_successful, maintenance_window_batch_cutoff_reached, packages, package_versions = self.install_packages_in_batches(
                all_packages, all_package_versions, packages, package_versions, maintenance_window, package_manager, max_batch_size_for_packages)

            installed_update_count_in_batch_patching += installed_update_count

            if patch_installation_successful is False:
                patch_installation_successful_in_batch_patching = False

            stopwatch_for_phase.stop()

            batch_phase_processing_perf_log = "[{0}={1}][{2}={3}][{4}={5}][{6}={7}][{8}={9}][{10}={11}][{12}={13}][{14}={15}]".format(Constants.PerfLogTrackerParams.TASK, "InstallPackagesInBatchInDifferentPhases",
                                         "Phase", str(phase), "InstalledPackagesCount", str(installed_update_count), "SuccessfulParentPackageInstallCount", self.successful_parent_package_install_count, "FailedParentPackageInstallCount",
                                         self.failed_parent_package_install_count, "RemainingPackagesToInstall", str(len(packages)), Constants.PerfLogTrackerParams.PATCH_OPERATION_SUCCESSFUL, str(patch_installation_successful),
                                         "IsMaintenanceWindowBatchCutoffReached", str(maintenance_window_batch_cutoff_reached))

            stopwatch_for_phase.write_telemetry_for_stopwatch(str(batch_phase_processing_perf_log))

            max_batch_size_for_packages = int(max_batch_size_for_packages / Constants.PackageBatchConfig.BATCH_SIZE_DECAY_FACTOR)

            if total_packages_to_install_count < max_batch_size_for_packages:
                # All the packages will be attempted in single batch as max batch size is larger than total packages.
                # All packages are already attempted in single batch as max batch size was higher than total packages in the last phase also.
                # Avoiding same packages in a single batch again as the chances of failures is high.
                break

        stopwatch_for_batch_install_process.stop()

        batch_processing_perf_log = "[{0}={1}][{2}={3}][{4}={5}][{6}={7}][{8}={9}][{10}={11}][{12}={13}][{14}={15}]".format(Constants.PerfLogTrackerParams.TASK, "InstallPackagesInBatches",
                                    "InstalledPackagesCountInBatchProcessing", str(installed_update_count_in_batch_patching), "AttemptedParentPackageInstallCount", self.attempted_parent_package_install_count,
                                    "SuccessfulParentPackageInstallCount", self.successful_parent_package_install_count, "FailedParentPackageInstallCount", self.failed_parent_package_install_count,
                                    "RemainingPackagesToInstall", str(len(packages)), Constants.PerfLogTrackerParams.PATCH_OPERATION_SUCCESSFUL, str(patch_installation_successful_in_batch_patching),
                                    "IsMaintenanceWindowBatchCutoffReached", str(maintenance_window_batch_cutoff_reached))

        stopwatch_for_batch_install_process.write_telemetry_for_stopwatch(str(batch_processing_perf_log))

        return packages, package_versions, installed_update_count_in_batch_patching, patch_installation_successful_in_batch_patching

    def install_packages_in_batches(self, all_packages, all_package_versions, packages, package_versions, maintenance_window, package_manager, max_batch_size_for_packages, simulate=False):
        """
        Install packages in batches.

        Parameters:

        all_packages (List of strings): List of all available packages to install.
        all_package_versions (List of strings): Versions of the packages in the list all_packages.
        packages (List of strings): List of all packages selected by user to install.
        package_versions (List of strings): Versions of packages in the list packages.
        maintenance_window (MaintenanceWindow): Maintenance window for the job.
        package_manager (PackageManager): Package manager used.
        max_batch_size_for_packages (Integer): Maximum batch size.
        simulate (bool): Whether this function is called from a test run.

        Returns:
        installed_update_count (int): Number of packages installed through installing packages in batches.
        patch_installation_successful (bool): Whether package installation succeeded for all attempted packages.
        maintenance_window_batch_cutoff_reached (bool): Whether process of installing packages in batches stopped due to not enough time in maintenance window
                                                        to install packages in batch.
        not_attempted_and_failed_packages (List of strings): List of packages which are (a) Not attempted due to not enough time in maintenance window to install in batch.
                                                             (b) Failed to install in batch patching.
        not_attempted_and_failed_package_versions (List of strings): Versions of packages in the list not_attempted_and_failed_packages.

        """
        number_of_batches = int(math.ceil(len(packages) / float(max_batch_size_for_packages)))
        self.composite_logger.log("\nDividing package install in batches. \nNumber of packages to be installed: " + str(len(packages)) + "\nBatch Size: " + str(max_batch_size_for_packages) + "\nNumber of batches: " + str(number_of_batches))
        installed_update_count = 0
        patch_installation_successful = True
        maintenance_window_batch_cutoff_reached = False

        # remaining_packages are the packages which are not attempted to install due to there is not enough remaining time in maintenance window to install packages in batches.
        # These packages will be attempted in sequential installation if there is enough time in maintenance window to install package sequentially.
        remaining_packages = []
        remaining_package_versions = []

        # failed_packages are the packages which are failed to install in batch patching. These packages will be attempted again in sequential patching if there is
        # enough time remaining in maintenance window.
        failed_packages = []
        failed_package_versions = []

        for batch_index in range(0, number_of_batches):
            per_batch_installation_stopwatch = Stopwatch(self.env_layer, self.telemetry_writer, self.composite_logger)
            per_batch_installation_stopwatch.start()

            # Extension state check
            if self.lifecycle_manager is not None:
                self.lifecycle_manager.lifecycle_status_check()

            begin_index = batch_index * max_batch_size_for_packages
            end_index = begin_index + max_batch_size_for_packages - 1
            end_index = min(end_index, len(packages) - 1)

            packages_in_batch = []
            package_versions_in_batch = []
            already_installed_packages = []

            for index in range(begin_index, end_index + 1):
                if packages[index] not in self.last_still_needed_packages:
                    # Could have got installed as dependent package of some other package. Package installation status could also have been set.
                    already_installed_packages.append(packages[index])
                    self.attempted_parent_package_install_count += 1
                    self.successful_parent_package_install_count += 1
                else:
                    packages_in_batch.append(packages[index])
                    package_versions_in_batch.append(package_versions[index])

            if len(already_installed_packages) > 0:
                self.composite_logger.log("Following packages are already installed. Could have got installed as dependent package of some other package " + str(already_installed_packages))

            if len(packages_in_batch) == 0:
                continue

            remaining_time = maintenance_window.get_remaining_time_in_minutes()

            if maintenance_window.is_package_install_time_available(package_manager, remaining_time, len(packages_in_batch)) is False:
                self.composite_logger.log("Stopped installing packages in batches as it is past the maintenance window cutoff time for installing in batches." +
                                           " Batch Index: {0}, remaining time: {1}, number of packages in batch: {2}".format(batch_index, remaining_time, str(len(packages_in_batch))))
                maintenance_window_batch_cutoff_reached = True
                remaining_packages = packages[begin_index:]
                remaining_package_versions = package_versions[begin_index:]
                break

            # point in time status
            progress_status = self.progress_template.format(str(datetime.timedelta(minutes=remaining_time)), str(self.attempted_parent_package_install_count), str(self.successful_parent_package_install_count), str(self.failed_parent_package_install_count), str(installed_update_count - self.successful_parent_package_install_count),
                                                            "Processing batch index: " + str(batch_index) + ", Number of packages: " + str(len(packages_in_batch)) + "\nProcessing packages: " + str(packages_in_batch))
            self.composite_logger.log(progress_status)

            # package_and_dependencies initially conains only packages in batch. The dependencies are added in the list by method include_dependencies
            package_and_dependencies = list(packages_in_batch)
            package_and_dependency_versions = list(package_versions_in_batch)

            self.include_dependencies(package_manager, packages_in_batch, package_versions_in_batch, all_packages, all_package_versions, packages, package_versions, package_and_dependencies, package_and_dependency_versions)

            parent_packages_installed_in_batch_count = 0
            parent_packages_failed_in_batch_count = 0
            number_of_dependencies_installed = 0
            number_of_dependencies_failed = 0

            code, out, exec_cmd = package_manager.install_update_and_dependencies(package_and_dependencies, package_and_dependency_versions, simulate)

            for package,version in zip(package_and_dependencies, package_and_dependency_versions):
                install_result = package_manager.get_installation_status(code, out, exec_cmd, package, version, simulate)

                if install_result == Constants.FAILED:
                    if package in packages_in_batch:
                        # parent package
                        self.status_handler.set_package_install_status(package_manager.get_product_name(str(package)), str(version), Constants.FAILED)
                        self.failed_parent_package_install_count += 1
                        patch_installation_successful = False
                        parent_packages_failed_in_batch_count += 1
                        failed_packages.append(package)
                        failed_package_versions.append(version)
                    else:
                        # dependent package
                        number_of_dependencies_failed +=1
                elif install_result == Constants.INSTALLED:
                    self.status_handler.set_package_install_status(package_manager.get_product_name(str(package)), str(version), Constants.INSTALLED)
                    if package in packages_in_batch:
                        # parent package
                        self.successful_parent_package_install_count += 1
                        parent_packages_installed_in_batch_count += 1
                    else:
                        # dependent package
                        number_of_dependencies_installed += 1

                    if package in self.last_still_needed_packages:
                        index = self.last_still_needed_packages.index(package)
                        self.last_still_needed_packages.pop(index)
                        self.last_still_needed_package_versions.pop(index)
                        installed_update_count += 1

            self.attempted_parent_package_install_count += len(packages_in_batch)

            # Update reboot pending status in status_handler
            self.status_handler.set_reboot_pending(self.package_manager.is_reboot_pending())

            # dependency package result management fallback (not reliable enough to be used as primary, and will be removed; remember to retain last_still_needed refresh when you do that)
            installed_update_count += self.perform_status_reconciliation_conditionally(package_manager, condition=(self.attempted_parent_package_install_count % Constants.PACKAGE_STATUS_REFRESH_RATE_IN_SECONDS == 0))  # reconcile status after every 10 attempted installs

            per_batch_install_perf_log = "[{0}={1}][{2}={3}][{4}={5}][{6}={7}][{8}={9}][{10}={11}][{12}={13}][{14}={15}]".format(Constants.PerfLogTrackerParams.TASK, "InstallBatchOfPackages",
                                         "PackagesInBatch", str(packages_in_batch), "PackageAndDependencies", str(package_and_dependencies), "PackageAndDependencyVersions", str(package_and_dependency_versions),
                                         "NumberOfParentPackagesInstalled", str(parent_packages_installed_in_batch_count), "NumberOfParentPackagesFailed", str(parent_packages_failed_in_batch_count),
                                         "NumberOfDependenciesInstalled", str(number_of_dependencies_installed), "NumberOfDependenciesFailed", str(number_of_dependencies_failed))

            per_batch_installation_stopwatch.stop_and_write_telemetry(str(per_batch_install_perf_log))

        # Performing reconciliation at the end to get accurate number of installed packages through this function.
        installed_update_count += self.perform_status_reconciliation_conditionally(package_manager, True)

        # not_attempted_and_failed_packages is the list of packages including two kind of packages:
        # (a) Not attempted due to not enough time in maintenance window to install packages in batches.
        # (b) Failed to install in batch patching.
        # These packages are attempted in the sequential patching if there is enough time remaining in maintenance window. The non attempted packages are in
        # the front of the list than failed packages and hence non attempated packages are attempted first in sequential patching than the failed packages.
        not_attempted_and_failed_packages = remaining_packages + failed_packages
        not_attempted_and_failed_package_versions = remaining_package_versions + failed_package_versions
        return installed_update_count, patch_installation_successful, maintenance_window_batch_cutoff_reached, not_attempted_and_failed_packages, not_attempted_and_failed_package_versions

    def mark_installation_completed(self):
        """ Marks Installation operation as completed by updating the status of PatchInstallationSummary as success and patch metadata to be sent to healthstore.
        This is set outside of start_installation function to a restriction in CRP, where installation substatus should be marked as completed only after the implicit (2nd) assessment operation """
        self.status_handler.set_current_operation(Constants.INSTALLATION)  # Required for status handler to log errors, that occur during marking installation completed, in installation substatus

        # RebootNever is selected and pending, set status warning else success
        if self.reboot_manager.reboot_setting == Constants.REBOOT_NEVER and self.reboot_manager.is_reboot_pending():
            # Set error details inline with windows extension when setting warning status. This message will be shown in portal.
            self.status_handler.add_error_to_status("Machine is Required to reboot. However, the customer-specified reboot setting doesn't allow reboots.", Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
            self.status_handler.set_installation_substatus_json(status=Constants.STATUS_WARNING)
        else:
            self.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # If esm packages are found, set the status as warning. This will show up in portal along with the error message we already set.
        if self.esm_packages_found_without_attach:
            self.status_handler.set_installation_substatus_json(status=Constants.STATUS_WARNING)

        # Update patch metadata in status for auto patching request, to be reported to healthStore
        self.__sent_metadata_health_store()

    def mark_installation_warning_completed(self):
        """ Marks Installation operation as warning by updating the status of PatchInstallationSummary as warning and patch metadata to be sent to healthstore.
        This is set outside of start_installation function to a restriction in CRP, where installation substatus should be marked as warning only after the implicit (2nd) assessment operation
        and all supposed packages are installed as expected
        """
        self.status_handler.set_installation_substatus_json(status=Constants.STATUS_WARNING)

        # Update patch metadata in status for auto patching request, to be reported to healthStore
        self.__sent_metadata_health_store()

    # region Installation Progress support
    def perform_status_reconciliation_conditionally(self, package_manager, condition=True):
        """Periodically based on the condition check, writes out success records as required; returns count of detected installs.
           This is mostly to capture the dependencies that get silently installed recorded.
           VERY IMPORTANT NOTE: THIS ONLY WORKS IF EACH DEPENDENCY INSTALLED WAS THE VERY LATEST VERSION AVAILABLE.
           So it's only here as a fallback method and shouldn't normally be required with newer code - it will be removed in the future."""
        if not condition:
            return 0

        self.composite_logger.log_verbose("\nStarting status reconciliation...")
        start_time = time.time()
        still_needed_packages, still_needed_package_versions = package_manager.get_all_updates(cached=False)  # do not use cache
        successful_packages = []
        successful_package_versions = []
        for i in range(0, len(self.last_still_needed_packages)):
            if self.last_still_needed_packages[i] not in still_needed_packages:
                successful_packages.append(self.last_still_needed_packages[i])
                successful_package_versions.append(self.last_still_needed_package_versions[i])

        self.status_handler.set_package_install_status(successful_packages, successful_package_versions, Constants.INSTALLED)
        self.last_still_needed_packages = still_needed_packages
        self.last_still_needed_package_versions = still_needed_package_versions
        self.composite_logger.log_verbose("Completed status reconciliation. Time taken: " + str(time.time() - start_time) + " seconds.")
        return len(successful_packages)
    # endregion

    # region Package List Manipulation @ Update Run level
    def get_not_included_updates(self, package_manager, included_packages):
        """Returns the list of updates not included given any list of packages that will be included"""
        self.composite_logger.log_debug("\nEvaluating for 'not included' packages...")
        all_packages, all_package_versions = package_manager.get_all_updates(cached=True)  # cached is fine
        not_included_packages = []
        not_included_package_versions = []
        for i in range(0, len(all_packages)):
            if all_packages[i] not in included_packages:
                not_included_packages.append(all_packages[i])
                not_included_package_versions.append(all_package_versions[i])

        self.composite_logger.log_debug(str(len(not_included_packages)) + " out of " + str(len(all_packages)) + " packages will be 'not included'.")
        return not_included_packages, not_included_package_versions

    def get_excluded_updates(self, package_manager, packages, package_versions):
        """"Returns the list of updates explicitly excluded by entries in the exclusion list"""
        self.composite_logger.log_debug("\nEvaluating for 'excluded' packages...")
        excluded_packages = []
        excluded_package_versions = []

        if not self.package_filter.is_exclusion_list_present():
            return excluded_packages, excluded_package_versions

        for package, package_version in zip(packages, package_versions):
            if self.package_filter.check_for_exclusion(package):
                excluded_packages.append(package)  # package is excluded, no need to check for dependency exclusion
                excluded_package_versions.append(package_version)
                continue

            dependency_list = package_manager.get_dependent_list([package])
            if dependency_list and self.package_filter.check_for_exclusion(dependency_list):
                self.composite_logger.log_debug(" - Exclusion list match on dependency list for package '{0}': {1}".format(str(package), str(dependency_list)))
                excluded_packages.append(package)  # one of the package's dependencies are excluded, so exclude the package
                excluded_package_versions.append(package_version)

        self.composite_logger.log_debug(str(len(excluded_packages)) + " 'excluded' packages were found.")
        return excluded_packages, excluded_package_versions

    def filter_out_excluded_updates(self, included_packages, included_package_versions, excluded_packages):
        """Returns list of included packages with all the excluded packages removed"""
        self.composite_logger.log_debug("\nFiltering out 'excluded' packages from included packages...")
        new_included_packages = []
        new_included_package_versions = []

        for package, version in zip(included_packages, included_package_versions):
            if package not in excluded_packages:
                new_included_packages.append(package)
                new_included_package_versions.append(version)
            else:
                self.composite_logger.log_debug(" - Package '" + str(package) + "' is being filtered out.")

        self.composite_logger.log_debug(str(len(new_included_packages)) + " out of " + str(len(included_packages)) + " packages will remain included in the run.")
        return new_included_packages, new_included_package_versions
    # endregion

    def get_max_batch_size(self, maintenance_window, package_manager):
        """Returns maximum batch size for batch patching as per the time remaining in the maintenance window and time taken to install package by package manager"""
        available_time_to_install_packages = maintenance_window.get_remaining_time_in_minutes()

        if Constants.REBOOT_SETTINGS[self.execution_config.reboot_setting] != Constants.REBOOT_NEVER:
            available_time_to_install_packages = available_time_to_install_packages - Constants.REBOOT_BUFFER_IN_MINUTES

        available_time_to_install_packages = available_time_to_install_packages - Constants.PackageBatchConfig.BUFFER_TIME_FOR_BATCH_PATCHING_START_IN_MINUTES

        self.composite_logger.log_debug("Avaliable time in minutes to install packages (after removing buffer time): {0}".format(available_time_to_install_packages))

        max_batch_size_for_packages = 0

        # Taking assumption that 1 of the packages in the batch takes maximum expected time to install and remaining packages take average time to install.
        if available_time_to_install_packages > Constants.PACKAGE_INSTALL_EXPECTED_MAX_TIME_IN_MINUTES:
            available_time_to_install_packages = available_time_to_install_packages - Constants.PACKAGE_INSTALL_EXPECTED_MAX_TIME_IN_MINUTES
            max_batch_size_for_packages += 1

            # Remaining packages take average expected time to install.
            package_install_expected_avg_time_in_minutes = package_manager.get_package_install_expected_avg_time_in_seconds() / 60.0
            max_batch_size_for_packages += int(math.floor(available_time_to_install_packages / package_install_expected_avg_time_in_minutes))

        if max_batch_size_for_packages > Constants.PackageBatchConfig.MAX_BATCH_SIZE_FOR_PACKAGES:
            max_batch_size_for_packages = Constants.PackageBatchConfig.MAX_BATCH_SIZE_FOR_PACKAGES

        self.composite_logger.log_debug("Calculated max batch size is: {0}".format(max_batch_size_for_packages))

        return max_batch_size_for_packages

    def __log_progress_status(self, maintenance_window, installed_update_count):
        progress_status = self.progress_template.format(str(datetime.timedelta(minutes=maintenance_window.get_remaining_time_in_minutes())), str(self.attempted_parent_package_install_count), str(self.successful_parent_package_install_count), str(self.failed_parent_package_install_count), str(installed_update_count - self.successful_parent_package_install_count),
                                                        "Completed processing packages!")
        self.composite_logger.log(progress_status)

    # region - Failed packages retry succeeded
    def __check_if_all_packages_installed(self):
        #type (none) -> bool
        """ Check if all supposed security and critical packages are installed """
        # Get the list of installed packages
        installed_packages_list = self.status_handler.get_installation_packages_list()
        print('what is installed_packages_list', installed_packages_list)
        # Get security and critical packages
        security_critical_packages = []
        for package in installed_packages_list:
            if 'classifications' in package and any(classification in ['Security', 'Critical'] for classification in package['classifications']):
                security_critical_packages.append(package)

        # Return false there's no security/critical packages
        if len(security_critical_packages) == 0:
            return False

        # Check if any security/critical package are not installed
        for package in security_critical_packages:
            if package['patchInstallationState'] != Constants.INSTALLED:
                return False

        # All security/critical packages are installed
        return True

    def __sent_metadata_health_store(self):
        self.composite_logger.log_debug("[PI] Reviewing final healthstore record write. [HealthStoreId={0}][MaintenanceRunId={1}]".format(str(self.execution_config.health_store_id), str(self.execution_config.maintenance_run_id)))
        if self.execution_config.health_store_id is not None:
            self.status_handler.set_patch_metadata_for_healthstore_substatus_json(
                patch_version=self.execution_config.health_store_id,
                report_to_healthstore=True,
                wait_after_update=False)

    def get_enabled_installation_warning_status(self):
        """Access enable_installation_warning_status value"""
        return self.__enable_installation_warning_status
    # endregion
