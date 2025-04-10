# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import os.path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QApplication

from .communication import UICommunication
from .settings import SettingsDialog


class ThreediModelsAndSimulations:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor."""
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize plugin settings
        self.plugin_settings = SettingsDialog(self.iface)

        # Declare instance attributes
        self.actions = []
        self.menu = "3Di Models and Simulations"
        self.toolbar = self.iface.addToolBar("ThreediModelsAndSimulations")
        self.toolbar.setObjectName("ThreediModelsAndSimulations")
        self.pluginIsActive = False
        self.dockwidget = None

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
    ):
        """Add a toolbar icon to the toolbar."""

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.add_action(icon_path, text="3Di Models and Simulations", callback=self.run, parent=self.iface.mainWindow())
        self.add_action(
            icon_path,
            text="Settings",
            callback=self.settings,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False,
        )

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed."""
        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)
        self.pluginIsActive = False

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu("3Di Models and Simulations", action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def settings(self):
        """Show plugin settings dialog."""
        self.plugin_settings.exec_()

    def ensure_required_api_client_version(self, available_api_client_version):
        """Ensure availability of the required 'threedi_api_client' version."""
        uc = UICommunication(self.iface, "3Di Models and Simulations")
        available_api_client_version_str = ".".join([str(i) for i in available_api_client_version])
        title = f"Wrong 'threedi-api-client' version ({available_api_client_version_str})"
        msg = (
            "Unsupported version of the python package 'threedi-api-client' has been installed in your python "
            "environment. It needs to be upgraded to be able to run the 3Di Models & Simulations plugin. "
            "This will now be attempted."
        )
        cancel, ok = "Cancel", "OK"
        clicked_button = uc.custom_ask(None, title, msg, cancel, ok)
        if clicked_button == ok:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            reinstall_results = reinstall_packages_from_wheels(API_CLIENT_WHEEL)
            package_reinstalled = reinstall_results[API_CLIENT_WHEEL]["success"]
            QApplication.restoreOverrideCursor()
            if package_reinstalled:
                info = (
                    "Python package 'threedi-api-client' has been upgraded successfully. "
                    "Please restart QGIS to be able to use the 3Di Models & Simulations plugin."
                )
                uc.show_info(info)
            else:
                feedback_message = reinstall_results[API_CLIENT_WHEEL]["error"]
                error = f"Upgrading of the 'threedi-api-client' failed due to following error:\n{feedback_message}"
                uc.show_error(error)

    def run(self):
        """Run method that loads and starts the plugin"""
        from threedi_models_and_simulations.widgets.threedi_dockwidget import \
            ThreediDockWidget

        if not self.plugin_settings.settings_are_valid():
            self.settings()

        if not self.pluginIsActive:
            self.pluginIsActive = True
            if self.dockwidget is None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = ThreediDockWidget(self.iface, self.plugin_settings)
            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)
            self.iface.addTabifiedDockWidget(Qt.RightDockWidgetArea, self.dockwidget, raiseTab=True)
            # Workaround for the issue with the interface elements getting invisible after combining with identify tool.
            self.iface.mainWindow().showNormal()
            self.iface.mainWindow().showMaximized()
