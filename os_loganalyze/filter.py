#!/usr/bin/env python
#
# Copyright (c) 2013 IBM Corp.
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

import os.path
import re

import os_loganalyze.generator as generator
import os_loganalyze.util as util

# which logs support severity
# This uses re.match so you must match the left hand side.
SUPPORTS_SEV = re.compile(
    r'((screen-)?(n-|c-|g-|h-|ir-|ironic-|m-|o-|df-|placement-api|'
    r'q-|neutron-|'  # support both lib/neutron and lib/neutron-legacy logs
    r'ceil|key|sah|des|tr)'  # openstack logs
    r'|(devstack\@)'  # systemd logs
    # other things we understand
    r'|(keystone|tempest)\.txt|syslog)')

SYSLOGDATE = '\w+\s+\d+\s+\d{2}:\d{2}:\d{2}((\.|\,)\d{3,6})?'
DATEFMT = '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}((\.|\,)\d{3,6})?'
STATUSFMT = '(DEBUG|INFO|WARNING|ERROR|TRACE|AUDIT|CRITICAL)'

OSLO_LOGMATCH = '^(?P<date>%s)(?P<line>(?P<pid> \d+)? (?P<status>%s).*)' % \
    (DATEFMT, STATUSFMT)
SYSLOG_MATCH = ('^(?P<date>%s)(?P<line> (?P<host>[\w\-]+) '
                '(?P<service>[^\[\s]+):.*)' %
                (SYSLOGDATE))
SYSTEMD_MATCH = (
    '^(?P<date>%s)(?P<line> (?P<host>\S+) \S+\[\d+\]\: (?P<status>%s)?.*)' %
    (SYSLOGDATE, STATUSFMT))
CONSOLE_MATCH = '^(?P<date>%s)(?P<line>.*)' % DATEFMT

OSLORE = re.compile(OSLO_LOGMATCH)
SYSLOGRE = re.compile(SYSLOG_MATCH)
CONSOLERE = re.compile(CONSOLE_MATCH)
SYSTEMDRE = re.compile(SYSTEMD_MATCH)

SEVS = {
    'NONE': 0,
    'DEBUG': 1,
    'INFO': 2,
    'AUDIT': 3,
    'TRACE': 4,
    'WARNING': 5,
    'ERROR': 6,
    'CRITICAL': 7,
    }


class LogLine(object):
    status = "NONE"
    line = ""
    date = ""
    pid = ""
    service = ""

    def __init__(self, line, old_sev="NONE"):
        self._parse(line, old_sev)

    def _syslog_status(self, service):
        if service in ('tgtd', 'proxy-server'):
            return 'DEBUG'
        else:
            return 'INFO'

    def safe_date(self):
        return '_' + re.sub('[\s\:\.\,]', '_', self.date)

    def _parse(self, line, old_sev):
        m = OSLORE.match(line)
        if m:
            self.status = m.group('status')
            self.line = m.group('line')
            self.date = m.group('date')
            self.pid = m.group('pid')
            return
        m = SYSTEMDRE.match(line)
        if m:
            self.status = m.group('status') or "NONE"
            self.line = m.group('line')
            self.date = m.group('date')
            self.host = m.group('host')
            return
        m = CONSOLERE.match(line)
        if m:
            self.date = m.group('date')
            self.status = old_sev
            self.line = m.group('line')
            return
        m = SYSLOGRE.match(line)
        if m:
            self.service = m.group('service')
            self.line = m.group('line')
            self.date = m.group('date')
            self.status = self._syslog_status(self.service)
            return

        self.status = old_sev
        self.line = line.rstrip()


class SevFilter(object):

    def __init__(self, file_generator, minsev="NONE", limit=None):
        self.minsev = minsev
        self.file_generator = file_generator
        # To avoid matching strings in the log dir path we only consider the
        # filename itself for severity support.
        filename = os.path.basename(file_generator.logname)
        self.supports_sev = \
            SUPPORTS_SEV.match(filename) is not None
        self.limit = limit
        self.strip_control = False

    def strip(self, line):
        return re.sub('\x1b\[(([03]\d)|\;)+m', '', line)

    def __iter__(self):
        old_sev = "NONE"
        lineno = 1
        for line in self.file_generator:
            # bail early for limits
            if self.limit and lineno > int(self.limit):
                raise StopIteration()
            # strip control chars in case the console is ascii colored
            if self.strip_control:
                line = self.strip(line)

            logline = LogLine(line, old_sev)

            # Some log lines come without severity. Treat those as
            # belonging to the previous non NONE severity so that we
            # get those log lines associated to the proper level.
            if logline.status != "NONE":
                old_sev = logline.status
            else:
                logline.status = old_sev

            if self.supports_sev and self.skip_by_sev(logline.status):
                continue

            lineno += 1
            yield logline

    def skip_by_sev(self, sev):
        """should we skip this line?

        If the line severity is less than our minimum severity,
        yes we should.
        """
        minsev = self.minsev
        return SEVS.get(sev, 0) < SEVS.get(minsev, 0)


class Line(object):
    date = ''

    def __init__(self, line):
        self.line = line


class NoFilter(object):
    supports_sev = False

    def __init__(self, file_generator):
        self.file_generator = file_generator

    def __iter__(self):
        for line in self.file_generator:
            l = Line(line)
            l.status = "NONE"
            yield l


def get_filter_generator(file_generator, environ, root_path, config):
    """Return the filter to use as per the config."""

    # Check if the generator is an index page. If so, we don't want to apply
    # any filters
    if isinstance(file_generator, generator.IndexIterableBuffer):
        return NoFilter(file_generator)

    # Check file specific conditions first
    filter_selected = util.get_file_conditions('filter', file_generator,
                                               environ, root_path, config)

    # Otherwise use the defaults in the config
    if not filter_selected:
        if config.has_section('general'):
            if config.has_option('general', 'filter'):
                filter_selected = config.get('general', 'filter')

    minsev = util.parse_param(environ, 'level', default="NONE")
    limit = util.parse_param(environ, 'limit')

    if filter_selected:
        if filter_selected.lower() in ['sevfilter', 'sev']:
            return SevFilter(file_generator, minsev, limit)
        elif filter_selected.lower() in ['nofilter', 'no']:
            return NoFilter(file_generator)

    # Otherwise guess
    if util.use_passthrough_view(file_generator.file_headers):
        return NoFilter(file_generator)

    return SevFilter(file_generator, minsev, limit)
