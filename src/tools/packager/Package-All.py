# Copyright 2020 Microsoft Corporation
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

""" Merges individual python modules from src to the AzGPSLinuxPatchExt files in the out directory.
Relative source and destination paths for the extension are auto-detected if the optional src parameter is not present.
How to use: python Package-All.py <optional: full path to extension 'src' folder>
Note: Package-All.py internally invokes Package-Core.py to generate AzGPSLinuxPatchCore.py """

from __future__ import print_function
import sys
import os
import errno
import datetime
from shutil import copyfile
from shutil import make_archive
import subprocess
import xml.etree.ElementTree as et

# imports in VERY_FIRST_IMPORTS, order should be kept
VERY_FIRST_IMPORTS = [
    'from __future__ import print_function\n',
    'from abc import ABCMeta, abstractmethod\n',
    'from distutils.version import LooseVersion\n']
GLOBAL_IMPORTS = set()


def read_python_module(source_code_path, module_name):
    module_full_path = os.path.join(source_code_path, module_name)
    imports = []
    codes = "\n\n# region ########## {0} ##########\n".format(os.path.basename(module_name))
    is_code_body = False
    if os.path.exists(module_full_path):
        with open(module_full_path) as py_file:
            for line in py_file:
                if line.startswith('import'):
                    imports.append(line)
                elif line.strip().startswith('class') or line.strip().startswith('def main(argv):'):
                    is_code_body = True

                if is_code_body is True:
                    codes = codes + line
    codes = codes + "\n# endregion ########## {0} ##########\n".format(os.path.basename(module_name))
    return imports, codes


def write_merged_code(code, merged_file_full_path):
    with open(merged_file_full_path, 'a+') as py_file:
        py_file.write(code)


def insert_copyright_notice(merged_file_full_path, merged_file_name):
    notice = '# coding=utf-8\n'
    notice += '# --------------------------------------------------------------------------------------------------------------------\n'
    notice += '# <copyright file="' + merged_file_name + '" company="Microsoft">\n'
    notice += '#   Copyright ' + str(datetime.date.today().year) + ' Microsoft Corporation\n' \
              '#\n' \
              '#   Licensed under the Apache License, Version 2.0 (the "License");\n' \
              '#   you may not use this file except in compliance with the License.\n' \
              '#   You may obtain a copy of the License at\n' \
              '#\n' \
              '#     https://www.apache.org/licenses/LICENSE-2.0\n' \
              '#\n' \
              '#   Unless required by applicable law or agreed to in writing, software\n' \
              '#   distributed under the License is distributed on an "AS IS" BASIS,\n' \
              '#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n' \
              '#   See the License for the specific language governing permissions and\n' \
              '#   limitations under the License.\n' \
              '#\n' \
              '#   Requires Python 2.7+\n'
    notice += '# </copyright>\n'
    notice += '# --------------------------------------------------------------------------------------------------------------------\n\n'
    prepend_content_to_file(notice, merged_file_full_path)


# noinspection PyPep8
def replace_text_in_file(file_path, old_text, new_text):
    with open(file_path, 'rb') as file_handle: text = file_handle.read()
    text = text.replace(old_text.encode(encoding='UTF-8'), new_text.encode(encoding='UTF-8'))
    with open(file_path, 'wb') as file_handle: file_handle.write(text)


def insert_imports(imports, merged_file_name):
    imports_str = ''.join(imports)
    prepend_content_to_file(imports_str, merged_file_name)


def prepend_content_to_file(content, file_name):
    temp_file = os.path.join(os.path.dirname(file_name), "temp_.py")
    with open(file_name, 'r') as file1:
        with open(temp_file, 'w+') as file2:
            file2.write(content)
            file2.write(file1.read())
    if os.name.lower() == 'nt':
        os.unlink(file_name)
    os.rename(temp_file, file_name)


