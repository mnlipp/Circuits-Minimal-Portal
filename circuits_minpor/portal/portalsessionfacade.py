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
from circuits_minpor.portal.events import portal_update, portal_message
from circuits_bricks.web.misc import ThemeSelection

class PortalSessionFacade(object):
    """
    This class provides access to the portal (and portal view)
    for portlets. It's main purpose is to add the session information
    to calls that are eventually processed by the portlet (view).
    
    An instance is passed to all portlet event handlers that
    are session related. 
    """
        
    def __init__(self, portal_view, session):
        self._session = session
        self._portal_view = portal_view
        self._portal = portal_view.portal
        self._theme = ThemeSelection.selected(session)
        self._tabs = portal_view.tab_manager(session).tabs

    @property
    def title(self):
        return self._portal.title
    
    @property
    def configuring(self):
        return self._portal_view.tab_manager(self._session).configuring

    @property
    def supported_locales(self):
        return self._portal.supported_locales

    @property
    def theme(self):
        return self._theme

    @property
    def tabs(self):
        return self._tabs

    @property
    def portlets(self):
        return self._portal.portlets

    @property
    def session(self):
        return self._session
    
    def update(self, portlet, *args, **kwargs):
        portlet.fire(portal_update(portlet, self._session, *args, **kwargs), \
                     self._portal.channel)

    def message(self, portlet, *args, **kwargs):
        portlet.fire(portal_message(self._session, *args, \
                                 **kwargs), self._portal.channel)
        