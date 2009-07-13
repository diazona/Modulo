#!/usr/bin/python

'''Testing utilities for the handler architecture.'''

from modulo.actions import Action

class HelloWorldAction(Action):
    def generate(self, rsp):
        rsp.data = 'Hello World!'
        return True