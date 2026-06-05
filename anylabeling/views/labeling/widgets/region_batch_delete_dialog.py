import json
import os.path as osp

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

from ..logger import logger


class RegionBatchDeletePreviewCanvas(QtWidgets.QWidget):
    region_changed = QtCore.pyqtSignal(object)

    FIT_HEIGHT = "fit_height"
    FIT_WIDTH = "fit_width"
    MANUAL_ZOOM = "manual"

    def __init__(
        self,
        image,
        shapes,
        parent=None,
        show_labels=True,
        show_scores=True,
        show_order=True,
        config=None,
    ):
        super().__init__(parent)
        self.pixmap = QtGui.QPixmap.fromImage(image) if image is not None else QtGui.QPixmap()
        self.shapes = list(shapes or [])
        self.show_labels = show_labels
        self.show_scores = show_scores
        self.show_order = show_order
        self.config = config or {}
        self.region = None
        self._scale = 1.0
        self._offset = QtCore.QPointF(0, 0)
        self._zoom_mode = self.FIT_HEIGHT
        self._manual_scale = 1.0
        self._scroll_area = None
        self._region_anchor = None
        self._press_pos = None
        self._press_image_pos = None
        self._panning = False
        self._zoom_tip_text = ""
        self._zoom_tip_timer = QtCore.QTimer(self)
        self._zoom_tip_timer.setSingleShot(True)
        self._zoom_tip_timer.timeout.connect(self._hide_zoom_tip)
        self.setMinimumSize(1, 1)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

    def set_scroll_area(self, scroll_area):
        self._scroll_area = scroll_area
        if scroll_area is not None:
            scroll_area.viewport().installEventFilter(self)
        self._update_canvas_size()

    def eventFilter(self, watched, event):
        if (
            self._scroll_area is not None
            and watched is self._scroll_area.viewport()
            and event.type() == QtCore.QEvent.Resize
        ):
            QtCore.QTimer.singleShot(0, self._update_canvas_size)
        return super().eventFilter(watched, event)

    def set_data(
        self,
        image,
        shapes,
        show_labels=True,
        show_scores=True,
        show_order=True,
        preserve_view=False,
    ):
        zoom_mode = self._zoom_mode
        manual_scale = self._manual_scale
        region = self.region
        h_ratio = 0.0
        v_ratio = 0.0
        if preserve_view and self._scroll_area is not None:
            hbar = self._scroll_area.horizontalScrollBar()
            vbar = self._scroll_area.verticalScrollBar()
            h_ratio = hbar.value() / hbar.maximum() if hbar.maximum() else 0.0
            v_ratio = vbar.value() / vbar.maximum() if vbar.maximum() else 0.0

        self.pixmap = QtGui.QPixmap.fromImage(image) if image is not None else QtGui.QPixmap()
        self.shapes = list(shapes or [])
        self.show_labels = show_labels
        self.show_scores = show_scores
        self.show_order = show_order
        self.region = region if preserve_view else None
        self._zoom_mode = zoom_mode if preserve_view else self.FIT_HEIGHT
        self._manual_scale = manual_scale if preserve_view else 1.0
        self._region_anchor = None
        self._panning = False
        self.region_changed.emit(self.region)
        self._update_canvas_size()
        if preserve_view and self._scroll_area is not None:
            hbar = self._scroll_area.horizontalScrollBar()
            vbar = self._scroll_area.verticalScrollBar()
            hbar.setValue(int(round(hbar.maximum() * h_ratio)))
            vbar.setValue(int(round(vbar.maximum() * v_ratio)))
        self.update()

    def update_display_options(self, show_labels=True, show_scores=True, show_order=True):
        self.show_labels = show_labels
        self.show_scores = show_scores
        self.show_order = show_order
        self.update()

    def _available_size(self):
        if self._scroll_area is not None:
            size = self._scroll_area.viewport().size()
        else:
            size = self.size()
        return QtCore.QSize(max(1, size.width()), max(1, size.height()))

    def _scale_for_mode(self, available_size):
        if self.pixmap.isNull():
            return 1.0
        if self._zoom_mode == self.FIT_WIDTH:
            return available_size.width() / self.pixmap.width()
        if self._zoom_mode == self.FIT_HEIGHT:
            return available_size.height() / self.pixmap.height()
        return self._manual_scale

    def _update_canvas_size(self):
        if self.pixmap.isNull():
            available = self._available_size()
            self.resize(available)
            return
        available = self._available_size()
        self._scale = self._scale_for_mode(available)
        scaled_width = max(1, int(round(self.pixmap.width() * self._scale)))
        scaled_height = max(1, int(round(self.pixmap.height() * self._scale)))
        canvas_width = max(available.width(), scaled_width)
        canvas_height = max(available.height(), scaled_height)
        self.setMinimumSize(canvas_width, canvas_height)
        self.resize(canvas_width, canvas_height)
        self._offset = QtCore.QPointF(
            (canvas_width - scaled_width) / 2.0 if canvas_width > scaled_width else 0,
            (canvas_height - scaled_height) / 2.0 if canvas_height > scaled_height else 0,
        )

    def _image_rect(self):
        if self.pixmap.isNull():
            return QtCore.QRectF()
        self._update_canvas_size()
        width = self.pixmap.width() * self._scale
        height = self.pixmap.height() * self._scale
        return QtCore.QRectF(self._offset.x(), self._offset.y(), width, height)

    def set_zoom_mode(self, mode):
        if self.pixmap.isNull():
            return
        if mode == self.MANUAL_ZOOM:
            self._manual_scale = 1.0
        self._zoom_mode = mode
        self._update_canvas_size()
        if self._scroll_area is not None:
            self._scroll_area.horizontalScrollBar().setValue(0)
            self._scroll_area.verticalScrollBar().setValue(0)
        self._show_zoom_tip()
        self.update()

    def _show_zoom_tip(self):
        self._zoom_tip_text = f"缩放: {int(round(self._scale * 100))}%"
        self._zoom_tip_timer.start(1400)
        self.update()

    def _hide_zoom_tip(self):
        self._zoom_tip_text = ""
        self.update()

    def _screen_to_image(self, point):
        rect = self._image_rect()
        if rect.isNull() or self._scale == 0:
            return QtCore.QPointF()
        x = min(max(point.x(), rect.left()), rect.right())
        y = min(max(point.y(), rect.top()), rect.bottom())
        return QtCore.QPointF(
            (x - self._offset.x()) / self._scale,
            (y - self._offset.y()) / self._scale,
        )

    def _image_to_screen(self, point):
        return QtCore.QPointF(
            self._offset.x() + point.x() * self._scale,
            self._offset.y() + point.y() * self._scale,
        )

    def _set_region(self, p1, p2):
        x1, y1 = min(p1.x(), p2.x()), min(p1.y(), p2.y())
        x2, y2 = max(p1.x(), p2.x()), max(p1.y(), p2.y())
        self.region = (x1, y1, x2, y2) if x2 - x1 >= 1 and y2 - y1 >= 1 else None
        self.region_changed.emit(self.region)
        self.update()

    def mousePressEvent(self, event):
        if self.pixmap.isNull():
            return
        if event.button() == Qt.LeftButton:
            self._press_pos = QtCore.QPointF(event.pos())
            self._press_image_pos = self._screen_to_image(self._press_pos)
            self._panning = False

    def mouseMoveEvent(self, event):
        pos = QtCore.QPointF(event.pos())
        if self._region_anchor is not None:
            self._set_region(self._region_anchor, self._screen_to_image(pos))
            return
        if event.buttons() & Qt.LeftButton and self._press_pos is not None:
            delta = pos - self._press_pos
            if self._panning or abs(delta.x()) + abs(delta.y()) > 3:
                self._panning = True
                self._scroll_by(-delta.x(), -delta.y())
                self._press_pos = pos
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        release_pos = QtCore.QPointF(event.pos())
        if self._panning:
            self._panning = False
            self._press_pos = None
            self._press_image_pos = None
            return
        if self._region_anchor is None:
            self._region_anchor = self._press_image_pos or self._screen_to_image(release_pos)
            self.region = None
            self.region_changed.emit(self.region)
            self.update()
        else:
            self._set_region(self._region_anchor, self._screen_to_image(release_pos))
            self._region_anchor = None
        self._press_pos = None
        self._press_image_pos = None

    def wheelEvent(self, event):
        if self.pixmap.isNull():
            return
        delta = event.angleDelta()
        if event.modifiers() & Qt.ControlModifier:
            old_image_pos = self._screen_to_image(QtCore.QPointF(event.pos()))
            old_viewport_pos = self._canvas_to_viewport(QtCore.QPointF(event.pos()))
            factor = 1.05 if delta.y() > 0 else 0.95
            self._manual_scale = max(0.02, min(20.0, self._scale * factor))
            self._zoom_mode = self.MANUAL_ZOOM
            self._update_canvas_size()
            new_screen_pos = self._image_to_screen(old_image_pos)
            self._set_scroll_to_canvas_point(new_screen_pos, old_viewport_pos)
            self._show_zoom_tip()
        else:
            self._scroll_by(-delta.x(), -delta.y())
        self.update()
        event.accept()

    def _scroll_by(self, dx, dy):
        if self._scroll_area is None:
            return
        hbar = self._scroll_area.horizontalScrollBar()
        vbar = self._scroll_area.verticalScrollBar()
        hbar.setValue(hbar.value() + int(round(dx)))
        vbar.setValue(vbar.value() + int(round(dy)))

    def _canvas_to_viewport(self, canvas_pos):
        if self._scroll_area is None:
            return canvas_pos
        return QtCore.QPointF(
            canvas_pos.x() - self._scroll_area.horizontalScrollBar().value(),
            canvas_pos.y() - self._scroll_area.verticalScrollBar().value(),
        )

    def _set_scroll_to_canvas_point(self, canvas_pos, viewport_pos):
        if self._scroll_area is None:
            return
        self._scroll_area.horizontalScrollBar().setValue(
            int(round(canvas_pos.x() - viewport_pos.x()))
        )
        self._scroll_area.verticalScrollBar().setValue(
            int(round(canvas_pos.y() - viewport_pos.y()))
        )

    @staticmethod
    def _shape_bbox(shape):
        points = getattr(shape, "points", None) or []
        if not points:
            return None
        xs = [point.x() for point in points]
        ys = [point.y() for point in points]
        return min(xs), min(ys), max(xs), max(ys)

    @staticmethod
    def _shape_center(shape):
        points = getattr(shape, "points", None) or []
        if not points:
            return None
        return QtCore.QPointF(
            sum(point.x() for point in points) / len(points),
            sum(point.y() for point in points) / len(points),
        )

    def _draw_order_circles(self, painter):
        if not self.show_order:
            return
        locked_labels = set()
        if self.config.get("locked_hide_order", True):
            locked_labels = {
                label.strip()
                for label in str(self.config.get("locked_labels", "")).split(",")
                if label.strip()
            }

        shape_orders = {}
        order_index = 0
        label_counters = {}
        for shape in self.shapes:
            label = getattr(shape, "label", "")
            if label in locked_labels and not getattr(shape, "is_session_unlocked", False):
                continue
            order_index += 1
            label_counters[label] = label_counters.get(label, 0) + 1
            shape_orders[id(shape)] = (order_index, label_counters[label])

        painter.save()
        for shape in self.shapes:
            if getattr(shape, "visible", True) is False:
                continue
            if getattr(shape, "label", "") in ["AUTOLABEL_OBJECT", "AUTOLABEL_ADD", "AUTOLABEL_REMOVE"]:
                continue
            global_order, _label_order = shape_orders.get(id(shape), (0, 0))
            if global_order <= 0:
                continue
            center = self._shape_center(shape)
            if center is None:
                continue
            center_screen = self._image_to_screen(center)
            painter.setBrush(QtGui.QBrush(QtGui.QColor(30, 144, 255)))
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
            painter.drawEllipse(center_screen, 12, 12)

            font = QtGui.QFont()
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(255, 255, 255))
            text = str(global_order)
            metrics = QtGui.QFontMetrics(font)
            text_x = center_screen.x() - metrics.horizontalAdvance(text) / 2
            text_y = center_screen.y() + (metrics.ascent() - metrics.descent()) / 2
            painter.drawText(QtCore.QPointF(text_x, text_y), text)
        painter.restore()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(38, 40, 43))
        image_rect = self._image_rect()
        if self.pixmap.isNull():
            return

        painter.drawPixmap(image_rect.toRect(), self.pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        for shape in self.shapes:
            bbox = self._shape_bbox(shape)
            if bbox is None:
                continue
            line_color = QtGui.QColor(getattr(shape, "line_color", QtGui.QColor(255, 44, 120)))
            fill_color = QtGui.QColor(getattr(shape, "fill_color", line_color))
            fill_color.setAlpha(70)
            shape_pen = QtGui.QPen(line_color, 2)
            painter.setPen(shape_pen)
            painter.setBrush(fill_color)
            p1 = self._image_to_screen(QtCore.QPointF(bbox[0], bbox[1]))
            p2 = self._image_to_screen(QtCore.QPointF(bbox[2], bbox[3]))
            rect = QtCore.QRectF(p1, p2).normalized()
            painter.drawRect(rect)

            text_parts = []
            label = str(getattr(shape, "label", "") or "")
            score = getattr(shape, "score", None)
            if self.show_labels and label:
                text_parts.append(label)
            if self.show_scores and score is not None:
                text_parts.append(f"{score:.2f}")
            text = " ".join(text_parts)
            if text:
                tag_width = min(180, max(46, len(text) * 7))
                tag_rect = QtCore.QRectF(rect.left(), rect.top() - 18, tag_width, 18)
                tag_color = QtGui.QColor(line_color)
                tag_color.setAlpha(220)
                painter.fillRect(tag_rect, tag_color)
                luminance = 0.299 * tag_color.red() + 0.587 * tag_color.green() + 0.114 * tag_color.blue()
                painter.setPen(QtGui.QColor(0, 0, 0) if luminance > 150 else QtGui.QColor(255, 255, 255))
                painter.drawText(tag_rect.adjusted(3, 0, -2, 0), Qt.AlignVCenter, text)
                painter.setPen(shape_pen)

        self._draw_order_circles(painter)

        if self.region is not None:
            p1 = self._image_to_screen(QtCore.QPointF(self.region[0], self.region[1]))
            p2 = self._image_to_screen(QtCore.QPointF(self.region[2], self.region[3]))
            rect = QtCore.QRectF(p1, p2).normalized()
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 170, 255), 3))
            painter.setBrush(QtGui.QColor(0, 170, 255, 55))
            painter.drawRect(rect)

        self._draw_zoom_tip(painter)

    def _draw_zoom_tip(self, painter):
        if not self._zoom_tip_text:
            return
        visible_center = self.rect().center()
        if self._scroll_area is not None:
            hbar = self._scroll_area.horizontalScrollBar()
            vbar = self._scroll_area.verticalScrollBar()
            viewport = self._scroll_area.viewport().rect()
            visible_center = QtCore.QPoint(
                hbar.value() + viewport.width() // 2,
                vbar.value() + viewport.height() // 2,
            )

        painter.save()
        font = QtGui.QFont()
        font.setPointSize(10)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        text_rect = metrics.boundingRect(self._zoom_tip_text).adjusted(-18, -10, 18, 10)
        text_rect.moveCenter(visible_center)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.QPen(QtGui.QColor(150, 120, 120, 180), 1))
        painter.setBrush(QtGui.QColor(245, 226, 226, 220))
        painter.drawRoundedRect(QtCore.QRectF(text_rect), 7, 7)
        painter.setPen(QtGui.QColor(35, 35, 35))
        painter.drawText(text_rect, Qt.AlignCenter, self._zoom_tip_text)
        painter.restore()


