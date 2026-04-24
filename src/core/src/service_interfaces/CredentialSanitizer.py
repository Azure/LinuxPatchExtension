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

import re


class CredentialSanitizer(object):
    """Sanitizes credential-like values from URIs. Removes password/token from URI userinfo."""

    @staticmethod
    def sanitize(message):
        """Sanitizes credential-like values from URIs.

        Removes password/token from URI userinfo.

        Args:
            message: The message to sanitize

        Returns:
            The message with credentials removed from URIs
        """
        try:
            # Pattern matches: scheme://user:password@host  →  scheme://user@host
            # Handles credentials containing special characters (except @, /, whitespace)
            # Groups:
            # (1) scheme: https://, http://, or ftp://
            # (2) username: one or more non-whitespace, non-slash, non-colon, non-@ characters
            # (3) password: zero or more non-whitespace, non-slash, non-@ characters
            sanitized_message = re.sub(
                r'(https?://|ftp://)([^:/@\s]+):([^@/\s]*)@',
                r'\1\2@',
                message
            )
            return sanitized_message
        except Exception:
            return message

