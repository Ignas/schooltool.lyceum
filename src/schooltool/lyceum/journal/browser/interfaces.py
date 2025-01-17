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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Lyceum journal interfaces.
"""
from zc.table.interfaces import IColumn
from zope.interface import Interface


class IIndependentColumn(Interface):
    """A marker interface for columns that render their own TD tags."""


class ISelectableColumn(IColumn):
    """A column that renders in a special way when the row gets selected."""

    def renderSelectedCell(item, formatter):
        """Render the cell for a selected row."""
