# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui
import functools

class ClickableLabel(QtWidgets.QLabel):
    """A QLabel that emits signals for left, right and middle clicks."""
    leftClicked = QtCore.pyqtSignal()
    rightClicked = QtCore.pyqtSignal()
    middleClicked = QtCore.pyqtSignal()
    ctrlLeftClicked = QtCore.pyqtSignal()  # 新增 Ctrl+左键信号

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
            if event.modifiers() & QtCore.Qt.ControlModifier:
                self.ctrlLeftClicked.emit()
            else:
                self.leftClicked.emit()
        elif event.button() == QtCore.Qt.RightButton:
            self.rightClicked.emit()
        elif event.button() == QtCore.Qt.MiddleButton:
            self.middleClicked.emit()
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
        self.resize(525, 470)

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
        self.table_widget.setColumnCount(10)  # 增加一列用于操作按钮
        self.table_widget.setHorizontalHeaderLabels([
            self.tr("标签"), self.tr("上"), "", self.tr("下"), "",
            self.tr("左"), "", self.tr("右"), "", self.tr("操作")
        ])
        self.table_widget.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        for i in range(1, 8, 2):
            self.table_widget.horizontalHeader().setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeToContents)
            self.table_widget.horizontalHeader().setSectionResizeMode(i + 1, QtWidgets.QHeaderView.ResizeToContents)
        self.table_widget.horizontalHeader().setSectionResizeMode(9, QtWidgets.QHeaderView.ResizeToContents)  # 操作列
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table_widget.viewport().installEventFilter(self)
        self.table_widget.setStyleSheet("""
            QTableWidget::item:hover {
                background-color: rgba(0, 120, 215, 0.2);
            }
        """)

        # 用于跟踪每个标签的行数
        self.label_row_counts = {}  # {label: row_count}
        self.label_order = []  # 保存标签顺序
        
        # 方向映射：{(row, col): actual_edge}，用于自定义按钮实际操作的方向
        self.edge_mapping = {}  # 例如 {(0, 2): "Bottom"} 表示第0行第2列的"上"按钮实际操作"下"

        # 先加载保存的行数和映射
        self.load_saved_data()

        self.populate_table(labels)
        
        # 加载保存的数值
        self.load_saved_margin_values()
        
        # 更新按钮显示（应用映射）
        self.update_edge_button_labels()
        
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
        self.jump_spinbox.setWrapping(True)  # 启用循环滚动：最大值+1回到最小值，最小值-1回到最大值
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
        # 保存标签顺序
        self.label_order = list(labels)
        
        # 初始化每个标签的行数为2（如果还没有记录）
        for label in labels:
            if label not in self.label_row_counts:
                self.label_row_counts[label] = 2
        
        # 计算总行数
        total_rows = sum(self.label_row_counts.get(label, 2) for label in labels)
        self.table_widget.setRowCount(total_rows)
        
        edges = ["Top", "Bottom", "Left", "Right"]
        edge_translations = {
            "Top": self.tr("上"), "Bottom": self.tr("下"),
            "Left": self.tr("左"), "Right": self.tr("右")
        }

        current_row = 0
        for label in labels:  # 按照传入的labels顺序遍历
            row_count = self.label_row_counts.get(label, 2)
            
            for row_offset in range(row_count):
                row = current_row + row_offset
                
                # 标签列
                label_item = QtWidgets.QTableWidgetItem(label)
                label_item.setFlags(label_item.flags() & ~QtCore.Qt.ItemIsEditable)
                label_item.setToolTip(self.tr("左键扩缩本页单个标签, 右键扩缩选中单个标签, 中键清零"))
                self._update_label_color(label_item, label)
                self.table_widget.setItem(row, 0, label_item)
                
                # 4个方向的spinbox和按钮
                for j, edge in enumerate(edges):
                    col_index = j * 2 + 1
                    translated_edge = edge_translations.get(edge, edge)
                    
                    # spinbox
                    spinbox = QtWidgets.QDoubleSpinBox()
                    spinbox.setRange(-1000, 1000)
                    spinbox.setDecimals(1)
                    spinbox.setSingleStep(1.0)
                    spinbox.setValue(0.0)
                    self.table_widget.setCellWidget(row, col_index, spinbox)

                    # 方向按钮
                    apply_button = ClickableLabel(translated_edge)
                    apply_button.setToolTip(
                        self.tr("左键: 应用到本页全部 '{label}' 标签的'{edge}'边\n右键: 应用到本页选中 '{label}' 标签的'{edge}'边\n中键: 清零\nCtrl+左键: 自定义此按钮操作的方向").format(
                            label=label, edge=translated_edge
                        )
                    )
                    apply_button.leftClicked.connect(functools.partial(self.on_single_edge_apply, row, edge, "all"))
                    apply_button.rightClicked.connect(functools.partial(self.on_single_edge_apply, row, edge, "selected"))
                    apply_button.middleClicked.connect(functools.partial(self.on_single_edge_clear, row, edge))
                    apply_button.ctrlLeftClicked.connect(functools.partial(self.on_customize_edge_mapping, row, col_index + 1, edge))
                    
                    container = QtWidgets.QWidget()
                    container_layout = QtWidgets.QHBoxLayout(container)
                    container_layout.setContentsMargins(0, 0, 0, 0)
                    container_layout.addWidget(apply_button)
                    container_layout.setAlignment(QtCore.Qt.AlignCenter)
                    self.table_widget.setCellWidget(row, col_index + 1, container)
                
                # 操作按钮列（第10列）
                btn_container = QtWidgets.QWidget()
                btn_layout = QtWidgets.QHBoxLayout(btn_container)
                btn_layout.setContentsMargins(2, 2, 2, 2)
                btn_layout.setSpacing(2)
                
                # 添加行按钮（+）
                btn_add = QtWidgets.QPushButton("+")
                btn_add.setFixedSize(20, 20)
                btn_add.setToolTip(self.tr("为此标签添加一行"))
                btn_add.clicked.connect(functools.partial(self.add_row_for_label, label))
                btn_layout.addWidget(btn_add)
                
                # 删除行按钮（-），只有当该标签行数>2时才显示
                if row_count > 2:
                    btn_remove = QtWidgets.QPushButton("-")
                    btn_remove.setFixedSize(20, 20)
                    btn_remove.setToolTip(self.tr("删除此行"))
                    btn_remove.clicked.connect(functools.partial(self.remove_row, row))
                    btn_layout.addWidget(btn_remove)
                
                self.table_widget.setCellWidget(row, 9, btn_container)
            
            current_row += row_count

    def add_row_for_label(self, label):
        """为指定标签添加一行"""
        self.label_row_counts[label] = self.label_row_counts.get(label, 2) + 1
        # 保存当前值
        current_values = self.get_margin_values_raw()
        # 重新生成表格（使用保存的标签顺序）
        self.populate_table(self.label_order)
        # 恢复值
        self.restore_margin_values(current_values)
    
    def remove_row(self, row):
        """删除指定行"""
        label = self.table_widget.item(row, 0).text()
        if self.label_row_counts.get(label, 2) <= 2:
            return  # 至少保留2行
        
        self.label_row_counts[label] -= 1
        # 保存当前值（删除指定行的值）
        current_values = self.get_margin_values_raw_with_row_removal(row)
        # 重新生成表格（使用保存的标签顺序）
        self.populate_table(self.label_order)
        # 恢复值
        self.restore_margin_values(current_values)
    
    def get_margin_values_raw_with_row_removal(self, row_to_remove):
        """获取边距值，但跳过要删除的行"""
        margins = {}
        current_row = 0
        
        for label in self.label_order:  # 使用保存的顺序
            row_count = self.label_row_counts.get(label, 2)
            values_list = []
            
            for row_offset in range(row_count):
                row = current_row + row_offset
                if row == row_to_remove:
                    continue  # 跳过要删除的行
                
                if row >= self.table_widget.rowCount():
                    break
                
                spinbox_top = self.table_widget.cellWidget(row, 1)
                spinbox_bottom = self.table_widget.cellWidget(row, 3)
                spinbox_left = self.table_widget.cellWidget(row, 5)
                spinbox_right = self.table_widget.cellWidget(row, 7)
                
                if spinbox_top and spinbox_bottom and spinbox_left and spinbox_right:
                    top = spinbox_top.value()
                    bottom = spinbox_bottom.value()
                    left = spinbox_left.value()
                    right = spinbox_right.value()
                    values_list.extend([top, bottom, left, right])
            
            if values_list:
                margins[label] = tuple(values_list)
            
            current_row += row_count
        
        return margins

    def update_labels(self, labels):
        current_values = {}
        if self.table_widget.rowCount() > 0:
            current_values = self.get_margin_values_raw()  # 使用原始值保存
        self.table_widget.setRowCount(0)
        self.populate_table(labels)
        self.restore_margin_values(current_values)

    def get_margin_values(self):
        """获取边距值，合并每个标签的所有行用于应用"""
        margins = {}
        current_row = 0
        
        for label in self.label_order:  # 使用保存的顺序
            row_count = self.label_row_counts.get(label, 2)
            top_sum = 0.0
            bottom_sum = 0.0
            left_sum = 0.0
            right_sum = 0.0
            
            for row_offset in range(row_count):
                row = current_row + row_offset
                if row >= self.table_widget.rowCount():
                    break
                
                spinbox_top = self.table_widget.cellWidget(row, 1)
                spinbox_bottom = self.table_widget.cellWidget(row, 3)
                spinbox_left = self.table_widget.cellWidget(row, 5)
                spinbox_right = self.table_widget.cellWidget(row, 7)
                
                if spinbox_top and spinbox_bottom and spinbox_left and spinbox_right:
                    top_sum += spinbox_top.value()
                    bottom_sum += spinbox_bottom.value()
                    left_sum += spinbox_left.value()
                    right_sum += spinbox_right.value()
            
            margins[label] = (top_sum, bottom_sum, left_sum, right_sum)
            current_row += row_count
        
        return margins

    def get_margin_values_raw(self):
        """获取边距值的原始值（每行4个值），用于保存和恢复"""
        margins = {}
        current_row = 0
        
        for label in self.label_order:  # 使用保存的顺序
            row_count = self.label_row_counts.get(label, 2)
            values_list = []
            
            for row_offset in range(row_count):
                row = current_row + row_offset
                if row >= self.table_widget.rowCount():
                    break
                
                spinbox_top = self.table_widget.cellWidget(row, 1)
                spinbox_bottom = self.table_widget.cellWidget(row, 3)
                spinbox_left = self.table_widget.cellWidget(row, 5)
                spinbox_right = self.table_widget.cellWidget(row, 7)
                
                if spinbox_top and spinbox_bottom and spinbox_left and spinbox_right:
                    top = spinbox_top.value()
                    bottom = spinbox_bottom.value()
                    left = spinbox_left.value()
                    right = spinbox_right.value()
                    values_list.extend([top, bottom, left, right])
            
            if values_list:
                margins[label] = tuple(values_list)
            
            current_row += row_count
        
        return margins

    def restore_margin_values(self, saved_values):
        """恢复边距值"""
        if not saved_values:
            return
        
        current_row = 0
        for label in self.label_order:  # 使用保存的顺序
            if label not in saved_values:
                current_row += self.label_row_counts.get(label, 2)
                continue
            
            values = saved_values[label]
            row_count = self.label_row_counts.get(label, 2)
            
            # 每行4个值
            for row_offset in range(row_count):
                row = current_row + row_offset
                if row >= self.table_widget.rowCount():
                    break
                
                value_offset = row_offset * 4
                
                if value_offset + 3 < len(values):
                    spinbox_top = self.table_widget.cellWidget(row, 1)
                    spinbox_bottom = self.table_widget.cellWidget(row, 3)
                    spinbox_left = self.table_widget.cellWidget(row, 5)
                    spinbox_right = self.table_widget.cellWidget(row, 7)
                    
                    if spinbox_top and spinbox_bottom and spinbox_left and spinbox_right:
                        spinbox_top.setValue(values[value_offset])
                        spinbox_bottom.setValue(values[value_offset + 1])
                        spinbox_left.setValue(values[value_offset + 2])
                        spinbox_right.setValue(values[value_offset + 3])
            
            current_row += row_count

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
        """清零所有行（包括两行）"""
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
        
        # 获取现有标签
        existing_labels = list(self.label_order) if hasattr(self, 'label_order') else []
        
        if set(current_labels) != set(existing_labels):
            self.update_labels(current_labels)
        else:
            # 更新所有行的颜色
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
        edges = ["Top", "Bottom", "Left", "Right"]
        
        # 获取这一行的所有数值，考虑映射
        margins_tuple = [0.0, 0.0, 0.0, 0.0]
        
        for edge_index, edge in enumerate(edges):
            spinbox_col = edge_index * 2 + 1
            button_col = edge_index * 2 + 2
            
            # 检查是否有自定义映射
            actual_edge = self.edge_mapping.get((row, button_col), edge)
            actual_edge_index = edges.index(actual_edge)
            
            # 读取输入框的值
            spinbox = self.table_widget.cellWidget(row, spinbox_col)
            if spinbox:
                value = spinbox.value()
                # 累加到映射后的方向（如果多个输入框映射到同一方向，会累加）
                margins_tuple[actual_edge_index] += value
        
        margins = {label: tuple(margins_tuple)}
        self.apply_single_label_selected.emit(margins)

    def on_apply_single_label(self, row):
        label = self.table_widget.item(row, 0).text()
        edges = ["Top", "Bottom", "Left", "Right"]
        
        # 获取这一行的所有数值，考虑映射
        margins_tuple = [0.0, 0.0, 0.0, 0.0]
        
        for edge_index, edge in enumerate(edges):
            spinbox_col = edge_index * 2 + 1
            button_col = edge_index * 2 + 2
            
            # 检查是否有自定义映射
            actual_edge = self.edge_mapping.get((row, button_col), edge)
            actual_edge_index = edges.index(actual_edge)
            
            # 读取输入框的值
            spinbox = self.table_widget.cellWidget(row, spinbox_col)
            if spinbox:
                value = spinbox.value()
                # 累加到映射后的方向（如果多个输入框映射到同一方向，会累加）
                margins_tuple[actual_edge_index] += value
        
        margins = {label: tuple(margins_tuple)}
        self.apply_single_label.emit(margins)

    def on_customize_edge_mapping(self, row, col, default_edge):
        """Ctrl+左键自定义按钮实际操作的方向"""
        menu = QtWidgets.QMenu(self)
        
        edges = ["Top", "Bottom", "Left", "Right"]
        edge_translations = {
            "Top": self.tr("上"), 
            "Bottom": self.tr("下"),
            "Left": self.tr("左"), 
            "Right": self.tr("右")
        }
        
        # 获取当前映射
        current_mapping = self.edge_mapping.get((row, col), default_edge)
        
        for edge in edges:
            action = menu.addAction(edge_translations[edge])
            action.setCheckable(True)
            if edge == current_mapping:
                action.setChecked(True)
            action.triggered.connect(functools.partial(self.set_edge_mapping, row, col, edge, default_edge))
        
        # 添加"恢复默认"选项
        menu.addSeparator()
        reset_action = menu.addAction(self.tr("恢复默认"))
        reset_action.triggered.connect(functools.partial(self.reset_edge_mapping, row, col, default_edge))
        
        # 在鼠标位置显示菜单
        menu.exec_(QtGui.QCursor.pos())
    
    def set_edge_mapping(self, row, col, new_edge, default_edge):
        """设置方向映射"""
        self.edge_mapping[(row, col)] = new_edge
        
        # 更新按钮显示文字
        container = self.table_widget.cellWidget(row, col)
        if container:
            label = container.findChild(ClickableLabel)
            if label:
                edge_translations = {
                    "Top": self.tr("上"), 
                    "Bottom": self.tr("下"),
                    "Left": self.tr("左"), 
                    "Right": self.tr("右")
                }
                # 如果不是默认映射，显示为"新"（只显示实际操作的方向）
                if new_edge != default_edge:
                    label.setText(edge_translations[new_edge])
                    # 修改背景色以区分自定义映射
                    label.setStyleSheet("""
                        QLabel {
                            background-color: #ffe4b5;
                            border: 1px solid #ffa500;
                            border-radius: 3px;
                            padding: 1px;
                        }
                        QLabel:hover {
                            background-color: #ffd700;
                            border: 1px solid #ff8c00;
                        }
                        QLabel:pressed {
                            background-color: #ffb90f;
                        }
                    """)
                else:
                    label.setText(edge_translations[default_edge])
                    # 恢复默认样式
                    label.setStyleSheet("""
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
        
        # 保存映射
        self.save_edge_mappings()
    
    def reset_edge_mapping(self, row, col, default_edge):
        """恢复默认映射"""
        if (row, col) in self.edge_mapping:
            del self.edge_mapping[(row, col)]
        
        # 更新按钮显示文字
        container = self.table_widget.cellWidget(row, col)
        if container:
            label = container.findChild(ClickableLabel)
            if label:
                edge_translations = {
                    "Top": self.tr("上"), 
                    "Bottom": self.tr("下"),
                    "Left": self.tr("左"), 
                    "Right": self.tr("右")
                }
                label.setText(edge_translations[default_edge])
                # 恢复默认样式
                label.setStyleSheet("""
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
        
        # 保存映射
        self.save_edge_mappings()

    def on_single_edge_apply(self, row, edge_name, scope):
        label = self.table_widget.item(row, 0).text()
        edges = ["Top", "Bottom", "Left", "Right"]
        try:
            # edge_name 是按钮的默认方向（例如"上"按钮的edge_name是"Top"）
            edge_index = edges.index(edge_name)
            button_col = edge_index * 2 + 2  # 按钮所在列
            spinbox_col = edge_index * 2 + 1  # 按钮左边的输入框列
            
            # 检查是否有自定义映射
            actual_edge = self.edge_mapping.get((row, button_col), edge_name)
            actual_edge_index = edges.index(actual_edge)
            
            # 读取按钮左边输入框的值
            value = self.table_widget.cellWidget(row, spinbox_col).value()
        except (ValueError, AttributeError):
            return
        
        # 应用到映射后的方向
        margins_tuple = [0.0, 0.0, 0.0, 0.0]
        margins_tuple[actual_edge_index] = value
        margins = {label: tuple(margins_tuple)}
        
        if scope == "all":
            self.apply_single_label.emit(margins)
        elif scope == "selected":
            self.apply_single_label_selected.emit(margins)

    def on_single_edge_clear(self, row, edge_name):
        """中键清零：将指定行的指定边距值设为0"""
        edges = ["Top", "Bottom", "Left", "Right"]
        try:
            edge_index = edges.index(edge_name)
            spinbox_col = edge_index * 2 + 1
            spinbox = self.table_widget.cellWidget(row, spinbox_col)
            if spinbox:
                spinbox.setValue(0.0)
        except (ValueError, AttributeError):
            pass

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
        # 同时更新"从"的值，让范围起点跟随当前页码
        if self.start_spinbox.minimum() <= page_number <= self.start_spinbox.maximum():
            self.start_spinbox.setValue(page_number)

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
        
        # 保存数值和行数到用户配置文件
        self.save_current_values()
    
    def save_current_values(self):
        """保存当前的数值和行数到用户配置文件"""
        if not self.parent() or not hasattr(self.parent(), '_config'):
            return
        
        # 保存行数
        self.parent()._config["expand_margins_label_row_counts"] = dict(self.label_row_counts)
        
        # 保存数值
        margin_values = {}
        current_row = 0
        
        for label in self.label_order:  # 使用保存的顺序
            row_count = self.label_row_counts.get(label, 2)
            values_list = []
            
            for row_offset in range(row_count):
                row = current_row + row_offset
                if row >= self.table_widget.rowCount():
                    break
                
                spinbox_top = self.table_widget.cellWidget(row, 1)
                spinbox_bottom = self.table_widget.cellWidget(row, 3)
                spinbox_left = self.table_widget.cellWidget(row, 5)
                spinbox_right = self.table_widget.cellWidget(row, 7)
                
                if spinbox_top and spinbox_bottom and spinbox_left and spinbox_right:
                    top = float(spinbox_top.value())
                    bottom = float(spinbox_bottom.value())
                    left = float(spinbox_left.value())
                    right = float(spinbox_right.value())
                    values_list.extend([top, bottom, left, right])
            
            if values_list:
                margin_values[label] = values_list  # 保存为list而不是tuple，因为JSON不支持tuple
            
            current_row += row_count
        
        self.parent()._config["expand_margins_values"] = margin_values
        
        # 保存到文件
        from anylabeling.config import save_config
        save_config(self.parent()._config)
    
    def save_edge_mappings(self):
        """保存方向映射到配置"""
        if not self.parent() or not hasattr(self.parent(), '_config'):
            return
        
        # 将映射转换为可序列化的格式
        mappings_serializable = {f"{row},{col}": edge for (row, col), edge in self.edge_mapping.items()}
        self.parent()._config["expand_margins_edge_mappings"] = mappings_serializable
        
        from anylabeling.config import save_config
        save_config(self.parent()._config)
    
    def update_edge_button_labels(self):
        """更新所有方向按钮的显示文字"""
        edge_translations = {
            "Top": self.tr("上"), 
            "Bottom": self.tr("下"),
            "Left": self.tr("左"), 
            "Right": self.tr("右")
        }
        edges = ["Top", "Bottom", "Left", "Right"]
        
        for (row, col), mapped_edge in self.edge_mapping.items():
            container = self.table_widget.cellWidget(row, col)
            if container:
                label = container.findChild(ClickableLabel)
                if label:
                    # 根据列号推断默认方向
                    if col == 2:  # 上
                        default_edge = "Top"
                    elif col == 4:  # 下
                        default_edge = "Bottom"
                    elif col == 6:  # 左
                        default_edge = "Left"
                    elif col == 8:  # 右
                        default_edge = "Right"
                    else:
                        continue
                    
                    if mapped_edge != default_edge:
                        # 只显示实际操作的方向，用橙色背景区分
                        label.setText(edge_translations[mapped_edge])
                        label.setStyleSheet("""
                            QLabel {
                                background-color: #ffe4b5;
                                border: 1px solid #ffa500;
                                border-radius: 3px;
                                padding: 1px;
                            }
                            QLabel:hover {
                                background-color: #ffd700;
                                border: 1px solid #ff8c00;
                            }
                            QLabel:pressed {
                                background-color: #ffb90f;
                            }
                        """)
                    else:
                        label.setText(edge_translations[default_edge])
                        label.setStyleSheet("""
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

    def load_saved_data(self):
        """从用户配置文件加载保存的行数和映射"""
        if not self.parent() or not hasattr(self.parent(), '_config'):
            return
        
        # 加载行数
        saved_row_counts = self.parent()._config.get("expand_margins_label_row_counts", {})
        if saved_row_counts and isinstance(saved_row_counts, dict):
            # 只恢复当前存在的标签的行数
            for label in saved_row_counts.keys():
                if isinstance(saved_row_counts[label], int) and saved_row_counts[label] >= 2:
                    self.label_row_counts[label] = saved_row_counts[label]
        
        # 加载方向映射（但不更新按钮，因为按钮还没创建）
        mappings_serializable = self.parent()._config.get("expand_margins_edge_mappings", {})
        if mappings_serializable and isinstance(mappings_serializable, dict):
            # 转换回原格式
            self.edge_mapping = {}
            for key, edge in mappings_serializable.items():
                try:
                    row, col = map(int, key.split(','))
                    self.edge_mapping[(row, col)] = edge
                except (ValueError, AttributeError):
                    pass
    
    def load_saved_margin_values(self):
        """从用户配置文件加载保存的数值"""
        if not self.parent() or not hasattr(self.parent(), '_config'):
            return
        
        # 加载数值
        saved_values = self.parent()._config.get("expand_margins_values", {})
        if not saved_values or not isinstance(saved_values, dict):
            return
        
        current_row = 0
        for label in self.label_order:  # 使用保存的顺序
            if label not in saved_values:
                current_row += self.label_row_counts.get(label, 2)
                continue
            
            values = saved_values[label]
            if not isinstance(values, (list, tuple)):
                current_row += self.label_row_counts.get(label, 2)
                continue
            
            row_count = self.label_row_counts.get(label, 2)
            
            # 每行4个值
            for row_offset in range(row_count):
                row = current_row + row_offset
                if row >= self.table_widget.rowCount():
                    break
                
                value_offset = row_offset * 4
                
                if value_offset + 3 < len(values):
                    spinbox_top = self.table_widget.cellWidget(row, 1)
                    spinbox_bottom = self.table_widget.cellWidget(row, 3)
                    spinbox_left = self.table_widget.cellWidget(row, 5)
                    spinbox_right = self.table_widget.cellWidget(row, 7)
                    
                    if spinbox_top and spinbox_bottom and spinbox_left and spinbox_right:
                        try:
                            spinbox_top.setValue(float(values[value_offset]))
                            spinbox_bottom.setValue(float(values[value_offset + 1]))
                            spinbox_left.setValue(float(values[value_offset + 2]))
                            spinbox_right.setValue(float(values[value_offset + 3]))
                        except (ValueError, TypeError):
                            pass
            
            current_row += row_count

    def closeEvent(self, event):
        self.save_window_position()
        super(ExpandMarginsDialog, self).closeEvent(event)

    def hideEvent(self, event):
        self.save_window_position()
        super(ExpandMarginsDialog, self).hideEvent(event)
