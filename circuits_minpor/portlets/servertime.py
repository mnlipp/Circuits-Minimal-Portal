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
from circuits_minpor.portlet import TemplatePortlet, Portlet
from circuits_bricks.core.timers import Timer
from circuits.core.events import Event
from circuits.core.handlers import handler
import datetime
from circuits_minpor.portal import PortalUpdate, PortalMessage
from circuits_bricks.web.filters import LanguagePreferences

class OnOffChanged(Event):
    pass

class ServerTimePortlet(TemplatePortlet):

    def __init__(self, *args, **kwargs):
        super(ServerTimePortlet, self) \
            .__init__("templates", "servertime", *args, **kwargs)
        self._portal_channel = None
        self._time_channel = self.channel + "-time"
        self._timer = None

    def description(self, locales=[]):
        return Portlet.Description\
            (self._handle, self.translation(locales) \
                .ugettext("Server Time Portlet"),
             events=[(OnOffChanged, self.channel)])

    @handler("portlet_added")
    def _on_portlet_added(self, portal, portlet):
        self._portal_channel = portal.channel
        @handler("portal_client_connect", channel=portal.channel)
        def _on_client_connect(*args):
            self._update_time()
        self.addHandler(_on_client_connect)

    def _update_time(self):
        if self._portal_channel is None:
            return
        td = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
        td = td.microseconds / 1000 + (td.seconds + td.days * 86400) * 1000
        td = int(td)
        self.fire(PortalUpdate(self, "new_time", str(td)), self._portal_channel)

    @property
    def updating(self):
        return getattr(self, "_timer", None) is not None

    @handler("on_off_changed")
    def _on_off_changed(self, value, **kwargs):
        if value and self._timer is None:
            evt = Event.create("TimeOver")
            evt.channels = (self.channel,)
            self._timer = Timer(1, evt, persist=True).register(self)
            locales = kwargs.get("locales", [])
            self.fire(PortalMessage(self.translation(locales) \
                                    .ugettext("TimeUpdateOn")),
                      self._portal_channel)
        if not value and self._timer is not None:
            self._timer.unregister()
            self._timer = None
    
    @handler("time_over")
    def _on_time_over(self):
        self._update_time()
