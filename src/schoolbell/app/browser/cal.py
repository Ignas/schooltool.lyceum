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
SchoolBell calendar views.

$Id$
"""

from datetime import datetime, date, time, timedelta
import urllib
import calendar
import sys

from zope.event import notify
from zope.app import zapi
from zope.app.event.objectevent import ObjectModifiedEvent
from zope.app.form.browser.add import AddView
from zope.app.form.browser.editview import EditView
from zope.app.form.utility import setUpWidgets
from zope.app.form.interfaces import ConversionError
from zope.app.form.interfaces import IWidgetInputError, IInputWidget
from zope.app.form.interfaces import WidgetInputError, WidgetsError
from zope.app.form.utility import getWidgetsData
from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile
from zope.app.publisher.browser import BrowserView
from zope.app.traversing.browser.absoluteurl import absoluteURL, AbsoluteURL
from zope.app.filerepresentation.interfaces import IWriteFile, IReadFile
from zope.component import queryView, queryMultiAdapter, adapts
from zope.interface import implements, Interface
from zope.publisher.interfaces.browser import IBrowserPublisher
from zope.publisher.interfaces import NotFound
from zope.schema import Date, TextLine, Choice, Int, Bool, List, Text
from zope.schema.interfaces import RequiredMissing, ConstraintNotSatisfied
from zope.app.securitypolicy.interfaces import IPrincipalPermissionManager
from zope.security.proxy import removeSecurityProxy
from zope.security.interfaces import ForbiddenAttribute
from zope.security.checker import canWrite, canAccess

from pytz import timezone

from schoolbell.app.browser import ViewPreferences
from schoolbell.app.app import getSchoolBellApplication
from schoolbell.app.cal import CalendarEvent
from schoolbell.app.interfaces import ICalendarOwner, ISchoolBellCalendarEvent
from schoolbell.app.interfaces import ISchoolBellCalendar, IPerson
from schoolbell.app.interfaces import ISchoolBellApplication
from schoolbell.app.interfaces import IPersonPreferences, IResource
from schoolbell.app.interfaces import vocabulary
from schoolbell.calendar.interfaces import ICalendar, ICalendarEvent
from schoolbell.calendar.recurrent import DailyRecurrenceRule
from schoolbell.calendar.recurrent import YearlyRecurrenceRule
from schoolbell.calendar.recurrent import MonthlyRecurrenceRule
from schoolbell.calendar.recurrent import WeeklyRecurrenceRule
from schoolbell.calendar.interfaces import IDailyRecurrenceRule
from schoolbell.calendar.interfaces import IYearlyRecurrenceRule
from schoolbell.calendar.interfaces import IMonthlyRecurrenceRule
from schoolbell.calendar.interfaces import IWeeklyRecurrenceRule
from schoolbell.calendar.utils import parse_date, parse_datetimetz
from schoolbell.calendar.utils import parse_timetz, weeknum_bounds
from schoolbell.calendar.utils import week_start, prev_month, next_month
from schoolbell.calendar.icalendar import ical_datetime
from schoolbell import SchoolBellMessageID as _

#
# Constants
#

month_names = {
    1: _("January"), 2: _("February"), 3: _("March"),
    4: _("April"), 5: _("May"), 6: _("June"),
    7: _("July"), 8: _("August"), 9: _("September"),
    10: _("October"), 11: _("November"), 12: _("December")}

day_of_week_names = {
    0: _("Monday"), 1: _("Tuesday"), 2: _("Wednesday"), 3: _("Thursday"),
    4: _("Friday"), 5: _("Saturday"), 6: _("Sunday")}

short_day_of_week_names = {
    0: _("Mon"), 1: _("Tue"), 2: _("Wed"), 3: _("Thu"),
    4: _("Fri"), 5: _("Sat"), 6: _("Sun"),
}

utc = timezone('UTC')

#
# Traversal
#

class CalendarOwnerTraverser(object):
    """A traverser that allows to traverse to a calendar owner's calendar."""

    adapts(ICalendarOwner)
    implements(IBrowserPublisher)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def publishTraverse(self, request, name):
        if name == 'calendar':
            return self.context.calendar
        elif name in ('calendar.ics', 'calendar.vfb'):
            calendar = self.context.calendar
            view = queryMultiAdapter((calendar, request), name=name)
            if view is not None:
                return view

        view = queryMultiAdapter((self.context, request), name=name)
        if view is not None:
            return view

        raise NotFound(self.context, name, request)

    def browserDefault(self, request):
        return self.context, ('index.html', )


class CalendarTraverser(object):
    """A smart calendar traverser that can handle dates in the URL."""

    adapts(ICalendarOwner)
    implements(IBrowserPublisher)

    queryMultiAdapter = staticmethod(queryMultiAdapter)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def browserDefault(self, request):
        return self.context, ('daily.html', )

    def publishTraverse(self, request, name):
        view_name = self.getViewByDate(request, name)
        if view_name:
            return self.queryMultiAdapter((self.context, request),
                                          name=view_name)

        view = queryMultiAdapter((self.context, request), name=name)
        if view is not None:
            return view

        try:
            return self.context.find(name)
        except KeyError:
            raise NotFound(self.context, name, request)

    def getViewByDate(self, request, name):
        parts = name.split('-')

        if len(parts) == 2 and parts[1].startswith('w'): # a week was given
            try:
                year = int(parts[0])
                week = int(parts[1][1:])
            except ValueError:
                return
            request.form['date'] = self.getWeek(year, week).isoformat()
            return 'weekly.html'

        # a year, month or day might have been given
        try:
            parts = [int(part) for part in parts]
        except ValueError:
            return
        if not parts:
            return
        parts = tuple(parts)

        if not (1900 < parts[0] < 2100):
            return

        if len(parts) == 1:
            request.form['date'] = "%d-01-01" % parts
            return 'yearly.html'
        elif len(parts) == 2:
            request.form['date'] = "%d-%02d-01" % parts
            return 'monthly.html'
        elif len(parts) == 3:
            request.form['date'] = "%d-%02d-%02d" % parts
            return 'daily.html'

    def getWeek(self, year, week):
        """Get the start of a week by week number.

        The Monday of the given week is returned as a datetime.date.

            >>> traverser = CalendarTraverser(None, None)
            >>> traverser.getWeek(2002, 11)
            datetime.date(2002, 3, 11)
            >>> traverser.getWeek(2005, 1)
            datetime.date(2005, 1, 3)
            >>> traverser.getWeek(2005, 52)
            datetime.date(2005, 12, 26)

        """
        return weeknum_bounds(year, week)[0]


class CalendarOwnerHTTPTraverser(object):
    """A traverser that allows to traverse to a calendar owner's calendar.

    For HTTPRequests.
    """

    adapts(ICalendarOwner)
    implements(IBrowserPublisher)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def publishTraverse(self, request, name):
        if name in ('calendar.ics', 'calendar.vfb', 'calendar'):
            return self.context.calendar

        raise NotFound(self.context, name, request)

    def browserDefault(self, request):
        return self.context, ('GET', )


