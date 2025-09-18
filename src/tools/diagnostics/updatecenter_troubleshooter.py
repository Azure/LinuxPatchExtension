#!/usr/bin/env python
from __future__ import print_function
import os
import re
import sys
import json
import shlex
import subprocess

import datetime
import platform
if os.name != "nt": import pwd  # do not make this multi-line - the packager won't package correctly
import time
import uuid
from abc import ABCMeta, abstractmethod
import os.path
import socket
import imp
import codecs
import string
if sys.version_info[0] == 2:
    from urlparse import urlparse
else:
    from urllib.parse import urlparse
from os import walk


_UNIXCONFDIR = os.environ.get('UNIXCONFDIR', '/etc')
_OS_RELEASE_BASENAME = 'os-release'

#: Translation table for normalizing the "ID" attribute defined in os-release
#: files, for use by the :func:`distro.id` method.
#:
#: * Key: Value as defined in the os-release file, translated to lower case,
#:   with blanks translated to underscores.
#:
#: * Value: Normalized value.
NORMALIZED_OS_ID = {
    'ol': 'oracle',  # Oracle Linux
}

#: Translation table for normalizing the "Distributor ID" attribute returned by
#: the lsb_release command, for use by the :func:`distro.id` method.
#:
#: * Key: Value as returned by the lsb_release command, translated to lower
#:   case, with blanks translated to underscores.
#:
#: * Value: Normalized value.
NORMALIZED_LSB_ID = {
    'enterpriseenterpriseas': 'oracle',  # Oracle Enterprise Linux 4
    'enterpriseenterpriseserver': 'oracle',  # Oracle Linux 5
    'redhatenterpriseworkstation': 'rhel',  # RHEL 6, 7 Workstation
    'redhatenterpriseserver': 'rhel',  # RHEL 6, 7 Server
    'redhatenterprisecomputenode': 'rhel',  # RHEL 6 ComputeNode
}

#: Translation table for normalizing the distro ID derived from the file name
#: of distro release files, for use by the :func:`distro.id` method.
#:
#: * Key: Value as derived from the file name of a distro release file,
#:   translated to lower case, with blanks translated to underscores.
#:
#: * Value: Normalized value.
NORMALIZED_DISTRO_ID = {
    'redhat': 'rhel',  # RHEL 6.x, 7.x
}

# Pattern for content of distro release file (reversed)
_DISTRO_RELEASE_CONTENT_REVERSED_PATTERN = re.compile(
    r'(?:[^)]*\)(.*)\()? *(?:STL )?([\d.+\-a-z]*\d) *(?:esaeler *)?(.+)')

# Pattern for base file name of distro release file
_DISTRO_RELEASE_BASENAME_PATTERN = re.compile(
    r'(\w+)[-_](release|version)$')

# Base file names to be ignored when searching for distro release file
_DISTRO_RELEASE_IGNORE_BASENAMES = (
    'debian_version',
    'lsb-release',
    'oem-release',
    _OS_RELEASE_BASENAME,
    'system-release',
    'plesk-release',
)

class cached_property(object):
    """A version of @property which caches the value.  On access, it calls the
    underlying function and sets the value in `__dict__` so future accesses
    will not re-call the property.
    """
    def __init__(self, f):
        self._fname = f.__name__
        self._f = f

    def __get__(self, obj, owner):
        assert obj is not None, 'call {} on an instance'.format(self._fname)
        ret = obj.__dict__[self._fname] = self._f(obj)
        return ret


