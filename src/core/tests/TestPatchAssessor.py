import json
import unittest
from tests.library.ArgumentComposer import ArgumentComposer
from tests.library.RuntimeCompositor import RuntimeCompositor


class TestPatchAssessor(unittest.TestCase):
    def setUp(self):
        self.runtime = RuntimeCompositor(ArgumentComposer().get_composed_arguments(), legacy_mode=True)
        self.container = self.runtime.container

    def tearDown(self):
        self.runtime.stop()

    def test_assessment_success(self):
        self.assertTrue(self.runtime.patch_assessor.start_assessment())

    def test_assessment_fail(self):
        self.runtime.set_legacy_test_type('UnalignedPath')
        self.assertRaises(Exception, self.runtime.patch_assessor.start_assessment)

    def test_get_all_updates_fail(self):
        self.runtime.set_legacy_test_type('UnalignedPath')
        self.assertRaises(Exception, self.runtime.package_manager.get_all_updates)

    def test_get_all_security_updates_fail(self):
        self.runtime.set_legacy_test_type('UnalignedPath')
        self.assertRaises(Exception, self.runtime.package_manager.get_security_updates)

    def test_assessment_fail_with_status_update(self):
        self.runtime.package_manager.refresh_repo = self.mock_refresh_repo
        self.runtime.set_legacy_test_type('UnalignedPath')
        self.runtime.patch_assessor.start_assessment()
        with open(self.runtime.execution_config.status_file_path, 'r') as file_handle:
            file_contents = json.loads(file_handle.read())
            self.assertTrue('Unexpected return code (100) from package manager on command: LANG=en_US.UTF8 sudo apt-get -s dist-upgrade' in str(file_contents))

    def mock_refresh_repo(self):
        pass

if __name__ == '__main__':
    unittest.main()
