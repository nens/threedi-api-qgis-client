# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import logging
import os
from math import ceil
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from threedi_api_client.openapi import ApiException
from ..api_calls.threedi_calls import ThreediCalls

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "schematisation_download.ui"))


logger = logging.getLogger(__name__)


class SchematisationDownload(uicls, basecls):
    """Dialog for schematisation download."""

    TABLE_LIMIT = 10

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin = plugin
        self.threedi_api = self.plugin.threedi_api
        self.schematisations = None
        self.schematisation_revisions = None
        self.current_schematisation = None
        self.tv_model = QStandardItemModel()
        self.models_tv.setModel(self.tv_model)
        self.pb_prev_page.clicked.connect(self.move_backward)
        self.pb_next_page.clicked.connect(self.move_forward)
        self.page_sbox.valueChanged.connect(self.fetch_schematisations_revisions)
        self.pb_download.clicked.connect(self.download_schematisation)
        self.pb_cancel.clicked.connect(self.cancel_download_schematisation)
        self.search_le.returnPressed.connect(self.search_schematisation)
        self.models_tv.selectionModel().selectionChanged.connect(self.toggle_download_schematisation)
        self.fetch_schematisations_revisions()

    def toggle_download_schematisation(self):
        """Toggle download button if any schematisation is selected."""
        selection_model = self.models_tv.selectionModel()
        if selection_model.hasSelection():
            self.pb_download.setEnabled(True)
        else:
            self.pb_download.setDisabled(True)

    def move_backward(self):
        """Moving to the previous results page."""
        self.page_sbox.setValue(self.page_sbox.value() - 1)

    def move_forward(self):
        """Moving to the next results page."""
        self.page_sbox.setValue(self.page_sbox.value() + 1)

    def fetch_schematisations_revisions(self):
        """Fetching schematisation revisions list."""
        try:
            tc = ThreediCalls(self.threedi_api)
            offset = (self.page_sbox.value() - 1) * self.TABLE_LIMIT
            text = self.search_le.text()

            schematisations, schematisations_count = tc.fetch_schematisations_with_count(
                limit=self.TABLE_LIMIT, offset=offset, name_contains=text
            )
            pages_nr = ceil(schematisations_count / self.TABLE_LIMIT) or 1
            self.page_sbox.setMaximum(pages_nr)
            self.page_sbox.setSuffix(f" / {pages_nr}")
            self.tv_model.clear()
            header = ["Schematisation", "Slug", "Owner"]#, "Commit message", "Commit user"]
            self.tv_model.setHorizontalHeaderLabels(header)
            for schematisation in schematisations:
                name_item = QStandardItem(schematisation.name)
                name_item.setData(schematisation, role=Qt.UserRole)
                slug_item = QStandardItem(schematisation.slug)
                owner_item = QStandardItem(schematisation.owner)
                self.tv_model.appendRow([name_item, slug_item, owner_item])
            for i in range(len(header)):
                self.models_tv.resizeColumnToContents(i)
            self.schematisations = schematisations
        except ApiException as e:
            self.close()
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            self.communication.show_error(error_msg)
        except Exception as e:
            self.close()
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)

    def search_schematisation(self):
        """Method used for searching schematisation with text typed withing search bar."""
        self.page_sbox.valueChanged.disconnect(self.fetch_schematisations_revisions)
        self.page_sbox.setValue(1)
        self.page_sbox.valueChanged.connect(self.fetch_schematisations_revisions)
        self.fetch_schematisations_revisions()

    def download_schematisation(self):
        """Loading selected schematisation revision."""
        index = self.models_tv.currentIndex()
        if index.isValid():
            current_row = index.row()
            name_item = self.tv_model.item(current_row, 0)
            self.current_schematisation = name_item.data(Qt.UserRole)
        self.close()

    def cancel_download_schematisation(self):
        """Cancel loading model."""
        self.close()
