from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
from anylabeling.config import save_config


class ShortcutLineEdit(QtWidgets.QLineEdit):
    """Custom line edit for capturing keyboard shortcuts."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("点击后按下快捷键...")
        self.setReadOnly(True)
        
    def keyPressEvent(self, event):
        """Capture key press and convert to shortcut string."""
        key = event.key()
        
        # Ignore modifier keys alone
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return
        
        # Build shortcut string
        modifiers = event.modifiers()
        key_text = []
        
        if modifiers & Qt.ControlModifier:
            key_text.append("Ctrl")
        if modifiers & Qt.AltModifier:
            key_text.append("Alt")
        if modifiers & Qt.ShiftModifier:
            key_text.append("Shift")
        if modifiers & Qt.MetaModifier:
            key_text.append("Meta")
        
        # Get key name
        key_name = QtGui.QKeySequence(key).toString()
        if key_name:
            key_text.append(key_name)
        
        if key_text:
            self.setText("+".join(key_text))
    
    def mousePressEvent(self, event):
        """Clear on click to allow re-recording."""
        if event.button() == Qt.LeftButton:
            self.clear()
        super().mousePressEvent(event)


class ShortcutManagerDialog(QtWidgets.QDialog):
    """Dialog for managing all application shortcuts."""

    shortcuts_saved = QtCore.pyqtSignal()  # Emitted when shortcuts are saved
    
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.parent = parent
        self._config = config if config is not None else {}
        self.shortcuts = self._config.get("shortcuts", {})
        
        self.setWindowTitle(self.tr("快捷键管理器"))
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowContextHelpButtonHint
            | Qt.WindowMinMaxButtonsHint
        )
        self.setMinimumSize(1000, 600)  # 增加宽度以容纳两列布局
        
        # Store line edits for each shortcut
        self.shortcut_edits = {}
        
        # Shortcut categories and descriptions
        self.shortcut_categories = {
            self.tr("文件操作"): [
                ("open", self.tr("打开文件")),
                ("open_dir", self.tr("打开文件夹")),
                ("open_video", self.tr("打开视频")),
                ("open_next", self.tr("下一张图片")),
                ("open_prev", self.tr("上一张图片")),
                ("save", self.tr("保存")),
                ("save_as", self.tr("另存为")),
                ("close", self.tr("关闭")),
                ("quit", self.tr("退出")),
                ("delete_file", self.tr("删除文件")),
                ("delete_image_file", self.tr("删除图片文件")),
            ],
            self.tr("绘制工具"): [
                ("create_polygon", self.tr("创建多边形")),
                ("create_rectangle", self.tr("创建矩形")),
                ("create_rotation", self.tr("创建旋转矩形")),
                ("create_rotation3", self.tr("创建旋转矩形3")),
                ("create_circle", self.tr("创建圆形")),
                ("create_line", self.tr("创建线段")),
                ("create_linestrip", self.tr("创建线条")),
                ("create_point", self.tr("创建点")),
            ],
            self.tr("编辑操作"): [
                ("edit_label", self.tr("编辑标签")),
                ("edit_polygon", self.tr("编辑多边形")),
                ("copy_polygon", self.tr("复制标注")),
                ("paste_polygon", self.tr("粘贴标注")),
                ("cancel_paste_preview", self.tr("取消粘贴预览")),
                ("delete_polygon", self.tr("删除标注")),
                ("undo", self.tr("撤销")),
                ("undo_last_point", self.tr("撤销最后一个点")),
                ("remove_selected_point", self.tr("删除选中的点")),
                ("add_point_to_edge", self.tr("在边上添加点")),
            ],
            self.tr("选择操作"): [
                ("select_all_shapes", self.tr("选择所有标注")),
                ("deselect_all_shapes", self.tr("取消选择所有标注")),
                ("invert_selection_shapes", self.tr("反选标注")),
                ("select_all_labels", self.tr("选择所有标签")),
                ("deselect_all_labels", self.tr("取消选择所有标签")),
                ("invert_selection_labels", self.tr("反选标签")),
            ],
            self.tr("显示控制"): [
                ("show_labels", self.tr("显示标签")),
                ("show_texts", self.tr("显示文本")),
                ("show_linking", self.tr("显示链接")),
                ("show_attributes", self.tr("显示属性")),
                ("show_order", self.tr("显示顺序")),
                ("show_wh", self.tr("显示宽高")),
                ("show_overview", self.tr("显示统计总览")),
                ("show_navigator", self.tr("显示导航器")),
                ("toggle_visibility_shapes", self.tr("切换标注可见性")),
                ("hide_selected_polygons", self.tr("隐藏选中的标注")),
                ("show_hidden_polygons", self.tr("显示隐藏的标注")),
                ("toggle_highlight", self.tr("切换高亮")),
                ("toggle_overlap", self.tr("切换重叠显示")),
                ("toggle_crosshair", self.tr("切换十字线")),
                ("toggle_degrees", self.tr("切换角度显示")),
                ("toggle_magnifier", self.tr("切换放大镜")),
                ("toggle_magnifier_auto_detect", self.tr("切换自动探测放大镜")),
            ],
            self.tr("视图控制"): [
                ("fit_window", self.tr("适应窗口")),
                ("fit_width", self.tr("适应宽度")),
                ("zoom_in", self.tr("放大")),
                ("zoom_out", self.tr("缩小")),
                ("zoom_to_original", self.tr("原始大小")),
            ],
            self.tr("工具功能"): [
                ("auto_label", self.tr("自动标注")),
                ("auto_run", self.tr("自动运行")),
                ("expand_margins", self.tr("标注框边距扩展工具")),
                ("tag_sort_tool", self.tr("标签排序工具")),
                ("angle_correction_tool", self.tr("旋转框角度修正工具")),
                ("alignment_tool", self.tr("矩形对齐工具")),
                ("segmentation_tool", self.tr("矩形分割工具")),
                ("merge_tool", self.tr("区域合并工具")),
                ("dual_color_tool", self.tr("双色标签工具")),
                ("mask_generator_tool", self.tr("掩膜生成")),
                ("traffic_light_tool", self.tr("红绿灯窗口")),
                ("rectangle_scale_tool", self.tr("矩形缩放工具")),
                ("page_text_tool", self.tr("页文本工具")),
                ("highlight_settings_tool", self.tr("高亮设置")),
                ("label_manager", self.tr("标签管理器")),
                ("object_manager", self.tr("标签页管理器")),
                ("edit_group_id", self.tr("群组编号管理器")),
                ("edit_digit_shortcut", self.tr("数字快捷键管理器")),
                ("label_toggle_shortcut_manager", self.tr("标签切换快捷键管理器")),
                ("keymap_dialog", self.tr("旋转标签快捷键管理器")),
                ("color_manager_tool", self.tr("颜色管理工具")),
                ("smart_guides_tool", self.tr("辅助线工具")),
                ("shortcut_manager_tool", self.tr("快捷键管理器")),
                ("wheel_settings_tool", self.tr("鼠标滚轮设置")),
                ("toggle_ghost_paste", self.tr("切换虚影粘贴模式")),
            ],
            self.tr("其他操作"): [
                ("loop_thru_labels", self.tr("循环标签")),
                ("toggle_keep_prev_mode", self.tr("切换保持上一个模式")),
                ("toggle_auto_use_last_label", self.tr("切换自动使用最后标签")),
                ("group_selected_shapes", self.tr("组合选中的标注")),
                ("ungroup_selected_shapes", self.tr("取消组合选中的标注")),
                ("union_selected_shapes", self.tr("合并选中的标注")),
            ],
        }
        
        self.init_ui()
        self.load_shortcuts()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QtWidgets.QVBoxLayout(self)
        
        # Search bar
        search_layout = QtWidgets.QHBoxLayout()
        search_label = QtWidgets.QLabel(self.tr("搜索:"))
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText(self.tr("输入功能名称或快捷键..."))
        self.search_edit.textChanged.connect(self.filter_shortcuts)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)
        
        # Scroll area for shortcuts
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
        
        # 存储每个快捷键项目的widget，用于过滤
        self.shortcut_items = {}  # key -> (container_widget, desc_label)
        
        # Create shortcut groups with two-column layout
        for category, shortcuts in self.shortcut_categories.items():
            group_box = QtWidgets.QGroupBox(category)
            group_layout = QtWidgets.QGridLayout()

            # 设置列宽：标签列固定宽度，快捷键列可伸缩
            group_layout.setColumnMinimumWidth(0, 120)  # 左侧标签列
            group_layout.setColumnMinimumWidth(1, 150)  # 左侧快捷键列
            group_layout.setColumnMinimumWidth(3, 120)  # 右侧标签列
            group_layout.setColumnMinimumWidth(4, 150)  # 右侧快捷键列
            group_layout.setColumnStretch(1, 1)
            group_layout.setColumnStretch(4, 1)
            group_layout.setHorizontalSpacing(10)
            group_layout.setVerticalSpacing(5)

            # 两列布局 - 每个项目用一个容器widget包装
            for idx, (key, description) in enumerate(shortcuts):
                # 计算行列位置
                row = idx // 2
                col_offset = (idx % 2) * 3  # 0 或 3

                # 创建容器widget来包装每个项目的3个控件
                item_container = QtWidgets.QWidget()
                item_layout = QtWidgets.QHBoxLayout(item_container)
                item_layout.setContentsMargins(0, 0, 0, 0)
                item_layout.setSpacing(5)

                # Description label
                desc_label = QtWidgets.QLabel(description)
                desc_label.setMinimumWidth(100)
                item_layout.addWidget(desc_label)

                # Shortcut edit
                shortcut_edit = ShortcutLineEdit()
                shortcut_edit.setMinimumWidth(120)
                shortcut_edit.textChanged.connect(
                    lambda text, k=key: self.on_shortcut_changed(k, text)
                )
                self.shortcut_edits[key] = shortcut_edit
                item_layout.addWidget(shortcut_edit)

                # Clear button
                clear_btn = QtWidgets.QPushButton(self.tr("清除"))
                clear_btn.setMaximumWidth(60)
                clear_btn.clicked.connect(lambda checked, edit=shortcut_edit: edit.clear())
                item_layout.addWidget(clear_btn)

                # 添加到grid布局
                group_layout.addWidget(item_container, row, col_offset, 1, 3)
                
                # 存储引用用于过滤
                self.shortcut_items[key] = (item_container, description)

            group_box.setLayout(group_layout)
            self.scroll_layout.addWidget(group_box)

            # Store group box for filtering
            group_box.setProperty("shortcut_keys", [key for key, _ in shortcuts])
        
        self.scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        reset_btn = QtWidgets.QPushButton(self.tr("恢复默认"))
        reset_btn.clicked.connect(self.reset_to_defaults)
        
        save_btn = QtWidgets.QPushButton(self.tr("保存"))
        save_btn.clicked.connect(self.save_shortcuts)
        
        close_btn = QtWidgets.QPushButton(self.tr("关闭"))
        close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(reset_btn)
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def load_shortcuts(self):
        """Load shortcuts from config into UI."""
        for key, edit in self.shortcut_edits.items():
            value = self.shortcuts.get(key)
            if value:
                # Handle both string and list formats
                if isinstance(value, list):
                    # Use first shortcut if multiple
                    edit.setText(value[0] if value else "")
                else:
                    edit.setText(value)
    
    def on_shortcut_changed(self, key, value):
        """Handle shortcut change."""
        # Update internal shortcuts dict
        value = value.strip()
        if value:
            self.shortcuts[key] = value
        else:
            # 如果值为空，设置为空字符串而不是删除键
            # 这样保存时会正确清除快捷键
            self.shortcuts[key] = ""

    def filter_shortcuts(self, text):
        """Filter shortcuts based on search text - 只显示匹配的项目."""
        text = text.lower().strip()

        # 如果搜索框为空，显示所有项目
        if not text:
            for key, (container, desc) in self.shortcut_items.items():
                container.setVisible(True)
            # 显示所有分组
            for i in range(self.scroll_layout.count()):
                item = self.scroll_layout.itemAt(i)
                if item and item.widget():
                    item.widget().setVisible(True)
            return

        # 遍历每个快捷键项目，检查是否匹配
        for key, (container, desc) in self.shortcut_items.items():
            current_value = self.shortcut_edits[key].text().lower()
            # 检查描述或快捷键值是否包含搜索文本
            if text in desc.lower() or text in current_value:
                container.setVisible(True)
            else:
                container.setVisible(False)

        # 检查每个分组是否有可见的项目，如果没有则隐藏整个分组
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, QtWidgets.QGroupBox):
                    shortcut_keys = widget.property("shortcut_keys")
                    if shortcut_keys:
                        # 检查该分组中是否有可见的项目
                        has_visible = False
                        for key in shortcut_keys:
                            if key in self.shortcut_items:
                                container, _ = self.shortcut_items[key]
                                if container.isVisible():
                                    has_visible = True
                                    break
                        widget.setVisible(has_visible)

    def reset_to_defaults(self):
        """Reset all shortcuts to default values."""
        reply = QtWidgets.QMessageBox.question(
            self,
            self.tr("确认重置"),
            self.tr("确定要将所有快捷键恢复为默认值吗？"),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            # Load default config
            from anylabeling.config import get_config
            default_config = get_config()
            default_shortcuts = default_config.get("shortcuts", {})

            # Update UI
            for key, edit in self.shortcut_edits.items():
                value = default_shortcuts.get(key)
                if value:
                    if isinstance(value, list):
                        edit.setText(value[0] if value else "")
                    else:
                        edit.setText(value)
                else:
                    edit.clear()

            QtWidgets.QMessageBox.information(
                self,
                self.tr("重置成功"),
                self.tr("快捷键已恢复为默认值，点击\"保存\"按钮应用更改。")
            )

    def save_shortcuts(self):
        """Save shortcuts to config."""
        # Check for duplicate shortcuts
        shortcut_map = {}
        duplicates = []

        for key, edit in self.shortcut_edits.items():
            value = edit.text().strip()
            if value:
                if value in shortcut_map:
                    duplicates.append((value, shortcut_map[value], key))
                else:
                    shortcut_map[value] = key

        if duplicates:
            msg = self.tr("发现重复的快捷键:\n\n")
            for shortcut, key1, key2 in duplicates:
                desc1 = self.get_description(key1)
                desc2 = self.get_description(key2)
                msg += f"{shortcut}: {desc1} 和 {desc2}\n"
            msg += self.tr("\n请修改后再保存。")

            QtWidgets.QMessageBox.warning(
                self,
                self.tr("快捷键冲突"),
                msg
            )
            return

        # Update config
        self._config["shortcuts"] = self.shortcuts.copy()
        save_config(self._config)

        # Emit signal to reload shortcuts
        self.shortcuts_saved.emit()

        # Close the dialog after successful save
        # The parent will show a success message
        self.close()

    def get_description(self, key):
        """Get description for a shortcut key."""
        for category, shortcuts in self.shortcut_categories.items():
            for sk, desc in shortcuts:
                if sk == key:
                    return desc
        return key

