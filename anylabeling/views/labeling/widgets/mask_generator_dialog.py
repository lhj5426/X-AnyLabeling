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
    """掩膜生成工作线程 - 使用预加载的CTD模型"""
    # 信号
    progress = QtCore.pyqtSignal(str)  # 进度信息
    finished = QtCore.pyqtSignal(dict)  # 完成信号，返回结果字典
    error = QtCore.pyqtSignal(str)  # 错误信号

    def __init__(self, image_path, yolo_labels, ctd_inference, output_path, params, save_png=False, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.yolo_labels = yolo_labels
        self.ctd_inference = ctd_inference  # 已加载的CTD模型实例
        self.output_path = output_path
        self.params = params
        self.save_png = save_png  # 是否保存PNG文件

    def run(self):
        """在后台线程执行CTD模型"""
        try:
            self.progress.emit("[CTD] 开始生成掩膜...")
            self.progress.emit(f"[CTD] 图片路径: {self.image_path}")
            self.progress.emit(f"[CTD] 使用自动标注已加载的模型")
            self.progress.emit(f"[CTD] YOLO标签数量: {len(self.yolo_labels)}")

            # 直接使用自动标注已加载的CTD模型，避免重复加载
            self.progress.emit("[CTD] 复用模型实例...")
            from anylabeling.services.auto_labeling.ctd.inference import preprocess_img
            import torch

            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            ctd_inference = self.ctd_inference
            detect_size = ctd_inference.detect_size
            self.progress.emit(f"[CTD] 加载模型... (设备: {device})")
            self.progress.emit(f"[CTD] 设备: {device}, 检测尺寸: {detect_size}")

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
            with torch.no_grad():
                img_in, ratio, dw, dh = preprocess_img(
                    img, bgr2rgb=False, detect_size=detect_size,
                    device=ctd_inference.device, half=ctd_inference.half,
                    to_tensor=(ctd_inference.backend == 'torch')
                )
                blks, mask_tensor, lines_map = ctd_inference.net(img_in)
            mask_out = mask_tensor.squeeze()
            if hasattr(mask_out, 'cpu'):
                mask_out = mask_out.cpu().numpy()
            # 移除letterbox padding
            mask_out = mask_out[..., :mask_out.shape[0] - dh, :mask_out.shape[1] - dw]
            # 阈值化: sigmoid 输出 > 0.5
            mask_binary = (mask_out > 0.5).astype(np.uint8) * 255
            mask_refined_full = cv2.resize(mask_binary, (img_w, img_h), interpolation=cv2.INTER_LINEAR)
            mask_full = mask_refined_full

            if mask_refined_full is None or mask_refined_full.size == 0:
                self.progress.emit("[CTD] ⚠️ 未检测到文字区域")
                mask = np.zeros((img_h, img_w), dtype=np.uint8)
            else:
                # 2. YOLO 框过滤：只保留框内的掩膜区域（照搬 yolo_to_mask_gui.py）
                self.progress.emit(f"[CTD] 用 {len(self.yolo_labels)} 个 YOLO 框过滤掩膜...")
                yolo_mask = np.zeros((img_h, img_w), dtype=np.uint8)
                pixel_boxes = []
                for label_data in self.yolo_labels:
                    x_center, y_center, width, height = label_data[1:]
                    x1 = int((x_center - width / 2) * img_w)
                    y1 = int((y_center - height / 2) * img_h)
                    x2 = int((x_center + width / 2) * img_w)
                    y2 = int((y_center + height / 2) * img_h)
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(img_w, x2), min(img_h, y2)
                    if x2 > x1 and y2 > y1:
                        yolo_mask[y1:y2, x1:x2] = 255
                        pixel_boxes.append((x1, y1, x2, y2))
                mask = cv2.bitwise_and(mask_refined_full, yolo_mask)

            # 保证掩膜与图片尺寸一致
            if mask.shape[:2] != (img_h, img_w):
                mask = cv2.resize(mask, (img_w, img_h))

            # 3. 整体大小调整（膨胀/腐蚀，照搬 yolo_to_mask_gui.py adjust_mask_size）
            if size_scale != 1.0:
                if size_scale > 1.0:
                    kernel_size = int((size_scale - 1.0) * 10) + 1
                    self.progress.emit(f"[CTD] 整体大小 {int(size_scale*100)}%，膨胀核大小 {kernel_size}")
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                    mask = cv2.dilate(mask, kernel, iterations=1)
                else:
                    kernel_size = int((1.0 - size_scale) * 10) + 1
                    self.progress.emit(f"[CTD] 整体大小 {int(size_scale*100)}%，腐蚀核大小 {kernel_size}")
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                    mask = cv2.erode(mask, kernel, iterations=1)

            # 4. 轮廓膨胀（用户面板参数 dilate_kernel_size）
            dilate_ks = self.params.get('dilate_kernel_size', 3)
            if dilate_ks > 0:
                kernel_d = np.ones((dilate_ks, dilate_ks), np.uint8)
                mask = cv2.dilate(mask, kernel_d, iterations=1)

            # 2. 方向延伸（像素移位法，照搬 yolo_to_mask_gui.py apply_directional_extensions）
            if extend_top > 0 or extend_bottom > 0 or extend_left > 0 or extend_right > 0:
                self.progress.emit(f"[CTD] 方向延伸: 上{extend_top} 下{extend_bottom} 左{extend_left} 右{extend_right}")
                result_mask = mask.copy()
                h_m, w_m = mask.shape
                if extend_top > 0:
                    for i in range(1, int(extend_top) + 1):
                        shifted = np.zeros_like(mask)
                        if i < h_m:
                            shifted[:-i, :] = mask[i:, :]
                            result_mask = np.maximum(result_mask, shifted)
                if extend_bottom > 0:
                    for i in range(1, int(extend_bottom) + 1):
                        shifted = np.zeros_like(mask)
                        if i < h_m:
                            shifted[i:, :] = mask[:-i, :]
                            result_mask = np.maximum(result_mask, shifted)
                if extend_left > 0:
                    for i in range(1, int(extend_left) + 1):
                        shifted = np.zeros_like(mask)
                        if i < w_m:
                            shifted[:, :-i] = mask[:, i:]
                            result_mask = np.maximum(result_mask, shifted)
                if extend_right > 0:
                    for i in range(1, int(extend_right) + 1):
                        shifted = np.zeros_like(mask)
                        if i < w_m:
                            shifted[:, i:] = mask[:, :-i]
                            result_mask = np.maximum(result_mask, shifted)
                mask = result_mask

            # 统一合成 PNG（照搬原逻辑）
            if self.save_png:
                self.progress.emit(f"[CTD] 生成掩膜PNG...")
                bg_bgra = self.params.get('bg_bgra', [0, 0, 0, 255])
                mask_bgra = self.params.get('mask_bgra', [255, 255, 255, 255])
                mask_rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)
                mask_rgba[..., 0] = bg_bgra[0]
                mask_rgba[..., 1] = bg_bgra[1]
                mask_rgba[..., 2] = bg_bgra[2]
                mask_rgba[..., 3] = bg_bgra[3]
                mask_indices = mask > 127
                if mask_indices.any():
                    mask_rgba[mask_indices, 0] = mask_bgra[0]
                    mask_rgba[mask_indices, 1] = mask_bgra[1]
                    mask_rgba[mask_indices, 2] = mask_bgra[2]
                    mask_rgba[mask_indices, 3] = mask_bgra[3]
                _, buffer = cv2.imencode('.png', mask_rgba)
                buffer.tofile(self.output_path)
            else:
                self.progress.emit(f"[生成] 跳过PNG保存，仅提取轮廓数据...")

            # 5. 提取轮廓 — 椭圆开运算磨圆直角
            self.progress.emit(f"[CTD] 提取多边形轮廓...")
            contours = []
            kernel_round = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask_round = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_round)
            cnt_list, _ = cv2.findContours(mask_round, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in cnt_list:
                if len(cnt) < 3 or cv2.contourArea(cnt) < 30:
                    continue
                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.0001 * peri, True)
                pts = [[int(pt[0][0]), int(pt[0][1])] for pt in approx]
                if len(pts) >= 3:
                    contours.append(pts)

            self.progress.emit(f"[CTD] 提取了 {len(contours)} 个多边形轮廓")
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

        # 设置为非模态窗口
        self.setWindowModality(QtCore.Qt.NonModal)

        # 添加最小化按钮
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowMinimizeButtonHint)

        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle(self.tr("掩膜生成设置"))
        self.setMinimumWidth(320)
        self.setMinimumHeight(700)
        self.resize(320, 720)

        # 主布局
        main_layout = QtWidgets.QVBoxLayout()

        # === 生成范围 ===
        scope_group = QtWidgets.QGroupBox(self.tr("生成范围"))
        scope_layout = QtWidgets.QVBoxLayout()

        scope_row = QtWidgets.QHBoxLayout()
        self.current_page_radio = QtWidgets.QRadioButton(self.tr("当前页面"))
        self.current_page_radio.setChecked(True)
        self.all_pages_radio = QtWidgets.QRadioButton(self.tr("所有页面"))
        scope_row.addWidget(self.current_page_radio)
        scope_row.addWidget(self.all_pages_radio)
        scope_row.addStretch()
        scope_layout.addLayout(scope_row)

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

        # 自动清理框外 mask 多边形开关
        self.auto_clean_checkbox = QtWidgets.QCheckBox(self.tr("自动清理框外多边形"))
        self.auto_clean_checkbox.setChecked(True)  # 默认勾选
        self.auto_clean_checkbox.setToolTip(self.tr("勾选后，生成完多边形会自动删除不在标注框内的 mask 多边形"))
        scope_layout.addWidget(self.auto_clean_checkbox)

        # 排除标签设置
        scope_layout.addSpacing(10)
        exclude_row = QtWidgets.QHBoxLayout()
        exclude_row.addWidget(QtWidgets.QLabel(self.tr("排除标签:")))
        self.exclude_labels_edit = QtWidgets.QLineEdit()
        self.exclude_labels_edit.setPlaceholderText(self.tr("如: other,background，逗号分隔多标签"))
        saved_exclude = ""
        try:
            if self.parent_widget and hasattr(self.parent_widget, '_config'):
                saved_exclude = self.parent_widget._config.get("mask_exclude_labels", "")
        except Exception:
            pass
        self.exclude_labels_edit.setText(saved_exclude if saved_exclude else "other")
        self.exclude_labels_edit.setToolTip(self.tr("跳过这些标签的标注框，不参与掩膜生成"))
        self.exclude_labels_edit.editingFinished.connect(self._save_exclude_labels)
        exclude_row.addWidget(self.exclude_labels_edit, 1)
        scope_layout.addLayout(exclude_row)

        scope_group.setLayout(scope_layout)
        main_layout.addWidget(scope_group)

        # === 掩膜参数调整 ===
        param_group = QtWidgets.QGroupBox(self.tr("掩膜参数"))
        param_layout = QtWidgets.QVBoxLayout()

        param_grid = QtWidgets.QGridLayout()
        param_grid.setSpacing(2)
        param_grid.setColumnStretch(4, 1)  # 第5列吃多余空间

        # 第1行：整体大小 | 向上延伸
        param_grid.addWidget(QtWidgets.QLabel(self.tr("整体大小")), 0, 0)
        self.size_spin = QtWidgets.QSpinBox()
        self.size_spin.setRange(20, 999)
        self.size_spin.setValue(100)
        self.size_spin.setSuffix("%")
        self.size_spin.setMaximumWidth(80)
        param_grid.addWidget(self.size_spin, 0, 1)

        param_grid.addWidget(QtWidgets.QLabel(self.tr("向上延伸")), 0, 2)
        self.extend_top_spin = QtWidgets.QSpinBox()
        self.extend_top_spin.setRange(0, 999)
        self.extend_top_spin.setSuffix("px")
        self.extend_top_spin.setMaximumWidth(80)
        param_grid.addWidget(self.extend_top_spin, 0, 3)

        # 第2行：向下延伸 | 向左延伸
        param_grid.addWidget(QtWidgets.QLabel(self.tr("向下延伸")), 1, 0)
        self.extend_bottom_spin = QtWidgets.QSpinBox()
        self.extend_bottom_spin.setRange(0, 999)
        self.extend_bottom_spin.setSuffix("px")
        self.extend_bottom_spin.setMaximumWidth(80)
        param_grid.addWidget(self.extend_bottom_spin, 1, 1)

        param_grid.addWidget(QtWidgets.QLabel(self.tr("向左延伸")), 1, 2)
        self.extend_left_spin = QtWidgets.QSpinBox()
        self.extend_left_spin.setRange(0, 999)
        self.extend_left_spin.setSuffix("px")
        self.extend_left_spin.setMaximumWidth(80)
        param_grid.addWidget(self.extend_left_spin, 1, 3)

        # 第3行：向右延伸 | 轮廓膨胀
        param_grid.addWidget(QtWidgets.QLabel(self.tr("向右延伸")), 2, 0)
        self.extend_right_spin = QtWidgets.QSpinBox()
        self.extend_right_spin.setRange(0, 999)
        self.extend_right_spin.setSuffix("px")
        self.extend_right_spin.setMaximumWidth(80)
        param_grid.addWidget(self.extend_right_spin, 2, 1)

        param_grid.addWidget(QtWidgets.QLabel(self.tr("轮廓膨胀")), 2, 2)
        self.dilate_kernel_spin = QtWidgets.QSpinBox()
        self.dilate_kernel_spin.setRange(0, 100)
        self.dilate_kernel_spin.setValue(3)
        self.dilate_kernel_spin.setSuffix("px")
        self.dilate_kernel_spin.setMaximumWidth(80)
        param_grid.addWidget(self.dilate_kernel_spin, 2, 3)
        # 空列吸收右边多余空间，让输入框靠左
        param_grid.addItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum), 0, 4)

        param_layout.addLayout(param_grid)

        param_group.setLayout(param_layout)
        main_layout.addWidget(param_group)

        # === 掩膜输出格式：背景 + 掩膜 两组独立的颜色/透明度 ===
        color_group = QtWidgets.QGroupBox(self.tr("掩膜输出格式"))
        color_layout = QtWidgets.QVBoxLayout()

        def _build_color_row(label_text, default_rgb, choose_slot, attr_color,
                             attr_btn, attr_spin):
            """构造一行：颜色按钮 + 透明度 spin"""
            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(QtWidgets.QLabel(self.tr(label_text)))
            color_btn = QtWidgets.QPushButton()
            setattr(self, attr_btn, color_btn)
            setattr(self, attr_color, QtGui.QColor(*default_rgb))
            self._update_color_button(getattr(self, attr_color), color_btn)
            color_btn.clicked.connect(choose_slot)
            row_layout.addWidget(color_btn)
            row_layout.addSpacing(12)
            row_layout.addWidget(QtWidgets.QLabel(self.tr("透明度:")))
            spin = QtWidgets.QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(100)
            spin.setSuffix("%")
            spin.setMaximumWidth(80)
            setattr(self, attr_spin, spin)
            row_layout.addWidget(spin)
            row_layout.addStretch()
            row_widget.setLayout(row_layout)
            return row_widget

        # 背景（默认黑+100% 不透明 → 等价 BallonsTranslator 风格）
        bg_label = QtWidgets.QLabel(self.tr("背景"))
        bg_label.setStyleSheet("font-weight: bold;")
        color_layout.addWidget(bg_label)
        bg_row = _build_color_row(
            label_text="颜色:",
            default_rgb=(0, 0, 0),
            choose_slot=self.choose_bg_color,
            attr_color="bg_color",
            attr_btn="bg_color_btn",
            attr_spin="bg_opacity_spin",
        )
        color_layout.addWidget(bg_row)

        color_layout.addSpacing(4)

        # 掩膜（默认白+100% 不透明）
        mask_label = QtWidgets.QLabel(self.tr("掩膜"))
        mask_label.setStyleSheet("font-weight: bold;")
        color_layout.addWidget(mask_label)
        mask_row = _build_color_row(
            label_text="颜色:",
            default_rgb=(255, 255, 255),
            choose_slot=self.choose_mask_color,
            attr_color="mask_color",
            attr_btn="mask_color_btn",
            attr_spin="mask_opacity_spin",
        )
        color_layout.addWidget(mask_row)

        color_group.setLayout(color_layout)
        main_layout.addWidget(color_group)

        # === 操作按钮（等宽，QGridLayout + 固定列宽） ===
        button_grid = QtWidgets.QGridLayout()
        button_grid.setSpacing(4)
        button_grid.setContentsMargins(0, 0, 0, 0)

        base_style = "padding: 2px 4px;"

        self.generate_btn = QtWidgets.QPushButton(self.tr("CTD生成多边形"))
        self.generate_btn.setMinimumHeight(35)
        self.generate_btn.setMinimumWidth(100)
        self.generate_btn.setMaximumWidth(150)
        self.generate_btn.setStyleSheet(base_style)
        self.generate_btn.clicked.connect(self.generate_mask)
        button_grid.addWidget(self.generate_btn, 0, 0, QtCore.Qt.AlignLeft)

        direct_box_btn = QtWidgets.QPushButton(self.tr("矩形生成"))
        direct_box_btn.setMinimumHeight(35)
        direct_box_btn.setMinimumWidth(100)
        direct_box_btn.setMaximumWidth(150)
        direct_box_btn.setStyleSheet(base_style)
        direct_box_btn.setToolTip(self.tr("从标注框直接生成掩膜"))
        direct_box_btn.clicked.connect(self.generate_mask_from_boxes)
        button_grid.addWidget(direct_box_btn, 0, 1, QtCore.Qt.AlignLeft)

        otsu_btn = QtWidgets.QPushButton(self.tr("Otsu智能掩膜"))
        otsu_btn.setMinimumHeight(35)
        otsu_btn.setMinimumWidth(100)
        otsu_btn.setMaximumWidth(150)
        otsu_btn.setStyleSheet("background-color:#5cb85c;color:white;border:none;border-radius:4px;padding:2px 4px;")
        otsu_btn.clicked.connect(self.generate_otsu_mask)
        button_grid.addWidget(otsu_btn, 0, 2, QtCore.Qt.AlignLeft)

        otsu_png_btn = QtWidgets.QPushButton(self.tr("Otsu生成PNG"))
        otsu_png_btn.setMinimumHeight(35)
        otsu_png_btn.setMinimumWidth(100)
        otsu_png_btn.setMaximumWidth(150)
        otsu_png_btn.setStyleSheet("background-color:#f0ad4e;color:white;border:none;border-radius:4px;padding:2px 4px;")
        otsu_png_btn.clicked.connect(self.generate_otsu_png)
        button_grid.addWidget(otsu_png_btn, 1, 0, QtCore.Qt.AlignLeft)

        ctd_direct_btn = QtWidgets.QPushButton(self.tr("CTD生成PNG"))
        ctd_direct_btn.setMinimumHeight(35)
        ctd_direct_btn.setMinimumWidth(100)
        ctd_direct_btn.setMaximumWidth(150)
        ctd_direct_btn.setStyleSheet(base_style)
        ctd_direct_btn.clicked.connect(self.generate_mask_with_ctd_direct)
        button_grid.addWidget(ctd_direct_btn, 1, 1, QtCore.Qt.AlignLeft)

        export_btn = QtWidgets.QPushButton(self.tr("多边形生成"))
        export_btn.setMinimumHeight(35)
        export_btn.setMinimumWidth(100)
        export_btn.setMaximumWidth(150)
        export_btn.setStyleSheet(base_style)
        export_btn.clicked.connect(self.export_mask)
        button_grid.addWidget(export_btn, 1, 2, QtCore.Qt.AlignLeft)

        main_layout.addLayout(button_grid)

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

    def _parse_exclude_labels(self):
        """从界面排除标签输入框解析标签列表"""
        text = self.exclude_labels_edit.text().strip()
        if not text:
            return []
        return [label.strip() for label in text.split(',') if label.strip()]

    def _save_exclude_labels(self):
        """保存排除标签到配置文件"""
        try:
            if self.parent_widget and hasattr(self.parent_widget, '_config'):
                cfg = self.parent_widget._config
                cfg["mask_exclude_labels"] = self.exclude_labels_edit.text().strip()
                from anylabeling.config import save_config
                save_config(cfg)
        except Exception:
            pass

    def _update_color_button(self, color, btn):
        """更新颜色按钮显示"""
        color_str = color.name()
        btn.setStyleSheet(
            f"background-color: {color_str}; min-width: 60px; min-height: 25px;"
        )

    def choose_mask_color(self):
        """选择掩膜颜色"""
        color = QtWidgets.QColorDialog.getColor(
            self.mask_color, self, self.tr("选择文字区域颜色")
        )
        if color.isValid():
            self.mask_color = color
            self._update_color_button(self.mask_color, self.mask_color_btn)

    def choose_bg_color(self):
        """选择背景颜色"""
        color = QtWidgets.QColorDialog.getColor(
            self.bg_color, self, self.tr("选择背景颜色")
        )
        if color.isValid():
            self.bg_color = color
            self._update_color_button(self.bg_color, self.bg_color_btn)

    def _color_bgra(self, color, opacity_spin):
        """生成 BGRA 4 元组 (B, G, R, A)"""
        return [
            color.blue(),
            color.green(),
            color.red(),
            int(opacity_spin.value() * 2.55),
        ]

    def _build_mask_rgba(self, mask, bg_bgra, mask_bgra):
        """合成最终 BGRA 掩膜：背景色铺底，掩膜区域覆盖"""
        if mask.ndim == 2:
            h, w = mask.shape
        else:
            h, w = mask.shape[:2]
        out = np.zeros((h, w, 4), dtype=np.uint8)
        out[..., 0] = bg_bgra[0]
        out[..., 1] = bg_bgra[1]
        out[..., 2] = bg_bgra[2]
        out[..., 3] = bg_bgra[3]
        indices = mask > 127
        if indices.any():
            out[indices, 0] = mask_bgra[0]
            out[indices, 1] = mask_bgra[1]
            out[indices, 2] = mask_bgra[2]
            out[indices, 3] = mask_bgra[3]
        return out

    def browse_model_path(self):
        """浏览选择模型路径（已废弃 - CTD 现在通过自动标注加载）"""
        QtWidgets.QMessageBox.information(
            self,
            self.tr("提示"),
            self.tr("请在「自动标注」面板加载 CTD 模型后使用本功能。")
        )

    def reset_model_path(self):
        """重置模型路径为默认"""
        pass

    def get_default_model_path(self):
        """获取默认模型路径（已废弃 - CTD 现在通过自动标注加载）"""
        return None

    def _get_ctd_inference(self):
        """从自动标注已加载的模型中获取 CTDInference 实例。

        Returns:
            CTDInference 实例；如果自动标注未加载 CTD 模型，返回 None。
        """
        if not self.parent_widget:
            return None
        # label_widget 把 model_manager 挂在 auto_labeling_widget 下
        alw = getattr(self.parent_widget, 'auto_labeling_widget', None)
        mm = getattr(alw, 'model_manager', None) if alw else None
        if mm is None:
            # 兜底：直接找 model_manager 属性
            mm = getattr(self.parent_widget, 'model_manager', None)
        if mm is None:
            return None
        loaded = getattr(mm, 'loaded_model_config', None)
        if loaded is None:
            return None
        model_obj = loaded.get("model")
        if model_obj is None:
            return None
        if loaded.get("type") != "comic_text_detector":
            return None
        return getattr(model_obj, 'model', None)

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
            params = {
                'size_scale': self.size_spin.value() / 100.0,
                'extend_top': self.extend_top_spin.value(),
                'extend_bottom': self.extend_bottom_spin.value(),
                'extend_left': self.extend_left_spin.value(),
                'extend_right': self.extend_right_spin.value(),
                'bg_bgra': self._color_bgra(self.bg_color, self.bg_opacity_spin),
                'mask_bgra': self._color_bgra(self.mask_color, self.mask_opacity_spin),
                'dilate_kernel_size': self.dilate_kernel_spin.value(),  # 膨胀核大小
                'direct_ctd': True  # 标记为直接CTD模式
            }

            # 从自动标注获取已加载的 CTD 模型
            ctd_inference = self._get_ctd_inference()
            if ctd_inference is None:
                self.append_log("[失败] 请先在「自动标注」面板加载 CTD 模型")
                self.status_label.setText(self.tr("❌ 未加载 CTD 模型"))
                self.ctd_direct_btn.setEnabled(True)
                return

            self.append_log(f"[CTD生成] 将在 {len(yolo_labels)} 个标注框内使用CTD检测...")

            # 创建Worker线程
            self.worker = MaskGeneratorWorker(
                image_path,
                yolo_labels,  # 传入所有标注框
                ctd_inference,
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
            params = {
                'size_scale': self.size_spin.value() / 100.0,
                'extend_top': self.extend_top_spin.value(),
                'extend_bottom': self.extend_bottom_spin.value(),
                'extend_left': self.extend_left_spin.value(),
                'extend_right': self.extend_right_spin.value(),
                'bg_bgra': self._color_bgra(self.bg_color, self.bg_opacity_spin),
                'mask_bgra': self._color_bgra(self.mask_color, self.mask_opacity_spin),
                'dilate_kernel_size': self.dilate_kernel_spin.value()  # 膨胀核大小
            }

            # 从自动标注获取已加载的 CTD 模型
            ctd_inference = self._get_ctd_inference()
            if ctd_inference is None:
                self.append_log("[失败] 请先在「自动标注」面板加载 CTD 模型")
                self.progress_bar.setVisible(False)
                self.generate_btn.setEnabled(True)
                self.status_label.setText(self.tr("❌ 未加载 CTD 模型"))
                return

            self.append_log(f"[CTD] 使用自动标注已加载的模型")

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

                    # 创建掩膜画布（背景铺底 + 掩膜区域后续合并）
                    bg_bgra = params.get('bg_bgra', [0, 0, 0, 255])
                    mask_bgra = params.get('mask_bgra', [255, 255, 255, 255])
                    mask_rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)
                    mask_rgba[..., 0] = bg_bgra[0]
                    mask_rgba[..., 1] = bg_bgra[1]
                    mask_rgba[..., 2] = bg_bgra[2]
                    mask_rgba[..., 3] = bg_bgra[3]
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

                        # CTD检测 - 使用预加载的CTD模型
                        from anylabeling.services.auto_labeling.ctd.inference import preprocess_img as _ctd_preprocess
                        with torch.no_grad():
                            _crop_in, _ratio, _dw, _dh = _ctd_preprocess(
                                crop, bgr2rgb=False, detect_size=ctd_inference.detect_size,
                                device=ctd_inference.device, half=ctd_inference.half,
                                to_tensor=(ctd_inference.backend == 'torch')
                            )
                            _blks, _mask_tensor, _lines_map = ctd_inference.net(_crop_in)
                        _m = _mask_tensor.squeeze()
                        if hasattr(_m, 'cpu'):
                            _m = _m.cpu().numpy()
                        _m = _m[..., :_m.shape[0] - _dh, :_m.shape[1] - _dw]
                        mask_refined_crop = ((_m > 0.5).astype(np.uint8) * 255)
                        mask_refined_crop = cv2.resize(mask_refined_crop, (x2 - x1, y2 - y1), interpolation=cv2.INTER_LINEAR)

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

                        # 合并到总掩膜（统一 BGRA 合成）
                        mask_indices = result_mask > 127
                        if mask_indices.any():
                            roi = mask_rgba[y1:y2, x1:x2]
                            roi[..., 0][mask_indices] = mask_bgra[0]
                            roi[..., 1][mask_indices] = mask_bgra[1]
                            roi[..., 2][mask_indices] = mask_bgra[2]
                            roi[..., 3][mask_indices] = mask_bgra[3]
                            mask_rgba[y1:y2, x1:x2] = roi

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
            self.append_log("[矩形框] 开始从矩形框直接生成PNG掩膜...")

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

            # 统一合成：根据背景/掩膜颜色和透明度生成 PNG
            bg_bgra = self._color_bgra(self.bg_color, self.bg_opacity_spin)
            mask_bgra = self._color_bgra(self.mask_color, self.mask_opacity_spin)
            mask_rgba = self._build_mask_rgba(mask, bg_bgra, mask_bgra)

            # 使用imencode支持中文路径
            _, buffer = cv2.imencode('.png', mask_rgba)
            buffer.tofile(output_path)
            self.append_log(f"[保存] 矩形掩膜PNG已保存: {output_path}")

            self.append_log(f"[完成] ✅ 矩形PNG生成完成！")
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
            self.append_log("[批量矩形框] 开始批量从矩形框生成PNG...")

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
            bg_bgra = self._color_bgra(self.bg_color, self.bg_opacity_spin)
            mask_bgra = self._color_bgra(self.mask_color, self.mask_opacity_spin)

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

                    # 统一合成掩膜 PNG
                    mask_rgba = self._build_mask_rgba(mask, bg_bgra, mask_bgra)
                    _, buffer = cv2.imencode('.png', mask_rgba)
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

    # ── Otsu 智能掩膜 ──────────────────────────────────────
    def generate_otsu_mask(self):
        """Otsu+连通组件智能掩膜 — 当前页面或所有页面"""
        if self.current_page_radio.isChecked():
            self._otsu_mask_current()
        else:
            self._otsu_mask_all()

    def _otsu_mask_current(self):
        """当前页面 Otsu 掩膜生成"""
        try:
            self.log_text.clear()
            self.append_log("[Otsu] 开始智能掩膜生成...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.generate_btn.setEnabled(False)

            if not self.parent_widget or not hasattr(self.parent_widget, 'filename'):
                raise Exception("无法获取当前图片信息")
            image_path = self.parent_widget.filename
            if not image_path:
                raise Exception("没有打开图片")

            json_path = os.path.splitext(image_path)[0] + '.json'
            if not os.path.exists(json_path):
                raise Exception(f"未找到JSON: {json_path}")

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 清空旧 mask 多边形
            if self.clear_old_polygons_checkbox.isChecked():
                old_count = len(data.get('shapes', []))
                data['shapes'] = [
                    s for s in data.get('shapes', [])
                    if not (s.get('label') == 'mask' and s.get('shape_type') == 'polygon')
                ]
                new_count = len(data['shapes'])
                if old_count != new_count:
                    self.append_log(f"[清理] 删除了 {old_count - new_count} 个旧 mask 多边形")

            # 读取排除标签
            exclude_labels = self._parse_exclude_labels()
            shapes = data.get('shapes', [])
            if exclude_labels:
                before = len(shapes)
                shapes = [s for s in shapes if s.get('label', '') not in exclude_labels]
                self.append_log(f"[过滤] 排除:{exclude_labels}，{before}→{len(shapes)} 个框")

            from PIL import Image
            pil_img = Image.open(image_path)
            img_rgb = np.array(pil_img.convert('RGB'))

            from anylabeling.services.text_splitter.mask_generator import generate_text_mask

            self._process_otsu_shapes(img_rgb, shapes, image_path, data, json_path)

            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)
            self.status_label.setText(self.tr("✅ Otsu掩膜生成完成"))

            # 刷新画布
            if self.parent_widget and hasattr(self.parent_widget, 'load_file'):
                self.parent_widget.load_file(self.parent_widget.filename)

        except Exception as e:
            import traceback
            self.append_log(f"[错误] {e}")
            self.append_log(traceback.format_exc())
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)
            self.status_label.setText(self.tr(f"❌ 失败: {e}"))

    def _otsu_mask_all(self):
        """所有页面批量 Otsu 掩膜"""
        try:
            self.log_text.clear()
            self.append_log("[Otsu] 开始批量智能掩膜...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.generate_btn.setEnabled(False)

            image_list = self.parent_widget.image_list
            total = len(image_list)
            processed = 0

            # 读取排除标签
            exclude_labels = self._parse_exclude_labels()
            if exclude_labels:
                self.append_log(f"[过滤] 排除: {exclude_labels}")

            from PIL import Image
            from anylabeling.services.text_splitter.mask_generator import generate_text_mask

            for idx, image_path in enumerate(image_list):
                json_path = os.path.splitext(image_path)[0] + '.json'
                if not os.path.exists(json_path):
                    continue

                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 清空旧 mask 多边形
                if self.clear_old_polygons_checkbox.isChecked():
                    data['shapes'] = [
                        s for s in data.get('shapes', [])
                        if not (s.get('label') == 'mask' and s.get('shape_type') == 'polygon')
                    ]

                shapes = data.get('shapes', [])
                if not shapes:
                    continue

                # 应用排除标签过滤
                if exclude_labels:
                    shapes = [s for s in shapes if s.get('label', '') not in exclude_labels]
                    if not shapes:
                        continue

                pil_img = Image.open(image_path)
                img_rgb = np.array(pil_img.convert('RGB'))

                self.append_log(f"[{idx+1}/{total}] {os.path.basename(image_path)}")
                self._process_otsu_shapes(img_rgb, shapes, image_path, data, json_path)

                processed += 1
                self.progress_bar.setValue(int(processed / total * 100))
                QtCore.QCoreApplication.processEvents()

            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)
            self.append_log(f"[Otsu] ✅ 批量完成！处理了 {processed}/{total} 个文件")
            self.status_label.setText(self.tr(f"✅ Otsu批量完成 ({processed}文件)"))

            # 刷新画布
            if self.parent_widget and hasattr(self.parent_widget, 'load_file'):
                self.parent_widget.load_file(self.parent_widget.filename)

        except Exception as e:
            import traceback
            self.append_log(f"[错误] {e}")
            self.append_log(traceback.format_exc())
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)

    def _process_otsu_shapes(self, img_rgb, shapes, image_path, data, json_path):
        """每个标注框 crop（带4px扩展）单独 Otsu → 文字轮廓 mask → polygon + PNG（照搬 detect_and_split.py）"""
        from anylabeling.services.text_splitter.mask_generator import generate_text_mask

        # 读取界面参数
        size_scale = self.size_spin.value() / 100.0
        extend_top = self.extend_top_spin.value()
        extend_bottom = self.extend_bottom_spin.value()
        extend_left = self.extend_left_spin.value()
        extend_right = self.extend_right_spin.value()
        dilate_kernel_size = self.dilate_kernel_spin.value()

        h, w = img_rgb.shape[:2]
        mask_full = np.zeros((h, w), dtype=np.uint8)
        modified = False
        box_count = 0

        for shape_data in shapes:
            if shape_data.get('shape_type') not in ('rectangle', 'rotation'):
                continue
            points = shape_data.get('points', [])
            if len(points) < 4:
                continue

            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            x1, y1 = int(min(xs)), int(min(ys))
            x2, y2 = int(max(xs)), int(max(ys))
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            # 照搬 detect_and_split.py：crop 外扩 2px
            # 让白色背景连通到 crop 边缘 → 被 border_mask 过滤掉 → 只剩文字笔画
            expand_px = 2
            ex1, ey1 = max(0, x1 - expand_px), max(0, y1 - expand_px)
            ex2, ey2 = min(w, x2 + expand_px), min(h, y2 + expand_px)
            crop = img_rgb[ey1:ey2, ex1:ex2]
            crop_mask = generate_text_mask(
                crop,
                dilate_kernel_size=dilate_kernel_size,
                dilate_iterations=1,
            )
            if crop_mask is None or crop_mask.size == 0 or not np.any(crop_mask):
                continue

            # 裁剪 mask 到原标注框内并内缩 1px，防止相邻区域误触
            inner_margin = 1
            bx1 = int(x1 - ex1 + inner_margin)
            by1 = int(y1 - ey1 + inner_margin)
            bx2 = int(x2 - ex1 - inner_margin)
            by2 = int(y2 - ey1 - inner_margin)
            # 确保坐标在 crop 范围内
            bx1 = max(0, min(bx1, crop_mask.shape[1]))
            by1 = max(0, min(by1, crop_mask.shape[0]))
            bx2 = max(0, min(bx2, crop_mask.shape[1]))
            by2 = max(0, min(by2, crop_mask.shape[0]))
            if bx2 <= bx1 or by2 <= by1:
                continue
            clip = np.zeros_like(crop_mask)
            clip[by1:by2, bx1:bx2] = crop_mask[by1:by2, bx1:bx2]
            crop_mask = clip
            if not np.any(crop_mask):
                continue

            # ── 合并 size_scale + 方向延伸为单次大核膨胀/腐蚀，保持圆滑 ──
            total_expand = 0
            if size_scale > 1.0:
                total_expand += int((size_scale - 1.0) * 10) + 1
            elif size_scale < 1.0:
                total_expand -= (int((1.0 - size_scale) * 10) + 1)
            total_expand += max(int(extend_top), int(extend_bottom),
                                int(extend_left), int(extend_right))

            if total_expand > 0:
                ksize = total_expand * 2 + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
                crop_mask = cv2.dilate(crop_mask, kernel, iterations=1)
            elif total_expand < 0:
                ksize = abs(total_expand) * 2 + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
                crop_mask = cv2.erode(crop_mask, kernel, iterations=1)

            # 只贴回原标注框内缩区域
            img_y1 = y1 + inner_margin
            img_x1 = x1 + inner_margin
            img_y2 = y2 - inner_margin
            img_x2 = x2 - inner_margin
            box_region = mask_full[img_y1:img_y2, img_x1:img_x2]
            box_mask = crop_mask[by1:by2, bx1:bx2]
            bh = min(box_mask.shape[0], box_region.shape[0])
            bw = min(box_mask.shape[1], box_region.shape[1])
            box_region[:bh, :bw] = np.bitwise_or(box_region[:bh, :bw], box_mask[:bh, :bw])

            crop_area = (img_y2 - img_y1) * (img_x2 - img_x1)
            mask_area = np.count_nonzero(box_mask)
            self.append_log(f"  [{x1},{y1},{x2},{y2}] mask:{mask_area}/{crop_area}={100*mask_area//max(1,crop_area)}% (贴入:[{img_x1},{img_y1},{img_x2},{img_y2}])")

            # polygon（用 crop_mask 在扩展坐标下提取轮廓，偏移到全图坐标）
            contours, _ = cv2.findContours(crop_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                if len(cnt) < 3:
                    continue
                peri = cv2.arcLength(cnt, True)
                # epsilon 从 0.005 降到 0.001，顶点密度提高 5 倍，消除直角折线
                approx = cv2.approxPolyDP(cnt, 0.001 * peri, True)
                abs_pts = [[int(pt[0][0]) + ex1, int(pt[0][1]) + ey1] for pt in approx]
                if len(abs_pts) >= 3:
                    data['shapes'].append({
                        "label": "mask", "score": None,
                        "points": abs_pts,
                        "group_id": None, "description": None, "difficult": False,
                        "shape_type": "polygon", "flags": None, "attributes": {},
                        "kie_linking": [], "is_edited": False, "is_manually_locked": False,
                    })
                    modified = True
                    box_count += 1

        # 保存 JSON polygon
        if modified:
            data.setdefault("manually_edited", True)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # ── 自动清理：删除不在矩形/旋转框内的 mask 多边形 ──
            if self.auto_clean_checkbox.isChecked():
                from anylabeling.services.text_splitter.mask_generator import filter_polygons_by_boxes
                filtered_shapes, auto_removed = filter_polygons_by_boxes(data['shapes'])
                if auto_removed > 0:
                    data['shapes'] = filtered_shapes
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    self.append_log(f"[自动清理] 删除了 {auto_removed} 个框外 mask 多边形")

        # 用实际标注框多边形裁剪 mask_full，删除 AABB 框外噪声
        if np.any(mask_full):
            valid_mask = np.zeros_like(mask_full)
            for s in shapes:
                if s.get('shape_type') in ('rectangle', 'rotation'):
                    pts = s.get('points', [])
                    if len(pts) >= 4:
                        pts_arr = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
                        cv2.fillPoly(valid_mask, [pts_arr], 255)
            mask_full = cv2.bitwise_and(mask_full, valid_mask)

        # 保存 PNG 掩膜图（两张：纯掩膜 + 叠加高亮，跟 detect_and_split.py 一样）
        if np.any(mask_full):
            mask_dir = os.path.join(os.path.dirname(image_path), "mask")
            os.makedirs(mask_dir, exist_ok=True)
            base = os.path.splitext(os.path.basename(image_path))[0]

            # 统一合成掩膜 PNG
            bg_bgra = self._color_bgra(self.bg_color, self.bg_opacity_spin)
            mask_bgra = self._color_bgra(self.mask_color, self.mask_opacity_spin)
            mask_rgba = self._build_mask_rgba(mask_full, bg_bgra, mask_bgra)
            _, buf = cv2.imencode('.png', mask_rgba)
            buf.tofile(os.path.join(mask_dir, f"{base}.png"))

        return box_count

    # ── Otsu 纯 PNG（不生成多边形） ─────────────────────────
    def generate_otsu_png(self):
        """Otsu 纯 PNG 掩膜 — 不生成多边形"""
        if self.current_page_radio.isChecked():
            self._otsu_png_current()
        else:
            self._otsu_png_all()

    def _otsu_png_current(self):
        try:
            self.log_text.clear()
            self.append_log("[Otsu PNG] 开始生成掩膜图...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.generate_btn.setEnabled(False)

            if not self.parent_widget or not hasattr(self.parent_widget, 'filename'):
                raise Exception("无法获取当前图片")
            image_path = self.parent_widget.filename
            if not image_path:
                raise Exception("没有打开图片")

            json_path = os.path.splitext(image_path)[0] + '.json'
            if not os.path.exists(json_path):
                raise Exception(f"未找到JSON: {json_path}")

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 读取排除标签
            exclude_labels = self._parse_exclude_labels()
            shapes = data.get('shapes', [])
            if exclude_labels:
                before = len(shapes)
                shapes = [s for s in shapes if s.get('label', '') not in exclude_labels]
                self.append_log(f"[过滤] 排除:{exclude_labels}，{before}→{len(shapes)} 个框")

            from PIL import Image
            pil_img = Image.open(image_path)
            img_rgb = np.array(pil_img.convert('RGB'))

            self._process_otsu_png(img_rgb, shapes, image_path)

            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)
            self.status_label.setText(self.tr("✅ Otsu PNG 完成"))

        except Exception as e:
            import traceback
            self.append_log(f"[错误] {e}")
            self.append_log(traceback.format_exc())
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)

    def _otsu_png_all(self):
        try:
            self.log_text.clear()
            self.append_log("[Otsu PNG] 批量生成...")
            self.progress_bar.setVisible(True)
            self.generate_btn.setEnabled(False)

            image_list = self.parent_widget.image_list
            total = len(image_list)
            processed = 0

            # 读取排除标签
            exclude_labels = self._parse_exclude_labels()
            if exclude_labels:
                self.append_log(f"[过滤] 排除: {exclude_labels}")

            from PIL import Image

            for idx, image_path in enumerate(image_list):
                json_path = os.path.splitext(image_path)[0] + '.json'
                if not os.path.exists(json_path):
                    continue
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                shapes = data.get('shapes', [])
                if not shapes:
                    continue

                # 应用排除标签过滤
                if exclude_labels:
                    shapes = [s for s in shapes if s.get('label', '') not in exclude_labels]
                    if not shapes:
                        continue

                pil_img = Image.open(image_path)
                img_rgb = np.array(pil_img.convert('RGB'))

                self.append_log(f"[{idx+1}/{total}] {os.path.basename(image_path)}")
                self._process_otsu_png(img_rgb, shapes, image_path)

                processed += 1
                self.progress_bar.setValue(int(processed / total * 100))
                QtCore.QCoreApplication.processEvents()

            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)
            self.append_log(f"[Otsu PNG] ✅ 完成 {processed}/{total} 文件")
            self.status_label.setText(self.tr(f"✅ Otsu PNG ({processed}文件)"))

        except Exception as e:
            import traceback
            self.append_log(f"[错误] {e}")
            self.append_log(traceback.format_exc())
            self.progress_bar.setVisible(False)
            self.generate_btn.setEnabled(True)

    def _process_otsu_png(self, img_rgb, shapes, image_path):
        """每个标注框 crop（带4px扩展）单独 Otsu → 文字轮廓 mask → 纯 PNG（照搬 detect_and_split.py）"""
        from anylabeling.services.text_splitter.mask_generator import generate_text_mask

        # 读取界面参数
        size_scale = self.size_spin.value() / 100.0
        extend_top = self.extend_top_spin.value()
        extend_bottom = self.extend_bottom_spin.value()
        extend_left = self.extend_left_spin.value()
        extend_right = self.extend_right_spin.value()
        dilate_kernel_size = self.dilate_kernel_spin.value()

        h, w = img_rgb.shape[:2]
        mask_full = np.zeros((h, w), dtype=np.uint8)

        for shape_data in shapes:
            if shape_data.get('shape_type') not in ('rectangle', 'rotation'):
                continue
            points = shape_data.get('points', [])
            if len(points) < 4:
                continue
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            x1, y1 = int(min(xs)), int(min(ys))
            x2, y2 = int(max(xs)), int(max(ys))
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            # 照搬 detect_and_split.py：crop 外扩 2px
            # 让白色背景连通到 crop 边缘 → 被 border_mask 过滤掉 → 只剩文字笔画
            expand_px = 2
            ex1, ey1 = max(0, x1 - expand_px), max(0, y1 - expand_px)
            ex2, ey2 = min(w, x2 + expand_px), min(h, y2 + expand_px)
            crop = img_rgb[ey1:ey2, ex1:ex2]
            mask = generate_text_mask(
                crop,
                dilate_kernel_size=dilate_kernel_size,
                dilate_iterations=1,
            )
            if mask is None or mask.size == 0 or not np.any(mask):
                continue

            # 裁剪 mask 到原标注框内并内缩 1px，防止相邻区域误触
            inner_margin = 1
            bx1 = int(x1 - ex1 + inner_margin)
            by1 = int(y1 - ey1 + inner_margin)
            bx2 = int(x2 - ex1 - inner_margin)
            by2 = int(y2 - ey1 - inner_margin)
            # 确保坐标在 crop 范围内
            bx1 = max(0, min(bx1, mask.shape[1]))
            by1 = max(0, min(by1, mask.shape[0]))
            bx2 = max(0, min(bx2, mask.shape[1]))
            by2 = max(0, min(by2, mask.shape[0]))
            if bx2 <= bx1 or by2 <= by1:
                continue
            clip = np.zeros_like(mask)
            clip[by1:by2, bx1:bx2] = mask[by1:by2, bx1:bx2]
            mask = clip
            if not np.any(mask):
                continue

            # ── 距离变换膨胀：保持文字轮廓圆滑，不产生直角 ──
            total_expand = 0
            if size_scale > 1.0:
                total_expand += int((size_scale - 1.0) * 10) + 1
            elif size_scale < 1.0:
                total_expand -= (int((1.0 - size_scale) * 10) + 1)
            total_expand += max(int(extend_top), int(extend_bottom),
                                int(extend_left), int(extend_right))

            if total_expand > 0:
                ksize = total_expand * 2 + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
                mask = cv2.dilate(mask, kernel, iterations=1)
            elif total_expand < 0:
                ksize = abs(total_expand) * 2 + 1
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
                mask = cv2.erode(mask, kernel, iterations=1)

            # 只贴回原标注框内缩区域
            box_region = mask_full[y1 + inner_margin:y2 - inner_margin, x1 + inner_margin:x2 - inner_margin]
            box_mask = mask[by1:by2, bx1:bx2]
            bh = min(box_mask.shape[0], box_region.shape[0])
            bw = min(box_mask.shape[1], box_region.shape[1])
            box_region[:bh, :bw] = np.bitwise_or(
                box_region[:bh, :bw], box_mask[:bh, :bw]
            )

        if not np.any(mask_full):
            self.append_log("  (无有效掩膜)")
            return

        # 用实际标注框多边形裁剪 mask_full，删除 AABB 框外噪声
        if np.any(mask_full):
            valid_mask = np.zeros_like(mask_full)
            for s in shapes:
                if s.get('shape_type') in ('rectangle', 'rotation'):
                    pts = s.get('points', [])
                    if len(pts) >= 4:
                        pts_arr = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
                        cv2.fillPoly(valid_mask, [pts_arr], 255)
            mask_full = cv2.bitwise_and(mask_full, valid_mask)

        # 保存 PNG
        mask_dir = os.path.join(os.path.dirname(image_path), "mask")
        os.makedirs(mask_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(image_path))[0]

        bg_bgra = self._color_bgra(self.bg_color, self.bg_opacity_spin)
        mask_bgra = self._color_bgra(self.mask_color, self.mask_opacity_spin)
        mask_rgba = self._build_mask_rgba(mask_full, bg_bgra, mask_bgra)
        _, buf = cv2.imencode('.png', mask_rgba)
        buf.tofile(os.path.join(mask_dir, f"{base}.png"))
        self.append_log(f"  → {mask_dir}/{base}.png")

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
        params = {
            'size_scale': self.size_spin.value() / 100.0,
            'extend_top': self.extend_top_spin.value(),
            'extend_bottom': self.extend_bottom_spin.value(),
            'extend_left': self.extend_left_spin.value(),
            'extend_right': self.extend_right_spin.value(),
            'bg_bgra': self._color_bgra(self.bg_color, self.bg_opacity_spin),
            'mask_bgra': self._color_bgra(self.mask_color, self.mask_opacity_spin),
            'dilate_kernel_size': self.dilate_kernel_spin.value(),  # 膨胀核大小
        }

        # 获取模型路径
        # 从自动标注获取已加载的 CTD 模型
        ctd_inference = self._get_ctd_inference()
        if ctd_inference is None:
            self.append_log("[失败] 请先在「自动标注」面板加载 CTD 模型")
            self.status_label.setText(self.tr("❌ 未加载 CTD 模型"))
            self.generate_btn.setEnabled(True)
            return

        self.append_log(f"[开始] 使用自动标注已加载的CTD模型...")

        # 创建Worker线程（直接传参数，不再使用subprocess）
        # save_png=False: 生成掩膜时不保存PNG，只提取轮廓
        self.worker = MaskGeneratorWorker(image_path, yolo_labels, ctd_inference, output_path, params, save_png=False)
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

            # ── 自动清理：删除不在矩形/旋转框内的 mask 多边形 ──
            if self.auto_clean_checkbox.isChecked():
                self.append_log(f"[自动清理] 正在清理框外 mask 多边形...")
                from anylabeling.services.text_splitter.mask_generator import filter_polygons_by_boxes
                img_path = self.parent_widget.filename
                json_path_c = os.path.splitext(img_path)[0] + '.json'
                with open(json_path_c, 'r', encoding='utf-8') as f:
                    clean_data = json.load(f)
                clean_shapes, clean_removed = filter_polygons_by_boxes(clean_data.get('shapes', []))
                if clean_removed > 0:
                    clean_data['shapes'] = clean_shapes
                    with open(json_path_c, 'w', encoding='utf-8') as f:
                        json.dump(clean_data, f, ensure_ascii=False, indent=2)
                    self.append_log(f"[自动清理] 删除了 {clean_removed} 个框外 mask 多边形")
                else:
                    self.append_log(f"[自动清理] 没有需要删除的多边形")

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
            params = {
                'size_scale': self.size_spin.value() / 100.0,
                'extend_top': self.extend_top_spin.value(),
                'extend_bottom': self.extend_bottom_spin.value(),
                'extend_left': self.extend_left_spin.value(),
                'extend_right': self.extend_right_spin.value(),
                'bg_bgra': self._color_bgra(self.bg_color, self.bg_opacity_spin),
                'mask_bgra': self._color_bgra(self.mask_color, self.mask_opacity_spin),
                'dilate_kernel_size': self.dilate_kernel_spin.value()  # 膨胀核大小
            }

            # 从自动标注获取已加载的 CTD 模型
            ctd_inference = self._get_ctd_inference()
            if ctd_inference is None:
                self.append_log("[失败] 请先在「自动标注」面板加载 CTD 模型")
                self.status_label.setText(self.tr("❌ 未加载 CTD 模型"))
                self.progress_bar.setVisible(False)
                self.generate_btn.setEnabled(True)
                return

            import torch
            self.append_log(f"[模型] ✅ 使用自动标注已加载的CTD模型")

            # 获取排除标签列表
            exclude_labels_text = self.exclude_labels_edit.text().strip()
            exclude_labels = []
            if exclude_labels_text:
                exclude_labels = [label.strip() for label in exclude_labels_text.split(',') if label.strip()]
                self.append_log(f"[过滤] 排除标签: {exclude_labels}")

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
                    result = self._run_worker_sync(worker, ctd_inference)

                    if result.get("success"):
                        contours = result.get("contours", [])
                        self.append_log(f"  [完成] 生成 {len(contours)} 个多边形")

                        # 保存到JSON
                        if contours:
                            self._save_contours_to_json_batch(json_path, contours)
                            # ── 自动清理 ──
                            if self.auto_clean_checkbox.isChecked():
                                from anylabeling.services.text_splitter.mask_generator import filter_polygons_by_boxes
                                with open(json_path, 'r', encoding='utf-8') as f:
                                    clean_data = json.load(f)
                                clean_shapes, clean_removed = filter_polygons_by_boxes(clean_data.get('shapes', []))
                                if clean_removed > 0:
                                    clean_data['shapes'] = clean_shapes
                                    with open(json_path, 'w', encoding='utf-8') as f:
                                        json.dump(clean_data, f, ensure_ascii=False, indent=2)
                                    self.append_log(f"  [自动清理] 删除了 {clean_removed} 个框外 mask 多边形")

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
            self.append_log("[多边形] 开始导出多边形PNG掩膜")
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

            self.append_log(f"[尺寸] {img_w}x{img_h}")

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

            self.append_log(f"[多边形] 绘制了 {polygon_count} 个多边形")

            # 确定输出路径
            image_dir = os.path.dirname(image_path)
            image_name = os.path.splitext(os.path.basename(image_path))[0]
            mask_dir = os.path.join(image_dir, "mask")
            os.makedirs(mask_dir, exist_ok=True)
            output_path = os.path.join(mask_dir, f"{image_name}.png")

            # 统一合成掩膜 PNG
            bg_bgra = self._color_bgra(self.bg_color, self.bg_opacity_spin)
            mask_bgra = self._color_bgra(self.mask_color, self.mask_opacity_spin)
            mask_rgba = self._build_mask_rgba(mask, bg_bgra, mask_bgra)

            # 使用imencode支持中文路径
            _, buffer = cv2.imencode('.png', mask_rgba)
            buffer.tofile(output_path)
            self.append_log(f"[导出] 掩膜PNG已保存: {output_path}")

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
            self.append_log("[批量多边形] 开始批量导出所有页面多边形PNG...")

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
            bg_bgra = self._color_bgra(self.bg_color, self.bg_opacity_spin)
            mask_bgra = self._color_bgra(self.mask_color, self.mask_opacity_spin)

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
                    # 统一合成掩膜 PNG
                    mask_rgba = self._build_mask_rgba(mask, bg_bgra, mask_bgra)
                    _, buffer = cv2.imencode('.png', mask_rgba)
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
            ctd_inference = ctd_model

            # 获取设备信息（用于返回值）
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'

            # 1. 全图检测获取最准确掩膜
            from anylabeling.services.auto_labeling.ctd.inference import preprocess_img
            with torch.no_grad():
                img_in, ratio, dw, dh = preprocess_img(
                    img, bgr2rgb=False, detect_size=ctd_inference.detect_size,
                    device=ctd_inference.device, half=ctd_inference.half,
                    to_tensor=(ctd_inference.backend == 'torch')
                )
                blks, mask_tensor, lines_map = ctd_inference.net(img_in)
            mask_out = mask_tensor.squeeze()
            if hasattr(mask_out, 'cpu'):
                mask_out = mask_out.cpu().numpy()
            mask_out = mask_out[..., :mask_out.shape[0] - dh, :mask_out.shape[1] - dw]
            mask_binary = (mask_out > 0.5).astype(np.uint8) * 255
            mask_refined_full = cv2.resize(mask_binary, (img_w, img_h), interpolation=cv2.INTER_LINEAR)

            if mask_refined_full is None or mask_refined_full.size == 0:
                mask = np.zeros((img_h, img_w), dtype=np.uint8)
            else:

                # 2. 局部聚合逻辑：在每个标注框内合并碎片
                mask = np.zeros((img_h, img_w), dtype=np.uint8)
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

            # 创建掩膜画布（背景铺底 + 掩膜区域后续合并）
            bg_bgra = worker.params.get('bg_bgra', [0, 0, 0, 255])
            mask_bgra = worker.params.get('mask_bgra', [255, 255, 255, 255])
            mask_rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)
            mask_rgba[..., 0] = bg_bgra[0]
            mask_rgba[..., 1] = bg_bgra[1]
            mask_rgba[..., 2] = bg_bgra[2]
            mask_rgba[..., 3] = bg_bgra[3]

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

                # 合并到总掩膜（统一 BGRA 合成）
                indices = binary_mask > 0
                if indices.any():
                    roi = mask_rgba[y1_ext:y2_ext, x1_ext:x2_ext]
                    ind_full = indices
                    roi[..., 0][ind_full] = np.maximum(
                        roi[..., 0][ind_full], mask_bgra[0]
                    )
                    roi[..., 1][ind_full] = np.maximum(
                        roi[..., 1][ind_full], mask_bgra[1]
                    )
                    roi[..., 2][ind_full] = np.maximum(
                        roi[..., 2][ind_full], mask_bgra[2]
                    )
                    roi[..., 3][ind_full] = np.maximum(
                        roi[..., 3][ind_full], mask_bgra[3]
                    )
                    mask_rgba[y1_ext:y2_ext, x1_ext:x2_ext] = roi

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
