# --------------------------------------------------------------------------------------------------------------------
# <copyright file="MsftLinuxPatchCore.py" company="Microsoft">
#   Copyright (c) Microsoft Corporation. All rights reserved.
# </copyright>
# --------------------------------------------------------------------------------------------------------------------

from __future__ import print_function
from abc import ABCMeta, abstractmethod
from datetime import timedelta
import time
import sys
import subprocess
import datetime
import os
import platform
import json
import base64
import fnmatch
import shutil
import re


# region ########## PackageManager ##########
class PackageManager(object):
    """Base class of package manager"""

    def __init__(self, env_layer, composite_logger, telemetry_writer):
        self.env_layer = env_layer
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.single_package_upgrade_cmd = ''
        self.single_package_upgrade_simulation_cmd = 'simulate-install'
        self.package_manager_settings = {}

        # Enabling caching for high performance retrieval (only for code explicitly requesting it)
        self.all_updates_cached = []
        self.all_update_versions_cached = []

        # Constants
        self.STR_NOTHING_TO_DO = "Error: Nothing to do"
        self.STR_ONLY_UPGRADES = "Skipping <PACKAGE>, it is not installed and only upgrades are requested."
        self.STR_OBSOLETED = "Package <PACKAGE> is obsoleted"
        self.STR_REPLACED = "\nReplaced:\n"
        self.REBOOT_PENDING_FILE_PATH = '/var/run/reboot-required'

    __metaclass__ = ABCMeta  # For Python 3.0+, it changes to class Abstract(metaclass=ABCMeta)

    @abstractmethod
    def refresh_repo(self):
        """Resynchronize the package index files from their sources."""
        pass

    # region Get Available Updates
    @abstractmethod
    def invoke_package_manager(self, command):
        pass

    def get_available_updates(self, package_filter):
        """Returns List of all installed packages with available updates."""
        class_packages, class_versions = self.get_updates_for_classification(package_filter)
        incl_packages, incl_versions = self.get_updates_for_inclusions(package_filter)

        # classification's package version will supercede any inclusion package version (for future reference: this is by design and not a bug)
        packages, package_versions = self.dedupe_update_packages(class_packages + incl_packages, class_versions + incl_versions)

        return packages, package_versions

    # region Classification-based (incl. All) update check
    def get_updates_for_classification(self, package_filter):
        """Get missing updates for classifications"""
        if package_filter.is_invalid_classification_combination():
            raise Exception("Invalid classification combination selection detected. Please edit the update deployment configuration, "
                            "unselect + reselect the desired classifications and save.")

        if package_filter.is_msft_critsec_classification_only():
            return self.get_security_updates()
        elif package_filter.is_msft_other_classification_only():
            return self.get_other_updates()
        elif package_filter.is_msft_all_classification_included():
            return self.get_all_updates()
        else:
            return [], []  # happens when nothing was selected, and inclusions are present

    @abstractmethod
    def get_all_updates(self, cached=False):
        """Same behavior as get_available_updates, but higher performance with no filters"""
        pass
        return [], []  # only here to suppress a static syntax validation problem

    @abstractmethod
    def get_security_updates(self):
        pass

    @abstractmethod
    def get_other_updates(self):
        pass
    # endregion

    def get_updates_for_inclusions(self, package_filter):
        """Get missing updates for inclusions"""
        self.composite_logger.log_debug("Checking for inclusions...")

        # Trivial empty list cases
        if not package_filter.is_inclusion_list_present():
            self.composite_logger.log_debug(" - No inclusion list was present.")
            return [], []
        if package_filter.is_msft_all_classification_included():  # remember that this function is inclusion-list aware if you suspect there's a bug here
            self.composite_logger.log_debug(" - Inclusion list was present, but all classifications were selected - inclusions are irrelevant and will be ignored.")
            return [], []

        # Get all available updates
        self.composite_logger.log_debug("Getting all available updates for filtering...")
        packages, package_versions = self.get_all_updates(True)  # if a cached version is available, that is fine here
        included_packages = []
        included_package_versions = []
        not_included_packages = []

        # Check for inclusions
        for index, package in enumerate(packages):
            if package_filter.check_for_inclusion(package, package_versions[index]):    # check for the latest version
                self.composite_logger.log_debug(" - Package satisfied inclusion list: " + str(package) + " (version=" + package_versions[index] + ")")
                included_packages.append(package)
                included_package_versions.append(package_versions[index])

            elif package_filter.check_for_inclusion(package):                           # check for all available versions
                available_versions = self.get_all_available_versions_of_package(package)
                matched = False
                for available_version in available_versions:
                    if not package_filter.check_for_inclusion(package, available_version):
                        continue
                    self.composite_logger.log_debug(" - Package satisfied inclusion list: " + str(package) + " (version=" + available_version + ", latest version=" + package_versions[index] + ")")
                    included_packages.append(package)
                    included_package_versions.append(available_version)
                    matched = True
                    break

                if not matched:
                    self.composite_logger.log_warning(" - Package [" + package + "] is available, but not the specific version requested. Available versions found: " + str(available_versions))
                    not_included_packages.append(package)

            else:                                                                       # no match
                self.composite_logger.log_debug(" - Package didn't satisfy inclusion list: " + str(package))
                not_included_packages.append(package)

        return included_packages, included_package_versions

    @staticmethod
    def dedupe_update_packages(packages, package_versions):
        """Remove duplicate packages and returns"""
        deduped_packages = []
        deduped_package_versions = []

        for index, package in enumerate(packages):
            if package in deduped_packages:
                continue  # Already included

            deduped_packages.append(package)
            deduped_package_versions.append(package_versions[index])

        return deduped_packages, deduped_package_versions
    # endregion

    # region Install Update
    def get_install_command(self, cmd, packages, package_versions):
        """ Composes the install command for one or more packages with versions"""
        composite_cmd = cmd
        for index, package in enumerate(packages):
            if index != 0:
                composite_cmd += ' '
            if package_versions[index] != Constants.DEFAULT_UNSPECIFIED_VALUE:
                composite_cmd += self.get_composite_package_identifier(package, package_versions[index])
            else:
                composite_cmd += ' ' + package

        return composite_cmd

    @abstractmethod
    def get_composite_package_identifier(self, package_name, package_version):
        pass
        return ""  # only here to suppress a static syntax validation problem

    @abstractmethod
    def install_updates_fail_safe(self, excluded_packages):
        pass

    def install_update_and_dependencies(self, package_and_dependencies, package_and_dependency_versions, simulate=False):
        """Install a single package along with its dependencies (explicitly)"""
        install_result = Constants.INSTALLED
        package_no_longer_required = False
        code_path = "| Install"
        start_time = time.time()

        if type(package_and_dependencies) is str:
            package_and_dependencies = [package_and_dependencies]
            package_and_dependency_versions = [package_and_dependency_versions]

        if simulate is False:
            cmd = self.single_package_upgrade_cmd
        else:
            cmd = self.single_package_upgrade_simulation_cmd
        exec_cmd = str(self.get_install_command(cmd, package_and_dependencies, package_and_dependency_versions))

        self.composite_logger.log_debug("UPDATING PACKAGE (WITH DEPENDENCIES) USING COMMAND: " + exec_cmd)
        code, out = self.env_layer.run_command_output(exec_cmd, False, False)
        package_size = self.get_package_size(out)
        self.composite_logger.log_debug("\n<PackageInstallOutput>\n" + out + "\n</PackageInstallOutput>")  # wrapping multi-line for readability

        # special case of package no longer being required (or maybe even present on the system)
        if code == 1 and self.get_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY) == Constants.YUM:
            self.composite_logger.log_debug(" - Detecting if package is no longer required (as return code is 1):")
            if self.STR_NOTHING_TO_DO in out:
                code_path += " > Nothing to do. (succeeded)"
                self.composite_logger.log_debug("    - Evidence of package no longer required detected.")
                package_no_longer_required = True
                code = 0
            else:
                code_path += " > Nothing to do. (possible failure, tbd)"
                self.composite_logger.log_debug("    - Evidence of package no longer required NOT detected.")

        if not package_no_longer_required:
            if not self.is_package_version_installed(package_and_dependencies[0], package_and_dependency_versions[0]):
                if code == 0 and self.STR_ONLY_UPGRADES.replace('<PACKAGE>', package_and_dependencies[0]) in out:
                    # It is premature to fail this package. In the *unlikely* case it never gets picked up, it'll remain NotStarted.
                    # The NotStarted status must not be written again in the calling function (it's not at the time of this writing).
                    code_path += " > Package has no prior version. (no operation; return 'not started')"
                    install_result = Constants.PENDING
                    self.composite_logger.log_warning(" |- Package " + package_and_dependencies[0] + " (" + package_and_dependency_versions[0] + ") needs to already have an older version installed in order to be upgraded. " +
                                                   "\n |- Another upgradeable package requiring it as a dependency can cause it to get installed later. No action may be required.\n")

                elif code == 0 and self.STR_OBSOLETED.replace('<PACKAGE>', self.get_composite_package_identifier(package_and_dependencies[0], package_and_dependency_versions[0])) in out:
                    # Package can be obsoleted by another package installed in the run (via dependencies)
                    code_path += " > Package obsoleted. (succeeded)"
                    install_result = Constants.INSTALLED    # close approximation to obsoleted
                    self.composite_logger.log_debug(" - Package was discovered to be obsoleted.")

                elif code == 0 and len(out.split(self.STR_REPLACED)) > 1 and package_and_dependencies[0] in out.split(self.STR_REPLACED)[1]:
                    code_path += " > Package replaced. (succeeded)"
                    install_result = Constants.INSTALLED    # close approximation to replaced
                    self.composite_logger.log_debug(" - Package was discovered to be replaced by another during its installation.")

                else:  # actual failure
                    install_result = Constants.FAILED
                    if code != 0:
                        code_path += " > Package NOT installed. (failed)"
                        self.composite_logger.log_error(" |- Package failed to install: " + package_and_dependencies[0] + " (" + package_and_dependency_versions[0] + "). " +
                                                     "\n |- Error code: " + str(code) + ". Command used: " + exec_cmd +
                                                     "\n |- Command output: " + out + "\n")
                    else:
                        code_path += " > Package NOT installed but return code: 0. (failed)"
                        self.composite_logger.log_error(" |- Package appears to have not been installed: " + package_and_dependencies[0] + " (" + package_and_dependency_versions[0] + "). " +
                                                     "\n |- Return code: 0. Command used: " + exec_cmd + "\n" +
                                                     "\n |- Command output: " + out + "\n")
            elif code != 0:
                code_path += " > Info, package installed, non-zero return. (succeeded)"
                self.composite_logger.log_warning(" - [Info] Desired package version was installed, but the package manager returned a non-zero return code: " + str(code) + ". Command used: " + exec_cmd + "\n")
            else:
                code_path += " > Info, Package installed, zero return. (succeeded)"

        if not simulate:
            if install_result == Constants.FAILED:
                error = self.telemetry_writer.send_package_info(package_and_dependencies[0], package_and_dependency_versions[0], package_size, round(time.time() - start_time, 2), install_result, code_path, exec_cmd, str(out))
            else:
                error = self.telemetry_writer.send_package_info(package_and_dependencies[0], package_and_dependency_versions[0], package_size, round(time.time() - start_time, 2), install_result, code_path, exec_cmd)

            if error is not None:
                self.composite_logger.log_debug('\nEXCEPTION writing package telemetry: ' + repr(error))

        return install_result
    # endregion

    # region Package Information
    @abstractmethod
    def get_all_available_versions_of_package(self, package_name):
        """ Returns a list of all the available version of a package """
        pass
        return []  # only here to suppress a static syntax validation problem

    @abstractmethod
    def is_package_version_installed(self, package_name, package_version):
        """ Returns true if the specific package version is installed """
        pass

    @abstractmethod
    def get_dependent_list(self, package_name):
        """Retrieve available updates. Expect an array being returned"""
        pass

    @abstractmethod
    def get_product_name(self, package_name):
        """Retrieve package name """
        pass

    @abstractmethod
    def get_package_size(self, output):
        """Retrieve package size from installation output string"""
        pass
    # endregion

    # region Package Manager Settings
    def get_package_manager_setting(self, setting_key, default_value='d5414abb-62f9-40e3-96e1-d579f85a79ba'):
        # type: (str, object) -> ""  # type hinting to remove a warning
        """Gets any set package manager setting"""
        if setting_key in self.package_manager_settings:
            return self.package_manager_settings[setting_key]
        elif default_value != 'd5414abb-62f9-40e3-96e1-d579f85a79ba':  # this is the way it is because of a limitation of the packager script - the guid could have been Constants.DEFAULT_UNSPECIFIED_VALUE
            return default_value
        else:
            raise Exception("Setting key [" + setting_key + "] does not exist in package manager settings.")

    def set_package_manager_setting(self, setting_key, setting_value=""):
        # type: (str, object) -> ""  # type hinting to remove a warning
        """Sets package manager setting"""
        self.package_manager_settings[setting_key] = setting_value
    # endregion

    @abstractmethod
    def do_processes_require_restart(self):
        """Signals whether processes require a restart due to updates to files"""
        pass

    def is_reboot_pending(self):
        """ Checks if there is a pending reboot on the machine. """
        try:
            pending_file_exists = os.path.isfile(self.REBOOT_PENDING_FILE_PATH)
            pending_processes_exists = self.do_processes_require_restart()
            self.composite_logger.log_debug(" - Reboot required debug flags: " + str(pending_file_exists) + ", " + str(pending_processes_exists) + ".")
            return pending_file_exists or pending_processes_exists
        except Exception as error:
            self.composite_logger.log_error('Error while checking for reboot pending: ' + repr(error))
            return True     # defaults for safety


# endregion ########## PackageManager ##########


# region ########## CoreMain ##########
class CoreMain(object):
    def __init__(self, argv):
        """The main entry point of patch operation execution"""
        # Level 1 bootstrapping - bare minimum components to allow for diagnostics in further bootstrapping
        bootstrapper = Bootstrapper(argv)
        file_logger = bootstrapper.file_logger
        composite_logger = bootstrapper.composite_logger
        stdout_file_mirror = bootstrapper.stdout_file_mirror
        lifecycle_manager = telemetry_writer = status_handler = None

        # Init operation statuses
        patch_operation_requested = Constants.UNKNOWN
        patch_assessment_successful = False
        patch_installation_successful = False

        try:
            # Level 2 bootstrapping
            composite_logger.log_debug("Building out full container...")
            container = bootstrapper.build_out_container()
            lifecycle_manager, telemetry_writer, status_handler = bootstrapper.build_core_components(container)
            composite_logger.log_debug("Completed building out full container.\n\n")

            # Basic environment check
            bootstrapper.bootstrap_splash_text()
            bootstrapper.basic_environment_health_check()
            lifecycle_manager.execution_start_check()      # terminates if this instance shouldn't be running (redundant)

            # Execution config retrieval
            composite_logger.log_debug("Obtaining execution configuration...")
            execution_config = container.get('execution_config')
            patch_operation_requested = execution_config.operation.lower()
            patch_assessor = container.get('patch_assessor')
            patch_installer = container.get('patch_installer')

            # Assessment happens no matter what
            patch_assessment_successful = patch_assessor.start_assessment()

            # Patching + additional assessment occurs if the operation is 'Installation'
            if patch_operation_requested == Constants.INSTALLATION.lower():
                patch_installation_successful = patch_installer.start_installation()
                patch_assessment_successful = patch_assessor.start_assessment()

        except Exception as error:
            # Privileged operation handling for non-production use
            if Constants.EnvLayer.PRIVILEGED_OP_MARKER in repr(error):
                composite_logger.log_debug('\nPrivileged operation request intercepted: ' + repr(error))
                raise

            # General handling
            composite_logger.log_error('\nEXCEPTION during patch operation: ' + repr(error))
            composite_logger.log_error('TO TROUBLESHOOT, please save this file before the next invocation: ' + bootstrapper.log_file_path)

            composite_logger.log_debug("Safely completing required operations after exception...")
            if telemetry_writer is not None:
                telemetry_writer.send_error_info("EXCEPTION: " + repr(error))
            if status_handler is not None:
                composite_logger.log_debug(' - Status handler pending writes flags [I=' + str(patch_installation_successful) + ', A=' + str(patch_assessment_successful) + ']')
                if patch_operation_requested == Constants.INSTALLATION.lower() and not patch_installation_successful:
                    status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)
                    composite_logger.log_debug('  -- Persisted failed installation substatus.')
                if not patch_assessment_successful:
                    status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
                    composite_logger.log_debug('  -- Persisted failed assessment substatus.')
            else:
                composite_logger.log_error(' - Status handler is not initialized, and status data cannot be written.')
            composite_logger.log_debug("Completed exception handling.\n")

        finally:
            if lifecycle_manager is not None:
                lifecycle_manager.update_core_sequence(completed=True)

            telemetry_writer.send_runbook_state_info("Succeeded.")
            telemetry_writer.close_transports()

            stdout_file_mirror.stop()
            file_logger.close(message_at_close="<End of output>")

# endregion ########## CoreMain ##########


# region ########## Bootstrapper ##########
class Bootstrapper(object):
    def __init__(self, argv):
        # Environment awareness
        self.current_env = self.get_current_env()
        self.argv = argv
        self.log_file_path, self.real_record_path = self.get_log_file_and_real_record_paths(argv)
        self.recorder_enabled, self.emulator_enabled = self.get_recorder_emulator_flags(argv)

        # Container initialization
        print("Building bootstrap container configuration...")
        self.configuration_factory = ConfigurationFactory(self.log_file_path, self.real_record_path, self.recorder_enabled, self.emulator_enabled)
        self.container = Container()
        self.container.build(self.configuration_factory.get_bootstrap_configuration(self.current_env))

        # Environment layer capture
        self.env_layer = self.container.get('env_layer')

        # Logging initializations
        self.file_logger = self.container.get('file_logger')
        self.stdout_file_mirror = StdOutFileMirror(self.env_layer, self.file_logger)
        self.composite_logger = self.container.get('composite_logger')
        self.telemetry_writer = None

        print("Completed building bootstrap container configuration.\n")

    @staticmethod
    def get_current_env():
        """ Decides what environment to bootstrap with """
        current_env = os.getenv(Constants.LPE_ENV_VARIABLE, Constants.PROD)
        if str(current_env) not in [Constants.DEV, Constants.TEST, Constants.PROD]:
            current_env = Constants.PROD
        print("Bootstrap environment: " + str(current_env))
        return current_env

    def get_log_file_and_real_record_paths(self, argv):
        """ Performs the minimum steps required to determine where to start logging """
        sequence_number = self.get_value_from_argv(argv, Constants.ARG_SEQUENCE_NUMBER)
        environment_settings = json.loads(base64.b64decode(self.get_value_from_argv(argv, Constants.ARG_ENVIRONMENT_SETTINGS)))
        log_folder = environment_settings[Constants.EnvSettings.LOG_FOLDER]  # can throw exception and that's okay (since we can't recover from this)
        log_file_path = os.path.join(log_folder, str(sequence_number) + ".core.log")
        real_rec_path = os.path.join(log_folder, str(sequence_number) + ".core.rec")
        return log_file_path, real_rec_path

    def get_recorder_emulator_flags(self, argv):
        """ Determines if the recorder or emulator flags need to be changed from the defaults """
        recorder_enabled = False
        emulator_enabled = False
        try:
            recorder_enabled = bool(self.get_value_from_argv(argv, Constants.ARG_INTERNAL_RECORDER_ENABLED))
            emulator_enabled = bool(self.get_value_from_argv(argv, Constants.ARG_INTERNAL_EMULATOR_ENABLED))
        except Exception as error:
            print("INFO: Default environment layer settings loaded.")
        return recorder_enabled, emulator_enabled

    @staticmethod
    def get_value_from_argv(argv, key):
        """ Discovers the value assigned to a given key based on the core contract on arguments """
        for x in range(1, len(argv)):
            if x % 2 == 1:  # key checker
                if str(argv[x]).lower() == key.lower() and x < len(argv):
                    return str(argv[x+1])
        raise Exception("Unable to find key {0} in core arguments: {1}.".format(key, str(argv)))

    def build_out_container(self):
        # First output in a positive bootstrap
        try:
            # input parameter incorporation
            arguments_config = self.configuration_factory.get_arguments_configuration(self.argv)
            self.container.build(arguments_config)

            # full configuration incorporation
            self.container.build(self.configuration_factory.get_configuration(self.current_env, self.env_layer.get_package_manager()))

            return self.container
        except Exception as error:
            self.composite_logger.log_error('\nEXCEPTION during patch management core bootstrap: ' + repr(error))
            raise
        pass

    def build_core_components(self, container):
        self.composite_logger.log_debug(" - Instantiating lifecycle manager.")
        lifecycle_manager = container.get('lifecycle_manager')
        self.composite_logger.log_debug(" - Instantiating telemetry writer.")
        telemetry_writer = container.get('telemetry_writer')
        self.composite_logger.log_debug(" - Instantiating progress status writer.")
        status_handler = container.get('status_handler')
        return lifecycle_manager, telemetry_writer, status_handler

    def bootstrap_splash_text(self):
        self.composite_logger.log("\n\nMsftLinuxPatchCore \t -- \t Copyright (c) Microsoft Corporation. All rights reserved. \nApplication version: 3.0.200327-2355\n\n")

    def basic_environment_health_check(self):
        self.composite_logger.log("Python version: " + " ".join(sys.version.splitlines()))
        self.composite_logger.log("Linux distribution: " + str(self.env_layer.platform.linux_distribution()) + "\n")

        # Ensure sudo works in the environment
        sudo_check_result = self.env_layer.check_sudo_status()
        self.composite_logger.log_debug("Sudo status check: " + str(sudo_check_result) + "\n")

