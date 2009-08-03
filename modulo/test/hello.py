#!/usr/bin/python

'''Testing utilities for the handler architecture.'''

from modulo.actions import Action

class HelloWorldAction(Action):
    def generate(self, rsp, canonical_uri):
        rsp.data = 'Hello World! URL=' + canonical_uri
        return True