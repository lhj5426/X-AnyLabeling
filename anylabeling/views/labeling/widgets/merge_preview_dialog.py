import math
import os

from PyQt5 import QtCore, QtGui, QtWidgets

from ....services import merger


# 合并组配色（同组同色；单独一组的框用灰色）
GROUP_COLORS = [
    QtGui.QColor(0x2e, 0xcc, 0x71),
    QtGui.QColor(0xe7, 0x4c, 0x3c),
    QtGui.QColor(0x34, 0x98, 0xdb),
    QtGui.QColor(0xf3, 0x9c, 0x12),
    QtGui.QColor(0x9b, 0x59, 0xb6),
    QtGui.QColor(0x1a, 0xbc, 0x9c),
    QtGui.QColor(0xe6, 0x7e, 0x22),
    QtGui.QColor(0x00, 0xa8, 0xff),
]
SINGLETON_COLOR = QtGui.QColor(0x8a, 0x8a, 0x8a)


def load_qimage(path):
    """读取图片为 QImage，失败时回退到 Pillow。"""
    reader = QtGui.QImageReader(path)
    reader.setAutoTransform(True)
    image = reader.read()
    if image is None or image.isNull():
        try:
            from PIL import Image
            pil = Image.open(path).convert("RGBA")
            data = pil.tobytes("raw", "RGBA")
            image = QtGui.QImage(data, pil.width, pil.height, pil.width * 4, QtGui.QImage.Format_RGBA8888)
            image = image.copy()
        except Exception:
            image = None
    return image


def shape_polygon(shape):
    """把 shape 的 points 转成 QPolygonF，保留旋转矩形的倾斜形状。"""
    pts = shape.get("points") or []
    if len(pts) >= 2:
        return QtGui.QPolygonF([QtCore.QPointF(p[0], p[1]) for p in pts])
    box = merger.get_bounding_box(shape)
    return QtGui.QPolygonF([
        QtCore.QPointF(box[0], box[1]), QtCore.QPointF(box[2], box[1]),
        QtCore.QPointF(box[2], box[3]), QtCore.QPointF(box[0], box[3]),
    ])


def merged_rect_polygon(group):
    """合并成水平矩形：取组内所有点的轴对齐外接矩形。"""
    boxes = [merger.get_bounding_box(s) for s in group]
    box = [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]
    return QtGui.QPolygonF([
        QtCore.QPointF(box[0], box[1]), QtCore.QPointF(box[2], box[1]),
        QtCore.QPointF(box[2], box[3]), QtCore.QPointF(box[0], box[3]),
    ])


def merged_rotation_polygon(group):
    """合并成旋转矩形：方向与 perform_merge 保持一致。
    组内方向相同时沿用原始 direction，否则用最小面积外接矩形（MABR）角度。"""
    all_points = [p for s in group for p in (s.get("points") or [])]
    if not all_points:
        return merged_rect_polygon(group)
    cx, cy, width, height, mab_angle = merger.get_mabr_from_points(all_points)

    first_direction = group[0].get("direction")
    all_same_direction = all(s.get("direction") == first_direction for s in group)
    final_angle = mab_angle
    if all_same_direction:
        final_angle = first_direction if first_direction is not None else 0

    cos_a = math.cos(final_angle)
    sin_a = math.sin(final_angle)
    half_w = width / 2
    half_h = height / 2
    corners = [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
    pts = []
    for dx, dy in corners:
        x = dx * cos_a - dy * sin_a + cx
        y = dx * sin_a + dy * cos_a + cy
        pts.append(QtCore.QPointF(x, y))
    return QtGui.QPolygonF(pts)


class PreviewItem(QtWidgets.QGraphicsPixmapItem):
    """承载图片，并在其上绘制「合并后的结果框」。"""

    def __init__(self):
        super().__init__()
        self.setTransformationMode(QtCore.Qt.SmoothTransformation)
        self.setShapeMode(QtWidgets.QGraphicsPixmapItem.BoundingRectShape)
        self.merged_boxes = []    # (QPolygonF, QColor, is_merged, text)
        self.overlap_labels = []  # (x, y, text)

    def set_preview_data(self, merged_boxes, overlap_labels):
        self.merged_boxes = merged_boxes
        self.overlap_labels = overlap_labels
        self.update()

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)

        scale = painter.transform().m11()
        if scale == 0:
            scale = 1.0
        inv = 1.0 / scale

        for poly, color, is_merged, text in self.merged_boxes:
            pen = QtGui.QPen(color)
            pen.setWidth(3 if is_merged else 2)
            pen.setCosmetic(True)
            painter.setPen(pen)

            if is_merged:
                fill = QtGui.QColor(color)
                fill.setAlpha(45)
                painter.setBrush(QtGui.QBrush(fill))
            else:
                painter.setBrush(QtCore.Qt.NoBrush)

            painter.drawPolygon(poly)

            if text:
                self._draw_label(painter, poly.boundingRect().topLeft(), text, inv, QtGui.QColor(0xff, 0xe0, 0x66), centered=False)

        # 重叠比例标注（居中显示在重叠区域）
        for x, y, text in self.overlap_labels:
            self._draw_label(painter, QtCore.QPointF(x, y), text, inv, QtGui.QColor(0x7f, 0xd4, 0xff), centered=True)

    def _draw_label(self, painter, pos, text, inv, text_color, centered=False):
        painter.save()
        painter.translate(pos)
        painter.scale(inv, inv)

        font = QtGui.QFont("Arial", 9)
        painter.setFont(font)
        fm = QtGui.QFontMetrics(font)
        w = fm.horizontalAdvance(text) + 10
        h = fm.height() + 6
        if centered:
            bg = QtCore.QRectF(-w / 2, -h / 2, w, h)
        else:
            bg = QtCore.QRectF(2, 2, w, h)

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(18, 18, 18, 210)))
        painter.drawRoundedRect(bg, 4, 4)
        painter.setPen(QtGui.QPen(text_color))
        painter.drawText(bg, QtCore.Qt.AlignCenter, text)
        painter.restore()


