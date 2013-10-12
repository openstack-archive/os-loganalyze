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
to the user grabbing the logs is largely not noticable (< 1s).

* Free software: Apache license
* Documentation: http://docs.openstack.org/developer/os_loganalyze

Features
--------
* Supports text/html or text/plain dynamically based on content
  negotiation
* html highlighting based on severity
* filtering based on severity using the level=XXXX parameter (works in
  either text/html or text/plain responses

Todo
------------
Next steps, roughly in order

* support keystone logs
* support devstack console logs
* support swift logs
* bail out early if we find a log we don't understand (filtering by
  name is probably appropriate to begin with)
* provide links to logstash for request streams (link well know
  request ids to logstash queries for them)
