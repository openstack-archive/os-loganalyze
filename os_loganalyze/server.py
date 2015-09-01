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


""" Run a simple WSGI server to serve htmlified logs from local devstack
machines. Add these lines to localrc before running stack.sh:

SCREEN_LOGDIR=$DEST/logs/screen
LOG_COLOR=false
"""

import argparse
import os
import socket
import sys
import wsgiref.simple_server

from os_loganalyze import wsgi

DEF_PORT = 8000
LOG_PATH = '/opt/stack/logs/screen/'
WSGI_CONFIG = '/etc/os_loganalyze/wsgi.conf'


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--port', '-p', type=int, default=DEF_PORT,
                        help='TCP port to listen on')

    parser.add_argument('--logdir', '-l', default=LOG_PATH,
                        help='Path to the log files to be served')

    parser.add_argument('--wsgi-config', '-c', default=WSGI_CONFIG,
                        help="Specify the WSGI configuration file")

    args = parser.parse_args()
    return (args.port, args.logdir, args.wsgi_config)


def top_wsgi_app(environ, start_response):
    return wsgi.application(environ, start_response, root_path=LOG_PATH,
                            wsgi_config=WSGI_CONFIG)


def my_ip():
    return socket.gethostbyname(socket.gethostname())


def main():
    global LOG_PATH, WSGI_CONFIG
    port, LOG_PATH, WSGI_CONFIG = parse_args()

    if not os.path.isdir(LOG_PATH):
        print("%s is not a directory. Quiting..." % LOG_PATH)
        sys.exit(1)

    url = "http://%s:%d/" % (my_ip(), port)
    print("Listening on port %d with %s as root path" % (port, LOG_PATH))
    print("URLs are like: %shtmlify/screen-n-api.log" % url)
    print("Or goto %s for a page of links" % url)

    wsgiref.simple_server.make_server('', port, top_wsgi_app).serve_forever()


if __name__ == '__main__':
    main()
