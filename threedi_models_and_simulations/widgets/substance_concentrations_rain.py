from functools import partial

from qgis.PyQt.QtGui import QFont, QDoubleValidator
from qgis.PyQt.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QWidget,
)


class SubstanceConcentrationsRainWidget(QWidget):
    """Widget for handling substance concentrations."""
    def __init__(
        self,
        parent: QWidget,
    ):
        super().__init__(parent)
        self.parent_widget = parent
        self.substance_constants = []
        self.groupbox = QGroupBox("Substance concentrations", self)
        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout()
        self.groupbox = QGroupBox("Substance concentrations")
        self.groupbox.setLayout(layout)
        self.groupbox.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.add_help_texts(layout)
        self.create_substance_concentrations(layout)

    def add_help_texts(self, layout: QGridLayout):
        """Help texts for substance concentrations."""
        font = QFont("Segoe UI", 10, QFont.Normal)
        text_layout = QHBoxLayout()
        text1 = QLabel("Specify constant substance concentrations for the whole duration of the rain event")
        text1.setFont(font)
        text_layout.addWidget(text1)
        text_layout_widget = QWidget()
        text_layout_widget.setLayout(text_layout)
        layout.addWidget(text_layout_widget, 0, 0)

    def create_substance_concentrations(self, layout: QGridLayout):
        """Create substance concentrations for rain events."""
        font = QFont("Segoe UI", 10, QFont.Normal)
        for i, substance in enumerate(self.parent_widget.substances):
            name = substance.get("name")
            units = substance.get("units", "")

            # label
            label = QLabel(f"{name}:")
            label.setMinimumWidth(100)
            label.setFont(font)

            # line edit for constant value
            line_edit_constant = QLineEdit()
            line_edit_constant.setObjectName(f"le_substance_constant_{name}")
            line_edit_constant.setPlaceholderText("Enter constant value")
            line_edit_constant.setFont(font)
            line_edit_constant.setFrame(False)
            line_edit_constant.setStyleSheet("background-color: white")

            # validator for constant value
            validator = QDoubleValidator()
            validator.setNotation(QDoubleValidator.StandardNotation)
            line_edit_constant.setValidator(validator)
            line_edit_constant.textChanged.connect(partial(self.handle_constant_value, name))

            # units label
            units_label = QLabel(units)
            units_label.setMinimumWidth(100)
            units_label.setFont(font)

            # add widgets to layout
            horizontal_layout = QHBoxLayout()
            horizontal_layout_widget = QWidget()
            horizontal_layout_widget.setLayout(horizontal_layout)
            horizontal_layout.setContentsMargins(0, 0, 9, 0)
            horizontal_layout.addWidget(label)
            horizontal_layout.addWidget(line_edit_constant)
            horizontal_layout.addWidget(units_label)
            layout.addWidget(horizontal_layout_widget, i + 1, 0)

    def handle_constant_value(self, name: str):
        """Handle constant value for substance concentrations."""
        le_substance_constant = self.groupbox.findChild(QLineEdit, f"le_substance_constant_{name}")
        constant_value = le_substance_constant.text().strip()
        if not constant_value:
            self.clear_substance_constants(name)
            return
        error_message = self.parent_widget.handle_substance_constant_error()
        if error_message:
            le_substance_constant.clear()
            self.clear_substance_constants(name)
            return
        float_value = float(constant_value)
        for substance in self.substance_constants:
            if name in substance:
                substance[name] = float_value
                return
        self.substance_constants.append({name: float_value})

    def clear_substance_constants(self, substance_name: str):
        """Remove the substance value from self.substance_constants."""
        self.substance_constants = [substance for substance in self.substance_constants if substance_name not in substance]
