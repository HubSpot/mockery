'''
A library for drop dead simple mocking, that validates method calls and attribute lookups against
the original objects or methods you are mocking out:

For simple usage see the README.md for seeing all features in live action checkout the test/test_mocking.py

'''

import inspect
import sys


class MockingBirdMixin(object):
    '''
    A mixin that you can inherit from in your TestCase to add support
    for mocking methods and objects
    '''
    _mocks_storage = None

    def stub(self, obj, method_name, mock_method=None):
        '''
        Use this method when you want to mock a method so that you avoid a database 
        call, but you dont want to be strict about matching the exact order and number
         of times that is called.
         @obj - the object that has a method you want to mock
         @method_name - the method to mock
         @return_val (optional) - the value you want the method call to return
         @substitute_method (optional) - a method to use in place of the one you are mocking out
        '''
        if self._mocks_storage == None:
            self._mocks_storage = {}
        org_method = getattr(obj, method_name)
        if isinstance(org_method, LaxMock):
            org_method = org_method.org_method
        mock = LaxMock(obj, org_method, method_name, mock_method)
        key = str(obj) + method_name
        storage = self._mocks_storage.get(key)
        if not storage:
            self._mocks_storage[key] = MockStorage(obj, org_method, method_name, mock)
        else:
            # Verify that the original mock method was used up, and then set a new mock method
            storage.lax_mock.verify_calls()
            storage.lax_mock = mock
        setattr(obj, method_name, mock)
        return mock

    def unstub(self, obj, method_name):
        key = str(obj) + method_name
        storage = self._mocks_storage[key]
        setattr(storage.target_obj, storage.method_name, storage.org_method)        
        

    def new_mock_object(self, cls_or_obj=None, *args, **kwargs):
        '''
        Instantiates a new mock object
        * if cls_or_obj is None, it will return a LaxObject which will happily return itself
          when any method or attribute is looked up on the object
        * if cls_or_obj is a Class, it mixes in the SimpleMockObject base class which will create a new mock
          class with every method from the original class mocked out
        * if cls_or_obj is an object, it will create a new instance of SimpleMockObject with every method 
          from the passed in object mocked out, and then will will the mock object with every instance
          property of the passed in object
        * kwargs are passed to the contructore in case of instanitating a class
        '''
        if not cls_or_obj:
            return LaxObject()
        obj = None
        if not isinstance(cls_or_obj, type) and not 'classobj' in str(type(cls_or_obj)):
            obj = cls_or_obj
            cls = obj.__class__
        else:
            cls = cls_or_obj
        mock_cls = MockObjectMetaClass(cls.__name__ + 'Mock', (SimpleMockObject, cls), {})
        mock_obj = mock_cls(*args, **kwargs)
        if obj:
            mock_obj.__dict__.update(obj.__dict__)
        return mock_obj

    def cleanup_mocks(self):
        if self._mocks_storage == None:
            return
        for storage in self._mocks_storage.values():
            # restore the original method
            setattr(storage.target_obj, storage.method_name, storage.org_method)
        self._mocks_storage = {}

    def verify_mocks(self):
        if self._mocks_storage == None:
            return
        for storage in self._mocks_storage.values():
            storage.lax_mock.verify_calls()            
        
    def tear_down_mocks(self):
        try:
            result = getattr(self, '_resultForDoCleanups', None)
            if not result or not (result.failures or result.errors):
                # Only verify calls if the unittests ran through without errors,
                # otherwise we get useless double reporting of errors
                self.verify_mocks()
        finally:
            self.cleanup_mocks()

    def tearDown(self, *args, **kwargs):
        self.tear_down_mocks()

class MockStorage(object):
    def __init__(self, target_obj, org_method, method_name, lax_mock):
        self.target_obj = target_obj
        self.org_method = org_method
        self.method_name = method_name
        self.lax_mock = lax_mock

