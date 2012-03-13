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
from circuits.web import tools
from circuits.core.components import BaseComponent
from circuits.web.servers import BaseServer
import os
from circuits.core.handlers import handler
import tenjin
from copy import copy
import uuid
from circuits_minpor.portlet import Portlet, RenderPortlet
from circuits_minpor.utils import serve_tenjin
from circuits_bricks.web.filters import LanguagePreferences, ThemeSelection
from circuits.web.sessions import Sessions
import threading
from rbtranslations import translation
from circuits.web.utils import parse_qs, parse_body
from threading import Thread, Semaphore

class Portal(BaseComponent):

    channel = "minpor"
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
                 name=server.channel+".session").register(server)
        LanguagePreferences(channel = server.channel).register(server)
        ThemeSelection(channel = server.channel).register(server)
        PortalDispatcher(self, channel = server.channel).register(server)
            
        self._tabs = [_TabInfo("Overview", "_dashboard", selected=True)]
        
    @classmethod
    def translation(cls):
        return translation("l10n", 
                           os.path.join(cls._themes_dir, 
                                        ThemeSelection.selected()),
                                        LanguagePreferences.preferred())
        
    @handler("registered", channel="*")
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

_ = Portal.translation().ugettext


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


class PortalDispatcher(BaseComponent):
    """
    The :class:`PortalDispatcher` handles all request directed at the
    portal. These may be render requests for the portal itself, requests
    for a portal resource, action requests directed at a portlet and resource
    requests directed at a portet.
    """

    _docroot = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                            "templates"))

    def __init__(self, portal, *args, **kwargs):
        super(PortalDispatcher, self).__init__(*args, **kwargs)
        self.host = kwargs.get("host", None)
        self._portal = portal
        path=[self._docroot]
        self._templates_override = kwargs.get("templates_dir", None)
        if self._templates_override:
            path.append(self._templates_override)
        self.engine = tenjin.Engine(path=path)
    
    @handler("request", filter=True, priority=0.1)
    def _on_request(self, event, request, response, peer_cert=None):
        """
        First request handler. This handler handles resource requests
        directed at the portal or a portlet.
        """
        if peer_cert:
            event.peer_cert = peer_cert
        event.kwargs = parse_qs(request.qs)
        parse_body(request, response, event.kwargs)
        # Is this a resource request?
        if request.path.startswith("/theme-resource/"):
            request.path = request.path[len("/theme-resource/"):]
            f = os.path.join(self._portal._themes_dir, 
                             self._portal.theme, request.path)
            return tools.serve_file(request, response, f)
        # TODO: handle portlet resources
        
    @handler("request", filter=True, priority=0.05)
    def _on_portal_request(self, event, request, response, peer_cert=None):
        """
        Second request handler. This handler processes portlet actions
        and portal render requests. Portal rendering has to be done in
        a separate handler, because it uses circuits' "suspend" feature
        (handler returns a generator, which may not be mixed with
        regular returns). This allows us to render the portlets
        using render events that are processed before this handler returns
        its result. Using :class:`RenderRequest` events instead of invoking
        the render method directly allows other components to intercept
        the requests as is usual in circuits.
        """
        # Perform requested portal actions (state changes)
        self._perform_portal_actions(event.kwargs)

        # Render portal
        if request.path == "/":
            event.portal_response = None
            # See _render_portal_template for an explanation
            # why we need another thread here. Pass any information
            # that is thread local as addition parameters
            Thread(target=self._render_portal_template,
                   args=(event, request, response, 
                         ThemeSelection.selected(),
                         LanguagePreferences.preferred(),
                         self._portal.translation())).start()
            while not event.portal_response:
                yield None
            yield event.portal_response

    def _perform_portal_actions(self, kwargs):
        """
        Perform any requested changes of the portal state.
        """
        if kwargs.get("action") == "select":
            self._portal.select_tab(int(kwargs.get("tab")))
        elif kwargs.get("action") == "close":
            self._portal.close_tab(int(kwargs.get("tab")))
        elif kwargs.get("action") == "solo":
            self._portal.add_solo(uuid.UUID(kwargs.get("portlet")))

    def _render_portal_template(self, req_evt, request, response, 
                                theme, locales, portal_translation):
        """
        Render the portal using the "top" template. The template needs
        the individual portlet's content at certain points. As we want
        that content to be provided as response to a :class:`RenderPortlet`
        event, we have to suspend the execution of the template until the
        response becomes available. If tenjin was made for circuits, it could
        yield until the results becomes available. As this is not the case,
        we execute the template in its own thread. Whenever portlet
        content is required, the :class:`RenderPortlet` event is fired
        and execution suspended by waiting on a semaphore. The render
        request is executed in the main thread and its completion signaled
        back to the template processor using the semaphore.
        """
        context = { "portlets": self._portal.portlets,
                    "tabs": self._portal.tabs,
                    "theme": theme,
                    "locales": locales
                  }
        
        def render(portlet, mode=Portlet.RenderMode.View, 
                   window_state=Portlet.WindowState.Normal, 
                   locales=[], **kwargs):
            """
            The render portlet function made availble to the template engine.
            It fires the :class:`RenderPortlet` event and waits for the
            result to become available.
            """
            evt = RenderPortlet(mode, window_state, locales, 
                                Portlet.UrlGenerator(), **kwargs)
            evt.success_channels = [self.channel]
            self.fire(evt, portlet.channel)
            evt.sync = Semaphore(0)
            evt.sync.acquire()
            return evt.value.value 
        # Render the template.
        req_evt.portal_response = serve_tenjin \
            (self.engine, request, response, "portal.pyhtml", 
             context, type="text/html", 
             globexts = { "_": portal_translation.ugettext , "render": render})


    @handler("render_portlet_success")
    def _render_portlet_success (self, e, *args, **kwargs):
        e.sync.release()
    