# endregion ########## Bootstrapper ##########


# region ########## ConfigurationFactory ##########
class ConfigurationFactory(object):
    """ Class for generating module definitions. Configuration is list of key value pairs. Please DON'T change key name.
    DI container relies on the key name to find and resolve dependencies. If you do need change it, please make sure to
    update the key name in all places that reference it. """
    def __init__(self, log_file_path, real_record_path, recorder_enabled, emulator_enabled):
        self.bootstrap_configurations = {
            'prod_config':  self.new_bootstrap_configuration(Constants.PROD, log_file_path, real_record_path, recorder_enabled, emulator_enabled),
            'dev_config':   self.new_bootstrap_configuration(Constants.DEV, log_file_path, real_record_path, recorder_enabled, emulator_enabled),
            'test_config':  self.new_bootstrap_configuration(Constants.TEST, log_file_path, real_record_path, recorder_enabled, emulator_enabled)
        }

        self.configurations = {
            'apt_prod_config':    self.new_prod_configuration(Constants.APT, AptitudePackageManager),
            'yum_prod_config':    self.new_prod_configuration(Constants.YUM, YumPackageManager),
            'zypper_prod_config': self.new_prod_configuration(Constants.ZYPPER, ZypperPackageManager),

            'apt_dev_config':     self.new_dev_configuration(Constants.APT, AptitudePackageManager),
            'yum_dev_config':     self.new_dev_configuration(Constants.YUM, YumPackageManager),
            'zypper_dev_config':  self.new_dev_configuration(Constants.ZYPPER, ZypperPackageManager),

            'apt_test_config':    self.new_test_configuration(Constants.APT, AptitudePackageManager),
            'yum_test_config':    self.new_test_configuration(Constants.YUM, YumPackageManager),
            'zypper_test_config': self.new_test_configuration(Constants.ZYPPER, ZypperPackageManager)
        }

    # region - Configuration Getters
    def get_bootstrap_configuration(self, env):
        """ Get core configuration for bootstrapping the application. """
        if str(env) not in [Constants.DEV, Constants.TEST, Constants.PROD]:
            print ("Error: Environment configuration not supported - " + str(env))
            return None

        configuration_key = str.lower('{0}_config'.format(str(env)))
        return self.bootstrap_configurations[configuration_key]

    @staticmethod
    def get_arguments_configuration(argv):
        """ Composes the configuration with the passed in arguments. """
        arguments_config = {
            'execution_arguments': str(argv),
            'execution_config': {
                'component': ExecutionConfig,
                'component_args': ['env_layer', 'composite_logger'],
                'component_kwargs': {
                    'execution_parameters': str(argv)
                }
            }
        }
        return arguments_config

    def get_configuration(self, env, package_manager_name):
        """ Gets the final configuration for a given env and package manager. """
        if str(env) not in [Constants.DEV, Constants.TEST, Constants.PROD]:
            print ("Error: Environment configuration not supported - " + str(env))
            return None

        if str(package_manager_name) not in [Constants.APT, Constants.YUM, Constants.ZYPPER]:
            print ("Error: Package manager configuration not supported - " + str(package_manager_name))
            return None

        configuration_key = str.lower('{0}_{1}_config'.format(str(package_manager_name), str(env)))
        selected_configuration = self.configurations[configuration_key]
        return selected_configuration
    # endregion

    # region - Configuration Builders
    @staticmethod
    def new_bootstrap_configuration(config_env, log_file_path, real_record_path, recorder_enabled, emulator_enabled):
        """ Core configuration definition. """
        configuration = {
            'config_env': config_env,
            'env_layer': {
                'component': EnvLayer,
                'component_args': [],
                'component_kwargs': {
                    'real_record_path': real_record_path,
                    'recorder_enabled': recorder_enabled,
                    'emulator_enabled': emulator_enabled
                }
            },
            'file_logger': {
                'component': FileLogger,
                'component_args': ['env_layer'],
                'component_kwargs': {
                    'log_file': log_file_path
                }
            },
            'composite_logger': {
                'component': CompositeLogger,
                'component_args': ['file_logger'],
                'component_kwargs': {
                    'current_env': config_env
                }
            },

        }

        if config_env is Constants.DEV or config_env is Constants.TEST:
            pass  # modify config as desired

        return configuration

    def new_prod_configuration(self, package_manager_name, package_manager_component):
        """ Base configuration for Prod V2. """
        configuration = {
            'config_env': Constants.PROD,
            'package_manager_name': package_manager_name,
            'lifecycle_manager': {
                'component': LifecycleManager,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer'],
                'component_kwargs': {}
            },
            'status_handler': {
                'component': StatusHandler,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'package_manager'],
                'component_kwargs': {}
            },
            'telemetry_writer': {
                'component': TelemetryWriter,
                'component_args': ['env_layer', 'execution_config'],
                'component_kwargs': {}
            },
            'package_manager': {
                'component': package_manager_component,
                'component_args': ['env_layer', 'composite_logger', 'telemetry_writer'],
                'component_kwargs': {}
            },
            'reboot_manager': {
                'component': RebootManager,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'status_handler', 'package_manager'],
                'component_kwargs': {
                    'default_reboot_setting': 'IfRequired'
                }
            },
            'package_filter': {
                'component': PackageFilter,
                'component_args': ['execution_config', 'composite_logger'],
                'component_kwargs': {}
            },
            'patch_assessor': {
                'component': PatchAssessor,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler', 'package_manager'],
                'component_kwargs': {}
            },
            'patch_installer': {
                'component': PatchInstaller,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler', 'lifecycle_manager', 'package_manager', 'package_filter', 'maintenance_window', 'reboot_manager'],
                'component_kwargs': {}
            },
            'maintenance_window': {
                'component': MaintenanceWindow,
                'component_args': ['env_layer', 'execution_config', 'composite_logger'],
                'component_kwargs': {}
            }
        }
        return configuration

    def new_dev_configuration(self, package_manager_name, package_manager_component):
        """ Base configuration definition for dev. It derives from the production configuration. """
        configuration = self.new_prod_configuration(package_manager_name, package_manager_component)
        configuration['config_env'] = Constants.DEV
        # perform desired modifications to configuration
        return configuration

    def new_test_configuration(self, package_manager_name, package_manager_component):
        """ Base configuration definition for test. It derives from the production configuration. """
        configuration = self.new_prod_configuration(package_manager_name, package_manager_component)
        configuration['config_env'] = Constants.TEST
        # perform desired modifications to configuration
        return configuration
    # endregion

# endregion ########## ConfigurationFactory ##########


# region ########## Constants ##########
class Constants(object):
    """Static class contains all constant variables"""
    # Enum Backport to support Enum in python 2.7
    class EnumBackport(object):
        class __metaclass__(type):
            def __iter__(self):
                for item in self.__dict__:
                    if item == self.__dict__[item]:
                        yield item

    DEFAULT_UNSPECIFIED_VALUE = '7d12c6abb5f74eecec4b94e19ac3d418'  # non-colliding default to distinguish between user selection and true default where used
    GLOBAL_EXCLUSION_LIST = ""   # if a package needs to be blocked across all of Azure
    UNKNOWN = "Unknown"

    # Runtime environments
    TEST = 'Test'
    DEV = 'Dev'
    PROD = 'Prod'
    LPE_ENV_VARIABLE = "LPE_ENV"    # Overrides environment setting

    # Execution Arguments
    ARG_SEQUENCE_NUMBER = '-sequenceNumber'
    ARG_ENVIRONMENT_SETTINGS = "-environmentSettings"
    ARG_CONFIG_SETTINGS = "-configSettings"
    ARG_PROTECTED_CONFIG_SETTINGS = "-protectedConfigSettings"
    ARG_INTERNAL_RECORDER_ENABLED = "-recorderEnabled"
    ARG_INTERNAL_EMULATOR_ENABLED = "-emulatorEnabled"

    class EnvSettings(EnumBackport):
        LOG_FOLDER = "logFolder"
        CONFIG_FOLDER = "configFolder"
        STATUS_FOLDER = "statusFolder"

    class ConfigSettings(EnumBackport):
        OPERATION = 'operation'
        ACTIVITY_ID = 'activityId'
        START_TIME = 'startTime'
        MAXIMUM_DURATION = 'maximumDuration'
        REBOOT_SETTING = 'rebootSetting'
        CLASSIFICATIONS_TO_INCLUDE = 'classificationsToInclude'
        PATCHES_TO_INCLUDE = 'patchesToInclude'
        PATCHES_TO_EXCLUDE = 'patchesToExclude'

    # Operations
    ASSESSMENT = "Assessment"
    INSTALLATION = "Installation"
    PATCH_ASSESSMENT_SUMMARY = "PatchAssessmentSummary"
    PATCH_INSTALLATION_SUMMARY = "PatchInstallationSummary"

    # Status file states
    STATUS_TRANSITIONING = "Transitioning"
    STATUS_ERROR = "Error"
    STATUS_SUCCESS = "Success"
    STATUS_WARNING = "Warning"

    # Wrapper-core handshake files
    EXT_STATE_FILE = 'ExtState.json'
    CORE_STATE_FILE = 'CoreState.json'

    # Operating System distributions
    UBUNTU = 'Ubuntu'
    RED_HAT = 'Red Hat'
    SUSE = 'SUSE'
    CENTOS = 'CentOS'

    # Package Managers
    APT = 'apt'
    YUM = 'yum'
    ZYPPER = 'zypper'

    # Package Statuses
    INSTALLED = 'Installed'
    FAILED = 'Failed'
    EXCLUDED = 'Excluded'        # explicitly excluded
    PENDING = 'Pending'
    NOT_SELECTED = 'NotSelected'  # implicitly not installed as it wasn't explicitly included
    AVAILABLE = 'Available'      # assessment only

    UNKNOWN_PACKAGE_SIZE = "Unknown"
    PACKAGE_STATUS_REFRESH_RATE_IN_SECONDS = 10
    MAX_FILE_OPERATION_RETRY_COUNT = 5
    MAX_ASSESSMENT_RETRY_COUNT = 5
    MAX_INSTALLATION_RETRY_COUNT = 3

    # Package Classifications
    PACKAGE_CLASSIFICATIONS = {
        0: 'Unclassified',           # doesn't serve a functional purpose in bit mask, but stands in for 'All' in code
        1: 'Critical',
        2: 'Security',
        4: 'Other'
    }
    PKG_MGR_SETTING_FILTER_CRITSEC_ONLY = 'FilterCritSecOnly'
    PKG_MGR_SETTING_IDENTITY = 'PackageManagerIdentity'
    PKG_MGR_SETTING_IGNORE_PKG_FILTER = 'IgnorePackageFilter'

    # Reboot Manager
    REBOOT_NEVER = 'Never reboot'
    REBOOT_IF_REQUIRED = 'Reboot if required'
    REBOOT_ALWAYS = 'Always reboot'
    REBOOT_SETTINGS = {  # API to exec-code mapping (+incl. validation)
        'Never': REBOOT_NEVER,
        'IfRequired': REBOOT_IF_REQUIRED,
        'Always': REBOOT_ALWAYS
    }
    REBOOT_BUFFER_IN_MINUTES = 15
    REBOOT_WAIT_TIMEOUT_IN_MINUTES = 5

    # Installation Reboot Statuses
    class RebootStatus(EnumBackport):
        NOT_NEEDED = "NotNeeded"
        REQUIRED = "Required"
        STARTED = "Started"
        COMPLETED = "Completed"
        FAILED = "Failed"

    # Maintenance Window
    PACKAGE_INSTALL_EXPECTED_MAX_TIME_IN_MINUTES = 5

    # Package Manager Setting
    PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION = "RepeatUpdateRun"

    # Telemetry Categories
    TELEMETRY_OPERATION_STATE = "State"
    TELEMETRY_CONFIG = "Config"
    TELEMETRY_PACKAGE = "PackageInfo"
    TELEMETRY_ERROR = "Error"
    TELEMETRY_INFO = "Info"
    TELEMETRY_DEBUG = "Debug"

    # EnvLayer Constants
    class EnvLayer(EnumBackport):
        PRIVILEGED_OP_MARKER = "Privileged_Op_e6df678d-d09b-436a-a08a-65f2f70a6798"
        PRIVILEGED_OP_REBOOT = PRIVILEGED_OP_MARKER + "Reboot_Exception"
        PRIVILEGED_OP_EXIT = PRIVILEGED_OP_MARKER + "Exit_"

# endregion ########## Constants ##########


