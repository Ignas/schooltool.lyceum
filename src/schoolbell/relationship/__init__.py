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
Many-to-many relationships.

See the README.txt file in this package for a detailed overview with working
code examples.
"""

from schoolbell.relationship.uri import URIObject, IURIObject       # reexport
from schoolbell.relationship.relationship import relate             # reexport
from schoolbell.relationship.relationship import getRelatedObjects  # reexport
from schoolbell.relationship.relationship import RelationshipSchema # reexport
from schoolbell.relationship.relationship import RelationshipProperty # ditto
