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

""" Merges individual python modules from src to the PatchMicrosoftOMSLinuxComputer.py and MsftLinuxPatchCore.py files in the out directory.
Relative source and destination paths for the patch runbook are auto-detected if the optional src parameter is not present.
How to use: python Package.py <optional: full path to runbook 'src' folder>"""

from __future__ import print_function

import shutil
import sys
import os
import errno
import datetime


# imports in VERY_FIRST_IMPORTS, order should be kept
VERY_FIRST_IMPORTS = [
    'from __future__ import print_function\n',
    'from abc import ABCMeta, abstractmethod\n',
    'from datetime import timedelta\n',
    'from external_dependencies import distro\n']
GLOBAL_IMPORTS = set()


def read_python_module(source_code_path, module_name):
    module_full_path = os.path.join(source_code_path, module_name)
    imports = []
    codes = "\n\n# region ########## {0} ##########\n".format(os.path.basename(module_name).replace('.py',''))
    is_code_body = False
    if os.path.exists(module_full_path):
        with open(module_full_path) as py_file:
            for line in py_file:
                if line.startswith('import'):
                    imports.append(line)
                elif line.strip().startswith('class') or line.strip().startswith('def main(argv):') or line.strip().startswith('if __name__ == "__main__"'):
                    is_code_body = True

                if is_code_body is True:
                    codes = codes + line
    codes = codes + "\n# endregion ########## {0} ##########\n".format(os.path.basename(module_name).replace('.py',''))
    return imports, codes


def write_merged_code(code, merged_file_full_path):
    with open(merged_file_full_path, 'a+') as py_file:
        py_file.write(code)


def insert_copyright_notice(merged_file_full_path, merged_file_name):
    notice = '# --------------------------------------------------------------------------------------------------------------------\n'
    notice += '# <copyright file="' + merged_file_name + '" company="Microsoft">\n'
    notice += '#   Copyright 2020 Microsoft Corporation\n' \
              '#\n' \
              '#   Licensed under the Apache License, Version 2.0 (the "License");\n' \
              '#   you may not use this file except in compliance with the License.\n' \
              '#   You may obtain a copy of the License at\n' \
              '#\n' \
              '#     http://www.apache.org/licenses/LICENSE-2.0\n' \
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


def generate_compiled_script(source_code_path, merged_file_full_path, merged_file_name, environment):
    try:
        print('\n\n=============================== GENERATING ' + merged_file_name + '... =============================================================\n')

        print('========== Delete old core file if it exists.')
        if os.path.exists(merged_file_full_path):
            os.remove(merged_file_full_path)

        print('\n========== Merging modules: \n')
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
                elif 'external_dependencies' in file_path:
                    continue
                elif os.path.basename(file_path) in ('PackageManager.py', 'Constants.py'):
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

        print('\n========== Prepend all import statements\n')
        insert_imports(GLOBAL_IMPORTS, merged_file_full_path)
        insert_imports(VERY_FIRST_IMPORTS, merged_file_full_path)

        print('========== Set Copyright, Version and Environment. Also enforce UNIX-style line endings.\n')
        insert_copyright_notice(merged_file_full_path, merged_file_name)
        timestamp = datetime.datetime.utcnow().strftime("%y%m%d-%H%M")
        replace_text_in_file(merged_file_full_path, '[%exec_name%]', merged_file_name.split('.')[0])
        replace_text_in_file(merged_file_full_path, '[%exec_sub_ver%]', timestamp)
        replace_text_in_file(merged_file_full_path, '\r\n', '\n')

        print("========== Merged core code was saved to:\n{0}\n".format(merged_file_full_path))

    except Exception as error:
        print('Exception during merge python modules: ' + repr(error))
        raise


def add_external_dependencies(external_dependencies_destination, external_dependencies_source_code_path):
    try:
        print('\n========= ADDING EXTERNAL DEPENDENCIES\n')

        print('========== Deleting old dependencies if they exists.')
        if os.path.exists(external_dependencies_destination):
            shutil.rmtree(external_dependencies_destination)

        print('\n========== Adding all dependencies to external_dependencies directory: \n')
        dependencies_to_be_added = []
        for root, dirs, files in os.walk(external_dependencies_source_code_path):
            for file_name in files:
                if ".py" not in file_name or ".pyc" in file_name:
                    continue
                file_path = os.path.join(root, file_name)
                dependencies_to_be_added.append(file_path)
        os.mkdir(external_dependencies_destination)
        for dependency in dependencies_to_be_added:
            print(format(os.path.basename(dependency)), end=', ')
            shutil.copyfile(dependency, os.path.join(external_dependencies_destination, os.path.basename(dependency)))

        print("\n\n========== External dependencies saved to:\n{0}\n".format(external_dependencies_destination))

    except Exception as error:
        print('Exception during adding external dependencies: ' + repr(error))
        raise


def main(argv):
    """The main entry of merge python modules run"""
    try:
        # Clear
        os.system('cls' if os.name == 'nt' else 'clear')

        # Determine code path if not specified
        if len(argv) < 2:
            # auto-detect src path
            source_code_path = os.path.dirname(os.path.realpath(__file__)).replace("tools", os.path.join("core","src"))
            if os.path.exists(os.path.join(source_code_path, "__main__.py")) is False:
                print("Invalid core source code path. Check enlistment.\n")
                return
        else:
            # explicit src path parameter
            source_code_path = argv[1]
            if os.path.exists(os.path.join(source_code_path, "PatchInstaller.py")) is False:
                print("Invalid core source code path. Check src parameter.\n")
                return

        # Prepare destination for compiled scripts
        working_directory = os.path.abspath(os.path.join(source_code_path, os.pardir, os.pardir))
        merge_file_directory = os.path.join(working_directory, 'out')
        try:
            os.makedirs(merge_file_directory)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        # Generated compiled scripts at the destination
        merged_file_details = [('MsftLinuxPatchCore.py', 'Constants.PROD')]
        for merged_file_detail in merged_file_details:
            merged_file_destination = os.path.join(working_directory, 'out', merged_file_detail[0])
            generate_compiled_script(source_code_path, merged_file_destination, merged_file_detail[0], merged_file_detail[1])

        # add all dependencies under core/src/external_dependencies to destination directory
        external_dependencies_destination = os.path.join(merge_file_directory, 'external_dependencies')
        external_dependencies_source_code_path = os.path.join(source_code_path, 'external_dependencies')
        add_external_dependencies(external_dependencies_destination, external_dependencies_source_code_path)

    except Exception as error:
        print('Exception during packaging all python modules in core: ' + repr(error))
        raise


if __name__ == "__main__":
    main(sys.argv)