'''
Run computer simulation experiments and configure them.

This scripts provides a general framework for setting up computer experiments
with logging, results dump, resuming, separation into phases, batch-training 
mdp networks and a command line or interactive console interface to start a run.

The basic idea is to separate the program logic of a computer simulation 
experiment with all its phases (from preparation, over training data generation 
and training to testing/applying and visualization) from the specific 
configuration of parameters.
The parameters are stored in a separate python file which contains a 
experiments.Config instance. Common parameters are the number of training 
samples, number of iterations and so on.

A common problem is to keep track of different runs with different parameters. 
The classes here help to easily define the parameters and storing
all the settings and results to files.

Features:
    * Nicely formatted logging to stderr and a log file with different options.
    * Command line interface or interactive usage (e.g. from IPython)
    * Separate different steps of your experiment into phases.
    * Phases can be auto-wrapped around functions.
    * Phases can optionally implement needsrun() to skip it if not needed.
    * Phases can optionally implement is_allowed_to_run() for (simple) dependency.
    * Results are dumped after each phase. If something went wrong, you can
      investigate and continue the already written results.
    * Printing the total amount of memory currently used by this python process.
    * Exception-robust: An exception in a phase does not break the whole 
      experiment and later phases can still be executed. Results are dumped.
    * The name of the experiment is used to create a dir for the log and 
      result file.
    * Additional custom command line options can be added.
    * Optionally call pylab.show() at the end.
    * You can continue an older run and pick up the results computed there 
      and continue to run the remaining needed phases. Thereby you can brake 
      dwon a large experiment in separate runs (for each phase one).
    * Version number support.
    * Report of some configuration setting of the current machine.
    * A list of matplotlib colors and markers to ease some plotting needs
      when you iterate over some visual object clases or whatever.
    * Experimental: loadnet. Load an mdp network
    * Experimental: batch_train


Experimental:
If you run a bunch of experiments that differ only in a certain parameter (or
few parameters, you can create something like "baseconfig.py"
that describes all the parameters for an experiment. Then for a specific run
you can overwrite some of the setting with another "config.py" 
(names arbitrary). 


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
   

@todo: Add tutorial
@todo: Use the Buffer logging handler that stores pickeled versions of the
       LogRecords and also add some viewer tools that can display log messages
       with on-the-fly filtering (e.g. based on logger hierarchy)
       Is there 
@todo: Switch to python 2.7's argparse
@todo: Python3 support
@todo: Add a support function to copy some stuff (possibly over the network)
       to the CWD (or localdisk / or tmp) 
@todo  Doc: Add a very simple config.py, run.py to show how cool this is :-)
@todo  Test and support to use custom options to the command line. (use argpase)
'''

#from experiments.phase import Phase
#from experiments.config import Config
#from experiments.loop_unroller import Unroller
from phase import Phase, DependsOnAnotherPhase
from config import Config
from loop_unroller import Unroller

from contextlib import closing
from subprocess import Popen, PIPE
import collections
import copy
import inspect
import logging
import os
import shelve
import shutil
import sys
import time
import unittest
import platform
import pickle


def time_string():
    '''Shorthand for getting the current time in a nice, consistent format.'''
    # todo: Make this function
    return time.strftime('%Y-%h-%d__%H-%M-%S')


def host_string():
    '''Return the network name of this machine.
    Might be handy if run on a cluster to know the host.'''
    return platform.node().split('.')[0]


def timehost_string():
    '''Get a unique string compose of the current time and host.'''
    return time_string() + '_on_' + host_string()


def get_version_string( version_tuple ):
    ''''''
    if isinstance(version_tuple, int):
        version_tuple= (version_tuple,0,0)
    elif isinstance(version_tuple, float):
        f = version_tuple
        import math
        version_tuple= (int(f.__trunc__()), 
                        int(math.floor((f - f.__trunc__()+0.00000001) * 10)), 
                        0 )
    s = "%i" % version_tuple[0]
    while len(version_tuple) < 3:
        version_tuple = list(version_tuple) + [0]
    for d in version_tuple[1:]:
        s += ".%i" % d
    return s


def enable_logging(loglevel=logging.INFO, stream=None): 
    '''Shorthand to globally enable the logging to stderr.'''
    rootLogger = logging.getLogger()
    rootLogger.setLevel(loglevel)
    if len(rootLogger.handlers)==0:
        rootLogger.setLevel(loglevel)
        #rootLogger.handlers = []
        loggingStderrHandler = logging.StreamHandler(stream)
        #loggingStderrHandler.setLevel(loglevel)
        formatter = logging.Formatter('%(levelname)-7s %(name)10s: %(message)s')
        loggingStderrHandler.setFormatter(formatter)
        rootLogger.addHandler(loggingStderrHandler)
    else:
        pass
        #print('enable_logging(): StreamHandler not added, because logging.getLogger().handlers was not empty:', rootLogger.handlers)




