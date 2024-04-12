=======================
threedi-api-qgis-client
=======================

.. image:: https://travis-ci.com/nens/threedi-api-qgis-client.svg?branch=master
        :target: https://travis-ci.com/nens/threedi-api-qgis-client

Deployment
----------

Make sure you have ``zest.releaser`` with ``qgispluginreleaser`` installed. The
``qgispluginreleaser`` ensures the metadata.txt, which is used by the qgis plugin
manager, is also updated to the new version. To make a new release enter the following
commands and follow their steps::

    $ cd /path/to/the/plugin
    $ fullrelease

This creates a new release and tag on github. Additionally, a zip file
``threedi_models_and_simulations.<version>.zip`` is created. Upload this zip-file to
https://artifacts.lizard.net/ via the ``upload-artifact.sh`` script. You'll need
to set $ARTIFACTS_KEY environment variable. Get the key from
https://artifacts.lizard.net/admin/ Afterwards run it like this::

    $ make zip
    $ bash upload-artifact.sh threedi_api_qgis_client_<version>.zip


Local development notes
-----------------------

On Linux, local development happens with docker to make sure we're working in a nicely
isolated environment. To start the development environment, run the following commands::

    $ docker compose build
    $ xhost +localhost
    $ docker compose up

and::

    $ docker compose run --rm qgis make test

On Mac, you might need to install xquartz, adjust the DISPLAY env variable in the docker-compose.yml
to `host.docker.internal:0` and remove the //tmp/x-something mount from volumes.
