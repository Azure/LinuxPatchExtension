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

import unittest
from extension.src.CredentialSanitizer import CredentialSanitizer
from extension.tests.helpers.RuntimeComposer import RuntimeComposer
from extension.tests.helpers.VirtualTerminal import VirtualTerminal


class TestCredentialSanitizer(unittest.TestCase):
    """Tests for CredentialSanitizer class"""

    def setUp(self):
        VirtualTerminal().print_lowlight("\n----------------- setup test runner -----------------")
        self.runtime = RuntimeComposer()
        self.logger = self.runtime.logger
        self.sanitizer = CredentialSanitizer(self.logger)

    def tearDown(self):
        VirtualTerminal().print_lowlight("\n----------------- tear down test runner -----------------")

    def test_sanitize_uri_with_credentials_all_schemes(self):
        """Test sanitization of URIs (HTTPS, HTTP, FTP) with user:password@host pattern"""
        # Test HTTPS
        https_message = "Error connecting to https://testuser:TESTTOKEN123456@invalid.repo.example/rpm/repodata/repomd.xml"
        https_result = self.sanitizer.sanitize(https_message)
        self.assertNotIn("TESTTOKEN123456", https_result)
        self.assertEqual("Error connecting to https://testuser@invalid.repo.example/rpm/repodata/repomd.xml", https_result)
        
        # Test HTTP
        http_message = "Connection failed to http://user123:password123@example.com/path"
        http_result = self.sanitizer.sanitize(http_message)
        self.assertNotIn("password123", http_result)
        self.assertIn("user123@example.com", http_result)
        
        # Test FTP
        ftp_message = "ftp://user:pass@host/file"
        ftp_result = self.sanitizer.sanitize(ftp_message)
        self.assertEqual("ftp://user@host/file", ftp_result)

    def test_sanitize_multiple_urls_and_special_cases(self):
        """Test multiple URLs, newlines, and special characters in credentials"""
        # Test multiple URLs
        multi_message = "a https://u:p@h and b https://u2:p2@h2"
        self.assertEqual("a https://u@h and b https://u2@h2", self.sanitizer.sanitize(multi_message))
        
        # Test newlines
        newline_message = "err\nhttps://user:token@repo\nmore"
        self.assertEqual("err\nhttps://user@repo\nmore", self.sanitizer.sanitize(newline_message))
        
        # Test special characters in token
        special_message = "https://user:tok-en_123.456@host"
        self.assertEqual("https://user@host", self.sanitizer.sanitize(special_message))
        
        # Test query string preservation
        query_message = "https://user:tok@host/path?x=1&y=2"
        self.assertEqual("https://user@host/path?x=1&y=2", self.sanitizer.sanitize(query_message))

    def test_no_sanitization_when_not_needed(self):
        """Test that URLs without credentials or non-URL patterns remain unchanged"""
        # No userinfo
        self.assertEqual("https://host/path", self.sanitizer.sanitize("https://host/path"))
        
        # Username only (no colon)
        self.assertEqual("https://user@host", self.sanitizer.sanitize("https://user@host"))
        
        # Port number
        self.assertEqual("https://host:8080/path", self.sanitizer.sanitize("https://host:8080/path"))
        
        # Query token (out of scope)
        self.assertEqual("https://host/path?token=abc", self.sanitizer.sanitize("https://host/path?token=abc"))
        
        # Random colon-at without scheme
        self.assertEqual("user:pass@host", self.sanitizer.sanitize("user:pass@host"))

    def test_edge_cases_and_exception_handling(self):
        """Test edge cases: empty string, None input, messages without URIs"""
        # None input
        self.assertIsNone(self.sanitizer.sanitize(None))
        
        # Empty string
        self.assertEqual("", self.sanitizer.sanitize(""))
        
        # No URIs
        message = "This is a normal error message without URLs"
        self.assertEqual(message, self.sanitizer.sanitize(message))
        
        # Message with @ but no scheme
        message_with_at = "Failed auth user:pass@host"
        self.assertEqual(message_with_at, self.sanitizer.sanitize(message_with_at))

    def test_real_world_scenarios(self):
        """Test real-world error messages with embedded credentials"""
        # YUM error
        yum_message = ("ERROR: Failed to download metadata for repo 'packages-microsoft-com-prod': "
                       "Status code: 401 for https://testuser:TESTTOKEN123456@packages-microsoft-com-prod/CENTRAL.rpm")
        yum_result = self.sanitizer.sanitize(yum_message)
        self.assertNotIn("TESTTOKEN123456", yum_result)
        self.assertIn("testuser@packages-microsoft-com-prod", yum_result)
        
        # JFrog Artifactory error
        jfrog_message = ("Failed to retrieve from https://cec-aa.jfrog.io/artifactory/glib-rpm-hel9-lts-microsoft-com/repodata/repomd.xml "
                         "Status code: 401 for https://user:token@cec-aa.jfrog.io/artifactory/repo")
        jfrog_result = self.sanitizer.sanitize(jfrog_message)
        self.assertNotIn(":token@", jfrog_result)
        self.assertIn("user@cec-aa.jfrog.io", jfrog_result)


if __name__ == '__main__':
    unittest.main()


