"""
dialog.py  --  load the .ui file at runtime using qgis.PyQt (Qt5/Qt6 shim).
"""

import os
from pathlib import Path

try:
    from qgis.PyQt import uic, QtWidgets
except ImportError:
    from PyQt5 import uic, QtWidgets  # fallback for standalone testing

UI_PATH = Path(__file__).parent / "main_dialog.ui"


def load_dialog(parent=None):
    """Return a loaded QDialog instance from main_dialog.ui."""
    DialogBase, _ = uic.loadUiType(str(UI_PATH))

    class ScriptBenchDialogImpl(DialogBase, QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setupUi(self)

    return ScriptBenchDialogImpl(parent)
