"""瀑布流缩略图查看器 - 性能优化版"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
import os
import json
import time

# ========== 自定义鼠标指针设置（可修改） ==========
SELECT_CURSOR_PATH = r"D:\Ddown\鼠标指针\Janguru Cursors X2\NO.cur"
DELETE_CURSOR_PATH = r"J:\文件夹存放\鼠标指针文件\222222\DroidCursorScheme\Droid.HelpSelect.cur"

SELECT_CURSOR_HOTSPOT = None
DELETE_CURSOR_HOTSPOT = None
# ==============================================


class SpaceConfirmMessageBox(QtWidgets.QMessageBox):
    """支持空格键确认的自定义消息框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._yes_button = None
        self._no_button = None
        self._filter_installed = False
    
    def showEvent(self, event):
        """对话框显示时，获取按钮并安装事件过滤器"""
        super().showEvent(event)
        
        if not self._filter_installed:
            self._yes_button = self.button(QtWidgets.QMessageBox.Yes)
            self._no_button = self.button(QtWidgets.QMessageBox.No)
            
            if self._yes_button:
                self._yes_button.setDefault(True)
                self._yes_button.setAutoDefault(True)
                self._yes_button.installEventFilter(self)
                self._yes_button.setFocus()
            
            if self._no_button:
                self._no_button.installEventFilter(self)
            
            self._filter_installed = True
    
    def eventFilter(self, obj, event):
        """拦截按钮的空格键事件"""
        if event.type() == QtCore.QEvent.KeyPress:
            if event.key() == Qt.Key_Space:
                if obj == self._yes_button:
                    self._yes_button.click()
                    return True
                elif obj == self._no_button:
                    self._no_button.click()
                    return True
        
        return super().eventFilter(obj, event)


class ThumbnailLoaderSignals(QtCore.QObject):
    """缩略图加载信号"""
    loaded = QtCore.pyqtSignal(str, QtGui.QPixmap, int, int, int)  # path, pixmap, orig_w, orig_h, load_width


class ThumbnailLoader(QtCore.QRunnable):
    """后台缩略图加载器"""
    
    def __init__(self, image_path, target_width):
        super().__init__()
        self.image_path = image_path
        self.target_width = target_width
        self.signals = ThumbnailLoaderSignals()
    
    def run(self):
        try:
            reader = QtGui.QImageReader(self.image_path)
            reader.setAutoTransform(True)
            
            orig_size = reader.size()
            image = None
            orig_w, orig_h = 0, 0
            
            if orig_size.isValid():
                orig_w = orig_size.width()
                orig_h = orig_size.height()
                
                # 计算缩略图尺寸
                aspect_ratio = orig_h / orig_w
                thumb_width = self.target_width
                thumb_height = int(self.target_width * aspect_ratio)
                
                reader.setScaledSize(QtCore.QSize(thumb_width, thumb_height))
                image = reader.read()
            
            # Fallback to Pillow if QImageReader fails (e.g., AVIF/HEIC)
            if image is None or image.isNull():
                try:
                    from PIL import Image
                    import numpy as np
                    pil_img = Image.open(self.image_path)
                    orig_w, orig_h = pil_img.size
                    pil_img = pil_img.convert("RGBA")
                    
                    aspect_ratio = orig_h / orig_w
                    thumb_width = self.target_width
                    thumb_height = int(self.target_width * aspect_ratio)
                    pil_img = pil_img.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
                    
                    # Convert PIL to QImage using RGBA for better alignment/stability
                    data = pil_img.tobytes("raw", "RGBA")
                    image = QtGui.QImage(data, thumb_width, thumb_height, thumb_width * 4, QtGui.QImage.Format_RGBA8888)
                    image = image.copy() # Ensure memory ownership
                except Exception:
                    image = None

            if image is not None and not image.isNull():
                pixmap = QtGui.QPixmap.fromImage(image)
                self.signals.loaded.emit(self.image_path, pixmap, orig_w, orig_h, self.target_width)
        except Exception:
            pass


