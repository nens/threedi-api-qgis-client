# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from qgis.PyQt.QtGui import QIcon, QColor


def icon_path(icon_filename):
    """Setting up path to the icon with given filename."""
    path = os.path.join(os.path.dirname(__file__), 'icons', icon_filename)
    return path


def set_icon(widget, icon_filename):
    """Setting up widget icon based on given icon filename."""
    path = icon_path(icon_filename)
    icon = QIcon(path)
    widget.setIcon(icon)


def set_widget_background_color(widget, hex_color='#F0F0F0'):
    """Setting widget background color."""
    palette = widget.palette()
    palette.setColor(widget.backgroundRole(), QColor(hex_color))
    widget.setPalette(palette)


def mmh_to_ms(mmh_value):
    """Converting values from 'mm/h' to the 'm/s'."""
    ms_value = mmh_value / 3600 * 0.001
    return ms_value


def ms_to_mmh(ms_value):
    """Converting values from 'm/s' to the 'mm/h'."""
    mmh_value = ms_value * 3600 * 1000
    return mmh_value


def mmtimestep_to_mmh(value, timestep, units='s'):
    """Converting values from 'mm/timestep' to the 'mm/h'."""
    if units == 's':
        timestep_seconds = timestep
    elif units == 'mins':
        timestep_seconds = timestep * 60
    elif units == 'hrs':
        timestep_seconds = timestep * 3600
    else:
        raise ValueError(f"Unsupported timestep units format ({units})!")
    value_per_second = value / timestep_seconds
    mmh_value = value_per_second * 3600
    return mmh_value


def mmh_to_mmtimestep(value, timestep, units='s'):
    """Converting values from 'mm/h' to the 'mm/timestep'."""
    if units == 's':
        timestep_seconds = timestep
    elif units == 'mins':
        timestep_seconds = timestep * 60
    elif units == 'hrs':
        timestep_seconds = timestep * 3600
    else:
        raise ValueError(f"Unsupported timestep units format ({units})!")
    value_per_second = value / 3600
    mmtimestep_value = value_per_second * timestep_seconds
    return mmtimestep_value