# region ########## Container ##########
class _Singleton(type):
    """ A metaclass that creates a Singleton base class when called. """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(_Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Singleton(_Singleton('SingletonMeta', (object,), {})):
    def __init__(self):
        pass


NO_DEFAULT = "NO_DEFAULT"


class Container(Singleton):
    """This is the lightweight implementation of DI Container"""

    def __init__(self):
        super(Container, self).__init__()
        self.instances = {}
        self.components = {}
        self.composite_logger = CompositeLogger()

    def register(self, component_id, component, *component_args, **component_kwargs):
        """Registers component for the given property name
        The component could be a callable or a raw value.
        Arguments of the component will be searched
        inside the container by their name.

        The component_args and component_kwargs allow
        to specify extra arguments for the component.component_property
        """
        if (component_args or component_kwargs) and not callable(component):
            raise ValueError(
                "Only callable component supports extra component_args: %s, %s(%s, %s)"
                % (component_id, component, component_args, component_kwargs))

        self.components[component_id] = component, component_args, component_kwargs

    def get(self, component_id):
        """Lookups the given property name in context.
        Raises KeyError when no such property is found.
        """
        if component_id not in self.components:
            raise KeyError("No component for: %s" % component_id)

        if component_id in self.instances:
            return self.instances[component_id]

        factory_spec = self.components[component_id]
        instance = self._instantiate(component_id, *factory_spec)
        self.instances[component_id] = instance
        return instance

    def build(self, config):
        """Build container based on the given configuration
        """
        for key, value in config.items():
            if isinstance(value, str):
                self.register(key, value)
            else:
                self.register(key, value['component'], *value['component_args'],
                              **value['component_kwargs'])

    def _instantiate(self, component_id, component, component_args, component_kwargs):
        if not callable(component):
            self.composite_logger.log_debug(str.format("\nComponent: {0}: {1}", component_id, component))
            return component

        kwargs = self._prepare_kwargs(component, component_args, component_kwargs)
        self.composite_logger.log_debug(
            str.format(
                "Component: {0}: {1}({2}, {3})",
                component_id,
                component.__name__,
                component_args,
                kwargs))

        return component(*(), **kwargs)

    # noinspection PyUnusedLocal
    def _prepare_kwargs(self, component, component_args, component_kwargs):
        """Returns keyword arguments usable for the given component.
        The component_kwargs could specify explicit keyword values.
        """
        defaults = self.get_argdefaults(component)

        for arg, default in defaults.items():
            if arg in component_kwargs:
                continue
            elif arg in self.components:
                defaults[arg] = self.get(arg)
            elif default is NO_DEFAULT:
                raise KeyError("No component for arg: %s" % arg)

        if component_kwargs is not None:
            defaults.update(component_kwargs)
        return defaults

    def get_argdefaults(self, component):
        """Returns dict of (arg_name, default_value) pairs.
        The default_value could be NO_DEFAULT
        when no default was specified.
        """
        component_args, defaults = self._getargspec(component)

        if defaults is not None:
            num_without_defaults = len(component_args) - len(defaults)
            default_values = (NO_DEFAULT,) * num_without_defaults + defaults
        else:
            default_values = (NO_DEFAULT,) * len(component_args)

        return dict(zip(component_args, default_values))

    @staticmethod
    def _getargspec(component):
        """Describes needed arguments for the given component.
        Returns tuple (component_args, defaults) with argument names
        and default values for component_args tail.
        """
        import inspect
        if inspect.isclass(component):
            component = component.__init__

        component_args, vargs, vkw, defaults = inspect.getargspec(component)
        if inspect.ismethod(component):
            component_args = component_args[1:]
        return component_args, defaults

    def reset(self):
        """reset registered dependencies"""
        self.instances = {}
        self.components = {}

# endregion ########## Container ##########


# region ########## EnvLayer ##########
class EnvLayer(object):
    """ Environment related functions """

    def __init__(self, real_record_path=None, recorder_enabled=False, emulator_enabled=False):
        # Recorder / emulator storage
        self.__real_record_path = real_record_path
        self.__real_record_pointer_path = real_record_path + ".pt"
        self.__real_record_handle = None
        self.__real_record_pointer = 0

        # Recorder / emulator state section
        self.__recorder_enabled = recorder_enabled                                  # dumps black box recordings
        self.__emulator_enabled = False if recorder_enabled else emulator_enabled   # only one can be enabled at a time

        # Recorder / emulator initialization
        if self.__recorder_enabled:
            self.__record_writer_init()
        elif self.__emulator_enabled:
            self.__record_reader_init()

        # Discrete components
        self.platform = self.Platform(recorder_enabled, emulator_enabled, self.__write_record, self.__read_record)
        self.datetime = self.DateTime(recorder_enabled, emulator_enabled, self.__write_record, self.__read_record)
        self.file_system = self.FileSystem(recorder_enabled, emulator_enabled, self.__write_record, self.__read_record,
                                           emulator_root_path=os.path.dirname(self.__real_record_path))

    def get_package_manager(self):
        """ Detects package manager type """
        ret = None

        # choose default - almost surely one will match.
        for b in ('apt-get', 'yum', 'zypper'):
            code, out = self.run_command_output('which ' + b, False, False)
            if code is 0:
                ret = b
                if ret == 'apt-get':
                    ret = Constants.APT
                    break
                if ret == 'yum':
                    ret = Constants.YUM
                    break
                if ret == 'zypper':
                    ret = Constants.ZYPPER
                    break

        if ret is None and platform.system() == 'Windows':
            ret = Constants.APT

        return ret

    def run_command_output(self, cmd, no_output=False, chk_err=False):
        operation = "RUN_CMD_OUT"
        if not self.__emulator_enabled:
            start = time.time()
            code, output = self.__run_command_output_raw(cmd, no_output, chk_err)
            self.__write_record(operation, code, output, delay=(time.time()-start))
            return code, output
        else:
            return self.__read_record(operation)

    def __run_command_output_raw(self, cmd, no_output, chk_err=True):
        """
        Wrapper for subprocess.check_output. Execute 'cmd'.
        Returns return code and STDOUT, trapping expected exceptions.
        Reports exceptions to Error if chk_err parameter is True
        """

        def check_output(no_output, *popenargs, **kwargs):
            """
            Backport from subprocess module from python 2.7
            """
            if 'stdout' in kwargs:
                raise ValueError('stdout argument not allowed, it will be overridden.')
            if no_output is True:
                out_file = None
            else:
                out_file = subprocess.PIPE

            process = subprocess.Popen(stdout=out_file, *popenargs, **kwargs)
            output, unused_err = process.communicate()
            retcode = process.poll()

            if retcode:
                cmd = kwargs.get("args")
                if cmd is None:
                    cmd = popenargs[0]
                raise subprocess.CalledProcessError(retcode, cmd, output=output)
            return output

        # noinspection PyShadowingNames,PyShadowingNames
        class CalledProcessError(Exception):
            """Exception classes used by this module."""

            def __init__(self, return_code, cmd, output=None):
                self.return_code = return_code
                self.cmd = cmd
                self.output = output

            def __str__(self):
                return "Command '%s' returned non-zero exit status %d" \
                       % (self.cmd, self.return_code)

        subprocess.check_output = check_output
        subprocess.CalledProcessError = CalledProcessError
        try:
            output = subprocess.check_output(
                no_output, cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            if chk_err:
                print("Error: CalledProcessError.  Error Code is: " + str(e.returncode), file=sys.stdout)
                print("Error: CalledProcessError.  Command string was: " + e.cmd, file=sys.stdout)
                print("Error: CalledProcessError.  Command result was: " + (e.output[:-1]).decode('utf8', 'ignore').encode("ascii", "ignore"), file=sys.stdout)
            if no_output:
                return e.return_code, None
            else:
                return e.return_code, e.output.decode('utf8', 'ignore').encode('ascii', 'ignore')
        except Exception as error:
            message = "Exception during cmd execution. [Exception={0}][Cmd={1}]".format(repr(error),str(cmd))
            print(message)
            raise message

        if no_output:
            return 0, None
        else:
            return 0, output.decode('utf8', 'ignore').encode('ascii', 'ignore')

    def check_sudo_status(self, raise_if_not_sudo=True):
        """ Checks if we can invoke sudo successfully. """
        try:
            print("Performing sudo status check... This should complete within 10 seconds.")
            return_code, output = self.run_command_output("timeout 10 sudo id && echo True || echo False", False, False)
            # output should look like either this (bad):
            #   [sudo] password for username:
            #   False
            # or this (good):
            #   uid=0(root) gid=0(root) groups=0(root)
            #   True

            output_lines = output.splitlines()
            if len(output_lines) < 2:
                raise Exception("Unexpected sudo check result. Output: " + " ".join(output.split("\n")))

            if output_lines[1] == "True":
                return True
            elif output_lines[1] == "False":
                if raise_if_not_sudo:
                    raise Exception("Unable to invoke sudo successfully. Output: " + " ".join(output.split("\n")))
                return False
            else:
                raise Exception("Unexpected sudo check result. Output: " + " ".join(output.split("\n")))
        except Exception as exception:
            print("Sudo status check failed. Please ensure the computer is configured correctly for sudo invocation. " +
                  "Exception details: " + str(exception))
            if raise_if_not_sudo:
                raise

    def reboot_machine(self, reboot_cmd):
        operation = "REBOOT_MACHINE"
        if not self.__emulator_enabled:
            self.__write_record(operation, 0, '', delay=0)
            subprocess.Popen(reboot_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            self.__read_record(operation)   # will throw if it's not the expected operation
            raise Exception(Constants.EnvLayer.PRIVILEGED_OP_REBOOT)

    def exit(self, code):
        operation = "EXIT_EXECUTION"
        if not self.__emulator_enabled:
            self.__write_record(operation, code, '', delay=0)
            exit(code)
        else:
            self.__read_record(operation)   # will throw if it's not the expected operation
            raise Exception(Constants.EnvLayer.PRIVILEGED_OP_EXIT + str(code))

# region - Platform emulation and extensions
    class Platform(object):
        def __init__(self, recorder_enabled=True, emulator_enabled=False, write_record_delegate=None, read_record_delegate=None):
            self.__recorder_enabled = recorder_enabled
            self.__emulator_enabled = False if recorder_enabled else emulator_enabled
            self.__write_record = write_record_delegate
            self.__read_record = read_record_delegate

        def linux_distribution(self):
            operation = "PLATFORM_LINUX_DISTRIBUTION"
            if not self.__emulator_enabled:
                value = platform.linux_distribution()
                if self.__recorder_enabled:
                    self.__write_record(operation, code=0, output=str(value))
                return value
            else:
                code, output = self.__read_record(operation)
                return eval(output)

        def system(self):   # OS Type
            operation = "PLATFORM_SYSTEM"
            if not self.__emulator_enabled:
                value = platform.system()
                if self.__recorder_enabled:
                    self.__write_record(operation, code=0, output=str(value))
                return value
            else:
                code, output = self.__read_record(operation)
                return output

        def machine(self):  # architecture
            operation = "PLATFORM_MACHINE"
            if not self.__emulator_enabled:
                value = platform.machine()
                if self.__recorder_enabled:
                    self.__write_record(operation, code=0, output=str(value))
                return value
            else:
                code, output = self.__read_record(operation)
                return output

        def node(self):     # machine name
            operation = "PLATFORM_NODE"
            if not self.__emulator_enabled:
                value = platform.node()
                if self.__recorder_enabled:
                    self.__write_record(operation, code=0, output=str(value))
                return value
            else:
                code, output = self.__read_record(operation)
                return output
# endregion - Platform emulation and extensions

# region - File system emulation and extensions
    class FileSystem(object):
        def __init__(self, recorder_enabled=True, emulator_enabled=False, write_record_delegate=None, read_record_delegate=None, emulator_root_path=None):
            self.__recorder_enabled = recorder_enabled
            self.__emulator_enabled = False if recorder_enabled else emulator_enabled
            self.__write_record = write_record_delegate
            self.__read_record = read_record_delegate
            self.__emulator_enabled = emulator_enabled
            self.__emulator_root_path = emulator_root_path

            # file-names of files that other processes may changes the contents of
            self.__non_exclusive_files = [Constants.EXT_STATE_FILE]

        def resolve_path(self, requested_path):
            """ Resolves any paths used with desired file system paths """
            if self.__emulator_enabled and self.__emulator_root_path is not None and self.__emulator_root_path not in requested_path:
                return os.path.join(self.__emulator_root_path, os.path.normpath(requested_path))
            else:
                return requested_path

        def open(self, file_path, mode):
            """ Provides a file handle to the file_path requested using implicit redirection where required """
            real_path = self.resolve_path(file_path)
            for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
                try:
                    return open(real_path, mode)
                except Exception as error:
                    if i <= Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                        time.sleep(i + 1)
                    else:
                        raise Exception("Unable to open {0} (retries exhausted). Error: {1}.".format(str(real_path), repr(error)))

        def __obtain_file_handle(self, file_path_or_handle, mode='a+'):
            """ Pass-through for handle. For path, resolution and handle open with retry. """
            is_path = False
            if isinstance(file_path_or_handle, str) or isinstance(file_path_or_handle, unicode):
                is_path = True
                file_path_or_handle = self.open(file_path_or_handle, mode)
            file_handle = file_path_or_handle
            return file_handle, is_path

        def read_with_retry(self, file_path_or_handle):
            """ Reads all content from a given file path in a single operation """
            operation = "FILE_READ"

            # only fully emulate non_exclusive_files from the real recording; exclusive files can be redirected and handled in emulator scenarios
            if not self.__emulator_enabled or (isinstance(file_path_or_handle, str) and os.path.basename(file_path_or_handle) not in self.__non_exclusive_files):
                file_handle, was_path = self.__obtain_file_handle(file_path_or_handle, 'r')
                value = file_handle.read()
                if was_path:  # what was passed in was not a file handle, so close the handle that was init here
                    file_handle.close()
                self.__write_record(operation, code=0, output=value, delay=0)
                return value
            else:
                code, output = self.__read_record(operation)
                return output

        def write_with_retry(self, file_path_or_handle, data, mode='a+'):
            """ Writes to a given real/emulated file path in a single operation """
            file_handle, was_path = self.__obtain_file_handle(file_path_or_handle, mode)

            for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
                try:
                    file_handle.write(str(data))
                    break
                except Exception as error:
                    if i <= Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                        time.sleep(i + 1)
                    else:
                        raise Exception("Unable to write to {0} (retries exhausted). Error: {1}.".format(str(file_handle.name), repr(error)))

            if was_path: # what was passed in was not a file handle, so close the handle that was init here
                file_handle.close()

# endregion - File system emulation and extensions

# region - DateTime emulation and extensions
    class DateTime(object):
        def __init__(self, recorder_enabled=True, emulator_enabled=False, write_record_delegate=None, read_record_delegate=None):
            self.__recorder_enabled = recorder_enabled
            self.__emulator_enabled = False if recorder_enabled else emulator_enabled
            self.__write_record = write_record_delegate
            self.__read_record = read_record_delegate

        def time(self):
            operation = "DATETIME_TIME"
            if not self.__emulator_enabled:
                value = time.time()
                self.__write_record(operation, code=0, output=value, delay=0)
                return value
            else:
                code, output = self.__read_record(operation)
                return int(output)

        def datetime_utcnow(self):
            operation = "DATETIME_UTCNOW"
            if not self.__emulator_enabled:
                value = datetime.datetime.utcnow()
                self.__write_record(operation, code=0, output=str(value), delay=0)
                return value
            else:
                code, output = self.__read_record(operation)
                return datetime.datetime.strptime(str(output), "%Y-%m-%d %H:%M:%S.%f")

        def timestamp(self):
            operation = "DATETIME_TIMESTAMP"
            if not self.__emulator_enabled:
                value = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                self.__write_record(operation, code=0, output=value, delay=0)
                return value
            else:
                code, output = self.__read_record(operation)
                return output

        # --------------------------------------------------------------------------------------------------------------
        # Static library functions
        # --------------------------------------------------------------------------------------------------------------
        @staticmethod
        def total_minutes_from_time_delta(time_delta):
            return ((time_delta.microseconds + (time_delta.seconds + time_delta.days * 24 * 3600) * 10 ** 6) / 10.0 ** 6) / 60

        @staticmethod
        def utc_to_standard_datetime(utc_datetime):
            """ Converts string of format '"%Y-%m-%dT%H:%M:%SZ"' to datetime object """
            return datetime.datetime.strptime(utc_datetime.split(".")[0], "%Y-%m-%dT%H:%M:%S")
# endregion - DateTime emulator and extensions

# region - Core Emulator support functions
    def __write_record(self, operation, code, output, delay, timestamp=None):
        """ Writes a single operation record to disk if the recorder is enabled """
        if not self.__recorder_enabled or self.__real_record_handle is None:
            return

        try:
            record = {
                "timestamp": str(timestamp) if timestamp is not None else datetime.datetime.strptime(str(datetime.datetime.utcnow()).split(".")[0], "%Y-%m-%dT%H:%M:%SZ"), #WRONG
                "operation": str(operation),
                "code": int(code),
                "output": base64.b64encode(str(output)),
                "delay": float(delay)
            }
            self.__real_record_handle.write('\n{0}'.format(json.dumps(record)))
        except Exception:
            print("EnvLayer: Unable to write real record to disk.")

    def __record_writer_init(self):
        """ Initializes the record writer handle """
        self.__real_record_handle = open(self.__real_record_path, 'a+')

    def __read_record(self, expected_operation):
        """ Returns code, output for a given operation if it matches """
        if self.__real_record_handle is None:
            raise Exception("Invalid real record handle.")

        # Get single record
        real_record_raw = self.__real_record_handle.readline().rstrip()
        real_record = json.loads(real_record_raw)

        # Load data from record
        timestamp = real_record['timestamp']
        operation = real_record['operation']
        code = int(real_record['code'])
        output = base64.b64decode(real_record['output'])
        delay = float(real_record['delay'])
        print("Real record read: {0}: {1} >> code({2}) - output.len({3} - {4})".format(timestamp, operation, str(code), str(len(output)), str(self.__real_record_pointer+1)))

        # Verify operation
        if real_record['operation'] != expected_operation:
            raise Exception("Execution deviation detected. Add adaptations for operation expected: {0}. Operation data found for: {1}.".format(expected_operation, real_record['operation']))

        # Advance and persist pointer
        self.__real_record_pointer += 1
        with open(self.__real_record_pointer_path, 'w') as file_handle:
            file_handle.write(str(self.__real_record_pointer))

        # Return data
        time.sleep(delay)
        return code, output

    def __record_reader_init(self):
        """ Seeks the real record pointer to the expected location """
        # Initialize record pointer
        if not os.path.exists(self.__real_record_pointer_path):
            self.__real_record_pointer = 0
        else:
            with open(self.__real_record_pointer_path, 'r') as file_handle:
                self.__real_record_pointer = int(file_handle.read().rstrip())  # no safety checks as there's no good recovery

        # Have the handle seek to the desired position
        self.__real_record_handle = open(self.__real_record_pointer_path, 'r')
        for x in range(1, self.__real_record_pointer):
            self.__real_record_handle.readline()
# endregion - Core Emulator support functions

# endregion ########## EnvLayer ##########


# region ########## ExecutionConfig ##########
class ExecutionConfig(object):
    def __init__(self, env_layer, composite_logger, execution_parameters):
        self.env_layer = env_layer
        self.composite_logger = composite_logger
        self.execution_parameters = eval(execution_parameters)

        # Environment details
        self.global_exclusion_list = str(Constants.GLOBAL_EXCLUSION_LIST)

        # Decoded input parameters
        self.composite_logger.log_debug(" - Decoding input parameters...")
        self.sequence_number = self.__get_value_from_argv(self.execution_parameters, Constants.ARG_SEQUENCE_NUMBER)
        self.environment_settings = self.__get_decoded_json_from_argv(self.execution_parameters, Constants.ARG_ENVIRONMENT_SETTINGS)
        self.config_settings = self.__get_decoded_json_from_argv(self.execution_parameters, Constants.ARG_CONFIG_SETTINGS)

        # Environment Settings
        self.composite_logger.log_debug(" - Parsing environment settings...")
        self.log_folder = self.environment_settings[Constants.EnvSettings.LOG_FOLDER]
        self.config_folder = self.environment_settings[Constants.EnvSettings.CONFIG_FOLDER]
        self.status_folder = self.environment_settings[Constants.EnvSettings.STATUS_FOLDER]

        # Config Settings
        self.composite_logger.log_debug(" - Parsing configuration settings... [ConfigSettings={0}]".format(str(self.config_settings)))
        self.operation = self.config_settings[Constants.ConfigSettings.OPERATION]
        self.activity_id = self.config_settings[Constants.ConfigSettings.ACTIVITY_ID]
        self.start_time = self.config_settings[Constants.ConfigSettings.START_TIME]
        self.duration = self.__convert_iso8601_duration_to_timedelta_str(self.config_settings[Constants.ConfigSettings.MAXIMUM_DURATION])
        self.included_classifications_list = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.CLASSIFICATIONS_TO_INCLUDE, [])
        self.included_package_name_mask_list = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.PATCHES_TO_INCLUDE, [])
        self.excluded_package_name_mask_list = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.PATCHES_TO_EXCLUDE, [])
        if self.operation == Constants.INSTALLATION:
            self.reboot_setting = self.config_settings[Constants.ConfigSettings.REBOOT_SETTING]     # expected to throw if not present
        else:
            self.reboot_setting = self.__get_execution_configuration_value_safely(self.config_settings, Constants.ConfigSettings.REBOOT_SETTING, Constants.REBOOT_NEVER)     # safe extension-level default

        # Derived Settings
        self.composite_logger.log_debug(" - Establishing data publishing paths...")
        self.log_file_path = os.path.join(self.log_folder, str(self.sequence_number) + ".core.log")
        self.composite_logger.log_debug("  -- Core log: " + str(self.log_file_path))
        self.status_file_path = os.path.join(self.status_folder, str(self.sequence_number) + ".status")
        self.composite_logger.log_debug("  -- Status file: " + str(self.status_file_path))

    @staticmethod
    def __get_value_from_argv(argv, key):
        """ Discovers the value associated with a specific parameter in input arguments. """
        for x in range(1, len(argv)):
            if x % 2 == 1:  # key checker
                if str(argv[x]).lower() == key.lower() and x < len(argv):
                    return str(argv[x+1])
        raise Exception("Unable to find key {0} in core arguments: {1}.".format(key, str(argv)))

    def __get_decoded_json_from_argv(self, argv, key):
        """ Discovers and decodes the JSON body of a specific base64 encoded JSON object in input arguments. """
        value = self.__get_value_from_argv(argv, key)

        try:
            decoded_value = base64.b64decode(value)
            decoded_json = json.loads(decoded_value)
        except Exception as error:
            self.composite_logger.log_error('Unable to process JSON in core arguments for key: {0}. Details: {1}.'.format(str(key), repr(error)))
            raise

        return decoded_json

    def __get_execution_configuration_value_safely(self, config_json, key, default_value=Constants.DEFAULT_UNSPECIFIED_VALUE):
        """ Allows a update deployment configuration value to be queried safely with a fall-back default (optional). """
        if key in config_json:
            value = config_json[key]
            return value
        else:  # If it is not present
            if default_value is Constants.DEFAULT_UNSPECIFIED_VALUE:  # return None if no preferred fallback
                self.composite_logger.log_debug('Warning: Config JSON did not contain ' + key + '. Returning None.')
                return None
            else:  # return preferred fallback value
                self.composite_logger.log_debug('Warning: Config JSON did not contain ' + key + '. Using default value (' + str(default_value) + ') instead.')
                return default_value

    def __convert_iso8601_duration_to_timedelta_str(self, duration):
        """
            Supports only a subset of the spec as applicable to patch management.
            No non-default period (Y,M,W,D) is supported. Time is supported (H,M,S).
            Can throw exceptions - expected to handled as appropriate in calling code.
        """
        remaining = str(duration)
        if 'PT' not in remaining:
            raise Exception("Unexpected duration format. [Duration={0}]".format(duration))

        discard, remaining = self.__extract_most_significant_unit_from_duration(remaining, 'PT')
        hours, remaining = self.__extract_most_significant_unit_from_duration(remaining, 'H')
        minutes, remaining = self.__extract_most_significant_unit_from_duration(remaining, 'M')
        seconds, remaining = self.__extract_most_significant_unit_from_duration(remaining, 'S')

        return str(datetime.timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds)))

    @staticmethod
    def __extract_most_significant_unit_from_duration(duration_portion, unit_delimiter):
        """ Internal helper function"""
        duration_split = duration_portion.split(unit_delimiter)
        most_significant_unit = 0
        if len(duration_split) == 2:  # found and extracted
            most_significant_unit = duration_split[0]
            remaining_duration_portion = duration_split[1]
        elif len(duration_split) == 1:  # not found
            remaining_duration_portion = duration_split[0]
        else:  # bad data
            raise Exception("Invalid duration portion: {0}".format(str(duration_portion)))
        return most_significant_unit, remaining_duration_portion

# endregion ########## ExecutionConfig ##########


# region ########## MaintenanceWindow ##########
class MaintenanceWindow(object):
    """Implements the maintenance window logic"""

    def __init__(self, env_layer, execution_config, composite_logger):
        self.execution_config = execution_config
        self.duration = self.execution_config.duration
        self.start_time = self.execution_config.start_time
        self.composite_logger = composite_logger
        self.env_layer = env_layer

    def get_remaining_time_in_minutes(self, current_time=None, log_to_stdout=False):
        """Calculate time remaining base on the given job start time"""
        try:
            if current_time is None:
                current_time = self.env_layer.datetime.datetime_utcnow()
            start_time = self.env_layer.datetime.utc_to_standard_datetime(self.start_time)
            dur = datetime.datetime.strptime(self.duration, "%H:%M:%S")
            dura = timedelta(hours=dur.hour, minutes=dur.minute, seconds=dur.second)
            total_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(dura)
            elapsed_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(current_time - start_time)
            remaining_time_in_minutes = max((total_time_in_minutes - elapsed_time_in_minutes), 0)

            log_line = "Maintenance Window Utilization: " + str(timedelta(seconds=int(elapsed_time_in_minutes*60))) + " / " + self.duration + "\
                        [Job start: " + str(start_time) + ", Current time: " + str(current_time.strftime("%Y-%m-%d %H:%M:%S")) + "]"
            if log_to_stdout:
                self.composite_logger.log(log_line)
            else:
                self.composite_logger.log_debug(log_line)
        except ValueError:
            self.composite_logger.log_error("\nError calculating time remaining. Check patch operation input parameters.")
            raise

        return remaining_time_in_minutes

    def is_package_install_time_available(self, remaining_time_in_minutes=None):
        """Check if time still available for package installation"""
        cutoff_time_in_minutes = Constants.REBOOT_BUFFER_IN_MINUTES + Constants.PACKAGE_INSTALL_EXPECTED_MAX_TIME_IN_MINUTES
        if remaining_time_in_minutes is None:
            remaining_time_in_minutes = self.get_remaining_time_in_minutes()

        if remaining_time_in_minutes > cutoff_time_in_minutes:
            self.composite_logger.log_debug("Time Remaining: " + str(timedelta(seconds=int(remaining_time_in_minutes * 60))) + ", Cutoff time: " + str(timedelta(minutes=cutoff_time_in_minutes)))
            return True
        else:
            self.composite_logger.log_warning("Time Remaining: " + str(timedelta(seconds=int(remaining_time_in_minutes * 60))) + ", Cutoff time: " + str(timedelta(minutes=cutoff_time_in_minutes)) + " [Out of time!]")
            return False