class Experiment(object):
    '''
    Experiment. A support class to configure and run python experiments with
    different phases and configuration options.

    Usage in your program:

    from experiments import *

    ex = Experiment( interactive=False if __name__ == '__main__' else True,
                     phases=(GenTrainData(), Train(), ShowOutputs()),
                     version=(1,0,2),
                     greeting='Learn a SFA hierarchy on moving and zooming 1d patterns.',
                     author='Your Name')
        #Then:

        ex.log.debug('foo')                  # easy access to logger
        ex.config.whatever...                # access the config file
        ex.__options.somecommandlineoption   # access the extracted & processed
                                             # command line arguments
        ex.version                           # The version of the experiment.
        ex.unique_ending                     # A unique string (date, host...)
        ex.saveresult                        # Should the resultfile be saved
        ex.resultfile                        # the resultfile
        ex.matplotlib_backend                # The backend for matplotlib
        ex.NET                               # optional the mdp network
        ex.markers                           # some matplotlib markers
        ex.colors                            # matplotlib ready colors

    ============================================================================
    
    In interactive mode, your next steps assuming an Experiment has been 
    created and named ex:
            
      ex.set_config("path/to/config.py", name="testrun", reusefile='old.RESULT') 
      ex.phases
      ex.run(phases=["GenTrainData","Train"])
      ex.memory()
      ex.result.keys()
      ex.log.info("That was fun!")
      ex.save()


    '''

    def __init__(self,
                 phases=[],
                 config=None,
                 options=[], 
                 greeting= 'A new experiment',
                 author=None, # -> will be os.envrion['USER']
                 version=(0,0,0),
                 name='run', # don't change the default without adapting the code below!
                 logfile=True,
                 loglevel='DEBUG',
                 stderrloglevel='INFO',
                 fileloglevel='DEBUG',
                 reusefile='',
                 resultfile='',
                 saveresult=True,
                 showplots=False, # setting this here to true lets pop up windows during unittests.
                 loadnet='',
                 interactive=True,
                 matplotlib_backend=''
                 ):
        '''
        Sets up a new experiment.
        
        @param phases:
            The different available phases for this experiment. A list of 
            object of the class *Phase*.
        @param interactive:
            If True (default) do not perform command line parsing. This is
            good, if you want to use it from ipython in interactive mode.

        All the parameters overwrite the information, given at the command line
        if interactive=False:

        @param config:
            Path of the config file to load. Must point to a python script.
            The file extension .py is optional. The imported module
            has to provide an object named "config". 
            That object should be a Mappable. Mostly this will be a 
            <experiments.Config> type.
        @param options:
            A list of optparse.Option or support_experiment.Option objects.
            The same as if you would call self.__parser.add_option() for each 
            element in the list.
        @param greeting:
            The greeting text (should be one line with the name of the prog.)
            Default: "A new experiment"
        @param author:
            The name of the author (you can put copyright statement here, too).
            It will be shown just below the greeting line after "Written by " .
            Defaults to os.environ['USER'].
        @param version:
            A tuple (major, minor, patch, ...) that identifies the version
            of your program. Can also be an int or an float.
        @param name:
            An optional name for this experimental run. Will overwrite
            the name defined in the config.py's config.NAME. 
            And in turn both will be overwritten from the command line 
            option --name.
        @param logfile:
            path (and name) of the logfile or True, if automatic naming should
            be used (default). None or False to disable logging to file.
        @param loglevel:
            The global (root) log level. Must be a string out of 'CRITICAL'
            'ERROR', 'WARNING', 'INFO', 'DEBUG' or 'ALL'.
        @param fileloglevel:
            Log level for the logfile.
        @param stderrloglevel:
            The log level for the stderr.
        @param reusefile:
            A string (filename) of a shelve file to load and use the
            stuff in there to continue this experiment. (still experimental)
        @param resultfile:
            A string (filename) of an shelve to create for storing all the
            results of this experimental run. If not given, a default unique
            name will be used (unless saveresult==False).
        @param saveresult:
            True for storing the results to a shelve file. Default: True.
        @param loadnet:
            Load (a possibly trained) MDP network instead of using the one
            from the config file. (experimental). The network then added
            as the key 'NET' to the result dict.
        @param showplots:
            call matplotlib.pyplot.show() at the end.



        '''
        self.unique_ending = timehost_string()
        self.loglevels = {'critical':50, 'error':40, 'warning':30, 'warn':30, 'info':20,
                       'debug':10, 'all':0, 'notset':0        }
        if logfile is True:
            logfile = self.unique_ending + ".log"
        self.version = version
        if author is None:
            try:
                author = os.environ['USER']
            except KeyError:
                pass 
        self.interactive = interactive
        self.author = author
        self.greeting = greeting
        self.__logfile = logfile
        self.__loglevel = loglevel
        self.__stderrloglevel = stderrloglevel
        self.__fileloglevel = fileloglevel 

        # command arg parsing --------------------------------------------------
        if not self.interactive:
            if True:#sys.version_info[0]==2 and sys.version_info[1] < 7: # todo: use argparse
                import optparse
                from optparse import OptionParser, Option

                self.__parser = OptionParser(usage='python %prog [--config FILE] [moreoptions] [[PHASE1][ PHASE2],...]' +
                                                 '\n\nAvailable PHASEs:\n    o  '+
                                                 '\n    o  '.join(str(p) for p in phases) + 
                                                 '\n\nIf no phases are given, all will be run.\n\n' , 
                                           version=get_version_string(self.version) )

                og=optparse.OptionGroup(self.__parser, 'General experiment options' )
                if options is not None and len(options) > 0:
                    for o in options:
                        og.add_option(o)

                og.add_option('--config', '-c', '--setup',
                              default=config,
                              type=str, dest='config', metavar='FILE',
                              help='The config python script that defines'
                                   ' the settings for this experiment.')

                og.add_option('--name',
                              default=name,
                              type=str, dest='name', metavar='STRING',
                              help='Optional. The speaking name for this'
                                   ' experimental run. Will be used '
                                   'for the logger, the logfile '
                                   'and to create the resultfile. '
                                   'Can also be defined in the '
                                   'config file itself but will be over'
                                   'written if given here.')

                og.add_option('--reuse',
                              default=reusefile,
                              type=str, dest='reusefile', metavar='SHELVEFILE',
                              help='Use another (older) shelve file '
                                   'instead of generating all results anew. '
                                   'Depending on what is in SHELVEFILE, '
                                   'it is inferred, what has still to be '
                                   'done. Everything that is found in the '
                                   'shelve is reused (if the phases support '
                                   'the needsrun() method) unless you explicitly '
                                   'specify certain phases to be run. '
                                   'Nothing from the SHELVEFILE is '
                                   'overwritten, instead results are written '
                                   'to --result if given or suppressed with '
                                   ' --dontsaveresult. However, --reuse and '
                                   '--result can point to the same file '
                                   'and in that case the file _is_ '
                                   'overwritten.' )

                og.add_option('--result',
                              default=resultfile,
                              type=str, dest='resultfile', metavar='SHELVEFILE',
                              help='Store results to a shelve file with the '
                                   'given name. Otherwise, a default unique '
                                   'file name will be created. If --reuse '
                                   'FILE1 and --result FILE2 point to the same '
                                   'file, then in effect FILE1 is overwritten '
                                   'with the new results (unless suppressed by '
                                   '--dontsaveresults).'
                                   'If SHELVEFILE already exists, it will '
                                   'be backed up.' )

                og.add_option('--dontsaveresult', action='store_false',
                              default=saveresult,
                              dest='saveresult',
                              help='Do not store results to file. Note that ' 
                                   'you can still use --reuse to continue a '
                                   'previous run but --result will be ignored.')

                og.add_option('--dontshowplots',
                              default=showplots, action='store_false',
                              dest='showplots', metavar='BOOL',
                              help='If given, matplotlib results are '
                                   'not shown.')

                og.add_option('--loadnet',
                              default=loadnet,
                              type=str, dest='loadnet', metavar='FILE',
                              help='Should the MDP network be loaded from '
                                   'a pickle FILE? This may perhaps be '
                                   'necessary, if you want a different MDP '
                                   'network to be used with a reused '
                                   'SHELVEFILE.')

                og.add_option('--matplotlib_backend',
                              default=matplotlib_backend, type=str,
                              dest='matplotlib_backend', metavar='BACKEND_NAME',
                              help='If given, matplotlib attempts to use that '
                                'specific backend. For example pdf output in '
                                'instead of GUIs popping up.')

                og.add_option('--listphases', 
                              default=False, action='store_true',
                              dest='listphases',
                              help='If given, does nothing more than listing'
                                   ' all available phases and ignored all'
                                   ' other given arguments.')

                logGroup = optparse.OptionGroup(self.__parser, 'Logging Options',
                            'These options control the log level and log file. '
                            'The log levels can be integer numbers or names. '
                            'The int numbers should be in the range from 0 to 50. '
                            'The understood names and their level are (case does '
                            'not matter here): '
                            'CRITICAL=50, ERROR=40, WARNING=30, INFO=20, '
                            'DEBUG=10, ALL=0.')

                logGroup.add_option('--loglevel',
                                    type='str', dest='loglevel', metavar='LEVEL',
                                    default=loglevel,
                                    help='The overall log level. '
                                         'Nothing below this level will be logged anywhere, '
                                         'despite what is set in the other loglevel arguments.'
                                         'Default: "DEBUG"')
                logGroup.add_option('--fileloglevel',
                                    type='str', dest='fileloglevel', metavar='LEVEL',
                                    default=fileloglevel,
                                    help='The log level for stderr. '
                                         'Default: "DEBUG"')
                logGroup.add_option('--stderrloglevel',
                                    type='str', dest='stderrloglevel', metavar='LEVEL',
                                    default=stderrloglevel,
                                    help='An integer value or name for the log level of stderr.'
                                         'Default: "INFO"')

                logGroup.add_option('--logfile',
                                    type='str', dest='logfile', metavar='FILE',
                                    help='Path (and name) of the log file to create. '
                                         'If there is already a logfile, ".old" will '
                                         'be append to the older one. '
                                         'Default: ' + str(logfile))


                self.__parser.add_option_group(og)
                self.__parser.add_option_group(logGroup)
                self.__options, self.__args = self.__parser.parse_args()
            else:
                raise NotImplementedError('I should impl. argpasrse for python 2.7')

            name    = self.__options.name
            config  = self.__options.config
            try:
                self.__loglevel = self.__options.loglevel.lower().strip()
            except:
                self.__loglevel = int(self.__options.loglevel) 
            if self.__options.logfile:
                self.__logfile = self.__options.logfile
            try:
                self.__stderrloglevel = self.__options.stderrloglevel.lower().strip()
            except:
                self.__stderrloglevel = int(self.__options.stderrloglevel)
            try: 
                self.__fileloglevel = self.__options.fileloglevel.lower().strip()
            except:
                self.__fileloglevel = int(self.__options.fileloglevel)
                
            loadnet                 = self.__options.loadnet
            reusefile               = self.__options.reusefile
            self.showplots          = self.__options.showplots
            self.resultfile         = self.__options.resultfile
            self.saveresult         = self.__options.saveresult
            self.matplotlib_backend = self.__options.matplotlib_backend
            if self.__options.listphases:
                print ('Available Phases:\n  ' +
                                        '\n  '.join(str(p) + ('\n    "' + p.__doc__ +'"' if p.__doc__ else '') for p in phases) +'\n' )
                exit(0)
        else:
            # interactive mode -------------------------------------------------
            print ('Experiment in interactive mode (no sys.argv parsing).')
            try:
                self.__loglevel        = self.__loglevel.lower().strip()
            except: 
                self.__loglevel        = int(self.__loglevel)
            try:
                self.__stderrloglevel  = self.__stderrloglevel.lower().strip()
            except: 
                self.__stderrloglevel  = int(self.__stderrloglevel)
            try:
                self.__fileloglevel    = self.__fileloglevel.lower().strip()
            except:
                self.__fileloglevel    = int(self.__fileloglevel)
            self.showplots          = showplots
            self.resultfile         = resultfile
            self.saveresult         = saveresult
            self.matplotlib_backend = matplotlib_backend
            self.__args             = [] # This will lead to no phases run initially

        # Stderr and file logging-----------------------------------------------
        if self.__loglevel in self.loglevels.keys():
            self.__loglevel = self.loglevels[self.__loglevel]
        self.__loglevel = int(self.__loglevel)

        if self.__fileloglevel in self.loglevels.keys():
            self.__fileloglevel = self.loglevels[self.__fileloglevel]
        self.__fileloglevel = int(self.__fileloglevel)

        if self.__stderrloglevel in self.loglevels.keys():
            self.__stderrloglevel = self.loglevels[self.__stderrloglevel]
        self.__stderrloglevel = int(self.__stderrloglevel)

        # Loading config -------------------------------------------------------
        print 'Setting up experiment...'
        sys.stdout.flush()
        self.__raw_phases = phases
        self.set_config(config, name=name, reusefile=reusefile)

        # A logger for the user ------------------------------------------------
        self.log = logging.getLogger(self.config.NAME)
        self.log.info('Experiment setup finished.')
        #if self.interactive:
        #    rootLogger.info(self.__doc__)
        self.log.info('\n================================================================================\n\n\n')
        
        # load a mdp net -------------------------------------------------------
        if loadnet:
            self.log.warn('Loading MDP net %s into self.result.NET', loadnet)
            import cPickle
            try:
                self.result.NET
                pass # ok there is no NET already in the current result
            except (KeyError,AttributeError) as e:
                self.log.warn('Overwriting result.NET from loaded result file with the NET from %s',loadnet)
            with open(loadnet, 'rb') as f:
                self.result.NET = cPickle.load(f)
        # Trying to set matplotlib back end ------------------------------------
        if self.matplotlib_backend:
            self.log.debug('Setting matplotlib back end to '+self.matplotlib_backend)
            import matplotlib
            matplotlib.use(self.matplotlib_backend)

        # provide matplotlib compatible colors ---------------------------------
        self.colors = [ (40/255.,  91/255.,  1.      ),
                        (1.,       50/255.,  49/255. ),
                        (13/255.,  125/255., 32/255. ),
                        (35/255., 195/255.,  240/255.),
                        (235/255., 163/255., 92/255. ),
                        (99/255.,  199/255., 21/255. ),
                        (153/255., 25/255.,   255/255.),
                        (229/255., 82/255.,  255/255.),
                        (149/255., 123/255., 54/255. ),
                        (255/255., 212/255., 0.      )
                                                 ]
        self.markers =  ['s',  #     square
                         'o',  #     circle
                         '^',  #     triangle up
                         'v',  #     triangle down
                         'd'  ]#     diamond
        
        # Add phases as methods with the same name for easy interactive calling
        for p in self.phases:
            n = p.name.lower().strip()
            if n in self.__dict__: continue
            
            class Proxy(object):
                def __init__(self, ex, name):
                    self.__ex = ex
                    self.__phase_name = name
                def __call__(self,**kws):
                    return self.__ex.run(self.__phase_name, **kws)

            temp = Proxy(ex=self,name=n)
            temp.__doc__ = p.__doc__
            self.__dict__[n] = temp
            
        
        # If positional __args were given, run the specified phases now --------
        if len(self.__args) > 0 :
            self.log.debug('Phases to run now (as given by command line): '+str(self.__args))
            self.run(phases=self.__args, force=True)
        elif len(self.__args) == 0 and not interactive:
            self.log.debug('Phases to run now: all.')
            self.run(phases='all', force=False)
        elif interactive:
            self.log.debug('Running no phases automatically. You have to call ex.run("name_of_phase").')
            
            
    def __str__(self):
        try:
            return '<Experiment ' + self.config.NAME + ': "' + self.greeting + '" with phases [' + ', '.join( str(p) for p in self.phases ) + ']>'
        except:
            return '<Experiment "' + self.greeting + '" yet without a config.>'
    __repr__ = __str__
    
    
    @property
    def stderrloglevel(self):
        return self.__stderrloglevel

    @stderrloglevel.setter
    def stderrloglevel(self,l):
        if isinstance(l,str):
            ll = l.lower().strip()
            if ll in self.loglevels.keys():
                ll = self.loglevels[ll]
            self.__stderrloglevel = int(ll)
        else:
            self.__stderrloglevel = int(l)
        self._setup_logging()  
        self.log.info('stderrloglevel is %s',logging.getLevelName(self.__stderrloglevel))

        
    @property
    def fileloglevel(self):
        return self.__stderrloglevel
    
    @fileloglevel.setter
    def fileloglevel(self,l):
        if isinstance(l,str):
            ll = l.lower().strip()
            if ll in self.loglevels.keys():
                ll = self.loglevels[ll]
            self.__fileloglevel = int(ll)
        else:
            self.__fileloglevel = int(l)    
        self._setup_logging()  
        self.log.info('fileloglevel is %s',logging.getLevelName(self.__fileloglevel))
        

    @property
    def loglevel(self):
        return self.__stderrloglevel
    
    @loglevel.setter
    def loglevel(self,l):
        if isinstance(l,str):
            ll = l.lower().strip()
            if ll in self.loglevels.keys():
                ll = self.loglevels[ll]
            self.__loglevel = int(ll)
        else:
            self.__loglevel = int(l)    
        self._setup_logging()  
        self.log.info('loglevel is %s',logging.getLevelName(self.__loglevel))
        
    
    def _setup_logging(self):
        rootLogger = logging.getLogger()
        rootLogger.setLevel(self.__loglevel)
        if len(rootLogger.handlers) == 0:
            loggingStderrHandler = logging.StreamHandler(sys.stderr)
            formatter = logging.Formatter('%(levelname)-7s %(name)10s: %(message)s')
            loggingStderrHandler.setFormatter(formatter)
            rootLogger.addHandler(loggingStderrHandler)
        for h in rootLogger.handlers:
            if isinstance(h,logging.FileHandler):
                h.setLevel(self.__fileloglevel)
            elif isinstance(h, logging.StreamHandler):
                h.setLevel(self.__stderrloglevel)
        return
    
    
    def set_config(self, config=None, name='run', reusefile=None):
        '''Set a config for this experiment.
        
        @param config: 
            Can be a file path, a mappable (like dict) or None (an empty
            configuration will be created.
        @param name: 
            A name you can assign for this experimental run. (default: 'run')
            A directory in the current dir with this name will be created to
            store the log and result files. Older files will not be overwritten.
            
        '''
        self._setup_logging()
        rootLogger = logging.getLogger()
        rootLogger.info('set_config(config=%s):',str(config))

        # Populating self.phases -----------------------------------------------
        if self.__raw_phases is None:
            self.phases = []
        else:
            self.phases = []
            for p in self.__raw_phases:
                if inspect.isfunction(p):
                    rootLogger.debug('   Phase %s was given as a function.', p)
                    self.phases.append( Phase(wrap_function=p) )
                elif inspect.isclass(p):
                    rootLogger.debug('   Phase %s was given as a class.', p)
                    self.phases.append( p() )
                else:
                    rootLogger.debug('   Phase %s was given as an instance', p)
                    self.phases.append( p )
        
        if config is not None: # makes only sense to show this if a config is loaded
            rootLogger.info('Available phases: \n' + 
                        '\n  '.join(str(p) + ('\n    "' + p.__doc__ +'"\n' if p.__doc__ else '') for p in self.phases) +'\n' )

        # Loading/Setting config -----------------------------------------------
        if config is None:
            rootLogger.info('No config specified. Creating an empty config obj. You may want to call ex.set_config("path_to_config.py")')
            self.config = Config()
        elif isinstance(config, collections.Mapping):
            self.config = Config(config)
            rootLogger.info('Using mapping ' + str(config.__class__.__name__) + ' as config.')
        else:
            rootLogger.info('Assuming %s is a path to a python file that contains a "config" object or a dict with that name.', config)
            if os.path.exists(config):
                global_dict = {}
                execfile(config, global_dict)
                try:
                    # Is there an item named "config"
                    self.config = global_dict['config']
                    rootLogger.info('Using item "config" from %s', config)
                except KeyError, ke:
                    rootLogger.warning('No item named "config" found in %s. Now searching for an instance of experiments.Config... ', config)
                    for i in global_dict:
                        if isinstance(i, Config): 
                            rootLogger.info('Found and instance of experiments.Config: %s ', i)
                            self.config = i
                    
            else:
                rootLogger.error('Specified config file %s does not exist.', config)
                raise IOError('Config file does not exist')

        # Setting NAME and UNIQUE_NAME -----------------------------------------
        if name != 'run' and not None:
            self.config.NAME = name
        elif not self.config.has_key('NAME'):
            self.config.NAME = name
        self.config.NAME = self.config.NAME.replace(' ', '_')
        self.config.NAME = self.config.NAME.replace('/', '_')
        self.config.NAME = self.config.NAME.replace('\\', '_')
        self.unique_name = self.config['NAME'] + "_" + self.unique_ending
        self.config.UNIQUE_NAME = self.unique_name

        # Creating dir for this experiment -------------------------------------
        if not os.path.exists(os.curdir + os.sep + self.config.NAME):
            os.mkdir(os.curdir + os.sep + self.config.NAME)
            rootLogger.info('Output for this experiment is put into the new directory: \n\t\t"%s"', os.path.abspath(os.curdir+os.sep+self.config.NAME))
        else:
            rootLogger.info('Output for this experiment is put into the existing directory \n\t\t"%s".', os.path.abspath(os.curdir+os.sep+self.config.NAME))

        # Adding logfile -------------------------------------------------------        
        if self.__logfile:
            logfile = os.curdir + os.sep + self.config.NAME + os.sep + self.__logfile 
            backupFile(logfile, '.bak')
            # Remove any other (older) FileHandlers
            rootLogger.handlers = [h for h in rootLogger.handlers if not isinstance(h,logging.FileHandler)]
            loggingFileHandler = logging.FileHandler( logfile, mode='w' )
            loggingFileHandler.setLevel( self.__fileloglevel )
            loggingFileHandler.setFormatter(logging.Formatter('%(levelname)-7s %(name)10s: %(message)s'))
            rootLogger.addHandler(loggingFileHandler)
            rootLogger.info( 'logfile: ' + str(logfile) )

        # Print/log infos ------------------------------------------------------
        welcome =('''
================================================================================
  %s
  Experiment written by %s. (version %s)
================================================================================''') % \
        (str(self.greeting), str(self.author), get_version_string(self.version))
        
        rootLogger.info( welcome)
        rootLogger.info( time.asctime()  )
        try:
            rootLogger.info( 'On %s', os.uname()[1] )
            rootLogger.info( 'Architecture %s', os.uname()[-1] )
        except:
            pass
        
        if not self.interactive:
            commandline = ""
            for a in sys.argv:
                commandline += ' ' + a
            rootLogger.info( 'Command line args were: ' + commandline)

        # Init result ----------------------------------------------------------
        self.result = Config()

        # REUSE ----------------------------------------------------------------
        self.reuse(reusefile)

        # SAVE (almost empty result to have the result.config stored) ----------
        self.result.config = copy.deepcopy(self.config)
        rootLogger.info('Storing the current cofing to result.config.')


    def reuse(self, reusefile):
        '''Loading and re-using an old result file.'''
        logger = logging.getLogger('reuse')
        self.unique_ending = timehost_string()
        logger.info('Setting unique_name to %s', self.unique_name)
        if not reusefile and self.config.has_key('REUSE_FILE'):
            reusefile = self.config['REUSE_FILE']
        if reusefile:
            self.config['REUSE_FILE'] = reusefile
            logger.warn('Reusing old results from %s', self.config.REUSE_FILE)
            if not os.path.exists(reusefile):
                raise ValueError('File "%s" does not exist.', reusefile)
            try:
                tmp = shelve.open(reusefile)
                for k,v in tmp.items():
                    self.result[k] = copy.deepcopy(v)
                    logger.debug('Reusing '+ k)
            except Exception as e:
                logger.exception('Failed using old result file.')
            finally:
                tmp.close()
        else:
            logger.debug('Not reusing old results.')
        
        
    def _find_phase(self, phase):
        '''Helper to find a phase by its (case insensitive) name.'''
        if isinstance(phase,str):
            #self.log.debug('   find_phase: Name of phase given as str (%s)...', phase)
            for p in self.phases:
                if p.name.lower().strip() == phase.lower().strip():
                    return p
                if p.name.lower().strip()+'-phase' == phase.lower().strip():
                    return p
        elif isinstance(phase,Phase):
            for p in self.phases:
                if phase is p:
                    return p
        return None # no phase found
    
    
    def run(self, phases='all', stopOnException=False, force=False, nosave=False, **kwargs):
        '''Actually run this experiment or more precisely the phases.

        @param phases:
            If 'all', then all phases, defined in self.phases are executed.
            Otherwise only the phases of the list of strings *phases*.
            Each phase to be run is a string
            with the name of a class (internally phases[i].__class__.__name__
            is used) or of a function from self.phases.'''
        retval = []
        if phases == 'all':
            phases = [ str(p.name) for p in self.phases ]
        if isinstance(phases,str):
            phases = [phases]
        if isinstance(phases,Phase):
            phases = [phases]
        if len(phases) > 0:
            self.log.info('Requested to run phases: \n%s', phases)
        for phase in phases:
            if self._find_phase(phase) is None:
                raise ValueError('Phase %s not found. Available are %s' % (str(phase),str(self.phases)) )
        for phase in phases:
            # Checking dependencies and constraints
            P = self._find_phase(phase) # get Phase obj from str if in self.phases
            tic = time.time()
            self.log.info('Starting %s ...', P)
            if P.has_wrap_function:
                try:
                    self.log.info('  ' + P.wrap_function.__doc__)
                except: pass
            elif P.__doc__:
                self.log.info('  ' + P.__doc__)
            try:
                if force:
                    needsrun = True
                    self.log.info('Forced to run this phase (skipping needsrun() and is_allowed_to_run() check).')
                else:
                    try:
                        needsrun = P.needsrun(ex=self, config=self.config, result=self.result)
                    except KeyError, e:
                        needsrun = True
                        self.log.debug('Need to run %s because an item was probably not found in ex.result. (KeyError in needsrun())', P)
                    except AttributeError, e:    
                        needsrun = True
                        self.log.debug('Need to run %s because an item was probably not found in ex.result. (KeyError in needsrun())', P)
                    except AssertionError, e:
                        needsrun = True
                        self.log.debug('Need to run %s because of: %s', str(e))
                # "allowed" is stronger than "force"
                try:
                    allowed = P.is_allowed_to_run(ex=self, config=self.config, result=self.result)
                except KeyError, e:
                    self.log.debug('Assuming to forbid run %s because an item was probably not found in ex.result. (KeyError in is_allowed_to_run().)', P)
                    allowed = False
                if needsrun and allowed:
                    # A local function for the recursive running of dependencies in case of DependsOnAnotherPhase Exception                  
                    def run_a_phase(the_phase, retval=[], extra_keywords={}):
                        try:
                            retval.append( the_phase(ex=self, config=self.config, result=self.result, **extra_keywords) )
                        except DependsOnAnotherPhase as err:
                            self.log.info('\n================================================================================')
                            self.log.info('The phase %s depends on %s. Now executing that one first...', P, err.depends_on)
                            tic=time.time()
                            run_a_phase(self._find_phase(err.depends_on),extra_keywords={})
                            tac=time.time()
                            self.log.info('Finished %s. Took %g seconds.', err.depends_on, tac-tic)
                            self.log.info('\n================================================================================')
                            self.log.info('And now trying to run %s again...', the_phase)
                            retval.append(run_a_phase(the_phase, extra_keywords=extra_keywords))
                    run_a_phase(P, retval, extra_keywords=kwargs)
                           
                elif not allowed:
                    self.log.error('The %s is not allowed to be run at this point.',P)
                elif not needsrun:
                    self.log.warn('%s needs not to be run. Using cached results.', P)
            except BaseException, e:
                self.log.exception('Exception in %s', P)
                if stopOnException:
                    tac = time.time()
                    self.log.info(str(e))
                    self.log.warn('ABORT: Breaking %s because stopOnException==True.', P, tac-tic)
                    self.log.info('\n================================================================================\n\n\n')
                    break # but still write the results
                else:
                    self.log.exception('Continuing with next phase and ignoring this Exception: ' + str(e))
            tac = time.time()
            self.log.info('Finished %s. Took %g seconds.', P, tac-tic)
            self.log.info('\n================================================================================\n\n\n')
        if not nosave: 
            self.save()
        if self.showplots:
            try:
                import matplotlib.pyplot as plt
                if self.interactive:
                    plt.draw()
                else:
                    plt.show()
            except AttributeError as ae:
                self.log.debug('It seems as no plot has been drawn with matplotlib.')
            except UserWarning as uw:
                self.log.debug('This matplotlib backend does not have a show() method.')
            except Exception as e:
                self.log.exception('Exception in pylab.show()...')
        self.log.info('All Finished.')
        return retval
    __call__ = run


    def save(self, protocol=None):
        '''If self.saveresult, then writing the current state of self.result to a shelve.'''
        tic = time.time()
        if self.saveresult:
            if self.resultfile is None and self.config.has_key('RESULT_FILE'):
                self.log.info('Using RESULT_FILE "%s" specified in the config.', self.config.RESULT_FILE)
            if self.resultfile:
                self.config['RESULT_FILE'] =  self.resultfile
            else:
                self.config['RESULT_FILE'] =  os.curdir + os.sep + self.config.NAME + os.sep + self.unique_ending + "_RESULT.shelve"
                self.log.info('No --result FILE was specified and the config does not contain a RESULT_FILE entry, too.')
                self.log.info('Creating a unique name for the result file.')
            
            #if not self.config['RESULT_FILE'].beginswith(self.config.NAME + os.sep):
            #    self.config['RESULT_FILE'] = self.config.NAME + os.sep + self.config['RESULT_FILE']
            
            if (os.path.exists(self.config['RESULT_FILE']) and
                self.config.has_key('REUSE_FILE') and 
                self.config['RESULT_FILE']==self.config['REUSE_FILE'] ):
                self.log.info('Reusing result file %s and updating it. The old one is backed up as ".old".', self.config['RESULT_FILE'])
            backupFile(self.config['RESULT_FILE'], ".old")
            backupFile(self.config['RESULT_FILE']+'.dir', ".old")
            backupFile(self.config['RESULT_FILE']+'.dat', ".old")
            backupFile(self.config['RESULT_FILE']+'.bak', ".old")
            with closing( shelve.open(self.config['RESULT_FILE'], protocol=protocol) ) as res:
                for k,v in self.result.items():
                    try: # Todo: How to avoid that a NET which fails during train leads to TypeError here
                        res[k] = v 
                    except TypeError as e:
                        self.log.error('Cannot save %s (%s) to result file.', str(k), str(v))
                    except RuntimeError as e:
                        self.log.error('Cannot save %s (%s) to result file.', str(k), str(v))
                    except pickle.PicklingError as e:
                        self.log.error('Cannot save %s (%s) to result file.', str(k), str(v))
            self.log.warn('==> Saving new results to %s', self.config.RESULT_FILE)
        else:
            self.config.RESULT_FILE = None
            self.log.info('Not requested to save results. (--dontsaveresult)')
        tac = time.time()
        self.log.debug('Saving result file took %i seconds.', tac-tic)


    def memory(self, pid=None):
        """Return int containing memory in Kilobytes used by the current process."""
        try:
            if not pid:
                pid = os.getpid()
            process = Popen("ps -o rss= -p %i" % pid,
                             shell=True,
                             stdout=PIPE )
            stdout_list = process.communicate()[0].split('\n')
            mem = int(stdout_list[0])
        except Exception, e:
            print("Cannot get amount of memory used by this process." + str(e))
            return -1
        return mem


    def needs_training(self,net=None):
        '''The missing method to check whether a mdp network has finished training.'''
        if net is None:
            net = self.result.network
        for node in net:
            if node.is_trainable() and node.is_training():
                return True # One Node is enough
        return False


    def batch_train(self, 
                    net=None, 
                    num_batches=None, 
                    datagen=None,
                    args=[],
                    kws={},
                    loop_over=[],
                    garbage_collect=False, 
                    progressbar=True  ):
        '''Ease the common task of training a mdp.flow by looping over some
        variables and calling a data generator (often datasource.sample())
        with the loop_over variables as keyword args.
        
        @param net: 
            The mdp flow to train. If None, self.result.NET is used.
        @param num_batches: 
            A list with at least as many entries as len(net) with the number 
            of repetitions for each item in net.
        @param datagen: 
            A Callable that generates data, which is understood by an mdp.Node.
            args, kws and the loop_over-variables (as keywords) are passed 
            to datagen.
        @param args: 
            Fixed args that are passed to datagen.
        @param kws: 
            Keyword args passed to datagen.
        @param loop_over: 
            A list of tuples to iterate over. See doc of Unroller.
            For example: [ ('x',range(10)), ('y', xrange(5)) ] is equivalent
            to for x in range(10):
                for y in range(5):
                    datagen(*args, **kws, x=x, y=y)
                    ...
            Optionally, the tuples can have three elements and then the third 
            element is used to define the len of the iterator. (Used for
            the progressbar).
        @param garbage_collect: 
            Optionally perform a gc.collect()
            
        '''
        import gc
        from mdp.utils import progressinfo
        if net is None:
            net = self.result.NET
        assert len(num_batches) >= len(net), str(num_batches) + str(net)
        for i, node in enumerate(net):
            if node.is_trainable() and node.is_training():
                for vars,vals in progressinfo( Unroller(loop_over, log=self.log), style='timer' ):
                    for batch in range(num_batches[i]):
                        self.log.info('   %s training batch %i/%i  [current mem: %gMB]...', 
                                    repr(node), batch+1, num_batches[i], self.memory()/1024.)
                        _kws=dict(kws)
                        _kws.update(zip(vars,vals))
                        data = datagen(*args, **_kws) 
                        #config.DS_train._labels_so_far = []# to free mem
                        #self.log.info('   memory usage: %gMB', self.memory()/1024.)
                        for pre in net[0:i]: 
                            self.log.info('      passing data through %s ...', pre)
                            data = pre(data) # execute previous nodes step by step
                        if garbage_collect:
                            mem_1 = self.memory()/1024.
                            gc.collect()
                            self.log.info('   gc.collect() freed %gMB memory...', self.memory()/1024.- mem1)
                        #self.log.info('   memory usage: %gMB', self.memory()/1024.)
                        self.log.info('   train...')
                        #self.log.info('   memory usage: %gMB', self.memory()/1024.)
                        node.train( data )
                try:
                    self.log.info('Dumping %s before stop_training.', node)
                    fn = str(node)+'_NET['+str(i)+']_trainable_'+self.unique_name+'.dump'
                    backupFile(fn)
                    node.save(fn)
                    self.log.info('Dumping finished.')
                except Exception:
                    self.log.exception('Failed to dump node %s', node)
                self.log.info('%s stop_training()...', node)
                node.stop_training()
                self.log.info('memory usage: %gMB', self.memory()/1024.)
                try:
                    self.log.info('Dumping %s which has finished training.', node)
                    fn = str(node)+'_NET['+str(i)+']_'+self.unique_name+'.dump'
                    backupFile(fn)
                    node.save(fn)
                    self.log.info('Dumping finished.')
                except Exception:
                    self.log.exception('Failed to dump trained node. %s', node)
                self.log.info('Assigning (partially) trained network to result.NET...')
                self.result.NET = net
                self.save()
            elif not node.is_trainable():
                self.log.info('Skipping untrainable node: %s', node)
            elif not node.is_training():
                self.log.info('Skipping already trained node: %s', node)
        self.log.info('Finished with all batches.')
        #self.result.TRAIN_LABELS = config.DS_train.get_labels()
        self.log.info('Assigning fully trained network to result.NET...')
        self.result.NET = net
        return net



