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

import re


class CredentialSanitizer(object):
    """Service that sanitizes credential-like values from URIs by removing password/token from URI userinfo."""

    def __init__(self, logger):
        self.logger = logger

    def sanitize(self, message):
        """Removes password/token from URI credentials in the given message.
        Args:
            message: The message to sanitize
        Returns: The message with credentials removed from URIs
        """
        try:
            # Pattern matches: scheme://user:password@host  →  scheme://user@host
            # Handles credentials containing special characters (except @, /, whitespace)
            # Groups:
            # (1) scheme: https://, http://, or ftp://
            # (2) username: one or more non-whitespace, non-slash, non-colon, non-@ characters
            # (3) password: zero or more non-whitespace, non-slash, non-@ characters
            sanitized_message = re.sub(r'(https?://|ftp://)([^:/@\s]+):([^@/\s]*)@',r'\1\2@',message)
            self.logger.log_verbose("Message was sanitized to remove sensitive information. [InputMessage={0}][SanitizedMessage={1}]".format(str(message), str(sanitized_message)))
            return sanitized_message
        except Exception as error:
            self.logger.log_error("Error occurred while sanitizing credentials from message: [Error={0}]".format(repr(error)))
            return message

