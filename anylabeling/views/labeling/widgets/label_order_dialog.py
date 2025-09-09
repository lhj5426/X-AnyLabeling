# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore

class LabelOrderDialog(QtWidgets.QDialog):
    def __init__(self, labels, parent=None):
        super(LabelOrderDialog, self).__init__(parent)
        self.setWindowTitle(self.tr("Label Order Manager"))
        self.setMinimumWidth(300)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.list_widget.addItems(labels)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(self.tr("Drag and drop to reorder labels:")))
        layout.addWidget(self.list_widget)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def get_ordered_labels(self):
        labels = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            labels.append(item.text())
        return labels
