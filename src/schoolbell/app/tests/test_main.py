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
Unit tests for schoolbell.app.main.

$Id$
"""

import unittest
from zope.testing import doctest


def doctest_Options():
    """Tests for Options.

    The only interesting thing Options does is find the default configuration
    file.

        >>> import os
        >>> from schoolbell.app.main import Options
        >>> options = Options()
        >>> options.config_file
        '...schoolbell.conf...'

    """

def doctest_main():
    """Tests for main().

    Main does nothing more but configures SchoolTool, prints the startup time,
    and starts the main loop.

    Since we don't want to actually create disk files and start a web server in
    a test, we will set up some stubs.

        >>> def load_options_stub(argv):
        ...     return ' '.join(argv)
        >>> def setup_stub(options):
        ...     print "Performing setup..."
        ...     print "Options: %s" % options
        >>> def run_stub():
        ...     print "Running..."
        >>> from schoolbell.app import main
        >>> old_load_options = main.load_options
        >>> old_setup = main.setup
        >>> old_run = main.run
        >>> main.load_options = load_options_stub
        >>> main.setup = setup_stub
        >>> main.run = run_stub

    Now we will run main().

        >>> main.main(['sb.py', '-d'])
        Performing setup...
        Options: sb.py -d
        Startup time: ... sec real, ... sec CPU
        Running...

    Clean up

        >>> main.load_options = old_load_options
        >>> main.setup = old_setup
        >>> main.run = old_run

    """


def doctest_load_options():
    """Tests for load_options().

    We will use a sample configuration file that comes with these tests.

        >>> import os
        >>> from schoolbell.app import tests
        >>> test_dir = os.path.dirname(tests.__file__)
        >>> sample_config_file = os.path.join(test_dir, 'sample.conf')
        >>> empty_config_file = os.path.join(test_dir, 'empty.conf')

    Load options parses command line arguments and the configuration file.

        >>> from schoolbell.app.main import load_options
        >>> o = load_options(['sb.py', '-c', sample_config_file, '-d'])
        Reading configuration from ...sample.conf

    Some options come from the command line

        >>> o.config_file
        '...sample.conf'
        >>> o.daemon
        True

    Some come from the config file

        >>> o.config.listen
        [('...', 123), ('10.20.30.40', 9999)]

    Note that "listen 123" in config.py produces ('localhost', 123) on
    Windows, but ('', 123) on other platforms.

    `load_options` can also give you a nice help message and exit with status
    code 0.

        >>> try:
        ...     o = load_options(['sb.py', '-h'])
        ... except SystemExit, e:
        ...     print '[exited with status %s]' % e
        Usage: sb.py [options]
        Options:
          -c, --config xxx  use this configuration file instead of the default
          -h, --help        show this help message
          -d, --daemon      go to background after starting
        [exited with status 0]

    It will report errors to stderr.  We need to temporarily redirect stderr to
    stdout, because otherwise doctests will not see it.

        >>> import sys
        >>> old_stderr = sys.stderr
        >>> sys.stderr = sys.stdout

    Here's what happens, when you use an unknown command line option.

        >>> try:
        ...     o = load_options(['sb.py', '-q'])
        ... except SystemExit, e:
        ...     print '[exited with status %s]' % e
        sb.py: option -q not recognized
        Run sb.py -h for help.
        [exited with status 1]

    Here's what happens when the configuration file cannot be found

        >>> try:
        ...     o = load_options(['sb.py', '-c', 'nosuchfile'])
        ... except SystemExit, e:
        ...     print '[exited with status %s]' % e
        Reading configuration from nosuchfile
        sb.py: error opening file ...nosuchfile: ...
        [exited with status 1]

    Here's what happens if you do not specify a storage section in the
    configuration file.

        >>> try:
        ...     o = load_options(['sb.py', '-c', empty_config_file])
        ... except SystemExit, e:
        ...     print '[exited with status %s]' % e
        Reading configuration from ...empty.conf
        sb.py: No storage defined in the configuration file.
        <BLANKLINE>
        If you're using the default configuration file, please edit it now and
        uncomment one of the ZODB storage sections.
        [exited with status 1]

    Cleaning up.

        >>> sys.stderr = old_stderr

    """


def doctest_setup():
    """Tests for setup()

    setup() does everything except enter the main application loop:

    - sets up loggers
    - configures Zope 3 components
    - opens the database
    - starts tcp servers

    It is difficult to unit test, but we'll try.

        >>> from schoolbell.app.main import Options, setup
        >>> from ZODB.MappingStorage import MappingStorage
        >>> from ZODB.DB import DB
        >>> options = Options()
        >>> class DatabaseConfigStub:
        ...     def open(self):
        ...         return DB(MappingStorage())
        >>> class ConfigStub:
        ...     listen = []
        ...     thread_pool_size = 1
        ...     database = DatabaseConfigStub()
        >>> options.config = ConfigStub()

        >>> setup(options)
        <ZODB.DB.DB object at ...>

    TODO: perform checks!
    TODO: clean up everything!

    Clean up

        >>> from zope.app.testing import setup
        >>> setup.placelessTearDown()

    """


def doctest_bootstrapSchoolBell():
    """Tests for bootstrapSchoolBell()

    Normally, bootstrapSchoolBell is called when Zope 3 is fully configured

        >>> from schoolbell.app.main import configure
        >>> configure()

    When we start with an empty database, bootstrapSchoolBell creates a
    SchoolBell application in it.

        >>> import transaction
        >>> from ZODB.DB import DB
        >>> from ZODB.MappingStorage import MappingStorage
        >>> db = DB(MappingStorage())

        >>> from schoolbell.app.main import bootstrapSchoolBell
        >>> bootstrapSchoolBell(db)

    Let's take a look...

        >>> connection = db.open()
        >>> root = connection.root()
        >>> from zope.app.publication.zopepublication import ZopePublication
        >>> app = root.get(ZopePublication.root_name)
        >>> app
        <schoolbell.app.app.SchoolBellApplication object at ...>

    This new application object is the containment root

        >>> from zope.app.traversing.interfaces import IContainmentRoot
        >>> IContainmentRoot.providedBy(app)
        True

    It is also a site

        >>> from zope.app.component.interfaces import ISite
        >>> ISite.providedBy(app)
        True

    It has a local authentication utility

        >>> from zope.app import zapi
        >>> from zope.app.security.interfaces import IAuthentication
        >>> zapi.getUtility(IAuthentication, context=app)
        <schoolbell.app.security.SchoolBellAuthenticationUtility object at ...>

    It has an initial user (username 'manager', password 'schoolbell')

        >>> manager = app['persons']['manager']
        >>> manager.checkPassword('schoolbell')
        True

    This user has a grant for zope.Manager role

        >>> from zope.app.securitypolicy.interfaces import IPrincipalRoleManager
        >>> grants = IPrincipalRoleManager(app)
        >>> grants.getRolesForPrincipal('sb.person.manager')
        [('zope.Manager', PermissionSetting: Allow)]

    bootstrapSchoolBell doesn't do anything if it finds the root object already
    present in the database.

        >>> root[ZopePublication.root_name] = 'even when the object is strange'
        >>> transaction.commit()
        >>> connection.close()

        >>> bootstrapSchoolBell(db)

        >>> connection = db.open()
        >>> root = connection.root()
        >>> root.get(ZopePublication.root_name)
        'even when the object is strange'

    Clean up

        >>> transaction.abort()
        >>> connection.close()

        >>> from zope.app.testing import setup
        >>> setup.placelessTearDown()

    """


def test_suite():
    return unittest.TestSuite([
                doctest.DocTestSuite(optionflags=doctest.ELLIPSIS),
                doctest.DocTestSuite('schoolbell.app.main',
                                     optionflags=doctest.ELLIPSIS),
           ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
