#!/usr/bin/env python
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
Test the view generators
"""

import os_loganalyze.filter as osfilter
import os_loganalyze.generator as osgen
from os_loganalyze.tests import base
import os_loganalyze.view as osview


class TestViews(base.TestCase):
    def get_generator(self, fname):
        # Override base's get_generator because we don't want the full
        # wsgi application. We just need the generator to give to Views.
        root_path = base.samples_path(self.samples_directory)
        kwargs = {'PATH_INFO': '/htmlify/%s' % fname}
        file_generator = osgen.get_file_generator(self.fake_env(**kwargs),
                                                  root_path)
        filter_generator = osfilter.SevFilter(file_generator)
        return filter_generator

    def test_html_detection(self):
        gen = self.get_generator('sample.html')
        html_view = osview.HTMLView(gen)
        i = iter(html_view)
        self.assertFalse(html_view.is_html)
        # Move the generator so that the is_html flag is set
        i.next()
        self.assertTrue(html_view.is_html)

    def test_doctype_html_detection(self):
        gen = self.get_generator('sample_doctype.html')
        html_view = osview.HTMLView(gen)
        i = iter(html_view)
        self.assertFalse(html_view.is_html)
        # Move the generator so that the is_html flag is set
        i.next()
        self.assertTrue(html_view.is_html)
