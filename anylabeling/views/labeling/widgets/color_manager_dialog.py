
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QWidget, QDialogButtonBox, QFormLayout, QPushButton, QColorDialog, QDoubleSpinBox, QSpinBox, QHBoxLayout, QGridLayout, QLabel, QFrame
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, pyqtSignal, QCoreApplication

# 统一的输入框宽度（包含上下箭头，与颜色按钮对齐）
SPINBOX_WIDTH = 60

class ColorManagerDialog(QDialog):
    setting_changed = pyqtSignal(str, object)

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("颜色管理器"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint | Qt.WindowMinMaxButtonsHint)

        self.config = config
        self.parent = parent

        self.original_config = {k: v for k, v in config.items()}

        self.color_formats = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # 整体边距

        # 使用水平布局实现双列显示
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(0)  # 去掉默认间距，手动控制
        columns_layout.setContentsMargins(0, 0, 0, 0)  # 去掉布局边距

        # 左列的表单布局
        left_form = QFormLayout()
        left_form.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        left_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        left_form.setHorizontalSpacing(5)  # 标签和控件之间的间距缩小到5像素
        left_form.setVerticalSpacing(5)  # 行间距缩小到5像素
        left_form.setContentsMargins(0, 0, 0, 0)  # 去掉边距

        # 右列的表单布局
        right_form = QFormLayout()
        right_form.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        right_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right_form.setHorizontalSpacing(5)  # 标签和控件之间的间距缩小到5像素
        right_form.setVerticalSpacing(5)  # 行间距缩小到5像素
        right_form.setContentsMargins(0, 0, 0, 0)  # 去掉边距

        # === 左列配置项 ===
        self.manually_edited_color_button = self.create_color_button('manually_edited_color', self.config.get('manually_edited_color', '#FFA500'))
        left_form.addRow(self.tr("手动编辑颜色:"), self.manually_edited_color_button)

        self.canvas_hover_line_color_button = self.create_color_button(['shape', 'canvas_hover_line_color'], self.config['shape']['canvas_hover_line_color'])
        left_form.addRow(self.tr("画布悬停线条颜色:"), self.canvas_hover_line_color_button)

        self.canvas_hover_line_width_spinbox = QDoubleSpinBox()
        self.canvas_hover_line_width_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.canvas_hover_line_width_spinbox.setValue(self.config['shape']['canvas_hover_line_width'])
        self.canvas_hover_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'canvas_hover_line_width'], value))
        left_form.addRow(self.tr("画布悬停线条宽度:"), self.canvas_hover_line_width_spinbox)

        self.canvas_select_line_color_button = self.create_color_button(['shape', 'canvas_select_line_color'], self.config['shape']['canvas_select_line_color'])
        left_form.addRow(self.tr("画布选中线条颜色:"), self.canvas_select_line_color_button)

        self.canvas_select_line_width_spinbox = QDoubleSpinBox()
        self.canvas_select_line_width_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.canvas_select_line_width_spinbox.setValue(self.config['shape']['canvas_select_line_width'])
        self.canvas_select_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'canvas_select_line_width'], value))
        left_form.addRow(self.tr("画布选中线条宽度:"), self.canvas_select_line_width_spinbox)

        self.fill_color_button = self.create_color_button(['shape', 'fill_color'], self.config['shape']['fill_color'])
        left_form.addRow(self.tr("填充颜色:"), self.fill_color_button)

        self.hvertex_fill_color_button = self.create_color_button(['shape', 'hvertex_fill_color'], self.config['shape']['hvertex_fill_color'])
        left_form.addRow(self.tr("拖拽时顶点填充色:"), self.hvertex_fill_color_button)

        self.line_color_button = self.create_color_button(['shape', 'line_color'], self.config['shape']['line_color'])
        left_form.addRow(self.tr("选择标签时填充颜色:"), self.line_color_button)

        self.line_width_spinbox = QDoubleSpinBox()
        self.line_width_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.line_width_spinbox.setValue(self.config['shape']['line_width'])
        self.line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'line_width'], value))
        left_form.addRow(self.tr("线条宽度:"), self.line_width_spinbox)

        self.navigator_hover_line_color_button = self.create_color_button(['shape', 'navigator_hover_line_color'], self.config['shape']['navigator_hover_line_color'])
        left_form.addRow(self.tr("导航器悬停线条颜色:"), self.navigator_hover_line_color_button)

        self.navigator_select_line_color_button = self.create_color_button(['shape', 'navigator_select_line_color'], self.config['shape']['navigator_select_line_color'])
        left_form.addRow(self.tr("导航器选中线条颜色:"), self.navigator_select_line_color_button)

        self.overlap_color_button = self.create_color_button(['shape', 'overlap_color'], self.config['shape']['overlap_color'])
        left_form.addRow(self.tr("重叠颜色:"), self.overlap_color_button)

        self.overlap_alpha_spinbox = QSpinBox()
        self.overlap_alpha_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.overlap_alpha_spinbox.setRange(0, 255)
        self.overlap_alpha_spinbox.setValue(self.config['shape']['overlap_color'][3])
        self.overlap_alpha_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'overlap_color_alpha'], value))
        left_form.addRow(self.tr("重叠颜色透明度:"), self.overlap_alpha_spinbox)

        self.point_size_spinbox = QDoubleSpinBox()
        self.point_size_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.point_size_spinbox.setValue(self.config['shape']['point_size'])
        self.point_size_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'point_size'], value))
        left_form.addRow(self.tr("点大小:"), self.point_size_spinbox)

        self.square_size_spinbox = QDoubleSpinBox()
        self.square_size_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.square_size_spinbox.setValue(self.config['shape'].get('square_size', 10))
        self.square_size_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'square_size'], value))
        left_form.addRow(self.tr("块大小:"), self.square_size_spinbox)

        # Paste preview settings (虚影样式设置)
        self.paste_preview_line_color_button = self.create_color_button('paste_preview_line_color', self.config.get('paste_preview_line_color', [255, 0, 255]))
        left_form.addRow(self.tr("虚影线条颜色:"), self.paste_preview_line_color_button)

        # Smart guides settings (辅助线样式设置)
        self.smart_guides_line_color_button = self.create_color_button('smart_guides_line_color', self.config.get('smart_guides_line_color', [255, 0, 255]))
        left_form.addRow(self.tr("辅助线线条颜色:"), self.smart_guides_line_color_button)

        # Rectangle spacing guide settings (矩形间距线样式设置)
        self.spacing_guide_line_color_button = self.create_color_button('spacing_guide_line_color', self.config.get('spacing_guide_line_color', [0, 255, 255]))
        left_form.addRow(self.tr("间距线线条颜色:"), self.spacing_guide_line_color_button)

        self.spacing_guide_text_bg_color_button = self.create_color_button('spacing_guide_text_bg_color', self.config.get('spacing_guide_text_bg_color', [0, 0, 0, 150]))
        left_form.addRow(self.tr("间距线文字背景色:"), self.spacing_guide_text_bg_color_button)

        # === 右列配置项 ===
        self.select_fill_color_button = self.create_color_button(['shape', 'select_fill_color'], self.config['shape']['select_fill_color'])
        right_form.addRow(self.tr("选中填充颜色:"), self.select_fill_color_button)

        self.select_line_color_button = self.create_color_button(['shape', 'select_line_color'], self.config['shape']['select_line_color'])
        right_form.addRow(self.tr("绘制时线条颜色:"), self.select_line_color_button)

        self.select_line_width_spinbox = QDoubleSpinBox()
        self.select_line_width_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.select_line_width_spinbox.setValue(self.config['shape'].get('select_line_width', 0) or 0)
        self.select_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'select_line_width'], value))
        right_form.addRow(self.tr("选中线条宽度:"), self.select_line_width_spinbox)

        self.shape_fill_alpha_highlight_spinbox = QSpinBox()
        self.shape_fill_alpha_highlight_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.shape_fill_alpha_highlight_spinbox.setRange(0, 255)
        self.shape_fill_alpha_highlight_spinbox.setValue(self.config['shape']['shape_fill_alpha_highlight'])
        self.shape_fill_alpha_highlight_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'shape_fill_alpha_highlight'], value))
        right_form.addRow(self.tr("形状填充高亮透明度:"), self.shape_fill_alpha_highlight_spinbox)

        self.shape_fill_alpha_idle_spinbox = QSpinBox()
        self.shape_fill_alpha_idle_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.shape_fill_alpha_idle_spinbox.setRange(0, 255)
        self.shape_fill_alpha_idle_spinbox.setValue(self.config['shape']['shape_fill_alpha_idle'])
        self.shape_fill_alpha_idle_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'shape_fill_alpha_idle'], value))
        right_form.addRow(self.tr("形状填充默认透明度:"), self.shape_fill_alpha_idle_spinbox)

        self.vertex_fill_color_button = self.create_color_button(['shape', 'vertex_fill_color'], self.config['shape']['vertex_fill_color'])
        right_form.addRow(self.tr("选中时顶点填充色:"), self.vertex_fill_color_button)

        # Alignment tool settings
        self.alignment_reference_color_button = self.create_color_button(['shape', 'alignment_reference_color'], self.config['shape'].get('alignment_reference_color', [255, 0, 255, 255]))
        right_form.addRow(self.tr("对齐工具参照颜色:"), self.alignment_reference_color_button)

        self.alignment_target_color_button = self.create_color_button(['shape', 'alignment_target_color'], self.config['shape'].get('alignment_target_color', [255, 165, 0, 255]))
        right_form.addRow(self.tr("对齐工具被执行颜色:"), self.alignment_target_color_button)

        self.alignment_reference_line_width_spinbox = QDoubleSpinBox()
        self.alignment_reference_line_width_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.alignment_reference_line_width_spinbox.setValue(self.config['shape'].get('alignment_reference_line_width', 4.0))
        self.alignment_reference_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'alignment_reference_line_width'], value))
        right_form.addRow(self.tr("对齐工具参照线宽度:"), self.alignment_reference_line_width_spinbox)

        self.alignment_target_line_width_spinbox = QDoubleSpinBox()
        self.alignment_target_line_width_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.alignment_target_line_width_spinbox.setValue(self.config['shape'].get('alignment_target_line_width', 2.0))
        self.alignment_target_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['shape', 'alignment_target_line_width'], value))
        right_form.addRow(self.tr("对齐工具被执行线宽度:"), self.alignment_target_line_width_spinbox)

        # Paste preview settings (虚影样式设置)
        self.paste_preview_line_width_spinbox = QDoubleSpinBox()
        self.paste_preview_line_width_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.paste_preview_line_width_spinbox.setRange(0.5, 10.0)
        self.paste_preview_line_width_spinbox.setSingleStep(0.5)
        self.paste_preview_line_width_spinbox.setValue(self.config.get('paste_preview_line_width', 2.0))
        self.paste_preview_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed('paste_preview_line_width', value))
        right_form.addRow(self.tr("虚影线条粗细:"), self.paste_preview_line_width_spinbox)

        self.paste_preview_opacity_spinbox = QDoubleSpinBox()
        self.paste_preview_opacity_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.paste_preview_opacity_spinbox.setRange(0.0, 1.0)
        self.paste_preview_opacity_spinbox.setSingleStep(0.1)
        self.paste_preview_opacity_spinbox.setValue(self.config.get('paste_preview_opacity', 0.4))
        self.paste_preview_opacity_spinbox.valueChanged.connect(lambda value: self._on_setting_changed('paste_preview_opacity', value))
        right_form.addRow(self.tr("虚影透明度:"), self.paste_preview_opacity_spinbox)

        self.paste_preview_fill_opacity_spinbox = QDoubleSpinBox()
        self.paste_preview_fill_opacity_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.paste_preview_fill_opacity_spinbox.setRange(0.0, 1.0)
        self.paste_preview_fill_opacity_spinbox.setSingleStep(0.1)
        self.paste_preview_fill_opacity_spinbox.setValue(self.config.get('paste_preview_fill_opacity', 0.3))
        self.paste_preview_fill_opacity_spinbox.valueChanged.connect(lambda value: self._on_setting_changed('paste_preview_fill_opacity', value))
        right_form.addRow(self.tr("虚影填充透明度:"), self.paste_preview_fill_opacity_spinbox)

        # Smart guides settings (辅助线样式设置)
        self.smart_guides_line_width_spinbox = QDoubleSpinBox()
        self.smart_guides_line_width_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.smart_guides_line_width_spinbox.setRange(0.5, 10.0)
        self.smart_guides_line_width_spinbox.setSingleStep(0.5)
        self.smart_guides_line_width_spinbox.setValue(self.config.get('smart_guides_line_width', 2.0))
        self.smart_guides_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed('smart_guides_line_width', value))
        right_form.addRow(self.tr("辅助线线条粗细:"), self.smart_guides_line_width_spinbox)

        self.smart_guides_opacity_spinbox = QDoubleSpinBox()
        self.smart_guides_opacity_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.smart_guides_opacity_spinbox.setRange(0.0, 1.0)
        self.smart_guides_opacity_spinbox.setSingleStep(0.1)
        self.smart_guides_opacity_spinbox.setValue(self.config.get('smart_guides_opacity', 0.8))
        self.smart_guides_opacity_spinbox.valueChanged.connect(lambda value: self._on_setting_changed('smart_guides_opacity', value))
        right_form.addRow(self.tr("辅助线透明度:"), self.smart_guides_opacity_spinbox)

        # Rectangle spacing guide settings (矩形间距线样式设置)
        self.spacing_guide_line_width_spinbox = QDoubleSpinBox()
        self.spacing_guide_line_width_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.spacing_guide_line_width_spinbox.setRange(0.5, 10.0)
        self.spacing_guide_line_width_spinbox.setSingleStep(0.5)
        self.spacing_guide_line_width_spinbox.setValue(self.config.get('spacing_guide_line_width', 2.0))
        self.spacing_guide_line_width_spinbox.valueChanged.connect(lambda value: self._on_setting_changed('spacing_guide_line_width', value))
        right_form.addRow(self.tr("间距线线条粗细:"), self.spacing_guide_line_width_spinbox)

        self.spacing_guide_opacity_spinbox = QDoubleSpinBox()
        self.spacing_guide_opacity_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.spacing_guide_opacity_spinbox.setRange(0.0, 1.0)
        self.spacing_guide_opacity_spinbox.setSingleStep(0.1)
        self.spacing_guide_opacity_spinbox.setValue(self.config.get('spacing_guide_opacity', 0.8))
        self.spacing_guide_opacity_spinbox.valueChanged.connect(lambda value: self._on_setting_changed('spacing_guide_opacity', value))
        right_form.addRow(self.tr("间距线透明度:"), self.spacing_guide_opacity_spinbox)

        # Canvas zoom settings (画布缩放设置)
        self.zoom_at_mouse_percentage_spinbox = QSpinBox()
        self.zoom_at_mouse_percentage_spinbox.setFixedWidth(SPINBOX_WIDTH)
        self.zoom_at_mouse_percentage_spinbox.setRange(1, 9999)
        self.zoom_at_mouse_percentage_spinbox.setSingleStep(5)
        self.zoom_at_mouse_percentage_spinbox.setValue(self.config.get('canvas', {}).get('zoom_at_mouse_percentage_increase', 20))
        self.zoom_at_mouse_percentage_spinbox.valueChanged.connect(lambda value: self._on_setting_changed(['canvas', 'zoom_at_mouse_percentage_increase'], value))
        right_form.addRow(self.tr("鼠标缩放倍率(%):"), self.zoom_at_mouse_percentage_spinbox)

        # 将左列添加到水平布局
        columns_layout.addLayout(left_form)
        columns_layout.addSpacing(5)  # 左列和分隔线之间5像素

        # 添加垂直分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setLineWidth(1)
        columns_layout.addWidget(separator)

        columns_layout.addSpacing(5)  # 分隔线和右列之间5像素
        # 将右列添加到水平布局
        columns_layout.addLayout(right_form)

        layout.addLayout(columns_layout)

        # 自动调整对话框大小以适应内容
        self.adjustSize()
        self.setFixedSize(self.sizeHint())

    def tr(self, text):
        return QCoreApplication.translate("ColorManagerDialog", text)

    def create_color_button(self, key, color):
        button = QPushButton()
        button.setFixedSize(60, 25)  # 缩小颜色按钮
        if isinstance(color, str):
            self.color_formats[str(key)] = 'hex'
            button.setStyleSheet(f"background-color: {color}")
        else:
            # 将列表格式的颜色转换为十六进制格式，避免CSS解析错误
            if len(color) == 3:
                r, g, b = color
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
            elif len(color) == 4:
                r, g, b, a = color
                # Qt的CSS不支持alpha，所以只使用RGB部分
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
            else:
                hex_color = "#000000"

            self.color_formats[str(key)] = 'rgba' if len(color) == 4 else 'rgb'
            button.setStyleSheet(f"background-color: {hex_color}")
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
