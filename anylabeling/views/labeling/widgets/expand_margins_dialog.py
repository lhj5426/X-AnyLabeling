# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui
import functools

class ClickableLabel(QtWidgets.QLabel):
    """A QLabel that emits signals for left and right clicks."""
    leftClicked = QtCore.pyqtSignal()
    rightClicked = QtCore.pyqtSignal()

    def __init__(self, *args, **kwargs):
        super(ClickableLabel, self).__init__(*args, **kwargs)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #b0b0b0;
                border-radius: 3px;
                padding: 1px;
            }
            QLabel:hover {
                background-color: #e0e0e0;
                border: 1px solid #a0a0a0;
            }
            QLabel:pressed {
                background-color: #d0d0d0;
            }
        """)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setFixedSize(20, 20)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.leftClicked.emit()
        elif event.button() == QtCore.Qt.RightButton:
            self.rightClicked.emit()
        super(ClickableLabel, self).mousePressEvent(event)

class ExpandMarginsDialog(QtWidgets.QDialog):
    """A dialog for expanding/shrinking bounding box margins."""

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
        self.resize(526, 323)

        self.restore_window_position()

        # 设置窗口标志：保持最小化按钮
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowTitleHint |
            QtCore.Qt.WindowSystemMenuHint |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowCloseButtonHint
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        self.table_widget = QtWidgets.QTableWidget()
        self.table_widget.setColumnCount(9)
        self.table_widget.setHorizontalHeaderLabels([
            self.tr("标签"), self.tr("上"), "", self.tr("下"), "",
            self.tr("左"), "", self.tr("右"), ""
        ])
        self.table_widget.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        for i in range(1, 8, 2):
            self.table_widget.horizontalHeader().setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeToContents)
            self.table_widget.horizontalHeader().setSectionResizeMode(i + 1, QtWidgets.QHeaderView.ResizeToContents)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table_widget.viewport().installEventFilter(self)
        self.table_widget.setStyleSheet("""
            QTableWidget::item:hover {
                background-color: rgba(0, 120, 215, 0.2);
            }
        """)

        self.populate_table(labels)
        layout.addWidget(self.table_widget)

        range_group = QtWidgets.QGroupBox(self.tr("范围选择"))
        range_layout = QtWidgets.QHBoxLayout(range_group)
        range_layout.setContentsMargins(10, 10, 10, 10)
        range_layout.setSpacing(10)

        self.start_spinbox = QtWidgets.QSpinBox()
        self.start_spinbox.setPrefix(self.tr("从: "))
        self.end_spinbox = QtWidgets.QSpinBox()
        self.end_spinbox.setPrefix(self.tr("到: "))

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

        self.jump_spinbox = QtWidgets.QSpinBox()
        self.jump_spinbox.setPrefix(self.tr("跳转到: "))
        if total_files > 0:
            self.jump_spinbox.setRange(1, total_files)
        self.btn_jump = QtWidgets.QPushButton(self.tr("跳转"))
        self.btn_jump.setFixedSize(QtCore.QSize(80, 30))

        range_layout.addWidget(self.jump_spinbox)
        range_layout.addWidget(self.btn_jump)
        layout.addWidget(range_group)

        button_layout = QtWidgets.QHBoxLayout()
        self.btn_apply_current = QtWidgets.QPushButton(self.tr("只扩缩本页"))
        self.btn_apply_selected = QtWidgets.QPushButton(self.tr("只扩缩选中"))
        self.btn_apply_all = QtWidgets.QPushButton(self.tr("扩缩全部页码"))
        self.btn_clear_all = QtWidgets.QPushButton(self.tr("一键清零"))

        button_size = QtCore.QSize(100, 30)
        self.btn_apply_current.setFixedSize(button_size)
        self.btn_apply_selected.setFixedSize(button_size)
        self.btn_apply_all.setFixedSize(QtCore.QSize(110, 30))
        self.btn_clear_all.setFixedSize(button_size)
        self.btn_clear_all.setStyleSheet("QPushButton { background-color: #ffebcd; }")

        button_layout.addWidget(self.btn_apply_current)
        button_layout.addWidget(self.btn_apply_selected)
        button_layout.addWidget(self.btn_apply_all)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_clear_all)
        layout.addLayout(button_layout)

        self.btn_apply_current.clicked.connect(self.on_apply_current)
        self.btn_apply_selected.clicked.connect(self.on_apply_selected)
        self.btn_apply_all.clicked.connect(self.on_apply_all)
        self.btn_apply_range.clicked.connect(self.on_apply_range)
        self.btn_jump.clicked.connect(self.on_jump_to_image)
        self.btn_clear_all.clicked.connect(self.on_clear_all)







    def populate_table(self, labels):
        self.table_widget.setRowCount(len(labels))
        edges = ["Top", "Bottom", "Left", "Right"]
        edge_translations = {
            "Top": self.tr("上"), "Bottom": self.tr("下"),
            "Left": self.tr("左"), "Right": self.tr("右")
        }

        for i, label in enumerate(labels):
            label_item = QtWidgets.QTableWidgetItem(label)
            label_item.setFlags(label_item.flags() & ~QtCore.Qt.ItemIsEditable)
            label_item.setToolTip(self.tr("左键扩缩本页单个标签, 右键扩缩选中单个标签, 中键清零"))
            self._update_label_color(label_item, label)
            self.table_widget.setItem(i, 0, label_item)

            for j, edge in enumerate(edges):
                col_index = j * 2 + 1
                spinbox = QtWidgets.QDoubleSpinBox()
                spinbox.setRange(-1000, 1000)
                spinbox.setDecimals(1)
                spinbox.setSingleStep(1.0)
                spinbox.setValue(0.0)
                self.table_widget.setCellWidget(i, col_index, spinbox)

                translated_edge = edge_translations.get(edge, edge)
                apply_button = ClickableLabel(translated_edge)
                apply_button.setToolTip(
                    self.tr("左键: 应用到本页全部 '{label}' 标签的'{edge}'边\n右键: 应用到本页选中 '{label}' 标签的'{edge}'边").format(
                        label=label, edge=translated_edge
                    )
                )
                
                apply_button.leftClicked.connect(functools.partial(self.on_single_edge_apply, i, edge, "all"))
                apply_button.rightClicked.connect(functools.partial(self.on_single_edge_apply, i, edge, "selected"))
                
                container = QtWidgets.QWidget()
                container_layout = QtWidgets.QHBoxLayout(container)
                container_layout.setContentsMargins(0, 0, 0, 0)
                container_layout.addWidget(apply_button)
                container_layout.setAlignment(QtCore.Qt.AlignCenter)
                self.table_widget.setCellWidget(i, col_index + 1, container)

    def update_labels(self, labels):
        current_values = {}
        if self.table_widget.rowCount() > 0:
            current_values = self.get_margin_values()
        self.table_widget.setRowCount(0)
        self.populate_table(labels)
        self.restore_margin_values(current_values)

    def get_margin_values(self):
        margins = {}
        for i in range(self.table_widget.rowCount()):
            label = self.table_widget.item(i, 0).text()
            top = self.table_widget.cellWidget(i, 1).value()
            bottom = self.table_widget.cellWidget(i, 3).value()
            left = self.table_widget.cellWidget(i, 5).value()
            right = self.table_widget.cellWidget(i, 7).value()
            margins[label] = (top, bottom, left, right)
        return margins

    def restore_margin_values(self, saved_values):
        if not saved_values:
            return
        for i in range(self.table_widget.rowCount()):
            label = self.table_widget.item(i, 0).text()
            if label in saved_values:
                top, bottom, left, right = saved_values[label]
                self.table_widget.cellWidget(i, 1).setValue(top)
                self.table_widget.cellWidget(i, 3).setValue(bottom)
                self.table_widget.cellWidget(i, 5).setValue(left)
                self.table_widget.cellWidget(i, 7).setValue(right)

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
        margins = self.get_margin_values()
        start_index = self.start_spinbox.value() - 1
        end_index = self.end_spinbox.value() - 1
        if start_index > end_index:
            QtWidgets.QMessageBox.warning(
                self, self.tr("范围无效"), self.tr("起始位置不能大于结束位置。")
            )
            return
        self.apply_all_in_range.emit(margins, start_index, end_index)

    def on_clear_all(self):
        for i in range(self.table_widget.rowCount()):
            for j in range(1, 9, 2):
                spinbox = self.table_widget.cellWidget(i, j)
                if spinbox:
                    spinbox.setValue(0.0)

    def refresh_colors(self):
        if not self.parent() or not hasattr(self.parent(), 'unique_label_list'):
            return
        current_labels = []
        for i in range(self.parent().unique_label_list.count()):
            item = self.parent().unique_label_list.item(i)
            label_text = item.data(QtCore.Qt.UserRole)
            current_labels.append(label_text)
        existing_labels = []
        for i in range(self.table_widget.rowCount()):
            label_item = self.table_widget.item(i, 0)
            if label_item:
                existing_labels.append(label_item.text())
        if set(current_labels) != set(existing_labels):
            self.update_labels(current_labels)
        else:
            for i in range(self.table_widget.rowCount()):
                label_item = self.table_widget.item(i, 0)
                if label_item:
                    label = label_item.text()
                    self._update_label_color(label_item, label)

    def _update_label_color(self, label_item, label):
        label_exists_on_current_page = False
        if self.parent() and hasattr(self.parent(), 'canvas'):
            try:
                for shape in self.parent().canvas.shapes:
                    if shape.label == label:
                        label_exists_on_current_page = True
                        break
            except Exception:
                pass
        if not label_exists_on_current_page:
            label_item.setBackground(QtGui.QBrush())
            label_item.setForeground(QtGui.QBrush())
            return
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
        if self.parent() and hasattr(self.parent(), '_get_rgb_by_label'):
            try:
                rgb = self.parent()._get_rgb_by_label(label)
                color = QtGui.QColor(rgb[0], rgb[1], rgb[2], 128)
                label_item.setBackground(color)
                luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
                text_color = QtGui.QColor(0, 0, 0) if luminance > 0.5 else QtGui.QColor(255, 255, 255)
                label_item.setForeground(text_color)
                return
            except Exception:
                pass
        label_item.setBackground(QtGui.QBrush())
        label_item.setForeground(QtGui.QBrush())

    def eventFilter(self, source, event):
        if source is self.table_widget.viewport() and event.type() == QtCore.QEvent.MouseButtonPress:
            index = self.table_widget.indexAt(event.pos())
            if index.isValid() and index.column() == 0:
                if event.button() == QtCore.Qt.LeftButton:
                    self.on_apply_single_label(index.row())
                    return True
                elif event.button() == QtCore.Qt.RightButton:
                    self.on_apply_single_label_selected(index.row())
                    return True
                elif event.button() == QtCore.Qt.MidButton:
                    self.clear_row(index.row())
                    return True
        return super(ExpandMarginsDialog, self).eventFilter(source, event)

    def clear_row(self, row):
        for j in range(1, 9, 2):
            spinbox = self.table_widget.cellWidget(row, j)
            if spinbox:
                spinbox.setValue(0.0)

    def on_apply_single_label_selected(self, row):
        label = self.table_widget.item(row, 0).text()
        top = self.table_widget.cellWidget(row, 1).value()
        bottom = self.table_widget.cellWidget(row, 3).value()
        left = self.table_widget.cellWidget(row, 5).value()
        right = self.table_widget.cellWidget(row, 7).value()
        margins = {label: (top, bottom, left, right)}
        self.apply_single_label_selected.emit(margins)

    def on_apply_single_label(self, row):
        label = self.table_widget.item(row, 0).text()
        top = self.table_widget.cellWidget(row, 1).value()
        bottom = self.table_widget.cellWidget(row, 3).value()
        left = self.table_widget.cellWidget(row, 5).value()
        right = self.table_widget.cellWidget(row, 7).value()
        margins = {label: (top, bottom, left, right)}
        self.apply_single_label.emit(margins)

    def on_single_edge_apply(self, row, edge_name, scope):
        label = self.table_widget.item(row, 0).text()
        edges = ["Top", "Bottom", "Left", "Right"]
        try:
            edge_index = edges.index(edge_name)
            spinbox_col = edge_index * 2 + 1
            value = self.table_widget.cellWidget(row, spinbox_col).value()
        except (ValueError, AttributeError):
            return
        margins_tuple = [0.0, 0.0, 0.0, 0.0]
        margins_tuple[edge_index] = value
        margins = {label: tuple(margins_tuple)}
        if scope == "all":
            self.apply_single_label.emit(margins)
        elif scope == "selected":
            self.apply_single_label_selected.emit(margins)

    def on_jump_to_image(self):
        index = self.jump_spinbox.value() - 1
        self.jump_to_image.emit(index)

    def showEvent(self, event):
        super(ExpandMarginsDialog, self).showEvent(event)
        total_files = 0
        if self.parent() and hasattr(self.parent(), 'file_list_widget'):
            total_files = self.parent().file_list_widget.count()

        if self.start_spinbox.maximum() != total_files:
            if total_files > 0:
                self.start_spinbox.setRange(1, total_files)
                self.end_spinbox.setRange(1, total_files)
                self.jump_spinbox.setRange(1, total_files)
                self.start_spinbox.setValue(1)
                self.end_spinbox.setValue(total_files)
            else:
                self.start_spinbox.setRange(0, 0)
                self.end_spinbox.setRange(0, 0)
                self.jump_spinbox.setRange(0, 0)
        
        current_page = 0
        if self.parent() and hasattr(self.parent(), 'file_list_widget'):
            current_page = self.parent().file_list_widget.currentRow() + 1
        
        self.set_current_page(current_page)

    def refresh_state(self, labels, total_files, current_page):
        if total_files > 0:
            self.start_spinbox.setRange(1, total_files)
            self.end_spinbox.setRange(1, total_files)
            self.jump_spinbox.setRange(1, total_files)
            self.start_spinbox.setValue(1)
            self.end_spinbox.setValue(total_files)
            self.set_current_page(current_page)
        self.update_labels(labels)

    def set_current_page(self, page_number):
        if self.jump_spinbox.minimum() <= page_number <= self.jump_spinbox.maximum():
            self.jump_spinbox.setValue(page_number)

    def restore_window_position(self):
        settings = QtCore.QSettings()
        geometry = settings.value("expand_margins_dialog/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
            if self.isMinimized():
                self.showNormal()
        else:
            if self.parent():
                parent_geometry = self.parent().geometry()
                x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
                y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
                self.move(x, y)

    def save_window_position(self):
        settings = QtCore.QSettings()
        settings.setValue("expand_margins_dialog/geometry", self.saveGeometry())

    def closeEvent(self, event):
        self.save_window_position()
        super(ExpandMarginsDialog, self).closeEvent(event)

    def hideEvent(self, event):
        self.save_window_position()
        super(ExpandMarginsDialog, self).hideEvent(event)
