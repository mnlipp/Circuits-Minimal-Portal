/**
 * CirMinPor establishes a namespace for the JavaScript functions
 * that are provided by the portal.
 */
CirMinPor = {

/**
 * This function changes the protocol of an HTTP url to the corresponding
 * web socket url. 
 */
wsUrl: function(path) {
    var loc = window.location;
    var url = "ws:";
    if (loc.protocol == "https:") {
        url = "wss";
    }
    url += "//" + loc.host;
    if (path.indexOf("/") != 0) {
        url += "/";
    }
    url += path;
    return url;
}

};

/**
 * Creates a function in namespace CirMinPor.
 * 
 * addEventExchangeHandler(handle, name, func) adds an event exchange handler.
 * Handlers are invoked when an event
 * is received from the server. Parameter "handle" is the handle (id) of
 * a portlet, "portal" or "*" and used to filter the events delivered to the
 * handler. Parameter "name" may be used to restrict the events delivered
 * to events with a given name (use "*" to get all events). Parameter
 * "func" is the function that is to be invoked. Upon invocation, the
 * data associated with the event is passed as an array parameter to the
 * function. 
 */
(function() {
	var ws;
	var eventHandlers = [];

	/**
	 * An internal helper function invoked by the portal after the page
	 * has loaded that opens the websocket connection for exchanging
	 * events with the server.
	 */
	CirMinPor._openEventExchange = function (resourceUrl) {
	  if ("WebSocket" in window && JSON) {
	     // Let us open a web socket
	     ws = new WebSocket(CirMinPor.wsUrl(resourceUrl));
	     ws.onmessage = function (evt) {
	        data = JSON.parse(evt.data);
	        channel = data[0];
	        name = data[1];
	        if (channel == "portal") {
	        	if (name == "portal_message") {
	        		CirMinPor.addMessage(data[2], data[3])
	        	}
	        	return;
	        }
	        // alert(CirMinPor._eventHandlers);
	        for (idx in eventHandlers) {
	           handlerData = eventHandlers[idx];
	           if ((handlerData[0] == "*" || handlerData[0] == channel)
	               && (handlerData[1] == "*" || handlerData[1] == name)) {
	              handlerData[2](data.slice(2));
	           }
	        }
	     };
	  } else {
	     CirMinPor.addMessage(CirMinPor._strings.WebSocketsUnavailable, "error");
	  }
	};
	
	CirMinPor.addEventExchangeHandler = function (handle, name, func) {
	    eventHandlers.push([handle, name, func]);
	}
	
	CirMinPor.sendEvent = function(handle, name, args) {
		env = { locales: CirMinPor._locales }
		ws.send(JSON.stringify([handle, name, args, env]));
	}


})();

/**
 * Creates two functions in namespace CirMinPor.
 * 
 * addMessage(text, class) appends the given
 * message to the top message display in a div with the given class.
 * It returns an id that can be used to remove the message later.
 * 
 * removeMessage(id) removes the message with the
 * given id from the top message display.
 */
(function() {
  var counter = 0;

  CirMinPor.addMessage = function(text, cls) {
    var msgList = document.getElementById("topMessageList");
    var newItem = document.createElement("li");
    if (cls) {
        newItem.setAttribute("class", cls);
    }
    id = "topMessageEntry_" + counter++;
    newItem.setAttribute("id", id);
    newItem.innerHTML = CirMinPor.tmpl("topMessageEntry", 
      {message: text, id: id });
    msgList.appendChild(newItem);
    var msgDiv = document.getElementById("topMessageDisplay");
    msgDiv.style.display = "block";
    return id;
  };
  
  CirMinPor.removeMessage = function(id) {
    var msgItem = document.getElementById(id);
    if (msgItem) {
      var msgList = msgItem.parentNode;
      msgList.removeChild(msgItem);
      if (msgList.childNodes.length == 0) {
        var msgDiv = document.getElementById("topMessageDisplay");
        msgDiv.style.display = "none";
      }
    }
  };
})();

// Simple JavaScript Templating
// John Resig - http://ejohn.org/ - MIT Licensed
(function() {
  var cache = {};
  
  CirMinPor.tmpl = function tmpl(str, data) {
    // Figure out if we're getting a template, or if we need to
    // load the template - and be sure to cache the result.
    var fn = !/\W/.test(str) ?
      cache[str] = cache[str] ||
        tmpl(document.getElementById(str).innerHTML) :
      
      // Generate a reusable function that will serve as a template
      // generator (and which will be cached).
      new Function("obj",
        "var p=[],print=function(){p.push.apply(p,arguments);};" +
        
        // Introduce the data as local variables using with(){}
        "with(obj){p.push('" +
        
        // Convert the template into pure JavaScript
        str
          .replace(/[\r\t\n]/g, " ")
          .split("<%").join("\t")
          .replace(/((^|%>)[^\t]*)'/g, "$1\r")
          .replace(/\t=(.*?)%>/g, "',$1,'")
          .split("\t").join("');")
          .split("%>").join("p.push('")
          .split("\r").join("\\'")
      + "');}return p.join('');");
    
    // Provide some basic currying to the user
    return data ? fn( data ) : fn;
  };
})();
