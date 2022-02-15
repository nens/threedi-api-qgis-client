#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

case "$OSTYPE" in
    solaris*) ;;
    darwin*)  ln -s $DIR/threedi_models_and_simulations ~/Library/Application\ Support/QGIS/QGIS3/profiles/default/python/plugins/threedi_models_and_simulations ;;
    linux*)   ln -s $DIR/threedi_models_and_simulations ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/threedi_models_and_simulations  ;;
    bsd*)     ;;
    msys*)    ;;
    *)        ;;
esac
