import os
import sys
from qgis.PyQt.QtSvg import QGraphicsSvgItem
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor

from qgis.PyQt.QtWidgets import QApplication, QWizardPage, QWizard, QGridLayout, QGraphicsScene, QSizePolicy
try:
    import pyqtgraph as pg
except ImportError:
    temp_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    print(temp_dir)
    path = os.path.join(temp_dir, "deps", "pyqtgraph-0.10.0.egg")
    print(path)
    sys.path.append(path)
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
        scene = QGraphicsScene()
        item = QGraphicsSvgItem(os.path.join(base_dir, 'icons', 'sim_wizard_p3.svg'))
        scene.addItem(item)
        self.gv_svg.setScene(scene)
        set_widget_background_color(self.gv_svg)
        set_widget_background_color(self)
        x = [0, 1, 2, 3, 4]
        y = [200, 300, 200, 100, 50]
        plot_widget = pg.PlotWidget(self)
        plot_widget.setBackground(None)
        bar_graph_item = pg.BarGraphItem(x=x, height=y,  width=1.0, brush=QColor('#1883D7'))
        plot_widget.addItem(bar_graph_item)
        self.lout_plot.addWidget(plot_widget, 0, 0)


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


class Page1(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        # set the page layout
        layout = QGridLayout()
        layout.addWidget(Page1Widget(), 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page2a(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        # set the page layout
        layout = QGridLayout()
        layout.addWidget(Page2aWidget(), 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page2b(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        # set the page layout
        layout = QGridLayout()
        layout.addWidget(Page2bWidget(), 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page3(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        # set the page layout
        layout = QGridLayout()
        layout.addWidget(Page3Widget(), 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page4(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        # set the page layout
        layout = QGridLayout()
        layout.addWidget(Page4Widget(), 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SimulationWizard(QWizard):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.addPage(Page1(self))
        self.addPage(Page2a(self))
        self.addPage(Page2b(self))
        self.addPage(Page3(self))
        self.addPage(Page4(self))
        self.setWindowTitle("New simulation")
        self.setStyleSheet("background-color:#F0F0F0")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(750, 500)
        #self.setAutoFillBackground(True)
        # set_widget_background_color(self)

    def reject(self):
        self.close()


def run_new_simulation():
    app = QApplication([])
    d = SimulationWizard()
    d.exec()


if __name__ == '__main__':
    run_new_simulation()
