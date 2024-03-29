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
#from __future__ import print_function, division, absolute_import
import inspect


class DependsOnAnotherPhase(Exception):
    '''An exception that may be raised by a Phase to indicate that another
    Phase should be run first. Usually, this would be something like
    "train-phase" depends on "GenTrainData". The Experiment will attempt to
    execute that phase and try again with the original phase to execute.'''
    def __init__(self, name_of_phase_that_needs_to_be_run_first):
        self.depends_on = name_of_phase_that_needs_to_be_run_first


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
            self.__doc__ = wrap_function.__doc__
            self.has_wrap_function = True
        else:
            self.wrap_function = lambda ex: None # "do nothing" placeholder
            self.has_wrap_function = False
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
        if len(inspect.getargspec(self.wrap_function).args) >= 3:
            r = self.wrap_function(ex=ex, config=config, result=result, **kwargs)
        else:
            kwargs['ex'] = ex
            kwargs['result'] = result
            kwargs['config'] = config
            r = self.wrap_function(**kwargs)
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
        return self.run(ex=ex, config=config, result=result, **kwargs)

    
    def __str__(self):
        return self.name+'-phase'
    __repr__ = __str__
    
    