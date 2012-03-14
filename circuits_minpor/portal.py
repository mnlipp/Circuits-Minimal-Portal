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
from circuits.web.events import Request
import os
from circuits.core.handlers import handler
import tenjin
from copy import copy
from circuits_minpor.portlet import Portlet, RenderPortlet
from circuits_minpor.utils import serve_tenjin
from circuits_bricks.web.filters import LanguagePreferences, ThemeSelection
from circuits.web.sessions import Sessions
from circuits.web.utils import parse_qs, parse_body
from threading import Thread, Semaphore
import rbtranslations

class Portal(BaseComponent):
    """
    This class implements a portal, i.e. a web application that manages
    consolidation of small web applications, the so called portlets. 
    """

    channel = "minpor"
    
    _prefix = None
    _title = None

    def __init__(self, server=None, prefix=None, 
                 title=None, templates_dir=None, **kwargs):
        """
        :param server: the component that handles the basic connection
                       and protocol management. If not provided, the
                       Portal creates its own  
                       :class:`~circuits.web.server.BaseServer` component
                       that listens on port 4444.
        :type server: :class:`circuits.web.server.BaseServer`
        
        :param prefix: a prefix for URLs used in the portal. This allows
                       the portal to co-exist with other content on the same
                       web server. If specified, all URLs will be prefixed
                       with this parameter. The value must start with a 
                       slash and must not end with a slash.
        :type prefix: string
        
        :param title: The title of the portal (displayed in the
                      browser's title bar)
        :type title: string
        
        :param templates_dir: a directory with templates that replace
                              the portal's standard templates. Any template
                              and localization resource is first searched
                              for in this directory, then in the portal's
                              built-in default directory.
        :type templates_dir: string
        """
        super(Portal, self).__init__(**kwargs)
        self._prefix = prefix or ""
        self._title = title
        self._portlets = []
        if server is None:
            server = BaseServer(("", 4444), channel=self.channel)
        else:
            self.channel = server.channel
        self.server = server
        if templates_dir:
            self._templates_path = [os.path.abspath(templates_dir)]
        else:
            self._templates_path = []
        self._templates_path \
            += [os.path.join(os.path.dirname(__file__), "templates")]
        Sessions(channel = server.channel, 
                 name=server.channel+".session").register(server)
        LanguagePreferences(channel = server.channel).register(server)
        ThemeSelection(channel = server.channel).register(server)
        PortalDispatcher(self, channel = server.channel).register(server)
            
        self._tabs = [_TabInfo("Overview", "_dashboard", selected=True)]
        
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
    def prefix(self):
        return self._prefix

    @property
    def title(self):
        return self._title

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

    class _UGFactory(Portlet.UrlGeneratorFactory):
        
        def __init__(self, prefix):
            self._prefix = prefix
        
        class UG(Portlet.UrlGenerator):
    
            def __init__(self, prefix, portlet):
                self._prefix = prefix
                self._handle = portlet.description().handle
        
            def action_url(self, event):
                return "#"
    
            def resource_url(self, resource):
                return self._prefix + "/portlet-resource/" + self._handle \
                    + (resource if resource.startswith("/") \
                                else ("/" + resource))
    
        def make_generator(self, portlet):
            return self.UG(self._prefix, portlet)
        
    def __init__(self, portal, *args, **kwargs):
        super(PortalDispatcher, self).__init__(*args, **kwargs)
        self.host = kwargs.get("host", None)
        self._portal = portal
        self._engine = tenjin.Engine(path=portal._templates_path)
        self._theme_resource = portal.prefix + "/theme-resource/"
        self._portlet_resource = portal.prefix + "/portlet-resource/"
        self._portal_path = "/" if portal.prefix == "" else portal.prefix
        self._ugFactory = PortalDispatcher._UGFactory(portal.prefix)

    
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
        # Is this a portal resource request?
        if request.path.startswith(self._theme_resource):
            request.path = request.path[len(self._theme_resource):]
            for directory in self._portal._templates_path:
                res = os.path.join(directory, "themes", 
                                   ThemeSelection.selected(), request.path)
                if os.path.exists(res):
                    return tools.serve_file(request, response, res)
            return
        # Is this a portlet resource request?
        if request.path.startswith(self._portlet_resource):
            segs = request.path[len(self._portlet_resource):].split("/")
            if len(segs) >= 2:
                request.path = "/".join(segs[1:])
                event.kwargs.update\
                    ({ "theme": ThemeSelection.selected(),
                       "locales": LanguagePreferences.preferred()})
                return self.fire\
                    (Request.create("PortletResource", *event.args,
                                    **event.kwargs), segs[0])        

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
        if request.path == self._portal_path:
            event.portal_response = None
            # See _render_portal_template for an explanation
            # why we need another thread here. Pass any information
            # that is thread local as addition parameters
            self._RenderThread(self, event, request, response).start()
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
            self._portal.add_solo(kwargs.get("portlet"))

                
    class _RenderThread(Thread):
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

        _translations_cache = dict()

        def __init__(self, dispatcher, req_evt, request, response):
            super(PortalDispatcher._RenderThread, self).__init__()
            self._dispatcher = dispatcher
            self._req_evt = req_evt
            self._request = request
            self._response = response
            self._theme = ThemeSelection.selected()
            self._locales = LanguagePreferences.preferred()
            lang_hash = ";".join(self._locales)
            self._translation = self._translations_cache.get\
                ((self._theme, lang_hash))
            if not self._translation:
                last_dir = len(dispatcher._portal._templates_path) - 1
                for i, d in enumerate(dispatcher._portal._templates_path):
                    trans = rbtranslations.translation\
                        ("l10n", d, self._locales, \
                         key_language=("en" if i == last_dir else None))
                    if not self._translation:
                        self._translation = trans
                    else:
                        self._translation.add_fallback(trans)
                self._translations_cache[(self._theme, lang_hash)] \
                    = self._translation

        def run(self):
            portal = self._dispatcher._portal
            context = { "title": portal.title,
                        "portlets": portal.portlets,
                        "tabs": portal.tabs,
                        "theme": self._theme,
                        "locales": self._locales
                      }
            
            def render(portlet, mode=Portlet.RenderMode.View, 
                       window_state=Portlet.WindowState.Normal, 
                       locales=[], **kwargs):
                """
                The render portlet function made availble to the template 
                engine. It fires the :class:`RenderPortlet` event and waits
                for the result to become available.
                """
                evt = RenderPortlet(mode, window_state, locales, 
                                    self._dispatcher._ugFactory, **kwargs)
                evt.success_channels = [self._dispatcher.channel]
                self._dispatcher.fire(evt, portlet.channel)
                evt.sync = Semaphore(0)
                evt.sync.acquire()
                return evt.value.value 
            # Render the template.
            self._req_evt.portal_response = serve_tenjin \
                (self._dispatcher._engine, self._request, self._response,
                 "portal.pyhtml", context, type="text/html", 
                 globexts = { "_": self._translation.ugettext,
                              "resource_url": (lambda x: portal.prefix + "/" + x),
                              "render": render})
    
    @handler("render_portlet_success")
    def _render_portlet_success (self, e, *args, **kwargs):
        e.sync.release()

                
