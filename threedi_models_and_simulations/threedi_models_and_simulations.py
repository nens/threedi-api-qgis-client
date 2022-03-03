# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtWidgets import QApplication, QAction
from qgis.PyQt.QtGui import QIcon
from .settings import SettingsDialog
from .communication import UICommunication
from .deps.custom_imports import patch_wheel_imports, api_client_version_matches, reinstall_required_api_client
import os.path


class ThreediModelsAndSimulations:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize plugin settings
        self.plugin_settings = SettingsDialog(self.iface)
        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        locale_path = os.path.join(self.plugin_dir, "i18n", f"ThreediModelsAndSimulations_{locale}.qm")

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr("&3Di Models and Simulations")
        self.toolbar = self.iface.addToolBar("ThreediModelsAndSimulations")
        self.toolbar.setObjectName("ThreediModelsAndSimulations")
        self.pluginIsActive = False
        self.dockwidget = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate("ThreediModelsAndSimulations", message)

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
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

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
        self.add_action(
            icon_path, text=self.tr("3Di Models and Simulations"), callback=self.run, parent=self.iface.mainWindow()
        )
        self.add_action(
            icon_path,
            text=self.tr("Settings"),
            callback=self.settings,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False,
        )

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""
        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)
        self.pluginIsActive = False

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr("&3Di Models and Simulations"), action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def settings(self):
        """Show plugin settings dialog."""
        self.plugin_settings.exec_()

    def ensure_required_api_client_version(self, available_api_client_version):
        """Ensure availability of the required 'threedi_api_client' version."""
        uc = UICommunication(self.iface, "3Di Models and Simulations")
        title = f"Wrong 'threedi-api-client' version ({available_api_client_version})"
        msg = (
            "Unsupported version of the python package 'threedi-api-client' has been installed in your python "
            "environment. It needs to be upgraded to be able to run the 3Di Models & Simulations plugin. "
            "This will now be attempted."
        )
        cancel, ok = "Cancel", "OK"
        clicked_button = uc.custom_ask(None, title, msg, cancel, ok)
        if clicked_button == ok:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            package_reinstalled, feedback_message = reinstall_required_api_client()
            QApplication.restoreOverrideCursor()
            if package_reinstalled:
                info = (
                    "Python package 'threedi-api-client' has been upgraded successfully. "
                    "Please restart QGIS to be able to use the 3Di Models & Simulations plugin."
                )
                uc.show_info(info)
            else:
                error = f"Upgrading of the 'threedi-api-client' failed due to following error:\n{feedback_message}"
                uc.show_error(error)

    def run(self):
        """Run method that loads and starts the plugin"""
        patch_wheel_imports()
        versions_matches, available_api_client_version = api_client_version_matches()
        if not versions_matches:
            self.ensure_required_api_client_version(available_api_client_version)
            return
        from threedi_models_and_simulations.widgets.threedi_dockwidget import ThreediDockWidget

        if not self.plugin_settings.settings_are_valid():
            self.settings()

        if not self.pluginIsActive:
            self.pluginIsActive = True
            if self.dockwidget is None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = ThreediDockWidget(self.iface, self.plugin_settings)
            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()
