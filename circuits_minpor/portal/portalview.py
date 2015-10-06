"""
..
   This file is part of the circuits minimal portal component.
   Copyright (C) 2012-2015 Michael N. Lipp
   
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
from circuits.core.components import BaseComponent
from circuits_minpor.portlet import Portlet, render_portlet
import urllib
import tenjin
from circuits.web.sessions import Sessions
from circuits_minpor.utils.dispatcher import WebSocketsDispatcherPlus
from circuits.core.handlers import handler
from circuits.web.utils import parse_qs, parse_body
import os
from circuits.web import tools
from circuits_bricks.web.misc import ThemeSelection, LanguagePreferences
from circuits_minpor.portal.events import portal_client_connect,\
    portal_client_disconnect, portlet_resource
from circuits_bricks.app.logger import log
import logging
import sys
from threading import Thread, Semaphore
import rbtranslations
from circuits_minpor.utils.misc import serve_tenjin
import json
from circuits.io.events import write
from circuits_minpor.portal.portalsessionfacade import PortalSessionFacade
from os.path import dirname, join

class PortalView(BaseComponent):
    """
    The :class:`PortalView` handles all requests directed at the portal
    from a client (browser). These may be render requests for the portal 
    itself, requests for a portal resource, action requests directed at 
    a portlet and resource requests directed at a portet.
    
    From a conceptual point of view, there is one PortalView per session.
    This would, however, consume a lot of resources as we'd also need
    copies of all the child components. So instead, all events handled
    by the PortalView have a direct or indirect association with the session.
    All operations (unless directed at the portal as a whole, i.e. affecting
    all sessions) operate on the data stored in this session object.
    """
    
    _waiting_for_event_complete = False    
    # The cache of events that portlets accept from the client.  
    _accepted_events = None 

    def __init__(self, portal, *args, **kwargs):
        super(PortalView, self).__init__(*args, **kwargs)
        self.host = kwargs.get("host", None)
        self._portal = portal
        self._engine = tenjin.Engine(path=portal._templates_dir)
        self._portal_prefix = "" if portal.path == "/" else portal.path
        self._portal_resource = self.prefix + "/portal-resource/"
        self._portal_resource_dir = join(dirname(dirname(__file__)), "static")
        self._theme_resource = self.prefix + "/theme-resource/"
        self._portlet_resource = self.prefix + "/portlet-resource/"
        self._ugFactory = UGFactory(self.prefix)
        Sessions(channel = self.channel, 
                 name=self.channel + ".session").register(self)
        self._event_exchange_channel = self._portal.channel + "-eventExchange"
        WebSocketsDispatcherPlus(self.prefix + "/eventExchange", 
                channel=self.channel, wschannel=self._event_exchange_channel) \
                .register(self)
                
        # Handle web socket connects from client
        @handler("connect", channel=self._event_exchange_channel)
        def _on_ws_connect(self, event, sock, *peername, **kwargs):
            session = kwargs.get("session")
            if session:
                session[self.__class__.__name__ + ".client_connection"] = sock
            self.fire(portal_client_connect(self.facade(session)), \
                      self._portal.channel)
        self.addHandler(_on_ws_connect)
        
        # Handle web socket disconnects from client
        @handler("disconnect", channel=self._event_exchange_channel)
        def _on_ws_disconnect(self, event, sock, *peername, **kwargs):
            session = kwargs.get("session")
            if self.client_connection(session) == sock:
                session[self.__class__.__name__ + ".client_connection"] = None
            self.fire(portal_client_disconnect(self.facade(session), sock), \
                      self._portal.channel)
        self.addHandler(_on_ws_disconnect)
        
        # Handle a message from the client
        @handler("read", channel=self._event_exchange_channel)
        def _on_ws_read(self, socket, data, **kwargs):
            self._on_message_from_client(kwargs.get("session"), data)
        self.addHandler(_on_ws_read)

        # Handle a portal update event for the portal
        @handler("portal_update", channel=self._portal.channel)
        def _on_portal_update_handler(self, portlet, session, name, *args):
            self._on_portal_update(portlet, session, name, *args)
        self.addHandler(_on_portal_update_handler)
        
        # Handle a portal message event for the portal
        @handler("portal_message", channel=self._portal.channel)
        def _on_portal_message(self, session, message, clazz=""):
            self._on_portal_update \
                (None, session, "portal_message", message, clazz)
        self.addHandler(_on_portal_message)

    @property
    def prefix(self):
        return self._portal_prefix

    def facade(self, session):
        facade = session.get(self.__class__.__name__ + ".facade")
        if facade is None:
            facade = PortalSessionFacade(self, session)
            session[self.__class__.__name__ + ".facade"] = facade
        return facade
        
    @handler("registered", channel="*")
    def _on_registered(self, c, m):
        """
        Flushes the accepted events cache if the set of known portlets
        changes.
        """
        if not isinstance(c, Portlet):
            return
        self._accepted_events = None

    @handler("unregistered")
    def _on_unregistered(self, c, m):
        """
        Flushes the accepted events cache if the set of known portlets
        changes.
        """
        if not isinstance(c, Portlet):
            return
        self._accepted_events = None

    @property
    def portal(self):
        return getattr(self, "_portal", None)

    @property
    def url_generator_factory(self):
        return getattr(self, "_ugFactory", None)

    def tab_manager(self, session):
        return TabManager.get(session)

    def configuring(self, session):
        return session.get("_configuring", None)

    def client_connection(self, session):
        return session.get(self.__class__.__name__ + ".client_connection")

    def _is_portal_request(self, request):
        return request.path == self.prefix \
            or (request.path.startswith(self.prefix + "/") \
                and request.path != self.prefix + "/eventExchange")
    
    @handler("request", priority=0.8)
    def _on_request_1(self, event, request, response, peer_cert=None):
        """
        First request handler. This handler handles resource requests
        directed at the portal or a portlet.
        """
        if not self._is_portal_request(request):
            return

        if peer_cert:
            event.peer_cert = peer_cert
            
        # Add path to session cookie, else duplicates may occur
        response.cookie[self.channel+".session"]["path"] = self._portal.path
        
        # Decode query parameters and body
        event.kwargs = parse_qs(request.qs)
        parse_body(request, response, event.kwargs)
        session = request.session
        # Is this a portal portal request?
        if request.path.startswith(self._portal_resource):
            res = os.path.join(os.path.join\
                (self._portal_resource_dir, 
                 request.path[len(self._portal_resource):]))
            if os.path.exists(res):
                event.stop()
                return tools.serve_file(request, response, res)
            return
        # Is this a portal theme resource request?
        if request.path.startswith(self._theme_resource):
            for directory in self._portal._templates_dir:
                res = os.path.join \
                    (directory, "themes", 
                     ThemeSelection.selected(session), 
                     request.path[len(self._theme_resource):])
                if os.path.exists(res):
                    event.stop()
                    return tools.serve_file(request, response, res)
            return
        # Is this a portlet resource request?
        if request.path.startswith(self._portlet_resource):
            segs = request.path[len(self._portlet_resource):].split("/")
            if len(segs) >= 2:
                request.path = "/".join(segs[1:])
                event.kwargs.update\
                    ({ "theme": ThemeSelection.selected(session),
                       "locales": LanguagePreferences.preferred(session)})
                return self.fire (portlet_resource(*event.args, 
                                                   **event.kwargs), segs[0])

    @handler("request", priority=0.79)
    def _on_request_2(self, event, request, response, peer_cert=None):
        """
        Second request handler. This handler processes portlet actions
        and portal render requests. Portal rendering has to be done in
        a separate handler, because it uses circuits' "suspend" feature
        (handler returns a generator, which may not be mixed with
        regular returns in Python). This allows us to render the portlets
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

        session = request.session
        
        path_segs = urllib.unquote \
            (request.path[len(self.prefix)+1:]).split("/")
        portlet = None
        if path_segs[0] != '':
            if path_segs[0] == "portal":
                # Perform requested portal actions
                self._perform_portal_actions \
                    (request, response, path_segs, event.kwargs)
            else:
                portlet = self._portal.portlet_by_handle(path_segs[0])
                if portlet != None:
                    del path_segs[0]


        if portlet != None:
            # Perform requested portlet state changes
            self._perform_portlet_state_changes(session, portlet, path_segs)
            # Get requested events
            if len(path_segs) >= 3 and path_segs[0] == "event":
                evt = self._create_event_from_request \
                    (session, path_segs[1], [], 
                     getattr(event, "kwargs", {}), path_segs[2])
                del path_segs[0:3]
                
                if evt:
                    evt.complete = True
                    self._waiting_for = evt
                    @handler("%s_complete" % evt.name, channel=evt.channels[0])
                    def _on_complete(self, e, value):
                        if id(self._waiting_for) == id(e):
                            self._waiting_for = None
                    complete_handler = self.addHandler(_on_complete)
                    self.fireEvent(evt)
                    while self._waiting_for:
                        yield None
                    self.removeHandler(complete_handler)
    
        # We'll handle this request
        event.stop()
        # Render portal
        event.portal_response = None
        # See _render_portal_template for an explanation
        # why we need another thread here. Pass any information
        # that is thread local as addition parameters
        RenderThread(self, event, request, response).start()
        while not event.portal_response:
            yield None
        yield event.portal_response

    @handler("request", priority=0.78)
    def _on_request_3(self, event, request, response, peer_cert=None):
        """
        Third request handler. Required because of GitHub bug #136.
        Will be removed when the bug is fixed.
        """
        if not self._is_portal_request(request):
            return
        event.stop()

    def _perform_portal_actions(self, request, response, path_segs, kwargs):
        """
        Perform any requested changes of the portal state.
        """
        action = path_segs[1]
        if action == "language":
            LanguagePreferences.override_accept \
                (request.session, [kwargs["language"]], response)
        elif action == "select":
            self.tab_manager(request.session).select_tab(int(kwargs.get("tab")))
        elif action == "close":
            self.tab_manager(request.session).close_tab(int(kwargs.get("tab")))
        elif action == "finish-editing":
            self.tab_manager(request.session).configure(None)

    def _perform_portlet_state_changes(self, session, portlet, path_segs):
        if len(path_segs) < 2 or path_segs[0] == "event":
            return
        mode = path_segs[0]
        window_state = path_segs[1]
        tab_manager = self.tab_manager(session)
        del path_segs[0:2]
        if tab_manager.configuring == portlet \
            and mode != "edit":
            tab_manager.configure(None)
        if mode == "edit":
            tab_manager.configure(portlet)
        if window_state == "solo":
            tab_manager.add_solo(portlet)

    def _create_event_from_request \
            (self, session, evt_class, args, kwargs, channel):
        if not self._check_event(evt_class, channel):
            return None
        try:
            names = evt_class.split(".")
            clazz = reduce(getattr, names[1:], sys.modules[names[0]])
        except AttributeError:
            self.fire(log(logging.ERROR, 
                          "Unknown event class in event URL: " + evt_class))
            return None
        try:
            evnt = clazz(self.facade(session), *args, **kwargs)
        except Exception:
            self.fire(log(logging.ERROR, 
                          "Cannot create event: " + str(sys.exc_info()[1])))
            return None
        evnt.channels = (channel,)
        return evnt
                
    def _check_event(self, event_name, channel):
        if not self._accepted_events:
            self._accepted_events = dict()
            for portlet in self._portal._portlets:
                for clazz, chan in portlet.description().events:
                    name = clazz.__module__ + "." + clazz.__name__
                    if not self._accepted_events.has_key(name):
                        self._accepted_events[name] = set()
                    if self._accepted_events[name] == None:
                        continue
                    if chan == "*":
                        self._accepted_events[name] = None
                        continue
                    self._accepted_events[name].add(chan)
        chans = self._accepted_events.get(event_name, set())
        return chans == None or channel in chans
                
    
    # Attached as handler to portal channel in __init__
    def _on_portal_update(self, portlet, session, name, *args):
        if portlet is None:
            handle = "portal"
        else:
            handle = portlet.description().handle
        data = [ handle, name ]
        for arg in args:
            data.append(arg)
        msg = json.dumps(data)
        self.fire(write(self.client_connection(session), msg), \
                  self._event_exchange_channel)
                
    # Attached as handler to portal channel in __init__
    def _on_message_from_client(self, session, data):
        evt_data = json.loads(data)
        handle = evt_data[0]
        # be a bit suspicious
        if handle == "portal":
            handle = self.channel
            return
        args = evt_data[2]
        if not isinstance(args, list):
            args = [args]
        evt = self._create_event_from_request \
            (session, evt_data[1], args, evt_data[3], handle)
        self.fire(evt)

    @handler("render_portlet_success")
    def _render_portlet_success (self, e, *args, **kwargs):
        """
        Causes the RenderThread to continue executing after
        a render_portlet event has been completed. This handler
        cannot be defined in RenderThread as it is not a component.
        """
        e.sync.release()


