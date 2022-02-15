#!/bin/bash
###########################################################################
#                                                                         #
#   This program is free software; you can redistribute it and/or modify  #
#   it under the terms of the GNU General Public License as published by  #
#   the Free Software Foundation; either version 2 of the License, or     #
#   (at your option) any later version.                                   #
#                                                                         #
###########################################################################

set -e

rm -f threedi_models_and_simulations.zip && cd threedi_models_and_simulations && git archive --prefix=threedi_models_and_simulations/ -o ../threedi_models_and_simulations.zip HEAD
