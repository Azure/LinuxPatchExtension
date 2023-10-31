# Copyright 2020 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.7+

""" Configuration Factory. This module populates configuration based on package manager and environment detected. """
from __future__ import print_function
import os
from core.src.bootstrap.Constants import Constants
from core.src.bootstrap.EnvLayer import EnvLayer
from core.src.bootstrap.ExitJanitor import ExitJanitor

from core_logic.patch_operators.ConfigurePatchingProcessor import ConfigurePatchingProcessor
from core_logic.CoreExecutionEngine import CoreExecutionEngine
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.src.core_logic.MaintenanceWindow import MaintenanceWindow
from core.src.core_logic.PackageFilter import PackageFilter
from core.src.core_logic.RebootManager import RebootManager
from core_logic.patch_operators.PatchAssessor import PatchAssessor
from core_logic.patch_operators.PatchInstaller import PatchInstaller

from core.src.core_logic.ServiceManager import ServiceManager
from core.src.core_logic.ServiceManager import ServiceInfo
from core.src.core_logic.TimerManager import TimerManager

from core.src.local_loggers.FileLogger import FileLogger
from core.src.local_loggers.CompositeLogger import CompositeLogger

from package_managers.apt.AptPackageManager import AptPackageManager
from package_managers.apt.AptPatchModeManager import AptPatchModeManager
from package_managers.apt.AptSourcesManager import AptSourcesManager
from package_managers.apt.AptHealthManager import AptHealthManager

from package_managers.yum.YumPackageManager import YumPackageManager
from package_managers.yum.YumPatchModeManager import YumPatchModeManager
from package_managers.yum.YumSourcesManager import YumSourcesManager
from package_managers.yum.YumHealthManager import YumHealthManager

from package_managers.zypper.ZypperPackageManager import ZypperPackageManager
from package_managers.zypper.ZypperPatchModeManager import ZypperPatchModeManager
from package_managers.zypper.ZypperSourcesManager import ZypperSourcesManager
from package_managers.zypper.ZypperHealthManager import ZypperHealthManager

from service_interfaces.lifecycle_managers.LifecycleManagerAzure import LifecycleManagerAzure
from service_interfaces.lifecycle_managers.LifecycleManagerArc import LifecycleManagerArc
from core.src.service_interfaces.StatusHandler import StatusHandler
from core.src.service_interfaces.TelemetryWriter import TelemetryWriter


