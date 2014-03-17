===============================
os_loganalyze
===============================

OpenStack tools for gate log analysis

os_loganalyze is designed as a lightweight wsgi filter for openstack
logs, making it easier to interact with them on OpenStack's
logs.openstack.org repository. This includes colorizing the logs based
on log level severity, having bookmarkable links to timestamps in the
logs for easy reference, and being able to filter by log level.

This is implemented as a low level wsgi application which returns a
generator so that it can act like a pipeline. Some of our logs are 35
MB uncompressed, so if we used a more advanced framework that required
we load the entire data stream into memory, the user response would be
very poor. As a pipeline and generator the delay added by this script
to the user grabbing the logs is largely not noticeable (< 1s).

* Free software: Apache license
* Documentation: http://docs.openstack.org/developer/os_loganalyze

Features
--------
* Supports text/html or text/plain dynamically based on content
  negotiation
* html highlighting based on severity
* filtering based on severity using the level=XXXX parameter (works in
  either text/html or text/plain responses
* Provides a script named htmlify_server.py that serves htmlified logs
  over HTTP. To view devstack logs: set
  SCREEN_LOGDIR=$DEST/logs/screen and LOG_COLOR=false in localrc
  before running stack.sh, run htmlify_server.py, and point your
  browser at http://devstack-ip:8000/

Todo
------------
Next steps, roughly in order

* support swift logs (timestamp linking only, no sevs in swift logs)
* provide links to logstash for request streams (link well know
  request ids to logstash queries for them)

Hacking
-------
If you are working on making changes one of the easiest ways to do
this is to run the server stack locally to see how your changes look
on same data included for the tests.

This can be done with ``tox -e run``, which will use the script
designed for devstack locally pointed at the sample data. A url where
you can browse the resultant content will be provided on the command
line.
