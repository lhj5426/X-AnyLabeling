"""
掩膜生成对话框
用于配置和生成文字区域掩膜
"""

import os
import sys
import cv2
import json
import numpy as np
from pathlib import Path
from PyQt5 import QtCore, QtWidgets, QtGui


class MaskGeneratorWorker(QtCore.QThread):
    """掩膜生成工作线程 - 直接调用CTD模型"""
    # 信号
    progress = QtCore.pyqtSignal(str)  # 进度信息
    finished = QtCore.pyqtSignal(dict)  # 完成信号，返回结果字典
    error = QtCore.pyqtSignal(str)  # 错误信号

    def __init__(self, image_path, yolo_labels, model_path, output_path, params, save_png=False, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.yolo_labels = yolo_labels
        self.model_path = model_path
        self.output_path = output_path
        self.params = params
        self.save_png = save_png  # 是否保存PNG文件

    def run(self):
        """在后台线程执行CTD模型"""
        try:
            self.progress.emit("[CTD] 开始生成掩膜...")
            self.progress.emit(f"[CTD] 图片路径: {self.image_path}")
            self.progress.emit(f"[CTD] 模型路径: {self.model_path}")
            self.progress.emit(f"[CTD] YOLO标签数量: {len(self.yolo_labels)}")

            # 添加BallonsTranslator路径
            ballons_path = r"D:\BallonsTranslator\BallonsTranslator"
            if ballons_path not in sys.path:
                sys.path.insert(0, ballons_path)

            # 导入CTD模块
            self.progress.emit("[CTD] 导入CTD模块...")
            from modules.textdetector.ctd import CTDModel
            import torch

            # 加载模型
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            self.progress.emit(f"[CTD] 加载模型... (设备: {device})")
            model = CTDModel(self.model_path, detect_size=1024, device=device)
            self.progress.emit("[CTD] 模型加载完成")

            # 读取图片（使用PIL支持中文路径，然后转换为OpenCV格式）
            self.progress.emit("[CTD] 读取图片...")
            try:
                from PIL import Image
                # PIL可以正确处理中文路径
                pil_img = Image.open(self.image_path)
                # 转换为numpy数组
                img = np.array(pil_img)
                # 确保图像为3通道BGR格式，以适配CTD模型
                if len(img.shape) == 2:
                    # 灰度图转BGR
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                elif len(img.shape) == 3:
                    if img.shape[2] == 4:
                        # RGBA转BGR
                        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                    elif img.shape[2] == 3:
                        # RGB (PIL默认) 转BGR
                        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

                if img is None or img.size == 0:
                    self.error.emit(f"无法读取图片: {self.image_path}")
                    return
            except Exception as e:
                self.error.emit(f"读取图片失败: {str(e)}")
                return

            img_h, img_w = img.shape[:2]
            self.progress.emit(f"[CTD] 图片尺寸: {img_w}x{img_h}")

            # 创建掩膜图
            mask = np.zeros((img_h, img_w), dtype=np.uint8)

            # 获取参数
            size_scale = self.params.get('size_scale', 1.0)
            extend_top = self.params.get('extend_top', 0)
            extend_bottom = self.params.get('extend_bottom', 0)
            extend_left = self.params.get('extend_left', 0)
            extend_right = self.params.get('extend_right', 0)

            # 1. 全图文字检测 - 获取高质量文字掩膜（提供完整上下文）
            self.progress.emit("[CTD] 正在进行全图文字检测...")
            mask_full, mask_refined_full, _ = model(img, refine_mode=0, keep_undetected_mask=False)

            if mask_refined_full is None or mask_refined_full.size == 0:
                self.progress.emit("[CTD] ⚠️ 未检测到文字区域")
                mask = np.zeros((img_h, img_w), dtype=np.uint8)
            else:
                # 确保掩膜大小对齐
                if mask_refined_full.shape[:2] != (img_h, img_w):
                    mask_refined_full = cv2.resize(mask_refined_full, (img_w, img_h))

                # 2. 针对每个标注框进行局部优化和轮廓提取
                self.progress.emit(f"[CTD] 正在处理 {len(self.yolo_labels)} 个标注区域的掩膜连通性...")
                final_contours = []
                
                # 准备形态学内核，用于粘合离散的字符笔画
                kernel_close = np.ones((5, 5), np.uint8)
                
                for idx, label_data in enumerate(self.yolo_labels):
                    x_center, y_center, width, height = label_data[1:]
                    x1 = int((x_center - width / 2) * img_w)
                    y1 = int((y_center - height / 2) * img_h)
                    x2 = int((x_center + width / 2) * img_w)
                    y2 = int((y_center + height / 2) * img_h)
                    
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(img_w, x2), min(img_h, y2)
                    
                    if x2 <= x1 or y2 <= y1:
                        continue

                    # 提取该区域的掩膜
                    region_mask = mask_refined_full[y1:y2, x1:x2].copy()
                    
                    # 应用闭运算：粘合字符笔画，减少碎片多边形
                    region_mask = cv2.morphologyEx(region_mask, cv2.MORPH_CLOSE, kernel_close)
                    
                    # 应用参数：缩放/延伸（在这里应用以确保局部精度）
                    if size_scale != 1.0 or any([extend_top, extend_bottom, extend_left, extend_right]):
                        # 转换为大掩膜或在局部处理（为了简单，后续在全局统一后处理，此处仅提取初始轮廓）
                        pass

                    # 将处理后的掩膜贴回主掩膜（用于PNG导出）
                    mask[y1:y2, x1:x2] = np.maximum(mask[y1:y2, x1:x2], region_mask)

            # 对掩膜进行后处理：应用膨胀操作来扩展掩膜区域
            # 1. 根据size_scale计算膨胀量（使用独立工具的算法）
            if size_scale != 1.0:
                if size_scale > 1.0:
                    # 膨胀：kernel_size = int((factor - 1.0) * 10) + 1
                    kernel_size = int((size_scale - 1.0) * 10) + 1
                    self.progress.emit(f"[CTD] 整体大小 {int(size_scale*100)}%，膨胀核大小 {kernel_size}")
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                    mask = cv2.dilate(mask, kernel, iterations=1)
                else:
                    # 腐蚀：kernel_size = int((1.0 - factor) * 10) + 1
                    kernel_size = int((1.0 - size_scale) * 10) + 1
                    self.progress.emit(f"[CTD] 整体大小 {int(size_scale*100)}%，腐蚀核大小 {kernel_size}")
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                    mask = cv2.erode(mask, kernel, iterations=1)

            # 2. 应用方向延伸参数（使用像素移位方法）
            if extend_top > 0 or extend_bottom > 0 or extend_left > 0 or extend_right > 0:
                self.progress.emit(f"[CTD] 应用方向延伸: 上{extend_top} 下{extend_bottom} 左{extend_left} 右{extend_right}")
                h, w = mask.shape
                result_mask = mask.copy()

                # 向上单向延伸
                if extend_top > 0:
                    for i in range(1, int(extend_top) + 1):
                        shifted = np.zeros_like(mask)
                        if i < h:
                            shifted[:-i, :] = mask[i:, :]
                            result_mask = np.maximum(result_mask, shifted)

                # 向下单向延伸
                if extend_bottom > 0:
                    for i in range(1, int(extend_bottom) + 1):
                        shifted = np.zeros_like(mask)
                        if i < h:
                            shifted[i:, :] = mask[:-i, :]
                            result_mask = np.maximum(result_mask, shifted)

                # 向左单向延伸
                if extend_left > 0:
                    for i in range(1, int(extend_left) + 1):
                        shifted = np.zeros_like(mask)
                        if i < w:
                            shifted[:, :-i] = mask[:, i:]
                            result_mask = np.maximum(result_mask, shifted)

                # 向右单向延伸
                if extend_right > 0:
                    for i in range(1, int(extend_right) + 1):
                        shifted = np.zeros_like(mask)
                        if i < w:
                            shifted[:, i:] = mask[:, :-i]
                            result_mask = np.maximum(result_mask, shifted)

                mask = result_mask
                self.progress.emit(f"[CTD] ✅ 方向延伸完成")

            # 根据格式生成掩膜图（仅在需要导出PNG时）
            if self.save_png:
                self.progress.emit(f"[CTD] 生成掩膜PNG...")
                mask_format = self.params.get('format', 'ballons')
                text_color = self.params.get('text_color', [255, 255, 255])  # RGB
                text_alpha = self.params.get('text_alpha', 255)  # 0-255

                if mask_format == 'imagetrans':
                    self.progress.emit(f"[CTD] 使用ImageTrans格式（透明背景 + RGB{text_color}, Alpha={text_alpha}）")
                    # ImageTrans格式：透明背景 + 自定义颜色文字区域
                    mask_rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)
                    mask_indices = mask > 127
                    mask_rgba[mask_indices] = [text_color[2], text_color[1], text_color[0], text_alpha]  # BGRA
                    # 使用imencode支持中文路径
                    _, buffer = cv2.imencode('.png', mask_rgba)
                    buffer.tofile(self.output_path)
                    self.progress.emit(f"[CTD] ImageTrans掩膜已保存: {self.output_path}")
                else:
                    self.progress.emit(f"[CTD] 使用BallonsTranslator格式（黑背景 + 白色文字）")
                    # 使用imencode支持中文路径
                    _, buffer = cv2.imencode('.png', mask)
                    buffer.tofile(self.output_path)
                    self.progress.emit(f"[CTD] BallonsTranslator掩膜已保存: {self.output_path}")
            else:
                self.progress.emit(f"[生成] 跳过PNG保存，仅提取轮廓数据...")

            # 5. 提取轮廓（用于多边形显示）
            self.progress.emit(f"[CTD] 正在从合并掩膜中提取最终多边形...")
            contours = []
            
            # 最终全局掩膜后处理：使用闭运算粘合碎片
            mask_binary = (mask > 127).astype(np.uint8)
            kernel_glue = np.ones((5, 5), np.uint8)
            mask_glued = cv2.morphologyEx(mask_binary, cv2.MORPH_CLOSE, kernel_glue)
            
            # 额外的膨胀（根据用户参数）
            dilate_kernel_size = self.params.get('dilate_kernel_size', 3)
            if dilate_kernel_size > 0:
                kernel_dilate = np.ones((dilate_kernel_size, dilate_kernel_size), np.uint8)
                mask_glued = cv2.dilate(mask_glued, kernel_dilate, iterations=1)

            contour_list, _ = cv2.findContours(mask_glued, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            self.progress.emit(f"[CTD] 找到 {len(contour_list)} 个聚合文字块轮廓")

            for idx, cnt in enumerate(contour_list):
                # 过滤太小的噪点
                if cv2.contourArea(cnt) < 15:
                    continue
                    
                # 拟合平滑多边形
                epsilon = 0.005 * cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, epsilon, True)
                
                points = [[float(point[0][0]), float(point[0][1])] for point in approx]
                if len(points) >= 3:
                    contours.append(points)

            self.progress.emit(f"[CTD] 提取了 {len(contours)} 个有效多边形轮廓")
            self.progress.emit(f"[CTD] ✅ 掩膜生成完成！")

            # 返回结果
            result = {
                "success": True,
                "mask_path": self.output_path,
                "contours": contours,
                "device": device
            }
            self.finished.emit(result)

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self.progress.emit(f"[CTD] ❌ 错误: {str(e)}")
            self.progress.emit(error_trace)
            self.error.emit(f"{str(e)}\n{error_trace}")


