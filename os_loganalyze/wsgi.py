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


import cgi
import ConfigParser
import fileinput
import os.path
import re
import sys

import os_loganalyze.filter as osfilter
import os_loganalyze.generator as osgen

SYSLOGDATE = '\w+\s+\d+\s+\d{2}:\d{2}:\d{2}'
DATEFMT = '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}((\.|\,)\d{3})?'
STATUSFMT = '(DEBUG|INFO|WARNING|ERROR|TRACE|AUDIT)'

OSLO_LOGMATCH = '^(?P<date>%s)(?P<pid> \d+)? (?P<status>%s)' % \
    (DATEFMT, STATUSFMT)
SYSLOG_MATCH = '^(?P<date>%s) (?P<host>[\w\-]+) (?P<service>\S+):' % \
    (SYSLOGDATE)

ALL_DATE = '(%s|%s)' % (DATEFMT, SYSLOGDATE)


def _html_close():
    return """
</span></pre></body>
<script>
var old_highlight;

function remove_highlight() {
    if (old_highlight) {
        items = document.getElementsByClassName(old_highlight);
        for (var i = 0; i < items.length; i++) {
            items[i].className = items[i].className.replace('highlight','');
        }
    }
}

function update_selector(highlight) {
    var selector = document.getElementById('selector');
    if (selector) {
        var links = selector.getElementsByTagName('a');
        for (var i = 0; i < links.length; i++) {
            links[i].hash = "#" + highlight;
        }
    }
}

function highlight_by_hash(event) {
    var highlight = window.location.hash.substr(1);
    // handle changes to highlighting separate from reload
    if (event) {
         highlight = event.target.hash.substr(1);
    }
    remove_highlight();
    if (highlight) {
        elements = document.getElementsByClassName(highlight);
        for (var i = 0; i < elements.length; i++) {
            elements[i].className += " highlight";
        }
        update_selector(highlight);
        old_highlight = highlight;
    }
}
document.onclick = highlight_by_hash;
highlight_by_hash();
</script>
</html>
"""


def _css_preamble(supports_sev):
    """Write a valid html start with css that we need."""
    header = """<html>
<head>
<style>
a {color: #000; text-decoration: none}
a:hover {text-decoration: underline}
.DEBUG, .DEBUG a {color: #888}
.ERROR, .ERROR a {color: #c00; font-weight: bold}
.TRACE, .TRACE a {color: #c60}
.WARNING, .WARNING a {color: #D89100;  font-weight: bold}
.INFO, .INFO a {color: #006}
#selector, #selector a {color: #888}
#selector a:hover {color: #c00}
.highlight {
    background-color: rgb(255, 255, 204);
    display: block;
}
pre span span {padding-left: 0}
pre span {
    padding-left: 22em;
    text-indent: -22em;
    white-space: pre-wrap;
    display: block;
}
</style>
<body>"""
    if supports_sev:
        header = header + """
<span id='selector'>
Display level: [
<a href='?'>ALL</a> |
<a href='?level=DEBUG'>DEBUG</a> |
<a href='?level=INFO'>INFO</a> |
<a href='?level=AUDIT'>AUDIT</a> |
<a href='?level=TRACE'>TRACE</a> |
<a href='?level=WARNING'>WARNING</a> |
<a href='?level=ERROR'>ERROR</a> ]
</span>"""

    header = header + "<pre><span>"
    return header


def not_html(fname):
    return re.search('(\.html(\.gz)?)$', fname) is None


def syslog_sev_translator(service):
    if service in ('tgtd', 'proxy-server'):
        return 'DEBUG'
    else:
        return 'INFO'


def sev_of_line(line, oldsev="NONE"):
    m = re.match(OSLO_LOGMATCH, line)
    if m:
        return m.group('status')

    m = re.match(SYSLOG_MATCH, line)
    if m:
        return syslog_sev_translator(m.group('service'))

    return oldsev


def color_by_sev(line, sev):
    """Wrap a line in a span whose class matches it's severity."""
    return "</span><span class='%s'>%s" % (sev, line)


def escape_html(line):
    """Escape the html in a line.

    We need to do this because we dump xml into the logs, and if we don't
    escape the xml we end up with invisible parts of the logs in turning it
    into html.
    """
    return cgi.escape(line)


def link_timestamp(line):

    m = re.search(
        '(<span class=\'(?P<class>[^\']+)\'>)?'
        '(?P<date>%s)(?P<rest>.*)' % (ALL_DATE),
        line)
    if m:
        date = "_" + re.sub('[\s\:\.\,]', '_', m.group('date'))

        # everyone that got this far had a date
        line = "<a name='%s' class='date' href='#%s'>%s</a>%s\n" % (
            date, date, m.group('date'), m.group('rest'))

        # if we found a severity class, put the spans back
        if m.group('class'):
            line = "</span><span class='%s %s'>%s" % (
                m.group('class'), date, line)

    return line


def passthrough_filter(fname, flines_generator, minsev):
    for line in flines_generator:
        yield line


def html_filter(fname, flines_generator, minsev):
    """Generator to read logs and output html in a stream.

    This produces a stream of the htmlified logs which lets us return
    data quickly to the user, and use minimal memory in the process.
    """

    sev = "NONE"
    should_escape = not_html(fname)

    yield _css_preamble(flines_generator.supports_sev)

    for line in flines_generator:
        # skip pre lines coming off the file, this fixes highlighting on
        # console logs
        if re.match('<(/)?pre>$', line):
            continue

        if should_escape:
            newline = escape_html(line)
        else:
            newline = line

        sev = sev_of_line(newline, sev)
        if sev:
            newline = color_by_sev(newline, sev)
        else:
            newline = "<span class='line'>" + newline + '</span>'

        newline = link_timestamp(newline)
        yield newline
    yield _html_close()


def htmlify_stdin():
    minsev = "NONE"
    out = sys.stdout
    out.write(_css_preamble())
    for line in fileinput.FileInput():
        newline = escape_html(line)
        newline = color_by_sev(newline, minsev)
        newline = link_timestamp(newline)
        out.write(newline)
    out.write(_html_close())


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


def get_min_sev(environ):
    print environ.get('QUERY_STRING')
    parameters = cgi.parse_qs(environ.get('QUERY_STRING', ''))
    if 'level' in parameters:
        return cgi.escape(parameters['level'][0])
    else:
        return "NONE"


def get_config(wsgi_config):
    config = ConfigParser.ConfigParser()
    config.read(os.path.expanduser(wsgi_config))
    return config


def application(environ, start_response, root_path=None,
                wsgi_config='/etc/os_loganalyze/wsgi.conf'):
    if root_path is None:
        root_path = os.environ.get('OS_LOGANALYZE_ROOT_PATH',
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

    minsev = get_min_sev(environ)
    flines_generator = osfilter.Filter(logname, flines_generator, minsev)
    if should_be_html(environ):
        response_headers = [('Content-type', 'text/html')]
        generator = html_filter(logname, flines_generator, minsev)
    else:
        response_headers = [('Content-type', 'text/plain')]
        generator = passthrough_filter(logname, flines_generator, minsev)

    start_response(status, response_headers)
    return generator


# for development purposes, makes it easy to test the filter output
if __name__ == "__main__":
    htmlify_stdin()
