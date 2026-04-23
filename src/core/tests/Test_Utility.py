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

from core.src.Utility import Utility


class TestUtility(unittest.TestCase):

    def setUp(self):
        self.utility = Utility()

    def tearDown(self):
        pass

    def test_sanitize_credentials_from_uri_https(self):
        """ Test sanitization of HTTPS URIs with credentials """
        message = "Error connecting to https://testuser:TESTTOKEN123456@invalid.repo.example/rpm/repodata/repomd.xml"
        sanitized = self.utility.sanitize_credentials_from_uri(message)
        expected_message = "Error connecting to https://testuser@invalid.repo.example/rpm/repodata/repomd.xml"
        self.assertEqual(sanitized, expected_message)

    def test_sanitize_credentials_from_uri_http(self):
        """ Test sanitization of HTTP URIs with credentials """
        message = "Connection failed to http://user123:password123@example.com/path"
        sanitized = self.utility.sanitize_credentials_from_uri(message)
        # Password should be removed
        self.assertNotIn("password123", sanitized)
        # Username should be preserved
        self.assertIn("user123@example.com", sanitized)

    def test_sanitize_credentials_multiple_urls(self):
        """ Test sanitization with multiple URLs containing credentials """
        message = "Failed to fetch from https://user1:pass1@host1.com/api and http://user2:pass2@host2.com/data"
        sanitized = self.utility.sanitize_credentials_from_uri(message)
        # Passwords should be removed
        self.assertNotIn("pass1", sanitized)
        self.assertNotIn("pass2", sanitized)
        # Usernames should be preserved
        self.assertIn("user1@host1.com", sanitized)
        self.assertIn("user2@host2.com", sanitized)

    def test_sanitize_credentials_jfrog_repo_error(self):
        """  ERROR with 401 status code from jfrog.io """
        message = "ERROR: Failed to download metadata for repo 'packages-microsoft-com-prod': Status code: 401 for https://cec-aa.jfrog.io/artifactory/glib-rpm-hel9-lts-microsoft-com/repodata/repomd.xml"
        sanitized = self.utility.sanitize_credentials_from_uri(message)
        expected_message = "ERROR: Failed to download metadata for repo 'packages-microsoft-com-prod': Status code: 401 for https://cec-aa.jfrog.io/artifactory/glib-rpm-hel9-lts-microsoft-com/repodata/repomd.xml"
        self.assertEqual(sanitized, expected_message)

    def test_sanitize_credentials_curl_error_buildbot_token(self):
        """  Curl error with buildbot:BuildBotToken credentials """
        message = ("Curl error (6): Couldn't resolve host 'packages.microsoft.com' Could not "
                   "retrieve mirrorlist https://buildbot:BuildBotToken@mirror.example.com/repodata/repomd.xml")
        sanitized = self.utility.sanitize_credentials_from_uri(message)
        expected_message = ("Curl error (6): Couldn't resolve host 'packages.microsoft.com' Could not "
                           "retrieve mirrorlist https://buildbot@mirror.example.com/repodata/repomd.xml")
        self.assertEqual(sanitized, expected_message)

    def test_sanitize_credentials_expired_ssl_certs_error(self):
        """ ERROR with expired SSL certs and TESTTOKEN123456 """
        message = ("ERROR: Customer environment error (expired SSL certs): "
                   "Command=sudo yum update -y --disablerepo='*' "
                   "--enablerepo='microsoft' !!Code=11 Out- Updating "
                   "Subscription Management repositories. "
                   "Unable to read consumer identity This system is not registered "
                   "with an entitlement server. Status code: 401 "
                   "for https://testuser:TESTTOKEN123456@packages-microsoft-com-prod/CENTRAL.rpm "
                   "Error: Failed to download metadata for repo 'packages-microsoft-com-prod': "
                   "Cannot download repomd.xml: All mirrors were tried")
        sanitized = self.utility.sanitize_credentials_from_uri(message)
        expected_message = ("ERROR: Customer environment error (expired SSL certs): "
                           "Command=sudo yum update -y --disablerepo='*' "
                           "--enablerepo='microsoft' !!Code=11 Out- Updating "
                           "Subscription Management repositories. "
                           "Unable to read consumer identity This system is not registered "
                           "with an entitlement server. Status code: 401 "
                           "for https://testuser@packages-microsoft-com-prod/CENTRAL.rpm "
                           "Error: Failed to download metadata for repo 'packages-microsoft-com-prod': "
                           "Cannot download repomd.xml: All mirrors were tried")
        self.assertEqual(sanitized, expected_message)

    def test_sanitize_credentials_exception_handling(self):
        """ Test exception handling: passing None should return the input unchanged """
        result = self.utility.sanitize_credentials_from_uri(None)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()