class LaxMock(object):
    def __init__(self, obj, method, method_name, mock_method=None):
        self.obj = obj
        self.org_method = method
        self.method_name = method_name
        self.mock_method = mock_method
        self.return_obj = LaxObject()
        self.return_method = mock_method
        self.expected_args = None
        self.expected_kwargs = None
        self.at_least_count = 1
        self.exact_count = None
        self.call_count = 0

    def expect(self, *args, **kwargs):
        '''
        Send the mock object a list of expected arguments that the mock
        will expect to find every time __call__ is called
        The expected arguments can be exact values, or type() values such as int, dict, etc.
        '''
        self.expected_args = args
        self.expected_kwargs = kwargs
        return self


    def ret(self, obj=None):
        '''
        Set the obj that every __call__ will return
        @obj - the obj that __call__ will return
        '''
        self.return_obj = obj
        return self

    def count(self, at_least=None, exact=None):
        '''
        Set the number of times you expect __call__ to be called.
        '''
        if at_least != None and exact != None:
            raise ValueError('You cannot set both an exact count and an at least count')
        self.at_least_count = at_least
        self.exact_count = exact
        return self

    def verify_calls(self):
        '''
        Verify that __call__ was called the number of times we expected it to be called
        '''
        if self.at_least_count != None:
            if self.call_count < self.at_least_count:
                raise AssertionError('Expected at least %s calls, got %s, calling %s.%s' % 
                                (self.at_least_count, self.call_count, self.obj, self.method_name))

        if self.exact_count != None:
            if self.exact_count != self.call_count:
                raise AssertionError('Expected exactly %s calls, got %s, calling %s.%s' % 
                                (self.exact_count, self.call_count, self.obj, self.method_name))

    def __call__(self, *args, **kwargs):
        '''
        Call the mock method
        '''
        self.call_count += 1
        self._validate_against_org_signature(args, kwargs)
        self._validate_against_expected(args, kwargs)
        if self.return_method:
            return self.return_method(*args, **kwargs)
        else:
            return self.return_obj

    def _validate_against_org_signature(self, actual_args, actual_kwargs):
        '''
        Validate that the arguments match the signature of the original method that we are mocking
        '''
        org_args, variable_args, variable_keyword_args, default_args = inspect.getargspec(self.org_method)
        if org_args == None:
            org_args = []
        if default_args == None:
            default_args = []

        # Strip out the first argument of instance methods and class methods (self and cls)
        if inspect.ismethod(self.org_method) or (org_args and org_args[0] == 'self'):
            org_args = org_args[1:]  # Skip 'self'.
        if actual_args and isinstance(actual_args[0], type(self.obj)):
            # if the first argument of params is an uninstantiated class
            # the first check above will always evaluate to true, so we also
            # verify that the classes are the same before trimming
            if type(actual_args[0]) == type and type(self.obj) == type and actual_args[0] == self.obj:
                actual_args = actual_args[1:]

        # Validate positional arguments
        min_positional_count = len(org_args) - len(default_args)
        max_positional_count = len(org_args)
        if variable_args:
            max_positional_count = 999
        if len(actual_args) < min_positional_count:
            raise TypeError('Expected at least %s positional args, got %s args, calling %s.%s' % 
                            (min_positional_count, len(actual_args), str(self.obj), self.method_name))
        if len(actual_args) > max_positional_count:
            raise TypeError('Expected no more than %s posiational args, got %s args, calling %s.%s' % 
                            (max_positional_count, len(actual_args), str(self.obj), self.method_name))

        # Validate keyword arguments
        if variable_keyword_args != None:
            return True
        for key in actual_kwargs.keys():
            if key not in org_args:
                raise TypeError('Unexpected keyword argument %s, calling %s.%s' % 
                                (key, str(self.obj), self.method_name))
        return True

    def _validate_against_expected(self, actual_args, actual_kwargs):
        '''
        Validate that the arguments match the values and/or types set by the expect() method
        '''
        msg = ' calling %s.%s' % (str(self.obj), self.method_name)
        expected_args_iter = enumerate(self.expected_args) if self.expected_args else []
        expected_kwargs_iter = self.expected_kwargs.items() if self.expected_kwargs else []
        # Verify that the number of arguments match
        if self.expected_args != None:
            if len(actual_args) != len(self.expected_args):
                raise AssertionError('Expected %s positional args, got %s args, %s'  % 
                                (len(self.expected_args), len(actual_args), msg))
        if self.expected_kwargs != None:
            if len(actual_kwargs) != len(self.expected_kwargs):
                raise AssertionError('Expected %s keyword args, got %s args, %s'  % 
                                (len(self.expected_kwargs), len(actual_kwargs), msg))

        # Verify that the position and key word arguments match
        for actual_key_vals, expected_key_vals  in [(actual_args, expected_args_iter), (actual_kwargs, expected_kwargs_iter)]:
            for key, expected in expected_key_vals:
                actual = actual_key_vals[key]
                self._verify_actual_matches_expected(actual, expected, actual_args, actual_kwargs, msg)

    def _verify_actual_matches_expected(self, actual, expected, actual_args, actual_kwargs, msg):
        if type(expected) is IgnoreArg or (expected and getattr(expected, '__name__', '') == 'IgnoreArg'):
            return
        elif type(expected) is type or inspect.isclass(expected):
            if not isinstance(actual, expected):
                raise AssertionError('Expected type %s, got %s of type %s, %s' % (expected, actual, type(actual), msg))
        elif expected != actual:
            sys.stderr.write("ACTUAL ARGS %s, %s \n" % (actual_args, actual_kwargs))
            sys.stderr.write("EXPECTED ARGS %s, %s \n" % (self.expected_args, 
                                                          self.expected_kwargs))
            raise AssertionError('Expected %s, got %s, %s' % (expected, actual, msg))
        

