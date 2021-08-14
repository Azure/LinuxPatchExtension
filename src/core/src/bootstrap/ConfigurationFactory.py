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

""" Configure factory. This module populates configuration based on package manager and environment, e.g. TEST/DEV/PROD"""
from __future__ import print_function
import os
from core.src.bootstrap.Constants import Constants
from core.src.bootstrap.EnvLayer import EnvLayer

from core.src.core_logic.ConfigurePatchingProcessor import ConfigurePatchingProcessor
from core.src.core_logic.ExecutionConfig import ExecutionConfig
from core.src.core_logic.MaintenanceWindow import MaintenanceWindow
from core.src.core_logic.PackageFilter import PackageFilter
from core.src.core_logic.RebootManager import RebootManager
from core.src.core_logic.PatchAssessor import PatchAssessor
from core.src.core_logic.PatchInstaller import PatchInstaller

from core.src.core_logic.ServiceManager import ServiceManager
from core.src.core_logic.ServiceManager import ServiceInfo
from core.src.core_logic.TimerManager import TimerManager

from core.src.local_loggers.FileLogger import FileLogger
from core.src.local_loggers.CompositeLogger import CompositeLogger

from core.src.package_managers.AptitudePackageManager import AptitudePackageManager
from core.src.package_managers.YumPackageManager import YumPackageManager
from core.src.package_managers.ZypperPackageManager import ZypperPackageManager

from core.src.service_interfaces.LifecycleManager import LifecycleManager
from core.src.service_interfaces.LifecycleManagerAzure import LifecycleManagerAzure
from core.src.service_interfaces.LifecycleManagerArc import LifecycleManagerArc                                                      
from core.src.service_interfaces.StatusHandler import StatusHandler
from core.src.service_interfaces.TelemetryWriter import TelemetryWriter

try:
    import urllib2 as urlreq   #Python 2.x
except:
    import urllib.request as urlreq   #Python 3.x


class ConfigurationFactory(object):
    """ Class for generating module definitions. Configuration is list of key value pairs. Please DON'T change key name.
    DI container relies on the key name to find and resolve dependencies. If you do need change it, please make sure to
    update the key name in all places that reference it. """
    def __init__(self, log_file_path, real_record_path, recorder_enabled, emulator_enabled, events_folder):
        self.bootstrap_configurations = {
            'prod_config':  self.new_bootstrap_configuration(Constants.PROD, log_file_path, real_record_path, recorder_enabled, emulator_enabled, events_folder),
            'dev_config':   self.new_bootstrap_configuration(Constants.DEV, log_file_path, real_record_path, recorder_enabled, emulator_enabled, events_folder),
            'test_config':  self.new_bootstrap_configuration(Constants.TEST, log_file_path, real_record_path, recorder_enabled, emulator_enabled, events_folder)
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
        
        self.vm_cloud_type = self.get_vm_cloud_type()
        self.lifecycle_manager_component = self.get_lifecycle_manager_component(self.vm_cloud_type)

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
    def new_bootstrap_configuration(config_env, log_file_path, real_record_path, recorder_enabled, emulator_enabled, events_folder):
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
                    'events_folder_path': events_folder
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
                'component': self.lifecycle_manager_component,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer'],
                'component_kwargs': {}
            },
            'status_handler': {
                'component': StatusHandler,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer'],
                'component_kwargs': {
                    'vm_cloud_type': self.vm_cloud_type
                }
            },
            'package_manager': {
                'component': package_manager_component,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler'],
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
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler', 'package_manager','lifecycle_manager'],
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
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'telemetry_writer', 'status_handler', 'package_manager', 'auto_assess_service_manager', 'auto_assess_timer_manager'],
                'component_kwargs': {}
            },
            'maintenance_window': {
                'component': MaintenanceWindow,
                'component_args': ['env_layer', 'execution_config', 'composite_logger', 'status_handler'],
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

    def get_lifecycle_manager_component(self, vm_cloud_type):
        """ finding life cycle manager based on vm and returning component name added in the prod configuration """
        azure_lifecycle_manager_component = LifecycleManagerAzure
        arc_lifecycle_manager_component = LifecycleManagerArc
        if(vm_cloud_type == Constants.VMCloudType.AZURE):
            return azure_lifecycle_manager_component
        elif (vm_cloud_type == Constants.VMCloudType.ARC):
            return arc_lifecycle_manager_component
        
        return azure_lifecycle_manager_component
   
    def get_vm_cloud_type(self):
        """ detects vm type.
        Todo:  how to check this only when it is Auto Assessment operation??? """
        try:
            metadata = "True"
            request = urlreq.Request(Constants.IMDS_END_POINT)
            request.add_header('Metadata',metadata)
            res = urlreq.urlopen(request,timeout=2)

            if(res.getcode() == 200):
                return Constants.VMCloudType.AZURE
            else:
                return Constants.VMCloudType.ARC
        except:
            return Constants.VMCloudType.ARC

    # endregion