class RegionBatchDeleteDialog(QtWidgets.QDialog):
    def __init__(
        self,
        labeling_widget,
        image,
        shapes,
        has_image_list,
        show_labels=True,
        show_scores=True,
        show_order=True,
    ):
        super().__init__(labeling_widget)
        self.labeling_widget = labeling_widget
        self.setWindowFlags(
            (self.windowFlags() | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
            & ~Qt.WindowContextHelpButtonHint
        )
        self.setWindowTitle("区域批量删除")
        self.resize(1180, 760)

        layout = QtWidgets.QVBoxLayout(self)
        self.preview_canvas = RegionBatchDeletePreviewCanvas(
            image,
            shapes,
            self,
            show_labels=show_labels,
            show_scores=show_scores,
            show_order=show_order,
            config=getattr(labeling_widget, "_config", {}),
        )
        self.preview_scroll_area = QtWidgets.QScrollArea(self)
        self.preview_scroll_area.setWidget(self.preview_canvas)
        self.preview_scroll_area.setWidgetResizable(False)
        self.preview_scroll_area.setAlignment(Qt.AlignCenter)
        self.preview_scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.preview_canvas.set_scroll_area(self.preview_scroll_area)
        layout.addWidget(self.preview_scroll_area, 1)

        controls = QtWidgets.QHBoxLayout()
        self.region_label = QtWidgets.QLabel("", self)
        controls.addWidget(self.region_label, 1)

        self.fit_height_button = QtWidgets.QPushButton("适应高度", self)
        self.fit_width_button = QtWidgets.QPushButton("适应宽度", self)
        self.zoom_100_button = QtWidgets.QPushButton("100%", self)
        controls.addWidget(self.fit_height_button)
        controls.addWidget(self.fit_width_button)
        controls.addWidget(self.zoom_100_button)

        controls.addWidget(QtWidgets.QLabel("范围", self))
        self.scope_combo = QtWidgets.QComboBox(self)
        self.scope_combo.addItem("当前页", "current")
        self.scope_combo.addItem("全部图片", "all")
        self.scope_combo.setEnabled(bool(has_image_list))
        self.scope_combo.setCurrentIndex(1 if has_image_list else 0)
        controls.addWidget(self.scope_combo)

        controls.addWidget(QtWidgets.QLabel("条件", self))
        self.match_combo = QtWidgets.QComboBox(self)
        self.match_combo.addItem("中心点在区域内", "center")
        self.match_combo.addItem("与区域相交", "intersect")
        self.match_combo.setCurrentIndex(1)
        controls.addWidget(self.match_combo)

        self.same_size_checkbox = QtWidgets.QCheckBox("仅处理相同尺寸", self)
        self.same_size_checkbox.setChecked(True)
        controls.addWidget(self.same_size_checkbox)

        self.labels_edit = QtWidgets.QLineEdit(self)
        self.labels_edit.setPlaceholderText("留空=自动使用当前区域命中的标签；也可手填 other,qipao")
        controls.addWidget(self.labels_edit)

        self.run_button = QtWidgets.QPushButton("执行删除", self)
        self.run_button.setEnabled(False)
        self.close_button = QtWidgets.QPushButton("关闭", self)
        controls.addWidget(self.run_button)
        controls.addWidget(self.close_button)
        layout.addLayout(controls)

        self.preview_canvas.region_changed.connect(self._on_region_changed)
        self.fit_height_button.clicked.connect(
            lambda: self.preview_canvas.set_zoom_mode(
                RegionBatchDeletePreviewCanvas.FIT_HEIGHT
            )
        )
        self.fit_width_button.clicked.connect(
            lambda: self.preview_canvas.set_zoom_mode(
                RegionBatchDeletePreviewCanvas.FIT_WIDTH
            )
        )
        self.zoom_100_button.clicked.connect(
            lambda: self.preview_canvas.set_zoom_mode(
                RegionBatchDeletePreviewCanvas.MANUAL_ZOOM
            )
        )
        self.run_button.clicked.connect(self.run_region_batch_delete)
        self.close_button.clicked.connect(self.hide)

    def update_preview(self, image, shapes, has_image_list, show_labels=True, show_scores=True, show_order=True):
        self.preview_canvas.set_data(
            image,
            shapes,
            show_labels=show_labels,
            show_scores=show_scores,
            show_order=show_order,
            preserve_view=True,
        )
        self.scope_combo.setEnabled(bool(has_image_list))
        self.scope_combo.setCurrentIndex(1 if has_image_list else 0)

    def update_display_options(self, show_labels=True, show_scores=True, show_order=True):
        self.preview_canvas.update_display_options(
            show_labels=show_labels,
            show_scores=show_scores,
            show_order=show_order,
        )

    def _on_region_changed(self, region):
        self.run_button.setEnabled(region is not None)
        if region is None:
            self.region_label.setText("")
            return
        x1, y1, x2, y2 = region
        self.region_label.setText(
            f"区域: x={x1:.1f}, y={y1:.1f}, w={x2 - x1:.1f}, h={y2 - y1:.1f}"
        )

    def get_options(self):
        labels_text = self.labels_edit.text().strip()
        labels = {
            item.strip()
            for item in labels_text.replace("，", ",").split(",")
            if item.strip()
        }
        return {
            "region": self.preview_canvas.region,
            "scope": self.scope_combo.currentData(),
            "match_mode": self.match_combo.currentData(),
            "labels": labels,
            "same_size_only": self.same_size_checkbox.isChecked(),
        }

    @staticmethod
    def _bbox_from_points(points):
        if not points:
            return None
        xs = []
        ys = []
        for point in points:
            try:
                if hasattr(point, "x"):
                    xs.append(float(point.x()))
                    ys.append(float(point.y()))
                else:
                    xs.append(float(point[0]))
                    ys.append(float(point[1]))
            except (TypeError, ValueError, IndexError):
                return None
        if not xs or not ys:
            return None
        return min(xs), min(ys), max(xs), max(ys)

    @staticmethod
    def _bbox_intersects(a, b):
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        return ax1 <= bx2 and ax2 >= bx1 and ay1 <= by2 and ay2 >= by1

    @staticmethod
    def _bbox_center_inside(inner, outer):
        x1, y1, x2, y2 = inner
        ox1, oy1, ox2, oy2 = outer
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        return ox1 <= cx <= ox2 and oy1 <= cy <= oy2

    def _shape_hits_region(self, shape_bbox, region, match_mode):
        if match_mode == "intersect":
            return self._bbox_intersects(shape_bbox, region)
        return self._bbox_center_inside(shape_bbox, region)

    def _label_path_for_image(self, image_path):
        label_path = osp.splitext(image_path)[0] + ".json"
        output_dir = getattr(self.labeling_widget, "output_dir", None)
        if output_dir:
            label_path = osp.join(output_dir, osp.basename(label_path))
        return label_path

    def _labels_hit_by_region_on_current_page(self, region, match_mode):
        hit_labels = set()
        canvas = getattr(self.labeling_widget, "canvas", None)
        for shape in getattr(canvas, "shapes", []) or []:
            shape_bbox = self._bbox_from_points(getattr(shape, "points", []))
            if shape_bbox is None:
                continue
            if self._shape_hits_region(shape_bbox, region, match_mode):
                label = getattr(shape, "label", None)
                if label:
                    hit_labels.add(label)
        return hit_labels

    def _files_to_process(self, scope):
        filename = getattr(self.labeling_widget, "filename", None)
        image_list = list(getattr(self.labeling_widget, "image_list", []) or [])
        if scope == "all" and image_list:
            return image_list
        return [filename] if filename else []

    def _reference_size(self):
        image = getattr(self.labeling_widget, "image", None)
        if image is not None and not image.isNull():
            return int(image.width()), int(image.height())
        return None, None

    @staticmethod
    def _format_counts(counts):
        return ", ".join(f"{label} x{count}" for label, count in sorted(counts.items()))

    def _localize_message_box_buttons(self, box):
        button_texts = {
            QtWidgets.QMessageBox.Yes: "是",
            QtWidgets.QMessageBox.No: "否",
            QtWidgets.QMessageBox.Ok: "确定",
            QtWidgets.QMessageBox.Cancel: "取消",
        }
        for standard_button, text in button_texts.items():
            button = box.button(standard_button)
            if button is not None:
                button.setText(text)

        for button in box.findChildren(QtWidgets.QPushButton):
            if button.text() == "Show Details...":
                button.setText("显示详情")
                button.clicked.connect(
                    lambda _checked=False, message_box=box: QtCore.QTimer.singleShot(
                        0, lambda: self._localize_message_box_buttons(message_box)
                    )
                )
            elif button.text() == "Hide Details...":
                button.setText("隐藏详情")
                button.clicked.connect(
                    lambda _checked=False, message_box=box: QtCore.QTimer.singleShot(
                        0, lambda: self._localize_message_box_buttons(message_box)
                    )
                )

    def _show_message(self, icon, text, details=None):
        box = QtWidgets.QMessageBox(icon, "区域批量删除", text, parent=self)
        if details:
            box.setDetailedText("\n".join(details))
        self._localize_message_box_buttons(box)
        return box.exec_()

    def _add_modified_files_to_filter(self, modified_image_paths):
        if not modified_image_paths:
            return

        unique_paths = list(dict.fromkeys(modified_image_paths))
        widget = self.labeling_widget
        widget.current_filter_config = {
            "mode": "custom_files",
            "value": "",
            "custom_files": unique_paths,
        }

        last_open_dir = getattr(widget, "last_open_dir", None)
        if last_open_dir and osp.exists(last_open_dir):
            widget.import_image_folder(
                last_open_dir,
                load=False,
                recursive=getattr(widget, "_config", {}).get("load_subfolders", False),
                filter_config=widget.current_filter_config,
            )

        current_filename = getattr(widget, "filename", None)
        if current_filename in unique_paths:
            widget.load_file(current_filename)
        else:
            widget.load_file(unique_paths[0])

    def _scan_plan(self, files_to_process, region, match_mode, labels, same_size_only):
        ref_width, ref_height = self._reference_size()
        planned_changes = []
        skipped_size_files = []
        missing_label_files = []
        scan_errors = []
        processed = 0
        label_totals = {}

        for image_path in files_to_process:
            label_path = self._label_path_for_image(image_path)
            if not osp.exists(label_path):
                missing_label_files.append(osp.basename(image_path))
                continue

            try:
                with open(label_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if same_size_only and ref_width and ref_height:
                    image_width = data.get("imageWidth")
                    image_height = data.get("imageHeight")
                    if image_width is None or image_height is None:
                        actual_image = QtGui.QImage(image_path)
                        image_width = actual_image.width()
                        image_height = actual_image.height()
                    if int(image_width) != ref_width or int(image_height) != ref_height:
                        skipped_size_files.append(
                            f"{osp.basename(image_path)} ({image_width}x{image_height})"
                        )
                        continue

                processed += 1
                kept_shapes = []
                removed_count = 0
                file_label_counts = {}

                for shape_dict in data.get("shapes", []) or []:
                    label = shape_dict.get("label", "") or "(empty)"
                    if label not in labels:
                        kept_shapes.append(shape_dict)
                        continue

                    shape_bbox = self._bbox_from_points(shape_dict.get("points", []))
                    if shape_bbox is None:
                        kept_shapes.append(shape_dict)
                        continue

                    if self._shape_hits_region(shape_bbox, region, match_mode):
                        removed_count += 1
                        file_label_counts[label] = file_label_counts.get(label, 0) + 1
                        label_totals[label] = label_totals.get(label, 0) + 1
                    else:
                        kept_shapes.append(shape_dict)

                if removed_count:
                    planned_changes.append(
                        {
                            "image_path": image_path,
                            "label_path": label_path,
                            "data": data,
                            "kept_shapes": kept_shapes,
                            "removed_count": removed_count,
                            "label_counts": file_label_counts,
                        }
                    )
            except Exception as exc:
                scan_errors.append(f"{osp.basename(label_path)}: {exc}")
                logger.error(f"Region batch delete scan failed for {label_path}: {exc}")

        return {
            "planned_changes": planned_changes,
            "skipped_size_files": skipped_size_files,
            "missing_label_files": missing_label_files,
            "scan_errors": scan_errors,
            "processed": processed,
            "label_totals": label_totals,
        }

    def _build_plan_details(self, plan):
        details = []
        if plan["planned_changes"]:
            details.append("将修改:")
            for item in plan["planned_changes"]:
                details.append(
                    f"{osp.basename(item['image_path'])}: 删除 {item['removed_count']} 个 "
                    f"({self._format_counts(item['label_counts'])})"
                )
        if plan["skipped_size_files"]:
            details.append("\n尺寸不同跳过:")
            details.extend(plan["skipped_size_files"])
        if plan["missing_label_files"]:
            details.append("\n缺少 JSON:")
            details.extend(plan["missing_label_files"])
        if plan["scan_errors"]:
            details.append("\n扫描失败:")
            details.extend(plan["scan_errors"])
        return details

    def _confirm_plan(self, files_to_process, region, match_mode, plan):
        match_text = "与区域相交" if match_mode == "intersect" else "中心点在区域内"
        confirm = QtWidgets.QMessageBox(
            QtWidgets.QMessageBox.Question,
            "区域批量删除确认",
            (
                f"将处理 {len(files_to_process)} 个文件，命中 {len(plan['planned_changes'])} 个文件。\n"
                f"删除条件: {match_text}\n"
                f"命中标签: {self._format_counts(plan['label_totals'])}\n"
                f"区域: x={region[0]:.2f}, y={region[1]:.2f}, "
                f"w={region[2] - region[0]:.2f}, h={region[3] - region[1]:.2f}\n"
                "确定继续吗？"
            ),
            parent=self,
        )
        confirm.setDetailedText("\n".join(self._build_plan_details(plan)))
        confirm.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        confirm.setDefaultButton(QtWidgets.QMessageBox.No)
        self._localize_message_box_buttons(confirm)
        return confirm.exec_() == QtWidgets.QMessageBox.Yes

    def _write_plan(self, planned_changes):
        progress = None
        if len(planned_changes) > 1:
            progress = QtWidgets.QProgressDialog(
                "正在执行区域批量删除...", "取消", 0, len(planned_changes), self
            )
            progress.setWindowModality(QtCore.Qt.NonModal)
            progress.show()

        modified_image_paths = []
        write_errors = []
        written_details = []
        deleted_shapes = 0

        for index, item in enumerate(planned_changes, start=1):
            if progress is not None:
                progress.setValue(index - 1)
                progress.setLabelText(f"写入: {osp.basename(item['image_path'])}")
                QtWidgets.QApplication.processEvents()
                if progress.wasCanceled():
                    break

            try:
                item["data"]["shapes"] = item["kept_shapes"]
                with open(item["label_path"], "w", encoding="utf-8") as f:
                    json.dump(item["data"], f, indent=2, ensure_ascii=False)
                modified_image_paths.append(item["image_path"])
                deleted_shapes += item["removed_count"]
                written_details.append(
                    f"{osp.basename(item['image_path'])}: 删除 {item['removed_count']} 个 "
                    f"({self._format_counts(item['label_counts'])})"
                )
            except Exception as exc:
                write_errors.append(f"{osp.basename(item['label_path'])}: {exc}")
                logger.error(f"Region batch delete write failed for {item['label_path']}: {exc}")

        if progress is not None:
            progress.setValue(len(planned_changes))
            progress.close()

        return modified_image_paths, write_errors, written_details, deleted_shapes

    def run_region_batch_delete(self):
        options = self.get_options()
        region = options["region"]
        if region is None:
            self._show_message(QtWidgets.QMessageBox.Warning, "请先在图片上画出一个区域。")
            return

        labels = set(options["labels"] or [])
        if not labels:
            labels = self._labels_hit_by_region_on_current_page(region, options["match_mode"])
            if not labels:
                self._show_message(
                    QtWidgets.QMessageBox.Warning,
                    "当前图片的框选区域没有命中任何标签，请重新框选。",
                )
                return

        widget = self.labeling_widget
        if getattr(widget, "dirty", False):
            widget.save_file()

        files_to_process = self._files_to_process(options["scope"])
        if not files_to_process:
            self._show_message(QtWidgets.QMessageBox.Warning, "请先打开一个图片文件。")
            return

        plan = self._scan_plan(
            files_to_process,
            region,
            options["match_mode"],
            labels,
            options["same_size_only"],
        )
        if not plan["planned_changes"]:
            text = f"未找到需要删除的标签。已检查 {plan['processed']} 个同尺寸 JSON。"
            if plan["skipped_size_files"]:
                text += f"\n因图片尺寸不同跳过 {len(plan['skipped_size_files'])} 个文件。"
            self._show_message(QtWidgets.QMessageBox.Information, text, self._build_plan_details(plan))
            return

        if not self._confirm_plan(files_to_process, region, options["match_mode"], plan):
            return

        modified_image_paths, write_errors, written_details, deleted_shapes = self._write_plan(
            plan["planned_changes"]
        )
        self._add_modified_files_to_filter(modified_image_paths)

        result_details = []
        if written_details:
            result_details.append("已修改:")
            result_details.extend(written_details)
        if plan["skipped_size_files"]:
            result_details.append("\n尺寸不同跳过:")
            result_details.extend(plan["skipped_size_files"])
        if plan["missing_label_files"]:
            result_details.append("\n缺少 JSON:")
            result_details.extend(plan["missing_label_files"])
        if plan["scan_errors"]:
            result_details.append("\n扫描失败:")
            result_details.extend(plan["scan_errors"])
        if write_errors:
            result_details.append("\n写入失败:")
            result_details.extend(write_errors)

        result_text = (
            f"区域批量删除完成：检查 {plan['processed']} 个同尺寸 JSON，"
            f"修改 {len(modified_image_paths)} 个文件，删除 {deleted_shapes} 个标签。"
        )
        if plan["skipped_size_files"]:
            result_text += f"\n因图片尺寸不同跳过 {len(plan['skipped_size_files'])} 个文件。"
        if modified_image_paths:
            result_text += "\n已把修改过的图片加入文件过滤。"
        if write_errors or plan["scan_errors"]:
            result_text += f"\n失败 {len(write_errors) + len(plan['scan_errors'])} 个文件。"

        self._show_message(QtWidgets.QMessageBox.Information, result_text, result_details)
