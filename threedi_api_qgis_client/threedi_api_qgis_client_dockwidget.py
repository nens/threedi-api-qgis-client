# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from .widgets.wizard import SimulationWizard
from .widgets.log_in import LogInDialog
from .api_calls.threedi_calls import ApiClient
from .utils import set_icon

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'threedi_api_qgis_client_dockwidget_base.ui'))


class ThreediQgisClientDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(ThreediQgisClientDockWidget, self).__init__(parent)
        self.setupUi(self)
        self.api_client = None
        self.current_model = None
        self.log_in_dialog = None
        self.widget_authorized.hide()
        self.btn_start.clicked.connect(self.log_in)
        self.btn_simulate.clicked.connect(self.run_wizard)
        self.btn_log_out.clicked.connect(self.log_out)
        set_icon(self.btn_build, 'build.svg')
        set_icon(self.btn_check, 'check.svg')
        set_icon(self.btn_upload, 'upload.svg')
        set_icon(self.btn_simulate, 'api.svg')
        set_icon(self.btn_results, 'results.svg')

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def log_in(self):
        self.log_in_dialog = LogInDialog()
        self.log_in_dialog.exec_()
        self.api_client = self.log_in_dialog.api_client
        self.current_model = self.log_in_dialog.current_model
        if self.current_model is None:
            return

        self.widget_unauthorized.hide()
        self.widget_authorized.show()
        self.btn_simulate.setEnabled(True)

        self.label_user.setText(self.log_in_dialog.user)
        self.label_repo.setText(self.current_model.repository_slug)
        revision = self.log_in_dialog.revisions[self.current_model.revision_hash]
        self.label_rev.setText(f"{revision.number}")
        self.label_db.setText(self.current_model.model_ini)

    def log_out(self):
        self.log_in_dialog = None
        self.api_client = None
        self.current_model = None
        self.widget_unauthorized.show()
        self.widget_authorized.hide()
        self.btn_simulate.setDisabled(True)

    def run_wizard(self):
        d = SimulationWizard(self)
        d.exec_()
