********
Tutorial
********

In a typical web application, there's a huge amount of code that goes into processing a single request for a web page, an image, or a stylesheet. But if you look at it, a lot of that code is pretty repetitive. Not only are different URLs processed with similar blocks of code, but even entirely different kinds of web applications share a lot of their code under the hood. Whether you're building a blog engine or a bug tracker, you wind up taking the same pieces and just putting them together in different ways.

Modulo is designed to make that easy. It provides you with the pieces, and all you have to do is choose how they go together. You can create any kind of web application by just fitting different pieces together.

A Simple Example
================

Let's look at a simple example. Since all websites have some static files, we'll start by making a static file server; all it does is read a requested file from the disk and send it out over the internet. It's a simple task, so fittingly, Modulo makes it very simple to accomplish. This is the entire program::

    from modulo import WSGIModuloApplication
    from modulo.actions.standard import FileResource
    from wsgiref import simple_server

    action_tree = FileResource
    application = WSGIModuloApplication(action_tree)
    simple_server(application).serve_forever()

Copy and paste that into your favorite text editor, save it, and run it. Congratulations, you've just written a web server!

Let's go through this line by line. The first three lines just import the objects the program needs to run. ::

    from modulo import WSGIModuloApplication
    from modulo.actions.standard import FileResource
    from wsgiref import simple_server

The main step in creating any Modulo application is constructing the *action tree*. In Modulo, each little piece of code is called an *action*. It's represented by a subclass of ``modulo.actions.Action``, and these classes can be built up into a tree that handles requests to your web app. Modulo has a built-in action that sets a file's content to be sent back as the response body, called ``FileResource``. ::

    action_tree = FileResource

For a simple file server, that's all we need.

Once we have the action tree, the next step is to turn it into a WSGI application. If you're not already familiar with WSGI, it's a standard that specifies how a Python web application interacts with the server that's running it. Modulo provides the class ``modulo.WSGIModuloApplication`` to create a WSGI application from an action tree. ::

    application = WSGIModuloApplication(action_tree)

Finally, we insert the Python code to run the WSGI application. In this example, I've used the WSGI reference server from the Python standard library, but you can use any WSGI-capable web server. ::

    simple_server(application).serve_forever()

Chaining Actions
----------------

Obviously if your web apps are limited to one action, there's not a whole lot you can do. Modulo provides you with a couple of operators you can use to combine several basic actions into more complicated ones.

First, let's look at the ``&`` operator, which combines two actions into a new action that will run both of its constituent actions. In other words, writing ``Action1 & Action2`` gives you an action that uses ``Action1`` *and* ``Action2`` to handle the request.

We can use this to add some capabilities to our web server. For example, we might want it to send back a ``Content-Length`` header that tells the browser how many bytes are in the file. Modulo has an action to do this, of course; it's called ``modulo.actions.standard.ContentLengthAction``. The new program is ::

    from modulo import WSGIModuloApplication
    from modulo.actions.standard import FileResource, ContentLengthAction
    from wsgiref import simple_server

    action_tree = FileResource & ContentLengthAction
    application = WSGIModuloApplication(action_tree)
    simple_server(application).serve_forever()

Edit your Python file to include this, then save it and run it. Now, in addition to serving up the file content, your server will include a header that tells the browser how many bytes are in the file.

You can use the ``&`` operator multiple times to produce a chain of more than two actions. For instance, we might want to add another HTTP header that specifies the type of content that's in the file the server is sending. The action to do that is ``modulo.actions.standard.ContentTypeAction``, and it can be chained into the server like this::

    from modulo import WSGIModuloApplication
    from modulo.actions.standard import FileResource, ContentLengthAction, ContentTypeAction
    from wsgiref import simple_server

    action_tree = FileResource & ContentLengthAction & ContentTypeAction
    application = WSGIModuloApplication(action_tree)
    simple_server(application).serve_forever()

As an alternative to the ``&`` Modulo offers the function ``modulo.actions.all_of``, which does the same thing, but can handle any number of actions at once. It can be more convenient than ``&`` when you have many actions to chain together, or when you're building a deeply nested action tree. The last code sample could be rewritten like this::

    from modulo import WSGIModuloApplication
    from modulo.actions import all_of
    from modulo.actions.standard import FileResource, ContentLengthAction, ContentTypeAction
    from wsgiref import simple_server

    action_tree = all_of(
        FileResource,
        ContentLengthAction,
        ContentTypeAction
    ) 
    application = WSGIModuloApplication(action_tree)
    simple_server(application).serve_forever()

Alternate Actions
-----------------

The other action combination operator that Modulo offers is the ``|`` operator, which combines two actions into a new action that will run *one* of its constituent actions. In other words, writing ``Action1 | Action2`` gives you a new action which will use *either* ``Action1`` *or* ``Action2``, but not both. It'll first try ``Action1``, and if that doesn't work for some reason, it'll try ``Action2`` before giving up.

As an example, let's say we want to expand our server to provide directory listings. Modulo offers the action ``modulo.actions.standard.DirectoryResource`` to do this. Obviously, any given HTTP request could correspond to either a file or a directory, but not both. With the ``|`` operator, we can set up the server to first see if the request corresponds to a directory, and if not, fall back to handling it as a file. ::

    from modulo import WSGIModuloApplication
    from modulo.actions import all_of
    from modulo.actions.standard import DirectoryResource, FileResource, ContentLengthAction, ContentTypeAction
    from wsgiref import simple_server

    action_tree = DirectoryResource | all_of(
        FileResource,
        ContentLengthAction,
        ContentTypeAction
    )
    application = WSGIModuloApplication(action_tree)
    simple_server(application).serve_forever()

As with ``&``, there is also a function that duplicates the behavior of the ``|`` operator: ``modulo.actions.any_of``. The last example could be rewritten as ::

    from modulo import WSGIModuloApplication
    from modulo.actions import all_of, any_of
    from modulo.actions.standard import DirectoryResource, FileResource, ContentLengthAction, ContentTypeAction
    from wsgiref import simple_server

    action_tree = any_of(
        DirectoryResource,
        all_of(
            FileResource,
            ContentLengthAction,
            ContentTypeAction
        )
    )
    application = WSGIModuloApplication(action_tree)
    simple_server(application).serve_forever()

Configuring Actions
-------------------

.. note:: This is a work in progress.

Many actions can be configured with parameters. For example, ``FileResource`` takes a parameter called ``search_path`` which tells it which directory to look in to find the file. It takes the URL path of the requested file, appends it to that directory, and tries to return the resulting file. ::

    action_tree = FileResource(search_path='/var/www/localhost/htdocs')
