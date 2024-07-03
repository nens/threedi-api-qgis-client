from functools import partial
from typing import Dict, List, Optional

from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
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

from ..utils_ui import get_filepath


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
        self.connect_signals()

    def setup_ui(self):
        layout = QGridLayout()
        self.widget.setLayout(layout)
        self.create_initial_concentrations(layout)

    def connect_signals(self):
        for substance in self.substances:
            name = substance["name"]
            cbo_local_raster = self.widget.findChild(QgsMapLayerComboBox, f"cbo_local_raster_{name}")
            browse_button = self.widget.findChild(QToolButton, f"btn_browse_local_raster_{name}")
            browse_button.clicked.connect(partial(self.browse_for_local_raster, cbo_local_raster))

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
            cbo_online_raster.setEnabled(False)
            rb_online_raster.toggled.connect(lambda checked: cbo_online_raster.setEnabled(checked))

            # Local raster upload
            rb_local_raster = QRadioButton("Local raster")
            cbo_local_raster = QgsMapLayerComboBox()
            cbo_local_raster.setFilters(QgsMapLayerProxyModel.RasterLayer)
            cbo_local_raster.setEnabled(False)
            cbo_local_raster.setObjectName(f"cbo_local_raster_{name}")
            btn_browse_local_raster = QToolButton()
            btn_browse_local_raster.setText("...")
            btn_browse_local_raster.setEnabled(False)
            btn_browse_local_raster.setObjectName(f"btn_browse_local_raster_{name}")
            rb_local_raster.toggled.connect(
                lambda checked: (cbo_local_raster.setEnabled(checked), btn_browse_local_raster.setEnabled(checked))
            )

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

    @staticmethod
    def browse_for_local_raster(widget: QgsMapLayerComboBox):
        """Allow user to browse for a raster layer and insert it to the widget."""
        name_filter = "GeoTIFF (*.tif *.TIF *.tiff *.TIFF)"
        title = "Select raster file"
        raster_file = get_filepath(None, extension_filter=name_filter, dialog_title=title)
        if not raster_file:
            return
        items = widget.additionalItems()
        if raster_file not in items:
            items.append(raster_file)
        widget.setAdditionalItems(items)
