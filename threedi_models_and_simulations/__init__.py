# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load ThreediModelsAndSimulations class from file ThreediModelsAndSimulations.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .qlogging import setup_logging

    setup_logging()

    from .threedi_models_and_simulations import ThreediModelsAndSimulations

    return ThreediModelsAndSimulations(iface)
