import re
import os.path as osp
import json

from PyQt5.QtWidgets import (QHeaderView, QTableView, QDialog, QVBoxLayout,
                             QHBoxLayout, QWidget, QPushButton, QStyledItemDelegate,
                             QComboBox, QLineEdit)
from PyQt5.QtCore import Qt, QSortFilterProxyModel
from PyQt5.QtGui import QStandardItem, QStandardItemModel, QColor, QPixmap, QIcon

from anylabeling.views.labeling.logger import logger

LABEL_NAMES = ["balloon", "qipao", "shuqing", "changfangtiao", "hengxie"]

COL_LABEL = 0
COL_KEYWORD = 1
COL_SUB = 2
COL_REGEX = 3
COL_CASE = 4

SWATCH_SIZE = 12
_BASE = osp.dirname(osp.dirname(osp.dirname(osp.dirname(osp.abspath(__file__)))))
OCR_REPLACE_CONFIG = osp.join(_BASE, ".ocr_text_replace.json")


class OCRReplaceFilterProxy(QSortFilterProxyModel):
    """按 标签/关键词/替换为 三列过滤"""

    def filterAcceptsRow(self, row, parent):
        if not self.filterRegularExpression():
            return True
        pattern = self.filterRegularExpression().pattern()
        if not pattern:
            return True
        model = self.sourceModel()
        for col in (COL_LABEL, COL_KEYWORD, COL_SUB):
            idx = model.index(row, col, parent)
            if pattern.lower() in model.data(idx, Qt.EditRole).lower():
                return True
        return False


