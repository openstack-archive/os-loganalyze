#!/usr/bin/env python
#
# Copyright (c) 2013 IBM Corp.
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
import ConfigParser
import fileinput
import os.path
import sys

import os_loganalyze.filter as osfilter
import os_loganalyze.generator as osgen
import os_loganalyze.util as util
import os_loganalyze.view as osview


def htmlify_stdin():
    out = sys.stdout
    gen = osview.HTMLView(fileinput.FileInput())
    for line in gen:
        out.write(line)


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


def get_config(wsgi_config):
    config = ConfigParser.ConfigParser()
    config.read(os.path.expanduser(wsgi_config))
    return config


def application(environ, start_response, root_path=None,
                wsgi_config='/etc/os_loganalyze/wsgi.conf'):
    if root_path is None:
        root_path = environ.get('OS_LOGANALYZE_ROOT_PATH',
                                '/srv/static/logs')
    config = get_config(wsgi_config)

    # make root path absolute in case we have a path with local components
    # specified
    root_path = os.path.abspath(root_path)

    status = '200 OK'

    try:
        logname, flines_generator = osgen.get(environ, root_path, config)
    except osgen.UnsafePath:
        status = '400 Bad Request'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)
        return ['Invalid file url']
    except osgen.NoSuchFile:
        status = "404 Not Found"
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)
        return ['File Not Found']

    minsev = util.parse_param(environ, 'level', default="NONE")
    limit = util.parse_param(environ, 'limit')
    flines_generator = osfilter.Filter(
        logname, flines_generator, minsev, limit)
    if environ.get('OS_LOGANALYZE_STRIP', None):
        flines_generator.strip_control = True
    if should_be_html(environ):
        generator = osview.HTMLView(flines_generator)
    else:
        generator = osview.TextView(flines_generator)

    start_response(status, generator.headers)
    return generator


# for development purposes, makes it easy to test the filter output
if __name__ == "__main__":
    htmlify_stdin()