class LinuxDistribution(object):
    """
    Provides information about a OS distribution.

    This package creates a private module-global instance of this class with
    default initialization arguments, that is used by the
    `consolidated accessor functions`_ and `single source accessor functions`_.
    By using default initialization arguments, that module-global instance
    returns data about the current OS distribution (i.e. the distro this
    package runs on).

    Normally, it is not necessary to create additional instances of this class.
    However, in situations where control is needed over the exact data sources
    that are used, instances of this class can be created with a specific
    distro release file, or a specific os-release file, or without invoking the
    lsb_release command.
    """

    def __init__(self,
                 include_lsb=True,
                 os_release_file='',
                 distro_release_file='',
                 include_uname=True):
        """
        The initialization method of this class gathers information from the
        available data sources, and stores that in private instance attributes.
        Subsequent access to the information items uses these private instance
        attributes, so that the data sources are read only once.

        Parameters:

        * ``include_lsb`` (bool): Controls whether the
          `lsb_release command output`_ is included as a data source.

          If the lsb_release command is not available in the program execution
          path, the data source for the lsb_release command will be empty.

        * ``os_release_file`` (string): The path name of the
          `os-release file`_ that is to be used as a data source.

          An empty string (the default) will cause the default path name to
          be used (see `os-release file`_ for details).

          If the specified or defaulted os-release file does not exist, the
          data source for the os-release file will be empty.

        * ``distro_release_file`` (string): The path name of the
          `distro release file`_ that is to be used as a data source.

          An empty string (the default) will cause a default search algorithm
          to be used (see `distro release file`_ for details).

          If the specified distro release file does not exist, or if no default
          distro release file can be found, the data source for the distro
          release file will be empty.

        * ``include_uname`` (bool): Controls whether uname command output is
          included as a data source. If the uname command is not available in
          the program execution path the data source for the uname command will
          be empty.

        Public instance attributes:

        * ``os_release_file`` (string): The path name of the
          `os-release file`_ that is actually used as a data source. The
          empty string if no distro release file is used as a data source.

        * ``distro_release_file`` (string): The path name of the
          `distro release file`_ that is actually used as a data source. The
          empty string if no distro release file is used as a data source.

        * ``include_lsb`` (bool): The result of the ``include_lsb`` parameter.
          This controls whether the lsb information will be loaded.

        * ``include_uname`` (bool): The result of the ``include_uname``
          parameter. This controls whether the uname information will
          be loaded.

        Raises:

        * :py:exc:`IOError`: Some I/O issue with an os-release file or distro
          release file.

        * :py:exc:`subprocess.CalledProcessError`: The lsb_release command had
          some issue (other than not being available in the program execution
          path).

        * :py:exc:`UnicodeError`: A data source has unexpected characters or
          uses an unexpected encoding.
        """
        self.os_release_file = os_release_file or \
            os.path.join(_UNIXCONFDIR, _OS_RELEASE_BASENAME)
        self.distro_release_file = distro_release_file or ''  # updated later
        self.include_lsb = include_lsb
        self.include_uname = include_uname

    def __repr__(self):
        """Return repr of all info
        """
        return \
            "LinuxDistribution(" \
            "os_release_file={self.os_release_file!r}, " \
            "distro_release_file={self.distro_release_file!r}, " \
            "include_lsb={self.include_lsb!r}, " \
            "include_uname={self.include_uname!r}, " \
            "_os_release_info={self._os_release_info!r}, " \
            "_lsb_release_info={self._lsb_release_info!r}, " \
            "_distro_release_info={self._distro_release_info!r}, " \
            "_uname_info={self._uname_info!r})".format(
                self=self)

    def linux_distribution(self, full_distribution_name=True):
        """
        Return information about the OS distribution that is compatible
        with Python's :func:`platform.linux_distribution`, supporting a subset
        of its parameters.

        For details, see :func:`distro.linux_distribution`.
        """
        return (
            self.name() if full_distribution_name else self.id(),
            self.version(),
            self.codename()
        )

    def id(self):
        """Return the distro ID of the OS distribution, as a string.

        For details, see :func:`distro.id`.
        """
        def normalize(distro_id, table):
            distro_id = distro_id.lower().replace(' ', '_')
            return table.get(distro_id, distro_id)

        distro_id = self.os_release_attr('id')
        if distro_id:
            return normalize(distro_id, NORMALIZED_OS_ID)

        distro_id = self.lsb_release_attr('distributor_id')
        if distro_id:
            return normalize(distro_id, NORMALIZED_LSB_ID)

        distro_id = self.distro_release_attr('id')
        if distro_id:
            return normalize(distro_id, NORMALIZED_DISTRO_ID)

        distro_id = self.uname_attr('id')
        if distro_id:
            return normalize(distro_id, NORMALIZED_DISTRO_ID)

        return ''

    def name(self, pretty=False):
        """
        Return the name of the OS distribution, as a string.

        For details, see :func:`distro.name`.
        """
        name = self.os_release_attr('name') \
            or self.lsb_release_attr('distributor_id') \
            or self.distro_release_attr('name') \
            or self.uname_attr('name')
        if pretty:
            name = self.os_release_attr('pretty_name') \
                or self.lsb_release_attr('description')
            if not name:
                name = self.distro_release_attr('name') \
                       or self.uname_attr('name')
                version = self.version(pretty=True)
                if version:
                    name = name + ' ' + version
        return name or ''

    def version(self, pretty=False, best=False):
        """
        Return the version of the OS distribution, as a string.

        For details, see :func:`distro.version`.
        """
        versions = [
            self.os_release_attr('version_id'),
            self.lsb_release_attr('release'),
            self.distro_release_attr('version_id'),
            self._parse_distro_release_content(
                self.os_release_attr('pretty_name')).get('version_id', ''),
            self._parse_distro_release_content(
                self.lsb_release_attr('description')).get('version_id', ''),
            self.uname_attr('release')
        ]
        version = ''
        if best:
            # This algorithm uses the last version in priority order that has
            # the best precision. If the versions are not in conflict, that
            # does not matter; otherwise, using the last one instead of the
            # first one might be considered a surprise.
            for v in versions:
                if v.count(".") > version.count(".") or version == '':
                    version = v
        else:
            for v in versions:
                if v != '':
                    version = v
                    break
        if pretty and version and self.codename():
            version = '{0} ({1})'.format(version, self.codename())
        return version

    def version_parts(self, best=False):
        """
        Return the version of the OS distribution, as a tuple of version
        numbers.

        For details, see :func:`distro.version_parts`.
        """
        version_str = self.version(best=best)
        if version_str:
            version_regex = re.compile(r'(\d+)\.?(\d+)?\.?(\d+)?')
            matches = version_regex.match(version_str)
            if matches:
                major, minor, build_number = matches.groups()
                return major, minor or '', build_number or ''
        return '', '', ''

    def major_version(self, best=False):
        """
        Return the major version number of the current distribution.

        For details, see :func:`distro.major_version`.
        """
        return self.version_parts(best)[0]

    def minor_version(self, best=False):
        """
        Return the minor version number of the current distribution.

        For details, see :func:`distro.minor_version`.
        """
        return self.version_parts(best)[1]

    def build_number(self, best=False):
        """
        Return the build number of the current distribution.

        For details, see :func:`distro.build_number`.
        """
        return self.version_parts(best)[2]

    def like(self):
        """
        Return the IDs of distributions that are like the OS distribution.

        For details, see :func:`distro.like`.
        """
        return self.os_release_attr('id_like') or ''

    def codename(self):
        """
        Return the codename of the OS distribution.

        For details, see :func:`distro.codename`.
        """
        try:
            # Handle os_release specially since distros might purposefully set
            # this to empty string to have no codename
            return self._os_release_info['codename']
        except KeyError:
            return self.lsb_release_attr('codename') \
                or self.distro_release_attr('codename') \
                or ''

    def info(self, pretty=False, best=False):
        """
        Return certain machine-readable information about the OS
        distribution.

        For details, see :func:`distro.info`.
        """
        return dict(
            id=self.id(),
            version=self.version(pretty, best),
            version_parts=dict(
                major=self.major_version(best),
                minor=self.minor_version(best),
                build_number=self.build_number(best)
            ),
            like=self.like(),
            codename=self.codename(),
        )

    def os_release_info(self):
        """
        Return a dictionary containing key-value pairs for the information
        items from the os-release file data source of the OS distribution.

        For details, see :func:`distro.os_release_info`.
        """
        return self._os_release_info

    def lsb_release_info(self):
        """
        Return a dictionary containing key-value pairs for the information
        items from the lsb_release command data source of the OS
        distribution.

        For details, see :func:`distro.lsb_release_info`.
        """
        return self._lsb_release_info

    def distro_release_info(self):
        """
        Return a dictionary containing key-value pairs for the information
        items from the distro release file data source of the OS
        distribution.

        For details, see :func:`distro.distro_release_info`.
        """
        return self._distro_release_info

    def uname_info(self):
        """
        Return a dictionary containing key-value pairs for the information
        items from the uname command data source of the OS distribution.

        For details, see :func:`distro.uname_info`.
        """
        return self._uname_info

    def os_release_attr(self, attribute):
        """
        Return a single named information item from the os-release file data
        source of the OS distribution.

        For details, see :func:`distro.os_release_attr`.
        """
        return self._os_release_info.get(attribute, '')

    def lsb_release_attr(self, attribute):
        """
        Return a single named information item from the lsb_release command
        output data source of the OS distribution.

        For details, see :func:`distro.lsb_release_attr`.
        """
        return self._lsb_release_info.get(attribute, '')

    def distro_release_attr(self, attribute):
        """
        Return a single named information item from the distro release file
        data source of the OS distribution.

        For details, see :func:`distro.distro_release_attr`.
        """
        return self._distro_release_info.get(attribute, '')

    def uname_attr(self, attribute):
        """
        Return a single named information item from the uname command
        output data source of the OS distribution.

        For details, see :func:`distro.uname_release_attr`.
        """
        return self._uname_info.get(attribute, '')

    @cached_property
    def _os_release_info(self):
        """
        Get the information items from the specified os-release file.

        Returns:
            A dictionary containing all information items.
        """
        if os.path.isfile(self.os_release_file):
            with open(self.os_release_file) as release_file:
                return self._parse_os_release_content(release_file)
        return {}

    @staticmethod
    def _parse_os_release_content(lines):
        """
        Parse the lines of an os-release file.

        Parameters:

        * lines: Iterable through the lines in the os-release file.
                 Each line must be a unicode string or a UTF-8 encoded byte
                 string.

        Returns:
            A dictionary containing all information items.
        """
        props = {}
        lexer = shlex.shlex(lines, posix=True)
        lexer.whitespace_split = True

        # The shlex module defines its `wordchars` variable using literals,
        # making it dependent on the encoding of the Python source file.
        # In Python 2.6 and 2.7, the shlex source file is encoded in
        # 'iso-8859-1', and the `wordchars` variable is defined as a byte
        # string. This causes a UnicodeDecodeError to be raised when the
        # parsed content is a unicode object. The following fix resolves that
        # (... but it should be fixed in shlex...):
        if sys.version_info[0] == 2 and isinstance(lexer.wordchars, bytes):
            lexer.wordchars = lexer.wordchars.decode('iso-8859-1')

        tokens = list(lexer)
        for token in tokens:
            # At this point, all shell-like parsing has been done (i.e.
            # comments processed, quotes and backslash escape sequences
            # processed, multi-line values assembled, trailing newlines
            # stripped, etc.), so the tokens are now either:
            # * variable assignments: var=value
            # * commands or their arguments (not allowed in os-release)
            if '=' in token:
                k, v = token.split('=', 1)
                props[k.lower()] = v
            else:
                # Ignore any tokens that are not variable assignments
                pass

        if 'version_codename' in props:
            # os-release added a version_codename field.  Use that in
            # preference to anything else Note that some distros purposefully
            # do not have code names.  They should be setting
            # version_codename=""
            props['codename'] = props['version_codename']
        elif 'ubuntu_codename' in props:
            # Same as above but a non-standard field name used on older Ubuntus
            props['codename'] = props['ubuntu_codename']
        elif 'version' in props:
            # If there is no version_codename, parse it from the version
            codename = re.search(r'(\(\D+\))|,(\s+)?\D+', props['version'])
            if codename:
                codename = codename.group()
                codename = codename.strip('()')
                codename = codename.strip(',')
                codename = codename.strip()
                # codename appears within paranthese.
                props['codename'] = codename

        return props

    @cached_property
    def _lsb_release_info(self):
        """
        Get the information items from the lsb_release command output.

        Returns:
            A dictionary containing all information items.
        """
        if not self.include_lsb:
            return {}
        with open(os.devnull, 'w') as devnull:
            try:
                cmd = ('lsb_release', '-a')
                stdout = subprocess.check_output(cmd, stderr=devnull)
            except OSError:  # Command not found
                return {}
        content = self._to_str(stdout).splitlines()
        return self._parse_lsb_release_content(content)

    @staticmethod
    def _parse_lsb_release_content(lines):
        """
        Parse the output of the lsb_release command.

        Parameters:

        * lines: Iterable through the lines of the lsb_release output.
                 Each line must be a unicode string or a UTF-8 encoded byte
                 string.

        Returns:
            A dictionary containing all information items.
        """
        props = {}
        for line in lines:
            kv = line.strip('\n').split(':', 1)
            if len(kv) != 2:
                # Ignore lines without colon.
                continue
            k, v = kv
            props.update({k.replace(' ', '_').lower(): v.strip()})
        return props

    @cached_property
    def _uname_info(self):
        with open(os.devnull, 'w') as devnull:
            try:
                cmd = ('uname', '-rs')
                stdout = subprocess.check_output(cmd, stderr=devnull)
            except OSError:
                return {}
        content = self._to_str(stdout).splitlines()
        return self._parse_uname_content(content)

    @staticmethod
    def _parse_uname_content(lines):
        props = {}
        match = re.search(r'^([^\s]+)\s+([\d\.]+)', lines[0].strip())
        if match:
            name, version = match.groups()

            # This is to prevent the Linux kernel version from
            # appearing as the 'best' version on otherwise
            # identifiable distributions.
            if name == 'Linux':
                return {}
            props['id'] = name.lower()
            props['name'] = name
            props['release'] = version
        return props

    @staticmethod
    def _to_str(text):
        encoding = sys.getfilesystemencoding()
        encoding = 'utf-8' if encoding == 'ascii' else encoding

        if sys.version_info[0] >= 3:
            if isinstance(text, bytes):
                return text.decode(encoding)
        else:
            if isinstance(text, unicode):  # noqa
                return text.encode(encoding)

        return text

    @cached_property
    def _distro_release_info(self):
        """
        Get the information items from the specified distro release file.

        Returns:
            A dictionary containing all information items.
        """
        if self.distro_release_file:
            # If it was specified, we use it and parse what we can, even if
            # its file name or content does not match the expected pattern.
            distro_info = self._parse_distro_release_file(
                self.distro_release_file)
            basename = os.path.basename(self.distro_release_file)
            # The file name pattern for user-specified distro release files
            # is somewhat more tolerant (compared to when searching for the
            # file), because we want to use what was specified as best as
            # possible.
            match = _DISTRO_RELEASE_BASENAME_PATTERN.match(basename)
            if 'name' in distro_info \
               and 'cloudlinux' in distro_info['name'].lower():
                distro_info['id'] = 'cloudlinux'
            elif match:
                distro_info['id'] = match.group(1)
            return distro_info
        else:
            try:
                basenames = os.listdir(_UNIXCONFDIR)
                # We sort for repeatability in cases where there are multiple
                # distro specific files; e.g. CentOS, Oracle, Enterprise all
                # containing `redhat-release` on top of their own.
                basenames.sort()
            except OSError:
                # This may occur when /etc is not readable but we can't be
                # sure about the *-release files. Check common entries of
                # /etc for information. If they turn out to not be there the
                # error is handled in `_parse_distro_release_file()`.
                basenames = ['SuSE-release',
                             'arch-release',
                             'base-release',
                             'centos-release',
                             'fedora-release',
                             'gentoo-release',
                             'mageia-release',
                             'mandrake-release',
                             'mandriva-release',
                             'mandrivalinux-release',
                             'manjaro-release',
                             'oracle-release',
                             'redhat-release',
                             'sl-release',
                             'slackware-version']
            for basename in basenames:
                if basename in _DISTRO_RELEASE_IGNORE_BASENAMES:
                    continue
                match = _DISTRO_RELEASE_BASENAME_PATTERN.match(basename)
                if match:
                    filepath = os.path.join(_UNIXCONFDIR, basename)
                    distro_info = self._parse_distro_release_file(filepath)
                    if 'name' in distro_info:
                        # The name is always present if the pattern matches
                        self.distro_release_file = filepath
                        distro_info['id'] = match.group(1)
                        if 'cloudlinux' in distro_info['name'].lower():
                            distro_info['id'] = 'cloudlinux'
                        return distro_info
            return {}

    def _parse_distro_release_file(self, filepath):
        """
        Parse a distro release file.

        Parameters:

        * filepath: Path name of the distro release file.

        Returns:
            A dictionary containing all information items.
        """
        try:
            with open(filepath) as fp:
                # Only parse the first line. For instance, on SLES there
                # are multiple lines. We don't want them...
                return self._parse_distro_release_content(fp.readline())
        except (OSError, IOError):
            # Ignore not being able to read a specific, seemingly version
            # related file.
            # See https://github.com/nir0s/distro/issues/162
            return {}

    @staticmethod
    def _parse_distro_release_content(line):
        """
        Parse a line from a distro release file.

        Parameters:
        * line: Line from the distro release file. Must be a unicode string
                or a UTF-8 encoded byte string.

        Returns:
            A dictionary containing all information items.
        """
        matches = _DISTRO_RELEASE_CONTENT_REVERSED_PATTERN.match(
            line.strip()[::-1])
        distro_info = {}
        if matches:
            # regexp ensures non-None
            distro_info['name'] = matches.group(3)[::-1]
            if matches.group(2):
                distro_info['version_id'] = matches.group(2)[::-1]
            if matches.group(1):
                distro_info['codename'] = matches.group(1)[::-1]
        elif line:
            distro_info['name'] = line.strip()
        return distro_info


