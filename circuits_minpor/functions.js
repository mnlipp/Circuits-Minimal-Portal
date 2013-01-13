CirMinPor = {

_eventHandlers: [],

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
},

_openEventExchange: function (resourceUrl) {
  if ("WebSocket" in window && JSON) {
     // Let us open a web socket
     var ws = new WebSocket(CirMinPor.wsUrl(resourceUrl));
     ws.onmessage = function (evt) {
        data = JSON.parse(evt.data);
        channel = data[0];
        name = data[1];
        // alert(CirMinPor._eventHandlers);
        for (idx in CirMinPor._eventHandlers) {
           handlerData = CirMinPor._eventHandlers[idx];
           if ((handlerData[0] == "*" || handlerData[0] == channel)
               && (handlerData[1] == "*" || handlerData[1] == name)) {
              handlerData[2](data.slice(2));
           }
        }
     };
  } else {
     CirMinPor.addMessage(CirMinPor._strings.WebSocketsUnavailable, "error");
  }
},

addEventExchangeHandler: function (handle, name, func) {
    CirMinPor._eventHandlers.push([handle, name, func]);
}

};

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
  }
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
