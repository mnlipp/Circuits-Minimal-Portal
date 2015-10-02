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
from circuits.core.events import Event

class portlet_added(Event):
    """
    Sent to a Portlet when it is added to a Portal.
    :param portal: the portal component
    :param portlet: the portlet comoponent
    """

class portlet_removed(Event):
    """
    Sent to a Portlet when it is removed from a Portal.
    :param portal: the portal component
    :param portlet: the portlet comoponent
    """

class portal_client_connect(Event):
    """
    This event signals that a client has connected to the event
    exchange. This is event can be used by portlets with dynamic content
    to immediately fire an event to update (actually initialize) the content.

    :param portal: the portal session facade
    """

class portal_client_disconnect(Event):
    """
    This event signals that a client has disconnected from the event
    exchange. 

    :param portal: the portal session facade
    :param sock: the web socket that has closed.
    """

class portal_update(Event):
    """
    An event that forwards information (as "event") to the client (browser).
    :param portlet: the portlet where the change occured or None if
        the change affects the complete portal.
    :param session: the session.
    :param name: a name that further classifies the information ("event name").
    :param *args: more information to be sent.
    
    Arbitrary additional arguments may be added provided that
    they can be serialized using json.dump.  
    """

class portal_message(Event):
    """
    This event can be used to add a message to the portal's top
    message display.
    
    :param session: the session.
    :param message: the message to display.
    :type message: string
    :param class: (optional) a CSS class to be used for the message display.
    :type class: string
    """

class portlet_resource(Event):
    """request(Event) -> request Event

    args: request, response
    """

    success = True
    failure = True
    complete = True