class CalendarHTTPTraverser(object):
    """Traverser that allows different ways of accessing ones calendar.

    For HTTPRequest.
    """

    adapts(ISchoolBellCalendar)
    implements(IBrowserPublisher)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def publishTraverse(self, request, name):
        if name in ('calendar.ics', 'calendar.vfb'):
            return self.context

        raise NotFound(self.context, name, request)

    def browserDefault(self, request):
        return self.context, ('GET', )


#
# Calendar displaying backend
#

class EventForDisplay(object):
    """A single calendar event.

    This is a wrapper around an ICalendarEvent object.  It adds view-specific
    attributes:

        dtend -- timestamp when the event ends
        color1, color2 -- colors used for display
        shortTitle -- title truncated to ~15 characters
        cssClass - 'class' attribute for styles
        dtstarttz -- dtstart renderred in the view's timezone
        dtendtz -- dtend renderred in the view's timezone

    """

    cssClass = 'event'  # at the moment no other classes are used

    def __init__(self, event, color1, color2, source_calendar, timezone=utc):
        self.source_calendar = source_calendar
        if canAccess(source_calendar, '__iter__'):
            # Due to limitations in the default Zope 3 security policy, a
            # calendar event inherits permissions from the calendar of its
            # __parent__.  However if there's an event that books a resource,
            # and the authenticated user has schoolbell.viewCalendar access
            # for the resource's calendar, she should be able to view this
            # event when it comes from the resource's calendar.  For this
            # reason we have to remove the security proxy and check the
            # permission manually.
            event = removeSecurityProxy(event)
        self.context = event
        self.dtend = event.dtstart + event.duration
        self.color1 = color1
        self.color2 = color2
        self.shortTitle = self.title
        if len(self.title) > 16:
            self.shortTitle = self.title[:15] + '...'
        self.dtstarttz = event.dtstart.astimezone(timezone)
        self.dtendtz = self.dtend.astimezone(timezone)

    def __cmp__(self, other):
        return cmp(self.context.dtstart, other.context.dtstart)

    def __getattr__(self, name):
        return getattr(self.context, name)

    def getBooker(self):
        """If context event comes from a resource calendar - return the booker.

        Checking whether the source calendar of the event is the same
        as the parent calendar is enough, because only booked
        resources can have events with non matching parent and source.
        """
        if self.source_calendar != self.context.__parent__:
            #                    Calendar    Person
            return self.context.__parent__.__parent__
        return None

    def getBookedResources(self):
        """Return the list of booked resources.

        Only if the source calendar is not a parent calendar of the
        event.
        """
        if self.source_calendar == self.context.__parent__:
            return self.context.resources
        return ()

    def renderShort(self):
        """Short representation of the event for the monthly view."""
        if self.dtstart.date() == self.dtend.date():
            duration =  "%s&ndash;%s" % \
                    (self.dtstarttz.strftime('%H:%M'),
                     self.dtendtz.strftime('%H:%M'))
        else:
            duration =  "%s&ndash;%s" % \
                (self.dtstarttz.strftime('%b&nbsp;%d'),
                 self.dtendtz.strftime('%b&nbsp;%d'))
        return "%s (%s)" % (self.shortTitle, duration)


class CalendarDay(object):
    """A single day in a calendar.

    Attributes:
       'date'   -- date of the day (a datetime.date instance)
       'title'  -- day title, including weekday and date.
       'events' -- list of events that took place that day, sorted by start
                   time (in ascending order).
    """

    def __init__(self, date, events=None):
        if events is None:
            events = []
        self.date = date
        self.events = events
        day_of_week = day_of_week_names[date.weekday()]
        self.title = _('%s, %s') % (day_of_week, date.strftime('%Y-%m-%d'))

    def __cmp__(self, other):
        return cmp(self.date, other.date)

    def today(self):
        """Return 'today' if self.date is today, otherwise return ''."""
        return self.date == date.today() and 'today' or ''


#
# Calendar display views
#

