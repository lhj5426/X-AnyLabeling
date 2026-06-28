"""文件过滤对话框"""

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QRadioButton,
    QButtonGroup,
    QSpinBox,
)


class FileFilterDialog(QDialog):
    """文件过滤对话框，支持互斥的过滤条件"""
    
    filter_applied = pyqtSignal(dict)  # 发送过滤条件
    
    def __init__(self, parent=None, available_labels=None):
        super().__init__(parent)
        self.setWindowTitle("文件过滤")
        self.setMinimumWidth(400)
        self.setMinimumHeight(500)
        
        # 添加最小化按钮
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint)
        
        self.label_widget = parent  # 保存label_widget的引用
        self.available_labels = available_labels or []
        self.init_ui()

        # 监听标签库变化，自动刷新标签列表
        if self.label_widget and hasattr(self.label_widget, 'unique_label_list'):
            try:
                self.label_widget.unique_label_list.model().rowsInserted.connect(
                    self._on_label_list_changed)
                self.label_widget.unique_label_list.model().rowsRemoved.connect(
                    self._on_label_list_changed)
            except Exception:
                pass

    def _on_label_list_changed(self, *args):
        """标签库变化时自动刷新"""
        if not self.label_widget or not hasattr(self.label_widget, 'unique_label_list'):
            return
        # 合并 _config 和 unique_label_list 中的标签
        labels = list(self.label_widget._config.get('labels', []))
        for row in range(self.label_widget.unique_label_list.count()):
            item = self.label_widget.unique_label_list.item(row)
            if item:
                label_text = item.data(Qt.UserRole)
                if label_text and label_text not in labels:
                    labels.append(label_text)
        self.update_label_list(labels)

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 创建一个按钮组，使所有过滤选项互斥
        self.filter_group = QButtonGroup(self)

        # 标注状态过滤
        status_group = QGroupBox("标注状态")
        status_layout = QVBoxLayout()
        
        self.status_labeled = QRadioButton("已标注")
        self.status_unlabeled = QRadioButton("未标注")
        self.filter_group.addButton(self.status_labeled)
        self.filter_group.addButton(self.status_unlabeled)
        
        status_layout.addWidget(self.status_labeled)
        status_layout.addWidget(self.status_unlabeled)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # 编辑状态过滤
        edit_group = QGroupBox("编辑状态")
        edit_layout = QVBoxLayout()
        
        self.edit_manually = QRadioButton("仅手动编辑")
        self.edit_not_manually = QRadioButton("仅未手动编辑")
        self.filter_group.addButton(self.edit_manually)
        self.filter_group.addButton(self.edit_not_manually)
        
        edit_layout.addWidget(self.edit_manually)
        edit_layout.addWidget(self.edit_not_manually)
        edit_group.setLayout(edit_layout)
        layout.addWidget(edit_group)
        
        # 文本内容过滤
        text_group = QGroupBox("文本内容")
        text_layout = QVBoxLayout()
        
        self.text_has_text = QRadioButton("包含文本")
        self.text_no_text = QRadioButton("不包含文本")
        self.filter_group.addButton(self.text_has_text)
        self.filter_group.addButton(self.text_no_text)
        
        text_layout.addWidget(self.text_has_text)
        text_layout.addWidget(self.text_no_text)
        
        self.text_exclude_locked = QCheckBox("排除锁定的标签")
        self.text_exclude_locked.setChecked(
            self.label_widget._config.get("text_exclude_locked", True)
            if self.label_widget and hasattr(self.label_widget, "_config")
            else True
        )
        text_layout.addWidget(self.text_exclude_locked)
        
        text_group.setLayout(text_layout)
        layout.addWidget(text_group)
        
        # 困难标记过滤
        difficult_group = QGroupBox("困难标记")
        difficult_layout = QVBoxLayout()
        
        self.difficult_only = QRadioButton("仅困难标记")
        self.difficult_not_only = QRadioButton("仅非困难标记")
        self.filter_group.addButton(self.difficult_only)
        self.filter_group.addButton(self.difficult_not_only)
        
        difficult_layout.addWidget(self.difficult_only)
        difficult_layout.addWidget(self.difficult_not_only)
        difficult_group.setLayout(difficult_layout)
        layout.addWidget(difficult_group)

        # 重叠检测过滤
        overlap_group = QGroupBox("过滤重叠")
        overlap_layout = QVBoxLayout()

        self.overlap_only = QRadioButton("仅过滤有重叠的文件")
        self.filter_group.addButton(self.overlap_only)
        overlap_layout.addWidget(self.overlap_only)

        self.overlap_exclude_locked = QCheckBox("排除锁定的标签")
        self.overlap_exclude_locked.setChecked(
            self.label_widget._config.get("overlap_exclude_locked", True)
            if self.label_widget and hasattr(self.label_widget, "_config")
            else True
        )
        overlap_layout.addWidget(self.overlap_exclude_locked)

        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("重叠率阈值：")
        self.overlap_threshold_spin = QSpinBox()
        self.overlap_threshold_spin.setRange(1, 100)
        self.overlap_threshold_spin.setValue(
            self.label_widget._config.get("overlap_detect_threshold", 50)
            if self.label_widget and hasattr(self.label_widget, "_config")
            else 50
        )
        self.overlap_threshold_spin.setSuffix("%")
        self.overlap_threshold_spin.setToolTip(
            "两个矩形的交集面积占较小矩形面积的百分比达到此值时，视为重叠"
        )
        threshold_layout.addWidget(threshold_label)
        threshold_layout.addWidget(self.overlap_threshold_spin)
        threshold_layout.addStretch()
        overlap_layout.addLayout(threshold_layout)

        overlap_group.setLayout(overlap_layout)
        layout.addWidget(overlap_group)
        
        # 标签过滤
        label_group = QGroupBox("标签过滤")
        label_layout = QVBoxLayout()
        
        self.filter_by_label = QRadioButton("按标签过滤")
        self.filter_group.addButton(self.filter_by_label)
        label_layout.addWidget(self.filter_by_label)
        
        # 添加标签匹配模式选择
        match_mode_layout = QHBoxLayout()
        match_mode_label = QLabel("匹配模式：")
        self.label_match_any = QRadioButton("包含任一标签")
        self.label_match_all = QRadioButton("同时包含所有标签")
        self.label_match_any.setChecked(True)  # 默认为"任一"模式
        match_mode_layout.addWidget(match_mode_label)
        match_mode_layout.addWidget(self.label_match_any)
        match_mode_layout.addWidget(self.label_match_all)
        match_mode_layout.addStretch()
        label_layout.addLayout(match_mode_layout)
        
        label_info = QLabel("选择要显示的标签（可多选）：")
        label_layout.addWidget(label_info)
        
        self.label_list = QListWidget()
        # 不使用MultiSelection，而是使用复选框
        self.label_list.setSelectionMode(QListWidget.NoSelection)
        self.update_label_list(self.available_labels)
        label_layout.addWidget(self.label_list)
        
        # 标签选择按钮
        label_btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_none_btn = QPushButton("全不选")
        self.select_all_btn.clicked.connect(self.select_all_labels)
        self.select_none_btn.clicked.connect(self.select_no_labels)
        label_btn_layout.addWidget(self.select_all_btn)
        label_btn_layout.addWidget(self.select_none_btn)
        label_layout.addLayout(label_btn_layout)
        
        label_group.setLayout(label_layout)
        layout.addWidget(label_group)
        
        # 连接信号：当勾选标签时，自动选中"按标签过滤"；重叠检测时保留为联动标签
        self.label_list.itemChanged.connect(self.on_label_selection_changed)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        self.apply_btn = QPushButton("应用")
        self.reset_btn = QPushButton("重置")
        self.close_btn = QPushButton("关闭")
        
        self.apply_btn.clicked.connect(self.apply_filter)
        self.reset_btn.clicked.connect(self.reset_filter)
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.reset_btn)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_label_selection_changed(self):
        """当标签选择改变时，自动选中对应的单选按钮"""
        # 检查是否有任何标签被勾选
        has_checked = False
        for i in range(self.label_list.count()):
            if self.label_list.item(i).checkState() == Qt.Checked:
                has_checked = True
                break
        
        if not has_checked:
            return
        
        # 如果当前已是文本过滤模式，保持在文本模式（标签作为文本过滤的范围限定）
        if self.text_has_text.isChecked() or self.text_no_text.isChecked():
            return
        
        if (
            not self.overlap_only.isChecked()
        ):
            self.filter_by_label.setChecked(True)

    def update_label_list(self, labels):
        """更新可用标签列表（带颜色和复选框）"""
        self.available_labels = labels or []
        self._populate_label_list(self.available_labels)

    def _populate_label_list(self, labels):
        """填充下方复选列表。"""
        self.label_list.blockSignals(True)
        self.label_list.clear()
        
        # 从父窗口获取标签颜色
        for label in labels or []:
            item = QListWidgetItem()
            item.setText(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)  # 默认不选中
            
            # 尝试获取标签颜色
            if self.label_widget and hasattr(self.label_widget, '_get_rgb_by_label'):
                try:
                    rgb = self.label_widget._get_rgb_by_label(label)
                    if rgb:
                        color = QtGui.QColor(rgb[0], rgb[1], rgb[2], 128)
                        item.setBackground(color)
                except Exception as e:
                    print(f"[DEBUG] 获取标签 '{label}' 颜色失败: {e}")
            
            self.label_list.addItem(item)
        self.label_list.blockSignals(False)
    
    def select_all_labels(self):
        """全选标签"""
        for i in range(self.label_list.count()):
            self.label_list.item(i).setCheckState(Qt.Checked)
        # 如果当前已是文本过滤或重叠模式，不切换单选按钮
        if (
            self.text_has_text.isChecked() or self.text_no_text.isChecked()
            or self.overlap_only.isChecked()
        ):
            return
        self.filter_by_label.setChecked(True)
    
    def select_no_labels(self):
        """取消全选标签"""
        for i in range(self.label_list.count()):
            self.label_list.item(i).setCheckState(Qt.Unchecked)
    
    def get_filter_config(self):
        """获取当前过滤配置"""
        config = {
            'mode': 'none',  # none, status, edit, text, difficult, labels
            'value': None
        }
        
        # 检查哪个过滤选项被选中
        if self.status_labeled.isChecked():
            config['mode'] = 'status'
            config['value'] = 'labeled'
        elif self.status_unlabeled.isChecked():
            config['mode'] = 'status'
            config['value'] = 'unlabeled'
        elif self.edit_manually.isChecked():
            config['mode'] = 'edit'
            config['value'] = 'manually'
        elif self.edit_not_manually.isChecked():
            config['mode'] = 'edit'
            config['value'] = 'not_manually'
        elif self.text_has_text.isChecked():
            config['mode'] = 'text'
            config['value'] = 'has_text'
            # 收集勾选的标签（限定文本搜索范围）
            checked_labels = []
            for i in range(self.label_list.count()):
                item = self.label_list.item(i)
                if item.checkState() == Qt.Checked:
                    checked_labels.append(item.text())
            config['filter_labels'] = checked_labels
            config['exclude_locked'] = self.text_exclude_locked.isChecked()
            # 保存设置
            if self.label_widget and hasattr(self.label_widget, "_config"):
                self.label_widget._config["text_exclude_locked"] = self.text_exclude_locked.isChecked()
        elif self.text_no_text.isChecked():
            config['mode'] = 'text'
            config['value'] = 'no_text'
            # 收集勾选的标签（限定文本搜索范围）
            checked_labels = []
            for i in range(self.label_list.count()):
                item = self.label_list.item(i)
                if item.checkState() == Qt.Checked:
                    checked_labels.append(item.text())
            config['filter_labels'] = checked_labels
            config['exclude_locked'] = self.text_exclude_locked.isChecked()
            # 保存设置
            if self.label_widget and hasattr(self.label_widget, "_config"):
                self.label_widget._config["text_exclude_locked"] = self.text_exclude_locked.isChecked()
        elif self.difficult_only.isChecked():
            config['mode'] = 'difficult'
            config['value'] = 'difficult'
            # 获取勾选的标签（用于联动）
            checked_labels = []
            for i in range(self.label_list.count()):
                item = self.label_list.item(i)
                if item.checkState() == Qt.Checked:
                    checked_labels.append(item.text())
            if checked_labels:
                config['filter_labels'] = checked_labels
        elif self.difficult_not_only.isChecked():
            config['mode'] = 'difficult'
            config['value'] = 'not_difficult'
            # 获取勾选的标签（用于联动）
            checked_labels = []
            for i in range(self.label_list.count()):
                item = self.label_list.item(i)
                if item.checkState() == Qt.Checked:
                    checked_labels.append(item.text())
            if checked_labels:
                config['filter_labels'] = checked_labels
        elif self.overlap_only.isChecked():
            checked_labels = []
            for i in range(self.label_list.count()):
                item = self.label_list.item(i)
                if item.checkState() == Qt.Checked:
                    checked_labels.append(item.text())

            config['mode'] = 'overlap'
            config['value'] = {
                'threshold': self.overlap_threshold_spin.value(),
                'exclude_locked': self.overlap_exclude_locked.isChecked(),
                'filter_labels': checked_labels,
            }
        elif self.filter_by_label.isChecked():
            config['mode'] = 'labels'
            # 获取所有勾选的标签
            checked_labels = []
            for i in range(self.label_list.count()):
                item = self.label_list.item(i)
                if item.checkState() == Qt.Checked:
                    checked_labels.append(item.text())
            
            # 添加匹配模式信息
            match_mode = 'any' if self.label_match_any.isChecked() else 'all'
            config['value'] = {
                'labels': checked_labels,
                'match_mode': match_mode
            }
        
        return config
    
    def apply_filter(self):
        """应用过滤"""
        config = self.get_filter_config()
        self.filter_applied.emit(config)
    
    def reset_filter(self):
        """重置过滤条件"""
        # 取消所有选中的单选按钮
        self.filter_group.setExclusive(False)
        for button in self.filter_group.buttons():
            button.setChecked(False)
        self.filter_group.setExclusive(True)
        
        # 取消所有标签的勾选
        for i in range(self.label_list.count()):
            self.label_list.item(i).setCheckState(Qt.Unchecked)
        
        # 发送重置信号（mode='none'表示无过滤）
        config = {'mode': 'none', 'value': None}
        self.filter_applied.emit(config)
