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

"""Non-invasive Dependency Injection Container.
It fills given constructors or component methods
based on their named arguments."""
import sys
from core.src.local_loggers.CompositeLogger import CompositeLogger


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

        major_version = None
        if hasattr(sys.version_info, 'major'):
            major_version = sys.version_info.major
        else:
            major_version = sys.version_info[0]  # python 2.6 doesn't have attributes like 'major' within sys.version_info

        if major_version == 2:
            component_args, vargs, vkw, defaults = inspect.getargspec(component)
        elif major_version == 3:
            component_args, vargs, vkw, defaults, kwonlyargs, kwonlydefaults, annotations = inspect.getfullargspec(component)
        else:
            raise Exception("Unknown version of python encountered.")

        if inspect.ismethod(component) or inspect.isfunction(component):
            component_args = component_args[1:]
        return component_args, defaults

    def reset(self):
        """reset registered dependencies"""
        self.instances = {}
        self.components = {}
