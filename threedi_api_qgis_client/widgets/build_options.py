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

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin = plugin
        self.new_schematisation_wizard = None
        self.pb_new.clicked.connect(self.new_schematisation)
        self.pb_load_local.clicked.connect(self.load_local_schematisation)
        self.pb_load_web.clicked.connect(self.load_web_schematisation)

    @api_client_required
    def new_schematisation(self):
        """Create a new schematisation."""
        self.new_schematisation_wizard = NewSchematisationWizard(self.plugin, self)
        self.new_schematisation_wizard.exec_()
        new_schematisation = self.new_schematisation_wizard.new_schematisation
        if new_schematisation is not None:
            new_schematisation_sqlite = self.new_schematisation_wizard.new_schematisation_sqlite
            self.plugin.current_schematisation_id = new_schematisation.id
            self.plugin.current_schematisation_name = new_schematisation.name
            self.plugin.current_schematisation_revision = 1
            self.plugin.current_schematisation_sqlite = new_schematisation_sqlite
            self.plugin.update_schematisation_view()
            self.close()

    def load_local_schematisation(self, schematisation_sqlite=None):
        """Load locally stored schematisation."""
        if not schematisation_sqlite:
            schematisation_sqlite = get_filepath(self, extension_filter="Spatialite Files (*.sqlite *.SQLITE)")
        if schematisation_sqlite:
            try:
                schematisation_id, schematisation_name, revision_number = get_local_schematisation_info(
                    schematisation_sqlite
                )
                self.plugin.current_schematisation_id = schematisation_id
                self.plugin.current_schematisation_name = schematisation_name
                self.plugin.current_schematisation_revision = revision_number
                self.plugin.current_schematisation_sqlite = schematisation_sqlite
            except (TypeError, ValueError):
                error_msg = "Invalid schematisation directory structure. Loading schematisation canceled."
                self.plugin.communication.show_error(error_msg)
            self.plugin.update_schematisation_view()
            self.close()

    @api_client_required
    def load_web_schematisation(self):
        """Download an existing schematisation."""
        schematisation_download = SchematisationDownload(self.plugin)
        schematisation_download.exec_()
        schematisation_sqlite = schematisation_download.downloaded_schematisation_filepath
        if schematisation_sqlite is not None:
            self.load_local_schematisation(schematisation_sqlite)
