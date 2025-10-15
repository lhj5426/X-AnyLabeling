
import re
from PyQt5 import QtCore, QtGui, QtWidgets
from anylabeling.views.labeling.utils.qt import new_icon_path


class ColoredLabelComboBox(QtWidgets.QComboBox):
    """A QComboBox that displays items with colored backgrounds."""
    def __init__(self, parent=None, get_label_qcolor_func=None):
        super(ColoredLabelComboBox, self).__init__(parent)
        self.setStyleSheet("combobox-popup: 0;") # Remove popup frame
        self.get_label_qcolor_func = get_label_qcolor_func

    def addLabelItems(self, all_unique_labels, get_label_qcolor_func):
        """Populate the combobox with labels and their colors."""
        self.get_label_qcolor_func = get_label_qcolor_func # Update the stored function
        self.addItem("") # Add an empty item first
        for label in all_unique_labels:
            self.addItem(label)
            index = self.count() - 1
            
            color = self.get_label_qcolor_func(label)
            
            # Set background color
            self.setItemData(index, color, QtCore.Qt.BackgroundRole)
            
            # Set text color based on background brightness
            lum = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255
            text_color = QtGui.QColor(0, 0, 0) if lum > 0.5 else QtGui.QColor(255, 255, 255)
            self.setItemData(index, text_color, QtCore.Qt.ForegroundRole)

    def paintEvent(self, event):
        """Custom paint event to draw the background color of the selected item."""
        painter = QtWidgets.QStylePainter(self)
        
        opt = QtWidgets.QStyleOptionComboBox()
        self.initStyleOption(opt)

        # Draw the combobox frame, button, etc.
        painter.drawComplexControl(QtWidgets.QStyle.CC_ComboBox, opt)

        # Draw the background for the selected item
        current_text = self.currentText()
        # Always try to get color if get_label_qcolor_func is available
        if self.get_label_qcolor_func:
            color = self.get_label_qcolor_func(current_text)
            if isinstance(color, QtGui.QColor):
                rect = self.style().subElementRect(QtWidgets.QStyle.SE_ComboBoxFocusRect, opt, self)
                painter.fillRect(rect, color)

        # Draw the text
        text_color_data = self.itemData(self.currentIndex(), QtCore.Qt.ForegroundRole)
        if isinstance(text_color_data, QtGui.QColor):
            painter.setPen(text_color_data)
        else:
            painter.setPen(self.palette().color(QtGui.QPalette.Text))
            
        rect = self.style().subElementRect(QtWidgets.QStyle.SE_ComboBoxFocusRect, opt, self)
        rect.adjust(5, 0, -5, 0) # Adjust text padding
        painter.drawText(rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, current_text)
class LabelToggleShortcutDialog(QtWidgets.QDialog):
    """Dialog for managing label toggle shortcuts"""

    def __init__(self, parent=None, shortcuts=None, all_unique_labels=None, get_label_qcolor_func=None):
        """
        Initialize the dialog.

        Args:
            parent: The parent widget.
            shortcuts (dict): Existing shortcuts {'shortcut': 'label'}.
            all_unique_labels (list): List of all unique label names.
            get_label_qcolor_func (function): Function to get QColor for a given label name.
        """
        super(LabelToggleShortcutDialog, self).__init__(parent)
        self.parent = parent
        self.shortcuts = shortcuts if shortcuts is not None else {}
        self.all_unique_labels = sorted(list(set(all_unique_labels))) if all_unique_labels is not None else []
        self.get_label_qcolor_func = get_label_qcolor_func

        self.setWindowTitle(self.tr("标签切换快捷键管理器"))
        self.setModal(True)
        self.setMinimumSize(600, 400)
        self.setWindowFlags(
            self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
        )

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        header_label = QtWidgets.QLabel(
            self.tr("配置用于切换标签可见性的快捷键：")
        )
        header_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header_label)

        # Table for shortcuts
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([self.tr("快捷键"), self.tr("标签")])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

        # Buttons for table manipulation
        table_button_layout = QtWidgets.QHBoxLayout()
        self.add_button = QtWidgets.QPushButton(self.tr("添加"))
        self.remove_button = QtWidgets.QPushButton(self.tr("移除"))
        table_button_layout.addStretch()
        table_button_layout.addWidget(self.add_button)
        table_button_layout.addWidget(self.remove_button)
        layout.addLayout(table_button_layout)

        # Dialog buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(8)
        self.reset_button = QtWidgets.QPushButton(self.tr("重置"))
        ok_button = QtWidgets.QPushButton(self.tr("确认"))
        cancel_button = QtWidgets.QPushButton(self.tr("取消"))
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Populate table
        self.populate_table()

        # Connections
        self.add_button.clicked.connect(self.add_row)
        self.remove_button.clicked.connect(self.remove_row)
        ok_button.clicked.connect(self.save_settings)
        cancel_button.clicked.connect(self.reject)
        self.reset_button.clicked.connect(self.reset_settings)

    def populate_table(self):
        self.table.setRowCount(0)
        for shortcut, label in self.shortcuts.items():
            self.add_row(shortcut, label)

    def add_row(self, shortcut="", label=""):
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)

        # Shortcut editor
        key_sequence_edit = QtWidgets.QKeySequenceEdit(QtGui.QKeySequence(shortcut))
        self.table.setCellWidget(row_position, 0, key_sequence_edit)

        # Label combobox
        label_combo = ColoredLabelComboBox(get_label_qcolor_func=self.get_label_qcolor_func)
        label_combo.addLabelItems(self.all_unique_labels, self.get_label_qcolor_func)
        if label:
            label_combo.setCurrentText(label)
        self.table.setCellWidget(row_position, 1, label_combo)

    def remove_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def reset_settings(self):
        confirm = QtWidgets.QMessageBox.warning(
            self,
            self.tr("确认重置"),
            self.tr("您确定要重置所有快捷键吗？"),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if confirm == QtWidgets.QMessageBox.Yes:
            self.shortcuts = {}
            self.populate_table()

    def save_settings(self):
        new_shortcuts = {}
        for row in range(self.table.rowCount()):
            key_sequence_edit = self.table.cellWidget(row, 0)
            shortcut = key_sequence_edit.keySequence().toString()
            label_combo = self.table.cellWidget(row, 1)
            label = label_combo.currentText()

            if shortcut and label:
                new_shortcuts[shortcut] = label
        
        self.shortcuts = new_shortcuts
        self.accept()

