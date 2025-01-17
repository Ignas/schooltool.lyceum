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
Lyceum journal interfaces.
"""
from zope.interface import Interface
from zope.interface import Attribute


class ISectionJournalData(Interface):
    """A journal for a section."""

    section = Attribute("""Section this data belongs to.""")

    def setGrade(person, meeting, grade):
        """Set a grade for a person participating in this meeting."""

    def getGrade(person, meetgig, default=None):
        """Retrieve a grade for a person and a meeting."""

    def setAsbence(person, meeting, explained=True):
        """Mark an absence as an explained or unexplained one."""

    def getAbsence(person, meeting, default=False):
        """Retrieve the status of an absence."""

    def setDescription(meeting, description):
        """Set the description of the meeting."""

    def getDescription(meeting):
        """Retrieve the description of a meeting."""

    def recordedMeetings(person):
        """Returns a list of recorded grades/absences for a person."""


class ISectionJournal(Interface):

    section = Attribute("Section this journal belongs to.")
    members = Attribute("List of students that belong to this section or any of the adjacent.")

    def setGrade(person, meeting, grade):
        """Set a grade for a person participating in this meeting."""

    def getGrade(person, meetgig, default=None):
        """Retrieve a grade for a person and a meeting."""

    def setAsbence(person, meeting, explained=True):
        """Mark an absence as an explained or unexplained one."""

    def getAbsence(person, meeting, default=False):
        """Retrieve the status of an absence."""

    def setDescription(meeting, description):
        """Set the description of the meeting."""

    def getDescription(meeting):
        """Retrieve the description of a meeting."""

    def meetings():
        """List all possible meetings for this section."""

    def recordedMeetings(student):
        """Returns a list of recorded grades/absences for a person."""

    def hasMeeting(person, meeting):
        """Returns true if person should participate in a given meeting."""

    def findMeeting(meeting_id):
        """Returns the meeting object for this meeting id.

        The meeting might belong to any of the adjacent sections so it
        goes through all their calendars to find the meeting.
        """


class ITermGradingData(Interface):
    """Term Grades for a person."""

    def setGrade(course, term, grade):
        """Set term grade for this course."""

    def getGrade(course, term, default=None):
        """Retrieve the term grade for this course."""
