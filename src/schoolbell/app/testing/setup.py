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
SchoolBell Testing Support

$Id: app.py 4705 2005-08-15 14:49:07Z srichter $
"""
__docformat__ = 'restructuredtext'

from schoolbell.app.security import setUpLocalAuth
from schoolbell.app.testing import registry

# ----------------------------- Session setup ------------------------------
from zope.publisher.interfaces import IRequest
from zope.app.session.http import CookieClientIdManager
from zope.app.session.interfaces import ISessionDataContainer
from zope.app.session.interfaces import IClientId
from zope.app.session.interfaces import IClientIdManager, ISession
from zope.app.session.session import ClientId, Session
from zope.app.session.session import PersistentSessionDataContainer
from zope.app.testing import ztapi
def setupSessions():
    """Set up the session machinery.

    Do this after placelessSetUp().
    """
    ztapi.provideAdapter(IRequest, IClientId, ClientId)
    ztapi.provideAdapter(IRequest, ISession, Session)
    ztapi.provideUtility(IClientIdManager, CookieClientIdManager())
    sdc = PersistentSessionDataContainer()
    ztapi.provideUtility(ISessionDataContainer, sdc)


# --------------------- Create a SchoolBell application --------------------
from schoolbell.app.app import SchoolBellApplication
def createSchoolBellApplication():
    """Create a ``SchoolBellApplication`` instance with all its high-level
    containers."""
    app = SchoolBellApplication()
    registry.setupApplicationContainers(app)
    return app


# ----------------- Setup SchoolBell application as a site -----------------
from zope.interface import directlyProvides
from zope.app.component.hooks import setSite
from zope.app.component.site import LocalSiteManager
from zope.app.traversing.interfaces import IContainmentRoot
def setupSchoolBellSite():
    """This should only be called after ``placefulSetUp()``."""
    app = createSchoolBellApplication()
    directlyProvides(app, IContainmentRoot)
    app.setSiteManager(LocalSiteManager(app))
    setUpLocalAuth(app)
    setSite(app)
    return app
