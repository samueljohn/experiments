#!/usr/bin/env python
''''''


def do_something(ex, config, result):
    x = []
    for n in xrange(config.num_runs):
        x.append(n)
    ex.log.info('computed x %s', str(x))
    return x
    
    
    
    

from experiments import *
ex = Experiment( interactive=False if __name__ == '__main__' else True,
                 phases=( [ do_something ]),
                 version=(1,0,0),
                 greeting='Some stuff.',
                 author='Your Name')

        

    