class MaskGeneratorDialog(QtWidgets.QDialog):
    """掩膜生成配置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.ctd_model = None
        self.ctd_model_path = None

        # 设置为非模态窗口
        self.setWindowModality(QtCore.Qt.NonModal)

        # 添加最小化按钮
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowMinimizeButtonHint)

        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle(self.tr("掩膜生成设置"))
        self.setMinimumWidth(650)
        self.setMinimumHeight(700)
        self.resize(650, 720)

        # 主布局
        main_layout = QtWidgets.QVBoxLayout()

        # === CTD模型配置 ===
        model_group = QtWidgets.QGroupBox(self.tr("CTD模型配置"))
        model_layout = QtWidgets.QVBoxLayout()

        # 模型路径选择
        model_path_layout = QtWidgets.QHBoxLayout()
        model_path_layout.addWidget(QtWidgets.QLabel(self.tr("模型路径:")))
        self.model_path_edit = QtWidgets.QLineEdit()
        self.model_path_edit.setPlaceholderText(self.tr("默认: BallonsTranslator/data/models/comictextdetector.pt"))
        self.model_path_edit.setReadOnly(True)
        self.model_path_edit.setMinimumHeight(28)
        model_path_layout.addWidget(self.model_path_edit, 1)

        browse_btn = QtWidgets.QPushButton(self.tr("浏览..."))
        browse_btn.setMinimumHeight(28)
        browse_btn.clicked.connect(self.browse_model_path)
        model_path_layout.addWidget(browse_btn)

        reset_btn = QtWidgets.QPushButton(self.tr("重置"))
        reset_btn.setMinimumHeight(28)
        reset_btn.clicked.connect(self.reset_model_path)
        model_path_layout.addWidget(reset_btn)

        model_layout.addLayout(model_path_layout)

        model_group.setLayout(model_layout)
        main_layout.addWidget(model_group)

        # === 生成范围 ===
        scope_group = QtWidgets.QGroupBox(self.tr("生成范围"))
        scope_layout = QtWidgets.QVBoxLayout()

        self.current_page_radio = QtWidgets.QRadioButton(self.tr("当前页面"))
        self.current_page_radio.setChecked(True)
        self.all_pages_radio = QtWidgets.QRadioButton(self.tr("所有页面"))

        scope_layout.addWidget(self.current_page_radio)
        scope_layout.addWidget(self.all_pages_radio)

        # 添加分隔线
        scope_layout.addSpacing(10)
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        scope_layout.addWidget(separator)
        scope_layout.addSpacing(5)

        # 清空旧多边形选项
        self.clear_old_polygons_checkbox = QtWidgets.QCheckBox(self.tr("生成前清空旧多边形"))
        self.clear_old_polygons_checkbox.setChecked(True)  # 默认勾选
        self.clear_old_polygons_checkbox.setToolTip(self.tr("勾选后，每次生成多边形前会自动删除画布上已有的多边形标注"))
        scope_layout.addWidget(self.clear_old_polygons_checkbox)

        # 排除标签设置
        scope_layout.addSpacing(10)
        exclude_label_layout = QtWidgets.QHBoxLayout()
        exclude_label_layout.addWidget(QtWidgets.QLabel(self.tr("排除标签:")))
        self.exclude_labels_edit = QtWidgets.QLineEdit()
        self.exclude_labels_edit.setPlaceholderText(self.tr("例如: other,background (用逗号分隔)"))
        self.exclude_labels_edit.setText("other")  # 默认排除other
        self.exclude_labels_edit.setToolTip(self.tr("生成掩膜时会跳过这些标签的标注框，多个标签用英文逗号分隔"))
        exclude_label_layout.addWidget(self.exclude_labels_edit, 1)
        scope_layout.addLayout(exclude_label_layout)

        scope_group.setLayout(scope_layout)
        main_layout.addWidget(scope_group)

        # === 掩膜参数调整 ===
        param_group = QtWidgets.QGroupBox(self.tr("掩膜参数"))
        param_layout = QtWidgets.QVBoxLayout()

        # 添加说明文字
        param_hint = QtWidgets.QLabel(self.tr("💡 提示：整体大小>100%膨胀掩膜，<100%收缩掩膜；方向延伸额外扩展边界"))
        param_hint.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        param_hint.setWordWrap(True)
        param_layout.addWidget(param_hint)

        param_form = QtWidgets.QFormLayout()

        # 整体大小调整
        size_layout = QtWidgets.QHBoxLayout()
        self.size_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.size_slider.setMinimum(20)
        self.size_slider.setMaximum(500)
        self.size_slider.setValue(100)
        self.size_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.size_slider.setTickInterval(50)
        self.size_slider.valueChanged.connect(self.update_size_label)

        self.size_label = QtWidgets.QLabel("100%")
        size_layout.addWidget(self.size_slider, 1)
        size_layout.addWidget(self.size_label)
        param_form.addRow(self.tr("整体大小:"), size_layout)

        # 方向延伸
        self.extend_top_spin = QtWidgets.QSpinBox()
        self.extend_top_spin.setRange(0, 100)
        self.extend_top_spin.setSuffix(" px")
        self.extend_top_spin.setToolTip(self.tr("向上扩展掩膜边界（像素）"))
        param_form.addRow(self.tr("向上延伸:"), self.extend_top_spin)

        self.extend_bottom_spin = QtWidgets.QSpinBox()
        self.extend_bottom_spin.setRange(0, 100)
        self.extend_bottom_spin.setSuffix(" px")
        self.extend_bottom_spin.setToolTip(self.tr("向下扩展掩膜边界（像素）"))
        param_form.addRow(self.tr("向下延伸:"), self.extend_bottom_spin)

        self.extend_left_spin = QtWidgets.QSpinBox()
        self.extend_left_spin.setRange(0, 100)
        self.extend_left_spin.setSuffix(" px")
        self.extend_left_spin.setToolTip(self.tr("向左扩展掩膜边界（像素）"))
        param_form.addRow(self.tr("向左延伸:"), self.extend_left_spin)

        self.extend_right_spin = QtWidgets.QSpinBox()
        self.extend_right_spin.setRange(0, 100)
        self.extend_right_spin.setSuffix(" px")
        self.extend_right_spin.setToolTip(self.tr("向右扩展掩膜边界（像素）"))
        param_form.addRow(self.tr("向右延伸:"), self.extend_right_spin)

        # 膨胀核大小（用于轮廓提取）
        self.dilate_kernel_spin = QtWidgets.QSpinBox()
        self.dilate_kernel_spin.setRange(0, 15)
        self.dilate_kernel_spin.setValue(3)
        self.dilate_kernel_spin.setSuffix(" px")
        self.dilate_kernel_spin.setToolTip(self.tr("膨胀核大小，用于扩展轮廓边界（0=不膨胀，推荐3-5）"))
        param_form.addRow(self.tr("轮廓膨胀:"), self.dilate_kernel_spin)

        param_layout.addLayout(param_form)

        param_group.setLayout(param_layout)
        main_layout.addWidget(param_group)

        # === 掩膜颜色设置 ===
        color_group = QtWidgets.QGroupBox(self.tr("掩膜输出格式"))
        color_layout = QtWidgets.QVBoxLayout()

        # 格式选择
        format_label = QtWidgets.QLabel(self.tr("掩膜格式:"))
        format_label.setStyleSheet("font-weight: bold;")
        color_layout.addWidget(format_label)

        self.ballons_format_radio = QtWidgets.QRadioButton(
            self.tr("BallonsTranslator格式（黑背景+白色文字区域）")
        )
        self.ballons_format_radio.setChecked(True)
        self.ballons_format_radio.toggled.connect(self.on_format_changed)
        color_layout.addWidget(self.ballons_format_radio)

        self.imagetrans_format_radio = QtWidgets.QRadioButton(
            self.tr("ImageTrans格式（透明背景+自定义颜色文字区域）")
        )
        self.imagetrans_format_radio.toggled.connect(self.on_format_changed)
        color_layout.addWidget(self.imagetrans_format_radio)

        color_layout.addSpacing(10)

        # 颜色设置（仅ImageTrans格式可用）
        self.color_settings_widget = QtWidgets.QWidget()
        color_settings_layout = QtWidgets.QVBoxLayout()
        color_settings_layout.setContentsMargins(20, 0, 0, 0)

        # 掩膜颜色
        mask_color_layout = QtWidgets.QHBoxLayout()
        mask_color_layout.addWidget(QtWidgets.QLabel(self.tr("文字区域颜色:")))
        self.mask_color_btn = QtWidgets.QPushButton()
        self.mask_color = QtGui.QColor(255, 255, 255)  # 默认白色
        self.update_color_button()
        self.mask_color_btn.clicked.connect(self.choose_mask_color)
        mask_color_layout.addWidget(self.mask_color_btn)
        mask_color_layout.addStretch()
        color_settings_layout.addLayout(mask_color_layout)

        # 透明度（仅ImageTrans格式）
        opacity_layout = QtWidgets.QHBoxLayout()
        opacity_layout.addWidget(QtWidgets.QLabel(self.tr("透明度:")))
        self.opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(100)  # 默认不透明
        self.opacity_slider.valueChanged.connect(self.update_opacity_label)
        self.opacity_label = QtWidgets.QLabel("100%")
        opacity_layout.addWidget(self.opacity_slider, 1)
        opacity_layout.addWidget(self.opacity_label)
        color_settings_layout.addLayout(opacity_layout)

        self.color_settings_widget.setLayout(color_settings_layout)
        self.color_settings_widget.setEnabled(False)  # 默认禁用
        color_layout.addWidget(self.color_settings_widget)

        color_group.setLayout(color_layout)
        main_layout.addWidget(color_group)

        # === 操作按钮 ===
        button_layout = QtWidgets.QHBoxLayout()

        self.generate_btn = QtWidgets.QPushButton(self.tr("CTD生成多边形"))
        self.generate_btn.setMinimumHeight(35)
        self.generate_btn.setToolTip(self.tr("使用CTD模型在画布上和JSON里生成多边形（不导出PNG）"))
        self.generate_btn.clicked.connect(self.generate_mask)
        button_layout.addWidget(self.generate_btn)

        direct_box_btn = QtWidgets.QPushButton(self.tr("从标注框生成"))
        direct_box_btn.setMinimumHeight(35)
        direct_box_btn.setToolTip(self.tr("直接从JSON矩形框生成掩膜（不使用CTD）"))
        direct_box_btn.clicked.connect(self.generate_mask_from_boxes)
        button_layout.addWidget(direct_box_btn)

        ctd_direct_btn = QtWidgets.QPushButton(self.tr("使用CTD生成"))
        ctd_direct_btn.setMinimumHeight(35)
        ctd_direct_btn.setToolTip(self.tr("从JSON标注框使用CTD模型生成PNG掩膜（不生成多边形）"))
        ctd_direct_btn.clicked.connect(self.generate_mask_with_ctd_direct)
        button_layout.addWidget(ctd_direct_btn)

        export_btn = QtWidgets.QPushButton(self.tr("导出PNG"))
        export_btn.setMinimumHeight(35)
        export_btn.setToolTip(self.tr("将多边形导出为PNG图片"))
        export_btn.clicked.connect(self.export_mask)
        button_layout.addWidget(export_btn)

        close_btn = QtWidgets.QPushButton(self.tr("关闭"))
        close_btn.setMinimumHeight(35)
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        main_layout.addLayout(button_layout)

        # 状态显示
        self.status_label = QtWidgets.QLabel("")
        main_layout.addWidget(self.status_label)

        # 实时日志输出窗口
        log_group = QtWidgets.QGroupBox(self.tr("执行日志"))
        log_layout = QtWidgets.QVBoxLayout()

        # 进度条（放在日志窗口内）
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMinimumHeight(25)
        self.progress_bar.setVisible(False)
        log_layout.addWidget(self.progress_bar)

        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("font-family: Consolas, monospace; font-size: 9pt;")
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        self.setLayout(main_layout)

        # Worker线程
        self.worker = None

    def append_log(self, message):
        """添加日志到文本框"""
        self.log_text.append(message)
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def update_size_label(self, value):
        """更新大小标签"""
        self.size_label.setText(f"{value}%")

    def update_opacity_label(self, value):
        """更新透明度标签"""
        self.opacity_label.setText(f"{value}%")

    def on_format_changed(self):
        """格式选择变更时的处理"""
        # ImageTrans格式时启用颜色设置
        is_imagetrans = self.imagetrans_format_radio.isChecked()
        self.color_settings_widget.setEnabled(is_imagetrans)

    def update_color_button(self):
        """更新颜色按钮显示"""
        color_str = self.mask_color.name()
        self.mask_color_btn.setStyleSheet(
            f"background-color: {color_str}; min-width: 60px; min-height: 25px;"
        )

    def choose_mask_color(self):
        """选择掩膜颜色"""
        color = QtWidgets.QColorDialog.getColor(
            self.mask_color, self, self.tr("选择文字区域颜色")
        )
        if color.isValid():
            self.mask_color = color
            self.update_color_button()

    def browse_model_path(self):
        """浏览选择模型路径"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("选择CTD模型文件"),
            "",
            self.tr("模型文件 (*.pt *.pth)")
        )
        if file_path:
            self.model_path_edit.setText(file_path)
            self.ctd_model_path = file_path

    def reset_model_path(self):
        """重置模型路径为默认"""
        self.model_path_edit.clear()
        self.ctd_model_path = None

    def get_default_model_path(self):
        """获取默认模型路径"""
        # 默认路径：BallonsTranslator目录下
        default_path = r"D:\BallonsTranslator\BallonsTranslator\data\models\comictextdetector.pt"
        if os.path.exists(default_path):
            return default_path
        return None

    def generate_mask(self):
        """生成掩膜（从JSON标注框）"""
        if self.current_page_radio.isChecked():
            self.generate_current_mask()
        else:
            self.generate_all_masks()

    def generate_mask_with_ctd_direct(self):
        """使用CTD在JSON标注框内生成PNG掩膜"""
        if self.current_page_radio.isChecked():
            self.generate_mask_with_ctd_direct_current()
        else:
            self.generate_mask_with_ctd_direct_all()

    def generate_mask_with_ctd_direct_current(self):
        """使用CTD在JSON标注框内生成PNG掩膜（当前页面）"""
        try:
            # 清空日志
            self.log_text.clear()
            self.append_log("[CTD生成] 开始从JSON标注框使用CTD生成PNG掩膜...")

            # 获取当前图片路径
            if not self.parent_widget or not hasattr(self.parent_widget, 'filename'):
                self.append_log("[错误] 无法获取当前图片信息！")
                self.status_label.setText(self.tr("❌ 错误：无法获取图片信息"))
                return

            image_path = self.parent_widget.filename
            if not image_path:
                self.append_log("[错误] 当前没有打开的图片！")
                self.status_label.setText(self.tr("❌ 错误：没有打开图片"))
                return

            self.append_log(f"[图片] {image_path}")

            # 读取JSON文件
            json_path = os.path.splitext(image_path)[0] + '.json'
            if not os.path.exists(json_path):
                self.append_log("[错误] 未找到JSON文件！")
                self.status_label.setText(self.tr("❌ 错误：未找到JSON文件"))
                return

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            shapes = data.get('shapes', [])
            if not shapes:
                self.append_log("[错误] JSON中没有标注！")
                self.status_label.setText(self.tr("❌ 错误：JSON中没有标注"))
                return

            # 获取排除标签列表
            exclude_labels_text = self.exclude_labels_edit.text().strip()
            exclude_labels = []
            if exclude_labels_text:
                exclude_labels = [label.strip() for label in exclude_labels_text.split(',') if label.strip()]
                self.append_log(f"[过滤] 排除标签: {exclude_labels}")

            # 提取rotation和rectangle类型的标注
            boxes = []
            skipped_count = 0
            for shape in shapes:
                shape_label = shape.get('label', '')

                # 检查是否需要排除此标签
                if exclude_labels and shape_label in exclude_labels:
                    skipped_count += 1
                    continue

                if shape.get('shape_type') in ['rotation', 'rectangle']:
                    points = shape.get('points', [])
                    if len(points) >= 2:
                        boxes.append(points)

            if skipped_count > 0:
                self.append_log(f"[过滤] 已跳过 {skipped_count} 个排除标签的标注")

            if not boxes:
                self.append_log("[错误] 没有找到矩形或旋转框标注！")
                self.status_label.setText(self.tr("❌ 错误：没有矩形标注"))
                return

            self.append_log(f"[标注框] 找到 {len(boxes)} 个矩形框")

            # 读取图片尺寸
            try:
                from PIL import Image
                pil_img = Image.open(image_path)
                img_w, img_h = pil_img.size
            except Exception as e:
                self.append_log(f"[错误] 无法读取图片: {str(e)}")
                self.status_label.setText(self.tr(f"❌ 读取图片失败"))
                return

            self.append_log(f"[尺寸] {img_w}x{img_h}")

            # 转换为YOLO格式
            yolo_labels = []
            for points in boxes:
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)

                # 归一化为YOLO格式
                x_center = (x_min + x_max) / 2 / img_w
                y_center = (y_min + y_max) / 2 / img_h
                width = (x_max - x_min) / img_w
                height = (y_max - y_min) / img_h

                yolo_labels.append([0, x_center, y_center, width, height])

            self.append_log(f"[YOLO] 转换了 {len(yolo_labels)} 个YOLO标签")

            # 准备输出路径
            image_dir = os.path.dirname(image_path)
            image_name = os.path.splitext(os.path.basename(image_path))[0]
            mask_dir = os.path.join(image_dir, "mask")
            os.makedirs(mask_dir, exist_ok=True)
            output_path = os.path.join(mask_dir, f"{image_name}.png")

            self.append_log(f"[输出] {output_path}")

            # 准备参数
            is_imagetrans = self.imagetrans_format_radio.isChecked()
            params = {
                'size_scale': float(self.size_slider.value()) / 100.0,
                'extend_top': self.extend_top_spin.value(),
                'extend_bottom': self.extend_bottom_spin.value(),
                'extend_left': self.extend_left_spin.value(),
                'extend_right': self.extend_right_spin.value(),
                'format': 'imagetrans' if is_imagetrans else 'ballons',
                'text_color': [self.mask_color.red(), self.mask_color.green(), self.mask_color.blue()],
                'text_alpha': int(self.opacity_slider.value() * 2.55),
                'dilate_kernel_size': self.dilate_kernel_spin.value(),  # 膨胀核大小
                'direct_ctd': True  # 标记为直接CTD模式
            }

            # 获取模型路径
            model_path = self.ctd_model_path or self.get_default_model_path()

            self.append_log(f"[CTD生成] 将在 {len(yolo_labels)} 个标注框内使用CTD检测...")

            # 创建Worker线程
            self.worker = MaskGeneratorWorker(
                image_path,
                yolo_labels,  # 传入所有标注框
                model_path,
                output_path,
                params,
                save_png=True  # 直接生成PNG文件
            )
            self.worker.progress.connect(self.append_log)
            self.worker.finished.connect(lambda result: self.on_ctd_direct_finished(result, output_path))
            self.worker.error.connect(self.on_mask_generation_error)

            # 禁用按钮
            self.generate_btn.setEnabled(False)
            self.status_label.setText(self.tr("⏳ 正在使用CTD检测..."))

            # 启动线程
            self.worker.start()

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.append_log(f"[错误] {str(e)}")
            self.append_log(error_detail)
            self.status_label.setText(self.tr(f"❌ 准备失败: {str(e)}"))

    def generate_mask_with_ctd_direct_all(self):
        """使用CTD批量生成所有页面的PNG掩膜"""
        try:
            # 清空日志
            self.log_text.clear()
            self.append_log("[批量CTD] 开始批量使用CTD生成所有页面PNG...")

            # 获取所有图片列表
            if not self.parent_widget or not hasattr(self.parent_widget, 'image_list'):
                self.append_log("[错误] 无法获取图片列表！")
                self.status_label.setText(self.tr("❌ 错误：无法获取图片列表"))
                return

            image_list = self.parent_widget.image_list
            if not image_list:
                self.append_log("[错误] 图片列表为空！")
                self.status_label.setText(self.tr("❌ 错误：图片列表为空"))
                return

            total = len(image_list)
            self.append_log(f"[批量] 共 {total} 个文件需要处理")

            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(0)

            # 禁用按钮
            self.generate_btn.setEnabled(False)

            # 获取参数
            is_imagetrans = self.imagetrans_format_radio.isChecked()
            params = {
                'size_scale': float(self.size_slider.value()) / 100.0,
                'extend_top': self.extend_top_spin.value(),
                'extend_bottom': self.extend_bottom_spin.value(),
                'extend_left': self.extend_left_spin.value(),
                'extend_right': self.extend_right_spin.value(),
                'format': 'imagetrans' if is_imagetrans else 'ballons',
                'text_color': [self.mask_color.red(), self.mask_color.green(), self.mask_color.blue()],
                'text_alpha': int(self.opacity_slider.value() * 2.55),
                'dilate_kernel_size': self.dilate_kernel_spin.value()  # 膨胀核大小
            }

            model_path = self.ctd_model_path or self.get_default_model_path()

            # 预先加载CTD模型（只加载一次）
            self.append_log(f"[CTD] 加载模型: {model_path}")
            try:
                import sys
                import torch

                # 添加BallonsTranslator路径
                ballons_path = r"D:\BallonsTranslator\BallonsTranslator"
                if ballons_path not in sys.path:
                    sys.path.insert(0, ballons_path)
                    self.append_log(f"[CTD] 添加模块路径: {ballons_path}")

                # 导入CTD模块
                from modules.textdetector.ctd import CTDModel

                # 加载模型
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                ctd_model = CTDModel(model_path, detect_size=1024, device=device)
                self.append_log(f"[CTD] 模型加载成功，设备: {device}")
            except Exception as e:
                import traceback
                self.append_log(f"[错误] CTD模型加载失败: {str(e)}")
                self.append_log(traceback.format_exc())
                self.progress_bar.setVisible(False)
                self.generate_btn.setEnabled(True)
                self.status_label.setText(self.tr(f"❌ CTD模型加载失败"))
                return

            success_count = 0
            skip_count = 0
            error_count = 0

            # 批量处理每个图片
            for idx, image_path in enumerate(image_list):
                self.append_log(f"\n[{idx+1}/{total}] 处理: {os.path.basename(image_path)}")
                self.progress_bar.setValue(idx + 1)
                QtWidgets.QApplication.processEvents()

                try:
                    # 检查JSON文件
                    json_path = os.path.splitext(image_path)[0] + '.json'
                    if not os.path.exists(json_path):
                        self.append_log(f"  [跳过] 未找到JSON文件")
                        skip_count += 1
                        continue

                    # 读取JSON
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    shapes = data.get('shapes', [])
                    if not shapes:
                        self.append_log(f"  [跳过] JSON中没有标注")
                        skip_count += 1
                        continue

                    # 提取rotation和rectangle类型的标注
                    boxes = []
                    for shape in shapes:
                        if shape.get('shape_type') in ['rotation', 'rectangle']:
                            points = shape.get('points', [])
                            if len(points) >= 2:
                                boxes.append(points)

                    if not boxes:
                        self.append_log(f"  [跳过] 没有矩形或旋转框标注")
                        skip_count += 1
                        continue

                    # 读取图片尺寸
                    from PIL import Image
                    pil_img = Image.open(image_path)
                    img_w, img_h = pil_img.size

                    # 转换为YOLO格式
                    yolo_labels = []
                    for points in boxes:
                        x_coords = [p[0] for p in points]
                        y_coords = [p[1] for p in points]
                        x_min, x_max = min(x_coords), max(x_coords)
                        y_min, y_max = min(y_coords), max(y_coords)

                        x_center = (x_min + x_max) / 2 / img_w
                        y_center = (y_min + y_max) / 2 / img_h
                        width = (x_max - x_min) / img_w
                        height = (y_max - y_min) / img_h

                        yolo_labels.append([0, x_center, y_center, width, height])

                    # 准备输出路径
                    image_dir = os.path.dirname(image_path)
                    image_name = os.path.splitext(os.path.basename(image_path))[0]
                    mask_dir = os.path.join(image_dir, "mask")
                    os.makedirs(mask_dir, exist_ok=True)
                    output_path = os.path.join(mask_dir, f"{image_name}.png")

                    # 直接调用CTD生成PNG（不使用Worker）
                    self.append_log(f"  [处理] {len(yolo_labels)} 个标注框...")

                    # 读取图片（使用PIL支持中文路径）
                    import numpy as np
                    import cv2
                    img = np.array(pil_img)
                    # 确保图像为3通道BGR格式
                    if len(img.shape) == 2:
                        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                    elif len(img.shape) == 3:
                        if img.shape[2] == 4:
                            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                        elif img.shape[2] == 3:
                            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

                    # 创建掩膜画布
                    if is_imagetrans:
                        mask_rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)
                    else:
                        mask_rgba = np.zeros((img_h, img_w), dtype=np.uint8)

                    # 处理每个标注框
                    for label in yolo_labels:
                        cls, x_center, y_center, w, h = label

                        x1 = int((x_center - w / 2) * img_w)
                        y1 = int((y_center - h / 2) * img_h)
                        x2 = int((x_center + w / 2) * img_w)
                        y2 = int((y_center + h / 2) * img_h)

                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(img_w, x2), min(img_h, y2)

                        # 裁剪区域（不应用参数）
                        crop = img[y1:y2, x1:x2]

                        if crop.size == 0:
                            continue

                        # CTD检测
                        mask_crop, mask_refined_crop, blk_list = ctd_model(crop, refine_mode=0, keep_undetected_mask=False)

                        if mask_refined_crop is None or mask_refined_crop.size == 0:
                            continue

                        # 应用参数（整体大小 + 方向延伸）
                        size_scale = params.get('size_scale', 1.0)
                        extend_top = params.get('extend_top', 0)
                        extend_bottom = params.get('extend_bottom', 0)
                        extend_left = params.get('extend_left', 0)
                        extend_right = params.get('extend_right', 0)

                        # 整体大小膨胀/腐蚀
                        if size_scale != 1.0:
                            if size_scale > 1.0:
                                kernel_size = int((size_scale - 1.0) * 10) + 1
                                kernel = (kernel_size, kernel_size)
                                mask_refined_crop = cv2.dilate(mask_refined_crop, np.ones(kernel, np.uint8), iterations=1)
                            else:
                                kernel_size = int((1.0 - size_scale) * 10) + 1
                                kernel = (kernel_size, kernel_size)
                                mask_refined_crop = cv2.erode(mask_refined_crop, np.ones(kernel, np.uint8), iterations=1)

                        # 方向延伸（像素移位方法）
                        result_mask = mask_refined_crop.copy()
                        for i in range(1, int(extend_top) + 1):
                            shifted = np.zeros_like(mask_refined_crop)
                            shifted[:-i, :] = mask_refined_crop[i:, :]
                            result_mask = np.maximum(result_mask, shifted)
                        for i in range(1, int(extend_bottom) + 1):
                            shifted = np.zeros_like(mask_refined_crop)
                            shifted[i:, :] = mask_refined_crop[:-i, :]
                            result_mask = np.maximum(result_mask, shifted)
                        for i in range(1, int(extend_left) + 1):
                            shifted = np.zeros_like(mask_refined_crop)
                            shifted[:, :-i] = mask_refined_crop[:, i:]
                            result_mask = np.maximum(result_mask, shifted)
                        for i in range(1, int(extend_right) + 1):
                            shifted = np.zeros_like(mask_refined_crop)
                            shifted[:, i:] = mask_refined_crop[:, :-i]
                            result_mask = np.maximum(result_mask, shifted)

                        # 合并到总掩膜
                        if is_imagetrans:
                            text_color = params['text_color']
                            text_alpha = params['text_alpha']
                            # 将检测结果叠加到对应位置
                            mask_indices = result_mask > 127
                            mask_rgba[y1:y2, x1:x2, 0][mask_indices] = text_color[2]  # B
                            mask_rgba[y1:y2, x1:x2, 1][mask_indices] = text_color[1]  # G
                            mask_rgba[y1:y2, x1:x2, 2][mask_indices] = text_color[0]  # R
                            mask_rgba[y1:y2, x1:x2, 3][mask_indices] = text_alpha     # A
                        else:
                            # BallonsTranslator格式：黑背景 + 白色文字
                            mask_rgba[y1:y2, x1:x2] = np.maximum(
                                mask_rgba[y1:y2, x1:x2],
                                result_mask
                            )

                    # 保存PNG（支持中文路径）
                    _, buffer = cv2.imencode('.png', mask_rgba)
                    buffer.tofile(output_path)

                    self.append_log(f"  [完成] PNG已保存")
                    success_count += 1

                except Exception as e:
                    import traceback
                    self.append_log(f"  [错误] {str(e)}")
                    self.append_log(traceback.format_exc())
                    error_count += 1

            # 完成
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)

            self.append_log(f"\n[批量完成] 成功: {success_count}, 跳过: {skip_count}, 失败: {error_count}")
            self.status_label.setText(self.tr(f"✅ 批量完成！成功:{success_count} 跳过:{skip_count} 失败:{error_count}"))

        except Exception as e:
            import traceback
            self.append_log(f"[错误] {str(e)}")
            self.append_log(traceback.format_exc())
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)
            self.status_label.setText(self.tr(f"❌ 批量生成失败"))

    def generate_mask_from_boxes(self):
        """直接从JSON矩形框生成PNG掩膜（不使用CTD）"""
        if self.current_page_radio.isChecked():
            self.generate_mask_from_boxes_current()
        else:
            self.generate_mask_from_boxes_all()

    def generate_mask_from_boxes_current(self):
        """从JSON矩形框生成PNG掩膜（当前页面）"""
        try:
            # 清空日志
            self.log_text.clear()
            self.append_log("[标注框] 开始从JSON标注框直接生成PNG掩膜...")

            # 获取当前图片路径
            if not self.parent_widget or not hasattr(self.parent_widget, 'filename'):
                self.append_log("[错误] 无法获取当前图片信息！")
                self.status_label.setText(self.tr("❌ 错误：无法获取图片信息"))
                return

            image_path = self.parent_widget.filename
            if not image_path:
                self.append_log("[错误] 当前没有打开的图片！")
                self.status_label.setText(self.tr("❌ 错误：没有打开图片"))
                return

            self.append_log(f"[图片] {image_path}")

            # 读取JSON文件
            json_path = os.path.splitext(image_path)[0] + '.json'
            if not os.path.exists(json_path):
                self.append_log(f"[错误] 未找到JSON文件: {json_path}")
                self.status_label.setText(self.tr("❌ 错误：未找到JSON文件"))
                return

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            shapes = data.get('shapes', [])
            if not shapes:
                self.append_log(f"[错误] JSON文件中没有标注数据")
                self.status_label.setText(self.tr("❌ 错误：没有标注数据"))
                return

            self.append_log(f"[标注] 找到 {len(shapes)} 个标注")

            # 读取图片尺寸
            try:
                from PIL import Image
                pil_img = Image.open(image_path)
                img_w, img_h = pil_img.size
            except Exception as e:
                self.append_log(f"[错误] 无法读取图片: {str(e)}")
                self.status_label.setText(self.tr("❌ 读取图片失败"))
                return

            self.append_log(f"[尺寸] {img_w}x{img_h}")

            # 创建空白掩膜
            mask = np.zeros((img_h, img_w), dtype=np.uint8)

            # 处理每个标注框
            box_count = 0
            for shape in shapes:
                shape_type = shape.get('shape_type')
                points = shape.get('points', [])

                if shape_type in ['rotation', 'rectangle'] and len(points) >= 4:
                    # 获取4个点
                    pts = np.array(points[:4], dtype=np.int32)
                    # 填充多边形为白色
                    cv2.fillPoly(mask, [pts], 255)
                    box_count += 1
                    self.append_log(f"[标注框] 处理第 {box_count} 个框")

            self.append_log(f"[标注框] 共处理了 {box_count} 个矩形框")

            # 准备输出路径
            image_dir = os.path.dirname(image_path)
            image_name = os.path.splitext(os.path.basename(image_path))[0]
            mask_dir = os.path.join(image_dir, "mask")
            os.makedirs(mask_dir, exist_ok=True)
            output_path = os.path.join(mask_dir, f"{image_name}.png")

            # 根据格式保存PNG
            is_imagetrans = self.imagetrans_format_radio.isChecked()
            if is_imagetrans:
                # ImageTrans格式：透明背景 + 自定义颜色
                text_color = [self.mask_color.red(), self.mask_color.green(), self.mask_color.blue()]
                text_alpha = int(self.opacity_slider.value() * 2.55)

                mask_rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)
                mask_indices = mask > 127
                mask_rgba[mask_indices] = [text_color[2], text_color[1], text_color[0], text_alpha]  # BGRA

                # 使用imencode支持中文路径
                _, buffer = cv2.imencode('.png', mask_rgba)
                buffer.tofile(output_path)
                self.append_log(f"[保存] ImageTrans格式PNG已保存: {output_path}")
            else:
                # BallonsTranslator格式：黑背景 + 白色文字
                _, buffer = cv2.imencode('.png', mask)
                buffer.tofile(output_path)
                self.append_log(f"[保存] BallonsTranslator格式PNG已保存: {output_path}")

            self.append_log(f"[完成] ✅ PNG生成完成！")
            self.append_log(f"[保存] {output_path}")
            self.append_log(f"[统计] 矩形框数: {box_count}")
            self.status_label.setText(self.tr(f"✅ 从标注框生成PNG完成 ({box_count}个框)"))

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.append_log(f"[错误] {str(e)}")
            self.append_log(error_detail)
            self.status_label.setText(self.tr(f"❌ 生成失败: {str(e)}"))

    def generate_mask_from_boxes_all(self):
        """批量从JSON矩形框生成PNG掩膜（所有页面）"""
        try:
            # 清空日志
            self.log_text.clear()
            self.append_log("[批量标注框] 开始批量从JSON标注框生成PNG...")

            # 获取所有图片列表
            if not self.parent_widget or not hasattr(self.parent_widget, 'image_list'):
                self.append_log("[错误] 无法获取图片列表！")
                self.status_label.setText(self.tr("❌ 错误：无法获取图片列表"))
                return

            image_list = self.parent_widget.image_list
            if not image_list:
                self.append_log("[错误] 图片列表为空！")
                self.status_label.setText(self.tr("❌ 错误：图片列表为空"))
                return

            total = len(image_list)
            self.append_log(f"[批量] 共 {total} 个文件需要处理")

            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(0)

            # 禁用按钮
            self.generate_btn.setEnabled(False)

            # 获取参数
            is_imagetrans = self.imagetrans_format_radio.isChecked()
            text_color = [self.mask_color.red(), self.mask_color.green(), self.mask_color.blue()]
            text_alpha = int(self.opacity_slider.value() * 2.55)

            success_count = 0
            skip_count = 0
            error_count = 0

            # 批量处理每个图片
            for idx, image_path in enumerate(image_list):
                self.append_log(f"\n[{idx+1}/{total}] 处理: {os.path.basename(image_path)}")
                self.progress_bar.setValue(idx + 1)
                QtWidgets.QApplication.processEvents()

                try:
                    # 检查JSON文件
                    json_path = os.path.splitext(image_path)[0] + '.json'
                    if not os.path.exists(json_path):
                        self.append_log(f"  [跳过] 未找到JSON文件")
                        skip_count += 1
                        continue

                    # 读取JSON
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    shapes = data.get('shapes', [])
                    if not shapes:
                        self.append_log(f"  [跳过] JSON中没有标注")
                        skip_count += 1
                        continue

                    # 读取图片尺寸
                    from PIL import Image
                    pil_img = Image.open(image_path)
                    img_w, img_h = pil_img.size

                    # 创建空白掩膜
                    mask = np.zeros((img_h, img_w), dtype=np.uint8)

                    # 处理每个标注框
                    box_count = 0
                    for shape in shapes:
                        shape_type = shape.get('shape_type')
                        points = shape.get('points', [])

                        if shape_type in ['rotation', 'rectangle'] and len(points) >= 4:
                            pts = np.array(points[:4], dtype=np.int32)
                            cv2.fillPoly(mask, [pts], 255)
                            box_count += 1

                    if box_count == 0:
                        self.append_log(f"  [跳过] 没有矩形或旋转框标注")
                        skip_count += 1
                        continue

                    # 准备输出路径
                    image_dir = os.path.dirname(image_path)
                    image_name = os.path.splitext(os.path.basename(image_path))[0]
                    mask_dir = os.path.join(image_dir, "mask")
                    os.makedirs(mask_dir, exist_ok=True)
                    output_path = os.path.join(mask_dir, f"{image_name}.png")

                    # 根据格式保存PNG
                    if is_imagetrans:
                        mask_rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)
                        mask_indices = mask > 127
                        mask_rgba[mask_indices] = [text_color[2], text_color[1], text_color[0], text_alpha]
                        _, buffer = cv2.imencode('.png', mask_rgba)
                        buffer.tofile(output_path)
                    else:
                        _, buffer = cv2.imencode('.png', mask)
                        buffer.tofile(output_path)

                    self.append_log(f"  [完成] PNG已保存 ({box_count}个框)")
                    success_count += 1

                except Exception as e:
                    import traceback
                    self.append_log(f"  [错误] {str(e)}")
                    error_count += 1

            # 完成
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)

            self.append_log(f"\n[批量完成] 成功: {success_count}, 跳过: {skip_count}, 失败: {error_count}")
            self.status_label.setText(self.tr(f"✅ 批量完成！成功:{success_count} 跳过:{skip_count} 失败:{error_count}"))

        except Exception as e:
            import traceback
            self.append_log(f"[错误] {str(e)}")
            self.append_log(traceback.format_exc())
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)
            self.status_label.setText(self.tr(f"❌ 批量生成失败"))

    def generate_current_mask(self):
        """生成当前页面的掩膜（异步执行）"""
        try:
            # 清空日志
            self.log_text.clear()
            self.append_log("[准备] 开始准备掩膜生成...")

            # 从主窗口获取当前图片和标注
            if not self.parent_widget or not self.parent_widget.filename:
                self.status_label.setText(self.tr("❌ 请先打开图片"))
                return

            image_path = self.parent_widget.filename
            self.append_log(f"[图片] {image_path}")

            # 获取JSON标签文件路径
            json_path = os.path.splitext(image_path)[0] + '.json'

            if not os.path.exists(json_path):
                self.append_log(f"[错误] 未找到JSON文件: {json_path}")
                self.status_label.setText(self.tr("❌ 错误：未找到JSON文件"))
                return

            # 读取JSON标注
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            # 从JSON提取shapes
            shapes = json_data.get('shapes', [])
            if not shapes:
                self.append_log(f"[错误] JSON文件中没有标注数据")
                self.status_label.setText(self.tr("❌ 错误：没有标注数据"))
                return

            self.append_log(f"[标注] 找到 {len(shapes)} 个标注")

            # 获取排除标签列表
            exclude_labels_text = self.exclude_labels_edit.text().strip()
            exclude_labels = []
            if exclude_labels_text:
                exclude_labels = [label.strip() for label in exclude_labels_text.split(',') if label.strip()]
                self.append_log(f"[过滤] 排除标签: {exclude_labels}")

            # 读取图片尺寸（使用PIL支持中文路径）
            try:
                from PIL import Image
                pil_img = Image.open(image_path)
                img_w, img_h = pil_img.size  # PIL返回(width, height)
            except Exception as e:
                self.append_log(f"[错误] 无法读取图片: {str(e)}")
                self.status_label.setText(self.tr("❌ 读取图片失败"))
                return
            # 将标注转换为YOLO格式（归一化坐标）
            yolo_labels = []
            skipped_count = 0
            for shape in shapes:
                shape_label = shape.get('label', '')
                
                # 全部形状都尝试提取框，提高兼容性
                points = shape.get('points', [])
                if not points:
                    continue

                # 检查是否需要排除此标签
                if exclude_labels and shape_label in exclude_labels:
                    skipped_count += 1
                    continue

                # 计算外接矩形
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                x_min, x_max = min(xs), max(xs)
                y_min, y_max = min(ys), max(ys)

                x_center = (x_min + x_max) / 2
                y_center = (y_min + y_max) / 2
                width = x_max - x_min
                height = y_max - y_min

                # 归一化
                x_center_norm = x_center / img_w
                y_center_norm = y_center / img_h
                width_norm = width / img_w
                height_norm = height / img_h

                # YOLO格式: [class, x_center, y_center, width, height]
                yolo_labels.append([0, x_center_norm, y_center_norm, width_norm, height_norm])

            if skipped_count > 0:
                self.append_log(f"[过滤] 已跳过 {skipped_count} 个排除标签的标注")

            if not yolo_labels:
                self.append_log(f"[错误] JSON中没有可用的标注（需要rotation或rectangle类型）")
                self.status_label.setText(self.tr("❌ 错误：没有可用标注"))
                return

            self.append_log(f"[转换] 转换了 {len(yolo_labels)} 个YOLO标签")

            # 准备输出路径
            image_dir = os.path.dirname(image_path)
            image_name = os.path.splitext(os.path.basename(image_path))[0]
            mask_dir = os.path.join(image_dir, "mask")
            os.makedirs(mask_dir, exist_ok=True)
            output_path = os.path.join(mask_dir, f"{image_name}.png")

            self.append_log(f"[输出] {output_path}")

            # 异步调用CTD生成掩膜
            self.start_mask_generation_async(image_path, yolo_labels, output_path)

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.append_log(f"[错误] {str(e)}")
            self.append_log(error_detail)
            self.status_label.setText(self.tr(f"❌ 准备失败: {str(e)}"))

    def start_mask_generation_async(self, image_path, yolo_labels, output_path):
        """异步启动掩膜生成"""
        # 准备参数
        is_imagetrans = self.imagetrans_format_radio.isChecked()
        params = {
            'size_scale': self.size_slider.value() / 100.0,
            'extend_top': self.extend_top_spin.value(),
            'extend_bottom': self.extend_bottom_spin.value(),
            'extend_left': self.extend_left_spin.value(),
            'extend_right': self.extend_right_spin.value(),
            'format': 'imagetrans' if is_imagetrans else 'ballons',
            'text_color': [self.mask_color.red(), self.mask_color.green(), self.mask_color.blue()],
            'text_alpha': int(self.opacity_slider.value() * 2.55),
            'dilate_kernel_size': self.dilate_kernel_spin.value(),  # 膨胀核大小
        }

        # 获取模型路径
        model_path = self.ctd_model_path or self.get_default_model_path()

        self.append_log(f"[开始] 使用CTD模型直接生成...")

        # 创建Worker线程（直接传参数，不再使用subprocess）
        # save_png=False: 生成掩膜时不保存PNG，只提取轮廓
        self.worker = MaskGeneratorWorker(image_path, yolo_labels, model_path, output_path, params, save_png=False)
        self.worker.progress.connect(self.append_log)
        self.worker.finished.connect(lambda result: self.on_mask_generation_finished(result, output_path))
        self.worker.error.connect(self.on_mask_generation_error)

        # 禁用按钮
        self.generate_btn.setEnabled(False)
        self.status_label.setText(self.tr("⏳ 正在生成掩膜..."))

        # 启动线程
        self.worker.start()

    def on_mask_generation_finished(self, result, output_path):
        """掩膜生成完成"""
        # 重新启用按钮
        self.generate_btn.setEnabled(True)

        if not result.get("success"):
            error_msg = result.get("error", "未知错误")
            traceback_info = result.get("traceback", "")
            self.append_log(f"[失败] {error_msg}")
            if traceback_info:
                self.append_log(traceback_info)
            self.status_label.setText(self.tr(f"❌ 生成失败"))
            return

        # 成功
        contours = result.get("contours", [])
        device = result.get("device", "unknown")

        self.append_log(f"[完成] 设备: {device}")
        self.append_log(f"[完成] 生成了 {len(contours)} 个区域")

        # 将轮廓保存为polygon shapes到JSON文件
        if contours:
            self.append_log(f"[保存] 将轮廓保存到JSON...")
            self.save_contours_to_json(contours)

        self.append_log(f"[完成] ✅ 掩膜生成完成！已保存到JSON并刷新画布")
        self.status_label.setText(
            self.tr(f"✅ 掩膜生成完成！生成 {len(contours)} 个区域")
        )

    def on_ctd_direct_finished(self, result, output_path):
        """CTD直接生成PNG完成（不保存JSON）"""
        # 重新启用按钮
        self.generate_btn.setEnabled(True)

        if not result.get("success"):
            error_msg = result.get("error", "未知错误")
            traceback_info = result.get("traceback", "")
            self.append_log(f"[失败] {error_msg}")
            if traceback_info:
                self.append_log(traceback_info)
            self.status_label.setText(self.tr(f"❌ 生成失败"))
            return

        # 成功
        device = result.get("device", "unknown")

        self.append_log(f"[完成] 设备: {device}")
        self.append_log(f"[完成] PNG文件已保存: {output_path}")
        self.append_log(f"[完成] ✅ CTD直接生成PNG完成！")
        self.status_label.setText(self.tr(f"✅ CTD生成PNG完成！"))

    def on_mask_generation_error(self, error_msg):
        """掩膜生成错误"""
        # 重新启用按钮
        self.generate_btn.setEnabled(True)

        self.append_log(f"[错误] {error_msg}")
        self.status_label.setText(self.tr("❌ 执行错误"))

    def generate_all_masks(self):
        """批量生成所有页面的掩膜"""
        try:
            # 清空日志
            self.log_text.clear()
            self.append_log("[批量] 开始批量生成所有页面...")

            # 获取所有图片列表
            if not self.parent_widget or not hasattr(self.parent_widget, 'image_list'):
                self.append_log("[错误] 无法获取图片列表！")
                self.status_label.setText(self.tr("❌ 错误：无法获取图片列表"))
                return

            image_list = self.parent_widget.image_list
            if not image_list:
                self.append_log("[错误] 图片列表为空！")
                self.status_label.setText(self.tr("❌ 错误：图片列表为空"))
                return

            total = len(image_list)
            self.append_log(f"[批量] 共 {total} 个文件需要处理")

            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(0)

            # 禁用按钮
            self.generate_btn.setEnabled(False)

            # 获取参数
            is_imagetrans = self.imagetrans_format_radio.isChecked()
            params = {
                'size_scale': float(self.size_slider.value()) / 100.0,
                'extend_top': self.extend_top_spin.value(),
                'extend_bottom': self.extend_bottom_spin.value(),
                'extend_left': self.extend_left_spin.value(),
                'extend_right': self.extend_right_spin.value(),
                'format': 'imagetrans' if is_imagetrans else 'ballons',
                'text_color': [self.mask_color.red(), self.mask_color.green(), self.mask_color.blue()],
                'text_alpha': int(self.opacity_slider.value() * 2.55),
                'dilate_kernel_size': self.dilate_kernel_spin.value()  # 膨胀核大小
            }

            model_path = self.ctd_model_path or self.get_default_model_path()

            # 获取排除标签列表
            exclude_labels_text = self.exclude_labels_edit.text().strip()
            exclude_labels = []
            if exclude_labels_text:
                exclude_labels = [label.strip() for label in exclude_labels_text.split(',') if label.strip()]
                self.append_log(f"[过滤] 排除标签: {exclude_labels}")

            # 🎯 在批量处理前加载一次CTD模型
            self.append_log(f"[模型] 正在加载CTD模型...")
            try:
                import sys
                import torch

                # 添加BallonsTranslator路径
                ballons_path = r"D:\BallonsTranslator\BallonsTranslator"
                if ballons_path not in sys.path:
                    sys.path.insert(0, ballons_path)

                from modules.textdetector.ctd import CTDModel

                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                ctd_model = CTDModel(model_path, detect_size=1024, device=device)
                self.append_log(f"[模型] ✅ CTD模型加载完成 (设备: {device})")
            except Exception as e:
                self.append_log(f"[错误] 模型加载失败: {str(e)}")
                self.status_label.setText(self.tr("❌ 模型加载失败"))
                self.progress_bar.setVisible(False)
                self.generate_btn.setEnabled(True)
                return

            success_count = 0
            skip_count = 0
            error_count = 0

            # 批量处理每个图片
            for idx, image_path in enumerate(image_list):
                self.append_log(f"\n[{idx+1}/{total}] 处理: {os.path.basename(image_path)}")
                self.progress_bar.setValue(idx + 1)
                QtWidgets.QApplication.processEvents()

                try:
                    # 检查JSON文件
                    json_path = os.path.splitext(image_path)[0] + '.json'
                    if not os.path.exists(json_path):
                        self.append_log(f"  [跳过] 未找到JSON文件")
                        skip_count += 1
                        continue

                    # 读取JSON
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    shapes = data.get('shapes', [])
                    if not shapes:
                        self.append_log(f"  [跳过] JSON中没有标注")
                        skip_count += 1
                        continue

                    # 全部形状都尝试提取框
                    boxes = []
                    skipped_count = 0
                    for shape in shapes:
                        shape_label = shape.get('label', '')

                        # 检查是否需要排除此标签
                        if exclude_labels and shape_label in exclude_labels:
                            skipped_count += 1
                            continue
                        
                        points = shape.get('points', [])
                        if len(points) >= 2:
                            boxes.append(points)

                    if skipped_count > 0:
                        self.append_log(f"  [过滤] 已跳过 {skipped_count} 个排除标签的标注")

                    if not boxes:
                        self.append_log(f"  [跳过] 没有矩形或旋转框标注")
                        skip_count += 1
                        continue

                    # 读取图片尺寸
                    from PIL import Image
                    pil_img = Image.open(image_path)
                    img_w, img_h = pil_img.size

                    # 转换为YOLO格式
                    yolo_labels = []
                    for points in boxes:
                        x_coords = [p[0] for p in points]
                        y_coords = [p[1] for p in points]
                        x_min, x_max = min(x_coords), max(x_coords)
                        y_min, y_max = min(y_coords), max(y_coords)

                        x_center = (x_min + x_max) / 2 / img_w
                        y_center = (y_min + y_max) / 2 / img_h
                        width = (x_max - x_min) / img_w
                        height = (y_max - y_min) / img_h

                        yolo_labels.append([0, x_center, y_center, width, height])

                    # 准备输出路径
                    image_dir = os.path.dirname(image_path)
                    image_name = os.path.splitext(os.path.basename(image_path))[0]
                    mask_dir = os.path.join(image_dir, "mask")
                    os.makedirs(mask_dir, exist_ok=True)
                    output_path = os.path.join(mask_dir, f"{image_name}.png")

                    # 调用CTD生成
                    self.append_log(f"  [处理] {len(yolo_labels)} 个标注框...")

                    # 同步调用Worker（简化版，不使用线程）
                    worker = MaskGeneratorWorker(
                        image_path,
                        yolo_labels,
                        model_path,
                        output_path,
                        params,
                        save_png=False
                    )

                    # 直接运行（不启动线程），传入已加载的模型
                    result = self._run_worker_sync(worker, ctd_model)

                    if result.get("success"):
                        contours = result.get("contours", [])
                        self.append_log(f"  [完成] 生成 {len(contours)} 个多边形")

                        # 保存到JSON
                        if contours:
                            self._save_contours_to_json_batch(json_path, contours)

                        success_count += 1
                    else:
                        error_msg = result.get("error", "未知错误")
                        self.append_log(f"  [失败] {error_msg}")
                        error_count += 1

                except Exception as e:
                    import traceback
                    self.append_log(f"  [错误] {str(e)}")
                    self.append_log(traceback.format_exc())
                    error_count += 1

            # 完成
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)

            self.append_log(f"\n[批量完成] 成功: {success_count}, 跳过: {skip_count}, 失败: {error_count}")
            self.status_label.setText(self.tr(f"✅ 批量完成！成功:{success_count} 跳过:{skip_count} 失败:{error_count}"))

        except Exception as e:
            import traceback
            self.append_log(f"[错误] {str(e)}")
            self.append_log(traceback.format_exc())
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)
            self.status_label.setText(self.tr(f"❌ 批量生成失败"))

    def export_mask(self):
        """导出掩膜为PNG"""
        if self.current_page_radio.isChecked():
            self.export_mask_current()
        else:
            self.export_mask_all()

    def export_mask_current(self):
        """导出当前页面的掩膜为PNG"""
        try:
            self.log_text.clear()
            self.append_log("[导出] 开始导出PNG...")
            self.status_label.setText(self.tr("正在导出掩膜..."))
            QtWidgets.QApplication.processEvents()

            # 获取当前图片信息
            if not self.parent_widget or not hasattr(self.parent_widget, 'filename'):
                self.append_log("[错误] 无法获取当前图片信息！")
                self.status_label.setText(self.tr("❌ 错误：无法获取图片信息"))
                return

            image_path = self.parent_widget.filename
            if not image_path:
                self.append_log("[错误] 当前没有打开的图片！")
                self.status_label.setText(self.tr("❌ 错误：没有打开图片"))
                return

            # 读取JSON文件
            json_path = os.path.splitext(image_path)[0] + '.json'
            if not os.path.exists(json_path):
                self.append_log("[错误] 未找到JSON文件！请先生成掩膜")
                self.status_label.setText(self.tr("❌ 错误：未找到JSON文件"))
                return

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 读取图片尺寸（使用PIL支持中文路径）
            try:
                from PIL import Image
                pil_img = Image.open(image_path)
                img_w, img_h = pil_img.size  # PIL返回(width, height)
            except Exception as e:
                self.append_log(f"[错误] 读取图片失败: {str(e)}")
                self.status_label.setText(self.tr("❌ 读取图片失败"))
                return

            self.append_log(f"[导出] 图片尺寸: {img_w}x{img_h}")

            # 创建空白掩膜
            mask = np.zeros((img_h, img_w), dtype=np.uint8)

            # 从JSON中读取polygon shapes并绘制
            shapes = data.get("shapes", [])
            polygon_count = 0
            for shape in shapes:
                if shape.get("shape_type") == "polygon":
                    points = shape.get("points", [])
                    if len(points) >= 3:
                        # 转换为numpy数组
                        pts = np.array(points, dtype=np.int32)
                        # 填充多边形为白色
                        cv2.fillPoly(mask, [pts], 255)
                        polygon_count += 1

            self.append_log(f"[导出] 绘制了 {polygon_count} 个多边形")

            # 确定输出路径
            image_dir = os.path.dirname(image_path)
            image_name = os.path.splitext(os.path.basename(image_path))[0]
            mask_dir = os.path.join(image_dir, "mask")
            os.makedirs(mask_dir, exist_ok=True)
            output_path = os.path.join(mask_dir, f"{image_name}.png")

            # 根据格式保存（使用imencode支持中文路径）
            is_imagetrans = self.imagetrans_format_radio.isChecked()
            if is_imagetrans:
                # ImageTrans格式：透明背景 + 自定义颜色
                text_color = [self.mask_color.red(), self.mask_color.green(), self.mask_color.blue()]
                text_alpha = int(self.opacity_slider.value() * 2.55)

                mask_rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)
                mask_indices = mask > 127
                mask_rgba[mask_indices] = [text_color[2], text_color[1], text_color[0], text_alpha]  # BGRA

                # 使用imencode支持中文路径
                _, buffer = cv2.imencode('.png', mask_rgba)
                buffer.tofile(output_path)
                self.append_log(f"[导出] ImageTrans格式PNG已保存: {output_path}")
            else:
                # BallonsTranslator格式：黑背景 + 白色文字
                # 使用imencode支持中文路径
                _, buffer = cv2.imencode('.png', mask)
                buffer.tofile(output_path)
                self.append_log(f"[导出] BallonsTranslator格式PNG已保存: {output_path}")

            self.append_log(f"[完成] ✅ PNG导出完成！")
            self.append_log(f"[保存] {output_path}")
            self.append_log(f"[统计] 多边形数: {polygon_count}")
            self.status_label.setText(self.tr(f"✅ 掩膜导出完成 ({polygon_count}个多边形)"))

        except Exception as e:
            import traceback
            self.append_log(f"[导出] ❌ 错误: {str(e)}")
            self.append_log(traceback.format_exc())
            self.status_label.setText(self.tr(f"❌ 导出失败: {str(e)}"))

    def export_mask_all(self):
        """批量导出所有页面的掩膜为PNG"""
        try:
            # 清空日志
            self.log_text.clear()
            self.append_log("[批量导出] 开始批量导出所有页面PNG...")

            # 获取所有图片列表
            if not self.parent_widget or not hasattr(self.parent_widget, 'image_list'):
                self.append_log("[错误] 无法获取图片列表！")
                self.status_label.setText(self.tr("❌ 错误：无法获取图片列表"))
                return

            image_list = self.parent_widget.image_list
            if not image_list:
                self.append_log("[错误] 图片列表为空！")
                self.status_label.setText(self.tr("❌ 错误：图片列表为空"))
                return

            total = len(image_list)
            self.append_log(f"[批量] 共 {total} 个文件需要处理")

            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(0)

            # 禁用按钮
            self.generate_btn.setEnabled(False)

            # 获取参数
            is_imagetrans = self.imagetrans_format_radio.isChecked()
            text_color = [self.mask_color.red(), self.mask_color.green(), self.mask_color.blue()]
            text_alpha = int(self.opacity_slider.value() * 2.55)

            success_count = 0
            skip_count = 0
            error_count = 0

            # 批量处理每个图片
            for idx, image_path in enumerate(image_list):
                self.append_log(f"\n[{idx+1}/{total}] 处理: {os.path.basename(image_path)}")
                self.progress_bar.setValue(idx + 1)
                QtWidgets.QApplication.processEvents()

                try:
                    # 检查JSON文件
                    json_path = os.path.splitext(image_path)[0] + '.json'
                    if not os.path.exists(json_path):
                        self.append_log(f"  [跳过] 未找到JSON文件")
                        skip_count += 1
                        continue

                    # 读取JSON
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    shapes = data.get('shapes', [])
                    if not shapes:
                        self.append_log(f"  [跳过] JSON中没有标注")
                        skip_count += 1
                        continue

                    # 读取图片尺寸
                    from PIL import Image
                    pil_img = Image.open(image_path)
                    img_w, img_h = pil_img.size

                    # 创建空白掩膜
                    mask = np.zeros((img_h, img_w), dtype=np.uint8)

                    # 绘制多边形
                    polygon_count = 0
                    for shape in shapes:
                        if shape.get("shape_type") == "polygon":
                            points = shape.get("points", [])
                            if len(points) >= 3:
                                pts = np.array(points, dtype=np.int32)
                                cv2.fillPoly(mask, [pts], 255)
                                polygon_count += 1

                    if polygon_count == 0:
                        self.append_log(f"  [跳过] 没有多边形标注")
                        skip_count += 1
                        continue

                    # 准备输出路径
                    image_dir = os.path.dirname(image_path)
                    image_name = os.path.splitext(os.path.basename(image_path))[0]
                    mask_dir = os.path.join(image_dir, "mask")
                    os.makedirs(mask_dir, exist_ok=True)
                    output_path = os.path.join(mask_dir, f"{image_name}.png")

                    # 根据格式保存PNG
                    if is_imagetrans:
                        mask_rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)
                        mask_indices = mask > 127
                        mask_rgba[mask_indices] = [text_color[2], text_color[1], text_color[0], text_alpha]
                        _, buffer = cv2.imencode('.png', mask_rgba)
                        buffer.tofile(output_path)
                    else:
                        _, buffer = cv2.imencode('.png', mask)
                        buffer.tofile(output_path)

                    self.append_log(f"  [完成] PNG已保存 ({polygon_count}个多边形)")
                    success_count += 1

                except Exception as e:
                    import traceback
                    self.append_log(f"  [错误] {str(e)}")
                    error_count += 1

            # 完成
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)

            self.append_log(f"\n[批量完成] 成功: {success_count}, 跳过: {skip_count}, 失败: {error_count}")
            self.status_label.setText(self.tr(f"✅ 批量完成！成功:{success_count} 跳过:{skip_count} 失败:{error_count}"))

        except Exception as e:
            import traceback
            self.append_log(f"[错误] {str(e)}")
            self.append_log(traceback.format_exc())
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)
            self.status_label.setText(self.tr(f"❌ 批量导出失败"))

    def save_contours_to_json(self, contours):
        """将轮廓保存为polygon格式到JSON文件"""
        try:
            # 获取当前图片信息
            if not self.parent_widget or not hasattr(self.parent_widget, 'filename'):
                self.append_log("[保存] 无法获取当前图片信息")
                return

            image_path = self.parent_widget.filename
            if not image_path:
                self.append_log("[保存] 当前没有打开的图片")
                return

            # 读取图片尺寸（使用PIL支持中文路径）
            try:
                from PIL import Image
                pil_img = Image.open(image_path)
                img_w, img_h = pil_img.size  # PIL返回(width, height)
            except Exception as e:
                self.append_log(f"[保存] 读取图片失败: {str(e)}")
                return

            img_h, img_w = img_h, img_w  # 保持img_h, img_w的顺序

            # 构建JSON路径（与图片同名，.json扩展名）
            json_path = os.path.splitext(image_path)[0] + '.json'

            # 读取现有JSON（如果存在）
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.append_log(f"[保存] 读取现有JSON: {json_path}")
            else:
                # 创建新JSON
                data = {
                    "version": "3.2.2",
                    "flags": {"NSFW": False, "SFW": False},
                    "shapes": [],
                    "imagePath": os.path.basename(image_path),
                    "imageData": None,
                    "imageHeight": img_h,
                    "imageWidth": img_w,
                    "description": "",
                    "manually_edited": False
                }
                self.append_log(f"[保存] 创建新JSON: {json_path}")

            # 如果勾选了"清空旧多边形"，则删除所有polygon类型的标注
            if self.clear_old_polygons_checkbox.isChecked():
                old_shapes = data.get("shapes", [])
                old_total_count = len(old_shapes)

                # 统计各类型标注数量
                shape_types = {}
                polygon_labels = {}  # 统计多边形的label
                for shape in old_shapes:
                    shape_type = shape.get("shape_type", "unknown")
                    shape_types[shape_type] = shape_types.get(shape_type, 0) + 1

                    # 如果是多边形，统计label
                    if shape_type == "polygon":
                        label = shape.get("label", "unknown")
                        polygon_labels[label] = polygon_labels.get(label, 0) + 1

                self.append_log(f"[清理] 原有标注总数: {old_total_count}")
                for shape_type, count in shape_types.items():
                    self.append_log(f"[清理]   - {shape_type}: {count} 个")

                old_polygon_count = shape_types.get("polygon", 0)

                if old_polygon_count > 0:
                    # 显示多边形的label分布
                    self.append_log(f"[清理] 多边形label分布:")
                    for label, count in polygon_labels.items():
                        self.append_log(f"[清理]   - label='{label}': {count} 个")

                    # 保留非polygon类型的标注
                    data["shapes"] = [shape for shape in old_shapes if shape.get("shape_type") != "polygon"]
                    new_total_count = len(data["shapes"])
                    self.append_log(f"[清理] ✅ 已删除所有 {old_polygon_count} 个多边形，保留 {new_total_count} 个其他标注")
                else:
                    self.append_log(f"[清理] 没有找到旧多边形，跳过清理")

            # 将轮廓转换为polygon shapes
            for idx, contour in enumerate(contours):
                # contour是点列表: [[x1,y1], [x2,y2], ...]
                points = [[float(pt[0]), float(pt[1])] for pt in contour]

                shape = {
                    "label": "mask",
                    "score": None,
                    "points": points,
                    "group_id": None,
                    "description": "",
                    "difficult": False,
                    "shape_type": "polygon",
                    "flags": {},
                    "attributes": {},
                    "kie_linking": []
                }
                data["shapes"].append(shape)

            # 保存JSON
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.append_log(f"[保存] ✅ 已保存 {len(contours)} 个多边形到: {json_path}")

            # 刷新主窗口的shapes显示
            if hasattr(self.parent_widget, 'load_file'):
                self.parent_widget.load_file(image_path)
                self.append_log(f"[保存] 已刷新画布显示")

        except Exception as e:
            import traceback
            self.append_log(f"[保存] ❌ 保存JSON失败: {str(e)}")
            self.append_log(traceback.format_exc())

    def _save_contours_to_json_batch(self, json_path, contours):
        """批量模式下保存轮廓到JSON（不刷新画布）"""
        try:
            # 读取现有JSON
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 如果勾选了"清空旧多边形"，则删除所有polygon类型的标注
            if self.clear_old_polygons_checkbox.isChecked():
                old_polygon_count = sum(1 for shape in data.get("shapes", []) if shape.get("shape_type") == "polygon")
                if old_polygon_count > 0:
                    data["shapes"] = [shape for shape in data.get("shapes", []) if shape.get("shape_type") != "polygon"]

            # 将轮廓转换为polygon shapes
            for idx, contour in enumerate(contours):
                points = [[float(pt[0]), float(pt[1])] for pt in contour]

                shape = {
                    "label": "mask",
                    "score": None,
                    "points": points,
                    "group_id": None,
                    "description": "",
                    "difficult": False,
                    "shape_type": "polygon",
                    "flags": {},
                    "attributes": {},
                    "kie_linking": []
                }
                data["shapes"].append(shape)

            # 保存JSON
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            raise e

    def _run_worker_sync(self, worker, ctd_model):
        """同步运行Worker（用于批量处理）

        Args:
            worker: MaskGeneratorWorker对象
            ctd_model: 已加载的CTD模型（避免重复加载）
        """
        try:
            # 读取图片（使用PIL支持中文路径）
            from PIL import Image
            import numpy as np
            import cv2

            pil_img = Image.open(worker.image_path)
            img = np.array(pil_img)
            # 确保图像为3通道BGR格式
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            elif len(img.shape) == 3:
                if img.shape[2] == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                elif img.shape[2] == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            img_h, img_w = img.shape[:2]

            # 使用传入的已加载模型（不再重复加载）
            model = ctd_model

            # 获取设备信息（用于返回值）
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'

            # 1. 全图检测获取最准确掩膜
            mask_full, mask_refined_full, _ = model(img, refine_mode=0, keep_undetected_mask=False)

            if mask_refined_full is None or mask_refined_full.size == 0:
                mask = np.zeros((img_h, img_w), dtype=np.uint8)
            else:
                if mask_refined_full.shape[:2] != (img_h, img_w):
                    mask_refined_full = cv2.resize(mask_refined_full, (img_w, img_h))

                # 2. 局部聚合逻辑：在每个标注框内合并碎片
                mask = np.zeros((img_h, img_w), dtype=np.uint8)
                kernel_close = np.ones((5, 5), np.uint8)
                
                for label in worker.yolo_labels:
                    cls, x_center, y_center, w, h = label
                    x1 = int((x_center - w / 2) * img_w)
                    y1 = int((y_center - h / 2) * img_h)
                    x2 = int((x_center + w / 2) * img_w)
                    y2 = int((y_center + h / 2) * img_h)
                    
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(img_w, x2), min(img_h, y2)
                    
                    if x2 <= x1 or y2 <= y1:
                        continue

                    region_m = mask_refined_full[y1:y2, x1:x2].copy()
                    # 闭运算连接字符
                    region_m = cv2.morphologyEx(region_m, cv2.MORPH_CLOSE, kernel_close)
                    mask[y1:y2, x1:x2] = np.maximum(mask[y1:y2, x1:x2], region_m)

            # 获取延伸/大小参数
            size_scale = worker.params.get('size_scale', 1.0)
            extend_top = int(worker.params.get('extend_top', 0))
            extend_bottom = int(worker.params.get('extend_bottom', 0))
            extend_left = int(worker.params.get('extend_left', 0))
            extend_right = int(worker.params.get('extend_right', 0))

            # 3. 后处理：大小调整
            if size_scale != 1.0:
                if size_scale > 1.0:
                    kernel_size = int((size_scale - 1.0) * 10) + 1
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                    mask = cv2.dilate(mask, kernel, iterations=1)
                else:
                    kernel_size = int((1.0 - size_scale) * 10) + 1
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                    mask = cv2.erode(mask, kernel, iterations=1)

            # 4. 后处理：方向延伸
            if extend_top > 0 or extend_bottom > 0 or extend_left > 0 or extend_right > 0:
                result_mask = mask.copy()
                if extend_top > 0:
                    for i in range(1, int(extend_top) + 1):
                        shifted = np.zeros_like(mask)
                        shifted[:-i, :] = mask[i:, :]
                        result_mask = np.maximum(result_mask, shifted)
                if extend_bottom > 0:
                    for i in range(1, int(extend_bottom) + 1):
                        shifted = np.zeros_like(mask)
                        shifted[i:, :] = mask[:-i, :]
                        result_mask = np.maximum(result_mask, shifted)
                if extend_left > 0:
                    for i in range(1, int(extend_left) + 1):
                        shifted = np.zeros_like(mask)
                        shifted[:, :-i] = mask[:, i:]
                        result_mask = np.maximum(result_mask, shifted)
                if extend_right > 0:
                    for i in range(1, int(extend_right) + 1):
                        shifted = np.zeros_like(mask)
                        shifted[:, i:] = mask[:, :-i]
                        result_mask = np.maximum(result_mask, shifted)
                mask = result_mask

            # 5. 提取所有轮廓
            all_contours = []
            _, binary_mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
            
            # 使用界面参数中的膨胀设置
            dilate_kernel_size = worker.params.get('dilate_kernel_size', 3)
            if dilate_kernel_size > 0:
                kernel = np.ones((dilate_kernel_size, dilate_kernel_size), np.uint8)
                binary_mask = cv2.dilate(binary_mask, kernel, iterations=1)

            contours_raw, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours_raw:
                epsilon = 0.005 * cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, epsilon, True)

                if len(approx) < 3:
                    continue

                # 转换坐标到原图（当前mask已经是全图比例，直接提取即可）
                polygon = []
                for pt in approx:
                    x = float(pt[0][0])
                    y = float(pt[0][1])
                    polygon.append([x, y])

                all_contours.append(polygon)

            return {
                "success": True,
                "contours": all_contours,
                "device": device
            }

        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    def _run_worker_sync_png(self, worker):
        """同步运行Worker生成PNG（用于批量处理，不提取contours）"""
        try:
            # 直接调用Worker的run方法
            # Worker会自动生成PNG（因为save_png=True）
            from PIL import Image
            import numpy as np
            import cv2
            import sys
            import torch
            from pathlib import Path

            # 读取图片（使用PIL支持中文路径）
            pil_img = Image.open(worker.image_path)
            img = np.array(pil_img)
            # 确保图像为3通道BGR格式
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            elif len(img.shape) == 3:
                if img.shape[2] == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                elif img.shape[2] == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            img_h, img_w = img.shape[:2]

            # 加载CTD模型
            ctd_path = Path(worker.model_path).parent.parent.parent
            if str(ctd_path) not in sys.path:
                sys.path.insert(0, str(ctd_path))

            from detection import dispatch

            device = 'cuda' if torch.cuda.is_available() else 'cpu'

            # 创建掩膜画布
            is_imagetrans = worker.params['format'] == 'imagetrans'

            if is_imagetrans:
                mask_rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)
            else:
                mask_rgba = np.zeros((img_h, img_w), dtype=np.uint8)

            # 处理每个标注框
            for label in worker.yolo_labels:
                cls, x_center, y_center, w, h = label

                x1 = int((x_center - w / 2) * img_w)
                y1 = int((y_center - h / 2) * img_h)
                x2 = int((x_center + w / 2) * img_w)
                y2 = int((y_center + h / 2) * img_h)

                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(img_w, x2), min(img_h, y2)

                # 扩展边距
                extend_left = int(worker.params['extend_left'])
                extend_right = int(worker.params['extend_right'])
                extend_top = int(worker.params['extend_top'])
                extend_bottom = int(worker.params['extend_bottom'])

                x1_ext = max(0, x1 - extend_left)
                y1_ext = max(0, y1 - extend_top)
                x2_ext = min(img_w, x2 + extend_right)
                y2_ext = min(img_h, y2 + extend_bottom)

                crop = img[y1_ext:y2_ext, x1_ext:x2_ext]

                if crop.size == 0:
                    continue

                # CTD检测
                mask_raw, _ = dispatch(worker.model_path, crop, device)

                if mask_raw is None:
                    continue

                mask_resized = cv2.resize(mask_raw, (x2_ext - x1_ext, y2_ext - y1_ext))
                _, binary_mask = cv2.threshold(mask_resized, 127, 255, cv2.THRESH_BINARY)

                # 合并到总掩膜
                if is_imagetrans:
                    text_color = worker.params['text_color']
                    text_alpha = worker.params['text_alpha']
                    mask_rgba[y1_ext:y2_ext, x1_ext:x2_ext, 0] = np.maximum(
                        mask_rgba[y1_ext:y2_ext, x1_ext:x2_ext, 0],
                        (binary_mask > 0).astype(np.uint8) * text_color[2]
                    )
                    mask_rgba[y1_ext:y2_ext, x1_ext:x2_ext, 1] = np.maximum(
                        mask_rgba[y1_ext:y2_ext, x1_ext:x2_ext, 1],
                        (binary_mask > 0).astype(np.uint8) * text_color[1]
                    )
                    mask_rgba[y1_ext:y2_ext, x1_ext:x2_ext, 2] = np.maximum(
                        mask_rgba[y1_ext:y2_ext, x1_ext:x2_ext, 2],
                        (binary_mask > 0).astype(np.uint8) * text_color[0]
                    )
                    mask_rgba[y1_ext:y2_ext, x1_ext:x2_ext, 3] = np.maximum(
                        mask_rgba[y1_ext:y2_ext, x1_ext:x2_ext, 3],
                        (binary_mask > 0).astype(np.uint8) * text_alpha
                    )
                else:
                    mask_rgba[y1_ext:y2_ext, x1_ext:x2_ext] = np.maximum(
                        mask_rgba[y1_ext:y2_ext, x1_ext:x2_ext],
                        binary_mask
                    )

            # 保存PNG（支持中文路径）
            _, buffer = cv2.imencode('.png', mask_rgba)
            buffer.tofile(worker.output_path)

            return {
                "success": True,
                "device": device
            }

        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
