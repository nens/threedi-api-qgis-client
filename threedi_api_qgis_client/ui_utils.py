# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import QDate, QTime, QSettings
from qgis.PyQt.QtWidgets import (
    QLineEdit,
    QDateEdit,
    QTimeEdit,
    QCheckBox,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QWidget,
    QRadioButton,
    QFileDialog,
)


def style_path(qml_filename):
    """Setting up path to the QML style with given filename."""
    path = os.path.join(os.path.dirname(__file__), "styles", qml_filename)
    return path


def set_named_style(layer, qml_filename):
    """Set QML style to the vector layer."""
    qml_path = style_path(qml_filename)
    layer.loadNamedStyle(qml_path)


def icon_path(icon_filename):
    """Setting up path to the icon with given filename."""
    path = os.path.join(os.path.dirname(__file__), "icons", icon_filename)
    return path


def set_icon(widget, icon_filename):
    """Setting up widget icon based on given icon filename."""
    path = icon_path(icon_filename)
    icon = QIcon(path)
    widget.setIcon(icon)


def set_widget_background_color(widget, hex_color="#F0F0F0"):
    """Setting widget background color."""
    palette = widget.palette()
    palette.setColor(widget.backgroundRole(), QColor(hex_color))
    widget.setPalette(palette)


def scan_widgets_parameters(main_widget):
    """Scan widget children and get their values."""
    parameters = {}
    for widget in main_widget.children():
        obj_name = widget.objectName()
        if isinstance(widget, QLineEdit):
            parameters[obj_name] = widget.text()
        elif isinstance(widget, (QCheckBox, QRadioButton)):
            parameters[obj_name] = widget.isChecked()
        elif isinstance(widget, QComboBox):
            parameters[obj_name] = widget.currentText()
        elif isinstance(widget, QDateEdit):
            parameters[obj_name] = widget.dateTime().toString("yyyy-MM-dd")
        elif isinstance(widget, QTimeEdit):
            parameters[obj_name] = widget.time().toString("H:m")
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            parameters[obj_name] = widget.value()
        elif isinstance(widget, QWidget):
            parameters.update(scan_widgets_parameters(widget))
    return parameters


def set_widgets_parameters(main_widget, **widget_parameters):
    """Set widget children values based on derived parameters."""
    for name, value in widget_parameters.items():
        widget = getattr(main_widget, name, None)
        if widget is None:
            continue
        if isinstance(widget, QLineEdit):
            widget.setText(value)
        elif isinstance(widget, (QCheckBox, QRadioButton)):
            widget.setChecked(value)
        elif isinstance(widget, QComboBox):
            idx = widget.findText(value)
            widget.setCurrentIndex(idx)
        elif isinstance(widget, QDateEdit):
            widget.setDate(QDate.fromString(value, "yyyy-MM-dd"))
        elif isinstance(widget, QTimeEdit):
            widget.setTime(QTime.fromString(value, "H:m"))
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.setValue(value)


def get_filepath(parent, extension_filter=None, extension=None, save=False, dialog_title=None):
    """Opening dialog to get a filepath."""
    if extension_filter is None:
        extension_filter = "All Files (*.*)"

    if dialog_title is None:
        dialog_title = "Choose file"

    starting_dir = QSettings().value("threedi/last_schematisation_folder", os.path.expanduser("~"), type=str)
    if save is True:
        file_name, __ = QFileDialog.getSaveFileName(parent, dialog_title, starting_dir, extension_filter)
    else:
        file_name, __ = QFileDialog.getOpenFileName(parent, dialog_title, starting_dir, extension_filter)
    if len(file_name) == 0:
        return None

    if extension:
        if not file_name.endswith(extension):
            file_name += extension

    QSettings().setValue("threedi/last_schematisation_folder", os.path.dirname(file_name))
    return file_name
