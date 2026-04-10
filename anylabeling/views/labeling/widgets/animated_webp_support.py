import os

from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt

from .. import utils


_ANIMATED_WEBP_INFO_CACHE = {}


def get_animated_webp_info(path):
    cache_key = os.path.normcase(os.path.abspath(path))
    cached = _ANIMATED_WEBP_INFO_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    info = {"is_animated": False, "frame_count": 1}
    if os.path.splitext(path)[1].lower() != ".webp":
        _ANIMATED_WEBP_INFO_CACHE[cache_key] = info
        return dict(info)

    movie = QtGui.QMovie(path)
    if movie.isValid():
        frame_count = movie.frameCount()
        if frame_count > 1 and movie.jumpToFrame(0):
            info = {"is_animated": True, "frame_count": frame_count}
            _ANIMATED_WEBP_INFO_CACHE[cache_key] = info
            return dict(info)

    try:
        reader = utils.AnimatedWebPReader(path)
    except Exception:
        _ANIMATED_WEBP_INFO_CACHE[cache_key] = info
        return dict(info)

    try:
        if reader.frame_count > 1:
            info = {"is_animated": True, "frame_count": reader.frame_count}
    finally:
        reader.close()

    _ANIMATED_WEBP_INFO_CACHE[cache_key] = info
    return dict(info)


def is_animated_webp_file(path):
    return get_animated_webp_info(path).get("is_animated", False)


def progress_ratio_from_frame(current_frame, total_frames):
    if total_frames <= 1:
        return 0.0
    return max(0.0, min(1.0, current_frame / max(1, total_frames - 1)))


def progress_rect_for_rect(rect):
    if rect.isNull():
        return QtCore.QRectF()
    line_height = 2.0
    return QtCore.QRectF(
        rect.left(),
        rect.bottom() - line_height + 1.0,
        rect.width(),
        line_height,
    )


def progress_hit_rect_for_rect(rect, hit_height=60.0):
    progress_rect = progress_rect_for_rect(rect)
    if progress_rect.isNull():
        return QtCore.QRectF()
    return QtCore.QRectF(
        progress_rect.left(),
        progress_rect.top() - float(hit_height),
        progress_rect.width(),
        progress_rect.height() + float(hit_height),
    )


def progress_ratio_from_point(rect, point, hit_height=60.0):
    hit_rect = progress_hit_rect_for_rect(rect, hit_height=hit_height)
    if hit_rect.isNull() or not hit_rect.contains(point):
        return None

    progress_rect = progress_rect_for_rect(rect)
    if progress_rect.width() <= 0:
        return 0.0

    return max(
        0.0,
        min(1.0, (point.x() - progress_rect.left()) / progress_rect.width()),
    )


def draw_progress_bar(painter, rect, ratio, visible=True):
    if not visible or rect.isNull():
        return

    progress_rect = progress_rect_for_rect(rect)
    if progress_rect.isNull():
        return

    painter.fillRect(progress_rect, QtGui.QColor(24, 28, 34, 230))
    if ratio > 0:
        played_rect = QtCore.QRectF(
            progress_rect.left(),
            progress_rect.top(),
            progress_rect.width() * max(0.0, min(1.0, ratio)),
            progress_rect.height(),
        )
        painter.fillRect(played_rect, QtGui.QColor(0, 190, 255, 245))


