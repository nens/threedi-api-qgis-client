# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import logging
import os
from qgis.PyQt import uic
from .log_in import api_client_required
from ..widgets.new_schematisation_wizard import NewSchematisationWizard
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
        self.new_schematisation_wizard = NewSchematisationWizard(self.plugin)
        self.close()
        self.new_schematisation_wizard.exec_()

    def load_local_schematisation(self):
        """Load locally stored schematisation."""
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
                error_msg = "Invalid schematisation directory structure. Loading local schematisation canceled."
                self.plugin.communication.show_error(error_msg)
            self.plugin.update_schematisation_view()
            self.close()

    @api_client_required
    def load_web_schematisation(self):
        """Download an existing schematisation."""
        pass
