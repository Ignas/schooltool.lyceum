#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2007 Shuttleworth Foundation
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
Lyceum person specific code.

$Id$

"""
from zope.interface import implements
from zope.component import adapts
from zope.interface import directlyProvides

from zc.table.interfaces import ISortableColumn

from schooltool.person.person import Person
from schooltool.person.interfaces import IPersonFactory
from schooltool.course.section import PersonInstructorsCrowd
from schooltool.person.person import PersonCalendarCrowd
from schooltool.skin.table import LocaleAwareGetterColumn

from lyceum.interfaces import ILyceumPerson
from lyceum import LyceumMessage as _


class LyceumPerson(Person):
    implements(ILyceumPerson)

    gender = None
    gradeclass = None
    birth_date = None
    advisor = None

    def __init__(self, username, first_name, last_name,
                 email=None, phone=None):
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.email = email
        self.phone = phone

    @property
    def title(self):
        return "%s %s" % (self.last_name, self.first_name)


class PersonFactoryUtility(object):

    implements(IPersonFactory)

    def columns(self):
        first_name = LocaleAwareGetterColumn(
            name='first_name',
            title=_(u'First Name'),
            getter=lambda i, f: i.first_name,
            subsort=True)
        directlyProvides(first_name, ISortableColumn)
        last_name = LocaleAwareGetterColumn(
            name='last_name',
            title=_(u'Last Name'),
            getter=lambda i, f: i.last_name,
            subsort=True)
        directlyProvides(last_name, ISortableColumn)

        return [first_name, last_name]

    def createManagerUser(self, username, system_name):
        return self(username, system_name, "Administratorius")

    def sortOn(self):
        return (("last_name", False),)

    def groupBy(self):
        return (("grade", False),)

    def __call__(self, *args, **kw):
        result = LyceumPerson(*args, **kw)
        return result


class LyceumPersonCalendarCrowd(PersonCalendarCrowd):
    """Crowd that allows instructor of a person access persons calendar.

    XXX write functional test.
    """
    adapts(ILyceumPerson)

    def contains(self, principal):
        return (PersonCalendarCrowd.contains(self, principal) or
                PersonInstructorsCrowd(self.context).contains(principal))
