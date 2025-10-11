# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui

class ExpandMarginsDialog(QtWidgets.QDialog):
    """A dialog for expanding/shrinking bounding box margins."""

    # Signals to be emitted when buttons are clicked
    # The dictionary will have the format: {label: (top, bottom, left, right)}
    apply_current = QtCore.pyqtSignal(dict)
    apply_selected = QtCore.pyqtSignal(dict)
    apply_all = QtCore.pyqtSignal(dict)
    apply_all_in_range = QtCore.pyqtSignal(dict, int, int)
    apply_single_label = QtCore.pyqtSignal(dict)
    apply_single_label_selected = QtCore.pyqtSignal(dict)
    jump_to_image = QtCore.pyqtSignal(int)

    def __init__(self, labels, parent=None):
        super(ExpandMarginsDialog, self).__init__(parent)
        self.setWindowTitle(self.tr("标注框边距扩展工具"))
        self.setMinimumWidth(550)
        self.resize(565, 404)

        # 恢复上次保存的窗口位置
        self.restore_window_position()

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

        # Install event filter to handle left and right clicks on the table
        self.table_widget.viewport().installEventFilter(self)

        # Add hover effect for label column
        self.table_widget.setStyleSheet("""
            QTableWidget::item:hover {
                background-color: rgba(0, 120, 215, 0.2);
            }
        """)

        self.populate_table(labels)
        layout.addWidget(self.table_widget)

        # Range selection group
        range_group = QtWidgets.QGroupBox(self.tr("范围选择"))
        range_layout = QtWidgets.QHBoxLayout(range_group)
        range_layout.setContentsMargins(10, 10, 10, 10)
        range_layout.setSpacing(10)

        self.start_spinbox = QtWidgets.QSpinBox()
        self.start_spinbox.setPrefix(self.tr("从: "))
        self.end_spinbox = QtWidgets.QSpinBox()
        self.end_spinbox.setPrefix(self.tr("到: "))

        # Get file count from parent to set range
        total_files = 0
        if self.parent() and hasattr(self.parent(), 'file_list_widget'):
            total_files = self.parent().file_list_widget.count()

        if total_files > 0:
            self.start_spinbox.setRange(1, total_files)
            self.end_spinbox.setRange(1, total_files)
            self.start_spinbox.setValue(1)
            self.end_spinbox.setValue(total_files)

        self.btn_apply_range = QtWidgets.QPushButton(self.tr("扩缩指定范围"))
        self.btn_apply_range.setFixedSize(QtCore.QSize(110, 30))

        range_layout.addWidget(self.start_spinbox)
        range_layout.addWidget(self.end_spinbox)
        range_layout.addWidget(self.btn_apply_range)
        range_layout.addStretch()

        # Add jump to page functionality
        self.jump_spinbox = QtWidgets.QSpinBox()
        self.jump_spinbox.setPrefix(self.tr("跳转到: "))
        if total_files > 0:
            self.jump_spinbox.setRange(1, total_files)
        self.btn_jump = QtWidgets.QPushButton(self.tr("跳转"))
        self.btn_jump.setFixedSize(QtCore.QSize(80, 30))

        range_layout.addWidget(self.jump_spinbox)
        range_layout.addWidget(self.btn_jump)
        
        layout.addWidget(range_group)

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
        self.btn_apply_all.setFixedSize(QtCore.QSize(110, 30))
        self.btn_clear_all.setFixedSize(button_size)

        # Style the clear button differently
        self.btn_clear_all.setStyleSheet("QPushButton { background-color: #ffebcd; }")

        button_layout.addWidget(self.btn_apply_current)
        button_layout.addWidget(self.btn_apply_selected)
        button_layout.addWidget(self.btn_apply_all)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_clear_all)

        layout.addLayout(button_layout)

        # Connect signals
        self.btn_apply_current.clicked.connect(self.on_apply_current)
        self.btn_apply_selected.clicked.connect(self.on_apply_selected)
        self.btn_apply_all.clicked.connect(self.on_apply_all)
        self.btn_apply_range.clicked.connect(self.on_apply_range)
        self.btn_jump.clicked.connect(self.on_jump_to_image)
        self.btn_clear_all.clicked.connect(self.on_clear_all)

        # Add shortcut for closing the dialog
        self.close_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Shift+M"), self)
        self.close_shortcut.activated.connect(self.close)

    def populate_table(self, labels):
        self.table_widget.setRowCount(len(labels))
        for i, label in enumerate(labels):
            # Label item with color background
            label_item = QtWidgets.QTableWidgetItem(label)
            label_item.setFlags(label_item.flags() & ~QtCore.Qt.ItemIsEditable)

            # Add tooltip to indicate clickable functionality
            label_item.setToolTip(self.tr("左键清零, 右键扩缩本页单个标签, 中键扩缩选中单个标签"))

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
        """Clears and repopulates the table with a new list of labels, preserving existing values."""
        # Save current margin values before clearing
        current_values = {}
        if self.table_widget.rowCount() > 0:
            current_values = self.get_margin_values()

        # Clear the table and repopulate with colors
        self.table_widget.setRowCount(0)
        self.populate_table(labels)

        # Restore saved values for labels that still exist
        self.restore_margin_values(current_values)

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

    def restore_margin_values(self, saved_values):
        """Restores margin values from a saved dictionary."""
        if not saved_values:
            return

        for i in range(self.table_widget.rowCount()):
            label = self.table_widget.item(i, 0).text()
            if label in saved_values:
                top, bottom, left, right = saved_values[label]
                # Set the values in the spinboxes
                self.table_widget.cellWidget(i, 1).setValue(top)      # Top
                self.table_widget.cellWidget(i, 2).setValue(bottom)   # Bottom
                self.table_widget.cellWidget(i, 3).setValue(left)     # Left
                self.table_widget.cellWidget(i, 4).setValue(right)    # Right

    def on_apply_current(self):
        margins = self.get_margin_values()
        self.apply_current.emit(margins)

    def on_apply_selected(self):
        margins = self.get_margin_values()
        self.apply_selected.emit(margins)

    def on_apply_all(self):
        margins = self.get_margin_values()
        self.apply_all.emit(margins)

    def on_apply_range(self):
        """Handle applying margins to a specified range of images."""
        margins = self.get_margin_values()
        start_index = self.start_spinbox.value() - 1
        end_index = self.end_spinbox.value() - 1

        # Basic validation to ensure start is not after end
        if start_index > end_index:
            QtWidgets.QMessageBox.warning(
                self, self.tr("范围无效"), self.tr("起始位置不能大于结束位置。")
            )
            return
            
        self.apply_all_in_range.emit(margins, start_index, end_index)

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

    def eventFilter(self, source, event):
        """Filter events to handle left and right clicks on the table."""
        if source is self.table_widget.viewport() and event.type() == QtCore.QEvent.MouseButtonPress:
            index = self.table_widget.indexAt(event.pos())
            if index.isValid() and index.column() == 0:
                if event.button() == QtCore.Qt.LeftButton:
                    self.clear_row(index.row())
                    return True  # Event handled
                elif event.button() == QtCore.Qt.RightButton:
                    self.on_apply_single_label(index.row())
                    return True  # Event handled
                elif event.button() == QtCore.Qt.MidButton:
                    self.on_apply_single_label_selected(index.row())
                    return True  # Event handled
        return super(ExpandMarginsDialog, self).eventFilter(source, event)

    def clear_row(self, row):
        """Clear all margin values for a specific row."""
        for j in range(1, 5):  # Columns for Top, Bottom, Left, Right
            spinbox = self.table_widget.cellWidget(row, j)
            if spinbox:
                spinbox.setValue(0.0)

    def on_apply_single_label_selected(self, row):
        """Emit a signal to apply margins for a single label on selected shapes."""
        label = self.table_widget.item(row, 0).text()
        top = self.table_widget.cellWidget(row, 1).value()
        bottom = self.table_widget.cellWidget(row, 2).value()
        left = self.table_widget.cellWidget(row, 3).value()
        right = self.table_widget.cellWidget(row, 4).value()
        margins = {label: (top, bottom, left, right)}
        self.apply_single_label_selected.emit(margins)

    def on_apply_single_label(self, row):
        """Emit a signal to apply margins for a single label on the current page."""
        label = self.table_widget.item(row, 0).text()
        top = self.table_widget.cellWidget(row, 1).value()
        bottom = self.table_widget.cellWidget(row, 2).value()
        left = self.table_widget.cellWidget(row, 3).value()
        right = self.table_widget.cellWidget(row, 4).value()
        margins = {label: (top, bottom, left, right)}
        self.apply_single_label.emit(margins)

    def on_jump_to_image(self):
        """Handle jumping to a specific image index."""
        index = self.jump_spinbox.value() - 1
        self.jump_to_image.emit(index)

    def set_current_page(self, page_number):
        """Sets the value of the jump spinbox."""
        if self.jump_spinbox.minimum() <= page_number <= self.jump_spinbox.maximum():
            self.jump_spinbox.setValue(page_number)

    def restore_window_position(self):
        """恢复上次保存的窗口位置"""
        settings = QtCore.QSettings()
        geometry = settings.value("expand_margins_dialog/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
            # 确保窗口不是最小化状态
            if self.isMinimized():
                self.showNormal()
        else:
            # 如果没有保存的位置，设置默认位置（相对于父窗口居中）
            if self.parent():
                parent_geometry = self.parent().geometry()
                x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
                y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
                self.move(x, y)

    def save_window_position(self):
        """保存当前窗口位置"""
        settings = QtCore.QSettings()
        settings.setValue("expand_margins_dialog/geometry", self.saveGeometry())

    def closeEvent(self, event):
        """窗口关闭事件，保存位置"""
        self.save_window_position()
        super(ExpandMarginsDialog, self).closeEvent(event)

    def hideEvent(self, event):
        """窗口隐藏事件，保存位置"""
        self.save_window_position()
        super(ExpandMarginsDialog, self).hideEvent(event)