# endregion ########## MaintenanceWindow ##########


# region ########## PackageFilter ##########
class PackageFilter(object):
    """implements the Package filtering logic"""

    def __init__(self, execution_config, composite_logger):
        self.execution_config = execution_config
        self.composite_logger = composite_logger

        # Exclusions - note: version based exclusion is not supported
        self.global_excluded_packages = self.sanitize_str_to_list(self.execution_config.global_exclusion_list)
        self.installation_excluded_package_masks = self.execution_config.excluded_package_name_mask_list
        self.installation_excluded_packages, self.installation_excluded_package_versions = self.get_packages_and_versions_from_masks(self.installation_excluded_package_masks)

        # Inclusions - note: version based inclusion is optionally supported
        self.installation_included_package_masks = self.execution_config.included_package_name_mask_list
        self.installation_included_packages, self.installation_included_package_versions = self.get_packages_and_versions_from_masks(self.installation_included_package_masks)
        self.installation_included_classifications = self.execution_config.included_classifications_list

        # Neutralize global excluded packages, if customer explicitly includes the package
        packages_to_clear_from_global = []
        for package in self.global_excluded_packages:
            if self.check_for_explicit_inclusion(package):
                self.composite_logger.log_debug('Removing package from global exclusion list: ' + package)
                packages_to_clear_from_global.append(package)
        self.global_excluded_packages = [x for x in self.global_excluded_packages if x not in packages_to_clear_from_global]

        # Logging
        self.composite_logger.log("\nAzure globally-excluded packages: " + str(self.global_excluded_packages))
        self.composite_logger.log("Included package classifications: " + ', '.join(self.installation_included_classifications))
        self.composite_logger.log("Included packages: " + str(self.installation_included_package_masks))
        self.composite_logger.log("Excluded packages: " + str(self.installation_excluded_packages))
        if '=' in str(self.installation_excluded_package_masks):
            self.composite_logger.log_error("\n /!\\ Package exclusions do not support version matching in the filter today. "
                                            "Due to this, more packages than expected may be excluded from this update deployment.")

    # region Inclusion / exclusion presence checks
    def is_exclusion_list_present(self):
        """Return true if either Global or patch installation specific exclusion list present"""
        return bool(self.global_excluded_packages) or bool(self.installation_excluded_packages)

    def is_inclusion_list_present(self):
        """Return true if patch installation Inclusion is present"""
        return bool(self.installation_included_packages)
    # endregion

    # region Package exclusion checks
    def check_for_exclusion(self, one_or_more_packages):
        """Return true if package need to be excluded"""
        return self.check_for_match(one_or_more_packages, self.installation_excluded_packages) or \
               self.check_for_match(one_or_more_packages, self.global_excluded_packages)
    # endregion

    # region Package inclusion checks
    def check_for_inclusion(self, package, package_version=Constants.DEFAULT_UNSPECIFIED_VALUE):
        """Return true if package should be included (either because no inclusion list is specified, or because of explicit match)"""
        return not self.is_inclusion_list_present() or self.check_for_explicit_inclusion(package, package_version)

    def check_for_explicit_inclusion(self, package, package_version=Constants.DEFAULT_UNSPECIFIED_VALUE):
        """Return true if package should be included due to an explicit match to the inclusion list """
        return self.check_for_match(package, self.installation_included_packages, package_version, self.installation_included_package_versions)
    # endregion

    # region Inclusion / exclusion common match checker
    def check_for_match(self, one_or_more_packages, matching_list, linked_package_versions=Constants.DEFAULT_UNSPECIFIED_VALUE, version_matching_list=Constants.DEFAULT_UNSPECIFIED_VALUE):
        # type: (str, object, str, object) -> bool  # type hinting to remove a warning
        """Return true if package(s) (with, optionally, linked version(s)) matches the filter list"""
        if matching_list:
            if type(one_or_more_packages) is str:
                return self.single_package_check_for_match(one_or_more_packages, matching_list, linked_package_versions, version_matching_list)
            else:
                for index, each_package in enumerate(one_or_more_packages):
                    if type(linked_package_versions) is str:
                        if self.single_package_check_for_match(each_package, matching_list, linked_package_versions, version_matching_list):
                            return True
                    else:
                        if self.single_package_check_for_match(each_package, matching_list, linked_package_versions[index], version_matching_list):
                            return True
        return False

    def single_package_check_for_match(self, package, matching_list, package_version, version_matching_list):
        """Returns true if a single package (optionally, version) matches the filter list"""
        for index, matching_package in enumerate(matching_list):
            if fnmatch.fnmatch(package, matching_package) or fnmatch.fnmatch(self.get_product_name_without_arch(package), matching_package):
                self.composite_logger.log_debug('    - [Package] {0} matches expression {1}'.format(package, matching_package))
                if package_version == Constants.DEFAULT_UNSPECIFIED_VALUE or not version_matching_list or version_matching_list[index] == Constants.DEFAULT_UNSPECIFIED_VALUE:
                    self.composite_logger.log_debug('    - [Version] Check skipped as not specified.')
                    return True
                elif len(version_matching_list) > index and fnmatch.fnmatch(package_version, version_matching_list[index]):
                    self.composite_logger.log_debug('    - [Version] {0} matches expression {1}'.format(package, version_matching_list[index]))
                    return True
                elif len(version_matching_list) <= index:   # This should never happen - something has gone horribly wrong
                    self.composite_logger.log_error('    - [Version] Index error - ({0} of {1})'.format(index + 1, len(version_matching_list)))
                else:
                    self.composite_logger.log_debug('    - Package {0} (version={1}) was found, but it did not match filter specified for version ({2})'.format(package, package_version, version_matching_list[index]))
        return False

    @staticmethod
    def get_product_name_without_arch(package_name):
        """Splits out product name without architecture - if this is changed, review YumPackageManager"""
        architectures = ['.x86_64', '.noarch', '.i686']
        for arch in architectures:
            if package_name.endswith(arch):
                return package_name.replace(arch, '')
        return package_name
    # endregion

    # region Get included / excluded package masks
    def get_packages_and_versions_from_masks(self, package_masks):
        """Return package names and versions"""
        packages = []
        package_versions = []

        if package_masks is not None:
            for index, package_mask in enumerate(package_masks):
                package_mask_split = str(package_mask).split('=')
                if len(package_mask_split) == 1:        # no version specified
                    packages.append(package_mask_split[0].strip())
                    package_versions.append(Constants.DEFAULT_UNSPECIFIED_VALUE)
                elif len(package_mask_split) == 2:      # version also specified
                    packages.append(package_mask_split[0].strip())
                    package_versions.append(package_mask_split[1].strip())
                else:                                   # invalid format
                    self.composite_logger.log_warning("Invalid package format: " + str(package_mask) + " [Ignored]")

        return packages, package_versions

    @staticmethod
    def sanitize_str_to_list(string_input):
        """Strips excess white-space and converts a comma-separated string to a list"""
        return [] if (string_input is None) else string_input.strip().split(",")
    # endregion

    # region Get installation classifications from execution configuration
    def is_msft_critsec_classification_only(self):
        return ('Critical' in self.installation_included_classifications or 'Security' in self.installation_included_classifications) and 'Other' not in self.installation_included_classifications

    def is_msft_other_classification_only(self):
        return 'Other' in self.installation_included_classifications and not ('Critical' in self.installation_included_classifications or 'Security' in self.installation_included_classifications)

    def is_msft_all_classification_included(self):
        """Returns true if all classifications were individually selected *OR* (nothing was selected AND no inclusion list is present) -- business logic"""
        all_classifications_explicitly_selected = bool((len(self.installation_included_classifications) == len(Constants.PACKAGE_CLASSIFICATIONS) - 1))
        no_classifications_selected = bool(len(self.installation_included_classifications) == 0)
        only_unclassified_selected = bool('Unclassified' in self.installation_included_classifications and len(self.installation_included_classifications) == 1)
        return all_classifications_explicitly_selected or ((no_classifications_selected or only_unclassified_selected) and not self.is_inclusion_list_present())

    def is_invalid_classification_combination(self):
        return ('Other' in self.installation_included_classifications and 'Critical' in self.installation_included_classifications and 'Security' not in self.installation_included_classifications) or \
               ('Other' in self.installation_included_classifications and 'Security' in self.installation_included_classifications and 'Critical' not in self.installation_included_classifications)
    # endregion

# endregion ########## PackageFilter ##########


# region ########## PatchAssessor ##########
class PatchAssessor(object):
    """ Wrapper class of a single patch assessment """
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager):
        self.env_layer = env_layer
        self.execution_config = execution_config

        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.status_handler = status_handler

        self.package_manager = package_manager

    def start_assessment(self):
        """ Start an update assessment """
        self.composite_logger.log('\nStarting patch assessment...')

        self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_TRANSITIONING)
        self.composite_logger.log("\nMachine Id: " + self.env_layer.platform.node())
        self.composite_logger.log("Activity Id: " + self.execution_config.activity_id)
        self.composite_logger.log("Operation request time: " + self.execution_config.start_time)

        self.composite_logger.log("\n\nGetting available patches...")
        self.package_manager.refresh_repo()
        self.status_handler.reset_assessment_data()

        for i in range(0, Constants.MAX_ASSESSMENT_RETRY_COUNT):
            try:
                packages, package_versions = self.package_manager.get_all_updates()
                self.telemetry_writer.send_debug_info("Full assessment: " + str(packages))
                self.status_handler.set_package_assessment_status(packages, package_versions)
                sec_packages, sec_package_versions = self.package_manager.get_security_updates()
                self.telemetry_writer.send_debug_info("Security assessment: " + str(sec_packages))
                self.status_handler.set_package_assessment_status(sec_packages, sec_package_versions, "Security")
                self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)
                break
            except Exception as error:
                if i <= Constants.MAX_ASSESSMENT_RETRY_COUNT:
                    self.composite_logger.log_warning('Retryable error retrieving available patches: ' + repr(error))
                    time.sleep(2*(i + 1))
                else:
                    self.composite_logger.log_error('Error retrieving available patches: ' + repr(error))
                    self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
                    raise

        self.composite_logger.log("\nPatch assessment competed.\n")
        return True

# endregion ########## PatchAssessor ##########


# region ########## PatchInstaller ##########
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
        self.package_filter = package_filter
        self.maintenance_window = maintenance_window
        self.reboot_manager = reboot_manager

        self.last_still_needed_packages = None  # Used for 'Installed' status records
        self.last_still_needed_package_versions = None
        self.progress_template = "[Time available: {0} | A: {1}, S: {2}, F: {3} | D: {4}]\t {5}"

    def start_installation(self, simulate=False):
        """ Kick off a patch installation run """
        self.composite_logger.log('\nStarting patch installation...')

        self.composite_logger.log("\nMachine Id: " + self.env_layer.platform.node())
        self.composite_logger.log("Activity Id: " + self.execution_config.activity_id)
        self.composite_logger.log("Operation request time: " + self.execution_config.start_time + ",               Maintenance Window Duration: " + self.execution_config.duration)

        maintenance_window = self.maintenance_window
        package_manager = self.package_manager
        reboot_manager = self.reboot_manager

        # Early reboot if reboot is allowed by settings and required by the machine
        if package_manager.is_reboot_pending():
            if reboot_manager.is_setting(Constants.REBOOT_NEVER):
                self.composite_logger.log_warning("/!\\ There was a pending reboot on the machine before any package installations started.\n" +
                                                  "    Consider re-running the patch installation after a reboot if any packages fail to install due to this.")
            else:
                self.composite_logger.log_debug("Attempting to reboot the machine prior to patch installation as there is a reboot pending...")
                reboot_manager.start_reboot_if_required_and_time_available(maintenance_window.get_remaining_time_in_minutes(None, False))

        # Install Updates
        installed_update_count, update_run_successful, maintenance_window_exceeded = self.install_updates(maintenance_window, package_manager, simulate)

        # Repeat patch installation if flagged as required and time is available
        if not maintenance_window_exceeded and package_manager.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, False):
            self.composite_logger.log("\nInstalled update count (first round): " + str(installed_update_count))
            self.composite_logger.log("\nPatch installation run will be repeated as the package manager recommended it --------------------------------------------->")
            package_manager.set_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, False)  # Resetting
            new_installed_update_count, update_run_successful, maintenance_window_exceeded = self.install_updates(maintenance_window, package_manager, simulate)
            installed_update_count += new_installed_update_count

            if package_manager.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, False):  # We should not see this again
                raise Exception("Unexpected repeated package manager update occurred. Please re-run the update deployment.")

        self.composite_logger.log("\nInstalled update count: " + str(installed_update_count) + " (including dependencies)")

        # Reboot as per setting and environment state
        reboot_manager.start_reboot_if_required_and_time_available(maintenance_window.get_remaining_time_in_minutes(None, False))
        maintenance_window_exceeded = maintenance_window_exceeded or reboot_manager.maintenance_window_exceeded_flag

        # Combining maintenance
        overall_patch_installation_successful = bool(update_run_successful and not maintenance_window_exceeded)
        if overall_patch_installation_successful:
            self.status_handler.set_installation_substatus_json(status=Constants.STATUS_SUCCESS)
        else:
            self.status_handler.set_installation_substatus_json(status=Constants.STATUS_ERROR)

        return overall_patch_installation_successful

    def install_updates(self, maintenance_window, package_manager, simulate=False):
        """wrapper function of installing updates"""
        self.composite_logger.log("\n\nGetting available updates...")
        package_manager.refresh_repo()

        packages, package_versions = package_manager.get_available_updates(self.package_filter)  # Initial, ignoring exclusions
        self.telemetry_writer.send_debug_info("Initial package list: " + str(packages))

        not_included_packages, not_included_package_versions = self.get_not_included_updates(package_manager, packages)
        self.telemetry_writer.send_debug_info("Not Included package list: " + str(not_included_packages))

        excluded_packages, excluded_package_versions = self.get_excluded_updates(package_manager, packages, package_versions)
        self.telemetry_writer.send_debug_info("Excluded package list: " + str(excluded_packages))

        packages, package_versions = self.filter_out_excluded_updates(packages, package_versions, excluded_packages)  # Final, honoring exclusions
        self.telemetry_writer.send_debug_info("Final package list: " + str(packages))

        # Set initial statuses
        if not package_manager.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, False):  # 'Not included' list is not accurate when a repeat is required
            self.status_handler.set_package_install_status(not_included_packages, not_included_package_versions, Constants.NOT_SELECTED)
        self.status_handler.set_package_install_status(excluded_packages, excluded_package_versions, Constants.EXCLUDED)
        self.status_handler.set_package_install_status(packages, package_versions, Constants.PENDING)
        self.composite_logger.log("\nList of packages to be updated: \n" + str(packages))

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
        self.telemetry_writer.send_debug_info("All available packages list: " + str(all_packages))
        self.last_still_needed_packages = all_packages
        self.last_still_needed_package_versions = all_package_versions

        for package, version in zip(packages, package_versions):
            # Extension state check
            if self.lifecycle_manager is not None:
                self.lifecycle_manager.lifecycle_status_check()     # may terminate the code abruptly, as designed

            # maintenance window check
            remaining_time = maintenance_window.get_remaining_time_in_minutes()
            if maintenance_window.is_package_install_time_available(remaining_time) is False:
                self.composite_logger.log_error("\nStopped patch installation as it is past the maintenance window cutoff time.")
                maintenance_window_exceeded = True
                self.status_handler.set_maintenance_window_exceeded(True)
                break

            # point in time status
            progress_status = self.progress_template.format(str(datetime.timedelta(minutes=remaining_time)), str(attempted_parent_update_count), str(successful_parent_update_count), str(failed_parent_update_count), str(installed_update_count - successful_parent_update_count),
                                                            "Processing package: " + str(package) + " (" + str(version) + ")")
            self.composite_logger.log(progress_status)
            self.telemetry_writer.send_info(progress_status)

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
                    if i <= Constants.MAX_INSTALLATION_RETRY_COUNT:
                        time.sleep(i + 1)
                        self.composite_logger.log_warning("Retrying installation of package. [Package={0}]".format(package_manager.get_product_name(package_and_dependencies[0])))

            if install_result == Constants.FAILED:
                self.status_handler.set_package_install_status(package_manager.get_product_name(package_and_dependencies[0]), package_and_dependency_versions[0], Constants.FAILED)
                failed_parent_update_count += 1
                patch_installation_successful = False
            elif install_result == Constants.INSTALLED:
                self.status_handler.set_package_install_status(package_manager.get_product_name(package_and_dependencies[0]), package_and_dependency_versions[0], Constants.INSTALLED)
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
                    self.status_handler.set_package_install_status(package_manager.get_product_name(str(dependency)), dependency_version, Constants.INSTALLED)
                    index = self.last_still_needed_packages.index(dependency)
                    self.last_still_needed_packages.pop(index)
                    self.last_still_needed_package_versions.pop(index)
                    installed_update_count += 1
                else:
                    # status is not logged by design here, in case you were wondering if that's a bug
                    message = " - [Info] Dependency appears to have failed to install (note: it *may* be retried): " + str(dependency) + "(" + str(dependency_version) + ")"
                    self.composite_logger.log_debug(message)
                    self.telemetry_writer.send_debug_info(message)

            # dependency package result management fallback (not reliable enough to be used as primary, and will be removed; remember to retain last_still_needed refresh when you do that)
            installed_update_count += self.perform_status_reconciliation_conditionally(package_manager, condition=(attempted_parent_update_count % Constants.PACKAGE_STATUS_REFRESH_RATE_IN_SECONDS == 0))  # reconcile status after every 10 attempted installs

        progress_status = self.progress_template.format(str(datetime.timedelta(minutes=maintenance_window.get_remaining_time_in_minutes())), str(attempted_parent_update_count), str(successful_parent_update_count), str(failed_parent_update_count), str(installed_update_count - successful_parent_update_count),
                                                        "Completed processing packages!")
        self.composite_logger.log(progress_status)
        self.telemetry_writer.send_info(progress_status)

        self.composite_logger.log_debug("\nPerforming final system state reconciliation...")
        installed_update_count += self.perform_status_reconciliation_conditionally(package_manager, True)  # final reconciliation

        message = "\n\nOperation status was marked as failed because: "
        message += "[X] a failure occurred during the operation  " if not patch_installation_successful else ""
        message += "[X] maintenance window exceeded " if maintenance_window_exceeded else ""
        self.composite_logger.log_error(message)

        return installed_update_count, patch_installation_successful, maintenance_window_exceeded

    # region Update Run Progress support
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
                successful_packages.append(self.last_still_needed_packages.pop(i))
                successful_package_versions.append(self.last_still_needed_package_versions.pop(i))

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

# endregion ########## PatchInstaller ##########


