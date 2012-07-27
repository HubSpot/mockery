mocking_bird
============

A python mocking library for unittests


Simple usage:

```python
import difflib
from unittest import TestCase
import urllib2

from mocking_bird import MockingBirdMixin

class MyCase(TestCase, MockingBirdMixin):

    def test_stuff(self):
        # Stub out urlopen, all calls to urlopen will be validated against the original signature
        self.stub(urllib2, 'urlopen')

        # Stub out urlopen, 
        # - when called the arguments should match the arguments to 'expect',
        # - it should be called 3 times during the course of the test
        # - return the instance of StringIO
        # These additional parameters are chained, you can set them in any order, or leave any out
        self.stub(urllib2, 'urlopen').expect('http://myurl.com').count(3).ret(StringIO("fake data"))

        # Mock out urlopen with a replacement method
        self.stub(urllib2, 'urlopen', lambda url: StringIO('heythere'))

        # Create a mock instance of an entire class, all methods of the class will be mocked out
        mock_diff = self.new_mock_object(difflib.HtmlDiff)

        # Create a mock instance of an object, methods are mocked out, attributes are copied over
        diff = difflib.HtmlDiff(tabsize=13)
        mock_diff = self.new_mock_object(diff)
        

```

There are more features of mocking_bird, for complete usage, read through the unittests

