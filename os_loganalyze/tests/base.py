# -*- coding: utf-8 -*-

# Copyright 2010-2011 OpenStack Foundation
# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import ConfigParser
import os
import os.path
import tempfile
import urllib
from wsgiref import util

import fixtures
import testtools

import os_loganalyze.wsgi as log_wsgi

_TRUE_VALUES = ('true', '1', 'yes')


def samples_path(append_folder='samples'):
    """Create an abs path for our test samples

    Because the wsgi has a security check that ensures that we don't
    escape our root path, we need to actually create a full abs path
    for the tests, otherwise the sample files aren't findable.
    """
    return os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            append_folder)) + os.sep


class TestCase(testtools.TestCase):

    """Test case base class for all unit tests."""

    def setUp(self):
        """Run before each test method to initialize test environment."""

        super(TestCase, self).setUp()
        test_timeout = os.environ.get('OS_TEST_TIMEOUT', 0)
        try:
            test_timeout = int(test_timeout)
        except ValueError:
            # If timeout value is invalid do not set a timeout.
            test_timeout = 0
        if test_timeout > 0:
            self.useFixture(fixtures.Timeout(test_timeout, gentle=True))

        self.useFixture(fixtures.NestedTempfile())
        self.useFixture(fixtures.TempHomeDir())

        if os.environ.get('OS_STDOUT_CAPTURE') in _TRUE_VALUES:
            stdout = self.useFixture(fixtures.StringStream('stdout')).stream
            self.useFixture(fixtures.MonkeyPatch('sys.stdout', stdout))
        if os.environ.get('OS_STDERR_CAPTURE') in _TRUE_VALUES:
            stderr = self.useFixture(fixtures.StringStream('stderr')).stream
            self.useFixture(fixtures.MonkeyPatch('sys.stderr', stderr))

        self.log_fixture = self.useFixture(fixtures.FakeLogger())
        self.samples_directory = 'samples'
        self.wsgi_config_file = samples_path('samples') + 'wsgi.conf'

    def _start_response(self, *args):
        return

    def fake_env(self, **kwargs):
        environ = dict(**kwargs)
        util.setup_testing_defaults(environ)
        return environ

    def _create_wsgi_config_file_for_job(self):
        # We need to create a new config file for each job run to have the
        # opportunity to modify paths to the tests samples dir
        config = ConfigParser.ConfigParser()
        config.read(os.path.expanduser(self.wsgi_config_file))

        if config.has_section('general'):
            if config.has_option('general', 'file_conditions'):
                config.set(
                    'general', 'file_conditions',
                    samples_path() + config.get('general', 'file_conditions'))
        fd, filename = tempfile.mkstemp()
        config.write(os.fdopen(fd, 'w'))
        return filename

    def get_generator(self, fname, level=None, html=True,
                      limit=None, source=None):
        kwargs = {'PATH_INFO': '/htmlify/%s/%s' % (self.samples_directory,
                                                   fname)}
        qs = {}
        if level:
            qs['level'] = level
        if limit:
            qs['limit'] = limit
        if source:
            qs['source'] = source
        if qs:
            kwargs['QUERY_STRING'] = urllib.urlencode(qs)

        if html:
            kwargs['HTTP_ACCEPT'] = 'text/html'

        gen = log_wsgi.application(
            self.fake_env(**kwargs),
            self._start_response,
            root_path=samples_path(''),
            wsgi_config=self._create_wsgi_config_file_for_job())

        return iter(gen)
