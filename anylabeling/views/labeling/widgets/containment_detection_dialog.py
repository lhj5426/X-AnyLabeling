"""
包围检测对话框
用于检测 other 标签是否包围了 qipao 或 balloon 标签
"""

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt


class ContainmentDetectionDialog(QtWidgets.QDialog):
    """包围检测对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle(self.tr("包围检测"))
        self.setModal(False)
        self.resize(500, 600)
        
        # 设置窗口标志，添加最小化按钮
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowMaximizeButtonHint |
            QtCore.Qt.WindowCloseButtonHint
        )
        
        # 获取配置
        self.config = self.get_config()
        
        self.init_ui()
        
        # 恢复窗口位置
        self.restore_window_position()
        
    def init_ui(self):
        """初始化界面"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 说明文本
        info_label = QtWidgets.QLabel(
            self.tr("检测 other 标签是否包围了其他标签（如 qipao、balloon）\n"
                   "用于判断漫画气泡检测是否正确")
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 设置区域
        settings_group = QtWidgets.QGroupBox(self.tr("检测设置"))
        settings_layout = QtWidgets.QFormLayout(settings_group)
        
        # 外层标签（要检测的包围框）
        self.outer_label_input = QtWidgets.QLineEdit(self.config.get('outer_label', 'other'))
        self.outer_label_input.textChanged.connect(self.save_config)
        settings_layout.addRow(self.tr("外层标签:"), self.outer_label_input)
        
        # 内层标签（被包围的标签）
        self.inner_labels_input = QtWidgets.QLineEdit(self.config.get('inner_labels', 'qipao,balloon,changfangtiao'))
        self.inner_labels_input.setPlaceholderText(self.tr("多个标签用逗号分隔"))
        self.inner_labels_input.textChanged.connect(self.save_config)
        settings_layout.addRow(self.tr("内层标签:"), self.inner_labels_input)
        
        # 包围阈值（内层标签中心点在外层标签内的比例）
        self.threshold_spinbox = QtWidgets.QSpinBox()
        self.threshold_spinbox.setRange(50, 100)
        self.threshold_spinbox.setValue(self.config.get('threshold', 80))
        self.threshold_spinbox.setSuffix("%")
        self.threshold_spinbox.setToolTip(self.tr("内层标签面积在外层标签内的最小比例"))
        self.threshold_spinbox.valueChanged.connect(self.save_config)
        settings_layout.addRow(self.tr("包围阈值:"), self.threshold_spinbox)
        
        layout.addWidget(settings_group)
        
        # 范围选择区域
        range_group = QtWidgets.QGroupBox(self.tr("范围选择"))
        range_layout = QtWidgets.QHBoxLayout(range_group)
        
        self.range_from = QtWidgets.QSpinBox()
        self.range_from.setMinimum(1)
        self.range_from.setValue(1)
        self.range_from.setPrefix(self.tr("从: "))
        
        self.range_to = QtWidgets.QSpinBox()
        self.range_to.setMinimum(1)
        self.range_to.setValue(1)
        self.range_to.setPrefix(self.tr("到: "))
        
        range_layout.addWidget(self.range_from)
        range_layout.addWidget(self.range_to)
        range_layout.addStretch()
        
        layout.addWidget(range_group)
        
        # 包围检测区域（添加GroupBox包裹）
        contain_group = QtWidgets.QGroupBox(self.tr("包围检测"))
        contain_layout = QtWidgets.QVBoxLayout(contain_group)
        
        info_label_contain = QtWidgets.QLabel(
            self.tr("检测外层标签是否包围了内层标签")
        )
        info_label_contain.setWordWrap(True)
        contain_layout.addWidget(info_label_contain)
        
        # 检测按钮区域
        detect_btn_layout = QtWidgets.QHBoxLayout()
        
        self.detect_current_btn = QtWidgets.QPushButton(self.tr("检测当前页"))
        self.detect_current_btn.clicked.connect(self.detect_current_page_clicked)
        detect_btn_layout.addWidget(self.detect_current_btn)
        
        self.detect_range_btn = QtWidgets.QPushButton(self.tr("检测范围页面"))
        self.detect_range_btn.clicked.connect(self.detect_range_clicked)
        detect_btn_layout.addWidget(self.detect_range_btn)
        
        self.detect_all_btn = QtWidgets.QPushButton(self.tr("检测全部页面"))
        self.detect_all_btn.clicked.connect(self.detect_all_clicked)
        detect_btn_layout.addWidget(self.detect_all_btn)
        
        contain_layout.addLayout(detect_btn_layout)
        layout.addWidget(contain_group)
        
        # 非包围检测区域（独立的设置）
        non_contain_group = QtWidgets.QGroupBox(self.tr("非包围检测"))
        non_contain_layout = QtWidgets.QVBoxLayout(non_contain_group)
        
        info_label2 = QtWidgets.QLabel(
            self.tr("检测哪些内层标签没有被任何外层标签包围")
        )
        info_label2.setWordWrap(True)
        non_contain_layout.addWidget(info_label2)
        
        # 非包围检测的独立设置
        non_contain_settings = QtWidgets.QGroupBox(self.tr("检测设置"))
        non_contain_settings_layout = QtWidgets.QFormLayout(non_contain_settings)
        
        # 外层标签
        self.non_outer_label_input = QtWidgets.QLineEdit(self.config.get('non_outer_label', 'other'))
        self.non_outer_label_input.textChanged.connect(self.save_config)
        non_contain_settings_layout.addRow(self.tr("外层标签:"), self.non_outer_label_input)
        
        # 内层标签
        self.non_inner_labels_input = QtWidgets.QLineEdit(self.config.get('non_inner_labels', 'qipao,balloon,changfangtiao'))
        self.non_inner_labels_input.setPlaceholderText(self.tr("多个标签用逗号分隔"))
        self.non_inner_labels_input.textChanged.connect(self.save_config)
        non_contain_settings_layout.addRow(self.tr("内层标签:"), self.non_inner_labels_input)
        
        # 包围阈值
        self.non_threshold_spinbox = QtWidgets.QSpinBox()
        self.non_threshold_spinbox.setRange(50, 100)
        self.non_threshold_spinbox.setValue(self.config.get('non_threshold', 80))
        self.non_threshold_spinbox.setSuffix("%")
        self.non_threshold_spinbox.setToolTip(self.tr("内层标签面积在外层标签内的最小比例"))
        self.non_threshold_spinbox.valueChanged.connect(self.save_config)
        non_contain_settings_layout.addRow(self.tr("包围阈值:"), self.non_threshold_spinbox)
        
        non_contain_layout.addWidget(non_contain_settings)
        
        # 非包围检测的范围选择
        non_range_group = QtWidgets.QGroupBox(self.tr("范围选择"))
        non_range_layout = QtWidgets.QHBoxLayout(non_range_group)
        
        self.non_range_from = QtWidgets.QSpinBox()
        self.non_range_from.setMinimum(1)
        self.non_range_from.setValue(1)
        self.non_range_from.setPrefix(self.tr("从: "))
        
        self.non_range_to = QtWidgets.QSpinBox()
        self.non_range_to.setMinimum(1)
        self.non_range_to.setValue(1)
        self.non_range_to.setPrefix(self.tr("到: "))
        
        non_range_layout.addWidget(self.non_range_from)
        non_range_layout.addWidget(self.non_range_to)
        non_range_layout.addStretch()
        
        non_contain_layout.addWidget(non_range_group)
        
        # 非包围检测按钮
        non_contain_btn_layout = QtWidgets.QHBoxLayout()
        
        self.non_contain_current_btn = QtWidgets.QPushButton(self.tr("检测当前页"))
        self.non_contain_current_btn.clicked.connect(self.non_contain_current_clicked)
        non_contain_btn_layout.addWidget(self.non_contain_current_btn)
        
        self.non_contain_range_btn = QtWidgets.QPushButton(self.tr("检测范围页面"))
        self.non_contain_range_btn.clicked.connect(self.non_contain_range_clicked)
        non_contain_btn_layout.addWidget(self.non_contain_range_btn)
        
        self.non_contain_all_btn = QtWidgets.QPushButton(self.tr("检测全部页面"))
        self.non_contain_all_btn.clicked.connect(self.non_contain_all_clicked)
        non_contain_btn_layout.addWidget(self.non_contain_all_btn)
        
        non_contain_layout.addLayout(non_contain_btn_layout)
        layout.addWidget(non_contain_group)
        
        # 操作按钮区域
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.delete_empty_btn = QtWidgets.QPushButton(self.tr("删除空包围"))
        self.delete_empty_btn.clicked.connect(self.delete_empty_containers)
        self.delete_empty_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_empty_btn)
        
        self.batch_delete_btn = QtWidgets.QPushButton(self.tr("批量删除范围"))
        self.batch_delete_btn.clicked.connect(self.batch_delete_selected)
        self.batch_delete_btn.setEnabled(False)
        btn_layout.addWidget(self.batch_delete_btn)
        
        self.add_to_filter_btn = QtWidgets.QPushButton(self.tr("添加到过滤器"))
        self.add_to_filter_btn.clicked.connect(self.add_results_to_filter)
        self.add_to_filter_btn.setEnabled(False)
        self.add_to_filter_btn.setToolTip(self.tr("将检测到有问题的页面添加到文件过滤器"))
        btn_layout.addWidget(self.add_to_filter_btn)
        
        self.reset_filter_btn = QtWidgets.QPushButton(self.tr("重置过滤器"))
        self.reset_filter_btn.clicked.connect(self.reset_filter)
        self.reset_filter_btn.setToolTip(self.tr("清除过滤，显示全部页面"))
        btn_layout.addWidget(self.reset_filter_btn)
        
        btn_layout.addStretch()
        
        self.close_btn = QtWidgets.QPushButton(self.tr("关闭"))
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
        
        # 结果显示区域
        result_group = QtWidgets.QGroupBox(self.tr("检测结果"))
        result_layout = QtWidgets.QVBoxLayout(result_group)
        
        self.result_text = QtWidgets.QTextEdit()
        self.result_text.setReadOnly(True)
        result_layout.addWidget(self.result_text)
        
        layout.addWidget(result_group)
        
        # 存储检测结果
        self.empty_containers = []
        self.all_results = []  # 存储所有页面的检测结果
        self.non_contained_items = []  # 存储未被包围的标签
        
        # 初始化范围
        self.update_range_limits()
        
        # 连接父窗口的文件改变信号，实现动态更新
        if hasattr(self.parent, 'file_list_widget'):
            self.parent.file_list_widget.currentRowChanged.connect(self.on_page_changed)
    
    def get_config(self):
        """从父窗口的配置中读取包围检测的配置"""
        if self.parent and hasattr(self.parent, '_config'):
            if 'containment_detection' not in self.parent._config:
                self.parent._config['containment_detection'] = {}
            return self.parent._config['containment_detection']
        return {}
    
    def save_config(self):
        """保存配置到父窗口的配置中"""
        if self.parent and hasattr(self.parent, '_config'):
            if 'containment_detection' not in self.parent._config:
                self.parent._config['containment_detection'] = {}
            
            # 包围检测配置
            self.parent._config['containment_detection']['outer_label'] = self.outer_label_input.text()
            self.parent._config['containment_detection']['inner_labels'] = self.inner_labels_input.text()
            self.parent._config['containment_detection']['threshold'] = self.threshold_spinbox.value()
            
            # 非包围检测配置
            self.parent._config['containment_detection']['non_outer_label'] = self.non_outer_label_input.text()
            self.parent._config['containment_detection']['non_inner_labels'] = self.non_inner_labels_input.text()
            self.parent._config['containment_detection']['non_threshold'] = self.non_threshold_spinbox.value()
            
            # 保存配置文件
            if hasattr(self.parent, 'save_config'):
                self.parent.save_config()
    
    def on_page_changed(self, current_row):
        """当页面改变时更新"从"的值"""
        if current_row >= 0:
            self.range_from.setValue(current_row + 1)
            self.non_range_from.setValue(current_row + 1)
    
    def showEvent(self, event):
        """窗口显示时更新范围"""
        super().showEvent(event)
        self.update_range_limits()
        # 设置"从"为当前页（包围检测和非包围检测都设置）
        if self.parent and hasattr(self.parent, 'filename') and self.parent.filename:
            if self.parent.filename in self.parent.fn_to_index:
                current_page = self.parent.fn_to_index[str(self.parent.filename)] + 1
                self.range_from.setValue(current_page)
                self.non_range_from.setValue(current_page)
    
    def closeEvent(self, event):
        """窗口关闭时断开信号连接并保存位置"""
        self.save_window_position()
        if hasattr(self.parent, 'file_list_widget'):
            try:
                self.parent.file_list_widget.currentRowChanged.disconnect(self.on_page_changed)
            except:
                pass
        super().closeEvent(event)
    
    def hideEvent(self, event):
        """窗口隐藏时保存位置"""
        self.save_window_position()
        super().hideEvent(event)
    
    def restore_window_position(self):
        """恢复窗口位置和大小"""
        settings = QtCore.QSettings()
        geometry = settings.value("containment_detection_dialog/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            # 默认位置（居中）
            if self.parent:
                parent_geo = self.parent.geometry()
                x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
                y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
                self.move(x, y)
    
    def save_window_position(self):
        """保存窗口位置和大小"""
        settings = QtCore.QSettings()
        settings.setValue("containment_detection_dialog/geometry", self.saveGeometry())
    
    def update_range_limits(self):
        """更新范围限制"""
        if hasattr(self.parent, 'image_list') and self.parent.image_list:
            total = len(self.parent.image_list)
            self.range_from.setMaximum(total)
            self.range_to.setMaximum(total)
            self.range_to.setValue(total)
            # 同时更新非包围检测的范围
            self.non_range_from.setMaximum(total)
            self.non_range_to.setMaximum(total)
            self.non_range_to.setValue(total)
        else:
            self.range_from.setMaximum(1)
            self.range_to.setMaximum(1)
            self.non_range_from.setMaximum(1)
            self.non_range_to.setMaximum(1)
    
    def detect_current_page_clicked(self):
        """检测当前页按钮点击"""
        outer_label = self.outer_label_input.text().strip()
        inner_labels_text = self.inner_labels_input.text().strip()
        inner_labels = [label.strip() for label in inner_labels_text.split(',') if label.strip()]
        threshold = self.threshold_spinbox.value() / 100.0
        
        if not self.validate_inputs(outer_label, inner_labels):
            return
        
        self.detect_current_page(outer_label, inner_labels, threshold)
    
    def detect_range_clicked(self):
        """检测范围页面按钮点击"""
        outer_label = self.outer_label_input.text().strip()
        inner_labels_text = self.inner_labels_input.text().strip()
        inner_labels = [label.strip() for label in inner_labels_text.split(',') if label.strip()]
        threshold = self.threshold_spinbox.value() / 100.0
        
        if not self.validate_inputs(outer_label, inner_labels):
            return
        
        from_page = self.range_from.value()
        to_page = self.range_to.value()
        
        if from_page > to_page:
            QtWidgets.QMessageBox.warning(
                self, self.tr("警告"), self.tr("起始页不能大于结束页")
            )
            return
        
        self.detect_custom_range(outer_label, inner_labels, threshold, from_page, to_page)
    
    def detect_all_clicked(self):
        """检测全部页面按钮点击"""
        outer_label = self.outer_label_input.text().strip()
        inner_labels_text = self.inner_labels_input.text().strip()
        inner_labels = [label.strip() for label in inner_labels_text.split(',') if label.strip()]
        threshold = self.threshold_spinbox.value() / 100.0
        
        if not self.validate_inputs(outer_label, inner_labels):
            return
        
        self.detect_all_pages(outer_label, inner_labels, threshold)
    
    def validate_inputs(self, outer_label, inner_labels):
        """验证输入"""
        if not outer_label:
            QtWidgets.QMessageBox.warning(
                self, self.tr("警告"), self.tr("请输入外层标签名称")
            )
            return False
            
        if not inner_labels:
            QtWidgets.QMessageBox.warning(
                self, self.tr("警告"), self.tr("请输入至少一个内层标签名称")
            )
            return False
        
        return True
        
    
    def detect_current_page(self, outer_label, inner_labels, threshold):
        """检测当前页面"""
        shapes = self.parent.canvas.shapes
        
        # 找出所有外层标签（支持普通矩形和旋转矩形）
        outer_shapes = [s for s in shapes if s.label == outer_label and s.shape_type in ['rectangle', 'rotation']]
        
        if not outer_shapes:
            self.result_text.setPlainText(
                self.tr(f"未找到标签为 '{outer_label}' 的矩形框")
            )
            return
        
        # 检测结果
        results = []
        self.empty_containers = []
        self.non_contained_items = []  # 清空非包围检测结果
        self.all_results = []
        
        for outer_shape in outer_shapes:
            contained_labels = self.check_containment(outer_shape, shapes, inner_labels, threshold)
            
            result = {
                'outer': outer_shape,
                'contained': contained_labels,
                'is_empty': len(contained_labels) == 0,
                'page': None,  # 当前页不需要页码
                'file_path': None
            }
            
            if result['is_empty']:
                self.empty_containers.append(outer_shape)
            
            results.append(result)
            self.all_results.append(result)
        
        # 显示结果
        self.display_results(results, outer_label, inner_labels, "当前页")
        
        # 启用删除按钮
        if self.empty_containers:
            self.delete_empty_btn.setEnabled(True)
            self.batch_delete_btn.setEnabled(True)
            self.add_to_filter_btn.setEnabled(True)
        else:
            self.delete_empty_btn.setEnabled(False)
            self.batch_delete_btn.setEnabled(False)
            self.add_to_filter_btn.setEnabled(False)
    
    def detect_all_pages(self, outer_label, inner_labels, threshold):
        """检测全部页面"""
        if not hasattr(self.parent, 'image_list') or not self.parent.image_list:
            QtWidgets.QMessageBox.warning(
                self, self.tr("警告"), self.tr("没有加载图像列表")
            )
            return
        
        total_pages = len(self.parent.image_list)
        self.detect_custom_range(outer_label, inner_labels, threshold, 1, total_pages)
    
    def detect_custom_range(self, outer_label, inner_labels, threshold, from_page, to_page):
        """检测自定义范围的页面（后台检测，不加载图片）"""
        if not hasattr(self.parent, 'image_list') or not self.parent.image_list:
            QtWidgets.QMessageBox.warning(
                self, self.tr("警告"), self.tr("没有加载图像列表")
            )
            return
        
        total_pages = len(self.parent.image_list)
        if from_page < 1 or to_page > total_pages:
            QtWidgets.QMessageBox.warning(
                self, self.tr("警告"), 
                self.tr(f"页码范围应在 1-{total_pages} 之间")
            )
            return
        
        # 显示进度
        progress = QtWidgets.QProgressDialog(
            self.tr("正在检测..."), self.tr("取消"), 
            from_page, to_page, self
        )
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setMinimumDuration(0)
        
        all_results = []
        self.empty_containers = []
        self.non_contained_items = []  # 清空非包围检测结果
        self.all_results = []
        
        import json
        import os.path as osp
        
        for page_num in range(from_page, to_page + 1):
            progress.setValue(page_num)
            if progress.wasCanceled():
                break
            
            # 获取图片路径和对应的标签文件路径
            page_index = page_num - 1
            image_path = self.parent.image_list[page_index]
            
            # 获取标签文件路径
            label_file = osp.splitext(image_path)[0] + ".json"
            
            # 如果有output_dir，标签文件在output_dir中
            if hasattr(self.parent, 'output_dir') and self.parent.output_dir:
                label_file = osp.join(
                    self.parent.output_dir,
                    osp.splitext(osp.basename(image_path))[0] + ".json"
                )
            
            # 读取标签文件
            if not osp.exists(label_file):
                continue
            
            try:
                with open(label_file, 'r', encoding='utf-8') as f:
                    label_data = json.load(f)
                
                # 解析shapes
                shapes = []
                if 'shapes' in label_data:
                    for shape_data in label_data['shapes']:
                        # 创建简化的shape对象用于检测
                        shape_obj = type('Shape', (), {
                            'label': shape_data.get('label', ''),
                            'shape_type': shape_data.get('shape_type', 'rectangle'),
                            'points': shape_data.get('points', [])
                        })()
                        shapes.append(shape_obj)
                
                # 找出外层标签
                outer_shapes = [s for s in shapes if s.label == outer_label and s.shape_type in ['rectangle', 'rotation']]
                
                for outer_shape in outer_shapes:
                    contained_labels = self.check_containment_from_data(outer_shape, shapes, inner_labels, threshold)
                    
                    result = {
                        'outer': outer_shape,
                        'contained': contained_labels,
                        'is_empty': len(contained_labels) == 0,
                        'page': page_num,
                        'file_path': image_path
                    }
                    
                    if result['is_empty']:
                        self.empty_containers.append({
                            'shape': outer_shape,
                            'page': page_num,
                            'file_path': image_path,
                            'label_file': label_file
                        })
                    
                    all_results.append(result)
                    self.all_results.append(result)
            
            except Exception as e:
                print(f"Error reading {label_file}: {e}")
                continue
        
        progress.setValue(to_page)
        
        # 显示结果
        range_text = f"第 {from_page}-{to_page} 页" if from_page != to_page else f"第 {from_page} 页"
        self.display_results(all_results, outer_label, inner_labels, range_text)
        
        # 启用删除按钮
        if self.empty_containers:
            self.delete_empty_btn.setEnabled(True)
            self.batch_delete_btn.setEnabled(True)
            self.add_to_filter_btn.setEnabled(True)
        else:
            self.delete_empty_btn.setEnabled(False)
            self.batch_delete_btn.setEnabled(False)
            self.add_to_filter_btn.setEnabled(False)
    
    def check_containment_from_data(self, outer_shape, all_shapes, inner_labels, threshold):
        """从数据检查包围关系（不需要QPointF对象）"""
        contained = []
        
        # 获取外层矩形的边界
        outer_points = outer_shape.points
        if len(outer_points) < 2:
            return contained
        
        # 处理points可能是列表或QPointF的情况
        if isinstance(outer_points[0], (list, tuple)):
            x_coords = [p[0] for p in outer_points]
            y_coords = [p[1] for p in outer_points]
        else:
            # QPointF对象
            x_coords = [p.x() for p in outer_points]
            y_coords = [p.y() for p in outer_points]
        
        outer_x1, outer_x2 = min(x_coords), max(x_coords)
        outer_y1, outer_y2 = min(y_coords), max(y_coords)
        
        # 检查每个内层标签
        for shape in all_shapes:
            if shape == outer_shape:
                continue
                
            if shape.label not in inner_labels:
                continue
                
            if shape.shape_type not in ['rectangle', 'rotation']:
                continue
            
            inner_points = shape.points
            if len(inner_points) < 2:
                continue
            
            # 处理points
            if isinstance(inner_points[0], (list, tuple)):
                x_coords = [p[0] for p in inner_points]
                y_coords = [p[1] for p in inner_points]
            else:
                x_coords = [p.x() for p in inner_points]
                y_coords = [p.y() for p in inner_points]
            
            inner_x1, inner_x2 = min(x_coords), max(x_coords)
            inner_y1, inner_y2 = min(y_coords), max(y_coords)
            inner_area = (inner_x2 - inner_x1) * (inner_y2 - inner_y1)
            
            # 计算重叠区域
            overlap_x1 = max(outer_x1, inner_x1)
            overlap_y1 = max(outer_y1, inner_y1)
            overlap_x2 = min(outer_x2, inner_x2)
            overlap_y2 = min(outer_y2, inner_y2)
            
            if overlap_x2 > overlap_x1 and overlap_y2 > overlap_y1:
                overlap_area = (overlap_x2 - overlap_x1) * (overlap_y2 - overlap_y1)
                
                if inner_area > 0:
                    overlap_ratio = overlap_area / inner_area
                    if overlap_ratio >= threshold:
                        contained.append({
                            'shape': shape,
                            'label': shape.label,
                            'ratio': overlap_ratio
                        })
        
        return contained
    
    def check_containment(self, outer_shape, all_shapes, inner_labels, threshold):
        """检查外层标签包围了哪些内层标签"""
        contained = []
        
        # 获取外层矩形的边界
        outer_points = outer_shape.points
        if len(outer_points) < 2:
            return contained
        
        # 计算外层矩形的边界框（无论是否旋转）
        x_coords = [p.x() for p in outer_points]
        y_coords = [p.y() for p in outer_points]
        outer_x1, outer_x2 = min(x_coords), max(x_coords)
        outer_y1, outer_y2 = min(y_coords), max(y_coords)
        outer_area = (outer_x2 - outer_x1) * (outer_y2 - outer_y1)
        
        # 检查每个内层标签
        for shape in all_shapes:
            if shape == outer_shape:
                continue
                
            if shape.label not in inner_labels:
                continue
                
            # 支持普通矩形和旋转矩形
            if shape.shape_type not in ['rectangle', 'rotation']:
                continue
            
            # 获取内层矩形的边界
            inner_points = shape.points
            if len(inner_points) < 2:
                continue
            
            # 计算内层矩形的边界框
            x_coords = [p.x() for p in inner_points]
            y_coords = [p.y() for p in inner_points]
            inner_x1, inner_x2 = min(x_coords), max(x_coords)
            inner_y1, inner_y2 = min(y_coords), max(y_coords)
            inner_area = (inner_x2 - inner_x1) * (inner_y2 - inner_y1)
            
            # 计算重叠区域
            overlap_x1 = max(outer_x1, inner_x1)
            overlap_y1 = max(outer_y1, inner_y1)
            overlap_x2 = min(outer_x2, inner_x2)
            overlap_y2 = min(outer_y2, inner_y2)
            
            if overlap_x2 > overlap_x1 and overlap_y2 > overlap_y1:
                # 有重叠
                overlap_area = (overlap_x2 - overlap_x1) * (overlap_y2 - overlap_y1)
                
                if inner_area > 0:
                    overlap_ratio = overlap_area / inner_area
                    if overlap_ratio >= threshold:
                        contained.append({
                            'shape': shape,
                            'label': shape.label,
                            'ratio': overlap_ratio
                        })
        
        return contained
    
    def display_results(self, results, outer_label, inner_labels, range_text="当前页"):
        """显示检测结果"""
        text = []
        text.append(self.tr(f"检测设置:"))
        text.append(self.tr(f"  外层标签: {outer_label}"))
        text.append(self.tr(f"  内层标签: {', '.join(inner_labels)}"))
        text.append(self.tr(f"  包围阈值: {self.threshold_spinbox.value()}%"))
        text.append(self.tr(f"  检测范围: {range_text}"))
        text.append("")
        text.append(self.tr(f"检测结果:"))
        text.append(self.tr(f"  总共检测到 {len(results)} 个 '{outer_label}' 标签"))
        text.append("")
        
        empty_count = sum(1 for r in results if r['is_empty'])
        valid_count = len(results) - empty_count
        
        text.append(self.tr(f"  有效包围: {valid_count} 个"))
        text.append(self.tr(f"  空包围: {empty_count} 个"))
        
        # 如果有空包围，列出所有空包围的页数
        if empty_count > 0:
            empty_pages = set()
            for r in results:
                if r['is_empty'] and r.get('page'):
                    empty_pages.add(r['page'])
            
            if empty_pages:
                sorted_pages = sorted(empty_pages)
                text.append("")
                text.append(self.tr(f"  空包围所在页码: {', '.join(map(str, sorted_pages))}"))
        
        text.append("")
        
        # 详细信息
        text.append(self.tr("详细信息:"))
        text.append("-" * 50)
        
        for i, result in enumerate(results, 1):
            outer = result['outer']
            contained = result['contained']
            page = result.get('page')
            
            # 获取外层框的坐标信息
            outer_points = outer.points
            
            # 处理points可能是列表或QPointF的情况
            if isinstance(outer_points[0], (list, tuple)):
                x_coords = [p[0] for p in outer_points]
                y_coords = [p[1] for p in outer_points]
            else:
                # QPointF对象
                x_coords = [p.x() for p in outer_points]
                y_coords = [p.y() for p in outer_points]
            
            outer_x1, outer_x2 = min(x_coords), max(x_coords)
            outer_y1, outer_y2 = min(y_coords), max(y_coords)
            
            # 如果有页码信息，显示页码
            page_info = f"第 {page} 页 - " if page else ""
            text.append(self.tr(f"\n[{i}] {page_info}{outer_label} 框 (位置: {int(outer_x1)},{int(outer_y1)} - {int(outer_x2)},{int(outer_y2)})"))
            
            if result['is_empty']:
                text.append(self.tr(f"  ❌ 空包围 - 未包含任何 {', '.join(inner_labels)} 标签"))
            else:
                text.append(self.tr(f"  ✓ 包含 {len(contained)} 个标签:"))
                for item in contained:
                    text.append(self.tr(f"    - {item['label']} (重叠率: {item['ratio']*100:.1f}%)"))
        
        self.result_text.setPlainText('\n'.join(text))
    
    def delete_empty_containers(self):
        """删除空包围的标签（仅当前页）"""
        if not self.empty_containers:
            return
        
        # 过滤出当前页的空包围
        current_page_empty = []
        if self.parent.filename and self.parent.filename in self.parent.fn_to_index:
            current_page_num = self.parent.fn_to_index[str(self.parent.filename)] + 1
        else:
            current_page_num = 1
        
        for item in self.empty_containers:
            if isinstance(item, dict):
                # 多页检测结果
                if item.get('page') == current_page_num:
                    current_page_empty.append(item['shape'])
            else:
                # 单页检测结果
                current_page_empty.append(item)
        
        if not current_page_empty:
            QtWidgets.QMessageBox.information(
                self, self.tr("提示"), self.tr("当前页没有空包围标签")
            )
            return
        
        reply = QtWidgets.QMessageBox.question(
            self,
            self.tr("确认删除"),
            self.tr(f"确定要删除当前页的 {len(current_page_empty)} 个空包围标签吗？"),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            for shape in current_page_empty:
                if shape in self.parent.canvas.shapes:
                    self.parent.canvas.shapes.remove(shape)
                    # 从标签列表中移除
                    item = self.parent.label_list.find_item_by_shape(shape)
                    if item:
                        self.parent.label_list.remove_item(item)
            
            self.parent.canvas.update()
            self.parent.set_dirty()
            
            QtWidgets.QMessageBox.information(
                self,
                self.tr("删除完成"),
                self.tr(f"已删除当前页的 {len(current_page_empty)} 个空包围标签")
            )
            
            # 重新检测当前页
            outer_label = self.outer_label_input.text().strip()
            inner_labels_text = self.inner_labels_input.text().strip()
            inner_labels = [label.strip() for label in inner_labels_text.split(',') if label.strip()]
            threshold = self.threshold_spinbox.value() / 100.0
            if outer_label and inner_labels:
                self.detect_current_page(outer_label, inner_labels, threshold)
    
    def batch_delete_selected(self):
        """批量删除范围内的空包围标签（直接修改JSON文件）"""
        if not self.empty_containers:
            return
        
        # 统计各页的空包围数量
        page_counts = {}
        for item in self.empty_containers:
            if isinstance(item, dict):
                page = item.get('page', 1)
                page_counts[page] = page_counts.get(page, 0) + 1
        
        if not page_counts:
            QtWidgets.QMessageBox.information(
                self, self.tr("提示"), self.tr("没有空包围标签可删除")
            )
            return
        
        total_count = sum(page_counts.values())
        page_range = f"{min(page_counts.keys())}-{max(page_counts.keys())}" if len(page_counts) > 1 else str(list(page_counts.keys())[0])
        
        reply = QtWidgets.QMessageBox.question(
            self,
            self.tr("确认批量删除"),
            self.tr(f"确定要删除第 {page_range} 页共 {total_count} 个空包围标签吗？\n\n") +
            self.tr("详细信息:\n") +
            "\n".join([self.tr(f"第 {page} 页: {count} 个") for page, count in sorted(page_counts.items())]),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            import json
            import os.path as osp
            
            # 显示进度
            progress = QtWidgets.QProgressDialog(
                self.tr("正在删除..."), self.tr("取消"), 
                0, len(page_counts), self
            )
            progress.setWindowModality(QtCore.Qt.WindowModal)
            progress.setMinimumDuration(0)
            
            deleted_count = 0
            
            # 按页分组
            items_by_page = {}
            for item in self.empty_containers:
                if isinstance(item, dict):
                    page = item.get('page')
                    if page not in items_by_page:
                        items_by_page[page] = []
                    items_by_page[page].append(item)
            
            for i, (page, items) in enumerate(sorted(items_by_page.items())):
                progress.setValue(i)
                if progress.wasCanceled():
                    break
                
                # 获取标签文件路径
                label_file = items[0].get('label_file')
                if not label_file or not osp.exists(label_file):
                    continue
                
                try:
                    # 读取标签文件
                    with open(label_file, 'r', encoding='utf-8') as f:
                        label_data = json.load(f)
                    
                    # 获取要删除的shape的坐标
                    shapes_to_delete = []
                    for item in items:
                        shape = item['shape']
                        points = shape.points
                        if isinstance(points[0], (list, tuple)):
                            shapes_to_delete.append(points)
                        else:
                            shapes_to_delete.append([[p.x(), p.y()] for p in points])
                    
                    # 过滤掉要删除的shapes
                    original_count = len(label_data.get('shapes', []))
                    new_shapes = []
                    
                    for shape_data in label_data.get('shapes', []):
                        shape_points = shape_data.get('points', [])
                        # 检查是否是要删除的shape
                        is_delete = False
                        for delete_points in shapes_to_delete:
                            if self.points_match(shape_points, delete_points):
                                is_delete = True
                                break
                        
                        if not is_delete:
                            new_shapes.append(shape_data)
                    
                    label_data['shapes'] = new_shapes
                    deleted_count += original_count - len(new_shapes)
                    
                    # 保存文件
                    with open(label_file, 'w', encoding='utf-8') as f:
                        json.dump(label_data, f, ensure_ascii=False, indent=2)
                
                except Exception as e:
                    print(f"Error processing {label_file}: {e}")
                    continue
            
            progress.setValue(len(page_counts))
            
            # 如果当前页被修改了，重新加载
            if self.parent.filename:
                current_page = self.parent.fn_to_index.get(str(self.parent.filename), -1) + 1
                if current_page in items_by_page:
                    self.parent.load_file(self.parent.filename)
            
            QtWidgets.QMessageBox.information(
                self,
                self.tr("删除完成"),
                self.tr(f"已删除 {deleted_count} 个空包围标签")
            )
            
            # 清空结果
            self.empty_containers = []
            self.non_contained_items = []  # 清空非包围检测结果
            self.all_results = []
            self.delete_empty_btn.setEnabled(False)
            self.batch_delete_btn.setEnabled(False)
            self.result_text.clear()
    
    def points_match(self, points1, points2, tolerance=0.1):
        """比较两个点集是否匹配"""
        if len(points1) != len(points2):
            return False
        
        for p1, p2 in zip(points1, points2):
            if isinstance(p1, (list, tuple)):
                x1, y1 = p1[0], p1[1]
            else:
                x1, y1 = p1, p1
            
            if isinstance(p2, (list, tuple)):
                x2, y2 = p2[0], p2[1]
            else:
                x2, y2 = p2, p2
            
            if abs(x1 - x2) > tolerance or abs(y1 - y2) > tolerance:
                return False
        
        return True

    
    # ==================== 非包围检测功能 ====================
    
    def non_contain_current_clicked(self):
        """检测当前页未被包围的标签"""
        outer_label = self.non_outer_label_input.text().strip()
        inner_labels_text = self.non_inner_labels_input.text().strip()
        inner_labels = [label.strip() for label in inner_labels_text.split(',') if label.strip()]
        threshold = self.non_threshold_spinbox.value() / 100.0
        
        if not self.validate_inputs(outer_label, inner_labels):
            return
        
        self.detect_non_contained_current(outer_label, inner_labels, threshold)
    
    def non_contain_range_clicked(self):
        """检测范围页面未被包围的标签"""
        outer_label = self.non_outer_label_input.text().strip()
        inner_labels_text = self.non_inner_labels_input.text().strip()
        inner_labels = [label.strip() for label in inner_labels_text.split(',') if label.strip()]
        threshold = self.non_threshold_spinbox.value() / 100.0
        
        if not self.validate_inputs(outer_label, inner_labels):
            return
        
        from_page = self.non_range_from.value()
        to_page = self.non_range_to.value()
        
        if from_page > to_page:
            QtWidgets.QMessageBox.warning(
                self, self.tr("警告"), self.tr("起始页不能大于结束页")
            )
            return
        
        self.detect_non_contained_range(outer_label, inner_labels, threshold, from_page, to_page)
    
    def non_contain_all_clicked(self):
        """检测全部页面未被包围的标签"""
        outer_label = self.non_outer_label_input.text().strip()
        inner_labels_text = self.non_inner_labels_input.text().strip()
        inner_labels = [label.strip() for label in inner_labels_text.split(',') if label.strip()]
        threshold = self.non_threshold_spinbox.value() / 100.0
        
        if not self.validate_inputs(outer_label, inner_labels):
            return
        
        if not hasattr(self.parent, 'image_list') or not self.parent.image_list:
            QtWidgets.QMessageBox.warning(
                self, self.tr("警告"), self.tr("没有加载图像列表")
            )
            return
        
        total_pages = len(self.parent.image_list)
        self.detect_non_contained_range(outer_label, inner_labels, threshold, 1, total_pages)
    
    def detect_non_contained_current(self, outer_label, inner_labels, threshold):
        """检测当前页未被包围的标签"""
        # 清空包围检测结果
        self.empty_containers = []
        self.all_results = []
        
        shapes = self.parent.canvas.shapes
        
        # 找出所有外层标签和内层标签
        outer_shapes = [s for s in shapes if s.label == outer_label and s.shape_type in ['rectangle', 'rotation']]
        inner_shapes = [s for s in shapes if s.label in inner_labels and s.shape_type in ['rectangle', 'rotation']]
        
        if not inner_shapes:
            self.result_text.setPlainText(
                self.tr(f"未找到内层标签 ({', '.join(inner_labels)}) 的矩形框")
            )
            return
        
        # 检测哪些内层标签未被包围
        non_contained = []
        for inner_shape in inner_shapes:
            is_contained = False
            for outer_shape in outer_shapes:
                # 检查是否被这个外层标签包围
                contained = self.check_containment(outer_shape, [inner_shape], [inner_shape.label], threshold)
                if contained:
                    is_contained = True
                    break
            
            if not is_contained:
                non_contained.append({
                    'shape': inner_shape,
                    'label': inner_shape.label,
                    'page': None
                })
        
        self.non_contained_items = non_contained
        
        # 显示结果
        self.display_non_contained_results(non_contained, outer_label, inner_labels, "当前页")
        
        # 启用删除按钮
        if non_contained:
            self.batch_delete_btn.setEnabled(True)
            self.add_to_filter_btn.setEnabled(True)
        else:
            self.batch_delete_btn.setEnabled(False)
            self.add_to_filter_btn.setEnabled(False)
    
    def detect_non_contained_range(self, outer_label, inner_labels, threshold, from_page, to_page):
        """检测范围页面未被包围的标签（后台检测）"""
        # 清空包围检测结果
        self.empty_containers = []
        self.all_results = []
        
        if not hasattr(self.parent, 'image_list') or not self.parent.image_list:
            QtWidgets.QMessageBox.warning(
                self, self.tr("警告"), self.tr("没有加载图像列表")
            )
            return
        
        total_pages = len(self.parent.image_list)
        if from_page < 1 or to_page > total_pages:
            QtWidgets.QMessageBox.warning(
                self, self.tr("警告"), 
                self.tr(f"页码范围应在 1-{total_pages} 之间")
            )
            return
        
        # 显示进度
        progress = QtWidgets.QProgressDialog(
            self.tr("正在检测未被包围的标签..."), self.tr("取消"), 
            from_page, to_page, self
        )
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setMinimumDuration(0)
        
        all_non_contained = []
        self.non_contained_items = []
        
        import json
        import os.path as osp
        
        for page_num in range(from_page, to_page + 1):
            progress.setValue(page_num)
            if progress.wasCanceled():
                break
            
            # 获取图片路径和对应的标签文件路径
            page_index = page_num - 1
            image_path = self.parent.image_list[page_index]
            
            # 获取标签文件路径
            label_file = osp.splitext(image_path)[0] + ".json"
            
            # 如果有output_dir，标签文件在output_dir中
            if hasattr(self.parent, 'output_dir') and self.parent.output_dir:
                label_file = osp.join(
                    self.parent.output_dir,
                    osp.splitext(osp.basename(image_path))[0] + ".json"
                )
            
            # 读取标签文件
            if not osp.exists(label_file):
                continue
            
            try:
                with open(label_file, 'r', encoding='utf-8') as f:
                    label_data = json.load(f)
                
                # 解析shapes
                shapes = []
                if 'shapes' in label_data:
                    for shape_data in label_data['shapes']:
                        shape_obj = type('Shape', (), {
                            'label': shape_data.get('label', ''),
                            'shape_type': shape_data.get('shape_type', 'rectangle'),
                            'points': shape_data.get('points', [])
                        })()
                        shapes.append(shape_obj)
                
                # 找出外层和内层标签
                outer_shapes = [s for s in shapes if s.label == outer_label and s.shape_type in ['rectangle', 'rotation']]
                inner_shapes = [s for s in shapes if s.label in inner_labels and s.shape_type in ['rectangle', 'rotation']]
                
                # 检测未被包围的内层标签
                for inner_shape in inner_shapes:
                    is_contained = False
                    for outer_shape in outer_shapes:
                        contained = self.check_containment_from_data(outer_shape, [inner_shape], [inner_shape.label], threshold)
                        if contained:
                            is_contained = True
                            break
                    
                    if not is_contained:
                        item = {
                            'shape': inner_shape,
                            'label': inner_shape.label,
                            'page': page_num,
                            'file_path': image_path,
                            'label_file': label_file
                        }
                        all_non_contained.append(item)
                        self.non_contained_items.append(item)
            
            except Exception as e:
                print(f"Error reading {label_file}: {e}")
                continue
        
        progress.setValue(to_page)
        
        # 显示结果
        range_text = f"第 {from_page}-{to_page} 页" if from_page != to_page else f"第 {from_page} 页"
        self.display_non_contained_results(all_non_contained, outer_label, inner_labels, range_text)
        
        # 启用删除按钮
        if all_non_contained:
            self.batch_delete_btn.setEnabled(True)
            self.add_to_filter_btn.setEnabled(True)
        else:
            self.batch_delete_btn.setEnabled(False)
            self.add_to_filter_btn.setEnabled(False)
    
    def display_non_contained_results(self, non_contained, outer_label, inner_labels, range_text):
        """显示未被包围的检测结果"""
        text = []
        text.append(self.tr(f"非包围检测设置:"))
        text.append(self.tr(f"  外层标签: {outer_label}"))
        text.append(self.tr(f"  内层标签: {', '.join(inner_labels)}"))
        text.append(self.tr(f"  包围阈值: {self.non_threshold_spinbox.value()}%"))
        text.append(self.tr(f"  检测范围: {range_text}"))
        text.append("")
        text.append(self.tr(f"检测结果:"))
        text.append(self.tr(f"  未被包围的标签: {len(non_contained)} 个"))
        
        # 按标签类型统计
        label_counts = {}
        for item in non_contained:
            label = item['label']
            label_counts[label] = label_counts.get(label, 0) + 1
        
        if label_counts:
            text.append("")
            text.append(self.tr("  按标签类型统计:"))
            for label, count in sorted(label_counts.items()):
                text.append(self.tr(f"    - {label}: {count} 个"))
        
        # 列出所有未被包围标签所在的页码
        if non_contained:
            pages = set()
            for item in non_contained:
                if item.get('page'):
                    pages.add(item['page'])
            
            if pages:
                sorted_pages = sorted(pages)
                text.append("")
                text.append(self.tr(f"  未被包围标签所在页码: {', '.join(map(str, sorted_pages))}"))
        
        text.append("")
        text.append(self.tr("详细信息:"))
        text.append("-" * 50)
        
        # 详细列表
        for i, item in enumerate(non_contained, 1):
            shape = item['shape']
            label = item['label']
            page = item.get('page')
            
            # 获取坐标
            points = shape.points
            if isinstance(points[0], (list, tuple)):
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
            else:
                x_coords = [p.x() for p in points]
                y_coords = [p.y() for p in points]
            
            x1, x2 = min(x_coords), max(x_coords)
            y1, y2 = min(y_coords), max(y_coords)
            
            page_info = f"第 {page} 页 - " if page else ""
            text.append(self.tr(f"\n[{i}] {page_info}{label} (位置: {int(x1)},{int(y1)} - {int(x2)},{int(y2)})"))
            text.append(self.tr(f"  ⚠️ 未被任何 '{outer_label}' 标签包围"))
        
        self.result_text.setPlainText('\n'.join(text))

    
    def add_results_to_filter(self):
        """将检测结果中有问题的页面添加到文件过滤器"""
        # 收集所有有问题的页面
        problem_pages = set()
        
        # 从空包围结果中收集
        for item in self.empty_containers:
            if isinstance(item, dict) and item.get('page'):
                problem_pages.add(item['page'])
        
        # 从非包围结果中收集
        for item in self.non_contained_items:
            if isinstance(item, dict) and item.get('page'):
                problem_pages.add(item['page'])
        
        if not problem_pages:
            QtWidgets.QMessageBox.information(
                self, self.tr("提示"), 
                self.tr("没有检测到有问题的页面")
            )
            return
        
        # 获取对应的文件名
        problem_files = []
        for page in sorted(problem_pages):
            page_index = page - 1
            if page_index < len(self.parent.image_list):
                problem_files.append(self.parent.image_list[page_index])
        
        if not problem_files:
            return
        
        # 创建自定义过滤配置
        filter_config = {
            'mode': 'custom_files',
            'custom_files': problem_files
        }
        
        # 应用过滤
        if hasattr(self.parent, 'apply_file_filter'):
            self.parent.apply_file_filter(filter_config)
        else:
            QtWidgets.QMessageBox.warning(
                self, self.tr("错误"), 
                self.tr("无法访问文件过滤功能")
            )

    
    def reset_filter(self):
        """重置文件过滤器，显示全部页面"""
        # 创建无过滤配置
        filter_config = {
            'mode': 'none'
        }
        
        # 应用过滤
        if hasattr(self.parent, 'apply_file_filter'):
            self.parent.apply_file_filter(filter_config)
        else:
            QtWidgets.QMessageBox.warning(
                self, self.tr("错误"), 
                self.tr("无法访问文件过滤功能")
            )
