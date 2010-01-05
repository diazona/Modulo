#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import logging
import sys
from os.path import abspath, dirname

basedir = dirname(dirname(dirname(abspath(__file__))))
if basedir not in sys.path:
    sys.path.append(basedir)
logging.getLogger().setLevel(logging.DEBUG)

from modulo import *
from modulo.actions.filters import *
from modulo.actions.standard import *
from modulo.templating.clearsilver import *
from modulo.templating.minitmpl import *
from modulo.test.hello import HelloWorldAction
from werkzeug import script
from werkzeug.routing import Map, Rule

class SetDocRoot(Action):
    def __init__(self, req):
        super(SetDocRoot, self).__init__(req)
        req.environ['DOCUMENT_ROOT'] = dirname(abspath(__file__))

def make_app():
    hello_tree = WerkzeugCanonicalizer & HelloWorldAction
    resource_tree = all_of(
        SetDocRoot,
        DateAction,
        ContentTypeAction('text/html'),
        WerkzeugMapFilter(routing_map = Map([
            Rule('/hello', endpoint=hello_tree),
            Rule('/hello<anything>', endpoint=hello_tree)
        ])) | all_of(
            any_of(
                all_of(
                    ClearsilverTemplate(filename=ClearsilverTemplate.ext_request_filename),
                    ClearsilverDataFile(filename=ClearsilverDataFile.ext_request_filename)
                ),
                ClearsilverTemplate(filename=ClearsilverTemplate.ext_request_filename),
                ClearsilverDataFile(filename=ClearsilverDataFile.ext_request_filename)
            ),
            ClearsilverRendering
        ) | all_of(
            URIFilter(r'/templates/.*\.tmpl'),
            MiniTemplate
        ) | FileResource | DirectoryResource
    )
    return WSGIModuloApp(resource_tree, raise_exceptions=True)

action_runserver = script.make_runserver(make_app, use_reloader=True, use_debugger=True)
action_shell = script.make_shell(lambda: {'app': make_app()})

if __name__ == '__main__':
    script.run()
