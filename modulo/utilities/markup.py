#!/usr/bin/python
# -*- coding: iso-8859-1 -*-

'''A processor for converting a simple markup language to HTML.

This module currently uses Markdown with extensions for code highlighting
and mathematical (LaTeX) syntax.'''

import markdown
# preload for markdown
#import mdx_latex
#import mdx_punctuation
#import mdx_xlinking

# We can't just create a single instance with safe mode and a single instance without
# because apparently the markdown module stores its config options (e.g. safe mode)
# as module_level properties :( STUPID STUPID STUPID

mk_opts = dict(extensions = [], extension_configs = {})
mk_parser = None
mk_is_safe = None

def add_markdown_extension(extension, extension_config):
    '''Adds an extension to be loaded into the Markdown parser.
    
    extension is the name of the extension, extension_config is a list
    of (name, value) pairs representing config options for the module'''
    global mk_opts
    mk_opts['extensions'].append(extension)
    mk_opts['extension_configs'][extension] = extension_config

def get_markdown_parser(safe = False):
    global mk_parser, mk_is_safe, mk_opts
    if safe:
        if mk_is_safe is not True:
            mk_parser = markdown.Markdown(safe_mode = 'escape', **mk_opts)
            mk_is_safe = True
    else:
        if mk_is_safe is not False:
            mk_parser = markdown.Markdown(**mk_opts)
            mk_is_safe = False
    return mk_parser

def process_source(src, mode):
    if mode == 'markdown':
        return process_markdown(src)
    elif mode == 'html':
        return process_html(src)
    elif mode == 'text':
        return process_text(src)
    else:
        return process_markdown(src)

def process_text(src):
    return process_markdown(src) # temporary until we create a plain text parser

def process_markdown(src):
    return get_markdown_parser().convert(src.encode('ascii', 'xmlcharrefreplace')) # we shouldn't have non-ASCII characters in XHTML

def process_markdown_safe(src):
    return get_markdown_parser(safe = True).convert(src.encode('ascii', 'xmlcharrefreplace'))

def process_html(src):
    return src # TODO: strip dangerous tags
