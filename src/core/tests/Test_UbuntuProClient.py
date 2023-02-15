# Copyright 2023 Microsoft Corporation
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

import unittest

from core.src.bootstrap.Constants import Constants
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestUbuntuProClient(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), True, Constants.APT)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def test_install_or_update_pro_is_None(self):
        package_manager = self.container.get('package_manager')
        self.assertIsNone(package_manager.ubuntu_pro_client.install_or_update_pro())

    def test_get_security_updates_is_None(self):
        package_manager = self.container.get('package_manager')
        self.assertIsNone(package_manager.ubuntu_pro_client.get_security_updates())

    def test_get_all_updates_is_None(self):
        package_manager = self.container.get('package_manager')
        self.assertIsNone(package_manager.ubuntu_pro_client.get_all_updates())

    def test_get_other_updates_is_None(self):
        package_manager = self.container.get('package_manager')
        self.assertIsNone(package_manager.ubuntu_pro_client.get_other_updates())


if __name__ == '__main__':
    unittest.main()