class CalendarViewBase(BrowserView):
    """A base class for the calendar views.

    This class provides functionality that is useful to several calendar views.
    """

    __used_for__ = ISchoolBellCalendar

    # Which day is considered to be the first day of the week (0 = Monday,
    # 6 = Sunday).  Based on authenticated user preference, defaults to Monday

    def __init__(self, context, request):
        self.context = context
        self.request = request
        person = IPerson(self.request.principal, None)
        if person is not None:
            prefs = IPersonPreferences(person)

            if prefs.weekstart is not None:
                self.first_day_of_week = prefs.weekstart
            else:
                self.first_day_of_week = 0

            if prefs.timeformat == "H:MM am/pm":
                self.time_fmt = '%I:%M %p'
            else:
                self.time_fmt = '%H:%M'

            if prefs.timezone is not None:
                self.timezone = timezone(prefs.timezone)
            else:
                self.timezone = utc

            self.dateformat = prefs.dateformat

        else:
            self.first_day_of_week = 0
            self.time_fmt = '%H:%M'
            self.dateformat = 'YYYY-MM-DD'
            self.timezone = utc

    def internationalDate(self, day):
        day_of_week = day_of_week_names[day.weekday()]
        return _('%s, %s') % (day_of_week, day.strftime('%Y-%m-%d'))

    def usDate(self, day):
        day_of_week = day_of_week_names[day.weekday()]
        return _('%s, %s') % (day_of_week, day.strftime('%m/%d/%Y'))

    def longDate(self, day):
        day_of_week = day_of_week_names[day.weekday()]
        return _('%s, %s') % (day_of_week, day.strftime('%d %B, %Y'))

    def dayTitle(self, day):
        if self.dateformat == "MM/DD/YY":
            return self.usDate(day)
        elif self.dateformat == "Day Month, Year":
            return self.longDate(day)
        else:
            return self.internationalDate(day)

    __url = None

    def calURL(self, cal_type, cursor=None):
        """Construct a URL to a calendar at cursor."""
        if cursor is None:
            cursor = self.cursor
        if self.__url is None:
            self.__url = absoluteURL(self.context, self.request)

        if cal_type == 'daily':
            dt = cursor.isoformat()
        elif cal_type == 'weekly':
            dt = '%04d-w%02d' % cursor.isocalendar()[:2]
        elif cal_type == 'monthly':
            dt = cursor.strftime('%Y-%m')
        elif cal_type == 'yearly':
            dt = str(cursor.year)
        else:
            raise ValueError(cal_type)

        return '%s/%s' % (self.__url, dt)

    def update(self):
        if 'date' not in self.request:
            self.cursor = date.today()
        else:
            # It would be nice not to b0rk when the date is invalid but fall
            # back to the current date, as if the date had not been specified.
            self.cursor = parse_date(self.request['date'])

    def getWeek(self, dt):
        """Return the week that contains the day dt.

        Returns a list of CalendarDay objects.
        """
        start = week_start(dt, self.first_day_of_week)
        end = start + timedelta(7)
        return self.getDays(start, end)

    def getMonth(self, dt):
        """Return a nested list of days in the month that contains dt.

        Returns a list of lists of date objects.  Days in neighbouring
        months are included if they fall into a week that contains days in
        the current month.
        """
        weeks = []
        start_of_next_month = next_month(dt)
        start_of_week = week_start(dt.replace(day=1), self.first_day_of_week)
        while start_of_week < start_of_next_month:
            start_of_next_week = start_of_week + timedelta(7)
            weeks.append(self.getDays(start_of_week, start_of_next_week))
            start_of_week = start_of_next_week
        return weeks

    def getYear(self, dt):
        """Return the current year.

        This returns a list of quarters, each quarter is a list of months,
        each month is a list of weeks, and each week is a list of CalendarDays.
        """
        quarters = []
        for q in range(4):
            quarter = [self.getMonth(date(dt.year, month + (q * 3), 1))
                       for month in range(1, 4)]
            quarters.append(quarter)
        return quarters

    def dayEvents(self, date):
        """Return events for a day sorted by start time.

        Events spanning several days and overlapping with this day
        are included.
        """
        day = self.getDays(date, date + timedelta(1))[0]
        return day.events

    def getCalendars(self):
        """Get a list of calendars to display.

        Yields tuples (calendar, color1, color2).
        """
        yield (self.context, '#9db8d2', '#7590ae')
        user = IPerson(self.request.principal, None)
        if (user and
            removeSecurityProxy(self.context) is
            removeSecurityProxy(user.calendar)):
            for item in user.overlaid_calendars:
                if item.show and canAccess(item.calendar, '__iter__'):
                    yield (item.calendar, item.color1, item.color2)

    def getEvents(self, start_dt, end_dt):
        """Get a list of EventForDisplay objects for a selected time interval.

        `start_dt` and `end_dt` (datetime objects) are bounds (half-open) for
        the result.
        """
        my_events = []
        start_dt = start_dt.replace(tzinfo=self.timezone)
        end_dt = end_dt.replace(tzinfo=self.timezone)
        for calendar, color1, color2 in self.getCalendars():
            for event in calendar.expand(start_dt, end_dt):
                if (removeSecurityProxy(event.__parent__) is removeSecurityProxy(self.context) and
                    calendar is not self.context) or event.allday:
                    # Skip resource booking events (coming from
                    # overlayed calendars) if they were booked by the
                    # person whose calendar we are viewing.
                    # removeSecurityProxy(event.__parent__) and
                    # removeSecurityProxy(self.context) are needed so we
                    # could compare them.
                    continue
                yield EventForDisplay(event, color1, color2, calendar,
                                      self.timezone)

    def getAllDayEvents(self, date=None):
        """Get a list of EventForDisplay objects for the all-day events at the
        cursors current position.

        'day' can be None, or the day the allday events should be taken from
        """
        if not date:
            date = self.cursor
        start = datetime(date.year, date.month, date.day,
                         tzinfo=self.timezone)
        end = datetime(date.year, date.month, date.day, 23, 59,
                       tzinfo=self.timezone)
        for calendar, color1, color2 in self.getCalendars():
            for event in calendar.expand(start, end):
                # XXX removeSecurityProxy needed here
                if event.__parent__ is self.context and calendar is not \
                        self.context or not event.allday:
                    continue
                yield EventForDisplay(event, color1, color2, calendar,
                                      self.timezone)

    def getDays(self, start, end):
        """Get a list of CalendarDay objects for a selected period of time.

        `start` and `end` (date objects) are bounds (half-open) for the result.

        Events spanning more than one day get included in all days they
        overlap.
        """
        events = {}
        day = start
        while day < end:
            events[day] = []
            day += timedelta(1)

        # We have date objects, but ICalendar.expand needs datetime objects
        start_dt = datetime.combine(start, time(tzinfo=utc))
        end_dt = datetime.combine(end, time(tzinfo=utc))
        for event in self.getEvents(start_dt, end_dt):
            #  day1  day2  day3  day4  day5
            # |.....|.....|.....|.....|.....|
            # |     |  [-- event --)  |     |
            # |     |  ^  |     |  ^  |     |
            # |     |  `dtstart |  `dtend   |
            #        ^^^^^       ^^^^^
            #      first_day   last_day
            #
            # dtstart and dtend are datetime.datetime instances and point to
            # time instants.  first_day and last_day are datetime.date
            # instances and point to whole days.  Also note that [dtstart,
            # dtend) is a half-open interval, therefore
            #   last_day == dtend.date() - 1 day   when dtend.time() is 00:00
            #                                      and duration > 0
            #               dtend.date()           otherwise
            dtend = event.dtend
            first_day = event.dtstart.date()
            last_day = max(first_day, (dtend - dtend.resolution).date())
            # Loop through the intersection of two day ranges:
            #    [start, end) intersect [first_day, last_day]
            # Note that the first interval is half-open, but the second one is
            # closed.  Since we're dealing with whole days,
            #    [first_day, last_day] == [first_day, last_day + 1 day)
            day = max(start, first_day)
            limit = min(end, last_day + timedelta(1))
            while day < limit:
                events[day].append(event)
                day += timedelta(1)

        days = []
        day = start
        while day < end:
            events[day].sort()
            days.append(CalendarDay(day, events[day]))
            day += timedelta(1)
        return days

    def prevMonth(self):
        """Return the first day of the previous month."""
        return prev_month(self.cursor)

    def nextMonth(self):
        """Return the first day of the next month."""
        return next_month(self.cursor)

    def prevDay(self):
        return self.cursor - timedelta(1)

    def nextDay(self):
        return self.cursor + timedelta(1)

    def getJumpToYears(self):
        """Return jump targets for five years centered on the current year."""
        this_year = datetime.today().year
        return [{'label': year,
                 'href': self.calURL('yearly', date(year, 1, 1))}
                for year in range(this_year - 2, this_year + 3)]

    def getJumpToMonths(self):
        """Return a list of months for the drop down in the jump portlet."""
        year = self.cursor.year
        return [{'label': v,
                 'href': self.calURL('monthly', date(year, k, 1))}
                for k, v in month_names.items()]

    def monthTitle(self, date):
        return month_names[date.month]

    def renderRow(self, week, month):
        """Do some HTML rendering in Python for performance.

        This gains us 0.4 seconds out of 0.6 on my machine.
        Here is the original piece of ZPT:

         <td class="cal_yearly_day" tal:repeat="day week">
          <a tal:condition="python:day.date.month == month[1][0].date.month"
             tal:content="day/date/day"
             tal:attributes="href python:view.calURL('daily', day.date);
                             class python:(len(day.events) > 0
                                           and 'cal_yearly_day_busy'
                                           or  'cal_yearly_day')
                                        + (day.today() and ' today' or '')"/>
         </td>
        """
        result = []

        for day in week:
            result.append('<td class="cal_yearly_day">')
            if day.date.month == month:
                if len(day.events + 
                        [e for e in self.getAllDayEvents(day.date)]):
                    cssClass = 'cal_yearly_day_busy'
                else:
                    cssClass = 'cal_yearly_day'
                if day.today():
                    cssClass += ' today'
                # Let us hope that URLs will not contain < > & or "
                # This is somewhat related to
                #   http://issues.schooltool.org/issue96
                result.append('<a href="%s" class="%s">%s</a>' %
                              (self.calURL('daily', day.date), cssClass,
                               day.date.day))
            result.append('</td>')
        return "\n".join(result)


