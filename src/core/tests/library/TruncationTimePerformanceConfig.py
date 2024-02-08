# Copyright 2024 Microsoft Corporation
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


class TruncationTimePerformanceConfig(object):
    """ Helps set up constants for comparing time performance of prior and post truncation logic unit test """
    class UTConfig:
        MIN_OPERATION_ITERATIONS = 0
        MAX_OPERATION_ITERATIONS = 30
        NUMBER_OF_PATCHES = 350
        EXPECTED_TRUNCATION_TIME_LIMIT_IN_SEC = 30

