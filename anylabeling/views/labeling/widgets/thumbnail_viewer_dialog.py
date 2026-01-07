"""瀑布流缩略图查看器 - 性能优化版"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
import os
import json
import time


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
            if orig_size.isValid():
                orig_w = orig_size.width()
                orig_h = orig_size.height()
                
                # 计算缩略图尺寸
                aspect_ratio = orig_h / orig_w
                thumb_width = self.target_width
                thumb_height = int(self.target_width * aspect_ratio)
                
                reader.setScaledSize(QtCore.QSize(thumb_width, thumb_height))
                image = reader.read()
                
                if not image.isNull():
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
        
        self.setFixedSize(thumbnail_width, thumbnail_width)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        
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
            
            # 绘制边框
            if self.is_manually_edited:
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
            
            if self.hovered:
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
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.image_path)
        elif event.button() == Qt.MiddleButton:
            # 中键点击：切换已编辑状态
            self.toggle_edited.emit(self)
    
    def contextMenuEvent(self, event):
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
        
        action = menu.exec_(event.globalPos())
        if action == h_action:
            self.request_horizontal_viewer.emit(self.image_path)
        elif action == v_action:
            self.request_vertical_viewer.emit(self.image_path)


class MasonryWidget(QtWidgets.QWidget):
    """瀑布流容器"""
    
    resized = QtCore.pyqtSignal()  # 大小变化信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.columns = 4
        self.spacing = 10
        self.margin = 10
        self.horizontal_mode = False  # 横向模式
        self.row_height = 200  # 横向模式的行高
        self.grid_mode = False  # 方格子模式
        self.grid_size = 200  # 方格子尺寸
        self._resize_timer = QtCore.QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._do_relayout)
    
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
        total_spacing = (self.columns - 1) * self.spacing
        return max(50, (available_width - total_spacing) // self.columns)
    
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
        
        # 更新所有item的几何尺寸
        for item in self.items:
            item.horizontal_mode = False
            item.keep_aspect = False  # 瀑布流模式不保持比例
            item.update_geometry_only(col_width)
        
        # 按顺序轮流分配到各列（瀑布流，但按序号顺序）
        column_heights = [self.margin] * self.columns
        
        for idx, item in enumerate(self.items):
            # 按顺序分配到列：0,1,2,3,0,1,2,3...
            col = idx % self.columns
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
            
            # 只有非最后一行不足时才补齐误差
            if not (is_last_row and is_incomplete):
                if num_items > 0:
                    total_used = sum(widths) + total_spacing
                    diff = available_width - total_used
                    if diff != 0 and widths:
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
            
            # 只有非最后一行不足时才补齐误差
            if not (is_last_row and is_incomplete):
                if num_items > 0:
                    total_used = sum(widths) + total_spacing
                    diff = available_width - total_used
                    if diff != 0 and widths:
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


class MasonryThumbnailDialog(QtWidgets.QDialog):
    """瀑布流缩略图查看器"""
    
    image_switched = QtCore.pyqtSignal(str)
    open_horizontal_viewer = QtCore.pyqtSignal(str)
    open_vertical_viewer = QtCore.pyqtSignal(str)
    
    def __init__(self, image_list, current_filename=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("瀑布流缩略图")
        self.resize(1200, 800)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowState(Qt.WindowMaximized)  # 默认最大化
        
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
        
        self.loaded_count = 0
        self.load_batch_size = 10
        self.items_map = {}
        self.reload_queue = []  # 需要重新加载的item队列
        
        # 线程池
        self.thread_pool = QtCore.QThreadPool()
        self.thread_pool.setMaxThreadCount(4)
        
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
    
    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)
        
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background-color: #1e1e1e; border: none; }
            QScrollBar:vertical { border: none; background: #2b2b2b; width: 12px; }
            QScrollBar::handle:vertical { background: #666; min-height: 20px; border-radius: 5px; margin: 2px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        
        self.masonry_widget = MasonryWidget()
        self.masonry_widget.setStyleSheet("background-color: #1e1e1e;")
        self.masonry_widget.columns = self.columns
        self.masonry_widget.spacing = self.spacing
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
        layout.addWidget(QtWidgets.QLabel("列距:"))
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
        layout.addWidget(QtWidgets.QLabel("圆角:"))
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
        layout.addWidget(QtWidgets.QLabel("边框:"))
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
        layout.addWidget(QtWidgets.QLabel("列数:"))
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
        self.columns_slider.sliderReleased.connect(self.on_columns_released)
        self.columns_slider.valueChanged.connect(lambda v: self.columns_label.setText(str(v)))
        layout.addWidget(self.columns_slider)
        self.columns_label = QtWidgets.QLabel(str(self.columns))
        self.columns_label.setFixedWidth(25)
        layout.addWidget(self.columns_label)
        
        self._add_sep(layout)
        # 高度（横向模式）
        layout.addWidget(QtWidgets.QLabel("高度:"))
        self.height_mode_btn = QtWidgets.QPushButton("横向")
        self.height_mode_btn.setFixedWidth(40)
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
        self.height_slider.setEnabled(False)  # 默认禁用
        layout.addWidget(self.height_slider)
        self.height_label = QtWidgets.QLabel(str(self.row_height))
        self.height_label.setFixedWidth(30)
        layout.addWidget(self.height_label)
        
        self._add_sep(layout)
        
        # 瀑布流/方格子切换
        self.layout_mode_btn = QtWidgets.QPushButton("瀑布流")
        self.layout_mode_btn.setFixedSize(60, 28)
        self.layout_mode_btn.setStyleSheet("""
            QPushButton { background: #0078d4; color: #fff; border: 1px solid #005a9e; border-radius: 3px; padding: 4px 8px; font-weight: bold; }
            QPushButton:hover { background: #1084d8; }
        """)
        self.layout_mode_btn.clicked.connect(self.toggle_layout_mode)
        layout.addWidget(self.layout_mode_btn)
        
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
            self.masonry_widget.add_item(item)
            self.items_map[path] = item
        
        self.masonry_widget._do_relayout()
    
    def start_loading(self):
        """开始后台加载"""
        self.load_timer = QtCore.QTimer()
        self.load_timer.timeout.connect(self.load_next_batch)
        self.load_timer.start(30)
    
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
            # 处理重新加载队列
            self.process_reload_queue()
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
        self.image_switched.emit(path)
        self.showMinimized()
    
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
        
        # 更新主界面的文件列表颜色
        if self.labeling_widget and hasattr(self.labeling_widget, 'update_file_item_color'):
            self.labeling_widget.update_file_item_color(path, item.is_manually_edited)
    
    def on_spacing_released(self):
        self.spacing = self.spacing_slider.value()
        self.masonry_widget.spacing = self.spacing
        self.masonry_widget.schedule_relayout(0)
    
    def on_radius_released(self):
        self.border_radius = self.radius_slider.value()
        for item in self.masonry_widget.items:
            item.update_radius(self.border_radius)
    
    def on_border_released(self):
        self.border_width = self.border_slider.value()
        for item in self.masonry_widget.items:
            item.set_border_width(self.border_width)
    
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
    
    def on_columns_released(self):
        self.columns = self.columns_slider.value()
        self.masonry_widget.columns = self.columns
        self.masonry_widget.schedule_relayout(0)
        # 延迟处理重新加载，避免卡顿
        self._resize_reload_timer.start(500)
    
    def on_height_released(self):
        """高度滑块释放"""
        self.row_height = self.height_slider.value()
        self.masonry_widget.row_height = self.row_height
        self.masonry_widget.schedule_relayout(0)
        # 延迟处理重新加载，避免卡顿
        self._resize_reload_timer.start(500)
    
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
        super().closeEvent(event)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
