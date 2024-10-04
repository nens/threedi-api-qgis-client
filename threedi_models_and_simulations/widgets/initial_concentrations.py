import logging
import os
from functools import partial
from operator import attrgetter
from typing import Dict, List

from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (QComboBox, QGridLayout, QGroupBox, QLabel,
                                 QRadioButton, QSizePolicy, QToolButton,
                                 QWidget)

from ..api_calls.threedi_calls import ThreediCalls
from ..utils_ui import get_filepath

logger = logging.getLogger(__name__)


class Initial1DConcentrationsWidget(QWidget):
    """Widget for handling initial concentrations."""

    def __init__(
        self,
        substances: List[Dict],
        parent: QWidget,
    ):
        super().__init__(parent)
        self.substances = substances
        self.parent_page = parent
        self.widget = QWidget()
        self.files = []
        self.load_files()
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        layout = QGridLayout()
        self.widget.setLayout(layout)
        self.create_initial_concentrations(layout)

    def connect_signals(self):
        for substance in self.substances:
            substance_name = substance["name"]
            # online file
            cbo_online_file: QComboBox = self.widget.findChild(QComboBox, f"cbo_online_file_1d_{substance_name}")
            for file in sorted(self.files, key=attrgetter("id")):
                cbo_online_file.addItem(file.filename)
        
            # local file
            cbo_local_file = self.widget.findChild(QgsMapLayerComboBox, f"cbo_local_file_{substance_name}")
            browse_button = self.widget.findChild(QToolButton, f"btn_browse_local_file_{substance_name}")
            browse_button.clicked.connect(partial(self.browse_for_local_file, cbo_local_file))

    def load_files(self):
        tc = ThreediCalls(self.parent_page.parent_wizard.plugin_dock.threedi_api)
        model_id = self.parent_page.parent_wizard.model_selection_dlg.current_model.id
        files = tc.fetch_3di_model_initial_concentrations(model_id)
        for file in files:
            if file.dimension == "one_d":
                self.files.append(file)

    def create_initial_concentrations(self, main_layout: QGridLayout):
        """Create initial concentrations."""
        for i, substance in enumerate(self.substances):
            name = substance["name"]
            # Substance groupbox widget
            groupbox = QGroupBox(name)
            groupbox.setFont(QFont("Segoe UI", 10))
            groupbox.setCheckable(True)
            groupbox.setChecked(False)
            groupbox.setObjectName(f"gb_initial_concentrations_1d_{name}")
            groupbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            # Online file upload widget
            is_online_file_available = True if self.files else False
            rb_online_file = QRadioButton("Online file")
            rb_online_file.setObjectName(f"rb_online_file_1d_{name}")
            rb_online_file.setChecked(is_online_file_available)
            cbo_online_file = QComboBox()
            cbo_online_file.setEnabled(is_online_file_available)
            cbo_online_file.setObjectName(f"cbo_online_file_1d_{name}")
            rb_online_file.toggled.connect(lambda checked: cbo_online_file.setEnabled(checked))

            # Local csv upload widget
            rb_local_file = QRadioButton("Upload CSV")
            rb_local_file.setObjectName(f"rb_local_file_{name}")
            rb_local_file.setChecked(not is_online_file_available)
            cbo_local_file = QgsMapLayerComboBox()
            # cbo_local_file.setFilters(QgsMapLayerProxyModel.RasterLayer)
            cbo_local_file.setEnabled(not is_online_file_available)
            cbo_local_file.setObjectName(f"cbo_local_file_{name}")
            btn_browse_local_file = QToolButton()
            btn_browse_local_file.setText("...")
            btn_browse_local_file.setEnabled(not is_online_file_available)
            btn_browse_local_file.setObjectName(f"btn_browse_local_file_{name}")
            rb_local_file.toggled.connect(
                lambda checked: (cbo_local_file.setEnabled(checked), btn_browse_local_file.setEnabled(checked))
            )

            # Add widgets to layout
            groupbox_layout = QGridLayout()
            groupbox_layout.addWidget(rb_online_file, 0, 0)
            groupbox_layout.addWidget(cbo_online_file, 0, 1)
            groupbox_layout.addWidget(rb_local_file, 1, 0)
            groupbox_layout.addWidget(cbo_local_file, 1, 1)
            groupbox_layout.addWidget(btn_browse_local_file, 1, 2)

            # Add groupbox to the main layout
            groupbox.setLayout(groupbox_layout)
            main_layout.addWidget(groupbox, i, 0)

    def browse_for_local_file(self, widget: QgsMapLayerComboBox):
        logger.error("browse")
    #     """Allow user to browse for a raster layer and insert it to the widget."""
    #     name_filter = "GeoTIFF (*.tif *.TIF *.tiff *.TIFF)"
    #     title = "Select raster file"
    #     raster_file = get_filepath(None, extension_filter=name_filter, dialog_title=title)
    #     if not raster_file:
    #         return
    #     filename = os.path.basename(raster_file)
    #     if filename in self.filenames:
    #         error_message = f"Raster {filename} is already in the online rasters."
    #         self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
    #         return
    #     items = widget.additionalItems()
    #     if raster_file not in items:
    #         items.append(raster_file)
    #     widget.setAdditionalItems(items)