# region ########## RebootManager ##########
class RebootManager(object):
    """Implements the reboot management logic"""
    def __init__(self, env_layer, execution_config, composite_logger, status_handler, package_manager, default_reboot_setting='IfRequired'):
        self.execution_config = execution_config

        self.composite_logger = composite_logger
        self.package_manager = package_manager
        self.status_handler = status_handler
        self.env_layer = env_layer

        self.minutes_to_shutdown = str((Constants.REBOOT_BUFFER_IN_MINUTES - 5) if (Constants.REBOOT_BUFFER_IN_MINUTES > 5) else Constants.REBOOT_BUFFER_IN_MINUTES)  # give at least 5 minutes for a reboot unless the buffer is configured to be lower than that
        self.reboot_cmd = 'sudo shutdown -r '
        self.maintenance_window_exceeded_flag = False

        self.reboot_setting = self.sanitize_reboot_setting(self.execution_config.reboot_setting, default_reboot_setting)

    @staticmethod
    def is_reboot_time_available(current_time_available):
        """ Check if time still available for system reboot """
        return current_time_available >= Constants.REBOOT_BUFFER_IN_MINUTES

    # REBOOT SETTING
    # ==============
    def sanitize_reboot_setting(self, reboot_setting_key, default_reboot_setting):
        """ Ensures that the value obtained is one we know what to do with. """
        reboot_setting = Constants.REBOOT_SETTINGS[default_reboot_setting]

        try:
            reboot_setting = Constants.REBOOT_SETTINGS[reboot_setting_key]
        except KeyError:
            self.composite_logger.log_error('Invalid reboot setting detected in update configuration: ' + str(reboot_setting_key))
            self.composite_logger.log_warning('Defaulting reboot setting to: ' + str(default_reboot_setting))
        finally:
            return reboot_setting

    def is_setting(self, setting_to_check):
        return self.reboot_setting == setting_to_check

    # REBOOT ACTION
    # =============
    def start_reboot(self, message="Azure Patch Management initiated a reboot after a patch installation run."):
        """ Perform a system reboot """
        self.composite_logger.log("\nThe machine is set to reboot in " + self.minutes_to_shutdown + " minutes.")

        self.status_handler.set_installation_reboot_status(Constants.RebootStatus.STARTED)
        reboot_init_time = self.env_layer.datetime.datetime_utcnow()
        self.env_layer.reboot_machine(self.reboot_cmd + self.minutes_to_shutdown + ' ' + message)

        # Wait for timeout
        max_allowable_time_to_reboot_in_minutes = int(self.minutes_to_shutdown) + Constants.REBOOT_WAIT_TIMEOUT_IN_MINUTES
        while 1:
            current_time = self.env_layer.datetime.datetime_utcnow()
            elapsed_time_in_minutes = self.env_layer.datetime.total_minutes_from_time_delta(current_time - reboot_init_time)
            if elapsed_time_in_minutes >= max_allowable_time_to_reboot_in_minutes:
                self.status_handler.set_installation_reboot_status(Constants.RebootStatus.FAILED)
                raise Exception("Reboot failed to proceed on the machine in a timely manner.")
            else:
                self.composite_logger.log_debug("Waiting for machine reboot. [ElapsedTimeInMinutes={0}] [MaxTimeInMinutes={1}]".format(str(elapsed_time_in_minutes), str(max_allowable_time_to_reboot_in_minutes)))
                time.sleep(60)

    def start_reboot_if_required_and_time_available(self, current_time_available):
        """ Starts a reboot if required. Happens only at the end of the run if required. """
        self.composite_logger.log("\nReboot Management")
        reboot_pending = self.package_manager.is_reboot_pending()

        # return if never
        if self.reboot_setting == Constants.REBOOT_NEVER:
            if reboot_pending:
                self.composite_logger.log_warning(' - There is a reboot pending, but reboot is blocked, as per patch installation configuration. (' + str(Constants.REBOOT_NEVER) + ')')
            else:
                self.composite_logger.log_warning(' - There is no reboot pending, and reboot is blocked regardless, as per patch installation configuration (' + str(Constants.REBOOT_NEVER) + ').')
            return False

        # return if system doesn't require it (and only reboot if it does)
        if self.reboot_setting == Constants.REBOOT_IF_REQUIRED and not reboot_pending:
            self.composite_logger.log(" - There was no reboot pending detected. Reboot is being skipped as it's not required, as per patch installation configuration (" + str(Constants.REBOOT_IF_REQUIRED) + ").")
            return False

        # attempt to reboot is enough time is available
        if self.reboot_setting == Constants.REBOOT_ALWAYS or (self.reboot_setting == Constants.REBOOT_IF_REQUIRED and reboot_pending):
            if self.is_reboot_time_available(current_time_available):
                self.composite_logger.log(' - Reboot is being scheduled, as per patch installation configuration (' + str(self.reboot_setting) + ').')
                self.composite_logger.log(" - Reboot-pending status: " + str(reboot_pending))
                self.start_reboot()
                return True
            else:
                self.composite_logger.log_error(' - There is not enough time to schedule a reboot as per patch installation configuration (' + str(self.reboot_setting) + '). Reboot-pending status: ' + str(reboot_pending))
                self.maintenance_window_exceeded_flag = True
                return False

# endregion ########## RebootManager ##########


# region ########## CompositeLogger ##########
class CompositeLogger(object):
    """ Manages diverting different kinds of output to the right sinks for them. """

    def __init__(self, file_logger=None, current_env=None):
        self.file_logger = file_logger
        self.ERROR = "ERROR:"
        self.WARNING = "WARNING:"
        self.DEBUG = "DEBUG:"
        self.VERBOSE = "VERBOSE:"
        self.current_env = current_env
        self.NEWLINE_REPLACE_CHAR = " "

    @staticmethod
    def log(message):
        """log output"""
        for line in message.splitlines():  # allows the extended file logger to strip unnecessary white space
            print(line)

    def log_error(self, message):
        """log errors"""
        message = self.ERROR + (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        self.log(message)

    def log_warning(self, message):
        """log warning"""
        message = self.WARNING + (self.NEWLINE_REPLACE_CHAR.join(message.split(os.linesep))).strip()
        self.log(message)

    def log_debug(self, message):
        """log debug"""
        message = message.strip()
        if self.current_env in (Constants.DEV, Constants.TEST):
            self.log(self.current_env + ": " + message)  # send to standard output if dev or test env
        elif self.file_logger is not None:
            self.file_logger.write("\n\t" + self.DEBUG + " " + "\n\t".join(message.splitlines()).strip())

    def log_verbose(self, message):
        """log verbose"""
        if self.file_logger is not None:
            self.file_logger.write("\n\t" + self.VERBOSE + " " + "\n\t".join(message.strip().splitlines()).strip())

# endregion ########## CompositeLogger ##########


# region ########## FileLogger ##########
class FileLogger(object):
    """Facilitates writing selected logs to a file"""

    def __init__(self, env_layer, log_file):
        self.env_layer = env_layer
        self.log_file = log_file
        self.log_failure_log_file = log_file + ".failure"
        self.log_file_handle = None
        try:
            self.log_file_handle = self.env_layer.file_system.open(self.log_file, "a+")
        except Exception as error:
            failure_message = "FileLogger - Error opening '" + self.log_file + "': " + repr(error)
            sys.stdout.write(failure_message)
            self.write_irrecoverable_exception(failure_message)
            raise

    def __del__(self):
        self.close()

    def write(self, message, fail_silently=True):
        try:
            if self.log_file_handle is not None:
                self.log_file_handle.write(message)
        except Exception as error:
            # DO NOT write any errors here to stdout
            failure_message = "Fatal exception trying to write to log file: " + repr(error) + ". Attempted message: " + str(message)
            if not fail_silently:
                self.write_irrecoverable_exception(message)
                raise Exception(failure_message)

    def write_irrecoverable_exception(self, message):
        """ A best-effort attempt to write out errors where writing to the primary log file was interrupted"""
        try:
            with self.env_layer.file_system.open(self.log_failure_log_file, 'a+') as fail_log:
                timestamp = self.env_layer.datetime.timestamp()
                fail_log.write("\n" + timestamp + "> " + message)
        except Exception:
           pass

    def flush(self):
        if self.log_file_handle is not None:
            self.log_file_handle.flush()

    def close(self, message_at_close='<Log file was closed.>'):
        if self.log_file_handle is not None:
            if message_at_close is not None:
                self.write(str(message_at_close))
            self.log_file_handle.close()

# endregion ########## FileLogger ##########


# region ########## StdOutFileMirror ##########
class StdOutFileMirror(object):
    """Mirrors all terminal output to a local file"""

    def __init__(self, env_layer, file_logger):
        self.env_layer = env_layer
        self.terminal = sys.stdout  # preserve for recovery
        self.file_logger = file_logger

        if self.file_logger.log_file_handle is not None:
            sys.stdout = self
            sys.stdout.write(str('-'*128))   # provoking an immediate failure if anything is wrong
        else:
            sys.stdout = self.terminal
            sys.stdout.write("WARNING: StdOutFileMirror - Skipping as FileLogger is not initialized")

    def write(self, message):
        self.terminal.write(message)  # enable standard job output

        if len(message.strip()) > 0:
            try:
                timestamp = self.env_layer.datetime.timestamp()
                self.file_logger.write("\n" + timestamp + "> " + message, fail_silently=False)  # also write to the file logger file
            except Exception as error:
                sys.stdout = self.terminal  # suppresses further job output mirror failures
                sys.stdout.write("WARNING: StdOutFileMirror - Error writing to log file: " + repr(error))

    def flush(self):
        pass

    def stop(self):
        sys.stdout = self.terminal

# endregion ########## StdOutFileMirror ##########


# region ########## AptitudePackageManager ##########
class AptitudePackageManager(PackageManager):
    """Implementation of Debian/Ubuntu based package management operations"""

    # For more details, try `man apt-get` on any Debian/Ubuntu based box.
    def __init__(self, env_layer, composite_logger, telemetry_writer):
        super(AptitudePackageManager, self).__init__(env_layer, composite_logger, telemetry_writer)
        # Repo refresh
        self.repo_refresh = 'sudo apt-get -q update'

        # Support to get updates and their dependencies
        self.security_sources_list = '/tmp/az-update-security.list'
        self.prep_security_sources_list_cmd = 'sudo grep security /etc/apt/sources.list > ' + self.security_sources_list
        self.dist_upgrade_simulation_cmd_template = 'LANG=en_US.UTF8 sudo apt-get -s dist-upgrade <SOURCES> '  # Dist-upgrade simulation template - <SOURCES> needs to be replaced before use; sudo is used as sometimes the sources list needs sudo to be readable
        self.single_package_check_versions = 'apt-cache madison <PACKAGE-NAME>'
        self.single_package_find_installed_dpkg = 'sudo dpkg -s <PACKAGE-NAME>'
        self.single_package_find_installed_apt = 'sudo apt list --installed <PACKAGE-NAME>'
        self.single_package_upgrade_simulation_cmd = '''DEBIAN_FRONTEND=noninteractive apt-get -y --only-upgrade true -s install '''
        self.single_package_dependency_resolution_template = 'DEBIAN_FRONTEND=noninteractive LANG=en_US.UTF8 apt-get -y --only-upgrade true -s install <PACKAGE-NAME> '

        # Install update
        # --only-upgrade: upgrade only single package (only if it is installed)
        self.single_package_upgrade_cmd = '''sudo DEBIAN_FRONTEND=noninteractive apt-get -y --only-upgrade true install '''

        # Package manager exit code(s)
        self.apt_exitcode_ok = 0

        # Miscellaneous
        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'  # Avoid a config prompt
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.APT)
        self.STR_DPKG_WAS_INTERRUPTED = "E: dpkg was interrupted, you must manually run 'sudo dpkg --configure -a' to correct the problem."

    def refresh_repo(self):
        self.composite_logger.log("\nRefreshing local repo...")
        self.invoke_package_manager(self.repo_refresh)

    # region Get Available Updates
    def invoke_package_manager(self, command):
        """Get missing updates using the command input"""
        self.composite_logger.log_debug('\nInvoking package manager using: ' + command)
        code, out = self.env_layer.run_command_output(command, False, False)

        if code != self.apt_exitcode_ok and self.STR_DPKG_WAS_INTERRUPTED in out:
            self.composite_logger.log_error('[ERROR] YOU NEED TO TAKE ACTION TO PROCEED. The package manager on this machine is not in a healthy state, and '
                                            'Patch Management cannot proceed successfully. Before the next Patch Operation, please run the following '
                                            'command and perform any configuration steps necessary on the machine to return it to a healthy state: '
                                            'sudo dpkg --configure -a')
            self.telemetry_writer.send_execution_error(command, code, out)
            raise Exception('Package manager on machine is not healthy. To fix, please run: sudo dpkg --configure -a')
        elif code != self.apt_exitcode_ok:
            self.composite_logger.log('[ERROR] Package manager was invoked using: ' + command)
            self.composite_logger.log_warning(" - Return code from package manager: " + str(code))
            self.composite_logger.log_warning(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.telemetry_writer.send_execution_error(command, code, out)
            raise Exception('Unexpected return code (' + str(code) + ') from package manager on command: ' + command)
            # more known return codes should be added as appropriate
        else:  # verbose diagnostic log
            self.composite_logger.log_debug("\n\n==[SUCCESS]===============================================================")
            self.composite_logger.log_debug(" - Return code from package manager: " + str(code))
            self.composite_logger.log_debug(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.composite_logger.log_debug("==========================================================================\n\n")
        return out

    def invoke_apt_cache(self, command):
        """Invoke apt-cache using the command input"""
        self.composite_logger.log_debug('Invoking apt-cache using: ' + command)
        code, out = self.env_layer.run_command_output(command, False, False)
        if code != 0:
            self.composite_logger.log('[ERROR] apt-cache was invoked using: ' + command)
            self.composite_logger.log_warning(" - Return code from apt-cache: " + str(code))
            self.composite_logger.log_warning(" - Output from apt-cache: \n|\t" + "\n|\t".join(out.splitlines()))
            raise Exception('Unexpected return code (' + str(code) + ') from apt-cache on command: ' + command)
            # more known return codes should be added as appropriate
        else:  # verbose diagnostic log
            self.composite_logger.log_debug("\n\n==[SUCCESS]===============================================================")
            self.composite_logger.log_debug(" - Return code from apt-cache: " + str(code))
            self.composite_logger.log_debug(" - Output from apt-cache: \n|\t" + "\n|\t".join(out.splitlines()))
            self.composite_logger.log_debug("==========================================================================\n\n")
        return out

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_debug("\nDiscovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug(" - Returning cached package data.")
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        cmd = self.dist_upgrade_simulation_cmd_template.replace('<SOURCES>', '')
        out = self.invoke_package_manager(cmd)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)

        self.composite_logger.log_debug("Discovered " + str(len(self.all_updates_cached)) + " package entries.")
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates"""
        self.composite_logger.log("\nDiscovering 'security' packages...")
        code, out = self.env_layer.run_command_output(self.prep_security_sources_list_cmd, False, False)
        if code != 0:
            self.composite_logger.log_warning(" - SLP:: Return code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))

        cmd = self.dist_upgrade_simulation_cmd_template.replace('<SOURCES>', '-oDir::Etc::Sourcelist=' + self.security_sources_list)
        out = self.invoke_package_manager(cmd)
        security_packages, security_package_versions = self.extract_packages_and_versions(out)

        self.composite_logger.log("Discovered " + str(len(security_packages)) + " 'security' package entries.")
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates"""
        self.composite_logger.log("\nDiscovering 'other' packages...")
        other_packages = []
        other_package_versions = []

        all_packages, all_package_versions = self.get_all_updates(True)
        security_packages, security_package_versions = self.get_security_updates()

        for index, package in enumerate(all_packages):
            if package not in security_packages:
                other_packages.append(package)
                other_package_versions.append(all_package_versions[index])

        self.composite_logger.log("Discovered " + str(len(other_packages)) + " 'other' package entries.")
        return other_packages, other_package_versions
    # endregion

    # region Output Parser(s)
    def extract_packages_and_versions(self, output):
        # sample output format
        # Inst coreutils [8.25-2ubuntu2] (8.25-2ubuntu3~16.10 Ubuntu:16.10/yakkety-updates [amd64])
        # Inst python3-update-manager [1:16.10.7] (1:16.10.8 Ubuntu:16.10/yakkety-updates [all]) [update-manager-core:amd64 ]
        # Inst update-manager-core [1:16.10.7] (1:16.10.8 Ubuntu:16.10/yakkety-updates [all])

        self.composite_logger.log_debug("\nExtracting package and version data...")
        packages = []
        versions = []

        search_text = r'Inst[ ](.*?)[ ].*?[(](.*?)[ ](.*?)[ ]\[(.*?)\]'
        search = re.compile(search_text, re.M | re.S)
        package_list = search.findall(str(output))

        for package in package_list:
            packages.append(package[0])
            versions.append(package[1])

        self.composite_logger.log_debug("Extracted package and version data for " + str(len(packages)) + " packages.")
        return packages, versions
    # endregion
    # endregion

    # region Install Update
    def get_composite_package_identifier(self, package, package_version):
        return package + '=' + package_version

    def install_updates_fail_safe(self, excluded_packages):
        return
    # endregion

    # region Package Information
    def get_all_available_versions_of_package(self, package_name):
        """ Returns a list of all the available versions of a package """
        # Sample output format
        #      bash | 4.3-14ubuntu1.3 | http://us.archive.ubuntu.com/ubuntu xenial-updates/main amd64 Packages
        #      bash | 4.3-14ubuntu1.2 | http://security.ubuntu.com/ubuntu xenial-security/main amd64 Packages
        #      bash | 4.3-14ubuntu1 | http://us.archive.ubuntu.com/ubuntu xenial/main amd64 Packages

        package_versions = []

        cmd = self.single_package_check_versions.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_apt_cache(cmd)
        lines = output.strip().split('\n')

        for line in lines:
            package_details = line.split(' |')
            if len(package_details) == 3:
                self.composite_logger.log_debug(" - Applicable line: " + str(line))
                package_versions.append(package_details[1].strip())
            else:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))

        return package_versions

    def is_package_version_installed(self, package_name, package_version):
        """ Returns true if the specific package version is installed """

        self.composite_logger.log_debug("\nCHECKING PACKAGE INSTALL STATUS FOR: " + str(package_name) + " (" + str(package_version) + ")")

        # DEFAULT METHOD
        self.composite_logger.log_debug(" - [1/2] Verifying install status with Dpkg.")
        cmd = self.single_package_find_installed_dpkg.replace('<PACKAGE-NAME>', package_name)
        code, output = self.env_layer.run_command_output(cmd, False, False)
        lines = output.strip().split('\n')

        if code == 1:  # usually not found
            # Sample output format ------------------------------------------
            # dpkg-query: package 'mysql-client' is not installed and no information is available
            # Use dpkg --info (= dpkg-deb --info) to examine archive files,
            # and dpkg --contents (= dpkg-deb --contents) to list their contents.
            #  ------------------------------------------ -------------------
            self.composite_logger.log_debug("    - Return code: 1. The package is likely NOT present on the system.")
            for line in lines:
                if 'not installed' in line and package_name in line:
                    self.composite_logger.log_debug("    - Discovered to be not installed: " + str(line))
                    return False
                else:
                    self.composite_logger.log_debug("    - Inapplicable line: " + str(line))

            self.telemetry_writer.send_debug_info("[Installed check] Return code: 1. Unable to verify package not present on the system: " + str(output))
        elif code == 0:  # likely found
            # Sample output format ------------------------------------------
            # Package: mysql-server
            # Status: install ok installed
            # Priority: optional
            # Section: database
            # Installed-Size: 107
            # Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
            # Architecture: all
            # Source: mysql-5.7
            # Version: 5.7.25-0ubuntu0.16.04.2
            # Depends: mysql-server-5.7
            #  ------------------------------------------ --------------------
            self.composite_logger.log_debug("    - Return code: 0. The package is likely present on the system.")
            composite_found_flag = 0
            for line in lines:
                if 'Package: ' in line:
                    if package_name in line:
                        composite_found_flag = composite_found_flag | 1
                    else:  # should never hit for the way this is invoked, hence telemetry
                        self.composite_logger.log_debug("    - Did not match name: " + str(package_name) + " (" + str(line) + ")")
                        self.telemetry_writer.send_debug_info("[Installed check] Name did not match: " + package_name + " (line=" + str(line) + ")(out=" + str(output) + ")")
                    continue
                if 'Version: ' in line:
                    if package_version in line:
                        composite_found_flag = composite_found_flag | 2
                    else:  # should never hit for the way this is invoked, hence telemetry
                        self.composite_logger.log_debug("    - Did not match version: " + str(package_version) + " (" + str(line) + ")")
                        self.telemetry_writer.send_debug_info("[Installed check] Version did not match: " + str(package_version) + " (line=" + str(line) + ")(out=" + str(output) + ")")
                    continue
                if 'Status: ' in line:
                    if 'install ok installed' in line:
                        composite_found_flag = composite_found_flag | 4
                    else:  # should never hit for the way this is invoked, hence telemetry
                        self.composite_logger.log_debug("    - Did not match status: " + str(package_name) + " (" + str(line) + ")")
                        self.telemetry_writer.send_debug_info("[Installed check] Status did not match: 'install ok installed' (line=" + str(line) + ")(out=" + str(output) + ")")
                    continue
                if composite_found_flag & 7 == 7:  # whenever this becomes true, the exact package version is installed
                    self.composite_logger.log_debug("    - Package, Version and Status matched. Package is detected as 'Installed'.")
                    return True
                self.composite_logger.log_debug("    - Inapplicable line: " + str(line))
            self.composite_logger.log_debug("    - Install status check did NOT find the package installed: (composite_found_flag=" + str(composite_found_flag) + ")")
            self.telemetry_writer.send_debug_info("Install status check did NOT find the package installed: (composite_found_flag=" + str(composite_found_flag) + ")(output=" + output + ")")
        else:  # This is not expected to execute. If it does, the details will show up in telemetry. Improve this code with that information.
            self.composite_logger.log_debug("    - Unexpected return code from dpkg: " + str(code) + ". Output: " + str(output))
            self.telemetry_writer.send_debug_info("Unexpected return code from dpkg: Cmd=" + str(cmd) + ". Code=" + str(code) + ". Output=" + str(output))

        # SECONDARY METHOD - Fallback
        # Sample output format
        # Listing... Done
        # apt/xenial-updates,now 1.2.29 amd64 [installed]
        self.composite_logger.log_debug(" - [2/2] Verifying install status with Apt.")
        cmd = self.single_package_find_installed_apt.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        lines = output.strip().split('\n')

        for line in lines:
            package_details = line.split(' ')
            if len(package_details) < 4:
                self.composite_logger.log_debug("    - Inapplicable line: " + str(line))
            else:
                self.composite_logger.log_debug("    - Applicable line: " + str(line))
                discovered_package_name = package_details[0].split('/')[0]  # index out of bounds check is deliberately not being done
                if discovered_package_name != package_name:
                    self.composite_logger.log_debug("      - Did not match name: " + discovered_package_name + " (" + package_name + ")")
                    continue
                if package_details[1] != package_version:
                    self.composite_logger.log_debug("      - Did not match version: " + package_details[1] + " (" + str(package_details[1]) + ")")
                    continue
                if 'installed' not in package_details[3]:
                    self.composite_logger.log_debug("      - Did not find status: " + str(package_details[3] + " (" + str(package_details[3]) + ")"))
                    continue
                self.composite_logger.log_debug("      - Package version specified was determined to be installed.")
                self.telemetry_writer.send_debug_info("[Installed check] Fallback code disagreed with dpkg.")
                return True

        self.composite_logger.log_debug("   - Package version specified was determined to NOT be installed.")
        return False

    def get_dependent_list(self, package_name):
        """Returns dependent List of the package"""
        cmd = self.single_package_dependency_resolution_template.replace('<PACKAGE-NAME>', package_name)

        self.composite_logger.log_debug("\nRESOLVING DEPENDENCIES USING COMMAND: " + str(cmd))
        output = self.invoke_package_manager(cmd)

        packages, package_versions = self.extract_packages_and_versions(output)
        if package_name in packages:
            packages.remove(package_name)

        self.composite_logger.log_debug(str(len(packages)) + " dependent updates were found for package '" + package_name + "'.")
        return packages

    def get_product_name(self, package_name):
        """Retrieve product name """
        return package_name

    def get_package_size(self, output):
        """Retrieve package size from update output string"""
        # Sample line from output:
        # Need to get 0 B/433 kB of archives
        # or
        # Need to get 110 kB of archives.
        try:
            if "is already the newest version" in output:
                return Constants.UNKNOWN_PACKAGE_SIZE
            search_txt = r'Need to get[ ](.*?)[ ]B/(.*?)[ ]of'
            search = re.compile(search_txt, re.M | re.S)
            pkg_list = search.findall(str(output))
            if not pkg_list:
                search_txt = r'Need to get[ ](.*?)[ ]of'
                search = re.compile(search_txt, re.M | re.S)
                pkg_list = search.findall(str(output))
                if not pkg_list or pkg_list[0] == "":
                    return Constants.UNKNOWN_PACKAGE_SIZE
                return pkg_list[0]
            elif pkg_list[0][1] == "":
                return Constants.UNKNOWN_PACKAGE_SIZE
            return pkg_list[0][1]
        except Exception as error:
            self.composite_logger.log_debug(" - Could not get package size from output: " + repr(error))
            return Constants.UNKNOWN_PACKAGE_SIZE
    # endregion

    def do_processes_require_restart(self):
        """Defaulting this for Apt"""
        return False