def backupFile( path, backup_extension='.old'):
    '''
    Helper to move a file out of the way and rename it (to .old).
    If the file at "path" does not exist, no error is raised.

    @param path:
        the path and name of the file that should be backed up, if it exists.
    @param backup_extension:
        The string that will be appended to path for the backup. Default: '.old'
    @return:
        True on success and if the file path exists.
        False if path does not exist.
    '''
    log = logging.getLogger('backupFile')
    if path.endswith('.'):
        path = path[:-2]
        log.warning('Removed "." at the end of the file: ' + path)
    if not backup_extension.startswith('.'):
        if backup_extension == '.':
            backup_extension = '.old'
            log.warning('The arg backup_extesion was: "."! Changed to '+backup_extension)
        backup_extension = '.'+backup_extension
        log.debug('Added a "." at the beginning of the backup_extension.')
    if os.path.exists(path):
        log.debug('Backup of %s to %s%s .'  %( path, path, backup_extension))
        if os.path.exists(path + backup_extension):
            log.info('Replacing old backup: %s%s ...' % (path, backup_extension))
            os.remove(path + backup_extension)
        os.rename(path, path + backup_extension)
        return True
    return False



class Shell(object):
    """
    Simple class that collects commands for the shell and
    executes them on run() all at once.

    Usage like:

    shell = Shell()
    shell( "cd somewhere" )
    shell( "pwd" )
    shell.run()

    @warning: There is a certain limit of how much you can put into the shell
           before you run it. This is more for a small number (~100?) of
           commands. Beware!
    """
    def __init__(self, cwd=None):
        self.finished = False
        self.cwd=cwd
        self.execute_str = ""

    def addCommand(self, command):
        if self.finished:
            raise ValueError('Cannot addCommand() after run().')
        self.execute_str += str(command) + "\n"

    def __call__(self,arg):
        self.addCommand(arg)

    def run(self):
        """ Execute in current shell."""
        self.finished =True
        if self.cwd:
            s= Popen(self.execute_str, shell=True, cwd=self.cwd)
        else:
            s= Popen(self.execute_str, shell=True)
        os.waitpid(s.pid, 0)