class Initial2DConcentrationsWidget(QWidget):
    """Widget for handling initial concentrations."""

    def __init__(
        self,
        substances: List[Dict],
        parent: QWidget,
    ):
        super().__init__(parent)
        self.substances = substances
        self.parent_page = parent
        self.widget = QWidget()
        self.rasters = []
        self.filenames = []
        self.load_rasters()
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        layout = QGridLayout()
        self.widget.setLayout(layout)
        self.create_initial_concentrations(layout)

    def connect_signals(self):
        for substance in self.substances:
            substance_name = substance["name"]
            # online raster
            cbo_online_raster: QComboBox = self.widget.findChild(QComboBox, f"cbo_online_raster_{substance_name}")
            for raster in sorted(self.rasters, key=attrgetter("id")):
                cbo_online_raster.addItem(raster.name)
            # local raster
            cbo_local_raster = self.widget.findChild(QgsMapLayerComboBox, f"cbo_local_raster_{substance_name}")
            browse_button = self.widget.findChild(QToolButton, f"btn_browse_local_raster_{substance_name}")
            browse_button.clicked.connect(partial(self.browse_for_local_raster, cbo_local_raster))

    def load_rasters(self):
        tc = ThreediCalls(self.parent_page.parent_wizard.plugin_dock.threedi_api)
        model_id = self.parent_page.parent_wizard.model_selection_dlg.current_model.id
        rasters = tc.fetch_3di_model_rasters(model_id, type="initial_concentration_file")
        for raster in rasters:
            if raster.file:
                self.rasters.append(raster)
                self.filenames.append(raster.file.filename)

    def create_initial_concentrations(self, main_layout: QGridLayout):
        """Create initial concentrations."""
        for i, substance in enumerate(self.substances):
            name = substance["name"]
            # Substance groupbox widget
            groupbox = QGroupBox(name)
            groupbox.setFont(QFont("Segoe UI", 10))
            groupbox.setCheckable(True)
            groupbox.setChecked(False)
            groupbox.setObjectName(f"gb_initial_concentrations_2d_{name}")
            groupbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            # Online raster upload widget
            is_online_raster_available = True if self.rasters else False
            rb_online_raster = QRadioButton("Online raster")
            rb_online_raster.setObjectName(f"rb_online_raster_{name}")
            rb_online_raster.setChecked(is_online_raster_available)
            cbo_online_raster = QComboBox()
            cbo_online_raster.setEnabled(is_online_raster_available)
            cbo_online_raster.setObjectName(f"cbo_online_raster_{name}")
            rb_online_raster.toggled.connect(lambda checked: cbo_online_raster.setEnabled(checked))

            # Local raster upload widget
            rb_local_raster = QRadioButton("Local raster")
            rb_local_raster.setObjectName(f"rb_local_raster_{name}")
            rb_local_raster.setChecked(not is_online_raster_available)
            cbo_local_raster = QgsMapLayerComboBox()
            cbo_local_raster.setFilters(QgsMapLayerProxyModel.RasterLayer)
            cbo_local_raster.setEnabled(not is_online_raster_available)
            cbo_local_raster.setObjectName(f"cbo_local_raster_{name}")
            btn_browse_local_raster = QToolButton()
            btn_browse_local_raster.setText("...")
            btn_browse_local_raster.setEnabled(not is_online_raster_available)
            btn_browse_local_raster.setObjectName(f"btn_browse_local_raster_{name}")
            rb_local_raster.toggled.connect(
                lambda checked: (cbo_local_raster.setEnabled(checked), btn_browse_local_raster.setEnabled(checked))
            )

            # Aggregation method widget
            label_aggregation = QLabel("     Aggregation method:")
            cbo_aggregation = QComboBox()
            cbo_aggregation.addItems(["mean", "max", "min"])
            cbo_aggregation.setObjectName(f"cbo_aggregation_{name}")

            # Add widgets to layout
            groupbox_layout = QGridLayout()
            groupbox_layout.addWidget(rb_online_raster, 0, 0)
            groupbox_layout.addWidget(cbo_online_raster, 0, 1)
            groupbox_layout.addWidget(rb_local_raster, 1, 0)
            groupbox_layout.addWidget(cbo_local_raster, 1, 1)
            groupbox_layout.addWidget(btn_browse_local_raster, 1, 2)
            groupbox_layout.addWidget(label_aggregation, 2, 0)
            groupbox_layout.addWidget(cbo_aggregation, 2, 1)

            # Add groupbox to the main layout
            groupbox.setLayout(groupbox_layout)
            main_layout.addWidget(groupbox, i, 0)

    def browse_for_local_raster(self, widget: QgsMapLayerComboBox):
        """Allow user to browse for a raster layer and insert it to the widget."""
        name_filter = "GeoTIFF (*.tif *.TIF *.tiff *.TIFF)"
        title = "Select raster file"
        raster_file = get_filepath(None, extension_filter=name_filter, dialog_title=title)
        if not raster_file:
            return
        filename = os.path.basename(raster_file)
        if filename in self.filenames:
            error_message = f"Raster {filename} is already in the online rasters."
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
            return
        items = widget.additionalItems()
        if raster_file not in items:
            items.append(raster_file)
        widget.setAdditionalItems(items)