class WeeklyCalendarView(CalendarViewBase):
    """A view that shows one week of the calendar."""

    __used_for__ = ISchoolBellCalendar

    next_title = _("Next week")
    current_title = _("Current week")
    prev_title = _("Previous week")

    def title(self):
        month_name = month_names[self.cursor.month]
        args = {'month': month_name,
                'year': self.cursor.year,
                'week': self.cursor.isocalendar()[1]}
        return _('%(month)s, %(year)s (week %(week)s)') % args

    def prev(self):
        """Return the link for the previous week."""
        return self.calURL('weekly', self.cursor - timedelta(weeks=1))

    def current(self):
        """Return the link for the current week."""
        return self.calURL('weekly', date.today())

    def next(self):
        """Return the link for the next week."""
        return self.calURL('weekly', self.cursor + timedelta(weeks=1))

    def getCurrentWeek(self):
        """Return the current week as a list of CalendarDay objects."""
        return self.getWeek(self.cursor)


class AtomCalendarView(WeeklyCalendarView):
    """View the upcoming week's events in Atom formatted xml."""

    def getCurrentWeek(self):
        """Return the current week as a list of CalendarDay objects."""
        return self.getWeek(date.today())

    def w3cdtf_datetime(self, dt):
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def w3cdtf_datetime_now(self):
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")


class MonthlyCalendarView(CalendarViewBase):
    """Monthly calendar view."""

    next_title = _("Next month")
    current_title = _("Current month")
    prev_title = _("Previous month")

    def title(self):
        month_name = month_names[self.cursor.month]
        args = {'month': month_name, 'year': self.cursor.year}
        return _('%(month)s, %(year)s') % args

    def prev(self):
        """Return the link for the previous month."""
        return self.calURL('monthly', self.prevMonth())

    def current(self):
        """Return the link for the current month."""
        return self.calURL('monthly', date.today())

    def next(self):
        """Return the link for the next month."""
        return self.calURL('monthly', self.nextMonth())

    def dayOfWeek(self, date):
        return day_of_week_names[date.weekday()]

    def weekTitle(self, date):
        return _('Week %d') % date.isocalendar()[1]

    def getCurrentMonth(self):
        """Return the current month as a nested list of CalendarDays."""
        return self.getMonth(self.cursor)


class YearlyCalendarView(CalendarViewBase):
    """Yearly calendar view."""

    next_title = _("Next year")
    current_title = _("Current year")
    prev_title = _("Previous year")

    def title(self):
        return self.cursor.strftime('%Y')

    def prev(self):
        """Return the link for the previous year."""
        return self.calURL('yearly', date(self.cursor.year - 1, 1, 1))

    def current(self):
        """Return the link for the current year."""
        return self.calURL('yearly', date.today())

    def next(self):
        """Return the link for the next year."""
        return self.calURL('yearly', date(self.cursor.year + 1, 1, 1))

    def shortDayOfWeek(self, date):
        return short_day_of_week_names[date.weekday()]


