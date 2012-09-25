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
from circuits.core.events import Event
from circuits.core.handlers import handler

class ToggleWorld(Event):
    pass

class HelloWorldPortlet(TemplatePortlet):

    def __init__(self, *args, **kwargs):
        super(HelloWorldPortlet, self) \
            .__init__("templates", "helloworld", *args, **kwargs)
        self._show_world = True

    def description(self, locales=[]):
        return Portlet.Description\
            (self._handle, self.translation(locales) \
                .ugettext("Hello World Portlet"),
             events=[(ToggleWorld, self.channel)])

    @handler("toggle_world")
    def _on_toggle(self, *args, **kwargs):
        self._show_world = not self._show_world
        