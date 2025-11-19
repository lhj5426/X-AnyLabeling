import os
import csv
import json
import re
import zipfile

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressDialog,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from anylabeling.views.labeling.logger import logger
from anylabeling.views.labeling.utils.qt import new_icon_path
from anylabeling.views.labeling.utils.style import get_progress_dialog_style
from anylabeling.views.labeling.widgets.popup import Popup


overview_dialog_styles = f"""
    QLineEdit {{
        padding: 5px 8px;
        background: white;
        border: 1px solid #d2d2d7;
        border-radius: 6px;
        min-height: 24px;
        selection-background-color: #0071e3;
    }}
    
    QSpinBox {{
        padding: 5px 8px;
        background: white;
        border: 1px solid #d2d2d7;
        border-radius: 6px;
        min-height: 24px;
        selection-background-color: #0071e3;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        width: 20px;
        border: none;
        background: #f0f0f0;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background: #e0e0e0;
    }}
    QSpinBox::up-arrow {{
        image: url({new_icon_path("caret-up", "svg")});
        width: 12px;
        height: 12px;
    }}
    QSpinBox::down-arrow {{
        image: url({new_icon_path("caret-down", "svg")});
        width: 12px;
        height: 12px;
    }}

    .secondary-button {{
        background-color: #f5f5f7;
        color: #1d1d1f;
        border: 1px solid #d2d2d7;
        border-radius: 8px;
        font-weight: 500;
        min-width: 100px;
        height: 36px;
    }}
    .secondary-button:hover {{
        background-color: #e5e5e5;
    }}
    .secondary-button:pressed {{
        background-color: #d5d5d5;
    }}

    .primary-button {{
        background-color: #0071e3;
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 500;
        min-width: 100px;
        height: 36px;
    }}
    .primary-button:hover {{
        background-color: #0077ED;
    }}
    .primary-button:pressed {{
        background-color: #0068D0;
    }}
"""


