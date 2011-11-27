'''
A Config object that is a dict but you can access and set items as properties.

@copyright: 
    2009-2011, Samuel John
@author: 
    Samuel John.
@contact: 
    www.SamuelJohn.de
@license: 
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
   
@note: 
    The tests need the nose module.
'''

#from __future__ import print_function, division, absolute_import
import os
import sys
import unittest
import collections
import logging


class Config(collections.OrderedDict):
    '''An intermezzo between a Python OrderedDict and an object.
    
    Basically, you can assign and get keys like attributes a la JavaScript:
    ```
       conf = Config()
       conf.spam = 'eggs'      # Assignment equivalent of conf['spam'] = 'eggs'
       print( conf.a )         # Access items via properties 
    ```
       
    Features:
    *    Init with a dict. (Like a dict)
    *    Init with a path to a python file containing a "config" object.
    *    Nice str (and repr) formatting.
    
    The Config object is meant to easily setup experiments with a lot of 
    parameters.
    '''

    def __init__(self, *args, **kws ):
        '''Create a new Config instance.
        
        @warning: 
            Anything can be a key in the dict but only strings are allowed 
            as attributes. 
               For example:
                  config[2] = 'two'  # ok
                  config.2           # not ok. Syntax err!!
                  config[AnyHashable] = 1324 # ok
           
        '''
        self.__allow_underscore_attributes = True
        super(Config,self).__init__(*args, **kws)
        self.__allow_underscore_attributes = False
#        @param init_with_configfile: 
#            Give the path to a python file that contains an object "config"
#            which is a Mappable. The path is assumed absolute unless you 
#            also provide configfile_relative_to.
#        @param configfile_relative_to: 
#            You can pass __file__ to this arg, to define that 
#            init_with_configfile should be relative to that __file__.
#            Example: config = Config(init_with_configfile='../masterconf.py',
#                                     configfile_relative_to=__file__)
#                                     
#        @warning: 
#            init_with_configfile and configfile_relative_to are experimental!
#        init_with_configfile=None,
#        configfile_relative_to=None,
        
#        if init_with_configfile:
#            if configfile_relative_to:
#                path = os.path.dirname(os.path.abspath(configfile_relative_to))+\
#                       os.sep+init_with_configfile
#            else:
#                path = init_with_configfile
#            dirname = os.path.dirname(path)
#            if dirname == '': dirname = os.curdir
#            filename = os.path.basename(path)
#            gl = {}
#            execfile(filename, globals=gl)
#            self.update( gl['config'] )


    
    def __setattr__(self, n ,v):
        'set an attribute that does NOT start with "_" like a dict item.'
        if not n.startswith('_'):
            if hasattr(self,n) and n not in self:
                raise UserWarning("User warning: %s will be shadowed by an "
                                  "built-in attribute. You can only get it "
                                  "via %s['%s'] !"%(n,self.__class__.__name__,n))
            self[n] = v
        elif n.endswith("__allow_underscore_attributes"):
            super(Config,self).__setattr__(n,v)
        elif self.__allow_underscore_attributes:
            super(Config,self).__setattr__(n,v)
        else:
            raise ValueError('Setting attributes beginning with "_" is not '
                             'allowed for Config objects! (%s)'%n)
 
    
    def __getattr__(self,n):
        # __getattr__ is called as a last resort
        if n in self: 
            return self[n]
        else:
            # Default behaviour
            raise AttributeError            
    
    def __delattr__(self,n):
        if not n.startswith('_'):
            del self[n]
        else:
            super(Config, self).__delattr__(n)
        
        
    def __dir__(self):
        # dir() is used for tab-completion in ipython
        return self.keys()    
    
    
    def __repr__(self):
        '''Get string representation of this config object'''
        s  = (  [ "Config( " ]
              + ["\n   %s=%s"%(k,repr(v))
                  for k,v in self.items() ]
              + [ " )" ] )
        return reduce(lambda a,b:a+b,s,"")
    __str__ = __repr__


#----- Tests -------------------------------------------------------------------
try:
    from nose.tools import raises
except ImportError, ie:
    pass


class TestConfig(unittest.TestCase):
    
    def setUp(self):
        pass
    
    def test_empty_config(self):
        '''The most basic test: Creating an object of type config.'''
        c = Config()
        del c

    def test_type(self):
        'Config should be an instance of collections.OrderedDict'
        c = Config()
        assert isinstance(c,collections.OrderedDict) 
    
    
    def test_del_attr_and_del_as_dict_item(self):
        'del c.spam and del c["spam"]'
        c = Config()
        c.spam = 123
        c['foo'] = 456
        del c['foo']
        assert len(c) == 1
        del c.spam 
        assert len(c) == 0
        
    
    @raises(AttributeError)
    def test_raise_AttributeError_if_key_not_in_config(self):
        'Raise AttributeError if attribute is not in config.'
        c = Config()
        c.gibbetnich

        
    @raises(ValueError)
    def test_raise_AttributeError_for_underscore_attr(self):
        'Raise an AttributeError if assigning an underscore attribute.'
        c = Config()
        c.__foo = 'bar' 
            
            
    def test_ok_for_underscroe_attr_if__allow_underscore_attributes(self):
        "if config.__allow_underscore_attributes = True, then it's ok to c.__foo = 123"
        c = Config()
        c.__allow_underscore_attributes = True
