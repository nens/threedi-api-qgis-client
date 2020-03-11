# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from .widgets.wizard import SimulationWizard
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'threedi_api_qgis_client_dockwidget_base.ui'))


class ThreediQgisClientDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(ThreediQgisClientDockWidget, self).__init__(parent)
        self.setupUi(self)
        self.widget_authorized.hide()
        self.btn_start.clicked.connect(self.log_in)
        self.btn_simulate.clicked.connect(self.run_wizard)
        self.btn_log_out.clicked.connect(self.log_out)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def log_in(self):
        self.widget_unauthorized.hide()
        self.widget_authorized.show()
        self.btn_simulate.setEnabled(True)

    def log_out(self):
        self.widget_unauthorized.show()
        self.widget_authorized.hide()
        self.btn_simulate.setDisabled(True)

    def run_wizard(self):
        d = SimulationWizard(self)
        d.exec_()
