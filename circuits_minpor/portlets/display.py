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
from circuits_minpor.portlet import Portlet
from circuits.core.events import Event
from circuits.core.handlers import handler
from circuits_bricks.app.config import ConfigValue

class SetText(Event):
    pass

class DisplayPortlet(Portlet):

    _short_text = ""
    _long_text = None

    def description(self, locales=[]):
        return Portlet.Description\
            (self._handle, 
             self.translation(locales).ugettext("Display Portlet"),
             markup_types=dict({ "text/html": Portlet.MarkupType\
                (modes=[Portlet.RenderMode.View, Portlet.RenderMode.Edit])}),
             events=[(SetText, self.channel)])

    def do_render(self, markup, mode, window_state, locales, 
                   url_generator, **kwargs):
        if mode == Portlet.RenderMode.Edit:
            return "<form action=\"%s\" method=\"post\">" \
                % url_generator.event_url \
                ("circuits_minpor.portlets.display.SetText", 
                 channel=self.channel, \
                 portlet_window_state=Portlet.WindowState.Normal) \
                + "Short text<br/>" \
                + "<textarea name=\"short_text\" cols=\"30\" rows=\"3\">" \
                + self._short_text \
                + "</textarea><br/>" \
                + "Long text<br/>" \
                + "<textarea name=\"long_text\" cols=\"80\" rows=\"20\">" \
                + (self._long_text if self._long_text != None 
                   else self._short_text) \
                + "</textarea><br/>" \
                + "<input type=\"submit\">" \
                + "</form>"
        if window_state == Portlet.WindowState.Solo \
            and self._long_text != None:
            return "<div>" + self._long_text + "</div>"
        else:
            return "<div>" + self._short_text + "</div>"

    @handler("set_text")
    def _on_set_text(self, short_text, long_text):
        self.fire(ConfigValue(self.channel, "short_text", short_text))
        self.fire(ConfigValue(self.channel, "long_text", long_text))

    @handler("config_value", channel="*")
    def _on_config_value(self, section, option, value):
        if section != self.channel:
            return
        if option == "short_text":
            self._short_text = value
        if option == "long_text":
            self._long_text = value
        pass
