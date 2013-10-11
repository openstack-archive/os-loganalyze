#!/usr/bin/python
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

"""
Test the ability to convert files into wsgi generators
"""

import os
import os.path
import types
from wsgiref.util import setup_testing_defaults

from os_loganalyze.tests import base
import os_loganalyze.wsgi as log_wsgi


def _start_response(*args):
    return


def fake_env(**kwargs):
    environ = dict(**kwargs)
    setup_testing_defaults(environ)
    print environ
    return environ


def samples_path():
    """ Create an abs path for our test samples

    Because the wsgi has a security check that ensures that we don't
    escape our root path, we need to actually create a full abs path
    for the tests, otherwise the sample files aren't findable.
    """
    return os.path.join(os.getcwd(), 'os_loganalyze/tests/samples/')


class TestWsgiBasic(base.TestCase):

    def test_invalid_file(self):
        gen = log_wsgi.application(fake_env(), _start_response)
        self.assertEqual(gen, ['Invalid file url'])

    def test_file_not_found(self):
        gen = log_wsgi.application(fake_env(PATH_INFO='/htmlify/foo.txt'),
                                   _start_response)
        self.assertEqual(gen, ['File Not Found'])

    def test_found_file(self):
        gen = log_wsgi.application(
            fake_env(PATH_INFO='/htmlify/screen-c-api.txt.gz'),
            _start_response, root_path=samples_path())
        self.assertEqual(type(gen), types.GeneratorType)

    def test_plain_text(self):
        gen = log_wsgi.application(
            fake_env(PATH_INFO='/htmlify/screen-c-api.txt.gz'),
            _start_response, root_path=samples_path())

        first = gen.next()
        self.assertIn(
            '+ ln -sf /opt/stack/new/screen-logs/screen-c-api.2013-09-27-1815',
            first)

    def test_html_gen(self):
        gen = log_wsgi.application(
            fake_env(
                PATH_INFO='/htmlify/screen-c-api.txt.gz',
                HTTP_ACCEPT='text/html'
                ),
            _start_response, root_path=samples_path())

        first = gen.next()
        self.assertIn('<html>', first)
