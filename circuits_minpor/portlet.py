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
from circuits.core.components import BaseComponent
from abc import ABCMeta
import uuid
from circuits.web.errors import NotFound
from circuits.core.events import Event
from circuits.core.handlers import handler

class RenderPortlet(Event):
    
    success = True
    
    def __init__(self, *args, **kwargs):
        """
        Renders a portlet.
        
        :param mode: the render mode
        :type mode: :class:`RenderMode`
        
        :param window_state: the window state
        :type window_state: :class:`WindowState`
        
        :param locales: the preferred locales
        :type locales: list of strings
        
        :param urlGenerator: generator used by portlet to generate URLs
        :type urlGenerator: :class:`UrlGenerator`
        """
        super(RenderPortlet, self).__init__(args, **kwargs)

class Portlet(BaseComponent):
    
    __metaclass__ = ABCMeta
    
    class RenderMode(object):
        View = 1
        Edit = 2
        Help = 3
        Preview = 4
        
    class WindowState(object):
        Normal = 1
        Minimized = 2
        Maximized = 3
        Solo = 4

    class MarkupType(object):

        def __init__(self, modes = None, states = None):
            self._modes = modes or [Portlet.RenderMode.View]
            self._states = states or [Portlet.WindowState.Normal]
        
        @property
        def render_modes(self):
            return self._modes
        
        @property
        def window_states(self):
            return self.states

    class Description(object):
        def __init__(self, handle, short_title, title = None,  
                     markup_types=None, locale = "en-US"):
            self._handle = handle
            self._short_title = short_title
            self._title = title or short_title
            self._markup_types = markup_types \
                or dict({ "text/html": Portlet.MarkupType()})
            self._locale = locale

        @property
        def short_title(self):
            return self._short_title
        
        @property
        def title(self):
            return self._title

        @property
        def handle(self):
            return self._handle
        
        @property
        def markup_types(self):
            return self._markup_types

        @property
        def locale(self):
            return self._locale

    class UrlGenerator(object):
        
        def actionUrl(self, event):
            return "#"

        def resourceUrl(self, resource):
            return "#"

    def __init__(self, *args, **kwargs):
        self._handle = uuid.uuid4()
        if not kwargs.has_key("channel"):
            kwargs["channel"] = self._handle
        super(Portlet, self).__init__(*args, **kwargs)

    def description(self, locales=[]):
        return Portlet.Description(self._handle, "Base Portlet")
    
    @handler("render_portlet")
    def _render_portlet(self, mode=RenderMode.View,
                        window_state=WindowState.Normal, locales=[],
                        urlGenerator=UrlGenerator()):
        return self._do_render(mode, window_state, locales, urlGenerator)

    def _do_render(self, mode, window_state, locales, urlGenerator):
        return "<div class=\"portlet-msg-error\">" \
                + "Portlet not implemented yet</div>"

    @handler("render_portlet_success", filter=True)
    def _render_portlet_success (self, event, e, *args, **kwargs):
        channel = getattr(e, "redirect_success", False)
        if channel:
            return self.fireEvent(event, channel)

    def resource(self, request, response, resource):
        return NotFound(request, response)
