# Copyright 2026 Microsoft Corporation
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

import json
import os
import shutil
import tempfile
import unittest

from core.src.bootstrap.Constants import Constants
from core.tests.library.ExtStatusAsserter import ExtStatusAsserter


class _TestFileSystem(object):
    @staticmethod
    def open(path, mode):
        return open(path, mode)


class _TestEnvLayer(object):
    def __init__(self):
        self.file_system = _TestFileSystem()

# IMPORTANT: THIS CLASS ONLY VALIDATES TEST CODE THAT NEEDS TO RELIABLY RAISE PRODUCT FAILURES IF THEY HAPPEN.
# NONE OF THE TESTS HERE ARE INTENDED TO BE DIRECTLY PRODUCT-FACING.
class TestExtStatusAsserter(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()
        self._env_layer = _TestEnvLayer()

    def tearDown(self):
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _write_status_file(self, substatuses):
        status_file_path = os.path.join(self._temp_dir, "status.json")
        payload = [{"status": {"substatus": substatuses}}]
        with open(status_file_path, "w") as file_handle:
            file_handle.write(json.dumps(payload))
        return status_file_path

    @staticmethod
    def _build_substatus(name, status, message_dict):
        return {
            "name": name,
            "status": status,
            "formattedMessage": {"message": json.dumps(message_dict)}
        }

    def _build_default_substatuses(self):
        configure_message = {
            "patches": [{"name": "pkg1", "classifications": ["Security"], "patchId": "id-123"}],
            "errors": {"details": [{"message": "configure root error"}]},
            "patchModeStatus": {"errors": {"details": [{"message": "patch mode problem"}]}},
            "autoAssessmentStatus": {
                "autoAssessmentState": Constants.AutoAssessmentStates.ENABLED,
                "errors": {"details": [{"message": "auto assessment problem"}]}
            },
            "startedBy": "Platform",
            "automaticOSPatchState": Constants.AutomaticOSPatchStates.DISABLED
        }

        assessment_message = {
            "patches": [{"name": "pkgA", "classifications": ["Critical"], "patchId": "id-A"}],
            "errors": {"details": [{"message": "assessment error"}]},
            "startedBy": "User"
        }

        installation_message = {
            "patches": [{"name": "pkgI", "classifications": ["Security"], "patchId": "id-I"}],
            "errors": {"details": [{"message": "installation error"}]},
            "startedBy": "User"
        }

        healthstore_message = {
            "patchVersion": "v1",
            "shouldReportToHealthStore": True
        }

        return [
            self._build_substatus(Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, assessment_message),
            self._build_substatus(Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS, installation_message),
            self._build_substatus(Constants.CONFIGURE_PATCHING_SUMMARY, Constants.STATUS_SUCCESS, configure_message),
            self._build_substatus(Constants.PATCH_METADATA_FOR_HEALTHSTORE, Constants.STATUS_SUCCESS, healthstore_message)
        ]

    def _create_asserter(self, substatuses):
        status_file_path = self._write_status_file(substatuses)
        return ExtStatusAsserter(status_file_path, self._env_layer)

    def test_constructor_raises_for_unknown_substatus(self):
        substatuses = [
            self._build_substatus("UnknownSummary", Constants.STATUS_SUCCESS, {"errors": {"details": []}})
        ]
        status_file_path = self._write_status_file(substatuses)

        with self.assertRaises(KeyError):
            ExtStatusAsserter(status_file_path, self._env_layer)

    def test_get_default_substatus_expectations_contains_expected_defaults(self):
        defaults = ExtStatusAsserter.get_default_substatus_expectations()

        self.assertEqual(defaults[Constants.CONFIGURE_PATCHING_SUMMARY], Constants.STATUS_SUCCESS)
        self.assertEqual(defaults[Constants.PATCH_ASSESSMENT_SUMMARY], Constants.STATUS_SUCCESS)
        self.assertEqual(defaults[Constants.PATCH_INSTALLATION_SUMMARY], Constants.STATUS_SUCCESS)
        self.assertEqual(defaults[Constants.PATCH_METADATA_FOR_HEALTHSTORE], Constants.STATUS_SUCCESS)

    def test_assert_status_file_substatuses_uses_defaults(self):
        asserter = self._create_asserter(self._build_default_substatuses())
        asserter.assert_status_file_substatuses()

    def test_assert_status_file_substatus_raises_for_unknown_operation(self):
        asserter = self._create_asserter(self._build_default_substatuses())

        with self.assertRaises(KeyError):
            asserter.assert_status_file_substatus("UnknownOperation", Constants.STATUS_SUCCESS)

    def test_assert_status_file_substatus_raises_when_summary_not_present(self):
        substatuses = [
            self._build_substatus(Constants.PATCH_ASSESSMENT_SUMMARY, Constants.STATUS_SUCCESS, {"errors": {"details": []}})
        ]
        asserter = self._create_asserter(substatuses)

        with self.assertRaises(AssertionError):
            asserter.assert_status_file_substatus(Constants.PATCH_INSTALLATION_SUMMARY, Constants.STATUS_SUCCESS)

    def test_assert_status_file_substatus_raises_for_status_mismatch(self):
        asserter = self._create_asserter(self._build_default_substatuses())

        with self.assertRaises(AssertionError):
            asserter.assert_status_file_substatus(Constants.CONFIGURE_PATCHING_SUMMARY, Constants.STATUS_ERROR)

    def test_assert_operation_summary_has_patch_validates_classification_and_patch_id(self):
        asserter = self._create_asserter(self._build_default_substatuses())

        self.assertTrue(asserter.assert_operation_summary_has_patch(Constants.CONFIGURE_PATCHING_SUMMARY, "pkg1", "Security", "id-123"))

    def test_assert_operation_summary_has_patch_raises_when_patch_or_fields_mismatch(self):
        asserter = self._create_asserter(self._build_default_substatuses())

        with self.assertRaises(AssertionError):
            asserter.assert_operation_summary_has_patch(Constants.CONFIGURE_PATCHING_SUMMARY, "pkg1", "Critical")

        with self.assertRaises(AssertionError):
            asserter.assert_operation_summary_has_patch(Constants.CONFIGURE_PATCHING_SUMMARY, "pkg1", patch_id="missing")

        with self.assertRaises(AssertionError):
            asserter.assert_operation_summary_has_patch(Constants.CONFIGURE_PATCHING_SUMMARY, "not-found")

    def test_assert_operation_summary_has_error_validates_sub_level(self):
        asserter = self._create_asserter(self._build_default_substatuses())

        with self.assertRaises(ValueError):
            asserter.assert_operation_summary_has_error(Constants.CONFIGURE_PATCHING_SUMMARY, "error", "invalid-level")

    def test_assert_operation_summary_has_error_for_configure_sub_levels(self):
        asserter = self._create_asserter(self._build_default_substatuses())

        self.assertTrue(asserter.assert_operation_summary_has_error(Constants.CONFIGURE_PATCHING_SUMMARY, "auto assessment", "autoAssessmentStatus"))
        self.assertTrue(asserter.assert_operation_summary_has_error(Constants.CONFIGURE_PATCHING_SUMMARY, "patch mode", "patchModeStatus"))

    def test_assert_operation_summary_has_error_raises_when_error_missing(self):
        asserter = self._create_asserter(self._build_default_substatuses())

        with self.assertRaises(AssertionError):
            asserter.assert_operation_summary_has_error(Constants.PATCH_ASSESSMENT_SUMMARY, "missing error text")

    def test_assert_operation_summary_has_started_by_raises_for_mismatch(self):
        asserter = self._create_asserter(self._build_default_substatuses())

        with self.assertRaises(AssertionError):
            asserter.assert_operation_summary_has_started_by(Constants.CONFIGURE_PATCHING_SUMMARY, "User")

    def test_assert_configure_patching_states_raise_for_mismatch(self):
        asserter = self._create_asserter(self._build_default_substatuses())

        with self.assertRaises(AssertionError):
            asserter.assert_configure_patching_patch_mode_state(Constants.AutomaticOSPatchStates.ENABLED)

        with self.assertRaises(AssertionError):
            asserter.assert_configure_patching_auto_assessment_state(Constants.AutoAssessmentStates.DISABLED)

    def test_assert_healthstore_status_info_validates_reporting_and_patch_version(self):
        asserter = self._create_asserter(self._build_default_substatuses())
        asserter.assert_healthstore_status_info("v1", should_report=True)

        with self.assertRaises(AssertionError):
            asserter.assert_healthstore_status_info("v2", should_report=True)

        substatuses = self._build_default_substatuses()
        substatuses[3] = self._build_substatus(
            Constants.PATCH_METADATA_FOR_HEALTHSTORE,
            Constants.STATUS_SUCCESS,
            {"patchVersion": "v1", "shouldReportToHealthStore": False}
        )
        asserter = self._create_asserter(substatuses)

        asserter.assert_healthstore_status_info("v1", should_report=False)
        with self.assertRaises(AssertionError):
            asserter.assert_healthstore_status_info("v1", should_report=True)


if __name__ == '__main__':
    unittest.main()