# endregion ########## AptitudePackageManager ##########


# region ########## YumPackageManager ##########
class YumPackageManager(PackageManager):
    """Implementation of Redhat/CentOS package management operations"""

    def __init__(self, env_layer, composite_logger, telemetry_writer):
        super(YumPackageManager, self).__init__(env_layer, composite_logger, telemetry_writer)
        # Repo refresh
        # There is no command as this is a no op.

        # Support to get updates and their dependencies
        self.yum_check = 'sudo yum -q check-update'
        self.yum_check_security_prerequisite = 'sudo yum -y install yum-plugin-security'
        self.yum_check_security = 'sudo yum -q --security check-update'
        self.single_package_check_versions = 'sudo yum list available <PACKAGE-NAME> --showduplicates'
        self.single_package_check_installed = 'sudo yum list installed <PACKAGE-NAME>'
        self.single_package_upgrade_simulation_cmd = 'LANG=en_US.UTF8 sudo yum install --assumeno '

        # Install update
        self.single_package_upgrade_cmd = 'sudo yum -y install '
        self.all_but_excluded_upgrade_cmd = 'sudo yum -y update --exclude='

        # Package manager exit code(s)
        self.yum_exitcode_no_applicable_packages = 0
        self.yum_exitcode_ok = 1
        self.yum_exitcode_updates_available = 100

        # Support to check for processes requiring restart
        self.yum_utils_prerequisite = 'sudo yum -y install yum-utils'
        self.needs_restarting = 'sudo LANG=en_US.UTF8 needs-restarting'
        self.needs_restarting_with_flag = 'sudo LANG=en_US.UTF8 needs-restarting -r'
        self.yum_ps_prerequisite = 'sudo yum -y install yum-plugin-ps'
        self.yum_ps = 'sudo yum ps'

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.YUM)
        self.STR_TOTAL_DOWNLOAD_SIZE = "Total download size: "

    def refresh_repo(self):
        pass  # Refresh the repo is no ops in YUM

    # region Get Available Updates
    def invoke_package_manager(self, command):
        """Get missing updates using the command input"""
        self.composite_logger.log_debug('\nInvoking package manager using: ' + command)
        code, out = self.env_layer.run_command_output(command, False, False)
        if code not in [self.yum_exitcode_ok, self.yum_exitcode_no_applicable_packages, self.yum_exitcode_updates_available]:
            self.composite_logger.log('[ERROR] Package manager was invoked using: ' + command)
            self.composite_logger.log_warning(" - Return code from package manager: " + str(code))
            self.composite_logger.log_warning(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.telemetry_writer.send_execution_error(command, code, out)
            raise Exception('Unexpected return code (' + str(code) + ') from package manager on command: ' + command)
            # more return codes should be added as appropriate
        else:  # verbose diagnostic log
            self.composite_logger.log_debug("\n\n==[SUCCESS]===============================================================")
            self.composite_logger.log_debug(" - Return code from package manager: " + str(code))
            self.composite_logger.log_debug(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.composite_logger.log_debug("==========================================================================\n\n")
        return out

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_debug("\nDiscovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug(" - Returning cached package data.")
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        out = self.invoke_package_manager(self.yum_check)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)
        self.composite_logger.log_debug("Discovered " + str(len(self.all_updates_cached)) + " package entries.")
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates"""
        self.composite_logger.log("\nDiscovering 'security' packages...")
        self.install_yum_security_prerequisite()
        out = self.invoke_package_manager(self.yum_check_security)
        security_packages, security_package_versions = self.extract_packages_and_versions(out)

        if len(security_packages) == 0 and 'CentOS' in str(self.env_layer.platform.linux_distribution()):   # deliberately non-terminal
            self.composite_logger.log_warning("Classification-based patching is only supported on YUM if the machine is independently configured to receive classification information.")

        self.composite_logger.log("Discovered " + str(len(security_packages)) + " 'security' package entries.")
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates"""
        self.composite_logger.log("\nDiscovering 'other' packages...")
        other_packages = []
        other_package_versions = []

        all_packages, all_package_versions = self.get_all_updates(True)
        security_packages, security_package_versions = self.get_security_updates()
        if len(security_packages) == 0 and 'CentOS' in str(self.env_layer.platform.linux_distribution()):  # deliberately terminal - erring on the side of caution to avoid dissat in uninformed customers
            self.composite_logger.log_error("Please review patch management documentation for information on classification-based patching on YUM.")
            raise Exception("Classification-based patching is only supported on YUM if the computer is independently configured to receive classification information." +
                            "Please remove classifications from update deployments to CentOS machines to bypass this error.")

        for index, package in enumerate(all_packages):
            if package not in security_packages:
                other_packages.append(package)
                other_package_versions.append(all_package_versions[index])

        self.composite_logger.log("Discovered " + str(len(other_packages)) + " 'other' package entries.")
        return other_packages, other_package_versions

    def install_yum_security_prerequisite(self):
        """Not installed by default in versions prior to RHEL 7. This step is idempotent and fast, so we're not writing more complex code."""
        self.composite_logger.log_debug('Ensuring RHEL yum-plugin-security is present.')
        code, out = self.env_layer.run_command_output(self.yum_check_security_prerequisite, False, False)
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output : \n|\t" + "\n|\t".join(out.splitlines()))
    # endregion

    # region Output Parser(s)
    def extract_packages_and_versions(self, output):
        """Returns packages and versions from given output"""
        packages, versions = self.extract_packages_and_versions_including_duplicates(output)
        packages, versions = self.dedupe_update_packages(packages, versions)
        return packages, versions

    def extract_packages_and_versions_including_duplicates(self, output):
        """Returns packages and versions from given output"""
        self.composite_logger.log_debug("\nExtracting package and version data...")
        packages = []
        versions = []
        package_extensions = ['.x86_64', '.noarch', '.i686']

        def is_package(chunk):
            # Using a list comprehension to determine if chunk is a package
            return len([p for p in package_extensions if p in chunk]) == 1

        lines = output.strip().split('\n')

        for line_index in range(0, len(lines)):
            line = re.split(r'\s+', lines[line_index].strip())
            next_line = []

            if line_index < len(lines) - 1:
                next_line = re.split(r'\s+', lines[line_index + 1].strip())

            # If we run into a length of 3, we'll accept it and continue
            if len(line) == 3 and is_package(line[0]):
                packages.append(self.get_product_name(line[0]))
                versions.append(line[1])
            # We will handle these two edge cases where the output is on
            # two different lines and treat them as one line
            elif len(line) == 1 and len(next_line) == 2 and is_package(line[0]):
                packages.append(self.get_product_name(line[0]))
                versions.append(next_line[0])
                line_index += 1
            elif len(line) == 2 and len(next_line) == 1 and is_package(line[0]):
                packages.append(self.get_product_name(line[0]))
                versions.append(line[1])
                line_index += 1
            else:
                self.composite_logger.log_debug(" - Inapplicable line (" + str(line_index) + "): " + lines[line_index])

        return packages, versions
    # endregion
    # endregion

    # region Install Update
    def get_composite_package_identifier(self, package, package_version):
        package_without_arch, arch = self.get_product_name_and_arch(package)
        package_identifier = package_without_arch + '-' + self.get_package_version_without_epoch(package_version)
        if arch is not None:
            package_identifier += arch
        return package_identifier

    def install_updates_fail_safe(self, excluded_packages):
        excluded_string = ""
        for excluded_package in excluded_packages:
            excluded_string += excluded_package + ' '
        cmd = self.all_but_excluded_upgrade_cmd + excluded_string

        self.composite_logger.log_debug("[FAIL SAFE MODE] UPDATING PACKAGES USING COMMAND: " + cmd)
        self.invoke_package_manager(cmd)
    # endregion

    # region Package Information
    def get_all_available_versions_of_package(self, package_name):
        """ Returns a list of all the available versions of a package """
        # Sample output format
        # Available Packages
        # kernel.x86_64                                                                                    3.10.0-862.el7                                                                                         base
        # kernel.x86_64                                                                                    3.10.0-862.2.3.el7                                                                                     updates
        # kernel.x86_64                                                                                    3.10.0-862.3.2.el7                                                                                     updates
        cmd = self.single_package_check_versions.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)
        return package_versions

    def is_package_version_installed(self, package_name, package_version):
        """ Returns true if the specific package version is installed """
        # Loaded plugins: product-id, search-disabled-repos, subscription-manager
        # Installed Packages
        # kernel.x86_64                                                                                   3.10.0-514.el7                                                                                    @anaconda/7.3
        self.composite_logger.log_debug("\nCHECKING PACKAGE INSTALL STATUS FOR: " + str(package_name) + " (" + str(package_version) + ")")
        cmd = self.single_package_check_installed.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        packages, package_versions = self.extract_packages_and_versions_including_duplicates(output)

        for index, package in enumerate(packages):
            if package == package_name and (package_versions[index] == package_version):
                self.composite_logger.log_debug(" - Installed version match found.")
                return True
            else:
                self.composite_logger.log_debug(" - Did not match: " + package + " (" + package_versions[index] + ")")

        # sometimes packages are removed entirely from the system during installation of other packages
        # so let's check that the package is still needed before

        return False

    def get_dependent_list(self, package_name):
        # Sample output for the cmd 'sudo yum update --assumeno selinux-policy.noarch' is :
        #
        # Loaded plugins: langpacks, product-id, search-disabled-repos
        # Resolving Dependencies
        # --> Running transaction check
        # ---> Package selinux-policy.noarch 0:3.13.1-102.el7_3.15 will be updated
        # --> Processing Dependency: selinux-policy = 3.13.1-102.el7_3.15 for \
        # package: selinux-policy-targeted-3.13.1-102.el7_3.15.noarch
        # --> Processing Dependency: selinux-policy = 3.13.1-102.el7_3.15 for \
        # package: selinux-policy-targeted-3.13.1-102.el7_3.15.noarch
        # ---> Package selinux-policy.noarch 0:3.13.1-102.el7_3.16 will be an update
        # --> Running transaction check
        # ---> Package selinux-policy-targeted.noarch 0:3.13.1-102.el7_3.15 will be updated
        # ---> Package selinux-policy-targeted.noarch 0:3.13.1-102.el7_3.16 will be an update
        # --> Finished Dependency Resolution

        self.composite_logger.log_debug("\nRESOLVING DEPENDENCIES USING COMMAND: " + str(self.single_package_upgrade_simulation_cmd + package_name))
        dependent_updates = []

        output = self.invoke_package_manager(self.single_package_upgrade_simulation_cmd + package_name)
        lines = output.strip().split('\n')

        for line in lines:
            if line.find(" will be updated") < 0 and line.find(" will be an update") < 0 and line.find(" will be installed") < 0:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue

            updates_line = re.split(r'\s+', line.strip())
            if len(updates_line) != 7:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue

            dependent_package_name = self.get_product_name(updates_line[2])
            if len(dependent_package_name) != 0 and dependent_package_name != package_name:
                self.composite_logger.log_debug(" - Dependency detected: " + dependent_package_name)
                dependent_updates.append(dependent_package_name)

        self.composite_logger.log_debug(str(len(dependent_updates)) + " dependent updates were found for package '" + package_name + "'.")
        return dependent_updates

    def get_product_name(self, package_name):
        """Retrieve product name including arch where present"""
        return package_name

    def get_product_name_and_arch(self, package_name):
        """Splits out product name and architecture - if this is changed, modify in PackageFilter also"""
        architectures = ['.x86_64', '.noarch', '.i686']
        for arch in architectures:
            if package_name.endswith(arch):
                return package_name[:-len(arch)], arch
        return package_name, None

    def get_product_name_without_arch(self, package_name):
        """Retrieve product name only"""
        product_name, arch = self.get_product_name_and_arch(package_name)
        return product_name

    def get_product_arch(self, package_name):
        """Retrieve product architecture only"""
        product_name, arch = self.get_product_name_and_arch(package_name)
        return arch

    def get_package_version_without_epoch(self, package_version):
        """Returns the package version stripped of any epoch"""
        package_version_split = str(package_version).split(':', 1)

        if len(package_version_split) == 2:
            self.composite_logger.log_debug("   - Removed epoch from version (" + package_version + "): " + package_version_split[1])
            return package_version_split[1]

        if len(package_version_split) != 1:
            self.composite_logger.log_error("Unexpected error during version epoch removal from: " + package_version)

        return package_version

    def get_package_size(self, output):
        """Retrieve package size from installation output string"""
        # Sample output line:
        # Total download size: 15 M
        if "No packages were marked for update" not in output:
            lines = output.strip().split('\n')
            for line in lines:
                if line.find(self.STR_TOTAL_DOWNLOAD_SIZE) >= 0:
                    return line.replace(self.STR_TOTAL_DOWNLOAD_SIZE, "")

        return Constants.UNKNOWN_PACKAGE_SIZE
    # endregion

    def do_processes_require_restart(self):
        """Signals whether processes require a restart due to updates"""

        # Checking using yum-utils
        self.composite_logger.log_debug("Ensuring yum-utils is present.")
        code, out = self.env_layer.run_command_output(self.yum_utils_prerequisite, False, False)  # idempotent, doesn't install if already present
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))

        # Checking for restart for distros with -r flag such as RHEL 7+
        code, out = self.env_layer.run_command_output(self.needs_restarting_with_flag, False, False)
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))
        if out.find("Reboot is required") < 0:
            self.composite_logger.log_debug(" - Reboot not detected to be required (L1).")
        else:
            self.composite_logger.log_debug(" - Reboot is detected to be required (L1).")
            return True

        # Checking for restart for distro without -r flag such as RHEL 6
        code, out = self.env_layer.run_command_output(self.needs_restarting, False, False)
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))
        if len(out.strip()) == 0 and code == 0:
            self.composite_logger.log_debug(" - Reboot not detected to be required (L2).")
        else:
            self.composite_logger.log_debug(" - Reboot is detected to be required (L2).")
            return True

        # Double-checking using yum ps (where available)
        self.composite_logger.log_debug("Ensuring yum-plugin-ps is present.")
        code, out = self.env_layer.run_command_output(self.yum_ps_prerequisite, False, False)  # idempotent, doesn't install if already present
        self.composite_logger.log_debug(" - Code: " + str(code) + ", Output: \n|\t" + "\n|\t".join(out.splitlines()))

        output = self.invoke_package_manager(self.yum_ps)
        lines = output.strip().split('\n')

        process_list_flag = False
        process_count = 0
        process_list_verbose = ""

        for line in lines:
            if not process_list_flag:  # keep going until the process list starts
                if line.find("pid") < 0 and line.find("proc") < 0 and line.find("uptime") < 0:
                    self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                    continue
                else:
                    self.composite_logger.log_debug(" - Process list started: " + str(line))
                    process_list_flag = True
                    continue

            process_details = re.split(r'\s+', line.strip())
            if len(process_details) < 7:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue
            else:
                self.composite_logger.log_debug(" - Applicable line: " + str(line))
                process_count += 1
                process_list_verbose += process_details[1] + " (" + process_details[0] + "), "  # process name and id

            self.composite_logger.log(" - Processes requiring restart (" + str(process_count) + "): [" + process_list_verbose + "<eol>]")
            return process_count != 0  # True if there were anys

# endregion ########## YumPackageManager ##########


