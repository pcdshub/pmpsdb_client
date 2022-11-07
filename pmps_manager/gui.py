from pathlib import Path

from qtpy.QtWidgets import QWidget
from pcdsutils.qt import DesignerDisplay


class PMPSManagerGui(DesignerDisplay, QWidget):
    filename = Path(__file__).parent / 'tables.ui'

