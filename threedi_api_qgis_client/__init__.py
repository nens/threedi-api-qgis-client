# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load ThreediQgisClient class from file ThreediQgisClient.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .threedi_api_qgis_client import ThreediQgisClient
    return ThreediQgisClient(iface)