# region ########## ZypperPackageManager ##########
class ZypperPackageManager(PackageManager):
    """Implementation of SUSE package management operations"""

    def __init__(self, env_layer, composite_logger, telemetry_writer):
        super(ZypperPackageManager, self).__init__(env_layer, composite_logger, telemetry_writer)
        # Repo refresh
        self.repo_clean = 'sudo zypper clean -a'
        self.repo_refresh = 'sudo zypper refresh'

        # Support to get updates and their dependencies
        self.zypper_check = 'sudo LANG=en_US.UTF8 zypper list-updates'
        self.zypper_check_security = 'sudo LANG=en_US.UTF8 zypper list-patches --category security'
        self.single_package_check_versions = 'LANG=en_US.UTF8 zypper search -s <PACKAGE-NAME>'
        self.single_package_upgrade_simulation_cmd = 'sudo LANG=en_US.UTF8 zypper --non-interactive update --dry-run '
        self.zypper_install_security_patches_simulate = 'sudo LANG=en_US.UTF8 zypper --non-interactive patch --category security --dry-run'

        # Install update
        self.single_package_upgrade_cmd = 'sudo zypper --non-interactive update '
        self.zypper_install_security_patches = 'sudo zypper --non-interactive patch --category security'

        # Package manager exit code(s)
        self.zypper_exitcode_ok = 0
        self.zypper_exitcode_zypper_updated = 103

        # Support to check for processes requiring restart
        self.zypper_ps = "sudo zypper ps -s"

        # Miscellaneous
        self.set_package_manager_setting(Constants.PKG_MGR_SETTING_IDENTITY, Constants.ZYPPER)

    def refresh_repo(self):
        self.composite_logger.log("Refreshing local repo...")
        # self.invoke_package_manager(self.repo_clean)  # purges local metadata for rebuild - addresses a possible customer environment error
        self.invoke_package_manager(self.repo_refresh)

    # region Get Available Updates
    def invoke_package_manager(self, command):
        """Get missing updates using the command input"""
        self.composite_logger.log_debug('\nInvoking package manager using: ' + command)
        code, out = self.env_layer.run_command_output(command, False, False)
        if code not in [self.zypper_exitcode_ok, self.zypper_exitcode_zypper_updated]:  # more known return codes should be added as appropriate
            self.composite_logger.log('[ERROR] Package manager was invoked using: ' + command)
            self.composite_logger.log_warning(" - Return code from package manager: " + str(code))
            self.composite_logger.log_warning(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.telemetry_writer.send_execution_error(command, code, out)
            raise Exception('Unexpected return code (' + str(code) + ') from package manager on command: ' + command)
        else:  # verbose diagnostic log
            self.composite_logger.log_debug("\n\n==[SUCCESS]===============================================================")
            self.composite_logger.log_debug(" - Return code from package manager: " + str(code))
            self.composite_logger.log_debug(" - Output from package manager: \n|\t" + "\n|\t".join(out.splitlines()))
            self.composite_logger.log_debug("==========================================================================\n\n")

        if code == self.zypper_exitcode_zypper_updated:
            self.composite_logger.log_debug(" - Package manager update detected. Patch installation run will be repeated.")
            self.set_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, True)
        return out

    # region Classification-based (incl. All) update check
    def get_all_updates(self, cached=False):
        """Get all missing updates"""
        self.composite_logger.log_debug("\nDiscovering all packages...")
        if cached and not len(self.all_updates_cached) == 0:
            self.composite_logger.log_debug(" - Returning cached package data.")
            return self.all_updates_cached, self.all_update_versions_cached  # allows for high performance reuse in areas of the code explicitly aware of the cache

        out = self.invoke_package_manager(self.zypper_check)
        self.all_updates_cached, self.all_update_versions_cached = self.extract_packages_and_versions(out)
        self.composite_logger.log_debug("Discovered " + str(len(self.all_updates_cached)) + " package entries.")
        return self.all_updates_cached, self.all_update_versions_cached

    def get_security_updates(self):
        """Get missing security updates"""
        self.composite_logger.log_debug("\nDiscovering 'security' packages...")
        security_packages = []
        security_package_versions = []

        # Get all security packages
        out = self.invoke_package_manager(self.zypper_install_security_patches_simulate)
        packages_from_patch_data = self.extract_packages_from_patch_data(out)

        # Correlate and enrich with versions from all package data
        all_packages, all_package_versions = self.get_all_updates(True)

        for index, package in enumerate(all_packages):
            if package in packages_from_patch_data:
                security_packages.append(package)
                security_package_versions.append(all_package_versions[index])
                self.composite_logger.log_debug(" - " + str(package) + " [" + str(all_package_versions[index]) + "]")

        self.composite_logger.log_debug("Discovered " + str(len(security_packages)) + " 'security' package entries.\n")
        return security_packages, security_package_versions

    def get_other_updates(self):
        """Get missing other updates"""
        self.composite_logger.log_debug("\nDiscovering 'other' packages...")
        other_packages = []
        other_package_versions = []

        # Get all security packages
        out = self.invoke_package_manager(self.zypper_install_security_patches_simulate)
        packages_from_patch_data = self.extract_packages_from_patch_data(out)

        # SPECIAL CONDITION IF ZYPPER UPDATE IS DETECTED - UNAVOIDABLE SECURITY UPDATE(S) WILL BE INSTALLED AND THE RUN REPEATED FOR 'OTHER".
        if self.get_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, True):
            self.composite_logger.log_warning("Important: Zypper-related security updates are necessary to continue - those will be installed first.")
            self.composite_logger.log_warning("Temporarily skipping 'other' package entry discovery due to Zypper-related security updates.\n")
            return self.get_security_updates()  # TO DO: in some cases, some misc security updates may sneak in - filter this (to do item)
            # also for above: also note that simply force updating only zypper does not solve the issue - tried

        # Subtract from all package data
        all_packages, all_package_versions = self.get_all_updates(True)

        for index, package in enumerate(all_packages):
            if package not in packages_from_patch_data:
                other_packages.append(package)
                other_package_versions.append(all_package_versions[index])
                self.composite_logger.log_debug(" - " + str(package) + " [" + str(all_package_versions[index]) + "]")

        self.composite_logger.log_debug("Discovered " + str(len(other_packages)) + " 'other' package entries.\n")
        return other_packages, other_package_versions
    # endregion

    # region Output Parser(s)
    def extract_packages_and_versions(self, output):
        """Returns packages and versions from given output"""

        # Sample output for the cmd 'zypper list-updates' is :
        # Loading repository data...
        # Reading installed packages...
        # S | Repository         | Name               | Current Version | Available Version | Arch
        # --+--------------------+--------------------+-----------------+-------------------+-------#
        # v | SLES12-SP2-Updates | kernel-default     | 4.4.38-93.1     | 4.4.49-92.11.1    | x86_64
        # v | SLES12-SP2-Updates | libgoa-1_0-0       | 3.20.4-7.2      | 3.20.5-9.6        | x86_64

        self.composite_logger.log_debug("\nExtracting package and version data...")
        packages = []
        versions = []

        lines = output.strip().split('\n')
        for line in lines:
            line_split = line.split(' | ')
            if len(line_split) == 6 and line_split[1].strip() != 'Repository':
                package = line_split[2].strip()
                packages.append(package)
                version = line_split[4].strip()
                versions.append(version)
                self.composite_logger.log_debug(" - Applicable line: " + line + ". Package: " + package + ". Version: " + version + ".")
            else:
                self.composite_logger.log_debug(" - Inapplicable line: " + line)

        return packages, versions

    def extract_packages_from_patch_data(self, output):
        """Returns packages (sometimes with version information embedded) from patch data"""
        self.composite_logger.log_debug("\nExtracting package entries from security patch data...")
        packages = []
        parser_seeing_packages_flag = False

        lines = output.strip().split('\n')
        for line in lines:
            if "Warning: One of the installed patches affects the package manager itself. Run this command once more to install any other needed patches." in line:
                self.composite_logger.log_debug(" - Package manager requires restart. Patch installation run will be repeated.")
                self.set_package_manager_setting(Constants.PACKAGE_MGR_SETTING_REPEAT_PATCH_OPERATION, True)

            if not parser_seeing_packages_flag:
                if 'package is going to be installed' in line or 'package is going to be upgraded' in line or \
                        'packages are going to be installed:' in line or 'packages are going to be upgraded:' in line:
                    self.composite_logger.log_debug(" - Start marker line: " + line)
                    parser_seeing_packages_flag = True  # Start -- Next line contains information we need
                else:
                    self.composite_logger.log_debug(" - Inapplicable line: " + line)
                continue

            if not line or line.isspace():
                self.composite_logger.log_debug(" - End marker line: " + line)
                parser_seeing_packages_flag = False
                continue  # End -- We're past a package information block

            line_parts = line.strip().split(' ')
            self.composite_logger.log_debug(" - Package list line: " + line)
            for line_part in line_parts:
                packages.append(line_part)
                self.composite_logger.log_debug("    - Package: " + line_part)

        self.composite_logger.log_debug("\nExtracted " + str(len(packages)) + " prospective package entries from security patch data.\n")
        return packages
    # endregion
    # endregion

    # region Install Update
    def get_composite_package_identifier(self, package, package_version):
        return package + '=' + package_version

    def install_updates_fail_safe(self, excluded_packages):
        return
    # endregion

    # region Package Information
    def get_all_available_versions_of_package(self, package_name):
        """ Returns a list of all the available versions of a package that are not already installed """
        return self.get_all_available_versions_of_package_ex(package_name, include_installed=False, include_available=True)

    def is_package_version_installed(self, package_name, package_version):
        """ Returns true if the specific package version is installed """
        self.composite_logger.log_debug("\nCHECKING PACKAGE INSTALL STATUS FOR: " + str(package_name) + "(" + str(package_version) + ")")
        installed_package_versions = self.get_all_available_versions_of_package_ex(package_name, include_installed=True, include_available=False)
        for version in installed_package_versions:
            if version == package_version:
                self.composite_logger.log_debug(" - Installed version match found.")
                return True
            else:
                self.composite_logger.log_debug(" - Did not match: " + str(version))

        return False

    def get_all_available_versions_of_package_ex(self, package_name, include_installed=False, include_available=True):
        """ Returns a list of all the available versions of a package """
        # Sample output format
        # S | Name                    | Type       | Version      | Arch   | Repository
        # --+-------------------------+------------+--------------+--------+-------------------
        # v | bash                    | package    | 4.3-83.5.2   | x86_64 | SLES12-SP2-Updates

        package_versions = []

        self.composite_logger.log_debug("\nGetting all available versions of package '" + package_name + "' [Installed=" + str(include_installed) + ", Available=" + str(include_available) + "]...")
        cmd = self.single_package_check_versions.replace('<PACKAGE-NAME>', package_name)
        output = self.invoke_package_manager(cmd)
        lines = output.strip().split('\n')

        packages_list_flag = False
        for line in lines:
            if not packages_list_flag:  # keep going until the packages list starts
                if not all(word in line for word in ["S", "Name", "Type", "Version", "Arch", "Repository"]):
                    self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                    continue
                else:
                    self.composite_logger.log_debug(" - Package list started: " + str(line))
                    packages_list_flag = True
                    continue

            package_details = line.split(' |')
            if len(package_details) != 6:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue
            else:
                self.composite_logger.log_debug(" - Applicable line: " + str(line))
                details_status = str(package_details[0].strip())
                details_name = str(package_details[1].strip())
                details_type = str(package_details[2].strip())
                details_version = str(package_details[3].strip())

                if details_name != package_name:
                    self.composite_logger.log_debug("    - Excluding as package name doesn't match exactly: " + details_name)
                    continue
                if details_type == "srcpackage":
                    self.composite_logger.log_debug("    - Excluding as package is of type 'srcpackage'.")
                    continue
                if (details_status == "i" or details_status == "i+") and not include_installed:  # exclude installed as (include_installed not selected)
                    self.composite_logger.log_debug("    - Excluding as package version is installed: " + details_version)
                    continue
                if (details_status != "i" and details_status != "i+") and not include_available:  # exclude available as (include_available not selected)
                    self.composite_logger.log_debug("    - Excluding as package version is available: " + details_version)
                    continue

                package_versions.append(details_version)

        return package_versions

    def get_dependent_list(self, package_name):
        # Sample output for the cmd
        # 'sudo  LANG=en_US.UTF8 zypper --non-interactive update --dry-run man' is :
        #
        # Refreshing service 'SMT-http_smt-azure_susecloud_net'.
        # Refreshing service 'cloud_update'.
        # Loading repository data...
        # Reading installed packages...
        # Resolving package dependencies...
        #
        # The following 16 NEW packages are going to be installed:
        #   cups-filters-ghostscript ghostscript ghostscript-fonts-other\
        # ghostscript-fonts-std  ghostscript-x11 groff-full libICE6 libjasper1 libjbig2 libjpeg8
        #  libnetpbm11 libSM6 libtiff5 libXt6 netpbm psutils
        #
        # The following package is going to be upgraded:
        #   man

        # 1 package to upgrade, 16 new.
        # Overall download size: 23.7 MiB. Already cached: 0 B. \
        # After the operation, additional 85.1 MiB will be used.
        # Continue? [y/n/? shows all options] (y): y

        self.composite_logger.log_debug("\nRESOLVING DEPENDENCIES USING COMMAND:: " + str(self.single_package_upgrade_simulation_cmd + package_name))
        dependent_updates = []

        output = self.invoke_package_manager(self.single_package_upgrade_simulation_cmd + package_name)
        lines = output.strip().split('\n')

        for line in lines:
            if line.find(" going to be ") < 0:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue

            updates_line = lines[lines.index(line) + 1]
            dependent_package_names = re.split(r'\s+', updates_line)
            for dependent_package_name in dependent_package_names:
                if len(dependent_package_name) != 0 and dependent_package_name != package_name:
                    self.composite_logger.log_debug(" - Dependency detected: " + dependent_package_name)
                    dependent_updates.append(dependent_package_name)

        self.composite_logger.log_debug(str(len(dependent_updates)) + " dependent updates were found for package '" + package_name + "'.")
        return dependent_updates

    def get_product_name(self, package_name):
        """Retrieve product name """
        return package_name

    def get_package_size(self, output):
        """Retrieve package size from installation output string"""
        # Sample output line:
        # Overall download size: 195.0 KiB. Already cached: 0 B. After the operation, additional 281.0 B will be used.
        try:
            if "Nothing to do." in output:
                return Constants.UNKNOWN_PACKAGE_SIZE
            search_txt = r'Overall download size:[ ](.*?)\.[ ]Already'
            search = re.compile(search_txt, re.M | re.S)
            pkg_list = search.findall(str(output))
            if len(pkg_list) == 0 or pkg_list[0] == "":
                return Constants.UNKNOWN_PACKAGE_SIZE
            return pkg_list[0]
        except Exception as error:
            self.composite_logger.log_debug(" - Could not get package size from output: " + repr(error))
            return Constants.UNKNOWN_PACKAGE_SIZE
    # endregion

    def do_processes_require_restart(self):
        """Signals whether processes require a restart due to updates"""
        output = self.invoke_package_manager(self.zypper_ps)
        lines = output.strip().split('\n')

        process_list_flag = False
        process_count = 0
        process_list_verbose = ""
        for line in lines:
            if not process_list_flag:  # keep going until the process list starts
                if not all(word in line for word in ["PID", "PPID", "UID", "User", "Command", "Service"]):
                    self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                    continue
                else:
                    self.composite_logger.log_debug(" - Process list started: " + str(line))
                    process_list_flag = True
                    continue

            process_details = line.split(' |')
            if len(process_details) < 6:
                self.composite_logger.log_debug(" - Inapplicable line: " + str(line))
                continue
            else:
                self.composite_logger.log_debug(" - Applicable line: " + str(line))
                process_count += 1
                process_list_verbose += process_details[4].strip() + " (" + process_details[0].strip() + "), "  # process name and id

        self.composite_logger.log(" - Processes requiring restart (" + str(process_count) + "): [" + process_list_verbose + "<eol>]")
        return process_count != 0  # True if there were any

# endregion ########## ZypperPackageManager ##########


