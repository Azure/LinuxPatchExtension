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
import os
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
        self.stopwatch = Stopwatch(self.env_layer, self.telemetry_writer, self.composite_logger)

    def start_installation(self, simulate=False):
        """ Kick off a patch installation run """
        self.status_handler.set_current_operation(Constants.INSTALLATION)
        self.raise_if_telemetry_unsupported()

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

        # Install Updates
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
                                       Constants.PerfLogTrackerParams.MAINTENANCE_WINDOW, str(maintenance_window.duration), Constants.PerfLogTrackerParams.PERC_MAINTENANCE_WINDOW_USED, str(perc_maintenance_window_used),
                                       Constants.PerfLogTrackerParams.MAINTENANCE_WINDOW_EXCEEDED, str(maintenance_window_exceeded), Constants.PerfLogTrackerParams.MACHINE_INFO, self.telemetry_writer.machine_info)
        self.stopwatch.stop_and_write_telemetry(patch_installation_perf_log)

    def raise_if_telemetry_unsupported(self):
        if self.lifecycle_manager.get_vm_cloud_type() == Constants.VMCloudType.ARC and self.execution_config.operation not in [Constants.ASSESSMENT, Constants.INSTALLATION]:
            self.composite_logger.log("Skipping telemetry compatibility check for Arc cloud type when operation is not manual")
            return
        if not self.telemetry_writer.is_telemetry_supported():
            error_msg = "{0}".format(Constants.TELEMETRY_NOT_COMPATIBLE_ERROR_MSG)
            self.composite_logger.log_error(error_msg)
            raise Exception(error_msg)

        self.composite_logger.log("{0}".format(Constants.TELEMETRY_COMPATIBLE_MSG))

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

        packages, package_versions = self.filter_out_excluded_updates(packages, package_versions, excluded_packages)  # Final, honoring exclusions
        self.telemetry_writer.write_event("Final package list: " + str(packages), Constants.TelemetryEventLevel.Verbose)

        # Set initial statuses
        if not package_manager.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, False):  # 'Not included' list is not accurate when a repeat is required
            self.status_handler.set_package_install_status(not_included_packages, not_included_package_versions, Constants.NOT_SELECTED)
        self.status_handler.set_package_install_status(excluded_packages, excluded_package_versions, Constants.EXCLUDED)
        self.status_handler.set_package_install_status(packages, package_versions, Constants.PENDING)
        self.composite_logger.log("\nList of packages to be updated: \n" + str(packages))

        sec_packages, sec_package_versions = self.package_manager.get_security_updates()
        self.telemetry_writer.write_event("Security packages out of the final package list: " + str(sec_packages), Constants.TelemetryEventLevel.Verbose)
        self.status_handler.set_package_install_status_classification(sec_packages, sec_package_versions, classification="Security")

        self.composite_logger.log("\nNote: Packages that are neither included nor excluded may still be installed if an included package has a dependency on it.")
        # We will see this as packages going from NotSelected --> Installed. We could remove them preemptively from not_included_packages, but we're explicitly choosing not to.

        self.composite_logger.log("\n\nInstalling patches in sequence...")
        self.composite_logger.log("[Progress Legend: (A)ttempted, (S)ucceeded, (F)ailed, (D)ependencies est.* (Important: Dependencies are excluded in all other counts)]")
        attempted_parent_update_count = 0
        successful_parent_update_count = 0
        failed_parent_update_count = 0
        installed_update_count = 0  # includes dependencies

        patch_installation_successful = True
        maintenance_window_exceeded = False
        all_packages, all_package_versions = package_manager.get_all_updates(True)  # cached is fine
        self.telemetry_writer.write_event("All available packages list: " + str(all_packages), Constants.TelemetryEventLevel.Verbose)
        self.last_still_needed_packages = all_packages
        self.last_still_needed_package_versions = all_package_versions

        for package, version in zip(packages, package_versions):
            # Extension state check
            if self.lifecycle_manager is not None:
                self.lifecycle_manager.lifecycle_status_check()     # may terminate the code abruptly, as designed

            # maintenance window check
            remaining_time = maintenance_window.get_remaining_time_in_minutes()
            if maintenance_window.is_package_install_time_available(remaining_time) is False:
                error_msg = "Stopped patch installation as it is past the maintenance window cutoff time."
                self.composite_logger.log_error("\n" + error_msg)
                self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                maintenance_window_exceeded = True
                self.status_handler.set_maintenance_window_exceeded(True)
                break

            # point in time status
            progress_status = self.progress_template.format(str(datetime.timedelta(minutes=remaining_time)), str(attempted_parent_update_count), str(successful_parent_update_count), str(failed_parent_update_count), str(installed_update_count - successful_parent_update_count),
                                                            "Processing package: " + str(package) + " (" + str(version) + ")")
            if version == Constants.UA_ESM_REQUIRED:
                progress_status += "[Skipping - requires Ubuntu Advantage for Infrastructure with Extended Security Maintenance]"
                self.composite_logger.log(progress_status)
                self.status_handler.set_package_install_status(package_manager.get_product_name(package), str(version), Constants.NOT_SELECTED)     # may be changed to Failed in the future
                continue
            self.composite_logger.log(progress_status)

            # include all dependencies (with specified versions) explicitly
            package_and_dependencies = [package]
            package_and_dependency_versions = [version]
            dependencies = package_manager.get_dependent_list(package)
            for dependency in dependencies:
                if dependency not in all_packages:
                    continue
                package_and_dependencies.append(dependency)
                package_and_dependency_versions.append(package_versions[packages.index(dependency)] if dependency in packages else Constants.DEFAULT_UNSPECIFIED_VALUE)

            # multilib resolution for yum
            if package_manager.get_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY) == Constants.YUM:
                package_name_without_arch = package_manager.get_product_name_without_arch(package)
                for possible_arch_dependency, possible_arch_dependency_version in zip(packages, package_versions):
                    if package_manager.get_product_name_without_arch(possible_arch_dependency) == package_name_without_arch and possible_arch_dependency not in package_and_dependencies:
                        package_and_dependencies.append(possible_arch_dependency)
                        package_and_dependency_versions.append(possible_arch_dependency_version)

            # remove duplicates
            package_and_dependencies, package_and_dependency_versions = package_manager.dedupe_update_packages(package_and_dependencies, package_and_dependency_versions)

            # parent package install (+ dependencies) and parent package result management
            install_result = Constants.FAILED
            for i in range(0, Constants.MAX_INSTALLATION_RETRY_COUNT):
                install_result = package_manager.install_update_and_dependencies(package_and_dependencies, package_and_dependency_versions, simulate)
                if install_result != Constants.INSTALLED:
                    if i < Constants.MAX_INSTALLATION_RETRY_COUNT - 1:
                        time.sleep(i + 1)
                        self.composite_logger.log_warning("Retrying installation of package. [Package={0}]".format(package_manager.get_product_name(package_and_dependencies[0])))

            # Update reboot pending status in status_handler
            self.status_handler.set_reboot_pending(self.package_manager.is_reboot_pending())

            if install_result == Constants.FAILED:
                self.status_handler.set_package_install_status(package_manager.get_product_name(str(package_and_dependencies[0])), str(package_and_dependency_versions[0]), Constants.FAILED)
                failed_parent_update_count += 1
                patch_installation_successful = False
            elif install_result == Constants.INSTALLED:
                self.status_handler.set_package_install_status(package_manager.get_product_name(str(package_and_dependencies[0])), str(package_and_dependency_versions[0]), Constants.INSTALLED)
                successful_parent_update_count += 1
                if package in self.last_still_needed_packages:
                    index = self.last_still_needed_packages.index(package)
                    self.last_still_needed_packages.pop(index)
                    self.last_still_needed_package_versions.pop(index)
                    installed_update_count += 1
            attempted_parent_update_count += 1

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
                else:
                    # status is not logged by design here, in case you were wondering if that's a bug
                    message = " - [Info] Dependency appears to have failed to install (note: it *may* be retried): " + str(dependency) + "(" + str(dependency_version) + ")"
                    self.composite_logger.log_debug(message)

            # dependency package result management fallback (not reliable enough to be used as primary, and will be removed; remember to retain last_still_needed refresh when you do that)
            installed_update_count += self.perform_status_reconciliation_conditionally(package_manager, condition=(attempted_parent_update_count % Constants.PACKAGE_STATUS_REFRESH_RATE_IN_SECONDS == 0))  # reconcile status after every 10 attempted installs

        progress_status = self.progress_template.format(str(datetime.timedelta(minutes=maintenance_window.get_remaining_time_in_minutes())), str(attempted_parent_update_count), str(successful_parent_update_count), str(failed_parent_update_count), str(installed_update_count - successful_parent_update_count),
                                                        "Completed processing packages!")
        self.composite_logger.log(progress_status)

        self.composite_logger.log_debug("\nPerforming final system state reconciliation...")
        installed_update_count += self.perform_status_reconciliation_conditionally(package_manager, True)  # final reconciliation

        if not patch_installation_successful or maintenance_window_exceeded:
            message = "\n\nOperation status was marked as failed because: "
            message += "[X] a failure occurred during the operation  " if not patch_installation_successful else ""
            message += "[X] maintenance window exceeded " if maintenance_window_exceeded else ""
            self.status_handler.add_error_to_status(message, Constants.PatchOperationErrorCodes.OPERATION_FAILED)
            self.composite_logger.log_error(message)

        return installed_update_count, patch_installation_successful, maintenance_window_exceeded

    def mark_installation_completed(self):
        """ Marks Installation operation as completed by updating the status of PatchInstallationSummary as success and patch metadata to be sent to healthstore.
        This is set outside of start_installation function to a restriction in CRP, where installation substatus should be marked as completed only after the implicit (2nd) assessment operation """
        self.status_handler.set_current_operation(Constants.INSTALLATION)  # Required for status handler to log errors, that occur during marking installation completed, in installation substatus
        self.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)

        # Update patch metadata in status for auto patching request, to be reported to healthStore
        # When available, HealthStoreId always takes precedence over the 'overriden' Maintenance Run Id that is being re-purposed for other reasons
        # In the future, maintenance run id will be completely deprecated for health store reporting.
        patch_version_raw = self.execution_config.health_store_id if self.execution_config.health_store_id is not None else self.execution_config.maintenance_run_id
        self.composite_logger.log_debug("Patch version raw value set. [Raw={0}][HealthStoreId={1}][MaintenanceRunId={2}]".format(str(patch_version_raw), str(self.execution_config.health_store_id), str(self.execution_config.maintenance_run_id)))

        if patch_version_raw is not None:
            try:
                patch_version = datetime.datetime.strptime(patch_version_raw.split(" ")[0], "%m/%d/%Y").strftime('%Y.%m.%d')
            except ValueError as e:
                patch_version = str(patch_version_raw) # CRP is supposed to guarantee that healthStoreId is always in the correct format; (Legacy) Maintenance Run Id may not be; what happens prior to this is just defensive coding
                self.composite_logger.log_debug("Patch version _may_ be in an incorrect format. [CommonFormat=DateTimeUTC][Actual={0}][Error={1}]".format(str(self.execution_config.maintenance_run_id), repr(e)))

            self.status_handler.set_patch_metadata_for_healthstore_substatus_json(
                patch_version=patch_version if patch_version is not None and patch_version != "" else Constants.PATCH_VERSION_UNKNOWN,
                report_to_healthstore=True,
                wait_after_update=False)

    # region Installation Progress support
    def perform_status_reconciliation_conditionally(self, package_manager, condition=True):
        """Periodically based on the condition check, writes out success records as required; returns count of detected installs.
           This is mostly to capture the dependencies that get silently installed recorded.
           VERY IMPORTANT NOTE: THIS ONLY WORKS IF EACH DEPENDENCY INSTALLED WAS THE VERY LATEST VERSION AVAILABLE.
           So it's only here as a fall back method and shouldn't normally be required with newer code - it will be removed in the future."""
        if not condition:
            return 0

        self.composite_logger.log_debug("\nStarting status reconciliation...")
        start_time = time.time()
        still_needed_packages, still_needed_package_versions = package_manager.get_all_updates(False)  # do not use cache
        successful_packages = []
        successful_package_versions = []
        for i in range(0, len(self.last_still_needed_packages)):
            if self.last_still_needed_packages[i] not in still_needed_packages:
                successful_packages.append(self.last_still_needed_packages[i])
                successful_package_versions.append(self.last_still_needed_package_versions[i])

        self.status_handler.set_package_install_status(successful_packages, successful_package_versions, Constants.INSTALLED)
        self.last_still_needed_packages = still_needed_packages
        self.last_still_needed_package_versions = still_needed_package_versions
        self.composite_logger.log_debug("Completed status reconciliation. Time taken: " + str(time.time() - start_time) + " seconds.")
        return len(successful_packages)
    # endregion

    # region Package List Manipulation @ Update Run level
    def get_not_included_updates(self, package_manager, included_packages):
        """Returns the list of updates not included given any list of packages that will be included"""
        self.composite_logger.log_debug("\nEvaluating for 'not included' packages...")
        all_packages, all_package_versions = package_manager.get_all_updates(True)  # cached is fine
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

            dependency_list = package_manager.get_dependent_list(package)
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
