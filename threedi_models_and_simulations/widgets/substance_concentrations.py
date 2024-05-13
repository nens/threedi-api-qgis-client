import csv
import os
from functools import partial

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (QFileDialog, QGridLayout, QGroupBox,
                                 QHBoxLayout, QLabel, QLineEdit, QPushButton,
                                 QWidget)


class SubstanceConcentrationsWidget(QWidget):
    """Widget for handling substance concentrations."""

    def __init__(self, substances, handle_substance_error, parent=None):
        super().__init__(parent)
        self.substances = substances
        self.handle_substance_errors = handle_substance_error
        self.substance_concentrations = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout()
        self.groupbox = QGroupBox("Substance concentrations")
        self.groupbox.setLayout(layout)
        self.groupbox.setFont(QFont("Segoe UI", 14, QFont.Bold))
        font = QFont("Segoe UI", 10, QFont.Normal)
        for i, substance in enumerate(self.substances):
            name = substance["name"]
            label = QLabel(f"{name}:")
            label.setMinimumWidth(100)
            label.setFont(font)
            line_edit = QLineEdit()
            line_edit.setObjectName("le_substance_" + name)
            line_edit.setReadOnly(True)
            line_edit.setFrame(False)
            line_edit.setFont(font)
            line_edit.setStyleSheet("background-color: white")
            upload_button = QPushButton("Upload CSV")
            upload_button.setObjectName("pb_substance_" + name)
            upload_button.setMinimumWidth(100)
            upload_button.setFont(font)
            horizontal_layout = QHBoxLayout()
            horizontal_layout_widget = QWidget()
            horizontal_layout_widget.setLayout(horizontal_layout)
            horizontal_layout.setContentsMargins(0, 0, 9, 0)
            horizontal_layout.addWidget(label)
            horizontal_layout.addWidget(line_edit)
            horizontal_layout.addWidget(upload_button)
            layout.addWidget(horizontal_layout_widget, i, 0)
        self.connect_substance_upload_signals()

    def connect_substance_upload_signals(self):
        """Connect substance upload signals."""
        for substance in self.substances:
            name = substance["name"]
            upload_button = self.groupbox.findChild(QPushButton, "pb_substance_" + name)
            upload_button.clicked.connect(partial(self.load_substance_csv, name))

    def load_substance_csv(self, name):
        """Load substance CSV file."""
        substances, filename = self.open_substance_upload_dialog(name)
        if not filename:
            return
        le_substance = self.groupbox.findChild(QLineEdit, "le_substance_" + name)
        le_substance.setText(filename)
        self.substance_concentrations.update(substances)

    def open_substance_upload_dialog(self, name):
        """Open dialog for selecting CSV file with laterals."""
        last_folder = QSettings().value("threedi/last_substances_folder", os.path.expanduser("~"), type=str)
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(
            self, f"Substance Concentrations for {name}", last_folder, file_filter
        )
        if len(filename) == 0:
            return None, None
        QSettings().setValue("threedi/last_substances_folder", os.path.dirname(filename))
        substances = {}
        substance_list = []
        with open(filename, encoding="utf-8-sig") as substance_file:
            substance_reader = csv.reader(substance_file)
            substance_list += list(substance_reader)
        error_msg = self.handle_substance_errors(substance_list)
        if error_msg is not None:
            return None, None
        for id, timeseries in substance_list:
            try:
                concentrations = [[float(f) for f in line.split(",")] for line in timeseries.split("\n")]
                substance = {
                    "substance": name,
                    "concentrations": concentrations,
                }
                if id not in substances:
                    substances[id] = []
                substances[id].append(substance)
            except ValueError:
                continue
        return substances, filename
