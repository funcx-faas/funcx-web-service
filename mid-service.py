from bottle import route, run, template, request, get
import cherrypy
import wsgiserver
import json

import requests

# from cherrypy.wsgiserver import CherryPyWSGIServer


@route('/hello/<name>')
def index(name):
    return template('<b>Hello {{name}}</b>!', name=name)


@get('/runjob')
def runjob():

    data = request.json
    cmd = data["cmd"]
    # print(data)

    url = "http://ec2-52-204-235-103.compute-1.amazonaws.com:8080/runjob"
    payload = {'cmd': 'echo hello world'}
    x = requests.get(url, json=payload)

    print(x)
    #res = requests.get('ec2-52-204-235-103.compute-1.amazonaws.com:8080/runjob', json=data)
    #print(res)
    # print(t1-t0)
    #return res
    return x

#server = CherryPyWSGIServer(
#    ('0.0.0.0', '80'),


run(host='0.0.0.0', port=8080, server="paste")
