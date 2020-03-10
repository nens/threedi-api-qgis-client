import os
import sys
import json
from math import ceil
from qgis.PyQt.QtSvg import QGraphicsSvgItem
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor

from qgis.PyQt.QtWidgets import QApplication, QWizardPage, QWizard, QGridLayout, QGraphicsScene, QSizePolicy, QInputDialog
try:
    import pyqtgraph as pg
except ImportError:
    main_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    deps_path = os.path.join(main_dir, "deps", "pyqtgraph-0.10.0-py3-none-any.whl")
    sys.path.append(deps_path)
    import pyqtgraph as pg


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_p1, basecls_p1 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page1.ui'))
uicls_p2a, basecls_p2a = uic.loadUiType(os.path.join(base_dir, 'ui', 'page2a.ui'))
uicls_p2b, basecls_p2b = uic.loadUiType(os.path.join(base_dir, 'ui', 'page2b.ui'))
uicls_p3, basecls_p3 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page3.ui'))
uicls_p4, basecls_p4 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page4.ui'))


def set_widget_background_color(widget, hex_color='#F0F0F0'):
    palette = widget.palette()
    palette.setColor(widget.backgroundRole(), QColor(hex_color))
    widget.setPalette(palette)


class Page1Widget(uicls_p1, basecls_p1):
    def __init__(self):
        super(Page1Widget, self).__init__()
        self.setupUi(self)
        scene = QGraphicsScene()
        item = QGraphicsSvgItem(os.path.join(base_dir, 'icons', 'sim_wizard_p1.svg'))
        scene.addItem(item)
        self.gv_svg.setScene(scene)
        set_widget_background_color(self.gv_svg)
        set_widget_background_color(self)
        line_edit = self.cbo_db.lineEdit()
        line_edit.setPlaceholderText('Choose database')


class Page2aWidget(uicls_p2a, basecls_p2a):
    def __init__(self):
        super(Page2aWidget, self).__init__()
        self.setupUi(self)
        scene = QGraphicsScene()
        item = QGraphicsSvgItem(os.path.join(base_dir, 'icons', 'sim_wizard_p2.svg'))
        scene.addItem(item)
        self.gv_svg.setScene(scene)
        set_widget_background_color(self.gv_svg)
        set_widget_background_color(self)


class Page2bWidget(uicls_p2b, basecls_p2b):
    def __init__(self):
        super(Page2bWidget, self).__init__()
        self.setupUi(self)
        scene = QGraphicsScene()
        item = QGraphicsSvgItem(os.path.join(base_dir, 'icons', 'sim_wizard_p2.svg'))
        scene.addItem(item)
        self.gv_svg.setScene(scene)
        set_widget_background_color(self.gv_svg)
        set_widget_background_color(self)


class Page3Widget(uicls_p3, basecls_p3):
    def __init__(self):
        super(Page3Widget, self).__init__()
        self.setupUi(self)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.setMaximumHeight(100)
        self.plot_widget.hideAxis('left')
        self.lout_plot.addWidget(self.plot_widget, 0, 0)
        self.custom_time_series = [[0, 200], [300, 300], [600, 400], [900, 200], [1200, 50]]
        self.widget_constant.hide()
        self.widget_custom.hide()
        self.widget_design.hide()
        self.cbo_prec_type.currentIndexChanged.connect(self.precipitation_changed)
        self.le_intensity.textChanged.connect(self.plot_precipitation)
        self.pb_set.clicked.connect(self.set_custom_time_series)
        set_widget_background_color(self)
        scene = QGraphicsScene()
        item = QGraphicsSvgItem(os.path.join(base_dir, 'icons', 'sim_wizard_p3.svg'))
        scene.addItem(item)
        self.gv_svg.setScene(scene)
        set_widget_background_color(self.gv_svg)
        self.plot_precipitation()

    def precipitation_changed(self, idx):
        if idx == 1:
            self.widget_constant.show()
            self.widget_custom.hide()
            self.widget_design.hide()
        elif idx == 2:
            self.widget_constant.hide()
            self.widget_custom.show()
            self.widget_design.hide()
        elif idx == 3:
            self.widget_constant.hide()
            self.widget_custom.hide()
            self.widget_design.show()
        else:
            self.widget_constant.hide()
            self.widget_custom.hide()
            self.widget_design.hide()
        self.plot_precipitation()

    def plot_precipitation(self):
        self.plot_widget.clear()
        ax = self.plot_widget.getAxis('bottom')
        x_values, y_values = [], []
        current_index = self.cbo_prec_type.currentIndex()
        if current_index == 1:
            try:
                intensity = float(self.le_intensity.text())
            except ValueError:
                return
            x_values += list(range(0, 3600 + 180, 180))
            y_values += [intensity] * 21
        elif current_index == 2:
            for x, y in self.custom_time_series:
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    x_values.append(x)
                    y_values.append(y)
                else:
                    return
        else:
            #  TODO: Add handling for Design
            return
        width = x_values[1] - x_values[0]
        bar_graph_item = pg.BarGraphItem(x=x_values, height=y_values, width=width, brush=QColor('#1883D7'))
        dx = [(value, f"{ceil(value / 60)} (mins)") for value in x_values]
        ax.setTicks([[dx[0], dx[-1]]])
        self.plot_widget.addItem(bar_graph_item)

    def set_custom_time_series(self):
        text_ts = json.dumps(self.custom_time_series) if self.custom_time_series else ''
        text, ok = QInputDialog.getMultiLineText(None, 'Precipitation Time Series', '', text=text_ts)
        if ok is False:
            return
        try:
            time_series = json.loads(text)
        except json.JSONDecodeError as e:
            return
        self.custom_time_series = time_series
        self.plot_precipitation()


class Page4Widget(uicls_p4, basecls_p4):
    def __init__(self):
        super(Page4Widget, self).__init__()
        self.setupUi(self)
        scene = QGraphicsScene()
        item = QGraphicsSvgItem(os.path.join(base_dir, 'icons', 'sim_wizard_p4.svg'))
        scene.addItem(item)
        self.gv_svg.setScene(scene)
        set_widget_background_color(self.gv_svg)
        set_widget_background_color(self)
        # self.lout_plot.addWidget(self.plot_widget, 0, 0)


class Page1(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout()
        layout.addWidget(Page1Widget(), 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page2a(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout()
        layout.addWidget(Page2aWidget(), 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page2b(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout()
        layout.addWidget(Page2bWidget(), 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page3(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout()
        layout.addWidget(Page3Widget(), 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page4(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout()
        layout.addWidget(Page4Widget(), 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SimulationWizard(QWizard):

    def __init__(self, parent=None):
        super().__init__(parent)
        p1 = Page1(self)
        p2a = Page2a(self)
        p2b = Page2b(self)
        p3 = Page3(self)
        p4 = Page4(self)
        self.addPage(p1)
        self.addPage(p2a)
        self.addPage(p2b)
        self.addPage(p3)
        self.addPage(p4)
        self.setWindowTitle("New simulation")
        self.setStyleSheet("background-color:#F0F0F0")
        self.parentWidget().setStyleSheet("background-color:#F0F0F0")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(850, 600)


def run_new_simulation():
    app = QApplication([])
    d = SimulationWizard()
    d.exec()


if __name__ == '__main__':
    run_new_simulation()