class TabManager(object):

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

    @classmethod
    def get(cls, session):
        mgr = session.get(cls.__class__.__name__ + ".tabs")
        if mgr is None:
            mgr = TabManager(session)
            session[cls.__class__.__name__ + ".tabs"] = mgr
        return mgr

    def __init__(self, session, *args, **kwargs):
        self._session = session
        self._tabs = [self._TabInfo("_dashboard", selected=True)]
        self._configuring = None

    @property
    def tabs(self):
        return self._tabs

    def select_tab(self, tab_id):
        found = False
        for tab in self._tabs:
            tab._selected = (id(tab) == tab_id)
            found = found or tab._selected
        if not found:
            self._tabs[0]._selected = True

    def find_tab(self, tab_id):
        found = filter(lambda x: id(x) == tab_id, self._tabs)
        if len(found) > 0:
            return found[0]
        return None

    def close_tab(self, tab_id):
        closed = self.find_tab(tab_id)
        if closed is None:
            return
        closed_idx = self._tabs.index(closed)
        del self._tabs[closed_idx]
        if closed._selected:
            if len(self._tabs) > closed_idx:
                self._tabs[closed_idx]._selected = True
            else:
                self._tabs[0]._selected = True

    def add_solo(self, portlet):
        solo_tabs = filter(lambda x: x.portlet == portlet, self._tabs)
        if len(solo_tabs) > 0:
            self.select_tab(id(solo_tabs[0]))
            return
        tab = self._TabInfo("_solo", closeable=True, portlet=portlet)
        self._tabs.append(tab)
        self.select_tab(id(tab))

    def configure(self, portlet):
        self._configuring = portlet

    @property
    def configuring(self):
        return self._configuring

    
