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

"""
Test the ability to convert files into wsgi generators
"""

import collections
import os
import re
import types

import mock
import swiftclient  # noqa needed for monkeypatching
import testtools

from os_loganalyze.tests import base
import os_loganalyze.util
import os_loganalyze.wsgi as log_wsgi


SEVS = {
    'NONE': 0,
    'DEBUG': 1,
    'INFO': 2,
    'AUDIT': 3,
    'TRACE': 4,
    'WARNING': 5,
    'ERROR': 6
    }

SEVS_SEQ = ['NONE', 'DEBUG', 'INFO', 'AUDIT', 'TRACE', 'WARNING', 'ERROR']

ISO8601RE = r'\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(.\d+)?'
TIME_REGEX = r'\d\d\d\d-\d\d-\d\d\s\d\d:\d\d:\d\d(.\d+)?'


# add up all the counts from a generator
def count_types(gen):
    counts = collections.defaultdict(lambda: 0)

    for line in gen:
        counted = False

        # is it even a proper log message?
        if re.match(TIME_REGEX, line):
            # skip NONE since it's an implicit level
            for key in SEVS_SEQ[1:]:
                if ' %s ' % key in line:
                    counts[key] += 1
                    counted = True
                    break
        if not counted:
            counts['NONE'] += 1
    return counts


# count up all the lines at all levels
def compute_total(level, counts):
    total = 0
    for l in SEVS_SEQ[SEVS[level]:]:
        # so that we don't need to know all the levels
        if counts.get(l):
            total = total + counts[l]
    return total


def fake_get_object(self, container, name, resp_chunk_size=None):
    name = name[len('non-existent/'):]
    if not os.path.isfile(base.samples_path('samples') + name):
        return {}, None
    if resp_chunk_size:

        def _object_body():
            with open(base.samples_path('samples') + name) as f:

                buf = f.read(resp_chunk_size)
                while buf:
                    yield buf
                    buf = f.read(resp_chunk_size)

        object_body = _object_body()
    else:
        with open(base.samples_path('samples') + name) as f:
            object_body = f.read()
    resp_headers = os_loganalyze.util.get_headers_for_file(
        base.samples_path('samples') + name)
    return resp_headers, object_body


def fake_get_container_factory(_swift_index_items=None):
    def fake_get_container(self, container, prefix=None, delimiter=None):
        index_items = []
        if _swift_index_items:
            for i in _swift_index_items:
                if i[-1] == '/':
                    index_items.append({'subdir': os.path.join(prefix, i)})
                else:
                    index_items.append({'name': os.path.join(prefix, i),
                                        'last_modified': '2042-12-31T23:59:59',
                                        'bytes': 4200})
        elif _swift_index_items == []:
            name = prefix[len('non-existent/'):]
            p = os.path.join(base.samples_path('samples'), name)
            for i in os.listdir(p):
                if os.path.isdir(os.path.join(p, i)):
                    index_items.append(
                        {'subdir': os.path.join(prefix, i + '/')})
                else:
                    index_items.append({'name': os.path.join(prefix, i),
                                        'last_modified': '2042-12-31T23:59:59',
                                        'bytes': 4200})
        else:
            # No swift container data.
            pass
        return {}, index_items
    return fake_get_container


