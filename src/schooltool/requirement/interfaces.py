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
"""Requirement Interfaces

$Id$
"""
import zope.interface
import zope.schema
import zope.app.container.constraints
import zope.app.container.interfaces


class IRequirement(zope.interface.Interface):
    '''The simplest form of a standard.'''
    zope.app.container.constraints.containers('.IGroupRequirement')

    title = zope.schema.TextLine(
        title=u'Title',
        description=u'A brief title of the requirement.',
        required=True)


class IGroupRequirement(zope.app.container.interfaces.IContainer, IRequirement):
    '''A group of requirements.'''
    zope.app.container.constraints.contains(IRequirement)

    bases = zope.schema.List(
        title=u'Bases',
        description=u'An enumeration of base requirements.',
        readonly=True)

    def addBase(definition):
        '''Add a group requirement as a base definition.'''

    def removeBase(definition):
        '''Remove a group requirement from the bases.

        This method is responsible for notifying its contained requirements
        about the removal of this requirement.
        '''

class ICompetency(IRequirement):
    '''A competency.

    This is a competency as defined by the state of Virginia, USA.
    '''

    id = zope.schema.TextLine(
        title=u'Id',
        description=u'Arbitrary string identifier.',
        required=True)

    required = zope.schema.Choice(
        title=u'Required',
        description=u'A flag that descibes the requirement of the competency.',
        required=True,
        values=[u'required', u'optional', u'sensitive'])
