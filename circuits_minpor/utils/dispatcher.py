'''
Created on 01.10.2015

@author: mnl
'''
from circuits.web.websockets.dispatcher import WebSocketsDispatcher
from circuits.core.handlers import handler
from circuits.net.events import connect, disconnect

class WebSocketsDispatcherPlus(WebSocketsDispatcher):
    '''
    classdocs
    '''

    def __init__(self, path=None, wschannel="wsserver", *args, **kwargs):
        """
        :param path: the path to handle. Requests that start with this
            path are considered to be WebSocket Opening Handshakes.

        :param wschannel: the channel on which :class:`~.sockets.read`
            events from the client will be delivered and where
            :class:`~.net.events.write` events to the client will be
            sent to.
        """

        super(WebSocketsDispatcherPlus, self).__init__ \
            (path, wschannel, *args, **kwargs)
        self._sessions = dict()
        @handler("read", channel=wschannel, priority=100)
        def _on_read_handler(self, event, socket, data):
            if socket in self._sessions:
                event.kwargs["session"] = self._sessions[socket]
        self.addHandler(_on_read_handler)

    @handler("response_complete", override=True)
    def _on_response_complete(self, e, value):
        response = e.args[0]
        request = response.request
        if request.sock in self._codecs:
            self._sessions[request.sock] = request.session
        if request.sock in self._codecs:
            evt = connect(request.sock,*request.sock.getpeername())
            evt.kwargs["session"] = request.session 
            self.fire(evt, self._wschannel)
        
    @handler("disconnect", override=True)
    def _on_disconnect(self, sock):
        if sock in self._codecs:
            evt = disconnect(sock)
            if sock in self._sessions:
                evt.kwargs["session"] = self._sessions[sock] 
                del self._sessions[sock]
            self.fire(evt, self._wschannel)
            del self._codecs[sock]
