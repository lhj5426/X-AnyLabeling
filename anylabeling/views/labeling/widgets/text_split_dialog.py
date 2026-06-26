"""文本分割工具 — 基于 heuristic_lines 的行分割"""
import cv2
import math
import numpy as np
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
    QLabel, QProgressBar, QSpinBox, QWidget,
)
from anylabeling.views.labeling.shape import Shape
from anylabeling.services.text_splitter.core import _detect_lines_and_direction_in_crop
from anylabeling.services.text_splitter.geometry import _line_axis_box, _is_polygon_line


class TextSplitDialog(QDialog):
    split_selected_signal = QtCore.pyqtSignal(str, dict)  # mode, options
    split_page_signal = QtCore.pyqtSignal(str, dict)
    split_range_signal = QtCore.pyqtSignal(int, int, str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle(self.tr("文本分割工具"))
        self.setMinimumWidth(340)
        self._init_ui()

    def tr(self, text):
        return QCoreApplication.translate("TextSplitDialog", text)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(self.tr("将选中/全部矩形框内的文字逐行分割为 line 标签"))
        info.setWordWrap(True)
        layout.addWidget(info)

        self.cb_keep_original = QCheckBox(self.tr("保留原始框"))
        self.cb_keep_original.setChecked(True)
        layout.addWidget(self.cb_keep_original)

        # ── 分割选中 ──
        self.btn_selected = QPushButton(self.tr("分割选中"))
        self.btn_selected.clicked.connect(self._on_selected)
        layout.addWidget(self.btn_selected)

        # ── 分割本页 ──
        self.btn_page = QPushButton(self.tr("分割本页"))
        self.btn_page.clicked.connect(self._on_page)
        layout.addWidget(self.btn_page)

        # ── 分割范围 ──
        range_widget = QWidget()
        range_layout = QHBoxLayout(range_widget)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.addWidget(QLabel(self.tr("从")))
        self.spin_start = QSpinBox()
        self.spin_start.setMinimum(1)
        self.spin_start.setMaximum(9999)
        self.spin_start.setValue(1)
        range_layout.addWidget(self.spin_start)
        range_layout.addWidget(QLabel(self.tr("到")))
        self.spin_end = QSpinBox()
        self.spin_end.setMinimum(1)
        self.spin_end.setMaximum(9999)
        self.spin_end.setValue(10)
        range_layout.addWidget(self.spin_end)
        layout.addWidget(range_widget)

        self.btn_range = QPushButton(self.tr("分割范围"))
        self.btn_range.clicked.connect(self._on_range)
        layout.addWidget(self.btn_range)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def _options(self):
        return {"keep_original": self.cb_keep_original.isChecked()}

    def _on_selected(self):
        self.split_selected_signal.emit("selected", self._options())

    def _on_page(self):
        self.split_page_signal.emit("page", self._options())

    def _on_range(self):
        start = self.spin_start.value()
        end = self.spin_end.value()
        if start > end:
            start, end = end, start
        self.split_range_signal.emit(start, end, "range", self._options())

    def set_progress(self, value, maximum):
        self.progress.setVisible(True)
        self.progress.setMaximum(maximum)
        self.progress.setValue(value)

    def set_status(self, text):
        self.status_label.setText(text)

    @staticmethod
    def _is_line_within_rect(shape, x1, y1, x2, y2):
        """检查 shape 是否是 line 标签且完整的被矩形框住"""
        if shape.label != "line":
            return False
        pts = shape.points
        xs = [p.x() for p in pts]
        ys = [p.y() for p in pts]
        lx1, ly1 = min(xs), min(ys)
        lx2, ly2 = max(xs), max(ys)
        return lx1 >= x1 and lx2 <= x2 and ly1 >= y1 and ly2 <= y2

    @staticmethod
    def _remove_lines_in_rect(shapes, x1, y1, x2, y2):
        """删除在指定矩形范围内的所有 line 形状"""
        removed = []
        for s in list(shapes):
            if TextSplitDialog._is_line_within_rect(s, x1, y1, x2, y2):
                shapes.remove(s)
                removed.append(s)
        return removed

    @staticmethod
    def _make_rotation_shape(label, polygon_pts):
        """从多边形点计算最小外接旋转矩形，创建标准 rotation Shape。

        YOLO-OBB 需要标准旋转矩形，不能是任意四边形。
        用 cv2.minAreaRect → cv2.boxPoints 得到标准矩形的 4 个角点。
        """
        pts = np.array(polygon_pts[:4], dtype=np.float32)
        rect = cv2.minAreaRect(pts)  # ((cx, cy), (w, h), angle)
        corners = cv2.boxPoints(rect)  # 4 个角点，逆时针，起始点是左下

        shape = Shape(label=label, shape_type="rotation")
        for pt in corners:
            shape.add_point(QtCore.QPointF(float(pt[0]), float(pt[1])))
        dx = corners[1][0] - corners[0][0]
        dy = corners[1][1] - corners[0][1]
        shape.direction = math.atan2(dy, dx) % (2 * math.pi)  # XA 内部用弧度 0-2π
        shape.close()
        return shape

    @staticmethod
    def split_canvas_shapes(canvas, image_np, options=None):
        """对画布上的形状做行分割（静态方法，供外部调用）"""
        if options is None:
            options = {}
        shapes = canvas.shapes
        keep = options.get("keep_original", True)
        target_labels_raw = options.get("target_labels", "")

        # 解析指定标签
        target_labels = None
        if target_labels_raw.strip():
            target_labels = {lbl.strip() for lbl in target_labels_raw.split(",") if lbl.strip()}

        # 同时支持 rectangle 和 rotation 形状
        rects = [(s, TextSplitDialog._shape_to_rect(s)) for s in shapes
                 if s.shape_type in ("rectangle", "rotation")]
        total = 0
        for shape, (x1, y1, x2, y2) in rects:
            if target_labels and shape.label not in target_labels:
                continue
            TextSplitDialog._remove_lines_in_rect(shapes, x1 - 4, y1 - 4, x2 + 4, y2 + 4)
            lines = TextSplitDialog._split_rect_static(image_np, x1, y1, x2, y2)
            for line in lines:
                if _is_polygon_line(line):
                    new_shape = TextSplitDialog._make_rotation_shape("line", line)
                else:
                    lx1, ly1, lx2, ly2 = map(int, line)
                    new_shape = Shape(label="line", shape_type="rectangle")
                    new_shape.add_point(QtCore.QPointF(lx1, ly1))
                    new_shape.add_point(QtCore.QPointF(lx2, ly1))
                    new_shape.add_point(QtCore.QPointF(lx2, ly2))
                    new_shape.add_point(QtCore.QPointF(lx1, ly2))
                canvas.shapes.append(new_shape)
                total += 1
            if not keep and shape in canvas.shapes:
                canvas.shapes.remove(shape)
        canvas.update()
        return total

    @staticmethod
    def _shape_to_rect(shape):
        pts = shape.points
        xs = [p.x() for p in pts]
        ys = [p.y() for p in pts]
        return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))

    @staticmethod
    def _split_rect_static(img_np, x1, y1, x2, y2):
        h, w = img_np.shape[:2]
        ex1, ey1 = max(0, x1 - 4), max(0, y1 - 4)
        ex2, ey2 = min(w, x2 + 4), min(h, y2 + 4)
        if ex2 <= ex1 or ey2 <= ey1:
            return [(x1, y1, x2, y2)]
        crop = img_np[ey1:ey2, ex1:ex2]
        lines, direction = _detect_lines_and_direction_in_crop(crop, source_language="")

        # 如果没有多边形（倾斜）行，尝试转置后走 skew 扫描
        has_polygon = any(_is_polygon_line(l) for l in lines)
        if not has_polygon:
            ch, cw = crop.shape[:2]
            transp = np.ascontiguousarray(np.transpose(crop, (1, 0, 2))[:, ::-1, :])
            t_lines, t_dir = _detect_lines_and_direction_in_crop(transp, source_language="")
            t_has_poly = any(_is_polygon_line(l) for l in t_lines)
            if t_has_poly:
                rotated = []
                max_skew = 0
                for l in t_lines:
                    if _is_polygon_line(l):
                        # 转置映射: transposed(tx,ty) → original crop (x=ty, y=ch-1-tx)
                        pts = [[int(round(p[1])), int(round(ch - 1 - p[0]))] for p in l]
                        rect = cv2.minAreaRect(np.array(pts, dtype=np.float32))
                        angle = abs(rect[2]) % 90
                        angle = min(angle, 90 - angle)
                        max_skew = max(max_skew, angle)
                        rotated.append(pts)
                    else:
                        t_lx1, t_ly1, t_lx2, t_ly2 = _line_axis_box(l)
                        rx1, ry1 = t_ly1, ch - 1 - t_lx2
                        rx2, ry2 = t_ly2, ch - 1 - t_lx1
                        rotated.append([rx1, ry1, rx2, ry2])
                # 倾斜角度 < 15° 时，直接用原始 axis-aligned lines，避免水平文字误判
                if max_skew < 15:
                    pass  # 保留原始 lines（axis-aligned boxes）
                else:
                    lines = rotated

        mapped = []
        for l in lines:
            if _is_polygon_line(l):
                pts = [[p[0] + ex1, p[1] + ey1] for p in l]
                mapped.append(pts)
            else:
                lx1, ly1, lx2, ly2 = _line_axis_box(l)
                mapped.append((lx1 + ex1, ly1 + ey1, lx2 + ex1, ly2 + ey1))
        return mapped
