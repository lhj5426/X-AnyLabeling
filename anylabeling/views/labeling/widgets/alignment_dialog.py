# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui
from datetime import datetime


class AlignmentButton(QtWidgets.QPushButton):
    """Custom button that emits different signals for left and right click."""

    left_clicked = QtCore.pyqtSignal()  # Left click: execute and exit
    right_clicked = QtCore.pyqtSignal()  # Right click: execute only

    def __init__(self, text, parent=None):
        super(AlignmentButton, self).__init__(text, parent)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.left_clicked.emit()
        elif event.button() == QtCore.Qt.RightButton:
            self.right_clicked.emit()
        # Call parent to maintain button visual feedback
        super(AlignmentButton, self).mousePressEvent(event)


class AlignmentDialog(QtWidgets.QDialog):
    """A non-modal dialog for aligning shapes."""

    # Signals now carry a boolean: True = auto exit, False = stay in mode
    align_left = QtCore.pyqtSignal(bool)
    align_h_center = QtCore.pyqtSignal(bool)
    align_right = QtCore.pyqtSignal(bool)
    align_top = QtCore.pyqtSignal(bool)
    align_v_center = QtCore.pyqtSignal(bool)
    align_bottom = QtCore.pyqtSignal(bool)
    unify_height = QtCore.pyqtSignal(bool)
    unify_width = QtCore.pyqtSignal(bool)
    unify_angle = QtCore.pyqtSignal(bool)
    push_out = QtCore.pyqtSignal(bool)  # 矩形弹出/分离信号（依赖参照物）
    push_out_all = QtCore.pyqtSignal()  # 整页矩形弹出分离信号（独立功能）
    push_out_selected = QtCore.pyqtSignal()  # 选中矩形弹出分离信号（独立功能）
    clear_edge_connections = QtCore.pyqtSignal()  # 清除全部边缘连接信号
    clear_selected_edge_connections = QtCore.pyqtSignal()  # 清除选中矩形的边缘连接信号
    
    # 指定尺寸信号: (标签列表, 宽度, 高度, 范围) 范围: "current", "selected", "range", "all"
    apply_specified_size = QtCore.pyqtSignal(list, int, int, str)
    # 指定尺寸范围信号: (标签列表, 宽度, 高度, 起始索引, 结束索引)
    apply_specified_size_range = QtCore.pyqtSignal(list, int, int, int, int)

    select_reference = QtCore.pyqtSignal(bool)
    reset_mode = QtCore.pyqtSignal()
    select_all_same_label = QtCore.pyqtSignal()
    closing = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super(AlignmentDialog, self).__init__(parent)
        self.setWindowTitle(self.tr("矩形对齐工具"))
        # 设置窗口标志：保持最小化按钮
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowTitleHint |
            QtCore.Qt.WindowSystemMenuHint |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowCloseButtonHint
        )
        self.resize(400, 450)
        
        self.init_ui()
        


    def init_ui(self):
        """Initialize the user interface."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Label Filter
        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(QtWidgets.QLabel(self.tr("指定标签 (逗号分隔):")))
        self.label_filter_input = QtWidgets.QLineEdit("balloon, qipao, changfangtiao, other")
        self.label_filter_input.setPlaceholderText(self.tr("留空则处理所有标签"))
        filter_layout.addWidget(self.label_filter_input)
        main_layout.addLayout(filter_layout)

        # --- Control Buttons ---
        control_layout = QtWidgets.QHBoxLayout()
        self.select_ref_button = QtWidgets.QPushButton(self.tr("选择/重选参照物"))
        self.select_ref_button.setCheckable(True)
        
        self.select_same_button = QtWidgets.QPushButton(self.tr("选中同类"))

        self.exit_button = QtWidgets.QPushButton(self.tr("退出对齐模式"))

        # --- Styles ---
        button_height = 36
        button_min_width = 120

        toggle_style = """
            QPushButton {
                background-color: #0071e3; /* Default Blue */
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                min-width: %dpx;
                height: %dpx;
            }
            QPushButton:hover {
                background-color: #0077ED;
            }
            QPushButton:checked {
                background-color: #5cb85c; /* Active Green */
                color: white;
                border: 1px solid #4cae4c;
            }
            QPushButton:checked:hover {
                background-color: #62c462;
            }
        """ % (button_min_width, button_height)

        select_same_style = """
            QPushButton {
                background-color: #5bc0de;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                min-width: %dpx;
                height: %dpx;
            }
            QPushButton:hover {
                background-color: #46b8da;
            }
        """ % (button_min_width, button_height)

        danger_style = """
            QPushButton {
                background-color: #d9534f;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                min-width: %dpx;
                height: %dpx;
            }
            QPushButton:hover {
                background-color: #c9302c;
            }
        """ % (button_min_width, button_height)

        # Save default style for later reset
        self.default_button_style = toggle_style

        self.target_selection_style = """
            QPushButton {
                background-color: #f0ad4e; /* Orange */
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                min-width: %dpx;
                height: %dpx;
            }
            QPushButton:hover {
                background-color: #ec971f;
            }
        """ % (button_min_width, button_height)

        self.select_ref_button.setStyleSheet(toggle_style)
        self.select_same_button.setStyleSheet(select_same_style)
        self.exit_button.setStyleSheet(danger_style)

        control_layout.addWidget(self.select_ref_button)
        control_layout.addWidget(self.select_same_button)
        control_layout.addWidget(self.exit_button)
        main_layout.addLayout(control_layout)
        
        # --- Alignment buttons ---
        alignment_group = QtWidgets.QGroupBox(self.tr("对齐"))
        alignment_layout = QtWidgets.QGridLayout(alignment_group)

        tooltip_text = self.tr("左键: 执行后自动退出模式\n右键: 执行后保持模式")

        self.btn_align_left = AlignmentButton(self.tr("左对齐"))
        self.btn_align_left.setToolTip(tooltip_text)

        self.btn_align_h_center = AlignmentButton(self.tr("水平居中"))
        self.btn_align_h_center.setToolTip(tooltip_text)

        self.btn_align_right = AlignmentButton(self.tr("右对齐"))
        self.btn_align_right.setToolTip(tooltip_text)

        self.btn_align_top = AlignmentButton(self.tr("上对齐"))
        self.btn_align_top.setToolTip(tooltip_text)

        self.btn_align_v_center = AlignmentButton(self.tr("垂直居中"))
        self.btn_align_v_center.setToolTip(tooltip_text)

        self.btn_align_bottom = AlignmentButton(self.tr("下对齐"))
        self.btn_align_bottom.setToolTip(tooltip_text)

        alignment_layout.addWidget(self.btn_align_left, 0, 0)
        alignment_layout.addWidget(self.btn_align_h_center, 0, 1)
        alignment_layout.addWidget(self.btn_align_right, 0, 2)
        alignment_layout.addWidget(self.btn_align_top, 1, 0)
        alignment_layout.addWidget(self.btn_align_v_center, 1, 1)
        alignment_layout.addWidget(self.btn_align_bottom, 1, 2)
        main_layout.addWidget(alignment_group)

        # --- Unify Size buttons ---
        unify_group = QtWidgets.QGroupBox(self.tr("统一尺寸"))
        unify_layout = QtWidgets.QVBoxLayout(unify_group)

        # 统一高度和宽度按钮
        unify_buttons_layout = QtWidgets.QHBoxLayout()
        self.btn_unify_height = AlignmentButton(self.tr("统一高度"))
        self.btn_unify_height.setToolTip(tooltip_text)

        self.btn_unify_width = AlignmentButton(self.tr("统一宽度"))
        self.btn_unify_width.setToolTip(tooltip_text)

        unify_buttons_layout.addWidget(self.btn_unify_height)
        unify_buttons_layout.addWidget(self.btn_unify_width)
        unify_layout.addLayout(unify_buttons_layout)

        # 统一角度专用区域
        angle_layout = QtWidgets.QHBoxLayout()
        angle_layout.addWidget(QtWidgets.QLabel(self.tr("旋转标签:")))
        self.angle_label_input = QtWidgets.QLineEdit("shuqing, hengxie")
        self.angle_label_input.setPlaceholderText(self.tr("统一角度时只处理这些标签"))
        self.angle_label_input.setToolTip(self.tr("统一角度时只处理这些标签的旋转矩形"))
        angle_layout.addWidget(self.angle_label_input)

        self.btn_unify_angle = AlignmentButton(self.tr("统一角度"))
        self.btn_unify_angle.setToolTip(tooltip_text)
        angle_layout.addWidget(self.btn_unify_angle)

        unify_layout.addLayout(angle_layout)
        
        # 分隔线
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        unify_layout.addWidget(separator)
        
        # 指定尺寸区域 - 标签选择列表（带复选框）
        label_select_layout = QtWidgets.QHBoxLayout()
        label_select_layout.addWidget(QtWidgets.QLabel(self.tr("选择标签:")))
        
        # 全选/全不选按钮
        self.btn_select_all_labels = QtWidgets.QPushButton(self.tr("全选"))
        self.btn_select_none_labels = QtWidgets.QPushButton(self.tr("全不选"))
        self.btn_select_all_labels.setFixedWidth(50)
        self.btn_select_none_labels.setFixedWidth(50)
        self.btn_select_all_labels.clicked.connect(self._select_all_size_labels)
        self.btn_select_none_labels.clicked.connect(self._select_none_size_labels)
        label_select_layout.addWidget(self.btn_select_all_labels)
        label_select_layout.addWidget(self.btn_select_none_labels)
        label_select_layout.addStretch()
        unify_layout.addLayout(label_select_layout)
        
        # 标签复选框列表（至少显示5行）
        self.size_label_list = QtWidgets.QListWidget()
        self.size_label_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.size_label_list.setMinimumHeight(110)  # 约5行高度
        self.size_label_list.setMaximumHeight(150)
        unify_layout.addWidget(self.size_label_list)
        
        # 第一行：宽 高 从 到
        row1_layout = QtWidgets.QHBoxLayout()
        row1_layout.setSpacing(5)
        row1_layout.addWidget(QtWidgets.QLabel(self.tr("宽:")))
        self.size_width_input = QtWidgets.QSpinBox()
        self.size_width_input.setRange(0, 9999)
        self.size_width_input.setValue(0)
        self.size_width_input.setSpecialValueText(self.tr("不变"))
        self.size_width_input.setToolTip(self.tr("0表示不修改宽度"))
        self.size_width_input.setFixedWidth(60)
        row1_layout.addWidget(self.size_width_input)
        
        row1_layout.addWidget(QtWidgets.QLabel(self.tr("高:")))
        self.size_height_input = QtWidgets.QSpinBox()
        self.size_height_input.setRange(0, 9999)
        self.size_height_input.setValue(0)
        self.size_height_input.setSpecialValueText(self.tr("不变"))
        self.size_height_input.setToolTip(self.tr("0表示不修改高度"))
        self.size_height_input.setFixedWidth(60)
        row1_layout.addWidget(self.size_height_input)
        
        row1_layout.addSpacing(15)
        row1_layout.addWidget(QtWidgets.QLabel(self.tr("从:")))
        self.size_start_spinbox = QtWidgets.QSpinBox()
        self.size_start_spinbox.setRange(1, 9999)
        self.size_start_spinbox.setValue(1)
        self.size_start_spinbox.setFixedWidth(55)
        row1_layout.addWidget(self.size_start_spinbox)
        
        row1_layout.addWidget(QtWidgets.QLabel(self.tr("到:")))
        self.size_end_spinbox = QtWidgets.QSpinBox()
        self.size_end_spinbox.setRange(1, 9999)
        self.size_end_spinbox.setValue(1)
        self.size_end_spinbox.setFixedWidth(55)
        row1_layout.addWidget(self.size_end_spinbox)
        row1_layout.addStretch()
        unify_layout.addLayout(row1_layout)
        
        # 第二行：4个按钮（和上面的范围输入框右边对齐）
        row2_layout = QtWidgets.QHBoxLayout()
        row2_layout.setSpacing(8)
        
        self.btn_apply_size_current = QtWidgets.QPushButton(self.tr("本页"))
        self.btn_apply_size_selected = QtWidgets.QPushButton(self.tr("选中"))
        self.btn_apply_size_range = QtWidgets.QPushButton(self.tr("范围"))
        self.btn_apply_size_all = QtWidgets.QPushButton(self.tr("全部"))
        
        # 按钮不设固定宽度，让它们自动填充
        
        apply_btn_style = """
            QPushButton {
                background-color: #5cb85c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 0px;
            }
            QPushButton:hover {
                background-color: #4cae4c;
            }
        """
        range_btn_style = apply_btn_style.replace("#5cb85c", "#5bc0de").replace("#4cae4c", "#46b8da")
        all_btn_style = apply_btn_style.replace("#5cb85c", "#f0ad4e").replace("#4cae4c", "#ec971f")
        
        self.btn_apply_size_current.setStyleSheet(apply_btn_style)
        self.btn_apply_size_selected.setStyleSheet(apply_btn_style)
        self.btn_apply_size_range.setStyleSheet(range_btn_style)
        self.btn_apply_size_all.setStyleSheet(all_btn_style)
        
        # 创建一个容器来包含4个按钮，固定总宽度和上面对齐
        btn_container = QtWidgets.QWidget()
        btn_container.setFixedWidth(365)  # 和上面的控件总宽度对齐
        btn_inner_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_inner_layout.setContentsMargins(0, 0, 0, 0)
        btn_inner_layout.setSpacing(8)
        btn_inner_layout.addWidget(self.btn_apply_size_current, 1)
        btn_inner_layout.addWidget(self.btn_apply_size_selected, 1)
        btn_inner_layout.addWidget(self.btn_apply_size_range, 1)
        btn_inner_layout.addWidget(self.btn_apply_size_all, 1)
        
        row2_layout.addWidget(btn_container)
        row2_layout.addStretch()
        unify_layout.addLayout(row2_layout)
        
        main_layout.addWidget(unify_group)

        # --- 矩形边界边距对齐功能区（独立功能，不依赖参照物） ---
        push_out_group = QtWidgets.QGroupBox(self.tr("矩形边界边距对齐"))
        push_out_layout = QtWidgets.QVBoxLayout(push_out_group)
        
        # 说明文字
        push_out_desc = QtWidgets.QLabel(self.tr("自动检测重叠的矩形，将穿透的矩形推出使边缘贴合"))
        push_out_desc.setWordWrap(True)
        push_out_desc.setStyleSheet("color: #666; font-size: 11px;")
        push_out_layout.addWidget(push_out_desc)
        
        # 按钮行
        push_out_btn_layout = QtWidgets.QHBoxLayout()
        
        self.btn_push_out_selected = QtWidgets.QPushButton(self.tr("选中矩形"))
        self.btn_push_out_all = QtWidgets.QPushButton(self.tr("整页矩形"))
        
        push_out_btn_style = """
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """
        self.btn_push_out_selected.setStyleSheet(push_out_btn_style)
        self.btn_push_out_all.setStyleSheet(push_out_btn_style)
        
        self.btn_push_out_selected.setToolTip(self.tr("处理当前选中的矩形之间的重叠"))
        self.btn_push_out_all.setToolTip(self.tr("处理整页所有矩形之间的重叠"))
        
        push_out_btn_layout.addWidget(self.btn_push_out_selected)
        push_out_btn_layout.addWidget(self.btn_push_out_all)
        push_out_layout.addLayout(push_out_btn_layout)
        
        # 连接边缘选项
        connect_layout = QtWidgets.QHBoxLayout()
        self.connect_edges_checkbox = QtWidgets.QCheckBox(self.tr("弹出后连接边缘"))
        self.connect_edges_checkbox.setToolTip(self.tr("弹出后将贴合的边缘连接起来，移动或调整一个矩形时另一个会同步变化"))
        connect_layout.addWidget(self.connect_edges_checkbox)
        
        self.btn_clear_selected_connections = QtWidgets.QPushButton(self.tr("清除选中"))
        self.btn_clear_selected_connections.setToolTip(self.tr("清除选中矩形的边缘连接关系"))
        self.btn_clear_selected_connections.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
        """)
        connect_layout.addWidget(self.btn_clear_selected_connections)
        
        self.btn_clear_connections = QtWidgets.QPushButton(self.tr("清除全部"))
        self.btn_clear_connections.setToolTip(self.tr("清除当前页面所有的边缘连接关系"))
        self.btn_clear_connections.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        connect_layout.addWidget(self.btn_clear_connections)
        connect_layout.addStretch()
        push_out_layout.addLayout(connect_layout)
        
        # 弹出方向选项
        direction_layout = QtWidgets.QHBoxLayout()
        direction_layout.addWidget(QtWidgets.QLabel(self.tr("弹出方向:")))
        self.push_direction_combo = QtWidgets.QComboBox()
        self.push_direction_combo.addItem(self.tr("水平（左右）"), "horizontal")
        self.push_direction_combo.addItem(self.tr("垂直（上下）"), "vertical")
        self.push_direction_combo.addItem(self.tr("自动（最短距离）"), "auto")
        self.push_direction_combo.setCurrentIndex(0)  # 默认水平
        self.push_direction_combo.setToolTip(self.tr("选择弹出方向：水平适合竖排矩形，垂直适合横排矩形"))
        direction_layout.addWidget(self.push_direction_combo)
        direction_layout.addStretch()
        push_out_layout.addLayout(direction_layout)
        
        main_layout.addWidget(push_out_group)

        # --- Log GroupBox ---
        log_group = QtWidgets.QGroupBox(self.tr("日志"))
        log_layout = QtWidgets.QVBoxLayout(log_group)
        self.log_widget = QtWidgets.QTextEdit()
        self.log_widget.setReadOnly(True)
        log_layout.addWidget(self.log_widget)
        main_layout.addWidget(log_group)
        
        # --- Connect signals ---
        self.select_ref_button.toggled.connect(self.set_reference_mode)
        self.exit_button.clicked.connect(self._on_exit_alignment_mode)
        self.select_same_button.clicked.connect(self.select_all_same_label.emit)

        # Connect alignment buttons: left click = auto exit, right click = stay
        self.btn_align_left.left_clicked.connect(lambda: self.align_left.emit(True))
        self.btn_align_left.right_clicked.connect(lambda: self.align_left.emit(False))

        self.btn_align_h_center.left_clicked.connect(lambda: self.align_h_center.emit(True))
        self.btn_align_h_center.right_clicked.connect(lambda: self.align_h_center.emit(False))

        self.btn_align_right.left_clicked.connect(lambda: self.align_right.emit(True))
        self.btn_align_right.right_clicked.connect(lambda: self.align_right.emit(False))

        self.btn_align_top.left_clicked.connect(lambda: self.align_top.emit(True))
        self.btn_align_top.right_clicked.connect(lambda: self.align_top.emit(False))

        self.btn_align_v_center.left_clicked.connect(lambda: self.align_v_center.emit(True))
        self.btn_align_v_center.right_clicked.connect(lambda: self.align_v_center.emit(False))

        self.btn_align_bottom.left_clicked.connect(lambda: self.align_bottom.emit(True))
        self.btn_align_bottom.right_clicked.connect(lambda: self.align_bottom.emit(False))

        # Connect unify buttons: left click = auto exit, right click = stay
        self.btn_unify_height.left_clicked.connect(lambda: self.unify_height.emit(True))
        self.btn_unify_height.right_clicked.connect(lambda: self.unify_height.emit(False))

        self.btn_unify_width.left_clicked.connect(lambda: self.unify_width.emit(True))
        self.btn_unify_width.right_clicked.connect(lambda: self.unify_width.emit(False))

        self.btn_unify_angle.left_clicked.connect(lambda: self.unify_angle.emit(True))
        self.btn_unify_angle.right_clicked.connect(lambda: self.unify_angle.emit(False))

        # Connect push out buttons (独立功能)
        self.btn_push_out_selected.clicked.connect(self.push_out_selected.emit)
        self.btn_push_out_all.clicked.connect(self.push_out_all.emit)
        
        # Connect clear connections buttons
        self.btn_clear_selected_connections.clicked.connect(self.clear_selected_edge_connections.emit)
        self.btn_clear_connections.clicked.connect(self.clear_edge_connections.emit)
        
        # Connect specified size buttons
        self.btn_apply_size_current.clicked.connect(lambda: self._emit_apply_size("current"))
        self.btn_apply_size_selected.clicked.connect(lambda: self._emit_apply_size("selected"))
        self.btn_apply_size_range.clicked.connect(self._emit_apply_size_range)
        self.btn_apply_size_all.clicked.connect(lambda: self._emit_apply_size("all"))

    def _get_selected_labels(self):
        """获取选中的标签列表"""
        labels = []
        for i in range(self.size_label_list.count()):
            item = self.size_label_list.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                labels.append(item.data(QtCore.Qt.UserRole))
        return labels

    def _select_all_size_labels(self):
        """全选标签"""
        for i in range(self.size_label_list.count()):
            self.size_label_list.item(i).setCheckState(QtCore.Qt.Checked)

    def _select_none_size_labels(self):
        """全不选标签"""
        for i in range(self.size_label_list.count()):
            self.size_label_list.item(i).setCheckState(QtCore.Qt.Unchecked)

    def _emit_apply_size(self, scope):
        """发送指定尺寸信号"""
        labels = self._get_selected_labels()
        if not labels:
            self.log(self.tr("请选择至少一个标签"))
            return
        width = self.size_width_input.value()
        height = self.size_height_input.value()
        if width == 0 and height == 0:
            self.log(self.tr("宽度和高度不能都为0"))
            return
        self.apply_specified_size.emit(labels, width, height, scope)

    def _emit_apply_size_range(self):
        """发送指定尺寸范围信号"""
        labels = self._get_selected_labels()
        if not labels:
            self.log(self.tr("请选择至少一个标签"))
            return
        width = self.size_width_input.value()
        height = self.size_height_input.value()
        if width == 0 and height == 0:
            self.log(self.tr("宽度和高度不能都为0"))
            return
        start = self.size_start_spinbox.value() - 1  # 转为0索引
        end = self.size_end_spinbox.value() - 1
        if start > end:
            self.log(self.tr("起始位置不能大于结束位置"))
            return
        self.apply_specified_size_range.emit(labels, width, height, start, end)

    def _on_exit_alignment_mode(self):
        """Handle exit alignment mode button click."""
        self.log(self.tr("已退出对齐模式，所有状态已重置。鼠标可以移动矩形了"))
        self.reset_mode.emit()
        # Reset button to default style and text
        self.select_ref_button.setStyleSheet(self.default_button_style)
        self.select_ref_button.setText(self.tr("选择/重选参照物"))
        self.select_ref_button.setChecked(False)

    def set_button_to_target_selection_mode(self):
        """Set the reference selection button to indicate waiting for target selection."""
        self.select_ref_button.setStyleSheet(self.target_selection_style)
        self.select_ref_button.setText(self.tr("请选择要对齐的矩形"))
        self.select_ref_button.setChecked(False) # Ensure it's not in 'checked' green state

    def set_reference_mode(self, is_active):
        if is_active:
            self.select_ref_button.setText(self.tr("请选择参照"))
            self.log(self.tr("已进入参照物选择模式，已禁用鼠标移动矩形"))
        else:
            self.select_ref_button.setText(self.tr("选择/重选参照物"))
            self.select_ref_button.setChecked(False)
            # Back to default blue style when leaving selection mode
            self.select_ref_button.setStyleSheet(self.default_button_style)
        self.select_reference.emit(is_active)

    def log(self, message):
        """Append a message to the log widget with a timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_widget.append(f"[{timestamp}] {message}")
        # 自动滚动到底部
        scrollbar = self.log_widget.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def get_angle_target_labels(self):
        """获取统一角度专用的目标标签列表"""
        text = self.angle_label_input.text().strip()
        if not text:
            return set()
        return {label.strip() for label in text.split(',') if label.strip()}

    def is_connect_edges_enabled(self):
        """获取是否启用弹出后连接边缘"""
        return self.connect_edges_checkbox.isChecked()

    def get_push_direction(self):
        """获取弹出方向设置
        
        Returns:
            str: "horizontal"（水平/左右）, "vertical"（垂直/上下）, 或 "auto"（自动）
        """
        return self.push_direction_combo.currentData()

    def update_page_range(self, current_page, total_pages):
        """更新范围选择的页码范围"""
        if total_pages > 0:
            self.size_start_spinbox.setRange(1, total_pages)
            self.size_end_spinbox.setRange(1, total_pages)
            self.size_start_spinbox.setValue(current_page)
            self.size_end_spinbox.setValue(total_pages)

    def update_label_list(self, labels, label_colors=None):
        """更新标签复选框列表"""
        # 保存当前选中的标签
        checked_labels = self._get_selected_labels()
        
        self.size_label_list.clear()
        for label in labels:
            item = QtWidgets.QListWidgetItem()
            item.setText(label)
            item.setData(QtCore.Qt.UserRole, label)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            # 恢复之前的选中状态
            if label in checked_labels:
                item.setCheckState(QtCore.Qt.Checked)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)
            # 设置背景颜色
            if label_colors and label in label_colors:
                rgb = label_colors[label]
                color = QtGui.QColor(rgb[0], rgb[1], rgb[2], 128)
                item.setBackground(color)
            self.size_label_list.addItem(item)

    def closeEvent(self, event):
        """Emit a closing signal when the dialog is closed."""
        self.closing.emit()
        super(AlignmentDialog, self).closeEvent(event)
