#!/usr/bin/env python
#
# Copyright (c) 2013 IBM Corp.
# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
# Copyright (c) 2014 Rackspace Australia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import collections
import datetime
import fileinput
import os.path
import re

import jinja2

import os_loganalyze.util as util


class UnsafePath(Exception):
    pass


class NoSuchFile(Exception):
    pass


def does_file_exist(fname):
    """Figure out if we'll be able to read this file.

    Because we are handling the file streams as generators, we actually raise
    an exception too late for us to be able to handle it before apache has
    completely control. This attempts to do the same open outside of the
    generator to trigger the IOError early enough for us to catch it, without
    completely changing the logic flow, as we really want the generator
    pipeline for performance reasons.

    This does open us up to a small chance for a race where the file comes
    or goes between this call and the next, however that is a vanishingly
    small possibility.
    """
    try:
        f = open(fname)
        f.close()
        return True
    except IOError:
        return False


def log_name(environ):
    path = environ['PATH_INFO']
    if path[0] == '/':
        path = path[1:]
    match = re.search('htmlify/(.*)', path)
    if match:
        raw = match.groups(1)[0]
        return raw

    return path


def safe_path(root, log_name):
    """Pull out a safe path from a url.

    Basically we need to ensure that the final computed path
    remains under the root path. If not, we return None to indicate
    that we are very sad.
    """
    if log_name is not None:
        newpath = os.path.abspath(os.path.join(root, log_name))
        if newpath.find(root) == 0:
            return newpath

    return None


def sizeof_fmt(num, suffix='B'):
    # From http://stackoverflow.com/questions/1094841/
    # reusable-library-to-get-human-readable-version-of-file-size
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)


class DiskIterableBuffer(collections.Iterable):
    def __init__(self, logname, logpath, config):
        self.logname = logname
        self.logpath = logpath
        self.resp_headers = {}
        self.obj = fileinput.FileInput(self.logpath,
                                       openhook=fileinput.hook_compressed)
        self.file_headers = {}
        self.file_headers['filename'] = logname
        self.file_headers.update(util.get_headers_for_file(logpath))

    def __iter__(self):
        return self.obj


class IndexIterableBuffer(collections.Iterable):
    def __init__(self, logname, logpath, config):
        self.logname = logname
        self.logpath = logpath
        self.config = config
        self.resp_headers = {}
        self.file_headers = {}
        self.file_headers['Content-type'] = 'text/html'

        # Use sets here to dedup. We can have duplicates
        # if disk and swift based paths have overlap.
        file_set = self.disk_list()
        # file_list is a list of tuples (relpath, name, mtime, size)
        self.file_list = sorted(file_set, key=lambda tup: tup[0])

    def disk_list(self):
        file_set = set()
        if os.path.isdir(self.logpath):
            for f in os.listdir(self.logpath):
                full_path = os.path.join(self.logpath, f)
                stat_info = os.stat(full_path)
                size = sizeof_fmt(stat_info.st_size)
                mtime = datetime.datetime.utcfromtimestamp(
                    stat_info.st_mtime).isoformat()
                if os.path.isdir(full_path):
                    f = f + '/' if f[-1] != '/' else f
                file_set.add((
                    os.path.join('/', self.logname, f),
                    f,
                    mtime,
                    size
                ))
        return file_set

    def __iter__(self):
        env = jinja2.Environment(
            loader=jinja2.PackageLoader('os_loganalyze', 'templates'))
        template = env.get_template('file_index.html')
        gen = template.generate(logname=self.logname,
                                file_list=self.file_list)
        for l in gen:
            yield l.encode("utf-8")


def get_file_generator(environ, root_path, config=None):
    logname = log_name(environ)
    logpath = safe_path(root_path, logname)
    if logpath is None:
        raise UnsafePath()

    file_generator = None
    if does_file_exist(logpath):
        file_generator = DiskIterableBuffer(logname, logpath, config)

    if not file_generator or not file_generator.obj:
        if (config.has_section('general') and
                config.has_option('general', 'generate_folder_index') and
                config.getboolean('general', 'generate_folder_index')):
            index_generator = IndexIterableBuffer(logname, logpath,
                                                  config)
            if len(index_generator.file_list) > 0:
                return index_generator
        raise NoSuchFile()

    return file_generator
