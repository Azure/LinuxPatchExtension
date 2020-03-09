"""Unit test for extension HandlerManifest"""
import os
import json
import unittest
from src.Constants import Constants
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestHandlerManifest(unittest.TestCase):
    """Test case to guard against handler manifest changes - not really a unit test"""

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.handler_manifest_file = os.path.join(os.path.pardir, 'src', Constants.HANDLER_MANIFEST_FILE)

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def test_handler_manifest_json(self):
        self.handler_manifest_file_handle = open(self.handler_manifest_file, "r")
        file_contents = self.handler_manifest_file_handle.read()
        handler_json = json.loads(file_contents)
        self.assertEqual(len(handler_json), 1)
        self.assertEqual(handler_json[0]['version'], 1.0)
        self.assertEqual(handler_json[0]['handlerManifest']['disableCommand'], "MsftLinuxUpdateExtShim.sh -d")
        self.assertEqual(handler_json[0]['handlerManifest']['enableCommand'], "MsftLinuxUpdateExtShim.sh -e")
        self.assertEqual(handler_json[0]['handlerManifest']['uninstallCommand'], "MsftLinuxUpdateExtShim.sh -u")
        self.assertEqual(handler_json[0]['handlerManifest']['installCommand'], "MsftLinuxUpdateExtShim.sh -i")
        self.assertEqual(handler_json[0]['handlerManifest']['updateCommand'], "MsftLinuxUpdateExtShim.sh -p")
        self.assertEqual(handler_json[0]['handlerManifest']['rebootAfterInstall'], False)
        self.assertEqual(handler_json[0]['handlerManifest']['reportHeartbeat'], False)
        self.handler_manifest_file_handle.close()


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestHandlerManifest)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
