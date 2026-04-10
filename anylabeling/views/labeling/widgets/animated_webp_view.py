from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt


class AnimatedWebPView(QtWidgets.QWidget):
    toggle_requested = QtCore.pyqtSignal()
    seek_requested = QtCore.pyqtSignal(float)
    context_menu_requested = QtCore.pyqtSignal(QtCore.QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scale = 1.0
        self.pixmap = QtGui.QPixmap()
        self.progress_ratio = 0.0
        self.progress_visible = False
        self._dragging_progress = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def clear(self):
        self.pixmap = QtGui.QPixmap()
        self.progress_ratio = 0.0
        self.progress_visible = False
        self._dragging_progress = False
        self.updateGeometry()
        self.adjustSize()
        self.update()

    def set_pixmap(self, pixmap):
        size_changed = self.pixmap.size() != pixmap.size()
        self.pixmap = pixmap
        if size_changed:
            self.updateGeometry()
            self.adjustSize()
        self.update()

    def set_frame(self, pixmap, current_frame, total_frames, visible=True):
        size_changed = self.pixmap.size() != pixmap.size()
        self.pixmap = pixmap
        self.progress_visible = visible and total_frames > 1
        if total_frames > 1:
            self.progress_ratio = max(
                0.0,
                min(1.0, current_frame / max(1, total_frames - 1)),
            )
        else:
            self.progress_ratio = 0.0
        if size_changed:
            self.updateGeometry()
            self.adjustSize()
        self.update()

    def set_progress(self, current_frame, total_frames, visible=True):
        self.progress_visible = visible and total_frames > 1
        if total_frames > 1:
            self.progress_ratio = max(
                0.0,
                min(1.0, current_frame / max(1, total_frames - 1)),
            )
        else:
            self.progress_ratio = 0.0
        self.update()

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        if self.pixmap and not self.pixmap.isNull():
            return QtCore.QSize(
                max(1, int(round(self.pixmap.width() * self.scale))),
                max(1, int(round(self.pixmap.height() * self.scale))),
            )
        return super().minimumSizeHint()

    def _image_rect(self):
        if self.pixmap.isNull():
            return QtCore.QRectF()

        scaled_w = self.pixmap.width() * self.scale
        scaled_h = self.pixmap.height() * self.scale
        x = max(0.0, (self.width() - scaled_w) / 2)
        y = max(0.0, (self.height() - scaled_h) / 2)
        return QtCore.QRectF(x, y, scaled_w, scaled_h)

    def _progress_rect(self):
        image_rect = self._image_rect()
        if image_rect.isNull() or not self.progress_visible:
            return QtCore.QRectF()
        line_height = 2.0 if image_rect.height() >= 120 else 1.0
        return QtCore.QRectF(
            image_rect.left(),
            image_rect.bottom() - line_height + 1.0,
            image_rect.width(),
            line_height,
        )

    def _progress_hit_rect(self):
        rect = self._progress_rect()
        if rect.isNull():
            return QtCore.QRectF()
        return QtCore.QRectF(
            rect.left(),
            rect.top() - 80.0,
            rect.width(),
            rect.height() + 82.0,
        )

    def _ratio_from_pos(self, pos):
        hit_rect = self._progress_hit_rect()
        if hit_rect.isNull() or not hit_rect.contains(pos):
            return None
        progress_rect = self._progress_rect()
        if progress_rect.width() <= 0:
            return 0.0
        return max(
            0.0,
            min(1.0, (pos.x() - progress_rect.left()) / progress_rect.width()),
        )

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)

        if self.pixmap.isNull():
            return

        image_rect = self._image_rect()
        painter.drawPixmap(
            image_rect,
            self.pixmap,
            QtCore.QRectF(self.pixmap.rect()),
        )

        if self.progress_visible:
            progress_rect = self._progress_rect()
            painter.fillRect(progress_rect, QtGui.QColor(24, 28, 34, 230))
            if self.progress_ratio > 0:
                played_rect = QtCore.QRectF(
                    progress_rect.left(),
                    progress_rect.top(),
                    progress_rect.width() * self.progress_ratio,
                    progress_rect.height(),
                )
                painter.fillRect(played_rect, QtGui.QColor(0, 190, 255, 245))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or self.pixmap.isNull():
            return super().mousePressEvent(event)

        ratio = self._ratio_from_pos(event.localPos())
        if ratio is not None:
            self._dragging_progress = True
            self.seek_requested.emit(ratio)
            return

        if self._image_rect().contains(event.localPos()):
            self.toggle_requested.emit()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging_progress:
            ratio = self._ratio_from_pos(event.localPos())
            if ratio is not None:
                self.seek_requested.emit(ratio)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging_progress and event.button() == Qt.LeftButton:
            self._dragging_progress = False
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        if self.pixmap.isNull():
            return super().contextMenuEvent(event)
        self.context_menu_requested.emit(event.globalPos())
        event.accept()
