Modulo is a Python web framework which constructs websites from reusable code
snippets. It provides the pieces, and you get to put them together to create
whatever kind of website you want.

The official source for documentation and tutorials is the project website,
http://www.ellipsix.net/devweb/modulo/index.html, so if you really want to
learn how to create websites with Modulo, check there. This is just a quick
reference to get you started, and hopefully convince you that the software is
actually good for something ;-)

**Obligatory warning**: this is pretty primitive software. Don't use it
anywhere you need something reliable. But if you want to help improve it,
whether you just have a one-off bug fix or you want to be fully involved in the
development process, that would be much appreciated. See the website for
details on how to get involved.

Installing Modulo
-----------------
Modulo is distributed using the standard Python packaging system, distutils. So
to install it, you just have to extract the downloaded file, open a terminal in
the extracted directory, and run

> python setup.py install

To get a list of what else you can do with the setup script, run

> python setup.py --help

or see the Distutils documentation, http://docs.python.org/install/index.html.

Creating a Modulo webapp
------------------------
Modulo comes with a setup script that will set up the skeleton of a website for
you. It's called modulo-setup.py. So the quickest way to get started creating a
website is to open up a terminal in the directory where you want the application
to be created, and run

> modulo-setup.py

The script will open up a web browser and show you a web page where you can fill
in some configuration settings. Fill in the fields and click "Submit" and you
should see a page indicating that the setup procedure completed successfully.
Now there are four files in the directory:

app.py
  This contains the actual Modulo application, and this is where you make changes
  when you want to add features. By default, the setup script creates a little
  file server just to show you what an application looks like. See the project
  website for information on what it means and how you can modify it.

launch.wsgi
  This is a wrapper that you use if you are using Apache with mod_wsgi. See the
  doc comment in the file for explanation.

manage.py
  This is a script you can run from the command line to do various things, such as
  starting up a test server.

settings.py
  This is where the settings you typed into that HTML form wound up. It's just a
  Python module, so you can put any Python code in it, and it'll get run whenever
  the application is started in a server. It's good for site-specific
  configuration info.

Run the test server with

> python manage.py runserver

Open a web browser and navigate to http://localhost:5000/ and you should see a
directory listing showing those four files (and the ``.pyc`` versions). Running

> python manage.py --help

gives you a list of what else you can do with the management script.

Once you've had your fun with that, it's time to check the website
http://www.ellipsix.net/devweb/modulo/index.html
to see what more you can do with Modulo!