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
Unit tests for schooltool.main

$Id$
"""

import unittest
import re
import os
from StringIO import StringIO
from schooltool.tests.utils import RegistriesSetupMixin

__metaclass__ = type


# RFC 2616, section 3.3
http_date_rx = re.compile(r'(Sun|Mon|Tue|Wed|Thu|Fri|Sat), \d{2}'
                          r' (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
                          r' \d{4} \d{2}:\d{2}:\d{2} GMT')


class ReactorStub:
    def __init__(self):
        self._called_in_thread = []
        self._called_from_thread = []
        self._tcp_listeners = []
        self._suggested_thread_pool_size = None
        self._main_loop_running = False

    def callInThread(self, callback):
        self._called_in_thread.append(callback)

    def callFromThread(self, *args):
        self._called_from_thread.append(args)

    def suggestThreadPoolSize(self, size):
        self._suggested_thread_pool_size = size

    def listenTCP(self, port, site, interface=None):
        self._tcp_listeners.append((port, site, interface))

    def run(self):
        self._main_loop_running = True


class ConnectionStub:

    app = object()

    def __init__(self):
        self._root = {'app': self.app}
        self.closed = False

    def root(self):
        return self._root

    def close(self):
        self.closed = True

class DbStub:
    def __init__(self):
        self._connections = []

    def open(self):
        conn = ConnectionStub()
        self._connections.append(conn)
        return conn

class SiteStub:
    def __init__(self):
        self.conflictRetries = 5
        self.db = DbStub()

class ChannelStub:
    site = SiteStub()


class TransactionStub:
    def __init__(self):
        self._note = None
        self._user = None
        self.history = ''

    def note(self, note):
        self._note = note

    def setUser(self, user):
        self._user = user

    def abort(self):
        self.history += 'A'

    def commit(self):
        self.history += 'C'


class TestSite(unittest.TestCase):

    def test(self):
        from schooltool.main import Site
        db = object()
        rootName = 'foo'
        viewFactory = object()
        site = Site(db, rootName, viewFactory)
        self.assert_(site.db is db)
        self.assert_(site.viewFactory is viewFactory)
        self.assert_(site.rootName is rootName)
        self.assertEqual(site.conflictRetries, 5)

    def test_buildProtocol(self):
        from schooltool.main import Site, Request
        db = object()
        rootName = 'foo'
        viewFactory = object()
        site = Site(db, rootName, viewFactory)
        addr = None
        channel = site.buildProtocol(addr)
        self.assert_(channel.requestFactory is Request)


class TestRequest(unittest.TestCase):

    def test_parseAcept(self):
        from schooltool.main import Request
        rq = Request(ChannelStub(), True)
        p = rq._parseAccept
        self.assertEqual(p(None), [])
        self.assertEqual(p(''), [])
        self.assertEqual(p(', ,\t'), [])
        self.assertEqual(p('*/*'), [(1.0, '*/*', {}, {})])
        self.assertEqual(p('text/html;q=0.5'),
                         [(0.5, 'text/html', {}, {})])
        self.assertEqual(p('text/html;level=2;q=0.123'),
                         [(0.123, 'text/html', {'level': '2'}, {})])
        self.assertEqual(p('text/*; level=2; q=0.1; foo=xyzzy'),
                         [(0.1, 'text/*', {'level': '2'}, {'foo': 'xyzzy'})])
        self.assertEqual(p('text/html;q=0.5,\t'
                           'text/html;level=2;q=0.123, '
                           'text/*; level=2; q=0.1; foo=xyzzy,\r\n\t'
                           'image/png,'),
                         [(0.5, 'text/html', {}, {}),
                          (0.123, 'text/html', {'level': '2'}, {}),
                          (0.1, 'text/*', {'level': '2'}, {'foo': 'xyzzy'}),
                          (1.0, 'image/png', {}, {})])
        self.assertEqual(p('\ttext/html ; q="0.5" , '
                           'text/html ; level=2 ; Q=0.123 , '
                           'text/* ; level=2; q=0.1 ; foo=xyzzy ,\n\t'
                           'image/png , '),
                         [(0.5, 'text/html', {}, {}),
                          (0.123, 'text/html', {'level': '2'}, {}),
                          (0.1, 'text/*', {'level': '2'}, {'foo': 'xyzzy'}),
                          (1.0, 'image/png', {}, {})])
        self.assertEqual(p('text/x-foo;bar="fee fie foe foo";q=0.1'),
                         [(0.1, 'text/x-foo', {'bar': 'fee fie foe foo'}, {})])
        self.assertEqual(p('text/x-foo; bar="fee fie foe foo" ; q=0.1'),
                         [(0.1, 'text/x-foo', {'bar': 'fee fie foe foo'}, {})])
        self.assertEqual(p(r'text/x-foo;bar="qu\"ux";q=0.1'),
                         [(0.1, 'text/x-foo', {'bar': r'qu\"ux'}, {})])
        self.assertEqual(p(r'text/x-foo;bar="qu\\ux";q=0.1'),
                         [(0.1, 'text/x-foo', {'bar': r'qu\\ux'}, {})])
        self.assertEqual(p(r'text/x-foo;bar="qu\\";q=0.1'),
                         [(0.1, 'text/x-foo', {'bar': r'qu\\'}, {})])
        self.assertEqual(p(r'text/x-foo;bar="qu=ux";q=0.1'),
                         [(0.1, 'text/x-foo', {'bar': r'qu=ux'}, {})])
        self.assertEqual(p(r'text/x-foo;bar="qu;ux";q=0.1'),
                         [(0.1, 'text/x-foo', {'bar': r'qu;ux'}, {})])
        self.assertEqual(p(r'text/x-foo;bar="qu,ux";q=0.1'),
                         [(0.1, 'text/x-foo', {'bar': r'qu,ux'}, {})])
        # now check tolerance for invalid headers
        self.assertRaises(ValueError, p, 'error')
        self.assertRaises(ValueError, p, 'text/')
        self.assertRaises(ValueError, p, '@%@%#/@%@%')
        self.assertRaises(ValueError, p, 'foo/bar;')
        self.assertRaises(ValueError, p, 'foo/bar;q=')
        self.assertRaises(ValueError, p, 'foo/bar;q=xyzzy')
        self.assertRaises(ValueError, p, 'foo/bar;q=1.001')
        self.assertRaises(ValueError, p, 'foo/bar;Q="1.001"')
        self.assertRaises(ValueError, p, 'foo/bar;q=-2')
        self.assertRaises(ValueError, p, 'foo/bar;q=1.2.3')
        self.assertRaises(ValueError, p, 'foo/bar;;q=1')
        self.assertRaises(ValueError, p, 'foo/bar;arg')
        self.assertRaises(ValueError, p, 'foo/bar;arg=a=b')
        self.assertRaises(ValueError, p, 'foo/bar;x"y"z=w')
        self.assertRaises(ValueError, p, 'foo /bar;q=1')
        self.assertRaises(ValueError, p, 'foo/ bar;q=1')
        self.assertRaises(ValueError, p, 'foo/bar;q =1')
        self.assertRaises(ValueError, p, 'foo/bar;q= 1')

    def test_split(self):
        from schooltool.main import Request
        split = Request(None, True)._split
        self.assertEqual(split('', ','), [''])
        self.assertEqual(split('xyzzy', ','), ['xyzzy'])
        self.assertEqual(split('x,y,zzy', ','), ['x', 'y', 'zzy'])
        self.assertEqual(split(',xyzzy', ','), ['', 'xyzzy'])
        self.assertEqual(split('xyzzy,', ','), ['xyzzy', ''])
        self.assertEqual(split('x,y,zzy', 'y'), ['x,', ',zz', ''])
        self.assertEqual(split(',,,', ','), ['', '', '', ''])
        self.assertEqual(split('"xy, zzy"', ','), ['"xy, zzy"'])
        self.assertEqual(split('"x,y",z,"z",y', ','),
                         ['"x,y"', 'z', '"z"', 'y'])
        self.assertEqual(split(r'"x\"y,z","zy"', ','),
                         [r'"x\"y,z"', '"zy"'])

    def test_valid_token(self):
        from schooltool.main import Request
        valid_token = Request(None, True)._valid_token
        self.assert_(valid_token('foo'))
        self.assert_(valid_token('abcdefghijklmnopqrstuvwxyz'))
        self.assert_(valid_token('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
        self.assert_(valid_token('0123456789'))
        self.assert_(valid_token('`~!#$%^&*-_+\'|.'))
        self.assert_(not valid_token(''))
        for c in '()<>@,;:\\"/[]?={} \t':
            self.assert_(not valid_token(c),
                         '%r should not be a valid token' % c)
        for c in range(33):
            self.assert_(not valid_token(chr(c)),
                         'chr(%r) should not be a valid token' % c)
        self.assert_(not valid_token(chr(127)),
                     'chr(127) should not be a valid token')

    def test_valid_media_type(self):
        from schooltool.main import Request
        valid_media_type = Request(None, True)._valid_media_type
        self.assert_(valid_media_type('foo/bar'))
        self.assert_(valid_media_type('foo/*'))
        self.assert_(valid_media_type('*/*'))
        self.assert_(not valid_media_type(''))
        self.assert_(not valid_media_type('foo'))
        self.assert_(not valid_media_type('*'))
        self.assert_(not valid_media_type('/'))
        self.assert_(not valid_media_type('foo/'))
        self.assert_(not valid_media_type('foo/bar/baz'))
        self.assert_(not valid_media_type('foo / bar'))
        self.assert_(not valid_media_type('*/bar'))
        self.assert_(not valid_media_type('foo/"bar"'))

    def test_process(self):
        from schooltool.main import Request, SERVER_VERSION
        channel = ChannelStub()
        rq = Request(channel, True)
        rq.reactor_hook = ReactorStub()
        rq.path = '/foo/ba%72'
        rq.process()
        self.assertEqual(rq.site, ChannelStub.site)
        self.assertEqual(rq.prepath, [])
        self.assertEqual(rq.postpath, ['foo', 'bar'])
        self.assertEqual(rq.headers['server'], SERVER_VERSION)
        self.assert_(http_date_rx.match(rq.headers['date']))
        self.assertEqual(rq.headers['content-type'], 'text/html')
        self.assertEqual(rq.reactor_hook._called_in_thread, [rq._process])
        self.assertEqual(rq.accept, [])

        rq.received_headers['accept'] = 'text/plain;q=0.5, text/html'
        rq.process()
        self.assertEqual(rq.accept, [(0.5, 'text/plain', {}, {}),
                                     (1.0, 'text/html', {}, {})])

        rq.received_headers['accept'] = 'invalid value for this header'
        rq.process()
        self.assertEqual(rq.code, 400)

    def do_test__process(self, path, render_stub, user=None):
        from schooltool.main import Request

        transaction = TransactionStub()

        channel = None
        rq = Request(channel, True)
        rq.path = path
        rq.site = SiteStub()
        rq.reactor_hook = ReactorStub()
        rq.get_transaction_hook = lambda: transaction
        rq.traverse = lambda: path
        rq.render = render_stub
        if user is not None:
            rq.user = user
        rq._process()

        self.assert_(rq.zodb_conn is None)
        self.assert_(len(rq.site.db._connections) > 0)
        for connection in rq.site.db._connections:
            self.assert_(connection.closed)

        return rq, transaction

    def test__process(self):
        from twisted.python import failure

        path = '/foo'
        body = 'spam and eggs'
        user = 'john'

        def render_stub(resource):
            assert resource is path
            return body

        rq, transaction = self.do_test__process(path, render_stub, user=user)

        self.assertEquals(transaction.history, 'C')

        self.assertEquals(transaction._note, path)
        self.assertEquals(transaction._user, user)

        called = rq.reactor_hook._called_from_thread
        self.assertEquals(len(called), 2)
        self.assertEquals(called[0], (rq.write, body))
        self.assertEquals(called[1], (rq.finish, ))

    def test__process_on_exception(self):
        from twisted.python import failure

        path = '/foo'
        error_type = RuntimeError
        error_msg = 'Testing exception handling'

        def render_stub(resource):
            assert resource is path
            raise error_type(error_msg)

        rq, transaction = self.do_test__process(path, render_stub)

        self.assertEquals(transaction.history, 'A')

        called = rq.reactor_hook._called_from_thread
        self.assertEquals(len(called), 1)
        self.assertEquals(len(called[0]), 2)
        self.assertEquals(called[0][0], rq.processingFailed)
        self.assert_(isinstance(called[0][1], failure.Failure))
        self.assert_(called[0][1].type is error_type)
        self.assertEquals(called[0][1].value.args, (error_msg, ))

    def test__process_many_conflict_errors(self):
        from twisted.python import failure
        from zodb.interfaces import ConflictError

        path = '/foo'
        error_type = ConflictError
        error_msg = 'Testing exception handling'

        def render_stub(resource):
            assert resource is path
            raise error_type(error_msg)

        rq, transaction = self.do_test__process(path, render_stub)

        retries = rq.site.conflictRetries + 1
        self.assertEquals(transaction.history, 'A' * retries)

        called = rq.reactor_hook._called_from_thread
        self.assertEquals(len(called), 1)
        self.assertEquals(len(called[0]), 2)
        self.assertEquals(called[0][0], rq.processingFailed)
        self.assert_(isinstance(called[0][1], failure.Failure))
        self.assert_(called[0][1].type is error_type)

        self.assertEquals(len(rq.site.db._connections),
                          1 + rq.site.conflictRetries)

    def test__process_some_conflict_errors(self):
        from twisted.python import failure
        from zodb.interfaces import ConflictError

        path = '/foo'
        body = 'spam and eggs'
        user = 'john'
        retries = 3
        counter = [retries]

        def render_stub(resource):
            assert resource is path
            if counter[0] > 0:
                counter[0] -= 1
                raise ConflictError
            return body

        rq, transaction = self.do_test__process(path, render_stub, user=user)

        # these checks are a bit coarse...
        self.assertEquals(transaction.history, 'A' * retries + 'C')

        self.assertEquals(transaction._note, path)
        self.assertEquals(transaction._user, user)

        called = rq.reactor_hook._called_from_thread
        self.assertEquals(len(called), 2)
        self.assertEquals(called[0], (rq.write, body))
        self.assertEquals(called[1], (rq.finish, ))

        self.assertEquals(len(rq.site.db._connections),
                          1 + retries)

    def test_reset(self):
        from schooltool.main import Request
        rq = Request(None, True)
        rq.setHeader('x-bar', 'fee fie foe foo')
        rq.addCookie('foo', 'xyzzy')
        rq.setResponseCode(505, 'this is an error')
        rq.setLastModified(123)
        rq.setETag('spam')
        rq.reset()
        self.assertEquals(rq.headers, {})
        self.assertEquals(rq.cookies, [])
        self.assertEquals(rq.code, 200)
        self.assertEquals(rq.code_message, 'OK')
        self.assertEquals(rq.lastModified, None)
        self.assertEquals(rq.etag, None)

    def test_traverse(self):
        from schooltool.main import Request

        class ResourceStub:
            def getChildForRequest(self, request):
                return request

        class SiteStub:
            rootName = 'app'

            def viewFactory(self, context):
                assert context is ConnectionStub.app
                return ResourceStub()

        rq = Request(None, True)
        rq.zodb_conn = ConnectionStub()
        rq.site = SiteStub()
        rq.prepath = ['some', 'thing']
        self.assertEquals(rq.traverse(), rq)
        self.assertEquals(rq.sitepath, rq.prepath)
        self.assert_(rq.sitepath is not rq.prepath)
        self.assertEquals(rq.acqpath, rq.prepath)
        self.assert_(rq.acqpath is not rq.prepath)

    def test_render(self):
        from schooltool.main import Request
        rq = Request(None, True)

        class ResourceStub:
            _body = 'some text'
            def render(self, request):
                return self._body

        resource = ResourceStub()
        body = rq.render(resource)
        self.assertEquals(body, ResourceStub._body)
        self.assertEquals(rq.headers['content-length'],
                          len(ResourceStub._body))

    def test_render_head_empty(self):
        from schooltool.main import Request
        rq = Request(None, True)

        class ResourceStub:
            _len = 42
            def render(self, request):
                request.setHeader('Content-Length', self._len)
                return ''

        resource = ResourceStub()
        rq.method = 'HEAD'
        body = rq.render(resource)
        self.assertEquals(body, '')
        self.assertEquals(rq.headers['content-length'], ResourceStub._len)

    def test_render_head_not_empty(self):
        from schooltool.main import Request
        rq = Request(None, True)

        class ResourceStub:
            _body = 'some text'
            def render(self, request):
                return self._body

        resource = ResourceStub()
        rq.method = 'HEAD'
        body = rq.render(resource)
        self.assertEquals(body, '')
        self.assertEquals(rq.headers['content-length'],
                          len(ResourceStub._body))

    def test_render_not_a_string(self):
        from schooltool.main import Request
        rq = Request(None, True)

        class ResourceStub:
            def render(self, request):
                return 42

        resource = ResourceStub()
        self.assertRaises(AssertionError, rq.render, resource)


class TestServer(RegistriesSetupMixin, unittest.TestCase):

    def getConfigFileName(self):
        dirname = os.path.dirname(__file__)
        return os.path.join(dirname, 'sample.conf')

    def test_loadConfig(self):
        from schooltool.main import Server
        server = Server()
        server.notifyConfigFile = lambda x: None
        config_file = self.getConfigFileName()
        config = server.loadConfig(config_file)
        self.assertEquals(config.thread_pool_size, 42)
        self.assertEquals(config.listen, [('', 123), ('10.20.30.40', 9999)])
        self.assert_(config.database is not None)

    def test_findDefaultConfigFile(self):
        from schooltool.main import Server
        server = Server()
        config_file = server.findDefaultConfigFile()
        self.assert_('schooltool.conf' in config_file)

    def test_configure(self):
        from schooltool.main import Server
        from schooltool.component import getView
        server = Server()
        server.notifyConfigFile = lambda x: None
        server.findDefaultConfigFile = lambda: self.getConfigFileName()
        server.configure([])
        self.assertEquals(server.config.thread_pool_size, 42)
        self.assertEquals(server.config.listen,
                          [('', 123), ('10.20.30.40', 9999)])
        self.assert_(server.config.database is not None)
        self.assertEquals(server.appname, 'schooltool')
        self.assertEquals(server.viewFactory, getView)
        self.assertEquals(server.appFactory, server.createApplication)

    def test_configure_with_args(self):
        from schooltool.main import Server
        from schooltool.mockup import RootView, FakeApplication
        server = Server()
        server.notifyConfigFile = lambda x: None
        config_file = self.getConfigFileName()
        server.configure(['-c', config_file, '-m'])
        self.assertEquals(server.config.thread_pool_size, 42)
        self.assertEquals(server.config.listen,
                          [('', 123), ('10.20.30.40', 9999)])
        self.assert_(server.config.database is not None)
        self.assertEquals(server.appname, 'mockup')
        self.assertEquals(server.viewFactory, RootView)
        self.assertEquals(server.appFactory, FakeApplication)

        server.help = lambda: None
        self.assertRaises(SystemExit, server.configure, ['-h'])
        self.assertRaises(SystemExit, server.configure, ['--help'])

    def test_configure_bad_args(self):
        import getopt
        from schooltool.main import Server
        server = Server()
        self.assertRaises(getopt.GetoptError, server.configure, ['-x'])
        self.assertRaises(getopt.GetoptError, server.configure, ['xyzzy'])

    def test_main(self):
        import getopt
        from schooltool.main import Server
        stdout = StringIO()
        stderr = StringIO()
        server = Server(stdout, stderr)
        server.run = lambda: None
        server.main(['--invalid-arg'])
        self.assert_(stderr.getvalue() != '')

    def test_run(self):
        # make sure we have a clean fresh transaction
        from transaction import get_transaction
        get_transaction().abort()

        from schooltool.main import Server
        from schooltool.component import getView

        class ThreadableStub:
            def init(self):
                self._initialized = True

        server = Server()
        server.threadable_hook = threadable = ThreadableStub()
        server.reactor_hook = reactor = ReactorStub()
        server.notifyConfigFile = lambda x: None
        server.notifyServerStarted = lambda x, y: None
        config_file = self.getConfigFileName()
        server.configure(['-c', config_file])
        server.run()

        self.assert_(threadable._initialized)
        self.assert_(reactor._main_loop_running)
        # these should match sample.conf
        self.assert_(reactor._suggested_thread_pool_size, 42)
        self.assertEqual(len(reactor._tcp_listeners), 2)
        self.assertEquals(reactor._tcp_listeners[0][0], 123)
        self.assertEquals(reactor._tcp_listeners[0][2], '')
        self.assertEquals(reactor._tcp_listeners[1][0], 9999)
        self.assertEquals(reactor._tcp_listeners[1][2], '10.20.30.40')
        site = reactor._tcp_listeners[0][1]
        self.assertEquals(site.rootName, 'schooltool')
        self.assert_(site.viewFactory is getView)

        from schooltool.component import getRelationshipHandlerFor
        from schooltool.interfaces import ISpecificURI, URIMembership
        # make sure relationships.setUp was called
        x = getRelationshipHandlerFor(ISpecificURI)
        y = getRelationshipHandlerFor(URIMembership)
        self.assertNotEquals(x, y, "schooltool.membership.setUp not called")

    def test_ensureAppExists(self):
        from schooltool.main import Server
        server = Server()
        transaction = TransactionStub()
        server.get_transaction_hook = lambda: transaction
        db = DbStub()
        appname = 'app'
        server.ensureAppExists(db, appname)
        self.assertEquals(len(db._connections), 1)
        conn = db._connections[0]
        self.assert_(conn.closed)
        self.assert_(conn.root()['app'] is ConnectionStub.app)
        self.assertEquals(transaction.history, '')

    def test_ensureAppExists_creates(self):
        from schooltool.main import Server
        server = Server()
        transaction = TransactionStub()
        server.get_transaction_hook = lambda: transaction
        cookie = object()
        server.appFactory = lambda: cookie
        db = DbStub()
        appname = 'foo'
        server.ensureAppExists(db, appname)
        self.assertEquals(len(db._connections), 1)
        conn = db._connections[0]
        self.assert_(conn.closed)
        self.assert_(conn.root()['app'] is ConnectionStub.app)
        self.assert_(conn.root()['foo'] is cookie)
        self.assertEquals(transaction.history, 'C')

    def test_createApplication(self):
        from schooltool.main import Server
        from schooltool import relationship
        relationship.setUp()

        server = Server()
        class DummyDataManager:
                pass
        app = server.createApplication()
        a = app['groups']['teachers']
        b = app['persons']['Aiste']
        c = app['persons']['Steve']


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestSite))
    suite.addTest(unittest.makeSuite(TestRequest))
    suite.addTest(unittest.makeSuite(TestServer))
    return suite

if __name__ == '__main__':
    unittest.main()
