#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2006 Shuttleworth Foundation
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
SchoolTool metaconfiguration code.

$Id$

"""

from zope.configuration.exceptions import ConfigurationError
from zope.app import zapi
from zope.interface import implements
from zope.component import provideAdapter
from zope.interface import implements
from zope.component import provideSubscriptionAdapter
from schooltool.securitypolicy.crowds import Crowd
from schooltool.securitypolicy.interfaces import ICrowd
from schooltool.securitypolicy.interfaces import ICrowdsUtility
from schooltool.securitypolicy.interfaces import IAccessControlSetting
from schooltool.securitypolicy.interfaces import IAccessControlCustomisations
from schooltool.app.interfaces import ISchoolToolApplication


class CrowdsUtility(object):
    implements(ICrowdsUtility)

    def __init__(self):
        self.crowdmap = {}   # crowd_name -> crowd_factory
        self.objcrowds = {}  # (interface, permission) -> crowd_factory
        self.permcrowds = {} # permission -> crowd_factory


def getCrowdsUtility():
    """Helper - returns crowds utility and registers new one if missing."""
    utility = zapi.queryUtility(ICrowdsUtility)
    if not utility:
        utility = CrowdsUtility()
        zapi.getGlobalSiteManager().registerUtility(utility, ICrowdsUtility)
    return utility


def registerCrowdAdapter(iface, permission):
    """Register an adapter to ICrowd for iface.

    The adapter dynamically retrieves the list of crowds from the
    global objcrowds.  You should not call this function several times
    for the same (iface, permission).
    """
    class AggregateCrowdAdapter(Crowd):
        def contains(self, principal):
            crowd_factories = getCrowdsUtility().objcrowds[(iface, permission)]
            for crowdcls in crowd_factories:
                crowd = crowdcls(self.context)
                if crowd.contains(principal):
                    return True
            return False
    provideAdapter(AggregateCrowdAdapter, provides=ICrowd, adapts=[iface],
                   name=permission)


def handle_crowd(name, factory):
    """Handler for the ZCML <crowd> directive."""
    getCrowdsUtility().crowdmap[name] = factory


def handle_allow(iface, crowdname, permission):
    """Handler for the ZCML <allow> directive.

    iface is the interface for which the security declaration is issued,
    crowdname is a string,
    permission is an identifier for a permission.

    The function registers the given crowd factory in the ICrowdsUtility
    utility and registers an adapter to ICrowd if it was not registered before.

    iface may be None.  In that case permcrowds is updated instead.
    """

    utility = getCrowdsUtility()
    factory = utility.crowdmap[crowdname]
    if iface is None:
        utility.permcrowds.setdefault(permission, []).append(factory)
        return

    objcrowds = utility.objcrowds
    if (iface, permission) not in objcrowds:
        registerCrowdAdapter(iface, permission)
        objcrowds[(iface, permission)] = []
    objcrowds[(iface, permission)].append(factory)


def crowd(_context, name, factory):
    # TODO: raise ConfigurationError if arguments are invalid
    _context.action(discriminator=('Crowd', name), callable=handle_crowd,
                    args=(name, factory))


def allow(_context, interface=None, crowds=None, permission=None):
    # TODO: raise ConfigurationError if arguments are invalid
    for crowd in crowds:
        _context.action(discriminator=('Allow', interface, crowd, permission),
                        callable=handle_allow,
                        args=(interface, crowd, permission))


class AccessControlSetting(object):
    implements(IAccessControlSetting)

    def __init__(self, key, text, default):
        self.key = key
        self.text = text
        self.default = default

    def getValue(self):
        app = ISchoolToolApplication(None)
        customisations = IAccessControlCustomisations(app)
        return customisations.get(self.key)

    def __repr__(self):
        return "<AccessControlSetting key=%s, text=%s, default=%s>" % (
                self.key, self.text, self.default)


def handle_setting(key, text, default):
    def accessControlSettingFactory(context=None):
        return AccessControlSetting(key, text, default)
    provideSubscriptionAdapter(accessControlSettingFactory,
                               adapts=[None],
                               provides=IAccessControlSetting)

def setting(_context, key=None, text=None, default=None):
    _context.action(discriminator=None, callable=handle_setting,
                    args=(key, text, default))
