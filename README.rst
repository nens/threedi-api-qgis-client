=======================
threedi-api-qgis-client
=======================

.. image:: https://travis-ci.com/nens/threedi-api-qgis-client.svg?branch=master
        :target: https://travis-ci.com/nens/threedi-api-qgis-client

.. image:: https://readthedocs.org/projects/threedi-api-qgis-client/badge/?version=latest
        :target: https://threedi-api-qgis-client.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


Deployment
----------

Make sure you have ``zest.releaser`` with ``qgispluginreleaser`` installed. The
``qgispluginreleaser`` ensures the metadata.txt, which is used by the qgis plugin
manager, is also updated to the new version. To make a new release enter the following
commands and follow their steps::

    $ cd /path/to/the/plugin
    $ fullrelease

This creates a new release and tag on github. Additionally, a zip file
``threedi_api_qgis_client_<version>.zip`` is created. Upload this zip-file to 
https://artifacts.lizard.net/ via the ``upload-artifact.sh`` script. You'll need 
to set $ARTIFACTS_KEY environment variable. Get the key from 
https://artifacts.lizard.net/admin/ Afterwards run it like this::

    $ ./upload-artifact.sh threedi_api_qgis_client_<version>.zip

You can also manually create this zip file and upload it to a server from where you want
to distribute the new release::

    $ make zip
    $ scp threedi_api_qgis_client_<version>.zip <user.name>@packages-server.example.local:/srv/packages.lizard.net/var/plugins


Other
-----



Python Boilerplate contains all the boilerplate you need to create a Python package.


* Free software: GNU General Public License v3
* Documentation: https://threedi-api-qgis-client.readthedocs.io.


Features
--------

* TODO

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
