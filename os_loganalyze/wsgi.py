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
import fileinput
import os.path
import re
import sys
import wsgiref.util

# which logs support severity
SUPPORTS_SEV = '(screen-(n-|c-|q-|g-|h-|ceil|key)|tempest\.txt)'

DATEFMT = '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}((\.|\,)\d{3})?'
STATUSFMT = '(DEBUG|INFO|WARNING|ERROR|TRACE|AUDIT)'
KEY_COMPONENT = '\([^\)]+\):'

OSLO_LOGMATCH = '^(?P<date>%s)(?P<pid> \d+)? (?P<status>%s)' % \
    (DATEFMT, STATUSFMT)
KEY_LOGMATCH = '^(?P<comp>%s) (?P<date>%s) (?P<status>%s)' % \
    (KEY_COMPONENT, DATEFMT, STATUSFMT)


SEVS = {
    'NONE': 0,
    'DEBUG': 1,
    'INFO': 2,
    'AUDIT': 3,
    'TRACE': 4,
    'WARNING': 5,
    'ERROR': 6
    }


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


def file_supports_sev(fname):
    m = re.search(SUPPORTS_SEV, fname)
    return m is not None


def not_html(fname):
    return re.search('(\.html(\.gz)?)$', fname) is None


def sev_of_line(line, oldsev="NONE"):
    m = re.match(OSLO_LOGMATCH, line)
    if m:
        return m.group('status')

    m = re.match(KEY_LOGMATCH, line)
    if m:
        return m.group('status')

    return oldsev


def color_by_sev(line, sev):
    """Wrap a line in a span whose class matches it's severity."""
    return "<span class='%s'>%s</span>" % (sev, line)


def escape_html(line):
    """Escape the html in a line.

    We need to do this because we dump xml into the logs, and if we don't
    escape the xml we end up with invisible parts of the logs in turning it
    into html.
    """
    return cgi.escape(line)


def link_timestamp(line):
    m = re.match(
        '(<span class=\'(?P<class>[^\']+)\'>)?(?P<comp>%s )?'
        '(?P<date>%s)(?P<rest>.*)' % (KEY_COMPONENT, DATEFMT),
        line)
    if m:
        date = "_" + re.sub('[\s\:\.\,]', '_', m.group('date'))

        # everyone that got this far had a date
        line = "<a name='%s' class='date' href='#%s'>%s</a>%s\n" % (
            date, date, m.group('date'), m.group('rest'))
        # if we found a keystone component, add it back
        if m.group('comp'):
            line = ("%s" % m.group('comp')) + line

        # if we found a severity class, put the spans back
        if m.group('class'):
            line = "</span><span class='%s %s'>%s" % (
                m.group('class'), date, line)

    return line


def skip_line_by_sev(sev, minsev):
    """should we skip this line?

    If the line severity is less than our minimum severity,
    yes we should.
    """
    return SEVS.get(sev, 0) < SEVS.get(minsev, 0)


def passthrough_filter(fname, minsev):
    sev = "NONE"
    supports_sev = file_supports_sev(fname)

    for line in fileinput.FileInput(fname, openhook=fileinput.hook_compressed):
        if supports_sev:
            sev = sev_of_line(line, sev)

            if skip_line_by_sev(sev, minsev):
                continue

        yield line


def does_file_exist(fname):
    """Figure out if we'll be able to read this file.

    Because we are handling the file streams as generators, we actually raise
    an exception too late for us to be able to handle it before apache has
    completely control. This attempts to do the same open outside of the
    generator to trigger the IOError early enough for us to catch it, without
    completely changing the logic flow, as we really want the generator
    pipeline for performance reasons.

    This does open us up to a small chance for a race where the file comes
    or goes between this call and the next, however that is a vanishingly
    small possibility.
    """
    f = open(fname)
    f.close()


def html_filter(fname, minsev):
    """Generator to read logs and output html in a stream.

    This produces a stream of the htmlified logs which lets us return
    data quickly to the user, and use minimal memory in the process.
    """

    supports_sev = file_supports_sev(fname)
    sev = "NONE"
    should_escape = not_html(fname)

    yield _css_preamble(supports_sev)

    for line in fileinput.FileInput(fname, openhook=fileinput.hook_compressed):
        if should_escape:
            newline = escape_html(line)
        else:
            newline = line

        if supports_sev:
            sev = sev_of_line(newline, sev)
            if skip_line_by_sev(sev, minsev):
                continue
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


def safe_path(root, environ):
    """Pull out a safe path from a url.

    Basically we need to ensure that the final computed path
    remains under the root path. If not, we return None to indicate
    that we are very sad.
    """
    path = wsgiref.util.request_uri(environ, include_query=0)
    match = re.search('htmlify/(.*)', path)
    if match:
        raw = match.groups(1)[0]
        newpath = os.path.abspath(os.path.join(root, raw))
        if newpath.find(root) == 0:
            return newpath

    return None


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


def application(environ, start_response, root_path=None):
    if root_path is None:
        root_path = os.environ.get('OS_LOGANALYZE_ROOT_PATH',
                                   '/srv/static/logs')

    # make root path absolute in case we have a path with local components
    # specified
    root_path = os.path.abspath(root_path)

    status = '200 OK'

    logpath = safe_path(root_path, environ)
    if not logpath:
        status = '400 Bad Request'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)
        return ['Invalid file url']

    try:
        minsev = get_min_sev(environ)
        if should_be_html(environ):
            response_headers = [('Content-type', 'text/html')]
            does_file_exist(logpath)
            generator = html_filter(logpath, minsev)
            start_response(status, response_headers)
            return generator
        else:
            response_headers = [('Content-type', 'text/plain')]
            does_file_exist(logpath)
            generator = passthrough_filter(logpath, minsev)
            start_response(status, response_headers)
            return generator
    except IOError:
        status = "404 Not Found"
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)
        return ['File Not Found']


# for development purposes, makes it easy to test the filter output
if __name__ == "__main__":
    htmlify_stdin()
