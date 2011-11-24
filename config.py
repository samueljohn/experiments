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



class Config(dict):
    '''An intermezzo between a Python dict and an object.
    
    Basically a dict, you can assign and get keys like properties:
    ```
       conf = Config()
       conf.spam = 'eggs'      # Assignsment equivalent of conf['spam'] = 'eggs'
       print( conf.a )         # Access items via properties 
    ```
       
    Features:
    *    Init with a dict. (Like a dict)
    *    Init with a path to a python file containing a "config" object.
    *    Nice str (and repr) formatting.
    
    The Config object is meant to easily setup experiments with a lot of 
    parameters.
    '''

    def __init__(self, d=None, 
                 init_with_configfile=None,
                 configfile_relative_to=None,
                 **kws ):
        '''Create a new Config instance.
        
        @param d: 
            Mapping or Iterable, @see dict()'s init, because it behaves the 
            same as dict(d).
        @param init_with_configfile: 
            Give the path to a python file that contains an object "config"
            which is a Mappable. The path is assumed absolute unless you 
            also provide configfile_relative_to.
        @param configfile_relative_to: 
            You can pass __file__ to this arg, to define that 
            init_with_configfile should be relative to that __file__.
            Example: config = Config(init_with_configfile='../masterconf.py',
                                     configfile_relative_to=__file__)
                                     
        @warning: 
            init_with_configfile and configfile_relative_to are experimental!
           
        '''
        if d is None:
            dict.__init__(self)
        else:
            dict.__init__(self,d)
        self.update(kws)
        
        if init_with_configfile:
            if configfile_relative_to:
                path = os.path.dirname(os.path.abspath(configfile_relative_to))+\
                       os.sep+init_with_configfile
            else:
                path = init_with_configfile
            dirname = os.path.dirname(path)
            if dirname == '': dirname = os.curdir
            filename = os.path.basename(path)
            gl = {}
            execfile(filename, globals=gl)
            self.update( gl['config'] )
        


    def __setattr__(self,n,v):
        self[n] = v


    def __getattr__(self,n):
        return self[n] 


    def __delattr__(self,n):
        del self[n]


    def __getstate__(self):
        # needed for the shelve
        return self.__dict__


    def __repr__(self):
        '''Get string representation of this config object'''
        s  = (  [ "<Config: " ]
              + ["\n   %s=%s"%(k,repr(v))
                  for k,v in self.items() ]
              + [ " >" ] )
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
        
        
    def test_str_and_repr(self):
        c = Config({'foo':'bar'})
        c2= Config()
        s = str(c)
        #print(s)
        s2 = repr(c)
    
    
    def test_assign_and_read(self):
        '''Assign and read values via properties and the [ ] dict accessor.'''
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


    def test_single_underscore_properties(self):
        c = Config()
        c._a = 'spam' # should be ok
        assert '_a' in c.keys(), c.keys()
        
        
    
    def test_init_from_dict(self):
        d = dict(a=1, b=2, c=3)
        conf = Config(d)
        assert d['a'] == conf.a
        assert len(d) == len(conf) 
        for i in iter(conf):
            i

    def test_pickle(self):
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
