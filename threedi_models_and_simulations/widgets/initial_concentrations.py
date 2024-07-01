import csv
import os
from functools import partial
from typing import Callable, Dict, List, Optional

from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from ..utils_ui import read_3di_settings, save_3di_settings


class InitialConcentrationsWidget(QWidget):
    """Widget for handling initial concentrations."""

    def __init__(
        self,
        substances: List[Dict],
        current_model,
        handle_csv_errors: Callable,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.substances = substances
        self.current_model = current_model
        self.handle_csv_errors = handle_csv_errors
        self.initial_concentrations_2d = {}
        self.widget = QWidget()
        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout()
        self.widget.setLayout(layout)
        self.create_initial_concentrations(layout)
        self.connect_upload_signals()

    def create_initial_concentrations(self, main_layout: QGridLayout):
        """Create initial concentrations."""
        font = QFont("Segoe UI", 10, QFont.Normal)
        for i, substance in enumerate(self.substances):
            name = substance["name"]
            # Groupbox
            groupbox = QGroupBox(name)
            groupbox.setFont(QFont("Segoe UI", 12))
            groupbox.setCheckable(True)
            groupbox.setChecked(False)
            groupbox_layout = QGridLayout()

            # Widgets
            label = QLabel(name)
            label.setMinimumWidth(100)
            label.setFont(font)
            line_edit = QLineEdit()
            line_edit.setObjectName(f"le_substance_{name}")
            line_edit.setReadOnly(True)
            line_edit.setFrame(False)
            line_edit.setFont(font)
            line_edit.setStyleSheet("background-color: white")
            upload_button = QPushButton("Upload CSV")
            upload_button.setObjectName(f"pb_substance_{name}")
            upload_button.setMinimumWidth(100)
            upload_button.setFont(font)

            # Add widgets to layout
            groupbox_layout.addWidget(label, 0, 0)
            groupbox_layout.addWidget(line_edit, 0, 1)
            groupbox_layout.addWidget(upload_button, 0, 2)
            groupbox.setLayout(groupbox_layout)

            # Add groupbox to the main layout
            main_layout.addWidget(groupbox, i, 0)

    def connect_upload_signals(self):
        """Connect substance upload signals."""
        for substance in self.substances:
            name = substance["name"]
            upload_button = self.widget.findChild(QPushButton, f"pb_substance_{name}")
            upload_button.clicked.connect(partial(self.load_csv, name))

    def load_csv(self, name: str):
        """Load CSV file."""
        substances, filename = self.open_upload_dialog(name)
        if not filename:
            return
        le_substance = self.widget.findChild(QLineEdit, f"le_substance_{name}")
        le_substance.setText(filename)
        self.initial_concentrations_2d.update(substances)

    def open_upload_dialog(self, name):
        """Open dialog for selecting CSV file with laterals."""
        last_folder = read_3di_settings("last_substances_folder", os.path.expanduser("~"))
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(
            self, f"Substance Concentrations for {name}", last_folder, file_filter
        )
        if len(filename) == 0:
            return None, None
        save_3di_settings("last_substances_folder", os.path.dirname(filename))
        substances = {}
        with open(filename, encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)
            header = reader.fieldnames
            substance_list = list(reader)
        error_msg = self.handle_csv_errors(header, substance_list)
        if error_msg is not None:
            return None, None
        for row in substance_list:
            parent_id = row["id"]
            timeseries = row["timeseries"]
            try:
                concentrations = [[float(f) for f in line.split(",")] for line in timeseries.split("\n")]
                substance = {
                    "substance": name,
                    "concentrations": concentrations,
                }
                if parent_id not in substances:
                    substances[parent_id] = []
                substances[parent_id].append(substance)
            except ValueError:
                continue
        return substances, filename
