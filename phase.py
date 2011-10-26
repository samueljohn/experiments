'''
Define a phase in an experiment.

@copyright: 
    2009-2011, Samuel John
@author: 
    Samuel John.
@contact: 
    www.SamuelJohn.de
@license: 
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''



class Phase(object):
    '''A Phase is a step that is carried out for the experiment. Is has a 
    run() method, which is supposed to do the work and optionally a 
    needsrun() that may be overwritten to check if a run() is needed.
    
    
    @todo: Add a depends_on functionality
    @todo: Add run_after and run_before to enforce a certain execution order
           and make it possible to run the last phase and all prior phases
           are automatically started.
    '''
        
    def __init__(self, wrap_function=None ):
        '''You can define your phase as a function and pass it to the __init__.'''
        if wrap_function is not None:
            self.wrap_function = wrap_function
            self._name = self.wrap_function.__name__
        else:
            self.wrap_function = lambda ex: None # "do nothing" placeholder
        self.run_counter = 0
        if self.name in ('all', 'All', 'ALL'):
            raise ValueError('Name "all" not allowed for a subclass of Phase.')
         
    @property
    def name(self):
        try:
            return self._name
        except:
            pass
        return type(self).__name__
    
            
    def run(self, ex=None, config=None, result=None, **kwargs):
        '''Run this phase. You will probably want to overwrite this method.'''
        try:
            r = self.wrap_function(ex, config=config, result=result, **kwargs)
        except TypeError:
            r = self.wrap_function(ex, **kwargs)
        if r is not None:
            result[self.name + "_result"] = r
        self.run_counter += 1
        return r


    def needsrun(self, ex=None, config=None, result=None):
        '''Return True if this phase needs to be run. This function is optional
        and can inspect the Experiment ex to decide, if itself needs to be run.
        '''
        return True # default: always needs to be run

    
    def is_allowed_to_run(self, ex=None, config=None, result=None):
        '''Return true, if this phase is allowed to be run now. Default: True.
        '''
        return True
    

    def __call__(self, ex=None, config=None, result=None, **kwargs):
        '''Allow to call this object directly instead of run().'''
        try:
            return self.run(ex, config=config, result=result, **kwargs)
        except TypeError:
            return self.run(ex)

    
    def __str__(self):
        return self.name+'-phase'
    
    
    