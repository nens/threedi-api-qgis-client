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

rm -f threedi_api_qgis_client.zip && cd threedi_api_qgis_client && git archive --prefix=threedi_api_qgis_client/ -o ../threedi_api_qgis_client.zip HEAD
