# -*- coding: utf-8 -*-

import os, os.path
import random
import sys
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from modulo.actions import Action
from modulo.database import Entity, Session
from modulo.utilities import compact
from werkzeug import secure_filename

#---------------------------------------------------------------------------
# Database models
#---------------------------------------------------------------------------

class Upload(Entity):
    __tablename__ = 'upload'
    
    id = Column(Integer, primary_key=True)
    '''Stores metadata relating to an uploaded file.'''
    mime_type = Column(String(44)) # the MIME type
    group = Column(String(20)) # the group
    filename = Column(String(128)) # the name by which the upload should be referenced
    path = Column(String(256)) # the actual path to the disk file representing this upload

#---------------------------------------------------------------------------
# Functions
#---------------------------------------------------------------------------

def gen_chars(n):
    '''Produces a set of n random word characters'''
    return "".join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_') for i in xrange(n))

def make_file(suggested):
    '''Creates a file in the upload directory based on the suggested name.'''
    import settings
    name = suggested and secure_filename(suggested) or gen_chars(16) # intentional non-use of ...if...else...
    subdirs = os.listdir(settings.upload_dir)
    random.shuffle(subdirs)
    # potential for race conditions here, but they're unlikely... ignore for now
    for subdir in subdirs:
        path = os.path.join(settings.upload_dir, subdir, name)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0644)
        except OSError:
            pass
        else:
            file_obj = os.fdopen(fd, 'w')
            break
    else: # omg it's actually useful here
        subdir = gen_chars(4)
        # Possible, but very unlikely, that this could fail due to the file existing
        os.mkdir(os.path.join(settings.upload_dir, subdir))
        path = os.path.join(settings.upload_dir, subdir, name)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0644)
        file_obj = os.fdopen(fd, 'w')
    return file_obj, subdir, name, path

# TODO: replace this with a more generic selector like ValueSelector, MemberSelector, etc.
class UploadIDSelector(Action):
    def generate(self, rsp, upload_id):
        if not isinstance(upload_id, list):
            upload_id = [upload_id]
        return {'uploads': Session().query(Upload).filter(Upload.id.in_(upload_id)).all()}

class UploadSubmitAggregator(Action):
    '''Saves uploaded files'''
    # TODO: specify ability to handle only certain form fields
    @classmethod
    def handles(cls, req, params):
        return len(req.files) > 0
    def generate(self, rsp):
        files_to_save = ((make_file(upload.filename), upload) for name, upload in self.req.files.iteritems() if upload.filename)
        uploads = []
        for (file_obj, subdir, name, path), upload in files_to_save:
            try:
                upload.save(file_obj)
            except (IOError,OSError):
                logging.getLogger('modulo.addons.upload').exception('Error saving uploaded file to ' + path)
                continue
            else:
                uploads.append(Upload(mime_type=upload.content_type, group=subdir, filename=name, path=path))
            finally:
                file_obj.close()
        return compact('uploads')
