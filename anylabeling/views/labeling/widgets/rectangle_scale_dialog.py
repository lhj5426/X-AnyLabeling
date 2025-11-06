"""
矩形缩放工具对话框
用于按比例缩放所有矩形标注的坐标
"""

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt, pyqtSignal


class RectangleScaleDialog(QtWidgets.QDialog):
    """矩形缩放工具对话框"""
    
    # 信号：当用户点击应用时发出，参数为缩放比例
    scale_applied = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("矩形缩放工具"))
        self.setModal(False)  # 非模态对话框，可以同时操作主窗口
        # 去掉 WindowStaysOnTopHint，允许被其他窗口遮挡
        # 添加 WindowMinimizeButtonHint，支持最小化
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        self.init_ui()
        self.load_settings()

        # 初始化时计算一次，同步两个计算器
        self.calculate_scale_from_resolution()
        
    def init_ui(self):
        """初始化UI"""
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # 缩放比例输入区域
        scale_group = QtWidgets.QGroupBox(self.tr("缩放参数"))
        scale_layout = QtWidgets.QVBoxLayout()
        scale_layout.setSpacing(4)

        # 缩放比例输入行
        scale_input_layout = QtWidgets.QHBoxLayout()
        scale_input_layout.addWidget(QtWidgets.QLabel(self.tr("缩放比例:")))

        self.scale_input = QtWidgets.QLineEdit()
        self.scale_input.setPlaceholderText(self.tr("例如: 1.5"))
        self.scale_input.setText("1.0")
        self.scale_input.setValidator(QtGui.QDoubleValidator(-100.0, 100.0, 6))
        self.scale_input.returnPressed.connect(self.apply_scale)
        self.scale_input.setMaximumWidth(120)
        scale_input_layout.addWidget(self.scale_input)
        scale_input_layout.addStretch()
        scale_layout.addLayout(scale_input_layout)

        # 分辨率计算器 - 紧凑布局
        resolution_layout = QtWidgets.QHBoxLayout()
        resolution_layout.setSpacing(4)

        self.source_width = QtWidgets.QSpinBox()
        self.source_width.setRange(1, 99999)
        self.source_width.setValue(1920)
        self.source_width.setMaximumWidth(70)
        self.source_width.valueChanged.connect(self.calculate_scale_from_resolution)
        resolution_layout.addWidget(self.source_width)

        resolution_layout.addWidget(QtWidgets.QLabel("×"))

        self.source_height = QtWidgets.QSpinBox()
        self.source_height.setRange(1, 99999)
        self.source_height.setValue(1080)
        self.source_height.setMaximumWidth(70)
        self.source_height.valueChanged.connect(self.calculate_scale_from_resolution)
        resolution_layout.addWidget(self.source_height)

        resolution_layout.addWidget(QtWidgets.QLabel("→"))

        self.target_width = QtWidgets.QSpinBox()
        self.target_width.setRange(1, 99999)
        self.target_width.setValue(2560)
        self.target_width.setMaximumWidth(70)
        self.target_width.valueChanged.connect(self.calculate_scale_from_resolution)
        resolution_layout.addWidget(self.target_width)

        resolution_layout.addWidget(QtWidgets.QLabel("×"))

        self.target_height = QtWidgets.QSpinBox()
        self.target_height.setRange(1, 99999)
        self.target_height.setValue(1440)
        self.target_height.setMaximumWidth(70)
        self.target_height.valueChanged.connect(self.calculate_scale_from_resolution)
        resolution_layout.addWidget(self.target_height)

        self.reset_resolution_button = QtWidgets.QPushButton(self.tr("重置"))
        self.reset_resolution_button.setToolTip(self.tr("重置为默认值：1920×1080 → 2560×1440"))
        self.reset_resolution_button.clicked.connect(self.reset_resolution)
        self.reset_resolution_button.setMaximumWidth(50)
        resolution_layout.addWidget(self.reset_resolution_button)

        resolution_layout.addStretch()
        scale_layout.addLayout(resolution_layout)

        # 结果显示和应用按钮
        result_layout = QtWidgets.QHBoxLayout()
        self.scale_result_label = QtWidgets.QLabel(self.tr("比例: 1.3333"))
        self.scale_result_label.setStyleSheet("QLabel { color: #2196F3; font-weight: bold; font-size: 11px; }")
        result_layout.addWidget(self.scale_result_label)

        self.calc_apply_button = QtWidgets.QPushButton(self.tr("应用"))
        self.calc_apply_button.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 3px 8px; }")
        self.calc_apply_button.clicked.connect(self.apply_calculated_scale)
        self.calc_apply_button.setMaximumWidth(60)
        result_layout.addWidget(self.calc_apply_button)
        result_layout.addStretch()
        scale_layout.addLayout(result_layout)

        # 倒数计算器 - 紧凑布局
        inverse_layout = QtWidgets.QHBoxLayout()
        inverse_layout.setSpacing(4)
        inverse_layout.addWidget(QtWidgets.QLabel(self.tr("当前/原图:")))

        self.inverse_ratio = QtWidgets.QLineEdit()
        self.inverse_ratio.setPlaceholderText(self.tr("0.75"))
        self.inverse_ratio.setText("0.75")
        self.inverse_ratio.setValidator(QtGui.QDoubleValidator(0.0001, 100.0, 6))
        self.inverse_ratio.textChanged.connect(self.calculate_inverse_scale)
        self.inverse_ratio.setMaximumWidth(80)
        inverse_layout.addWidget(self.inverse_ratio)

        self.inverse_result_label = QtWidgets.QLabel(self.tr("需缩放: 1.333"))
        self.inverse_result_label.setStyleSheet("QLabel { color: #9C27B0; font-weight: bold; font-size: 11px; }")
        inverse_layout.addWidget(self.inverse_result_label)

        self.inverse_apply_button = QtWidgets.QPushButton(self.tr("应用"))
        self.inverse_apply_button.setStyleSheet("QPushButton { background-color: #9C27B0; color: white; padding: 3px 8px; }")
        self.inverse_apply_button.clicked.connect(self.apply_inverse_scale)
        self.inverse_apply_button.setMaximumWidth(60)
        inverse_layout.addWidget(self.inverse_apply_button)

        inverse_layout.addStretch()
        scale_layout.addLayout(inverse_layout)

        # 初始计算
        self.calculate_inverse_scale()

        # 图像和标注信息 - 单行显示
        info_layout = QtWidgets.QHBoxLayout()
        self.image_info_label = QtWidgets.QLabel(self.tr("图像: 未加载"))
        self.image_info_label.setStyleSheet("QLabel { color: #666; font-size: 10px; }")
        info_layout.addWidget(self.image_info_label)

        self.shapes_info_label = QtWidgets.QLabel(self.tr("矩形: 0"))
        self.shapes_info_label.setStyleSheet("QLabel { color: #666; font-size: 10px; }")
        info_layout.addWidget(self.shapes_info_label)
        info_layout.addStretch()
        scale_layout.addLayout(info_layout)

        scale_group.setLayout(scale_layout)
        layout.addWidget(scale_group)

        # 缩放中心和范围选项 - 合并到一个组
        options_group = QtWidgets.QGroupBox(self.tr("选项"))
        options_layout = QtWidgets.QVBoxLayout()
        options_layout.setSpacing(4)

        # 缩放中心 - 单行显示
        center_layout = QtWidgets.QHBoxLayout()
        center_layout.addWidget(QtWidgets.QLabel(self.tr("缩放中心:")))

        # 创建按钮组确保单选
        self.center_button_group = QtWidgets.QButtonGroup(self)

        self.center_image = QtWidgets.QRadioButton(self.tr("图像中心"))
        self.center_image.setChecked(True)
        self.center_image.setToolTip(self.tr("以图像中心为基准进行缩放，保持整体布局"))
        self.center_button_group.addButton(self.center_image)
        center_layout.addWidget(self.center_image)

        self.center_origin = QtWidgets.QRadioButton(self.tr("原点(0,0)"))
        self.center_origin.setToolTip(self.tr("以左上角为基准进行缩放"))
        self.center_button_group.addButton(self.center_origin)
        center_layout.addWidget(self.center_origin)
        center_layout.addStretch()
        options_layout.addLayout(center_layout)

        # 缩放范围 - 单行显示
        scope_layout = QtWidgets.QHBoxLayout()
        scope_layout.addWidget(QtWidgets.QLabel(self.tr("缩放范围:")))

        # 创建按钮组确保单选
        self.scope_button_group = QtWidgets.QButtonGroup(self)

        self.scope_current = QtWidgets.QRadioButton(self.tr("当前页"))
        self.scope_current.setChecked(True)
        self.scope_current.setToolTip(self.tr("只缩放当前打开的图像的标注"))
        self.scope_current.toggled.connect(self.on_scope_changed)
        self.scope_button_group.addButton(self.scope_current)
        scope_layout.addWidget(self.scope_current)

        self.scope_all = QtWidgets.QRadioButton(self.tr("全部"))
        self.scope_all.setToolTip(self.tr("缩放文件夹中所有图像的标注"))
        self.scope_all.toggled.connect(self.on_scope_changed)
        self.scope_button_group.addButton(self.scope_all)
        scope_layout.addWidget(self.scope_all)

        self.scope_range = QtWidgets.QRadioButton(self.tr("范围"))
        self.scope_range.setToolTip(self.tr("缩放指定范围内的页面"))
        self.scope_range.toggled.connect(self.on_scope_changed)
        self.scope_button_group.addButton(self.scope_range)
        scope_layout.addWidget(self.scope_range)

        self.page_start = QtWidgets.QSpinBox()
        self.page_start.setRange(1, 99999)
        self.page_start.setValue(1)
        self.page_start.setEnabled(False)
        self.page_start.setMaximumWidth(60)
        scope_layout.addWidget(self.page_start)

        scope_layout.addWidget(QtWidgets.QLabel("-"))

        self.page_end = QtWidgets.QSpinBox()
        self.page_end.setRange(1, 99999)
        self.page_end.setValue(10)
        self.page_end.setEnabled(False)
        self.page_end.setMaximumWidth(60)
        scope_layout.addWidget(self.page_end)

        scope_layout.addStretch()
        options_layout.addLayout(scope_layout)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # 进度条 - 紧凑显示
        progress_layout = QtWidgets.QVBoxLayout()
        progress_layout.setSpacing(2)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setMaximumHeight(18)
        self.progress_bar.setStyleSheet(
            "QProgressBar { "
            "border: 1px solid #555; "
            "border-radius: 3px; "
            "text-align: center; "
            "background-color: #f0f0f0; "
            "font-size: 10px; "
            "}"
            "QProgressBar::chunk { "
            "background-color: #4CAF50; "
            "}"
        )
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QtWidgets.QLabel(self.tr("等待操作..."))
        self.progress_label.setStyleSheet("QLabel { color: #666; font-size: 10px; }")
        progress_layout.addWidget(self.progress_label)

        layout.addLayout(progress_layout)

        # 日志显示区域 - 可自适应高度
        log_group = QtWidgets.QGroupBox(self.tr("日志"))
        log_layout = QtWidgets.QVBoxLayout()
        log_layout.setContentsMargins(4, 4, 4, 4)

        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(60)  # 只设置最小高度，允许拉伸
        self.log_text.setStyleSheet(
            "QTextEdit { "
            "background-color: #f5f5f5; "
            "color: #333333; "
            "font-family: Consolas, monospace; "
            "font-size: 10px; "
            "border: 1px solid #ccc; "
            "}"
        )
        self.log_text.append(self.tr("等待操作..."))

        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # 按钮区域 - 紧凑布局
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(4)

        self.apply_button = QtWidgets.QPushButton(self.tr("应用缩放"))
        self.apply_button.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; padding: 6px 12px; font-weight: bold; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.apply_button.clicked.connect(self.apply_scale)

        self.reset_button = QtWidgets.QPushButton(self.tr("重置"))
        self.reset_button.clicked.connect(self.reset_scale)
        self.reset_button.setMaximumWidth(60)

        self.clear_log_button = QtWidgets.QPushButton(self.tr("清空日志"))
        self.clear_log_button.clicked.connect(self.clear_log)
        self.clear_log_button.setMaximumWidth(70)

        self.close_button = QtWidgets.QPushButton(self.tr("关闭"))
        self.close_button.clicked.connect(self.close)
        self.close_button.setMaximumWidth(60)

        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.clear_log_button)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)  # 设置最小高度
        # 移除最大宽度限制，允许窗口自由拉伸
        
    def set_scale(self, scale):
        """设置缩放比例"""
        self.scale_input.setText(f"{scale:.4f}")
        
    def reset_scale(self):
        """重置缩放比例为1.0"""
        self.scale_input.setText("1.0")

    def reset_resolution(self):
        """重置分辨率为默认值"""
        self.source_width.setValue(1920)
        self.source_height.setValue(1080)
        self.target_width.setValue(2560)
        self.target_height.setValue(1440)
        self.add_log(self.tr("ℹ️ 已重置分辨率为默认值：1920×1080 → 2560×1440"), "info")
        
    def apply_scale(self):
        """应用缩放"""
        try:
            scale_text = self.scale_input.text().strip()
            if not scale_text:
                self.add_log(self.tr("❌ 错误：请输入缩放比例！"), "error")
                return

            scale_value = float(scale_text)

            # 处理负数（负数表示缩小）
            if scale_value < 0:
                scale_value = abs(scale_value)
                self.add_log(self.tr(f"ℹ️ 负数已转换为正数：{scale_value:.4f}"), "info")

            if scale_value == 0:
                self.add_log(self.tr("❌ 错误：缩放比例不能为0！"), "error")
                return

            if scale_value == 1.0:
                self.add_log(self.tr("⚠️ 警告：缩放比例为1.0，不会产生任何变化。"), "warning")
                return

            # 发出信号，不再显示确认对话框
            self.add_log(self.tr(f"🚀 开始缩放，比例：{scale_value:.4f}"), "info")
            self.scale_applied.emit(scale_value)
            self.save_settings()

        except ValueError:
            self.add_log(self.tr("❌ 错误：请输入有效的数字！"), "error")

    def calculate_scale_from_resolution(self):
        """根据分辨率计算缩放比例"""
        try:
            source_w = self.source_width.value()
            source_h = self.source_height.value()
            target_w = self.target_width.value()
            target_h = self.target_height.value()

            # 计算宽度和高度的缩放比例
            scale_w = target_w / source_w
            scale_h = target_h / source_h

            # 显示缩放比例
            if abs(scale_w - scale_h) < 0.0001:
                # 宽高比例相同
                self.scale_result_label.setText(
                    self.tr(f"比例: {scale_w:.4f}")
                )
                self.scale_result_label.setStyleSheet("QLabel { color: #4CAF50; font-weight: bold; font-size: 11px; }")
            else:
                # 宽高比例不同，显示警告
                self.scale_result_label.setText(
                    self.tr(f"宽:{scale_w:.4f} 高:{scale_h:.4f}")
                )
                self.scale_result_label.setStyleSheet("QLabel { color: #FF9800; font-weight: bold; font-size: 11px; }")

            # 同时计算倒数（原图比例）
            inverse_w = source_w / target_w
            inverse_h = source_h / target_h

            # 更新倒数计算器的输入框
            # 暂时断开信号，避免循环触发
            self.inverse_ratio.blockSignals(True)
            if abs(inverse_w - inverse_h) < 0.0001:
                # 宽高比例相同
                self.inverse_ratio.setText(f"{inverse_w:.4f}")
                self.inverse_result_label.setText(
                    self.tr(f"需缩放: {scale_w:.4f}")
                )
                self.inverse_result_label.setStyleSheet("QLabel { color: #9C27B0; font-weight: bold; font-size: 11px; }")
            else:
                # 宽高比例不同
                self.inverse_ratio.setText(f"{inverse_w:.4f}")
                self.inverse_result_label.setText(
                    self.tr(f"需缩放: {scale_w:.4f}/{scale_h:.4f}")
                )
                self.inverse_result_label.setStyleSheet("QLabel { color: #FF9800; font-weight: bold; font-size: 11px; }")
            # 恢复信号
            self.inverse_ratio.blockSignals(False)
        except:
            self.scale_result_label.setText(self.tr("比例: --"))
            self.inverse_result_label.setText(self.tr("需缩放: --"))

    def apply_calculated_scale(self):
        """应用计算出的缩放比例"""
        try:
            source_w = self.source_width.value()
            source_h = self.source_height.value()
            target_w = self.target_width.value()
            target_h = self.target_height.value()

            # 计算缩放比例（使用宽度）
            scale_w = target_w / source_w
            scale_h = target_h / source_h

            # 检查宽高比例是否相同
            if abs(scale_w - scale_h) > 0.0001:
                self.add_log(
                    self.tr(f"⚠️ 警告：宽度比例({scale_w:.6f})和高度比例({scale_h:.6f})不同！"),
                    "warning"
                )
                self.add_log(
                    self.tr(f"ℹ️ 将使用宽度比例: {scale_w:.6f}"),
                    "info"
                )

            # 将比例填入输入框
            self.scale_input.setText(f"{scale_w:.6f}")

            self.add_log(
                self.tr(f"✅ 已应用分辨率计算结果: {source_w}×{source_h} → {target_w}×{target_h} = {scale_w:.6f}"),
                "success"
            )
        except Exception as e:
            self.add_log(self.tr(f"❌ 错误：{str(e)}"), "error")

    def calculate_inverse_scale(self):
        """计算倒数缩放比例"""
        try:
            ratio_text = self.inverse_ratio.text().strip()
            if not ratio_text:
                self.inverse_result_label.setText(self.tr("需缩放: --"))
                return

            ratio = float(ratio_text)

            if ratio <= 0:
                self.inverse_result_label.setText(self.tr("需缩放: 错误"))
                self.inverse_result_label.setStyleSheet("QLabel { color: #F44336; font-weight: bold; font-size: 11px; }")
                return

            # 计算倒数
            inverse_scale = 1.0 / ratio

            self.inverse_result_label.setText(
                self.tr(f"需缩放: {inverse_scale:.4f}")
            )
            self.inverse_result_label.setStyleSheet("QLabel { color: #9C27B0; font-weight: bold; font-size: 11px; }")
        except ValueError:
            self.inverse_result_label.setText(self.tr("需缩放: 错误"))
            self.inverse_result_label.setStyleSheet("QLabel { color: #F44336; font-weight: bold; font-size: 11px; }")

    def apply_inverse_scale(self):
        """应用倒数计算的缩放比例"""
        try:
            ratio_text = self.inverse_ratio.text().strip()
            if not ratio_text:
                self.add_log(self.tr("❌ 错误：请输入当前图相对于原图的比例！"), "error")
                return

            ratio = float(ratio_text)

            if ratio <= 0:
                self.add_log(self.tr("❌ 错误：比例必须大于0！"), "error")
                return

            # 计算倒数
            inverse_scale = 1.0 / ratio

            # 将比例填入输入框
            self.scale_input.setText(f"{inverse_scale:.6f}")

            self.add_log(
                self.tr(f"✅ 已应用倒数计算结果: 当前图是原图的 {ratio} 倍，需要缩放 {inverse_scale:.6f} 倍恢复原图"),
                "success"
            )
        except ValueError:
            self.add_log(self.tr("❌ 错误：请输入有效的数字！"), "error")
        except Exception as e:
            self.add_log(self.tr(f"❌ 错误：{str(e)}"), "error")

    def update_image_info(self, width, height):
        """更新图像信息"""
        self.image_info_label.setText(
            self.tr(f"图像: {width}×{height}")
        )

    def update_shapes_info(self, count):
        """更新矩形数量信息"""
        self.shapes_info_label.setText(
            self.tr(f"矩形: {count}")
        )
    
    def get_scale_center(self):
        """获取缩放中心类型"""
        if self.center_image.isChecked():
            return "image"
        else:
            return "origin"

    def get_scale_scope(self):
        """获取缩放范围"""
        if self.scope_current.isChecked():
            return "current"
        elif self.scope_all.isChecked():
            return "all"
        else:
            return "range"

    def get_page_range(self):
        """获取页面范围"""
        return (self.page_start.value(), self.page_end.value())

    def on_scope_changed(self):
        """缩放范围改变时的处理"""
        is_range = self.scope_range.isChecked()
        self.page_start.setEnabled(is_range)
        self.page_end.setEnabled(is_range)

    def update_page_range(self, current_page, total_pages):
        """更新页面范围

        Args:
            current_page: 当前页码（从1开始）
            total_pages: 总页数
        """
        if total_pages > 0:
            self.page_start.setRange(1, total_pages)
            self.page_end.setRange(1, total_pages)
            # 默认从当前页到最后一页
            self.page_start.setValue(current_page)
            self.page_end.setValue(total_pages)
        else:
            self.page_start.setRange(0, 0)
            self.page_end.setRange(0, 0)

    def add_log(self, message, level="info"):
        """添加日志信息

        Args:
            message: 日志消息
            level: 日志级别 (info, warning, error, success)
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")

        # 根据级别设置颜色（适配浅色背景）
        color_map = {
            "info": "#333333",
            "warning": "#ff8c00",
            "error": "#d32f2f",
            "success": "#2e7d32"
        }
        color = color_map.get(level, "#333333")

        formatted_message = f'<span style="color: #666;">[{timestamp}]</span> <span style="color: {color};">{message}</span>'
        self.log_text.append(formatted_message)

        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
        self.add_log(self.tr("日志已清空"), "info")

    def update_progress(self, current, total, message=""):
        """更新进度条

        Args:
            current: 当前进度
            total: 总数
            message: 进度消息
        """
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)

            if message:
                self.progress_label.setText(message)
            else:
                self.progress_label.setText(self.tr(f"正在处理: {current}/{total}"))
        else:
            self.progress_bar.setValue(0)
            self.progress_label.setText(self.tr("等待操作..."))

        # 强制刷新UI
        QtWidgets.QApplication.processEvents()

    def reset_progress(self):
        """重置进度条"""
        self.progress_bar.setValue(0)
        self.progress_label.setText(self.tr("等待操作..."))

    def load_settings(self):
        """加载设置"""
        settings = QtCore.QSettings("X-AnyLabeling", "RectangleScaleTool")
        scale = settings.value("last_scale", "1.0")
        center = settings.value("scale_center", "image")
        
        self.scale_input.setText(scale)
        if center == "origin":
            self.center_origin.setChecked(True)
        else:
            self.center_image.setChecked(True)
    
    def save_settings(self):
        """保存设置"""
        settings = QtCore.QSettings("X-AnyLabeling", "RectangleScaleTool")
        settings.setValue("last_scale", self.scale_input.text())
        settings.setValue("scale_center", self.get_scale_center())
    
    def closeEvent(self, event):
        """关闭事件"""
        self.save_settings()
        super().closeEvent(event)

