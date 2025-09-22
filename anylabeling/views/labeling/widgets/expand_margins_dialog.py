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

        # Remove the help/question mark button and add minimize functionality
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowTitleHint |
            QtCore.Qt.WindowSystemMenuHint |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowCloseButtonHint
        )

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

        # Connect cell click signal for single-row clearing
        self.table_widget.cellClicked.connect(self.on_cell_clicked)

        # Add hover effect for label column
        self.table_widget.setStyleSheet("""
            QTableWidget::item:hover {
                background-color: rgba(0, 120, 215, 0.2);
            }
        """)

        self.populate_table(labels)
        layout.addWidget(self.table_widget)

        # Action Buttons
        button_layout = QtWidgets.QHBoxLayout()

        # Create buttons with smaller size
        self.btn_apply_current = QtWidgets.QPushButton(self.tr("只扩缩本页"))
        self.btn_apply_selected = QtWidgets.QPushButton(self.tr("只扩缩选中"))
        self.btn_apply_all = QtWidgets.QPushButton(self.tr("扩缩全部页码"))
        self.btn_clear_all = QtWidgets.QPushButton(self.tr("一键清零"))

        # Set smaller button sizes
        button_size = QtCore.QSize(100, 30)
        self.btn_apply_current.setFixedSize(button_size)
        self.btn_apply_selected.setFixedSize(button_size)
        self.btn_apply_all.setFixedSize(button_size)
        self.btn_clear_all.setFixedSize(button_size)

        # Style the clear button differently
        self.btn_clear_all.setStyleSheet("QPushButton { background-color: #ffebcd; }")

        button_layout.addWidget(self.btn_apply_current)
        button_layout.addWidget(self.btn_apply_selected)
        button_layout.addWidget(self.btn_apply_all)
        button_layout.addWidget(self.btn_clear_all)

        layout.addLayout(button_layout)

        # Connect signals
        self.btn_apply_current.clicked.connect(self.on_apply_current)
        self.btn_apply_selected.clicked.connect(self.on_apply_selected)
        self.btn_apply_all.clicked.connect(self.on_apply_all)
        self.btn_clear_all.clicked.connect(self.on_clear_all)

    def populate_table(self, labels):
        self.table_widget.setRowCount(len(labels))
        for i, label in enumerate(labels):
            # Label item with color background
            label_item = QtWidgets.QTableWidgetItem(label)
            label_item.setFlags(label_item.flags() & ~QtCore.Qt.ItemIsEditable)

            # Add tooltip to indicate clickable functionality
            label_item.setToolTip(self.tr("点击清零此行的所有边距值"))

            # Get label color using the new method
            self._update_label_color(label_item, label)

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
        # Clear the table and repopulate with colors
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

    def on_clear_all(self):
        """Clear all margin values to zero."""
        for i in range(self.table_widget.rowCount()):
            for j in range(1, 5):  # Columns for Top, Bottom, Left, Right
                spinbox = self.table_widget.cellWidget(i, j)
                if spinbox:
                    spinbox.setValue(0.0)

    def refresh_colors(self):
        """Refresh colors for all label items and sync with current labels."""
        if not self.parent() or not hasattr(self.parent(), 'unique_label_list'):
            return

        # Get current labels from parent's unique_label_list
        current_labels = []
        for i in range(self.parent().unique_label_list.count()):
            item = self.parent().unique_label_list.item(i)
            label_text = item.data(QtCore.Qt.UserRole)
            current_labels.append(label_text)

        # Check if we need to update the table structure
        existing_labels = []
        for i in range(self.table_widget.rowCount()):
            label_item = self.table_widget.item(i, 0)
            if label_item:
                existing_labels.append(label_item.text())

        # If labels have changed, update the entire table
        if set(current_labels) != set(existing_labels):
            self.update_labels(current_labels)
        else:
            # Just refresh colors for existing labels
            for i in range(self.table_widget.rowCount()):
                label_item = self.table_widget.item(i, 0)
                if label_item:
                    label = label_item.text()
                    self._update_label_color(label_item, label)

    def _update_label_color(self, label_item, label):
        """Update the color of a single label item - only color labels that exist on current page."""
        # First check if this label exists in current page
        label_exists_on_current_page = False
        if self.parent() and hasattr(self.parent(), 'canvas'):
            try:
                for shape in self.parent().canvas.shapes:
                    if shape.label == label:
                        label_exists_on_current_page = True
                        break
            except Exception:
                pass

        # If label doesn't exist on current page, keep default appearance
        if not label_exists_on_current_page:
            label_item.setBackground(QtGui.QBrush())
            label_item.setForeground(QtGui.QBrush())
            return

        # Label exists on current page, apply color
        # Method 1: Try to get color from unique_label_list (most accurate)
        if self.parent() and hasattr(self.parent(), 'unique_label_list'):
            try:
                items = self.parent().unique_label_list.find_items_by_label(label)
                if items and len(items) > 0:
                    list_item = items[0]
                    background_color = list_item.background()
                    if background_color.color().isValid():
                        label_item.setBackground(background_color)
                        rgb = background_color.color().getRgb()[:3]
                        luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
                        text_color = QtGui.QColor(0, 0, 0) if luminance > 0.5 else QtGui.QColor(255, 255, 255)
                        label_item.setForeground(text_color)
                        return
            except Exception:
                pass

        # Method 2: Fallback to computed color
        if self.parent() and hasattr(self.parent(), '_get_rgb_by_label'):
            try:
                rgb = self.parent()._get_rgb_by_label(label)
                # Apply the same LABEL_OPACITY as the main interface
                color = QtGui.QColor(rgb[0], rgb[1], rgb[2], 128)  # LABEL_OPACITY = 128
                label_item.setBackground(color)

                luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
                text_color = QtGui.QColor(0, 0, 0) if luminance > 0.5 else QtGui.QColor(255, 255, 255)
                label_item.setForeground(text_color)
                return
            except Exception:
                pass

        # Method 3: Reset to default if all methods fail
        label_item.setBackground(QtGui.QBrush())
        label_item.setForeground(QtGui.QBrush())

    def on_cell_clicked(self, row, column):
        """Handle cell click - if label column (0) is clicked, clear that row."""
        if column == 0:  # Label column clicked
            # Clear all margin values for this row
            for j in range(1, 5):  # Columns for Top, Bottom, Left, Right
                spinbox = self.table_widget.cellWidget(row, j)
                if spinbox:
                    spinbox.setValue(0.0)