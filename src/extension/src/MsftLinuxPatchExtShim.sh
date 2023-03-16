#!/usr/bin/env bash

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

# Keeping the default command
COMMAND="MsftLinuxPatchExt.py"
PYTHON=""

USAGE="$(basename "$0") [-h] [-i|--install] [-u|--uninstall] [-d|--disable] [-e|--enable] [-p|--update] [-r|--reset]
Program to find the installed python on the box and invoke a Python extension script.
where:
    -h|--help       show this help text
    -i|--install    install the extension
    -u|--uninstall  uninstall the extension
    -d|--disable    disable the extension
    -e|--enable     enable the extension
    -p|--update     update the extension
    -r|--reset      reset the extension
"

function find_python(){
    local python_exec_command=$1

    # Check if there is python defined.
    for p in python3 python python2 /usr/libexec/platform-python /usr/share/oem/python/bin/python3 /usr/share/oem/python/bin/python; do
        if command -v "${p}" ; then
            eval ${python_exec_command}=${p}
            return
        fi
    done
}

# Transform long options to short ones for getopts support (getopts doesn't support long args)
for arg in "$@"; do
  shift
  case "$arg" in
    "--help")       set -- "$@" "-h" ;;
    "--install")    set -- "$@" "-i" ;;
    "--update")     set -- "$@" "-p" ;;
    "--enable")     set -- "$@" "-e" ;;
    "--disable")    set -- "$@" "-d" ;;
    "--uninstall")  set -- "$@" "-u" ;;
    "--reset")      set -- "$@" "-r" ;;
    *)              set -- "$@" "$arg"
  esac
done

if [ -z "$arg" ]
then
   echo "$USAGE" >&2
   exit 1
fi

# Get the arguments
while getopts "iudephrt:?" o; do
    case "${o}" in
        h|\?)
            echo "$USAGE"
            exit 0
            ;;
        i)
            operation="-install"
            ;;
        u)
            operation="-uninstall"
            ;;
        d)
            operation="-disable"
            ;;
        e)
            operation="-enable"
            ;;
        p)
            operation="-update"
            ;;
        r)
            operation="-reset"
            ;;
        t)
            COMMAND="$OPTARG"
            ;;
        *)
            echo "$USAGE" >&2
            exit 1
            ;;
    esac
done

shift $((OPTIND-1))

# If find_python is not able to find a python installed, $PYTHON will be null.
find_python PYTHON


if [ -z "$PYTHON" ]; then
   # Error codes: https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
   echo "Python is required, but no Python interpreter was found on the box" >&2
   exit 52
else
   echo "${PYTHON} --version"
fi

${PYTHON} "${COMMAND}" ${operation}
# DONE
