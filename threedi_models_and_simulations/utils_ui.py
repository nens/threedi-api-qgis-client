# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import os
import re
import shutil
from uuid import uuid4

from qgis.gui import QgsFileWidget, QgsProjectionSelectionWidget
from qgis.PyQt.QtCore import QDate, QLocale, QSettings, QTime
from qgis.PyQt.QtGui import QColor, QDoubleValidator, QIcon
from qgis.PyQt.QtWidgets import (QCheckBox, QComboBox, QDateEdit,
                                 QDoubleSpinBox, QFileDialog, QGroupBox,
                                 QItemDelegate, QLineEdit, QRadioButton,
                                 QSpinBox, QTimeEdit, QWidget)
from threedi_mi_utils import bypass_max_path_limit


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


def scan_widgets_parameters(main_widget, get_combobox_text, remove_postfix, lineedits_as_float_or_none):
    """Scan widget children and get their values.
    
    In Qt Designer, widgets in the same UI file need to have an unique object name. When an object
    name already exist, Qt designer adds a _2 postfix. Use remove_postfix to remove these.
    """
    parameters = {}
    for widget in main_widget.children():
        obj_name = widget.objectName()
        if remove_postfix:
            result = re.match("^(.+)(_\d+)$", obj_name)
            if result is not None:
                obj_name = result.group(1)

        if isinstance(widget, QLineEdit):
            if lineedits_as_float_or_none:
                if widget.text():
                    val, to_float_possible = QLocale().toFloat(widget.text())
                    assert to_float_possible  # Should be handled by validators
                    if "e" in widget.text().lower():  # we use python buildin for scientific notation
                       parameters[obj_name] = float(widget.text()) 
                    else:
                        parameters[obj_name] = val
                else:
                    parameters[obj_name] = None
            else:
                parameters[obj_name] = widget.text()
        elif isinstance(widget, (QCheckBox, QRadioButton)):
            parameters[obj_name] = widget.isChecked()
        elif isinstance(widget, QComboBox):
            parameters[obj_name] = widget.currentText() if get_combobox_text else widget.currentIndex()
        elif isinstance(widget, QDateEdit):
            parameters[obj_name] = widget.dateTime().toString("yyyy-MM-dd")
        elif isinstance(widget, QTimeEdit):
            parameters[obj_name] = widget.time().toString("H:m")
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            parameters[obj_name] = widget.value() if widget.text() else None
        elif isinstance(widget, QgsProjectionSelectionWidget):
            parameters[obj_name] = widget.crs()
        elif isinstance(widget, QgsFileWidget):
            parameters[obj_name] = widget.filePath()
        elif isinstance(widget, QGroupBox):
            if widget.isCheckable():
                is_checked = widget.isChecked()
                parameters[obj_name] = is_checked
                if is_checked:
                    parameters.update(scan_widgets_parameters(widget, get_combobox_text=get_combobox_text, remove_postfix=remove_postfix, lineedits_as_float_or_none=lineedits_as_float_or_none))
            else:
                parameters.update(scan_widgets_parameters(widget, get_combobox_text=get_combobox_text, remove_postfix=remove_postfix, lineedits_as_float_or_none=lineedits_as_float_or_none))
        elif isinstance(widget, QWidget):
            parameters.update(scan_widgets_parameters(widget, get_combobox_text=get_combobox_text, remove_postfix=remove_postfix, lineedits_as_float_or_none=lineedits_as_float_or_none))
    return parameters


def set_widgets_parameters(main_widget, find_combobox_text=True, **widget_parameters):
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
            idx = widget.findText(value) if find_combobox_text else value
            widget.setCurrentIndex(idx)
        elif isinstance(widget, QDateEdit):
            widget.setDate(QDate.fromString(value, "yyyy-MM-dd"))
        elif isinstance(widget, QTimeEdit):
            widget.setTime(QTime.fromString(value, "H:m"))
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            if value is not None:
                widget.setValue(value)
            else:
                widget.clear()


def get_filepath(parent, extension_filter=None, extension=None, save=False, dialog_title=None):
    """Opening dialog to get a filepath."""
    if extension_filter is None:
        extension_filter = "All Files (*.*)"

    if dialog_title is None:
        dialog_title = "Choose file"

    working_dir = QSettings().value("threedi/working_dir", os.path.expanduser("~"), type=str)
    starting_dir = QSettings().value("threedi/last_schematisation_folder", working_dir, type=str)
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


def qgis_layers_cbo_get_layer_uri(qgis_map_layers_cbo):
    """Get selected map layer source uri, or additional path, from QgsMapLayerComboBox."""
    cur_layer = qgis_map_layers_cbo.currentLayer()
    if cur_layer is not None and cur_layer.isValid():
        dp = cur_layer.dataProvider()
        return dp.dataSourceUri()
    # no layer selected - check if there are any additional items
    if qgis_map_layers_cbo.currentText():
        # check if additional item path exists on disk
        lyr_path = qgis_map_layers_cbo.currentText()
        if os.path.exists(lyr_path):
            return lyr_path


def ensure_valid_schema(schematisation_sqlite, communication):
    """Check if schema version is up-to-date and migrate it if needed."""
    try:
        from threedi_schema import ThreediDatabase, errors
    except ImportError:
        return
    schematisation_dirname = os.path.dirname(schematisation_sqlite)
    schematisation_filename = os.path.basename(schematisation_sqlite)
    backup_folder = os.path.join(schematisation_dirname, "_backup")
    os.makedirs(bypass_max_path_limit(backup_folder), exist_ok=True)
    prefix = str(uuid4())[:8]
    backup_sqlite_path = os.path.join(backup_folder, f"{prefix}_{schematisation_filename}")
    shutil.copyfile(schematisation_sqlite, bypass_max_path_limit(backup_sqlite_path, is_file=True))
    threedi_db = ThreediDatabase(schematisation_sqlite)
    schema = threedi_db.schema
    try:
        schema.validate_schema()
        schema.set_spatial_indexes()
    except errors.MigrationMissingError:
        warn_and_ask_msg = (
            "The selected spatialite cannot be used because its database schema version is out of date. "
            "Would you like to migrate your spatialite to the current schema version?"
        )
        do_migration = communication.ask(None, "Missing migration", warn_and_ask_msg)
        if not do_migration:
            return False
        schema.upgrade(backup=False, upgrade_spatialite_version=True)
        schema.set_spatial_indexes()
        shutil.rmtree(backup_folder)
    except errors.UpgradeFailedError:
        error_msg = (
            "There are errors in the spatialite. Please re-open this file in QGIS 3.16, run the model checker and "
            "fix error messages. Then attempt to upgrade again. For questions please contact the servicedesk."
        )
        communication.show_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"{e}"
        communication.show_error(error_msg)
        return False
    return True


def save_3di_settings(entry_name, value):
    """Save the 3Di settings entry."""
    settings = QSettings()
    settings.setValue(f"threedi/{entry_name}", value)


def read_3di_settings(entry_name, default_value=""):
    """Read the 3Di settings entry."""
    settings = QSettings()
    value_from_settings = settings.value(f"threedi/{entry_name}", default_value)
    return value_from_settings


class NumericDelegate(QItemDelegate):
    def createEditor(self, parent: QWidget, option, index) -> QWidget:
        editor = QLineEdit(parent)
        validator = QDoubleValidator(0.0, 999999999.0, 10, parent)
        validator.setNotation(QDoubleValidator.StandardNotation)
        editor.setValidator(validator)
        return editor