class Utility(object):
    """Utility class has utility functions used by other modules"""
    LINUX_DISTRO = LinuxDistribution()

    def __init__(self):
        self.standard_datetime_format = "%Y-%m-%dT%H:%M:%S"
        self.touch_cmd = 'sudo touch '
        self.chown_cmd = 'sudo chown '
        self.omsagentusergroup = 'omsagent:omiusers '
        self.chmod_cmd = 'sudo chmod '
        self.permissions = 'u=rw,g=rw,o=r '

    def run_command_output(self, cmd, no_output, chk_err=True):
        """
        Wrapper for subprocess.check_output. Execute 'cmd'.
        Returns return code and STDOUT, trapping expected exceptions.
        Reports exceptions to Error if chk_err parameter is True
        """

        def check_output(no_output, *popenargs, **kwargs):
            """
            Backport from subprocess module from python 2.7
            """
            if 'stdout' in kwargs:
                raise ValueError(
                    'stdout argument not allowed, it will be overridden.')
            if no_output is True:
                out_file = None
            else:
                out_file = subprocess.PIPE

            process = subprocess.Popen(stdout=out_file, *popenargs, **kwargs)
            output, unused_err = process.communicate()
            retcode = process.poll()

            if retcode:
                cmd = kwargs.get("args")
                if cmd is None:
                    cmd = popenargs[0]
                raise subprocess.CalledProcessError(retcode,
                                                    cmd, output=output)
            return output

        class CalledProcessError(Exception):
            """Exception classes used by this module."""

            def __init__(self, returncode, cmd, output=None):
                self.returncode = returncode
                self.cmd = cmd
                self.output = output

            def __str__(self):
                return "Command '%s' returned non-zero exit status %d" \
                       % (self.cmd, self.returncode)

        subprocess.check_output = check_output
        subprocess.CalledProcessError = CalledProcessError
        try:
            output = subprocess.check_output(
                no_output, cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            if chk_err:
                print("Error: CalledProcessError.  Error Code is: " + str(e.returncode), file=sys.stdout)
                print("Error: CalledProcessError.  Command string was: " + e.cmd, file=sys.stdout)
                print("Error: CalledProcessError.  Command result was: " +
                      self.get_subprocess_output_as_asciistring((e.output[:-1])), file=sys.stdout)
            if no_output:
                return e.returncode, None
            else:
                return e.returncode, self.get_subprocess_output_as_asciistring(e.output)

        if no_output:
            return 0, None
        else:
           return 0, self.get_subprocess_output_as_asciistring(output)
    

    def get_subprocess_output_as_asciistring(self, subprocess_output):
        if subprocess_output is None:
            return None
        
        # python 3
        if sys.version_info[0] >= 3:
            return subprocess_output.decode('ascii', 'ignore')

        return subprocess_output.decode('utf8', 'ignore').encode('ascii', 'ignore')
    
    @staticmethod
    def get_linux_distribution():
        return Utility.LINUX_DISTRO.linux_distribution(full_distribution_name=False)    

utils = Utility()


rule_info_list = []
output = []

oms_admin_conf_path = "/etc/opt/microsoft/omsagent/conf/omsadmin.conf"
oms_agent_dir = "/var/opt/microsoft/omsagent"
oms_agent_log = "/var/opt/microsoft/omsagent/log/omsagent.log"
current_mof = "/etc/opt/omi/conf/omsconfig/configuration/Current.mof"
status_passed = "Passed"
status_failed = "Failed"
status_debug = "Debug"
empty_failure_reason = ""
workspace = ""

class RuleInfo:
    def __init__(self, rule_id, rule_group_id, status, result_msg_id):
        self.RuleId = rule_id
        self.RuleGroupId = rule_group_id
        self.CheckResult = status
        self.CheckResultMessageId = result_msg_id
        self.CheckResultMessageArguments = list()

def enum(**enums):
    return type('Enum', (), enums)

def printDebug(*args):
    args = [str(x) for x in args]
    msg = ''.join(args)
    print("RepoAccessCheck:: " + msg)

OSType = enum(NotAvailable = 0, Ubuntu = 1, Suse = 2, Redhat = 3, CentOs = 4)

class RepositoryManager:
    def __init__(self):
        self.logs = [] #List of tuple of msg and status

    def appendToLogs(self, msg, status):
        self.logs.append((msg, status))

    def checkRule(self):
        osInQuestion = get_os_type()
        
        repoUriList = self.getConfiguredRepos(osInQuestion)
        self.appendToLogs("repo URI List", status_debug)
        if repoUriList is None:
            return 0  #failed
        status = self.pingRepos(repoUriList)  #uncomment this

        if status == 0:
            self.appendToLogs("Access Check for Repo failed !", status_debug)
        return status

    def getConfiguredRepos(self, osType):
        #support for rhel, ubuntu, suse, centos
        if osType == OSType.Ubuntu:
            repoList = self.getConfiguredReposForUbuntu() 
        elif osType == OSType.Suse:
            repoList = self.getConfiguredReposForSuse()
        elif osType == OSType.Redhat:
            repoList = self.getConfiguredReposForRhel()
        elif osType == OSType.CentOs:
            repoList = self.getConfiguredReposForCentos()
        else:
            self.appendToLogs("OS Not Supported")
            repoList = None #os type not supported.
        return repoList

    def getConfiguredReposForSuse(self):
        repoDirectory = "/etc/zypp/repos.d/"
        if os.path.exists(repoDirectory) is False:
            self.appendToLogs("Error - Repo Directory /etc/zypp/repos.d/ not present", status_debug)
            return None

        unixCmd = "zypper refresh"

        self.appendToLogs("Refereshing Zypper Repos", status_debug)
        code, out = utils.run_command_output(unixCmd, False, False)
        if code == 0:
            self.appendToLogs("Success: Repositories refereshed successfully.", status_debug)
            return [] #success, repositories successfully refreshed means also accessible


    def getConfiguredReposForRhel(self):
        repoDirectory = "/etc/yum.repos.d/"
        if os.path.exists(repoDirectory) is False:
            self.appendToLogs("Error - Repo Directory /etc/yum.repos.d/ not present", status_debug)
            return None
        
        unixCmd =  "grep -roEh 'https?://[-A-Za-z0-9+&@#/%?=~_|!:,.;]*[-A-Za-z0-9+&@#/%=~_|]' /etc/yum.repos.d"
        (out, err) = self.executeCommand(unixCmd)

        if err != '':
            self.appendToLogs("Error while extracted repos -- " + err, status_debug)
            return None

        repoList = []
        out = out.split("\n")
        for o in out:
            if len(o) > 2:
                repoList.append(o)
        return repoList

    def getConfiguredReposForCentos(self):
        repoDirectory = "/etc/yum.repos.d/"
        if os.path.exists(repoDirectory) is False:
            self.appendToLogs("Error - Repo Directory /etc/yum.repos.d/ not present", status_debug)
            return None
        
        unixCmd =  "grep -roEh 'https?://[-A-Za-z0-9+&@#/%?=~_|!:,.;]*[-A-Za-z0-9+&@#/%=~_|]' /etc/yum.repos.d"
        (out, err) = self.executeCommand(unixCmd)

        if err != '':
            self.appendToLogs("Error while extracted repos -- " + err, status_debug)
            return None

        repoList = []
        out = out.split("\n")
        for o in out:
            if len(o) > 2:
                repoList.append(o)
        return repoList

    def getConfiguredReposForUbuntu(self):
        repoFile = "/etc/apt/sources.list"
        if os.path.isfile(repoFile) is False:
            self.appendToLogs("Error - Repo File /etc/apt/sources.list not present", status_debug)
            return None
        
        unixCmd = "grep -Erh ^deb /etc/apt/sources.list*"

        (out, err) = self.executeCommand(unixCmd)

        if err != '':
            self.appendToLogs("Error while extracted repos -- " + err, status_debug)
            return None
        
        out1 = out.split("\n")
        repoList = []
        for str1 in out1:
            strList = str1.split(" ")
            if len(strList) >= 2: #format: "deb uri", excluding space or other invalid strings
                repoList.append(strList[1])
        return repoList


    def executeCommand(self, unixCmd):
        proc = subprocess.Popen(unixCmd,
                                stdin = subprocess.PIPE,
                                stdout = subprocess.PIPE,
                                stderr = subprocess.PIPE,
                                shell=True
                            )
        (out, err) = proc.communicate()
        return (out.decode('utf8', 'ignore'), err.decode('utf8', 'ignore'))

    def pingRepos(self, repoUris):
        if len(repoUris) == 0:
            return 1 #success, nothing to check

        repoUris = self.extractNetLocFromUris(repoUris)
        self.appendToLogs("Extracted RepoURI netloc List: " + str(set(repoUris)), status_debug)

        status = 1
        for uri in repoUris:
            status &= self.pingEndpoint(uri)  #not stopping here, because want to ping all uris present
            
        if status == 0:
            self.appendToLogs("Error - Not able to ping all repositories!", status_debug)
            return 0  #failure
        return 1  #success

    def pingEndpoint(self, uri):
        hostname = uri
        response = os.system("ping -c 1 " + hostname + " >/dev/null 2>&1")

        if response == 0:
            self.appendToLogs(hostname + ' Ping successful!', status_debug)
            return 1

        sleep_wait=1
        max_ping_wait=2
        count=0
        #will try pinging till 2 seconds.
        while (count < max_ping_wait and os.system("ping -c 1 " + hostname + " >/dev/null 2>&1")):
            time.sleep(sleep_wait)
            count+=1

        if (count < max_ping_wait):
            self.appendToLogs(hostname + ' Ping successful!', status_debug)
            return 1
        else:
            self.appendToLogs(hostname + ' Ping unsuccessful.', status_debug)
            return 0

    def extractNetLocFromUris(self, repoUris):
        netLocList = []
        for uri in repoUris:
            currentNetLoc = None
            parsed = urlparse(uri)
            if parsed.netloc == '':  #since netloc is empty, possible it's present in path
                path = parsed.path
                if path is not None:
                    if "/" not in path:  #case of uri 'google.com'
                        currentNetLoc = path
                    else:
                        path = path.split("/")
                        if path[0] == '':  #case of uri "/google.com/path/to"
                            if path[1] != '':
                                currentNetLoc = path[1]
                        else:              #case of uri "google.com/path/to" 
                            currentNetLoc = path[0]
            else:
                currentNetLoc = parsed.netloc   # got netloc

            if currentNetLoc is None:
                self.appendToLogs("Unable to get netLoc for URI: " + uri + " Skipping it...", status_debug)
            else:
                netLocList.append(currentNetLoc)   

        netLocList = list(set(netLocList))
        return netLocList  

def check_access_to_linux_repos():
    rule_id = "Linux.ReposAccessCheck"
    rule_group_id = "connectivity"

    repoMgr = RepositoryManager()
    status = repoMgr.checkRule()
    logs = repoMgr.logs

    for log in logs:
        write_log_output(rule_id, rule_group_id, log[1], empty_failure_reason, log[0])

    if status == 0:
        write_log_output(rule_id, rule_group_id, status_failed, empty_failure_reason, "Some of the repositories configured could not be accessed")
    else:
        write_log_output(rule_id, rule_group_id, status_passed, empty_failure_reason, "Repositories Configured Properly & Accessible")

def main(output_path=None, return_json_output="False"):
    if os.geteuid() != 0:
        print ("Please run this script as root")
        exit()

    # supported python version greter than 2.7.x

    if(sys.version_info[0] == 2) and (sys.version_info[1] < 7):
        print("Unsupport python version:" + str(sys.version_info))
#       exit()


    print ("Processing Information...[can take upto 5 minutes]")

    get_machine_info()
    check_os_version()
    check_proxy_connectivity()
    check_general_internet_connectivity()
    if(1 == check_imds_connectivity()):
        check_azcmagent()
        check_arc_extension()
    else:
        check_azureagent()
    check_azure_extension()
    check_autoassessment_service()

    try:
        print ("Checking access to linux repos")
        check_access_to_linux_repos()
    except Exception as e:
        pass

    if return_json_output == "True":
        print (json.dumps([obj.__dict__ for obj in rule_info_list]))
    else:
        for line in output:
            print (line)

        if output_path is not None:
            try:
                os.makedirs(output_path)
            except OSError:
                if not os.path.isdir(output_path):
                    raise 
            log_path = "%s/healthcheck-%s.log" % (output_path, datetime.datetime.utcnow().isoformat())
            f = open(log_path, "w")
            f.write("".join(output))
            f.close()
            print ("Output is written to " + log_path)

def get_machine_info():
    FNULL = open(os.devnull, "w")
    if subprocess.call(["which", "hostnamectl"], stdout=FNULL, stderr=FNULL) == 0:
        hostname_output = os.popen("hostnamectl").read()
        write_log_output(None, None, status_debug, empty_failure_reason, "Machine Information:" + hostname_output)
    FNULL.close()
    return hostname_output

def get_os_type():
    vmMachineInfo = get_machine_info()
    if vmMachineInfo is None:
        vmMachineInfo = ""

    os_tuple = utils.get_linux_distribution()
    os_version = os_tuple[0] + "-" + os_tuple[1]
    if re.search("Ubuntu", os_version, re.IGNORECASE) != None or re.search("Ubuntu", vmMachineInfo, re.IGNORECASE) != None:
        return OSType.Ubuntu
    elif re.search("SuSE", os_version, re.IGNORECASE) != None or re.search("suse", vmMachineInfo, re.IGNORECASE) != None:
        return OSType.Suse
    elif re.search("redhat", os_version, re.IGNORECASE) != None or re.search("red hat", vmMachineInfo, re.IGNORECASE) != None:
        return OSType.Redhat
    elif re.search("centos", os_version, re.IGNORECASE) != None or re.search("centos", vmMachineInfo, re.IGNORECASE) != None:
        return OSType.CentOs
    else:
        return OSType.NotAvailable

def check_os_version():
    rule_id = "Linux.OperatingSystemCheck"
    rule_group_id = "prerequisites"
    os_tuple = utils.get_linux_distribution()
    os_version = os_tuple[0] + "-" + os_tuple[1]
    supported_os_url = "https://docs.microsoft.com/en-us/azure/automation/automation-update-management#clients"
    # We support (Ubuntu 14.04, Ubuntu 16.04, SuSE 11, SuSE 12, Redhat 6, Redhat 7, CentOs 6, CentOs 7)
    if re.search("Ubuntu-20.04", os_version, re.IGNORECASE) or \
       re.search("Ubuntu-16.04", os_version, re.IGNORECASE) or \
       re.search("Ubuntu-18.04", os_version, re.IGNORECASE) or \
       re.search("SuSE-12", os_version, re.IGNORECASE) or \
       re.search("SLES-12", os_version, re.IGNORECASE) or \
       re.search("SLES-15", os_version, re.IGNORECASE) or \
       re.search("SuSE-15", os_version, re.IGNORECASE) or \
       re.search("rhel-7", os_version, re.IGNORECASE) or \
       re.search("rhel-8", os_version, re.IGNORECASE) or \
       re.search("centos-8", os_version, re.IGNORECASE) or \
       re.search("centos-7", os_version, re.IGNORECASE) or \
       re.search("Oracle-8", os_version, re.IGNORECASE) or \
       re.search("Oracle-7", os_version, re.IGNORECASE) :
        write_log_output(rule_id, rule_group_id, status_passed, empty_failure_reason, "Operating system version is supported")
    else:
        log_msg = "Operating System version (%s) is not supported. Supported versions listed here: %s" % (os_version, supported_os_url)
        write_log_output(rule_id, rule_group_id, status_failed, empty_failure_reason, log_msg, supported_os_url)

def check_proxy_connectivity():
    rule_id = "Linux.ProxyCheck"
    rule_group_id = "connectivity"

    if os.environ.get('HTTP_PROXY') is None:
        write_log_output(rule_id, rule_group_id, status_passed, empty_failure_reason, "Machine has no proxy enabled.")
    else:
        write_log_output(rule_id, rule_group_id, status_failed, empty_failure_reason, "Machine has proxy enabled.")

def check_imds_connectivity():
    rule_id = "Linux.ImdsCheck"
    rule_group_id = "connectivity"
    #http://169.254.169.254/metadata/instance/compute?api-version=2019-06-01
    curl_cmd = "curl -H \"Metadata: true\" http://169.254.169.254/metadata/instance/compute?api-version=2019-06-01"
    code, out = utils.run_command_output(curl_cmd, False, False)

    if code == 0:
        write_log_output(rule_id, rule_group_id, status_debug, empty_failure_reason, "IMDS Server Information: " + str(out))
        write_log_output(rule_id, rule_group_id, status_passed, empty_failure_reason, "Machine is able to reach IMDS server. This is Azure Machine")
        return 0
    else:
        write_log_output(rule_id, rule_group_id, status_passed, empty_failure_reason, "Machine is not able to reach IMDS server. This is ARC machine")
        return 1

def check_general_internet_connectivity():
    rule_id = "Linux.InternetConnectionCheck"
    rule_group_id = "connectivity"

    if check_endpoint(None, "bing.com") and check_endpoint(None, "google.com"):
        write_log_output(rule_id, rule_group_id, status_passed, empty_failure_reason, "Machine is connected to internet")
    else:
        write_log_output(rule_id, rule_group_id, status_failed, empty_failure_reason, "Machine is not connected to internet")

def check_endpoint(workspace, endpoint):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    new_endpoint = None

    if "*" in endpoint and workspace is not None:
        new_endpoint = endpoint.replace("*", workspace)
    elif "*" not in endpoint:
        new_endpoint = endpoint

    if new_endpoint is not None:
        try:
            response = sock.connect_ex((new_endpoint, 443))

            if response == 0:
                return True
            else:
                return False

        except Exception as ex:
            return False
    else:
        return False

def check_azureagent():
    # currently dummy function need to update with azure agent related checks
    return 0

def check_arc_extension():
    rule_id = "Linux.ArcExtension"
    rule_group_id = "Extensions"
    command = "ls /var/lib/waagent/ | grep Microsoft.SoftwareUpdateManagement.LinuxOsUpdateExtension"
    grep_output = os.popen(command).read()
    if( grep_output == ""):
            write_log_output(rule_id, rule_group_id, status_debug, empty_failure_reason, " LinuxOsUpdateExtension is not installed")
    else:
        write_log_output(rule_id, rule_group_id, status_debug, empty_failure_reason, " LinuxOsUpdateExtension is installed: "+ str(grep_output))


def check_azure_extension():
    rule_id = "Linux.AzureExtension"
    rule_group_id = "Extensions"
    command = "ls /var/lib/waagent/ | grep Microsoft.CPlat.Core.LinuxPatchExtension"
    grep_output = os.popen(command).read()
    if( grep_output == ""):
            write_log_output(rule_id, rule_group_id, status_debug, empty_failure_reason, " LinuxPatchExtension is not installed")
    else:
        write_log_output(rule_id, rule_group_id, status_debug, empty_failure_reason, " LinuxPatchExtension is installed: "+ str(grep_output))

def check_autoassessment_service():
    rule_id = "Linux.AutoAssessment"
    rule_group_id = "Extensions"
    command = "sudo systemctl is-active AzGPSLinuxPatchAutoAssess.timer"
    grep_output = os.popen(command).read()
    if "active" not in str(grep_output):
        write_log_output(rule_id, rule_group_id, status_failed, empty_failure_reason," AzGPSLinuxPatchAutoAssess.timer is not active")
    else:
        write_log_output(rule_id, rule_group_id, status_passed , empty_failure_reason, " AzGPSLinuxPatchAutoAssess.timer is active")


    command = "sudo systemctl is-enabled AzGPSLinuxPatchAutoAssess.service"
    grep_output = os.popen(command).read()
    if "enabled" not in str(grep_output):
        write_log_output(rule_id, rule_group_id, status_failed, empty_failure_reason," AzGPSLinuxPatchAutoAssess.service is not enabled")
    else:
        write_log_output(rule_id, rule_group_id, status_passed , empty_failure_reason, " AzGPSLinuxPatchAutoAssess.service is enabled")
    return 0


def check_azcmagent():
    rule_id = "Linux.AgentAndServices"
    rule_group_id = "Agent"
    def check_service_state(service_name):
        command = "azcmagent show | grep %s" % (service_name)
        grep_output = os.popen(command).read()
        if "active" not in str(grep_output):
            write_log_output(rule_id, rule_group_id, status_failed, empty_failure_reason, str(service_name) + " servicce is not active")
        else:
            write_log_output(rule_id, rule_group_id, status_passed , empty_failure_reason, str(service_name) + " servicce is active")

    FNULL = open(os.devnull, "w")
    if subprocess.call(["which", "azcmagent"], stdout=FNULL, stderr=FNULL) == 0:
        check_service_state("extd")
        check_service_state("gcad")
        check_service_state("himdsd")
        command = "azcmagent show"
        grep_output = os.popen(command).read()
        write_log_output(rule_id, rule_group_id, status_debug, empty_failure_reason, str(grep_output))
    else:
        write_log_output(rule_id, rule_group_id, status_failed , empty_failure_reason, "azcmagent is not present on the machine")
    FNULL.close()


def is_process_running(process_name, search_criteria, output_name):
    command = "ps aux | grep %s | grep -v grep" % (process_name)
    grep_output = os.popen(command).read()
    if any(search_text in grep_output for search_text in search_criteria):
        return True, grep_output
    else:
        return False, grep_output

def write_log_output(rule_id, rule_group_id, status, failure_reason, log_msg, *result_msg_args):
    global output, rule_info_list

    if(type(log_msg) != str):
        log_msg = str(log_msg)

    if status != status_debug:
        if failure_reason == empty_failure_reason:
            result_msg_id = rule_id + "." + status
        else:
            result_msg_id = rule_id + "." + status + "." + failure_reason

        current_rule_info = RuleInfo(rule_id, rule_group_id, status, result_msg_id)

        result_msg_args_list = []
        for arg in result_msg_args:
            current_rule_info.CheckResultMessageArguments.append(arg)

        rule_info_list.append(current_rule_info)

    output.append(status + ": " + log_msg + "\n")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        main(sys.argv[1], sys.argv[2])
    elif len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
