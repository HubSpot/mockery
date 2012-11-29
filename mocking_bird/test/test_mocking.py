import difflib
from StringIO import StringIO
import tarfile
from unittest import TestCase
import urllib2
import urlparse

from ..mocking import MockingBirdMixin, LaxObject, IgnoreArg

class MockingCase(TestCase, MockingBirdMixin):
    def test_basic_stubs(self):
        # Most basic usage, stub out the method, each call with return a generic mock object,
        # each call is validated against the original method signature
        self.stub(urllib2, 'urlopen')
        result = urllib2.urlopen('notaurl')
        self.assertTrue(isinstance(result, LaxObject))
        # Calling with no arguments will result in an exception because it does not match
        # the original signature
        self.assertRaises(TypeError, urllib2.urlopen)

    def test_complete_stub(self):
        # Now we stub out, but define expected arguments and a return value
        html = '<html>hohoho</html>'
        self.stub(urllib2, 'urlopen').expect('notaurl', timeout=10).ret(StringIO(html))
        result = urllib2.urlopen('notaurl', timeout=10)
        self.assertEqual(html, result.read())

        # Expect arguments of a general type, rather than a specific value
        self.stub(urllib2, 'urlopen').expect(basestring, timeout=IgnoreArg()).ret(html)
        self.assertEqual(html, urllib2.urlopen('notaurl', timeout=None))
        self.assertRaises(AssertionError, urllib2.urlopen, 1231231, timeout=None)

        # Verify that we called the mock method the expected number of times
        self.stub(urllib2, 'urlopen').expect('notaurl').ret(StringIO(html)).count(2) 
        urllib2.urlopen('notaurl')
        self.assertRaises(AssertionError, self.tear_down_mocks)


    def test_mock_method_stub(self):
        # Replace the old method with a new mock method entirely
        output = 'IAmExpectedOutput'
        def mock_method(url):
            return output
        self.stub(urllib2, 'urlopen', mock_method)
        self.assertEqual(output, urllib2.urlopen('adfsa'))
        self.unstub(urllib2, 'urlopen')

        self.stub(ExampleClass, 'example_args').ret("yes!!")
        self.stub(ExampleClass, 'example_kwargs').ret("yes!!")
        self.stub(ExampleClass, 'example_full').ret("yes!!")
        self.stub(ExampleClass, 'example_static').ret("yes!!")
        self.stub(ExampleClass, 'example_instance').ret("yes!!")
        self.assertEqual("yes!!", ExampleClass.example_args('one', 'two'))
        self.assertEqual("yes!!", ExampleClass.example_kwargs(one='one', two='two'))
        self.assertEqual("yes!!", ExampleClass.example_full('a', 'b', 'c', one='one'))
        self.assertEqual("yes!!", ExampleClass.example_static('a', 'b'))
        self.assertEqual("yes!!", ExampleClass().example_instance('a', 'b'))

    def test_stub_obj_methods(self):
        # Make sure stubbing works on object methods, not just module level functions
        diff = difflib.HtmlDiff(tabsize=13)
        mode = 'mode'
        self.stub(diff, 'make_file').expect(1, 2, numlines=7).ret('hello')
        self.assertEqual('hello', diff.make_file(1, 2, numlines=7))
        self.assertRaises(AssertionError, diff.make_file, 1, 2, 3, numlines=7)
        self.assertRaises(TypeError, diff.make_file)

    def test_cleanup(self):
        # verify that the original method is restored after cleanup
        query = 'mykey=myval'
        before_val = urlparse.parse_qs(query)
        mock_val = {'fake': 'mock'}
        self.stub(urlparse, 'parse_qs').ret(mock_val)
        
        self.assertEqual(mock_val, urlparse.parse_qs(query))

        self.tear_down_mocks()
        self.assertEqual(before_val, urlparse.parse_qs(query))
    
    def test_mock_class(self):
        # Test creating a mock object from a class
        f = self.new_mock_object(tarfile.TarFile, 'fakefilename.txt')
        # all methods of the original class are mocked out and will return a LaxObject when called
        result = f.extract()
        self.assertTrue(isinstance(result, LaxObject))
        self.assertRaises(AttributeError, getattr, f, 'notamethod')

    def test_mock_object(self):
        # Test creating a mock object from a class
        # all methods of the original class are mocked out and will return a LaxObject when called
        # all instance attributes of the object are copied into the mock object
        diff = difflib.HtmlDiff(tabsize=13)
        mock_diff = self.new_mock_object(diff)
        self.assertEqual(13, mock_diff._tabsize)
        self.assertTrue(isinstance(mock_diff.make_file(), LaxObject))

        o = self.new_mock_object()
        self.assertTrue(isinstance(o, LaxObject))        

class ExampleClass(object):    
    @classmethod
    def example_args(cls, *args):
        return 'example'

    @classmethod
    def example_kwargs(cls, **kwargs):
        return 'example'

    @classmethod
    def example_full(cls, a, b='yes', *args, **kwargs):
        return 'example'


    @staticmethod
    def example_static(a, b):
        return 'example'


    def example_instance(self, a, b):
        return 'example'
