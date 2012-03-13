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
from abc import ABCMeta
import uuid
from circuits.web.errors import NotFound
from circuits.core.events import Event
from circuits.core.handlers import handler
import os
import rbtranslations
import tenjin
from nevow.url import URLGenerator

class RenderPortlet(Event):
    
    success = True
    
    def __init__(self, mode, window_state, locales, 
                 url_generator_factory, **kwargs):
        """
        Renders a portlet.
        
        :param mode: the render mode
        :type mode: :class:`RenderMode`
        
        :param window_state: the window state
        :type window_state: :class:`WindowState`
        
        :param locales: the preferred locales
        :type locales: list of strings
        
        :param url_generator_factory: factory for URL generator
        :type urlGenerator: :class:`UrlGeneratorFactory`
        """
        super(RenderPortlet, self).__init__\
            (mode, window_state, locales, url_generator_factory, **kwargs)


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
        
        def action_url(self, event):
            return "#"

        def resource_url(self, resource):
            return "#"

    class UrlGeneratorFactory(object):
        
        def make_generator(self, portlet):
            return URLGenerator()

    def __init__(self, *args, **kwargs):
        self._handle = str(uuid.uuid4())
        if not kwargs.has_key("channel"):
            kwargs["channel"] = self._handle
        super(Portlet, self).__init__(*args, **kwargs)

    def description(self, locales=[]):
        return Portlet.Description(self._handle, "Base Portlet")
    
    @handler("render_portlet")
    def _render_portlet(self, mode=RenderMode.View, 
                        window_state=WindowState.Normal, 
                        locales=[], url_generator_factory=None, **kwargs):
        if url_generator_factory:
            url_generator = url_generator_factory.make_generator(self)
        else:
            url_generator = Portlet.UrlGenerator()
        return self._do_render(mode, window_state, 
                               locales, url_generator, **kwargs)

    def _do_render(self, mode, window_state, locales, 
                   url_generator, **kwargs):
        return "<div class=\"portlet-msg-error\">" \
                + "Portlet not implemented yet</div>"

    @handler("portlet_resource")
    def portlet_resource(self, request, response, **kwargs):
        return self._do_portlet_resource(request, response, **kwargs)

    def _do_portlet_resource(self, request, response, **kwargs):
        return NotFound(request, response)


class TemplatePortlet(Portlet):

    _engines = dict()
    _translations = dict()

    def __init__(self, template_dir, name, *args, **kwargs):
        super(TemplatePortlet, self).__init__(*args, **kwargs)
        self._template_dir = os.path.abspath(template_dir)
        self._name = name

    def _do_render(self, mode, window_state, locales, url_generator, 
                   context_exts = {}, globs_exts = {}, **kwargs):
        theme = kwargs.get("theme", "default")
        theme_path = os.path.join(self._template_dir, "themes", theme)
        if not os.path.exists(theme_path):
            theme_path = os.path.join(self._template_dir, "themes", "default")
        # Find/Create engine
        engine = self._engines.get(theme, None)
        if not engine:
            engine = tenjin.Engine\
                (path=[theme_path, self._template_dir])
            self._engines[theme] = engine
        # Find/Create translations for globals
        lang_hash = ";".join(locales)
        translation = self._translations.get((theme, lang_hash), None)
        if not translation:
            translation = rbtranslations.translation\
                (self._name + "-l10n", theme_path, locales)
            translation.add_fallback(rbtranslations.translation\
                (self._name + "-l10n", self._template_dir, locales))
            self._translations[(theme, lang_hash)] = translation
        # Prepare context
        context = { "mode": mode, "window_state": window_state,
                    "theme": theme, "locales": locales }
        context.update(context_exts)
        # Prepare globals
        globs = tenjin.helpers.__dict__
        globs.update({ "_": translation.ugettext,
                       "action_url": url_generator.action_url,
                       "resource_url": url_generator.resource_url })
        return engine.render(self._name + ".pyhtml",  
                             context = context, globals = globs)

    def _do_portlet_resource(self, request, response, **kwargs):
        theme = kwargs.get("theme", "default")
        res_path = os.path.join\
            (self._template_dir, "themes", theme, request.path)
        if os.path.exists(res_path):
            return tools.serve_file(request, response, res_path)
        res_path = os.path.join (self._template_dir, request.path)
        if os.path.exists(res_path):
            return tools.serve_file(request, response, res_path)
        return NotFound(request, response)

