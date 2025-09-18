#!/usr/bin/env bash

# Copyright 2025 Microsoft Corporation
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

COMMAND="tools/packager/Publish.py"

function find_python(){
    local python_exec_command=$1

    # Check if there is python defined.
    for p in python3 /usr/share/oem/python/bin/python3 python python2 /usr/libexec/platform-python /usr/share/oem/python/bin/python; do
        if command -v "${p}" ; then
            eval ${python_exec_command}=${p}
            return
        fi
    done
}

find_python PYTHON

${PYTHON} "${COMMAND}"
