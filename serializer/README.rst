funcX Serialization Service
===========================


This is a REST micro service that handles serializing and deserialzing inputs for funcX.
The goal is to allow users to pass JSON inputs into funcX and use this service to serialize it such that the workers can act on it.
Similarly, this service will allow users to request a json response for a task.

/serialize
----------

This route expects a POST with a json payload to be serialized. If args and kwargs are specified they will be packed accordingly.


/tasks/<task_id>/deserialize/
-----------------------------

A route to retrieve a task from the Redis store and deserialize it. This will return a JSON.dumps response of the result.

/ping
-----

This route is for liveness checking. Will return "pong" string when you do a GET on this route.
