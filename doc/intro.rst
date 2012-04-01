..
   This file is part of the Circuits Minimal Portal package.
   Copyright (C) 2012 Michael N. Lipp


What this component is good for
===============================

.. toctree::
   :maxdepth: 1

When building a server application, you often find that you would like
to provide a user interface for simple management tasks like having
a look at a log, change some configuration parameter or inspect the 
current state of your server.

While the idea sounds simple and attractive, you often find that 
it is hard to implement. You have to provide a basic user interface
layout and somehow make the information available to the user
interface component. More often than not, this requires internal
APIs in your server that you didn't really need for its core
functions and that tend to spoil the overall architecture.

An approach to solving this problem is a web portal, "a web site
that brings together information from diverse sources in a
unified way" [Wikipedia]. In its simplest form, such a portal
aggregates so called portlets, pluggable components that can be 
developed independently.

From a developer's perspective, the Circuits Minimal Portal provides
two (main) components. The :class:`circuits_minpor.Portal` is a
component that tracks components of type 
:class:`circuits_minpor.Portlet` as they register with the component
hierarchy. In addition, it adds a dispatcher to an already existing
HTTP server component (or creates its own HTTP server component)
that handles all requests (optionally only those with a given prefix).

Requests directed at the portal dispatcher produce a page that
shows all portlets in a summary view. The portlets contribute
their summary presentation to this view individually. Portlets
can also provide a detail view that is shown by the portal on
request. When rendering their presentation, the portlets can 
generate links that cause a circuits :class:`Event` to be fired.

Portlets can be designed as views of other components in the system.
Every component that wants to present its state in the user 
interface or wants the user to be able to interact with the system
creates an appropriate portlet and adds it to the component hierarchy.
Due to the close coupling of the model component and its view,
such a portlet can also present information that is not available
using the official API of the model component. The combined development
of model and view makes sure that model and view continue to match 
when the component changes its internal implementation.

Thanks to circuits architecture, portlets can also be provided 
as an add-on to model components. In this case some factory
component must be registered that listens for register events of 
the model components and automatically add portlets as views whenever 
a model component is registered. In this case the portlet should, 
of course, restrict its access to the model component to the 
"official" interface.
  