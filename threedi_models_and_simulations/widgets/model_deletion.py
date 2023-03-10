# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import logging
import os
from operator import attrgetter

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QDateTime, Qt
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from threedi_api_client.openapi import ApiException

from ..api_calls.threedi_calls import ThreediCalls
from ..utils import extract_error_message

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
        self.organisation = self.plugin_dock.organisations[self.parent_widget.schematisation.owner]
        self.label_template = self.label.text()
        self.threedi_models_to_show = []
        self.models_model = QStandardItemModel()
        self.models_tv.setModel(self.models_model)
        self.pb_delete.clicked.connect(self.delete_models)
        self.pb_cancel.clicked.connect(self.reject)
        self.cb_filter.stateChanged.connect(self.filter_models_by_username)
        self.models_tv.selectionModel().selectionChanged.connect(self.toggle_delete_models)
        self.check_limits()

    def toggle_delete_models(self):
        """Toggle delete button if any model is selected."""
        selection_model = self.models_tv.selectionModel()
        if selection_model.hasSelection():
            self.pb_delete.setEnabled(True)
        else:
            self.pb_delete.setDisabled(True)

    def filter_models_by_username(self):
        """Filter models list and show only those created by currently logged-in user."""
        if self.cb_filter.isChecked():
            user_models = [
                model for model in self.threedi_models_to_show if model.user == self.plugin_dock.current_user
            ]
            self.populate_models(user_models)
        else:
            self.populate_models(self.threedi_models_to_show)

    def check_limits(self):
        """Check 3Di models creation limits."""
        self.threedi_models_to_show.clear()
        try:
            tc = ThreediCalls(self.threedi_api)
            schematisation_limit_filters = {
                "limit": tc.FETCH_LIMIT,
                "schematisation_name": self.local_schematisation.name,
            }
            schematisation_limit = self.parent_widget.MAX_SCHEMATISATION_MODELS
            threedi_models, models_count = tc.fetch_3di_models_with_count(**schematisation_limit_filters)
            if models_count >= schematisation_limit:
                self.label.setText(self.label_template.format("schematisation", schematisation_limit, models_count))
                self.setup_dialog(threedi_models)
                return
            organisation_uuid = self.organisation.unique_id
            contract = tc.fetch_contracts(organisation__unique_id=organisation_uuid)[0]
            organisation_limit = contract.threedimodel_limit
            organisation_limit_filters = {
                "limit": tc.FETCH_LIMIT,
                "schematisation_owner": organisation_uuid,
            }
            threedi_models, models_count = tc.fetch_3di_models_with_count(**organisation_limit_filters)
            if models_count >= organisation_limit:
                self.label.setText(self.label_template.format("organisation", organisation_limit, models_count))
                self.setup_dialog(threedi_models)
                return
            else:
                self.accept()
        except ApiException as e:
            error_msg = extract_error_message(e)
            self.communication.show_error(error_msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)

    def setup_dialog(self, threedi_models):
        """Setup model deletion dialog."""
        self.threedi_models_to_show.clear()
        self.populate_models(threedi_models)
        self.threedi_models_to_show = threedi_models

    def populate_models(self, threedi_models):
        """Populate 3Di models within a dialog."""
        self.models_tv.clearSelection()
        self.models_model.clear()
        header = ["ID", "Model", "Schematisation", "Revision", "Created By", "Created On"]
        self.models_model.setHorizontalHeaderLabels(header)
        for sim_model in sorted(threedi_models, key=attrgetter("revision_commit_date"), reverse=True):
            id_item = QStandardItem(str(sim_model.id))
            name_item = QStandardItem(sim_model.name)
            name_item.setData(sim_model, role=Qt.UserRole)
            schema_item = QStandardItem(sim_model.schematisation_name)
            rev_item = QStandardItem(sim_model.revision_number)
            created_by_item = QStandardItem(sim_model.user)
            created_on = sim_model.revision_commit_date.split("T")[0]
            created_on_datetime = QDateTime.fromString(created_on, "yyyy-MM-dd")
            created_on_item = QStandardItem(created_on_datetime.toString("dd-MMMM-yyyy"))
            self.models_model.appendRow([id_item, name_item, schema_item, rev_item, created_by_item, created_on_item])

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
            error_msg = extract_error_message(e)
            self.communication.show_error(error_msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)
        finally:
            self.check_limits()