class DailyCalendarView(CalendarViewBase):
    """Daily calendar view.

    The events are presented as boxes on a 'sheet' with rows
    representing hours.

    The challenge here is to present the events as a table, so that
    the overlapping events are displayed side by side, and the size of
    the boxes illustrate the duration of the events.
    """

    __used_for__ = ISchoolBellCalendar

    starthour = 8
    endhour = 19

    next_title = _("The next day")
    current_title = _("Today")
    prev_title = _("The previous day")

    def title(self):
        return self.dayTitle(self.cursor)

    def prev(self):
        """Return the link for the next day."""
        return self.calURL('daily', self.cursor - timedelta(1))

    def current(self):
        """Return the link for today."""
        return self.calURL('daily', date.today())

    def next(self):
        """Return the link for the previous day."""
        return self.calURL('daily', self.cursor + timedelta(1))

    def getColumns(self):
        """Return the maximum number of events that are overlapping.

        Extends the event so that start and end times fall on hour
        boundaries before calculating overlaps.
        """
        width = [0] * 24
        daystart = datetime.combine(self.cursor, time(tzinfo=utc))
        for event in self.dayEvents(self.cursor):
            t = daystart
            dtend = daystart + timedelta(1)
            for title, start, duration in self.calendarRows():
                if start <= event.dtstart < start + duration:
                    t = start
                if start < event.dtstart + event.duration <= start + duration:
                    dtend = start + duration
            while True:
                width[t.hour] += 1
                t += timedelta(hours=1)
                if t >= dtend:
                    break
        return max(width) or 1

    def _setRange(self, events):
        """Set the starthour and endhour attributes according to events.

        The range of the hours to display is the union of the range
        8:00-18:00 and time spans of all the events in the events
        list.
        """
        for event in events:
            start = datetime.combine(self.cursor, time(self.starthour,tzinfo=utc))
            end = (datetime.combine(self.cursor, time(tzinfo=utc)) +
                   timedelta(hours=self.endhour)) # endhour may be 24
            if event.dtstart < start:
                newstart = max(datetime.combine(self.cursor, time(tzinfo=utc)),
                               event.dtstart)
                self.starthour = newstart.hour

            if event.dtstart + event.duration > end:
                newend = min(
                    datetime.combine(self.cursor, time(tzinfo=utc)) + timedelta(1),
                    event.dtstart + event.duration + timedelta(0, 3599))
                self.endhour = newend.hour
                if self.endhour == 0:
                    self.endhour = 24

    def rowTitle(self, hour, minute):
        """Return the row title as HH:MM or H:MM am/pm."""
        return time(hour, minute).strftime(self.time_fmt)

    def calendarRows(self):
        """Iterate over (title, start, duration) of time slots that make up
        the daily calendar.
        """
        # XXX not tested
        today = datetime.combine(self.cursor, time(tzinfo=utc))
        row_ends = [today + timedelta(hours=hour + 1)
                    for hour in range(self.starthour, self.endhour)]

        start = today + timedelta(hours=self.starthour)
        for end in row_ends:
            duration = end - start
            yield (self.rowTitle(start.hour, start.minute), start, duration)
            start = end

    def getHours(self):
        """Return an iterator over the rows of the table.

        Every row is a dict with the following keys:

            'time' -- row label (e.g. 8:00)
            'cols' -- sequence of cell values for this row

        A cell value can be one of the following:
            None  -- if there is no event in this cell
            event -- if an event starts in this cell
            ''    -- if an event started above this cell

        """
        nr_cols = self.getColumns()
        events = self.dayEvents(self.cursor)
        self._setRange(events)
        slots = Slots()
        for title, start, duration in self.calendarRows():
            end = start + duration
            hour = start.hour

            # Remove the events that have already ended
            for i in range(nr_cols):
                ev = slots.get(i, None)
                if ev is not None and ev.dtstart + ev.duration <= start:
                    del slots[i]

            # Add events that start during (or before) this hour
            while (events and events[0].dtstart < end):
                event = events.pop(0)
                slots.add(event)

            cols = []
            # Format the row
            for i in range(nr_cols):
                ev = slots.get(i, None)
                if (ev is not None
                    and ev.dtstart < start
                    and hour != self.starthour):
                    # The event started before this hour (except first row)
                    cols.append('')
                else:
                    # Either None, or new event
                    cols.append(ev)

            yield {'title': title, 'cols': tuple(cols),
                   'time': start.strftime("%H:%M"),
                   # We can trust no period will be longer than a day
                   'duration': duration.seconds // 60}

    def rowspan(self, event):
        """Calculate how many calendar rows the event will take today."""
        count = 0
        for title, start, duration in self.calendarRows():
            if (start < event.dtstart + event.duration and
                event.dtstart < start + duration):
                count += 1
        return count

    def snapToGrid(self, dt):
        """Calculate the position of a datetime on the display grid.

        The daily view uses a grid where a unit (currently 'em', but that
        can be changed in the page template) corresponds to 15 minutes, and
        0 represents self.starthour.

        Clips dt so that it is never outside today's box.
        """
        dtaware = dt.replace(tzinfo=self.timezone)
        base = datetime.combine(self.cursor,
                time(tzinfo=self.timezone))
        display_start = base + timedelta(hours=self.starthour)
        display_end = base + timedelta(hours=self.endhour)
        clipped_dt = max(display_start, min(dtaware, display_end))
        td = clipped_dt - display_start
        offset_in_minutes = td.seconds / 60 + td.days * 24 * 60
        return offset_in_minutes / 15.

    def eventTop(self, event):
        """Calculate the position of the top of the event block in the display.

        See `snapToGrid`.
        """
        return self.snapToGrid(event.dtstart.astimezone(self.timezone))

    def eventHeight(self, event, minheight=3):
        """Calculate the height of the event block in the display.

        Rounds the height up to a minimum of minheight.

        See `snapToGrid`.
        """
        dtend = event.dtstart + event.duration
        return max(minheight,
                   self.snapToGrid(dtend) - self.snapToGrid(event.dtstart))

    def isResourceCalendar(self):
        """Are we showing a calendar of some resource."""

        return IResource.providedBy(self.context.__parent__)


#
# Calendar modification views
#

class EventDeleteView(BrowserView):
    """A view for deleting events."""

    __used_for__ = ISchoolBellCalendar

    def handleEvent(self):
        """Handle a request to delete an event.

        If the event is not recurrent, it is simply deleted, None is returned
        and the user is redirected to the calendar view.

        If the event being deleted is recurrent event, the request is checked
        for a command.  If one is found, it is handled, the user again is
        redirected to the calendar view.  If no commands are found in the
        request, the recurrent event is returned to be shown in the view.
        """
        event_id = self.request['event_id']
        date = parse_date(self.request['date'])

        event = self._findEvent(event_id)
        if event is None:
            # The event was not found.
            return self._redirectBack(date)

        if event.recurrence is None:
            # Bah, the event is not recurrent.  Easy!
            # XXX It shouldn't be.  We should still ask for confirmation.
            ICalendar(event).removeEvent(event)
            return self._redirectBack(date)
        else:
            # The event is recurrent, we might need to show a form.
            return self._deleteRepeatingEvent(event, date)

    def _findEvent(self, event_id):
        """Find an event that has the id event_id.

        First the event is searched for in the current calendar and then,
        overlaid calendars if any.

        If no event with the given id is found, None is returned.
        """
        try:
            return self.context.find(event_id)
        except KeyError:
            pass

        # We could not find the event in the current calendar, so we scan
        # the overlaid ones.  We only need to look if the current calendar
        # is the owner's (otherwise the overlays are not active).
        owner = IPerson(self.request.principal, None)
        if owner and owner.username == self.context.__parent__.username:
            for info in owner.overlaid_calendars:
                try:
                    return info.calendar.find(event_id)
                except KeyError:
                    pass

    def _redirectBack(self, date):
        """Redirect to the current calendar's daily view."""
        isodate = date.isoformat()
        url = '%s/%s' % (absoluteURL(self.context, self.request), isodate)
        self.request.response.redirect(url)

    def _deleteRepeatingEvent(self, event, date):
        """Delete a repeating event."""
        if 'CANCEL' in self.request:
            pass # Fall through and redirect back to the calendar.
        elif 'ALL' in self.request:
            ICalendar(event).removeEvent(event)
        elif 'FUTURE' in self.request:
            self._modifyRecurrenceRule(event, until=(date - timedelta(1)),
                                       count=None)
        elif 'CURRENT' in self.request:
            exceptions = event.recurrence.exceptions + (date, )
            self._modifyRecurrenceRule(event, exceptions=exceptions)
        else:
            return event # We don't know what to do, let's ask the user.

        # We did our job, redirect back to the calendar view.
        return self._redirectBack(date)

    def _modifyRecurrenceRule(self, event, **kwargs):
        """Modify the recurrence rule of an event.

        If the event does not have any recurrences afterwards, it is removed
        from the parent calendar
        """
        # XXX This depends on mutable events. Is this OK? -- gintas
        rrule = event.recurrence
        new_rrule = rrule.replace(**kwargs)
        # This view requires the modifyEvent permission.
        event.recurrence = removeSecurityProxy(new_rrule)
        if not event.hasOccurrences():
            ICalendar(event).removeEvent(event)


class Slots(dict):
    """A dict with automatic key selection.

    The add method automatically selects the lowest unused numeric key
    (starting from 0).

    Example:

      >>> s = Slots()
      >>> s.add("first")
      >>> s
      {0: 'first'}

      >>> s.add("second")
      >>> s
      {0: 'first', 1: 'second'}

    The keys can be reused:

      >>> del s[0]
      >>> s.add("third")
      >>> s
      {0: 'third', 1: 'second'}

    """

    def add(self, obj):
        i = 0
        while i in self:
            i += 1
        self[i] = obj


class CalendarEventView(BrowserView):
    """View for single events."""

    def __init__(self, context, request):
        self.context = context
        self.request = request

        self.preferences = ViewPreferences(request)

        self.dtstart = context.dtstart.astimezone(self.preferences.timezone)
        self.dtend = self.dtstart + context.duration
        self.start = self.dtstart.strftime(self.preferences.timeformat)
        self.end = self.dtend.strftime(self.preferences.timeformat)


class ICalendarEventAddForm(Interface):
    """Schema for event adding form."""

    title = TextLine(
        title=_("Title"),
        required=False)
    allday = Bool(
        title=_("All day"),
        required=False)
    start_date = Date(
        title=_("Date"),
        required=False)
    start_time = TextLine(
        title=_("Time"),
        required=False)

    duration = Int(
        title=_("Duration"),
        required=False,
        default=60)

    duration_type = Choice(
        title=_("Duration Type"),
        required=False,
        default="minutes",
        vocabulary=vocabulary([("minutes", _("Minutes")),
                               ("hours", _("Hours")),
                               ("days", _("Days"))]))

    location = TextLine(
        title=_("Location"),
        required=False)

    description = Text(
        title=_("Description"),
        required=False)

    # Recurrence
    recurrence = Bool(
        title=_("Recurring"),
        required=False)

    recurrence_type = Choice(
        title=_("Recurs every"),
        required=True,
        default="daily",
        vocabulary=vocabulary([("daily", _("Day")),
                               ("weekly", _("Week")),
                               ("monthly", _("Month")),
                               ("yearly", _("Year"))]))

    interval = Int(
        title=_("Repeat every"),
        required=False,
        default=1)

    range = Choice(
        title=_("Range"),
        required=False,
        default="forever",
        vocabulary=vocabulary([("count", _("Count")),
                               ("until", _("Until")),
                               ("forever", _("forever"))]))

    count = Int(
        title=_("Number of events"),
        required=False)

    until = Date(
        title=_("Repeat until"),
        required=False)

    weekdays = List(
        title=_("Weekdays"),
        required=False,
        value_type=Choice(
            title=_("Weekday"),
            vocabulary=vocabulary([(0, _("Mon")),
                                   (1, _("Tue")),
                                   (2, _("Wed")),
                                   (3, _("Thu")),
                                   (4, _("Fri")),
                                   (5, _("Sat")),
                                   (6, _("Sun"))])))

    monthly = Choice(
        title=_("Monthly"),
        default="monthday",
        required=False,
        vocabulary=vocabulary([("monthday", "md"),
                               ("weekday", "wd"),
                               ("lastweekday", "lwd")]))

    exceptions = Text(
        title=_("Exception dates"),
        required=False)


class CalendarEventViewMixin(object):
    """A mixin that holds the code common to CalendarEventAdd and Edit Views."""

    timezone = utc

    def _setError(self, name, error=RequiredMissing()):
        """Set an error on a widget."""
        # XXX Touching widget._error is bad, see
        #     http://dev.zope.org/Zope3/AccessToWidgetErrors
        # The call to setRenderedValue is necessary because
        # otherwise _getFormValue will call getInputValue and
        # overwrite _error while rendering.
        widget = getattr(self, name + '_widget')
        widget.setRenderedValue(widget._getFormValue())
        if not IWidgetInputError.providedBy(error):
            error = WidgetInputError(name, widget.label, error)
        widget._error = error

    def _requireField(self, name, errors):
        """If widget has no input, WidgetInputError is set.

        Also adds the exception to the `errors` list.
        """
        widget = getattr(self, name + '_widget')
        field = widget.context
        try:
            if widget.getInputValue() == field.missing_value:
                self._setError(name)
                errors.append(widget._error)
        except WidgetInputError, e:
            # getInputValue might raise an exception on invalid input
            errors.append(e)

    def weekdayChecked(self, weekday):
        """Return True if the given weekday should be checked.

        The weekday of start_date is always checked, others can be selected by
        the user.

        Used to format checkboxes for weekly recurrences.
        """
        return (int(weekday) in self.weekdays_widget._getFormValue() or
                self.weekdayDisabled(weekday))

    def weekdayDisabled(self, weekday):
        """Return True if the given weekday should be disabled.

        The weekday of start_date is always disabled, all others are always
        enabled.

        Used to format checkboxes for weekly recurrences.
        """
        day = self.getStartDate()
        return bool(day and day.weekday() == int(weekday))

    def getMonthDay(self):
        """Return the day number in a month, according to start_date.

        Used by the page template to format monthly recurrence rules.
        """
        evdate = self.getStartDate()
        if evdate is None:
            return '??'
        else:
            return str(evdate.day)

    def getWeekDay(self):
        """Return the week and weekday in a month, according to start_date.

        The output looks like '4th Tuesday'

        Used by the page template to format monthly recurrence rules.
        """
        evdate = self.getStartDate()
        if evdate is None:
            return _("same weekday")

        weekday = evdate.weekday()
        index = (evdate.day + 6) // 7

        indexes = {1: _('1st'), 2: _('2nd'), 3: _('3rd'), 4: _('4th'),
                   5: _('5th')}
        day_of_week = day_of_week_names[weekday]
        return "%s %s" % (indexes[index], day_of_week)

    def getLastWeekDay(self):
        """Return the week and weekday in a month, counting from the end.

        The output looks like 'Last Friday'

        Used by the page template to format monthly recurrence rules.
        """
        evdate = self.getStartDate()

        if evdate is None:
            return _("last weekday")

        lastday = calendar.monthrange(evdate.year, evdate.month)[1]

        if lastday - evdate.day >= 7:
            return None
        else:
            weekday = evdate.weekday()
            day_of_week = day_of_week_names[weekday]
            return _("Last %(weekday)s") % {'weekday': day_of_week}

    def getStartDate(self):
        """If a start_date is set returns the value of the widget."""
        try:
            return self.start_date_widget.getInputValue()
        except (WidgetInputError, ConversionError):
            return None

    def updateForm(self):
        # Just refresh the form.  It is necessary because some labels for
        # monthly recurrence rules depend on the event start date.
        self.update_status = ''
        try:
            data = getWidgetsData(self, self.schema, names=self.fieldNames)
            kw = {}
            for name in self._keyword_arguments:
                if name in data:
                    kw[str(name)] = data[name]
            self.processRequest(kw)
        except WidgetsError, errors:
            self.errors = errors
            self.update_status = _("An error occured.")
            return self.update_status
        # AddView.update() sets self.update_status and returns it.  Weird,
        # but let's copy that behavior.
        return self.update_status

    def processRequest(self, kwargs):
        """Puts informations from the widgets into a dict.

        This method performs additional validation, because Zope 3 forms aren't
        powerful enough.  If any errors are encountered, a WidgetsError is
        raised.
        """
        errors = []
        self._requireField("title", errors)
        self._requireField("start_date", errors)

        # What we require depends on weather or not we have an allday event
        allday = kwargs.pop('allday', None)
        if not allday:
            self._requireField("start_time", errors)
            self._requireField("duration", errors)

        # Remove fields not needed for makeRecurrenceRule from kwargs
        title = kwargs.pop('title', None)
        start_date = kwargs.pop('start_date', None)
        start_time = kwargs.pop('start_time', None)
        if start_time:
            try:
                start_time = parse_timetz(start_time, self.timezone)
            except ValueError:
                self._setError("start_time",
                               ConversionError(_("Invalid time")))
                errors.append(self.start_time_widget._error)
        duration = kwargs.pop('duration', None)
        duration_type = kwargs.pop('duration_type', 'minutes')
        location = kwargs.pop('location', None)
        description = kwargs.pop('description', None)
        recurrence = kwargs.pop('recurrence', None)

        if recurrence:
            self._requireField("interval", errors)
            self._requireField("recurrence_type", errors)
            self._requireField("range", errors)

            range = kwargs.get('range')
            if range == "count":
                self._requireField("count", errors)
            elif range == "until":
                self._requireField("until", errors)
                if start_date and kwargs.get('until'):
                    if kwargs['until'] < start_date:
                        self._setError("until", ConstraintNotSatisfied(
                                    _("End date is earlier than start date")))
                        errors.append(self.until_widget._error)

        exceptions = kwargs.pop("exceptions", None)
        if exceptions:
            try:
                kwargs["exceptions"] = datesParser(exceptions)
            except ValueError:
                self._setError("exceptions", ConversionError(
                 _("Invalid date.  Please specify YYYY-MM-DD, one per line.")))
                errors.append(self.exceptions_widget._error)

        if errors:
            raise WidgetsError(errors)

        # Some fake data for allday events, based on what iCalendar seems to
        # expect
        if allday is True:
            # iCalendar has no spec for describing all-day events, but it seems
            # to be the de facto standard to give them a 1d duration.
            duration = 1
            duration_type = "days"
            start_time = time(0, 0, tzinfo=utc)
            start = datetime.combine(start_date, start_time)
        else:
            start = datetime.combine(start_date, start_time).astimezone(utc)

        dargs = {duration_type : duration}
        duration = timedelta(**dargs)

        rrule = recurrence and makeRecurrenceRule(**kwargs) or None
        return {'location': location,
                'description': description,
                'title': title,
                'allday': allday,
                'start': start,
                'duration': duration,
                'rrule': rrule}


class CalendarEventAddView(CalendarEventViewMixin, AddView):
    """A view for adding an event."""

    __used_for__ = ISchoolBellCalendar
    schema = ICalendarEventAddForm

    title = _("Add event")
    submit_button_title = _("Add")

    show_book_checkbox = True
    show_book_link = False
    _event_uid = None

    error = None

    def __init__(self, context, request):

        # the default timezone 'UTC' is inherited from Mixin
        person = IPerson(request.principal, None)
        if person is not None:
            prefs = IPersonPreferences(person)
            if prefs.timezone is not None:
                self.timezone = timezone(prefs.timezone)

        if "field.start_date" not in request:
            today = date.today().strftime("%Y-%m-%d")
            request.form["field.start_date"] = today
        super(AddView, self).__init__(context, request)

    def create(self, **kwargs):
        """Create an event."""
        data = self.processRequest(kwargs)
        event = self._factory(data['start'], data['duration'], data['title'],
                              recurrence=data['rrule'],
                              location=data['location'],
                              allday=data['allday'],
                              description=data['description'])
        return event

    def add(self, event):
        """Add the event to a calendar."""
        self.context.addEvent(event)
        self._event_uid = event.unique_id
        self._redirectToDate = event.dtstart.date()
        return event

    def update(self):
        """Process the form."""
        if 'UPDATE' in self.request:
            return self.updateForm()
        elif 'CANCEL' in self.request:
            self.update_status = ''
            self.request.response.redirect(self.nextURL(date.today()))
            return self.update_status
        else:
            return AddView.update(self)

    def nextURL(self, date=None):
        """Return the URL to be displayed after the add operation.

        If the date argument is specified, the user is redirected to that
        particular day in the calendar.  Otherwise, the date is taken from
        self._redirectToDate, which is set by add() or any other method.
        # XXX A bit hacky...
        """
        if date is None:
            date = self._redirectToDate

        if "field.book" in self.request:
            return self._bookingURL(date)

        url = absoluteURL(self.context, self.request)
        return '%s/%s' % (url, date)

    def _bookingURL(self, date):
        """Returns link to the booking view of the newly created event.

        Passes the date supplied as a redirect date to the booking view.
        """

        url = absoluteURL(self.context, self.request)
        return '%s/%s/booking.html?date=%s' % (url, self._event_uid, date)


class ICalendarEventEditForm(ICalendarEventAddForm):
    pass


class CalendarEventEditView(CalendarEventViewMixin, EditView):
    """A view for editing an event."""

    error = None
    _redirectToDate = None
    show_book_checkbox = False
    show_book_link = True

    title = _("Edit event")
    submit_button_title = _("Update")

    def keyword_arguments(self):
        """Wraps fieldNames under another name.

        AddView and EditView api does not match so some wraping is needed.
        """
        return self.fieldNames

    _keyword_arguments = property(keyword_arguments, None)

    def _setUpWidgets(self):
        setUpWidgets(self, self.schema, IInputWidget, names=self.fieldNames,
                     initial=self._getInitialData(self.context))

    def _getInitialData(self, context):
        """Extracts initial widgets data from context."""

        initial = {}
        initial["title"] = context.title
        initial["allday"] = context.allday
        initial["start_date"] = context.dtstart.date()
        initial["start_time"] = context.dtstart.strftime("%H:%M")
        initial["duration"] = context.duration.seconds / 60
        initial["location"] = context.location
        initial["description"] = context.description
        recurrence = context.recurrence
        initial["recurrence"] = recurrence is not None
        if recurrence:
            initial["interval"] = recurrence.interval
            recurrence_type = (
                IDailyRecurrenceRule.providedBy(recurrence) and "daily" or
                IWeeklyRecurrenceRule.providedBy(recurrence) and "weekly" or
                IMonthlyRecurrenceRule.providedBy(recurrence) and "monthly" or
                IYearlyRecurrenceRule.providedBy(recurrence) and "yearly")

            initial["recurrence_type"] = recurrence_type
            if recurrence.until:
                initial["until"] = recurrence.until
                initial["range"] = "until"
            elif recurrence.count:
                initial["count"] = recurrence.count
                initial["range"] = "count"
            else:
                initial["range"] = "forever"

            if recurrence.exceptions:
                exceptions = map(str, recurrence.exceptions)
                initial["exceptions"] = "\n".join(exceptions)

            if recurrence_type == "weekly":
                if recurrence.weekdays:
                    initial["weekdays"] = list(recurrence.weekdays)

            if recurrence_type == "monthly":
                if recurrence.monthly:
                    initial["monthly"] = recurrence.monthly

        return initial

    def getStartDate(self):
        if "field.start_date" in self.request:
            return CalendarEventViewMixin.getStartDate(self)
        else:
            return self.context.dtstart.date()

    def applyChanges(self):
        data = getWidgetsData(self, self.schema, names=self.fieldNames)
        kw = {}
        for name in self._keyword_arguments:
            if name in data:
                kw[str(name)] = data[name]

        widget_data = self.processRequest(kw)

        parsed_date = parse_datetimetz(widget_data['start'].isoformat())
        if self.context.dtstart != parsed_date:
            self._redirectToDate = widget_data['start'].strftime("%Y-%m-%d")
        self.context.dtstart = parsed_date
        self.context.recurrence = widget_data['rrule']
        for attrname in ['allday', 'duration', 'title',
                         'location', 'description']:
            setattr(self.context, attrname, widget_data[attrname])
        return True

    def update(self):
        if self.update_status is not None:
            # We've been called before. Just return the status we previously
            # computed.
            return self.update_status

        status = ''

        start_date = self.context.dtstart.strftime("%Y-%m-%d")
        self._redirectToDate = self.request.get('date', start_date)

        if "UPDATE" in self.request:
            return self.updateForm()
        elif 'CANCEL' in self.request:
            self.update_status = ''
            self.request.response.redirect(self.nextURL())
            return self.update_status
        elif "UPDATE_SUBMIT" in self.request:
            # Replicating EditView functionality
            changed = False
            try:
                changed = self.applyChanges()
                if changed:
                    notify(ObjectModifiedEvent(self.context))
            except WidgetsError, errors:
                self.errors = errors
                status = _("An error occured.")
                get_transaction().abort()
            else:
                if changed:
                    formatter = self.request.locale.dates.getFormatter(
                        'dateTime', 'medium')
                    status = _("Updated on ${date_time}")
                    status.mapping = {'date_time': formatter.format(
                            datetime.utcnow())}
                self.request.response.redirect(self.nextURL())

        self.update_status = status
        return status

    def nextURL(self, date=None):
        """Return the URL to be displayed after the add operation.

        If the date argument is specified, the user is redirected to that
        particular day in the calendar.  Otherwise, the date is taken from
        self._redirectToDate, which is set by add() or any other method.
        # XXX A bit hacky...
        """
        if date is None:
            date = self._redirectToDate

        if "field.book" in self.request:
            return self.bookingURL(date)
        else:
            url = absoluteURL(self.context.__parent__, self.request)
            return '%s/%s' % (url, date)

    def bookingURL(self, date=None):
        """Returns link to the booking view of the newly created event.

        If a date is supplied passes it as a redirect date to the booking view
        else - passes the date that was supplied in the request.
        """
        if date is None:
            date = self._redirectToDate
        url = absoluteURL(self.context, self.request)
        return '%s/booking.html?date=%s' % (url, date)


class EventForBookingDisplay(object):
    """Event wraper for display in booking view.

    This is a wrapper around an ICalendarEvent object.  It adds view-specific
    attributes:

        dtend -- timestamp when the event ends
        shortTitle -- title truncated to ~15 characters

    """

    def __init__(self, event):
        # The event came from resource calendar yet it's parent might
        # be a calendar we don't have permission to view.
        self.context = removeSecurityProxy(event)
        self.dtstart = self.context.dtstart
        self.dtend = self.context.dtstart + self.context.duration
        self.title = self.context.title
        if len(self.title) > 16:
            # Title needs truncation.
            self.shortTitle = self.title[:15] + '...'
        else:
            self.shortTitle = self.title


class CalendarEventBookingView(BrowserView):
    """A view for booking resources."""

    errors = ()
    update_status = None
    _redirectToDate = None

    def update(self):
        """Books and unbooks resources according to the request."""
        start_date = self.context.dtstart.strftime("%Y-%m-%d")
        self._redirectToDate = self.request.get('date', start_date)

        if "UPDATE_SUBMIT" in self.request and not self.update_status:
            self.update_status = ''
            sb = getSchoolBellApplication()

            for res_id, resource in sb["resources"].items():
                if 'marker-%s' % res_id in self.request:
                    booked = self.hasBooked(resource)
                    checked = res_id in self.request
                    if booked != checked:
                        if checked:
                            # TODO: make sure the user has permission to book
                            self.context.bookResource(resource)
                        else:
                            # Always allow unbooking, even if permission to
                            # book was revoked
                            self.context.unbookResource(resource)
            self.request.response.redirect(self.nextURL())

        return self.update_status

    def _availableResources(self):
        """Gives us a list of all bookable resources."""
        sb = getSchoolBellApplication()
        resources = []
        for resource in sb["resources"].values():
            if (canAccess(resource.calendar, "addEvent") or
                self.hasBooked(resource)):
                resources.append(resource)
        return resources

    availableResources = property(_availableResources)

    def hasBooked(self, resource):
        """Checks whether a resource is booked by this event."""
        return resource in self.context.resources

    def nextURL(self):
        """Return the URL to be displayed after the add operation."""
        url = absoluteURL(self.context.__parent__, self.request)
        return '%s/%s' % (url, self._redirectToDate)

    def getConflictingEvents(self, resource):
        """Return a list of events that would conflict when booking resource."""
        events = []
        if not canAccess(resource.calendar, "expand"):
            return events

        for event in resource.calendar.expand(
            self.context.dtstart,
            self.context.dtstart + self.context.duration):
            if event != self.context:
                events.append(EventForBookingDisplay(event))
        return events


def makeRecurrenceRule(interval=None, until=None,
                       count=None, range=None,
                       exceptions=None, recurrence_type=None,
                       weekdays=None, monthly=None):
    """Return a recurrence rule according to the arguments."""
    if interval is None:
        interval = 1

    if range != 'until':
        until = None
    if range != 'count':
        count = None

    if exceptions is None:
        exceptions = ()

    kwargs = {'interval': interval, 'count': count,
              'until': until, 'exceptions': exceptions}

    if recurrence_type == 'daily':
        return DailyRecurrenceRule(**kwargs)
    elif recurrence_type == 'weekly':
        weekdays = weekdays or ()
        return WeeklyRecurrenceRule(weekdays=tuple(weekdays), **kwargs)
    elif recurrence_type == 'monthly':
        monthly = monthly or "monthday"
        return MonthlyRecurrenceRule(monthly=monthly, **kwargs)
    elif recurrence_type == 'yearly':
        return YearlyRecurrenceRule(**kwargs)
    else:
        raise NotImplementedError()


def datesParser(raw_dates):
    r"""Parse dates on separate lines into a tuple of date objects.

    Incorrect lines are ignored.

    >>> datesParser('2004-05-17\n\n\n2004-01-29')
    (datetime.date(2004, 5, 17), datetime.date(2004, 1, 29))

    >>> datesParser('2004-05-17\n123\n\nNone\n2004-01-29')
    Traceback (most recent call last):
    ...
    ValueError: Invalid date: '123'

    """
    results = []
    for dstr in raw_dates.splitlines():
        if dstr:
            d = parse_date(dstr)
            if isinstance(d, date):
                results.append(d)
    return tuple(results)


def enableVfbView(ical_view):
    """XXX wanna docstring!"""
    return IReadFile(ical_view.context)


def enableICalendarUpload(ical_view):
    """An adapter that enables HTTP PUT for calendars.

    When the user performs an HTTP PUT request on /path/to/calendar.ics,
    Zope 3 traverses to a view named 'calendar.ics' (which is most likely
    a schoolbell.calendar.browser.CalendarICalendarView).  Then Zope 3 finds an
    IHTTPrequest view named 'PUT'.  There is a standard one, that adapts
    its context (which happens to be the view named 'calendar.ics' in this
    case) to IWriteFile, and calls `write` on it.

    So, to hook up iCalendar uploads, the simplest way is to register an
    adapter for CalendarICalendarView that provides IWriteFile.

        >>> from zope.app.testing import setup, ztapi
        >>> setup.placelessSetUp()

    We have a calendar that provides IEditCalendar.

        >>> from schoolbell.calendar.interfaces import IEditCalendar
        >>> from schoolbell.app.cal import Calendar
        >>> calendar = Calendar()

    We have a fake "real adapter" for IEditCalendar

        >>> class RealAdapter:
        ...     implements(IWriteFile)
        ...     def __init__(self, context):
        ...         pass
        ...     def write(self, data):
        ...         print 'real adapter got %r' % data
        >>> ztapi.provideAdapter(IEditCalendar, IWriteFile, RealAdapter)

    We have a fake view on that calendar

        >>> from zope.app.publisher.browser import BrowserView
        >>> from zope.publisher.browser import TestRequest
        >>> view = BrowserView(calendar, TestRequest())

    And now we can hook things up together

        >>> adapter = enableICalendarUpload(view)
        >>> adapter.write('iCalendar data')
        real adapter got 'iCalendar data'

        >>> setup.placelessTearDown()

    """
    return IWriteFile(ical_view.context)


class CalendarEventAbsoluteURL(AbsoluteURL):

    def breadcrumbs(self):
        # XXX Doesn't seem to be tested.
        container = getattr(self.context, '__parent__', None)
        base = tuple(zapi.getMultiAdapter((container, self.request),
                                          name='absolute_url').breadcrumbs())
        name = urllib.quote(self.context.__name__.encode('utf-8'), "@+")
        return base + ({'name': self.context.title,
                        'url': "%s/%s/edit.html" % (base[-1]['url'], name)}, )