class TestWsgiDisk(base.TestCase):
    """Test loading files from samples on disk."""

    # counts for known files for testing
    files = {
        'screen-c-api.txt.gz': {
            'DEBUG': 2804,
            'INFO': 486,
            'AUDIT': 249,
            'TRACE': 0,
            'WARNING': 50,
            'ERROR': 0,
            },
        'screen-n-api.txt.gz': {
            'DEBUG': 11886,
            'INFO': 2721,
            'AUDIT': 271,
            'TRACE': 0,
            'WARNING': 6,
            'ERROR': 5
            },
        'screen-q-svc.txt.gz': {
            'DEBUG': 43584,
            'INFO': 262,
            'AUDIT': 0,
            'TRACE': 589,
            'WARNING': 48,
            'ERROR': 72,
            },
        'screen-neutron-l3.txt.gz': {
            'DEBUG': 25212,
            'INFO': 85,
            'AUDIT': 0,
            'TRACE': 0,
            'WARNING': 122,
            'ERROR': 19,
            },
        }

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_pass_through_all(self):
        for fname in self.files:
            gen = self.get_generator(fname, html=False)
            self.assertEqual(
                compute_total('DEBUG', count_types(gen)),
                compute_total('DEBUG', self.files[fname]))

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_pass_through_at_levels(self):
        for fname in self.files:
            for level in self.files[fname]:
                gen = self.get_generator(fname, level=level, html=False)

                counts = count_types(gen)
                print(fname, counts)

                self.assertEqual(
                    compute_total(level, counts),
                    compute_total(level, self.files[fname]))

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_invalid_file(self):
        gen = log_wsgi.application(
            self.fake_env(PATH_INFO='../'), self._start_response)
        self.assertEqual(gen, ['Invalid file url'])

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_file_not_found(self):
        gen = log_wsgi.application(
            self.fake_env(PATH_INFO='/htmlify/foo.txt'),
            self._start_response)
        self.assertEqual(gen, ['File Not Found'])

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_plain_text(self):
        gen = self.get_generator('screen-c-api.txt.gz', html=False)
        self.assertEqual(type(gen), types.GeneratorType)

        first = gen.next()
        self.assertIn(
            '+ ln -sf /opt/stack/new/screen-logs/screen-c-api.2013-09-27-1815',
            first)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_html_gen(self):
        gen = self.get_generator('screen-c-api.txt.gz')
        first = gen.next()
        self.assertIn('<html>', first)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_plain_non_compressed(self):
        gen = self.get_generator('screen-c-api.txt', html=False)
        self.assertEqual(type(gen), types.GeneratorType)

        first = gen.next()
        self.assertIn(
            '+ ln -sf /opt/stack/new/screen-logs/screen-c-api.2013-09-27-1815',
            first)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_passthrough_filter(self):
        # Test the passthrough filter returns an image stream
        gen = self.get_generator('openstack_logo.png')
        first = gen.next()
        self.assertNotIn('html', first)
        with open(base.samples_path('samples') + 'openstack_logo.png') as f:
            self.assertEqual(first, f.readline())

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_config_no_filter(self):
        self.wsgi_config_file = (base.samples_path('samples') +
                                 'wsgi_plain.conf')
        # Try to limit the filter to 10 lines, but we should get the full
        # amount.
        gen = self.get_generator('devstacklog.txt.gz', limit=10)

        lines = 0
        for line in gen:
            lines += 1

        # the lines should actually be 2 + the limit we've asked for
        # given the header and footer, but we expect to get the full file
        self.assertNotEqual(12, lines)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_config_passthrough_view(self):
        self.wsgi_config_file = (base.samples_path('samples') +
                                 'wsgi_plain.conf')
        # Check there is no HTML on a file that should otherwise have it
        gen = self.get_generator('devstacklog.txt.gz')

        first = gen.next()
        self.assertNotIn('<html>', first)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_file_conditions(self):
        self.wsgi_config_file = (base.samples_path('samples') +
                                 'wsgi_file_conditions.conf')
        # Check we are matching and setting the HTML filter
        gen = self.get_generator('devstacklog.txt.gz')

        first = gen.next()
        self.assertIn('<html>', first)

        # Check for simple.html we don't have HTML but do have date lines
        gen = self.get_generator('simple.txt')

        first = gen.next()
        self.assertIn('2013-09-27 18:22:35.392 testing 123', first)

        # Test images go through the passthrough filter
        gen = self.get_generator('openstack_logo.png')
        first = gen.next()
        self.assertNotIn('html', first)
        with open(base.samples_path('samples') + 'openstack_logo.png') as f:
            self.assertEqual(first, f.readline())

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_accept_range(self):
        gen = self.get_generator('screen-c-api.txt.gz', range_bytes='0-5')
        body = gen.next()
        self.assertEqual('<html>', body)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_accept_range_seek(self):
        gen = self.get_generator('screen-c-api.txt.gz', range_bytes='7-12')
        body = gen.next()
        self.assertEqual('<head>', body)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_accept_range_no_start(self):
        gen = self.get_generator('screen-c-api.txt.gz', range_bytes='-8')
        body = gen.next()
        self.assertEqual('</html>\n', body)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_accept_range_no_end(self):
        gen = self.get_generator('screen-c-api.txt.gz', range_bytes='7-')
        body = gen.next()
        self.assertNotIn('<html>', body)
        self.assertIn('<head>', body)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_accept_range_no_start_no_end(self):
        gen = self.get_generator('screen-c-api.txt.gz', range_bytes='-')
        body = gen.next()
        self.assertEqual('Invalid Range', body)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_accept_range_no_hyphen(self):
        gen = self.get_generator('screen-c-api.txt.gz', range_bytes='7')
        body = gen.next()
        self.assertEqual('Invalid Range', body)

    @mock.patch.object(swiftclient.client.Connection, 'get_container',
                       fake_get_container_factory())
    def test_folder_index(self):
        self.wsgi_config_file = (base.samples_path('samples') +
                                 'wsgi_folder_index.conf')
        gen = self.get_generator('')
        full = ''
        for line in gen:
            full += line

        full_lines = full.split('\n')
        self.assertEqual('<!DOCTYPE html>', full_lines[0])
        self.assertIn('samples/</title>', full_lines[3])
        self.assertThat(
            full_lines[9],
            testtools.matchers.MatchesRegex(
                r'        <tr><td><a href="/samples/console.html.gz">'
                r'console.html.gz</a></td><td>' + ISO8601RE + r'</td>'
                r'<td style="text-align: right">277.4KB</td></tr>'))
        self.assertThat(
            full_lines[-5],
            testtools.matchers.MatchesRegex(
                r'        <tr><td><a href="/samples/wsgi_plain.conf">'
                r'wsgi_plain.conf</a></td><td>' + ISO8601RE + r'</td>'
                r'<td style="text-align: right">177.0B</td></tr>'))
        self.assertEqual('</html>', full_lines[-1])


