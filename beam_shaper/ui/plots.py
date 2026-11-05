import numpy as np
import pyqtgraph as pg

pg.setConfigOptions(background="w", foreground="k", antialias=True)

# Line colours: the matplotlib defaults used by the previous version
BLUE = pg.mkPen("#1f77b4", width=2)
ORANGE = pg.mkPen("#ff7f0e", width=2)


def make_plot(title, x_label=None):
    plot = pg.PlotWidget(title=title)
    plot.showGrid(x=True, y=True, alpha=0.2)
    if x_label:
        plot.setLabel("bottom", x_label)
    return plot


class PreviewWindow(pg.PlotWidget):
    """A standalone window showing one curve."""

    def __init__(self, title, data):
        super().__init__(title=title)
        self.setWindowTitle(title)
        self.showGrid(x=True, y=True, alpha=0.2)
        self.plot(np.asarray(data), pen=BLUE)
        self.resize(640, 420)
