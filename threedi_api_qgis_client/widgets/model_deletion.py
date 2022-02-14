# 3Di Models & Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import logging
import os
from operator import attrgetter
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QDateTime
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from threedi_api_client.openapi import ApiException
from ..api_calls.threedi_calls import ThreediCalls

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "model_deletion.ui"))


logger = logging.getLogger(__name__)


class ModelDeletionDialog(uicls, basecls):
    """Dialog for model(s) deletion."""

    def __init__(self, plugin_dock, parent):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_widget = parent
        self.plugin_dock = plugin_dock
        self.communication = self.plugin_dock.communication
        self.threedi_api = self.plugin_dock.threedi_api
        self.local_schematisation = self.plugin_dock.current_local_schematisation
        self.threedi_models = None
        self.models_model = QStandardItemModel()
        self.models_tv.setModel(self.models_model)
        self.pb_delete.clicked.connect(self.delete_models)
        self.pb_cancel.clicked.connect(self.reject)
        self.models_tv.selectionModel().selectionChanged.connect(self.toggle_delete_models)
        self.fetch_3di_models()

    def toggle_delete_models(self):
        """Toggle delete button if any model is selected."""
        selection_model = self.models_tv.selectionModel()
        if selection_model.hasSelection():
            self.pb_delete.setEnabled(True)
        else:
            self.pb_delete.setDisabled(True)

    def fetch_3di_models(self):
        """Fetching 3Di models list."""
        try:
            tc = ThreediCalls(self.threedi_api)
            threedi_models, models_count = tc.fetch_3di_models_with_count(
                limit=tc.FETCH_LIMIT, schematisation_name=self.local_schematisation.name
            )
            self.models_model.clear()
            if models_count < self.parent_widget.MAX_SCHEMATISATION_MODELS:
                self.accept()
            header = ["ID", "Model", "Schematisation", "Revision", "Last updated", "Updated by"]
            self.models_model.setHorizontalHeaderLabels(header)
            for sim_model in sorted(threedi_models, key=attrgetter("revision_commit_date"), reverse=True):
                if sim_model.schematisation_id != self.local_schematisation.id:
                    continue
                id_item = QStandardItem(str(sim_model.id))
                name_item = QStandardItem(sim_model.name)
                name_item.setData(sim_model, role=Qt.UserRole)
                schema_item = QStandardItem(sim_model.schematisation_name)
                rev_item = QStandardItem(sim_model.revision_number)
                last_updated_day = sim_model.revision_commit_date.split("T")[0]
                lu_datetime = QDateTime.fromString(last_updated_day, "yyyy-MM-dd")
                lu_item = QStandardItem(lu_datetime.toString("dd-MMMM-yyyy"))
                ub_item = QStandardItem(sim_model.user)
                self.models_model.appendRow([id_item, name_item, schema_item, rev_item, lu_item, ub_item])
            self.threedi_models = threedi_models
        except ApiException as e:
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            self.communication.show_error(error_msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)

    def delete_models(self):
        """Deleting selected model(s)."""
        selection_model = self.models_tv.selectionModel()
        if not selection_model.hasSelection():
            return
        try:
            tc = ThreediCalls(self.threedi_api)
            for index in selection_model.selectedRows():
                current_row = index.row()
                model_id_item = self.models_model.item(current_row, 0)
                model_id = int(model_id_item.text())
                tc.delete_3di_model(model_id)
        except ApiException as e:
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            self.communication.show_error(error_msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)
        finally:
            self.fetch_3di_models()
