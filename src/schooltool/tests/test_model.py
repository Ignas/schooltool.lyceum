#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2003 Shuttleworth Foundation
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
Unit tests for schooltool.model

$Id$
"""

import unittest
from sets import Set
from zope.interface import implements
from zope.interface.verify import verifyObject
from schooltool.interfaces import IGroupMember, IFacet, IFaceted
from schooltool.interfaces import IEventConfigurable, IEvent

__metaclass__ = type

class MemberStub:
    added = None
    removed = None
    implements(IGroupMember, IFaceted)
    def __init__(self):
        self.__facets__ = {}
    def notifyAdd(self, group, name):
        self.added = group
    def notifyRemove(self, group):
        self.removed = group

class FacetStub:
    implements(IFacet)

    def __init__(self, context=None, active=False):
        self.context = context
        self.active = active

class FacetWithEventsStub(FacetStub):
    implements(IEventConfigurable)

    def __init__(self, context=None, active=False, eventTable=None):
        FacetStub.__init__(self, context, active)
        if eventTable is None:
            eventTable = []
        self.eventTable = eventTable


class TestPerson(unittest.TestCase):

    def test(self):
        from schooltool.interfaces import IPerson, IEventTarget
        from schooltool.model import Person
        person = Person('John Smith')
        verifyObject(IPerson, person)
        verifyObject(IEventTarget, person)
        verifyObject(IEventConfigurable, person)


class TestGroupMember(unittest.TestCase):

    def test_notifyAdd(self):
        from schooltool.model import GroupMember
        member = GroupMember()
        group = object()
        member.notifyAdd(group, 1)
        self.assertEqual(list(member.groups()), [group])
        self.assertEqual(member.__parent__, group)
        self.assertEqual(member.__name__, '1')
        member.notifyAdd(object(), '2')
        self.assertEqual(member.__parent__, group)
        self.assertEqual(member.__name__, '1')

    def test_notifyRemove(self):
        from schooltool.model import GroupMember
        member = GroupMember()
        group = object()
        other = object()
        for parent in (group, other):
            member.__parent__ = parent
            member.__name__ = 'spam'
            member._groups = Set([group])
            member.notifyRemove(group)
            self.assertEqual(list(member.groups()), [])
            self.assertRaises(KeyError, member.notifyRemove, group)
            if parent == group:
                self.assertEqual(member.__parent__, None)
                self.assertEqual(member.__name__, None)
            else:
                self.assertEqual(member.__parent__, other)
                self.assertEqual(member.__name__, 'spam')


class TestGroup(unittest.TestCase):

    def test(self):
        from schooltool.interfaces import IGroup, IEventTarget
        from schooltool.model import Group
        group = Group("root")
        verifyObject(IGroup, group)
        verifyObject(IGroupMember, group)
        verifyObject(IFaceted, group)
        verifyObject(IEventTarget, group)
        verifyObject(IEventConfigurable, group)

    def test_add(self):
        from schooltool.model import Group
        group = Group("root")
        member = MemberStub()
        key = group.add(member)
        self.assertEqual(member, group[key])
        self.assertEqual(member.added, group)
        self.assertRaises(TypeError, group.add, "not a member")

    def test_add_group(self):
        from schooltool.model import Group
        group = Group("root")
        member = Group("people")
        key = group.add(member)
        self.assertEqual(member, group[key])
        self.assertEqual(list(member.groups()), [group])

    def test_facet_management(self):
        from schooltool.model import Group
        from schooltool.adapters import getFacet
        group = Group("root", FacetStub)
        member = MemberStub()
        key = group.add(member)
        facet = getFacet(member, group)
        self.assertEquals(facet.context, member)
        self.assert_(facet.active)

        del group[key]
        self.assert_(getFacet(member, group) is facet)
        self.assert_(not facet.active)

        key = group.add(member)
        self.assert_(getFacet(member, group) is facet)
        self.assert_(facet.active)

    def test_remove(self):
        from schooltool.model import Group
        group = Group("root")
        member = MemberStub()
        key = group.add(member)
        del group[key]
        self.assertRaises(KeyError, group.__getitem__, key)
        self.assertRaises(KeyError, group.__delitem__, key)
        self.assertEqual(member.removed, group)

    def test_items(self):
        from schooltool.model import Group
        group = Group("root")
        self.assertEquals(list(group.keys()), [])
        self.assertEquals(list(group.values()), [])
        self.assertEquals(list(group.items()), [])
        member = MemberStub()
        key = group.add(member)
        self.assertEquals(list(group.keys()), [key])
        self.assertEquals(list(group.values()), [member])
        self.assertEquals(list(group.items()), [(key, member)])


class TestRootGroup(unittest.TestCase):

    def test_interfaces(self):
        from schooltool.interfaces import IRootGroup
        from schooltool.model import RootGroup
        group = RootGroup("root")
        verifyObject(IRootGroup, group)


class TestFacetedMixin(unittest.TestCase):

    def test(self):
        from schooltool.model import FacetedMixin
        from schooltool.interfaces import IFaceted
        m = FacetedMixin()
        verifyObject(IFaceted, m)


class TargetStub:
    events = ()

    def handle(self, event):
        self.events += (event, )

class TestEventMixin(unittest.TestCase):

    def test(self):
        from schooltool.model import EventMixin
        from schooltool.interfaces import IEvent
        marker = object()
        e = EventMixin(marker)
        verifyObject(IEvent, e)
        self.assertEquals(e.context, marker)

    def test_dispatch(self):
        from schooltool.model import EventMixin
        target = TargetStub()
        e = EventMixin()
        e.dispatch(target)
        self.assertEquals(target.events, (e, ))

    def test_dispatch_default_arg(self):
        from schooltool.model import EventMixin
        target = TargetStub()
        e = EventMixin(target)
        e.dispatch()
        self.assertEquals(target.events, (e, ))

    def test_dispatch_repeatedly(self):
        from schooltool.model import EventMixin
        target = TargetStub()
        e = EventMixin()
        e.dispatch(target)
        e.dispatch(target)
        e.dispatch(target)
        self.assertEquals(target.events, (e, ))


class IEventA(IEvent):
    pass

class IEventB(IEvent):
    pass

class EventAStub:
    implements(IEventA)

    def __init__(self):
        self.dispatched_to = []

    def dispatch(self, target):
        self.dispatched_to.append(target)

class EventActionStub:
    def __init__(self, evtype):
        self.eventType = evtype
        self.calls = []

    def handle(self, event, target):
        self.calls.append((event, target))

class TestEventTargetMixin(unittest.TestCase):

    def test(self):
        from schooltool.model import EventTargetMixin
        from schooltool.interfaces import IEventTarget, IEventConfigurable
        et = EventTargetMixin()
        verifyObject(IEventTarget, et)
        verifyObject(IEventConfigurable, et)
        self.assertEquals(list(et.eventTable), [])

    def test_handle(self):
        from schooltool.model import EventTargetMixin
        et = EventTargetMixin()
        handler_a = EventActionStub(IEventA)
        handler_b = EventActionStub(IEventB)
        et.eventTable.extend([handler_a, handler_b])
        event = EventAStub()
        et.handle(event)
        self.assertEqual(handler_a.calls, [(event, et)])
        self.assertEqual(handler_b.calls, [])


class TestFacetedEventTargetMixin(unittest.TestCase):

    def test(self):
        from schooltool.model import FacetedEventTargetMixin
        from schooltool.interfaces import IFaceted, IEventTarget, IEventConfigurable
        et = FacetedEventTargetMixin()
        verifyObject(IFaceted, et)
        verifyObject(IEventTarget, et)
        verifyObject(IEventConfigurable, et)

    def test_getEventTable(self):
        from schooltool.model import FacetedEventTargetMixin
        from schooltool.adapters import setFacet
        et = FacetedEventTargetMixin()
        et.__facets__ = {} # use a simple dict instead of PersistentKeysDict
        et.eventTable.append(0)
        setFacet(et, 1, FacetStub())
        setFacet(et, 2, FacetStub(active=True))
        setFacet(et, 3, FacetWithEventsStub(eventTable=[1]))
        setFacet(et, 4, FacetWithEventsStub(active=True, eventTable=[2]))
        self.assertEquals(et.getEventTable(), [0, 2])


class TestEventActionMixins(unittest.TestCase):

    def test(self):
        from schooltool.model import EventActionMixin
        from schooltool.interfaces import IEventAction
        marker = object()
        ea = EventActionMixin(marker)
        verifyObject(IEventAction, ea)
        self.assertEquals(ea.eventType, marker)
        self.assertRaises(NotImplementedError, ea.handle, None, None)

    def testLookupAction(self):
        from schooltool.model import LookupAction
        from schooltool.interfaces import ILookupAction
        la = LookupAction()
        verifyObject(ILookupAction, la)
        self.assertEquals(list(la.eventTable), [])
        self.assertEquals(la.eventType, IEvent)

        handler_a = EventActionStub(IEventA)
        handler_b = EventActionStub(IEventB)
        la = LookupAction(eventType=IEventA, eventTable=[handler_a, handler_b])
        self.assertEquals(la.eventType, IEventA)
        event = EventAStub()
        target = object()
        la.handle(event, target)
        self.assertEqual(handler_a.calls, [(event, target)])
        self.assertEqual(handler_b.calls, [])

    def testRouteToMembersAction(self):
        from schooltool.model import RouteToMembersAction
        from schooltool.interfaces import IRouteToMembersAction
        action = RouteToMembersAction(IEventA)
        verifyObject(IRouteToMembersAction, action)
        self.assertEquals(action.eventType, IEventA)

        event = EventAStub()
        child1, child2 = object(), object()
        target = {1: child1, 2: child2}
        action.handle(event, target)
        dispatched_to = event.dispatched_to
        members = [child1, child2]
        members.sort()
        dispatched_to.sort()
        self.assertEquals(dispatched_to, members)

    def testRouteToGroupsAction(self):
        from schooltool.model import RouteToGroupsAction
        from schooltool.interfaces import IRouteToGroupsAction
        action = RouteToGroupsAction(IEventA)
        verifyObject(IRouteToGroupsAction, action)
        self.assertEquals(action.eventType, IEventA)

        event = EventAStub()
        group1, group2 = object(), object()
        target = MemberStub()
        target.groups = lambda: [group1, group2]
        action.handle(event, target)
        dispatched_to = event.dispatched_to
        groups = [group1, group2]
        groups.sort()
        dispatched_to.sort()
        self.assertEquals(dispatched_to, groups)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPerson))
    suite.addTest(unittest.makeSuite(TestGroup))
    suite.addTest(unittest.makeSuite(TestRootGroup))
    suite.addTest(unittest.makeSuite(TestGroupMember))
    suite.addTest(unittest.makeSuite(TestFacetedMixin))
    suite.addTest(unittest.makeSuite(TestEventMixin))
    suite.addTest(unittest.makeSuite(TestEventTargetMixin))
    suite.addTest(unittest.makeSuite(TestFacetedEventTargetMixin))
    suite.addTest(unittest.makeSuite(TestEventActionMixins))
    return suite

if __name__ == '__main__':
    unittest.main()
