# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import logging
import os
from qgis.PyQt import uic
from .log_in import api_client_required
from ..widgets.new_schematisation_wizard import NewSchematisationWizard
from ..widgets.schematisation_download import SchematisationDownload

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "build_options.ui"))

logger = logging.getLogger(__name__)


class BuildOptionsDialog(uicls, basecls):
    """Dialog with schematisation build options."""

    def __init__(self, plugin_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin_dock = plugin_dock
        self.new_schematisation_wizard = None
        self.pb_new.clicked.connect(self.new_schematisation)
        self.pb_load_local.clicked.connect(self.load_local_schematisation)
        self.pb_load_web.clicked.connect(self.download_schematisation)

    @api_client_required
    def new_schematisation(self):
        """Create a new schematisation."""
        self.new_schematisation_wizard = NewSchematisationWizard(self.plugin_dock, self)
        self.close()
        self.new_schematisation_wizard.exec_()
        new_schematisation = self.new_schematisation_wizard.new_schematisation
        if new_schematisation is not None:
            local_schematisation = self.new_schematisation_wizard.new_local_schematisation
            self.load_local_schematisation(local_schematisation, action="created")

    def load_local_schematisation(self, local_schematisation=None, action="loaded"):
        """Load locally stored schematisation."""
        if local_schematisation and local_schematisation.sqlite:
            try:
                self.plugin_dock.current_local_schematisation = local_schematisation
                self.plugin_dock.update_schematisation_view()
                sqlite_filepath = local_schematisation.sqlite
                msg = f"Schematisation '{local_schematisation.name}' {action}!\n"
                msg += f"Please use the 3Di Toolbox to load it to your project from the Spatialite:\n{sqlite_filepath}"
                self.plugin_dock.communication.show_info(msg)
                self.close()
            except (TypeError, ValueError):
                error_msg = "Invalid schematisation directory structure. Loading schematisation canceled."
                self.plugin_dock.communication.show_error(error_msg)
                self.plugin_dock.update_schematisation_view()

    @api_client_required
    def download_schematisation(self):
        """Download an existing schematisation."""
        schematisation_download = SchematisationDownload(self.plugin_dock)
        self.close()
        schematisation_download.exec_()
        downloaded_local_schematisation = schematisation_download.downloaded_local_schematisation
        if downloaded_local_schematisation is not None:
            self.load_local_schematisation(local_schematisation=downloaded_local_schematisation, action="downloaded")
