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
Unit tests for the schooltool.timetable module.

$Id$
"""

import calendar
import unittest
from sets import Set
from pprint import pformat
from datetime import date, time, timedelta, datetime

from persistent import Persistent
from zope.interface.verify import verifyObject
from zope.interface import implements, directlyProvides
from schooltool.tests.helpers import diff, sorted
from schooltool.tests.utils import NiceDiffsMixin, EqualsSortedMixin
from schooltool.tests.utils import RegistriesSetupMixin
from schooltool.tests.utils import EventServiceTestMixin
from schooltool.tests.utils import LocatableEventTargetMixin
from schooltool.tests.utils import TraversableRoot, LocationStub
from schooltool.interfaces import ISchooldayModel
from schooltool.interfaces import ITimetableActivity
from schooltool.interfaces import ILocation
from schooltool.interfaces import IOptions
from schooltool.facet import FacetedMixin
from schooltool.timetable import TimetabledMixin
from schooltool.relationship import RelatableMixin

__metaclass__ = type


def setPath(obj, path):
    """Trick getPath(obj) into returning path.

    Also, the fictional root will be returned by getOptions
    """
    assert path.startswith('/')
    obj.__name__ = path[1:]
    directlyProvides(obj, ILocation)
    obj.__parent__ = TraversableRoot()
    directlyProvides(obj.__parent__, IOptions)


class ActivityStub:

    implements(ITimetableActivity)
    replaced = False
    timetable = None

    def replace(self, **kwargs):
        self.replaced = True
        if 'timetable' in kwargs:
            self.timetable = kwargs['timetable']
        return self


class TestTimetable(unittest.TestCase):

    def test_interface(self):
        from schooltool.timetable import Timetable
        from schooltool.interfaces import ITimetable, ITimetableWrite
        from schooltool.interfaces import ILocation

        t = Timetable(('1', '2'))
        verifyObject(ITimetable, t)
        verifyObject(ITimetableWrite, t)
        verifyObject(ILocation, t)

    def test_keys(self):
        from schooltool.timetable import Timetable
        days = ('Mo', 'Tu', 'We', 'Th', 'Fr')
        t = Timetable(days)
        self.assertEqual(t.keys(), list(days))

    def test_getitem_setitem(self):
        from schooltool.timetable import Timetable
        from schooltool.interfaces import ITimetableDay

        days = ('Mo', 'Tu', 'We', 'Th', 'Fr')
        t = Timetable(days)
        self.assertRaises(KeyError, t.__getitem__, "Mo")
        self.assertRaises(KeyError, t.__getitem__, "What!?")

        class DayStub:
            implements(ITimetableDay)
            timetable = None
            day_id = None

        self.assertRaises(TypeError, t.__setitem__, "Mo", object())
        self.assertRaises(ValueError, t.__setitem__, "Mon", DayStub())
        monday = DayStub()
        t["Mo"] = monday
        self.assertEqual(t["Mo"], monday)
        self.assert_(monday.timetable is t)
        self.assert_(monday.day_id is 'Mo')

    def test_items(self):
        from schooltool.timetable import Timetable
        from schooltool.interfaces import ITimetableDay

        days = ('Day 1', 'Day 2', 'Day 3')
        t = Timetable(days)

        class DayStub:
            implements(ITimetableDay)
            timetable = None

        t["Day 1"] = day1 = DayStub()
        t["Day 2"] = day2 = DayStub()
        self.assertRaises(KeyError, t.items)
        t["Day 3"] = day3 = DayStub()
        self.assertEqual(t.items(),
                         [("Day 1", day1), ("Day 2", day2), ("Day 3", day3)])

    def createTimetable(self):
        from schooltool.timetable import Timetable, TimetableDay
        days = ('A', 'B')
        periods = ('Green', 'Blue')
        tt = Timetable(days)
        tt["A"] = TimetableDay(periods)
        tt["B"] = TimetableDay(periods)
        return tt

    def test_clear(self):
        from schooltool.timetable import TimetableActivity
        tt = self.createTimetable()
        english = TimetableActivity("English")
        math = TimetableActivity("Math")
        bio = TimetableActivity("Biology")
        tt["A"].add("Green", english)
        tt["A"].add("Blue", math)
        tt["B"].add("Green", bio)

        tt.clear()

        empty_tt = self.createTimetable()
        self.assertEqual(tt, empty_tt)

    def test_update(self):
        from schooltool.timetable import Timetable, TimetableDay
        from schooltool.timetable import TimetableActivity

        tt = self.createTimetable()
        english = TimetableActivity("English")
        math = TimetableActivity("Math")
        bio = TimetableActivity("Biology")
        tt["A"].add("Green", english)
        tt["A"].add("Blue", math)
        tt["B"].add("Green", bio)
        exc1 = object()
        tt.exceptions.append(exc1)

        tt2 = self.createTimetable()
        french = TimetableActivity("French")
        math2 = TimetableActivity("Math 2")
        geo = TimetableActivity("Geography")
        tt2["A"].add("Green", french)
        tt2["A"].add("Blue", math2)
        tt2["B"].add("Blue", geo)
        exc2 = object()
        tt2.exceptions.append(exc2)

        tt.update(tt2)

        items = [(p, Set(i)) for p, i in tt["A"].items()]
        self.assertEqual(items, [("Green", Set([english, french])),
                                 ("Blue", Set([math, math2]))])

        items = [(p, Set(i)) for p, i in tt["B"].items()]
        self.assertEqual(items, [("Green", Set([bio])),
                                 ("Blue", Set([geo]))])

        self.assertEqual(tt.exceptions, [exc1, exc2])

        tt3 = Timetable(("A", ))
        tt3["A"] = TimetableDay(('Green', 'Blue'))
        self.assertRaises(ValueError, tt.update, tt3)

    def test_cloneEmpty(self):
        from schooltool.timetable import TimetableActivity
        from schooltool.timetable import TimetableException

        tt = self.createTimetable()
        english = TimetableActivity("English")
        math = TimetableActivity("Math")
        bio = TimetableActivity("Biology")
        tt["A"].add("Green", english)
        tt["A"].add("Blue", math)
        tt["B"].add("Green", bio)
        tt.model = object()
        tt.exceptions.append(TimetableException(date(2005, 1, 4),
                                                'Green', bio))

        tt2 = tt.cloneEmpty()
        self.assert_(tt2 is not tt)
        self.assertEquals(tt.day_ids, tt2.day_ids)
        self.assert_(tt.model is tt2.model)
        self.assertEquals(tt2.exceptions, [])
        for day_id in tt2.day_ids:
            day = tt[day_id]
            day2 = tt2[day_id]
            self.assert_(day is not day2)
            self.assertEquals(day.periods, day2.periods)
            for period in day2.periods:
                self.assertEquals(list(day2[period]), [])

    def testComparison(self):
        from schooltool.timetable import TimetableActivity

        model = object()
        tt = self.createTimetable()
        english = TimetableActivity("English")
        math = TimetableActivity("Math")
        bio = TimetableActivity("Biology")
        tt["A"].add("Green", english)
        tt["A"].add("Blue", math)
        tt["B"].add("Green", bio)

        self.assertEquals(tt, tt)
        self.assertNotEquals(tt, None)

        tt2 = self.createTimetable()
        self.assertNotEquals(tt, tt2)

        tt2["A"].add("Green", english)
        tt2["A"].add("Blue", math)
        tt2["B"].add("Green", bio)
        self.assertEquals(tt, tt2)
        tt2.model = model
        self.assertNotEquals(tt, tt2)
        tt.model = model
        self.assertEquals(tt, tt2)

        tt.exceptions.append('foo')
        self.assertNotEquals(tt, tt2)

        tt2.exceptions.append('foo')
        self.assertEquals(tt, tt2)

        tt2["B"].remove("Green", bio)
        self.assertNotEquals(tt, tt2)

    def test_itercontent(self):
        from schooltool.timetable import TimetableActivity
        tt = self.createTimetable()
        english = TimetableActivity("English")
        math = TimetableActivity("Math")
        bio = TimetableActivity("Biology")
        tt["A"].add("Green", english)
        tt["A"].add("Blue", math)
        tt["B"].add("Green", bio)
        result = list(tt.itercontent())
        expected = [("A", "Green", english),
                    ("A", "Blue", math),
                    ("B", "Green", bio)]
        self.assertEquals(result, expected)


class TestTimetableDay(EventServiceTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpEventService()

    def test_interface(self):
        from schooltool.timetable import TimetableDay
        from schooltool.interfaces import ITimetableDay, ITimetableDayWrite

        td = TimetableDay()
        verifyObject(ITimetableDay, td)
        verifyObject(ITimetableDayWrite, td)

    def test_keys(self):
        from schooltool.timetable import TimetableDay

        periods = ('1', '2', '3', '4', '5')
        td = TimetableDay(periods)
        self.assertEqual(td.keys(), periods)

    def testComparison(self):
        from schooltool.timetable import TimetableDay, Timetable

        periods = ('A', 'B')
        td1 = TimetableDay(periods)
        td2 = TimetableDay(periods)
        tt = Timetable(['td1', 'td2'])
        tt['td1'] = td1
        tt['td2'] = td2

        self.assertEquals(td1, td2)
        self.assertNotEquals(td1, None)
        self.failIf(td1 != td2)

        a1 = ActivityStub()
        td1.add("A", a1)
        self.assertNotEquals(td1, td2)
        td2.add("A", a1)
        self.assertEquals(td1, td2)

        td3 = TimetableDay(('C', 'D'))
        self.assertNotEquals(td1, td3)

    def test_getitem_add_items_clear_remove(self):
        from schooltool.timetable import TimetableDay, Timetable, TimetableDict
        from schooltool.interfaces import ITimetableActivityAddedEvent
        from schooltool.interfaces import ITimetableActivityRemovedEvent

        periods = ('1', '2', '3', '4')
        timetable = Timetable(['td'])
        ttd = TimetableDict()
        ttd['a', 'key'] = timetable
        ttd.__parent__ = self.eventService
        td = timetable['td'] = TimetableDay(periods)

        self.assertRaises(KeyError, td.__getitem__, "Mo")
        self.assertEqual(len(list(td["1"])), 0)

        self.assertRaises(TypeError, td.add, "1", object())
        math = ActivityStub()
        self.assertRaises(ValueError, td.add, "Mo", math)

        td.add("1", math)
        e1 = self.checkOneEventReceived()
        self.assert_(ITimetableActivityAddedEvent.providedBy(e1))
        self.assert_(e1.activity.timetable is timetable)
        self.assertEquals(e1.activity, math)
        self.assertEquals(e1.day_id, 'td')
        self.assertEquals(e1.period_id, '1')

        self.assertEqual(list(td["1"]), [math])
        self.assert_(list(td["1"])[0].replaced)

        result = [(p, Set(i)) for p, i in td.items()]

        self.assertEqual(result, [('1', Set([math])), ('2', Set([])),
                                  ('3', Set([])), ('4', Set([]))])
        english = ActivityStub()
        self.eventService.clearEvents()
        td.add("2", english)
        e2 = self.checkOneEventReceived()
        self.assertEquals(e2.period_id, '2')

        result = [(p, Set(i)) for p, i in td.items()]
        self.assertEqual(result, [('1', Set([math])), ('2', Set([english])),
                                  ('3', Set([])), ('4', Set([]))])


        # test clear()
        self.assertEqual(Set(td["2"]), Set([english]))
        self.assertRaises(ValueError, td.clear, "Mo")
        self.eventService.clearEvents()
        td.clear("2")
        e2 = self.checkOneEventReceived()
        self.assert_(ITimetableActivityRemovedEvent.providedBy(e2))
        self.assert_(e2.activity.timetable is timetable)
        self.assertEquals(e2.activity, english)
        self.assertEquals(e2.day_id, 'td')
        self.assertEquals(e2.period_id, '2')
        self.assertRaises(ValueError, td.clear, "foo")
        self.assertEqual(Set(td["2"]), Set([]))

        # test remove()
        td.add("1", english)
        result = [(p, Set(i)) for p, i in td.items()]
        self.assertEqual(result, [('1', Set([english, math])),
                                  ('2', Set([])), ('3', Set([])),
                                  ('4', Set([]))])
        self.eventService.clearEvents()
        td.remove("1", math)
        e3 = self.checkOneEventReceived()
        self.assert_(ITimetableActivityRemovedEvent.providedBy(e3))
        self.assert_(e3.activity.timetable is timetable)
        self.assertEquals(e3.activity, math)
        self.assertEquals(e3.day_id, 'td')
        self.assertEquals(e3.period_id, '1')
        self.assertRaises(KeyError, td.remove, "1", math)
        result = [(p, Set(i)) for p, i in td.items()]
        self.assertEqual(result, [('1', Set([english])),
                                  ('2', Set([])), ('3', Set([])),
                                  ('4', Set([]))])


class TestTimetableActivity(unittest.TestCase):

    def test(self):
        from schooltool.timetable import TimetableActivity
        from schooltool.interfaces import ITimetableActivity

        owner = object()
        ta = TimetableActivity("Dancing", owner)
        verifyObject(ITimetableActivity, ta)
        self.assertEqual(ta.title, "Dancing")
        self.assert_(ta.owner is owner)
        self.assertEqual(list(ta.resources), [])

        class FakeThing:
            title = "Dancing"
        fake_thing = FakeThing()
        tb = TimetableActivity("Dancing", owner)
        tc = TimetableActivity("Fencing", owner)
        td = TimetableActivity("Dancing", object())
        res1 = object()
        res2 = object()
        te = TimetableActivity("Dancing", owner, [res1, res2])
        tf = TimetableActivity("Dancing", owner, [res2, res1])
        tg = TimetableActivity("Dancing", owner, [res1, res2],
                               timetable=object())

        # Do we really want to ignore timetable when hashing/comparing?
        # On further thought it does not matter -- we never compare activities
        # that come from timetables with different keys.

        # __eq__
        self.assertEqual(ta, ta)
        self.assertEqual(ta, tb)
        self.assertNotEqual(ta, tc)
        self.assertNotEqual(ta, td)
        self.assertNotEqual(ta, fake_thing)
        self.assertNotEqual(ta, te)
        self.assertEqual(te, tf)
        self.assertEqual(tf, tg)

        # __ne__
        self.failIf(ta != ta)
        self.failIf(ta != tb)
        self.assert_(ta != tc)
        self.assert_(ta != td)
        self.assert_(ta != fake_thing)
        self.assert_(ta != te)
        self.failIf(te != tf)
        self.failIf(tf != tg)

        # __hash__
        self.assertEqual(hash(ta), hash(tb))
        self.assertNotEqual(hash(ta), hash(tc))
        self.assertNotEqual(hash(ta), hash(td))
        self.assertNotEqual(hash(ta), hash(te))
        self.assertEqual(hash(te), hash(tf))
        self.assertEqual(hash(tf), hash(tg))

    def test_immutability(self):
        from schooltool.timetable import TimetableActivity
        owner = object()
        ta = TimetableActivity("Dancing", owner)

        def try_to_assign_title():
            ta.title = "xyzzy"
        def try_to_assign_owner():
            ta.owner = "xyzzy"
        def try_to_assign_resources():
            ta.resources = "xyzzy"
        def try_to_modify_resources():
            ta.resources.add("xyzzy")
        self.assertRaises(AttributeError, try_to_assign_title)
        self.assertRaises(AttributeError, try_to_assign_owner)
        self.assertRaises(AttributeError, try_to_assign_resources)
        self.assertRaises(AttributeError, try_to_modify_resources)
        self.assertEquals(ta.title, "Dancing")

    def test_replace(self):
        from schooltool.timetable import TimetableActivity
        owner = object()
        owner2 = object()
        ta = TimetableActivity("Dancing", owner)
        tb = ta.replace(title=None, owner=owner2)
        self.assertEquals(tb.title, None)
        self.assertEquals(tb.owner, owner2)


class TestTimetableExceptionList(EventServiceTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpEventService()

    def test(self):
        from schooltool.timetable import TimetableExceptionList
        from schooltool.interfaces import ITimetableExceptionList
        from schooltool.interfaces import ITimetableExceptionAddedEvent
        from schooltool.interfaces import ITimetableExceptionRemovedEvent
        timetable = LocationStub()
        timetable.__parent__ = self.eventService
        l = TimetableExceptionList(timetable)
        verifyObject(ITimetableExceptionList, l)

        # empty list
        self.assertEquals(list(l), [])
        self.assertEquals(len(l), 0)
        self.assertEquals(l, [])
        self.assertRaises(IndexError, l.__getitem__, 0)

        ex1 = object()
        l.append(ex1)
        self.assertEquals(list(l), [ex1])
        self.assertEquals(len(l), 1)
        self.assertEquals(l, [ex1])
        self.assert_(l[0] is ex1)
        e1 = self.checkOneEventReceived()
        self.assert_(ITimetableExceptionAddedEvent.providedBy(e1))
        self.assert_(e1.timetable is timetable)
        self.assert_(e1.exception is ex1)

        timetable2 = object()
        l2 = TimetableExceptionList(timetable2)
        l2.append(ex1)
        self.assertEquals(l, l2)

        ex2 = object()
        l.extend([ex2])
        self.assertNotEquals(l, l2)
        self.assertEquals(l, [ex1, ex2])

        self.eventService.clearEvents()
        l.remove(ex1)
        self.assertEquals(l, [ex2])
        e2 = self.checkOneEventReceived()
        self.assert_(ITimetableExceptionRemovedEvent.providedBy(e2))
        self.assert_(e1.timetable is timetable)
        self.assert_(e1.exception is ex1)

        self.assertRaises(ValueError, l.remove, ex1)


class TestTimetableEvents(unittest.TestCase):

    def test_tt_exception_events(self):
        from schooltool.timetable import TimetableExceptionAddedEvent
        from schooltool.timetable import TimetableExceptionRemovedEvent
        from schooltool.interfaces import ITimetableExceptionAddedEvent
        from schooltool.interfaces import ITimetableExceptionRemovedEvent
        timetable = object()
        exception = object()
        e1 = TimetableExceptionAddedEvent(timetable, exception)
        verifyObject(ITimetableExceptionAddedEvent, e1)
        e2 = TimetableExceptionRemovedEvent(timetable, exception)
        verifyObject(ITimetableExceptionRemovedEvent, e2)

    def test_tt_replaced_event(self):
        from schooltool.timetable import TimetableReplacedEvent
        from schooltool.interfaces import ITimetableReplacedEvent
        obj = object()
        key = ('a', 'b')
        old_timetable = object()
        new_timetable = object()
        e = TimetableReplacedEvent(obj, key, old_timetable, new_timetable)
        verifyObject(ITimetableReplacedEvent, e)

    def test_activity_added_event(self):
        from schooltool.timetable import TimetableActivityAddedEvent
        from schooltool.interfaces import ITimetableActivityAddedEvent
        obj = object()
        day_id = 'Monday'
        period_id = 'autumn'
        e = TimetableActivityAddedEvent(obj, day_id, period_id)
        verifyObject(ITimetableActivityAddedEvent, e)

    def test_activity_removed_event(self):
        from schooltool.timetable import TimetableActivityRemovedEvent
        from schooltool.interfaces import ITimetableActivityRemovedEvent
        obj = object()
        day_id = 'Monday'
        period_id = 'autumn'
        e = TimetableActivityRemovedEvent(obj, day_id, period_id)
        verifyObject(ITimetableActivityRemovedEvent, e)


class TestTimetableException(unittest.TestCase):

    def test(self):
        from schooltool.timetable import TimetableException
        from schooltool.timetable import ExceptionalTTCalendarEvent
        from schooltool.interfaces import ITimetableException
        activity = object()
        e = TimetableException(date(2004, 10, 12), 123, activity)
        e.replacement = ExceptionalTTCalendarEvent(date(2004, 10, 13),
                                                 timedelta(45),
                                                 "Math",
                                                 exception=e)
        verifyObject(ITimetableException, e)
        self.assertEquals(e.date, date(2004, 10, 12))
        self.assertEquals(e.period_id, 123)
        assert e.activity is activity
        e.replacement = None

        self.assertRaises(ValueError, setattr, e, 'replacement', object())
        self.assertRaises(AttributeError, setattr, e, 'date', object())
        self.assertRaises(AttributeError, setattr, e, 'period_id', object())
        self.assertRaises(AttributeError, setattr, e, 'activity', object())

    def test_comparison(self):
        from schooltool.timetable import TimetableException
        from schooltool.timetable import ExceptionalTTCalendarEvent
        activity1 = object()
        activity2 = object()

        e1 = TimetableException(date(2004, 10, 14), 'period 1', activity1)
        e2 = TimetableException(date(2004, 10, 14), 'period 1', activity1)
        assert e1 == e2
        assert not (e1 != e2)

        e3 = TimetableException(date(2004, 10, 15), 'period 1', activity1)
        assert e1 != e3
        assert not (e1 == e3)

        e4 = TimetableException(date(2004, 10, 14), 'period 2', activity1)
        assert e1 != e4
        assert not (e1 == e4)

        e5 = TimetableException(date(2004, 10, 14), 'period 1', activity2)
        assert e1 != e5
        assert not (e1 == e5)

        e6 = TimetableException(date(2004, 10, 14), 'period 1', activity1)
        e6.replacement = ExceptionalTTCalendarEvent(date(2004, 10, 14),
                                                    timedelta(45),
                                                    "Math",
                                                    exception=e6)
        assert e1 != e6
        assert not (e1 == e6)


class TestTimetablingPersistence(unittest.TestCase):
    """A functional test for timetables persistence."""

    def setUp(self):
        from ZODB.DB import DB
        from ZODB.MappingStorage import MappingStorage
        self.db = DB(MappingStorage())
        self.datamgr = self.db.open()

    def test(self):
        from schooltool.timetable import Timetable, TimetableDay
        from schooltool.timetable import TimetableActivity
        import transaction
        tt = Timetable(('A', 'B'))
        self.datamgr.root()['tt'] = tt
        transaction.commit()

        periods = ('Green', 'Blue')
        tt["A"] = TimetableDay(periods)
        tt["B"] = TimetableDay(periods)
        transaction.commit()

        try:
            datamgr = self.db.open()
            tt2 = datamgr.root()['tt']
            self.assert_(tt2["A"].periods, periods)
            self.assert_(tt2["B"].periods, periods)
        finally:
            transaction.abort()
            datamgr.close()

        tt["A"].add("Green", TimetableActivity("English"))
        tt["A"].add("Blue", TimetableActivity("Math"))
        tt["B"].add("Green", TimetableActivity("Biology"))
        tt["B"].add("Blue", TimetableActivity("Geography"))
        transaction.commit()

        self.assertEqual(len(list(tt["A"]["Green"])), 1)
        self.assertEqual(len(list(tt["A"]["Blue"])), 1)
        self.assertEqual(len(list(tt["B"]["Green"])), 1)
        self.assertEqual(len(list(tt["B"]["Blue"])), 1)

        try:
            datamgr = self.db.open()
            tt3 = datamgr.root()['tt']
            self.assertEqual(len(list(tt3["A"]["Green"])), 1)
            self.assertEqual(len(list(tt3["A"]["Blue"])), 1)
            self.assertEqual(len(list(tt3["B"]["Green"])), 1)
            self.assertEqual(len(list(tt3["B"]["Blue"])), 1)
            act = iter(tt3["B"]["Blue"]).next()
            self.assertEqual(act.title, "Geography")
        finally:
            transaction.abort()
            datamgr.close()

    def testTimetableActivity(self):
        from schooltool.timetable import TimetableActivity
        from schooltool.interfaces import IContainmentRoot
        import transaction
        from schooltool.model import Person, Resource

        parent = PersistentLocatableStub()
        directlyProvides(parent, IContainmentRoot)
        owner = Person()
        owner.__parent__ = parent
        owner.__name__ = 'parent'
        res1 = Resource()
        res1.__parent__ = parent
        res1.__name__ = 'res1'
        res2 = Resource()
        res2.__parent__ = parent
        res2.__name__ = 'res2'
        ta = TimetableActivity("Pickling", owner, [res1, res2])
        tb = TimetableActivity("Pickling", owner, [res2, res1])
        tseta = Set([ta, tb])
        tsetb = Set([ta, tb])
        self.datamgr.root()['ta'] = ta
        self.datamgr.root()['tb'] = tb
        self.datamgr.root()['tseta'] = tseta
        self.datamgr.root()['tsetb'] = tsetb
        transaction.commit()

        try:
            datamgr = self.db.open()
            ta2 = datamgr.root()['ta']
            tb2 = datamgr.root()['tb']
            tseta2 = datamgr.root()['tseta']
            tsetb2 = datamgr.root()['tsetb']
            self.assertEqual(ta2, tb2)
            self.assertEqual(hash(ta2), hash(tb2))
            self.assertEqual(tseta2, tsetb2)
            ## Activities unpersisted in different DB connections are not
            ## supposed to be compared
            #self.assertEqual(ta, ta2)
            self.assertEqual(hash(ta), hash(ta2))
            #self.assertEqual(tset, tset2)
        finally:
            transaction.abort()
            datamgr.close()


class TestTimetableCalendarEvent(unittest.TestCase):

    def test(self):
        from schooltool.timetable import TimetableCalendarEvent
        from schooltool.interfaces import ITimetableCalendarEvent

        period_id = 'Mathematics'
        activity = object()

        ev = TimetableCalendarEvent(date(2004, 10, 13), timedelta(45), "Math",
                                    period_id=period_id, activity=activity)
        verifyObject(ITimetableCalendarEvent, ev)
        for attr in ['period_id', 'activity']:
            self.assertRaises(AttributeError, setattr, ev, attr, object())


class TestExceptionalTTCalendarEvent(unittest.TestCase):

    def test(self):
        from schooltool.timetable import ExceptionalTTCalendarEvent
        from schooltool.timetable import TimetableException
        from schooltool.interfaces import IExceptionalTTCalendarEvent

        period_id = 'Mathematics'
        activity = object()
        exc = TimetableException(date(2004, 10, 12), 123, activity)
        ev = ExceptionalTTCalendarEvent(date(2004, 10, 13), timedelta(45),
                                        "Math", exception=exc)
        verifyObject(IExceptionalTTCalendarEvent, ev)
        self.assert_(ev.exception is exc)

        exc.replacement = ev

        self.assertRaises(AttributeError, setattr, ev, 'exception', object())
        self.assertRaises(ValueError, ExceptionalTTCalendarEvent,
                          date(2004, 10, 13), timedelta(45), "Math",
                          exception=object())


class TestSchooldayPeriod(unittest.TestCase):

    def test(self):
        from schooltool.timetable import SchooldayPeriod
        from schooltool.interfaces import ISchooldayPeriod

        ev = SchooldayPeriod("1", time(9, 00), timedelta(minutes=45))
        verifyObject(ISchooldayPeriod, ev)
        self.assertEqual(ev.title, "1")
        self.assertEqual(ev.tstart, time(9,0))
        self.assertEqual(ev.duration, timedelta(seconds=2700))

    def test_eq(self):
        from schooltool.timetable import SchooldayPeriod
        self.assertEqual(
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=45)),
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=45)))
        self.assertEqual(
            hash(SchooldayPeriod("1", time(9, 0), timedelta(minutes=45))),
            hash(SchooldayPeriod("1", time(9, 0), timedelta(minutes=45))))
        self.assertNotEqual(
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=45)),
            SchooldayPeriod("2", time(9, 00), timedelta(minutes=45)))
        self.assertNotEqual(
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=45)),
            SchooldayPeriod("1", time(9, 01), timedelta(minutes=45)))
        self.assertNotEqual(
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=45)),
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=90)))
        self.assertNotEqual(
            SchooldayPeriod("1", time(9, 00), timedelta(minutes=45)),
            object())


class TestSchooldayTemplate(unittest.TestCase):

    def test_interface(self):
        from schooltool.timetable import SchooldayTemplate
        from schooltool.interfaces import ISchooldayTemplate
        from schooltool.interfaces import ISchooldayTemplateWrite

        tmpl = SchooldayTemplate()
        verifyObject(ISchooldayTemplate, tmpl)
        verifyObject(ISchooldayTemplateWrite, tmpl)

    def test_add_remove_iter(self):
        from schooltool.timetable import SchooldayTemplate, SchooldayPeriod

        tmpl = SchooldayTemplate()
        self.assertEqual(list(iter(tmpl)), [])
        self.assertRaises(TypeError, tmpl.add, object())

        lesson1 = SchooldayPeriod("1", time(9, 0), timedelta(minutes=45))
        lesson2 = SchooldayPeriod("2", time(10, 0), timedelta(minutes=45))

        tmpl.add(lesson1)
        self.assertEqual(list(iter(tmpl)), [lesson1])

        # Adding the same thing again.
        tmpl.add(lesson1)
        self.assertEqual(list(iter(tmpl)), [lesson1])

        tmpl.add(lesson2)
        self.assertEqual(len(list(iter(tmpl))), 2)
        tmpl.remove(lesson1)
        self.assertEqual(list(iter(tmpl)), [lesson2])

    def test_eq(self):
        from schooltool.timetable import SchooldayTemplate, SchooldayPeriod

        tmpl = SchooldayTemplate()
        tmpl.add(SchooldayPeriod("1", time(9, 0), timedelta(minutes=45)))
        tmpl.add(SchooldayPeriod("2", time(10, 0), timedelta(minutes=45)))

        tmpl2 = SchooldayTemplate()
        tmpl2.add(SchooldayPeriod("1", time(9, 0), timedelta(minutes=45)))
        tmpl2.add(SchooldayPeriod("2", time(10, 0), timedelta(minutes=45)))

        self.assertEqual(tmpl, tmpl)
        self.assertEqual(tmpl, tmpl2)
        self.assert_(not tmpl != tmpl2)


class SchooldayModelStub:

    implements(ISchooldayModel)

    #     November 2003
    #  Su Mo Tu We Th Fr Sa
    #                     1
    #   2  3  4  5  6  7  8
    #   9 10 11 12 13 14 15
    #  16 17 18 19<20-21>22
    #  23<24-25-26>27 28 29
    #  30

    first = date(2003, 11, 20)
    last = date(2003, 11, 26)

    def __iter__(self):
        return iter((date(2003, 11, 20),
                     date(2003, 11, 21),
                     date(2003, 11, 22),
                     date(2003, 11, 23),
                     date(2003, 11, 24),
                     date(2003, 11, 25),
                     date(2003, 11, 26)))

    def isSchoolday(self, day):
        return day in (date(2003, 11, 20),
                       date(2003, 11, 21),
                       date(2003, 11, 24),
                       date(2003, 11, 25),
                       date(2003, 11, 26))

    def __contains__(self, day):
        return date(2003, 11, 20) <= day <= date(2003, 11, 26)


class BaseTestTimetableModel:

    def extractCalendarEvents(self, cal, daterange):
        result = []
        for d in daterange:
            calday = cal.byDate(d)
            events = []
            for event in calday:
                events.append(event)
            result.append(dict([(event.dtstart, event.title)
                           for event in events]))
        return result


class TestSequentialDaysTimetableModel(NiceDiffsMixin, RegistriesSetupMixin,
                                       unittest.TestCase,
                                       BaseTestTimetableModel):
                                       

    def test_interface(self):
        from schooltool.timetable import SequentialDaysTimetableModel
        from schooltool.interfaces import ITimetableModel

        model = SequentialDaysTimetableModel(("A","B"), {None: 3})
        verifyObject(ITimetableModel, model)

    def test_eq(self):
        from schooltool.timetable import SequentialDaysTimetableModel
        from schooltool.timetable import WeeklyTimetableModel
        model = SequentialDaysTimetableModel(("A","B"), {1: 2, None: 3})
        model2 = SequentialDaysTimetableModel(("A","B"), {1: 2, None: 3})
        model3 = WeeklyTimetableModel(("A","B"), {1: 2, None: 3})
        model4 = SequentialDaysTimetableModel(("A"), {1: 2, None: 3})

        self.assertEqual(model, model2)
        self.assertNotEqual(model2, model3)
        self.assertNotEqual(model2, model4)
        self.assert_(not model2 != model)

    def createTimetable(self):
        """Create a simple timetable.

              Period | Day A    Day B
              ------ : -------  ---------
              Green  : English  Biology
              Blue   : Math     Geography

        """
        from schooltool.timetable import Timetable, TimetableDay
        from schooltool.timetable import TimetableActivity
        from schooltool.component import getOptions
        tt = Timetable(('A', 'B'))
        setPath(tt, '/path/to/tt')
        getOptions(tt).timetable_privacy = 'public'
        periods = ('Green', 'Blue')
        tt["A"] = TimetableDay(periods)
        tt["B"] = TimetableDay(periods)
        tt["A"].add("Green", TimetableActivity("English"))
        tt["A"].add("Blue", TimetableActivity("Math"))
        tt["B"].add("Green", TimetableActivity("Biology"))
        tt["B"].add("Blue", TimetableActivity("Geography"))
        return tt

    def createModel(self):
        """Create a simple sequential timetable model.

        Days A and B are alternated.

        Green period occurs at 9:00-10:30 on all days.
        Blue period occurs at 11:00-12:30 on all days except Fridays, when it
        occurs at 10:30-12:00.
        """
        from schooltool.timetable import SchooldayTemplate, SchooldayPeriod
        from schooltool.timetable import SequentialDaysTimetableModel

        t, td = time, timedelta
        template1 = SchooldayTemplate()
        template1.add(SchooldayPeriod('Green', t(9, 0), td(minutes=90)))
        template1.add(SchooldayPeriod('Blue', t(11, 0), td(minutes=90)))
        template2 = SchooldayTemplate()
        template2.add(SchooldayPeriod('Green', t(9, 0), td(minutes=90)))
        template2.add(SchooldayPeriod('Blue', t(10, 30), td(minutes=90)))

        model = SequentialDaysTimetableModel(("A", "B"),
                                             {None: template1,
                                              calendar.FRIDAY: template2})
        return model

    def test_createCalendar(self):
        from schooltool.interfaces import ICalendar

        tt = self.createTimetable()
        model = self.createModel()
        schooldays = SchooldayModelStub()

        cal = model.createCalendar(schooldays, tt)
        verifyObject(ICalendar, cal)

        # The calendar is functionally derived, therefore everything
        # in it (including unique calendar event IDs) must not change
        # if it is regenerated.
        cal2 = model.createCalendar(schooldays, tt)
        self.assertEquals(cal.events, cal2.events)

        result = self.extractCalendarEvents(cal, schooldays)

        expected = [{datetime(2003, 11, 20, 9, 0): "English",
                     datetime(2003, 11, 20, 11, 0): "Math"},
                    {datetime(2003, 11, 21, 9, 0): "Biology",
                     datetime(2003, 11, 21, 10, 30): "Geography"},
                    {}, {},
                    {datetime(2003, 11, 24, 9, 0): "English",
                     datetime(2003, 11, 24, 11, 0): "Math"},
                    {datetime(2003, 11, 25, 9, 0): "Biology",
                     datetime(2003, 11, 25, 11, 0): "Geography"},
                    {datetime(2003, 11, 26, 9, 0): "English",
                     datetime(2003, 11, 26, 11, 0): "Math"}]

        self.assertEqual(expected, result,
                         diff(pformat(expected), pformat(result)))

    def test_createCalendar_with_exceptions(self):
        from schooltool.timetable import TimetableException
        from schooltool.timetable import ExceptionalTTCalendarEvent
        from schooltool.timetable import TimetableActivity
        tt = self.createTimetable()
        tt.exceptions.append(
                TimetableException(date=date(2003, 11, 24),
                                   period_id='Blue',
                                   activity=TimetableActivity("Math")))

        exc = TimetableException(date=date(2003, 11, 26),
                                 period_id='Green',
                                 activity=TimetableActivity("English"))
        exc.replacement = ExceptionalTTCalendarEvent(
                                      datetime(2003, 11, 26, 9, 30),
                                      timedelta(minutes=60),
                                      "English (short)",
                                      exception=exc)
        tt.exceptions.append(exc)

        model = self.createModel()
        schooldays = SchooldayModelStub()
        cal = model.createCalendar(schooldays, tt)
        result = self.extractCalendarEvents(cal, schooldays)

        expected = [{datetime(2003, 11, 20, 9, 0): "English",
                     datetime(2003, 11, 20, 11, 0): "Math"},
                    {datetime(2003, 11, 21, 9, 0): "Biology",
                     datetime(2003, 11, 21, 10, 30): "Geography"},
                    {}, {},
                    {datetime(2003, 11, 24, 9, 0): "English",
                     # Exception:
                     #   datetime(2003, 11, 24, 11, 0): "Math"
                     # disappears
                    },
                    {datetime(2003, 11, 25, 9, 0): "Biology",
                     datetime(2003, 11, 25, 11, 0): "Geography"},
                    {# Exception:
                     #  datetime(2003, 11, 26, 9, 0): "English",
                     # becomes
                     datetime(2003, 11, 26, 9, 30): "English (short)",
                     datetime(2003, 11, 26, 11, 0): "Math"}]

        self.assertEqual(expected, result,
                         diff(pformat(expected), pformat(result)))

    def test_periodsInDay(self):
        from schooltool.interfaces import ICalendar
        from schooltool.timetable import SchooldayPeriod

        tt = self.createTimetable()
        model = self.createModel()
        schooldays = SchooldayModelStub()

        cal = model.createCalendar(schooldays, tt)
        verifyObject(ICalendar, cal)

        self.assertEqual(
            model.periodsInDay(schooldays, tt, date(2003, 11, 20)),
            [SchooldayPeriod("Green", time(9, 0), timedelta(minutes=90)),
             SchooldayPeriod("Blue", time(11, 0), timedelta(minutes=90))])

        self.assertEqual(
            model.periodsInDay(schooldays, tt, date(2003, 11, 21)),
            [SchooldayPeriod("Green", time(9, 0), timedelta(minutes=90)),
             SchooldayPeriod("Blue", time(10, 30), timedelta(minutes=90))])

        self.assertEqual(
            model.periodsInDay(schooldays, tt, date(2003, 11, 22)),
            [])


class TestWeeklyTimetableModel(RegistriesSetupMixin, unittest.TestCase,
                               BaseTestTimetableModel):

    def test(self):
        from schooltool.timetable import WeeklyTimetableModel
        from schooltool.timetable import SchooldayTemplate, SchooldayPeriod
        from schooltool.timetable import Timetable, TimetableDay
        from schooltool.timetable import TimetableActivity
        from schooltool.interfaces import ITimetableModel
        from schooltool.component import getOptions

        days = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday')
        tt = Timetable(days)
        setPath(tt, '/path/to/tt')
        getOptions(tt).timetable_privacy = 'private'

        periods = ('1', '2', '3', '4')
        for day_id in days:
            tt[day_id] = TimetableDay(periods)

        tt["Monday"].add("1", TimetableActivity("English"))
        tt["Monday"].add("2", TimetableActivity("History"))
        tt["Monday"].add("3", TimetableActivity("Biology"))
        tt["Monday"].add("4", TimetableActivity("Physics"))

        tt["Tuesday"].add("1", TimetableActivity("Geography"))
        tt["Tuesday"].add("2", TimetableActivity("Math"))
        tt["Tuesday"].add("3", TimetableActivity("English"))
        tt["Tuesday"].add("4", TimetableActivity("Music"))

        tt["Wednesday"].add("1", TimetableActivity("English"))
        tt["Wednesday"].add("2", TimetableActivity("History"))
        tt["Wednesday"].add("3", TimetableActivity("Biology"))
        tt["Wednesday"].add("4", TimetableActivity("Physics"))

        tt["Thursday"].add("1", TimetableActivity("Chemistry"))
        tt["Thursday"].add("2", TimetableActivity("English"))
        tt["Thursday"].add("3", TimetableActivity("English"))
        tt["Thursday"].add("4", TimetableActivity("Math"))

        tt["Friday"].add("1", TimetableActivity("Geography"))
        tt["Friday"].add("2", TimetableActivity("Drawing"))
        tt["Friday"].add("4", TimetableActivity("Math"))

        t, td = time, timedelta
        template = SchooldayTemplate()
        template.add(SchooldayPeriod('1', t(9, 0), td(minutes=45)))
        template.add(SchooldayPeriod('2', t(9, 50), td(minutes=45)))
        template.add(SchooldayPeriod('3', t(10, 50), td(minutes=45)))
        template.add(SchooldayPeriod('4', t(12, 0), td(minutes=45)))

        model = WeeklyTimetableModel(day_templates={None: template})
        verifyObject(ITimetableModel, model)

        cal = model.createCalendar(SchooldayModelStub(), tt)

        for event in cal:
            self.assertEqual(event.privacy, "private", event)

        result = self.extractCalendarEvents(cal, SchooldayModelStub())

        expected = [
            {datetime(2003, 11, 20, 9, 0): "Chemistry",
             datetime(2003, 11, 20, 9, 50): "English",
             datetime(2003, 11, 20, 10, 50): "English",
             datetime(2003, 11, 20, 12, 00): "Math"},
            {datetime(2003, 11, 21, 9, 0): "Geography",
             datetime(2003, 11, 21, 9, 50): "Drawing",
             # skip! datetime(2003, 11, 21, 10, 50): "History",
             datetime(2003, 11, 21, 12, 00): "Math"},
            {}, {},
            {datetime(2003, 11, 24, 9, 0): "English",
             datetime(2003, 11, 24, 9, 50): "History",
             datetime(2003, 11, 24, 10, 50): "Biology",
             datetime(2003, 11, 24, 12, 00): "Physics"},
            {datetime(2003, 11, 25, 9, 0): "Geography",
             datetime(2003, 11, 25, 9, 50): "Math",
             datetime(2003, 11, 25, 10, 50): "English",
             datetime(2003, 11, 25, 12, 00): "Music"},
            {datetime(2003, 11, 26, 9, 0): "English",
             datetime(2003, 11, 26, 9, 50): "History",
             datetime(2003, 11, 26, 10, 50): "Biology",
             datetime(2003, 11, 26, 12, 00): "Physics"},
            ]

        self.assertEqual(expected, result,
                         diff(pformat(expected), pformat(result)))

    def test_not_enough_days(self):
        from schooltool.timetable import WeeklyTimetableModel
        from schooltool.timetable import SchooldayTemplate, SchooldayPeriod
        from schooltool.timetable import Timetable, TimetableDay
        from schooltool.component import getOptions
        template = SchooldayTemplate()
        template.add(SchooldayPeriod('1', time(8), timedelta(minutes=30)))
        days = ["Mon", "Tue"]
        model = WeeklyTimetableModel(days, {None: template})
        day = date(2003, 11, 20)    # 2003-11-20 is a Thursday
        self.assert_(model.schooldayStrategy(day, None) is None)

        tt = Timetable(days)
        for day_id in days:
            tt[day_id] = TimetableDay()
        schooldays = SchooldayModelStub()
        self.assertEquals(model.periodsInDay(schooldays, tt, day), [])

        # Just make sure there are no exceptions.
        setPath(tt, '/path/to/tt')
        getOptions(tt).timetable_privacy = 'private'
        model.createCalendar(schooldays, tt)


class TimetabledStub(TimetabledMixin, RelatableMixin,
                     LocatableEventTargetMixin, FacetedMixin):

    def __init__(self, parent):
        RelatableMixin.__init__(self)
        TimetabledMixin.__init__(self)
        LocatableEventTargetMixin.__init__(self, parent)
        FacetedMixin.__init__(self)


class PersistentLocatableStub(Persistent):
    implements(ILocation)
    __name__ = None
    __parent__ = None


class TestTimetableDict(EventServiceTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpEventService()

    def test(self):
        from schooltool.timetable import TimetableDict
        from persistent.dict import PersistentDict
        from schooltool.interfaces import ILocation, IEventTarget

        timetables = TimetableDict()
        self.assert_(isinstance(timetables, PersistentDict))
        verifyObject(ILocation, timetables)
        verifyObject(IEventTarget, timetables)

    def test_notify(self):
        from schooltool.timetable import TimetableDict
        from schooltool.interfaces import IEventTarget

        class EventStub:
            def __init__(self):
                self.dispatched_to = []
            def dispatch(self, target):
                self.dispatched_to.append(target)

        class EventTargetStub:
            implements(IEventTarget)

        e = EventStub()
        timetables = TimetableDict()
        timetables.notify(e)
        self.assertEquals(e.dispatched_to, [])

        timetables.__parent__ = EventTargetStub()
        timetables.notify(e)
        self.assertEquals(e.dispatched_to, [timetables.__parent__])

    def test_setitem_delitem(self):
        from schooltool.timetable import TimetableDict

        td = TimetableDict()
        item = PersistentLocatableStub()
        td['aa', 'bb'] = item
        self.assertEqual(item.__name__, ('aa', 'bb'))
        self.assertEqual(item.__parent__, td)
        self.assertEqual(item, td['aa', 'bb'])

        item2 = PersistentLocatableStub()
        td['aa', 'bb'] = item2
        self.assertEqual(item2, td['aa', 'bb'])
        self.assertEqual(item.__parent__, None)
        self.assertEqual(item.__name__, None)

        del td['aa', 'bb']
        self.assertRaises(KeyError, td.__getitem__, ('aa', 'bb'))
        self.assertEqual(item2.__parent__, None)
        self.assertEqual(item2.__name__, None)

    def test_setitem_delitem_events(self):
        from schooltool.timetable import TimetableDict
        from schooltool.interfaces import ITimetableReplacedEvent

        td = TimetableDict()
        td.__parent__ = self.eventService
        item = PersistentLocatableStub()
        td['aa', 'bb'] = item
        e = self.checkOneEventReceived()
        self.assert_(ITimetableReplacedEvent.providedBy(e))
        self.assert_(e.object is td.__parent__)
        self.assertEquals(e.key, ('aa', 'bb'))
        self.assert_(e.old_timetable is None)
        self.assert_(e.new_timetable is item)

        self.eventService.clearEvents()
        item2 = PersistentLocatableStub()
        td['aa', 'bb'] = item2
        e = self.checkOneEventReceived()
        self.assert_(ITimetableReplacedEvent.providedBy(e))
        self.assert_(e.object is td.__parent__)
        self.assertEquals(e.key, ('aa', 'bb'))
        self.assert_(e.old_timetable is item)
        self.assert_(e.new_timetable is item2)

        self.eventService.clearEvents()
        del td['aa', 'bb']
        e = self.checkOneEventReceived()
        self.assert_(ITimetableReplacedEvent.providedBy(e))
        self.assert_(e.object is td.__parent__)
        self.assertEquals(e.key, ('aa', 'bb'))
        self.assert_(e.old_timetable is item2)
        self.assert_(e.new_timetable is None)

    def test_clear(self):
        from schooltool.timetable import TimetableDict
        td = TimetableDict()
        td.__parent__ = self.eventService
        td['a', 'b'] = PersistentLocatableStub()
        td['b', 'c'] = PersistentLocatableStub()
        self.eventService.clearEvents()
        td.clear()
        self.assertEquals(td.keys(), [])
        self.assertEquals(len(self.eventService.events), 2)


class TestTimetabledMixin(RegistriesSetupMixin, EventServiceTestMixin,
                          NiceDiffsMixin, unittest.TestCase,
                          EqualsSortedMixin):

    def setUp(self):
        self.setUpRegistries()
        self.setUpEventService()

    def tearDown(self):
        self.tearDownRegistries()

    def test_interface(self):
        from schooltool.interfaces import ITimetabled
        from schooltool.timetable import TimetabledMixin, TimetableDict

        tm = TimetabledMixin()
        verifyObject(ITimetabled, tm)
        self.assert_(isinstance(tm.timetables, TimetableDict))
        self.assertEqual(tm.timetables.__parent__, tm)

    def newTimetable(self):
        from schooltool.timetable import Timetable, TimetableDay
        tt = Timetable(("A", "B"))
        tt.exceptions.extend(['exc1', 'exc2'])
        tt["A"] = TimetableDay(("Green", "Blue"))
        tt["B"] = TimetableDay(("Green", "Blue"))
        return tt

    def test_composite_table_own(self):
        tm = TimetabledStub(self.eventService)
        self.assertEqual(tm.timetables, {})
        self.assertEqual(tm.getCompositeTimetable("a", "b"), None)
        self.assertEqual(tm.listCompositeTimetables(), Set())

        tt = tm.timetables["2003 fall", "sequential"] = self.newTimetable()

        result = tm.getCompositeTimetable("2003 fall", "sequential")
        self.assertEqual(result, tt)
        self.assert_(result is not tt)

        self.assertEqual(tm.listCompositeTimetables(),
                         Set([("2003 fall", "sequential")]))

    def test_composite_table_related(self):
        from schooltool.timetable import TimetableActivity
        from schooltool.membership import Membership
        from schooltool.uris import URIGroup
        import schooltool.membership

        schooltool.membership.setUp()

        tm = TimetabledStub(self.eventService)
        parent = TimetabledStub(self.eventService)
        Membership(group=parent, member=tm)

        composite = self.newTimetable()
        english = TimetableActivity("English")
        composite["A"].add("Green", english)

        def newComposite(period_id, schema_id):
            if (period_id, schema_id) == ("2003 fall", "sequential"):
                return composite
            else:
                return None

        def listComposites():
            return Set([("2003 fall", "sequential")])

        parent.getCompositeTimetable = newComposite
        parent.listCompositeTimetables = listComposites

        tm.timetableSource = ((URIGroup, False), )
        result = tm.getCompositeTimetable("2003 fall", "sequential")
        self.assert_(result is None)
        self.assertEqual(tm.listCompositeTimetables(), Set())

        tm.timetableSource = ((URIGroup, True), )
        result = tm.getCompositeTimetable("2003 fall", "sequential")
        self.assertEqual(result, composite)
        self.assert_(result is not composite)
        self.assertEqual(tm.listCompositeTimetables(),
                         Set([("2003 fall", "sequential")]))

        # Now test with our object having a private timetable
        private = self.newTimetable()
        math = TimetableActivity("Math")
        private["B"].add("Blue", math)
        tm.timetables["2003 fall", "sequential"] = private

        result = tm.getCompositeTimetable("2003 fall", "sequential")
        expected = composite.cloneEmpty()
        expected.update(composite)
        expected.update(private)
        self.assertEqual(result, expected)
        self.assertEqual(tm.listCompositeTimetables(),
                         Set([("2003 fall", "sequential")]))

        # Now test things with a table which says (URIGroup, False)
        tm.timetableSource = ((URIGroup, False), )

        parent_private = self.newTimetable()
        french = TimetableActivity("French")
        parent_private["A"].add("Green", french)
        parent.timetables["2003 fall", "sequential"] = parent_private

        result = tm.getCompositeTimetable("2003 fall", "sequential")
        expected = composite.cloneEmpty()
        expected.update(private)
        expected.update(parent_private)
        self.assertEqual(result, expected)
        self.assertEqual(Set(result["B"]["Blue"]), Set([math]))
        self.assertEqual(Set(result["A"]["Green"]), Set([french]))
        self.assertEqual(tm.listCompositeTimetables(),
                         Set([("2003 fall", "sequential")]))

    def test_getCompositeTable_facets(self):
        from schooltool.timetable import TimetableActivity
        from schooltool.component import FacetManager
        from schooltool.interfaces import IFacet, ICompositeTimetableProvider
        from schooltool.teaching import Teaching
        from schooltool.uris import URITaught
        import schooltool.relationship

        schooltool.relationship.setUp()

        class TeacherFacet(Persistent):
            implements(IFacet, ICompositeTimetableProvider)
            __parent__ = None
            __name__ = None
            active = False
            owner = None
            timetableSource = ((URITaught, False), )

        teacher = TimetabledStub(self.eventService)
        taught = TimetabledStub(self.eventService)
        Teaching(teacher=teacher, taught=taught)

        facets = FacetManager(teacher)
        facets.setFacet(TeacherFacet())

        tt = self.newTimetable()
        taught.timetables['2003 fall', 'sequential'] = tt
        stuff = TimetableActivity("Stuff")
        tt["A"].add("Green", stuff)

        result = teacher.getCompositeTimetable('2003 fall', 'sequential')
        self.assertEqual(result, tt)

    def test_paths(self):
        from schooltool.component import getPath

        tm = TimetabledStub(self.eventService)
        tm.__name__ = 'stub'
        tt = tm.timetables["2003-fall", "sequential"] = self.newTimetable()
        tt1 = tm.getCompositeTimetable("2003-fall", "sequential")

        self.assertEqual(getPath(tt),
                         '/stub/timetables/2003-fall/sequential')
        self.assertEqual(getPath(tt1),
                         '/stub/composite-timetables/2003-fall/sequential')

    def test_makeTimetableCalendar(self):
        from schooltool.timetable import TimetableActivity
        from schooltool.cal import Calendar, CalendarEvent
        tps = self.serviceManager.timePeriodService = {}
        sms = tps['2003 fall'] = SchooldayModelStub()
        tss = self.serviceManager.timetableSchemaService = {}
        tss['sequential'] = None
        tss['other'] = None
        tss['and another'] = None
        tm = TimetabledStub(self.serviceManager)

        tt1 = self.newTimetable()
        tt1["A"].add("Green", TimetableActivity("AG"))
        cal1 = Calendar()
        ev1 = CalendarEvent(datetime(2003, 11, 26, 12, 00),
                            timedelta(minutes=30), "AG")
        cal1.addEvent(ev1)

        tt2 = self.newTimetable()
        tt2["A"].add("Blue", TimetableActivity("AB"))
        cal2 = Calendar()
        ev2 = CalendarEvent(datetime(2003, 11, 26, 13, 00),
                            timedelta(minutes=30), "AB")
        cal2.addEvent(ev2)

        ttdict = {("2003 fall", "sequential"): tt1,
                  ("2003 fall", "other"): tt2}
        tm.getCompositeTimetable = lambda p, s: ttdict.get((p, s))
        tm.listCompositeTimetables = ttdict.keys

        class TimetableModelStub:
            def createCalendar(this_self, schoolday_model, tt):
                self.assert_(schoolday_model is sms)
                if tt is tt1:
                    return cal1
                elif tt is tt2:
                    return cal2
                else:
                    self.fail("what is %r?" % tt)

        tt1.model = TimetableModelStub()
        tt2.model = TimetableModelStub()
        cal = tm.makeTimetableCalendar()
        self.assertEqualSorted(list(cal), list(cal1) + list(cal2))
        self.assert_(cal.__parent__ is tm)


class TestTimetableSchemaService(unittest.TestCase):

    def test_interface(self):
        from schooltool.timetable import TimetableSchemaService
        from schooltool.interfaces import ITimetableSchemaService

        service = TimetableSchemaService()
        verifyObject(ITimetableSchemaService, service)

    def test(self):
        from schooltool.timetable import TimetableSchemaService
        from schooltool.timetable import Timetable, TimetableDay
        from schooltool.timetable import TimetableActivity

        service = TimetableSchemaService()
        self.assertEqual(service.keys(), [])

        tt = Timetable(("A", "B"))
        tt["A"] = TimetableDay(("Green", "Blue"))
        tt["B"] = TimetableDay(("Red", "Yellow"))
        tt["A"].add("Green", TimetableActivity("Slacking"))
        self.assertEqual(len(list(tt["A"]["Green"])), 1)

        service["super"] = tt
        self.assertEqual(service.keys(), ["super"])
        self.assertEqual(service["super"].__name__, "super")
        self.assert_(service["super"].__parent__ is service)
        self.assertEqual(service.default_id, "super")

        copy1 = service["super"]
        copy2 = service["super"]
        self.assert_(copy2 is not copy1)
        self.assertEqual(copy2, copy1)
        self.assertEqual(service.getDefault(), copy1)
        self.assertEqual(tt.cloneEmpty(), copy1)

        self.assertEqual(len(list(copy1["A"]["Green"])), 0)

        copy1["A"].add("Green", TimetableActivity("Slacking"))
        self.assertEqual(len(list(copy1["A"]["Green"])), 1)
        self.assertEqual(len(list(copy2["A"]["Green"])), 0)

        del service["super"]
        self.assertRaises(KeyError, service.__getitem__, "super")
        self.assertEqual(service.keys(), [])
        self.assertEqual(service.default_id, None)

        self.assertRaises(ValueError, setattr, service, 'default_id', 'nosuch')


class TestTimePeriodService(unittest.TestCase):

    def test_interface(self):
        from schooltool.timetable import TimePeriodService
        from schooltool.interfaces import ITimePeriodService

        service = TimePeriodService()
        verifyObject(ITimePeriodService, service)

    def test(self):
        from schooltool.timetable import TimePeriodService
        service = TimePeriodService()
        self.assertEqual(service.keys(), [])

        schooldays = SchooldayModelStub()
        service['2003 fall'] = schooldays
        self.assertEqual(service.keys(), ['2003 fall'])
        self.assert_('2003 fall' in service)
        self.assert_('2004 spring' not in service)
        self.assert_(service['2003 fall'] is schooldays)
        self.assertEquals(schooldays.__name__, '2003 fall')
        self.assert_(schooldays.__parent__ is service)

        # duplicate registration
        schooldays2 = SchooldayModelStub()
        service['2003 fall'] = schooldays2
        self.assertEqual(service.keys(), ['2003 fall'])
        self.assert_('2003 fall' in service)
        self.assert_(service['2003 fall'] is schooldays2)

        schooldays3 = SchooldayModelStub()
        service['2004 spring'] = schooldays3
        self.assertEqual(sorted(service.keys()), ['2003 fall', '2004 spring'])
        self.assert_('2004 spring' in service)
        self.assert_(service['2004 spring'] is schooldays3)

        del service['2003 fall']
        self.assertEqual(service.keys(), ['2004 spring'])
        self.assert_('2003 fall' not in service)
        self.assert_('2004 spring' in service)
        self.assertRaises(KeyError, lambda: service['2003 fall'])

        # duplicate deletion
        self.assertRaises(KeyError, service.__delitem__, '2003 fall')


class TestGetPeriodsForDay(unittest.TestCase):

    def setUp(self):
        from schooltool.interfaces import IServiceManager
        from schooltool.timetable import TimePeriodService
        from schooltool.timetable import Timetable
        from schooltool.cal import SchooldayModel
        from schooltool.timetable import TimetableSchemaService
        context = TraversableRoot()
        directlyProvides(context, IServiceManager)
        context.timePeriodService = TimePeriodService()
        self.sm1 = SchooldayModel(date(2004, 9, 1), date(2004, 12, 20))
        self.sm2 = SchooldayModel(date(2005, 1, 1), date(2005, 6, 1))
        context.timePeriodService['2004-fall'] = self.sm1
        context.timePeriodService['2005-spring'] = self.sm2
        context.timetableSchemaService = TimetableSchemaService()
        tt = Timetable([])

        class TimetableModelStub:
            def periodsInDay(self, schooldays, ttschema, date):
                return 'periodsInDay', schooldays, ttschema, date

        tt.model = TimetableModelStub()
        self.tt = tt
        context.timetableSchemaService['default'] = tt
        self.context = context

    def test_getTimePeriodForDate(self):
        from schooltool.timetable import getTimePeriodForDate
        c = self.context
        self.assert_(getTimePeriodForDate(date(2004, 8, 31), c) is None)
        self.assert_(getTimePeriodForDate(date(2004, 9, 1), c) is self.sm1)
        self.assert_(getTimePeriodForDate(date(2004, 11, 5), c) is self.sm1)
        self.assert_(getTimePeriodForDate(date(2004, 12, 20), c) is self.sm1)
        self.assert_(getTimePeriodForDate(date(2004, 12, 21), c) is None)
        self.assert_(getTimePeriodForDate(date(2005, 3, 17), c) is self.sm2)
        self.assert_(getTimePeriodForDate(date(2005, 11, 5), c) is None)

    def test_getPeriodsForDay(self):
        from schooltool.timetable import getPeriodsForDay
        # A white-box test: we delegate to ITimetableModel.periodsInDay
        # with the correct arguments
        self.assertEquals(getPeriodsForDay(date(2004, 10, 14), self.context),
                          ('periodsInDay', self.sm1, self.tt,
                           date(2004, 10, 14)))

        # However, if there is no time period, we return []
        self.assertEquals(getPeriodsForDay(date(2005, 10, 14), self.context),
                          [])

        # If there is no timetable schema, we return []
        self.context.timetableSchemaService.default_id = None
        self.assertEquals(getPeriodsForDay(date(2004, 10, 14), self.context),
                          [])


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestTimetable))
    suite.addTest(unittest.makeSuite(TestTimetableDay))
    suite.addTest(unittest.makeSuite(TestTimetableActivity))
    suite.addTest(unittest.makeSuite(TestTimetableExceptionList))
    suite.addTest(unittest.makeSuite(TestTimetableEvents))
    suite.addTest(unittest.makeSuite(TestTimetableException))
    suite.addTest(unittest.makeSuite(TestTimetablingPersistence))
    suite.addTest(unittest.makeSuite(TestTimetableCalendarEvent))
    suite.addTest(unittest.makeSuite(TestExceptionalTTCalendarEvent))
    suite.addTest(unittest.makeSuite(TestSchooldayPeriod))
    suite.addTest(unittest.makeSuite(TestSchooldayTemplate))
    suite.addTest(unittest.makeSuite(TestSequentialDaysTimetableModel))
    suite.addTest(unittest.makeSuite(TestWeeklyTimetableModel))
    suite.addTest(unittest.makeSuite(TestTimetableDict))
    suite.addTest(unittest.makeSuite(TestTimetabledMixin))
    suite.addTest(unittest.makeSuite(TestTimetableSchemaService))
    suite.addTest(unittest.makeSuite(TestTimePeriodService))
    suite.addTest(unittest.makeSuite(TestGetPeriodsForDay))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