class ThumbnailItem(QtWidgets.QWidget):
    """单个缩略图项"""
    
    clicked = QtCore.pyqtSignal(str)
    request_horizontal_viewer = QtCore.pyqtSignal(str)
    request_vertical_viewer = QtCore.pyqtSignal(str)
    request_switch_image = QtCore.pyqtSignal(str)
    need_reload = QtCore.pyqtSignal(object)  # 需要重新加载
    toggle_edited = QtCore.pyqtSignal(object)  # 切换已编辑状态
    merge_state_changed = QtCore.pyqtSignal(object)  # 删合状态改变
    range_select_requested = QtCore.pyqtSignal(object, int)  # 范围选择请求 (item, index)
    set_merge_target_requested = QtCore.pyqtSignal(object, int)  # 设置合并目标请求 (item, index)
    
    def __init__(self, image_path, thumbnail_width=200, border_radius=8, edited_color="#FFA500", border_width=0, label_color_getter=None, difficult_color="#800080", parent=None, index=0):
        super().__init__(parent)
        self.image_path = image_path
        self.thumbnail_width = thumbnail_width
        self.thumbnail_height = thumbnail_width  # 横向模式用
        self.border_radius = border_radius
        self.edited_color = edited_color  # 手动编辑颜色
        self.difficult_color = difficult_color  # 困难标记颜色
        self.border_width = border_width  # 边框宽度
        self.label_color_getter = label_color_getter  # 获取标签颜色的回调函数
        self.pixmap = None
        self.is_manually_edited = False
        self.image_width = 0
        self.image_height = 0
        self.file_size = 0
        self.file_date = ""
        self.loaded = False
        self.loading = False
        self.hovered = False
        self.actual_height = thumbnail_width
        self.actual_width = thumbnail_width
        self.loaded_width = 0  # 已加载的pixmap宽度
        self.horizontal_mode = False  # 横向模式
        self.index = index  # 图片序号（从1开始）
        self.show_index = True  # 是否显示序号
        self.keep_aspect = False  # 方格子模式：保持比例居中显示
        
        # 删合模式状态
        self.merge_mode = False  # 是否处于删合模式
        self.current_merge_sub_mode = 'select'  # 'select' 或 'delete'
        self.is_selected = False  # 是否被选中
        self.is_marked_delete = False  # 是否标记删除
        self.is_merge_target = False  # 是否为合并目标
        
        # 普通模式多选状态
        self.is_multi_selected = False  # Ctrl+左键多选状态
        
        # 单击高亮状态
        self.is_clicked = False  # 是否被单击(显示边框提示)
        self._rainbow_hue = 0  # 彩虹色相值(0-360)
        self._rainbow_timer = None  # 彩虹边框动画定时器
        
        # 悬停信息显示开关
        self.show_hover_info = True  # 默认显示悬停信息
        
        # 高亮状态（用于定位提示）
        self.is_highlighted = False  # 是否高亮显示
        self._highlight_opacity = 0  # 高亮透明度（0-255）
        self._highlight_timer = None  # 高亮动画定时器
        
        # 鼠标指针
        self._select_cursor = None
        self._delete_cursor = None
        
        # 左上角状态图标（紧跟在序号标签右边）
        self.status_icon = QtWidgets.QLabel(self)
        self.status_icon.setAlignment(Qt.AlignCenter)
        self.status_icon.setStyleSheet("background-color: transparent; font-size: 18px;")
        self.status_icon.setGeometry(50, 5, 25, 25)  # 放在序号标签右边
        self.status_icon.raise_()  # 确保图标在最上层
        self.status_icon.hide()
        
        self.setFixedSize(thumbnail_width, thumbnail_width)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        
        # 关键修复：不接受焦点，确保键盘事件由父对话框处理
        self.setFocusPolicy(Qt.NoFocus)
        
        self._check_manually_edited()
        self._get_file_info()
    
    def set_edited_color(self, color):
        """设置手动编辑颜色"""
        self.edited_color = color
        if self.is_manually_edited:
            self.update()
    
    def set_difficult_color(self, color):
        """设置困难标记颜色"""
        self.difficult_color = color
        if self.difficult_count > 0:
            self.update()
    
    def set_border_width(self, width):
        """设置边框宽度"""
        self.border_width = width
        self.update()
    
    def set_cursors(self, select_cursor: QtGui.QCursor, delete_cursor: QtGui.QCursor):
        """设置选择和删除模式的鼠标指针"""
        self._select_cursor = select_cursor
        self._delete_cursor = delete_cursor
    
    def set_merge_mode_cursor(self, mode: str):
        """根据删合模式设置鼠标指针"""
        if not self.merge_mode:
            # 非删合模式，使用默认指针
            self.setCursor(Qt.PointingHandCursor)
            return
        
        if mode == 'delete':
            if self._delete_cursor:
                self.setCursor(self._delete_cursor)
            else:
                self.setCursor(Qt.CrossCursor)
        else:  # select
            if self._select_cursor:
                self.setCursor(self._select_cursor)
            else:
                self.setCursor(Qt.PointingHandCursor)
    
    def set_horizontal_mode(self, enabled, height=200):
        """设置横向模式"""
        self.horizontal_mode = enabled
        self.thumbnail_height = height
        if enabled and self.image_width > 0 and self.image_height > 0:
            # 横向模式：高度固定，宽度按比例
            self.actual_height = height
            self.actual_width = int(height * self.image_width / self.image_height)
            self.setFixedSize(self.actual_width, self.actual_height)
        self.update()
    
    def _check_manually_edited(self):
        json_path = os.path.splitext(self.image_path)[0] + ".json"
        self.label_stats = {}  # 标签统计
        self.total_labels = 0  # 总标签数
        self.difficult_count = 0  # 困难标记数量
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.is_manually_edited = data.get("manually_edited", False)
                    # 统计标签和困难标记
                    shapes = data.get("shapes", [])
                    for shape in shapes:
                        label = shape.get("label", "unknown")
                        self.label_stats[label] = self.label_stats.get(label, 0) + 1
                        # 统计困难标记
                        if shape.get("difficult", False):
                            self.difficult_count += 1
                    self.total_labels = len(shapes)
            except Exception:
                pass
    
    def _get_file_info(self):
        try:
            self.file_size = os.path.getsize(self.image_path)
            mtime = os.path.getmtime(self.image_path)
            self.file_date = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
        except Exception:
            pass
    
    def _format_file_size(self):
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
    
    def set_pixmap(self, pixmap, orig_w, orig_h, load_width):
        """设置已加载的pixmap"""
        self.pixmap = pixmap
        self.image_width = orig_w
        self.image_height = orig_h
        self.loaded_width = load_width
        self.loaded = True
        self.loading = False
        
        if self.horizontal_mode:
            # 横向模式：高度固定，宽度按比例
            if orig_h > 0:
                self.actual_width = int(self.thumbnail_height * orig_w / orig_h)
                self.actual_height = self.thumbnail_height
        else:
            # 纵向模式：宽度固定，高度按比例
            if orig_w > 0:
                self.actual_height = int(self.thumbnail_width * orig_h / orig_w)
                self.actual_width = self.thumbnail_width
        
        self.setFixedSize(self.actual_width, self.actual_height)
        self.update()
    
    def needs_reload(self, new_size):
        """检查是否需要重新加载更高分辨率"""
        if not self.loaded or self.loaded_width == 0:
            return True
        # 如果新尺寸比已加载的宽度大20%以上，需要重新加载
        return new_size > self.loaded_width * 1.2
    
    def update_geometry_only(self, new_width):
        """只更新几何尺寸（纵向模式）"""
        self.thumbnail_width = new_width
        self.actual_width = new_width
        
        if self.image_width > 0 and self.image_height > 0:
            new_height = int(new_width * self.image_height / self.image_width)
            self.actual_height = new_height
        else:
            self.actual_height = new_width
        
        # 强制设置尺寸
        self.setFixedSize(self.actual_width, self.actual_height)
        
        # 检查是否需要重新加载
        if self.loaded and self.needs_reload(new_width):
            self.need_reload.emit(self)
        
        return self.actual_height
    
    def update_geometry_horizontal(self, new_height):
        """只更新几何尺寸（横向模式）"""
        self.thumbnail_height = new_height
        self.actual_height = new_height
        self.setFixedHeight(new_height)
        
        if self.image_width > 0 and self.image_height > 0:
            new_width = int(new_height * self.image_width / self.image_height)
            self.actual_width = new_width
            self.setFixedWidth(new_width)
        else:
            self.actual_width = new_height
            self.setFixedWidth(new_height)
        
        # 检查是否需要重新加载
        if self.loaded and self.needs_reload(new_height):
            self.need_reload.emit(self)
        
        return self.actual_width
    
    def mark_for_reload(self):
        """标记需要重新加载"""
        self.loading = False
    
    def update_radius(self, new_radius):
        self.border_radius = new_radius
        self.update()
    
    def resizeEvent(self, event):
        """窗口大小改变时更新status_icon位置"""
        super().resizeEvent(event)
        # 状态图标固定在左上角序号标签右边，不需要动态调整位置
        # self.status_icon.setGeometry(50, 5, 25, 25)  # 已在初始化时设置
    
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        
        rect = QtCore.QRectF(0, 0, self.width(), self.height())
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, self.border_radius, self.border_radius)
        
        if self.pixmap and not self.pixmap.isNull():
            painter.setClipPath(path)
            
            if self.keep_aspect:
                # 方格子模式：保持比例居中显示，背景填充深灰色
                painter.fillRect(rect, QtGui.QColor(40, 40, 40))
                # 保持比例缩放
                scaled = self.pixmap.scaled(self.width(), self.height(), 
                                            Qt.KeepAspectRatio, Qt.SmoothTransformation)
                # 居中绘制
                x = (self.width() - scaled.width()) // 2
                y = (self.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            else:
                # 瀑布流模式：填满整个区域
                scaled = self.pixmap.scaled(self.width(), self.height(), 
                                            Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                painter.drawPixmap(0, 0, scaled)
            
            painter.setClipping(False)
            
            # 绘制序号标签（左上角，圆角矩形）
            if self.show_index and self.index > 0:
                index_str = str(self.index)
                
                # 计算文字尺寸
                font = painter.font()
                font.setPointSize(9)
                font.setBold(True)
                painter.setFont(font)
                fm = QtGui.QFontMetrics(font)
                text_width = fm.horizontalAdvance(index_str)
                text_height = fm.height()
                
                # 计算标签尺寸（文字+内边距）
                padding_h = 6  # 水平内边距
                padding_v = 3  # 垂直内边距
                label_width = text_width + padding_h * 2
                label_height = text_height + padding_v * 2
                label_margin = 6
                label_x = label_margin
                label_y = label_margin
                corner_radius = 4  # 圆角半径
                
                # 绘制半透明背景圆角矩形
                painter.setPen(Qt.NoPen)
                painter.setBrush(QtGui.QColor(0, 80, 160, 200))  # 深蓝色半透明
                label_rect = QtCore.QRectF(label_x, label_y, label_width, label_height)
                painter.drawRoundedRect(label_rect, corner_radius, corner_radius)
                
                # 绘制序号文字
                painter.setPen(QtGui.QColor(255, 255, 255))
                painter.drawText(label_rect, Qt.AlignCenter, index_str)
                
                # 动态更新status_icon位置（紧跟在序号标签右边）
                icon_x = int(label_x + label_width + 4)  # 序号标签右边留4像素间距
                icon_y = int(label_y)
                self.status_icon.setGeometry(icon_x, icon_y, 25, 25)
            
            # 绘制边框
            if self.merge_mode and (self.is_merge_target or self.is_marked_delete or self.is_selected):
                # 删合模式下的边框
                if self.is_merge_target:
                    # 合并目标：金色边框
                    border_w = 4
                    pen = QtGui.QPen(QtGui.QColor(255, 215, 0), border_w)  # 金色
                elif self.is_marked_delete:
                    # 待删除：红色边框
                    border_w = 3
                    pen = QtGui.QPen(QtGui.QColor(255, 0, 0), border_w)  # 红色
                elif self.is_selected:
                    # 已选中：蓝色边框
                    border_w = 3
                    pen = QtGui.QPen(QtGui.QColor(42, 122, 226), border_w)  # 蓝色
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                offset = border_w / 2
                painter.drawRoundedRect(rect.adjusted(offset, offset, -offset, -offset), self.border_radius, self.border_radius)
            elif self.is_clicked:
                # 单击状态：彩虹色边框(红→橙→黄→绿→青→蓝→紫→白→黑)
                border_w = 4
                
                if self._rainbow_hue < 360:
                    # 0-359: 彩虹色(红→橙→黄→绿→青→蓝→紫)
                    color = QtGui.QColor.fromHsv(self._rainbow_hue, 255, 255)
                elif self._rainbow_hue < 405:
                    # 360-404: 紫色渐变到白色
                    progress = (self._rainbow_hue - 360) / 45  # 0.0 到 1.0
                    # 从紫色(300度HSV)渐变到白色(降低饱和度)
                    saturation = int(255 * (1 - progress))
                    color = QtGui.QColor.fromHsv(300, saturation, 255)
                else:
                    # 405-449: 白色渐变到黑色
                    progress = (self._rainbow_hue - 405) / 45  # 0.0 到 1.0
                    # 从白色渐变到黑色(降低明度)
                    value = int(255 * (1 - progress))
                    color = QtGui.QColor.fromHsv(0, 0, value)
                
                pen = QtGui.QPen(color, border_w)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                offset = border_w / 2
                painter.drawRoundedRect(rect.adjusted(offset, offset, -offset, -offset), self.border_radius, self.border_radius)
            elif self.is_multi_selected:
                # 普通模式多选：亮绿色边框
                border_w = 3
                pen = QtGui.QPen(QtGui.QColor(0, 230, 118), border_w)  # 亮绿色 #00E676
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                offset = border_w / 2
                painter.drawRoundedRect(rect.adjusted(offset, offset, -offset, -offset), self.border_radius, self.border_radius)
            elif self.is_manually_edited:
                # 已编辑：使用编辑颜色，边框宽度+2
                border_w = max(self.border_width + 2, 3)
                pen = QtGui.QPen(QtGui.QColor(self.edited_color), border_w)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                offset = border_w / 2
                painter.drawRoundedRect(rect.adjusted(offset, offset, -offset, -offset), self.border_radius, self.border_radius)
            elif self.border_width > 0:
                # 普通图片：白色边框（纯色）
                pen = QtGui.QPen(QtGui.QColor(255, 255, 255), self.border_width)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                offset = self.border_width / 2
                painter.drawRoundedRect(rect.adjusted(offset, offset, -offset, -offset), self.border_radius, self.border_radius)
            
            # 绘制高亮边框（定位提示）
            if self.is_highlighted:
                border_w = 6
                # 使用动态透明度的纯绿色边框（非常醒目）
                pen = QtGui.QPen(QtGui.QColor(0, 255, 0, self._highlight_opacity), border_w)  # 纯绿色
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                offset = border_w / 2
                painter.drawRoundedRect(rect.adjusted(offset, offset, -offset, -offset), self.border_radius, self.border_radius)
            
            if self.hovered and self.show_hover_info:
                painter.setClipPath(path)
                painter.fillRect(rect, QtGui.QColor(0, 0, 0, 180))
                painter.setClipping(False)
                
                painter.setPen(QtGui.QColor(255, 255, 255))
                font = painter.font()
                font.setPointSize(9)
                painter.setFont(font)
                
                filename = os.path.basename(self.image_path)
                resolution = f"{self.image_width}x{self.image_height}"
                size_str = self._format_file_size()
                
                margin, y_offset, line_height = 8, 22, 16
                painter.drawText(margin, y_offset, size_str)
                painter.drawText(margin, y_offset + line_height, resolution)
                painter.drawText(margin, y_offset + line_height * 2, self.file_date)
                
                max_chars = max(10, (self.width() - 16) // 7)
                if len(filename) > max_chars:
                    filename = filename[:max_chars - 3] + "..."
                painter.drawText(margin, y_offset + line_height * 3, filename)
                
                current_line = 4
                if self.is_manually_edited:
                    painter.setPen(QtGui.QColor(self.edited_color))
                    painter.drawText(margin, y_offset + line_height * current_line, "[已编辑]")
                    current_line += 1
                
                # 显示困难标记数量
                if self.difficult_count > 0:
                    painter.setPen(QtGui.QColor(self.difficult_color))
                    painter.drawText(margin, y_offset + line_height * current_line, f"[困难标记: {self.difficult_count}]")
                    current_line += 1
                
                # 显示标签统计
                if self.total_labels > 0:
                    painter.setPen(QtGui.QColor(100, 200, 255))  # 浅蓝色
                    painter.drawText(margin, y_offset + line_height * current_line, f"总标签: {self.total_labels}")
                    current_line += 1
                    
                    # 计算可用高度和右侧列的起始位置
                    max_y = self.height() - 10
                    right_column_x = self.width() // 2 + 5  # 右侧列起始X
                    right_column_line = 0  # 右侧列当前行
                    use_right_column = False  # 是否开始使用右侧列
                    
                    # 根据宽度计算最大字符数（左侧列用半宽）
                    left_max_chars = max(10, (self.width() // 2 - 16) // 7)
                    right_max_chars = max(10, (self.width() // 2 - 16) // 7)
                    
                    for label, count in self.label_stats.items():
                        # 获取标签颜色
                        if self.label_color_getter:
                            rgb = self.label_color_getter(label)
                            if rgb:
                                painter.setPen(QtGui.QColor(rgb[0], rgb[1], rgb[2]))
                            else:
                                painter.setPen(QtGui.QColor(180, 180, 180))
                        else:
                            painter.setPen(QtGui.QColor(180, 180, 180))
                        
                        if not use_right_column:
                            # 检查是否快超出高度
                            if y_offset + line_height * (current_line + 1) > max_y:
                                use_right_column = True
                                right_column_line = 0
                        
                        if use_right_column:
                            # 右侧列显示
                            display_label = label if len(label) <= right_max_chars else label[:right_max_chars - 2] + ".."
                            y_pos = y_offset + line_height * right_column_line
                            if y_pos < max_y:
                                painter.drawText(right_column_x, y_pos, f"{display_label}: {count}")
                                right_column_line += 1
                        else:
                            # 左侧列显示
                            display_label = label if len(label) <= left_max_chars else label[:left_max_chars - 2] + ".."
                            painter.drawText(margin, y_offset + line_height * current_line, f"{display_label}: {count}")
                            current_line += 1
        else:
            painter.setClipPath(path)
            painter.fillRect(rect, QtGui.QColor(50, 50, 50))
            painter.setClipping(False)
            painter.setPen(QtGui.QColor(100, 100, 100))
            painter.drawText(rect, Qt.AlignCenter, "...")
    
    def enterEvent(self, event):
        self.hovered = True
        self.update()
    
    def leaveEvent(self, event):
        self.hovered = False
        self.update()
    
    def mousePressEvent(self, event):
        if self.merge_mode:
            # 删合模式下的点击处理
            if event.button() == Qt.LeftButton:
                # 检查是否按住 Shift 键
                modifiers = QtWidgets.QApplication.keyboardModifiers()
                shift_pressed = (modifiers & Qt.ShiftModifier) == Qt.ShiftModifier
                
                if self.current_merge_sub_mode == 'select':
                    # 选择模式
                    if shift_pressed:
                        # Shift+左键：范围选择
                        self.range_select_requested.emit(self, self.index - 1)  # index从1开始，转为0开始
                    else:
                        # 普通左键：切换选中状态
                        self.is_selected = not self.is_selected
                        if not self.is_selected and self.is_merge_target:
                            # 取消选中时，同时取消合并目标
                            self.is_merge_target = False
                        self.update_merge_visual()
                        self.merge_state_changed.emit(self)
                        # 记录最后点击的索引（用于范围选择）
                        parent = self.parent()
                        while parent and not isinstance(parent, QtWidgets.QDialog):
                            parent = parent.parent()
                        if parent and hasattr(parent, '_last_selected_index'):
                            parent._last_selected_index = self.index - 1
                        
                elif self.current_merge_sub_mode == 'delete':
                    # 删除模式：切换删除标记
                    self.is_marked_delete = not self.is_marked_delete
                    self.update_merge_visual()
                    self.merge_state_changed.emit(self)
                    
            elif event.button() == Qt.RightButton:
                # 右键：设置为合并目标（仅在选择模式且已选中时）
                if self.current_merge_sub_mode == 'select' and self.is_selected:
                    self.set_merge_target_requested.emit(self, self.index - 1)
                    event.accept()
                else:
                    # 其他情况让事件传播到父控件，显示工具栏切换菜单
                    event.ignore()
                return
        else:
            # 正常模式：原有的点击处理
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            ctrl_pressed = (modifiers & Qt.ControlModifier) == Qt.ControlModifier
            shift_pressed = (modifiers & Qt.ShiftModifier) == Qt.ShiftModifier
            
            if event.button() == Qt.LeftButton:
                if shift_pressed:
                    # Shift+左键：范围选择（普通模式）
                    parent = self.parent()
                    while parent and not isinstance(parent, QtWidgets.QDialog):
                        parent = parent.parent()
                    if parent and hasattr(parent, 'on_normal_range_select'):
                        parent.on_normal_range_select(self, self.index - 1)
                elif ctrl_pressed:
                    # Ctrl+左键:多选
                    self.is_multi_selected = not self.is_multi_selected
                    # 更新图标显示
                    if self.is_multi_selected:
                        self.status_icon.setText("✅")
                        self.status_icon.setStyleSheet("background-color: transparent; color: #00E676; font-size: 18px;")  # 亮绿色
                        self.status_icon.show()
                    else:
                        self.status_icon.hide()
                    self.update()
                    # 通知父窗口更新多选列表
                    parent = self.parent()
                    while parent and not isinstance(parent, QtWidgets.QDialog):
                        parent = parent.parent()
                    if parent and hasattr(parent, 'update_multi_selection'):
                        parent.update_multi_selection()
                    # 记录最后点击的索引(用于范围选择)
                    if parent and hasattr(parent, '_last_multi_selected_index'):
                        parent._last_multi_selected_index = self.index - 1
                else:
                    # 普通左键:切换点击状态(显示/隐藏彩虹边框)
                    if self.is_clicked:
                        # 如果已经是点击状态,再次点击则取消
                        self.is_clicked = False
                        self.stop_rainbow_animation()
                        self.update()
                    else:
                        # 清除其他图片的点击状态
                        parent = self.parent()
                        while parent and not isinstance(parent, QtWidgets.QDialog):
                            parent = parent.parent()
                        if parent and hasattr(parent, 'clear_all_clicked_states'):
                            parent.clear_all_clicked_states()
                        # 设置当前图片为点击状态并启动彩虹动画
                        self.is_clicked = True
                        self.start_rainbow_animation()
                        self.update()
            elif event.button() == Qt.MiddleButton:
                # 中键点击：切换已编辑状态（支持批量）
                parent = self.parent()
                while parent and not isinstance(parent, QtWidgets.QDialog):
                    parent = parent.parent()
                if parent and hasattr(parent, 'multi_selected_items') and parent.multi_selected_items:
                    # 如果有多选项，批量切换已编辑状态
                    parent.batch_toggle_edited()
                else:
                    # 单个切换
                    self.toggle_edited.emit(self)
            elif event.button() == Qt.RightButton:
                # 右键：让事件传播到父控件，显示工具栏切换菜单
                event.ignore()
                return
            elif event.button() == Qt.RightButton:
                # 右键：让事件传播到父控件，显示工具栏切换菜单
                event.ignore()
    
    def update_merge_visual(self):
        """更新删合模式下的视觉效果"""
        if self.is_merge_target:
            self.status_icon.setText("⭐")
            self.status_icon.setStyleSheet("background-color: transparent; color: gold; font-size: 18px;")
            self.status_icon.show()
            self.status_icon.raise_()  # 确保在最上层
        elif self.is_marked_delete:
            self.status_icon.setText("❌")
            self.status_icon.setStyleSheet("background-color: transparent; color: red; font-size: 18px;")
            self.status_icon.show()
            self.status_icon.raise_()
        elif self.is_selected:
            self.status_icon.setText("✅")
            self.status_icon.setStyleSheet("background-color: transparent; color: #4CAF50; font-size: 18px;")
            self.status_icon.show()
            self.status_icon.raise_()
        else:
            self.status_icon.hide()
        
        self.update()
    
    def mouseDoubleClickEvent(self, event):
        """双击事件:切换到主界面对应图片"""
        if not self.merge_mode and event.button() == Qt.LeftButton:
            # 双击时停止彩虹动画
            if self.is_clicked:
                self.is_clicked = False
                self.stop_rainbow_animation()
            # 切换到主界面对应图片
            self.clicked.emit(self.image_path)
        else:
            super().mouseDoubleClickEvent(event)
    
    def start_highlight(self):
        """开始高亮动画（闪烁3次）"""
        self.is_highlighted = True
        self._highlight_opacity = 255
        self._highlight_count = 0  # 闪烁次数
        self._highlight_direction = -1  # -1表示变暗，1表示变亮
        
        if self._highlight_timer:
            self._highlight_timer.stop()
        
        self._highlight_timer = QtCore.QTimer()
        self._highlight_timer.timeout.connect(self._update_highlight)
        self._highlight_timer.start(30)  # 每30ms更新一次
        self.update()
    
    def _update_highlight(self):
        """更新高亮动画"""
        # 调整透明度
        self._highlight_opacity += self._highlight_direction * 15
        
        # 检查是否需要反转方向
        if self._highlight_opacity <= 0:
            self._highlight_opacity = 0
            self._highlight_direction = 1
            self._highlight_count += 1
        elif self._highlight_opacity >= 255:
            self._highlight_opacity = 255
            self._highlight_direction = -1
        
        # 闪烁3次后停止
        if self._highlight_count >= 3:
            self.is_highlighted = False
            if self._highlight_timer:
                self._highlight_timer.stop()
                self._highlight_timer = None
        
        self.update()
    
    def start_rainbow_animation(self):
        """开始彩虹边框动画"""
        self._rainbow_hue = 0
        
        if self._rainbow_timer:
            self._rainbow_timer.stop()
        
        self._rainbow_timer = QtCore.QTimer()
        self._rainbow_timer.timeout.connect(self._update_rainbow)
        self._rainbow_timer.start(30)  # 每30ms更新一次
    
    def _update_rainbow(self):
        """更新彩虹色相 - 红→橙→黄→绿→青→蓝→紫→白→黑循环"""
        # 检查图片是否在可见区域内,不可见则停止动画
        if not self.isVisible():
            # 图片不可见,停止动画
            self.is_clicked = False
            self.stop_rainbow_animation()
            return
        
        # 检查图片是否在滚动区域的可视范围内
        parent = self.parent()
        if parent:
            # 获取图片在父控件中的位置
            item_rect = self.geometry()
            # 查找滚动区域
            scroll_parent = parent
            while scroll_parent and not isinstance(scroll_parent, QtWidgets.QScrollArea):
                scroll_parent = scroll_parent.parent()
            
            if scroll_parent and isinstance(scroll_parent, QtWidgets.QScrollArea):
                viewport = scroll_parent.viewport()
                viewport_rect = viewport.rect()
                # 将图片坐标转换到viewport坐标系
                item_global_pos = self.mapTo(viewport, QtCore.QPoint(0, 0))
                item_in_viewport = QtCore.QRect(item_global_pos, self.size())
                
                # 如果图片完全不在可视区域内,停止动画
                if not viewport_rect.intersects(item_in_viewport):
                    self.is_clicked = False
                    self.stop_rainbow_animation()
                    return
        
        self._rainbow_hue = (self._rainbow_hue + 4) % 450  # 0-449循环(360彩虹+45白+45黑)
        self.update()
    
    def stop_rainbow_animation(self):
        """停止彩虹边框动画"""
        if self._rainbow_timer:
            self._rainbow_timer.stop()
            self._rainbow_timer = None
    
    def contextMenuEvent(self, event):
        # 删合模式下禁用右键菜单，但不阻止事件传递
        # 右键事件已在mousePressEvent中处理
        if self.merge_mode:
            event.accept()  # 接受事件但不显示菜单
            return
        
        # 获取父窗口
        parent = self.parent()
        while parent and not isinstance(parent, QtWidgets.QDialog):
            parent = parent.parent()
        
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 20px;
                color: #333;
            }
            QMenu::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)
        h_action = menu.addAction("横向滚动看图打开")
        v_action = menu.addAction("垂直滚动看图打开")
        
        # 如果有多选项，添加删除选项
        if parent and hasattr(parent, 'multi_selected_items') and parent.multi_selected_items:
            menu.addSeparator()
            delete_action = menu.addAction(f"删除选中的 {len(parent.multi_selected_items)} 张图片")
        else:
            menu.addSeparator()
            delete_action = menu.addAction("删除此图片")
        
        # 添加显示/隐藏工具栏选项
        menu.addSeparator()
        if parent and hasattr(parent, 'toolbar'):
            if parent.toolbar.isVisible():
                toolbar_action = menu.addAction("隐藏工具栏")
            else:
                toolbar_action = menu.addAction("显示工具栏")
        else:
            toolbar_action = None
        
        action = menu.exec_(event.globalPos())
        if action == h_action:
            self.request_horizontal_viewer.emit(self.image_path)
        elif action == v_action:
            self.request_vertical_viewer.emit(self.image_path)
        elif action == delete_action:
            # 删除功能
            if parent and hasattr(parent, 'delete_multi_selected'):
                parent.delete_multi_selected()
        elif toolbar_action and action == toolbar_action:
            # 切换工具栏显示
            if parent and hasattr(parent, 'toggle_toolbar'):
                parent.toggle_toolbar()


class MasonryWidget(QtWidgets.QWidget):
    """瀑布流容器"""
    
    resized = QtCore.pyqtSignal()  # 大小变化信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.columns = 4
        self.spacing = 10
        self.margin = 0  # 边距设为0，让图片完全占满窗口
        self.horizontal_mode = False  # 横向模式
        self.row_height = 200  # 横向模式的行高
        self.grid_mode = False  # 方格子模式
        self.grid_size = 200  # 方格子尺寸
        self._resize_timer = QtCore.QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._do_relayout)
        
        # 关键修复：不接受焦点，确保键盘事件由父对话框处理
        self.setFocusPolicy(Qt.NoFocus)
    
    def add_item(self, item):
        item.setParent(self)
        self.items.append(item)
    
    def clear_items(self):
        for item in self.items:
            item.setParent(None)
            item.deleteLater()
        self.items.clear()
    
    def get_column_width(self):
        """获取当前列宽（纵向模式）"""
        available_width = self.width() - 2 * self.margin
        if available_width <= 0:
            available_width = 800
        
        # 直接使用用户设置的列数,不自动调整
        total_spacing = (self.columns - 1) * self.spacing
        column_width = (available_width - total_spacing) // self.columns
        
        # 确保列宽不会太小
        return max(50, column_width)
    
    def schedule_relayout(self, delay=50):
        """延迟布局"""
        self._resize_timer.start(delay)
    
    def _do_relayout(self):
        """执行布局"""
        if not self.items:
            self.setMinimumHeight(100)
            return
        
        if self.grid_mode:
            if self.horizontal_mode:
                self._do_grid_horizontal_layout()
            else:
                self._do_grid_layout()
        elif self.horizontal_mode:
            self._do_horizontal_layout()
        else:
            self._do_vertical_layout()
    
    def _do_vertical_layout(self):
        """纵向瀑布流布局（按顺序轮流分配到各列：1→列1, 2→列2, 3→列3, 4→列4, 5→列1...）"""
        col_width = self.get_column_width()
        
        # 使用用户设置的列数
        actual_columns = self.columns
        
        # 更新所有item的几何尺寸
        for item in self.items:
            item.horizontal_mode = False
            item.keep_aspect = False  # 瀑布流模式不保持比例
            item.update_geometry_only(col_width)
        
        # 按顺序轮流分配到各列（瀑布流，但按序号顺序）
        column_heights = [self.margin] * actual_columns
        
        for idx, item in enumerate(self.items):
            # 按顺序分配到列：0,1,2,3,0,1,2,3...
            col = idx % actual_columns
            x = self.margin + col * (col_width + self.spacing)
            y = column_heights[col]
            
            item.move(int(x), int(y))
            item.show()
            
            column_heights[col] += item.actual_height + self.spacing
        
        max_height = max(column_heights) + self.margin
        self.setMinimumHeight(int(max_height))
    
    def _do_grid_layout(self):
        """缩略图纵向布局（固定列数，高度统一，宽度按比例，横向铺满窗口，无黑边）"""
        available_width = self.width() - 2 * self.margin
        if available_width <= 0:
            available_width = 800
        
        # 直接使用用户设置的列数,不自动调整
        cols = max(1, self.columns)
        
        # 计算每张图片的宽高比
        items_data = []
        for item in self.items:
            if item.image_width > 0 and item.image_height > 0:
                ratio = item.image_width / item.image_height
            else:
                ratio = 1.0
            items_data.append((item, ratio))
        
        # 按列数分行（每行固定 cols 张图片）
        rows = []
        for i in range(0, len(items_data), cols):
            row = items_data[i:i + cols]
            rows.append(row)
        
        # 布局每一行
        y = self.margin
        prev_row_height = 150  # 记录上一行高度
        
        for row_idx, row in enumerate(rows):
            if not row:
                continue
            
            # 计算这一行所有图片的宽高比之和
            total_ratio = sum(r for _, r in row)
            num_items = len(row)
            total_spacing = (num_items - 1) * self.spacing
            
            is_last_row = row_idx == len(rows) - 1
            is_incomplete = num_items < cols
            
            # 计算行高：让所有图片正好填满整行宽度
            row_height = (available_width - total_spacing) / total_ratio
            
            # 最后一行图片不足时，使用前一行的高度，不拉伸
            if is_last_row and is_incomplete and len(rows) > 1:
                row_height = prev_row_height
            
            row_height = max(80, int(row_height))
            prev_row_height = row_height
            
            # 计算每张图片的宽度
            x = self.margin
            widths = []
            for item, ratio in row:
                widths.append(int(row_height * ratio))
            
            # 只有非最后一行不足时才补齐误差
            if not (is_last_row and is_incomplete):
                if num_items > 0:
                    total_used = sum(widths) + total_spacing
                    diff = available_width - total_used
                    if diff != 0 and widths:
                        widths[-1] += diff
            
            # 布局这一行的图片
            for i, (item, ratio) in enumerate(row):
                item_width = widths[i]
                
                item.horizontal_mode = False
                item.keep_aspect = False  # 不保持比例，无黑边
                item.actual_width = item_width
                item.actual_height = row_height
                item.setFixedSize(item_width, row_height)
                
                if item.loaded and item.needs_reload(max(item_width, row_height)):
                    item.need_reload.emit(item)
                
                item.move(int(x), int(y))
                item.show()
                
                x += item_width + self.spacing
            
            y += row_height + self.spacing
        
        self.setMinimumHeight(int(y + self.margin))
    
    def _do_grid_horizontal_layout(self):
        """缩略图横向布局（justified布局，高度控制行高，横向铺满窗口）"""
        available_width = self.width() - 2 * self.margin
        if available_width <= 0:
            available_width = 800
        
        target_row_height = self.row_height
        
        # 计算每张图片在目标高度下的宽度
        items_data = []
        for item in self.items:
            if item.image_width > 0 and item.image_height > 0:
                ratio = item.image_width / item.image_height
            else:
                ratio = 1.0
            items_data.append((item, ratio))
        
        # 分行：根据目标高度计算每行能放多少图片
        rows = []
        current_row = []
        current_width = 0
        
        for item, ratio in items_data:
            item_width = target_row_height * ratio
            
            if current_row and current_width + item_width + self.spacing > available_width:
                rows.append(current_row)
                current_row = [(item, ratio)]
                current_width = item_width
            else:
                current_row.append((item, ratio))
                current_width += item_width + (self.spacing if len(current_row) > 1 else 0)
        
        if current_row:
            rows.append(current_row)
        
        # 布局：每行图片拉伸填满宽度
        y = self.margin
        prev_row_height = target_row_height  # 记录上一行高度
        
        for row_idx, row in enumerate(rows):
            if not row:
                continue
            
            # 计算这一行所有图片的宽高比之和
            total_ratio = sum(r for _, r in row)
            num_items = len(row)
            total_spacing = (num_items - 1) * self.spacing
            
            is_last_row = row_idx == len(rows) - 1
            is_incomplete = num_items < 2  # 横向模式：少于2张算不完整
            
            # 计算这一行的实际高度，使得所有图片正好填满宽度
            if is_last_row and is_incomplete and len(rows) > 1:
                # 最后一行不足时，使用前一行的高度
                row_height = prev_row_height
            else:
                row_height = (available_width - total_spacing) / total_ratio
                # 限制高度范围
                row_height = max(target_row_height * 0.5, min(row_height, target_row_height * 1.5))
            
            row_height = int(row_height)
            prev_row_height = row_height
            
            # 计算每张图片的宽度
            widths = []
            for item, ratio in row:
                widths.append(int(row_height * ratio))
            
            # 只有完整行才补齐误差,最后一行不足时不补齐
            if not (is_last_row and is_incomplete):
                if num_items > 0:
                    total_used = sum(widths) + total_spacing
                    diff = available_width - total_used
                    # 限制补齐的误差范围,避免过度拉伸
                    if diff != 0 and widths and abs(diff) < widths[-1] * 0.1:  # 误差不超过10%
                        widths[-1] += diff
            
            # 布局这一行的图片
            x = self.margin
            for i, (item, ratio) in enumerate(row):
                item_width = widths[i]
                
                item.horizontal_mode = False
                item.keep_aspect = False  # 不保持比例，填满格子
                item.actual_width = item_width
                item.actual_height = row_height
                item.setFixedSize(item_width, row_height)
                
                if item.loaded and item.needs_reload(max(item_width, row_height)):
                    item.need_reload.emit(item)
                
                item.move(int(x), int(y))
                item.show()
                
                x += item_width + self.spacing
            
            y += row_height + self.spacing
        
        total_height = y + self.margin
        self.setMinimumHeight(int(total_height))
    
    def _do_horizontal_layout(self):
        """横向justified布局（按行高，自动填满每行）"""
        available_width = self.width() - 2 * self.margin
        if available_width <= 0:
            available_width = 800
        
        # 先计算每张图片在目标高度下的宽度比例
        items_with_ratio = []
        for item in self.items:
            item.horizontal_mode = True
            item.keep_aspect = False  # 横向模式不保持比例
            if item.image_width > 0 and item.image_height > 0:
                # 宽高比
                ratio = item.image_width / item.image_height
            else:
                ratio = 1.0
            items_with_ratio.append((item, ratio))
        
        # 分行：计算每行应该包含哪些图片
        rows = []
        current_row = []
        current_row_width = 0
        
        for item, ratio in items_with_ratio:
            # 在目标高度下的宽度
            item_width = self.row_height * ratio
            
            # 如果当前行加上这张图片会超出，且当前行不为空，则换行
            if current_row and current_row_width + item_width + self.spacing > available_width:
                rows.append(current_row)
                current_row = [(item, ratio)]
                current_row_width = item_width
            else:
                current_row.append((item, ratio))
                current_row_width += item_width + (self.spacing if current_row_width > 0 else 0)
        
        # 添加最后一行
        if current_row:
            rows.append(current_row)
        
        # 布局每一行
        y = self.margin
        prev_row_height = self.row_height  # 记录上一行高度
        
        for row_idx, row in enumerate(rows):
            if not row:
                continue
            
            # 计算这一行所有图片的宽高比之和
            total_ratio = sum(ratio for _, ratio in row)
            num_items = len(row)
            total_spacing = (num_items - 1) * self.spacing
            
            is_last_row = row_idx == len(rows) - 1
            is_incomplete = len(row) < 3
            
            # 计算这一行的实际高度，使得所有图片正好填满宽度
            if is_last_row and is_incomplete and len(rows) > 1:
                # 最后一行不足时，使用前一行的高度
                row_height = prev_row_height
            else:
                row_height = (available_width - total_spacing) / total_ratio
                # 限制高度范围
                row_height = max(self.row_height * 0.5, min(row_height, self.row_height * 1.5))
            
            prev_row_height = row_height
            
            # 计算每张图片的宽度
            widths = []
            for item, ratio in row:
                widths.append(int(row_height * ratio))
            
            # 只有完整行才补齐误差,最后一行不足时不补齐
            if not (is_last_row and is_incomplete):
                if num_items > 0:
                    total_used = sum(widths) + total_spacing
                    diff = available_width - total_used
                    # 限制补齐的误差范围,避免过度拉伸
                    if diff != 0 and widths and abs(diff) < widths[-1] * 0.1:  # 误差不超过10%
                        widths[-1] += diff
            
            # 布局这一行的图片
            x = self.margin
            for i, (item, ratio) in enumerate(row):
                item_width = widths[i]
                item_height = int(row_height)
                
                item.actual_width = item_width
                item.actual_height = item_height
                item.thumbnail_height = item_height
                item.setFixedSize(item_width, item_height)
                
                item.move(int(x), int(y))
                item.show()
                
                x += item_width + self.spacing
            
            y += int(row_height) + self.spacing
        
        total_height = y + self.margin
        self.setMinimumHeight(int(total_height))
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_relayout(100)
        # 发出大小变化信号
        self.resized.emit()
    
    def contextMenuEvent(self, event):
        """右键菜单 - 在缩略图区域"""
        # 获取父对话框
        parent_dialog = self.parent()
        while parent_dialog and not isinstance(parent_dialog, MasonryThumbnailDialog):
            parent_dialog = parent_dialog.parent()
        
        if parent_dialog:
            menu = QtWidgets.QMenu(self)
            
            # 添加显示/隐藏工具栏选项
            if parent_dialog.toolbar.isVisible():
                toggle_action = menu.addAction("隐藏工具栏")
            else:
                toggle_action = menu.addAction("显示工具栏")
            toggle_action.triggered.connect(parent_dialog.toggle_toolbar)
            
            menu.exec_(event.globalPos())
        self.resized.emit()


class MasonryThumbnailDialog(QtWidgets.QDialog):
    """瀑布流缩略图查看器"""
    
    image_switched = QtCore.pyqtSignal(str)
    open_horizontal_viewer = QtCore.pyqtSignal(str)
    open_vertical_viewer = QtCore.pyqtSignal(str)
    files_changed = QtCore.pyqtSignal()  # 文件列表变化信号（合并/删除后）
    
    def __init__(self, image_list, current_filename=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("瀑布流缩略图")
        self.resize(1200, 800)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowState(Qt.WindowMaximized)  # 默认最大化
        
        # 设置焦点策略，确保能接收键盘事件
        self.setFocusPolicy(Qt.StrongFocus)
        
        # 启用拖放功能
        self.setAcceptDrops(True)
        
        # 设置最小尺寸，允许窗口缩小到很小
        self.setMinimumSize(300, 200)
        
        self.image_list = image_list
        self.current_filename = current_filename
        self.labeling_widget = parent  # 保存父窗口引用
        
        self.thumbnail_width = 200
        self.border_radius = 20
        self.border_width = 0  # 边框宽度
        self.spacing = 5
        self.columns = 4
        self.row_height = 200  # 横向模式行高
        self.horizontal_mode = False  # 横向模式
        self.grid_mode = False  # 方格子模式（统一尺寸）
        self.grid_size = 200  # 方格子尺寸
        
        # 悬停信息显示开关（需要在load_settings之前定义）
        self.show_hover_info = True  # 默认显示悬停信息
        
        # 加载持久化设置
        self.load_settings()
        
        self.loaded_count = 0
        self.load_batch_size = 10
        self.items_map = {}
        self.reload_queue = []  # 需要重新加载的item队列
        
        # 线程池
        self.thread_pool = QtCore.QThreadPool()
        self.thread_pool.setMaxThreadCount(4)
        
        # 删合模式相关状态
        self.merge_mode = False  # 是否处于删合模式
        self.current_merge_sub_mode = 'select'  # 'select' 或 'delete'
        self.selected_images = []  # 选中的图片文件名列表
        self.deletion_list = []  # 标记删除的图片文件名列表
        self.merge_target = None  # 合并目标文件名
        self._last_selected_index = None  # 记录上次点击的索引，用于Shift范围选择（删合模式）
        
        # 普通模式多选状态
        self.multi_selected_items = []  # Ctrl+左键多选的图片项列表
        self._last_multi_selected_index = None  # 记录上次点击的索引，用于Shift范围选择（普通模式）
        
        # 初始化鼠标指针
        self._init_cursors()
        
        self.init_ui()
        
        # 不在这里启动加载，等showEvent时再启动
        self._loading_started = False
    
    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        if not self._loading_started:
            self._loading_started = True
            # 窗口显示后再开始加载，确保尺寸正确
            QtCore.QTimer.singleShot(50, self.start_loading)
        
        # 确保窗口获得焦点，以便接收键盘事件
        self.setFocus()
        
        # 在普通模式下也需要临时移除主窗口的W/A/D快捷键
        if not self.merge_mode:
            self._remove_main_window_shortcuts()
    
    def focusInEvent(self, event):
        """窗口获得焦点时"""
        super().focusInEvent(event)
        # 获得焦点时，移除主窗口的快捷键
        self._remove_main_window_shortcuts()
        # 自动刷新已编辑状态
        self.refresh_edited_status()
    
    def refresh_edited_status(self):
        """刷新所有图片的已编辑状态"""
        for item in self.masonry_widget.items:
            # 重新检查已编辑状态
            item._check_manually_edited()
            item.update()
        
        # 更新已编辑统计
        self.update_edited_count()
    
    def focusOutEvent(self, event):
        """窗口失去焦点时"""
        super().focusOutEvent(event)
        # 失去焦点时，恢复主窗口的快捷键
        self._restore_main_window_shortcuts()
    
    def changeEvent(self, event):
        """窗口状态改变事件"""
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.WindowStateChange:
            # 窗口最小化时，恢复主窗口快捷键
            if self.isMinimized():
                self._restore_main_window_shortcuts()
                # 激活主窗口，确保快捷键生效
                if self.labeling_widget:
                    # 使用更长的延迟，确保最小化动画完成
                    QtCore.QTimer.singleShot(100, lambda: self.labeling_widget.raise_())
                    QtCore.QTimer.singleShot(150, lambda: self.labeling_widget.activateWindow())
                    QtCore.QTimer.singleShot(200, lambda: self.labeling_widget.setFocus())
                    # 再次确保快捷键已恢复
                    QtCore.QTimer.singleShot(250, self._restore_main_window_shortcuts)
            # 窗口从最小化恢复时，移除主窗口快捷键
            elif event.oldState() & Qt.WindowMinimized:
                # 延迟移除主窗口快捷键，确保窗口完全恢复
                QtCore.QTimer.singleShot(100, self._remove_main_window_shortcuts)
    
    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.toolbar = self.create_toolbar()  # 保存工具栏引用
        main_layout.addWidget(self.toolbar)
        
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # 关键修复：不接受焦点，确保键盘事件由父对话框处理
        self.scroll_area.setFocusPolicy(Qt.NoFocus)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background-color: #1e1e1e; border: none; }
            QScrollBar:vertical { border: none; background: #2b2b2b; width: 12px; }
            QScrollBar::handle:vertical { background: #666; min-height: 20px; border-radius: 5px; margin: 2px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        
        # 连接滚动条信号，更新标题显示当前位置
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_title_with_position)
        
        self.masonry_widget = MasonryWidget()
        self.masonry_widget.setStyleSheet("background-color: #1e1e1e;")
        self.masonry_widget.columns = self.columns
        self.masonry_widget.spacing = self.spacing
        self.masonry_widget.row_height = self.row_height
        self.masonry_widget.grid_mode = self.grid_mode
        self.masonry_widget.horizontal_mode = self.horizontal_mode
        self.masonry_widget.border_radius = self.border_radius
        self.masonry_widget.border_width = self.border_width
        self.masonry_widget.resized.connect(self.on_masonry_resized)
        
        self.scroll_area.setWidget(self.masonry_widget)
        main_layout.addWidget(self.scroll_area)
        
        # 窗口大小变化延迟处理定时器
        self._resize_reload_timer = QtCore.QTimer()
        self._resize_reload_timer.setSingleShot(True)
        self._resize_reload_timer.timeout.connect(self.process_reload_queue)
        
        self.create_thumbnail_items()

    def create_toolbar(self):
        toolbar = QtWidgets.QWidget()
        toolbar.setFixedHeight(50)
        toolbar.setStyleSheet("""
            QWidget { background-color: #2b2b2b; }
            QLabel { color: #fff; padding: 0 3px; font-size: 12px; }
            QSlider { min-width: 80px; max-width: 120px; }
            QSlider::groove:horizontal { border: 1px solid #555; height: 4px; background: #444; border-radius: 2px; }
            QSlider::handle:horizontal { background: #888; border: 1px solid #666; width: 14px; margin: -5px 0; border-radius: 7px; }
            QSlider::handle:horizontal:hover { background: #aaa; }
        """)
        
        layout = QtWidgets.QHBoxLayout(toolbar)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # 列距
        self.spacing_label_text = QtWidgets.QLabel("列距:")
        layout.addWidget(self.spacing_label_text)
        self.spacing_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.spacing_slider.setRange(0, 40)
        self.spacing_slider.setValue(self.spacing)
        self.spacing_slider.sliderReleased.connect(self.on_spacing_released)
        self.spacing_slider.valueChanged.connect(lambda v: self.spacing_label.setText(str(v)))
        layout.addWidget(self.spacing_slider)
        self.spacing_label = QtWidgets.QLabel(str(self.spacing))
        self.spacing_label.setFixedWidth(25)
        layout.addWidget(self.spacing_label)
        
        self._add_sep(layout)
        
        # 圆角
        self.radius_label_text = QtWidgets.QLabel("圆角:")
        layout.addWidget(self.radius_label_text)
        self.radius_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.radius_slider.setRange(0, 40)
        self.radius_slider.setValue(self.border_radius)
        self.radius_slider.sliderReleased.connect(self.on_radius_released)
        self.radius_slider.valueChanged.connect(lambda v: self.radius_label.setText(str(v)))
        layout.addWidget(self.radius_slider)
        self.radius_label = QtWidgets.QLabel(str(self.border_radius))
        self.radius_label.setFixedWidth(25)
        layout.addWidget(self.radius_label)
        
        self._add_sep(layout)
        
        # 边框
        self.border_label_text = QtWidgets.QLabel("边框:")
        layout.addWidget(self.border_label_text)
        self.border_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.border_slider.setRange(0, 10)
        self.border_slider.setValue(self.border_width)
        self.border_slider.sliderReleased.connect(self.on_border_released)
        self.border_slider.valueChanged.connect(lambda v: self.border_label.setText(str(v)))
        layout.addWidget(self.border_slider)
        self.border_label = QtWidgets.QLabel(str(self.border_width))
        self.border_label.setFixedWidth(25)
        layout.addWidget(self.border_label)
        
        self._add_sep(layout)
        
        # 列数（纵向模式）
        self.columns_label_text = QtWidgets.QLabel("列数:")
        layout.addWidget(self.columns_label_text)
        self.mode_btn = QtWidgets.QPushButton("纵向")
        self.mode_btn.setFixedWidth(40)
        self.mode_btn.setStyleSheet("""
            QPushButton { background: #444; color: #fff; border: 1px solid #666; border-radius: 3px; padding: 2px 5px; }
            QPushButton:hover { background: #555; }
        """)
        self.mode_btn.clicked.connect(self.set_vertical_mode)
        layout.addWidget(self.mode_btn)
        
        self.columns_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.columns_slider.setRange(1, 10)
        self.columns_slider.setValue(self.columns)
        self.columns_slider.setEnabled(not self.horizontal_mode)
        self.columns_slider.sliderReleased.connect(self.on_columns_released)
        self.columns_slider.valueChanged.connect(lambda v: self.columns_label.setText(str(v)))
        layout.addWidget(self.columns_slider)
        self.columns_label = QtWidgets.QLabel(str(self.columns))
        self.columns_label.setFixedWidth(25)
        layout.addWidget(self.columns_label)
        
        self._add_sep(layout)
        # 高度（横向模式）
        self.height_label_text = QtWidgets.QLabel("高度:")
        layout.addWidget(self.height_label_text)
        self.height_mode_btn = QtWidgets.QPushButton("横向")
        self.height_mode_btn.setFixedWidth(40)
        if self.horizontal_mode:
            self.height_mode_btn.setStyleSheet("""
                QPushButton { background: #444; color: #fff; border: 1px solid #666; border-radius: 3px; padding: 2px 5px; }
                QPushButton:hover { background: #555; }
            """)
        else:
            self.height_mode_btn.setStyleSheet("""
                QPushButton { background: #333; color: #888; border: 1px solid #555; border-radius: 3px; padding: 2px 5px; }
                QPushButton:hover { background: #444; }
            """)
        self.height_mode_btn.clicked.connect(self.set_horizontal_mode)
        layout.addWidget(self.height_mode_btn)
        
        self.height_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.height_slider.setRange(100, 600)
        self.height_slider.setValue(self.row_height)
        self.height_slider.sliderReleased.connect(self.on_height_released)
        self.height_slider.valueChanged.connect(lambda v: self.height_label.setText(str(v)))
        self.height_slider.setEnabled(self.horizontal_mode)
        layout.addWidget(self.height_slider)
        self.height_label = QtWidgets.QLabel(str(self.row_height))
        self.height_label.setFixedWidth(30)
        layout.addWidget(self.height_label)
        
        self._add_sep(layout)
        
        # 瀑布流/方格子切换
        self.layout_mode_btn = QtWidgets.QPushButton("缩略图" if self.grid_mode else "瀑布流")
        self.layout_mode_btn.setFixedSize(60, 28)
        self.layout_mode_btn.setStyleSheet("""
            QPushButton { background: #0078d4; color: #fff; border: 1px solid #005a9e; border-radius: 3px; padding: 4px 8px; font-weight: bold; }
            QPushButton:hover { background: #1084d8; }
        """)
        self.layout_mode_btn.clicked.connect(self.toggle_layout_mode)
        layout.addWidget(self.layout_mode_btn)
        
        self._add_sep(layout)
        
        # 隐藏悬停信息开关
        self.hide_hover_info_btn = QtWidgets.QPushButton("隐藏信息")
        self.hide_hover_info_btn.setFixedSize(70, 28)
        self.hide_hover_info_btn.setCheckable(True)
        self.hide_hover_info_btn.setChecked(not self.show_hover_info)  # 根据配置设置初始状态
        self.hide_hover_info_btn.setStyleSheet("""
            QPushButton { 
                background: #444; 
                color: #fff; 
                border: 1px solid #666; 
                border-radius: 3px; 
                padding: 4px 8px; 
            }
            QPushButton:hover { background: #555; }
            QPushButton:checked { 
                background: #0078d4; 
                border: 1px solid #005a9e; 
                font-weight: bold;
            }
        """)
        self.hide_hover_info_btn.clicked.connect(self.toggle_hover_info)
        layout.addWidget(self.hide_hover_info_btn)
        
        self._add_sep(layout)
        
        # 删合模式按钮
        self.merge_mode_btn = QtWidgets.QPushButton("删合模式")
        self.merge_mode_btn.setFixedSize(70, 28)
        self.merge_mode_btn.setStyleSheet("""
            QPushButton { 
                background: #d83b01; 
                color: #fff; 
                border: 1px solid #a52a00; 
                border-radius: 3px; 
                padding: 4px 8px; 
                font-weight: bold; 
            }
            QPushButton:hover { background: #e74c1c; }
        """)
        self.merge_mode_btn.clicked.connect(self.toggle_merge_mode)
        layout.addWidget(self.merge_mode_btn)
        
        # 删合模式状态标签（初始隐藏）
        self.merge_mode_status_label = QtWidgets.QLabel("")
        self.merge_mode_status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 13px; padding-left: 8px;")
        self.merge_mode_status_label.setVisible(False)
        layout.addWidget(self.merge_mode_status_label)
        
        # 删合模式统计标签（初始隐藏）
        self.merge_stats_label = QtWidgets.QLabel("")
        self.merge_stats_label.setStyleSheet("color: #aaa; font-size: 12px; padding-left: 15px;")
        self.merge_stats_label.setVisible(False)
        layout.addWidget(self.merge_stats_label)
        
        # 普通模式多选统计标签（始终显示）
        self.multi_select_label = QtWidgets.QLabel("已选中: 0")
        self.multi_select_label.setStyleSheet("color: #00E676; font-weight: bold; font-size: 12px; padding-left: 15px;")  # 亮绿色
        layout.addWidget(self.multi_select_label)
        
        # 已编辑统计标签（始终显示）
        self.edited_count_label = QtWidgets.QLabel("已编辑: 0")
        self.edited_count_label.setStyleSheet("color: #FFA500; font-weight: bold; font-size: 12px; padding-left: 15px;")  # 橙色
        layout.addWidget(self.edited_count_label)
        
        layout.addStretch()
        
        self.count_label = QtWidgets.QLabel(f"总数: {len(self.image_list)} | 加载中...")
        self.count_label.setStyleSheet("color: #aaa;")
        layout.addWidget(self.count_label)
        
        return toolbar
    
    def _add_sep(self, layout):
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet("color: #555;")
        layout.addWidget(sep)
    
    def _get_manually_edited_color(self):
        """获取手动编辑颜色配置"""
        default_color = "#FFA500"  # 默认橙色
        if self.labeling_widget and hasattr(self.labeling_widget, '_config'):
            color_value = self.labeling_widget._config.get("manually_edited_color", default_color)
            if isinstance(color_value, list):
                # RGB列表格式
                return QtGui.QColor(*color_value[:3])
            else:
                return QtGui.QColor(color_value)
        return QtGui.QColor(default_color)
    
    def _get_difficult_color(self):
        """获取困难标记颜色配置"""
        default_color = [128, 0, 128]  # 默认紫色
        if self.labeling_widget and hasattr(self.labeling_widget, '_config'):
            traffic_light_colors = self.labeling_widget._config.get("traffic_light_colors", {})
            color_value = traffic_light_colors.get("difficult", default_color)
            if isinstance(color_value, (list, tuple)):
                # RGB列表或元组格式
                return QtGui.QColor(*color_value[:3])
        return QtGui.QColor(*default_color)
    
    def _get_label_color(self, label):
        """获取标签颜色（从主界面同步）"""
        if self.labeling_widget and hasattr(self.labeling_widget, '_get_rgb_by_label'):
            return self.labeling_widget._get_rgb_by_label(label)
        return None
    
    def create_thumbnail_items(self):
        """创建所有缩略图项"""
        edited_color = self._get_manually_edited_color().name()
        difficult_color = self._get_difficult_color().name()
        for idx, path in enumerate(self.image_list, start=1):
            item = ThumbnailItem(
                path, self.thumbnail_width, self.border_radius, 
                edited_color, self.border_width, self._get_label_color,
                difficult_color, index=idx
            )
            item.clicked.connect(self.on_thumbnail_clicked)
            item.request_horizontal_viewer.connect(self.open_horizontal_viewer.emit)
            item.request_vertical_viewer.connect(self.open_vertical_viewer.emit)
            item.request_switch_image.connect(self.on_thumbnail_clicked)
            item.need_reload.connect(self.on_item_need_reload)
            item.toggle_edited.connect(self.on_toggle_edited)
            # 连接删合模式信号
            item.merge_state_changed.connect(self.on_merge_state_changed)
            item.range_select_requested.connect(self.on_range_select)
            item.set_merge_target_requested.connect(self.on_set_merge_target)
            
            # 如果当前处于删合模式，设置item的删合模式状态和鼠标指针
            if self.merge_mode:
                item.merge_mode = True
                item.current_merge_sub_mode = self.current_merge_sub_mode
                item.set_cursors(self.select_cursor, self.delete_cursor)
                item.set_merge_mode_cursor(self.current_merge_sub_mode)
            
            # 设置悬停信息显示状态
            item.show_hover_info = self.show_hover_info
            
            self.masonry_widget.add_item(item)
            self.items_map[path] = item
        
        self.masonry_widget._do_relayout()
    
    def on_merge_state_changed(self, item):
        """当选择状态改变时更新"""
        self.update_selected_list()
        self.update_merge_stats()
    
    def on_range_select(self, item, current_index):
        """处理范围选择（Shift+左键）- 删合模式"""
        if self._last_selected_index is None:
            # 第一次点击，只选中当前项
            self._last_selected_index = current_index
            item.is_selected = True
            item.update_merge_visual()
            self.update_selected_list()
            return
        
        # 计算范围
        start_idx = min(self._last_selected_index, current_index)
        end_idx = max(self._last_selected_index, current_index)
        
        # 选中范围内的所有项
        for idx in range(start_idx, end_idx + 1):
            if idx < len(self.masonry_widget.items):
                target_item = self.masonry_widget.items[idx]
                target_item.is_selected = True
                target_item.update_merge_visual()
        
        self._last_selected_index = current_index
        self.update_selected_list()
        self.update_merge_stats()
    
    def on_normal_range_select(self, item, current_index):
        """处理范围选择（Shift+左键）- 普通模式"""
        
        if self._last_multi_selected_index is None:
            # 第一次点击，只选中当前项
            self._last_multi_selected_index = current_index
            item.is_multi_selected = True
            item.status_icon.setText("✅")
            item.status_icon.setStyleSheet("background-color: transparent; color: #00E676; font-size: 18px;")
            item.status_icon.show()
            item.update()
            self.update_multi_selection()
            return
        
        # 计算范围
        start_idx = min(self._last_multi_selected_index, current_index)
        end_idx = max(self._last_multi_selected_index, current_index)
        
        # 选中范围内的所有项
        for idx in range(start_idx, end_idx + 1):
            if idx < len(self.masonry_widget.items):
                target_item = self.masonry_widget.items[idx]
                if not target_item.is_multi_selected:
                    target_item.is_multi_selected = True
                    target_item.status_icon.setText("✅")
                    target_item.status_icon.setStyleSheet("background-color: transparent; color: #00E676; font-size: 18px;")
                    target_item.status_icon.show()
                    target_item.update()
        
        self._last_multi_selected_index = current_index
        self.update_multi_selection()
    
    def on_set_merge_target(self, item, index):
        """设置合并目标"""
        # 清除之前的合并目标
        for target_item in self.masonry_widget.items:
            if target_item.is_merge_target:
                target_item.is_merge_target = False
                target_item.update_merge_visual()
        
        # 设置新的合并目标
        if index < len(self.image_list):
            item.is_merge_target = True
            item.update_merge_visual()
            self.merge_target = self.image_list[index]
            self.update_merge_stats()
        else:
            pass
    
    def update_selected_list(self):
        """更新选中和删除列表"""
        self.selected_images.clear()
        self.deletion_list.clear()
        
        for idx, item in enumerate(self.masonry_widget.items):
            if item.is_selected:
                self.selected_images.append(self.image_list[idx])
            if item.is_marked_delete:
                self.deletion_list.append(self.image_list[idx])
    
    def start_loading(self):
        """开始后台加载"""
        self.load_timer = QtCore.QTimer()
        self.load_timer.timeout.connect(self.load_next_batch)
        self.load_timer.start(30)
        
        # 初始化标题显示
        self.update_title_with_position()
    
    def scroll_to_image(self, filename):
        """滚动到指定图片并高亮显示"""
        if not filename:
            return
        
        # 查找图片对应的item
        target_item = None
        for item in self.masonry_widget.items:
            if item.image_path == filename:
                target_item = item
                break
        
        if not target_item:
            return
        
        # 获取item在父控件中的位置
        item_pos = target_item.pos()
        item_y = item_pos.y()
        item_height = target_item.height()
        
        # 获取滚动区域的可见高度
        viewport_height = self.scroll_area.viewport().height()
        
        # 计算滚动位置，让目标图片显示在可见区域的中间偏上位置
        scroll_value = item_y - viewport_height // 3
        
        # 确保滚动值在有效范围内
        scroll_bar = self.scroll_area.verticalScrollBar()
        scroll_value = max(0, min(scroll_value, scroll_bar.maximum()))
        
        # 平滑滚动到目标位置
        scroll_bar.setValue(int(scroll_value))
        
        # 启动高亮动画
        target_item.start_highlight()
    
    def get_load_width(self):
        """获取加载宽度/高度"""
        window_width = self.width()
        if window_width < 100:
            window_width = 1200
        
        available_width = window_width - 2 * self.masonry_widget.margin - 20
        
        if self.grid_mode:
            # 缩略图模式：根据列数估算最大尺寸
            # justified布局下，图片高度约等于 available_width / columns
            estimated_size = available_width // max(1, self.columns)
            return max(300, int(estimated_size * 1.5))
        elif self.horizontal_mode:
            # 横向模式：使用行高
            return max(250, self.row_height)
        else:
            # 纵向瀑布流模式：使用列宽
            total_spacing = (self.columns - 1) * self.spacing
            col_width = (available_width - total_spacing) // self.columns
            return max(250, col_width)
    
    def load_next_batch(self):
        """加载下一批"""
        items = self.masonry_widget.items
        if self.loaded_count >= len(items):
            self.load_timer.stop()
            self.count_label.setText(f"总数: {len(self.image_list)} | 已加载: {self.loaded_count}")
            # 更新已编辑统计
            self.update_edited_count()
            # 处理重新加载队列
            self.process_reload_queue()
            # 首次加载完成后，滚动到当前图片并高亮
            if self.current_filename and not hasattr(self, '_initial_scroll_done'):
                self._initial_scroll_done = True
                # 延迟执行，确保布局完成
                QtCore.QTimer.singleShot(300, lambda: self.scroll_to_image(self.current_filename))
            return
        
        load_width = self.get_load_width()
        end_idx = min(self.loaded_count + self.load_batch_size, len(items))
        
        for i in range(self.loaded_count, end_idx):
            item = items[i]
            if not item.loaded and not item.loading:
                item.loading = True
                loader = ThumbnailLoader(item.image_path, load_width)
                loader.signals.loaded.connect(self.on_thumbnail_loaded)
                self.thread_pool.start(loader)
        
        self.loaded_count = end_idx
        self.count_label.setText(f"总数: {len(self.image_list)} | 加载: {self.loaded_count}")
    
    def on_thumbnail_loaded(self, path, pixmap, orig_w, orig_h, load_width):
        """缩略图加载完成"""
        if path in self.items_map:
            item = self.items_map[path]
            item.set_pixmap(pixmap, orig_w, orig_h, load_width)
            self.masonry_widget.schedule_relayout(50)
    
    def on_item_need_reload(self, item):
        """item需要重新加载更高分辨率"""
        if item not in self.reload_queue:
            self.reload_queue.append(item)
    
    def process_reload_queue(self):
        """处理重新加载队列"""
        if not self.reload_queue:
            return
        
        load_width = self.get_load_width()
        
        for item in self.reload_queue:
            if not item.loading:
                item.loading = True
                loader = ThumbnailLoader(item.image_path, load_width)
                loader.signals.loaded.connect(self.on_thumbnail_loaded)
                self.thread_pool.start(loader)
        
        self.reload_queue.clear()
    
    def on_thumbnail_clicked(self, path):
        # 先恢复主窗口的快捷键
        self._restore_main_window_shortcuts()
        
        self.image_switched.emit(path)
        self.showMinimized()
        
        # 切换到主界面时，让主窗口获得焦点并强制刷新快捷键
        if self.labeling_widget:
            # 激活主窗口
            QtCore.QTimer.singleShot(100, lambda: self.labeling_widget.activateWindow())
            QtCore.QTimer.singleShot(150, lambda: self.labeling_widget.setFocus())
            # 再次确保快捷键已恢复（延迟执行，确保窗口状态已更新）
            QtCore.QTimer.singleShot(200, self._restore_main_window_shortcuts)
    
    def on_toggle_edited(self, item):
        """切换图片的已编辑状态"""
        path = item.image_path
        json_path = os.path.splitext(path)[0] + ".json"
        
        if not os.path.exists(json_path):
            # JSON文件不存在，创建一个带有manually_edited标记的文件
            data = {
                "version": "3.2.2",
                "flags": {},
                "shapes": [],
                "imagePath": os.path.basename(path),
                "imageData": None,
                "imageHeight": 0,
                "imageWidth": 0,
                "manually_edited": True
            }
            # 尝试获取图片尺寸
            reader = QtGui.QImageReader(path)
            size = reader.size()
            if size.isValid():
                data["imageWidth"] = size.width()
                data["imageHeight"] = size.height()
        else:
            # 读取现有JSON文件
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                return
            # 切换manually_edited状态
            data["manually_edited"] = not data.get("manually_edited", False)
        
        # 保存JSON文件
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            return
        
        # 更新item的状态
        item.is_manually_edited = data.get("manually_edited", False)
        # 更新标签统计和困难标记
        shapes = data.get("shapes", [])
        item.label_stats = {}
        item.difficult_count = 0
        for shape in shapes:
            label = shape.get("label", "unknown")
            item.label_stats[label] = item.label_stats.get(label, 0) + 1
            # 统计困难标记
            if shape.get("difficult", False):
                item.difficult_count += 1
        item.total_labels = len(shapes)
        item.update()
        
        # 更新已编辑统计
        self.update_edited_count()
        
        # 更新主界面的文件列表颜色
        if self.labeling_widget and hasattr(self.labeling_widget, 'update_file_item_color'):
            self.labeling_widget.update_file_item_color(path, item.is_manually_edited)
    
    def on_spacing_released(self):
        self.spacing = self.spacing_slider.value()
        self.masonry_widget.spacing = self.spacing
        self.masonry_widget.schedule_relayout(0)
        self.save_masonry_settings()
    
    def on_radius_released(self):
        self.border_radius = self.radius_slider.value()
        for item in self.masonry_widget.items:
            item.update_radius(self.border_radius)
        self.save_masonry_settings()
    
    def on_border_released(self):
        self.border_width = self.border_slider.value()
        for item in self.masonry_widget.items:
            item.set_border_width(self.border_width)
        self.save_masonry_settings()
    
    def toggle_layout_mode(self):
        """切换瀑布流/方格子模式"""
        self.grid_mode = not self.grid_mode
        self.masonry_widget.grid_mode = self.grid_mode
        
        if self.grid_mode:
            self.layout_mode_btn.setText("缩略图")
        else:
            self.layout_mode_btn.setText("瀑布流")
        
        self.masonry_widget.schedule_relayout(0)
        self._resize_reload_timer.start(300)
        self.save_masonry_settings()
        # 延迟更新标题以确保布局完成
        QtCore.QTimer.singleShot(350, self.update_title_with_position)
    
    def toggle_hover_info(self):
        """切换悬停信息显示"""
        self.show_hover_info = not self.show_hover_info
        
        # 更新所有item的悬停信息显示状态
        for item in self.masonry_widget.items:
            item.show_hover_info = self.show_hover_info
            # 如果当前正在悬停，立即更新显示
            if item.hovered:
                item.update()
        
        # 保存配置
        self.save_masonry_settings()
    
    def toggle_merge_mode(self):
        """切换删合模式"""
        self.merge_mode = not self.merge_mode
        
        if self.merge_mode:
            # 进入删合模式
            self.merge_mode_btn.setText("退出删合")
            self.merge_mode_btn.setStyleSheet("""
                QPushButton { 
                    background: #107c10; 
                    color: #fff; 
                    border: 1px solid #0b5a0b; 
                    border-radius: 3px; 
                    padding: 4px 8px; 
                    font-weight: bold; 
                }
                QPushButton:hover { background: #13a313; }
            """)
            self.enter_merge_mode()
        else:
            # 退出删合模式
            self.merge_mode_btn.setText("删合模式")
            self.merge_mode_btn.setStyleSheet("""
                QPushButton { 
                    background: #d83b01; 
                    color: #fff; 
                    border: 1px solid #a52a00; 
                    border-radius: 3px; 
                    padding: 4px 8px; 
                    font-weight: bold; 
                }
                QPushButton:hover { background: #e74c1c; }
            """)
            self.exit_merge_mode()
    
    def enter_merge_mode(self):
        """进入删合模式"""
        # 清除普通模式的所有多选
        for item in self.masonry_widget.items:
            if item.is_multi_selected:
                item.is_multi_selected = False
                item.status_icon.hide()
                item.update()
        self.multi_selected_items.clear()
        
        # 隐藏普通模式的多选统计标签和已编辑统计标签
        self.multi_select_label.setVisible(False)
        self.edited_count_label.setVisible(False)
        
        # 临时移除主窗口的快捷键（如果还没移除的话）
        self._remove_main_window_shortcuts()
        
        # 显示模式状态标签（在主工具栏）
        self.merge_mode_status_label.setText("当前模式：选择模式")
        self.merge_mode_status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 13px; padding-left: 8px;")
        self.merge_mode_status_label.setVisible(True)
        
        # 显示统计标签（在主工具栏）
        self.merge_stats_label.setText("已选: 0 | 已标记删除: 0")
        self.merge_stats_label.setVisible(True)
        
        # 修改缩略图项的点击行为
        for item in self.masonry_widget.items:
            item.merge_mode = True
            item.current_merge_sub_mode = self.current_merge_sub_mode
        
        # 应用鼠标指针（在设置merge_mode之后）
        self._apply_background_cursor()
        self._update_items_cursor()
    
    def exit_merge_mode(self):
        """退出删合模式"""
        # 不恢复快捷键，因为普通模式也需要使用W/A/D
        
        # 隐藏删合模式状态标签和统计标签
        self.merge_mode_status_label.setVisible(False)
        self.merge_stats_label.setVisible(False)
        
        # 显示普通模式的多选统计标签和已编辑统计标签
        self.multi_select_label.setVisible(True)
        self.edited_count_label.setVisible(True)
        
        # 恢复默认鼠标指针
        if hasattr(self, 'scroll_area') and self.scroll_area is not None:
            self.scroll_area.viewport().setCursor(Qt.ArrowCursor)
        
        # 清除选择状态
        self.selected_images.clear()
        self.deletion_list.clear()
        self.merge_target = None
        self._last_selected_index = None
        
        # 恢复缩略图项的正常行为并清除所有标记
        for item in self.masonry_widget.items:
            item.merge_mode = False
            item.is_selected = False
            item.is_marked_delete = False
            item.is_merge_target = False
            item.is_multi_selected = False  # 同时清除多选状态
            item.status_icon.hide()  # 隐藏状态图标
            item.setCursor(Qt.PointingHandCursor)  # 恢复默认指针
            item.update()  # 强制重绘以清除边框
        
        # 清空多选列表
        self.multi_selected_items.clear()
        
        # 更新多选统计标签
        self.multi_select_label.setText("已选中: 0")
        self.multi_select_label.setStyleSheet("color: #666; font-size: 12px; padding-left: 15px;")
        
        # 更新已编辑统计
        self.update_edited_count()
    
    def switch_merge_sub_mode(self, mode):
        """切换删合子模式（选择/删除）"""
        self.current_merge_sub_mode = mode
        
        if mode == 'select':
            self.merge_mode_status_label.setText("当前模式：选择模式")
            self.merge_mode_status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 13px; padding-left: 8px;")
        else:
            self.merge_mode_status_label.setText("当前模式：删除模式")
            self.merge_mode_status_label.setStyleSheet("color: #f44336; font-weight: bold; font-size: 13px; padding-left: 8px;")
        
        # 应用鼠标指针
        self._apply_background_cursor()
        self._update_items_cursor()
        
        # 更新所有缩略图项的模式
        for item in self.masonry_widget.items:
            item.current_merge_sub_mode = mode
    
    def merge_selected_images(self):
        """合并选中的图片"""
        
        if len(self.selected_images) < 2:
            QtWidgets.QMessageBox.warning(self, "警告", "请至少选择两张图片进行合并！")
            return
        
        if not self.merge_target:
            QtWidgets.QMessageBox.warning(self, "警告", "请右键点击选中的图片设置合并目标（保留的图片）！")
            return
        
        if self.merge_target not in self.selected_images:
            QtWidgets.QMessageBox.warning(self, "警告", "合并目标必须在选中的图片中！")
            return
        
        # 构建确认对话框的HTML内容
        def esc(t: str) -> str:
            return (t.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))
        
        GREEN = 'style="background:#00e676;color:#000;padding:0 2px;border-radius:2px"'
        RED = 'style="color:#fff;background:#ff1744;padding:0 2px;border-radius:2px"'
        
        # 按起始时间排序（而不是字母顺序）
        def get_start_ms(path):
            try:
                fname = os.path.basename(path)
                ms, _ = self._parse_start_time(fname)
                return ms
            except:
                return 0
        
        sel_list = sorted(self.selected_images, key=get_start_ms)
        
        # 获取第一张和最后一张的文件名（用于高亮显示）
        first_file = os.path.basename(sel_list[0])
        last_file = os.path.basename(sel_list[-1])
        target_file = os.path.basename(self.merge_target)
        
        def line_with_highlight(fn: str, is_first: bool, is_last: bool) -> str:
            """高亮显示文件名中的开始和结束时间"""
            name_no_ext, ext = os.path.splitext(fn)
            if "__" not in name_no_ext:
                return esc(fn)
            
            left, right = name_no_ext.split("__", 1)
            # 提取开始时间（前4段）
            start_parts = left.split("_")[:4]
            if len(start_parts) == 4:
                start_str = "_".join(start_parts)
            else:
                start_str = None
            
            # 提取结束时间（右侧前4段）
            end_parts = right.split("_", 4)
            if len(end_parts) >= 4:
                end_str = "_".join(end_parts[:4])
            else:
                end_str = None
            
            left_html = esc(left)
            right_html = esc(right)
            
            # 高亮第一张的开始时间（绿色）
            if is_first and start_str:
                left_html = left_html.replace(esc(start_str), f'<span {GREEN}>{esc(start_str)}</span>', 1)
            
            # 高亮最后一张的结束时间（红色）
            if is_last and end_str:
                right_html = right_html.replace(esc(end_str), f'<span {RED}>{esc(end_str)}</span>', 1)
            
            return f"{left_html}__{right_html}{esc(ext)}"
        
        # 构建预览列表（最多显示10个）
        preview_items = []
        for i, path in enumerate(sel_list[:10]):
            fn = os.path.basename(path)
            preview_items.append(f"- {line_with_highlight(fn, is_first=(i == 0), is_last=(i == len(sel_list)-1))}")
        if len(sel_list) > 10:
            preview_items.append("...")
        
        # === 提前计算新文件名（用于显示） ===
        # 1) 找到最早的开始时间
        earliest_ms = None
        earliest_start_str = None
        for path in sel_list:
            fname = os.path.basename(path)
            ms, start_str = self._parse_start_time(fname)
            if earliest_ms is None or ms < earliest_ms:
                earliest_ms = ms
                earliest_start_str = start_str
        
        # 2) 找到最晚的结束时间
        latest_end_ms = -1
        latest_end_str = None
        for path in sel_list:
            fname = os.path.basename(path)
            end_str = self._extract_end_str(fname)
            h, m, s, ms = map(int, end_str.split("_"))
            cur_ms = h*3600000 + m*60000 + s*1000 + ms
            if cur_ms > latest_end_ms:
                latest_end_ms = cur_ms
                latest_end_str = end_str
        
        # 3) 提取目标文件的后缀部分
        target_name = os.path.basename(self.merge_target)
        target_ext = os.path.splitext(target_name)[1]
        end_and_suffix = self._extract_end_and_suffix(target_name)
        end_parts = end_and_suffix.split("_", 4)
        if len(end_parts) >= 4:
            target_suffix_rest = end_and_suffix[len("_".join(end_parts[:4])):]
        else:
            target_suffix_rest = ""
        
        # 构建目标文件的显示（高亮旧的结束时间）
        def target_with_old_end_red(fn: str) -> str:
            name_no_ext, ext = os.path.splitext(fn)
            if "__" not in name_no_ext:
                return esc(fn)
            left, right = name_no_ext.split("__", 1)
            end_parts = right.split("_", 4)
            if len(end_parts) >= 4:
                end_str = "_".join(end_parts[:4])
                right_html = esc(right).replace(esc(end_str), f'<span {RED}>{esc(end_str)}</span>', 1)
            else:
                right_html = esc(right)
            return f"{esc(left)}__{right_html}{esc(ext)}"
        
        # 构建新文件名的显示（绿色开始时间 + 红色结束时间）
        def new_name_with_colors(start_str: str, end_str: str, suffix_rest: str, ext: str) -> str:
            start_html = f'<span {GREEN}>{esc(start_str)}</span>'
            end_html = f'<span {RED}>{esc(end_str)}</span>'
            return f"{start_html}__{end_html}{esc(suffix_rest)}{esc(ext)}"
        
        # 计算动态剩余张数
        total_cnt = len(self.image_list)
        will_delete_cnt = max(0, len(sel_list) - 1)
        remain_cnt = max(0, total_cnt - will_delete_cnt)
        
        # 构建HTML内容
        html = []
        html.append(f"<div>将要合并 {len(sel_list)} 张图片：</div>")
        html.append("<div style='margin-top:4px; font-family: Consolas, monospace;'>")
        html.append("<br/>".join(preview_items))
        html.append("</div>")
        html.append("<div style='margin-top:8px;'>保留并重命名：</div>")
        html.append("<div style='margin-top:4px; font-family: Consolas, monospace;'>")
        html.append(f"{target_with_old_end_red(target_file)}")
        html.append("<br/>")
        html.append(f"→ {new_name_with_colors(earliest_start_str, latest_end_str, target_suffix_rest, target_ext)}")
        html.append("</div>")
        html.append(f"<div style='margin-top:8px;font-weight:bold;'>动态剩余张数：{remain_cnt}（总计 {total_cnt} - 删除 {will_delete_cnt}）</div>")
        html.append("<div style='margin-top:8px;'>其余将被删除。<br/>是否继续？</div>")
        full_html = "<div style='font-size:13px; line-height:1.38;'>" + "".join(html) + "</div>"
        
        # 创建消息框（使用自定义类支持空格键）
        box = SpaceConfirmMessageBox(self)
        box.setWindowTitle("确认合并")
        box.setIcon(QtWidgets.QMessageBox.Question)
        box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        box.setDefaultButton(QtWidgets.QMessageBox.Yes)
        
        # 添加富文本标签
        label = QtWidgets.QLabel(full_html)
        label.setTextFormat(Qt.RichText)
        label.setOpenExternalLinks(False)
        label.setWordWrap(True)
        label.setMinimumWidth(520)
        label.setFocusPolicy(Qt.NoFocus)  # 标签不接受焦点
        box.layout().addWidget(label, 0, 1)
        
        ret = box.exec_()
        
        if ret != QtWidgets.QMessageBox.Yes:
            return
        
        # 解析文件名并计算新文件名
        try:
            # 1) 找到最早的开始时间（从所有选中的图片中）
            earliest_ms = None
            earliest_start_str = None
            for path in self.selected_images:
                fname = os.path.basename(path)  # 提取文件名
                ms, start_str = self._parse_start_time(fname)
                if earliest_ms is None or ms < earliest_ms:
                    earliest_ms = ms
                    earliest_start_str = start_str
            
            if earliest_start_str is None:
                QtWidgets.QMessageBox.warning(self, "错误", "未能解析起始时间！")
                return
            
            # 2) 找到最晚的结束时间（从所有选中的图片中）
            latest_end_ms = -1
            latest_end_str = None
            for path in self.selected_images:
                fname = os.path.basename(path)  # 提取文件名
                end_str = self._extract_end_str(fname)
                h, m, s, ms = map(int, end_str.split("_"))
                cur_ms = h*3600000 + m*60000 + s*1000 + ms
                if cur_ms > latest_end_ms:
                    latest_end_ms = cur_ms
                    latest_end_str = end_str
            
            if latest_end_str is None:
                QtWidgets.QMessageBox.warning(self, "错误", "未能解析结束时间！")
                return
            
            # 3) 构建新文件名
            target_name = os.path.basename(self.merge_target)
            target_ext = os.path.splitext(target_name)[1]
            end_and_suffix = self._extract_end_and_suffix(target_name)
            
            # 拆出保留目标的结束时间与"之后的后缀"
            end_parts = end_and_suffix.split("_", 4)
            if len(end_parts) >= 4:
                target_end_str = "_".join(end_parts[:4])
                target_suffix_rest = end_and_suffix[len(target_end_str):]
            else:
                target_end_str = end_and_suffix
                target_suffix_rest = ""
            
            new_name = f"{earliest_start_str}__{latest_end_str}{target_suffix_rest}{target_ext}"
            
            # 检查文件名冲突
            target_img_path = self.merge_target
            new_path = os.path.join(os.path.dirname(target_img_path), new_name)
            if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(target_img_path):
                reply2 = QtWidgets.QMessageBox.question(
                    self, '文件已存在',
                    f'目标文件名已存在：\n{new_name}\n是否覆盖？\n（选择"否"将取消本次操作）',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if reply2 != QtWidgets.QMessageBox.Yes:
                    return
            
            # 执行合并操作
            delete_list = [path for path in self.selected_images if path != self.merge_target]
            self._run_merge_operation(target_img_path, new_path, delete_list, target_name, new_name)
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"合并失败：{str(e)}")
    
    def _parse_start_time(self, filename):
        """从文件名解析起始时间段，返回（毫秒总数, 起始段字符串）"""
        name_no_ext, _ = os.path.splitext(filename)
        if "__" not in name_no_ext:
            raise ValueError("缺少分隔符 '__'")
        start = name_no_ext.split("__", 1)[0]
        parts = start.split("_")
        if len(parts) != 4:
            raise ValueError("起始时间应为 4 段：H_MM_SS_mmm")
        h, m, s, ms = map(int, parts)
        total_ms = h*3600000 + m*60000 + s*1000 + ms
        return total_ms, start
    
    def _extract_end_and_suffix(self, filename):
        """提取右侧"结束时间+后缀（不含扩展名）"部分"""
        name_no_ext, _ = os.path.splitext(filename)
        if "__" not in name_no_ext:
            raise ValueError("缺少分隔符 '__'")
        return name_no_ext.split("__", 1)[1]
    
    def _extract_start_str(self, filename):
        """提取左侧起始时间字符串 H_MM_SS_mmm"""
        name_no_ext, _ = os.path.splitext(filename)
        left = name_no_ext.split("__", 1)[0]
        return "_".join(left.split("_")[:4])
    
    def _extract_end_str(self, filename):
        """提取右侧结束时间字符串 H_MM_SS_mmm"""
        right = self._extract_end_and_suffix(filename)
        parts = right.split("_", 4)
        return "_".join(parts[:4]) if len(parts) >= 4 else right
    
    def _run_merge_operation(self, target_path, new_path, delete_list, target_name, new_name):
        """执行合并操作：重命名目标文件，移动其他文件到_delete_文件夹"""
        import shutil
        try:
            # 1) 重命名目标文件
            if os.path.abspath(target_path) != os.path.abspath(new_path):
                os.replace(target_path, new_path)
                # 同时重命名JSON文件
                target_json = os.path.splitext(target_path)[0] + ".json"
                new_json = os.path.splitext(new_path)[0] + ".json"
                if os.path.exists(target_json):
                    os.replace(target_json, new_json)
            
            # 2) 移动其他文件到_delete_文件夹
            image_path = os.path.dirname(target_path)
            delete_folder = os.path.join(image_path, "..", "_delete_")
            os.makedirs(delete_folder, exist_ok=True)
            
            deleted = []
            failed = []
            for path in delete_list:
                try:
                    if os.path.exists(path):
                        image_name = os.path.basename(path)
                        save_file = os.path.join(delete_folder, image_name)
                        shutil.move(path, save_file)
                        deleted.append(path)
                        # 同时移动JSON文件
                        json_path = os.path.splitext(path)[0] + ".json"
                        if os.path.exists(json_path):
                            json_name = os.path.basename(json_path)
                            json_save_file = os.path.join(delete_folder, json_name)
                            shutil.move(json_path, json_save_file)
                except Exception as e:
                    failed.append((path, str(e)))
            
            # 3) 更新界面
            self._post_merge_update(target_path, new_path, deleted, target_name, new_name)
            
            # 发出文件列表变化信号，通知主窗口刷新
            self.files_changed.emit()
            
            # 静默完成，不弹出提示框
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"合并失败：{str(e)}")
    
    def _post_merge_update(self, old_path, new_path, deleted_list, old_name, new_name):
        """合并完成后更新界面"""
        # 更新image_list
        new_image_list = []
        for path in self.image_list:
            if path == old_path:
                new_image_list.append(new_path)
            elif path not in deleted_list:
                new_image_list.append(path)
        
        # 清空选择状态
        self.selected_images.clear()
        self.merge_target = None
        self._last_selected_index = None
        
        # 重新加载图片列表
        self.update_image_list(new_image_list, new_path)
        
        # 更新统计信息
        self.update_merge_stats()
    
    def delete_marked_images(self):
        """删除标记的图片（移动到_delete_文件夹）"""
        
        if not self.deletion_list:
            QtWidgets.QMessageBox.warning(self, "警告", "没有标记要删除的图片！")
            return
        
        # 构建预览列表（最多显示10个）
        preview_list = [os.path.basename(path) for path in self.deletion_list[:10]]
        preview = '\n'.join(preview_list)
        
        # 计算动态剩余张数
        total_cnt = len(self.image_list)
        will_delete_cnt = len(self.deletion_list)
        remain_cnt = max(0, total_cnt - will_delete_cnt)
        
        msg = f'确定要删除 {len(self.deletion_list)} 张图片吗？\n\n{preview}'
        if len(self.deletion_list) > 10:
            msg += '\n...'
        msg += f'\n\n动态剩余张数：{remain_cnt}（总计 {total_cnt} - 删除 {will_delete_cnt}）'
        msg += '\n\n图片将移动到 _delete_ 文件夹！'
        
        # 使用自定义消息框（支持空格键）
        msg_box = SpaceConfirmMessageBox(self)
        msg_box.setWindowTitle("确认删除")
        msg_box.setIcon(QtWidgets.QMessageBox.Question)
        msg_box.setText(msg)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg_box.setDefaultButton(QtWidgets.QMessageBox.Yes)
        
        reply = msg_box.exec_()
        
        if reply != QtWidgets.QMessageBox.Yes:
            return
        
        # 执行删除操作（移动到_delete_文件夹）
        import shutil
        try:
            # 创建_delete_文件夹
            if self.deletion_list:
                first_path = self.deletion_list[0]
                image_path = os.path.dirname(first_path)
                delete_folder = os.path.join(image_path, "..", "_delete_")
                os.makedirs(delete_folder, exist_ok=True)
            
            deleted = []
            failed = []
            
            for path in self.deletion_list:
                try:
                    if os.path.exists(path):
                        image_name = os.path.basename(path)
                        save_file = os.path.join(delete_folder, image_name)
                        shutil.move(path, save_file)
                        deleted.append(path)
                        # 同时移动JSON文件
                        json_path = os.path.splitext(path)[0] + ".json"
                        if os.path.exists(json_path):
                            json_name = os.path.basename(json_path)
                            json_save_file = os.path.join(delete_folder, json_name)
                            shutil.move(json_path, json_save_file)
                except Exception as e:
                    failed.append((path, str(e)))
            
            # 更新界面
            self._post_delete_update(deleted)
            
            # 发出文件列表变化信号，通知主窗口刷新
            self.files_changed.emit()
            
            # 静默完成，不弹出提示框
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"删除失败：{str(e)}")
    
    def _post_delete_update(self, deleted_list):
        """删除完成后更新界面"""
        # 更新image_list
        new_image_list = [path for path in self.image_list if path not in deleted_list]
        
        # 清空删除列表
        self.deletion_list.clear()
        self._last_selected_index = None
        
        # 重新加载图片列表
        current_file = self.current_filename if self.current_filename not in deleted_list else None
        self.update_image_list(new_image_list, current_file)
        
        # 更新统计信息
        self.update_merge_stats()
    
    def clear_merge_selection(self):
        """清除所有选择"""
        
        self.selected_images.clear()
        self.deletion_list.clear()
        self.merge_target = None
        self._last_selected_index = None
        
        cleared_count = 0
        for item in self.masonry_widget.items:
            if item.is_selected or item.is_marked_delete or item.is_merge_target:
                cleared_count += 1
            item.is_selected = False
            item.is_marked_delete = False
            item.is_merge_target = False
            item.status_icon.hide()  # 隐藏状态图标
            item.update()
        
        self.update_merge_stats()
    
    def update_multi_selection(self):
        """更新普通模式的多选列表"""
        self.multi_selected_items.clear()
        for item in self.masonry_widget.items:
            if item.is_multi_selected:
                self.multi_selected_items.append(item)
        
        # 更新多选统计标签
        count = len(self.multi_selected_items)
        if count > 0:
            self.multi_select_label.setText(f"已选中: {count}")
            self.multi_select_label.setStyleSheet("color: #00E676; font-weight: bold; font-size: 12px; padding-left: 15px;")  # 亮绿色
        else:
            self.multi_select_label.setText("已选中: 0")
            self.multi_select_label.setStyleSheet("color: #666; font-size: 12px; padding-left: 15px;")
        
        # 更新已编辑统计
        self.update_edited_count()
    
    def clear_all_clicked_states(self):
        """清除所有图片的单击状态"""
        for item in self.masonry_widget.items:
            if item.is_clicked:
                item.is_clicked = False
                item.stop_rainbow_animation()
                item.update()
    
    def update_edited_count(self):
        """更新已编辑统计标签"""
        edited_count = sum(1 for item in self.masonry_widget.items if item.is_manually_edited)
        
        if edited_count > 0:
            self.edited_count_label.setText(f"已编辑: {edited_count}")
            self.edited_count_label.setStyleSheet("color: #FFA500; font-weight: bold; font-size: 12px; padding-left: 15px;")  # 橙色
        else:
            self.edited_count_label.setText("已编辑: 0")
            self.edited_count_label.setStyleSheet("color: #666; font-size: 12px; padding-left: 15px;")
    
    def batch_toggle_edited(self):
        """批量切换已编辑状态"""
        if not self.multi_selected_items:
            return
        
        # 确定操作：如果所有选中项都已编辑，则取消编辑；否则添加编辑标记
        all_edited = all(item.is_manually_edited for item in self.multi_selected_items)
        
        for item in self.multi_selected_items:
            self.on_toggle_edited(item)  # 使用正确的方法名
    
    def delete_multi_selected(self):
        """删除多选的图片（移动到_delete_文件夹）"""
        if not self.multi_selected_items:
            # 没有多选项，删除当前右键点击的图片
            # 需要找到当前右键点击的item
            for item in self.masonry_widget.items:
                if item.underMouse():
                    to_delete = [item.image_path]
                    break
            else:
                return
        else:
            # 删除所有多选的图片
            to_delete = [item.image_path for item in self.multi_selected_items]
        
        # 直接删除，不需要确认（右键操作不会误操作）
        
        # 执行删除（移动到_delete_文件夹）
        import shutil
        deleted = []
        failed = []
        
        for path in to_delete:
            try:
                if os.path.exists(path):
                    # 创建_delete_文件夹
                    image_path, image_name = os.path.split(path)
                    delete_folder = os.path.join(image_path, "..", "_delete_")
                    os.makedirs(delete_folder, exist_ok=True)
                    
                    # 移动图片文件
                    save_file = os.path.join(delete_folder, image_name)
                    shutil.move(path, save_file)
                    deleted.append(path)
                    
                    # 移动对应的JSON文件
                    json_path = os.path.splitext(path)[0] + ".json"
                    if os.path.exists(json_path):
                        json_name = os.path.basename(json_path)
                        json_save_file = os.path.join(delete_folder, json_name)
                        shutil.move(json_path, json_save_file)
            except Exception as e:
                failed.append((path, str(e)))
        
        # 清空多选状态和图标
        for item in self.multi_selected_items:
            item.is_multi_selected = False
            item.status_icon.hide()
        self.multi_selected_items.clear()
        
        # 更新多选统计标签
        self.multi_select_label.setText("已选中: 0")
        self.multi_select_label.setStyleSheet("color: #666; font-size: 12px; padding-left: 15px;")
        
        # 更新界面
        new_image_list = [p for p in self.image_list if p not in deleted]
        current_file = self.current_filename if self.current_filename not in deleted else None
        self.update_image_list(new_image_list, current_file)
        
        # 发出文件列表变化信号
        self.files_changed.emit()
    
    def update_merge_stats(self):
        """更新统计信息"""
        if hasattr(self, 'merge_stats_label'):
            self.merge_stats_label.setText(
                f"已选: {len(self.selected_images)} | 已标记删除: {len(self.deletion_list)}"
            )
    
    def on_columns_released(self):
        self.columns = self.columns_slider.value()
        self.masonry_widget.columns = self.columns
        self.masonry_widget.schedule_relayout(0)
        # 延迟处理重新加载，避免卡顿
        self._resize_reload_timer.start(500)
        self.save_masonry_settings()
    
    def on_height_released(self):
        """高度滑块释放"""
        self.row_height = self.height_slider.value()
        self.masonry_widget.row_height = self.row_height
        self.masonry_widget.schedule_relayout(0)
        # 延迟处理重新加载，避免卡顿
        self._resize_reload_timer.start(500)
        self.save_masonry_settings()
    
    def set_vertical_mode(self):
        """设置为纵向模式"""
        if not self.horizontal_mode:
            return  # 已经是纵向模式
        
        self.horizontal_mode = False
        self.masonry_widget.horizontal_mode = False
        
        # 更新按钮样式
        self.mode_btn.setStyleSheet("""
            QPushButton { background: #444; color: #fff; border: 1px solid #666; border-radius: 3px; padding: 2px 5px; }
            QPushButton:hover { background: #555; }
        """)
        self.columns_slider.setEnabled(True)
        
        self.height_mode_btn.setStyleSheet("""
            QPushButton { background: #333; color: #888; border: 1px solid #555; border-radius: 3px; padding: 2px 5px; }
            QPushButton:hover { background: #444; }
        """)
        self.height_slider.setEnabled(False)
        
        self.masonry_widget.schedule_relayout(0)
        self._resize_reload_timer.start(300)
        self.save_masonry_settings()
        # 延迟更新标题以确保布局完成
        QtCore.QTimer.singleShot(350, self.update_title_with_position)
    
    def set_horizontal_mode(self):
        """设置为横向模式"""
        if self.horizontal_mode:
            return  # 已经是横向模式
        
        self.horizontal_mode = True
        self.masonry_widget.horizontal_mode = True
        
        # 更新按钮样式
        self.mode_btn.setStyleSheet("""
            QPushButton { background: #333; color: #888; border: 1px solid #555; border-radius: 3px; padding: 2px 5px; }
            QPushButton:hover { background: #444; }
        """)
        self.columns_slider.setEnabled(False)
        
        self.height_mode_btn.setStyleSheet("""
            QPushButton { background: #444; color: #fff; border: 1px solid #666; border-radius: 3px; padding: 2px 5px; }
            QPushButton:hover { background: #555; }
        """)
        self.height_slider.setEnabled(True)
        
        self.masonry_widget.schedule_relayout(0)
        self._resize_reload_timer.start(300)
        self.save_masonry_settings()
        # 延迟更新标题以确保布局完成
        QtCore.QTimer.singleShot(350, self.update_title_with_position)

    def _remove_main_window_shortcuts(self):
        """移除主窗口的W/A/D快捷键"""
        if self.labeling_widget and hasattr(self.labeling_widget, 'actions'):
            # 保存并移除W键快捷键
            if hasattr(self.labeling_widget.actions, 'show_hidden_polygons'):
                action = self.labeling_widget.actions.show_hidden_polygons
                if not hasattr(self, '_original_w_shortcuts'):
                    self._original_w_shortcuts = action.shortcuts()
                action.setShortcuts([])
            
            # 保存并移除A键快捷键
            if hasattr(self.labeling_widget.actions, 'open_prev_image'):
                action = self.labeling_widget.actions.open_prev_image
                if not hasattr(self, '_original_a_shortcuts'):
                    self._original_a_shortcuts = action.shortcuts()
                action.setShortcuts([])
            
            # 保存并移除D键快捷键
            if hasattr(self.labeling_widget.actions, 'open_next_image'):
                action = self.labeling_widget.actions.open_next_image
                if not hasattr(self, '_original_d_shortcuts'):
                    self._original_d_shortcuts = action.shortcuts()
                action.setShortcuts([])
    
    def _restore_main_window_shortcuts(self):
        """恢复主窗口的W/A/D快捷键"""
        if self.labeling_widget and hasattr(self.labeling_widget, 'actions'):
            # 恢复W键快捷键
            if hasattr(self.labeling_widget.actions, 'show_hidden_polygons'):
                shortcuts = getattr(self, '_original_w_shortcuts', [QtGui.QKeySequence('W')])
                self.labeling_widget.actions.show_hidden_polygons.setShortcuts(shortcuts)
            
            # 恢复A键快捷键
            if hasattr(self.labeling_widget.actions, 'open_prev_image'):
                shortcuts = getattr(self, '_original_a_shortcuts', [QtGui.QKeySequence('A')])
                self.labeling_widget.actions.open_prev_image.setShortcuts(shortcuts)
            
            # 恢复D键快捷键
            if hasattr(self.labeling_widget.actions, 'open_next_image'):
                shortcuts = getattr(self, '_original_d_shortcuts', [QtGui.QKeySequence('D')])
                self.labeling_widget.actions.open_next_image.setShortcuts(shortcuts)
    
    def load_settings(self):
        """从配置加载设置"""
        if self.labeling_widget and hasattr(self.labeling_widget, '_config'):
            settings = self.labeling_widget._config.get("masonry_settings", {})
            if settings:
                self.spacing = settings.get("spacing", self.spacing)
                self.border_radius = settings.get("border_radius", self.border_radius)
                self.border_width = settings.get("border_width", self.border_width)
                self.columns = settings.get("columns", self.columns)
                self.row_height = settings.get("row_height", self.row_height)
                self.horizontal_mode = settings.get("horizontal_mode", self.horizontal_mode)
                self.grid_mode = settings.get("grid_mode", self.grid_mode)
                self.show_hover_info = settings.get("show_hover_info", self.show_hover_info)
    
    def _build_cursor(self, path: str, fallback_shape: Qt.CursorShape, hotspot=None) -> QtGui.QCursor:
        """从文件构建自定义光标（失败则回退到系统光标）"""
        try:
            if path and os.path.isfile(path):
                pix = QtGui.QPixmap(path)
                if not pix.isNull():
                    if hotspot is None:
                        hx, hy = pix.width() // 2, pix.height() // 2
                    else:
                        hx, hy = hotspot
                    return QtGui.QCursor(pix, hx, hy)
        except Exception:
            pass
        return QtGui.QCursor(fallback_shape)
    
    def _init_cursors(self):
        """初始化自定义鼠标指针"""
        self.select_cursor = self._build_cursor(SELECT_CURSOR_PATH, Qt.PointingHandCursor, SELECT_CURSOR_HOTSPOT)
        self.delete_cursor = self._build_cursor(DELETE_CURSOR_PATH, Qt.CrossCursor, DELETE_CURSOR_HOTSPOT)
    
    def _apply_background_cursor(self):
        """根据模式为滚动区域设置背景光标"""
        if hasattr(self, 'scroll_area') and self.scroll_area is not None:
            if self.current_merge_sub_mode == 'delete':
                self.scroll_area.viewport().setCursor(self.delete_cursor)
            else:
                self.scroll_area.viewport().setCursor(self.select_cursor)
    
    def _update_items_cursor(self):
        """更新所有图片项的鼠标指针"""
        for item in self.masonry_widget.items:
            item.set_cursors(self.select_cursor, self.delete_cursor)
            item.set_merge_mode_cursor(self.current_merge_sub_mode)

    def save_masonry_settings(self):
        """保存设置到配置"""
        if self.labeling_widget and hasattr(self.labeling_widget, '_config'):
            settings = {
                "spacing": self.spacing,
                "border_radius": self.border_radius,
                "border_width": self.border_width,
                "columns": self.columns,
                "row_height": self.row_height,
                "horizontal_mode": self.horizontal_mode,
                "grid_mode": self.grid_mode,
                "show_hover_info": self.show_hover_info
            }
            self.labeling_widget._config["masonry_settings"] = settings
            try:
                from ....config import save_config
                save_config(self.labeling_widget._config)
            except Exception:
                pass
    
    def scroll_page(self, direction):
        """智能翻页并对齐到图片顶部（direction: 1=下一页, -1=上一页）"""
        if not self.masonry_widget.items:
            return
        
        viewport_height = self.scroll_area.viewport().height()
        scroll_bar = self.scroll_area.verticalScrollBar()
        current_scroll = scroll_bar.value()
        
        # 删合模式：按一屏高度翻页（快速浏览多张图）
        if self.merge_mode:
            # 计算目标滚动位置（当前位置 + 一屏高度）
            target_scroll = current_scroll + (viewport_height * direction)
            
            # 限制在有效范围内
            max_value = scroll_bar.maximum()
            target_scroll = max(0, min(target_scroll, max_value))
            
            # 找到目标位置附近最近的图片顶部
            closest_item_top = None
            min_distance = float('inf')
            
            for item in self.masonry_widget.items:
                item_top = item.y()
                
                # 向下翻页：找目标位置之后最近的图片顶部
                if direction > 0:
                    if item_top >= target_scroll:
                        distance = item_top - target_scroll
                        if distance < min_distance:
                            min_distance = distance
                            closest_item_top = item_top
                # 向上翻页：找目标位置之前最近的图片顶部
                else:
                    if item_top <= target_scroll:
                        distance = target_scroll - item_top
                        if distance < min_distance:
                            min_distance = distance
                            closest_item_top = item_top
            
            # 如果找到了对齐的图片，滚动到该位置
            if closest_item_top is not None:
                final_scroll = closest_item_top
            else:
                final_scroll = target_scroll
        else:
            # 普通模式（瀑布流或方格子）：找第一张部分可见的图片，对齐到顶部
            visible_top = current_scroll
            visible_bottom = visible_top + viewport_height
            
            if direction > 0:
                # 向下翻页：找第一张顶部在可见区域下方的图片
                target_item_top = None
                
                # 检查当前是否已经对齐到某张图片的顶部
                current_aligned = False
                for item in self.masonry_widget.items:
                    item_top = item.y()
                    # 如果当前滚动位置已经对齐到某张图片（容差10像素）
                    if abs(item_top - visible_top) <= 10:
                        current_aligned = True
                        # 找下一张图片
                        for next_item in self.masonry_widget.items:
                            next_top = next_item.y()
                            if next_top > item_top + 10:
                                target_item_top = next_top
                                break
                        break
                
                # 如果当前没有对齐到任何图片，找第一张顶部在下方的图片
                if not current_aligned:
                    for item in self.masonry_widget.items:
                        item_top = item.y()
                        if item_top > visible_top + 5:
                            target_item_top = item_top
                            break
                
                if target_item_top is not None:
                    final_scroll = target_item_top
                else:
                    # 如果没有找到，说明已经到底了
                    final_scroll = scroll_bar.maximum()
            else:
                # 向上翻页：找最后一张顶部在当前可见区域顶部之前的图片
                target_item_top = None
                
                # 检查当前是否已经对齐到某张图片的顶部
                current_aligned = False
                for item in self.masonry_widget.items:
                    item_top = item.y()
                    # 如果当前滚动位置已经对齐到某张图片（容差10像素）
                    if abs(item_top - visible_top) <= 10:
                        current_aligned = True
                        # 找上一张图片
                        for prev_item in reversed(self.masonry_widget.items):
                            prev_top = prev_item.y()
                            if prev_top < item_top - 10:
                                target_item_top = prev_top
                                break
                        break
                
                # 如果当前没有对齐到任何图片，找最后一张顶部在上方的图片
                if not current_aligned:
                    for item in reversed(self.masonry_widget.items):
                        item_top = item.y()
                        if item_top < visible_top - 5:
                            target_item_top = item_top
                            break
                
                if target_item_top is not None:
                    final_scroll = target_item_top
                else:
                    # 如果没有找到，说明已经到顶了
                    final_scroll = 0
        
        # 限制在有效范围内
        max_value = scroll_bar.maximum()
        final_scroll = max(0, min(final_scroll, max_value))
        
        scroll_bar.setValue(int(final_scroll))
    
    def on_masonry_resized(self):
        """瀑布流容器大小变化"""
        # 延迟处理重新加载队列
        self._resize_reload_timer.start(300)
    
    def update_image_list(self, new_image_list, current_filename=None):
        """更新图片列表"""
        self.image_list = new_image_list
        if current_filename:
            self.current_filename = current_filename
        
        self.masonry_widget.clear_items()
        self.items_map.clear()
        self.loaded_count = 0
        self.reload_queue.clear()
        
        self.create_thumbnail_items()
        self.start_loading()
        
        # 重置滚动位置到顶部
        if hasattr(self, 'scroll_area') and self.scroll_area is not None:
            self.scroll_area.verticalScrollBar().setValue(0)
        
        # 如果处于删合模式，重新应用鼠标指针
        if self.merge_mode:
            self._apply_background_cursor()
            self._update_items_cursor()
    
    def update_edited_color(self):
        """更新手动编辑颜色（当颜色管理器修改颜色时调用）"""
        new_color = self._get_manually_edited_color().name()
        for item in self.masonry_widget.items:
            item.set_edited_color(new_color)
    
    def update_difficult_color(self):
        """更新困难标记颜色（当红绿灯设置修改颜色时调用）"""
        new_color = self._get_difficult_color().name()
        for item in self.masonry_widget.items:
            item.set_difficult_color(new_color)
    
    def closeEvent(self, event):
        if hasattr(self, 'load_timer'):
            self.load_timer.stop()
        self.thread_pool.clear()
        
        # 关闭窗口时恢复主窗口的快捷键
        self._restore_main_window_shortcuts()
        
        super().closeEvent(event)
    
    def toggle_toolbar(self):
        """切换工具栏显示/隐藏"""
        if self.toolbar.isVisible():
            self.toolbar.hide()
        else:
            self.toolbar.show()
    
    def toggle_fullscreen(self):
        """切换全屏模式"""
        if self.isFullScreen():
            # 退出全屏
            self.showNormal()
            # 恢复最大化状态（如果之前是最大化的）
            if hasattr(self, '_was_maximized') and self._was_maximized:
                self.showMaximized()
        else:
            # 进入全屏前记录是否是最大化状态
            self._was_maximized = self.isMaximized()
            self.showFullScreen()
    
    def update_title_with_position(self):
        """更新窗口标题，显示当前完全可见的最后一张图片序号"""
        if not self.masonry_widget.items:
            self.setWindowTitle("瀑布流缩略图")
            return
        
        # 获取滚动区域的可见范围
        scroll_value = self.scroll_area.verticalScrollBar().value()
        viewport_height = self.scroll_area.viewport().height()
        visible_bottom = scroll_value + viewport_height
        
        # 找到最后一张完全可见的图片
        last_visible_index = 0
        for i, item in enumerate(self.masonry_widget.items):
            item_top = item.y()
            item_bottom = item.y() + item.height()
            
            # 图片必须完全在可见区域内：顶部和底部都要在可见范围内
            if item_top >= scroll_value and item_bottom <= visible_bottom:
                last_visible_index = i
            elif item_bottom > visible_bottom:
                # 图片底部超出可见区域，停止查找
                break
        
        # 更新标题：显示 "序号/总数"
        current_num = last_visible_index + 1  # 从1开始计数
        total_num = len(self.masonry_widget.items)
        self.setWindowTitle(f"瀑布流缩略图 - {current_num}/{total_num}")
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            items = [i.toLocalFile() for i in event.mimeData().urls()]
            # 获取支持的图片格式
            extensions = [
                f".{fmt.data().decode().lower()}"
                for fmt in QtGui.QImageReader.supportedImageFormats()
            ]
            # 接受文件夹或图片文件的拖放
            if any(os.path.isdir(i) or i.lower().endswith(tuple(extensions)) for i in items):
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """拖放事件"""
        if not self.labeling_widget:
            event.ignore()
            return
        
        items = [i.toLocalFile() for i in event.mimeData().urls()]
        
        # 检查是否有文件夹被拖放
        folders = [i for i in items if os.path.isdir(i)]
        if folders:
            # 如果拖放了文件夹，通知主窗口打开第一个文件夹
            folder_path = folders[0]
            # 获取主窗口的递归加载设置
            recursive = False
            if hasattr(self.labeling_widget, '_config'):
                recursive = self.labeling_widget._config.get("load_subfolders", False)
            
            # 调用主窗口的import_image_folder方法
            if hasattr(self.labeling_widget, 'import_image_folder'):
                self.labeling_widget.import_image_folder(folder_path, recursive=recursive)
                event.accept()
            else:
                event.ignore()
            return
        
        # 检查是否有图片文件被拖放
        extensions = [
            f".{fmt.data().decode().lower()}"
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]
        image_files = [i for i in items if i.lower().endswith(tuple(extensions))]
        if image_files:
            # 取第一个图片文件，打开其所在文件夹
            first_image = image_files[0]
            folder_path = os.path.dirname(first_image)
            # 获取主窗口的递归加载设置
            recursive = False
            if hasattr(self.labeling_widget, '_config'):
                recursive = self.labeling_widget._config.get("load_subfolders", False)
            
            # 调用主窗口的import_image_folder方法
            if hasattr(self.labeling_widget, 'import_image_folder'):
                self.labeling_widget.import_image_folder(folder_path, recursive=recursive)
                # 加载完文件夹后，定位到拖放的图片
                # 使用延迟调用，确保文件夹加载完成
                QtCore.QTimer.singleShot(100, lambda: self._load_dropped_image(first_image))
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def _load_dropped_image(self, image_path):
        """加载拖放的图片（延迟调用）"""
        if self.labeling_widget and hasattr(self.labeling_widget, 'load_file'):
            # 检查图片是否在文件列表中
            if hasattr(self.labeling_widget, 'fn_to_index') and image_path in self.labeling_widget.fn_to_index:
                self.labeling_widget.load_file(image_path)
    
    def keyPressEvent(self, event):
        """处理键盘事件"""
        # 如果有模态子窗口，完全不处理键盘事件，让事件传递给模态窗口
        if QtWidgets.QApplication.activeModalWidget():
            super().keyPressEvent(event)
            return
        
        key = event.key()
        modifiers = event.modifiers()
        
        # F11键：切换全屏（不分模式，全局快捷键）
        if key == Qt.Key_F11:
            self.toggle_fullscreen()
            event.accept()
            return
        
        if not self.merge_mode:
            # 非删合模式下的快捷键处理
            
            # W键：清除所有多选
            if key == Qt.Key_W:
                if self.multi_selected_items:
                    for item in self.multi_selected_items:
                        item.is_multi_selected = False
                        item.status_icon.hide()
                        item.update()
                    self.multi_selected_items.clear()
                    self.multi_select_label.setText("已选中: 0")
                    self.multi_select_label.setStyleSheet("color: #666; font-size: 12px; padding-left: 15px;")
                    event.accept()
                    return
            
            # A键：上一页
            elif key == Qt.Key_A:
                self.scroll_page(-1)
                event.accept()
                return
            
            # D键：下一页
            elif key == Qt.Key_D:
                self.scroll_page(1)
                event.accept()
                return
            
            # 其他键使用默认处理
            super().keyPressEvent(event)
            return
        
        # 删合模式下的快捷键处理
        
        # Q键：切换选择/删除模式
        if key == Qt.Key_Q:
            if self.current_merge_sub_mode == 'select':
                self.switch_merge_sub_mode('delete')
            else:
                self.switch_merge_sub_mode('select')
            event.accept()
            return
        
        # W键：清除选择
        elif key == Qt.Key_W:
            self.clear_merge_selection()
            event.accept()
            return
        
        # E键或Enter键：执行操作
        elif key in (Qt.Key_E, Qt.Key_Return, Qt.Key_Enter):
            if self.current_merge_sub_mode == 'select':
                self.merge_selected_images()
            else:
                self.delete_marked_images()
            event.accept()
            return
        
        # A键：上一页
        elif key == Qt.Key_A:
            self.scroll_page(-1)
            event.accept()
            return
        
        # D键：下一页
        elif key == Qt.Key_D:
            self.scroll_page(1)
            event.accept()
            return
        
        # 其他键使用默认处理
        else:
            super().keyPressEvent(event)
