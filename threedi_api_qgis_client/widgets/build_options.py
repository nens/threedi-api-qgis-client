# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import logging
import os
from qgis.PyQt import uic
from .log_in import api_client_required
from ..widgets.new_schematisation_wizard import NewSchematisationWizard
from ..widgets.schematisation_download import SchematisationDownload
from ..utils import get_local_schematisation_info
from ..utils_ui import get_filepath

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
            sqlite_filepath = self.new_schematisation_wizard.new_schematisation_sqlite
            if sqlite_filepath is not None:
                self.load_local_schematisation(sqlite_filepath=sqlite_filepath, action="created")

    def load_local_schematisation(self, sqlite_filepath=None, action="loaded"):
        """Load locally stored schematisation."""
        if not sqlite_filepath:
            sqlite_filepath = get_filepath(self, extension_filter="Spatialite Files (*.sqlite *.SQLITE)")
        if sqlite_filepath:
            try:
                schematisation_id, schematisation_name, revision_number = get_local_schematisation_info(sqlite_filepath)
                self.plugin_dock.current_schematisation_id = schematisation_id
                self.plugin_dock.current_schematisation_name = schematisation_name
                self.plugin_dock.current_schematisation_revision = revision_number
                self.plugin_dock.current_schematisation_sqlite = sqlite_filepath
                self.plugin_dock.update_schematisation_view()
                msg = f"Schematisation '{schematisation_name} (revision {revision_number})' {action}!\n"
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
        sqlite_filepath = schematisation_download.downloaded_schematisation_filepath
        if sqlite_filepath is not None:
            self.load_local_schematisation(sqlite_filepath=sqlite_filepath, action="downloaded")
