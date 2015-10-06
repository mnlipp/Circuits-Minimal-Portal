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
from circuits.web.servers import BaseServer
import os
from circuits.core.handlers import handler
from copy import copy
from circuits_minpor.portlet import Portlet
from circuits_bricks.web.misc import LanguagePreferences, ThemeSelection
import rbtranslations
from circuits_minpor.portal.portalview import PortalView
from circuits_minpor.portal.events import portlet_added, portlet_removed
from os.path import dirname


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
    
    _path = None
    _title = None

    def __init__(self, server=None, path="/", 
                 title=None, templates_dir=None, **kwargs):
        """
        :param server: the component that handles the basic connection
                       and protocol management. If not provided, the
                       Portal creates its own  
                       :class:`~circuits.web.server.BaseServer` component
                       that listens on port 4444.
        :type server: :class:`circuits.web.server.BaseServer`
        
        :param path: a path for URLs used by the portal. This allows
                     the portal to co-exist with other content on the same
                     web server. If specified, only requests starting with the
                     given path are handled by the portal dispatcher and 
                     the path is prepended to all generated URLs.
                     The value must start with a slash and must not 
                     end with a slash.
        :type path: string
        
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
        self._path = path or ""
        self._title = title
        self._portlets = []
        if server is None:
            server = BaseServer(("", 4444), channel=self.channel)
        else:
            self.channel = server.channel
        self.server = server
        if templates_dir:
            self._templates_dir = [os.path.abspath(templates_dir)]
        else:
            self._templates_dir = []
        self._templates_dir \
            += [os.path.join(dirname(dirname(__file__)), "templates")]
        LanguagePreferences(channel = server.channel).register(server)
        ThemeSelection(channel = server.channel).register(server)
        view = PortalView(self, channel = server.channel).register(server)
        self._url_generator_factory = view.url_generator_factory
        self._supported_locales = []
        for locale in rbtranslations.available_translations\
            ("l10n", self._templates_dir, "en"):
            trans = rbtranslations.translation\
                ("l10n", self._templates_dir, [locale], "en")
            locale_name = trans.ugettext("language_" + locale)
            self._supported_locales.append((locale, locale_name))
        self._supported_locales.sort(key=lambda x: x[1])
            
    @handler("registered", channel="*")
    def _on_registered(self, c, m):
        if not isinstance(c, Portlet):
            return
        if not c in self._portlets:
            self._portlets.append(c)
            self.fire(portlet_added(self, c), c)
            for idx, p in enumerate(self._portlets):
                if c.weight < p.weight:
                    self._portlets.insert(idx, c)
                    del self._portlets[len(self._portlets) - 1]
                    break;

    @handler("unregistered")
    def _on_unregistered(self, c, m):
        if not isinstance(c, Portlet):
            return
        if c in self._portlets:
            self._portlets.remove(c)
            self.fire(portlet_removed(self, c), c)

    @property
    def path(self):
        return self._path

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

    def url_generator(self, portlet):
        return self._url_generator_factory.make_generator(portlet)

