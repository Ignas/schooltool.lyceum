#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2004 Shuttleworth Foundation
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
Unit tests for schoolbell.app.browser.csvimport

$Id$
"""

import unittest

from zope.testing import doctest
from zope.publisher.browser import TestRequest

from schoolbell.app.browser.tests.setup import setUp, tearDown

__metaclass__ = type


def doctest_GroupCSVImporter():
    r"""Tests for GroupCSVImporter.

    Create a group container and an importer

        >>> from schoolbell.app.browser.csvimport import GroupCSVImporter
        >>> from schoolbell.app.app import GroupContainer
        >>> container = GroupContainer()
        >>> importer = GroupCSVImporter(container, None)

    Import some sample data

        >>> csvdata="Group 1, Group 1 Description\nGroup2, Group 2 Description"
        >>> importer.importFromCSV(csvdata)
        True

    Check that the groups exist

        >>> [group for group in container]
        [u'Group 1', u'Group2']

    Check that descriptions were imported properly

        >>> [group.description for group in container.values()]
        ['Group 1 Description', 'Group 2 Description']

    """

def doctest_BaseCSVImportView():
    r"""
    We'll create a base csv import view

        >>> from schoolbell.app.browser.csvimport import GroupCSVImportView
        >>> from schoolbell.app.app import GroupContainer
        >>> from zope.publisher.browser import TestRequest
        >>> container = GroupContainer()
        >>> request = TestRequest()

    Now we'll try a text import.  Note that the description is not required

        >>> request.form = {'csvtext' : "A Group, The best Group\nAnother Group",
        ...                 'charset' : 'UTF-8',
        ...                 'UPDATE_SUBMIT': 1}
        >>> view = GroupCSVImportView(container, request)
        >>> view.update()
        >>> [group for group in container]
        [u'A Group', u'Another Group']

    If no data is provided, we naturally get an error

        >>> request.form = {'charset' : 'UTF-8', 'UPDATE_SUBMIT': 1}
        >>> view.update()
        >>> view.errors
        [u'No data provided']

    """

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(setUp=setUp, tearDown=tearDown,
                                       optionflags=doctest.ELLIPSIS|
                                                   doctest.REPORT_NDIFF))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
