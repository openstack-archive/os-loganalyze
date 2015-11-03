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


import ConfigParser
import fileinput
import os.path
import sys

import os_loganalyze.filter as osfilter
import os_loganalyze.generator as osgen
import os_loganalyze.view as osview


def htmlify_stdin():
    out = sys.stdout
    gen = osview.HTMLView(fileinput.FileInput())
    for line in gen:
        out.write(line)


def get_config(wsgi_config):
    config = ConfigParser.ConfigParser()
    config.read(os.path.expanduser(wsgi_config))
    return config


def get_range(environ, start_response, view_generator):
        if '-' not in environ['HTTP_RANGE']:
            status = '400 Bad Request'
            response_headers = [('Content-type', 'text/plain')]
            start_response(status, response_headers)
            yield 'Invalid Range'
            return

        _range = environ['HTTP_RANGE'].split('=')[1].split('-')

        try:
            start = None
            if _range[0] is not '':
                start = int(_range[0])

            end = None
            if _range[1] is not '':
                end = int(_range[1])
        except ValueError:
            status = '400 Bad Request'
            response_headers = [('Content-type', 'text/plain')]
            start_response(status, response_headers)
            yield 'Invalid Range'
            return

        if start is None and end is None:
            status = '400 Bad Request'
            response_headers = [('Content-type', 'text/plain')]
            start_response(status, response_headers)
            yield 'Invalid Range'
            return

        # bytes=-5 means the last 5 bytes
        remainder = None
        if start is None:
            remainder = -end  # this will be a negative index
            start = 0
            end = None

        position = 0
        body = []

        status = '206 Partial Content'
        start_response(status, view_generator.headers)

        stop = False
        for chunk in view_generator:
            new_chunk = None

            if (position + len(chunk)) < start:
                # ignore this chunk
                position += len(chunk)
            elif position < start:
                # start is between position and position + len(chunk)
                # we only want a portion of this chunk
                offset = start - position
                if end and end < (position + len(chunk)):
                    # the entire range is a subset of this chunk
                    cutoff = end - position + 1
                    new_chunk = chunk[offset:cutoff]
                    stop = True  # don't break until we have yielded
                else:
                    new_chunk = chunk[offset:]
                    position += len(chunk[offset:])
            elif end and end <= (position + len(chunk)):
                cutoff = end - position + 1
                new_chunk = chunk[:cutoff]
                stop = True  # don't break until we have yielded
            else:
                new_chunk = chunk
                position += len(chunk)

            if remainder and new_chunk:
                body.append(new_chunk)
            elif new_chunk:
                yield new_chunk

            if stop:
                break

        if remainder:
            _body = ''.join(body)
            if len(_body) > -remainder:  # remainder is negative
                yield _body[remainder:]
            else:
                yield _body


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
        file_generator = osgen.get_file_generator(environ, root_path, config)
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

    filter_generator = osfilter.get_filter_generator(file_generator, environ,
                                                     root_path, config)
    view_generator = osview.get_view_generator(filter_generator, environ,
                                               root_path, config)

    if 'HTTP_RANGE' in environ:
        return get_range(environ, start_response, view_generator)

    else:
        start_response(status, view_generator.headers)
        return view_generator


# for development purposes, makes it easy to test the filter output
if __name__ == "__main__":
    htmlify_stdin()
