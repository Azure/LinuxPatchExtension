# Copyright 2025 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.7+

""" Publishes a new extension version by incrementing the version number in the manifest.xml file."""

from __future__ import print_function
import sys
import os
import errno
import subprocess
import xml.etree.ElementTree as et

# noinspection PyPep8
def replace_text_in_file(file_path, old_text, new_text):
    with open(file_path, 'rb') as file_handle: text = file_handle.read()
    text = text.replace(old_text.encode(encoding='UTF-8'), new_text.encode(encoding='UTF-8'))
    with open(file_path, 'wb') as file_handle: file_handle.write(text)


def main(argv):
    try:
        # Clear
        os.system('cls' if os.name == 'nt' else 'clear')

        # Determine code path if not specified
        if len(argv) < 2:
            # auto-detect src path
            source_code_path = os.path.dirname(os.path.realpath(__file__)).replace(os.path.join("tools", "packager"), os.path.join("extension", "src"))
            if os.path.exists(os.path.join(source_code_path, "__main__.py")) is False:
                print("Invalid extension source code path. Check enlistment.\n")
                return
        else:
            # explicit src path parameter
            source_code_path = argv[1]
            if os.path.exists(os.path.join(source_code_path, "ActionHandler.py")) is False:
                print("Invalid extension source code path. Check src parameter.\n")
                return

        # Prepare destination for compiled scripts
        working_directory = os.path.abspath(os.path.join(source_code_path, os.pardir, os.pardir))
        merge_file_directory = os.path.join(working_directory, 'out')
        try:
            os.makedirs(merge_file_directory)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        # Get version from manifest for code
        new_version = None
        manifest_xml_file_path = os.path.join(working_directory, 'extension', 'src', 'manifest.xml')
        manifest_tree = et.parse(manifest_xml_file_path)
        manifest_root = manifest_tree.getroot()
        for i in range(0, len(manifest_root)):
            if 'Version' in str(manifest_root[i]):
                new_version = manifest_root[i].text
        if new_version is None:
            raise Exception("Unable to determine target version.")

        # Rev handler version
        current_version = "Unknown"
        manifest_xml_file_path = os.path.join(working_directory, 'extension', 'src', 'manifest.xml')
        manifest_tree = et.parse(manifest_xml_file_path)
        manifest_root = manifest_tree.getroot()
        for i in range(0, len(manifest_root)):
            if 'Version' in str(manifest_root[i]):
                current_version = manifest_root[i].text
                version_split = current_version.split('.')
                version_split[len(version_split)-1] = str(int(version_split[len(version_split)-1]) + 1)
                new_version = '.'.join(version_split)
                replace_text_in_file(manifest_xml_file_path, current_version, new_version)

        # Invoke core business logic code packager
        exec_core_build_path = os.path.join(working_directory, 'tools', 'packager', 'Package-All.py')
        subprocess.call('python ' + exec_core_build_path, shell=True)
        
        # Report extension version change
        print("==========================================================================================================\n")
        print("! PUBLISHER > THE EXTENSION VERSION WAS CHANGED FROM {0} to {1}. DO NOT RE-RUN.".format(current_version, new_version))
        print("!           > This is only meant to be run once prior to extension publish and pushed as a PR. Not for automation.")
        print("!           > If this was an error, revert the extension manifest, and only use the build script instead of publish.\n")

    except Exception as error:
        print('Exception during merge python modules: ' + repr(error))
        raise


if __name__ == "__main__":
    main(sys.argv)
