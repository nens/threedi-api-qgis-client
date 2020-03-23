#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

case "$OSTYPE" in
    solaris*) ;;
    darwin*)  ln -s $DIR/threedi_api_qgis_client ~/Library/Application\ Support/QGIS/QGIS3/profiles/default/python/plugins/threedi_api_qgis_client ;;
    linux*)   ln -s $DIR/threedi_api_qgis_client ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/threedi_api_qgis_client  ;;
    bsd*)     ;;
    msys*)    ;;
    *)        ;;
esac
