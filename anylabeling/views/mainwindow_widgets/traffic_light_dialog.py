from PyQt5 import QtWidgets # Import QtWidgets module directly
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QColorDialog,
    QLabel,
    QPlainTextEdit,
    QGroupBox,
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import pyqtSignal, Qt


class TrafficLightDialog(QDialog):
    """
    A dialog for setting traffic light colors and clearing edited states.
    """

    # Signal to emit when "Clear All Edited" button is clicked
    clear_all_edited = pyqtSignal()
    # Signal to emit when "Clear Current Page Edited" button is clicked
    clear_current_page_edited = pyqtSignal()
    # Signal to emit when "Clear All Difficult" button is clicked
    clear_all_difficult = pyqtSignal()
    # Signal to emit when "Clear Current Page Difficult" button is clicked
    clear_current_page_difficult = pyqtSignal()
    # Signal to emit when "Clear All Manual Lock" button is clicked
    clear_all_manual_lock = pyqtSignal()
    # Signal to emit when "Clear Current Page Manual Lock" button is clicked
    clear_current_page_manual_lock = pyqtSignal()
    # Signal to emit when a traffic light color is changed
    color_changed = pyqtSignal(str, QColor) # light_name, new_color

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("红绿灯设置")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint) # Add minimize button
        # self.setMinimumWidth(400) # Removed fixed minimum width
        self.config = config

        # Mapping from English config key to Chinese display name
        self.key_to_display_name = {
            "selected": "已选中",
            "edited": "已编辑",
            "difficult": "困难标记",
            "locked": "已锁定",
            "unlocked": "已解锁",
        }
        # Mapping from Chinese display name to English config key
        self.display_name_to_key = {v: k for k, v in self.key_to_display_name.items()}

        # Default colors (if not in config or config is None)
        default_colors_rgb = {
            "selected": [255, 0, 0],  # Red
            "edited": [0, 255, 0],  # Green
            "difficult": [128, 0, 128],  # Purple
            "locked": [255, 255, 0],  # Yellow
            "unlocked": [0, 0, 255],  # Blue
        }

        self.traffic_light_colors = {}
        for key, display_name in self.key_to_display_name.items():
            rgb = default_colors_rgb[key]
            if self.config and "traffic_light_colors" in self.config and key in self.config["traffic_light_colors"]:
                rgb = self.config["traffic_light_colors"][key]
            self.traffic_light_colors[display_name] = QColor(*rgb)

        self._init_ui()
        self.resize(280, 400) # Set a reasonable initial size

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # Traffic Light Color Settings Group
        color_group_box = QGroupBox("信号灯颜色")
        color_grid_layout = QtWidgets.QGridLayout() # Use QGridLayout for grid arrangement
        color_grid_layout.setContentsMargins(10, 10, 10, 10) # Add some padding
        color_grid_layout.setSpacing(10) # Add spacing between items

        # Define the order for the grid (3 rows x 2 columns)
        # Row 0: selected, edited
        # Row 1: difficult, locked
        # Row 2: unlocked
        grid_order_keys = ["selected", "edited", "difficult", "locked", "unlocked"]

        for i, key in enumerate(grid_order_keys):
            display_name = self.key_to_display_name[key]
            current_color = self.traffic_light_colors[display_name]

            label = QLabel(f"{display_name}:")
            color_button = QPushButton("")
            color_button.setFixedSize(50, 25)
            color_button.setStyleSheet(
                f"background-color: {current_color.name()};"
            )
            color_button.clicked.connect(
                lambda checked, name=display_name: self._pick_color(name)
            )
            setattr(self, f"color_button_{key}", color_button) # Store button reference using English key

            row = i // 2
            col = i % 2 * 2 # Multiply by 2 to leave space for the button

            color_grid_layout.addWidget(label, row, col, Qt.AlignRight)
            color_grid_layout.addWidget(color_button, row, col + 1, Qt.AlignLeft)

        color_group_box.setLayout(color_grid_layout)
        main_layout.addWidget(color_group_box)

        # Clear Buttons - 2 columns x 3 rows layout
        buttons_grid_layout = QtWidgets.QGridLayout()
        buttons_grid_layout.setContentsMargins(10, 10, 10, 10)
        buttons_grid_layout.setSpacing(10)

        # Left column: Clear current page
        # Row 0: Clear current page edited
        self.clear_current_page_button = QPushButton("清除本页已编辑")
        self.clear_current_page_button.clicked.connect(self._on_clear_current_page_edited)
        buttons_grid_layout.addWidget(self.clear_current_page_button, 0, 0)

        # Row 1: Clear current page difficult
        self.clear_current_page_difficult_button = QPushButton("清除本页困难标记")
        self.clear_current_page_difficult_button.clicked.connect(self._on_clear_current_page_difficult)
        buttons_grid_layout.addWidget(self.clear_current_page_difficult_button, 1, 0)

        # Row 2: Clear current page manual lock
        self.clear_current_page_manual_lock_button = QPushButton("清除本页手动锁定")
        self.clear_current_page_manual_lock_button.clicked.connect(self._on_clear_current_page_manual_lock)
        buttons_grid_layout.addWidget(self.clear_current_page_manual_lock_button, 2, 0)

        # Right column: Clear all
        # Row 0: Clear all edited
        self.clear_button = QPushButton("清除全部已编辑")
        self.clear_button.clicked.connect(self._on_clear_all_edited)
        buttons_grid_layout.addWidget(self.clear_button, 0, 1)

        # Row 1: Clear all difficult
        self.clear_all_difficult_button = QPushButton("清除全部困难标记")
        self.clear_all_difficult_button.clicked.connect(self._on_clear_all_difficult)
        buttons_grid_layout.addWidget(self.clear_all_difficult_button, 1, 1)

        # Row 2: Clear all manual lock
        self.clear_all_manual_lock_button = QPushButton("清除全部手动锁定")
        self.clear_all_manual_lock_button.clicked.connect(self._on_clear_all_manual_lock)
        buttons_grid_layout.addWidget(self.clear_all_manual_lock_button, 2, 1)

        main_layout.addLayout(buttons_grid_layout)

        # Log Display
        log_group_box = QGroupBox("日志")
        log_layout = QVBoxLayout()
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        log_group_box.setLayout(log_layout)
        main_layout.addWidget(log_group_box)

    def _pick_color(self, display_name_chinese):
        initial_color = self.traffic_light_colors[display_name_chinese]
        color = QColorDialog.getColor(initial_color, self, f"选择 {display_name_chinese} 的颜色")
        if color.isValid():
            self.traffic_light_colors[display_name_chinese] = color
            english_key = self.display_name_to_key[display_name_chinese]
            button = getattr(self, f"color_button_{english_key}")
            button.setStyleSheet(f"background-color: {color.name()};")
            self.log_message(f"设置 {display_name_chinese} 颜色为 {color.name()}")
            self.color_changed.emit(english_key, color) # Emit signal with English key and new color


    def _on_clear_all_edited(self):
        self.log_message('"清除全部已编辑"按钮被点击。')
        self.clear_all_edited.emit()  # Emit signal for parent to handle

    def _on_clear_current_page_edited(self):
        self.log_message('"清除本页已编辑"按钮被点击。')
        self.clear_current_page_edited.emit()  # Emit signal for parent to handle

    def _on_clear_all_difficult(self):
        self.log_message('"清除全部困难标记"按钮被点击。')
        self.clear_all_difficult.emit()  # Emit signal for parent to handle

    def _on_clear_current_page_difficult(self):
        self.log_message('"清除本页困难标记"按钮被点击。')
        self.clear_current_page_difficult.emit()  # Emit signal for parent to handle

    def _on_clear_all_manual_lock(self):
        self.log_message('"清除全部手动锁定"按钮被点击。')
        self.clear_all_manual_lock.emit()  # Emit signal for parent to handle

    def _on_clear_current_page_manual_lock(self):
        self.log_message('"清除本页手动锁定"按钮被点击。')
        self.clear_current_page_manual_lock.emit()  # Emit signal for parent to handle

    def log_message(self, message):
        self.log_display.appendPlainText(message)

    def get_traffic_light_colors(self):
        return self.traffic_light_colors
