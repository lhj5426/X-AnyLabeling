# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore

class Rectangle3WidthDialog(QtWidgets.QDialog):
    """Dialog for configuring rectangle3 width."""

    width_changed = QtCore.pyqtSignal(int)
    copy_line_length_changed = QtCore.pyqtSignal(int)

    def __init__(self, parent=None, initial_width=200, initial_copy_line_length=500):
        super(Rectangle3WidthDialog, self).__init__(parent)
        self.setWindowTitle(self.tr("新标注模式设置"))
        self.setWindowFlags(
            self.windowFlags()
            & ~QtCore.Qt.WindowContextHelpButtonHint
            | QtCore.Qt.WindowMinimizeButtonHint
        )
        self.setMinimumWidth(300)

        main_layout = QtWidgets.QVBoxLayout(self)

        # Rectangle3 宽度设置
        width_layout = QtWidgets.QHBoxLayout()
        width_label = QtWidgets.QLabel(self.tr("Rectangle3 宽度设置："))
        width_layout.addWidget(width_label)

        self.width_spinbox = QtWidgets.QSpinBox()
        self.width_spinbox.setRange(1, 10000)
        self.width_spinbox.setValue(initial_width)
        self.width_spinbox.valueChanged.connect(self.on_width_changed)
        width_layout.addWidget(self.width_spinbox)
        width_layout.addWidget(QtWidgets.QLabel(self.tr("像素")))

        main_layout.addLayout(width_layout)
        
        # Rotation3 虚线长度设置
        copy_line_layout = QtWidgets.QHBoxLayout()
        copy_line_label = QtWidgets.QLabel(self.tr("Rotation3 虚线长度设置："))
        copy_line_layout.addWidget(copy_line_label)

        self.copy_line_spinbox = QtWidgets.QSpinBox()
        self.copy_line_spinbox.setRange(100, 5000)
        self.copy_line_spinbox.setValue(initial_copy_line_length)
        self.copy_line_spinbox.valueChanged.connect(self.on_copy_line_length_changed)
        copy_line_layout.addWidget(self.copy_line_spinbox)
        copy_line_layout.addWidget(QtWidgets.QLabel(self.tr("像素")))

        main_layout.addLayout(copy_line_layout)

    def on_width_changed(self, value):
        self.width_changed.emit(value)
    
    def on_copy_line_length_changed(self, value):
        self.copy_line_length_changed.emit(value)

    def closeEvent(self, event):
        if self.parent():
            self.parent().rectangle3_width_dialog = None
        super(Rectangle3WidthDialog, self).closeEvent(event)