class IgnoreArg(object):
    pass

class LaxObject(object):
    '''
    Used for mocking internal objects, where we are not testing the 
    implementation, and just want to accept the usage as given
    '''
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __call__(self, *args, **kwargs):
        return LaxObject()



class MockObjectMetaClass(type):
    def __new__(mcs, name, bases, dct):
        new_dict = {}
        if len(bases) > 1:
            new_dict = mcs.mock_base_attributes(bases)
        new_dict.update(dct)
        return type.__new__(mcs, name, bases, new_dict)


    @classmethod
    def mock_base_attributes(mcs, bases):
        bases = [b for b in bases if 'SimpleMockObject' not in str(b)]
        base = bases[0]
        base_attr_dict = {}
        # TODO: validate that the method signature of overriden
        #       methods match
        for attr_name in dir(base):
            attr = getattr(base, attr_name)
            if attr_name.startswith('_') and attr_name not in ('__init__',):
                continue
            if inspect.isfunction(attr):
                mock_method = LaxMock(base, attr, attr_name)
                if attr_name == '__init__':
                    mock_method.ret(None)
                else:
                    mock_method.ret(LaxObject())
                base_attr_dict[attr_name] = mock_method
                continue
            if type(attr) in (dict, list, basestring, unicode, str):
                base_attr_dict[attr_name] = attr
            elif not attr_name.startswith('_'):
                base_attr_dict[attr_name] = LaxObject()

        return base_attr_dict
    

class SimpleMockObject(object):
    '''
    A base class for creating mock objects that automatically validates
    against the methods and attributes of the original class

    To use, in a test_file write something like:
    class MockMyConnection(SimpleMockObject, TheRealObject):
        pass

    The metaclass will introspect the class on creation, and for every
    method in TheRealObject it will create a method validator (LaxMock) 
    in the mock object.  The validator will validate the arguments against
    the expected arguments if the method is called.  The metaclass will
    also create matching mock attributes that match the original class
    
    You can create your own override moock methods as desired.
    
    '''
    __metaclass__ = MockObjectMetaClass
    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)    
