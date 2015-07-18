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


def should_be_html(environ):
    """Simple content negotiation.

    If the client supports content negotiation, and asks for text/html,
    we give it to them, unless they also specifically want to override
    by passing ?content-type=text/plain in the query.

    This should be able to handle the case of dumb clients defaulting to
    html, but also let devs override the text format when 35 MB html
    log files kill their browser (as per a nova-api log).
    """
    text_override = False
    accepts_html = ('HTTP_ACCEPT' in environ and
                    'text/html' in environ['HTTP_ACCEPT'])
    parameters = cgi.parse_qs(environ.get('QUERY_STRING', ''))
    if 'content-type' in parameters:
        ct = cgi.escape(parameters['content-type'][0])
        if ct == 'text/plain':
            text_override = True

    return accepts_html and not text_override


def use_passthrough_view(file_headers):
    """Guess if we need to use the passthrough filter."""

    if 'content-type' not in file_headers:
        # For legacy we'll try and format. This shouldn't occur though.
        return False
    else:
        if file_headers['content-type'] in ['text/plain', 'text/html']:
            # We want to format these files
            return False
        if file_headers['content-type'] in ['application/x-gzip',
                                            'application/gzip']:
            # We'll need to guess if we should render the output or offer a
            # download.
            filename = file_headers['filename']
            filename = filename[:-3] if filename[-3:] == '.gz' else filename
            if os.path.splitext(filename)[1] in ['.txt', '.html']:
                return False
    return True
