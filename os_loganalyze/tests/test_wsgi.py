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

import types

import fixtures
import swiftclient  # noqa needed for monkeypatching

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


# add up all the counts from a generator
def count_types(gen):
    counts = {
        'TOTAL': 0,
        'DEBUG': 0,
        'INFO': 0,
        'WARNING': 0,
        'ERROR': 0,
        'TRACE': 0,
        'AUDIT': 0}

    laststatus = None
    for line in gen:
        counts['TOTAL'] = counts['TOTAL'] + 1
        for key in counts:
            if ' %s ' % key in line:
                laststatus = key
                continue
        if laststatus:
            counts[laststatus] = counts[laststatus] + 1
    return counts


# count up all the lines at all levels
def compute_total(level, counts):
    total = 0
    for l in SEVS_SEQ[SEVS[level]:]:
        # so that we don't need to know all the levels
        if counts.get(l):
            total = total + counts[l]
    return total


class TestWsgiDisk(base.TestCase):
    """Test loading files from samples on disk."""

    # counts for known files for testing
    files = {
        'screen-c-api.txt.gz': {
            'TOTAL': 3695,
            'DEBUG': 2906,
            'INFO': 486,
            'AUDIT': 249,
            'TRACE': 0,
            'WARNING': 50,
            'ERROR': 0,
            },
        'screen-n-api.txt.gz': {
            'TOTAL': 50745,
            'DEBUG': 46071,
            'INFO': 4388,
            'AUDIT': 271,
            'TRACE': 0,
            'WARNING': 6,
            'ERROR': 5
            },
        'screen-q-svc.txt.gz': {
            'TOTAL': 47887,
            'DEBUG': 46912,
            'INFO': 262,
            'AUDIT': 0,
            'TRACE': 589,
            'WARNING': 48,
            'ERROR': 72,
            },
        }

    def test_pass_through_all(self):
        for fname in self.files:
            gen = self.get_generator(fname, html=False)

            counts = count_types(gen)
            self.assertEqual(counts['TOTAL'], self.files[fname]['TOTAL'])

    def test_pass_through_at_levels(self):
        for fname in self.files:
            for level in self.files[fname]:
                if level == 'TOTAL':
                    continue

                gen = self.get_generator(fname, level=level, html=False)

                counts = count_types(gen)
                total = compute_total(level, self.files[fname])
                print(fname, counts)

                self.assertEqual(counts['TOTAL'], total)

    def test_invalid_file(self):
        gen = log_wsgi.application(
            self.fake_env(), self._start_response)
        self.assertEqual(gen, ['Invalid file url'])

    def test_file_not_found(self):
        gen = log_wsgi.application(
            self.fake_env(PATH_INFO='/htmlify/foo.txt'),
            self._start_response)
        self.assertEqual(gen, ['File Not Found'])

    def test_plain_text(self):
        gen = self.get_generator('screen-c-api.txt.gz', html=False)
        self.assertEqual(type(gen), types.GeneratorType)

        first = gen.next()
        self.assertIn(
            '+ ln -sf /opt/stack/new/screen-logs/screen-c-api.2013-09-27-1815',
            first)

    def test_html_gen(self):
        gen = self.get_generator('screen-c-api.txt.gz')
        first = gen.next()
        self.assertIn('<html>', first)

    def test_plain_non_compressed(self):
        gen = self.get_generator('screen-c-api.txt', html=False)
        self.assertEqual(type(gen), types.GeneratorType)

        first = gen.next()
        self.assertIn(
            '+ ln -sf /opt/stack/new/screen-logs/screen-c-api.2013-09-27-1815',
            first)

    def test_passthrough_filter(self):
        # Test the passthrough filter returns an image stream
        gen = self.get_generator('openstack_logo.png')
        first = gen.next()
        self.assertNotIn('html', first)
        with open(base.samples_path('samples') + 'openstack_logo.png') as f:
            self.assertEqual(first, f.readline())

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

    def test_config_passthrough_view(self):
        self.wsgi_config_file = (base.samples_path('samples') +
                                 'wsgi_plain.conf')
        # Check there is no HTML on a file that should otherwise have it
        gen = self.get_generator('devstacklog.txt.gz')

        first = gen.next()
        self.assertNotIn('<html>', first)

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


class TestWsgiSwift(TestWsgiDisk):
    """Test loading files from swift."""
    def setUp(self):
        class fake_swiftclient(object):
            def __init__(self, *args, **kwargs):
                pass

            def get_object(self, container, name, resp_chunk_size=None):
                name = name[len('non-existent'):]
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

        self.useFixture(fixtures.MonkeyPatch(
            'swiftclient.client.Connection', fake_swiftclient))
        super(TestWsgiSwift, self).setUp()

        # Set the samples directory to somewhere non-existent so that swift
        # is checked for files
        self.samples_directory = 'non-existent'

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

    def test_skip_file(self):
        # this should generate a TypeError because we're telling it to
        # skip the filesystem, but we don't have a working swift here.
        self.assertRaises(
            TypeError,
            self.get_generator('screen-c-api.txt.gz', source='swift'))

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

    def test_compare_disk_to_swift_no_chunks(self):
        self.wsgi_config_file = (base.samples_path('samples') +
                                 'wsgi_no_chunks.conf')
        self.test_compare_disk_to_swift_no_compression()
        self.test_compare_disk_to_swift_plain()
        self.test_compare_disk_to_swift_html()
