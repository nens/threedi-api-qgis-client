# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import logging
import os
from math import ceil
from operator import attrgetter
from time import sleep

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QStandardItem, QStandardItemModel
from threedi_api_client.openapi import ApiException

from ..api_calls.threedi_calls import ThreediCalls
from ..utils import (
    LocalSchematisation,
    extract_error_message,
    get_download_file,
    list_local_schematisations,
    unzip_archive,
)

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "schematisation_download.ui"))


logger = logging.getLogger(__name__)


class SchematisationDownload(uicls, basecls):
    """Dialog for schematisation download."""

    TABLE_LIMIT = 10

    def __init__(self, plugin_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin_dock = plugin_dock
        self.working_dir = self.plugin_dock.plugin_settings.working_dir
        self.communication = self.plugin_dock.communication
        self.threedi_api = self.plugin_dock.threedi_api
        self.schematisations = None
        self.revisions = None
        self.local_schematisations = list_local_schematisations(self.working_dir)
        self.downloaded_local_schematisation = None
        self.tv_schematisations_model = QStandardItemModel()
        self.schematisations_tv.setModel(self.tv_schematisations_model)
        self.tv_revisions_model = QStandardItemModel()
        self.revisions_tv.setModel(self.tv_revisions_model)
        self.pb_schematisations_prev_page.clicked.connect(self.move_schematisations_backward)
        self.pb_schematisations_next_page.clicked.connect(self.move_schematisations_forward)
        self.schematisations_page_sbox.valueChanged.connect(self.fetch_schematisations)
        self.pb_revisions_prev_page.clicked.connect(self.move_revisions_backward)
        self.pb_revisions_next_page.clicked.connect(self.move_revisions_forward)
        self.revisions_page_sbox.valueChanged.connect(self.fetch_revisions)
        self.pb_revisions_fetch.clicked.connect(self.fetch_revisions)
        self.pb_download.clicked.connect(self.download_schematisation_revision)
        self.pb_cancel.clicked.connect(self.cancel_download_schematisation_revision)
        self.schematisations_search_le.returnPressed.connect(self.search_schematisations)
        self.schematisations_tv.selectionModel().selectionChanged.connect(self.toggle_fetch_revisions)
        self.revisions_tv.selectionModel().selectionChanged.connect(self.toggle_download_schematisation_revision)
        self.fetch_schematisations()

    def toggle_fetch_revisions(self):
        """Toggle fetch revisions button if any schematisation is selected."""
        selection_model = self.schematisations_tv.selectionModel()
        if selection_model.hasSelection():
            self.pb_revisions_fetch.setEnabled(True)
        else:
            self.pb_revisions_fetch.setDisabled(True)
        self.tv_revisions_model.clear()
        self.revisions_page_sbox.setMaximum(1)
        self.revisions_page_sbox.setSuffix(" / 1")
        self.toggle_download_schematisation_revision()

    def toggle_download_schematisation_revision(self):
        """Toggle download button if any schematisation revision is selected."""
        selection_model = self.revisions_tv.selectionModel()
        if selection_model.hasSelection():
            self.pb_download.setEnabled(True)
        else:
            self.pb_download.setDisabled(True)

    def move_schematisations_backward(self):
        """Moving to the previous schematisations results page."""
        self.schematisations_page_sbox.setValue(self.schematisations_page_sbox.value() - 1)

    def move_schematisations_forward(self):
        """Moving to the next schematisations results page."""
        self.schematisations_page_sbox.setValue(self.schematisations_page_sbox.value() + 1)

    def search_schematisations(self):
        """Method used for searching schematisations with text typed withing search bar."""
        self.schematisations_page_sbox.valueChanged.disconnect(self.fetch_schematisations)
        self.schematisations_page_sbox.setValue(1)
        self.schematisations_page_sbox.valueChanged.connect(self.fetch_schematisations)
        self.fetch_schematisations()

    def move_revisions_backward(self):
        """Moving to the previous revisions results page."""
        self.revisions_page_sbox.setValue(self.revisions_page_sbox.value() - 1)

    def move_revisions_forward(self):
        """Moving to the next revisions results page."""
        self.revisions_page_sbox.setValue(self.revisions_page_sbox.value() + 1)

    def fetch_schematisations(self):
        """Fetching schematisation list."""
        try:
            tc = ThreediCalls(self.threedi_api)
            offset = (self.schematisations_page_sbox.value() - 1) * self.TABLE_LIMIT
            text = self.schematisations_search_le.text()

            schematisations, schematisations_count = tc.fetch_schematisations_with_count(
                limit=self.TABLE_LIMIT, offset=offset, name_contains=text
            )
            pages_nr = ceil(schematisations_count / self.TABLE_LIMIT) or 1
            self.schematisations_page_sbox.setMaximum(pages_nr)
            self.schematisations_page_sbox.setSuffix(f" / {pages_nr}")
            self.tv_schematisations_model.clear()
            header = ["Schematisation name", "Slug", "Owner", "Created by"]
            self.tv_schematisations_model.setHorizontalHeaderLabels(header)
            for schematisation in schematisations:
                name_item = QStandardItem(schematisation.name)
                name_item.setData(schematisation, role=Qt.UserRole)
                slug_item = QStandardItem(schematisation.slug)
                organisation = self.plugin_dock.organisations[schematisation.owner]
                owner_item = QStandardItem(organisation.name)
                created_by_item = QStandardItem(schematisation.created_by)
                self.tv_schematisations_model.appendRow([name_item, slug_item, owner_item, created_by_item])
            for i in range(len(header)):
                self.schematisations_tv.resizeColumnToContents(i)
            self.schematisations = schematisations
        except ApiException as e:
            self.close()
            error_msg = extract_error_message(e)
            self.communication.show_error(error_msg)
        except Exception as e:
            self.close()
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)

    def fetch_revisions(self):
        """Fetching schematisation revisions list."""
        try:
            tc = ThreediCalls(self.threedi_api)
            offset = (self.revisions_page_sbox.value() - 1) * self.TABLE_LIMIT
            selected_schematisation = self.get_selected_schematisation()
            schematisation_pk = selected_schematisation.id
            revisions, revisions_count = tc.fetch_schematisation_revisions_with_count(
                schematisation_pk, limit=self.TABLE_LIMIT, offset=offset
            )
            pages_nr = ceil(revisions_count / self.TABLE_LIMIT) or 1
            self.revisions_page_sbox.setMaximum(pages_nr)
            self.revisions_page_sbox.setSuffix(f" / {pages_nr}")
            self.tv_revisions_model.clear()
            header = ["Revision number", "Commit message", "Committed by", "Commit date"]
            self.tv_revisions_model.setHorizontalHeaderLabels(header)
            for revision in revisions:
                number_item = QStandardItem(str(revision.number))
                number_item.setData(revision, role=Qt.UserRole)
                commit_message_item = QStandardItem(revision.commit_message or "")
                commit_user_item = QStandardItem(revision.commit_user or "")
                commit_date = revision.commit_date.strftime("%d-%m-%Y") if revision.commit_date else ""
                commit_date_item = QStandardItem(commit_date)
                self.tv_revisions_model.appendRow(
                    [number_item, commit_message_item, commit_user_item, commit_date_item]
                )
            for i in range(len(header)):
                self.revisions_tv.resizeColumnToContents(i)
            self.revisions = revisions
        except ApiException as e:
            error_msg = extract_error_message(e)
            self.communication.show_error(error_msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)

    def get_selected_schematisation(self):
        """Get currently selected schematisation."""
        index = self.schematisations_tv.currentIndex()
        if index.isValid():
            current_row = index.row()
            name_item = self.tv_schematisations_model.item(current_row, 0)
            selected_schematisation = name_item.data(Qt.UserRole)
        else:
            selected_schematisation = None
        return selected_schematisation

    def get_selected_revision(self):
        """Get currently selected revision."""
        index = self.revisions_tv.currentIndex()
        if index.isValid():
            current_row = index.row()
            name_item = self.tv_revisions_model.item(current_row, 0)
            selected_revision = name_item.data(Qt.UserRole)
        else:
            selected_revision = None
        return selected_revision

    def download_schematisation_revision(self):
        """Downloading selected schematisation revision."""
        selected_schematisation = self.get_selected_schematisation()
        selected_revision = self.get_selected_revision()
        self.download_required_files(selected_schematisation, selected_revision)
        if self.downloaded_local_schematisation:
            self.close()

    def download_required_files(self, schematisation, revision):
        """Download required schematisation revision files."""
        try:
            latest_online_revision = max([rev.number for rev in self.revisions])
            schematisation_pk = schematisation.id
            schematisation_name = schematisation.name
            revision_pk = revision.id
            revision_number = revision.number
            revision_sqlite = revision.sqlite
            is_latest_revision = revision_number == latest_online_revision
            try:
                local_schematisation = self.local_schematisations[schematisation_pk]
                local_schematisation_present = True
            except KeyError:
                local_schematisation = LocalSchematisation(
                    self.working_dir, schematisation_pk, schematisation_name, create=True
                )
                self.local_schematisations[schematisation_pk] = local_schematisation
                local_schematisation_present = False

            def decision_tree():
                title = "Pick action"
                question = f"Replace local WIP or store as a revision {revision_number}?"
                picked_action_name = self.communication.custom_ask(self, title, question, "Replace", "Store")
                if picked_action_name == "Replace":
                    # Replace
                    local_schematisation.set_wip_revision(revision_number)
                    schema_db_dir = local_schematisation.wip_revision.schematisation_dir
                else:
                    # Store as a separate revision
                    if revision_number in local_schematisation.revisions:
                        question = f"Replace local revision {revision_number} or Cancel?"
                        picked_action_name = self.communication.custom_ask(self, title, question, "Replace", "Cancel")
                        if picked_action_name == "Replace":
                            local_revision = local_schematisation.add_revision(revision_number)
                            schema_db_dir = local_revision.schematisation_dir
                        else:
                            schema_db_dir = None
                    else:
                        local_revision = local_schematisation.add_revision(revision_number)
                        schema_db_dir = local_revision.schematisation_dir
                return schema_db_dir

            if local_schematisation_present:
                if is_latest_revision:
                    if local_schematisation.wip_revision is None:
                        # WIP not exist
                        local_schematisation.set_wip_revision(revision_number)
                        schematisation_db_dir = local_schematisation.wip_revision.schematisation_dir
                    else:
                        # WIP exist
                        schematisation_db_dir = decision_tree()
                else:
                    schematisation_db_dir = decision_tree()
            else:
                local_schematisation.set_wip_revision(revision_number)
                schematisation_db_dir = local_schematisation.wip_revision.schematisation_dir

            if not schematisation_db_dir:
                return

            tc = ThreediCalls(self.threedi_api)
            sqlite_download = tc.download_schematisation_revision_sqlite(schematisation_pk, revision_pk)
            revision_models = tc.fetch_schematisation_revision_3di_models(schematisation_pk, revision_pk)
            rasters_downloads = []
            for raster_file in revision.rasters or []:
                raster_download = tc.download_schematisation_revision_raster(
                    raster_file.id, schematisation_pk, revision_pk
                )
                rasters_downloads.append((raster_file.name, raster_download))
            number_of_steps = len(rasters_downloads) + 1

            gridadmin_file, gridadmin_download = (None, None)
            ignore_gridadmin_error_message = "Gridadmin file not found"
            for revision_model in sorted(revision_models, key=attrgetter("id"), reverse=True):
                try:
                    gridadmin_file, gridadmin_download = tc.fetch_3di_model_gridadmin_download(revision_model.id)
                    if gridadmin_download is not None:
                        number_of_steps += 1
                        break
                except ApiException as e:
                    error_msg = extract_error_message(e)
                    if ignore_gridadmin_error_message not in error_msg:
                        raise

            gpkg_file, gpkg_download = (None, None)
            ignore_gpkg_error_message = "Geopackage file not found"
            for revision_model in sorted(revision_models, key=attrgetter("id"), reverse=True):
                try:
                    gpkg_file, gpkg_download = tc.fetch_3di_model_geopackage_download(revision_model.id)
                    if gpkg_download is not None:
                        number_of_steps += 1
                        break
                except ApiException as e:
                    error_msg = extract_error_message(e)
                    if ignore_gpkg_error_message not in error_msg:
                        raise

            if revision_pk in local_schematisation.revisions:
                local_schematisation.add_revision(revision_pk)
            zip_filepath = os.path.join(schematisation_db_dir, revision_sqlite.file.filename)
            self.pbar_download.setMaximum(number_of_steps)
            current_progress = 0
            self.pbar_download.setValue(current_progress)
            get_download_file(sqlite_download, zip_filepath)
            content_list = unzip_archive(zip_filepath)
            os.remove(zip_filepath)
            sqlite_file = content_list[0]
            current_progress += 1
            self.pbar_download.setValue(current_progress)
            if gridadmin_download is not None:
                grid_filepath = os.path.join(os.path.dirname(schematisation_db_dir), "grid", gridadmin_file.filename)
                get_download_file(gridadmin_download, grid_filepath)
                current_progress += 1
                self.pbar_download.setValue(current_progress)
            if gpkg_download is not None:
                gpkg_filepath = os.path.join(os.path.dirname(schematisation_db_dir), "grid", gpkg_file.filename)
                get_download_file(gpkg_download, gpkg_filepath)
                current_progress += 1
                self.pbar_download.setValue(current_progress)
            for raster_filename, raster_download in rasters_downloads:
                raster_filepath = os.path.join(schematisation_db_dir, "rasters", raster_filename)
                get_download_file(raster_download, raster_filepath)
                current_progress += 1
                self.pbar_download.setValue(current_progress)
            local_schematisation.wip_revision.sqlite_filename = sqlite_file
            self.downloaded_local_schematisation = local_schematisation
            sleep(1)
            msg = f"Schematisation '{schematisation_name} (revision {revision_number})' downloaded!"
            self.communication.bar_info(msg, log_text_color=QColor(Qt.darkGreen))
        except ApiException as e:
            error_msg = extract_error_message(e)
            self.communication.show_error(error_msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)

    def cancel_download_schematisation_revision(self):
        """Cancel schematisation revision download."""
        self.close()
