#!/usr/bin/python

'''Testing utilities for the handler architecture.'''

from modulo.resources import Resource

class HelloWorldResource(Resource):
    def generate(self, rsp):
        rsp.data = 'Hello World!'
        return True