class TestWsgiSwift(TestWsgiDisk):
    """Test loading files from swift."""
    def setUp(self):
        super(TestWsgiSwift, self).setUp()

        # Set the samples directory to somewhere non-existent so that swift
        # is checked for files
        self.samples_directory = 'non-existent'

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_compare_disk_to_swift_html(self):
        """Compare loading logs from disk vs swift."""
        # Load from disk
        self.samples_directory = 'samples'
        gen = self.get_generator('screen-c-api.txt.gz')
        result_disk = ''
        for line in gen:
            result_disk += line

        self.samples_directory = 'non-existent'
        gen = self.get_generator('screen-c-api.txt.gz')
        result_swift = ''
        for line in gen:
            result_swift += line

        self.assertEqual(result_disk, result_swift)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_compare_disk_to_swift_plain(self):
        """Compare loading logs from disk vs swift."""
        # Load from disk
        self.samples_directory = 'samples'
        gen = self.get_generator('screen-c-api.txt.gz', html=False)
        result_disk = ''
        for line in gen:
            result_disk += line

        self.samples_directory = 'non-existent'
        gen = self.get_generator('screen-c-api.txt.gz', html=False)
        result_swift = ''
        for line in gen:
            result_swift += line

        self.assertEqual(result_disk, result_swift)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_skip_file(self):
        # this should generate a TypeError because we're telling it to
        # skip the filesystem, but we don't have a working swift here.
        self.assertRaises(
            TypeError,
            self.get_generator('screen-c-api.txt.gz', source='swift'))

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_compare_disk_to_swift_no_compression(self):
        """Compare loading logs from disk vs swift."""
        # Load from disk
        self.samples_directory = 'samples'
        gen = self.get_generator('screen-c-api.txt')
        result_disk = ''
        for line in gen:
            result_disk += line

        self.samples_directory = 'non-existent'
        gen = self.get_generator('screen-c-api.txt')
        result_swift = ''
        for line in gen:
            result_swift += line

        self.assertEqual(result_disk, result_swift)

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    def test_compare_disk_to_swift_no_chunks(self):
        self.wsgi_config_file = (base.samples_path('samples') +
                                 'wsgi_no_chunks.conf')
        self.test_compare_disk_to_swift_no_compression()
        self.test_compare_disk_to_swift_plain()
        self.test_compare_disk_to_swift_html()

    @mock.patch.object(swiftclient.client.Connection, 'get_object',
                       fake_get_object)
    @mock.patch.object(swiftclient.client.Connection, 'get_container',
                       fake_get_container_factory([]))
    def test_folder_index(self):
        self.wsgi_config_file = (base.samples_path('samples') +
                                 'wsgi_folder_index.conf')
        gen = self.get_generator('')
        full = ''
        for line in gen:
            full += line

        full_lines = full.split('\n')
        self.assertEqual('<!DOCTYPE html>', full_lines[0])
        self.assertIn('non-existent/</title>', full_lines[3])
        self.assertThat(
            full_lines[9],
            testtools.matchers.MatchesRegex(
                r'        <tr><td><a href="/non-existent/console.html.gz">'
                r'console.html.gz</a></td><td>' + ISO8601RE + r'</td>'
                r'<td style="text-align: right">4.1KB</td></tr>'))
        self.assertThat(
            full_lines[-5],
            testtools.matchers.MatchesRegex(
                r'        <tr><td><a href="/non-existent/wsgi_plain.conf">'
                r'wsgi_plain.conf</a></td><td>' + ISO8601RE + r'</td>'
                r'<td style="text-align: right">4.1KB</td></tr>'))
        self.assertEqual('</html>', full_lines[-1])

    @mock.patch.object(swiftclient.client.Connection, 'get_container',
                       fake_get_container_factory(['a', 'b', 'dir/', 'z']))
    def test_folder_index_dual(self):
        # Test an index is correctly generated where files may exist on disk as
        # well as in swift.
        self.samples_directory = 'samples'
        self.wsgi_config_file = (base.samples_path('samples') +
                                 'wsgi_folder_index.conf')

        gen = self.get_generator('')
        full = ''
        for line in gen:
            full += line

        full_lines = full.split('\n')
        self.assertEqual('<!DOCTYPE html>', full_lines[0])
        self.assertIn('samples/</title>', full_lines[3])
        self.assertThat(
            full_lines[9],
            testtools.matchers.MatchesRegex(
                r'        <tr><td><a href="/samples/a">a</a></td>'
                r'<td>' + ISO8601RE + r'</td>'
                r'<td style="text-align: right">4.1KB</td></tr>'))
        self.assertThat(
            full_lines[11],
            testtools.matchers.MatchesRegex(
                r'        <tr><td><a href="/samples/b">b</a></td>'
                r'<td>' + ISO8601RE + r'</td>'
                r'<td style="text-align: right">4.1KB</td></tr>'))
        self.assertThat(
            full_lines[13],
            testtools.matchers.MatchesRegex(
                r'        <tr><td><a href="/samples/console.html.gz">'
                r'console.html.gz</a></td><td>' + ISO8601RE + r'</td>'
                r'<td style="text-align: right">277.4KB</td></tr>'))
        self.assertEqual(
            full_lines[17],
            '        <tr><td><a href="/samples/dir/">dir/</a></td>'
            '<td>unknown</td><td style="text-align: right">0.0B</td></tr>')
        self.assertThat(
            full_lines[-7],
            testtools.matchers.MatchesRegex(
                r'        <tr><td><a href="/samples/wsgi_plain.conf">'
                r'wsgi_plain.conf</a></td><td>' + ISO8601RE + r'</td>'
                r'<td style="text-align: right">177.0B</td></tr>'))
        self.assertThat(
            full_lines[-5],
            testtools.matchers.MatchesRegex(
                r'        <tr><td><a href="/samples/z">z</a></td>'
                r'<td>' + ISO8601RE + r'</td>'
                r'<td style="text-align: right">4.1KB</td></tr>'))
        self.assertEqual('</html>', full_lines[-1])
