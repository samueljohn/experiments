'''
Run computer simulation experiments and configure them. The geek way.

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
#future stuff not used because python 2.6 cannot handle the imports that way
#from __future__ import print_function, division, absolute_import
#from experiments.phase import Phase
#from experiments.experiment import ( Experiment, get_version_string,
#                                     timehost_string, host_string, time_string )
#from experiments.config import Config

from loop_unroller import Unroller
from phase import Phase, DependsOnAnotherPhase
from experiment import ( Experiment, get_version_string,
                                     timehost_string, host_string, time_string )
from config import Config
from loop_unroller import Unroller

__version__ = '0.9.5'

# todo: all sub tests callable here? perhaps not needed due to py.test
