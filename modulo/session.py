#!/usr/bin/python

from werkzeug.contrib.sessions import FilesystemSessionStore

session_store = FilesystemSessionStore()
