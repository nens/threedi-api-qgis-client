# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import logging
import os
from qgis.PyQt import uic

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "build_options.ui"))

logger = logging.getLogger(__name__)


class BuildOptionsDialog(uicls, basecls):
    """Dialog with schematisation build options."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin = plugin
        self.communication = self.plugin.communication
        self.user = None
        self.threedi_api = None