class LabelDelegate(QStyledItemDelegate):
    """标签列的下拉编辑器 —— 可编辑，预设标签带颜色色块"""

    def __init__(self, dialog, parent=None):
        super().__init__(parent)
        self.dialog = dialog

    def _get_rgb(self, label):
        """从父窗口获取标签颜色"""
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
        if text:
            dialog = self.dialog
            rgb = self._get_rgb(text)
            color = QColor(*rgb)
            src_model = dialog.model
            src_idx = index
            if isinstance(model, QSortFilterProxyModel):
                src_idx = model.mapToSource(index)
            item = src_model.itemFromIndex(src_idx)
            if item:
                item.setBackground(color)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class OCRTextReplaceDialog(QDialog):
    """OCR 文本替换 —— 单表格，标签 | 关键词 | 替换为 | 正则 | 大小写"""

    def __init__(self, all_sublists=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("OCR文本替换"))
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)

        # 从独立 JSON 文件加载规则
        if all_sublists is None:
            all_sublists = self._load_from_file()
        self.sublist = self._normalize(all_sublists or {})

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels([
            self.tr("标签"), self.tr("关键词"), self.tr("替换为"),
            self.tr("正则"), self.tr("大小写")
        ])
        # itemChanged 在 setData 时触发，但 QStandardItem 直接改属性不一定触发
        # 改用 dataChanged 信号更加可靠
        self.model.dataChanged.connect(self._on_data_changed)
        self._changing = False

        self.proxy = OCRReplaceFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)

        self.table = QTableView(self)
        self.table.setModel(self.proxy)
        self.table.setItemDelegateForColumn(COL_LABEL, LabelDelegate(self, self.table))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_LABEL, QHeaderView.Fixed)
        header.resizeSection(COL_LABEL, 120)
        header.setSectionResizeMode(COL_KEYWORD, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_SUB, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_REGEX, QHeaderView.Fixed)
        header.resizeSection(COL_REGEX, 50)
        header.setSectionResizeMode(COL_CASE, QHeaderView.Fixed)
        header.resizeSection(COL_CASE, 60)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableView.SelectRows)

        # 搜索框
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(self.tr("搜索标签/关键词/替换为..."))
        self.search_edit.textChanged.connect(self._on_search)

        # 按钮
        self.btn_add = QPushButton(self.tr("添加"), self)
        self.btn_del = QPushButton(self.tr("删除"), self)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_del.clicked.connect(self._on_del)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        btn_layout.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.table)
        layout.addLayout(btn_layout)
        self.setMinimumWidth(650)
        self.setMinimumHeight(350)

        # 填充数据
        for row_data in self.sublist:
            self._add_row(
                row_data.get("label", "balloon"),
                row_data.get("keyword", ""),
                row_data.get("sub", ""),
                row_data.get("use_reg", False),
                row_data.get("case_sens", True),
                save=False,
            )

    def _get_rgb(self, label):
        """获取标签对应颜色"""
        p = self.parent()
        if p and hasattr(p, "_get_rgb_by_label"):
            try:
                rgb = p._get_rgb_by_label(label)
                if rgb:
                    return rgb
            except Exception:
                pass
        return (150, 150, 150)

    def _normalize(self, data):
        """兼容旧格式 {label: [...]} → 新格式 [...]"""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            result = []
            for label, items in data.items():
                for item in items:
                    if isinstance(item, dict):
                        item = dict(item)
                        item.setdefault("label", label)
                        result.append(item)
            return result
        return []

    def _add_row(self, label="", keyword="", sub="", use_reg=False, case_sens=False, save=True):
        self._changing = True
        row = self.model.rowCount()

        # 标签列 —— 背景色匹配软件标签颜色
        li = QStandardItem(label)
        if label:
            rgb = self._get_rgb(label)
            li.setBackground(QColor(*rgb))
        self.model.setItem(row, COL_LABEL, li)

        self.model.setItem(row, COL_KEYWORD, QStandardItem(keyword))
        self.model.setItem(row, COL_SUB, QStandardItem(sub))

        ri = QStandardItem()
        ri.setCheckable(True)
        ri.setCheckState(Qt.Checked if use_reg else Qt.Unchecked)
        ri.setEditable(False)
        ri.setTextAlignment(Qt.AlignCenter)
        self.model.setItem(row, COL_REGEX, ri)

        ci = QStandardItem()
        ci.setCheckable(True)
        ci.setCheckState(Qt.Checked if case_sens else Qt.Unchecked)
        ci.setEditable(False)
        ci.setTextAlignment(Qt.AlignCenter)
        self.model.setItem(row, COL_CASE, ci)

        if save:
            self.sublist.append({
                "label": label, "keyword": keyword, "sub": sub,
                "use_reg": use_reg, "case_sens": case_sens,
            })
        self._changing = False

    def _on_search(self, text):
        self.proxy.setFilterRegularExpression(text)

    def _on_add(self):
        self._add_row()

    def _on_del(self):
        rows = set()
        for idx in self.table.selectedIndexes():
            src = self.proxy.mapToSource(idx)
            rows.add(src.row())
        for row in sorted(rows, reverse=True):
            if row < len(self.sublist):
                self.sublist.pop(row)
            self.model.removeRow(row)

    def _on_data_changed(self, topLeft, bottomRight, roles):
        if self._changing:
            return
        # dataChanged 返回的是源 model 的 index
        for row in range(topLeft.row(), bottomRight.row() + 1):
            for col in range(topLeft.column(), bottomRight.column() + 1):
                if row >= len(self.sublist):
                    continue
                entry = self.sublist[row]
                item = self.model.item(row, col)
                if not item:
                    continue
                if col == COL_LABEL:
                    label = item.text().strip()
                    entry["label"] = label
                    if label:
                        rgb = self._get_rgb(label)
                        item.setBackground(QColor(*rgb))
                elif col == COL_KEYWORD:
                    entry["keyword"] = item.text()
                elif col == COL_SUB:
                    entry["sub"] = item.text()
                elif col == COL_REGEX:
                    entry["use_reg"] = item.checkState() == Qt.Checked
                elif col == COL_CASE:
                    entry["case_sens"] = item.checkState() == Qt.Checked

    def _get_rules(self):
        """从源 model 读取所有规则 —— 不依赖 sublist 同步"""
        rules = []
        for row in range(self.model.rowCount()):
            label_item = self.model.item(row, COL_LABEL)
            kw_item = self.model.item(row, COL_KEYWORD)
            sub_item = self.model.item(row, COL_SUB)
            reg_item = self.model.item(row, COL_REGEX)
            cs_item = self.model.item(row, COL_CASE)
            if not label_item or not kw_item:
                continue
            kw = kw_item.text().strip()
            if not kw:
                continue
            rules.append({
                "label": label_item.text().strip(),
                "keyword": kw,
                "sub": (sub_item.text() or "") if sub_item else "",
                "use_reg": reg_item.checkState() == Qt.Checked if reg_item else False,
                "case_sens": cs_item.checkState() == Qt.Checked if cs_item else False,
            })
        return rules

    def apply(self, label, text):
        """按标签名过滤并替换 —— 直接从 model 读规则"""
        if not text:
            return text
        rules = self._get_rules()
        matches = [e for e in rules if e.get("label", "") == label]
        if matches:
            logger.info(f"OCR replace [{label}]: applying {len(matches)} rule(s) — {[(e['keyword'], e.get('sub','')) for e in matches]}")
        for entry in rules:
            if not entry.get("label") or entry.get("label") != label:
                continue
            k = entry["keyword"]
            pattern = k
            flags = re.DOTALL
            if not entry.get("case_sens", True):
                flags |= re.IGNORECASE
            if not entry.get("use_reg", False):
                pattern = re.escape(pattern)
            try:
                text = re.sub(pattern, entry.get("sub", ""), text)
            except Exception:
                logger.error(f"Invalid regex: {pattern}")
        return text

    def _load_from_file(self):
        """从独立 JSON 文件加载规则"""
        try:
            if osp.exists(OCR_REPLACE_CONFIG):
                with open(OCR_REPLACE_CONFIG, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_to_file(self):
        """保存规则到独立 JSON 文件"""
        try:
            with open(OCR_REPLACE_CONFIG, "w", encoding="utf-8") as f:
                json.dump(self.get_all_sublists(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_all_sublists(self):
        """返回扁平列表 —— 直接从 model 读取"""
        return self._get_rules()

    def closeEvent(self, event):
        self._save_to_file()
        super().closeEvent(event)
