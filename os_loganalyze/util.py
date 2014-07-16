#!/usr/bin/python
#
# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
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

import cgi
import os
import time

import magic


def parse_param(env, name, default=None):
    parameters = cgi.parse_qs(env.get('QUERY_STRING', ''))
    if name in parameters:
        return cgi.escape(parameters[name][0])
    else:
        return default


def get_file_mime(file_path):
    """Get the file mime using libmagic."""

    if not os.path.isfile(file_path):
        return None

    if hasattr(magic, 'from_file'):
        return magic.from_file(file_path, mime=True)
    else:
        # no magic.from_file, we might be using the libmagic bindings
        m = magic.open(magic.MAGIC_MIME)
        m.load()
        return m.file(file_path).split(';')[0]


def get_headers_for_file(file_path):
    """Get some headers for a real (on-disk) file.

    In a format similar to fetching from swift.
    """

    resp = {}
    resp['content-length'] = str(os.stat(file_path).st_size)
    resp['accept-ranges'] = 'bytes'
    resp['last-modified'] = time.strftime(
        "%a, %d %b %Y %H:%M:%S GMT", time.gmtime(os.path.getmtime(file_path)))
    resp['etag'] = ''
    resp['x-trans-id'] = str(time.time())
    resp['date'] = time.strftime("%a, %d %b %Y %H:%M:%S GMT")
    resp['content-type'] = get_file_mime(file_path)
    return resp
