# -*- encoding: utf-8 -*-

import json
import os.path as osp

from PyQt5.QtWidgets import (QHeaderView, QTableView, QDialog, QVBoxLayout,
                             QHBoxLayout, QWidget, QPushButton, QStyledItemDelegate,
                             QComboBox, QLineEdit, QLabel)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItem, QStandardItemModel, QColor, QPixmap, QIcon

LABEL_NAMES = ["balloon", "qipao", "shuqing", "changfangtiao", "hengxie"]

COL_LABEL = 0
COL_CHAR = 1
COL_ROTATE = 2
COL_OFFSET_X = 3
COL_OFFSET_Y = 4
COL_SPACING = 5

SWATCH_SIZE = 12
_BASE = osp.dirname(osp.dirname(osp.dirname(osp.dirname(osp.dirname(osp.abspath(__file__))))))
RENDER_RULES_CONFIG = osp.join(_BASE, "char_render_rules.json")


class LabelDelegate(QStyledItemDelegate):
    """标签列的下拉编辑器 —— 带颜色色块"""

    def __init__(self, dialog, parent=None):
        super().__init__(parent)
        self.dialog = dialog

    def _get_rgb(self, label):
        p = self.dialog.parent()
        if p and hasattr(p, "_get_rgb_by_label"):
            try:
                rgb = p._get_rgb_by_label(label)
                if rgb:
                    return rgb
            except Exception:
                pass
        return (150, 150, 150)

    def _make_swatch(self, r, g, b):
        pixmap = QPixmap(SWATCH_SIZE, SWATCH_SIZE)
        pixmap.fill(QColor(r, g, b))
        return QIcon(pixmap)

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        for label in LABEL_NAMES:
            rgb = self._get_rgb(label)
            combo.addItem(self._make_swatch(*rgb), label)
        return combo

    def setEditorData(self, editor, index):
        val = index.data(Qt.EditRole) or ""
        idx = editor.findText(val)
        if idx >= 0:
            editor.setCurrentIndex(idx)
        else:
            editor.setCurrentText(val)

    def setModelData(self, editor, model, index):
        text = editor.currentText().strip()
        model.setData(index, text, Qt.EditRole)


class CharRenderDialog(QDialog):
    """字符渲染规则工具 —— 独立于 OCR，按标签设置字符旋转与偏移"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("字符渲染"))
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)

        self.rules = self._load_from_file()

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels([
            self.tr("标签"), self.tr("字符"), self.tr("旋转°"),
            self.tr("偏移X"), self.tr("偏移Y"), self.tr("间距")
        ])

        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setItemDelegateForColumn(COL_LABEL, LabelDelegate(self, self.table))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_LABEL, QHeaderView.Fixed)
        header.resizeSection(COL_LABEL, 100)
        header.setSectionResizeMode(COL_CHAR, QHeaderView.Fixed)
        header.resizeSection(COL_CHAR, 60)
        header.setSectionResizeMode(COL_ROTATE, QHeaderView.Fixed)
        header.resizeSection(COL_ROTATE, 60)
        header.setSectionResizeMode(COL_OFFSET_X, QHeaderView.Fixed)
        header.resizeSection(COL_OFFSET_X, 60)
        header.setSectionResizeMode(COL_OFFSET_Y, QHeaderView.Fixed)
        header.resizeSection(COL_OFFSET_Y, 60)
        header.setSectionResizeMode(COL_SPACING, QHeaderView.Fixed)
        header.resizeSection(COL_SPACING, 50)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableView.SelectRows)

        self.btn_add = QPushButton(self.tr("添加"), self)
        self.btn_del = QPushButton(self.tr("删除"), self)
        self.btn_apply = QPushButton(self.tr("应用"), self)
        self.btn_close = QPushButton(self.tr("关闭"), self)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_del.clicked.connect(self._on_del)
        self.btn_apply.clicked.connect(self._apply)
        self.btn_close.clicked.connect(self.close)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_close)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("按标签设置字符的旋转角度、偏移和间距。标签留空则匹配所有标签。间距仅对竖排连续相同字符生效。")))
        layout.addWidget(self.table)
        layout.addLayout(btn_layout)
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)

        self._load_data()

    def _load_data(self):
        for row in self.rules:
            self._add_row(
                label=row.get("label", ""),
                char=row.get("char", ""),
                rotate=row.get("rotate", 0),
                offset_x=row.get("offset_x", 0),
                offset_y=row.get("offset_y", 0),
                spacing=row.get("spacing", 0),
            )

    def _add_row(self, label="", char="", rotate=0, offset_x=0, offset_y=0, spacing=0):
        row = self.model.rowCount()
        li = QStandardItem(label)
        self.model.setItem(row, COL_LABEL, li)
        self.model.setItem(row, COL_CHAR, QStandardItem(char))
        self.model.setItem(row, COL_ROTATE, QStandardItem(str(rotate)))
        self.model.setItem(row, COL_OFFSET_X, QStandardItem(str(offset_x)))
        self.model.setItem(row, COL_OFFSET_Y, QStandardItem(str(offset_y)))
        self.model.setItem(row, COL_SPACING, QStandardItem(str(spacing)))

    def _on_add(self):
        self._add_row()

    def _on_del(self):
        rows = set()
        for idx in self.table.selectedIndexes():
            rows.add(idx.row())
        for row in sorted(rows, reverse=True):
            self.model.removeRow(row)

    def _collect_rules(self):
        """从表格收集规则"""
        rules = []
        for row in range(self.model.rowCount()):
            label_item = self.model.item(row, COL_LABEL)
            char_item = self.model.item(row, COL_CHAR)
            rot_item = self.model.item(row, COL_ROTATE)
            ox_item = self.model.item(row, COL_OFFSET_X)
            oy_item = self.model.item(row, COL_OFFSET_Y)
            sp_item = self.model.item(row, COL_SPACING)

            char = (char_item.text() or "").strip() if char_item else ""
            if not char:
                continue

            label = (label_item.text() or "").strip() if label_item else ""

            try:
                rotate = int(rot_item.text()) if rot_item else 0
            except (ValueError, TypeError):
                rotate = 0
            try:
                offset_x = int(ox_item.text()) if ox_item else 0
            except (ValueError, TypeError):
                offset_x = 0
            try:
                offset_y = int(oy_item.text()) if oy_item else 0
            except (ValueError, TypeError):
                offset_y = 0
            try:
                spacing = int(sp_item.text()) if sp_item else 0
            except (ValueError, TypeError):
                spacing = 0

            rules.append({
                "char": char,
                "label": label,
                "rotate": rotate,
                "offset_x": offset_x,
                "offset_y": offset_y,
                "spacing": spacing,
            })
        return rules

    def get_rules(self):
        """返回字符渲染规则列表"""
        return self._collect_rules()

    def _apply(self):
        """保存并应用，不关闭窗口"""
        self.rules = self._collect_rules()
        self._save_to_file()
        if self.parent() and hasattr(self.parent(), "_sync_char_render_rules"):
            self.parent()._sync_char_render_rules()

    def _load_from_file(self):
        try:
            if osp.exists(RENDER_RULES_CONFIG):
                with open(RENDER_RULES_CONFIG, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_to_file(self):
        try:
            with open(RENDER_RULES_CONFIG, "w", encoding="utf-8") as f:
                json.dump(self.rules, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def closeEvent(self, event):
        self._save_to_file()
        super().closeEvent(event)

    def tr(self, text):
        from PyQt5.QtWidgets import QApplication
        return QApplication.translate("CharRenderDialog", text)
