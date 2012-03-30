"""
..
   This file is part of the circuits minimal portal component.
   Copyright (C) 2012 Michael N. Lipp
   
   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.
   
   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <http://www.gnu.org/licenses/>.

.. moduleauthor:: mnl
"""
from circuits.web.controllers import BaseController
from circuits.web.errors import HTTPError

import os
import sys, traceback
import mimetypes
import tenjin
from tenjin.helpers import *

class BaseControllerExt(BaseController):

    def __init__(self, *args, **kwargs):
        super(BaseControllerExt, self).__init__(*args, **kwargs)
        self.engine = tenjin.Engine()

    def serve_tenjin(self, request, response, path, context, 
                     type=None, disposition=None, name=None,
                     engine=None, globexts=None):
        return serve_tenjin(engine or self.engine, request, response, path, 
                            context, type, disposition, name, globexts)

def serve_tenjin(engine, request, response, path, context, 
                 type=None, disposition=None, name=None, globexts=None):
    if not engine and not os.path.isabs(path):
        raise ValueError("'%s' is not an absolute path." % path)

    if type is None:
        # Set content-type based on filename extension
        ext = ""
        i = path.rfind('.')
        if i != -1:
            ext = path[i:].lower()
        if ext == ".pyhtml":
            ext = ".html"
        type = mimetypes.types_map.get(ext, "text/plain")
    response.headers['Content-Type'] = type

    if disposition is not None:
        if name is None:
            name = os.path.basename(path)
        cd = '%s; filename="%s"' % (disposition, name)
        response.headers["Content-Disposition"] = cd

    if globexts:
        globs = tenjin.helpers.__dict__.copy()
        globs.update(globexts)
    else:
        globs = tenjin.helpers.__dict__
    #tenjin.helpers.

    try:
        response.body = engine.render(path, context, globals = globs)
    except Exception as error:
        etype, evalue, etraceback = sys.exc_info()
        error = (etype, evalue, traceback.format_tb(etraceback))
        return HTTPError(request, response, 500, error=error)        
    return response
