#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2005 Shuttleworth Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
SchoolTool skin.

$Id$
"""

from zope.interface import Interface
from zope.interface import implements
from zope.schema import Object
from zope.publisher.interfaces.browser import ILayer, IDefaultBrowserLayer
from zope.publisher.interfaces.browser import IBrowserRequest
from zope.viewlet.interfaces import IViewletManager
from zope.viewlet.manager import ViewletManagerBase
from zope.app import zapi

from schooltool.app.app import getSchoolToolApplication

class IJavaScriptManager(IViewletManager):
    """Provides a viewlet hook for the javascript link entries."""

class ICSSManager(IViewletManager):
    """Provides a viewlet hook for the CSS link entries."""

class IHeaderManager(IViewletManager):
    """Provides a viewlet hook for the header of a page."""

class INavigationManager(IViewletManager):
    """Provides a viewlet hook for the navigation section of a page."""

class OrderedViewletManager(ViewletManagerBase):
    """Viewlet manager that orders viewlets by their 'order' attribute.

    The order attribute can be a string, but it will be sorted numerically
    (i.e. '1' before '5' before '20').  The attribute is optional; viewlets
    without an ``order`` attribute will be sorted alphabetically by their
    ``title`` attribute, and placed below all the ordered viewlets.
    """

    def sort(self, viewlets):
        """Sort the viewlets.

        ``viewlets`` is a list of tuples of the form (name, viewlet).
        """

        def key_func((name, viewlet)):
            if hasattr(viewlet, 'order'):
                return (0, int(viewlet.order))
            elif hasattr(viewlet, 'title'):
                return (1, viewlet.title)
            else:
                raise AttributeError('%r viewlet has neither order nor title'
                                     % name)

        return sorted(viewlets, key=key_func)

class NavigationViewlet(object):
    """A navigation viewlet base class."""

    def appURL(self):
        return zapi.absoluteURL(getSchoolToolApplication(), self.request)


class ISchoolToolLayer(ILayer, IBrowserRequest):
    """SchoolTool layer."""


class ISchoolToolSkin(ISchoolToolLayer, IDefaultBrowserLayer):
    """The SchoolTool skin"""
