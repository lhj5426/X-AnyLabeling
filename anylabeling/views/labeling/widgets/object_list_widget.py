# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore


class ObjectListWidget(QtWidgets.QListWidget):
    order_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super(ObjectListWidget, self).__init__(parent)
        self._is_dragging = False

    def startDrag(self, supportedActions):
        self._is_dragging = True
        super(ObjectListWidget, self).startDrag(supportedActions)

    def dropEvent(self, event):
        super(ObjectListWidget, self).dropEvent(event)
        if self._is_dragging:
            self.order_changed.emit()
            self._is_dragging = False