#----- Tests -------------------------------------------------------------------
try:
    from nose.tools import raises
    from nose import SkipTest
except ImportError, ie:
    pass

class TestShell(unittest.TestCase):

    def test_basics(self):
        sh = Shell()
        sh('echo "test"'),

        sh('''
for i in 1 2 3 4 5 6 7
do
    echo "spam $i times"
done
''')

        sh('echo "test2"'),
        sh('echo "Shell testing successful"')
        sh.run()

    def test_cwd(self):
        sh = Shell(cwd=os.curdir)
        sh('echo spam')
        sh.run()

    @raises(ValueError)
    def test_no_commands_after_run(self):
        sh = Shell()
        sh.run()
        sh('echo spam')


class TestBackupFile(unittest.TestCase):
    def test(self):
        path = '/tmp/testBackupFile'

        if os.path.exists(path):
            if os.path.isdir(path) :
                os.rmdir(path)
            else:
                os.remove(path)

        # we create a file
        f = open(path,'w')
        f.write('original')
        f.close()

        # Now we expect path + ".backup" to be created ("." prepended)
        backupFile(path, backup_extension='backup')
        f = open(path,'w')
        f.write('foo1')
        f.close()
        self.assertTrue(os.path.exists(path + '.backup'), str(path) +'.backup was not exist.')
        # We hope that
        self.assertTrue(os.path.exists(path),'The original file' +str(path) + ' must still exist.')

        f = open(path, 'r')
        res = f.read()
        self.assertEqual(res,'foo1','File content of of '+path+' not as expected. Expected: "foo1" Was: "' + res + '"')
        f.close()

        # automatically added extension
        backupFile(path)
        f = open(path,'w')
        f.write('foo2')
        f.close()
        self.assertTrue(os.path.exists(path + '.old'))

        f = open(path, 'r')
        res = f.read()
        self.assertEqual(res,'foo2','File content of of '+path+' not as expected. Expected: "foo2" Was: "' + res + '"')
        f.close()
        f = open(path+'.old', 'r')
        res = f.read()
        self.assertEqual(res,'foo1','File content of '+path+'.old not as expected. Expected: "foo1" Was: "' + res + '"')
        f.close()
        f = open(path+'.backup', 'r')
        res = f.read()
        self.assertEqual(res,'original','File content of '+path+'.backup not as expected. Expected: "original" Was: "' + res + '"')
        f.close()

        # Replace old backup
        backupFile(path, 'backup')
        f = open(path,'w')
        foo3 = 'foo3'
        f.write(foo3)
        f.close()
        f = open(path+'.backup', 'r')
        res = f.read()
        self.assertEqual(res,'foo2','File content of '+path+'.backup not as expected.  Expected: "foo2" Was: "' + res + '"' )
        f.close()

        path = "/tmp/a/folder/that/does/not/exist/backupFile"



