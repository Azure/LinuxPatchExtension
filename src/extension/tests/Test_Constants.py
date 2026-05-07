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

import unittest
from extension.src.Constants import Constants


class TestConstants(unittest.TestCase):
    def test_extension_version_alias(self):
        self.assertEqual(Constants.EXTENSION_VERSION, "1.6.64")
        self.assertEqual(Constants.EXT_VERSION, Constants.EXTENSION_VERSION)

    def test_max_runtime_constants_include_units(self):
        self.assertEqual(Constants.ENABLE_MAX_RUNTIME_MINUTES, 3)
        self.assertEqual(Constants.DISABLE_MAX_RUNTIME_MINUTES, 13)

    def test_top_level_error_codes_include_warning(self):
        self.assertEqual(Constants.PatchOperationTopLevelErrorCode.WARNING, 2)
