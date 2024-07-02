
from typing import Dict, List, Optional

from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QRadioButton,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from ..utils_ui import read_3di_settings, save_3di_settings


class InitialConcentrationsWidget(QWidget):
    """Widget for handling initial concentrations."""

    def __init__(
        self,
        substances: List[Dict],
        current_model,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.substances = substances
        self.current_model = current_model
        self.initial_concentrations_2d = {}
        self.widget = QWidget()
        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout()
        self.widget.setLayout(layout)
        self.create_initial_concentrations(layout)

    def create_initial_concentrations(self, main_layout: QGridLayout):
        """Create initial concentrations."""
        for i, substance in enumerate(self.substances):
            name = substance["name"]
            # Groupbox
            groupbox = QGroupBox(name)
            groupbox.setFont(QFont("Segoe UI", 10))
            groupbox.setCheckable(True)
            groupbox.setChecked(False)
            groupbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            groupbox_layout = QGridLayout()

            # Online raster upload
            rb_online_raster = QRadioButton("Online raster")
            cbo_online_raster = QComboBox()

            # Local raster upload
            rb_local_raster = QRadioButton("Local raster")
            cbo_local_raster = QComboBox()
            btn_browse_local_raster = QToolButton()
            btn_browse_local_raster.setText("...")

            # Aggregation method widget
            label_aggregation = QLabel("     Aggregation method:")
            cbo_aggregation = QComboBox()
            cbo_aggregation.addItems(["mean", "max", "min"])

            # Add widgets to layout
            groupbox_layout.addWidget(rb_online_raster, 0, 0)
            groupbox_layout.addWidget(cbo_online_raster, 0, 1)
            groupbox_layout.addWidget(rb_local_raster, 1, 0)
            groupbox_layout.addWidget(cbo_local_raster, 1, 1)
            groupbox_layout.addWidget(btn_browse_local_raster, 1, 2)
            groupbox_layout.addWidget(label_aggregation, 2, 0)
            groupbox_layout.addWidget(cbo_aggregation, 2, 1)

            groupbox.setLayout(groupbox_layout)

            # Add groupbox to the main layout
            main_layout.addWidget(groupbox, i, 0)
