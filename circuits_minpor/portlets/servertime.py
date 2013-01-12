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
from circuits_bricks.web.dispatchers.websockets import WebSockets
from circuits_bricks.core.timers import Timer
from circuits.core.events import Event
from circuits.core.handlers import handler
from circuits.net.sockets import Write
import datetime

class ServerTimePortlet(TemplatePortlet):

    def __init__(self, *args, **kwargs):
        super(ServerTimePortlet, self) \
            .__init__("templates", "servertime", *args, **kwargs)
        self._time_channel = self.channel + "-time"
        evt = Event.create("TimeOver")
        evt.channels = (self.channel,)
        Timer(1, evt, persist=True).register(self)

    def description(self, locales=[]):
        return Portlet.Description\
            (self._handle, self.translation(locales) \
                .ugettext("Server Time Portlet"),
             events=[])

    @handler("portlet_added")
    def _on_portlet_added(self, portal, portlet):
        ws_url = portal.url_generator(portlet).resource_url("timeSocket")
        WebSockets(ws_url, self._time_channel,
                   channel=portal.channel).register(self)

    @handler("time_over")
    def _on_time_over(self):
        td = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
        td = td.microseconds / 1000 + (td.seconds + td.days * 86400) * 1000
        td = int(td)
        self.fire(Write(None, str(td)), self._time_channel)