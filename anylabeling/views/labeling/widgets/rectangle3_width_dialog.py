# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore

class Rectangle3WidthDialog(QtWidgets.QDialog):
    """Dialog for configuring rectangle3 width."""

    width_changed = QtCore.pyqtSignal(int)

    def __init__(self, parent=None, initial_width=200):
        super(Rectangle3WidthDialog, self).__init__(parent)
        self.setWindowTitle(self.tr("Rectangle3 宽度设置"))
        self.setWindowFlags(
            self.windowFlags()
            & ~QtCore.Qt.WindowContextHelpButtonHint
            | QtCore.Qt.WindowMinimizeButtonHint
        )
        self.setMinimumWidth(300)

        main_layout = QtWidgets.QVBoxLayout(self)

        width_layout = QtWidgets.QHBoxLayout()
        width_label = QtWidgets.QLabel(self.tr("宽度："))
        width_layout.addWidget(width_label)

        self.width_spinbox = QtWidgets.QSpinBox()
        self.width_spinbox.setRange(1, 10000)
        self.width_spinbox.setValue(initial_width)
        self.width_spinbox.valueChanged.connect(self.on_width_changed)
        width_layout.addWidget(self.width_spinbox)
        width_layout.addWidget(QtWidgets.QLabel(self.tr("像素")))

        main_layout.addLayout(width_layout)

    def on_width_changed(self, value):
        self.width_changed.emit(value)

    def closeEvent(self, event):
        if self.parent():
            self.parent().rectangle3_width_dialog = None
        super(Rectangle3WidthDialog, self).closeEvent(event)
