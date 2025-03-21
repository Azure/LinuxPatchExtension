# Copyright 2025 Microsoft Corporation
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


class TestExecutionConfig(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_healthstoreid_acceptable_format(self):
        argument_composer = ArgumentComposer()
        argument_composer.health_store_id = str("pub_off_sku_2020.09.29")
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.assertTrue(runtime.execution_config.max_patch_publish_date == "20200929T000000Z")
        runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.health_store_id = str("pu_b_off_sk_u_2020.09.29")
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.assertTrue(runtime.execution_config.max_patch_publish_date == "20200929T000000Z")
        runtime.stop()

    def test_healthstoreid_unacceptable_format(self):
        argument_composer = ArgumentComposer()
        argument_composer.health_store_id = str()
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.assertTrue(runtime.execution_config.max_patch_publish_date == str())
        runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.health_store_id = str("pub_off_sku_20.09.29")
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.assertTrue(runtime.execution_config.max_patch_publish_date == str())
        runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.health_store_id = str("pub_off_sku_2020.9.29")
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.assertTrue(runtime.execution_config.max_patch_publish_date == str())
        runtime.stop()

        argument_composer = ArgumentComposer()
        argument_composer.health_store_id = str("pub_off_sk_u2020.09.29")
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True, Constants.YUM)
        self.assertTrue(runtime.execution_config.max_patch_publish_date == str())
        runtime.stop()


if __name__ == '__main__':
    unittest.main()
