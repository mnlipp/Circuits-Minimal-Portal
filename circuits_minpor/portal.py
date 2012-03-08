"""
..
   This file is part of the circuits bricks component library.
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
from circuits.web import expose
from circuits.core.components import BaseComponent
from circuits.web.servers import BaseServer
import os
from circuits.core.handlers import handler
import tenjin
from copy import copy
import uuid
from circuits_minpor.portlet import Portlet
from circuits_minpor.utils import BaseControllerExt
from circuits_bricks.web.dispatchers.dispatcher import HostDispatcher
from circuits_bricks.web.filters import LanguagePreferences, ThemeSelection
from circuits.web.sessions import Sessions
import threading
from rbtranslations import Translations, translation

class Portal(BaseComponent):

    channel = "mipypo"
    _thread_data = threading.local()
    _themes_dir = os.path.join(os.path.dirname(__file__), "templates", "themes")

    def __init__(self, server=None, prefix=None, 
                 portal_title=None, templates_dir=None, **kwargs):
        super(Portal, self).__init__(**kwargs)
        self._portlets = []
        if server is None:
            server = BaseServer(("", 4444), channel=self.channel)
        else:
            self.channel = server.channel
        self.server = server
        Sessions(channel = server.channel, 
                 name="mipypo.session").register(server)
        LanguagePreferences(channel = server.channel).register(server)
        ThemeSelection(channel = server.channel).register(server)
        dispatcher = HostDispatcher(channel = server.channel).register(server)
        _Root(self, host = server.channel,
              channel = prefix if prefix else "/",
              portal_title = portal_title,
              templates_dir = templates_dir) \
              .register(dispatcher)
            
        self._tabs = [_TabInfo("Overview", "_dashboard", selected=True)]
        
    @classmethod
    def translate(cls, text):
        trans = translation("l10n", 
                            os.path.join(cls._themes_dir, 
                                         ThemeSelection.selected()),
                                         LanguagePreferences.preferred())
        return trans.ugettext(text)
        
    @handler("registered")
    def _on_registered(self, c, m):
        if not isinstance(c, Portlet):
            return
        if not c in self._portlets:
            self._portlets.append(c)

    @handler("unregistered")
    def _on_unregistered(self, c, m):
        if not isinstance(c, Portlet):
            return
        if c in self._portlets:
            self._portlets.remove(c)

    @property
    def portlets(self):
        return copy(getattr(self, "_portlets", None))
    
    @property
    def tabs(self):
        return copy(getattr(self, "_tabs", None))

    @property
    def theme(self):
        return getattr(self, "_theme", "default")

    def select_tab(self, tab_id):
        for tab in self._tabs:
            tab._selected = (id(tab) == tab_id)

    def close_tab(self, tab_id):
        tabs = filter(lambda x: id(x) == tab_id, self._tabs)
        if len(tabs) == 0:
            return
        closed = tabs[0]
        closed_idx = self._tabs.index(closed)
        del self._tabs[closed_idx]
        if closed._selected:
            if len(self._tabs) > closed_idx:
                self._tabs[closed_idx]._selected = True
            else:
                self._tabs[0]._selected = True

    def add_solo(self, portlet_handle):
        for portlet in self._portlets:
            portlet_desc = portlet.description()
            if portlet_desc.handle == portlet_handle:
                break
            else:
                portlet_desc = None
        if not portlet_desc:
            return
        solo_tabs = filter(lambda x: x.portlet == portlet, self._tabs)
        if len(solo_tabs) > 0:
            self.select_tab(id(solo_tabs[0]))
            return
        tab = _TabInfo(portlet_desc.short_title, "_solo", closeable=True,
                       portlet=portlet)
        self._tabs.append(tab)
        self.select_tab(id(tab))

_ = Portal.translate


class _TabInfo(object):
    
    def __init__(self, label, renderer, selected = False, closeable=False,
                 portlet=None):
        self._label = label
        self._content_renderer = renderer
        self._selected = selected
        self._closeable = closeable
        self._portlet = portlet

    @property
    def label(self):
        return self._label
    
    @property
    def content_renderer(self):
        return self._content_renderer
        
    @property
    def selected(self):
        return self._selected
    
    @property
    def closeable(self):
        return self._closeable

    @property
    def portlet(self):
        return self._portlet


class _Root(BaseControllerExt):

    _docroot = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                            "templates"))
    
    def __init__(self, portal, **kwargs):
        super(_Root, self).__init__(**kwargs)
        self.host = kwargs.get("host", None)
        self._portal = portal
        path=[self._docroot]
        self._templates_override = kwargs.get("templates_dir", None)
        if self._templates_override:
            path.append(self._templates_override)
        self.engine = tenjin.Engine(path=path)
    
    @expose("index", filter=True)
    def index(self, *args, **kwargs):
        if len(args) > 0:
            return
        if kwargs.get("action") == "select":
            self._portal.select_tab(int(kwargs.get("tab")))
        elif kwargs.get("action") == "close":
            self._portal.close_tab(int(kwargs.get("tab")))
        elif kwargs.get("action") == "solo":
            self._portal.add_solo(uuid.UUID(kwargs.get("portlet")))
        context = {}
        context["portlets"] = self._portal.portlets
        context["tabs"] = self._portal.tabs
        context["locales"] = ["en_US"]
        return self.serve_tenjin \
            (self.request, self.response, "portal.pyhtml", context,
             engine=self.engine, type="text/html", 
             globexts = { "_": _ })

    @expose("theme-resource")
    def theme_resource(self, resource):
        if self._templates_override:
            f = os.path.join(self._templates_override, 
                             "themes", self._portal.theme, resource)
            if os.access(f, os.R_OK):
                return self.serve_file (f)
        f = os.path.join(self._docroot, 
                         "themes", self._portal.theme, resource)
        return self.serve_file (f)