# region ########## LifecycleManager ##########
class LifecycleManager(object):
    """Class for managing the core code's lifecycle within the extension wrapper"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer):
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer

        # Handshake file paths
        self.ext_state_file_path = os.path.join(self.execution_config.config_folder, Constants.EXT_STATE_FILE)
        self.core_state_file_path = os.path.join(self.execution_config.config_folder, Constants.CORE_STATE_FILE)

    # region - State checkers
    def execution_start_check(self):
        self.composite_logger.log_debug("Execution start check initiating...")
        extension_sequence = self.read_extension_sequence()
        core_sequence = self.read_core_sequence()

        if int(extension_sequence['number']) == int(self.execution_config.sequence_number):
            if core_sequence['completed'] is True:
                # Block attempts to execute what last completed (fully) again
                self.composite_logger.log_warning("LifecycleManager recorded false enable for completed sequence {0}.".format(str(extension_sequence['number'])))
                self.env_layer.exit(0)
            else:
                # Incomplete current execution
                self.composite_logger.log_debug("Restarting execution for incomplete sequence number: {0}.".format(str(self.execution_config.sequence_number)))
        elif int(extension_sequence['number']) < int(self.execution_config.sequence_number):
            # Allow this but log a warning
            self.composite_logger.log_warning("Unexpected lower sequence number: {0} < {1}.".format(str(self.execution_config.sequence_number), str(extension_sequence['number'])))
        else:
            # New sequence number
            self.composite_logger.log_debug("New sequence number accepted for execution: {0} > {1}.".format(str(self.execution_config.sequence_number), str(extension_sequence['number'])))

        self.composite_logger.log_debug("Completed execution start check.")

    def lifecycle_status_check(self):
        self.composite_logger.log_debug("Performing lifecycle status check...")
        extension_sequence = self.read_extension_sequence()
        if int(extension_sequence['number']) == int(self.execution_config.sequence_number):
            self.composite_logger.log_debug("Extension sequence number verified to have not changed: {0}".format(str(extension_sequence['number'])))
        else:
            self.composite_logger.log_error("Extension goal state has changed. Terminating current sequence: {0}".format(self.execution_config.sequence_number))
            self.update_core_sequence(completed=True)   # forced-to-complete scenario | extension wrapper will be watching for this event
            self.env_layer.exit(0)
        self.composite_logger.log_debug("Completed lifecycle status check.")
    # endregion

    # region - State management
    def read_extension_sequence(self):
        self.composite_logger.log_debug("Reading extension sequence...")
        if not os.path.exists(self.ext_state_file_path) or not os.path.isfile(self.ext_state_file_path):
            raise Exception("Extension state file not found.")

        # Read (with retries for only IO Errors)
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.ext_state_file_path, mode="r") as file_handle:
                    return json.load(file_handle)['extensionSequence']
            except Exception as error:
                if i <= Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                    self.composite_logger.log_warning("Exception on extension sequence read. [Exception={0}] [RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i+1)
                else:
                    self.composite_logger.log_error("Unable to read extension state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise

    def read_core_sequence(self):
        self.composite_logger.log_debug("Reading core sequence...")
        if not os.path.exists(self.core_state_file_path) or not os.path.isfile(self.core_state_file_path):
            # Neutralizes directories
            if os.path.isdir(self.core_state_file_path):
                self.composite_logger.log_error("Core state file path returned a directory. Attempting to reset.")
                shutil.rmtree(self.core_state_file_path)
            # Writes a vanilla core sequence file
            self.update_core_sequence()

        # Read (with retries for only IO Errors) - TODO: Refactor common code
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.core_state_file_path, mode="r") as file_handle:
                    core_sequence = json.load(file_handle)['coreSequence']
                    print(str(core_sequence))
                    return core_sequence
            except Exception as error:
                if i <= Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                    self.composite_logger.log_warning("Exception on core sequence read. [Exception={0}] [RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to read core state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise

    def update_core_sequence(self, completed=False):
        self.composite_logger.log_debug("Updating core sequence...")
        core_sequence = {'number': self.execution_config.sequence_number,
                         'action': self.execution_config.operation,
                         'completed': str(completed),
                         'lastHeartbeat': str(self.env_layer.datetime.timestamp()),
                         'processIds': [os.getpid()]}
        core_state_payload = json.dumps({"coreSequence": core_sequence})

        if os.path.isdir(self.core_state_file_path):
            self.composite_logger.log_error("Core state file path returned a directory. Attempting to reset.")
            shutil.rmtree(self.core_state_file_path)

        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.core_state_file_path, 'w+') as file_handle:
                    file_handle.write(core_state_payload)
            except Exception as error:
                if i <= Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                    self.composite_logger.log_warning("Exception on core sequence update. [Exception={0}] [RetryCount={1}]".format(repr(error), str(i)))
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to write to core state file (retries exhausted). [Exception={0}]".format(repr(error)))
                    raise

        self.composite_logger.log_debug("Completed updating core sequence.")
    # endregion

# endregion ########## LifecycleManager ##########


# region ########## StatusHandler ##########
class StatusHandler(object):
    """Class for managing the core code's lifecycle within the extension wrapper"""

    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, package_manager):
        # Map supporting components for operation
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer    # not used immediately but need to know if there are issues persisting status
        self.package_manager = package_manager
        self.status_file_path = self.execution_config.status_file_path

        # Status components
        self.__high_level_status_message = ""

        # Internal in-memory representation of Patch Installation data
        self.__installation_substatus_json = None
        self.__installation_summary_json = None
        self.__installation_packages = []
        self.__maintenance_window_exceeded = False
        self.__installation_reboot_status = Constants.RebootStatus.NOT_NEEDED

        # Internal in-memory representation of Patch Assessment data
        self.__assessment_substatus_json = None
        self.__assessment_summary_json = None
        self.__assessment_packages = []

        # Load the currently persisted status file into memory
        self.__load_status_file_components(initial_load=True)

        # Enable reboot completion status capture
        if self.__installation_reboot_status == Constants.RebootStatus.STARTED:
            self.set_installation_reboot_status(Constants.RebootStatus.COMPLETED)  # switching to completed after the reboot

        # Discovers OS name and version for package id composition
        self.__os_name_and_version = self.get_os_name_and_version()

    # region - Package Data
    def reset_assessment_data(self):
        """ Externally available method to wipe out any assessment package records in memory. """
        self.__assessment_packages = []

    def set_package_assessment_status(self, package_names, package_versions, classification="Other", status="Available"):
        """ Externally available method to set assessment status for one or more packages of the **SAME classification and status** """
        self.composite_logger.log_debug("Setting package assessment status in bulk. [Count={0}]".format(str(len(package_names))))
        for package_name, package_version in zip(package_names, package_versions):
            patch_already_saved = False
            patch_id = self.__get_patch_id(package_name, package_version)
            for i in range(0, len(self.__assessment_packages)):
                if patch_id == self.__assessment_packages[i]['patchId']:
                    patch_already_saved = True
                    self.__assessment_packages[i]['classifications'] = [classification]
                    self.__assessment_packages[i]['patchState'] = status

            if patch_already_saved is False:
                record = {
                    "patchId": str(patch_id),
                    "name": str(package_name),
                    "version": str(package_version),
                    "classifications": [classification]
                    # "patchState": str(status) # Allows for capturing 'Installed' packages in addition to 'Available', when commented out, if spec changes
                }
                self.__assessment_packages.append(record)

        self.set_assessment_substatus_json()

    def set_package_install_status(self, package_names, package_versions, status="Pending", classification=None):
        """ Externally available method to set installation status for one or more packages of the **SAME classification and status** """
        self.composite_logger.log_debug("Setting package installation status in bulk. [Count={0}]".format(str(len(package_names))))
        for package_name, package_version in zip(package_names, package_versions):
            self.composite_logger.log_debug("Logging progress [Package: " + package_name + "; Status: " + status + "]")
            patch_already_saved = False
            patch_id = self.__get_patch_id(package_name, package_version)
            for i in range(0, len(self.__installation_packages)):
                if patch_id == self.__installation_packages[i]['patchId']:
                    patch_already_saved = True
                    if classification is not None:
                        self.__installation_packages[i]['classifications'] = [classification]
                    self.__installation_packages[i]['patchInstallationState'] = status

            if patch_already_saved is False:
                if classification is None:
                    classification = "Other"
                record = {
                    "patchId": str(patch_id),
                    "name": str(package_name),
                    "version": str(package_version),
                    "classifications": [classification],
                    "patchInstallationState": str(status)
                }
                self.__installation_packages.append(record)

        self.set_installation_substatus_json()

    def __get_patch_id(self, package_name, package_version):
        """ Returns normalized patch id """
        return "{0}_{1}_{2}".format(str(package_name), str(package_version), self.__os_name_and_version)

    def get_os_name_and_version(self):
        try:
            if self.env_layer.platform.system() != "Linux":
                raise Exception("Unsupported OS type: {0}.".format(self.env_layer.platform.system()))
            platform_info = self.env_layer.platform.linux_distribution()
            return "{0}_{1}".format(platform_info[0], platform_info[1])
        except Exception as error:
            self.composite_logger.log_error("Unable to determine platform information: {0}".format(repr(error)))
            return "unknownDist_unknownVer"
    # endregion

    # region - Installation Reboot Status
    def set_installation_reboot_status(self, new_reboot_status):
        """ Valid reboot statuses: NotNeeded, Required, Started, Failed, Completed """
        if new_reboot_status not in [Constants.RebootStatus.NOT_NEEDED, Constants.RebootStatus.REQUIRED, Constants.RebootStatus.STARTED, Constants.RebootStatus.FAILED, Constants.RebootStatus.COMPLETED]:
            raise "Invalid reboot status specified. [Status={0}]".format(str(new_reboot_status))

        # State transition validation
        if (new_reboot_status == Constants.RebootStatus.NOT_NEEDED and self.__installation_reboot_status not in [Constants.RebootStatus.NOT_NEEDED])\
                or (new_reboot_status == Constants.RebootStatus.REQUIRED and self.__installation_reboot_status not in [Constants.RebootStatus.NOT_NEEDED, Constants.RebootStatus.REQUIRED, Constants.RebootStatus.COMPLETED])\
                or (new_reboot_status == Constants.RebootStatus.STARTED and self.__installation_reboot_status not in [Constants.RebootStatus.NOT_NEEDED, Constants.RebootStatus.REQUIRED, Constants.RebootStatus.STARTED])\
                or (new_reboot_status == Constants.RebootStatus.FAILED and self.__installation_reboot_status not in [Constants.RebootStatus.STARTED, Constants.RebootStatus.FAILED])\
                or (new_reboot_status == Constants.RebootStatus.COMPLETED and self.__installation_reboot_status not in [Constants.RebootStatus.STARTED, Constants.RebootStatus.COMPLETED]):
            self.composite_logger.log_error("Invalid reboot status transition attempted. [CurrentRebootStatus={0}] [NewRebootStatus={1}]".format(self.__installation_reboot_status, str(new_reboot_status)))
            return

        # Persisting new reboot status (with machine state incorporation)
        self.composite_logger.log_debug("Setting new installation reboot status. [NewRebootStatus={0}] [CurrentRebootStatus={1}]".format(str(new_reboot_status), self.__installation_reboot_status))
        self.__installation_reboot_status = new_reboot_status
        self.__write_status_file()

    def __refresh_installation_reboot_status(self):
        """ Discovers if the system needs a reboot. Never allows going back to NotNeeded (deliberate). ONLY called internally. """
        self.composite_logger.log_debug("Checking if reboot status needs to reflect machine reboot status.")
        if self.__installation_reboot_status in [Constants.RebootStatus.NOT_NEEDED, Constants.RebootStatus.COMPLETED]:
            # Checks only if it's a state transition we allow
            reboot_needed = self.package_manager.is_reboot_pending()
            if reboot_needed:
                self.composite_logger.log_debug("Machine reboot status has changed to 'Required'.")
                self.__installation_reboot_status = Constants.RebootStatus.REQUIRED
    # endregion

    # region - Substatus generation
    def set_maintenance_window_exceeded(self, maintenance_windows_exceeded):
        self.__maintenance_window_exceeded = maintenance_windows_exceeded
        self.__write_status_file()

    def set_assessment_substatus_json(self, status=Constants.STATUS_TRANSITIONING, code=0):
        """ Prepare the assessment substatus json including the message containing assessment summary """
        self.composite_logger.log_debug("Setting assessment substatus. [Substatus={0}]".format(str(status)))

        # Wrap patches into assessment summary
        self.__assessment_summary_json = self.__new_assessment_summary_json(self.__assessment_packages)

        # Wrap assessment summary into assessment substatus
        self.__assessment_substatus_json = self.__new_substatus_json_for_operation(Constants.PATCH_ASSESSMENT_SUMMARY, status, code, json.dumps(self.__assessment_summary_json))

        # Update status on disk
        self.__write_status_file()

    def __new_assessment_summary_json(self, assessment_packages_json):
        """ Called by: set_assessment_substatus_json
            Purpose: This composes the message inside the patch installation summary substatus:
                Root --> Status --> Substatus [name: "PatchAssessmentSummary"] --> FormattedMessage --> **Message** """

        # Calculate summary
        critsec_patch_count = 0
        other_patch_count = 0
        for i in range(0, len(assessment_packages_json)):
            classifications = assessment_packages_json[i]['classifications']
            if "Critical" in classifications or "Security" in classifications:
                critsec_patch_count += 1
            else:
                other_patch_count += 1

        # Compose substatus message
        return {
            "assessmentActivityId": str(self.execution_config.activity_id),
            "rebootPending": self.package_manager.is_reboot_pending(),
            "criticalAndSecurityPatchCount": critsec_patch_count,
            "otherPatchCount": other_patch_count,
            "patches": assessment_packages_json,
            "startTime": str(self.execution_config.start_time),
            "lastModifiedTime": str(self.env_layer.datetime.timestamp()),
            "errors": {"code": 0}  # TODO: Implement this to spec
        }

    def set_installation_substatus_json(self, status=Constants.STATUS_TRANSITIONING, code=0):
        """ Prepare the deployment substatus json including the message containing deployment summary """
        self.composite_logger.log_debug("Setting installation substatus. [Substatus={0}]".format(str(status)))

        # Wrap patches into deployment summary
        self.__installation_summary_json = self.__new_installation_summary_json(self.__installation_packages)

        # Wrap deployment summary into deployment substatus
        self.__installation_substatus_json = self.__new_substatus_json_for_operation(Constants.PATCH_INSTALLATION_SUMMARY, status, code, json.dumps(self.__installation_summary_json))

        # Update status on disk
        self.__write_status_file()

    def __new_installation_summary_json(self, installation_packages_json):
        """ Called by: set_installation_substatus_json
            Purpose: This composes the message inside the patch installation summary substatus:
                Root --> Status --> Substatus [name: "PatchInstallationSummary"] --> FormattedMessage --> **Message** """

        # Calculate summary
        not_selected_patch_count = 0
        excluded_patch_count = 0
        pending_patch_count = 0
        installed_patch_count = 0
        failed_patch_count = 0
        for i in range(0, len(installation_packages_json)):
            patch_installation_state = installation_packages_json[i]['patchInstallationState']
            if patch_installation_state == Constants.NOT_SELECTED:
                not_selected_patch_count += 1
            elif patch_installation_state == Constants.EXCLUDED:
                excluded_patch_count += 1
            elif patch_installation_state == Constants.PENDING:
                pending_patch_count += 1
            elif patch_installation_state == Constants.INSTALLED:
                installed_patch_count += 1
            elif patch_installation_state == Constants.FAILED:
                failed_patch_count += 1
            else:
                self.composite_logger.log_error("Unknown patch state recorded: {0}".format(str(patch_installation_state)))

        # Reboot status refresh
        self.__refresh_installation_reboot_status()

        # Compose substatus message
        return {
            "installationActivityId": str(self.execution_config.activity_id),
            "rebootStatus": str(self.__installation_reboot_status),
            "maintenanceWindowExceeded": self.__maintenance_window_exceeded,
            "notSelectedPatchCount": not_selected_patch_count,
            "excludedPatchCount": excluded_patch_count,
            "pendingPatchCount": pending_patch_count,
            "installedPatchCount": installed_patch_count,
            "failedPatchCount": failed_patch_count,
            "patches": installation_packages_json,
            "startTime": str(self.execution_config.start_time),
            "lastModifiedTime": str(self.env_layer.datetime.timestamp()),
            "errors": {"code": 0}    # TODO: Implement this to spec
        }

    @staticmethod
    def __new_substatus_json_for_operation(operation_name, status="Transitioning", code=0, message=json.dumps("{}")):
        """ Generic substatus for assessment and deployment """
        return {
            "name": str(operation_name),
            "status": str(status).lower(),
            "code": code,
            "formattedMessage": {
                "lang": "en-US",
                "message": str(message)
            }
        }
    # endregion

    # region - Status generation
    def __reset_status_file(self):
        self.env_layer.file_system.write_with_retry(self.status_file_path, '[{0}]'.format(json.dumps(self.__new_basic_status_json())), mode='w+')

    def __new_basic_status_json(self):
        return {
            "version": 1.0,
            "timestampUTC": str(self.env_layer.datetime.timestamp()),
            "status": {
                "name": "Azure Patch Management",
                "operation": str(self.execution_config.operation),
                "status": "success",
                "code": 0,
                "formattedMessage": {
                    "lang": "en-US",
                    "message": ""
                },
                "substatus": []
            }
        }
    # endregion

    # region - Status file read/write
    def __load_status_file_components(self, initial_load=False):
        """ Loads currently persisted status data into memory.
        :param initial_load: If no status file exists AND initial_load is true, a default initial status file is created.
        :return: None
        """

        # Initializing records safely
        self.__installation_substatus_json = None
        self.__installation_summary_json = None
        self.__installation_packages = []
        self.__assessment_substatus_json = None
        self.__assessment_summary_json = None
        self.__assessment_packages = []

        # Verify the status file exists - if not, reset status file
        if not os.path.exists(self.status_file_path) and initial_load:
            self.__reset_status_file()
            return

        # Read the status file - raise exception on persistent failure
        for i in range(0, Constants.MAX_FILE_OPERATION_RETRY_COUNT):
            try:
                with self.env_layer.file_system.open(self.status_file_path, 'r') as file_handle:
                    status_file_data_raw = json.load(file_handle)[0]    # structure is array of 1
            except Exception as error:
                if i <= Constants.MAX_FILE_OPERATION_RETRY_COUNT:
                    time.sleep(i + 1)
                else:
                    self.composite_logger.log_error("Unable to read status file (retries exhausted). Error: {0}.".format(repr(error)))
                    raise

        # Load status data and sanity check structure - raise exception if data loss risk is detected on corrupt data
        try:
            status_file_data = status_file_data_raw
            if 'status' not in status_file_data or 'substatus' not in status_file_data['status']:
                self.composite_logger.log_error("Malformed status file. Resetting status file for safety.")
                self.__reset_status_file()
                return
        except Exception as error:
            self.composite_logger.log_error("Unable to load status file json. Error: {0}; Data: {1}".format(repr(error), str(status_file_data_raw)))
            raise

        # Load portions of data that need to be built on for next write - raise exception if corrupt data is encountered
        self.__high_level_status_message = status_file_data['status']['formattedMessage']['message']
        for i in range(0, len(status_file_data['status']['substatus'])):
            name = status_file_data['status']['substatus'][i]['name']
            if name == Constants.PATCH_INSTALLATION_SUMMARY:     # if it exists, it must be to spec, or an exception will get thrown
                message = status_file_data['status']['substatus'][i]['formattedMessage']['message']
                self.__installation_summary_json = json.loads(message)
                self.__installation_packages = self.__installation_summary_json['patches']
                self.__maintenance_window_exceeded = bool(self.__installation_summary_json['maintenanceWindowExceeded'])
                self.__installation_reboot_status = self.__installation_summary_json['rebootStatus']
            if name == Constants.PATCH_ASSESSMENT_SUMMARY:     # if it exists, it must be to spec, or an exception will get thrown
                message = status_file_data['status']['substatus'][i]['formattedMessage']['message']
                self.__assessment_summary_json = json.loads(message)
                self.__assessment_packages = self.__assessment_summary_json['patches']

    def __write_status_file(self):
        """ Composes and writes the status file from **already up-to-date** in-memory data.
            This is usually the final call to compose and persist after an in-memory data update in a specialized method.

            Pseudo-composition (including steps prior):
            [__new_basic_status_json()]
                assessment_substatus_json == set_assessment_substatus_json()
                    __new_substatus_json_for_operation()
                    __new_assessment_summary_json() with external data --
                        assessment_packages
                        errors

                installation_substatus_json == set_installation_substatus_json
                    __new_substatus_json_for_operation
                    __new_installation_summary_json with external data --
                        installation_packages
                        maintenance_window_exceeded
                        __refresh_installation_reboot_status
                        errors

        :return: None
        """
        status_file_payload = self.__new_basic_status_json()
        status_file_payload['status']['formattedMessage']['message'] = str(self.__high_level_status_message)

        if self.__assessment_substatus_json is not None:
            status_file_payload['status']['substatus'].append(self.__assessment_substatus_json)
        if self.__installation_substatus_json is not None:
            status_file_payload['status']['substatus'].append(self.__installation_substatus_json)

        if os.path.isdir(self.status_file_path):
            self.composite_logger.log_error("Core state file path returned a directory. Attempting to reset.")
            shutil.rmtree(self.status_file_path)

        self.env_layer.file_system.write_with_retry(self.status_file_path, '[{0}]'.format(json.dumps(status_file_payload)), mode='w+')
    # endregion

# endregion ########## StatusHandler ##########


# region ########## TelemetryWriter ##########
class TelemetryWriter(object):
    """Class for writing telemetry data to data transports"""

    def __init__(self, env_layer, execution_config):
        self.data_transports = []
        self.env_layer = env_layer
        self.activity_id = execution_config.activity_id

        # Init state report
        self.send_runbook_state_info('Started Linux patch runbook.')
        self.send_machine_config_info()
        self.send_config_info(execution_config.config_settings, 'execution_config')

    # region Primary payloads
    def send_runbook_state_info(self, state_info):
        # Expected to send up only pivotal runbook state changes
        return self.try_send_message(state_info, Constants.TELEMETRY_OPERATION_STATE)

    def send_config_info(self, config_info, config_type='unknown'):
        # Configuration info
        payload_json = {
            'config_type': config_type,
            'config_value': config_info
        }
        return self.try_send_message(payload_json, Constants.TELEMETRY_CONFIG)

    def send_package_info(self, package_name, package_ver, package_size, install_dur, install_result, code_path, install_cmd, output=''):
        # Package information compiled after the package is attempted to be installed
        max_output_length = 3072
        errors = ""

        # primary payload
        message = {'package_name': str(package_name), 'package_version': str(package_ver),
                   'package_size': str(package_size), 'install_duration': str(install_dur),
                   'install_result': str(install_result), 'code_path': code_path,
                   'install_cmd': str(install_cmd), 'output': str(output)[0:max_output_length]}
        errors += self.try_send_message(message, Constants.TELEMETRY_PACKAGE)

        # additional message payloads for output continuation only if we need it for specific troubleshooting
        if len(output) > max_output_length:
            for i in range(1, int(len(output)/max_output_length) + 1):
                message = {'install_cmd': str(install_cmd), 'output_continuation': str(output)[(max_output_length*i):(max_output_length*(i+1))]}
                errors += self.try_send_message(message, Constants.TELEMETRY_PACKAGE)

        return errors  # if any. Nobody consumes this at the time of this writing.

    def send_error_info(self, error_info):
        # Expected to log significant errors or exceptions
        return self.try_send_message(error_info, Constants.TELEMETRY_ERROR)

    def send_debug_info(self, error_info):
        # Usually expected to instrument possibly problematic code
        return self.try_send_message(error_info, Constants.TELEMETRY_DEBUG)

    def send_info(self, info):
        # Usually expected to be significant runbook output
        return self.try_send_message(info, Constants.TELEMETRY_INFO)
    # endregion

    # Composed payload
    def send_machine_config_info(self):
        # Machine info - sent only once at the start of the run
        machine_info = {
            'platform_name': str(self.env_layer.platform.linux_distribution()[0]),
            'platform_version': str(self.env_layer.platform.linux_distribution()[1]),
            'machine_cpu': self.get_machine_processor(),
            'machine_arch': str(self.env_layer.platform.machine()),
            'disk_type': self.get_disk_type()
        }
        return self.send_config_info(machine_info, 'machine_config')

    def send_execution_error(self, cmd, code, output):
        # Expected to log any errors from a cmd execution, including package manager execution errors
        error_payload = {
            'cmd': str(cmd),
            'code': str(code),
            'output': str(output)[0:3072]
        }
        return self.send_error_info(error_payload)
    # endregion

    # region Transport layer
    def try_send_message(self, message, category=Constants.TELEMETRY_INFO):
        """ Tries to send a message immediately. Returns None if successful. Error message if not."""
        try:
            payload = {'activity_id': str(self.activity_id), 'category': str(category), 'ver': "[%runbook_sub_ver%]", 'message': message}
            payload = json.dumps(payload)[0:4095]
            for transport in self.data_transports:
                transport.write(payload)
            return ""  # for consistency
        except Exception as error:
            return repr(error)  # if the caller cares

    def close_transports(self):
        """Close data transports"""
        self.send_runbook_state_info('Closing telemetry channel(s).')
        for transport in self.data_transports:
            transport.close()
    # endregion

    # region Machine config retrieval methods
    def get_machine_processor(self):
        """Retrieve machine processor info"""
        cmd = "cat /proc/cpuinfo | grep name"
        code, out = self.env_layer.run_command_output(cmd, False, False)

        if out == "" or "not recognized as an internal or external command" in out:
            return "No information found"
        # Example output:
        # model name	: Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz
        lines = out.split("\n")
        return lines[0].split(":")[1].lstrip()

    def get_disk_type(self):
        """ Retrieve disk info """
        cmd = "cat /sys/block/sda/queue/rotational"
        code, out = self.env_layer.run_command_output(cmd, False, False)
        if "1" in out:
            return "Hard drive"
        elif "0" in out:
            return "SSD"
        else:
            return "Unknown"
    # end region

# endregion ########## TelemetryWriter ##########


# region ########## __main__ ##########
if __name__ == "__main__":
    CoreMain(sys.argv)

# endregion ########## __main__ ##########