def generate_compiled_script(source_code_path, merged_file_full_path, merged_file_name, environment, new_version):
    try:
        print('\n=============================== (2/3) GENERATING ' + merged_file_name + '... ================================\n')

        print('------------- Deleting old extension file if it exists.')
        if os.path.exists(merged_file_full_path):
            os.remove(merged_file_full_path)

        print('------------- Merging modules: ')
        modules_to_be_merged = []
        for root, dirs, files in os.walk(source_code_path):
            for file_name in files:
                if ".py" not in file_name or ".pyc" in file_name:
                    continue
                file_path = os.path.join(root, file_name)
                if '__main__.py' in file_path:
                    modules_to_be_merged.append(file_path)
                elif os.path.basename(file_path) in ('__init__.py'):
                    continue
                elif os.path.basename(file_path) in ('Constants.py'):
                    modules_to_be_merged.insert(0, file_path)
                else:
                    if len(modules_to_be_merged) > 0 and '__main__.py' in modules_to_be_merged[-1]:
                        modules_to_be_merged.insert(-1, file_path)
                    else:
                        modules_to_be_merged.append(file_path)
        for python_module in modules_to_be_merged:
            print(format(os.path.basename(python_module)), end=', ')
            imports, codes = read_python_module(source_code_path, python_module)
            GLOBAL_IMPORTS.update(imports)
            write_merged_code(codes, merged_file_full_path)
        print("<end>")

        print('------------- Prepend all import statements')
        insert_imports(GLOBAL_IMPORTS, merged_file_full_path)
        insert_imports(VERY_FIRST_IMPORTS, merged_file_full_path)

        print('------------- Set Copyright, Version and Environment. Also enforce UNIX-style line endings.')
        insert_copyright_notice(merged_file_full_path, merged_file_name)
        timestamp = datetime.datetime.now(datetime.timezone.UTC).strftime("%y%m%d-%H%M")
        replace_text_in_file(merged_file_full_path, '[%exec_name%]', merged_file_name)
        replace_text_in_file(merged_file_full_path, '[%exec_ver%]', str(new_version))
        replace_text_in_file(merged_file_full_path, '[%exec_build_timestamp%]', timestamp)
        replace_text_in_file(merged_file_full_path, 'Constants.UNKNOWN_ENV', environment)
        replace_text_in_file(merged_file_full_path, '\r\n', '\n')

        print("------------- Merged extension code was saved to:\n{0}\n".format(merged_file_full_path))

    except Exception as error:
        print('Exception during merge python modules: ' + repr(error))
        raise


def main(argv):
    """The main entry of merge python modules run"""
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

        # Invoke core business logic code packager
        exec_core_build_path = os.path.join(working_directory, 'tools', 'packager', 'Package-Core.py')
        subprocess.call('python ' + exec_core_build_path, shell=True)

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

        # Generated compiled scripts at the destination
        merged_file_details = [('AzGPSLinuxPatchExt.py', 'Constants.PROD')]
        for merged_file_detail in merged_file_details:
            merged_file_destination = os.path.join(working_directory, 'out', merged_file_detail[0])
            generate_compiled_script(source_code_path, merged_file_destination, merged_file_detail[0], merged_file_detail[1], new_version)

        # GENERATING EXTENSION
        print('\n=============================== (3/3) GENERATING LinuxPatchExtension.zip... ==============================\n')

        # Copy extension files
        print('------------- Copying extension files + enforcing UNIX style line endings.')
        ext_files = ['HandlerManifest.json', 'manifest.xml', 'AzGPSLinuxPatchExtShim.sh']
        for ext_file in ext_files:
            ext_file_src = os.path.join(working_directory, 'extension', 'src', ext_file)
            ext_file_destination = os.path.join(working_directory, 'out', ext_file)
            copyfile(ext_file_src, ext_file_destination)
            replace_text_in_file(ext_file_destination, '\r\n', '\n')

        # Generate extension zip
        ext_zip_file = 'LinuxPatchExtension.zip'
        ext_zip_file_path_src = os.path.join(working_directory, ext_zip_file)
        ext_zip_file_path_dest = os.path.join(working_directory, 'out', ext_zip_file)
        if os.path.exists(ext_zip_file_path_src):
            os.remove(ext_zip_file_path_src)
        if os.path.exists(ext_zip_file_path_dest):
            os.remove(ext_zip_file_path_dest)

        # Generate zip
        print('------------- Generating extension zip.')
        make_archive(os.path.splitext(ext_zip_file_path_src)[0], 'zip', os.path.join(working_directory, 'out'), '..')
        copyfile(ext_zip_file_path_src, ext_zip_file_path_dest)
        os.remove(ext_zip_file_path_src)

        # Remove extension file copies
        print('------------- Cleaning up environment.')
        for ext_file in ext_files:
            ext_file_path = os.path.join(working_directory, 'out', ext_file)
            os.remove(ext_file_path)

        print("------------- Extension ZIP was saved to:\n{0}\n".format(ext_zip_file_path_dest))

    except Exception as error:
        print('Exception during merge python modules: ' + repr(error))
        raise


if __name__ == "__main__":
    main(sys.argv)