class AnimatedWebPPlayer(QtCore.QObject):
    frame_changed = QtCore.pyqtSignal(QtGui.QPixmap, int, int)
    cycle_finished = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.movie = None
        self.reader = None
        self.path = None
        self.frame_count = 0
        self.current_frame = 0
        self.is_playing = False
        self.loop_enabled = True
        self.end_action_enabled = False
        self.target_size = QtCore.QSize()
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._advance_frame)
        self.end_timer = QtCore.QTimer(self)
        self.end_timer.setSingleShot(True)
        self.end_timer.timeout.connect(self._finalize_cycle)

    def clear(self):
        self.pause()
        self.end_timer.stop()
        self.path = None
        self.frame_count = 0
        self.current_frame = 0
        self.target_size = QtCore.QSize()
        if self.movie is not None:
            try:
                self.movie.frameChanged.disconnect(self._on_movie_frame_changed)
            except Exception:
                pass
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None
        if self.reader is not None:
            self.reader.close()
            self.reader = None

    def load(self, path, target_size=None):
        self.clear()
        self.path = path
        if target_size is not None:
            self.target_size = QtCore.QSize(target_size)

        movie = QtGui.QMovie(path)
        movie.setCacheMode(QtGui.QMovie.CacheAll)
        if movie.isValid() and movie.frameCount() > 1 and movie.jumpToFrame(0):
            if self.target_size.isValid():
                movie.setScaledSize(self.target_size)
                movie.jumpToFrame(0)
            movie.frameChanged.connect(self._on_movie_frame_changed)
            self.movie = movie
            self.frame_count = movie.frameCount()
            self.current_frame = 0
            pixmap = self._scaled_pixmap(movie.currentPixmap())
            if not pixmap.isNull():
                self.frame_changed.emit(pixmap, 0, self.frame_count)
            return True

        try:
            reader = utils.AnimatedWebPReader(path)
        except Exception:
            self.clear()
            return False

        self.reader = reader
        self.frame_count = reader.frame_count
        self.current_frame = 0
        self._display_reader_frame(0)
        return True

    def configure(self, loop_enabled=True, end_action_enabled=False):
        self.loop_enabled = bool(loop_enabled)
        self.end_action_enabled = bool(end_action_enabled)

    def set_target_size(self, target_size):
        if target_size is None:
            return

        target_size = QtCore.QSize(target_size)
        if not target_size.isValid():
            return

        self.target_size = target_size
        if self.movie is not None:
            if self.movie.scaledSize() != self.target_size:
                self.movie.setScaledSize(self.target_size)
                if self.movie.state() != QtGui.QMovie.Running:
                    self.movie.jumpToFrame(self.current_frame)
                pixmap = self._scaled_pixmap(self.movie.currentPixmap())
                if not pixmap.isNull():
                    self.frame_changed.emit(
                        pixmap,
                        self.current_frame,
                        self.frame_count,
                    )
        elif self.reader is not None and self.frame_count > 0:
            self._display_reader_frame(self.current_frame)

    def play(self):
        if self.frame_count <= 1:
            return

        self.end_timer.stop()
        if (
            self.current_frame >= self.frame_count - 1
            and (self.end_action_enabled or not self.loop_enabled)
        ):
            self.seek_frame(0)

        self.is_playing = True
        if self.movie is not None:
            if self.movie.state() == QtGui.QMovie.NotRunning:
                self.movie.start()
            else:
                self.movie.setPaused(False)
        elif self.reader is not None:
            self._schedule_next_frame()

    def pause(self):
        if self.movie is not None and self.movie.state() != QtGui.QMovie.NotRunning:
            self.movie.setPaused(True)
        self.is_playing = False
        self.timer.stop()

    def toggle(self):
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def seek_frame(self, frame_index):
        if self.frame_count <= 0:
            return

        frame_index = max(0, min(self.frame_count - 1, int(frame_index)))
        self.end_timer.stop()

        was_playing = self.is_playing
        self.pause()

        if self.movie is not None:
            if self.movie.currentFrameNumber() != frame_index:
                if not self.movie.jumpToFrame(frame_index):
                    return
            pixmap = self._scaled_pixmap(self.movie.currentPixmap())
            if not pixmap.isNull():
                self.current_frame = frame_index
                self.frame_changed.emit(pixmap, frame_index, self.frame_count)
        elif self.reader is not None:
            self._display_reader_frame(frame_index)

        if was_playing:
            self.play()

    def seek_ratio(self, ratio):
        if self.frame_count <= 1:
            return
        target_frame = int(
            round(max(0.0, min(1.0, ratio)) * max(0, self.frame_count - 1))
        )
        self.seek_frame(target_frame)

    def _scaled_pixmap(self, pixmap):
        if pixmap.isNull() or not self.target_size.isValid():
            return pixmap
        if pixmap.size() == self.target_size:
            return pixmap
        transformation = (
            Qt.FastTransformation
            if self.is_playing
            else Qt.SmoothTransformation
        )
        return pixmap.scaled(
            self.target_size,
            Qt.IgnoreAspectRatio,
            transformation,
        )

    def _on_movie_frame_changed(self, frame_index):
        if self.movie is None:
            return
        if frame_index == 0:
            self.end_timer.stop()

        self.current_frame = frame_index
        pixmap = self._scaled_pixmap(self.movie.currentPixmap())
        if not pixmap.isNull():
            self.frame_changed.emit(pixmap, frame_index, self.frame_count)

        if (
            self.is_playing
            and self.frame_count > 1
            and frame_index >= self.frame_count - 1
            and (self.end_action_enabled or not self.loop_enabled)
            and not self.end_timer.isActive()
        ):
            self.end_timer.start(0)

    def _display_reader_frame(self, frame_index):
        if self.reader is None:
            return
        image = self.reader.get_frame_qimage(frame_index)
        pixmap = self._scaled_pixmap(QtGui.QPixmap.fromImage(image))
        self.current_frame = frame_index
        self.frame_changed.emit(pixmap, frame_index, self.frame_count)

    def _schedule_next_frame(self):
        if self.reader is None or not self.is_playing:
            return
        delay = self.reader.get_frame_duration(self.current_frame)
        self.timer.start(max(20, int(delay)))

    def _advance_frame(self):
        if self.reader is None or not self.is_playing:
            return

        next_frame = self.current_frame + 1
        if next_frame >= self.frame_count:
            if self.end_action_enabled or not self.loop_enabled:
                self._finalize_cycle()
                return
            next_frame = 0

        self._display_reader_frame(next_frame)
        if self.is_playing:
            self._schedule_next_frame()

    def _finalize_cycle(self):
        self.pause()
        self.cycle_finished.emit()
