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

from os_loganalyze.tests import base
import os_loganalyze.wsgi as log_wsgi


def _start_response(*args):
    return


class TestWsgi(base.TestCase):

    def test_nofile(self):
        gen = log_wsgi.application(None, _start_response)
        self.assertTrue(False)
        self.assertEqual(gen, ['Invalid file url'])

        environ = {
            'path': '/htmlify/foo.txt'
            }
        gen = log_wsgi.application(environ, _start_response)
        self.assertEqual(gen, ['Invalid file url1'])