#        assert c.__allow_underscore_attributes == True
#        c.__foo = 'now this should work' 
#        c.__allow_underscore_attributes = False
#        assert c.__allow_underscore_attributes == False
#        assert c.__foo == 'now this should work' 
        
        
    def test_underscore_ok_if_used_as_dict(self):
        'Underscores are ok if used with the dict [] operator.'
        c = Config()
        c['__spam__'] = 'this is ok'
        assert c.keys() == ["__spam__"]
        del c['__spam__']
        assert len(c.keys()) == 0
    
    
    def test_ok_to_shadow_an_builtin_via_dict(self):
        "It's ok to set an item via dict that will not be available as an attribute."
        c = Config(a=1)
        c['items'] = 123
        assert c['items'] == 123
            
        
    @raises(AttributeError)
    def test_raise_AttributeError_if_key_not_there(self):
        "Raise AttributeError if an attribute is not in config."
        c = Config()
        c.gibbetnich
    
    
    @raises(UserWarning)
    def test_warn_about_shadowing_built_in_names(self):
        'Warn (raise UserWarning) if an attribute of collections.OrderedDict will shadow the item.'
        c = Config()
        c.items = 'spam' # should warn here
            
        
    def test_warn_about_shadowing_built_in_names_via_init(self):
        'Do not warn if an attribute of collections.OrderedDict will shadow the item given to __init__.'
        c = Config(items='spam')
        assert c['items'] == 'spam'
        c.items() # items is still the function
        del c.items
        c.items() # items-method is not deleted
        
        
        
    def test_str_and_repr(self):
        'Test str and repr strings for expected value.'
        c = Config({'foo':'bar'})
        c2= Config()
        s = str(c)
        assert s == "Config( \n   foo='bar' )", s
        #print(s)
        c.spam=1230
        s2 = repr(c)
        assert s2 == "Config( \n   foo='bar'\n   spam=1230 )", s2
    
    
    def test_dir(self):
        'Test calling dir(c).'
        c = Config({'foo':'bar'})
        dir(c)
    
    
    def test_len(self):
        'Test len(c).'
        c = Config({'foo':'bar'})
        assert len(c) == 1, c
        c.spam = 123
        
        
    def test_delattr(self):
        'Test and check del for an attribute.'
        c = Config({'foo':'bar'})
        del c.foo
        assert len(c) == 0, c

    
    def test_assign_and_read(self):
        '''Assign and read values via properties and the [ ].'''
        c = Config()
        c.spam = 'spam'
        c.eggs = 'lots'
        assert c.spam == c['spam']
        assert c.spam == 'spam'
        # reassign:
        c.spam = 'out'
        assert c.spam == 'out'
        assert c['spam'] == 'out' 
        c['spam'] = 'new'
        assert c.spam == 'new'
        o1 = object()
        o2 = object()
        c.o1 = o1
        c['o2'] = o2
        assert c.o1 is c['o1']
        assert c.o2 is c['o2']

    
    def test_init_from_dict(self):
        'Test init with a dict given as only arg.'
        d = dict(a=1, b=2, c=3)
        conf = Config(d)
        assert d['a'] == conf.a
        assert len(d) == len(conf) 
        for i in iter(conf):
            i


    def test_pickle(self):
        'Test pickle and unpickle of an Config object (via shelve).'
        import tempfile
        import os
        import shelve
        path = tempfile.mkdtemp()
        filename = path + 'test.dump'
        d = {'a':1, 'b':2, 'spam':[4,3,2,1]}
        c = Config(d.copy())
        for k,v in d.items():
            assert v == c[k], k + str(v)
        DB = shelve.open(filename)
        DB['dump'] = c
        DB.close()

        DB2 = shelve.open(filename)
        c2 = DB2['dump']
        for k,v in d.items():
            assert k in c2.keys()
            assert v == c2[k], '' + str(v) + ' was not '+str(c2[k])+' for c[' + str(k) + ']'
        DB2.close()
        os.remove(filename)
        os.rmdir(path)
        assert c2.keys() == c.keys(), str(c2.keys()) + ' -> ' + str(c.keys())
        assert c2.keys() == d.keys()
        assert type(c2) == type(c)
        c2.a_new_item = 132123 # this would fail if c2 is just a dict!
        
        

if __name__ == "__main__":
    unittest.main(verbosity=2)
