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
from abc import ABCMeta, abstractmethod
import uuid
from circuits.web.errors import NotFound
from circuits.core.events import Event
from circuits.core.handlers import handler
import os
import rbtranslations
import tenjin
import inspect

class RenderPortlet(Event):
    """
    The event sent to portlets when the portal needs their content.
    """
    
    success = True
    
    def __init__(self, mime_type, mode, window_state, locales, 
                 url_generator_factory, **kwargs):
        """
        Renders a portlet.
        
        :param mime_type: the mime type to produce (e.g. "text/html")
        :type mime_type: string
        
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
            (mime_type, mode, window_state, locales, 
             url_generator_factory, **kwargs)


class Portlet(BaseComponent):
    """
    A portlet is a component that contributes to the portal's content.
    Content is provided as the result of handling a
    :class:`~.RenderPortlet` event. Implementations usually override the
    :meth:`.do_render` method instead of providing the handler themselves.
    
    The interface of the portlet component has been designed with the
    WSRP specification in mind. Therefore it may appear a bit
    more complicated than necessary for the task at hand, but it should
    support future enhancements without fundamental changes.
    """
    
    __metaclass__ = ABCMeta
    
    class RenderMode(object):
        """
        The render modes that may be supported by the portlet.
        """        
        View = "view"
        """
        Normal content display.
        """
        Edit = "edit"
        """
        Special representation that allows the portlet to be customized.
        """
        Help = "help"
        """
        Display help information.
        """
        Preview = "preview"
        """
        Produce content that can be used to e.g. test a portal layout.
        """
        
    class WindowState(object):
        """
        Provides a hint about the available space to the render method
        of the portlet. 
        """
        Normal = "normal"
        """
        Portlet shares space with other portlets, e.g. in a two or three
        column layout.
        """
        Minimized = "minimized"
        """
        Use as little space as possible.
        """
        Maximized = "maximized"
        """
        The portlet is still part of an aggregated page but has significantly
        more space available than the other portlets on that page.
        """
        Solo = "solo"
        """
        Only this portlet provides content on the page shown to the user. 
        """

    class MarkupType(object):
        """
        Instances of this class are used to inform the portal about
        the capabilities of the portlet for a specific mime type.
        They are part of the portlets :class:`~.Description`.
        """

        def __init__(self, modes = None, states = None):
            """
            :param modes: the supported modes. Defaults to 
                ``[Portlet.RenderMode.View]``
            :type modes: list of :class:`~.RenderMode` values
            :param states: the supported windows states. Defaults to
                ``[Portlet.WindowState.Normal]``
            :type states: list of :class:`~.WindowState` values
            """
            self._modes = modes or [Portlet.RenderMode.View]
            self._states = states or [Portlet.WindowState.Normal]
        
        @property
        def render_modes(self):
            return self._modes
        
        @property
        def window_states(self):
            return self.states

    class Description(object):
        """
        Instances of this class are used by portlets to inform the
        portal about their capabilities. See :meth:`~.description`.
        """
        def __init__(self, handle, short_title, title = None,  
                     markup_types=None, locale = "en-US", events = []):
            """
            :param handle: a unique id for the portlet.
            :type handle: string
            :param short_title: a short title for the portlet.
            :type short_title: string
            :param title: a (long) title for the portlet.
            :type title: string
            :param markup_types: a dictionary of mappings from
                a mime type (such as "text/html") to an instance of
                :class:`~.MarkupType`. Defaults to
                ``dict({"text/html": Portlet.MarkupType()}``
            :type markup_types: dict
            """
            self._handle = handle
            self._short_title = short_title
            self._title = title or short_title
            self._markup_types = markup_types \
                or dict({"text/html": Portlet.MarkupType()})
            self._locale = locale
            self._events = events

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
        
        @property
        def events(self):
            return self._events

    class UrlGenerator(object):
        """
        This class defines the interface of an URL generator.
        An URL generator is used by the portlet to create the URLs
        for its rendered HTML. URL generators are provided by the
        portal via a :class:`~.URLGeneratorFactory`.
        """

        __metaclass__ = ABCMeta
        
        @abstractmethod
        def event_url(self, event_name, **kwargs):
            """
            Generate a URL that fires an event when clicked.
            :param event_name: the fully qualified name of the
            event class.
            :type event_name: string
            :param channel: the channel on which to fire the
            event. Implementations of this class must use the portlet's
            channel as default value.
            :type channel: string
            
            All remaining keyword arguments are appended as
            query parameters to the URL. 
            """
            return "#"

        @abstractmethod
        def resource_url(self, resource):
            """
            Return a URL that generates a :class:`PortletResource`
            event (a specialized circuits web
            :class:`~circuits.web.events.Request`) for the given
            *resource*. The handler interface is the same as for the
            circuits web request, a method that is invoked with
            ``request`` and ``response`` as parameters and returns the 
            result in one of the formats supported by circuits.
            Resource URLs should be used by portlets to embed images or other
            static content in the generated HTML.
            
            :param resource: the resource name.
            :type resource: string
            """
            return "#"

    class UrlGeneratorFactory(object):
        """
        The URL generator factory is passed to a portlet as
        attribute of the :class:`~.RenderPortlet` event.
        """

        __metaclass__ = ABCMeta

        @abstractmethod        
        def make_generator(self, portlet):
            """
            Invoked by the portlet to obtain its (portlet
            specific) URL generator from the portal.
            """
            return Portlet.URLGenerator()

    def __init__(self, key_language="en", *args, **kwargs):
        """
        :keyword key_language: the value of the key_language parameter used
            in :meth:`.translation`.
        :type key_language: string
        """
        self._handle = str(uuid.uuid4())
        if not kwargs.has_key("channel"):
            kwargs["channel"] = self._handle
        super(Portlet, self).__init__(*args, **kwargs)
        class_file = inspect.getfile(self.__class__)
        self._translation_basename \
            = os.path.basename(class_file).rsplit(".", 1)[0] + "-l10n"
        self._translation_props_dir = os.path.dirname(class_file)
        self._key_language = key_language

    def translation(self, locales=[]):
        """
        Returns an instance of :class:`rbtranslations.Translation` that
        looks for properties files named like the portlet's base source
        filename with "-l10n" appended in the same directory as the portlet's
        source file.
        """
        return rbtranslations.translation\
            (self._translation_basename, self._translation_props_dir,
             locales, key_language=self._key_language)

    def description(self, locales=[]):
        """
        Provides an instance of :class:`~.Description` that informs
        the portal about the capabilities of the portlet. All
        strings in the description should be localized using
        the given locales. The list specifies the accepted
        locales ordered by the user's preference.
        """
        return Portlet.Description(self._handle, "Base Portlet")
    
    @handler("render_portlet")
    def _render_portlet(self, mime_type="text/html", 
                        mode=RenderMode.View, 
                        window_state=WindowState.Normal, 
                        locales=[], url_generator_factory=None, **kwargs):
        url_generator = url_generator_factory.make_generator(self)
        return self.do_render(mime_type, mode, window_state, 
                               locales, url_generator, **kwargs)

    def do_render(self, mime_type, mode, window_state, locales, 
                   url_generator, **kwargs):
        """
        Return the markup for the portlet using the language 
        matching the specified *mime_type* and 
        taking into account the specified *mode*
        and *window_state*. All strings should be localized using
        the given *locales*.

        :param mime_type: the mime_type to generate (e.g. "text/html").
        :type mime_type: string
        :param mode: the mode to use when rendering the content.
        :type mode: :class:`~.RenderMode`
        :param window_state: the window state to use when rendering the content.
        :type window_state: :class:`~.WindowState`
        :param locales: the locales to use for localizing strings.
        :type locales: list of string
        :param url_generator: the URL generator to use for generating URLs.
        :type url_generator: :class:`~.URLGenerator`
        """
        return "<div class=\"portlet-msg-error\">" \
                + "Portlet not implemented yet</div>"

    @handler("portlet_resource")
    def _on_portlet_resource(self, request, response, **kwargs):
        return self.do_portlet_resource(request, response, **kwargs)
    
    def do_portlet_resource(self, request, response, **kwargs):
        """
        This is the method invoked by the handler for 
        :class:`PortletResource` events. It is provided as a
        convenience as it is a bit easier to override than the
        handler.
        """
        return NotFound(request, response)


class TemplatePortlet(Portlet):

    def __init__(self, template_dir, name, *args, **kwargs):
        super(TemplatePortlet, self).__init__(*args, **kwargs)
        if os.path.isabs(template_dir):
            self._template_dir = template_dir
        else:
            class_dir = os.path.dirname(inspect.getfile(self.__class__))
            self._template_dir \
                = os.path.abspath(os.path.join(class_dir, template_dir))
        self._name = name
        self._engine = tenjin.Engine(path=[self._template_dir])
        self._key_language = kwargs.get("key_language", "en")

    def translation(self, locales=[]):
        return rbtranslations.translation\
            (self._name + "-l10n", self._template_dir, locales,
             key_language=self._key_language)

    def do_render(self, mime_type, mode, window_state, locales, url_generator, 
                  context_exts = {}, globs_exts = {}, **kwargs):
        theme = kwargs.get("theme", "default")
        theme_path = os.path.join(self._template_dir, "themes", theme)
        if not os.path.exists(theme_path):
            theme_path = None
        # Find/Create translations for globals
        translation = self.translation(locales)
        # Prepare context
        context = { "portlet": self,
                    "mode": mode, "window_state": window_state,
                    "theme": theme, "locales": locales }
        context.update(context_exts)
        # Prepare globals
        globs = tenjin.helpers.__dict__
        globs.update({ "_": translation.ugettext,
                       "event_url": url_generator.event_url,
                       "resource_url": url_generator.resource_url })
        return self._engine.render(self._name + ".pyhtml",  
                                   context = context, globals = globs)

    def do_portlet_resource(self, request, response, **kwargs):
        theme = kwargs.get("theme", "default")
        res_path = os.path.join\
            (self._template_dir, "themes", theme, request.path)
        if os.path.exists(res_path):
            return tools.serve_file(request, response, res_path)
        res_path = os.path.join (self._template_dir, request.path)
        if os.path.exists(res_path):
            return tools.serve_file(request, response, res_path)
        return NotFound(request, response)

