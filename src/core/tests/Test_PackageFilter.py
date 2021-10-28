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
import unittest
from core.tests.library.ArgumentComposer import ArgumentComposer
from core.tests.library.RuntimeCompositor import RuntimeCompositor


class TestPackageFilter(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_exclusions(self):
        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = []
        argument_composer.patches_to_include = []
        argument_composer.patches_to_exclude = ["ssh*", "test"]
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)

        self.assertEqual(runtime.package_filter.is_exclusion_list_present(), True)

        self.assertEqual(runtime.package_filter.check_for_exclusion("ssh"), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("ssh-client"), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("custom-ssh"), False)
        self.assertEqual(runtime.package_filter.check_for_exclusion("test"), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("kernel"), False)

        self.assertEqual(runtime.package_filter.check_for_exclusion(["kernel", "firefox"]), False)
        self.assertEqual(runtime.package_filter.check_for_exclusion(["firefox", "ssh-client"]), True)
        runtime.stop()

    def test_exclusions_with_arch(self):
        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = []
        argument_composer.patches_to_include = []
        argument_composer.patches_to_exclude = ["python.i686", "ssh.i686", "all*", "added"]
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)

        self.assertEqual(runtime.package_filter.is_exclusion_list_present(), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("python.x86_64"), False)
        self.assertEqual(runtime.package_filter.check_for_exclusion("python.i686"), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("ssh.i686"), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("all*"), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("added"), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("random"), False)
        runtime.stop()

    def test_exclusions_with_python_arch(self):
        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = []
        argument_composer.patches_to_include = []
        argument_composer.patches_to_exclude = ["python", "ssh.i686", "all*", "added"]
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)

        self.assertEqual(runtime.package_filter.is_exclusion_list_present(), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("python.x86_64"), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("python.i686"), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("python.test"), False)
        self.assertEqual(runtime.package_filter.check_for_exclusion("python."), False)
        self.assertEqual(runtime.package_filter.check_for_exclusion("ssh.i686"), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("all"), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("added"), True)
        self.assertEqual(runtime.package_filter.check_for_exclusion("added.v4"), False)
        self.assertEqual(runtime.package_filter.check_for_exclusion("random"), False)
        runtime.stop()

    def test_included_classifications(self):
        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = ['Critical', 'Security']
        argument_composer.patches_to_include = []
        argument_composer.patches_to_exclude = []
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)

        self.assertEqual(runtime.package_filter.is_msft_critsec_classification_only(), True)
        self.assertEqual(runtime.package_filter.is_msft_other_classification_only(), False)
        runtime.stop()

    def test_included_classifications_short_term_accomodations(self):
        # this test should be removed once the accommodations in execution config are removed
        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = ['Security','Other']
        argument_composer.patches_to_include = []
        argument_composer.patches_to_exclude = []
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)

        self.assertEqual(runtime.package_filter.is_invalid_classification_combination(), False)  # this will fail after accommodations are removed.
        self.assertEqual(runtime.package_filter.is_msft_all_classification_included(), True)    # this will fail after accommodations are removed.
        self.assertEqual(runtime.package_filter.is_msft_critsec_classification_only(), False)
        self.assertEqual(runtime.package_filter.is_msft_other_classification_only(), False)
        runtime.stop()

    def test_invalid_classifications(self):
        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = ['Security', "Other"]
        argument_composer.patches_to_include = []
        argument_composer.patches_to_exclude = []
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)

        self.assertEqual(runtime.package_filter.is_invalid_classification_combination(), False)
        runtime.stop()

    def test_with_none_for_classifications(self):
        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = None
        argument_composer.patches_to_include = []
        argument_composer.patches_to_exclude = []
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)

        self.assertEqual(runtime.package_filter.is_invalid_classification_combination(), False)
        runtime.stop()

    def test_inclusions(self):
        argument_composer = ArgumentComposer()
        argument_composer.classifications_to_include = []
        argument_composer.patches_to_include = ["ssh*", "test"]
        argument_composer.patches_to_exclude = []
        runtime = RuntimeCompositor(argument_composer.get_composed_arguments(), True)

        self.assertEqual(runtime.package_filter.is_inclusion_list_present(), True)

        self.assertEqual(runtime.package_filter.check_for_inclusion("ssh"), True)
        self.assertEqual(runtime.package_filter.check_for_inclusion("ssh-client"), True)
        self.assertEqual(runtime.package_filter.check_for_inclusion("custom-ssh"), False)
        self.assertEqual(runtime.package_filter.check_for_inclusion("test"), True)
        self.assertEqual(runtime.package_filter.check_for_inclusion("kernel"), False)

        self.assertEqual(runtime.package_filter.check_for_inclusion(["kernel", "firefox"]), False)
        self.assertEqual(runtime.package_filter.check_for_inclusion(["firefox", "ssh-client"]), True)
        runtime.stop()


if __name__ == '__main__':
    unittest.main()
