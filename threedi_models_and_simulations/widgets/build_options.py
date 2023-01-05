# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import logging
from qgis.PyQt.QtCore import QSettings
from .log_in import api_client_required
from ..widgets.new_schematisation_wizard import NewSchematisationWizard
from ..widgets.schematisation_load_local import SchematisationLoad
from ..widgets.schematisation_download import SchematisationDownload

logger = logging.getLogger(__name__)


class BuildOptions:
    """Schematisation build options class."""

    def __init__(self, plugin_dock):
        self.plugin_dock = plugin_dock
        self.new_schematisation_wizard = None

    @api_client_required
    def new_schematisation(self):
        """Create a new schematisation."""
        self.new_schematisation_wizard = NewSchematisationWizard(self.plugin_dock)
        self.new_schematisation_wizard.exec_()
        new_schematisation = self.new_schematisation_wizard.new_schematisation
        if new_schematisation is not None:
            local_schematisation = self.new_schematisation_wizard.new_local_schematisation
            self.load_local_schematisation(local_schematisation, action="created")

    def load_local_schematisation(self, local_schematisation=None, action="loaded"):
        """Load locally stored schematisation."""
        if not local_schematisation:
            schematisation_load = SchematisationLoad(self.plugin_dock)
            schematisation_load.exec_()
            local_schematisation = schematisation_load.selected_local_schematisation
        if local_schematisation and local_schematisation.sqlite:
            try:
                self.plugin_dock.current_local_schematisation = local_schematisation
                self.plugin_dock.update_schematisation_view()
                sqlite_filepath = local_schematisation.sqlite
                msg = f"Schematisation '{local_schematisation.name}' {action}!\n"
                msg += f"Please use the 3Di Toolbox to load it to your project from the Spatialite:\n{sqlite_filepath}"
                self.plugin_dock.communication.show_info(msg)
            except (TypeError, ValueError):
                error_msg = "Invalid schematisation directory structure. Loading schematisation canceled."
                self.plugin_dock.communication.show_error(error_msg)
                self.plugin_dock.update_schematisation_view()

    @api_client_required
    def download_schematisation(self):
        """Download an existing schematisation."""
        schematisation_download = SchematisationDownload(self.plugin_dock)
        schematisation_download.exec_()
        downloaded_local_schematisation = schematisation_download.downloaded_local_schematisation
        if downloaded_local_schematisation is not None:
            self.load_local_schematisation(local_schematisation=downloaded_local_schematisation, action="downloaded")
            wip_revision = downloaded_local_schematisation.wip_revision
            if wip_revision is not None:
                settings = QSettings("3di", "qgisplugin")
                settings.setValue("last_used_spatialite_path", wip_revision.schematisation_dir)
