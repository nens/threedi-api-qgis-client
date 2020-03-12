import os
from qgis.PyQt.QtGui import QIcon


def icon_path(icon_filename):
    path = os.path.join(os.path.dirname(__file__), 'icons', icon_filename)
    return path


def set_icon(widget, icon_filename):
    path = icon_path(icon_filename)
    icon = QIcon(path)
    widget.setIcon(icon)




