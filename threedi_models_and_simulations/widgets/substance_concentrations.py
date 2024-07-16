import csv
import os
from functools import partial
from typing import Callable, Dict, List, Optional

from qgis.PyQt.QtGui import QFont, QDoubleValidator
from qgis.PyQt.QtWidgets import (
    QComboBox,
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
from ..utils import parse_timeseries


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
        self.header = None
        self.substance_list = []
        self.substance_concentrations_1d = {}
        self.substance_concentrations_2d = {}
        self.groupbox = QGroupBox("Substance concentrations", self)
        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout()
        self.groupbox = QGroupBox("Substance concentrations")
        self.groupbox.setLayout(layout)
        self.groupbox.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.add_help_texts(layout)
        if self.current_model.extent_one_d:
            self.create_substance_concentrations(layout, "1D")
        if self.current_model.extent_two_d:
            self.create_substance_concentrations(layout, "2D")

    def add_help_texts(self, layout: QGridLayout):
        """Help texts for substance concentrations."""
        font = QFont("Segoe UI", 10, QFont.Normal)
        text_layout = QHBoxLayout()
        text1 = QLabel("Specify the same constant substance concentrations for all laterals")
        text2 = QLabel("- or -")
        text3 = QLabel("Upload CSV containing a specific time series for each lateral (overules the constant values)")
        text1.setFont(font)
        text2.setFont(font)
        text3.setFont(font)
        text1.setMaximumWidth(250)
        text2.setMaximumWidth(50)
        text3.setMaximumWidth(350)
        text1.setWordWrap(True)
        text2.setWordWrap(True)
        text3.setWordWrap(True)
        text_layout.addWidget(text1)
        text_layout.addWidget(text2)
        text_layout.addWidget(text3)
        text_layout_widget = QWidget()
        text_layout_widget.setLayout(text_layout)
        layout.addWidget(text_layout_widget, 0, 0)

    def create_substance_concentrations(self, layout: QGridLayout, var_type: str):
        """Create substance concentrations for 1D and 2D laterals type."""
        font = QFont("Segoe UI", 10, QFont.Normal)
        for i, substance in enumerate(self.substances):
            name = substance.get("name")
            units = substance.get("units", "")

            # label
            label = QLabel(f"{name} ({var_type}):")
            label.setMinimumWidth(100)
            label.setFont(font)

            # line edit for constant value
            line_edit_constant = QLineEdit()
            line_edit_constant.setObjectName(f"le_substance_constant_{var_type}_{name}")
            line_edit_constant.setPlaceholderText("Enter constant value")
            line_edit_constant.setFont(font)
            line_edit_constant.setFrame(False)
            line_edit_constant.setStyleSheet("background-color: white")

            # validator for constant value
            validator = QDoubleValidator()
            validator.setNotation(QDoubleValidator.StandardNotation)
            line_edit_constant.setValidator(validator)

            # units label
            units_label = QLabel(units)
            units_label.setMinimumWidth(100)
            units_label.setFont(font)

            # line edit for CSV file
            line_edit_csv = QLineEdit()
            line_edit_csv.setObjectName(f"le_substance_{var_type}_{name}")
            line_edit_csv.setPlaceholderText("Upload CSV file")
            line_edit_csv.setReadOnly(True)
            line_edit_csv.setFrame(False)
            line_edit_csv.setFont(font)
            line_edit_csv.setStyleSheet("background-color: white")

            # combo box for time units
            combo_box_time_units = QComboBox()
            combo_box_time_units.addItems(["mins", "hrs", "s"])
            combo_box_time_units.setObjectName(f"cb_time_units_{var_type}_{name}")
            combo_box_time_units.setFont(font)
            combo_box_time_units.currentIndexChanged.connect(partial(self.update_time_units, name, var_type))

            # upload button
            upload_button = QPushButton("Upload CSV")
            upload_button.setObjectName(f"pb_substance_{var_type}_{name}")
            upload_button.setMinimumWidth(100)
            upload_button.setFont(font)
            upload_button.clicked.connect(partial(self.load_csv, name, var_type))

            # add widgets to layout
            horizontal_layout = QHBoxLayout()
            horizontal_layout_widget = QWidget()
            horizontal_layout_widget.setLayout(horizontal_layout)
            horizontal_layout.setContentsMargins(0, 0, 9, 0)
            horizontal_layout.addWidget(label)
            horizontal_layout.addWidget(line_edit_constant)
            horizontal_layout.addWidget(units_label)
            horizontal_layout.addWidget(line_edit_csv)
            horizontal_layout.addWidget(combo_box_time_units)
            horizontal_layout.addWidget(upload_button)
            row = i * 2 if var_type == self.TYPE_1D else i * 2 + 1
            layout.addWidget(horizontal_layout_widget, row + 1, 0)

    def load_csv(self, name: str, var_type: str):
        """Load CSV file."""
        combo_box_time_units = self.groupbox.findChild(QComboBox, f"cb_time_units_{var_type}_{name}")
        time_units = combo_box_time_units.currentText()
        substances, filename = self.open_upload_dialog(name, var_type, time_units)
        if not filename:
            return
        le_substance = self.groupbox.findChild(QLineEdit, f"le_substance_{var_type}_{name}")
        le_substance.setText(filename)
        if var_type == self.TYPE_1D:
            self.substance_concentrations_1d.update(substances)
        else:
            self.substance_concentrations_2d.update(substances)

    def open_upload_dialog(self, name: str, var_type: str, time_units: str = "s"):
        """Open dialog for selecting CSV file with laterals."""
        last_folder = read_3di_settings("last_substances_folder", os.path.expanduser("~"))
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(
            self, f"Substance Concentrations for {name} ({var_type})", last_folder, file_filter
        )
        if len(filename) == 0:
            return None, None
        save_3di_settings("last_substances_folder", os.path.dirname(filename))
        substances = {}
        with open(filename, encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)
            self.header = reader.fieldnames
            self.substance_list = list(reader)
        error_msg = self.handle_csv_errors(self.header, self.substance_list, var_type, time_units)
        if error_msg is not None:
            return None, None
        for row in self.substance_list:
            parent_id = row["id"]
            timeseries = row["timeseries"]
            try:
                concentrations = parse_timeseries(timeseries)
                substance = {
                    "substance": name,
                    "concentrations": concentrations,
                    "time_units": time_units,
                }
                if parent_id not in substances:
                    substances[parent_id] = []
                substances[parent_id].append(substance)
            except ValueError:
                continue
        return substances, filename

    def update_time_units(self, name: str, var_type: str):
        """Update time units for substance concentrations."""
        combo_box = self.groupbox.findChild(QComboBox, f"cb_time_units_{var_type}_{name}")
        time_units = combo_box.currentText()
        error_message = self.handle_csv_errors(self.header, self.substance_list, var_type, time_units)
        if error_message:
            # clear the QLineEdit
            le_substance = self.groupbox.findChild(QLineEdit, f"le_substance_{var_type}_{name}")
            le_substance.clear()
            # remove the substance from the values
            if var_type == self.TYPE_1D:
                self.substance_concentrations_1d = {
                    k: [substance for substance in v if substance["substance"] != name]
                    for k, v in self.substance_concentrations_1d.items()
                }
                self.substance_concentrations_1d = {k: v for k, v in self.substance_concentrations_1d.items() if v}
            else:
                self.substance_concentrations_2d = {
                    k: [substance for substance in v if substance["substance"] != name]
                    for k, v in self.substance_concentrations_2d.items()
                }
                self.substance_concentrations_2d = {k: v for k, v in self.substance_concentrations_2d.items() if v}
            return
