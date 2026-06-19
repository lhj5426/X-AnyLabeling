from PyQt5 import QtCore, QtGui, QtWidgets


UNCATEGORIZED_LABEL = "未分类"


class ImageCategoryManagerDialog(QtWidgets.QDialog):
    category_selected = QtCore.pyqtSignal(str, bool)
    reset_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None, color_getter=None):
        super().__init__(parent)
        self.color_getter = color_getter
        self.setWindowTitle("图片分类管理")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowMinimizeButtonHint)
        self.resize(320, 420)

        layout = QtWidgets.QVBoxLayout(self)

        stats_layout = QtWidgets.QHBoxLayout()
        self.total_label = QtWidgets.QLabel("总数：0")
        self.classified_label = QtWidgets.QLabel("已分类：0")
        stats_layout.addWidget(self.total_label)
        stats_layout.addStretch()
        stats_layout.addWidget(self.classified_label)
        layout.addLayout(stats_layout)

        self.category_table = QtWidgets.QTableWidget(0, 2)
        self.category_table.setHorizontalHeaderLabels(["标签", "数量"])
        self.category_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.category_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.category_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.category_table.verticalHeader().setVisible(False)
        self.category_table.horizontalHeader().setStretchLastSection(False)
        self.category_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch
        )
        self.category_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeToContents
        )
        self.category_table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.category_table)

        button_layout = QtWidgets.QHBoxLayout()
        self.reset_btn = QtWidgets.QPushButton("重置")
        self.reset_btn.clicked.connect(self._on_reset_clicked)
        button_layout.addStretch()
        button_layout.addWidget(self.reset_btn)
        layout.addLayout(button_layout)

    def update_categories(self, total, classified, category_rows, uncategorized_count):
        self.total_label.setText(f"总数：{total}")
        self.classified_label.setText(f"已分类：{classified}")
        self.category_table.setRowCount(0)

        for category, count in category_rows:
            self._add_category_row(category, count, False)

        self._add_category_row(UNCATEGORIZED_LABEL, uncategorized_count, True)

    def _add_category_row(self, category, count, uncategorized):
        row = self.category_table.rowCount()
        self.category_table.insertRow(row)

        label_item = QtWidgets.QTableWidgetItem(category)
        count_item = QtWidgets.QTableWidgetItem(str(count))
        label_item.setData(QtCore.Qt.UserRole, category)
        label_item.setData(QtCore.Qt.UserRole + 1, uncategorized)
        count_item.setData(QtCore.Qt.UserRole, category)
        count_item.setData(QtCore.Qt.UserRole + 1, uncategorized)

        label_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
        count_item.setTextAlignment(QtCore.Qt.AlignCenter)

        background = self._category_background(category, uncategorized)
        if background:
            label_item.setBackground(background)
            count_item.setBackground(background)

        self.category_table.setItem(row, 0, label_item)
        self.category_table.setItem(row, 1, count_item)

    def _category_background(self, category, uncategorized):
        if uncategorized:
            return QtGui.QColor(220, 235, 245)

        rgb = None
        if self.color_getter:
            try:
                rgb = self.color_getter(category)
            except Exception:
                rgb = None
        if rgb and len(rgb) >= 3:
            return QtGui.QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]), 128)
        return None

    def _on_cell_clicked(self, row, _column):
        item = self.category_table.item(row, 0)
        if not item:
            return
        category = item.data(QtCore.Qt.UserRole)
        uncategorized = bool(item.data(QtCore.Qt.UserRole + 1))
        self.category_selected.emit(category, uncategorized)

    def _on_reset_clicked(self):
        self.category_table.clearSelection()
        self.reset_requested.emit()
