'''
Run n nested for-loops. Ideal for running though all configurations of 
different parameters in an experiment.

Created on Mar 25, 2011

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
'''

class Unroller(object):
    '''
    Emulate nested for-loops.
    @param  loops: 
        loops is a list with a tuple of the variable name and an Iterable to 
        loop over.
    @param log: 
        An optional logger that can be used to print the variable and value
        for each step in the loop.
    
    Usage: for ns,vs in unroller( [ ('x',range(1)), ('y',range(2)), ('z',range(2)) ] ): 
              print ns, vs   
      out: ['x', 'y', 'z'] [0, 0, 0]
           ['x', 'y', 'z'] [0, 0, 1]
           ['x', 'y', 'z'] [0, 1, 0]
           ['x', 'y', 'z'] [0, 1, 1]
    '''
        
    def __init__(self, loops, log=None):
        self.loops = loops
        self.log = log
        self.total = 1
        for l in loops:
            if len(l)==3: self.total *= l[2] # len is explicitly given as third tuple element
            else: self.total *= len(l[1])
        if self.log:
            self.log.info('Iterating over %i items.', self.total)    
            
    def __len__(self):
        return self.total
            
            
    def __iter__(self):
        return self._unroll()
    
    
    def _unroll(self):
        loop_vars = []
        loop_vals = []
        loop_iter = []
        loops = self.loops
        for loop in loops:
            loop_vars.append(loop[0])
            loop_iter.append(iter(loop[1]))
            loop_vals.append(loop_iter[-1].next()) # get the first elem.
        cur = -1
        for i in range(len(loops)):
            cur += 1
            if self.log: 
                sp = '  ' * cur
                self.log.info('%s%s = %s: ...', sp, loop_vars[cur], loop_vals[cur])

        
        yield loop_vars, loop_vals
        last = cur
        while cur >= 0:
            #print ('main: cur=', cur)
            try:
                loop_vals[cur] = loop_iter[cur].next()
            except StopIteration:
                #print ('end of', cur, 'reached. resetting it')
                loop_iter[cur] = iter(loops[cur][1]) # reset iter
                loop_vals[cur] = loop_iter[cur].next()
                while cur >= 0:
                    #print ('   ',cur,'> 0 --> cur - 1 --> ', cur-1)
                    cur -= 1
                    if cur < 0: raise StopIteration
                    try:
                        #print ('    next of ',cur)
                        loop_vals[cur] = loop_iter[cur].next()
                        while cur < last:
                            if self.log: 
                                sp = '  ' * cur
                                self.log.info('%s%s = %s: ...', sp, loop_vars[cur], loop_vals[cur])
                            cur += 1
                        #print ('    cur +1 --> ', cur, ' BREAK ')
                        break
                    except StopIteration:
                        #print ('    end of', cur,'reached. resetting it.')
                        #if cur < 0: break
                        loop_iter[cur] = iter(loops[cur][1])
                        loop_vals[cur] = loop_iter[cur].next()
                        continue
            if self.log: 
                sp = '  ' * cur
                self.log.info('%s%s = %s: ...', sp, loop_vars[cur], loop_vals[cur])
            yield loop_vars[:], loop_vals[:]
            

import unittest
class Test_Unroller(unittest.TestCase):
    
    def setUp(self):
        pass
        #import diss_samuel_site
        #diss_samuel_site.enable_logging()
    
    
    def test_1_loop(self):
        import logging
        r = Unroller(loops=[('i',xrange(11))], log=logging.getLogger('Unroller'))
        j = 0
        for vars, vals in r:
            self.assertEqual( vars[0], 'i')
            self.assertEqual( j, vals[0] )
            j += 1
        self.assertTrue(j==11, 'j=%i but should be 10' %j)
            
    
    def test_0_loop(self):
        import logging
        r = Unroller(loops=[('i',[])], log=logging.getLogger('Unroller'))
        j = 0
        for vars, vals in r:
            self.assertEqual( vars[0], 'i')
            self.assertEqual( j, vals[0] )
            j += 1
        self.assertTrue(j==0, 'j=%i but should be 0' %j)
           
           
    def test_3_loops(self): 
        import logging
        r = Unroller(loops=[('i',range(2)),('j',xrange(3)),('k',range(2))], log=logging.getLogger('Unroller'))
        expected = [[0,0,0],[0,0,1],[0,1,0],[0,1,1],[0,2,0],[0,2,1],[1,0,0],[1,0,1],[1,1,0],[1,1,1],[1,2,0],[1,2,1]]
        vals = []
        count = 0 
        self.assertTrue(len(expected)==len(r), '%i != %i' % (len(expected), len(r)))
        for vars, vs in r:
            self.assertEqual( vars[0], 'i', vars)
            self.assertEqual( vars[1], 'j', vars)
            self.assertEqual( vars[2], 'k', vars)
            assert len(vs) == 3
            #print vars, '-->',vs
            vals.append(vs)
            #print 'vals', vals
            count += 1
        #print 'vals',vals 
        self.assertEqual(vals, expected)  
        self.assertTrue(count==len(expected), 'count=%i but should be %i' %(count, len(expected) ))
        
           