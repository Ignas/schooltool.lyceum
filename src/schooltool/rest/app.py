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
The views for the schooltool.app objects.

$Id$
"""

import datetime

from zope.app.traversing.api import traverse, getPath

from zope.interface import moduleProvides
from zope.component import getUtilitiesFor
from schooltool.interfaces import IApplication, IApplicationObjectContainer
from schooltool.interfaces import IModuleSetup, IResource, IURIObject
from schooltool.component import registerView
from schooltool.rest import View, Template
from schooltool.rest import TraversableView
from schooltool.rest import notFoundPage, textErrorPage
from schooltool.rest import absoluteURL, absolutePath
from schooltool.rest import read_file
from schooltool.rest import ViewError
from schooltool.rest.timetable import SchoolTimetableTraverseView
from schooltool.rest.cal import AllCalendarsView
from schooltool.rest.csvexport import CSVExporter
from schooltool.rest.auth import PublicAccess
from schooltool.rest.applog import ApplicationLogView
from schooltool.common import parse_date
from schooltool.translation import ugettext as _
from schooltool.rest.xmlparsing import XMLDocument
from schooltool.rest.xmlparsing import XMLParseError, XMLValidationError

__metaclass__ = type


moduleProvides(IModuleSetup)


class ApplicationView(TraversableView):
    """The root view for the application."""

    template = Template("www/app.pt", content_type="text/xml")
    authorization = PublicAccess

    def _traverse(self, name, request):
        if name == 'schooltt':
            return SchoolTimetableTraverseView(self.context)
        elif name == 'calendars.html':
            return AllCalendarsView(self.context)
        elif name == 'busysearch':
            return AvailabilityQueryView(self.context)
        elif name == 'csvexport.zip':
            return CSVExporter(self.context)
        elif name == 'applog':
            return ApplicationLogView(self.context)
        elif name == 'uris':
            return UriObjectListView(self.context)
        elif name == 'options':
            return OptionsView(self.context)
        else:
            return TraversableView._traverse(self, name, request)

    def getRoots(self):
        return [{'href': absolutePath(self.request, root),
                 'title': root.title}
                for root in self.context.getRoots()]

    def getContainers(self):
        base = absolutePath(self.request, self.context)
        if not base.endswith('/'):
            base += '/'
        return [{'href': '%s%s' % (base, key), 'title': key}
                for key in self.context.keys()]

    def getUtilities(self):
        return [{'href': absolutePath(self.request, utility),
                 'title': utility.title}
                for utility in self.context.utilityService.values()]


class ApplicationObjectCreator:
    """Mixin for adding new application objects"""

    schema = '''<?xml version="1.0" encoding="UTF-8"?>
        <grammar xmlns="http://relaxng.org/ns/structure/1.0"
                 ns="http://schooltool.org/ns/model/0.1"
                 datatypeLibrary="http://www.w3.org/2001/XMLSchema-datatypes">
          <start>
            <element name="object">
              <optional>
                <attribute name="title">
                  <text/>
                </attribute>
              </optional>
            </element>
          </start>
        </grammar>
        '''

    def create(self, request, container, name=None):
        body = request.content.read()
        kw = {}
        if name is not None:
            kw['__name__'] = name
        try:
            doc = XMLDocument(body, self.schema)
        except XMLValidationError:
            return textErrorPage(request,
                                 _("Document not valid according to schema"))
        except XMLParseError:
            return textErrorPage(request, _("Document not valid XML"))

        try:
            doc.registerNs('m', 'http://schooltool.org/ns/model/0.1')
            nodes = doc.query('/*/@title')
            if nodes:
                kw['title'] = nodes[0].content
        finally:
            doc.free()
        obj = container.new(**kw)
        location = absoluteURL(request, obj)
        request.setResponseCode(201, 'Created')
        request.setHeader('Content-Type', 'text/plain')
        request.setHeader('Location', location)
        request.appLog(_("Object %s of type %s created") %
                       (getPath(obj), obj.__class__.__name__))
        return _("Object created: %s") % location


class ApplicationObjectContainerView(TraversableView,
                                     ApplicationObjectCreator):
    """A view for the application object containers."""

    template = Template("www/aoc.pt", content_type="text/xml")
    authorization = PublicAccess

    def getName(self):
        return self.context.__name__

    def items(self):
        c = self.context
        return [{'href': absolutePath(self.request, c[key]),
                 'title': c[key].title}
                for key in self.context.keys()]

    def _traverse(self, name, request):
        try:
            return TraversableView._traverse(self, name, request)
        except KeyError:
            return ApplicationObjectCreatorView(self.context, name)

    def do_POST(self, request):
        return self.create(request, self.context)


class ApplicationObjectCreatorView(View, ApplicationObjectCreator):
    """A view for non-existing application objects."""

    authorization = PublicAccess

    def __init__(self, container, name):
        View.__init__(self, container)
        self.name = name

    do_GET = staticmethod(notFoundPage)
    do_DELETE = staticmethod(notFoundPage)

    def do_PUT(self, request):
        return self.create(request, self.context, self.name)


class AvailabilityQueryView(View):
    """Busy search"""

    template = Template("www/availability.pt", content_type="text/xml")
    authorization = PublicAccess

    def do_GET(self, request):
        """Parse the query and call the template rendering.

        Required arguments in the request query string:

            ======== ============ ===========
            Name     Type         Cardinality
            ======== ============ ===========
            first    'YYYY-MM-DD' 1
            last     'YYYY-MM-DD' 1
            duration int          1
            ======== ============ ===========

        Optional arguments (if not passed, 'all' assumed):

            ========= =========== ===========
            Name      Type        Cardinality
            ========= =========== ===========
            hours     int (0..23) many
            resources str         many
            ========= =========== ===========

        """
        status = self.update()
        if status:
            return textErrorPage(request, status)
        return View.do_GET(self, request)

    def update(self):
        """Parse the request args.

        Return an error message or None if there are no errors.
        """
        request = self.request
        for arg in 'first', 'last', 'duration':
            if arg not in request.args:
                return _("%r argument must be provided") % arg
        try:
            arg = 'first'
            self.first = parse_date(request.args['first'][0])
            arg = 'last'
            self.last = parse_date(request.args['last'][0])
            arg = 'duration'
            minutes = int(request.args['duration'][0])
            self.duration = datetime.timedelta(minutes=minutes)
            arg = 'hours'
            if 'hours' not in request.args:
                self.hours = [(datetime.time(0), datetime.timedelta(hours=24))]
            else:
                self.hours = self.parseHours(request.args['hours'])
        except ValueError:
            return _("%r argument is invalid") % arg
        self.resources = []
        if 'resources' not in request.args:
            resource_container = traverse(self.context, 'resources')
            self.resources.extend(resource_container.itervalues())
        else:
            for path in request.args['resources']:
                try:
                    resource = traverse(self.context, path)
                except KeyError:
                    return _("Invalid resource: %r") % path
                if not IResource.providedBy(resource):
                    return _("%r is not a resource") % path
                self.resources.append(resource)

    def parseHours(self, hours):
        hrs = map(int, hours)
        start = None
        results = []
        for hour in range(24):
            if hour in hrs:
                if start is None:
                    start = hour
            else:
                if start is not None:
                    results.append((datetime.time(start, 0),
                                    datetime.timedelta(hours=hour-start)))
                    start = None
        if start is not None:
            results.append((datetime.time(start, 0),
                            datetime.timedelta(hours=24-start)))
        return results

    def listResources(self):
        """The logic for the template"""
        results = []
        for resource in self.resources:
            slots = resource.getFreeIntervals(self.first, self.last,
                                              self.hours, self.duration)
            if slots:
                res_slots = []
                for start, duration in slots:
                    mins = duration.days * 60 * 24 + duration.seconds / 60
                    end = start + duration
                    res_slots.append(
                        {'start': start.strftime("%Y-%m-%d %H:%M:%S"),
                         'duration': mins,
                         'end': end.strftime("%Y-%m-%d %H:%M:%S") })
                results.append({'href': absolutePath(self.request, resource),
                                'path': getPath(resource),
                                'title': resource.title,
                                'slots': res_slots})
        return results


class UriObjectListView(View):
    """A list of registered URIObjects."""

    template = Template("www/uris.pt", content_type="text/xml")
    authorization = PublicAccess

    def uriobjects(self):
        return [uriobj for uristr, uriobj in getUtilitiesFor(IURIObject)]


class OptionsView(View):
    """View for viewing/changing application options."""

    template = Template("www/options.pt", content_type="text/xml")
    schema = read_file("../schema/options.rng")
    authorization = PublicAccess

    def do_PUT(self, request):
        xml = request.content.read()
        try:
            doc = XMLDocument(xml, self.schema)
        except XMLParseError:
            return textErrorPage(request, _("Ill-formed XML document"))
        except XMLValidationError:
            return textErrorPage(request, _("Invalid XML document"))
        try:
            options = doc.query('options')[0]

            def extract(key):
                nodes = options.query(key)
                if not nodes:
                    return None
                else:
                    return nodes[0].content.strip()

            defaultTimetableSchema = extract('defaultTimetableSchema')
            if defaultTimetableSchema is not None:
                ttservice = self.context.timetableSchemaService
                if defaultTimetableSchema == "":
                    defaultTimetableSchema = None
                elif defaultTimetableSchema not in ttservice.keys():
                    raise ViewError(_("Undefined timetable schema"))
                ttservice.default_id = defaultTimetableSchema

            value = extract('newEventPrivacy')
            if value is not None:
                self.context.new_event_privacy = value

            value = extract('timetablePrivacy')
            if value is not None:
                self.context.timetable_privacy = value

            value = extract('restrictMembership')
            if value is not None:
                self.context.restrictMembership = (value.lower() == 'true')

            doc.free()
        except ViewError, e:
            doc.free()
            return textErrorPage(request, e)
        request.setResponseCode(204)
        return ""


def setUp():
    """See IModuleSetup."""
    registerView(IApplication, ApplicationView)
    registerView(IApplicationObjectContainer, ApplicationObjectContainerView)