class TestExperiment(unittest.TestCase):
    def setUp(self):
        import os
        self.olddir = os.path.abspath(os.curdir)
        shutil.rmtree('/tmp/test-experiments/', ignore_errors=True)
        os.mkdir('/tmp/test-experiments/')
        os.chdir('/tmp/test-experiments/')
        class TestPhase1(Phase):
            def __init__(s):
                Phase.__init__(s)
                s.run_counter = 0
            def run(s, ex, result, config):
                result['foo'] = 'spam'
                s.run_counter += 1
            def needsrun(s, ex, config, result):
                if result.has_key('foo'):
                    return False
                else:
                    return True
        class AnotherTestPhase(Phase):
            def __init__(s):
                Phase.__init__(s)
                s.run_counter = 0
            def run(s, ex, config, result):
                ex.result['bar'] = 'eggs'
                s.run_counter += 1
        class PhaseThatFails(Phase):
            def __init__(s):
                Phase.__init__(s)
                s.run_counter = 0
            def run(s, ex, config, result):
                s.run_counter += 1
                raise Exception('boooom! This exception is thrown by intention to test the behavior of the run.')
        def phasefunction(**kws):
            kws['ex'].result.laa = 'lilu'
        
        self.TestPhase1 = TestPhase1
        self.AnotherTestPhase = AnotherTestPhase
        self.PhaseThatFails = PhaseThatFails
        self.phasefunction = phasefunction
            
        self.p1 = TestPhase1()
        self.p2 = TestPhase1 # given as a class not instance by intention!
        self.p3 = AnotherTestPhase()
        self.p4 = Phase()
        self.p5 = PhaseThatFails()
        self.p6 = Phase(phasefunction)
    
    
    def tearDown(self):
        os.chdir(self.olddir)    
        shutil.rmtree('/tmp/test-experiments/', ignore_errors=True)
        
    
    def test_version_tuple(self):    
        ex = Experiment(config=None,version=0)
        assert get_version_string(ex.version) == '0.0.0'
        ex = Experiment(config=None,version=99)
        assert get_version_string(ex.version) == '99.0.0'
        ex = Experiment(config=None,version=1.2)
        assert get_version_string(ex.version) == '1.2.0'
        ex = Experiment(config=None,version=1.4)
        assert get_version_string(ex.version) == '1.4.0'
        ex = Experiment(config=None,version=2.3)
        assert get_version_string(ex.version) == '2.3.0'
        ex = Experiment(config=None,version=1.10)
        assert get_version_string(ex.version) == '1.1.0'
        ex = Experiment(config=None,version=1.20)
        assert get_version_string(ex.version) == '1.2.0'
        ex = Experiment(config=None,version=[1])
        assert get_version_string(ex.version) == '1.0.0'
        ex = Experiment(config=None,version=[1,2])
        assert get_version_string(ex.version) == '1.2.0'
        ex = Experiment(config=None,version=[1,2,3])
        assert get_version_string(ex.version) == '1.2.3'
        ex = Experiment(config=None,version=[1,2,3,4])
        assert get_version_string(ex.version) == '1.2.3.4'
        ex = Experiment(config=None,version=(1,2,3,4))
        assert get_version_string(ex.version) == '1.2.3.4'
        
        
    def test_empty_experiment(self):
        '''Empty experiment has a result and log.'''
        ex = Experiment(config=None)
        import collections
        self.assertTrue( isinstance(ex.result, collections.Mapping), 'An experiment should have a dict named result.')
        self.assertTrue( isinstance(ex.config, collections.Mapping), 'The config should be a Mapping.')
        self.assertTrue( isinstance(ex.config, collections.Mapping), 'The config should be a Mapping.')
        self.assertTrue( ex.config is ex.config, 'config and config should be identical')
        self.assertTrue( len(ex.config)==2, 'config should only have NAME and UNIQUE_NAME: '+repr(ex.config) )
        assert ex.config.NAME =='run'
        assert ex.config.UNIQUE_NAME
        
        self.assertTrue( ex.unique_ending )
        ex.log.info('This should work.')
        ex.result.foo = 'spam'
        ex.config.foo = 'spam'
        ex.showplots = False # avoid PLT.show()
        ex.run() 
        ex() # direct call of the object possible
        del ex # cleanup
    
    
    def test_use_config_via_attributes(self):
        ex = Experiment(config=None)
        ex.config.foo = 'bar'
        assert ex.config.foo == 'bar'
        ex.config.spam = 'eggs'
        assert ex.config.spam == 'eggs'
        ex.result.res1 = 'ham'
        assert ex.result.res1 == 'ham'
        assert ex.result['res1'] == 'ham'
    
    
    def test_reuse(self):
        '''Does a "reuse"-file parameter actually fill the result dict'''
        original_sysarg = copy.copy(sys.argv)
        path = '/tmp/test_reuse.shelve'
        backupFile(path)
        a = 123
        b = [4, ['five', 'six', 7], []]
        sh = shelve.open(path)
        sh['a'] = a
        sh['b'] = b
        sh.close()

        ex = Experiment(config=None, reusefile=path)
        self.assertTrue( ex.result.has_key('b'))
        self.assertEqual( ex.result['a'], a)
        for i in range(len(b)):
            self.assertEqual(b[i], ex.result.b[i], 'b should be the same for item %s and %s' % (str(b[i]),str(ex.result.b[i])) )
        del ex
        
        ex = Experiment(config=None, reusefile=path, resultfile=path, saveresult=True)
        self.assertTrue( ex.result.has_key('b'))
        self.assertEqual( ex.result['a'], a)
        for i in range(len(b)):
            self.assertEqual(b[i], ex.result.b[i], 'b should be the same for item %s and %s' % (str(b[i]),str(ex.result.b[i])) )
        ex.result.somethingnew = 'new'
        ex.run() # will save the resultfile
        del ex
        
        ex = Experiment(config=dict(REUSE_FILE=path))
        self.assertEqual( ex.result.somethingnew, 'new') # should be here now, because in the last ex we safed the resultfile
        self.assertTrue( ex.result.has_key('b'))
        self.assertEqual( ex.result['a'], a)
        for i in range(len(b)):
            self.assertEqual(b[i], ex.result.b[i], 'b should be the same for item %s and %s' % (str(b[i]),str(ex.result.b[i])) )
        del ex
        
        ex = Experiment(config=None, reusefile=path, resultfile=path, saveresult=False)
        self.assertTrue( ex.result.has_key('b'))
        self.assertEqual( ex.result['a'], a)
        for i in range(len(b)):
            self.assertEqual(b[i], ex.result.b[i], 'b should be the same for item %s and %s' % (str(b[i]),str(ex.result.b[i])) )
        ex.result.somethingnew2 = 'new2'
        ex.run() # will save the resultfile
        del ex
        
        sys.argv = ['ignoreme', '--reuse', path]
        print('sys.argv changed to', sys.argv)
        ex = Experiment(config=None, interactive=False)
        self.assertEqual( ex.result.somethingnew, 'new') # should be here now, because in the last ex we safed the resultfile
        self.assertRaises( AttributeError, lambda ex: ex.result.somethingnew2, ex) # should be here now, because in the last ex we safed the resultfile
        self.assertTrue( ex.result.has_key('b'))
        self.assertEqual( ex.result['a'], a)
        for i in range(len(b)):
            self.assertEqual(b[i], ex.result.b[i], 'b should be the same for item %s and %s' % (str(b[i]),str(ex.result.b[i])) )
        del ex
        os.remove(path)
        sys.argv = original_sysarg
        
    
    def test_simple_experiment_and_phases(self):
        ex = Experiment(phases=(self.p1, self.p2, self.p3, self.p4, self.p5, self.p6), config=None)
        self.assertEqual(len(ex.phases),6, 'This experiment in this test should have 6 phases')
        del ex
        

    def test_copy_config_to_curdir(self):
        import os
        oldpath = os.path.abspath(os.curdir)
        shutil.rmtree('/tmp/test-config/', ignore_errors=True)
        shutil.rmtree('/tmp/test-run/', ignore_errors=True)
        os.mkdir('/tmp/test-config/')
        os.mkdir('/tmp/test-run/')
        os.chdir('/tmp/test-config/')
        with open('testconfig.py', 'w') as f:
            f.write('''
if __name__ == '__main__': exit('Usually you should call python run.py')
from experiments import *
config = Config()

config.NAME     = 'test'
config.seed     = 123

config.foo      = 'spam'
config.bar      = ['eggs','ham']
''')
        os.chdir('/tmp/test-run/')
        ex = Experiment(phases=None, config='/tmp/test-config/testconfig.py')
        self.assertTrue(ex.config)
        self.assertEqual(ex.config.seed, 123)
        self.assertEqual(ex.config.foo, 'spam')
        os.chdir(oldpath)
        shutil.rmtree('/tmp/test-config/', ignore_errors=True)
        shutil.rmtree('/tmp/test-run/', ignore_errors=True)
        del ex

    @SkipTest
    def test_config_imports_other_config(self):
        import os
        oldpath = os.path.abspath(os.curdir)
        shutil.rmtree('/tmp/test-config2/', ignore_errors=True)
        shutil.rmtree('/tmp/test-run2/', ignore_errors=True)
        os.mkdir('/tmp/test-config2/')
        os.mkdir('/tmp/test-run2/')
        os.chdir('/tmp/test-config2/')
        with open('config.py', 'w') as f:
            f.write('''
from experiments import Config
config = Config()

config.NAME     = 'base'
config.foo      = 'spam'
config.bar      = 'eggs'
''')
        os.chdir('/tmp/test-run2/')
        with open('config.py', 'w') as f:
            f.write('''
import os
from experiments import Config
config = Config(init_with_configfile='../test-config2/config.py', configfile_relative_to=__file__)
print '__file__ in config.py was:', __file__, os.path.abspath(__file__)
config.NAME     = 'derived'
config.bar      = 'ham'
''')
        ex = Experiment(phases=None, config='config.py')
        self.assertFalse(os.path.exists('/tmp/test-run2/config.py.old'), 'config.py should NOT have been copied to /tmp/test-run2/config.py. And therefore here should not be a config.py.old!!')
        self.assertTrue(ex.config)
        self.assertEqual(ex.config.foo, 'spam')
        self.assertEqual(ex.config.bar, 'ham') # should not be "eggs"
        os.chdir(oldpath)
        shutil.rmtree('/tmp/test-config2/', ignore_errors=True)
        shutil.rmtree('/tmp/test-run2/', ignore_errors=True)
        del ex
    
    
    def test_config_as_dict_given(self):
        d = dict(a=1,b='spam')
        ex = Experiment(config=d)
        ex.config.a
        assert ex.config.a == d['a']
        assert ex.config.b == d['b']
        del ex
    
    
    def test_loadnet(self):
        # If this test reports: "error: db type could not be determined", you 
        # have python installed without gdbm support.
        import mdp
        path = '/tmp/test-saved-mdp-net'
        path2 = '/tmp/test-resultfile-mdp'
        backupFile(path)
        backupFile(path2)
        net = mdp.nodes.PCANode(input_dim=2, output_dim=1) + mdp.nodes.HitParadeNode(n=3)
        net.save(path)
        ex = Experiment(config=None, loadnet=path, resultfile=path2)
        ex.result.NET # should be there now
        assert type(ex.result.NET[1]) == type(net[1]), 'result.NET[1]='+str(ex.result.NET[1])+' and net[1]=' + str(net[1]) + ' should be the same.'
        assert len(ex.result.NET) == len(net)
        ex.run() # triggers storing to resultfile
        # still ex.result.NET should be there
        assert type(ex.result.NET[1]) == type(net[1]), 'result.NET[1]='+str(ex.result.NET[1])+' and net[1]=' + str(net[1]) + ' should be the same.'
        assert len(ex.result.NET) == len(net)
        del ex
        ex = Experiment(config=None, reusefile=path2, loadnet=path)
        assert type(ex.result.NET[1]) == type(net[1]), 'result.NET[1]='+str(ex.result.NET[1])+' and net[1]=' + str(net[1]) + ' should be the same.'
        assert len(ex.result.NET) == len(net)
        del ex.result['NET']
        ex.run() # now save without the NET
        del ex
        # but still the loadnet should load the net even if reuse has no NET
        ex = Experiment(config=None, reusefile=path2, loadnet=path)
        assert type(ex.result.NET[1]) == type(net[1]), 'result.NET[1]='+str(ex.result.NET[1])+' and net[1]=' + str(net[1]) + ' should be the same.'
        assert len(ex.result.NET) == len(net)
        del ex
        os.remove(path)
        os.remove(path2)
    

    def test_run_phase_with_no_phases(self):
        ex = Experiment(phases=None, config=None)
        ex.run() # should be ok 
        ex()
        ex.run(phases='all') # should be ok
        self.assertRaises(ValueError, ex.run, 'somethingstupid') 
        del ex
        ex = Experiment(config=None)
        ex.run() # should be ok 
        self.assertRaises(ValueError, ex.run, 'somethingstupid') 
        self.assertRaises(ValueError, ex.run, ['somethingstupid']) 
        del ex


    def test_run_phase_all(self):
        ex = Experiment(greeting='test_run_phase_all', phases=(self.TestPhase1(), self.AnotherTestPhase(), self.PhaseThatFails(), self.phasefunction), config=None)
        ex.run() # implicit 'all'. Even if a phase fails this should be ok
        for p in ex.phases:
            print(type(p))
            assert p.run_counter == 1, str(p) + ': ' + str(p.run_counter)
        del ex


    def test_run_phase_function(self):
        ex = Experiment(phases=[self.phasefunction], config=None)
        ex.run() # even if a phase fails this should be ok
        del ex


    def test_run_phase_that_does_not_exist(self):
        ex = Experiment(phases=(self.TestPhase1(), self.AnotherTestPhase(), self.PhaseThatFails()), config=None)
        self.assertRaises(ValueError, ex.run, 'Phase') 
        self.assertRaises(ValueError, ex.run, '' ) 
        del ex


    def test_run_phase_by_list_of_classnames(self):
        ex = Experiment(phases=(self.TestPhase1(), self.AnotherTestPhase(), self.PhaseThatFails()), config=None, stderrloglevel='DEBUG')
        assert len(ex.phases) == 3
        for p in ex.phases:
            assert p.run_counter == 0, p.run_counter
        ex.run(phases='TestPhase1')
        ex.run(phases='AnotherTestPhase')
        ex.run(phases='PhaseThatFails')
        for p in ex.phases:
            assert p.run_counter == 1, str(p)+': '+str(p.run_counter)
        ex.run(phases='TEstPHAse1')
        ex.run(phases=['anothertestphase'])
        ex.run(phases=(' PhaseThatFAILS'))
        assert ex.phases[0].run_counter == 1, "TestPhase1 should have needsrun() returning false."
        for p in ex.phases[1:]: # TestPhase1 has needsrerun and therefore counter will not be incr.
            assert p.run_counter == 2,  str(p) + ' counter=' + str(p.run_counter)
        ex.run(phases=['TestPhase1','AnotherTestPhase','phasethatfails'])
        assert ex.phases[0].run_counter == 1, "TestPhase1 should have needsrun() returning false."
        for p in ex.phases[1:]:
            assert p.run_counter == 3
        ex.run()
        for p in ex.phases[1:]:
            assert p.run_counter == 4
            

    def test_saveresult(self):
        oldpath = os.path.abspath(os.curdir)
        path = '/tmp/test-saveresult/'
        if os.path.exists(path): shutil.rmtree(path, ignore_errors=True)
        os.mkdir(path)
        os.chdir(path)
        ex = Experiment(saveresult=False, 
                        phases=(self.TestPhase1(), self.AnotherTestPhase()), 
                        config=None)
        ex.run()
        assert ex.config.RESULT_FILE == None
        assert len(ex.result) > 0, str(ex.result) # even if the results should not be stored, there should be a result object containing 'foo'. See SetUp()
        del ex

        ex = Experiment(saveresult=True, 
                        phases=(self.TestPhase1(), self.AnotherTestPhase()), 
                        config=None)
        ex.run()
        db = shelve.open( ex.config.RESULT_FILE )
        assert len(db) > 0
        db['foo']
        db.close()
        os.chdir(oldpath)


    def test_use_matplotlib_backend_pdf(self):
        ex = Experiment(config=None, matplotlib_backend='pdf')
        ex.run()
        del ex
        

    def test_loglevels_as_int(self):
        ex = Experiment(loglevel=0)
        ex = Experiment(stderrloglevel=20)
        ex = Experiment(fileloglevel=30)
        
        ex = Experiment(loglevel='warn')
        ex = Experiment(stderrloglevel=' INFO ')
        ex = Experiment(fileloglevel='DEBUg') # to test case insensitiveness
        
        sys.argv = ['ignoreme', '--stderrloglevel', 'info']
        ex = Experiment(interactive=False, loglevel='warn')
        sys.argv = ['ignoreme', '--stderrloglevel', 'info']
        ex = Experiment(interactive=False, fileloglevel=12)
        sys.argv = ['ignoreme', '--stderrloglevel', 'info']
        ex = Experiment(interactive=False, logfile=None, fileloglevel=10)
        
        
    @raises(ValueError)
    def test_name_all_is_not_allowed_for_the_wrapped_function(self):
        def all(a): pass
        p = Phase(all)
    
    @raises(ValueError)
    def test_name_all_is_not_allowed_for_a_Phase(self):
        class All(Phase): pass
        p = All()
        

    def test_memory(self):
        ex = Experiment()
        ex.memory()

if __name__ == "__main__":
	unittest.main()

