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
Interfaces for SchoolTool security policy.

$Id$

"""

from zope.interface import Interface
from zope.schema import Dict, Bool, TextLine
from zope.interface import Attribute
from zope.configuration.fields import PythonIdentifier


class ICrowdsUtility(Interface):
    """Crowds Utility holds registered security information"""

    crowdmap = Dict(
        title=u"Crowd Map",
        description=u"Maps crowd names to crowd factories")

    objcrowds = Dict(
        title=u"Object Crowd Factories",
        description=u"Maps (interface, permission)s to crowd factories")

    permcrowds = Dict(
        title=u"Permission Crowd Factories",
        description=u"Maps permissions to crowd factories")


class ICrowd(Interface):
    """A crowd is conceptually a set of principals.

    A crowd need only support one operation -- a membership test.
    """

    def contains(principal):
        """Return True if principal is in the crowd."""


class IAccessControlCustomisations(Interface):
    """Access Control Customisation storage."""

    def get(key):
        """Return a value of a setting stored under the key."""

    def set(key, value):
        """Set the value of a setting stored under the key."""

    def __iter__():
        """Iterate through all customisation settings."""


class IAccessControlSetting(Interface):
    """An access control customisation setting."""

    key = PythonIdentifier(description=u"""A key that identified the setting.
                           For example: 'members_manage_groups',
                           'teachers_edit_person_info'
                           """)
    default = Bool(title=u"The default value for the setting.")
    text = TextLine(title=u"Description of the setting for the user interface.")

    def getValue():
        """Return the value of the setting.

        Return the default if it is not set in the
        AccessControlCusomisations storage.
        """
