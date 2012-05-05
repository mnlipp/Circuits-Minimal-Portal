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
from circuits.web import tools
from circuits.core.components import BaseComponent
from circuits.web.servers import BaseServer
from circuits.web.events import WebEvent
import os
from circuits.core.handlers import handler
import tenjin
from copy import copy
from circuits_minpor.portlet import Portlet, RenderPortlet
from circuits_minpor.utils import serve_tenjin
from circuits_bricks.web.filters import LanguagePreferences, ThemeSelection
from circuits_bricks.app.logger import Log
from circuits.web.sessions import Sessions
from circuits.web.utils import parse_qs, parse_body
from threading import Thread, Semaphore
import rbtranslations
import urllib
import sys
import logging

class Portal(BaseComponent):
    """
    This class provides a portal, i.e. a web application that manages
    consolidation of small web applications, the so called portlets. 

    Once created and added to the circuits component hierarchy, the
    portal tracks the registering of :class:`circuits_minpor.Portlet`
    components. An associated dispatcher component handles the web
    requests and displays the render results from the portlets. 
    
    The class implements the session independent aspects of the portal.
    All session and state dependent aspects are handled in the associated
    portal view class.
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
        
        :param prefix: a prefix for URLs used by the portal. This allows
                       the portal to co-exist with other content on the same
                       web server. If specified, only requests with the
                       given prefix are handled by the portal dispatcher and 
                       the prefix is prepended to all generated URLs.
                       The value must start with a slash and must not 
                       end with a slash.
        :type prefix: string
        
        :param title: The title of the portal (displayed in the
                      browser's title bar)
        :type title: string
        
        :param templates_dir: a directory with templates that override
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
        LanguagePreferences(channel = server.channel).register(server)
        ThemeSelection(channel = server.channel).register(server)
        PortalView(self, channel = server.channel).register(server)
        self._supported_locales = []
        for locale in rbtranslations.available_translations\
            ("l10n", self._templates_path, "en"):
            trans = rbtranslations.translation\
                ("l10n", self._templates_path, [locale], "en")
            locale_name = trans.ugettext("language_" + locale)
            self._supported_locales.append((locale, locale_name))
        self._supported_locales.sort(key=lambda x: x[1])
            
    @handler("registered", channel="*")
    def _on_registered(self, c, m):
        if not isinstance(c, Portlet):
            return
        if not c in self._portlets:
            self._portlets.append(c)
            self._enabled_events_changed = True

    @handler("unregistered")
    def _on_unregistered(self, c, m):
        if not isinstance(c, Portlet):
            return
        if c in self._portlets:
            self._portlets.remove(c)
            self._enabled_events_changed = True

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
    def supported_locales(self):
        return getattr(self, "_supported_locales", [])

    def portlet_by_handle(self, portlet_handle):
        for portlet in self._portlets:
            portlet_desc = portlet.description()
            if portlet_desc.handle == portlet_handle:
                return portlet
        return None


class _TabInfo(object):
    
    def __init__(self, renderer, selected = False, closeable=False,
                 portlet=None):
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

    
class PortalView(BaseComponent):
    """
    The :class:`PortalView` handles all requests directed at the portal.
    These may be render requests for the portal itself, requests
    for a portal resource, action requests directed at a portlet and 
    resource requests directed at a portet.
    """
    _waiting_for_event_complete = False
    _enabled_events = None
    _session = dict()

    class _UGFactory(Portlet.UrlGeneratorFactory):
        
        def __init__(self, prefix):
            self._prefix = prefix
        
        class UG(Portlet.UrlGenerator):
    
            def __init__(self, prefix, portlet):
                self._prefix = prefix
                self._handle = portlet.description().handle
                self._channel = portlet.channel
        
            def event_url(self, event_name, channel=None, 
                          portlet_mode=None, portlet_window_state=None,
                          **kwargs):
                if not channel:
                    channel = self._channel
                url = self._prefix + "/" + self._handle
                if portlet_mode != None or portlet_window_state != None:
                    if portlet_mode == None:
                        portlet_mode = "_"
                    if portlet_window_state == None:
                        portlet_window_state = "_"
                    url += "/" + portlet_mode + "/" + portlet_window_state
                return (url + "/event/"+ urllib.quote(event_name)
                        + "/" + urllib.quote(channel)
                        + ("" if len(kwargs) == 0 
                           else "?" + urllib.urlencode(kwargs)))

            def resource_url(self, resource):
                return self._prefix + "/portlet-resource/" \
                    + urllib.quote(self._handle) \
                    + (resource if resource.startswith("/") \
                                else ("/" + urllib.quote(resource)))
    
        def make_generator(self, portlet):
            return self.UG(self._prefix, portlet)
        
    def __init__(self, portal, *args, **kwargs):
        super(PortalView, self).__init__(*args, **kwargs)
        self.host = kwargs.get("host", None)
        self._portal = portal
        self._engine = tenjin.Engine(path=portal._templates_path)
        self._portal_resource = portal.prefix + "/portal-resource/"
        self._theme_resource = portal.prefix + "/theme-resource/"
        self._portlet_resource = portal.prefix + "/portlet-resource/"
        self._portal_prefix = portal.prefix
        self._portal_path = "/" if portal.prefix == "" else portal.prefix
        self._ugFactory = PortalView._UGFactory(portal.prefix)
        self._session_cookie = self.channel + ".session" 
        Sessions(channel = self.channel, 
                 name=self._session_cookie).register(self)

    @handler("registered", channel="*")
    def _on_registered(self, c, m):
        if not isinstance(c, Portlet):
            return
        self._enabled_events = None

    @handler("unregistered")
    def _on_unregistered(self, c, m):
        if not isinstance(c, Portlet):
            return
        self._enabled_events = None

    @property
    def portal(self):
        return getattr(self, "_portal", None)

    @property
    def tabs(self):
        return self._session.get("_tabs", [])

    @property
    def theme(self):
        return getattr(self._session, "_theme", "default")

    @property
    def configuring(self):
        return self._session.get("_configuring", None)

    def _select_tab(self, tab_id):
        found = False
        for tab in self._session["_tabs"]:
            tab._selected = (id(tab) == tab_id)
            found = found or tab._selected
        if not found:
            self._session["_tabs"][0]._selected = True

    def _close_tab(self, tab_id):
        tabs = filter(lambda x: id(x) == tab_id, self._session["_tabs"])
        if len(tabs) == 0:
            return
        closed = tabs[0]
        closed_idx = self._session["_tabs"].index(closed)
        del self._session["_tabs"][closed_idx]
        if closed._selected:
            if len(self._session["_tabs"]) > closed_idx:
                self._session["_tabs"][closed_idx]._selected = True
            else:
                self._session["_tabs"][0]._selected = True

    def _add_solo(self, portlet):
        solo_tabs = filter(lambda x: x.portlet 
                           == portlet, self._session["_tabs"])
        if len(solo_tabs) > 0:
            self._select_tab(id(solo_tabs[0]))
            return
        tab = _TabInfo("_solo", closeable=True, portlet=portlet)
        self._session["_tabs"].append(tab)
        self._select_tab(id(tab))

    def _is_portal_request(self, request):
        return request.path == self._portal_path \
            or request.path.startswith(self._portal_prefix + "/")
    
    @handler("request", filter=True, priority=0.1)
    def _on_request(self, event, request, response, peer_cert=None):
        """
        First request handler. This handler handles resource requests
        directed at the portal or a portlet.
        """
        if not self._is_portal_request(request):
            return None

        if peer_cert:
            event.peer_cert = peer_cert
        # Add path to session cookie, else duplicates may occur
        response.cookie[self.channel+".session"]["path"] = self._portal_path
        # Decode query parameters
        event.kwargs = dict()
        for key, value in parse_qs(request.qs).items():
            event.kwargs[unicode(key.encode("iso-8859-1"), "utf-8")] \
                = unicode(value.encode("iso-8859-1"), "utf-8")
        parse_body(request, response, event.kwargs)
        # Is this a portal request?
        if request.path.startswith(self._portal_resource):
            request.path = request.path[len(self._portal_resource):]
            res = os.path.join(os.path.join\
                (os.path.dirname(__file__), request.path))
            if os.path.exists(res):
                return tools.serve_file(request, response, res)
            return
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
                    (WebEvent.create("PortletResource", *event.args,
                                    **event.kwargs), segs[0])        

    @handler("request", filter=True, priority=0.09)
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
        
        The URLs carry most information in the path in order to
        be usable as form action URLs without problems. The format is
        ``/{"portal" or portlet handle}[/{new portlet mode or _}/{new portlet state or _}]``
        If the portlet is to perform an action as part of the request, the
        above is followed by 
        ``/event/{event class name}/{channel }``.
        """
        if not self._is_portal_request(request):
            return

        self._session = request.session        
        if not self._session.has_key("_tabs"):
            request.session["_tabs"] = [_TabInfo("_dashboard", selected=True)]
        
        path_segs = unicode(urllib.unquote\
                            (request.path[len(self._portal_prefix)+1:])
                            .encode("iso-8859-1"), "utf-8").split("/")
        portlet = None
        if path_segs[0] != '':
            if path_segs[0] == "portal":
                # Perform requested portal actions
                self._perform_portal_actions(request, path_segs, event.kwargs)
            else:
                portlet = self._portal.portlet_by_handle(path_segs[0])
                if portlet != None:
                    del path_segs[0]


        if portlet != None:
            # Perform requested portlet state changes
            self._perform_portlet_state_changes(portlet, path_segs)
            # Get requested events
            evt = self._requested_event(path_segs, event, request, response)
            
            if evt:
                self._waiting_for = evt
                @handler("%s_complete" % evt.name, channel=evt.channels[0])
                def _on_complete(dispatcher, e, value):
                    if id(self._waiting_for) == id(e):
                        self._waiting_for = None
                self.addHandler(_on_complete)
                self.fireEvent(evt)
                while self._waiting_for:
                    yield None
                self.removeHandler(_on_complete)
    
        # Render portal
        event.portal_response = None
        # See _render_portal_template for an explanation
        # why we need another thread here. Pass any information
        # that is thread local as addition parameters
        self._RenderThread(self, event, request, response).start()
        while not event.portal_response:
            yield None
        yield event.portal_response

    def _perform_portal_actions(self, request, path_segs, kwargs):
        """
        Perform any requested changes of the portal state.
        """
        action = path_segs[1]
        if action == "language":
            LanguagePreferences\
                .override_accept(request.session, [kwargs["language"]])
        elif action == "select":
            self._select_tab(int(kwargs.get("tab")))
        elif action == "close":
            self._close_tab(int(kwargs.get("tab")))
        elif action == "finish-editing":
            del self._session["_configuring"]

    def _perform_portlet_state_changes(self, portlet, path_segs):
        if len(path_segs) < 2 or path_segs[0] == "event":
            return
        mode = path_segs[0]
        window_state = path_segs[1]
        del path_segs[0:2]
        if self._session.get("_configuring", None) == portlet \
            and mode != "edit":
            del self._session["_configuring"]
        if mode == "edit":
            self._session["_configuring"] = portlet
        if window_state == "solo":
            self._add_solo(portlet)

    def _requested_event(self, path_segs, event, request, response):
        if len(path_segs) < 3 or path_segs[0] != "event":
            return None
        evt_class = path_segs[1]
        channel = path_segs[2]
        del path_segs[0:3]
        if not self._check_event(evt_class, channel):
            return None
        try:
            names = evt_class.split(".")
            clazz = reduce(getattr, names[1:], sys.modules[names[0]])
        except AttributeError:
            self.fire(Log(logging.ERROR, 
                          "Unknown event class in event URL: " + evt_class))
            return None
        try:
            if event.kwargs:
                evnt = clazz(**event.kwargs)
            else:
                evnt = clazz()
        except Exception:
            self.fire(Log(logging.ERROR, 
                          "Cannot create event: " + str(sys.exc_info()[1])))
            return None
        evnt.channels = (channel,)
        evnt.complete = True
        return evnt
                
    def _check_event(self, event_name, channel):
        if not self._enabled_events:
            self._enabled_events = dict()
            for portlet in self._portal._portlets:
                for clazz, chan in portlet.description().events:
                    name = clazz.__module__ + "." + clazz.__name__
                    if not self._enabled_events.has_key(name):
                        self._enabled_events[name] = set()
                    if self._enabled_events[name] == None:
                        continue
                    if chan == "*":
                        self._enabled_events[name] = None
                        continue
                    self._enabled_events[name].add(chan)
        chans = self._enabled_events.get(event_name, set())
        return chans == None or channel in chans
                
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

        def __init__(self, view, req_evt, request, response):
            super(PortalView._RenderThread, self).__init__()
            self._view = view
            self._req_evt = req_evt
            self._request = request
            self._response = response
            self._theme = ThemeSelection.selected()
            self._locales = LanguagePreferences.preferred()
            self._translation = rbtranslations.translation\
                ("l10n", view._portal._templates_path, 
                 self._locales, "en")
            if self._translation.language:
                response.headers["Content-Language"] \
                    = self._translation.language.replace("_", "-")

        def run(self):
            context = { "portal_view": self._view,
                        "theme": self._theme,
                        "locales": self._locales
                      }
            
            def render(portlet, mime_type="text/html", 
                       mode=Portlet.RenderMode.View, 
                       window_state=Portlet.WindowState.Normal, 
                       locales=[], **kwargs):
                """
                The render portlet function made available to the template 
                engine. It fires the :class:`RenderPortlet` event and waits
                for the result to become available.
                """
                evt = RenderPortlet(mime_type, mode, window_state, locales, 
                                    self._view._ugFactory, **kwargs)
                evt.success_channels = [self._view.channel]
                evt.sync = Semaphore(0)
                self._view.fire(evt, portlet.channel)
                evt.sync.acquire()
                return evt.value.value 
            # Render the template.
            def portal_action_url(action, **kwargs):
                return (self._view._portal_prefix
                        + "/portal/" + urllib.quote(action)
                        + (("?" + urllib.urlencode(kwargs)) if kwargs else ""))
            def portlet_state_url(portlet_handle, mode="_", window="_"):
                return (self._view._portal_prefix
                        + "/" + portlet_handle + "/" + mode + "/" + window)
                        
            self._req_evt.portal_response = serve_tenjin \
                (self._view._engine, self._request, self._response,
                 "portal.pyhtml", context, type="text/html", 
                 globexts = { "_": self._translation.ugettext,
                              "portal_action_url": portal_action_url,
                              "portlet_state_url": portlet_state_url,
                              "resource_url": 
                              (lambda x: self._view._portal.prefix + "/" + x),
                              "render": render})
    
    @handler("render_portlet_success")
    def _render_portlet_success (self, e, *args, **kwargs):
        e.sync.release()

                
