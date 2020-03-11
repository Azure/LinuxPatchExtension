import os
import shutil
import tempfile
import unittest
from unittest import mock
from src.Constants import Constants
from src.file_handlers.JsonFileHandler import JsonFileHandler
from src.local_loggers.Logger import Logger
from tests.helpers.VirtualTerminal import VirtualTerminal


class TestJsonFileHandler(unittest.TestCase):

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.logger = Logger()
        self.json_file_handler = JsonFileHandler(self.logger)

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    @mock.patch('src.file_handlers.JsonFileHandler.time.sleep', autospec=True)
    def test_get_json_file_content_success(self, time_sleep):
        file = Constants.EXT_STATE_FILE
        dir_path = os.path.join(os.path.pardir, "tests", "helpers")
        json_content = self.json_file_handler.get_json_file_content(file, dir_path, raise_if_not_found=True)
        self.assertIsNotNone(json_content)
        time_sleep.assert_called_once()

    @mock.patch('src.file_handlers.JsonFileHandler.time.sleep', autospec=True)
    def test_get_json_file_content_failure(self, time_sleep):
        file = Constants.EXT_STATE_FILE
        dir_path = os.path.join(os.path.pardir, "tests", "helper")
        self.assertRaises(Exception, self.json_file_handler.get_json_file_content, file, dir_path, raise_if_not_found=True)
        self.assertEqual(time_sleep.call_count, 5)

        dir_path = os.path.join(os.path.pardir, "tests", "helpers")
        with mock.patch('src.file_handlers.JsonFileHandler.json.loads', autospec=True) as mock_get_content:
            # 1st read trial failed
            time_sleep.call_count = 0
            mock_get_content.call_count = 0
            mock_get_content.side_effect = [OSError, None]
            self.json_file_handler.get_json_file_content(file, dir_path)
            self.assertEqual(time_sleep.call_count, 2)
            self.assertEqual(mock_get_content.call_count, 2)

            # 2nd read trial failed
            time_sleep.call_count = 0
            mock_get_content.call_count = 0
            mock_get_content.side_effect = [OSError, OSError, None]
            self.json_file_handler.get_json_file_content(file, dir_path)
            self.assertEqual(time_sleep.call_count, 3)
            self.assertEqual(mock_get_content.call_count, 3)

            # 3rd read trial failed
            time_sleep.call_count = 0
            mock_get_content.call_count = 0
            mock_get_content.side_effect = [OSError, Exception, OSError, None]
            self.json_file_handler.get_json_file_content(file, dir_path)
            self.assertEqual(time_sleep.call_count, 4)
            self.assertEqual(mock_get_content.call_count, 4)

            # 4th read trial failed
            time_sleep.call_count = 0
            mock_get_content.call_count = 0
            mock_get_content.side_effect = [OSError, Exception, OSError, OSError, None]
            self.json_file_handler.get_json_file_content(file, dir_path)
            self.assertEqual(time_sleep.call_count, 5)
            self.assertEqual(mock_get_content.call_count, 5)

            # All read trial failed, doesn't throw exception
            time_sleep.call_count = 0
            mock_get_content.call_count = 0
            mock_get_content.side_effect = [OSError, Exception, OSError, OSError, OSError]
            json_content = self.json_file_handler.get_json_file_content(file, dir_path, raise_if_not_found=False)
            self.assertEqual(time_sleep.call_count, 5)
            self.assertEqual(mock_get_content.call_count, 5)
            self.assertIsNone(json_content)

            # All read trial failed throws exception
            time_sleep.call_count = 0
            mock_get_content.call_count = 0
            mock_get_content.side_effect = [OSError, Exception, ValueError, OSError, OSError]
            self.assertRaises(Exception, self.json_file_handler.get_json_file_content, file, dir_path, raise_if_not_found=True)
            self.assertEqual(time_sleep.call_count, 5)
            self.assertEqual(mock_get_content.call_count, 5)

    @mock.patch('src.file_handlers.JsonFileHandler.time.sleep', autospec=True)
    def test_create_file_success(self, time_sleep):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file = "test.json"
        content = {'testKey1': 'testVal1',
                   'testKey2': {'testsubKey1': 'testsubVal1'},
                   'testKey3': [{'testsubKey2': 'testsubVal2'}]}
        # create a file
        self.json_file_handler.write_to_json_file(test_dir, file, content)
        self.assertTrue(os.path.exists(os.path.join(test_dir, "test.json")))
        time_sleep.assert_called_once()
        json_content = self.json_file_handler.get_json_file_content(file, test_dir, raise_if_not_found=False)
        self.assertTrue('testKey1' in json_content)
        # Remove the directory after the test
        shutil.rmtree(test_dir)

    @mock.patch('src.file_handlers.JsonFileHandler.time.sleep', autospec=True)
    def test_create_file_failure(self, time_sleep):
        # Create a temporary directory
        test_dir = tempfile.mkdtemp()
        file = "test.json"
        content = {'testKey1': 'testVal1',
                   'testKey2': {'testsubKey1': 'testsubVal1'},
                   'testKey3': [{'testsubKey2': 'testsubVal2'}]}

        self.assertRaises(Exception, self.json_file_handler.write_to_json_file, "test_dir", file, content)
        self.assertEqual(time_sleep.call_count, 0)

        with mock.patch('src.file_handlers.JsonFileHandler.json.dump', autospec=True) as mock_create:
            # 1st read trial failed
            time_sleep.call_count = 0
            mock_create.call_count = 0
            mock_create.side_effect = [OSError, None]
            self.json_file_handler.write_to_json_file(test_dir, file, content)
            self.assertEqual(time_sleep.call_count, 2)
            self.assertEqual(mock_create.call_count, 2)

            # 2nd delete trial failed
            time_sleep.call_count = 0
            mock_create.call_count = 0
            mock_create.side_effect = [OSError, OSError, None]
            self.json_file_handler.write_to_json_file(test_dir, file, content)
            self.assertEqual(time_sleep.call_count, 3)
            self.assertEqual(mock_create.call_count, 3)

            # 3rd delete trial failed
            time_sleep.call_count = 0
            mock_create.call_count = 0
            mock_create.side_effect = [OSError, Exception, OSError, None]
            self.json_file_handler.write_to_json_file(test_dir, file, content)
            self.assertEqual(time_sleep.call_count, 4)
            self.assertEqual(mock_create.call_count, 4)

            # 4th delete trial failed
            time_sleep.call_count = 0
            mock_create.call_count = 0
            mock_create.side_effect = [OSError, Exception, OSError, OSError, None]
            self.json_file_handler.write_to_json_file(test_dir, file, content)
            self.assertEqual(time_sleep.call_count, 5)
            self.assertEqual(mock_create.call_count, 5)

            # All delete trial failed
            time_sleep.call_count = 0
            mock_create.call_count = 0
            mock_create.side_effect = [OSError, Exception, OSError, OSError, OSError]
            self.assertRaises(Exception, self.json_file_handler.write_to_json_file, test_dir, file, content)
            self.assertEqual(time_sleep.call_count, 5)
            self.assertEqual(mock_create.call_count, 5)

        # Remove the directory after the test
        shutil.rmtree(test_dir)

    def test_get_json_config_value_safely(self):
        content = {'testKey1': 'testVal1',
                   'testKey2': {'testsubKey1': 'testsubVal1'},
                   'testKey3': [{'testsubKey2': 'testsubVal2'}]}

        self.assertIsNone(self.json_file_handler.get_json_config_value_safely(None, 'testsubKey1', 'testKey2', raise_if_not_found=True))
        self.assertEqual(self.json_file_handler.get_json_config_value_safely(content, 'testsubKey1', 'testKey2', raise_if_not_found=True), 'testsubVal1')
        self.assertRaises(Exception, self.json_file_handler.get_json_config_value_safely, content, 'testsubKey1', 'testKey3', raise_if_not_found=True)
        self.assertRaises(Exception, self.json_file_handler.get_json_config_value_safely, content, 'testsubKey2', 'testKey3', raise_if_not_found=True)
        self.assertIsNone(self.json_file_handler.get_json_config_value_safely(content, 'testsubKey2', 'testKey3', raise_if_not_found=False))
        self.assertRaises(Exception, self.json_file_handler.get_json_config_value_safely, content, 'testKey1', None, raise_if_not_found=True)

if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(TestJsonFileHandler)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
