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
        self.pushButton.clicked.connect(self.run_wizard)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def run_wizard(self):
        d = SimulationWizard(self)
        d.exec_()
