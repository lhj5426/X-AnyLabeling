import os
import csv
import json
import re
import zipfile

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QTimer
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
    QComboBox,
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
    
    QComboBox {{
        padding: 5px 8px;
        background: white;
        border: 1px solid #d2d2d7;
        border-radius: 6px;
        min-height: 24px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox::down-arrow {{
        image: url({new_icon_path("caret-down", "svg")});
        width: 12px;
        height: 12px;
    }}
    QComboBox:hover {{
        border: 1px solid #0071e3;
    }}
    QComboBox QAbstractItemView {{
        background: white;
        border: 1px solid #d2d2d7;
        selection-background-color: #0071e3;
        selection-color: white;
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
    
    .small-button {{
        background-color: #f5f5f7;
        color: #1d1d1f;
        border: 1px solid #d2d2d7;
        border-radius: 8px;
        font-weight: 500;
        min-width: 30px;
        height: 36px;
        padding: 0 5px;
    }}
    .small-button:hover {{
        background-color: #e5e5e5;
    }}
    .small-button:pressed {{
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
        self.search_field = "all"  # 当前搜索字段
        self.saved_rules = []  # 保存的搜索规则
        self.last_selected_rule_index = -1  # 记住最后选择的规则索引
        self.load_saved_rules()  # 加载已保存的规则
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
        self.search_layout = QVBoxLayout()
        self.search_layout.setSpacing(4)  # 减小行间距
        self.search_layout.setContentsMargins(0, 0, 0, 0)  # 去掉边距
        
        # 第一行：过滤条件
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)  # 减小控件间距
        filter_row.setContentsMargins(0, 0, 0, 0)
        
        # 字段选择下拉框 - 固定宽度
        self.field_combo = QComboBox()
        self.field_combo.addItems([
            self.tr("文件名"),
            self.tr("标签"),
            self.tr("描述"),
            self.tr("类型"),
            self.tr("组ID"),
        ])
        self.field_combo.currentIndexChanged.connect(self.on_field_changed)
        self.field_combo.setFixedWidth(100)
        
        # 条件选择下拉框 - 固定宽度
        self.condition_combo = QComboBox()
        self.condition_combo.addItems([
            self.tr("包含"),
            self.tr("等于"),
            self.tr("不包含"),
            self.tr("不等于"),
            self.tr("正则匹配"),
            self.tr("为空"),
            self.tr("不为空"),
        ])
        self.condition_combo.currentIndexChanged.connect(self.on_condition_changed)
        self.condition_combo.setFixedWidth(100)
        
        # 搜索输入框 - 固定宽度以实现精确对齐
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("输入搜索内容后按回车"))
        self.search_input.returnPressed.connect(self.perform_search)  # 按回车键触发搜索
        self.search_input.setFixedWidth(262)
        
        # 添加过滤地址栏按钮（放在第一行）
        self.filter_filelist_btn = QPushButton(self.tr("过滤地址栏"))
        self.filter_filelist_btn.setProperty("class", "primary-button")
        self.filter_filelist_btn.clicked.connect(self.filter_file_list)
        self.filter_filelist_btn.setFixedWidth(100)
        
        filter_row.addWidget(self.field_combo)
        filter_row.addWidget(self.condition_combo)
        filter_row.addWidget(self.search_input)
        filter_row.addWidget(self.filter_filelist_btn)
        filter_row.addStretch()
        
        # 第二行：操作按钮
        action_row = QHBoxLayout()
        action_row.setSpacing(4)  # 减小控件间距
        action_row.setContentsMargins(0, 0, 0, 0)
        
        # 保存当前规则按钮 - 固定宽度
        self.save_rule_btn = QPushButton(self.tr("保存规则"))
        self.save_rule_btn.setProperty("class", "secondary-button")
        self.save_rule_btn.clicked.connect(self.save_current_rule)
        self.save_rule_btn.setFixedWidth(100)
        
        # 已保存规则下拉框 - 固定宽度
        self.saved_rules_combo = QComboBox()
        self.saved_rules_combo.addItem(self.tr("已保存规则"))
        self.saved_rules_combo.currentIndexChanged.connect(self.on_saved_rule_selected)
        self.saved_rules_combo.setFixedWidth(150)
        
        # 删除规则按钮
        self.delete_rule_btn = QPushButton(self.tr("删除"))
        self.delete_rule_btn.setProperty("class", "secondary-button")
        self.delete_rule_btn.clicked.connect(self.delete_saved_rule)
        
        # 添加清除按钮
        self.clear_search_btn = QPushButton(self.tr("清除"))
        self.clear_search_btn.setProperty("class", "secondary-button")
        self.clear_search_btn.clicked.connect(self.clear_search)
        
        # 添加重置按钮（放在第二行）
        self.reset_filelist_btn = QPushButton(self.tr("重置"))
        self.reset_filelist_btn.setProperty("class", "secondary-button")
        self.reset_filelist_btn.clicked.connect(self.reset_file_list)
        
        action_row.addWidget(self.save_rule_btn)
        action_row.addWidget(self.saved_rules_combo)
        action_row.addWidget(self.delete_rule_btn)
        action_row.addWidget(self.clear_search_btn)
        action_row.addWidget(self.reset_filelist_btn)
        action_row.addStretch()
        
        self.search_layout.addLayout(filter_row)
        self.search_layout.addLayout(action_row)
        
        # 创建搜索容器widget，初始隐藏
        self.search_widget = QtWidgets.QWidget()
        self.search_widget.setLayout(self.search_layout)
        self.search_widget.setVisible(False)
        layout.addWidget(self.search_widget)
        
        # 初始化已保存规则下拉框
        self.update_saved_rules_combo()
        
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
            # 注意："为空"和"不为空"条件不需要搜索文本，也要执行过滤
            condition = self.condition_combo.currentText()
            if self.search_text or condition in [self.tr("为空"), self.tr("不为空")]:
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
        根据搜索文本过滤shape数据，支持多种条件和字段选择
        """
        # 获取当前条件
        condition = self.condition_combo.currentText()
        
        # "为空"和"不为空"条件不需要搜索文本
        if condition in [self.tr("为空"), self.tr("不为空")]:
            pass  # 这些条件不需要搜索文本
        elif not search_text:
            return shape_infos
        
        filtered = []
        
        # 字段映射
        field_map = {
            self.tr("文件名"): "filename",
            self.tr("标签"): "label",
            self.tr("描述"): "description",
            self.tr("类型"): "shape_type",
            self.tr("组ID"): "group_id",
        }
        
        current_field_name = self.field_combo.currentText()
        search_field = field_map.get(current_field_name, "filename")
        
        for shape in shape_infos:
            field_value = str(shape.get(search_field, ""))
            match = False
            
            # 根据条件进行匹配
            if condition == self.tr("包含"):
                match = search_text.lower() in field_value.lower()
            elif condition == self.tr("等于"):
                match = search_text.lower() == field_value.lower()
            elif condition == self.tr("不包含"):
                match = search_text.lower() not in field_value.lower()
            elif condition == self.tr("不等于"):
                match = search_text.lower() != field_value.lower()
            elif condition == self.tr("正则匹配"):
                try:
                    pattern = re.compile(search_text, re.IGNORECASE)
                    match = pattern.search(field_value) is not None
                except re.error:
                    # 正则表达式错误，使用普通包含匹配
                    match = search_text.lower() in field_value.lower()
            elif condition == self.tr("为空"):
                # 判断为空：空字符串、"None"字符串、null、或者只有空白字符
                match = (not field_value or 
                        field_value.strip() == "" or 
                        field_value == "None" or
                        field_value == "null" or
                        field_value == "{}")
            elif condition == self.tr("不为空"):
                # 判断不为空：有实际内容的字符串（排除None、null、空字符串等）
                match = (field_value and 
                        field_value.strip() != "" and 
                        field_value != "None" and
                        field_value != "null" and
                        field_value != "{}")
            
            if match:
                filtered.append(shape)
        
        return filtered
    
    def perform_search(self):
        """
        执行搜索（按回车键触发）
        """
        self.search_text = self.search_input.text()
        if not self.showing_label_infos:  # 只在Shape视图时搜索
            # 重新加载指定范围的数据并应用搜索
            self.populate_table(self.start_index, self.end_index)
    
    def clear_search(self):
        """
        清除搜索框内容并恢复显示所有数据
        """
        self.search_input.clear()
        self.field_combo.setCurrentIndex(0)
        self.condition_combo.setCurrentIndex(0)
        self.saved_rules_combo.setCurrentIndex(0)
        self.last_selected_rule_index = -1
        self.search_text = ""
        
        # 重新加载数据，显示所有记录
        if not self.showing_label_infos:
            self.populate_table(self.start_index, self.end_index)
    
    def on_field_changed(self, index):
        """
        字段选择改变时的处理
        """
        # 字段改变时不自动搜索，需要用户按回车
    
    def on_condition_changed(self, index):
        """
        条件选择改变时的处理
        """
        condition = self.condition_combo.currentText()
        
        # "为空"和"不为空"条件不需要输入框
        if condition in [self.tr("为空"), self.tr("不为空")]:
            self.search_input.setEnabled(False)
            self.search_input.setPlaceholderText(self.tr("此条件无需输入，按回车搜索"))
            # 自动执行搜索（因为不需要输入）
            self.perform_search()
        else:
            self.search_input.setEnabled(True)
            self.search_input.setPlaceholderText(self.tr("输入搜索内容后按回车"))
    
    def load_saved_rules(self):
        """
        从配置文件加载已保存的搜索规则
        """
        try:
            config_dir = os.path.join(os.path.expanduser("~"), ".anylabeling")
            os.makedirs(config_dir, exist_ok=True)
            rules_file = os.path.join(config_dir, "overview_search_rules.json")
            
            if os.path.exists(rules_file):
                with open(rules_file, "r", encoding="utf-8") as f:
                    self.saved_rules = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load saved rules: {e}")
            self.saved_rules = []
    
    def save_rules_to_file(self):
        """
        保存搜索规则到配置文件
        """
        try:
            config_dir = os.path.join(os.path.expanduser("~"), ".anylabeling")
            os.makedirs(config_dir, exist_ok=True)
            rules_file = os.path.join(config_dir, "overview_search_rules.json")
            
            with open(rules_file, "w", encoding="utf-8") as f:
                json.dump(self.saved_rules, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save rules: {e}")
    
    def save_current_rule(self):
        """
        保存当前的搜索规则
        """
        field = self.field_combo.currentText()
        condition = self.condition_combo.currentText()
        search_text = self.search_input.text()
        
        # 如果是"为空"或"不为空"，不需要搜索文本
        if condition not in [self.tr("为空"), self.tr("不为空")] and not search_text:
            popup = Popup(
                self.tr("请输入搜索内容"),
                self.parent,
                msec=2000,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self.parent)
            return
        
        # 弹出对话框让用户输入规则名称
        from PyQt5.QtWidgets import QInputDialog
        rule_name, ok = QInputDialog.getText(
            self,
            self.tr("保存搜索规则"),
            self.tr("请输入规则名称:"),
            QLineEdit.Normal,
            f"{field}-{condition}"
        )
        
        if ok and rule_name:
            # 检查是否已存在同名规则
            for i, rule in enumerate(self.saved_rules):
                if rule.get("name") == rule_name:
                    # 更新已存在的规则
                    self.saved_rules[i] = {
                        "name": rule_name,
                        "field": field,
                        "condition": condition,
                        "search_text": search_text
                    }
                    self.save_rules_to_file()
                    self.update_saved_rules_combo()
                    popup = Popup(
                        self.tr(f"规则 '{rule_name}' 已更新"),
                        self.parent,
                        msec=2000,
                        icon=new_icon_path("copy-green", "svg"),
                    )
                    popup.show_popup(self.parent)
                    return
            
            # 添加新规则
            new_rule = {
                "name": rule_name,
                "field": field,
                "condition": condition,
                "search_text": search_text
            }
            self.saved_rules.append(new_rule)
            self.save_rules_to_file()
            self.update_saved_rules_combo()
            
            popup = Popup(
                self.tr(f"规则 '{rule_name}' 已保存"),
                self.parent,
                msec=2000,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self.parent)
    
    def update_saved_rules_combo(self):
        """
        更新已保存规则下拉框
        """
        self.saved_rules_combo.clear()
        self.saved_rules_combo.addItem(self.tr("已保存规则"))
        for rule in self.saved_rules:
            self.saved_rules_combo.addItem(rule.get("name", ""))
    
    def on_saved_rule_selected(self, index):
        """
        选择已保存的规则时应用该规则并自动搜索
        """
        if index == 0:  # "已保存规则"选项
            self.last_selected_rule_index = -1
            return
        
        # 记住选择的规则索引
        self.last_selected_rule_index = index - 1
        
        if self.last_selected_rule_index < len(self.saved_rules):
            rule = self.saved_rules[self.last_selected_rule_index]
            
            # 应用规则
            self.field_combo.setCurrentText(rule.get("field", ""))
            self.condition_combo.setCurrentText(rule.get("condition", ""))
            self.search_input.setText(rule.get("search_text", ""))
            
            # 自动执行搜索
            self.perform_search()
        
        # 保持选中状态，下拉框会显示选中的规则名称
    
    def delete_saved_rule(self):
        """
        删除最后选择的规则
        """
        # 使用记住的规则索引，而不是当前下拉框的索引
        if self.last_selected_rule_index < 0:
            popup = Popup(
                self.tr("请先从下拉框选择要删除的规则"),
                self.parent,
                msec=2000,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self.parent)
            return
        
        if self.last_selected_rule_index < len(self.saved_rules):
            rule_name = self.saved_rules[self.last_selected_rule_index].get("name", "")
            
            # 确认删除
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                self.tr("确认删除"),
                self.tr(f"确定要删除规则 '{rule_name}' 吗？"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                del self.saved_rules[self.last_selected_rule_index]
                self.last_selected_rule_index = -1  # 重置
                self.save_rules_to_file()
                self.update_saved_rules_combo()
                
                popup = Popup(
                    self.tr(f"规则 '{rule_name}' 已删除"),
                    self.parent,
                    msec=2000,
                    icon=new_icon_path("copy-green", "svg"),
                )
                popup.show_popup(self.parent)
    
    def filter_file_list(self):
        """
        根据搜索结果过滤主窗口的文件列表
        """
        if self.showing_label_infos:
            # 在Label视图时不执行过滤
            return
        
        # 获取搜索结果中的所有文件名（去重）
        filtered_filenames = set()
        for shape in self.displayed_shape_infos:
            filename = shape.get("filename", "")
            if filename:
                filtered_filenames.add(filename)
        
        if not filtered_filenames:
            # 没有搜索结果，显示提示
            popup = Popup(
                self.tr("没有搜索结果，无法过滤地址栏"),
                self.parent,
                msec=2000,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self.parent)
            return
        
        # 隐藏不在搜索结果中的文件
        for i in range(self.parent.file_list_widget.count()):
            item = self.parent.file_list_widget.item(i)
            if item:
                item_filename = item.text()
                # 检查文件名是否在搜索结果中
                should_show = any(fn in item_filename for fn in filtered_filenames)
                item.setHidden(not should_show)
        
        # 显示成功提示
        popup = Popup(
            self.tr(f"已过滤地址栏，显示 {len(filtered_filenames)} 个文件"),
            self.parent,
            msec=2000,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self.parent)
    
    def reset_file_list(self):
        """
        重置文件列表，显示所有文件
        """
        # 显示所有文件
        for i in range(self.parent.file_list_widget.count()):
            item = self.parent.file_list_widget.item(i)
            if item:
                item.setHidden(False)
        
        # 显示成功提示
        popup = Popup(
            self.tr("已重置地址栏，显示所有文件"),
            self.parent,
            msec=2000,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self.parent)
    
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
