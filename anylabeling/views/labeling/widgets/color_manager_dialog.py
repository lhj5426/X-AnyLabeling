
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QWidget, QDialogButtonBox, QFormLayout, QPushButton, QColorDialog, QDoubleSpinBox, QSpinBox
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, pyqtSignal, QCoreApplication

class ColorManagerDialog(QDialog):
    setting_changed = pyqtSignal(str, object)

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("颜色管理器"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint | Qt.WindowMinMaxButtonsHint)
        self.setMaximumWidth(320)

        self.config = config
        self.parent = parent

        self.original_config = {k: v for k, v in config.items()}

        self.color_formats = {}

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.manually_edited_color_button = self.create_color_button('manually_edited_color', self.config.get('manually_edited_color', '#FFA500'))
        form_layout.addRow(self.tr("手动编辑颜色:"), self.manually_edited_color_button)

        self.canvas_hover_line_color_button = self.create_color_button(['shape', 'canvas_hover_line_color'], self.config['shape']['canvas_hover_line_color'])
        form_layout.addRow(self.tr("画布悬停线条颜色:"), self.canvas_hover_line_color_button)

        self.canvas_hover_line_width_spinbox = QDoubleSpinBox()
        self.canvas_hover_line_width_spinbox.setValue(self.config['shape']['canvas_hover_line_width'])
        self.canvas_hover_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'canvas_hover_line_width'], value))
        form_layout.addRow(self.tr("画布悬停线条宽度:"), self.canvas_hover_line_width_spinbox)

        self.canvas_select_line_color_button = self.create_color_button(['shape', 'canvas_select_line_color'], self.config['shape']['canvas_select_line_color'])
        form_layout.addRow(self.tr("画布选中线条颜色:"), self.canvas_select_line_color_button)

        self.canvas_select_line_width_spinbox = QDoubleSpinBox()
        self.canvas_select_line_width_spinbox.setValue(self.config['shape']['canvas_select_line_width'])
        self.canvas_select_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'canvas_select_line_width'], value))
        form_layout.addRow(self.tr("画布选中线条宽度:"), self.canvas_select_line_width_spinbox)

        self.fill_color_button = self.create_color_button(['shape', 'fill_color'], self.config['shape']['fill_color'])
        form_layout.addRow(self.tr("填充颜色:"), self.fill_color_button)

        self.hvertex_fill_color_button = self.create_color_button(['shape', 'hvertex_fill_color'], self.config['shape']['hvertex_fill_color'])
        form_layout.addRow(self.tr("高亮顶点填充颜色:"), self.hvertex_fill_color_button)

        self.line_color_button = self.create_color_button(['shape', 'line_color'], self.config['shape']['line_color'])
        form_layout.addRow(self.tr("选择标签时填充颜色:"), self.line_color_button)

        self.line_width_spinbox = QDoubleSpinBox()
        self.line_width_spinbox.setValue(self.config['shape']['line_width'])
        self.line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'line_width'], value))
        form_layout.addRow(self.tr("线条宽度:"), self.line_width_spinbox)

        self.navigator_hover_line_color_button = self.create_color_button(['shape', 'navigator_hover_line_color'], self.config['shape']['navigator_hover_line_color'])
        form_layout.addRow(self.tr("导航器悬停线条颜色:"), self.navigator_hover_line_color_button)

        self.navigator_select_line_color_button = self.create_color_button(['shape', 'navigator_select_line_color'], self.config['shape']['navigator_select_line_color'])
        form_layout.addRow(self.tr("导航器选中线条颜色:"), self.navigator_select_line_color_button)

        self.overlap_color_button = self.create_color_button(['shape', 'overlap_color'], self.config['shape']['overlap_color'])
        form_layout.addRow(self.tr("重叠颜色:"), self.overlap_color_button)

        self.overlap_alpha_spinbox = QSpinBox()
        self.overlap_alpha_spinbox.setRange(0, 255)
        self.overlap_alpha_spinbox.setValue(self.config['shape']['overlap_color'][3])
        self.overlap_alpha_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'overlap_color_alpha'], value))
        form_layout.addRow(self.tr("重叠颜色透明度:"), self.overlap_alpha_spinbox)

        self.point_size_spinbox = QDoubleSpinBox()
        self.point_size_spinbox.setValue(self.config['shape']['point_size'])
        self.point_size_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'point_size'], value))
        form_layout.addRow(self.tr("点大小:"), self.point_size_spinbox)

        self.select_fill_color_button = self.create_color_button(['shape', 'select_fill_color'], self.config['shape']['select_fill_color'])
        form_layout.addRow(self.tr("选中填充颜色:"), self.select_fill_color_button)

        self.select_line_color_button = self.create_color_button(['shape', 'select_line_color'], self.config['shape']['select_line_color'])
        form_layout.addRow(self.tr("绘制时线条颜色:"), self.select_line_color_button)

        self.select_line_width_spinbox = QDoubleSpinBox()
        self.select_line_width_spinbox.setValue(self.config['shape'].get('select_line_width', 0) or 0)
        self.select_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'select_line_width'], value))
        form_layout.addRow(self.tr("选中线条宽度:"), self.select_line_width_spinbox)

        self.shape_fill_alpha_highlight_spinbox = QSpinBox()
        self.shape_fill_alpha_highlight_spinbox.setRange(0, 255)
        self.shape_fill_alpha_highlight_spinbox.setValue(self.config['shape']['shape_fill_alpha_highlight'])
        self.shape_fill_alpha_highlight_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'shape_fill_alpha_highlight'], value))
        form_layout.addRow(self.tr("形状填充高亮透明度:"), self.shape_fill_alpha_highlight_spinbox)

        self.shape_fill_alpha_idle_spinbox = QSpinBox()
        self.shape_fill_alpha_idle_spinbox.setRange(0, 255)
        self.shape_fill_alpha_idle_spinbox.setValue(self.config['shape']['shape_fill_alpha_idle'])
        self.shape_fill_alpha_idle_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'shape_fill_alpha_idle'], value))
        form_layout.addRow(self.tr("形状填充默认透明度:"), self.shape_fill_alpha_idle_spinbox)

        self.vertex_fill_color_button = self.create_color_button(['shape', 'vertex_fill_color'], self.config['shape']['vertex_fill_color'])
        form_layout.addRow(self.tr("顶点填充颜色:"), self.vertex_fill_color_button)

        # Alignment tool settings
        self.alignment_reference_color_button = self.create_color_button(['shape', 'alignment_reference_color'], self.config['shape'].get('alignment_reference_color', [255, 0, 255, 255]))
        form_layout.addRow(self.tr("对齐工具参照颜色:"), self.alignment_reference_color_button)

        self.alignment_target_color_button = self.create_color_button(['shape', 'alignment_target_color'], self.config['shape'].get('alignment_target_color', [255, 165, 0, 255]))
        form_layout.addRow(self.tr("对齐工具被执行颜色:"), self.alignment_target_color_button)

        self.alignment_reference_line_width_spinbox = QDoubleSpinBox()
        self.alignment_reference_line_width_spinbox.setValue(self.config['shape'].get('alignment_reference_line_width', 4.0))
        self.alignment_reference_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'alignment_reference_line_width'], value))
        form_layout.addRow(self.tr("对齐工具参照线宽度:"), self.alignment_reference_line_width_spinbox)

        self.alignment_target_line_width_spinbox = QDoubleSpinBox()
        self.alignment_target_line_width_spinbox.setValue(self.config['shape'].get('alignment_target_line_width', 2.0))
        self.alignment_target_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'alignment_target_line_width'], value))
        form_layout.addRow(self.tr("对齐工具被执行线宽度:"), self.alignment_target_line_width_spinbox)

        layout.addLayout(form_layout)

    def tr(self, text):
        return QCoreApplication.translate("ColorManagerDialog", text)

    def create_color_button(self, key, color):
        button = QPushButton()
        if isinstance(color, str):
            self.color_formats[str(key)] = 'hex'
            button.setStyleSheet(f"background-color: {color}")
        else:
            self.color_formats[str(key)] = 'rgba'
            button.setStyleSheet(f"background-color: rgba({', '.join(map(str, color))})")
        button.clicked.connect(lambda: self.show_color_dialog(key, button))
        return button

    def show_color_dialog(self, key, button):
        color = QColorDialog.getColor(QColor(button.styleSheet().split(':')[-1].strip()))
        if color.isValid():
            # Set button to opaque color for display purposes, as requested by user
            opaque_color = QColor(color.red(), color.green(), color.blue())
            button.setStyleSheet(f"background-color: {opaque_color.name(QColor.HexRgb)}")

            # If we are changing the overlap color, we must use the alpha from the spinbox
            if str(key) == str(['shape', 'overlap_color']):
                current_alpha = self.overlap_alpha_spinbox.value()
                color.setAlpha(current_alpha)

            # Determine the actual value to emit, respecting the original format (hex vs rgba)
            if self.color_formats.get(str(key)) == 'hex':
                # For hex format, alpha is not supported, we send #RRGGBB
                value_to_emit = color.name(QColor.HexRgb)
            else:
                # For rgba format, we send the list with the correct alpha
                value_to_emit = list(color.getRgb())

            self._on_setting_changed(key, value_to_emit)

    def get_color_from_button(self, key, button):
        color_str = button.styleSheet().split(':')[-1].strip()
        color = QColor(color_str)
        if self.color_formats[str(key)] == 'hex':
            return color.name()
        else:
            return list(color.getRgb())

    def _on_setting_changed(self, key, value):
        self.setting_changed.emit(str(key), value)