class MergePreviewDialog(QtWidgets.QDialog):
    """合并预览：显示当前图片上「合并后的结果框」，随参数调整实时更新。"""

    def __init__(self, merge_dialog, parent=None):
        super().__init__(parent)
        self.merge_dialog = merge_dialog
        self.labeling_widget = merge_dialog.parent_widget

        self.setWindowTitle("合并预览")
        self.resize(1000, 800)
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowMinMaxButtonsHint |
            QtCore.Qt.WindowCloseButtonHint |
            QtCore.Qt.WindowStaysOnTopHint
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 顶部状态栏
        top = QtWidgets.QHBoxLayout()
        self.status_label = QtWidgets.QLabel("准备就绪")
        self.status_label.setStyleSheet("color:#1f1f1f; font-weight:bold;")
        top.addWidget(self.status_label)
        top.addStretch()
        self.pin_btn = QtWidgets.QPushButton("置顶")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(True)
        self.pin_btn.setToolTip("保持预览窗口在设置窗口之上，方便边调参数边看预览")
        self.pin_btn.toggled.connect(self._toggle_pin)
        top.addWidget(self.pin_btn)
        fit_btn = QtWidgets.QPushButton("适应窗口")
        fit_btn.clicked.connect(self.fit_view)
        top.addWidget(fit_btn)
        refresh_btn = QtWidgets.QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        # 画布
        self.scene = QtWidgets.QGraphicsScene()
        self.scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#1e1e1e")))
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self.view.setFrameShape(QtWidgets.QFrame.NoFrame)
        layout.addWidget(self.view, 1)

        self.view.installEventFilter(self)

        self.preview_item = PreviewItem()
        self.scene.addItem(self.preview_item)

        # 实时刷新（参数变化后去抖刷新）
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(150)
        self._refresh_timer.timeout.connect(self.refresh)

        self._connect_live_refresh()
        self._connect_page_change()

    # ---- 实时刷新绑定 ----
    def _connect_live_refresh(self):
        md = self.merge_dialog
        widgets = [
            (md.max_vertical_gap, "valueChanged"),
            (md.min_width_overlap_ratio, "valueChanged"),
            (md.max_horizontal_gap, "valueChanged"),
            (md.min_height_overlap_ratio, "valueChanged"),
            (md.color_tolerance, "valueChanged"),
            (md.merge_mode, "currentIndexChanged"),
            (md.label_merge_strategy, "currentIndexChanged"),
            (md.merge_by_color, "toggled"),
            (md.require_same_label, "toggled"),
            (md.use_specific_groups, "toggled"),
            (md.enable_exclude_labels, "toggled"),
            (md.radio_output_rectangle, "toggled"),
            (md.radio_output_rotation, "toggled"),
        ]
        for w, sig in widgets:
            getattr(w, sig).connect(self._schedule_refresh)
        if hasattr(md, "exclude_labels"):
            md.exclude_labels.editingFinished.connect(self._schedule_refresh)

    def _connect_page_change(self):
        fw = getattr(self.labeling_widget, "file_list_widget", None)
        if fw is not None:
            try:
                fw.currentRowChanged.connect(self._on_page_changed)
            except Exception:
                pass

    def _schedule_refresh(self, *args):
        self._refresh_timer.start()

    def _on_page_changed(self, row):
        self._fitted = False
        self._refresh_timer.start()

    # ---- 数据加载与绘制 ----
    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self.refresh)

    def _current_image_path(self):
        return getattr(self.labeling_widget, "filename", None)

    def refresh(self):
        image_path = self._current_image_path()
        if not image_path or not os.path.exists(image_path):
            self.status_label.setText("当前没有可预览的图片")
            return

        json_path = os.path.splitext(image_path)[0] + ".json"
        shapes = []
        if os.path.exists(json_path):
            try:
                import json
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                shapes = data.get("shapes", [])
            except Exception:
                shapes = []

        image = load_qimage(image_path)
        if image is None or image.isNull():
            self.status_label.setText("图片加载失败")
            return

        self.preview_item.setPixmap(QtGui.QPixmap.fromImage(image))

        merged_boxes, overlap_labels = self._compute_overlays(shapes)

        self.preview_item.set_preview_data(merged_boxes, overlap_labels)
        self.scene.setSceneRect(self.preview_item.boundingRect())

        if not shapes:
            self.status_label.setText("没有标注框")
        else:
            merged_count = sum(1 for _, _, m, _ in merged_boxes if m)
            self.status_label.setText(
                f"{len(shapes)} 个原框 → {len(merged_boxes)} 个合并框"
                f"（其中 {merged_count} 处发生了合并）· 参数变化自动更新"
            )

        if not getattr(self, "_fitted", False):
            self.fit_view()

    def fit_view(self):
        self._fitted = True
        if not self.preview_item.pixmap().isNull():
            self.view.fitInView(self.preview_item, QtCore.Qt.KeepAspectRatio)

    def _toggle_pin(self, checked):
        flags = self.windowFlags()
        if checked:
            flags |= QtCore.Qt.WindowStaysOnTopHint
        else:
            flags &= ~QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _compute_overlays(self, shapes):
        """根据当前设置计算合并结果，返回合并后的矩形框列表。"""
        config = self.merge_dialog.get_config()
        groups, edges = merger.analyze_merge(shapes, config)

        merged_boxes = []
        group_color = {}
        color_idx = 0
        for group in groups:
            is_merged = len(group) > 1
            if is_merged:
                color = GROUP_COLORS[color_idx % len(GROUP_COLORS)]
                color_idx += 1
                for s in group:
                    group_color[id(s)] = color
            else:
                for s in group:
                    group_color[id(s)] = SINGLETON_COLOR

        # 按组绘制合并后的框：单框按原始形状画（保留旋转），合并组按输出类型画
        output_shape_type = config.get("OUTPUT_SHAPE_TYPE", "rectangle")
        for group in groups:
            is_merged = len(group) > 1
            color = group_color.get(id(group[0]), SINGLETON_COLOR)
            if is_merged:
                if output_shape_type == "rotation":
                    poly = merged_rotation_polygon(group)
                else:
                    poly = merged_rect_polygon(group)
            else:
                poly = shape_polygon(group[0])
            text = f"×{len(group)}" if is_merged else ""
            merged_boxes.append((poly, color, is_merged, text))

        # 重叠比例标注（每处合并标一个）
        overlap_labels = []
        for box_a, box_b, direction, gap, overlap in edges:
            if direction == "上下":
                ox1 = max(box_a[0], box_b[0])
                ox2 = min(box_a[2], box_b[2])
                cx = (ox1 + ox2) / 2
                top_box = box_a if box_a[1] <= box_b[1] else box_b
                bot_box = box_b if top_box is box_a else box_a
                cy = (top_box[3] + bot_box[1]) / 2
                text = f"水平重叠 {overlap:.0f}%"
            else:
                oy1 = max(box_a[1], box_b[1])
                oy2 = min(box_a[3], box_b[3])
                cy = (oy1 + oy2) / 2
                left_box = box_a if box_a[0] <= box_b[0] else box_b
                right_box = box_b if left_box is box_a else box_a
                cx = (left_box[2] + right_box[0]) / 2
                text = f"垂直重叠 {overlap:.0f}%"
            overlap_labels.append((cx, cy, text))

        return merged_boxes, overlap_labels

    def eventFilter(self, obj, event):
        # Ctrl+滚轮缩放
        if obj == self.view and event.type() == QtCore.QEvent.Wheel:
            if event.modifiers() & QtCore.Qt.ControlModifier:
                factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
                self.view.scale(factor, factor)
                return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        self._refresh_timer.stop()
        fw = getattr(self.labeling_widget, "file_list_widget", None)
        if fw is not None:
            try:
                fw.currentRowChanged.disconnect(self._on_page_changed)
            except Exception:
                pass
        super().closeEvent(event)
