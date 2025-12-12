"""
标签同步对话框
用于将当前页面的标签同步到其他页面
"""

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt


class LabelSyncDialog(QtWidgets.QDialog):
    """标签同步对话框（非阻塞式）"""

    # 信号
    sync_requested = QtCore.pyqtSignal(list, int, int, bool, bool)
    selection_changed = QtCore.pyqtSignal(list)  # 选择变化信号，同步到画布
    align_requested = QtCore.pyqtSignal(object, str, int, int, bool, list)  # shape, align_type, start, end, skip_current, target_labels

    def __init__(self, parent=None):
        """初始化标签同步对话框"""
        super(LabelSyncDialog, self).__init__(parent)
        self.main_window = parent
        self.total_pages = 1
        self.current_page = 0
        self.config = parent._config if parent and hasattr(parent, '_config') else {}
        
        self.init_ui()
        
        # 设置为非阻塞式窗口
        self.setWindowFlags(
            QtCore.Qt.Window | 
            QtCore.Qt.WindowCloseButtonHint |
            QtCore.Qt.WindowMinimizeButtonHint
        )
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle(self.tr("标签同步工具"))
        self.setMinimumWidth(320)
        self.setMinimumHeight(500)
        self.resize(320, 520)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # === 标签选择区域 ===
        label_group = QtWidgets.QGroupBox(self.tr("选择要同步的标签"))
        label_layout = QtWidgets.QVBoxLayout()

        # 按钮
        button_layout = QtWidgets.QHBoxLayout()
        select_all_btn = QtWidgets.QPushButton(self.tr("全选"))
        deselect_all_btn = QtWidgets.QPushButton(self.tr("取消全选"))
        select_all_btn.setFixedWidth(80)
        deselect_all_btn.setFixedWidth(80)
        select_all_btn.clicked.connect(self.select_all_labels)
        deselect_all_btn.clicked.connect(self.deselect_all_labels)
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        label_layout.addLayout(button_layout)

        # 对象列表（和标签页管理器一样）
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.setMinimumHeight(150)
        
        # 应用红绿灯delegate
        from .object_manager_dialog import TrafficLightDelegate
        self.traffic_light_delegate = TrafficLightDelegate(self, self.config)
        self.list_widget.setItemDelegate(self.traffic_light_delegate)
        
        # 连接选择变化信号
        self.list_widget.itemSelectionChanged.connect(self._on_internal_selection_changed)
        
        label_layout.addWidget(self.list_widget)
        label_group.setLayout(label_layout)
        main_layout.addWidget(label_group)

        # === 页面范围选择区域 ===
        range_group = QtWidgets.QGroupBox(self.tr("选择目标页面范围"))
        range_layout = QtWidgets.QVBoxLayout()

        self.range_all_radio = QtWidgets.QRadioButton(self.tr("所有页面"))
        self.range_custom_radio = QtWidgets.QRadioButton(self.tr("自定义范围"))
        self.range_all_radio.setChecked(True)
        range_layout.addWidget(self.range_all_radio)
        range_layout.addWidget(self.range_custom_radio)

        custom_range_layout = QtWidgets.QHBoxLayout()
        custom_range_layout.setContentsMargins(25, 5, 0, 5)
        self.start_page_spin = QtWidgets.QSpinBox()
        self.start_page_spin.setMinimum(1)
        self.start_page_spin.setEnabled(False)
        self.end_page_spin = QtWidgets.QSpinBox()
        self.end_page_spin.setMinimum(1)
        self.end_page_spin.setEnabled(False)
        custom_range_layout.addWidget(QtWidgets.QLabel(self.tr("从第")))
        custom_range_layout.addWidget(self.start_page_spin)
        custom_range_layout.addWidget(QtWidgets.QLabel(self.tr("页 到第")))
        custom_range_layout.addWidget(self.end_page_spin)
        custom_range_layout.addWidget(QtWidgets.QLabel(self.tr("页")))
        custom_range_layout.addStretch()
        range_layout.addLayout(custom_range_layout)

        self.range_custom_radio.toggled.connect(self.on_range_mode_changed)

        self.skip_current_checkbox = QtWidgets.QCheckBox(self.tr("跳过当前页面"))
        self.skip_current_checkbox.setChecked(True)
        self.skip_current_checkbox.setStyleSheet("margin-top: 8px;")
        range_layout.addWidget(self.skip_current_checkbox)

        range_group.setLayout(range_layout)
        main_layout.addWidget(range_group)

        # === 同步选项 ===
        options_group = QtWidgets.QGroupBox(self.tr("同步选项"))
        options_layout = QtWidgets.QVBoxLayout()
        self.merge_mode_radio = QtWidgets.QRadioButton(
            self.tr("合并模式：保留原有标签，添加选中的标签")
        )
        self.replace_mode_radio = QtWidgets.QRadioButton(
            self.tr("替换模式：删除所有标签，仅保留选中的标签")
        )
        self.merge_mode_radio.setChecked(True)
        options_layout.addWidget(self.merge_mode_radio)
        options_layout.addWidget(self.replace_mode_radio)
        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)

        # === 同步对齐功能 ===
        align_group = QtWidgets.QGroupBox(self.tr("同步对齐（选中单个标签作为参照）"))
        align_layout = QtWidgets.QVBoxLayout()
        
        # 指定标签输入框
        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(QtWidgets.QLabel(self.tr("指定标签：")))
        self.align_label_edit = QtWidgets.QLineEdit()
        self.align_label_edit.setPlaceholderText(self.tr("留空=仅参照标签，逗号分隔多个"))
        self.align_label_edit.setToolTip(self.tr("输入要对齐的标签名（逗号分隔），留空则只对齐与参照标签相同的标签"))
        # 从配置读取上次的值
        self.align_label_edit.setText(self.config.get("label_sync_align_labels", ""))
        self.align_label_edit.textChanged.connect(self._save_align_labels)
        filter_layout.addWidget(self.align_label_edit)
        align_layout.addLayout(filter_layout)
        
        # 对齐按钮
        btn_layout = QtWidgets.QHBoxLayout()
        self.align_top_btn = QtWidgets.QPushButton(self.tr("上对齐"))
        self.align_left_btn = QtWidgets.QPushButton(self.tr("左对齐"))
        self.align_top_btn.clicked.connect(lambda: self.on_align_clicked("top"))
        self.align_left_btn.clicked.connect(lambda: self.on_align_clicked("left"))
        
        btn_layout.addWidget(self.align_top_btn)
        btn_layout.addWidget(self.align_left_btn)
        btn_layout.addStretch()
        align_layout.addLayout(btn_layout)
        
        align_group.setLayout(align_layout)
        main_layout.addWidget(align_group)

        # === 底部按钮 ===
        button_layout = QtWidgets.QHBoxLayout()
        
        self.sync_button = QtWidgets.QPushButton(self.tr("开始同步"))
        self.sync_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 6px 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.sync_button.clicked.connect(self.on_sync_clicked)
        
        close_button = QtWidgets.QPushButton(self.tr("关闭"))
        close_button.setStyleSheet("padding: 6px 16px;")
        close_button.clicked.connect(self.close)
        
        button_layout.addWidget(self.sync_button)
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def update_items(self, items, total_pages, current_page, initial_selection=None):
        """更新对话框数据"""
        is_first_open = initial_selection is not None
        old_total_pages = self.total_pages
        
        self.total_pages = total_pages
        self.current_page = current_page
        
        # 保存当前选中的shapes
        if initial_selection is not None:
            selected_shapes = initial_selection
        else:
            selected_shapes = [item.data(Qt.UserRole) for item in self.list_widget.selectedItems()]
        
        # 清空并重新填充列表
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        
        for item in items:
            new_item = QtWidgets.QListWidgetItem(item.text())
            new_item.setBackground(item.background())
            new_item.setData(Qt.UserRole, item.shape())
            new_item.setFlags(item.flags() | Qt.ItemIsSelectable)
            self.list_widget.addItem(new_item)
        
        # 恢复选中状态
        self.sync_selection(selected_shapes)
        
        self.list_widget.blockSignals(False)
        
        # 更新UI
        self.range_all_radio.setText(self.tr(f"所有页面 (1-{self.total_pages})"))
        self.start_page_spin.setMaximum(self.total_pages)
        self.end_page_spin.setMaximum(self.total_pages)
        
        # 动态更新：起始页跟随当前页，结束页始终是最后一页
        self.start_page_spin.setValue(self.current_page + 1)
        self.end_page_spin.setValue(self.total_pages)
        
        self.skip_current_checkbox.setText(
            self.tr(f"跳过当前页面（第 {self.current_page + 1} 页）")
        )

    def sync_selection(self, shapes_to_select):
        """从画布同步选择状态到列表"""
        self.list_widget.blockSignals(True)
        self.list_widget.clearSelection()
        if shapes_to_select:
            for shape in shapes_to_select:
                for i in range(self.list_widget.count()):
                    item = self.list_widget.item(i)
                    if item.data(Qt.UserRole) == shape:
                        item.setSelected(True)
                        break
        self.list_widget.blockSignals(False)

    def _on_internal_selection_changed(self):
        """列表选择变化时，同步到画布"""
        selected_shapes = [item.data(Qt.UserRole) for item in self.list_widget.selectedItems()]
        self.selection_changed.emit(selected_shapes)

    def on_range_mode_changed(self, checked):
        self.start_page_spin.setEnabled(checked)
        self.end_page_spin.setEnabled(checked)

    def select_all_labels(self):
        self.list_widget.selectAll()

    def deselect_all_labels(self):
        self.list_widget.clearSelection()

    def get_selected_shapes(self):
        return [item.data(Qt.UserRole) for item in self.list_widget.selectedItems()]

    def get_page_range(self):
        if self.range_all_radio.isChecked():
            return (0, self.total_pages - 1)
        else:
            return (self.start_page_spin.value() - 1, self.end_page_spin.value() - 1)

    def should_skip_current_page(self):
        return self.skip_current_checkbox.isChecked()

    def is_merge_mode(self):
        return self.merge_mode_radio.isChecked()

    def on_sync_clicked(self):
        selected_shapes = self.get_selected_shapes()
        
        if not selected_shapes:
            QtWidgets.QMessageBox.warning(self, self.tr("警告"), self.tr("请至少选择一个标签进行同步！"))
            return

        start_page, end_page = self.get_page_range()
        if start_page > end_page:
            QtWidgets.QMessageBox.warning(self, self.tr("警告"), self.tr("起始页面不能大于结束页面！"))
            return

        selected_labels = list(set([s.label for s in selected_shapes]))
        mode_text = self.tr("合并模式") if self.is_merge_mode() else self.tr("替换模式")
        skip_text = self.tr("（跳过当前页）") if self.should_skip_current_page() else ""
        
        message = self.tr(
            f"确认要同步以下标签吗？\n\n"
            f"选中：{len(selected_shapes)} 个标签对象\n"
            f"类型：{', '.join(selected_labels)}\n"
            f"范围：第 {start_page + 1} 页 到第 {end_page + 1} 页 {skip_text}\n"
            f"模式：{mode_text}\n\n"
            f"此操作将影响 {end_page - start_page + 1} 个页面"
        )
        
        reply = QtWidgets.QMessageBox.question(
            self, self.tr("确认同步"), message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.sync_requested.emit(
                selected_shapes, start_page, end_page,
                self.should_skip_current_page(), self.is_merge_mode()
            )

    def on_align_clicked(self, align_type):
        """对齐按钮点击处理"""
        selected_shapes = self.get_selected_shapes()
        
        if len(selected_shapes) != 1:
            QtWidgets.QMessageBox.warning(
                self, self.tr("警告"), 
                self.tr("请选择单个标签作为对齐参照！")
            )
            return

        reference_shape = selected_shapes[0]
        start_page, end_page = self.get_page_range()
        
        if start_page > end_page:
            QtWidgets.QMessageBox.warning(self, self.tr("警告"), self.tr("起始页面不能大于结束页面！"))
            return

        align_text = self.tr("上对齐") if align_type == "top" else self.tr("左对齐")
        skip_text = self.tr("（跳过当前页）") if self.should_skip_current_page() else ""
        
        # 获取指定标签列表
        label_text = self.align_label_edit.text().strip()
        if label_text:
            target_labels = [l.strip() for l in label_text.split(',') if l.strip()]
        else:
            target_labels = [reference_shape.label]  # 留空则只对齐参照标签
        
        filter_text = ', '.join(target_labels)
        
        message = self.tr(
            f"确认要执行{align_text}吗？\n\n"
            f"参照标签：{reference_shape.label}\n"
            f"目标标签：{filter_text}\n"
            f"范围：第 {start_page + 1} 页 到第 {end_page + 1} 页 {skip_text}\n\n"
            f"目标页面的指定标签将对齐到参照标签的{'上边Y坐标' if align_type == 'top' else '左边X坐标'}"
        )
        
        reply = QtWidgets.QMessageBox.question(
            self, self.tr("确认对齐"), message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.align_requested.emit(
                reference_shape, align_type, start_page, end_page,
                self.should_skip_current_page(), target_labels
            )

    def _save_align_labels(self, text):
        """保存指定标签到配置"""
        if self.config is not None:
            self.config["label_sync_align_labels"] = text