class OverviewDialog(QtWidgets.QDialog):
    """
    This dialog displays an overview of the label information and shape information for the images in the current project.
    It allows the user to select a range of images to display and export the data as a CSV file.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.supported_shape = parent.supported_shape
        self.image_file_list = self.get_image_file_list()
        self.start_index = 1
        self.end_index = len(self.image_file_list)
        self.showing_label_infos = True
        self.all_shape_infos = []  # 保存所有shape数据用于搜索
        self.displayed_shape_infos = []  # 当前显示的shape数据（用于跳转）
        self.search_text = ""  # 当前搜索文本
        # Shape type translation mapping
        self.shape_type_translation = {
            "polygon": self.tr("多边形"),
            "rectangle": self.tr("矩形"),
            "rectangle3": self.tr("三点矩形"),
            "rotation": self.tr("旋转框"),
            "rotation3": self.tr("三点旋转框"),
            "point": self.tr("点"),
            "line": self.tr("线"),
            "circle": self.tr("圆"),
            "linestrip": self.tr("折线"),
        }
        if self.image_file_list:
            self.init_ui()

    def init_ui(self):
        """
        Initialize the UI components for the overview dialog.
        """
        self.setWindowTitle(self.tr("Overview"))
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )
        self.resize(600, 400)
        self.move_to_center()

        layout = QVBoxLayout(self)
        
        # 添加搜索框（仅在Shape视图显示）
        self.search_layout = QHBoxLayout()
        search_label = QLabel(self.tr("搜索:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("支持正则表达式"))
        self.search_input.textChanged.connect(self.on_search_text_changed)
        
        # 添加清除按钮
        self.clear_search_btn = QPushButton(self.tr("清除"))
        self.clear_search_btn.setProperty("class", "secondary-button")
        self.clear_search_btn.clicked.connect(self.clear_search)
        
        self.search_layout.addWidget(search_label)
        self.search_layout.addWidget(self.search_input)
        self.search_layout.addWidget(self.clear_search_btn)
        self.search_layout.addStretch()
        
        # 创建搜索容器widget，初始隐藏
        self.search_widget = QtWidgets.QWidget()
        self.search_widget.setLayout(self.search_layout)
        self.search_widget.setVisible(False)
        layout.addWidget(self.search_widget)
        
        self.table = QTableWidget(self)
        
        # 连接双击事件
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        
        # 连接单元格选择改变事件（用于方向键导航）
        self.table.currentCellChanged.connect(self.on_current_cell_changed)

        self.populate_table()

        layout.addWidget(self.table)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        # 允许手动调整列宽
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Interactive
        )

        range_layout = QHBoxLayout()
        range_layout.addStretch(1)

        from_label = QLabel(self.tr("从:"))
        self.from_input = QSpinBox()
        self.from_input.setMinimum(1)
        self.from_input.setMaximum(len(self.image_file_list))
        self.from_input.setSingleStep(1)
        self.from_input.setValue(self.start_index)
        self.from_input.setProperty("class", "")
        range_layout.addWidget(from_label)
        range_layout.addWidget(self.from_input)

        to_label = QLabel(self.tr("到:"))
        self.to_input = QSpinBox()
        self.to_input.setMinimum(1)
        self.to_input.setMaximum(len(self.image_file_list))
        self.to_input.setSingleStep(1)
        self.to_input.setValue(len(self.image_file_list))
        self.to_input.setProperty("class", "")
        range_layout.addWidget(to_label)
        range_layout.addWidget(self.to_input)

        self.range_button = QPushButton(self.tr("跳转"))
        self.range_button.setProperty("class", "primary-button")
        range_layout.addWidget(self.range_button)
        self.range_button.clicked.connect(self.update_range)

        range_layout.addStretch(1)

        # Add export button for exporting data
        self.export_button = QPushButton(self.tr("Export"))
        self.export_button.setProperty("class", "secondary-button")

        # Add toggle button to switch between label_infos and shape_infos
        self.toggle_button = QPushButton(self.tr("Shape"))
        self.toggle_button.setProperty("class", "secondary-button")
        self.toggle_button.clicked.connect(self.toggle_info)

        range_and_export_layout = QHBoxLayout()
        range_and_export_layout.addWidget(self.toggle_button, 0, Qt.AlignLeft)
        range_and_export_layout.addStretch(1)
        range_and_export_layout.addLayout(range_layout)
        range_and_export_layout.addStretch(1)
        range_and_export_layout.addWidget(self.export_button, 0, Qt.AlignRight)

        layout.addLayout(range_and_export_layout)

        self.export_button.clicked.connect(self.export_to_csv)

        self.setStyleSheet(overview_dialog_styles)

        self.show()

    def move_to_center(self):
        """
        Move the dialog to the center of the screen.
        """
        qr = self.frameGeometry()
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def get_image_file_list(self):
        """
        Get the list of image files in the current project.
        """
        image_file_list = []
        count = self.parent.file_list_widget.count()
        for c in range(count):
            image_file = self.parent.file_list_widget.item(c).text()
            image_file_list.append(image_file)
        return image_file_list

    def get_label_infos(self, start_index: int = -1, end_index: int = -1):
        """
        Get the label information for the images in the current project.
        """
        initial_nums = [0 for _ in range(len(self.supported_shape))]
        label_infos = {}
        shape_infos = []

        progress_dialog = QProgressDialog(
            self.tr("Loading..."),
            self.tr("Cancel"),
            0,
            len(self.image_file_list),
            self,
        )
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setWindowTitle(self.tr("Progress"))
        progress_dialog.setMinimumWidth(400)
        progress_dialog.setMinimumHeight(150)
        progress_dialog.setStyleSheet(
            get_progress_dialog_style(color="#1d1d1f", height=20)
        )

        if start_index == -1:
            start_index = self.start_index
        if end_index == -1:
            end_index = self.end_index
        for i, image_file in enumerate(self.image_file_list):
            if i < start_index - 1 or i > end_index - 1:
                continue
            label_dir, filename = os.path.split(image_file)
            if self.parent.output_dir:
                label_dir = self.parent.output_dir
            label_file = os.path.join(
                label_dir, os.path.splitext(filename)[0] + ".json"
            )
            if not os.path.exists(label_file):
                continue
            with open(label_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            filename = data["imagePath"]
            shapes = data.get("shapes", [])
            for shape in shapes:
                if "label" not in shape or "shape_type" not in shape:
                    continue
                shape_type = shape["shape_type"]
                if shape_type not in self.supported_shape:
                    logger.warning(
                        f"Invalid shape_type {shape_type} of {label_file}!"
                    )
                    continue
                label = shape["label"]
                score = shape.get("score", 0.0)
                flags = shape.get("flags", {})
                points = shape.get("points", [])
                group_id = shape.get("group_id", -1)
                difficult = shape.get("difficult", False)
                description = shape.get("description", "")
                kie_linking = shape.get("kie_linking", [])
                if label not in label_infos:
                    label_infos[label] = dict(
                        zip(self.supported_shape, initial_nums)
                    )
                label_infos[label][shape_type] += 1
                current_shape = dict(
                    filename=filename,
                    label=label,
                    score=score,
                    flags=flags,
                    points=points,
                    group_id=group_id,
                    difficult=difficult,
                    shape_type=shape_type,
                    description=description,
                    kie_linking=kie_linking,
                )
                shape_infos.append(current_shape)

            progress_dialog.setValue(i)
            if progress_dialog.wasCanceled():
                break
        progress_dialog.close()

        label_infos = {k: label_infos[k] for k in sorted(label_infos)}
        return label_infos, shape_infos

    def get_total_infos(self, start_index: int = -1, end_index: int = -1):
        """
        Get the total information for the images in the current project.
        """
        label_infos, shape_infos = self.get_label_infos(start_index, end_index)
        # Translate shape type names
        translated_shapes = [
            self.shape_type_translation.get(shape, shape)
            for shape in self.supported_shape
        ]
        total_infos = [[self.tr("标签")] + translated_shapes + [self.tr("总计")]]
        shape_counter = [0 for _ in range(len(self.supported_shape) + 1)]

        for label, infos in label_infos.items():
            counter = [
                infos[shape_type] for shape_type in self.supported_shape
            ]
            counter.append(sum(counter))
            row = [label] + counter
            total_infos.append(row)
            shape_counter = [x + y for x, y in zip(counter, shape_counter)]

        total_infos.append([self.tr("总计")] + shape_counter)
        return total_infos, shape_infos

    def get_shape_infos_table(self, shape_infos):
        """
        Get the shape information table for the images in the current project.
        """
        headers = [
            self.tr("文件名"),
            self.tr("标签"),
            self.tr("类型"),
            self.tr("关联"),
            self.tr("组ID"),
            self.tr("困难"),
            self.tr("描述"),
            self.tr("标记"),
            self.tr("坐标点"),
        ]
        table_data = []
        for shape in shape_infos:
            row = [
                shape["filename"],
                shape["label"],
                shape["shape_type"],
                str(shape["kie_linking"]),
                str(shape["group_id"]),
                str(shape["difficult"]),
                shape["description"],
                str(shape["flags"]),
                str(shape["points"]),
            ]
            table_data.append(row)
        return headers, table_data

    def populate_table(self, start_index: int = -1, end_index: int = -1):
        """
        Populate the table with the label or shape information.
        """
        if self.showing_label_infos:
            total_infos, _ = self.get_total_infos(start_index, end_index)
            rows = len(total_infos) - 1
            cols = len(total_infos[0])
            self.table.setRowCount(rows)
            self.table.setColumnCount(cols)
            self.table.setHorizontalHeaderLabels(total_infos[0])

            data = [list(map(str, info)) for info in total_infos[1:]]

            for row, info in enumerate(data):
                for col, value in enumerate(info):
                    item = QTableWidgetItem(value)
                    # 第一列（标签列）左对齐，其他列居中
                    if col > 0:
                        item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row, col, item)
            
            # 自适应列宽
            self.table.resizeColumnsToContents()
        else:
            _, shape_infos = self.get_label_infos(start_index, end_index)
            self.all_shape_infos = shape_infos  # 保存完整数据
            
            # 应用搜索过滤
            if self.search_text:
                shape_infos = self.filter_shapes(shape_infos, self.search_text)
            
            # 保存当前显示的shape数据（用于跳转定位）
            self.displayed_shape_infos = shape_infos
            
            headers, table_data = self.get_shape_infos_table(shape_infos)
            self.table.setRowCount(len(table_data))
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)

            for row, data in enumerate(table_data):
                for col, value in enumerate(data):
                    item = QTableWidgetItem(value)
                    item.setToolTip(value)
                    self.table.setItem(row, col, item)
            # 允许手动调整列宽
            self.table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Interactive
            )
            # 自动调整列宽以适应内容
            self.table.resizeColumnsToContents()

    def update_range(self):
        """
        Update the range of images to display in the table.
        """
        from_value = (
            int(self.from_input.text())
            if self.from_input.text()
            else self.start_index
        )
        to_value = (
            int(self.to_input.text())
            if self.to_input.text()
            else self.end_index
        )
        if (
            (from_value > to_value)
            or (from_value < 1)
            or (to_value > len(self.image_file_list))
        ):
            self.from_input.setValue(1)
            self.to_input.setValue(len(self.image_file_list))
            self.populate_table(1, len(self.image_file_list))
        else:
            self.start_index = from_value
            self.end_index = to_value
            self.populate_table()

    def export_to_csv(self):
        """
        Export the label and shape information to a CSV file.
        """
        directory = QFileDialog.getExistingDirectory(
            self, self.tr("Select Directory"), ""
        )
        if not directory:
            return

        try:
            label_infos, shape_infos = self.get_total_infos(
                1, len(self.image_file_list)
            )
            headers, shape_infos_data = self.get_shape_infos_table(shape_infos)

            label_infos_path = os.path.join(directory, "label_infos.csv")
            shape_infos_path = os.path.join(directory, "shape_infos.csv")
            classes_path = os.path.join(directory, "classes.txt")
            zip_path = os.path.join(directory, "export_data.zip")

            # Write label_infos.csv
            with open(
                label_infos_path, "w", newline="", encoding="utf-8"
            ) as csvfile:
                writer = csv.writer(csvfile)
                for row in label_infos:
                    writer.writerow(row)

            # Write shape_infos.csv
            with open(
                shape_infos_path, "w", newline="", encoding="utf-8"
            ) as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                for row in shape_infos_data:
                    writer.writerow(row)

            # Write classes.txt
            classes = [
                row[0] for row in label_infos[1:-1]
            ]  # Exclude header and total
            with open(classes_path, "w", encoding="utf-8") as f:
                f.write("\n".join(classes))

            # Create zip file
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.write(label_infos_path, os.path.basename(label_infos_path))
                zf.write(shape_infos_path, os.path.basename(shape_infos_path))
                zf.write(classes_path, os.path.basename(classes_path))

            # Clean up temporary files
            os.remove(label_infos_path)
            os.remove(shape_infos_path)
            os.remove(classes_path)

            template = self.tr(
                "导出标注成功！\n"
                "结果已保存到：\n"
                "%s"
            )
            message_text = template % zip_path
            popup = Popup(
                message_text,
                self,
                msec=5000,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")

        except Exception as e:
            logger.error(f"Error occurred while exporting file: {e}")

            popup = Popup(
                self.tr(
                    f"Error occurred while exporting annotations statistics file."
                ),
                self.parent,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self.parent)

    def toggle_info(self):
        """
        Toggle the display of label or shape information.
        """
        self.showing_label_infos = not self.showing_label_infos
        if self.showing_label_infos:
            self.toggle_button.setText(self.tr("Shape"))
            self.search_widget.setVisible(False)
        else:
            self.toggle_button.setText(self.tr("Label"))
            self.search_widget.setVisible(True)
        self.populate_table(self.start_index, self.end_index)
    
    def filter_shapes(self, shape_infos, search_text):
        """
        根据搜索文本过滤shape数据，支持正则表达式
        """
        if not search_text:
            return shape_infos
        
        filtered = []
        
        # 尝试编译正则表达式
        try:
            pattern = re.compile(search_text, re.IGNORECASE)
            use_regex = True
        except re.error:
            # 如果不是有效的正则表达式，使用普通文本搜索
            search_text = search_text.lower()
            use_regex = False
        
        for shape in shape_infos:
            # 在所有字段中搜索
            searchable_text = " ".join([
                str(shape.get("filename", "")),
                str(shape.get("label", "")),
                str(shape.get("shape_type", "")),
                str(shape.get("description", "")),
                str(shape.get("group_id", "")),
                str(shape.get("difficult", "")),
                str(shape.get("flags", "")),
            ])
            
            # 使用正则或普通搜索
            if use_regex:
                if pattern.search(searchable_text):
                    filtered.append(shape)
            else:
                if search_text in searchable_text.lower():
                    filtered.append(shape)
        
        return filtered
    
    def on_search_text_changed(self, text):
        """
        搜索文本改变时的处理
        """
        self.search_text = text
        if not self.showing_label_infos:  # 只在Shape视图时搜索
            # 使用已加载的数据进行过滤，无需重新加载
            if self.all_shape_infos:
                filtered_shapes = self.filter_shapes(self.all_shape_infos, text)
                
                # 更新displayed_shape_infos以匹配过滤后的结果
                self.displayed_shape_infos = filtered_shapes
                
                headers, table_data = self.get_shape_infos_table(filtered_shapes)
                self.table.setRowCount(len(table_data))
                self.table.setColumnCount(len(headers))
                self.table.setHorizontalHeaderLabels(headers)

                for row, data in enumerate(table_data):
                    for col, value in enumerate(data):
                        item = QTableWidgetItem(value)
                        item.setToolTip(value)
                        self.table.setItem(row, col, item)
    
    def clear_search(self):
        """
        清除搜索框内容
        """
        self.search_input.clear()
    
    def on_current_cell_changed(self, current_row, current_column, previous_row, previous_column):
        """
        当前单元格改变时（包括方向键导航），自动跳转并选中对应对象
        """
        # 只在Shape视图时支持
        if self.showing_label_infos or current_row < 0:
            return
        
        # 调用跳转逻辑
        self.jump_to_shape(current_row)
    
    def on_cell_double_clicked(self, row, column):
        """
        双击表格单元格时跳转到对应文件和标注对象
        """
        # 只在Shape视图时支持跳转
        if self.showing_label_infos:
            return
        
        self.jump_to_shape(row)
    
    def jump_to_shape(self, row):
        """
        跳转到指定行对应的标注对象
        """
        # 从displayed_shape_infos获取该行对应的原始shape数据
        if row >= len(self.displayed_shape_infos):
            return
        
        shape_info = self.displayed_shape_infos[row]
        filename = shape_info.get("filename", "")
        label_name = shape_info.get("label", "")
        points = shape_info.get("points", [])
        
        # 在父窗口的文件列表中查找并加载该文件
        try:
            # 查找文件在列表中的索引
            file_index = None
            for i in range(self.parent.file_list_widget.count()):
                item = self.parent.file_list_widget.item(i)
                if item and filename in item.text():
                    file_index = i
                    break
            
            if file_index is not None:
                # 检查是否需要切换文件
                current_row = self.parent.file_list_widget.currentRow()
                need_load_file = (current_row != file_index)
                
                if need_load_file:
                    # 需要加载新文件
                    self.parent.file_list_widget.setCurrentRow(file_index)
                
                # 无论是否切换文件，都使用延迟来确保选中操作在文件加载完成后执行
                if label_name and points:
                    from PyQt5.QtCore import QTimer
                    # 如果需要加载文件，延迟时间长一些；否则短一些
                    delay = 300 if need_load_file else 50
                    QTimer.singleShot(delay, lambda: self.select_shape_by_points(label_name, points))
        
        except Exception as e:
            logger.error(f"跳转到文件失败: {e}")
    
    def select_shape_by_points(self, label_name, points):
        """
        根据标签名和坐标点精确选中对象
        points: 原始坐标点列表 [[x1,y1], [x2,y2], ...]
        """
        try:
            # 遍历标签列表，找到匹配的标签和坐标
            found_item = None
            for item in self.parent.label_list:
                if item and item.shape() and item.shape().label == label_name:
                    # 如果提供了坐标点，进行精确匹配
                    if points:
                        shape_points = item.shape().points
                        
                        # 比较坐标点数量
                        if len(points) == len(shape_points):
                            # 比较每个点（允许小的浮点误差）
                            all_match = True
                            for json_point, shape_point in zip(points, shape_points):
                                if abs(json_point[0] - shape_point.x()) > 0.01 or abs(json_point[1] - shape_point.y()) > 0.01:
                                    all_match = False
                                    break
                            
                            if all_match:
                                found_item = item
                                break
                    else:
                        # 没有坐标信息，匹配第一个同标签的对象
                        found_item = item
                        break
            
            if found_item and found_item.shape():
                shape = found_item.shape()
                
                # 清除之前的选择
                self.parent.label_list.clearSelection()
                # 获取item的索引并设置为当前选中
                index = self.parent.label_list.model().indexFromItem(found_item)
                self.parent.label_list.setCurrentIndex(index)
                # 滚动到该项
                self.parent.label_list.scroll_to_item(found_item)
                
                # 在画布上选中该形状（使用select_shapes方法）
                if hasattr(self.parent, 'canvas'):
                    self.parent.canvas.select_shapes([shape])
                    
        except Exception as e:
            logger.error(f"选中对象失败: {e}")
