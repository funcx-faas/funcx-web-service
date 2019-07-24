FuncX Forwarder Service
=======================


This is a REST micro service that handles requests for initializing Forwarders to which endpoints will connect.
This service will have the following routes:

/register
---------

This route expects a POST with a json payload that identifies the endpoint info and responds with a
json response.

For eg:

POST payload::

  {
     'endpoint_id': '<ENDPOINT_ID>',
     'redis_url': '<REDIS_URL>',
  }


Response payload::

  {
     'endpoint_id': endpoint_id,
     'task_url': 'tcp://55.77.66.22:50001',
     'result_url': 'tcp://55.77.66.22:50002',
     'command_port': 'tcp://55.77.66.22:50003'
  }

/list_endpoints
---------------

This route will list the endpoint mappings.


/ping
-----

This route is for liveness checking. Will return "pong" string when you do a GET on this route.





Architecture and Notes
----------------------

The endpoint registers and receives the information
 
```
                                       TaskQ ResultQ
                                          |    |
REST       /register--> Forwarder----->Executor Client
             ^                            |    ^
             |                            |    |
             |                            v    |
             |          +-------------> Interchange
User ----> Endpoint ----|
                        +--> Provider
```
