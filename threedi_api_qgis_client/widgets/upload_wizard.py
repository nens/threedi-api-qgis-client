# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
from collections import OrderedDict, defaultdict
from qgis.PyQt.QtSvg import QSvgWidget
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QSettings, Qt, QSize
from qgis.PyQt.QtWidgets import QWizardPage, QWizard, QGridLayout, QSizePolicy, QFileDialog
from threedi_api_client.openapi import ApiException
from ..ui_utils import get_filepath, set_widget_background_color
from ..api_calls.threedi_calls import ThreediCalls


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_start_page, basecls_start_page = uic.loadUiType(os.path.join(base_dir, "ui", "upload_wizard", "page_start.ui"))
uicls_check_page, basecls_check_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "upload_wizard", "page_check_model.ui")
)
uicls_files_page, basecls_files_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "upload_wizard", "page_select_files.ui")
)


class StartWidget(uicls_start_page, basecls_start_page):
    """Widget for the Start page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        # set_widget_background_color(self)


class CheckModelWidget(uicls_check_page, basecls_check_page):
    """Widget for the Check Model page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        # set_widget_background_color(self)


class SelectFilesWidget(uicls_files_page, basecls_files_page):
    """Widget for the Select Files page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        # set_widget_background_color(self)


class StartPage(QWizardPage):
    """Upload start definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = StartWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class CheckModelPage(QWizardPage):
    """Upload Check Model definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = CheckModelWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SelectFilesPage(QWizardPage):
    """Upload Select Files definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SelectFilesWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class UploadWizard(QWizard):
    """New upload wizard."""

    def __init__(self, parent_dock, upload_dialog, parent=None):
        super().__init__(parent)
        self.settings = QSettings()
        self.setWizardStyle(QWizard.ClassicStyle)
        self.parent_dock = parent_dock
        self.upload_dialog = upload_dialog
        self.tc = self.upload_dialog.tc
        self.latest_revision = self.tc.fetch_schematisation_latest_revision(self.upload_dialog.schematisation.id).number
        self.start_page = StartPage(self)
        self.start_page.main_widget.lbl_schematisation.setText(self.upload_dialog.schematisation.name)
        self.start_page.main_widget.lbl_online_revision.setText(str(self.latest_revision))
        self.check_model_page = CheckModelPage(self)
        self.select_files_page = SelectFilesPage(self)
        self.addPage(self.start_page)
        self.addPage(self.check_model_page)
        self.addPage(self.select_files_page)

        self.setButtonText(QWizard.FinishButton, "Start upload")
        self.finish_btn = self.button(QWizard.FinishButton)
        self.finish_btn.clicked.connect(self.start_upload)
        self.cancel_btn = self.button(QWizard.CancelButton)
        self.cancel_btn.clicked.connect(self.cancel_wizard)
        self.new_upload = defaultdict(lambda: None)
        self.new_upload_statuses = None
        self.setWindowTitle("New upload")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(self.settings.value("threedi/upload_wizard_size", QSize(800, 600)))

    def start_upload(self):
        self.new_upload.clear()
        self.new_upload["schematisation"] = self.upload_dialog.schematisation
        self.new_upload["commit_message"] = self.select_files_page.main_widget.te_upload_description.toPlainText()
        self.new_upload["latest_revision"] = self.latest_revision
        self.new_upload["sqlite_filepath"] = self.upload_dialog.schematisation_sqlite

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        self.settings.setValue("threedi/upload_wizard_size", self.size())
        self.reject()
