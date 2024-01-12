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
import json
import os.path
import shutil
import tempfile
import unittest
from extension.src.Constants import Constants
from extension.src.file_handlers.ExtEnvHandler import ExtEnvHandler
from extension.src.local_loggers.FileLogger import FileLogger
from extension.src.local_loggers.Logger import Logger
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestExtEnvHandler(unittest.TestCase):
    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.runtime = RuntimeComposer()
        self.json_file_handler = self.runtime.json_file_handler
        self.env_settings_fields = Constants.EnvSettingsFields

        self.backup_pathexists = os.path.exists
        os.path.exists = self.mock_os_pathexists

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")
        os.path.exists = self.backup_pathexists

    def mock_os_pathexists(self, path):
        return True

    def mock_os_remove(self, file_to_remove):
        raise Exception("File could not be deleted")

    def mock_shutil_rmtree(self, dir_to_remove):
        raise Exception("Directory could not be deleted")

    def __create_ext_env_handler_and_validate_tmp_folder(self, test_dir):
        # Reset os.pathexists that was mocked in setup()
        os.path.exists = self.backup_pathexists

        # create temp folder
        ext_env_settings = [{
            Constants.EnvSettingsFields.version: "1.0",
            Constants.EnvSettingsFields.settings_parent_key: {
                Constants.EnvSettingsFields.log_folder: os.path.join(test_dir, "testLog"),
                Constants.EnvSettingsFields.config_folder: os.path.join(test_dir, "testConfig"),
                Constants.EnvSettingsFields.status_folder: os.path.join(test_dir, "testStatus"),
                Constants.EnvSettingsFields.events_folder_preview: os.path.join(test_dir, "testEventsPreview")
            }
        }]
        file_name = Constants.HANDLER_ENVIRONMENT_FILE
        self.runtime.create_temp_file(test_dir, file_name, content=json.dumps(ext_env_settings))
        ext_env_handler = ExtEnvHandler(self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file_path=test_dir)
        self.assertTrue(ext_env_handler.config_folder is not None)
        self.assertTrue(ext_env_handler.temp_folder is not None)
        self.assertEqual(ext_env_handler.temp_folder, os.path.join(test_dir, "tmp"))

        # add files to tmp folder
        self.runtime.create_temp_file(ext_env_handler.temp_folder, "Test1.list", content='')
        self.runtime.create_temp_file(ext_env_handler.temp_folder, "Test2.list", content='')
        self.assertTrue(os.path.isfile(os.path.join(ext_env_handler.temp_folder, "Test1.list")))
        self.assertTrue(os.path.isfile(os.path.join(ext_env_handler.temp_folder, "Test2.list")))

        return ext_env_handler

    def test_file_read_success(self):
        ext_env_handler = ExtEnvHandler(self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        self.assertTrue(ext_env_handler.log_folder is not None)
        self.assertEqual(ext_env_handler.log_folder, "mockLog")
        self.assertTrue(ext_env_handler.status_folder is not None)
        self.assertTrue(ext_env_handler.temp_folder is not None)
        self.assertEqual(ext_env_handler.temp_folder, "tmp")

    def test_file_read_failure(self):
        # empty file
        test_dir = tempfile.mkdtemp()
        file_name = "test_handler_env.json"
        self.runtime.create_temp_file(test_dir, file_name, content=None)
        self.assertRaises(Exception, ExtEnvHandler, self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file=file_name, handler_env_file_path=test_dir)
        shutil.rmtree(test_dir)

        # invalid file content
        json_content = [{"key1": "value"}, {"key2": "value2"}]
        test_dir = tempfile.mkdtemp()
        file_name = "test_handler_env.json"
        self.runtime.create_temp_file(test_dir, file_name, str(json_content))
        self.assertRaises(Exception, ExtEnvHandler, self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file=file_name, handler_env_file_path=test_dir)
        shutil.rmtree(test_dir)

        # invalid file content
        json_content = [{}]
        test_dir = tempfile.mkdtemp()
        file_name = "test_handler_env.json"
        self.runtime.create_temp_file(test_dir, file_name, str(json_content))
        self.assertRaises(Exception, ExtEnvHandler, self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file=file_name, handler_env_file_path=test_dir)
        shutil.rmtree(test_dir)

    def test_read_event_folder_preview(self):
        ext_env_settings = [{
            Constants.EnvSettingsFields.version: "1.0",
            Constants.EnvSettingsFields.settings_parent_key: {
                Constants.EnvSettingsFields.log_folder: "testLog",
                Constants.EnvSettingsFields.config_folder: "testConfig",
                Constants.EnvSettingsFields.status_folder: "testStatus",
                Constants.EnvSettingsFields.events_folder_preview: "testEventsPreview"
            }
        }]
        test_dir = tempfile.mkdtemp()
        file_name = Constants.HANDLER_ENVIRONMENT_FILE
        self.runtime.create_temp_file(test_dir, file_name, content=json.dumps(ext_env_settings))
        ext_env_handler = ExtEnvHandler(self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file_path=test_dir)
        self.assertTrue(ext_env_handler.log_folder is not None)
        self.assertEqual(ext_env_handler.events_folder, "testEventsPreview")
        shutil.rmtree(test_dir)

    def test_temp_folder_creation_success(self):
        test_dir = tempfile.mkdtemp()
        ext_env_handler = self.__create_ext_env_handler_and_validate_tmp_folder(test_dir)
        shutil.rmtree(test_dir)

    def test_delete_temp_folder_contents_success(self):
        test_dir = tempfile.mkdtemp()
        ext_env_handler = self.__create_ext_env_handler_and_validate_tmp_folder(test_dir)

        # delete temp content
        ext_env_handler.delete_temp_folder_contents()

        # validate files are deleted
        self.assertFalse(os.path.isfile(os.path.join(ext_env_handler.temp_folder, "Test1.list")))
        self.assertFalse(os.path.isfile(os.path.join(ext_env_handler.temp_folder, "Test2.list")))
        shutil.rmtree(test_dir)

    def test_delete_temp_folder_contents_when_none_exists(self):
        ext_env_handler = ExtEnvHandler(self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        self.assertTrue(ext_env_handler.log_folder is not None)
        self.assertEqual(ext_env_handler.log_folder, "mockLog")
        self.assertTrue(ext_env_handler.status_folder is not None)
        self.assertTrue(ext_env_handler.temp_folder is not None)
        self.assertEqual(ext_env_handler.temp_folder, "tmp")

        # Reset os.pathexists that was mocked in setup()
        os.path.exists = self.backup_pathexists
        # delete temp content
        ext_env_handler.delete_temp_folder_contents()

    def test_delete_temp_folder_contents_failure(self):
        test_dir = tempfile.mkdtemp()
        ext_env_handler = self.__create_ext_env_handler_and_validate_tmp_folder(test_dir)

        # mock os.remove()
        self.backup_os_remove = os.remove
        os.remove = self.mock_os_remove

        # delete temp content attempt #1, throws exception
        self.assertRaises(Exception, lambda: ext_env_handler.delete_temp_folder_contents(raise_if_delete_failed=True))
        self.assertTrue(os.path.isfile(os.path.join(ext_env_handler.temp_folder, "Test1.list")))
        self.assertTrue(os.path.isfile(os.path.join(ext_env_handler.temp_folder, "Test2.list")))

        # delete temp content attempt #2, does not throws exception
        ext_env_handler.delete_temp_folder_contents()
        self.assertTrue(os.path.isfile(os.path.join(ext_env_handler.temp_folder, "Test1.list")))
        self.assertTrue(os.path.isfile(os.path.join(ext_env_handler.temp_folder, "Test2.list")))

        # reset os.remove() mock
        os.remove = self.backup_os_remove

        shutil.rmtree(test_dir)

    def test_delete_temp_folder_success(self):
        test_dir = tempfile.mkdtemp()
        ext_env_handler = self.__create_ext_env_handler_and_validate_tmp_folder(test_dir)
        ext_env_handler.delete_temp_folder()
        self.assertFalse(os.path.isdir(os.path.join(ext_env_handler.temp_folder)))
        shutil.rmtree(test_dir)

    def test_delete_temp_folder_when_none_exists(self):
        ext_env_handler = ExtEnvHandler(self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        self.assertTrue(ext_env_handler.log_folder is not None)
        self.assertEqual(ext_env_handler.log_folder, "mockLog")
        self.assertTrue(ext_env_handler.status_folder is not None)
        self.assertTrue(ext_env_handler.temp_folder is not None)
        self.assertEqual(ext_env_handler.temp_folder, "tmp")

        # Reset os.pathexists that was mocked in setup()
        os.path.exists = self.backup_pathexists
        # delete temp content
        ext_env_handler.delete_temp_folder_contents()
        self.assertFalse(os.path.isdir(os.path.join(ext_env_handler.temp_folder)))

    def test_delete_temp_folder_failure(self):
        test_dir = tempfile.mkdtemp()
        ext_env_handler = self.__create_ext_env_handler_and_validate_tmp_folder(test_dir)

        # mock shutil.rmtree()
        self.backup_shutil_rmtree = shutil.rmtree
        shutil.rmtree = self.mock_shutil_rmtree

        # delete temp content attempt #1, throws exception
        self.assertRaises(Exception, lambda: ext_env_handler.delete_temp_folder(raise_if_delete_failed=True))
        self.assertTrue(os.path.isdir(os.path.join(ext_env_handler.temp_folder)))

        # delete temp content attempt #2, does not throws exception
        ext_env_handler.delete_temp_folder()
        self.assertTrue(os.path.isdir(os.path.join(ext_env_handler.temp_folder)))

        # reset shutil.rmtree() mock
        shutil.rmtree = self.backup_shutil_rmtree

        shutil.rmtree(test_dir)

    def test_get_temp_folder_success(self):
        test_dir = tempfile.mkdtemp()
        ext_env_handler = self.__create_ext_env_handler_and_validate_tmp_folder(test_dir)

        # get temp content
        temp_folder_path = ext_env_handler.get_temp_folder()

        # validate path
        self.assertEqual(temp_folder_path, ext_env_handler.temp_folder)

        shutil.rmtree(test_dir)

    def test_get_temp_folder_failure(self):
        ext_env_handler = ExtEnvHandler(self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        self.assertTrue(ext_env_handler.log_folder is not None)
        self.assertEqual(ext_env_handler.log_folder, "mockLog")
        self.assertTrue(ext_env_handler.status_folder is not None)
        self.assertTrue(ext_env_handler.temp_folder is not None)
        self.assertEqual(ext_env_handler.temp_folder, "tmp")

        # Reset os.pathexists that was mocked in setup()
        os.path.exists = self.backup_pathexists
        # get temp content
        self.assertRaises(Exception, lambda: ext_env_handler.get_temp_folder())

    def test_log_temp_folder_success(self):
        test_dir = tempfile.mkdtemp()
        ext_env_handler = self.__create_ext_env_handler_and_validate_tmp_folder(test_dir)
        log_file_path = os.path.join(test_dir, 'test.log')
        file_logger = FileLogger(test_dir, 'test.log')
        ext_env_handler.logger = Logger(file_logger)

        # log temp content
        ext_env_handler.log_temp_folder_details()
        file_logger.close()

        # validate
        file_read = open(log_file_path, "r")
        self.assertTrue(file_read is not None)
        self.assertTrue("Temp folder details: " in file_read.readlines()[1])
        file_read.close()

        shutil.rmtree(test_dir)

    def test_log_temp_folder_failure(self):
        test_dir = tempfile.mkdtemp()
        ext_env_handler = ExtEnvHandler(self.runtime.logger, self.runtime.env_layer, self.json_file_handler, handler_env_file_path=os.path.join(os.path.pardir, "tests", "helpers"))
        log_file_path = os.path.join(test_dir, 'test.log')
        file_logger = FileLogger(test_dir, 'test.log')
        ext_env_handler.logger = Logger(file_logger)
        self.assertTrue(ext_env_handler.log_folder is not None)
        self.assertEqual(ext_env_handler.log_folder, "mockLog")
        self.assertTrue(ext_env_handler.status_folder is not None)
        self.assertTrue(ext_env_handler.temp_folder is not None)
        self.assertEqual(ext_env_handler.temp_folder, "tmp")

        # Reset os.pathexists that was mocked in setup()
        os.path.exists = self.backup_pathexists
        # log temp content
        ext_env_handler.temp_folder = None
        ext_env_handler.log_temp_folder_details()
        file_logger.close()

        # validate
        file_read = open(log_file_path, "r")
        self.assertTrue(file_read is not None)
        self.assertTrue("Temp folder not found" in file_read.readlines()[1])
        file_read.close()

        shutil.rmtree(test_dir)

