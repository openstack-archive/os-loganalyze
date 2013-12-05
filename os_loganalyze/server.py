#!/usr/bin/python
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


""" Run a simple WSGI server to serve htmlified logs from local devstack
machines. Add these lines to localrc before running stack.sh:

SCREEN_LOGDIR=$DEST/logs/screen
LOG_COLOR=false
"""

import argparse
import os
from os_loganalyze.wsgi import application
import re
import sys
import wsgiref.simple_server


DEF_PORT = 8000
LOG_PATH = '/opt/stack/logs/screen/'


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--port', '-p', type=int, default=DEF_PORT,
                        help='TCP port to listen on')

    parser.add_argument('--logdir', '-l', default=LOG_PATH,
                        help='Path to the log files to be served')

    args = parser.parse_args()
    return (args.port, args.logdir)


def top_wsgi_app(environ, start_response):
    req_path = environ.get('PATH_INFO')
    if bool(re.search('^/$|^/htmlify/?$', req_path)):
        return gen_links_wsgi_app(environ, start_response)
    else:
        return application(environ, start_response, root_path=LOG_PATH)


def gen_links_wsgi_app(environ, start_response):
    start_response('200 OK', [('Content-type', 'text/html')])
    if environ.get('QUERY_STRING') == 'all':
        return link_generator(all_files=True)
    else:
        return link_generator(all_files=False)


def link_generator(all_files):
    yield '<head><body>\n'

    filenames = os.listdir(LOG_PATH)
    if all_files:
        yield ("Showing all files in %s. "
               "<a href='/'>Show current logs only</a>\n" % LOG_PATH)
    else:
        yield ("Showing current log files in %s. "
               "<a href='/?all'>Show all files</a>\n" % LOG_PATH)
        filenames = [f for f in filenames if f.endswith('.log')]
        # also exclude files with datestamps in their name
        filenames = [f for f in filenames
                     if not re.search('\d{4}-\d{2}-\d{2}', f)]

    for filename in sorted(filenames):
        yield "<p><a href='/htmlify/%s'> %s </a>\n" % (filename, filename)

    yield '</body></html>\n'


def main():
    global LOG_PATH
    port, LOG_PATH = parse_args()

    if not os.path.isdir(LOG_PATH):
        print "%s is not a directory. Quiting..." % LOG_PATH
        sys.exit(1)

    print "Listening on port %d with %s as root path" % (port, LOG_PATH)
    print "URLs are like: http://host-ip:%d/htmlify/screen-n-api.log" % port
    print "Or goto http://host-ip:%d for a page of links" % port

    wsgiref.simple_server.make_server('', port, top_wsgi_app).serve_forever()


if __name__ == '__main__':
    main()
