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

"""Package Filter"""

from core.src.bootstrap.Constants import Constants
import fnmatch


class PackageFilter(object):
    """implements the Package filtering logic"""

    def __init__(self, execution_config, composite_logger):
        self.execution_config = execution_config
        self.composite_logger = composite_logger

        # Exclusions - note: version based exclusion is not supported
        self.global_excluded_packages = self.sanitize_str_to_list(self.execution_config.global_exclusion_list)
        self.installation_excluded_package_masks = self.execution_config.excluded_package_name_mask_list
        self.installation_excluded_packages, self.installation_excluded_package_versions = self.get_packages_and_versions_from_masks(self.installation_excluded_package_masks)

        # Inclusions - note: version based inclusion is optionally supported
        self.installation_included_package_masks = self.execution_config.included_package_name_mask_list
        self.installation_included_packages, self.installation_included_package_versions = self.get_packages_and_versions_from_masks(self.installation_included_package_masks)
        self.installation_included_classifications = [] if self.execution_config.included_classifications_list is None else self.execution_config.included_classifications_list

        # Neutralize global excluded packages, if customer explicitly includes the package
        packages_to_clear_from_global = []
        for package in self.global_excluded_packages:
            if self.check_for_explicit_inclusion(package):
                self.composite_logger.log_debug('Removing package from global exclusion list: ' + package)
                packages_to_clear_from_global.append(package)
        self.global_excluded_packages = [x for x in self.global_excluded_packages if x not in packages_to_clear_from_global]

        # Logging
        self.composite_logger.log("\nAzure globally-excluded packages: " + str(self.global_excluded_packages))
        self.composite_logger.log("Included package classifications: " + ', '.join(self.installation_included_classifications))
        self.composite_logger.log("Included packages: " + str(self.installation_included_package_masks))
        self.composite_logger.log("Excluded packages: " + str(self.installation_excluded_packages))
        if '=' in str(self.installation_excluded_package_masks):
            self.composite_logger.log_error("\n /!\\ Package exclusions do not support version matching in the filter today. "
                                            "Due to this, more packages than expected may be excluded from this update deployment.")

    # region Inclusion / exclusion presence checks
    def is_exclusion_list_present(self):
        """Return true if either Global or patch installation specific exclusion list present"""
        return bool(self.global_excluded_packages) or bool(self.installation_excluded_packages)

    def is_inclusion_list_present(self):
        """Return true if patch installation Inclusion is present"""
        return bool(self.installation_included_packages)
    # endregion

    # region Package exclusion checks
    def check_for_exclusion(self, one_or_more_packages):
        """Return true if package need to be excluded"""
        return self.check_for_match(one_or_more_packages, self.installation_excluded_packages) or \
               self.check_for_match(one_or_more_packages, self.global_excluded_packages)
    # endregion

    # region Package inclusion checks
    def check_for_inclusion(self, package, package_version=Constants.DEFAULT_UNSPECIFIED_VALUE):
        """Return true if package should be included (either because no inclusion list is specified, or because of explicit match)"""
        return not self.is_inclusion_list_present() or self.check_for_explicit_inclusion(package, package_version)

    def check_for_explicit_inclusion(self, package, package_version=Constants.DEFAULT_UNSPECIFIED_VALUE):
        """Return true if package should be included due to an explicit match to the inclusion list """
        return self.check_for_match(package, self.installation_included_packages, package_version, self.installation_included_package_versions)
    # endregion

    # region Inclusion / exclusion common match checker
    def check_for_match(self, one_or_more_packages, matching_list, linked_package_versions=Constants.DEFAULT_UNSPECIFIED_VALUE, version_matching_list=Constants.DEFAULT_UNSPECIFIED_VALUE):
        # type: (str, object, str, object) -> bool  # type hinting to remove a warning
        """Return true if package(s) (with, optionally, linked version(s)) matches the filter list"""
        if matching_list:
            if type(one_or_more_packages) is str:
                return self.single_package_check_for_match(one_or_more_packages, matching_list, linked_package_versions, version_matching_list)
            else:
                for index, each_package in enumerate(one_or_more_packages):
                    if type(linked_package_versions) is str:
                        if self.single_package_check_for_match(each_package, matching_list, linked_package_versions, version_matching_list):
                            return True
                    else:
                        if self.single_package_check_for_match(each_package, matching_list, linked_package_versions[index], version_matching_list):
                            return True
        return False

    def single_package_check_for_match(self, package, matching_list, package_version, version_matching_list):
        """Returns true if a single package (optionally, version) matches the filter list"""
        for index, matching_package in enumerate(matching_list):
            if fnmatch.fnmatch(package, matching_package) or fnmatch.fnmatch(self.get_product_name_without_arch(package), matching_package):
                self.composite_logger.log_debug('    - [Package] {0} matches expression {1}'.format(package, matching_package))
                if package_version == Constants.DEFAULT_UNSPECIFIED_VALUE or not version_matching_list or version_matching_list[index] == Constants.DEFAULT_UNSPECIFIED_VALUE:
                    self.composite_logger.log_debug('    - [Version] Check skipped as not specified.')
                    return True
                elif len(version_matching_list) > index and fnmatch.fnmatch(package_version, version_matching_list[index]):
                    self.composite_logger.log_debug('    - [Version] {0} matches expression {1}'.format(package, version_matching_list[index]))
                    return True
                elif len(version_matching_list) <= index:   # This should never happen - something has gone horribly wrong
                    self.composite_logger.log_error('    - [Version] Index error - ({0} of {1})'.format(index + 1, len(version_matching_list)))
                else:
                    self.composite_logger.log_debug('    - Package {0} (version={1}) was found, but it did not match filter specified for version ({2})'.format(package, package_version, version_matching_list[index]))
        return False

    @staticmethod
    def get_product_name_without_arch(package_name):
        """Splits out product name without architecture"""
        architectures = Constants.SUPPORTED_PACKAGE_ARCH
        for arch in architectures:
            if package_name.endswith(arch):
                return package_name.replace(arch, '')
        return package_name
    # endregion

    # region Get included / excluded package masks
    def get_packages_and_versions_from_masks(self, package_masks):
        """Return package names and versions"""
        packages = []
        package_versions = []

        if package_masks is not None:
            for index, package_mask in enumerate(package_masks):
                package_mask_split = str(package_mask).split('=')
                if len(package_mask_split) == 1:        # no version specified
                    packages.append(package_mask_split[0].strip())
                    package_versions.append(Constants.DEFAULT_UNSPECIFIED_VALUE)
                elif len(package_mask_split) == 2:      # version also specified
                    packages.append(package_mask_split[0].strip())
                    package_versions.append(package_mask_split[1].strip())
                else:                                   # invalid format
                    self.composite_logger.log_warning("Invalid package format: " + str(package_mask) + " [Ignored]")

        return packages, package_versions

    @staticmethod
    def sanitize_str_to_list(string_input):
        """Strips excess white-space and converts a comma-separated string to a list"""
        return [] if (string_input is None) else string_input.strip().split(",")
    # endregion

    # region Get installation classifications from execution configuration
    def is_msft_critsec_classification_only(self):
        return ('Critical' in self.installation_included_classifications or 'Security' in self.installation_included_classifications) and 'Other' not in self.installation_included_classifications

    def is_msft_other_classification_only(self):
        return 'Other' in self.installation_included_classifications and not ('Critical' in self.installation_included_classifications or 'Security' in self.installation_included_classifications)

    def is_msft_all_classification_included(self):
        """Returns true if all classifications were individually selected *OR* (nothing was selected AND no inclusion list is present) -- business logic"""
        all_classifications = [key for key in Constants.PackageClassification.__dict__.keys() if not key.startswith('__')]
        all_classifications_explicitly_selected = bool(len(self.installation_included_classifications) == (len(all_classifications) - 2))  # all_classifications has "UNCLASSIFIED" and "SECURITY-ESM" that should be ignored. Hence -2
        no_classifications_selected = bool(len(self.installation_included_classifications) == 0)
        only_unclassified_selected = bool('Unclassified' in self.installation_included_classifications and len(self.installation_included_classifications) == 1)
        return all_classifications_explicitly_selected or ((no_classifications_selected or only_unclassified_selected) and not self.is_inclusion_list_present())

    def is_invalid_classification_combination(self):
        return ('Other' in self.installation_included_classifications and 'Critical' in self.installation_included_classifications and 'Security' not in self.installation_included_classifications) or \
               ('Other' in self.installation_included_classifications and 'Security' in self.installation_included_classifications and 'Critical' not in self.installation_included_classifications)
    # endregion
