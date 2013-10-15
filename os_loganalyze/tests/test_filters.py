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


class TestFilters(base.TestCase):

    def test_consolodated_filters(self):
        gen = self.get_generator('screen-q-svc.txt.gz', level='DEBUG')
        # we don't need the header, we just don't want to deal with it
        header = gen.next()
        self.assertIn("Display level: ", header)

        # first line is INFO
        line = gen.next()
        self.assertIn("class='INFO", line)
        self.assertIn("href='#_2013-09-27_18_22_11_248'", line)

        # second line is an ERROR
        line = gen.next()
        self.assertIn("class='ERROR", line)
        self.assertIn("href='#_2013-09-27_18_22_11_249'", line)

        # third is a DEBUG
        line = gen.next()
        self.assertIn("class='DEBUG", line)
        self.assertIn("href='#_2013-09-27_18_22_11_249'", line)

    def test_keystone_filters(self):
        gen = self.get_generator('screen-key.txt.gz', level='DEBUG')
        # we don't need the header, we just don't want to deal with it
        gen.next()

        # first line is DEBUG
        line = gen.next()
        self.assertIn("class='DEBUG", line)
        self.assertIn("href='#_2013-09-27_18_20_55_636'", line)

    def test_devstack_filters(self):
        gen = self.get_generator('devstacklog.txt.gz')
        # dump the header
        gen.next()

        # first line
        line = gen.next()
        self.assertIn("href='#_2013-09-27_18_15_31'", line)

    def test_devstack_filters_nodrop(self):
        gen = self.get_generator('devstacklog.txt.gz', level='INFO')

        header = gen.next()
        self.assertNotIn("Display level: ", header)

        # we shouldn't be dropping anything with the first line
        line = gen.next()
        self.assertIn("href='#_2013-09-27_18_15_31'", line)

    def test_html_file_filters(self):
        # do we avoid double escaping html files
        gen = self.get_generator('console.html.gz')

        header = gen.next()
        self.assertNotIn("Display level: ", header)

        # we shouldn't be dropping anything with the first line
        line = gen.next()
        self.assertEqual("<pre>\n", line)

        line = gen.next()
        self.assertIn("<a name='_2013-09-27_18_07_11_860' "
                      "class='date' href='#_2013-09-27_18_07_11_860'>", line)

        line = gen.next()
        self.assertIn("<a name='_2013-09-27_18_07_11_884' "
                      "class='date' href='#_2013-09-27_18_07_11_884'>", line)