class ConfigurationFactory(object):
    """ Class for generating module definitions. Configuration is list of key value pairs. Please DON'T change key name.
    DI container relies on the key name to find and resolve dependencies. If you do need change it, please make sure to
    update the key name in all places that reference it. """
    def __init__(self, cloud_type, log_file_path, real_record_path, recorder_enabled, emulator_enabled, events_folder, telemetry_supported):
        self.cloud_type = cloud_type

        self.bootstrap_configurations = {
            'prod_config':  self.__new_bootstrap_configuration(Constants.ExecEnv.PROD, log_file_path, real_record_path, recorder_enabled, emulator_enabled, events_folder, telemetry_supported),
            'dev_config':   self.__new_bootstrap_configuration(Constants.ExecEnv.DEV, log_file_path, real_record_path, recorder_enabled, emulator_enabled, events_folder, telemetry_supported),
            'test_config':  self.__new_bootstrap_configuration(Constants.ExecEnv.TEST, log_file_path, real_record_path, recorder_enabled, emulator_enabled, events_folder, telemetry_supported)
        }

        self.configurations = {
            'apt_prod_config':    self.__new_prod_configuration(Constants.APT, AptPackageManager, AptPatchModeManager, AptSourcesManager, AptHealthManager),
            'yum_prod_config':    self.__new_prod_configuration(Constants.YUM, YumPackageManager, YumPatchModeManager, YumSourcesManager, YumHealthManager),
            'zypper_prod_config': self.__new_prod_configuration(Constants.ZYPPER, ZypperPackageManager, ZypperPatchModeManager, ZypperSourcesManager, ZypperHealthManager),

            'apt_dev_config':     self.__new_dev_configuration(Constants.APT, AptPackageManager, AptPatchModeManager, AptSourcesManager, AptHealthManager),
            'yum_dev_config':     self.__new_dev_configuration(Constants.YUM, YumPackageManager, YumPatchModeManager, YumSourcesManager, YumHealthManager),
            'zypper_dev_config':  self.__new_dev_configuration(Constants.ZYPPER, ZypperPackageManager, ZypperPatchModeManager, ZypperSourcesManager, ZypperHealthManager),

            'apt_test_config':    self.__new_test_configuration(Constants.APT, AptPackageManager, AptPatchModeManager, AptSourcesManager, AptHealthManager),
            'yum_test_config':    self.__new_test_configuration(Constants.YUM, YumPackageManager, YumPatchModeManager, YumSourcesManager, YumHealthManager),
            'zypper_test_config': self.__new_test_configuration(Constants.ZYPPER, ZypperPackageManager, ZypperPatchModeManager, ZypperSourcesManager, ZypperHealthManager)
        }

    # region - Configuration Getters
    def get_bootstrap_configuration(self, env):
        """ Get core configuration for bootstrapping the application. """
        if str(env) not in [Constants.ExecEnv.DEV, Constants.ExecEnv.TEST, Constants.ExecEnv.PROD]:
            print ("ERROR: Environment configuration not supported. [Environment={0}]".format(str(env)))
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
        if str(env) not in [Constants.ExecEnv.DEV, Constants.ExecEnv.TEST, Constants.ExecEnv.PROD]:
            raise Exception("ERROR: Environment configuration not supported. [Env={0}]".format(str(env)))

        if str(package_manager_name) not in [Constants.APT, Constants.YUM, Constants.ZYPPER]:
            raise Exception("ERROR: Package manager configuration not supported. [PackageManagerName={0}]".format(str(package_manager_name)))

        configuration_key = str.lower('{0}_{1}_config'.format(str(package_manager_name), str(env)))
        selected_configuration = self.configurations[configuration_key]
        return selected_configuration
    # endregion

    # region - Configuration Builders
    @staticmethod
    def __new_bootstrap_configuration(config_env, log_file_path, real_record_path, recorder_enabled, emulator_enabled, events_folder, telemetry_supported):
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
                'component_args': ['env_layer', 'file_logger'],
                'component_kwargs': {
                    'current_env': config_env,
                    'telemetry_writer': None  # Has to be initialized without telemetry_writer to avoid running into a circular dependency loop. Telemetry writer within composite logger will be set later after telemetry writer has been initialized
                }
            },
            'telemetry_writer': {
                'component': TelemetryWriter,
                'component_args': ['env_layer', 'composite_logger'],
                'component_kwargs': {
                    'events_folder_path': events_folder,
                    'telemetry_supported': telemetry_supported
                }
            }
        }

        if config_env is Constants.ExecEnv.DEV or config_env is Constants.ExecEnv.TEST:
            pass  # modify config as desired

        return configuration

    def __new_prod_configuration(self, package_manager_name, package_manager_component, patch_mode_manager_component, sources_manager_component, health_manager_component):
        """ Base configuration for production environments. """
        configuration = {
            'config_env': Constants.ExecEnv.PROD,
            'package_manager_name': package_manager_name,
            'exit_janitor': {
                'component': ExitJanitor,
                'component_args': ['env_layer', 'execution_config', 'composite_logger'],
                'component_kwargs': {}
            },
            'status_handler': {
                'component': StatusHandler,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'package_manager_name'],
                'component_kwargs': {
                    'cloud_type': self.cloud_type
                }
            },
            'lifecycle_manager': {
                'component': LifecycleManagerAzure if self.cloud_type == Constants.CloudType.AZURE else LifecycleManagerArc,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler'],
                'component_kwargs': {}
            },
            'patch_mode_manager': {
                'component': patch_mode_manager_component,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler', 'package_manager_name'],
                'component_kwargs': {}
            },
            'sources_manager': {
                'component': sources_manager_component,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler', 'package_manager_name'],
                'component_kwargs': {}
            },
            'health_manager': {
                'component': health_manager_component,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler', 'package_manager_name'],
                'component_kwargs': {}
            },
            'package_manager': {
                'component': package_manager_component,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler', 'patch_mode_manager', 'sources_manager', 'health_manager', 'package_manager_name'],
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
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler', 'package_manager', 'lifecycle_manager'],
                'component_kwargs': {}
            },
            'patch_installer': {
                'component': PatchInstaller,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler', 'lifecycle_manager', 'package_manager', 'package_filter', 'maintenance_window', 'reboot_manager'],
                'component_kwargs': {}
            },
            'service_info': {
                'component': ServiceInfo,
                'component_args': [],
                'component_kwargs': {
                    'service_name': Constants.AUTO_ASSESSMENT_SERVICE_NAME,
                    'service_desc': Constants.AUTO_ASSESSMENT_SERVICE_DESC,
                    'service_exec_path': os.path.join(os.path.dirname(os.path.realpath(__file__)), Constants.CORE_AUTO_ASSESS_SH_FILE_NAME)
                }
            },
            'auto_assess_service_manager': {
                'component': ServiceManager,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'service_info'],
                'component_kwargs': {}
            },
            'auto_assess_timer_manager': {
                'component': TimerManager,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'service_info'],
                'component_kwargs': {}
            },
            'configure_patching_processor': {
                'component': ConfigurePatchingProcessor,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler', 'package_manager', 'auto_assess_service_manager', 'auto_assess_timer_manager', 'lifecycle_manager'],
                'component_kwargs': {}
            },
            'maintenance_window': {
                'component': MaintenanceWindow,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'status_handler'],
                'component_kwargs': {}
            },
            'core_execution_engine': {
                'component': CoreExecutionEngine,
                'component_args': ['env_layer', 'execution_config', 'file_logger', 'composite_logger', 'telemetry_writer', 'lifecycle_manager', 'status_handler', 'package_manager', 'configure_patching_processor', 'patch_assessor', 'patch_installer'],
                'component_kwargs': {}
            }
        }
        return configuration

    def __new_dev_configuration(self, package_manager_name, package_manager_component, patch_mode_manager_component, sources_manager_component, health_manager_component):
        """ Base configuration definition for dev. It derives from the production configuration. """
        configuration = self.__new_prod_configuration(package_manager_name, package_manager_component, patch_mode_manager_component, sources_manager_component, health_manager_component)
        configuration['config_env'] = Constants.ExecEnv.DEV
        # perform desired modifications to configuration
        return configuration

    def __new_test_configuration(self, package_manager_name, package_manager_component, patch_mode_manager_component, sources_manager_component, health_manager_component):
        """ Base configuration definition for test. It derives from the production configuration. """
        configuration = self.__new_prod_configuration(package_manager_name, package_manager_component, patch_mode_manager_component, sources_manager_component, health_manager_component)
        configuration['config_env'] = Constants.ExecEnv.TEST
        # perform desired modifications to configuration
        return configuration
    # endregion