class UGFactory(Portlet.UrlGeneratorFactory):
    
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
    

class RenderThread(Thread):
    """
    Render the portal using the "top" template. The template needs
    the individual portlet's content at certain points. As we want
    that content to be provided as response to a :class:`render_portlet`
    event, we have to suspend the execution of the template until the
    response becomes available. If tenjin was made for circuits, it could
    yield until the results becomes available. As this is not the case,
    we execute the template in its own thread. Whenever portlet
    content is required, the :class:`render_portlet` event is fired
    and execution suspended by waiting on a semaphore. The render
    request is executed in the main thread and its completion signaled
    back to the template processor using the semaphore.
    """

    def __init__(self, view, req_evt, request, response):
        super(RenderThread, self).__init__()
        self.daemon = True
        self._view = view
        self._req_evt = req_evt
        self._request = request
        self._response = response
        self._locales = LanguagePreferences.preferred(request.session)
        self._translation = rbtranslations.translation\
            ("l10n", view._portal._templates_dir, 
             self._locales, "en")
        if self._translation.language:
            response.headers["Content-Language"] \
                = self._translation.language.replace("_", "-")
        self._portlet_counter = 0

    def run(self):
        
        def render(portlet, mime_type="text/html", 
                   mode=Portlet.RenderMode.View, 
                   window_state=Portlet.WindowState.Normal, 
                   locales=[], **kwargs):
            """
            The render portlet function made available to the template 
            engine. It fires the :class:`render_portlet` event and waits
            for the result to become available.
            """
            evt = render_portlet \
                (mime_type, mode, window_state, locales, 
                 self._view._ugFactory, self._portlet_counter, **kwargs)
            self._portlet_counter += 1
            evt.success_channels = [self._view.channel]
            evt.sync = Semaphore(0)
            self._view.fire(evt, portlet.channel)
            evt.sync.acquire()
            return evt.value.value 
        # Render the template.
        def portal_action_url(action, **kwargs):
            return (self._view.prefix
                    + "/portal/" + urllib.quote(action)
                    + (("?" + urllib.urlencode(kwargs)) if kwargs else ""))
        def portlet_state_url(portlet_handle, mode="_", window="_"):
            return (self._view.prefix
                    + "/" + portlet_handle + "/" + mode + "/" + window)
                    
        portal = PortalSessionFacade(self._view, self._request.session)
        self._req_evt.portal_response = serve_tenjin \
            (self._view._engine, self._request, self._response,
             "portal.pyhtml", {}, type="text/html", 
             globexts = { "portal": portal,
                          "preferred_locales": self._locales,
                          "_": self._translation.ugettext,
                          "portal_action_url": portal_action_url,
                          "portlet_state_url": portlet_state_url,
                          "resource_url": 
                          (lambda x: self._view.prefix + "/" + x),
                          "render": render})

