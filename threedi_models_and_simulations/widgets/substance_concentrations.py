import csv
import os
from functools import partial
from typing import Callable, Dict, List, Optional

from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from ..utils_ui import read_3di_settings, save_3di_settings


class SubstanceConcentrationsWidget(QWidget):
    """Widget for handling substance concentrations."""

    TYPE_1D = "1D"
    TYPE_2D = "2D"

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
        self.substance_concentrations_1d = {}
        self.substance_concentrations_2d = {}
        self.groupbox = QGroupBox("Substance concentrations", self)
        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout()
        self.groupbox = QGroupBox("Substance concentrations")
        self.groupbox.setLayout(layout)
        self.groupbox.setFont(QFont("Segoe UI", 14, QFont.Bold))
        if self.current_model.extent_one_d:
            self.create_substance_concentrations(layout, "1D")
            self.connect_substance_upload_signals(self.TYPE_1D)
        if self.current_model.extent_two_d:
            self.create_substance_concentrations(layout, "2D")
            self.connect_substance_upload_signals(self.TYPE_2D)

    def create_substance_concentrations(self, layout: QGridLayout, laterals_type: str):
        """Create substance concentrations for 1D and 2D laterals type."""
        font = QFont("Segoe UI", 10, QFont.Normal)
        for i, substance in enumerate(self.substances):
            name = substance["name"]
            label = QLabel(f"{name} ({laterals_type}):")
            label.setMinimumWidth(100)
            label.setFont(font)
            line_edit = QLineEdit()
            line_edit.setObjectName(f"le_substance_{laterals_type}_{name}")
            line_edit.setReadOnly(True)
            line_edit.setFrame(False)
            line_edit.setFont(font)
            line_edit.setStyleSheet("background-color: white")
            upload_button = QPushButton("Upload CSV")
            upload_button.setObjectName(f"pb_substance_{laterals_type}_{name}")
            upload_button.setMinimumWidth(100)
            upload_button.setFont(font)
            horizontal_layout = QHBoxLayout()
            horizontal_layout_widget = QWidget()
            horizontal_layout_widget.setLayout(horizontal_layout)
            horizontal_layout.setContentsMargins(0, 0, 9, 0)
            horizontal_layout.addWidget(label)
            horizontal_layout.addWidget(line_edit)
            horizontal_layout.addWidget(upload_button)
            row = i * 2 if laterals_type == self.TYPE_1D else i * 2 + 1
            layout.addWidget(horizontal_layout_widget, row, 0)

    def connect_substance_upload_signals(self, laterals_type: str):
        """Connect substance upload signals."""
        for substance in self.substances:
            name = substance["name"]
            upload_button = self.groupbox.findChild(QPushButton, f"pb_substance_{laterals_type}_{name}")
            upload_button.clicked.connect(partial(self.load_csv, name, laterals_type))

    def load_csv(self, name: str, laterals_type: str):
        """Load CSV file."""
        substances, filename = self.open_upload_dialog(name, laterals_type)
        if not filename:
            return
        le_substance = self.groupbox.findChild(QLineEdit, f"le_substance_{laterals_type}_{name}")
        le_substance.setText(filename)
        if laterals_type == self.TYPE_1D:
            self.substance_concentrations_1d.update(substances)
        else:
            self.substance_concentrations_2d.update(substances)

    def open_upload_dialog(self, name, laterals_type):
        """Open dialog for selecting CSV file with laterals."""
        last_folder = read_3di_settings("last_substances_folder", os.path.expanduser("~"))
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(
            self, f"Substance Concentrations for {name} ({laterals_type})", last_folder, file_filter
        )
        if len(filename) == 0:
            return None, None
        save_3di_settings("last_substances_folder", os.path.dirname(filename))
        substances = {}
        with open(filename, encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)
            header = reader.fieldnames
            substance_list = list(reader)
        error_msg = self.handle_csv_errors(header, substance_list, laterals_type)
        if error_msg is not None:
            return None, None
        for substance in substance_list:
            parent_id = substance["id"]
            timeseries = substance["timeseries"]
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
