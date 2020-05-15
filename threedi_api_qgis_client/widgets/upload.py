import os
from qgis.PyQt import uic


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_log, basecls_log = uic.loadUiType(os.path.join(base_dir, 'ui', 'upload_dialog.ui'))


class UploadDialog(uicls_log, basecls_log):
    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_dock = parent_dock
        self.communication = self.parent_dock.communication

        self.pb_cancel.clicked.connect(self.close)
        self.resize(600, 350)
