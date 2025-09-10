# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui

class ExpandMarginsDialog(QtWidgets.QDialog):
    """A dialog for expanding/shrinking bounding box margins."""

    # Signals to be emitted when buttons are clicked
    # The dictionary will have the format: {label: (top, bottom, left, right)}
    apply_current = QtCore.pyqtSignal(dict)
    apply_selected = QtCore.pyqtSignal(dict)
    apply_all = QtCore.pyqtSignal(dict)

    def __init__(self, labels, parent=None):
        super(ExpandMarginsDialog, self).__init__(parent)
        self.setWindowTitle(self.tr("标注框边距扩展工具"))
        self.setMinimumWidth(550)
        self.resize(565, 404)

        # Main Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Table for margin inputs
        self.table_widget = QtWidgets.QTableWidget()
        self.table_widget.setColumnCount(5)
        self.table_widget.setHorizontalHeaderLabels(
            [
                self.tr("标签"),
                self.tr("上"),
                self.tr("下"),
                self.tr("左"),
                self.tr("右"),
            ]
        )
        self.table_widget.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch
        )
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.NoSelection
        )

        self.populate_table(labels)
        layout.addWidget(self.table_widget)

        # Action Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.btn_apply_current = QtWidgets.QPushButton(self.tr("只扩缩本页"))
        self.btn_apply_selected = QtWidgets.QPushButton(self.tr("只扩缩选中"))
        self.btn_apply_all = QtWidgets.QPushButton(self.tr("扩缩全部页码"))

        button_layout.addWidget(self.btn_apply_current)
        button_layout.addWidget(self.btn_apply_selected)
        button_layout.addWidget(self.btn_apply_all)

        layout.addLayout(button_layout)

        # Connect signals
        self.btn_apply_current.clicked.connect(self.on_apply_current)
        self.btn_apply_selected.clicked.connect(self.on_apply_selected)
        self.btn_apply_all.clicked.connect(self.on_apply_all)

    def populate_table(self, labels):
        self.table_widget.setRowCount(len(labels))
        for i, label in enumerate(labels):
            # Label item (read-only)
            label_item = QtWidgets.QTableWidgetItem(label)
            label_item.setFlags(label_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table_widget.setItem(i, 0, label_item)

            # Spinboxes for margin values
            for j in range(1, 5):  # Columns for Top, Bottom, Left, Right
                spinbox = QtWidgets.QDoubleSpinBox()
                spinbox.setRange(-1000, 1000)
                spinbox.setDecimals(1)
                spinbox.setSingleStep(1.0)
                spinbox.setValue(0.0)
                self.table_widget.setCellWidget(i, j, spinbox)
        
    def update_labels(self, labels):
        """Clears and repopulates the table with a new list of labels."""
        # A more robust implementation could preserve existing values.
        # For now, a simple clear and repopulate is sufficient.
        self.table_widget.setRowCount(0)
        self.populate_table(labels)

    def get_margin_values(self):
        """Extracts the margin values from the table into a dictionary."""
        margins = {}
        for i in range(self.table_widget.rowCount()):
            label = self.table_widget.item(i, 0).text()
            top = self.table_widget.cellWidget(i, 1).value()
            bottom = self.table_widget.cellWidget(i, 2).value()
            left = self.table_widget.cellWidget(i, 3).value()
            right = self.table_widget.cellWidget(i, 4).value()
            margins[label] = (top, bottom, left, right)
        return margins

    def on_apply_current(self):
        margins = self.get_margin_values()
        self.apply_current.emit(margins)

    def on_apply_selected(self):
        margins = self.get_margin_values()
        self.apply_selected.emit(margins)

    def on_apply_all(self):
        margins = self.get_margin_values()
        self.apply_all.emit(margins)