import os
import sys
import json
from math import ceil
from qgis.PyQt.QtSvg import QGraphicsSvgItem
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor

from qgis.PyQt.QtWidgets import QWizardPage, QWizard, QGridLayout, QGraphicsScene, QSizePolicy, QInputDialog
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
    def __init__(self, parent_page):
        super(Page1Widget, self).__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        scene = QGraphicsScene()
        item = QGraphicsSvgItem(os.path.join(base_dir, 'icons', 'sim_wizard_p1.svg'))
        scene.addItem(item)
        self.gv_svg.setScene(scene)
        set_widget_background_color(self.gv_svg)
        set_widget_background_color(self)
        line_edit = self.cbo_db.lineEdit()
        line_edit.setPlaceholderText('Choose database')


class Page2aWidget(uicls_p2a, basecls_p2a):
    def __init__(self, parent_page):
        super(Page2aWidget, self).__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        scene = QGraphicsScene()
        item = QGraphicsSvgItem(os.path.join(base_dir, 'icons', 'sim_wizard_p2.svg'))
        scene.addItem(item)
        self.gv_svg.setScene(scene)
        set_widget_background_color(self.gv_svg)
        set_widget_background_color(self)


class Page2bWidget(uicls_p2b, basecls_p2b):
    def __init__(self, parent_page):
        super(Page2bWidget, self).__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        scene = QGraphicsScene()
        item = QGraphicsSvgItem(os.path.join(base_dir, 'icons', 'sim_wizard_p2.svg'))
        scene.addItem(item)
        self.gv_svg.setScene(scene)
        set_widget_background_color(self.gv_svg)
        set_widget_background_color(self)


class Page3Widget(uicls_p3, basecls_p3):
    def __init__(self, parent_page):
        super(Page3Widget, self).__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.setMaximumHeight(100)
        self.plot_widget.hideAxis('left')
        self.plot_bar_graph = None
        self.plot_ticks = None
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
        self.plot_bar_graph = None
        self.plot_ticks = None
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
        dx = [(value, f"{ceil(value / 60)} (mins)") for value in x_values]
        self.plot_ticks = [[dx[0], dx[-1]]]
        ax = self.plot_widget.getAxis('bottom')
        ax.setTicks(self.plot_ticks)
        self.plot_bar_graph = pg.BarGraphItem(x=x_values, height=y_values, width=width, brush=QColor('#1883D7'))
        self.plot_widget.addItem(self.plot_bar_graph)

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
    def __init__(self, parent_page):
        super(Page4Widget, self).__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.setMaximumHeight(100)
        self.plot_widget.hideAxis('left')
        self.lout_plot.addWidget(self.plot_widget, 0, 0)
        scene = QGraphicsScene()
        item = QGraphicsSvgItem(os.path.join(base_dir, 'icons', 'sim_wizard_p4.svg'))
        scene.addItem(item)
        self.gv_svg.setScene(scene)
        set_widget_background_color(self.gv_svg)
        set_widget_background_color(self)

    def plot_last_precipitation(self):
        self.plot_widget.clear()
        plot_bar_graph = self.parent_page.parent_wizard.p3.main_widget.plot_bar_graph
        if plot_bar_graph is None:
            return
        new_bar_graph = pg.BarGraphItem(**plot_bar_graph.opts)
        plot_ticks = self.parent_page.parent_wizard.p3.main_widget.plot_ticks
        ax = self.plot_widget.getAxis('bottom')
        ax.setTicks(plot_ticks)
        self.plot_widget.addItem(new_bar_graph)


class Page1(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = Page1Widget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page2a(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = Page2aWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page2b(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = Page2bWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page3(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = Page3Widget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page4(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = Page4Widget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SimulationWizard(QWizard):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.p1 = Page1(self)
        self.p2a = Page2a(self)
        self.p2b = Page2b(self)
        self.p3 = Page3(self)
        self.p4 = Page4(self)
        self.addPage(self.p1)
        self.addPage(self.p2a)
        self.addPage(self.p2b)
        self.addPage(self.p3)
        self.addPage(self.p4)
        self.currentIdChanged.connect(self.page_changed)
        self.setWindowTitle("New simulation")
        self.setStyleSheet("background-color:#F0F0F0")
        self.parentWidget().setStyleSheet("background-color:#F0F0F0")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(850, 600)

    def page_changed(self, page_id):
        print(page_id)
        if page_id == 4:
            self.p4.main_widget.plot_last_precipitation()
