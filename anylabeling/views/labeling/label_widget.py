import functools
import html
import json
import math
import math
import os
import os.path as osp
import re
import shutil
from typing import Optional, List, Dict, Any, Union, Tuple

import cv2
import numpy as np
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QDockWidget,
    QGridLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWhatsThis,
    QWidget,
    QMessageBox,
    QScrollArea,
)

from anylabeling.services.auto_labeling.types import AutoLabelingMode
from anylabeling.services.auto_labeling import _THUMBNAIL_RENDER_MODELS
from anylabeling.views.training import UltralyticsDialog

from ...app_info import (
    __appname__,
    __version__,
    __preferred_device__,
)
from . import utils
from ...config import get_config, save_config
from .label_file import LabelFile, LabelFileError
from .logger import logger
from .shape import Shape
from .widgets import (
    AboutDialog,
    AutoLabelingWidget,
    BrightnessContrastDialog,
    Canvas,
    ChatbotDialog,
    VQADialog,
    CrosshairSettingsDialog,
    FileDialogPreview,
    GroupIDFilterComboBox,
    LabelDialog,
    LabelFilterComboBox,
    LabelListWidget,
    LabelListWidgetItem,
    DigitShortcutDialog,
    LabelToggleShortcutDialog,
    LabelModifyDialog,
    ObjectManagerDialog,
    GroupIDModifyDialog,
    OverviewDialog,
    Popup,
    SearchBar,
    ToolBar,
    UniqueLabelQListWidget,
    ZoomWidget,
    NavigatorWidget,
    NavigatorDialog,
    ExpandMarginsDialog,
    LabelCategoryWidget,
    MergeDialog,
    LabelToolDialog,
    TagSortDialog,
    AngleCorrectionDialog,
    KeymapDialog,
    AlignmentDialog,
)
from ...services import merger, tag_sorting

LABEL_COLORMAP = utils.label_colormap()
LABEL_OPACITY = 128

class MergeThread(QtCore.QThread):
    progress = QtCore.pyqtSignal(int, str)
    finished = QtCore.pyqtSignal(str)

    def __init__(self, files, config, parent=None):
        super().__init__(parent)
        self.files = files
        self.config = config

    def run(self):
        success_count = 0
        fail_count = 0
        total_files = len(self.files)
        
        for i, file_path in enumerate(self.files):
            if self.isInterruptionRequested():
                break
            
            label_file = os.path.splitext(file_path)[0] + ".json"
            
            self.progress.emit(i, f"正在处理: {os.path.basename(label_file)}")
            
            success, message = merger.process_file(label_file, self.config)
            if success:
                success_count += 1
            else:
                fail_count += 1
        
        if self.isInterruptionRequested():
            final_message = "操作被用户取消。"
        else:
            final_message = f"处理完成！\n成功修改 {success_count} 个文件。"
            if fail_count > 0:
                final_message += f"\n{fail_count} 个文件处理失败或无需处理。"
        
        self.finished.emit(final_message)


class TagSortThread(QtCore.QThread):
    progress = QtCore.pyqtSignal(int, int, object)
    finished = QtCore.pyqtSignal(list, bool)

    def __init__(self, files, options, parent=None):
        super().__init__(parent)
        self.files = list(files)
        self.options = options
        self._cancelled = False

    def run(self):
        outcomes = []
        total = len(self.files)
        for index, file_path in enumerate(self.files, start=1):
            if self.isInterruptionRequested():
                self._cancelled = True
                break
            outcome = tag_sorting.sort_json_file(file_path, self.options)
            outcomes.append(outcome)
            self.progress.emit(index, total, outcome)
        self.finished.emit(outcomes, self._cancelled)


class LabelingWidget(QtWidgets.QWidget):
    """The main widget for labeling images"""

    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = 0, 1, 2
    next_files_changed = QtCore.pyqtSignal(list)
    shape_list_changed = QtCore.pyqtSignal()

    def __init__(  # noqa: C901
        self,
        parent=None,
        config=None,
        filename=None,
        output=None,
        output_file=None,
        output_dir=None,
    ):
        self.parent = parent
        super().__init__(parent=parent)
        if output is not None:
            logger.warning(
                "argument output is deprecated, use output_file instead"
            )
            if output_file is None:
                output_file = output

        self.filename = None
        self.image_path = None
        self.image_data = None
        self.label_file = None
        self.other_data = {}
        self.classes_file = None
        self.attributes = {}
        self.current_category = None
        self.selected_polygon_stack = []

        # Alignment tool state
        self.alignment_dialog = None
        self.reference_shape = None
        self.is_reference_selection_mode = False
        self.supported_shape = Shape.get_supported_shape()
        self.label_info = {}
        self.image_flags = []
        self.fn_to_index = {}
        self.cache_auto_label = None
        self.cache_auto_label_group_id = None
        self.object_manager_dialog = None
        self.expand_margins_dialog = None
        self.merge_tool_dialog = None
        self.merge_progress_dialog = None
        self.label_tool_dialog = None
        self.tag_sort_dialog = None
        self.angle_correction_dialog = None
        self.mask_generator_dialog = None
        self.keymap_dialog = None # New dialog instance
        self.tag_sort_thread = None
        self.tag_sort_scope = None
        self.tag_sort_files = []
        self.tag_sort_total = 0
        self.tag_sort_last_payload = None
        self._crosshair_was_toggled_for_drawing = False

        # see configs/anylabeling_config.yaml for valid configuration
        if config is None:
            config = get_config()
        self._config = config
        self.label_flags = self._config["label_flags"]
        self.label_loop_count = -1
        self.digit_to_label = None
        self.drawing_digit_shortcuts = self._config.get("digit_shortcuts", {})

        self.label_toggle_shortcuts = self._config.get("label_toggle_shortcuts", {})
        self.label_toggle_qshortcuts = []
        self.load_label_toggle_shortcuts()

        Shape.highlighting_enabled = False

        # Load alpha settings for shape fill
        Shape.alpha_idle = self._config["shape"].get("shape_fill_alpha_idle", 50)
        Shape.alpha_highlight = self._config["shape"].get("shape_fill_alpha_highlight", 180)

        # set default shape colors
        Shape.line_color = QtGui.QColor(*self._config["shape"]["line_color"])
        Shape.fill_color = QtGui.QColor(*self._config["shape"]["fill_color"])
        Shape.select_line_color = QtGui.QColor(
            *self._config["shape"]["select_line_color"]
        )
        Shape.canvas_select_line_color = QtGui.QColor(
            *self._config["shape"]["canvas_select_line_color"]
        )
        Shape.canvas_hover_line_color = QtGui.QColor(
            *self._config["shape"]["canvas_hover_line_color"]
        )
        Shape.select_fill_color = QtGui.QColor(
            *self._config["shape"]["select_fill_color"]
        )
        Shape.vertex_fill_color = QtGui.QColor(
            *self._config["shape"]["vertex_fill_color"]
        )
        Shape.hvertex_fill_color = QtGui.QColor(
            *self._config["shape"]["hvertex_fill_color"]
        )

        # Set point size from config file
        Shape.point_size = self._config["shape"]["point_size"]
        # Set line width from config file
        Shape.line_width = self._config["shape"]["line_width"]
        # Optional specific widths for interaction states
        Shape.select_line_width = self._config["shape"].get("select_line_width")
        Shape.canvas_select_line_width = self._config["shape"].get("canvas_select_line_width")
        Shape.canvas_hover_line_width = self._config["shape"].get("canvas_hover_line_width")

        # Whether we need to save or not.
        self.dirty = False

        self._no_selection_slot = False
        self._programmatic_selection_change = False
        self._copied_shapes = None
        self._batch_edit_warning_shown = False

        self.brightness_contrast_dialog = BrightnessContrastDialog(
            self.on_new_brightness_contrast, parent=self
        )

        # Main widgets and related state.
        self.label_dialog = LabelDialog(
            parent=self,
            labels=self._config["labels"],
            sort_labels=self._config["sort_labels"],
            show_text_field=self._config["show_label_text_field"],
            completion=self._config["label_completion"],
            fit_to_content=self._config["fit_to_content"],
            flags=self.label_flags,
        )

        self.label_list = LabelListWidget()
        self.last_open_dir = None

        self.flag_dock = self.flag_widget = None
        self.flag_dock = QtWidgets.QDockWidget(self.tr("Flags"), self)
        self.flag_dock.setObjectName("Flags")
        self.flag_widget = QtWidgets.QListWidget()
        if config["flags"]:
            self.image_flags = config["flags"]
            self.load_flags({k: False for k in self.image_flags})
        else:
            self.flag_dock.hide()
        self.flag_dock.setWidget(self.flag_widget)
        self.flag_widget.itemChanged.connect(self.set_dirty)
        self.flag_dock.setStyleSheet(
            "QDockWidget::title {" "text-align: center;" "padding: 0px;" "}"
        )

        # Create and add combobox for showing unique labels or group ids in group
        self.label_filter_combobox = LabelFilterComboBox(self)
        self.gid_filter_combobox = GroupIDFilterComboBox(self)

        self.label_list.item_selection_changed.connect(
            self.label_selection_changed
        )
        self.label_list.item_double_clicked.connect(self.edit_label)
        self.label_list.item_changed.connect(self.label_item_changed)
        self.label_list.item_dropped.connect(self.label_order_changed)
        self.shape_dock = QtWidgets.QDockWidget(self.tr("Objects"), self)
        
        # 创建对象控制按钮
        shape_control_widget = QtWidgets.QWidget()
        shape_control_layout = QtWidgets.QHBoxLayout()
        shape_control_layout.setContentsMargins(2, 2, 2, 2)
        shape_control_layout.setSpacing(2)
        
        btn_select_all_shapes = QtWidgets.QPushButton(self.tr("全选"))
        def select_all_objects():
            for item in self.label_list:
                item.setCheckState(Qt.Checked)
        btn_select_all_shapes.clicked.connect(select_all_objects)

        btn_invert_selection_shapes = QtWidgets.QPushButton(self.tr("反选"))
        def invert_all_objects():
            for item in self.label_list:
                item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)
        btn_invert_selection_shapes.clicked.connect(invert_all_objects)

        btn_deselect_all_shapes = QtWidgets.QPushButton(self.tr("取消"))
        def deselect_all_objects():
            for item in self.label_list:
                item.setCheckState(Qt.Unchecked)
        btn_deselect_all_shapes.clicked.connect(deselect_all_objects)
        
        # 高亮按钮
        self._highlight_on = False
        btn_highlight = QtWidgets.QPushButton(self.tr("高亮"))
        btn_highlight.setCheckable(True)
        def toggle_highlight():
            self._highlight_on = not self._highlight_on
            Shape.highlighting_enabled = self._highlight_on
            for item in self.label_list:
                shape = item.shape()
                shape.selected = self._highlight_on
            self.canvas.update()
        btn_highlight.clicked.connect(toggle_highlight)

        # Set shortcuts from config
        shortcuts = self._config.get("shortcuts", {})
        btn_select_all_shapes.setShortcut(shortcuts.get("select_all_shapes", ""))
        btn_invert_selection_shapes.setShortcut(shortcuts.get("invert_selection_shapes", ""))
        btn_deselect_all_shapes.setShortcut(shortcuts.get("deselect_all_shapes", ""))
        btn_highlight.setShortcut(shortcuts.get("toggle_highlight", ""))

        shape_control_layout.addWidget(btn_select_all_shapes)
        shape_control_layout.addWidget(btn_invert_selection_shapes)
        shape_control_layout.addWidget(btn_deselect_all_shapes)
        shape_control_layout.addWidget(btn_highlight)
        shape_control_layout.addStretch()
        shape_control_widget.setLayout(shape_control_layout)
        
        shape_container = QtWidgets.QWidget()
        shape_layout = QtWidgets.QVBoxLayout()
        shape_layout.setContentsMargins(0, 0, 0, 0)
        shape_layout.setSpacing(2)
        shape_layout.addWidget(shape_control_widget)
        shape_layout.addWidget(self.label_list)
        shape_container.setLayout(shape_layout)
        
        self.shape_dock.setWidget(shape_container)
        self.shape_dock.setStyleSheet(
            "QDockWidget::title {" "text-align: center;" "padding: 0px;" "}"
        )
        self.shape_dock.setTitleBarWidget(QtWidgets.QWidget())
        if self.shape_dock.titleBarWidget():
            self.shape_dock.titleBarWidget().installEventFilter(self)

        self.unique_label_list = UniqueLabelQListWidget(self)
        self.unique_label_list.setToolTip(
            self.tr(
                "Click labels to toggle visibility. "
                "Press 'Esc' to deselect."
            )
        )
        # 连接标签可见性变化信号
        self.unique_label_list.label_visibility_changed.connect(
            self.update_label_visibility
        )
        self.unique_label_list.labels_ordered.connect(self.on_labels_ordered)
        # 创建标签控制按钮
        self.create_label_control_buttons()

        self.label_dock = QtWidgets.QDockWidget(self.tr("Labels"), self)
        self.label_dock.setObjectName("Labels")
        
        # 创建标签容器widget
        label_container = QtWidgets.QWidget()
        label_layout = QtWidgets.QVBoxLayout()
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(2)
        
        # 添加控制按钮
        label_layout.addWidget(self.label_control_widget)
        # 添加标签列表
        label_layout.addWidget(self.unique_label_list)
        
        label_container.setLayout(label_layout)
        self.label_dock.setWidget(label_container)
        
        self.label_dock.setStyleSheet(
            "QDockWidget::title {" "text-align: center;" "padding: 0px;" "}"
        )

        self.file_search = SearchBar()
        self.file_search.setPlaceholderText(self.tr("Search Filename"))
        self.file_search.textChanged.connect(self.file_search_changed)
        self.file_list_widget = QtWidgets.QListWidget()
        self.file_list_widget.itemSelectionChanged.connect(
            self.file_selection_changed
        )
        file_list_layout = QtWidgets.QVBoxLayout()
        file_list_layout.setContentsMargins(0, 4, 0, 0)
        file_list_layout.setSpacing(4)
        file_list_layout.addWidget(self.file_search)
        file_list_layout.addWidget(self.file_list_widget)
        self.file_dock = QtWidgets.QDockWidget("", self)
        self.file_dock.setObjectName("Files")
        self.file_dock.setTitleBarWidget(QtWidgets.QWidget(self))
        file_list_widget = QtWidgets.QWidget()
        file_list_widget.setLayout(file_list_layout)
        self.file_dock.setWidget(file_list_widget)
        self.file_dock.setStyleSheet(
            "QDockWidget::title {" "text-align: center;" "padding: 0px;" "}"
        )

        self.zoom_widget = ZoomWidget()
        
        # Create navigator dialog with settings and config
        # Note: Create settings early for navigator dialog use
        if not hasattr(self, 'settings'):
            self.settings = QtCore.QSettings("anylabeling", "anylabeling")
        self.navigator_dialog = NavigatorDialog(self, settings=self.settings, config=self._config)
        self.navigator_dialog.navigator.set_colors(
            select_line_color=QtGui.QColor(
                *self._config["shape"]["navigator_select_line_color"]
            ),
            hover_line_color=QtGui.QColor(
                *self._config["shape"]["navigator_hover_line_color"]
            ),
        )
        self.navigator_dialog.navigator.navigation_requested.connect(
            self.on_navigator_request
        )
        # 连接导航器关闭事件
        self.navigator_dialog.closeEvent = self._navigator_close_event
        # Connect zoom controls - both overloads
        self.navigator_dialog.zoom_changed[int].connect(
            lambda zoom: self.on_navigator_zoom_changed(zoom, None)
        )
        self.navigator_dialog.zoom_changed[int, QtCore.QPoint].connect(
            self.on_navigator_zoom_changed
        )
        # Connect viewport update signal
        self.navigator_dialog.viewport_update_requested.connect(
            self.on_navigator_viewport_update_requested
        )
        
        self.setAcceptDrops(True)

        self.canvas = self.label_list.canvas = Canvas(
            parent=self,
            epsilon=self._config["epsilon"],
            double_click=self._config["canvas"]["double_click"],
            num_backups=self._config["canvas"]["num_backups"],
            wheel_rectangle_editing=self._config["canvas"][
                "wheel_rectangle_editing"
            ],
            config=self._config,
        )
        self.canvas.zoom_request.connect(self.zoom_request)

        self.load_labels(self._config["labels"])

        scroll_area = QScrollArea()
        scroll_area.setWidget(self.canvas)
        scroll_area.setWidgetResizable(True)
        self.scroll_bars = {
            Qt.Vertical: scroll_area.verticalScrollBar(),
            Qt.Horizontal: scroll_area.horizontalScrollBar(),
        }
        
        # Connect scrollbar value changes to update navigator
        self.scroll_bars[Qt.Vertical].valueChanged.connect(
            lambda: self.update_navigator_viewport()
        )
        self.scroll_bars[Qt.Horizontal].valueChanged.connect(
            lambda: self.update_navigator_viewport()
        )
        self.canvas.scroll_request.connect(self.scroll_request)
        self.canvas.new_shape.connect(self.new_shape)
        self.canvas.show_shape.connect(self.show_shape)
        self.canvas.shape_moved.connect(self.set_dirty)
        self.canvas.shape_rotated.connect(self.set_dirty)
        self.canvas.selection_changed.connect(self.shape_selection_changed)

        # Connect shape modifications to update navigator title
        self.canvas.shape_moved.connect(self._update_navigator_title_with_selection)
        self.canvas.shape_rotated.connect(self._update_navigator_title_with_selection)
        self.canvas.drawing_polygon.connect(self.toggle_drawing_sensitive)
        self.canvas.drawing_cancelled.connect(self.on_drawing_cancelled)
        # [Feature] support for automatically switching to editing mode
        # when the cursor moves over an object
        self.canvas.h_shape_is_hovered = self._config.get(
            "auto_highlight_shape", False
        )
        if self._config["auto_switch_to_edit_mode"]:
            self.canvas.mode_changed.connect(self.set_edit_mode)

        # Crosshair
        self.crosshair_settings = self._config["canvas"]["crosshair"]
        self.canvas.set_cross_line(**self.crosshair_settings)

        self._central_widget = scroll_area

        features = QtWidgets.QDockWidget.DockWidgetFeatures()
        for dock in ["flag_dock", "label_dock", "shape_dock", "file_dock"]:
            if self._config[dock]["closable"]:
                features = features | QtWidgets.QDockWidget.DockWidgetClosable
            if self._config[dock]["floatable"]:
                features = features | QtWidgets.QDockWidget.DockWidgetFloatable
            if self._config[dock]["movable"]:
                features = features | QtWidgets.QDockWidget.DockWidgetMovable
            getattr(self, dock).setFeatures(features)
            if self._config[dock]["show"] is False:
                getattr(self, dock).setVisible(False)

        # Actions
        action = functools.partial(utils.new_action, self)
        shortcuts = self._config["shortcuts"]

        open_ = action(
            self.tr("&Open File"),
            self.open_file,
            shortcuts["open"],
            "file",
            self.tr("Open image or label file"),
        )
        openvideo = action(
            self.tr("&Open Video"),
            lambda: utils.open_video_file(self),
            shortcuts["open_video"],
            "video",
            self.tr("Open video file"),
        )
        opendir = action(
            self.tr("&Open Dir"),
            self.open_folder_dialog,
            shortcuts["open_dir"],
            "open",
            self.tr("Open Dir"),
        )
        load_subfolders_action = action(
            text=self.tr("加载子文件夹"),
            slot=lambda x: self._config.update({"load_subfolders": x}),
            icon=None,
            tip=self.tr("加载所选文件夹的所有子文件夹中的图像"),
            checkable=True,
            enabled=True,
            checked=self._config.get("load_subfolders", False),
        )
        open_next_image = action(
            self.tr("&Next Image"),
            self.open_next_image,
            shortcuts["open_next"],
            "next",
            self.tr("Open next image"),
            enabled=False,
        )
        open_prev_image = action(
            self.tr("&Prev Image"),
            self.open_prev_image,
            shortcuts["open_prev"],
            "prev",
            self.tr("Open prev image"),
            enabled=False,
        )
        open_next_unchecked_image = action(
            self.tr("&Next Unchecked Image"),
            self.open_next_unchecked_image,
            shortcuts["open_next_unchecked"],
            "next",
            self.tr("Open next unchecked image"),
            enabled=False,
        )
        open_prev_unchecked_image = action(
            self.tr("&Prev Unchecked Image"),
            self.open_prev_unchecked_image,
            shortcuts["open_prev_unchecked"],
            "prev",
            self.tr("Open previous unchecked image"),
            enabled=False,
        )
        save = action(
            self.tr("&Save"),
            self.save_file,
            shortcuts["save"],
            "save",
            self.tr("Save labels to file"),
            enabled=False,
        )
        save_as = action(
            self.tr("&Save As"),
            self.save_file_as,
            shortcuts["save_as"],
            "save-as",
            self.tr("Save labels to a different file"),
            enabled=False,
        )
        run_all_images = action(
            self.tr("&Auto Run"),
            lambda: utils.run_all_images(self),
            shortcuts["auto_run"],
            "auto-run",
            self.tr("Auto run all images at once"),
            checkable=True,
            enabled=False,
        )
        delete_file = action(
            self.tr("&Delete File"),
            self.delete_file,
            shortcuts["delete_file"],
            "delete",
            self.tr("Delete current label file"),
            enabled=False,
        )
        delete_image_file = action(
            self.tr("&Delete Image File"),
            self.delete_image_file,
            shortcuts["delete_image_file"],
            "delete",
            self.tr("Delete current image file"),
            enabled=True,
        )

        change_output_dir = action(
            self.tr("&Change Output Dir"),
            slot=self.change_output_dir_dialog,
            shortcut=shortcuts["save_to"],
            icon="open",
            tip=self.tr("Change where annotations are loaded/saved"),
        )

        save_auto = action(
            text=self.tr("Save &Automatically"),
            slot=lambda x: self._config.update({"auto_save": x}),
            icon=None,
            tip=self.tr("Save automatically"),
            checkable=True,
            enabled=True,
            checked=self._config["auto_save"],
        )

        save_with_image_data = action(
            text=self.tr("Save With Image Data"),
            slot=lambda x: self._config.update({"store_data": x}),
            icon=None,
            tip=self.tr("Save image data in label file"),
            checkable=True,
            checked=self._config["store_data"],
        )

        close = action(
            self.tr("&Close"),
            self.close_file,
            shortcuts["close"],
            "cancel",
            self.tr("Close current file"),
        )

        keep_prev_mode = action(
            self.tr("Keep Previous Annotation"),
            lambda x: self._config.update({"keep_prev": x}),
            shortcuts["toggle_keep_prev_mode"],
            None,
            self.tr('Toggle "Keep Previous Annotation" mode'),
            checkable=True,
            checked=self._config["keep_prev"],
        )

        auto_use_last_label_mode = action(
            self.tr("Auto Use Last Label"),
            lambda x: self._config.update({"auto_use_last_label": x}),
            shortcuts["toggle_auto_use_last_label"],
            None,
            self.tr('Toggle "Auto Use Last Label" mode'),
            checkable=True,
            checked=self._config["auto_use_last_label"],
        )

        use_system_clipboard = action(
            self.tr("Use System Clipboard"),
            self.toggle_system_clipboard,
            tip=self.tr("Use system clipboard for copy and paste"),
            checkable=True,
            checked=self._config["system_clipboard"],
            enabled=True,
        )

        visibility_shapes_mode = action(
            self.tr("Visibility Shapes"),
            self.toggle_visibility_shapes,
            shortcuts["toggle_visibility_shapes"],
            None,
            self.tr('Toggle "Visibility Shapes" mode'),
            checkable=True,
            checked=self._config["show_shapes"],
        )

        create_mode = action(
            self.tr("Create Polygons"),
            lambda: self.toggle_draw_mode(False, create_mode="polygon"),
            shortcuts["create_polygon"],
            "polygon",
            self.tr("Start drawing polygons"),
            enabled=False,
        )
        create_rectangle_mode = action(
            self.tr("Create Rectangle"),
            lambda: self.toggle_draw_mode(False, create_mode="rectangle"),
            shortcuts["create_rectangle"],
            "rectangle",
            self.tr("Start drawing rectangles"),
            enabled=False,
        )
        create_rotation_mode = action(
            self.tr("Create Rotation"),
            lambda: self.toggle_draw_mode(False, create_mode="rotation"),
            shortcuts["create_rotation"],
            "rotation",
            self.tr("Start drawing rotations"),
            enabled=False,
        )
        create_rotation3_mode = action(
            "创建旋转框（三次点击）",
            lambda: self.toggle_draw_mode(False, create_mode="rotation3"),
            shortcuts.get("create_rotation3", "H"),  # 默认快捷键 H（象形"工"字）
            "rotation",  # 使用 rotation 图标
            "三次点击绘制旋转框（绿点 → 红色箭头 → 宽度）",
            enabled=False,
        )
        create_circle_mode = action(
            self.tr("Create Circle"),
            lambda: self.toggle_draw_mode(False, create_mode="circle"),
            shortcuts["create_circle"],
            "circle",
            self.tr("Start drawing circles"),
            enabled=False,
        )
        create_line_mode = action(
            self.tr("Create Line"),
            lambda: self.toggle_draw_mode(False, create_mode="line"),
            shortcuts["create_line"],
            "line",
            self.tr("Start drawing lines"),
            enabled=False,
        )
        create_point_mode = action(
            self.tr("Create Point"),
            lambda: self.toggle_draw_mode(False, create_mode="point"),
            shortcuts["create_point"],
            "point",
            self.tr("Start drawing points"),
            enabled=False,
        )
        create_line_strip_mode = action(
            self.tr("Create LineStrip"),
            lambda: self.toggle_draw_mode(False, create_mode="linestrip"),
            shortcuts["create_linestrip"],
            "line-strip",
            self.tr("Start drawing linestrip. Ctrl+LeftClick ends creation."),
            enabled=False,
        )
        digit_shortcut_0 = action(
            self.tr("Digit Shortcut 0"),
            lambda: self.create_digit_mode(0),
            "0",
            "digit0",
            enabled=False,
        )
        digit_shortcut_1 = action(
            self.tr("Digit Shortcut 1"),
            lambda: self.create_digit_mode(1),
            "1",
            "digit1",
            enabled=False,
        )
        digit_shortcut_2 = action(
            self.tr("Digit Shortcut 2"),
            lambda: self.create_digit_mode(2),
            "2",
            "digit2",
            enabled=False,
        )
        digit_shortcut_3 = action(
            self.tr("Digit Shortcut 3"),
            lambda: self.create_digit_mode(3),
            "3",
            "digit3",
            enabled=False,
        )
        digit_shortcut_4 = action(
            self.tr("Digit Shortcut 4"),
            lambda: self.create_digit_mode(4),
            "4",
            "digit4",
            enabled=False,
        )
        digit_shortcut_5 = action(
            self.tr("Digit Shortcut 5"),
            lambda: self.create_digit_mode(5),
            "5",
            "digit5",
            enabled=False,
        )
        digit_shortcut_6 = action(
            self.tr("Digit Shortcut 6"),
            lambda: self.create_digit_mode(6),
            "6",
            "digit6",
            enabled=False,
        )
        digit_shortcut_7 = action(
            self.tr("Digit Shortcut 7"),
            lambda: self.create_digit_mode(7),
            "7",
            "digit7",
            enabled=False,
        )
        digit_shortcut_8 = action(
            self.tr("Digit Shortcut 8"),
            lambda: self.create_digit_mode(8),
            "8",
            "digit8",
            enabled=False,
        )
        digit_shortcut_9 = action(
            self.tr("Digit Shortcut 9"),
            lambda: self.create_digit_mode(9),
            "9",
            "digit9",
            enabled=False,
        )
        edit_mode = action(
            self.tr("Edit Object"),
            self.set_edit_mode,
            shortcuts["edit_polygon"],
            "edit",
            self.tr("Move and edit the selected polygons"),
            enabled=False,
        )
        group_selected_shapes = action(
            self.tr("Group Selected Shapes"),
            self.group_selected_shapes,
            shortcuts["group_selected_shapes"],
            None,
            self.tr("Group shapes by assigning a same group_id"),
            enabled=True,
        )
        ungroup_selected_shapes = action(
            self.tr("Ungroup Selected Shapes"),
            self.ungroup_selected_shapes,
            shortcuts["ungroup_selected_shapes"],
            None,
            self.tr("Ungroup shapes"),
            enabled=True,
        )

        delete = action(
            self.tr("Delete"),
            self.delete_selected_shape,
            shortcuts["delete_polygon"],
            "cancel",
            self.tr("Delete the selected polygons"),
            enabled=False,
        )
        duplicate = action(
            self.tr("Duplicate Polygons"),
            self.duplicate_selected_shape,
            shortcuts["duplicate_polygon"],
            "copy",
            self.tr("Create a duplicate of the selected polygons"),
            enabled=False,
        )
        copy = action(
            self.tr("Copy Object"),
            self.copy_selected_shape,
            shortcuts["copy_polygon"],
            "copy",
            self.tr("Copy selected polygons to clipboard"),
            enabled=False,
        )
        paste = action(
            self.tr("Paste Object"),
            self.paste_selected_shape,
            shortcuts["paste_polygon"],
            "paste",
            self.tr("Paste copied polygons"),
            enabled=self._config["system_clipboard"],
        )
        undo_last_point = action(
            self.tr("Undo last point"),
            self.canvas.undo_last_point,
            shortcuts["undo_last_point"],
            "undo",
            self.tr("Undo last drawn point"),
            enabled=False,
        )
        remove_point = action(
            text=self.tr("Remove Selected Point"),
            slot=self.remove_selected_point,
            shortcut=shortcuts["remove_selected_point"],
            icon="edit",
            tip=self.tr("Remove selected point from polygon"),
            enabled=False,
        )

        undo = action(
            self.tr("Undo"),
            self.undo_shape_edit,
            shortcuts["undo"],
            "undo",
            self.tr("Undo last add and edit of shape"),
            enabled=False,
        )
        hide_selected_polygons = action(
            self.tr("Hide Selected Polygons"),
            self.hide_selected_polygons,
            shortcuts["hide_selected_polygons"],
            None,
            self.tr("Hide selected polygons"),
            enabled=True,
        )
        show_hidden_polygons = action(
            self.tr("Show Hidden Polygons"),
            self.show_hidden_polygons,
            shortcuts["show_hidden_polygons"],
            None,
            self.tr("Show hidden polygons"),
            enabled=True,
        )

        overview = action(
            self.tr("&Overview"),
            self.overview,
            shortcuts["show_overview"],
            icon="overview",
            tip=self.tr("Show annotations statistics"),
        )
        save_crop = action(
            self.tr("&Save Cropped Image"),
            lambda: utils.save_crop(self),
            icon="crop",
            tip=self.tr(
                "Save cropped image. (Support rectangle/rotation/polygon shape_type)"
            ),
        )
        digit_shortcut_manager = action(
            self.tr("&Digit Shortcut Manager"),
            self.digit_shortcut_manager,
            shortcuts["edit_digit_shortcut"],
            icon="edit",
            tip=self.tr(
                "Manage Digit Shortcuts: Assign Drawing Modes and Labels to Number Keys"
            ),
        )
        label_toggle_shortcut_manager = action(
            self.tr("标签切换快捷键管理器"),
            self.open_label_toggle_shortcut_manager,
            icon="edit",
            tip=self.tr("管理用于切换标签可见性的快捷键"),
        )

        label_manager = action(
            self.tr("&Label Manager"),
            self.label_manager,
            icon="edit",
            tip=self.tr("Manage Labels: Rename, Delete, Adjust Color"),
        )
        object_manager = action(
            self.tr("标签页管理器"),
            self.object_manager,
            shortcuts["object_manager"],
            icon="objects",
            tip=self.tr("在新窗口中管理和重排序当前页的对象"),
        )
        gid_manager = action(
            self.tr("&Group ID Manager"),
            self.gid_manager,
            shortcuts["edit_group_id"],
            icon="edit",
            tip=self.tr("Manage Group ID"),
        )
        union_selection = action(
            self.tr("&Union Selection"),
            self.union_selection,
            shortcuts["union_selected_shapes"],
            icon="union",
            tip=self.tr("Union multiple selected rectangle shapes"),
            enabled=False,
        )
        hbb_to_obb = action(
            self.tr("&Convert HBB to OBB"),
            lambda: utils.shape_conversion(self, "hbb_to_obb"),
            icon="convert",
            tip=self.tr(
                "Perform conversion from horizontal bounding box to oriented bounding box"
            ),
        )
        obb_to_hbb = action(
            self.tr("&Convert OBB to HBB"),
            lambda: utils.shape_conversion(self, "obb_to_hbb"),
            icon="convert",
            tip=self.tr(
                "Perform conversion from oriented bounding box to horizontal bounding box"
            ),
        )
        polygon_to_hbb = action(
            self.tr("&Convert Polygon to HBB"),
            lambda: utils.shape_conversion(self, "polygon_to_hbb"),
            icon="convert",
            tip=self.tr(
                "Perform conversion from polygon to horizontal bounding box"
            ),
        )
        polygon_to_obb = action(
            self.tr("&Convert Polygon to OBB"),
            lambda: utils.shape_conversion(self, "polygon_to_obb"),
            icon="convert",
            tip=self.tr(
                "Perform conversion from polygon to oriented bounding box"
            ),
        )
        expand_margins = action(
            self.tr("标注框边距扩展工具"),
            self.open_expand_margins_dialog,
            shortcuts["expand_margins"],
            icon="edit",
            tip=self.tr("批量扩展或收缩标注框的边距"),
        )
        tag_sort_tool = action(
            self.tr("标签排序工具"),
            self.open_tag_sort_dialog,
            icon="edit",
            tip=self.tr("根据排序规则批量调整标注标签顺序"),
        )
        angle_correction_tool = action(
            self.tr("旋转框角度修正工具"),
            self.open_angle_correction_dialog,
            icon="rotation",
            tip=self.tr("批量修正旋转框的角度"),
        )

        alignment_tool = action(
            self.tr("矩形对齐工具"),
            self.open_alignment_dialog,
            icon="edit",
            tip=self.tr("对齐或统一多个矩形的尺寸和位置"),
        )
        merge_shapes = action(
            self.tr("区域合并工具"),
            self.open_merge_tool,
            icon="union",
            tip=self.tr("根据规则合并标注对象"),
        )
        dual_color_label_tool = action(
            self.tr("双色标签工具"),
            self.open_label_tool,
            icon="edit",
            tip=self.tr("转换或还原双色标签"),
        )
        mask_generator_tool = action(
            self.tr("MASK生成"),
            self.open_mask_generator,
            icon="edit",
            tip=self.tr("使用CTD模型生成文字区域掩膜"),
        )

        keymap_tool = action(
            self.tr("旋转标签快捷键管理器"),
            self.open_keymap_dialog,
            shortcuts.get("keymap_dialog"),
            icon="edit", # Using a generic edit icon for now
            tip=self.tr("管理旋转标签的快捷键映射"),
        )
        self.addAction(keymap_tool) # Explicitly add action to widget for shortcut recognition

        open_chatbot = action(
            self.tr("ChatBot"),
            self.open_chatbot,
            shortcuts["open_chatbot"],
            icon="chatbot",
            tip=self.tr("Open chatbot dialog"),
        )
        open_vqa = action(
            self.tr("VQA"),
            self.open_vqa,
            shortcuts["open_vqa"],
            icon="vqa",
            tip=self.tr("Open VQA dialog"),
        )

        documentation = action(
            self.tr("&Documentation"),
            self.documentation,
            icon="docs",
            tip=self.tr("Show documentation"),
        )
        about = action(
            self.tr("&About"),
            self.about,
            icon="help",
            tip=self.tr("Open about dialog"),
        )

        loop_thru_labels = action(
            self.tr("&Loop through labels"),
            self.loop_thru_labels,
            shortcut=shortcuts["loop_thru_labels"],
            icon="loop",
            tip=self.tr("Loop through labels"),
            enabled=False,
        )

        ultralytics_train = action(
            "Ultralytics",
            lambda: self.start_training("ultralytics"),
            icon="ultralytics",
        )

        zoom = QtWidgets.QWidgetAction(self)
        zoom.setDefaultWidget(self.zoom_widget)
        self.zoom_widget.setWhatsThis(
            str(
                self.tr(
                    "Zoom in or out of the image. Also accessible with "
                    "{} and {} from the canvas."
                )
            ).format(
                utils.fmt_shortcut(
                    f"{shortcuts['zoom_in']},{shortcuts['zoom_out']}"
                ),
                utils.fmt_shortcut(self.tr("Ctrl+Wheel")),
            )
        )
        self.zoom_widget.setEnabled(False)

        zoom_in = action(
            self.tr("Zoom &In"),
            functools.partial(self.add_zoom, 1.1),
            shortcuts["zoom_in"],
            "zoom-in",
            self.tr("Increase zoom level"),
            enabled=False,
        )
        zoom_out = action(
            self.tr("&Zoom Out"),
            functools.partial(self.add_zoom, 0.9),
            shortcuts["zoom_out"],
            "zoom-out",
            self.tr("Decrease zoom level"),
            enabled=False,
        )
        zoom_org = action(
            self.tr("&Original size"),
            functools.partial(self.set_zoom, 100),
            shortcuts["zoom_to_original"],
            "zoom",
            self.tr("Zoom to original size"),
            enabled=False,
        )
        keep_prev_scale = action(
            self.tr("&Keep Previous Scale"),
            lambda x: self._config.update({"keep_prev_scale": x}),
            tip=self.tr("Keep previous zoom scale"),
            checkable=True,
            checked=self._config["keep_prev_scale"],
            enabled=True,
        )
        keep_prev_brightness = action(
            self.tr("&Keep Previous Brightness"),
            lambda x: self._config.update({"keep_prev_brightness": x}),
            tip=self.tr("Keep previous brightness"),
            checkable=True,
            checked=self._config["keep_prev_brightness"],
            enabled=True,
        )
        keep_prev_contrast = action(
            self.tr("&Keep Previous Contrast"),
            lambda x: self._config.update({"keep_prev_contrast": x}),
            tip=self.tr("Keep previous contrast"),
            checkable=True,
            checked=self._config["keep_prev_contrast"],
            enabled=True,
        )
        fit_window = action(
            self.tr("&Fit Window"),
            self.set_fit_window,
            shortcuts["fit_window"],
            "fit-window",
            self.tr("Zoom follows window size"),
            checkable=True,
            enabled=False,
        )
        fit_width = action(
            self.tr("Fit &Width"),
            self.set_fit_width,
            shortcuts["fit_width"],
            "fit-width",
            self.tr("Zoom follows window width"),
            checkable=True,
            enabled=False,
        )
        brightness_contrast = action(
            self.tr("&Set Brightness Contrast"),
            self.brightness_contrast,
            None,
            "color",
            "Adjust brightness and contrast",
            enabled=False,
        )
        set_cross_line = action(
            self.tr("&Set Cross Line"),
            self.set_cross_line,
            tip=self.tr("Adjust cross line for mouse position"),
            icon="cartesian",
        )
        toggle_cross_line = action(
            self.tr("显示十字线"),
            self.toggle_crosshair,
            shortcuts.get("toggle_crosshair", "Ctrl+Shift+H"),
            tip=self.tr("显示/隐藏十字线"),
            icon="eye",
            checkable=True,
            checked=self._config["canvas"]["crosshair"]["show"],
        )
        show_groups = action(
            self.tr("&Show Groups"),
            lambda x: self.set_canvas_params("show_groups", x),
            tip=self.tr("Show shape groups"),
            icon=None,
            checkable=True,
            checked=self._config["show_groups"],
            enabled=True,
            auto_trigger=True,
        )
        show_texts = action(
            self.tr("&Show Texts"),
            lambda x: self.set_canvas_params("show_texts", x),
            shortcut=shortcuts["show_texts"],
            tip=self.tr("Show text above shapes"),
            icon=None,
            checkable=True,
            checked=self._config["show_texts"],
            enabled=True,
            auto_trigger=True,
        )
        show_labels = action(
            self.tr("&Show Labels"),
            lambda x: self.set_canvas_params("show_labels", x),
            shortcut=shortcuts["show_labels"],
            tip=self.tr("Show label inside shapes"),
            icon=None,
            checkable=True,
            checked=self._config["show_labels"],
            enabled=True,
            auto_trigger=True,
        )
        show_scores = action(
            self.tr("&Show Scores"),
            lambda x: self.set_canvas_params("show_scores", x),
            tip=self.tr("Show score inside shapes"),
            icon=None,
            checkable=True,
            checked=self._config["show_scores"],
            enabled=True,
            auto_trigger=True,
        )
        show_attributes = action(
            self.tr("&Show Attributes"),
            lambda x: self.set_canvas_params("show_attributes", x),
            shortcut=shortcuts["show_attributes"],
            tip=self.tr("Show attribute inside shapes"),
            icon=None,
            checkable=True,
            checked=self._config["show_attributes"],
            enabled=True,
            auto_trigger=True,
        )
        show_degrees = action(
            self.tr("&Show Degress"),
            lambda x: self.set_canvas_params("show_degrees", x),
            shortcut=shortcuts.get("toggle_degrees", "Ctrl+Alt+D"),
            tip=self.tr("Show degrees above rotated shapes"),
            icon=None,
            checkable=True,
            checked=self._config["show_degrees"],
            enabled=True,
            auto_trigger=True,
        )
        show_wh = action(
            self.tr("显示宽高"),
            lambda x: self.set_canvas_params("show_wh", x),
            shortcut=shortcuts.get("show_wh", "Ctrl+Shift+W"),
            tip=self.tr("Show width and height on shapes"),
            icon=None,
            checkable=True,
            checked=self._config.get("show_wh", False),
            enabled=True,
            auto_trigger=True,
        )
        show_linking = action(
            self.tr("&Show KIE Linking"),
            lambda x: self.set_canvas_params("show_linking", x),
            shortcut=shortcuts["show_linking"],
            tip=self.tr("Show KIE linking between key and value"),
            icon=None,
            checkable=True,
            checked=self._config["show_linking"],
            enabled=True,
            auto_trigger=True,
        )
        show_order = action(
            self.tr("显示序号"),
            lambda x: self.set_canvas_params("show_order", x),
            shortcut=shortcuts["show_order"],
            tip=self.tr("Show order of shapes"),
            icon=None,
            checkable=True,
            checked=self._config["show_order"],
            enabled=True,
            auto_trigger=True,
        )

        # Languages
        select_lang_en = action(
            "English",
            functools.partial(self.set_language, "en_US"),
            icon="us",
            checkable=True,
            checked=self._config["language"] == "en_US",
            enabled=self._config["language"] != "en_US",
        )
        select_lang_zh = action(
            "中文",
            functools.partial(self.set_language, "zh_CN"),
            icon="cn",
            checkable=True,
            checked=self._config["language"] == "zh_CN",
            enabled=self._config["language"] != "zh_CN",
        )

        # Upload
        upload_image_flags_file = action(
            self.tr("&Upload Image Flags File"),
            lambda: utils.upload_image_flags_file(self),
            None,
            icon="format_classify",
            tip=self.tr("Upload Custom Image Flags File"),
        )
        upload_label_flags_file = action(
            self.tr("&Upload Label Flags File"),
            lambda: utils.upload_label_flags_file(self, LABEL_OPACITY),
            None,
            icon="format_classify",
            tip=self.tr("Upload Custom Label Flags File"),
        )
        upload_shape_attrs_file = action(
            self.tr("&Upload Attributes File"),
            lambda: utils.upload_shape_attrs_file(self, LABEL_OPACITY),
            None,
            icon="format_classify",
            tip=self.tr("Upload Custom Attributes File"),
        )
        upload_label_classes_file = action(
            self.tr("&Upload Label Classes File"),
            lambda: utils.upload_label_classes_file(self),
            None,
            icon="format_classify",
            tip=self.tr("Upload Custom Label Classes File"),
        )
        upload_yolo_hbb_annotation = action(
            self.tr("&Upload YOLO-Hbb Annotations"),
            lambda: utils.upload_yolo_annotation(self, "hbb", LABEL_OPACITY),
            None,
            icon="format_yolo",
            tip=self.tr(
                "Upload Custom YOLO Horizontal Bounding Boxes Annotations"
            ),
        )
        upload_yolo_obb_annotation = action(
            self.tr("&Upload YOLO-Obb Annotations"),
            lambda: utils.upload_yolo_annotation(self, "obb", LABEL_OPACITY),
            None,
            icon="format_yolo",
            tip=self.tr(
                "Upload Custom YOLO Oriented Bounding Boxes Annotations"
            ),
        )
        upload_yolo_seg_annotation = action(
            self.tr("&Upload YOLO-Seg Annotations"),
            lambda: utils.upload_yolo_annotation(self, "seg", LABEL_OPACITY),
            None,
            icon="format_yolo",
            tip=self.tr("Upload Custom YOLO Segmentation Annotations"),
        )
        upload_yolo_pose_annotation = action(
            self.tr("&Upload YOLO-Pose Annotations"),
            lambda: utils.upload_yolo_annotation(self, "pose", LABEL_OPACITY),
            None,
            icon="format_yolo",
            tip=self.tr("Upload Custom YOLO Pose Annotations"),
        )
        upload_voc_det_annotation = action(
            self.tr("&Upload VOC Detection Annotations"),
            lambda: utils.upload_voc_annotation(self, "rectangle"),
            None,
            icon="format_voc",
            tip=self.tr("Upload Custom Pascal VOC Detection Annotations"),
        )
        upload_voc_seg_annotation = action(
            self.tr("&Upload VOC Segmentation Annotations"),
            lambda: utils.upload_voc_annotation(self, "polygon"),
            None,
            icon="format_voc",
            tip=self.tr("Upload Custom Pascal VOC Segmentation Annotations"),
        )
        upload_coco_det_annotation = action(
            self.tr("&Upload COCO Detection Annotations"),
            lambda: utils.upload_coco_annotation(self, "rectangle"),
            None,
            icon="format_coco",
            tip=self.tr("Upload Custom COCO Detection Annotations"),
        )
        upload_coco_seg_annotation = action(
            self.tr("&Upload COCO Instance Segmentation Annotations"),
            lambda: utils.upload_coco_annotation(self, "polygon"),
            None,
            icon="format_coco",
            tip=self.tr(
                "Upload Custom COCO Instance Segmentation Annotations"
            ),
        )
        upload_coco_pose_annotation = action(
            self.tr("&Upload COCO Keypoint Annotations"),
            lambda: utils.upload_coco_annotation(self, "pose"),
            None,
            icon="format_coco",
            tip=self.tr("Upload Custom COCO Keypoint Annotations"),
        )
        upload_dota_annotation = action(
            self.tr("&Upload DOTA Annotations"),
            lambda: utils.upload_dota_annotation(self),
            None,
            icon="format_dota",
            tip=self.tr("Upload Custom DOTA Annotations"),
        )
        upload_mask_annotation = action(
            self.tr("&Upload MASK Annotations"),
            lambda: utils.upload_mask_annotation(self, LABEL_OPACITY),
            None,
            icon="format_mask",
            tip=self.tr("Upload Custom MASK Annotations"),
        )
        upload_mot_annotation = action(
            self.tr("&Upload MOT Annotations"),
            lambda: utils.upload_mot_annotation(self, LABEL_OPACITY),
            None,
            icon="format_mot",
            tip=self.tr("Upload Custom Multi-Object-Tracking Annotations"),
        )
        upload_odvg_annotation = action(
            self.tr("&Upload ODVG Annotations"),
            lambda: utils.upload_odvg_annotation(self),
            None,
            icon="format_odvg",
            tip=self.tr(
                "Upload Custom Object Detection Visual Grounding Annotations"
            ),
        )
        upload_mmgd_annotation = action(
            self.tr("&Upload MM-Grounding-DINO Annotations"),
            lambda: utils.upload_mmgd_annotation(self, LABEL_OPACITY),
            None,
            icon="format_mmgd",
            tip=self.tr("Upload Custom MM-Grounding-DINO Annotations"),
        )
        upload_ppocr_rec_annotation = action(
            self.tr("&Upload PPOCR-Rec Annotations"),
            lambda: utils.upload_ppocr_annotation(self, "rec"),
            None,
            icon="format_ppocr",
            tip=self.tr("Upload Custom PPOCR Recognition Annotations"),
        )
        upload_ppocr_kie_annotation = action(
            self.tr("&Upload PPOCR-KIE Annotations"),
            lambda: utils.upload_ppocr_annotation(self, "kie"),
            None,
            icon="format_ppocr",
            tip=self.tr(
                "Upload Custom PPOCR Key Information Extraction (KIE - Semantic Entity Recognition & Relation Extraction) Annotations"
            ),
        )
        upload_vlm_r1_ovd_annotation = action(
            self.tr("&Upload VLM-R1 OVD Annotations"),
            lambda: utils.upload_vlm_r1_ovd_annotation(self),
            None,
            icon="format_vlm_r1_ovd",
            tip=self.tr("Upload Custom VLM-R1 OVD Annotations"),
        )
        upload_ballontranslator_annotation = action(
            self.tr("导入 Ballontranslator JSON"),
            lambda: utils.upload_ballontranslator_annotation(self),
            None,
            icon="format_coco",
            tip=self.tr("导入 Ballontranslator JSON 项目文件"),
        )

        upload_imagetrans_annotation = action(
            self.tr("导入 ImageTrans ipt"),
            lambda: utils.upload_imagetrans_annotation(self),
            None,
            icon="format_coco",
            tip=self.tr("导入 ImageTrans ipt 项目文件"),
        )

        # Export
        export_yolo_hbb_annotation = action(
            self.tr("&Export YOLO-Hbb Annotations"),
            lambda: utils.export_yolo_annotation(self, "hbb"),
            None,
            icon="format_yolo",
            tip=self.tr(
                "Export Custom YOLO Horizontal Bounding Boxes Annotations"
            ),
        )
        export_yolo_obb_annotation = action(
            self.tr("&Export YOLO-Obb Annotations"),
            lambda: utils.export_yolo_annotation(self, "obb"),
            None,
            icon="format_yolo",
            tip=self.tr(
                "Export Custom YOLO Oriented Bounding Boxes Annotations"
            ),
        )
        export_yolo_seg_annotation = action(
            self.tr("&Export YOLO-Seg Annotations"),
            lambda: utils.export_yolo_annotation(self, "seg"),
            None,
            icon="format_yolo",
            tip=self.tr("Export Custom YOLO Segmentation Annotations"),
        )
        export_yolo_pose_annotation = action(
            self.tr("&Export YOLO-Pose Annotations"),
            lambda: utils.export_yolo_annotation(self, "pose"),
            None,
            icon="format_yolo",
            tip=self.tr("Export Custom YOLO Pose Annotations"),
        )
        export_voc_det_annotation = action(
            self.tr("&Export VOC Detection Annotations"),
            lambda: utils.export_voc_annotation(self, "rectangle"),
            None,
            icon="format_voc",
            tip=self.tr("Export Custom PASCAL VOC Detection Annotations"),
        )
        export_voc_seg_annotation = action(
            self.tr("&Export VOC Segmentation Annotations"),
            lambda: utils.export_voc_annotation(self, "polygon"),
            None,
            icon="format_voc",
            tip=self.tr("Export Custom PASCAL VOC Segmentation Annotations"),
        )
        export_coco_det_annotation = action(
            self.tr("&Export COCO Detection Annotations"),
            lambda: utils.export_coco_annotation(self, "rectangle"),
            None,
            icon="format_coco",
            tip=self.tr("Export Custom COCO Rectangle Annotations"),
        )
        export_coco_seg_annotation = action(
            self.tr("&Export COCO Instance Segmentation Annotations"),
            lambda: utils.export_coco_annotation(self, "polygon"),
            None,
            icon="format_coco",
            tip=self.tr(
                "Export Custom COCO Instance Segmentation Annotations"
            ),
        )
        export_coco_pose_annotation = action(
            self.tr("&Export COCO Keypoint Annotations"),
            lambda: utils.export_coco_annotation(self, "pose"),
            None,
            icon="format_coco",
            tip=self.tr("Export Custom COCO Keypoint Annotations"),
        )
        export_dota_annotation = action(
            self.tr("&Export DOTA Annotations"),
            lambda: utils.export_dota_annotation(self),
            None,
            icon="format_dota",
            tip=self.tr("Export Custom DOTA Annotations"),
        )
        export_mask_annotation = action(
            self.tr("&Export MASK Annotations"),
            lambda: utils.export_mask_annotation(self),
            None,
            icon="format_mask",
            tip=self.tr("Export Custom MASK Annotations - RGB/Gray"),
        )
        export_mot_annotation = action(
            self.tr("&Export MOT Annotations"),
            lambda: utils.export_mot_annotation(self, "mot"),
            None,
            icon="format_mot",
            tip=self.tr("Export Custom Multi-Object-Tracking Annotations"),
        )
        export_mots_annotation = action(
            self.tr("&Export MOTS Annotations"),
            lambda: utils.export_mot_annotation(self, "mots"),
            None,
            icon="format_mot",
            tip=self.tr(
                "Export Custom Multi-Object-Tracking-Segmentation Annotations"
            ),
        )
        export_odvg_annotation = action(
            self.tr("&Export ODVG Annotations"),
            lambda: utils.export_odvg_annotation(self),
            None,
            icon="format_odvg",
            tip=self.tr(
                "Export Custom Object Detection Visual Grounding Annotations"
            ),
        )
        export_pporc_rec_annotation = action(
            self.tr("&Export PPOCR-Rec Annotations"),
            lambda: utils.export_pporc_annotation(self, "rec"),
            None,
            icon="format_ppocr",
            tip=self.tr("Export Custom PPOCR Recognition Annotations"),
        )
        export_pporc_kie_annotation = action(
            self.tr("&Export PPOCR-KIE Annotations"),
            lambda: utils.export_pporc_annotation(self, "kie"),
            None,
            icon="format_ppocr",
            tip=self.tr(
                "Export Custom PPOCR Key Information Extraction (KIE - Semantic Entity Recognition & Relation Extraction) Annotations"
            ),
        )
        export_vlm_r1_ovd_annotation = action(
            self.tr("&Export VLM-R1 OVD Annotations"),
            lambda: utils.export_vlm_r1_ovd_annotation(self),
            None,
            icon="format_vlm_r1_ovd",
            tip=self.tr("Export Custom VLM-R1 OVD Annotations"),
        )
        export_ballontranslator_annotation = action(
            "导出 Ballontranslator JSON (兼容旋转矩形)",
            lambda: utils.export_ballontranslator_annotation(self),
            None,
            icon="format_coco",
            tip="导出为 Ballontranslator JSON 格式（同时支持旋转框）",
        )
        export_imagetrans_annotation = action(
            "导出 ImageTrans ipt",
            lambda: utils.export_imagetrans_annotation(self),
            None,
            icon="format_coco",
            tip="导出 ImageTrans ipt 项目文件",
        )        # Create action for zoom at mouse
        zoom_at_mouse = action(
            self.tr("Zoom at Mouse"),
            self.zoom_at_mouse_shortcut_triggered,
            QtGui.QKeySequence(self._config["canvas"].get("zoom_at_mouse_shortcut", "Ctrl+B")),
            "zoom-in",
            self.tr("Zoom in at mouse position"),
            # enabled=False, # Removed enabled=False, toggle_actions will handle it
        )
        self.addAction(zoom_at_mouse) # Explicitly add action to widget for shortcut recognition

        # Group zoom controls into a list for easier toggling.
        zoom_actions = (
            self.zoom_widget,
            zoom_in,
            zoom_out,
            zoom_org,
            fit_window,
            fit_width,
            zoom_at_mouse, # Add the new action here
        )
        self.zoom_mode = self.FIT_WINDOW
        fit_window.setChecked(Qt.Checked)
        self.scalers = {
            self.FIT_WINDOW: self.scale_fit_window,
            self.FIT_WIDTH: self.scale_fit_width,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        edit = action(
            self.tr("&Edit Label"),
            self.edit_label,
            shortcuts["edit_label"],
            "edit",
            self.tr("Modify the label of the selected polygon"),
            enabled=False,
        )

        fill_drawing = action(
            self.tr("Fill Drawing Polygon"),
            self.canvas.set_fill_drawing,
            None,
            "color",
            self.tr("Fill polygon while drawing"),
            checkable=True,
            enabled=True,
        )
        fill_drawing.trigger()

        # Navigator action
        show_navigator = action(
            self.tr("导航器(&N)"),
            self.toggle_navigator,
            shortcuts["show_navigator"],
            "zoom",
            self.tr("显示/隐藏导航器窗口"),
            checkable=True,
            enabled=True,
        )

        # AI Actions
        toggle_auto_labeling_widget = action(
            self.tr("&Auto Labeling"),
            self.toggle_auto_labeling_widget,
            shortcuts["auto_label"],
            "brain",
            self.tr("Auto Labeling"),
        )

        # Label list context menu.
        label_menu = QtWidgets.QMenu()
        utils.add_actions(label_menu, (edit, delete, union_selection))
        self.label_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.label_list.customContextMenuRequested.connect(
            self.pop_label_list_menu
        )

        # Store actions for further handling.
        self.actions = utils.Struct(
            save_auto=save_auto,
            save_with_image_data=save_with_image_data,
            change_output_dir=change_output_dir,
            save=save,
            save_as=save_as,
            open=open_,
            close=close,
            delete_file=delete_file,
            delete_image_file=delete_image_file,
            keep_prev_mode=keep_prev_mode,
            auto_use_last_label_mode=auto_use_last_label_mode,
            use_system_clipboard=use_system_clipboard,
            visibility_shapes_mode=visibility_shapes_mode,
            run_all_images=run_all_images,
            union_selection=union_selection,
            delete=delete,
            edit=edit,
            duplicate=duplicate,
            copy=copy,
            paste=paste,
            undo_last_point=undo_last_point,
            undo=undo,
            remove_point=remove_point,
            create_mode=create_mode,
            edit_mode=edit_mode,
            create_rectangle_mode=create_rectangle_mode,
            create_rotation_mode=create_rotation_mode,
            create_rotation3_mode=create_rotation3_mode,
            create_circle_mode=create_circle_mode,
            create_line_mode=create_line_mode,
            create_point_mode=create_point_mode,
            create_line_strip_mode=create_line_strip_mode,
            digit_shortcut_0=digit_shortcut_0,
            digit_shortcut_1=digit_shortcut_1,
            digit_shortcut_2=digit_shortcut_2,
            digit_shortcut_3=digit_shortcut_3,
            digit_shortcut_4=digit_shortcut_4,
            digit_shortcut_5=digit_shortcut_5,
            digit_shortcut_6=digit_shortcut_6,
            digit_shortcut_7=digit_shortcut_7,
            digit_shortcut_8=digit_shortcut_8,
            digit_shortcut_9=digit_shortcut_9,
            digit_shortcut_manager=digit_shortcut_manager,
            label_toggle_shortcut_manager=label_toggle_shortcut_manager,
            upload_image_flags_file=upload_image_flags_file,
            upload_label_flags_file=upload_label_flags_file,
            upload_shape_attrs_file=upload_shape_attrs_file,
            upload_label_classes_file=upload_label_classes_file,
            upload_yolo_hbb_annotation=upload_yolo_hbb_annotation,
            upload_yolo_obb_annotation=upload_yolo_obb_annotation,
            upload_yolo_seg_annotation=upload_yolo_seg_annotation,
            upload_yolo_pose_annotation=upload_yolo_pose_annotation,
            upload_voc_det_annotation=upload_voc_det_annotation,
            upload_voc_seg_annotation=upload_voc_seg_annotation,
            upload_coco_det_annotation=upload_coco_det_annotation,
            upload_coco_seg_annotation=upload_coco_seg_annotation,
            upload_coco_pose_annotation=upload_coco_pose_annotation,
            upload_dota_annotation=upload_dota_annotation,
            upload_mask_annotation=upload_mask_annotation,
            upload_mot_annotation=upload_mot_annotation,
            upload_odvg_annotation=upload_odvg_annotation,
            upload_mmgd_annotation=upload_mmgd_annotation,
            upload_ppocr_rec_annotation=upload_ppocr_rec_annotation,
            upload_ppocr_kie_annotation=upload_ppocr_kie_annotation,
            upload_vlm_r1_ovd_annotation=upload_vlm_r1_ovd_annotation,
            upload_ballontranslator_annotation=upload_ballontranslator_annotation,
            upload_imagetrans_annotation=upload_imagetrans_annotation,
            export_yolo_hbb_annotation=export_yolo_hbb_annotation,
            export_yolo_obb_annotation=export_yolo_obb_annotation,
            export_yolo_seg_annotation=export_yolo_seg_annotation,
            export_yolo_pose_annotation=export_yolo_pose_annotation,
            export_voc_det_annotation=export_voc_det_annotation,
            export_voc_seg_annotation=export_voc_seg_annotation,
            export_coco_det_annotation=export_coco_det_annotation,
            export_coco_seg_annotation=export_coco_seg_annotation,
            export_coco_pose_annotation=export_coco_pose_annotation,
            export_dota_annotation=export_dota_annotation,
            export_mask_annotation=export_mask_annotation,
            export_mot_annotation=export_mot_annotation,
            export_mots_annotation=export_mots_annotation,
            export_odvg_annotation=export_odvg_annotation,
            export_pporc_rec_annotation=export_pporc_rec_annotation,
            export_pporc_kie_annotation=export_pporc_kie_annotation,
            export_vlm_r1_ovd_annotation=export_vlm_r1_ovd_annotation,
            export_ballontranslator_annotation=export_ballontranslator_annotation,
            export_imagetrans_annotation=export_imagetrans_annotation,
            zoom=zoom,
            zoom_in=zoom_in,
            zoom_out=zoom_out,
            zoom_org=zoom_org,
            keep_prev_scale=keep_prev_scale,
            keep_prev_brightness=keep_prev_brightness,
            keep_prev_contrast=keep_prev_contrast,
            fit_window=fit_window,
            fit_width=fit_width,
            brightness_contrast=brightness_contrast,
            set_cross_line=set_cross_line,
            toggle_cross_line=toggle_cross_line,
            show_groups=show_groups,
            show_texts=show_texts,
            show_labels=show_labels,
            show_scores=show_scores,
            show_degrees=show_degrees,
            show_wh=show_wh,
            show_attributes=show_attributes,
            show_linking=show_linking,
            show_order=show_order,
            show_navigator=show_navigator,
            zoom_at_mouse=zoom_at_mouse, # Add the new action here
            zoom_actions=zoom_actions,
            open_next_image=open_next_image,
            open_prev_image=open_prev_image,
            open_next_unchecked_image=open_next_unchecked_image,
            open_prev_unchecked_image=open_prev_unchecked_image,
            open_chatbot=open_chatbot,
            open_vqa=open_vqa,
            file_menu_actions=(
                open_,
                openvideo,
                opendir,
                save,
                save_as,
                close,
            ),
            tool=(),
            # XXX: need to add some actions here to activate the shortcut
            editMenu=(
                edit,
                duplicate,
                delete,
                copy,
                paste,
                None,
                undo,
                undo_last_point,
                None,
                remove_point,
                union_selection,
                None,
                keep_prev_mode,
                auto_use_last_label_mode,
                use_system_clipboard,
                visibility_shapes_mode,
            ),
            # menu shown at right click
            menu=(
                create_mode,
                create_rectangle_mode,
                create_rotation_mode,
                create_circle_mode,
                create_line_mode,
                create_point_mode,
                create_line_strip_mode,
                edit_mode,
                edit,
                union_selection,
                duplicate,
                copy,
                paste,
                delete,
                undo,
                undo_last_point,
                remove_point,
            ),
            on_load_active=(
                close,
                create_mode,
                create_rectangle_mode,
                create_rotation_mode,
                create_circle_mode,
                create_line_mode,
                create_point_mode,
                create_line_strip_mode,
                digit_shortcut_0,
                digit_shortcut_1,
                digit_shortcut_2,
                digit_shortcut_3,
                digit_shortcut_4,
                digit_shortcut_5,
                digit_shortcut_6,
                digit_shortcut_7,
                digit_shortcut_8,
                digit_shortcut_9,
                edit_mode,
                brightness_contrast,
                loop_thru_labels,
            ),
            on_shapes_present=(save_as, delete),
            hide_selected_polygons=hide_selected_polygons,
            show_hidden_polygons=show_hidden_polygons,
            group_selected_shapes=group_selected_shapes,
            ungroup_selected_shapes=ungroup_selected_shapes,
        )

        self.canvas.vertex_selected.connect(
            self.actions.remove_point.setEnabled
        )

        self.menus = utils.Struct(
            file=self.menu(self.tr("&File")),
            edit=self.menu(self.tr("&Edit")),
            view=self.menu(self.tr("&View")),
            language=self.menu(self.tr("&Language")),
            upload=self.menu(self.tr("&Upload")),
            export=self.menu(self.tr("&Export")),
            tool=self.menu(self.tr("&Tool")),
            train=self.menu(self.tr("&Train")),
            help=self.menu(self.tr("&Help")),
            recent_files=QtWidgets.QMenu(self.tr("Open &Recent")),
            label_list=label_menu,
        )

        utils.add_actions(
            self.menus.file,
            (
                open_,
                open_next_image,
                open_prev_image,
                open_next_unchecked_image,
                open_prev_unchecked_image,
                opendir,
                load_subfolders_action,
                openvideo,
                self.menus.recent_files,
                save,
                save_as,
                save_auto,
                change_output_dir,
                save_with_image_data,
                close,
                delete_file,
                delete_image_file,
                None,
            ),
        )
        utils.add_actions(self.menus.train, (ultralytics_train,))
        utils.add_actions(
            self.menus.tool,
            (
                overview,
                None,
                save_crop,
                None,
                digit_shortcut_manager,
                label_toggle_shortcut_manager,
                label_manager,
                object_manager,
                gid_manager,
                None,
                hbb_to_obb,
                obb_to_hbb,
                polygon_to_hbb,
                polygon_to_obb,
                None,
                expand_margins,
                tag_sort_tool,
                angle_correction_tool,
                alignment_tool,
                merge_shapes,
                None,
                dual_color_label_tool,
                mask_generator_tool,
                None,
                keymap_tool,
            ),
        )
        utils.add_actions(
            self.menus.help,
            (
                documentation,
                None,
                about,
            ),
        )
        utils.add_actions(
            self.menus.language,
            (
                select_lang_en,
                select_lang_zh,
            ),
        )
        utils.add_actions(
            self.menus.upload,
            (
                upload_image_flags_file,
                upload_label_flags_file,
                upload_shape_attrs_file,
                upload_label_classes_file,
                None,
                upload_yolo_hbb_annotation,
                upload_yolo_obb_annotation,
                upload_yolo_seg_annotation,
                upload_yolo_pose_annotation,
                None,
                upload_voc_det_annotation,
                upload_voc_seg_annotation,
                None,
                upload_coco_det_annotation,
                upload_coco_seg_annotation,
                upload_coco_pose_annotation,
                None,
                upload_dota_annotation,
                upload_mask_annotation,
                upload_mot_annotation,
                upload_odvg_annotation,
                upload_mmgd_annotation,
                None,
                upload_ppocr_rec_annotation,
                upload_ppocr_kie_annotation,
                None,
                upload_vlm_r1_ovd_annotation,
                None,
                upload_ballontranslator_annotation,
                upload_imagetrans_annotation,
            ),
        )
        utils.add_actions(
            self.menus.export,
            (
                export_yolo_hbb_annotation,
                export_yolo_obb_annotation,
                export_yolo_seg_annotation,
                export_yolo_pose_annotation,
                None,
                export_voc_det_annotation,
                export_voc_seg_annotation,
                None,
                export_coco_det_annotation,
                export_coco_seg_annotation,
                export_coco_pose_annotation,
                None,
                export_dota_annotation,
                export_mask_annotation,
                export_odvg_annotation,
                None,
                export_mot_annotation,
                export_mots_annotation,
                None,
                export_pporc_rec_annotation,
                export_pporc_kie_annotation,
                None,
                export_vlm_r1_ovd_annotation,
                None,
                export_ballontranslator_annotation,
                export_imagetrans_annotation,
            ),
        )
        utils.add_actions(
            self.menus.view,
            (
                self.flag_dock.toggleViewAction(),
                self.label_dock.toggleViewAction(),
                self.shape_dock.toggleViewAction(),
                self.file_dock.toggleViewAction(),
                None,
                show_navigator,
                None,
                fill_drawing,
                None,
                loop_thru_labels,
                None,
                zoom_in,
                zoom_out,
                zoom_org,
                None,
                keep_prev_scale,
                keep_prev_brightness,
                keep_prev_contrast,
                None,
                fit_window,
                fit_width,
                None,
                brightness_contrast,
                set_cross_line,
                toggle_cross_line,
                show_texts,
                show_labels,
                show_scores,
                show_degrees,
                show_wh,
                show_attributes,
                show_linking,
                show_groups,
                show_order,
                hide_selected_polygons,
                show_hidden_polygons,
                group_selected_shapes,
                ungroup_selected_shapes,
            ),
        )

        # Connect aboutToShow to update menu RIGHT BEFORE showing
        # This ensures menu is always fresh when displayed
        self.menus.recent_files.aboutToShow.connect(self.update_file_menu)

        # Custom context menu for the canvas widget:
        utils.add_actions(self.canvas.menus[0], self.actions.menu)
        utils.add_actions(
            self.canvas.menus[1],
            (
                action("&Copy here", self.copy_shape),
                action("&Move here", self.move_shape),
            ),
        )

        self.tools = self.toolbar("Tools")
        # Menu buttons on Left
        self.actions.tool = (
            # open_,
            opendir,
            open_next_image,
            open_prev_image,
            save,
            delete_file,
            None,
            create_mode,
            self.actions.create_rectangle_mode,
            self.actions.create_rotation_mode,
            self.actions.create_rotation3_mode,  # 新增的三次点击旋转矩形
            self.actions.create_circle_mode,
            self.actions.create_line_mode,
            self.actions.create_point_mode,
            self.actions.create_line_strip_mode,
            None,
            edit_mode,
            delete,
            undo,
            loop_thru_labels,
            None,
            zoom,
            fit_width,
            open_chatbot,
            open_vqa,
            toggle_auto_labeling_widget,
            run_all_images,
        )

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self.tools)
        central_layout = QVBoxLayout()
        central_layout.setContentsMargins(0, 0, 0, 0)
        self.label_instruction = QLabel(self.get_labeling_instruction())
        self.label_instruction.setContentsMargins(0, 0, 0, 0)
        self.auto_labeling_widget = AutoLabelingWidget(self)
        self.auto_labeling_widget.auto_segmentation_requested.connect(
            self.on_auto_segmentation_requested
        )
        self.auto_labeling_widget.auto_segmentation_disabled.connect(
            self.on_auto_segmentation_disabled
        )
        self.canvas.auto_labeling_marks_updated.connect(
            self.auto_labeling_widget.on_new_marks
        )
        self.auto_labeling_widget.auto_labeling_mode_changed.connect(
            self.canvas.set_auto_labeling_mode
        )
        self.auto_labeling_widget.auto_decode_mode_changed.connect(
            self.canvas.set_auto_decode_mode
        )
        self.auto_labeling_widget.clear_auto_decode_requested.connect(
            self.canvas.reset_auto_decode_state
        )
        self.canvas.auto_decode_requested.connect(
            self.on_auto_decode_requested
        )
        self.canvas.auto_decode_finish_requested.connect(
            self.auto_labeling_widget.on_finish_clicked
        )
        # 连接形状hover状态变化信号到导航器更新
        self.canvas.shape_hover_changed.connect(self.update_navigator_shapes)
        self.auto_labeling_widget.clear_auto_labeling_action_requested.connect(
            self.clear_auto_labeling_marks
        )
        self.auto_labeling_widget.finish_auto_labeling_object_action_requested.connect(
            self.finish_auto_labeling_object
        )
        self.auto_labeling_widget.cache_auto_label_changed.connect(
            self.set_cache_auto_label
        )
        self.auto_labeling_widget.model_manager.prediction_started.connect(
            lambda: self.canvas.set_loading(True, self.tr("Please wait..."))
        )
        self.auto_labeling_widget.model_manager.prediction_finished.connect(
            lambda: self.canvas.set_loading(False)
        )
        self.auto_labeling_widget.model_manager.prediction_finished.connect(
            self.update_thumbnail_display
        )
        self.auto_labeling_widget.model_manager.model_loaded.connect(
            self.update_thumbnail_display
        )
        self.next_files_changed.connect(
            self.auto_labeling_widget.model_manager.on_next_files_changed
        )
        # NOTE(jack): this is not needed for now
        # self.auto_labeling_widget.model_manager.request_next_files_requested.connect(
        #     lambda: self.inform_next_files(self.filename)
        # )
        self.auto_labeling_widget.hide()  # Hide by default
        central_layout.addWidget(self.label_instruction)
        central_layout.addSpacing(5)
        central_layout.addWidget(self.auto_labeling_widget)
        central_layout.addWidget(scroll_area)
        layout.addItem(central_layout)

        # Save central area for resize
        self._central_widget = scroll_area

        # Stretch central area (image view)
        layout.setStretch(1, 1)

        right_sidebar_layout = QVBoxLayout()
        right_sidebar_layout.setContentsMargins(0, 0, 0, 0)

        # Thumbnail image display
        self.thumbnail_pixmap = None
        self.thumbnail_container = QWidget()
        thumbnail_image_layout = QVBoxLayout()
        thumbnail_image_layout.setContentsMargins(2, 2, 2, 2)
        self.thumbnail_image_label = QLabel()
        self.thumbnail_image_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_image_label.mousePressEvent = utils.on_thumbnail_click(
            self
        )
        thumbnail_image_layout.addWidget(self.thumbnail_image_label)
        self.thumbnail_container.setLayout(thumbnail_image_layout)
        self.thumbnail_container.hide()
        right_sidebar_layout.addWidget(self.thumbnail_container)

        # Shape attributes
        self.shape_attributes = QLabel(self.tr("Attributes"))
        self.grid_layout = QGridLayout()
        self.scroll_area = QScrollArea()
        # Show vertical scrollbar as needed
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Disable horizontal scrollbar
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidgetResizable(True)
        # Create a container widget for the grid layout
        self.grid_layout_container = QWidget()
        self.grid_layout_container.setLayout(self.grid_layout)
        self.scroll_area.setWidget(self.grid_layout_container)
        if not self.attributes:
            self.shape_attributes.hide()
            self.scroll_area.hide()
        right_sidebar_layout.addWidget(
            self.shape_attributes, 0, Qt.AlignCenter
        )
        right_sidebar_layout.addWidget(self.scroll_area)

        # Shape text label (缩小描述区域)
        self.shape_text_label = QLabel("Object Text")
        self.shape_text_edit = QPlainTextEdit()
        self.shape_text_edit.setMaximumHeight(60)  # 限制高度
        right_sidebar_layout.addWidget(
            self.shape_text_label, 0, Qt.AlignCenter
        )
        right_sidebar_layout.addWidget(self.shape_text_edit)
        right_sidebar_layout.addWidget(self.flag_dock)
        right_sidebar_layout.addWidget(self.label_dock)

        # Create a horizontal layout for the filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(self.label_filter_combobox, 90)
        filter_layout.addWidget(self.gid_filter_combobox, 10)
        right_sidebar_layout.addLayout(filter_layout)

        right_sidebar_layout.addWidget(self.shape_dock)
        right_sidebar_layout.addWidget(self.file_dock)
        self.file_dock.setFeatures(QDockWidget.DockWidgetFloatable)
        dock_features = (
            ~QDockWidget.DockWidgetMovable
            | ~QDockWidget.DockWidgetFloatable
            | ~QDockWidget.DockWidgetClosable
        )
        rev_dock_features = ~dock_features
        self.label_dock.setFeatures(
            self.label_dock.features() & rev_dock_features
        )
        self.file_dock.setFeatures(
            self.file_dock.features() & rev_dock_features
        )
        self.flag_dock.setFeatures(
            self.flag_dock.features() & rev_dock_features
        )
        self.shape_dock.setFeatures(
            self.shape_dock.features() & rev_dock_features
        )

        self.shape_text_edit.textChanged.connect(self.shape_text_changed)

        layout.addItem(right_sidebar_layout)
        self.setLayout(layout)

        if output_file is not None and self._config["auto_save"]:
            logger.warning(
                "If `auto_save` argument is True, `output_file` argument "
                "is ignored and output filename is automatically "
                "set as IMAGE_BASENAME.json."
            )
        self.output_file = output_file
        self.output_dir = output_dir

        # Application state.
        self.image = QtGui.QImage()
        self.image_path = None
        self.recent_files = []
        self.max_recent = 7
        self.recent_folders = []  # Store recently opened folder paths
        self.max_recent_folders = 50  # Maximum 50 recent folders
        self.other_data = {}
        self.zoom_level = 100
        self.fit_window = False
        self.zoom_values = {}  # key=filename, value=(zoom_mode, zoom_value)
        self.brightness_contrast_values = {}
        self.scroll_values = {
            Qt.Horizontal: {},
            Qt.Vertical: {},
        }  # key=filename, value=scroll_value

        if filename is not None and osp.isdir(filename):
            self.import_image_folder(filename, load=False)
        else:
            self.filename = filename

        if config["file_search"]:
            self.file_search.setText(config["file_search"])
            self.file_search_changed()

        # XXX: Could be completely declarative.
        # Restore application settings.
        self.settings = QtCore.QSettings("anylabeling", "anylabeling")
        self.recent_files = self.settings.value("recent_files", []) or []
        self.recent_folders = self.settings.value("recent_folders", []) or []
        size = self.settings.value("window/size", QtCore.QSize(600, 500))
        position = self.settings.value("window/position", QtCore.QPoint(0, 0))
        # state = self.settings.value("window/state", QtCore.QByteArray())
        self.resize(size)
        self.move(position)
        # or simply:
        # self.restoreGeometry(settings['window/geometry']

        # Since loading the file may take some time,
        # make sure it runs in the background.
        if self.filename is not None:
            self.queue_event(functools.partial(self.load_file, self.filename))

        # Callbacks:
        self.zoom_widget.valueChanged.connect(self.paint_canvas)

        self.populate_mode_actions()

        self.first_start = True
        if self.first_start:
            QWhatsThis.enterWhatsThisMode()

        self.set_text_editing(False)

        # 延迟恢复导航器状态，确保在界面完全初始化后执行
        QtCore.QTimer.singleShot(100, self.restore_navigator_state)

        self.shape_list_changed.connect(self._update_object_manager)

    def restore_navigator_state(self) -> None:
        """
        Restore navigator dialog state, position, and size from config file.

        This method restores the navigator's visibility, position, and size
        from the config file. If an image is loaded, it also updates the
        navigator content. Otherwise, it marks the navigator for update when an image
        becomes available.

        Returns:
            None

        Examples:
            >>> # Called automatically during application startup
            >>> self.restore_navigator_state()
            
        Note:
            This method is designed to be safe - if restoration fails for any reason,
            it won't affect normal program operation.
        """
        try:
            # Restore navigator from config file
            navigator_restored = self.navigator_dialog.restore_from_config()
            
            if navigator_restored:
                # Update navigator content only if image exists, otherwise mark for later
                if hasattr(self, 'image') and not self.image.isNull():
                    self.navigator_dialog.set_image(QtGui.QPixmap.fromImage(self.image))
                    self.update_navigator_viewport()
                else:
                    # Mark for restoration when image is loaded
                    self._should_restore_navigator = True
                
                # Update menu item checked state
                if hasattr(self, 'actions') and hasattr(self.actions, 'show_navigator'):
                    self.actions.show_navigator.setChecked(True)
                        
        except Exception as e:
            print(f"Error restoring navigator state: {e}")
            # If restoration fails, don't affect normal program operation
            
    def _navigator_close_event(self, event: QtGui.QCloseEvent) -> None:
        """
        Handle navigator dialog close event.

        This method is called when the navigator dialog is closed by the user
        clicking the close button. It ensures the menu item state is updated
        to reflect the navigator's closed state.

        Args:
            event (QtGui.QCloseEvent): The close event from Qt framework.

        Returns:
            None

        Examples:
            >>> # This method is automatically called when navigator is closed
            >>> # No direct usage required
            
        Note:
            This method calls the original close event to maintain proper cleanup.
        """
        # Update menu item state to reflect navigator closure
        if hasattr(self, 'actions') and hasattr(self.actions, 'show_navigator'):
            self.actions.show_navigator.setChecked(False)
        
        # Call original close event handler
        NavigatorDialog.closeEvent(self.navigator_dialog, event)

    def set_language(self, language):
        if self._config["language"] == language:
            return
        self._config["language"] = language

        # Show dialog to restart application
        msg_box = QMessageBox()
        msg_box.setText(
            self.tr("Please restart the application to apply changes.")
        )
        msg_box.exec_()
        self.parent.parent.close()

    def get_labeling_instruction(self):
        text_mode = self.tr("Mode:")
        text_shortcuts = self.tr("Shortcuts:")
        text_chatbot = self.tr("Chatbot")
        text_vqa = self.tr("VQA")
        text_previous = self.tr("Previous")
        text_next = self.tr("Next")
        text_rectangle = self.tr("Rectangle")
        text_polygon = self.tr("Polygon")
        text_rotation = self.tr("Rotation")
        return (
            f"<b>{text_mode}</b> {self.canvas.get_mode()} | "
            f"<b>{text_shortcuts}</b>"
            f" {text_chatbot}(<b>Ctrl+B</b>),"
            f" {text_vqa}(<b>Ctrl+1</b>),"
            f" {text_previous}(<b>A</b>),"
            f" {text_next}(<b>D</b>),"
            f" {text_rectangle}(<b>R</b>),"
            f" {text_polygon}(<b>P</b>),"
            f" {text_rotation}(<b>O</b>)"
        )

    @pyqtSlot()
    def on_auto_segmentation_requested(self):
        self.canvas.set_auto_labeling(True)
        self.label_instruction.setText(self.get_labeling_instruction())

    @pyqtSlot()
    def on_auto_segmentation_disabled(self):
        self.canvas.set_auto_labeling(False)
        self.label_instruction.setText(self.get_labeling_instruction())

    @pyqtSlot(list)
    def on_auto_decode_requested(self, marks):
        """Handle auto decode request"""
        self.auto_labeling_widget.model_manager.set_auto_labeling_marks(marks)
        self.auto_labeling_widget.run_prediction()

    def menu(self, title, actions=None):
        menu = self.parent.parent.menuBar().addMenu(title)
        if actions:
            utils.add_actions(menu, actions)
        return menu

    def central_widget(self):
        return self._central_widget

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(f"{title}ToolBar")
        toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbar.setIconSize(QtCore.QSize(24, 24))
        toolbar.setMaximumWidth(40)
        if actions:
            utils.add_actions(toolbar, actions)
        return toolbar

    def statusBar(self):
        return self.parent.parent.statusBar()

    def no_shape(self):
        return len(self.label_list) == 0

    def populate_mode_actions(self):
        tool = self.actions.tool
        menu = self.actions.menu
        self.tools.clear()
        utils.add_actions(self.tools, tool)

        self.canvas.menus[0].clear()
        utils.add_actions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (
            self.actions.create_mode,
            self.actions.create_rectangle_mode,
            self.actions.create_rotation_mode,
            self.actions.create_circle_mode,
            self.actions.create_line_mode,
            self.actions.create_point_mode,
            self.actions.create_line_strip_mode,
            self.actions.digit_shortcut_0,
            self.actions.digit_shortcut_1,
            self.actions.digit_shortcut_2,
            self.actions.digit_shortcut_3,
            self.actions.digit_shortcut_4,
            self.actions.digit_shortcut_5,
            self.actions.digit_shortcut_6,
            self.actions.digit_shortcut_7,
            self.actions.digit_shortcut_8,
            self.actions.digit_shortcut_9,
            self.actions.edit_mode,
        )
        utils.add_actions(self.menus.edit, actions + self.actions.editMenu)

    def set_dirty(self, mark_as_manually_edited: bool = True) -> None:
        """
        Mark the current document as modified (dirty) and handle auto-save.

        This method indicates that the current file has unsaved changes and
        handles automatic saving if enabled. It updates the UI to show unsaved
        changes and maintains navigator synchronization.

        Args:
            mark_as_manually_edited: If True, marks file as manually edited by user.
                                    If False (e.g., from AI inference), keeps manual edit flag unchanged.
                                    Defaults to True for user-initiated changes.

        Returns:
            None

        Examples:
            >>> # After user modifies shapes or labels
            >>> app.set_dirty()
            >>> # After AI inference (should not mark as manually edited)
            >>> app.set_dirty(mark_as_manually_edited=False)
            >>> # If auto-save enabled: automatically saves to file
            >>> # If auto-save disabled: shows "*" in window title

        Note:
            When auto-save is enabled, immediately saves the file and updates navigator.
            When auto-save is disabled, marks document as dirty and enables save action.
            Always updates navigator shapes to maintain synchronization.
        """
        if not self.image_path:
            return

        # Mark as manually edited only if requested (user changes, not AI inference)
        if mark_as_manually_edited:
            self.other_data["manually_edited"] = True

        # Even if we autosave the file, we keep the ability to undo
        self.actions.undo.setEnabled(self.canvas.is_shape_restorable)

        if self._config["auto_save"]:
            label_file = osp.splitext(self.image_path)[0] + ".json"
            if self.output_dir:
                label_file_without_path = osp.basename(label_file)
                label_file = self.output_dir + "/" + label_file_without_path
            self.save_labels(label_file)
            # Update navigator shapes when auto-saving
            self.update_navigator_shapes()
            return
        self.dirty = True
        self.actions.save.setEnabled(True)
        # Update navigator shapes when marking as dirty
        self.update_navigator_shapes()
        title = __appname__
        if self.filename is not None:
            title = f"{title} - {self.filename}*"
        self.setWindowTitle(title)

    def set_clean(self) -> None:
        """
        Mark the current document as clean (no unsaved changes) and reset UI state.

        This method indicates that the current file has been saved and has no
        pending modifications. It updates the UI to reflect the saved state,
        disables save actions, and enables all shape creation tools.

        Returns:
            None

        Examples:
            >>> # After successfully saving the file
            >>> app.set_clean()
            >>> # Window title removes "*", save disabled, creation tools enabled
            
        Note:
            Resets dirty flag, disables save/union actions, enables all creation modes
            and digit shortcuts. Updates window title to show clean state.
        """
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.union_selection.setEnabled(False)
        self.actions.create_mode.setEnabled(True)
        self.actions.create_rectangle_mode.setEnabled(True)
        self.actions.create_rotation_mode.setEnabled(True)
        self.actions.create_rotation3_mode.setEnabled(True)
        self.actions.create_circle_mode.setEnabled(True)
        self.actions.create_line_mode.setEnabled(True)
        self.actions.create_point_mode.setEnabled(True)
        self.actions.create_line_strip_mode.setEnabled(True)
        self.actions.digit_shortcut_0.setEnabled(True)
        self.actions.digit_shortcut_1.setEnabled(True)
        self.actions.digit_shortcut_2.setEnabled(True)
        self.actions.digit_shortcut_3.setEnabled(True)
        self.actions.digit_shortcut_4.setEnabled(True)
        self.actions.digit_shortcut_5.setEnabled(True)
        self.actions.digit_shortcut_6.setEnabled(True)
        self.actions.digit_shortcut_7.setEnabled(True)
        self.actions.digit_shortcut_8.setEnabled(True)
        self.actions.digit_shortcut_9.setEnabled(True)
        title = __appname__
        if self.filename is not None:
            title = f"{title} - {self.filename}"
        self.setWindowTitle(title)

        if self.has_label_file():
            self.actions.delete_file.setEnabled(True)
        else:
            self.actions.delete_file.setEnabled(False)

    def toggle_actions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for action in self.actions.zoom_actions:
            action.setEnabled(value)
        for action in self.actions.on_load_active:
            action.setEnabled(value)

    def queue_event(self, function):
        QtCore.QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def reset_state(self):
        self.label_list.clear()
        self.filename = None
        self.image_path = None
        self.image_data = None
        self.label_file = None
        self.other_data = {}
        self.canvas.reset_state()
        self.label_filter_combobox.text_box.clear()
        self.gid_filter_combobox.gid_box.clear()

    def reset_attribute(self, text):
        # Skip validation for auto-labeling special constants
        if text in [
            AutoLabelingMode.OBJECT,
            AutoLabelingMode.ADD,
            AutoLabelingMode.REMOVE,
        ]:
            return text

        valid_labels = list(self.attributes.keys())
        if text not in valid_labels:
            most_similar_label = utils.find_most_similar_label(
                text, valid_labels
            )
            self.error_message(
                self.tr("Invalid label"),
                self.tr(
                    "Invalid label '{}' with validation type: {}!\n"
                    "Reset the label as {}."
                ).format(text, valid_labels, most_similar_label),
            )
            text = most_similar_label
        return text

    def current_item(self):
        items = self.label_list.selected_items()
        if items:
            return items[0]
        return None

    def add_recent_file(self, filename: str) -> None:
        """
        Add a file to the recent files list with automatic management.

        This method maintains a list of recently opened files, automatically
        removing duplicates and enforcing the maximum recent files limit.
        The most recently added file appears at the top of the list.

        Args:
            filename (str): Full path of the file to add to recent files.

        Returns:
            None

        Examples:
            >>> # Add a new file to recent files
            >>> app.add_recent_file("/path/to/image.jpg")
            >>> 
            >>> # Adding same file again moves it to top
            >>> app.add_recent_file("/path/to/image.jpg")
            
        Note:
            If the file is already in the list, it's moved to the front.
            If the list exceeds max_recent limit, the oldest entry is removed.
            Changes are automatically saved to application settings.
        """
        if filename in self.recent_files:
            self.recent_files.remove(filename)
        elif len(self.recent_files) >= self.max_recent:
            self.recent_files.pop()
        self.recent_files.insert(0, filename)

    # Callbacks
    def undo_shape_edit(self) -> None:
        """
        Undo the last shape editing operation.

        This method reverts the most recent shape modification by restoring
        the previous state from the undo stack. It updates the UI to reflect
        the restored state and refreshes the shape list display.

        Returns:
            None

        Examples:
            >>> # User modifies a shape, then wants to undo
            >>> app.undo_shape_edit()
            >>> # Shape returns to previous state
            
        Note:
            Automatically updates the label list, canvas display, and undo
            action availability. Also marks the document as dirty to indicate
            unsaved changes after the undo operation.
        """
        self.canvas.restore_shape()
        self.label_list.clear()
        self.load_shapes(self.canvas.shapes)
        self.actions.undo.setEnabled(self.canvas.is_shape_restorable)
        self.set_dirty()

    def get_label_file_list(self):
        label_file_list = []
        if not self.image_list and self.filename:
            dir_path, filename = osp.split(self.filename)
            label_file = osp.join(
                dir_path, osp.splitext(filename)[0] + ".json"
            )
            if osp.exists(label_file):
                label_file_list = [label_file]
        elif self.image_list and not self.output_dir and self.filename:
            file_list = os.listdir(osp.dirname(self.filename))
            for file_name in file_list:
                if not file_name.endswith(".json"):
                    continue
                label_file_list.append(
                    osp.join(osp.dirname(self.filename), file_name)
                )
        if self.output_dir:
            for file_name in os.listdir(self.output_dir):
                if not file_name.endswith(".json"):
                    continue
                label_file_list.append(osp.join(self.output_dir, file_name))
        return label_file_list

    def _tag_sort_label_path_for_image(self, image_path: Optional[str]) -> Optional[str]:
        if not image_path:
            return None
        label_path = osp.splitext(image_path)[0] + LabelFile.suffix
        if self.output_dir:
            label_path = osp.join(self.output_dir, osp.basename(label_path))
        return label_path

    def _tag_sort_current_label_file(self) -> Optional[str]:
        if self.label_file and getattr(self.label_file, "filename", None):
            return self.label_file.filename
        return self._tag_sort_label_path_for_image(self.filename)

    def _tag_sort_collect_from_images(self, image_paths: List[str]) -> Tuple[List[str], List[str]]:
        existing: List[str] = []
        missing: List[str] = []
        for image_path in image_paths:
            label_path = self._tag_sort_label_path_for_image(image_path)
            if not label_path:
                continue
            if osp.exists(label_path):
                existing.append(label_path)
            else:
                missing.append(label_path)
        return existing, missing

    def _tag_sort_collect_from_directory(self, directory: str) -> List[str]:
        if not directory:
            return []
        file_paths: List[str] = []
        try:
            for entry in os.listdir(directory):
                if entry.lower().endswith(LabelFile.suffix):
                    full_path = osp.join(directory, entry)
                    if osp.isfile(full_path):
                        file_paths.append(full_path)
        except Exception as exc:  # pragma: no cover - surface to UI
            logger.error(f"Failed to read directory {directory}: {exc}")
            return []
        return sorted(file_paths)

    @staticmethod
    def _tag_sort_normalize_paths(paths: List[str]) -> List[str]:
        unique: List[str] = []
        seen = set()
        for path in paths:
            if not path:
                continue
            resolved = osp.abspath(path)
            if not osp.exists(resolved):
                continue
            if resolved not in seen:
                seen.add(resolved)
                unique.append(resolved)
        return unique

    def union_selection(self):
        """
        Merges selected shapes into one shape.
        """
        rectangle_shapes, polygon_shapes, rotation_shapes = [], [], []
        for shape in self.canvas.selected_shapes:
            points = shape.points
            if shape.shape_type == "rectangle":
                xmin, ymin = (points[0].x(), points[0].y())
                xmax, ymax = (points[2].x(), points[2].y())
                rectangle_shapes.append([xmin, ymin, xmax, ymax])
            elif shape.shape_type == "rotation":
                # 旋转矩形：保存所有四个顶点和方向
                rotation_shapes.append({
                    'points': [(p.x(), p.y()) for p in points],
                    'direction': shape.direction if hasattr(shape, 'direction') else 0
                })
            else:
                polygon_shapes.append([(p.x(), p.y()) for p in points])

        union_shape = self.canvas.selected_shapes[0].copy()  # 使用第一个形状作为模板

        if len(rectangle_shapes) > 0:
            # 处理普通矩形合并
            min_x = min([bbox[0] for bbox in rectangle_shapes])
            min_y = min([bbox[1] for bbox in rectangle_shapes])
            max_x = max([bbox[2] for bbox in rectangle_shapes])
            max_y = max([bbox[3] for bbox in rectangle_shapes])

            union_shape.points[0].setX(min_x)
            union_shape.points[0].setY(min_y)
            union_shape.points[1].setX(max_x)
            union_shape.points[1].setY(min_y)
            union_shape.points[2].setX(max_x)
            union_shape.points[2].setY(max_y)
            union_shape.points[3].setX(min_x)
            union_shape.points[3].setY(max_y)
        elif len(rotation_shapes) > 0:
            # 处理旋转矩形合并
            all_points = []
            for rot_shape in rotation_shapes:
                all_points.extend(rot_shape['points'])

            # 找到包围所有点的最小外接矩形
            min_x = min([p[0] for p in all_points])
            min_y = min([p[1] for p in all_points])
            max_x = max([p[0] for p in all_points])
            max_y = max([p[1] for p in all_points])

            # 保持为旋转矩形类型
            union_shape.shape_type = "rotation"

            # 获取第一个旋转矩形的角度
            first_angle = rotation_shapes[0]['direction']
            union_shape.direction = first_angle

            # 根据角度计算旋转矩形的四个点
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            width = max_x - min_x
            height = max_y - min_y

            # 计算旋转矩形的四个角点
            import math
            cos_angle = math.cos(first_angle)
            sin_angle = math.sin(first_angle)
            half_w = width / 2
            half_h = height / 2

            # 未旋转的四个角点（相对于中心）
            corners = [
                [-half_w, -half_h],  # 左上
                [half_w, -half_h],   # 右上
                [half_w, half_h],    # 右下
                [-half_w, half_h]    # 左下
            ]

            # 旋转并设置到union_shape的points
            for i, (dx, dy) in enumerate(corners):
                # 旋转变换
                rotated_x = dx * cos_angle - dy * sin_angle + center_x
                rotated_y = dx * sin_angle + dy * cos_angle + center_y
                union_shape.points[i].setX(rotated_x)
                union_shape.points[i].setY(rotated_y)
        else:
            # Create a blank mask
            min_x = min([min(p[0] for p in poly) for poly in polygon_shapes])
            min_y = min([min(p[1] for p in poly) for poly in polygon_shapes])
            max_x = max([max(p[0] for p in poly) for poly in polygon_shapes])
            max_y = max([max(p[1] for p in poly) for poly in polygon_shapes])

            width = int(max_x - min_x + 10)
            height = int(max_y - min_y + 10)
            mask = np.zeros((height, width), dtype=np.uint8)

            # Draw all polygons on the mask
            for polygon in polygon_shapes:
                contour = np.array(polygon, dtype=np.int32)
                shifted_contour = contour - np.array(
                    [min_x - 5, min_y - 5], dtype=np.int32
                )
                shifted_contour = shifted_contour.reshape((-1, 1, 2))
                cv2.fillPoly(mask, [shifted_contour], 255)

            # Find contours of the merged shape
            merged_contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if merged_contours:
                largest_contour = max(merged_contours, key=cv2.contourArea)
                epsilon = 0.001 * cv2.arcLength(largest_contour, True)
                approx_contour = cv2.approxPolyDP(
                    largest_contour, epsilon, True
                )
                approx_contour = approx_contour.reshape(-1, 2) + np.array(
                    [min_x - 5, min_y - 5], dtype=np.int32
                )
                union_shape.points = [
                    QtCore.QPointF(float(x), float(y))
                    for x, y in approx_contour
                ]

        # Append merged shape and remove selected shapes
        self.add_label(union_shape)
        self.remove_labels(self.canvas.delete_selected())
        self.set_dirty()
        # Update expand margins dialog colors after union operation
        self._update_expand_margins_colors()

        # Update UI state
        if self.no_shape():
            for action in self.actions.on_shapes_present:
                action.setEnabled(False)

    # Trainer
    def start_training(self, mode):
        if mode == "ultralytics":
            dialog = UltralyticsDialog(self)
        else:
            return

        try:
            _ = dialog.exec_()
        except Exception as e:
            self.error_message(
                "Start Error", f"Failed to start training dialog: {str(e)}"
            )

    # Tools
    def overview(self):
        if self.filename:
            OverviewDialog(parent=self)

    def digit_shortcut_manager(self):
        if self.label_file is None:
            return

        digit_shortcut_dialog = DigitShortcutDialog(parent=self)
        if digit_shortcut_dialog.exec_():
            self._config["digit_shortcuts"] = self.drawing_digit_shortcuts
            save_config(self._config)
            self.load_digit_shortcuts()

    def open_label_toggle_shortcut_manager(self):
        if not self.label_file:
            return

        all_unique_labels = sorted(list(set(self._config["labels"]) | set(self.label_dialog.get_all_labels())))
        # Add labels from existing shortcuts that might not be in config or history yet
        for label_in_shortcut in self.label_toggle_shortcuts.values():
            if label_in_shortcut not in all_unique_labels:
                all_unique_labels.append(label_in_shortcut)
        all_unique_labels = sorted(list(set(all_unique_labels))) # Re-sort and unique after adding from shortcuts

        def get_label_qcolor_func(label_name):
            rgb = self._get_rgb_by_label(label_name)
            return QtGui.QColor(*rgb, LABEL_OPACITY)

        dialog = LabelToggleShortcutDialog(
            parent=self,
            shortcuts=self.label_toggle_shortcuts,
            all_unique_labels=all_unique_labels,
            get_label_qcolor_func=get_label_qcolor_func
        )
        
        if dialog.exec_():
            self.label_toggle_shortcuts = dialog.shortcuts
            self._config["label_toggle_shortcuts"] = self.label_toggle_shortcuts
            save_config(self._config)
            self.load_label_toggle_shortcuts()

    def load_label_toggle_shortcuts(self):
        # Clear existing shortcuts
        for shortcut in self.label_toggle_qshortcuts:
            shortcut.setEnabled(False)
            shortcut.setParent(None)
            shortcut.deleteLater()
        self.label_toggle_qshortcuts.clear()

        # Load from config
        self.label_toggle_shortcuts = self._config.get("label_toggle_shortcuts", {})
        for key, label in self.label_toggle_shortcuts.items():
            qshortcut = QtWidgets.QShortcut(QtGui.QKeySequence(key), self)
            qshortcut.activated.connect(
                functools.partial(self.toggle_label_visibility_by_name, label)
            )
            self.label_toggle_qshortcuts.append(qshortcut)

    def toggle_label_visibility_by_name(self, label_name):
        for i in range(self.unique_label_list.count()):
            item = self.unique_label_list.item(i)
            if item.data(Qt.UserRole) == label_name:
                item.setCheckState(
                    Qt.Unchecked
                    if item.checkState() == Qt.Checked
                    else Qt.Checked
                )
                return

    def label_manager(self):
        modify_label_dialog = LabelModifyDialog(
            parent=self, opacity=LABEL_OPACITY
        )
        result = modify_label_dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            self.load_file(self.filename)

    def object_manager(self):
        """Toggle the object manager dialog."""
        if self.object_manager_dialog is None:
            self.object_manager_dialog = ObjectManagerDialog(
                [item for item in self.label_list], self
            )
            self.object_manager_dialog.order_changed.connect(
                self.on_object_order_changed
            )
            self.object_manager_dialog.apply_to_all_requested.connect(
                self.on_apply_reorder_to_all
            )
            self.object_manager_dialog.selection_changed.connect(
                self.on_object_manager_selection_changed
            )
            self.canvas.selection_changed.connect(
                self.object_manager_dialog.sync_selection
            )
            self.object_manager_dialog.item_double_clicked.connect(
               self.on_object_manager_double_clicked
            )
            self.object_manager_dialog.edit_requested.connect(self.edit_label)
            self.object_manager_dialog.delete_requested.connect(
                self.delete_selected_shape
            )
            self.object_manager_dialog.union_requested.connect(self.union_selection)
            self.object_manager_dialog.setAttribute(
                QtCore.Qt.WA_DeleteOnClose, False
            )

        # Always update the items before showing, to reflect the latest state.
        self.object_manager_dialog.update_items([item for item in self.label_list])

        if self.object_manager_dialog.isVisible():
            # If visible, hide it (toggle off)
            self.object_manager_dialog.hide()
        else:
            # If not visible, show it (toggle on)
            self.object_manager_dialog.show()
            self.object_manager_dialog.raise_()
            self.object_manager_dialog.activateWindow()

    def on_object_order_changed(self, ordered_shapes):
        """Callback for when the object order is changed in the dialog."""
        # Check if order has actually changed
        current_shapes = [item.shape() for item in self.label_list]
        if ordered_shapes == current_shapes:
            return

        self.load_shapes(ordered_shapes, replace=True)
        self.set_dirty()
        self._update_all_item_orders()
        self.shape_list_changed.emit()

    def on_object_manager_selection_changed(self, selected_shapes):
        """Callback for selection changes in the object manager dialog."""
        self.canvas.select_shapes(selected_shapes)

    def on_object_manager_double_clicked(self, shape):
        """Callback for double-clicks in the object manager dialog."""
        item = self.label_list.find_item_by_shape(shape)
        if item:
            # Ensure the shape is selected before editing
            # To match the behavior of a single click, we ensure the item is
            # the only one selected before editing.
            if item not in self.label_list.selected_items():
                index = self.label_list.model().indexFromItem(item)
                self.label_list.selectionModel().setCurrentIndex(
                    index, QtCore.QItemSelectionModel.ClearAndSelect
                )
            self.edit_label(item)

    def on_apply_reorder_to_all(self, selected_categories, move_to_top):
        """Handle reordering shapes for all images based on selected categories."""
        if not self.image_list:
            self.status(self.tr("No images loaded."))
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            self.tr("确认操作"),
            self.tr(
                "您将要对当前目录下的全部 {} 张图片应用此对象顺序更改。\n"
                "此操作将直接修改 JSON 文件且无法撤销。\n\n"
                "您确定要继续吗？"
            ).format(len(self.image_list)),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        processed_files = 0
        modified_shapes_total = 0

        for image_path in self.image_list:
            label_file_path = osp.splitext(image_path)[0] + ".json"
            if self.output_dir:
                label_file_path = osp.join(self.output_dir, osp.basename(label_file_path))

            if not osp.exists(label_file_path):
                continue

            try:
                with open(label_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                shapes_data = data.get("shapes", [])
                if not shapes_data:
                    continue

                selected_shapes = []
                other_shapes = []
                for shape_dict in shapes_data:
                    if shape_dict.get("label") in selected_categories:
                        selected_shapes.append(shape_dict)
                    else:
                        other_shapes.append(shape_dict)

                if not selected_shapes:
                    continue

                if move_to_top:
                    new_shapes_data = selected_shapes + other_shapes
                else:
                    new_shapes_data = other_shapes + selected_shapes

                if new_shapes_data != shapes_data:
                    data["shapes"] = new_shapes_data
                    with open(label_file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    processed_files += 1
                    modified_shapes_total += len(selected_shapes)

            except Exception as e:
                logger.error(f"Failed to process file {label_file_path}: {e}")
                continue

        # Reload current file to reflect changes if it was modified
        if self.filename in self.image_list:
            self.load_file(self.filename)

        self.status(
            self.tr(
                "操作完成！已修改 {processed_files} 个文件，并对 {modified_shapes_total} 个对象进行了重新排序。"
            ).format(processed_files=processed_files, modified_shapes_total=modified_shapes_total)
        )

    def on_tag_sort_run_requested(self, payload):
        if self.tag_sort_thread and self.tag_sort_thread.isRunning():
            QtWidgets.QMessageBox.information(
                self,
                self.tr("排序进行中"),
                self.tr("请等待当前排序任务完成。"),
            )
            return

        options = payload.get("options")
        scope = payload.get("scope")

        if not options:
            QtWidgets.QMessageBox.information(
                self,
                self.tr("排序配置错误"),
                self.tr("排序配置信息缺失。"),
            )
            return

        # 只有在使用自定义排序线模式时才检查排序线
        if getattr(options, "spatial_mode", None) == "LINE_GUIDES" and not getattr(options, "line_guides", None):
            QtWidgets.QMessageBox.information(
                self,
                self.tr("缺少排序线"),
                self.tr("请先在工具窗口中绘制排序线后再执行。"),
            )
            return

        files: List[str] = []
        missing: List[str] = []

        if scope == "current":
            label_path = self._tag_sort_current_label_file()
            if label_path and osp.exists(label_path):
                files = [label_path]
            elif label_path:
                missing.append(label_path)
        elif scope == "all":
            files, missing = self._tag_sort_collect_from_images(self.image_list)
        elif scope == "range":
            start_index = payload.get("start_index", 0)
            end_index = payload.get("end_index", -1)
            image_list_slice = self.image_list[start_index : end_index + 1]
            files, missing = self._tag_sort_collect_from_images(image_list_slice)
        else:
            files = []

        files = self._tag_sort_normalize_paths(files)
        total = len(files)

        if scope == "current" and total == 0:
            QtWidgets.QMessageBox.information(
                self,
                self.tr("未找到标签文件"),
                self.tr("当前页面尚未保存标注或标签文件不存在。"),
            )
            if self.tag_sort_dialog:
                self.tag_sort_dialog.append_log(
                    self.tr("已取消：没有找到当前页面的标签文件。")
                )
            return

        if scope == "opened" and total == 0:
            QtWidgets.QMessageBox.information(
                self,
                self.tr("未找到标签文件"),
                self.tr("当前项目中没有可排序的标签文件。"),
            )
            if self.tag_sort_dialog:
                self.tag_sort_dialog.append_log(
                    self.tr("已取消：项目中没有可排序的标签文件。")
                )
            return

        if not files:
            QtWidgets.QMessageBox.information(
                self,
                self.tr("未找到标签文件"),
                self.tr("所选范围内没有可排序的标签文件。"),
            )
            if self.tag_sort_dialog:
                self.tag_sort_dialog.append_log(
                    self.tr("已取消：没有可排序的标签文件。")
                )
            return

        current_label = self._tag_sort_current_label_file()
        if self.dirty and current_label:
            normalized_current = osp.abspath(current_label)
            if normalized_current in files:
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("存在未保存的修改"),
                    self.tr("请先保存当前标注后再执行排序。"),
                )
                if self.tag_sort_dialog:
                    self.tag_sort_dialog.append_log(
                        self.tr("已取消：当前标注未保存。")
                    )
                return

        self.tag_sort_files = files
        self.tag_sort_scope = scope
        self.tag_sort_total = total
        self.tag_sort_last_payload = {
            "options": options,
            "scope": scope,
        }

        if self.tag_sort_dialog:
            self.tag_sort_dialog.set_busy(True)
            self.tag_sort_dialog.set_progress(0, total)
            start_msg = self.tr("开始排序，共 {count} 个文件。").format(count=total)
            self.tag_sort_dialog.append_log(start_msg)
            if missing:
                skip_msg = self.tr("跳过 {count} 个缺失的标签文件。").format(
                    count=len(missing)
                )
                self.tag_sort_dialog.append_log(skip_msg)

        self.tag_sort_thread = TagSortThread(files, options, self)
        self.tag_sort_thread.progress.connect(self.on_tag_sort_progress)
        self.tag_sort_thread.finished.connect(self.on_tag_sort_finished)
        self.tag_sort_thread.start()
    def on_tag_sort_progress(self, processed: int, total: int, outcome):
        filename = osp.basename(outcome.file_path) if outcome.file_path else ""
        if self.tag_sort_dialog:
            self.tag_sort_dialog.set_progress(processed, total)
            if outcome.success:
                if outcome.changed:
                    msg = self.tr("[{current}/{total}] {name} - 已重新排序").format(
                        current=processed, total=total, name=filename
                    )
                else:
                    msg = self.tr("[{current}/{total}] {name} - 无需调整").format(
                        current=processed, total=total, name=filename
                    )
            else:
                msg = self.tr("[{current}/{total}] {name} - 失败：{reason}").format(
                    current=processed,
                    total=total,
                    name=filename,
                    reason=outcome.message,
                )
            self.tag_sort_dialog.append_log(msg)
        status_msg = self.tr("正在排序 {name} ({current}/{total})").format(
            name=filename or "-",
            current=processed,
            total=total,
        )
        self.status(status_msg, 4000)

    def on_tag_sort_finished(
        self,
        outcomes: List[tag_sorting.SortOutcome],
        cancelled: bool,
    ):
        if self.tag_sort_dialog:
            self.tag_sort_dialog.set_busy(False)
            if self.tag_sort_total:
                self.tag_sort_dialog.set_progress(
                    self.tag_sort_total,
                    self.tag_sort_total,
                )

        self.status(self.tr("标签排序完成"), 4000)

        if self.tag_sort_thread:
            self.tag_sort_thread.deleteLater()
        self.tag_sort_thread = None

        if not outcomes:
            if cancelled and self.tag_sort_dialog:
                self.tag_sort_dialog.append_log(self.tr("排序已取消。"))
            return

        sorted_count = sum(1 for o in outcomes if o.success and o.changed)
        unchanged_count = sum(1 for o in outcomes if o.success and not o.changed)
        failed_count = sum(1 for o in outcomes if not o.success)

        if self.tag_sort_dialog:
            if cancelled:
                self.tag_sort_dialog.append_log(
                    self.tr("排序已取消，以下为已处理的统计。")
                )
            summary = self.tr(
                "排序完成：成功 {sorted_count} 个，保持不变 {unchanged} 个，失败 {failed} 个。"
            ).format(
                sorted_count=sorted_count,
                unchanged=unchanged_count,
                failed=failed_count,
            )
            self.tag_sort_dialog.append_log(summary)

        current_label = self._tag_sort_current_label_file()
        if current_label and self.filename:
            normalized_current = osp.abspath(current_label)
            changed_paths = {
                osp.abspath(outcome.file_path)
                for outcome in outcomes
                if outcome.success and outcome.changed and outcome.file_path
            }
            if normalized_current in changed_paths:
                self.queue_event(
                    functools.partial(self.load_file, self.filename)
                )

        self.tag_sort_files = []
        self.tag_sort_scope = None
        self.tag_sort_total = 0

    def gid_manager(self):
        modify_gid_dialog = GroupIDModifyDialog(parent=self)
        result = modify_gid_dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            self.load_file(self.filename)

    def open_chatbot(self):
        dialog = ChatbotDialog(self)
        _ = dialog.exec_()

    def open_expand_margins_dialog(self):
        """Toggle the expand margins dialog."""
        # Use all possible labels from config
        labels = self._config.get("labels", [])

        if not labels:
            self.error_message(
                self.tr("无可用标签"),
                self.tr("右侧标签列表中没有标签可用于配置。"),
            )
            return

        if self.expand_margins_dialog is None:
            self.expand_margins_dialog = ExpandMarginsDialog(labels, self)
            self.expand_margins_dialog.apply_current.connect(self.on_expand_margins_current)
            self.expand_margins_dialog.apply_selected.connect(self.on_expand_margins_selected)
            self.expand_margins_dialog.apply_all.connect(self.on_expand_margins_all)
            self.expand_margins_dialog.apply_all_in_range.connect(self.on_expand_margins_in_range)
            self.expand_margins_dialog.apply_single_label.connect(self.on_expand_margins_single_label)
            self.expand_margins_dialog.jump_to_image.connect(self.on_jump_to_image)
            self.expand_margins_dialog.apply_single_label_selected.connect(
                self.on_expand_margins_single_label_selected
            )
            self.expand_margins_dialog.setAttribute(
                QtCore.Qt.WA_DeleteOnClose, False
            )
        else:
            # Update the labels in the dialog every time it's opened
            self.expand_margins_dialog.update_labels(labels)
            # Refresh colors when reopening
            self.expand_margins_dialog.refresh_colors()

        # Set current page number before showing
        current_index = self.file_list_widget.currentRow()
        if current_index >= 0:
            self.expand_margins_dialog.set_current_page(current_index + 1)

        if self.expand_margins_dialog.isVisible():
            # If visible, check if it's minimized
            if self.expand_margins_dialog.isMinimized():
                # If minimized, restore to normal state
                self.expand_margins_dialog.showNormal()
                self.expand_margins_dialog.raise_()
                self.expand_margins_dialog.activateWindow()
            else:
                # If visible and not minimized, hide it (toggle off)
                self.expand_margins_dialog.hide()
        else:
            # If not visible, show it (toggle on)
            self.expand_margins_dialog.show()
            self.expand_margins_dialog.raise_()
            self.expand_margins_dialog.activateWindow()

    def open_tag_sort_dialog(self):
        """Open the tag sorting dialog window."""
        if self.tag_sort_dialog is None:
            self.tag_sort_dialog = TagSortDialog(self)
            self.tag_sort_dialog.run_requested.connect(self.on_tag_sort_run_requested)

        pixmap = None
        if hasattr(self.canvas, "pixmap") and self.canvas.pixmap is not None:
            pixmap = self.canvas.pixmap.copy()
        shapes_data = []
        try:
            shapes_data = [shape.to_dict() for shape in getattr(self.canvas, "shapes", [])]
        except Exception:  # noqa: BLE001
            shapes_data = []
        self.tag_sort_dialog.set_context(pixmap, shapes_data)

        if self.tag_sort_dialog.isVisible():
            self.tag_sort_dialog.raise_()
            self.tag_sort_dialog.activateWindow()
        else:
            self.tag_sort_dialog.show()

    def open_angle_correction_dialog(self):
        """Open the angle correction dialog window."""
        if not self.image_list:
            self.error_message(
                self.tr("No images loaded"),
                self.tr("Please load an image folder before using this tool."),
            )
            return

        if self.angle_correction_dialog is None:
            self.angle_correction_dialog = AngleCorrectionDialog(parent=self)
            self.angle_correction_dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

        if self.angle_correction_dialog.isVisible():
            self.angle_correction_dialog.raise_()
            self.angle_correction_dialog.activateWindow()
        else:
            self.angle_correction_dialog.show()

    def open_alignment_dialog(self):
        """Open the alignment tool dialog."""
        if self.alignment_dialog is None:
            self.alignment_dialog = AlignmentDialog(parent=self)
            self.alignment_dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
            # Connect signals
            self.alignment_dialog.select_reference.connect(self.on_select_reference_mode)
            self.alignment_dialog.closing.connect(self.on_alignment_dialog_finished)
            self.alignment_dialog.reset_mode.connect(self.on_alignment_dialog_finished) # Also clean up on reset
            self.alignment_dialog.select_all_same_label.connect(self.on_select_all_same_label)
            self.alignment_dialog.align_left.connect(lambda: self._perform_alignment('left'))
            self.alignment_dialog.align_h_center.connect(lambda: self._perform_alignment('h_center'))
            self.alignment_dialog.align_right.connect(lambda: self._perform_alignment('right'))
            self.alignment_dialog.align_top.connect(lambda: self._perform_alignment('top'))
            self.alignment_dialog.align_v_center.connect(lambda: self._perform_alignment('v_center'))
            self.alignment_dialog.align_bottom.connect(lambda: self._perform_alignment('bottom'))
            self.alignment_dialog.unify_height.connect(lambda: self._perform_alignment('unify_height'))
            self.alignment_dialog.unify_width.connect(lambda: self._perform_alignment('unify_width'))
            # Connect canvas signal
            self.canvas.reference_selected.connect(self.on_reference_shape_selected)

        if self.alignment_dialog.isVisible():
            self.alignment_dialog.raise_()
            self.alignment_dialog.activateWindow()
        else:
            self.alignment_dialog.show()

    def on_alignment_dialog_finished(self):
        """Cleanup when the alignment dialog is closed or reset."""
        self.canvas.set_alignment_target_mode(False)
        self.canvas.set_reference_selection_mode(False)
        if self.alignment_dialog:
            self.alignment_dialog.set_reference_mode(False)
        self.reference_shape = None
        self.canvas.set_reference_shape(None)
        self.canvas.deselect_shape()
        self.canvas.update()

    # --- Alignment Tool Handlers ---
    def on_select_reference_mode(self, is_active):
        """Enter/Exit the reference shape selection mode."""
        self.is_reference_selection_mode = is_active
        self.canvas.set_reference_selection_mode(is_active)
        if self.alignment_dialog:
            if is_active:
                self.alignment_dialog.log(self.tr("请在画布上单击一个矩形作为参照物。"))
                self.reference_shape = None
                self.canvas.set_reference_shape(None)
            else:
                pass

    def on_reference_shape_selected(self, shape):
        """Callback when a reference shape is selected on the canvas."""
        self.reference_shape = shape
        self.canvas.set_reference_shape(shape)
        if self.alignment_dialog:
            self.alignment_dialog.log(self.tr("已选定 '{label}' 为参照物。").format(label=shape.label))
            self.alignment_dialog.log(self.tr("请单击或多选需要对齐的矩形。"))
            self.alignment_dialog.set_reference_mode(False)
            # Switch button to orange target-selection prompt
            self.alignment_dialog.set_button_to_target_selection_mode()
            self.canvas.set_alignment_target_mode(True)

    def on_select_all_same_label(self):
        """Select all shapes on the canvas with the same label as the reference shape."""
        if not self.reference_shape:
            if self.alignment_dialog:
                self.alignment_dialog.log(self.tr("错误: 请先选择一个参照物。"))
            return

        ref_label = self.reference_shape.label
        current_selection = set(self.canvas.selected_shapes)
        
        for shape in self.canvas.shapes:
            if shape.label == ref_label and shape is not self.reference_shape:
                current_selection.add(shape)

        self.canvas.select_shapes(list(current_selection))
        if self.alignment_dialog:
            self.alignment_dialog.log(self.tr("已选中所有 '{label}' 标签的矩形。").format(label=ref_label))

    def _perform_alignment(self, mode):
        """Generic helper to perform all alignment and unify actions."""
        if not self.alignment_dialog:
            return

        self.alignment_dialog.log_widget.clear()

        if not self.reference_shape:
            self.alignment_dialog.log(self.tr("错误: 未指定参照物。"))
            return

        targets = [s for s in self.canvas.selected_shapes if s is not self.reference_shape]
        if not targets:
            self.alignment_dialog.log(self.tr("错误: 没有选中任何需要对齐的矩形。"))
            return

        filter_text = self.alignment_dialog.label_filter_input.text().strip()
        target_labels = {label.strip() for label in filter_text.split(',') if label.strip()}
        mode_display_map = {
            'left': self.tr('左对齐'),
            'right': self.tr('右对齐'),
            'h_center': self.tr('水平居中'),
            'top': self.tr('上对齐'),
            'bottom': self.tr('下对齐'),
            'v_center': self.tr('垂直居中'),
            'unify_width': self.tr('统一宽度'),
            'unify_height': self.tr('统一高度'),
        }
        display_mode = mode_display_map.get(mode, mode)
        self.alignment_dialog.log(self.tr("开始执行: {mode}").format(mode=display_mode))
        if target_labels:
            self.alignment_dialog.log(self.tr("目标标签: {labels}").format(labels=target_labels))

        ref_rect = self.reference_shape.bounding_rect()
        self.canvas.store_shapes()
        
        processed_count = 0
        for shape in targets:
            if target_labels and shape.label not in target_labels:
                self.alignment_dialog.log(self.tr("跳过 '{label}': 标签不匹配").format(label=shape.label))
                continue

            shape_rect = shape.bounding_rect()
            delta = QtCore.QPointF(0, 0)
            action_taken = False

            if mode == 'left':
                delta.setX(ref_rect.left() - shape_rect.left())
            elif mode == 'right':
                delta.setX(ref_rect.right() - shape_rect.right())
            elif mode == 'h_center':
                delta.setX(ref_rect.center().x() - shape_rect.center().x())
            elif mode == 'top':
                delta.setY(ref_rect.top() - shape_rect.top())
            elif mode == 'bottom':
                delta.setY(ref_rect.bottom() - shape_rect.bottom())
            elif mode == 'v_center':
                delta.setY(ref_rect.center().y() - shape_rect.center().y())
            
            if not delta.isNull():
                shape.move_by(delta)
                action_taken = True
            
            # Unify size
            if mode == 'unify_width' or mode == 'unify_height':
                if shape.shape_type == 'rectangle':
                    # Rebuild rectangle points explicitly from a QRectF to avoid
                    # unintended coupling between width/height changes due to point ordering
                    target_rect = shape.bounding_rect()
                    new_left = target_rect.left()
                    new_top = target_rect.top()
                    new_right = target_rect.right()
                    new_bottom = target_rect.bottom()

                    if mode == 'unify_width':
                        ref_width = ref_rect.width()
                        new_right = new_left + ref_width
                        action_taken = True
                    elif mode == 'unify_height':
                        ref_height = ref_rect.height()
                        new_bottom = new_top + ref_height
                        action_taken = True

                    # Apply the new rectangle with canonical TL, TR, BR, BL order
                    shape.points = [
                        QtCore.QPointF(new_left, new_top),
                        QtCore.QPointF(new_right, new_top),
                        QtCore.QPointF(new_right, new_bottom),
                        QtCore.QPointF(new_left, new_bottom),
                    ]
                elif shape.shape_type == 'rotation':
                    # Get intrinsic center and dimensions of the target rotated rectangle
                    target_center_x = (shape.points[0].x() + shape.points[1].x() + shape.points[2].x() + shape.points[3].x()) / 4.0
                    target_center_y = (shape.points[0].y() + shape.points[1].y() + shape.points[2].y() + shape.points[3].y()) / 4.0
                    target_center = QtCore.QPointF(target_center_x, target_center_y)

                    target_intrinsic_width = utils.distance(shape.points[1] - shape.points[0])
                    target_intrinsic_height = utils.distance(shape.points[2] - shape.points[1])

                    # Get intrinsic dimensions of the reference shape
                    if self.reference_shape.shape_type == 'rotation':
                        ref_intrinsic_width = utils.distance(self.reference_shape.points[1] - self.reference_shape.points[0])
                        ref_intrinsic_height = utils.distance(self.reference_shape.points[2] - self.reference_shape.points[1])
                    else:  # rectangle
                        ref_intrinsic_width = ref_rect.width()
                        ref_intrinsic_height = ref_rect.height()

                    new_intrinsic_width = target_intrinsic_width
                    new_intrinsic_height = target_intrinsic_height

                    if mode == 'unify_width':
                        new_intrinsic_width = ref_intrinsic_width
                    elif mode == 'unify_height':
                        new_intrinsic_height = ref_intrinsic_height

                    # Reconstruct the rotated rectangle's points using math rotation
                    half_w = new_intrinsic_width / 2.0
                    half_h = new_intrinsic_height / 2.0
                    angle = shape.direction

                    cos_a = math.cos(angle)
                    sin_a = math.sin(angle)

                    # Local, centered at (0,0)
                    p0_local = QtCore.QPointF(-half_w, -half_h)
                    p1_local = QtCore.QPointF(half_w, -half_h)
                    p2_local = QtCore.QPointF(half_w, half_h)
                    p3_local = QtCore.QPointF(-half_w, half_h)

                    def rot(pt):
                        return QtCore.QPointF(
                            pt.x() * cos_a - pt.y() * sin_a + target_center.x(),
                            pt.x() * sin_a + pt.y() * cos_a + target_center.y(),
                        )

                    shape.points = [rot(p0_local), rot(p1_local), rot(p2_local), rot(p3_local)]
                    action_taken = True
            
            if action_taken:
                processed_count += 1

        self.set_dirty()
        self.canvas.repaint()
        
        if processed_count > 0:
            self.alignment_dialog.log(self.tr("操作完成，共处理了 {count} 个矩形。").format(count=processed_count))
        else:
            self.alignment_dialog.log(self.tr("操作完成，未找到符合条件的矩形进行处理。"))

    def open_keymap_dialog(self):
        """Open or toggle the keymap dialog window, restoring if minimized."""
        # No labels check needed for keymap dialog

        if self.keymap_dialog is None:
            self.keymap_dialog = KeymapDialog(
                parent=self,
                config=self._config,
                shortcut_key=self._config["shortcuts"].get("keymap_dialog"), # Pass the shortcut key
            )
            self.keymap_dialog.accepted.connect(self._save_keymap_config)
            self.keymap_dialog.rejected.connect(self._cancel_keymap_config)
            self.keymap_dialog.config_saved.connect(self._update_canvas_speed_settings)
            self.keymap_dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        # No else block for updating labels/colors needed for keymap dialog

        # No current page number setting needed for keymap dialog

        if self.keymap_dialog.isVisible():
            # If visible, check if it's minimized
            if self.keymap_dialog.isMinimized():
                # If minimized, restore to normal state
                self.keymap_dialog.showNormal()
                self.keymap_dialog.raise_()
                self.keymap_dialog.activateWindow()
            else:
                # If visible and not minimized, hide it (toggle off)
                self.keymap_dialog.hide()
        else:
            # If not visible, show it (toggle on)
            self.keymap_dialog.show()
            self.keymap_dialog.raise_()
            self.keymap_dialog.activateWindow()


    def open_vqa(self):
        if not self.image_list:
            self.error_message(
                self.tr("No images loaded"),
                self.tr(
                    "Please load an image folder before opening the VQA dialog."
                ),
            )
            return

        if not hasattr(self, "vqa_window") or self.vqa_window is None:
            self.vqa_window = VQADialog(self)
            self.vqa_window.setAttribute(Qt.WA_DeleteOnClose, False)
        if self.vqa_window.isVisible():
            self.vqa_window.raise_()
            self.vqa_window.activateWindow()
        else:
            self.vqa_window.show()

    def _save_keymap_config(self):
        """Slot to save keymap config when dialog is accepted."""
        if self.keymap_dialog:
            keymap_config = self.keymap_dialog.get_config()
            self._config["keymap"] = keymap_config
            save_config(self._config)
            # Update canvas speed settings
            speed_settings = self._config.get("speed_settings", {})
            self.canvas.update_speed_settings(speed_settings)

    def _cancel_keymap_config(self):
        """Slot to handle keymap dialog rejection (optional)."""
        # No action needed on cancel, as config is only saved on accept
        pass

    def _update_canvas_speed_settings(self, keymap_config: dict):
        """Update canvas speed settings and key actions from the keymap dialog."""
        speed_settings = keymap_config.get("speed_settings", {})
        self.canvas.update_speed_settings(speed_settings)

        # Pass the entire keymap_config to canvas to handle key actions
        self.canvas.update_key_actions(keymap_config)

    # Help
    def documentation(self):
        url = (
            "https://github.com/CVHub520/X-AnyLabeling/tree/main/docs"  # NOQA
        )
        utils.general.open_url(url)

    def about(self):
        about_dialog = AboutDialog(self)
        _ = about_dialog.exec_()

    def loop_thru_labels(self):
        self.label_loop_count += 1
        if len(self.label_list) == 0 or self.label_loop_count >= len(
            self.label_list
        ):
            # If we go through all the things go back to 100%
            self.label_loop_count = -1
            self.set_zoom(int(100 * self.scale_fit_window()))
            return

        width = self.central_widget().width() - 2.0
        height = self.central_widget().height() - 2.0

        im_width = self.canvas.pixmap.width()
        im_height = self.canvas.pixmap.height()

        zoom_scale = 4

        item = self.label_list[self.label_loop_count]
        xs = []
        ys = []
        # loop through all points on this label
        for point in item.shape().points:
            xs.append(point.x())
            ys.append(point.y())

        # Set minimum label width to 30px this should handle point
        # lables and very tiny labels gracefully
        label_width = max(int(max(xs) - min(xs)), 30)
        x = (max(xs) + min(xs)) / 2
        y = (max(ys) + min(ys)) / 2

        zoom = int(100 * width / (zoom_scale * label_width))
        # Don't go past the max zoom which is 1000
        zoom = min(1000, zoom)

        self.set_zoom(zoom)

        x_range = self.scroll_bars[Qt.Horizontal].maximum()
        x_step = self.scroll_bars[Qt.Horizontal].pageStep()

        y_range = self.scroll_bars[Qt.Vertical].maximum()
        # QT docs says Document length = maximum() - minimum() + pageStep().
        # so there's a weird pageStep thing we gotta add
        y_step = self.scroll_bars[Qt.Vertical].pageStep()
        screen_width = width / (zoom / 100)
        # add half a screen to this
        x_scroll = int((x - screen_width / 2) / im_width * (x_range + x_step))
        x_scroll = min(max(0, x_scroll), x_range)

        screen_height = height / (zoom / 100)

        y_scroll = int(
            (y - screen_height / 2) / (im_height) * (y_range + y_step)
        )
        y_scroll = min(max(0, y_scroll), y_range)

        self.set_scroll(Qt.Horizontal, x_scroll)
        self.set_scroll(Qt.Vertical, y_scroll)
        for shape in self.canvas.selected_shapes:
            shape.selected = False
        self.canvas.prev_h_shape = self.canvas.h_hape = item.shape()
        self.canvas.update()

    def copy_to_clipboard(self, text):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(
            self,
            self.tr("Copied"),
            self.tr("The information has been copied to the clipboard."),
        )

    # General
    def toggle_drawing_sensitive(self, drawing=True):
        """Toggle drawing sensitive.

        In the middle of drawing, toggling between modes should be disabled.
        """
        self.actions.edit_mode.setEnabled(not drawing)
        self.actions.undo_last_point.setEnabled(drawing)
        self.actions.undo.setEnabled(not drawing)
        self.actions.delete.setEnabled(not drawing)
        self.actions.union_selection.setEnabled(not drawing)

    def create_digit_mode(self, digit_num):
        if self.drawing_digit_shortcuts is None:
            return

        data = self.drawing_digit_shortcuts.get(digit_num, None)
        if not data:
            return

        label = data.get("label", "object")
        create_mode = data.get("mode", None)

        if create_mode not in [
            "polygon",
            "rectangle",
            "rotation",
            "rotation3",
            "circle",
            "line",
            "point",
            "linestrip",
        ]:
            return

        self.digit_to_label = label
        self.toggle_draw_mode(edit=False, create_mode=create_mode)

    def toggle_draw_mode(
        self, edit=True, create_mode="rectangle", disable_auto_labeling=True
    ):
        # Define modes that should have the auto-crosshair feature.
        auto_crosshair_modes = {"rotation", "rectangle", "rotation3"}

        # Restore crosshair if we are leaving a mode for which it was auto-enabled.
        if self.canvas.create_mode in auto_crosshair_modes and self._crosshair_was_toggled_for_drawing:
            is_leaving_special_mode = edit or create_mode != self.canvas.create_mode
            if is_leaving_special_mode:
                self.restore_crosshair_if_needed()

        # Disable auto labeling if needed
        if (
            disable_auto_labeling
            and self.auto_labeling_widget.auto_labeling_mode
            != AutoLabelingMode.NONE
        ):
            self.clear_auto_labeling_marks()
            self.auto_labeling_widget.set_auto_labeling_mode(None)

        self.set_text_editing(False)

        self.canvas.set_editing(edit)
        self.canvas.create_mode = create_mode
        if edit:
            self.actions.create_mode.setEnabled(True)
            self.actions.create_rectangle_mode.setEnabled(True)
            self.actions.create_rotation_mode.setEnabled(True)
            self.actions.create_rotation3_mode.setEnabled(True)
            self.actions.create_circle_mode.setEnabled(True)
            self.actions.create_line_mode.setEnabled(True)
            self.actions.create_point_mode.setEnabled(True)
            self.actions.create_line_strip_mode.setEnabled(True)
            self.actions.digit_shortcut_0.setEnabled(True)
            self.actions.digit_shortcut_1.setEnabled(True)
            self.actions.digit_shortcut_2.setEnabled(True)
            self.actions.digit_shortcut_3.setEnabled(True)
            self.actions.digit_shortcut_4.setEnabled(True)
            self.actions.digit_shortcut_5.setEnabled(True)
            self.actions.digit_shortcut_6.setEnabled(True)
            self.actions.digit_shortcut_7.setEnabled(True)
            self.actions.digit_shortcut_8.setEnabled(True)
            self.actions.digit_shortcut_9.setEnabled(True)
        else:
            self.actions.union_selection.setEnabled(False)
            
            # Automatically toggle crosshair for specific modes
            if create_mode in auto_crosshair_modes and not self._config["canvas"]["crosshair"]["show"]:
                self.toggle_crosshair()
                self._crosshair_was_toggled_for_drawing = True

            if create_mode == "polygon":
                self.actions.create_mode.setEnabled(False)
                self.actions.create_rectangle_mode.setEnabled(True)
                self.actions.create_rotation_mode.setEnabled(True)
                self.actions.create_rotation3_mode.setEnabled(True)
                self.actions.create_circle_mode.setEnabled(True)
                self.actions.create_line_mode.setEnabled(True)
                self.actions.create_point_mode.setEnabled(True)
                self.actions.create_line_strip_mode.setEnabled(True)
            elif create_mode == "rectangle":
                self.actions.create_mode.setEnabled(True)
                self.actions.create_rectangle_mode.setEnabled(False)
                self.actions.create_rotation_mode.setEnabled(True)
                self.actions.create_rotation3_mode.setEnabled(True)
                self.actions.create_circle_mode.setEnabled(True)
                self.actions.create_line_mode.setEnabled(True)
                self.actions.create_point_mode.setEnabled(True)
                self.actions.create_line_strip_mode.setEnabled(True)
            elif create_mode == "line":
                self.actions.create_mode.setEnabled(True)
                self.actions.create_rectangle_mode.setEnabled(True)
                self.actions.create_rotation_mode.setEnabled(True)
                self.actions.create_rotation3_mode.setEnabled(True)
                self.actions.create_circle_mode.setEnabled(True)
                self.actions.create_line_mode.setEnabled(False)
                self.actions.create_point_mode.setEnabled(True)
                self.actions.create_line_strip_mode.setEnabled(True)
            elif create_mode == "point":
                self.actions.create_mode.setEnabled(True)
                self.actions.create_rectangle_mode.setEnabled(True)
                self.actions.create_rotation_mode.setEnabled(True)
                self.actions.create_rotation3_mode.setEnabled(True)
                self.actions.create_circle_mode.setEnabled(True)
                self.actions.create_line_mode.setEnabled(True)
                self.actions.create_point_mode.setEnabled(False)
                self.actions.create_line_strip_mode.setEnabled(True)
            elif create_mode == "circle":
                self.actions.create_mode.setEnabled(True)
                self.actions.create_rectangle_mode.setEnabled(True)
                self.actions.create_rotation_mode.setEnabled(True)
                self.actions.create_rotation3_mode.setEnabled(True)
                self.actions.create_circle_mode.setEnabled(False)
                self.actions.create_line_mode.setEnabled(True)
                self.actions.create_point_mode.setEnabled(True)
                self.actions.create_line_strip_mode.setEnabled(True)
            elif create_mode == "linestrip":
                self.actions.create_mode.setEnabled(True)
                self.actions.create_rectangle_mode.setEnabled(True)
                self.actions.create_rotation_mode.setEnabled(True)
                self.actions.create_rotation3_mode.setEnabled(True)
                self.actions.create_circle_mode.setEnabled(True)
                self.actions.create_line_mode.setEnabled(True)
                self.actions.create_point_mode.setEnabled(True)
                self.actions.create_line_strip_mode.setEnabled(False)
            elif create_mode == "rotation":
                self.actions.create_mode.setEnabled(True)
                self.actions.create_rectangle_mode.setEnabled(True)
                self.actions.create_rotation_mode.setEnabled(False)
                self.actions.create_rotation3_mode.setEnabled(True)
                self.actions.create_circle_mode.setEnabled(True)
                self.actions.create_line_mode.setEnabled(True)
                self.actions.create_point_mode.setEnabled(True)
                self.actions.create_line_strip_mode.setEnabled(True)
            elif create_mode == "rotation3":
                self.actions.create_mode.setEnabled(True)
                self.actions.create_rectangle_mode.setEnabled(True)
                self.actions.create_rotation_mode.setEnabled(True)
                self.actions.create_rotation3_mode.setEnabled(False)
                self.actions.create_circle_mode.setEnabled(True)
                self.actions.create_line_mode.setEnabled(True)
                self.actions.create_point_mode.setEnabled(True)
                self.actions.create_line_strip_mode.setEnabled(True)
            else:
                raise ValueError(f"Unsupported create_mode: {create_mode}")
        self.actions.edit_mode.setEnabled(not edit)
        self.label_instruction.setText(self.get_labeling_instruction())

    def set_edit_mode(self):
        # Disable auto labeling
        self.clear_auto_labeling_marks()
        self.auto_labeling_widget.set_auto_labeling_mode(None)

        self.toggle_draw_mode(True)
        self.set_text_editing(True)
        self.label_instruction.setText(self.get_labeling_instruction())

    def update_file_menu(self):
        """Update the 'Open Recent' menu with recent folders (not files)."""
        def exists(path):
            return osp.exists(str(path))

        def truncate_path(path, max_length=200):
            """Truncate path to max_length characters if needed."""
            if len(path) <= max_length:
                return path
            return path[:max_length] + "..."

        def make_folder_opener(folder_path):
            """Create a function that opens the given folder - avoids closure issues."""
            def open_folder():
                # Respect the "load_subfolders" setting when opening from recent folders
                recursive = self._config.get("load_subfolders", False)
                self.import_image_folder(folder_path, recursive=recursive)
            return open_folder

        menu = self.menus.recent_files
        menu.clear()

        # Filter out non-existent folders
        folders = [f for f in self.recent_folders if exists(f)]

        if folders:
            # Add folder entries (max 50)
            for i, folder_path in enumerate(folders):
                icon = utils.new_icon("open")
                # Truncate display text if path is too long
                display_path = truncate_path(folder_path, 200)
                menu_text = "&%d %s" % (i + 1, display_path)
                action = QtWidgets.QAction(icon, menu_text, self)
                # Connect each action's triggered signal directly
                action.triggered.connect(make_folder_opener(folder_path))
                menu.addAction(action)

            # Add separator
            menu.addSeparator()

        # Add "Clear Recent History" option
        clear_action = QtWidgets.QAction(
            utils.new_icon("cancel"),
            self.tr("清除最近打开的历史"),
            self
        )
        clear_action.triggered.connect(self._clear_recent_folders)
        menu.addAction(clear_action)

    def _clear_recent_folders(self):
        """Clear all recent folder history."""
        self.recent_folders = []
        self.settings.setValue("recent_folders", self.recent_folders)
        self.update_file_menu()

    def pop_label_list_menu(self, point):
        self.menus.label_list.exec_(self.label_list.mapToGlobal(point))

    def validate_label(self, label):
        # no validation
        if self._config["validate_label"] is None:
            return True

        for i in range(self.unique_label_list.count()):
            label_i = self.unique_label_list.item(i).data(Qt.UserRole)
            if self._config["validate_label"] in ["exact"]:
                if label_i == label:
                    return True
        return False

        def _on_angle_preview_changed(self, angle_degrees):
            angle_radians = math.radians(angle_degrees)
            for shape in self.canvas.selected_shapes:
                if shape.shape_type == 'rotation':
                    self.canvas.set_shape_rotation(shape, angle_radians)
            self.set_dirty()  # Mark as dirty to enable saving
    
        def batch_edit_labels(self, shapes):
            if not self._batch_edit_warning_shown:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    self.tr("Batch Edit"),
                    self.tr(
                        "You are about to edit multiple shapes in batch mode. "
                        "This operation cannot be undone.\n\n"
                        "This warning will only be shown once. Do you want to continue?"
                    ),
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No,
                )
    
                if reply != QtWidgets.QMessageBox.Yes:
                    return
    
                self._batch_edit_warning_shown = True
    
            first_shape = shapes[0]
    
            # Check if all selected shapes are of the same type and are rotation
            are_all_rotation = all(s.shape_type == 'rotation' for s in shapes)
            
            # Connect for live preview if all are rotation shapes
            if are_all_rotation:
                self.label_dialog.angle_changed.connect(self._on_angle_preview_changed)
    
            # For pop_up, we can pass shape_type if all are rotation.
            # Direction can be None, which will default to 0 in the dialog.
            shape_type_for_dialog = 'rotation' if are_all_rotation else None
            
            result = self.label_dialog.pop_up(
                text=first_shape.label,
                flags=first_shape.flags,
                group_id=first_shape.group_id,
                description=first_shape.description,
                difficult=first_shape.difficult,
                kie_linking=first_shape.kie_linking,
                move_mode="center",
                order=None,  # Disable order editing in batch mode
                shape_type=shape_type_for_dialog,
                direction=None # Let dialog default to 0 for batch edit
            )
    
            # Disconnect after dialog is closed
            if are_all_rotation:
                try:
                    self.label_dialog.angle_changed.disconnect(self._on_angle_preview_changed)
                except TypeError:
                    pass
    
            if result[0] is None:
                # User cancelled, revert any preview changes
                self.load_shapes(self.canvas.shapes, replace=True)
                return
    
            text, flags, group_id, description, difficult, kie_linking, _, new_direction = result
    
            if not self.validate_label(text):
                self.error_message(
                    self.tr("Invalid label"),
                    self.tr("Invalid label '{}' with validation type '{}'").format(
                        text, self._config["validate_label"]
                    ),
                )
                return
    
            for shape in shapes:
                if self.attributes and text:
                    text = self.reset_attribute(text)
    
                shape.label = text
                shape.flags = flags
                shape.group_id = group_id
                shape.description = description
                shape.difficult = difficult
                shape.kie_linking = kie_linking
                
                if are_all_rotation and new_direction is not None:
                    shape.direction = new_direction
    
                self._update_shape_color(shape)
    
                item = self.label_list.find_item_by_shape(shape)
                if item is not None:
                    color = shape.fill_color.getRgb()[:3]
                    item.setBackground(QtGui.QColor(*color, LABEL_OPACITY))
    
            self.label_dialog.add_label_history(text)
    
            if not self.unique_label_list.find_items_by_label(text):
                unique_label_item = self.unique_label_list.create_item_from_label(
                    text
                )
                self.unique_label_list.addItem(unique_label_item)
                rgb = self._get_rgb_by_label(text)
                self.unique_label_list.set_item_label(
                    unique_label_item, text, rgb, LABEL_OPACITY
                )
    
            self.set_dirty()
            self._update_all_item_orders()
            self.update_combo_box()
            self.update_gid_box()
            self.update_label_counts()
            self.shape_list_changed.emit()
    def _on_angle_preview_changed(self, angle_degrees):
        angle_radians = math.radians(angle_degrees)
        for shape in self.canvas.selected_shapes:
            if shape.shape_type == 'rotation':
                self.canvas.set_shape_rotation(shape, angle_radians)
        self.set_dirty()  # Mark as dirty to enable saving

    def batch_edit_labels(self, shapes):
        if not self._batch_edit_warning_shown:
            reply = QtWidgets.QMessageBox.question(
                self,
                self.tr("Batch Edit"),
                self.tr(
                    "You are about to edit multiple shapes in batch mode. "
                    "This operation cannot be undone.\n\n"
                    "This warning will only be shown once. Do you want to continue?"
                ),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )

            if reply != QtWidgets.QMessageBox.Yes:
                return

            self._batch_edit_warning_shown = True

        first_shape = shapes[0]

        # Check if all selected shapes are of the same type and are rotation
        are_all_rotation = all(s.shape_type == 'rotation' for s in shapes)
        
        # Connect for live preview if all are rotation shapes
        if are_all_rotation:
            self.label_dialog.angle_changed.connect(self._on_angle_preview_changed)

        # For pop_up, we can pass shape_type if all are rotation.
        # Direction can be None, which will default to 0 in the dialog.
        shape_type_for_dialog = 'rotation' if are_all_rotation else None
        
        result = self.label_dialog.pop_up(
            text=first_shape.label,
            flags=first_shape.flags,
            group_id=first_shape.group_id,
            description=first_shape.description,
            difficult=first_shape.difficult,
            kie_linking=first_shape.kie_linking,
            move_mode="center",
            order=None,  # Disable order editing in batch mode
            shape_type=shape_type_for_dialog,
            direction=None # Let dialog default to 0 for batch edit
        )

        # Disconnect after dialog is closed
        if are_all_rotation:
            try:
                self.label_dialog.angle_changed.disconnect(self._on_angle_preview_changed)
            except TypeError:
                pass

        if result[0] is None:
            # User cancelled, revert any preview changes
            self.load_shapes(self.canvas.shapes, replace=True)
            return

        text, flags, group_id, description, difficult, kie_linking, _, new_direction = result

        if not self.validate_label(text):
            self.error_message(
                self.tr("Invalid label"),
                self.tr("Invalid label '{}' with validation type '{}'").format(
                    text, self._config["validate_label"]
                ),
            )
            return

        for shape in shapes:
            if self.attributes and text:
                text = self.reset_attribute(text)

            shape.label = text
            shape.flags = flags
            shape.group_id = group_id
            shape.description = description
            shape.difficult = difficult
            shape.kie_linking = kie_linking
            
            if are_all_rotation and new_direction is not None:
                shape.direction = new_direction

            self._update_shape_color(shape)

            item = self.label_list.find_item_by_shape(shape)
            if item is not None:
                color = shape.fill_color.getRgb()[:3]
                item.setBackground(QtGui.QColor(*color, LABEL_OPACITY))

        self.label_dialog.add_label_history(text)

        if not self.unique_label_list.find_items_by_label(text):
            unique_label_item = self.unique_label_list.create_item_from_label(
                text
            )
            self.unique_label_list.addItem(unique_label_item)
            rgb = self._get_rgb_by_label(text)
            self.unique_label_list.set_item_label(
                unique_label_item, text, rgb, LABEL_OPACITY
            )

        self.set_dirty()
        # Update expand margins dialog colors after batch label modification
        self._update_expand_margins_colors()
        self._update_all_item_orders()
        self.update_combo_box()
        self.update_gid_box()
        self.update_label_counts()
        self.shape_list_changed.emit()

    def edit_label(self, item=None):
        if item and not isinstance(item, LabelListWidgetItem):
            raise TypeError("item must be LabelListWidgetItem type")

        if not self.canvas.editing():
            return

        selected_shapes = self.canvas.selected_shapes
        if not selected_shapes:
            return

        if len(selected_shapes) > 1:
            return self.batch_edit_labels(selected_shapes)

        if not item:
            item = self.current_item()
        if item is None:
            return
        shape = item.shape()
        if shape is None:
            return
        current_order = self.label_list.model().indexFromItem(item).row() + 1
        
        # Connect for live preview
        if shape.shape_type == 'rotation':
            self.label_dialog.angle_changed.connect(self._on_angle_preview_changed)

        direction = getattr(shape, 'direction', None)
        (
            text,
            flags,
            group_id,
            description,
            difficult,
            kie_linking,
            new_order,
            new_direction,
        ) = self.label_dialog.pop_up(
            text=shape.label,
            flags=shape.flags,
            group_id=shape.group_id,
            description=shape.description,
            difficult=shape.difficult,
            kie_linking=shape.kie_linking,
            move_mode=self._config.get("move_mode", "auto"),
            order=current_order,
            direction=direction,
            shape_type=shape.shape_type,
        )

        # Disconnect after dialog is closed
        if shape.shape_type == 'rotation':
            try:
                self.label_dialog.angle_changed.disconnect(self._on_angle_preview_changed)
            except TypeError:
                pass # Fails if the connection was already broken, which is fine.

        if text is None:
            # User cancelled, revert any preview changes by reloading the shape state
            self.load_shapes(self.canvas.shapes, replace=True)
            return

        if not self.validate_label(text):
            self.error_message(
                self.tr("Invalid label"),
                self.tr("Invalid label '{}' with validation type '{}'").format(
                    text, self._config["validate_label"]
                ),
            )
            return
        if self.attributes and text:
            text = self.reset_attribute(text)
        shape.label = text
        shape.flags = flags
        shape.group_id = group_id
        shape.description = description
        shape.difficult = difficult
        shape.kie_linking = kie_linking
        if shape.shape_type == "rotation" and new_direction is not None:
            # Use set_shape_rotation to ensure points are updated to match the final angle
            self.canvas.set_shape_rotation(shape, new_direction)

        # Add to label history
        self.label_dialog.add_label_history(shape.label)

        # Update unique label list
        if not self.unique_label_list.find_items_by_label(shape.label):
            unique_label_item = self.unique_label_list.create_item_from_label(
                shape.label
            )
            self.unique_label_list.addItem(unique_label_item)
            rgb = self._get_rgb_by_label(shape.label)
            self.unique_label_list.set_item_label(
                unique_label_item, shape.label, rgb, LABEL_OPACITY
            )

        self._update_shape_color(shape)
        color = shape.fill_color.getRgb()[:3]
        item.setBackground(QtGui.QColor(*color, LABEL_OPACITY))

        self.set_dirty()

        # Update expand margins dialog colors after label modification
        self._update_expand_margins_colors()

        # Handle reordering if the order was changed
        if (
            new_order is not None
            and new_order != current_order
            and 1 <= new_order <= len(self.label_list)
        ):
            all_shapes = [it.shape() for it in self.label_list]
            shape_to_move = all_shapes.pop(current_order - 1)
            all_shapes.insert(new_order - 1, shape_to_move)
            self.load_shapes(all_shapes, replace=True)

        self._update_all_item_orders()
        self.update_combo_box()
        self.update_gid_box()
        self.update_label_counts()
        self.shape_list_changed.emit()

    def file_search_changed(self):
        current_file = self.filename
        pattern = self.file_search.text()
        self.import_image_folder(
            self.last_open_dir,
            pattern=pattern,
            load=False,
        )
        if not pattern and current_file in self.fn_to_index:
            try:
                index = self.fn_to_index[current_file]
                item = self.file_list_widget.item(index)
                if item:
                    self._programmatic_selection_change = True
                    self.file_list_widget.setCurrentItem(item)
                    self.file_list_widget.scrollToItem(item)
                    self._programmatic_selection_change = False
            except KeyError:
                # This can happen if the file is no longer in the list after a filter change, which is fine.
                pass

    def file_selection_changed(self):
        if self._programmatic_selection_change:
            return
        items = self.file_list_widget.selectedItems()
        if not items:
            return
        item = items[0]
        
        if not self.may_continue():
            return
        
        # Update expand margins dialog if it is visible
        if self.expand_margins_dialog and self.expand_margins_dialog.isVisible():
            current_index = self.file_list_widget.currentRow()
            if current_index >= 0:
                self.expand_margins_dialog.set_current_page(current_index + 1)

        # Update expand margins dialog if it is visible
        if self.expand_margins_dialog and self.expand_margins_dialog.isVisible():
            current_index = self.file_list_widget.currentRow()
            if current_index >= 0:
                self.expand_margins_dialog.set_current_page(current_index + 1)

        # Get actual filename (use UserRole for reliability)
        filename = item.data(Qt.UserRole)
        if not filename:
            filename = item.text()

        current_index = self.fn_to_index[str(filename)]
        if current_index < len(self.image_list):
            filename = self.image_list[current_index]
            if filename:
                self.load_file(filename)
                if self.attributes:
                    # Clear the history widgets from the QGridLayout
                    self.grid_layout = QGridLayout()
                    self.grid_layout_container = QWidget()
                    self.grid_layout_container.setLayout(self.grid_layout)
                    self.scroll_area.setWidget(self.grid_layout_container)
                    self.scroll_area.setWidgetResizable(True)
                    # Create a container widget for the grid layout
                    self.grid_layout_container = QWidget()
                    self.grid_layout_container.setLayout(self.grid_layout)
                    self.scroll_area.setWidget(self.grid_layout_container)

    def attribute_selection_changed(self, i, property, combo):
        # This function is called when the user changes the value in a QComboBox
        # It updates the shape's attributes and saves them immediately
        selected_option = combo.currentText()
        self.canvas.shapes[i].attributes[property] = selected_option
        self.save_attributes(self.canvas.shapes)

    def update_selected_options(self, selected_options):
        if not isinstance(selected_options, dict):
            # Handle the case where `selected_options`` is not valid
            return
        for row in range(len(selected_options)):
            category_label = None
            property_combo = None
            if self.grid_layout.itemAtPosition(row, 0):
                category_label = self.grid_layout.itemAtPosition(
                    row, 0
                ).widget()
            if self.grid_layout.itemAtPosition(row, 1):
                property_combo = self.grid_layout.itemAtPosition(
                    row, 1
                ).widget()
            if category_label and property_combo:
                category = category_label.text()
                if category in selected_options:
                    selected_option = selected_options[category]
                    index = property_combo.findText(selected_option)
                    if index >= 0:
                        property_combo.setCurrentIndex(index)
        return

    def update_attributes(self, i):
        selected_options = {}
        update_shape = self.canvas.shapes[i]
        update_category = update_shape.label
        update_attribute = update_shape.attributes
        current_attibute = self.attributes[update_category]
        # Clear the existing widgets from the QGridLayout
        self.grid_layout = QGridLayout()
        # Repopulate the QGridLayout with the updated data
        for row, (property, options) in enumerate(current_attibute.items()):
            property_label = QLabel(property)
            property_combo = QComboBox()
            property_combo.addItems(options)
            property_combo.currentIndexChanged.connect(
                lambda _, property=property, combo=property_combo: self.attribute_selection_changed(
                    i, property, combo
                )
            )
            self.grid_layout.addWidget(property_label, row, 0)
            self.grid_layout.addWidget(property_combo, row, 1)
            selected_options[property] = options[0]
        # Ensure the scroll_area updates its contents
        self.grid_layout_container = QWidget()
        self.grid_layout_container.setLayout(self.grid_layout)
        self.scroll_area.setWidget(self.grid_layout_container)
        self.scroll_area.setWidgetResizable(True)

        if update_attribute:
            for property, option in update_attribute.items():
                selected_options[property] = option
            self.update_selected_options(selected_options)
        else:
            update_shape.attributes = selected_options
            self.canvas.shapes[i] = update_shape
            self.save_attributes(self.canvas.shapes)

    def save_attributes(self, _shapes):
        filename = osp.splitext(self.image_path)[0] + ".json"
        if self.output_dir:
            label_file_without_path = osp.basename(filename)
            filename = osp.join(self.output_dir, label_file_without_path)
        label_file = LabelFile()

        def format_shape(s):
            data = s.other_data.copy()
            info = {
                "label": s.label,
                "points": [(p.x(), p.y()) for p in s.points],
                "group_id": s.group_id,
                "description": s.description,
                "difficult": s.difficult,
                "shape_type": s.shape_type,
                "flags": s.flags,
                "attributes": s.attributes,
                "kie_linking": s.kie_linking,
            }
            if s.shape_type == "rotation":
                info["direction"] = s.direction
            data.update(info)

            return data

        # Get current shapes
        # Excluding auto labeling special shapes
        shapes = [
            format_shape(shape)
            for shape in _shapes
            if shape.label
            not in [
                AutoLabelingMode.OBJECT,
                AutoLabelingMode.ADD,
                AutoLabelingMode.REMOVE,
            ]
        ]
        flags = {}
        for i in range(self.flag_widget.count()):
            item = self.flag_widget.item(i)
            key = item.text()
            flag = item.checkState() == Qt.Checked
            flags[key] = flag
        try:
            image_path = osp.relpath(self.image_path, osp.dirname(filename))
            image_data = (
                self.image_data if self._config["store_data"] else None
            )
            if osp.dirname(filename) and not osp.exists(osp.dirname(filename)):
                os.makedirs(osp.dirname(filename))
            label_file.save(
                filename=filename,
                shapes=shapes,
                image_path=image_path,
                image_data=image_data,
                image_height=self.image.height(),
                image_width=self.image.width(),
                other_data=self.other_data,
                flags=flags,
            )
            self.label_file = label_file
            items = self.file_list_widget.findItems(
                self.image_path, Qt.MatchExactly
            )
            if len(items) > 0:
                if len(items) != 1:
                    raise RuntimeError("There are duplicate files.")
                items[0].setCheckState(Qt.Checked)
            # disable allows next and previous image to proceed
            # self.filename = filename
            return True
        except LabelFileError as e:
            self.error_message(
                self.tr("Error saving label data"), self.tr("<b>%s</b>") % e
            )
            return False

    # React to canvas signals.
    def shape_selection_changed(self, selected_shapes):
        self._no_selection_slot = True
        for shape in self.canvas.shapes:
            shape.is_mouse_selected = False
        for shape in self.canvas.selected_shapes:
            shape.selected = False
        self.label_list.clearSelection()
        self.canvas.selected_shapes = selected_shapes
        allow_merge_shape_type = {"rectangle": 0, "polygon": 0, "rotation": 0}
        for shape in self.canvas.selected_shapes:
            shape.selected = True
            shape.is_mouse_selected = True
            if shape.shape_type in ["rectangle", "polygon", "rotation"]:
                allow_merge_shape_type[shape.shape_type] += 1
            item = self.label_list.find_item_by_shape(shape)
            # NOTE: Handle the case when the shape is not found
            if item is not None:
                self.label_list.select_item(item)
                self.label_list.scroll_to_item(item)
        self._no_selection_slot = False
        n_selected = len(selected_shapes)
        same_type = (
            len(set(shape.shape_type for shape in selected_shapes)) <= 1
        )
        self.actions.delete.setEnabled(n_selected)
        self.actions.duplicate.setEnabled(n_selected)
        self.actions.copy.setEnabled(n_selected)
        self.actions.edit.setEnabled(n_selected >= 1 and same_type)
        self.actions.union_selection.setEnabled(
            not all(value > 0 for value in allow_merge_shape_type.values())
            and (
                allow_merge_shape_type["rectangle"] > 1
                or allow_merge_shape_type["polygon"] > 1
                or allow_merge_shape_type["rotation"] > 1
            )
        )
        self.set_text_editing(True)
        if self.attributes:
            # TODO: For future optimization(add parm to monitor selected_shape status)
            for i in range(len(self.canvas.shapes)):
                if self.canvas.shapes[i].selected:
                    self.update_attributes(i)
                    break
        self.update_navigator_shapes()  # 更新导航器以同步点击选中效果
        self._update_navigator_title_with_selection()

    def _update_navigator_title_with_selection(self):
        """Update navigator title with the size of the currently selected shape."""
        selected_shapes = self.canvas.selected_shapes
        self.navigator_dialog.update_title_with_selection(selected_shapes)

    def add_label(self, shape, update_last_label=True):
        global_order = len(self.label_list) + 1

        # Text will be set in _update_all_item_orders
        text = shape.label

        label_list_item = LabelListWidgetItem(text, shape)
        self.label_list.addItem(label_list_item)
        if not self.unique_label_list.find_items_by_label(shape.label):
            item = self.unique_label_list.create_item_from_label(shape.label)
            self.unique_label_list.addItem(item)
            rgb = self._get_rgb_by_label(shape.label)
            # Correctly set initial text. `update_label_counts` will handle subsequent updates.
            count = sum(1 for s in self.canvas.shapes if s.label == shape.label)
            display_text = f"{shape.label} ({count})"
            self.unique_label_list.set_item_label(
                item, display_text, rgb, LABEL_OPACITY
            )

        # Add label to history if it is not a special label
        if shape.label not in [
            AutoLabelingMode.OBJECT,
            AutoLabelingMode.ADD,
            AutoLabelingMode.REMOVE,
        ]:
            self.label_dialog.add_label_history(
                shape.label, update_last_label=update_last_label
            )

        for action in self.actions.on_shapes_present:
            action.setEnabled(True)

        self._update_shape_color(shape)
        self._update_all_item_orders()
        color = shape.fill_color.getRgb()[:3]
        # label_list_item.setText is now handled by _update_all_item_orders
        label_list_item.setBackground(QtGui.QColor(*color, LABEL_OPACITY))
        self.update_combo_box()
        self.update_gid_box()
        self.update_label_counts()
        self.shape_list_changed.emit()
        # Update expand margins dialog colors after adding new label
        self._update_expand_margins_colors()

    def create_label_control_buttons(self):
        """创建标签控制按钮"""
        self.label_control_widget = QtWidgets.QWidget()
        control_layout = QtWidgets.QHBoxLayout()
        control_layout.setContentsMargins(2, 2, 2, 2)
        control_layout.setSpacing(2)

        # 全选按钮
        self.btn_select_all = QtWidgets.QPushButton(self.tr("全选"))
        self.btn_select_all.setToolTip(self.tr("选择所有标签"))
        def select_all_labels():
            for i in range(self.unique_label_list.count()):
                item = self.unique_label_list.item(i)
                item.setCheckState(Qt.Checked)
        self.btn_select_all.clicked.connect(select_all_labels)

        # 反选按钮
        self.btn_invert_selection = QtWidgets.QPushButton(self.tr("反选"))
        self.btn_invert_selection.setToolTip(self.tr("反向选择标签"))
        def invert_labels():
            # 统计对象区当前存在的标签集合
            object_labels = set()
            for obj_item in self.label_list:
                object_labels.add(obj_item.shape().label)
            for i in range(self.unique_label_list.count()):
                item = self.unique_label_list.item(i)
                label = item.data(Qt.UserRole)
                if label in object_labels:
                    # 反转
                    item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)
                else:
                    # 不存在的标签直接取消勾选
                    item.setCheckState(Qt.Unchecked)
        self.btn_invert_selection.clicked.connect(invert_labels)

        # 取消按钮
        self.btn_deselect_all = QtWidgets.QPushButton(self.tr("取消"))
        self.btn_deselect_all.setToolTip(self.tr("取消所有标签"))
        def deselect_all_labels():
            for i in range(self.unique_label_list.count()):
                item = self.unique_label_list.item(i)
                item.setCheckState(Qt.Unchecked)
        self.btn_deselect_all.clicked.connect(deselect_all_labels)

        # 重叠显示按钮
        self.btn_overlap = QtWidgets.QPushButton(self.tr("重叠"))
        self.btn_overlap.setCheckable(True)
        self.btn_overlap.setChecked(True)  # 默认启用
        self.btn_overlap.setToolTip(self.tr("切换重叠区域显示"))
        def toggle_overlap():
            self.canvas.toggle_overlap_display()
            # 更新按钮状态以反映当前显示状态
            self.btn_overlap.setChecked(self.canvas.show_overlap)
        self.btn_overlap.clicked.connect(toggle_overlap)

        # Set shortcuts from config
        shortcuts = self._config.get("shortcuts", {})
        self.btn_select_all.setShortcut(shortcuts.get("select_all_labels", ""))
        self.btn_invert_selection.setShortcut(shortcuts.get("invert_selection_labels", ""))
        self.btn_deselect_all.setShortcut(shortcuts.get("deselect_all_labels", ""))
        self.btn_overlap.setShortcut(shortcuts.get("toggle_overlap", ""))

        # 添加按钮到布局
        control_layout.addWidget(self.btn_select_all)
        control_layout.addWidget(self.btn_invert_selection)
        control_layout.addWidget(self.btn_deselect_all)
        control_layout.addWidget(self.btn_overlap)
        control_layout.addStretch()

        self.label_control_widget.setLayout(control_layout)


    def load_labels(self, labels, clear_existing=True):
        """
        Load labels to the unique label list widget.

        Args:
            labels (list): List of label names to load
            clear_existing (bool): Whether to clear existing labels before loading new ones
        """
        if not labels:
            return

        if clear_existing:
            self.unique_label_list.clear()

        label_counts = {}
        for shape in self.canvas.shapes:
            label = shape.label
            if label in label_counts:
                label_counts[label] += 1
            else:
                label_counts[label] = 1

        for i, label in enumerate(labels):
            # Check if label already exists to avoid duplicates
            if not self.unique_label_list.find_items_by_label(label):
                item = self.unique_label_list.create_item_from_label(label)
                self.unique_label_list.addItem(item)
                rgb = self._get_rgb_by_label(label)
                count = label_counts.get(label, 0)
                display_text = f"{label} ({count})"
                self.unique_label_list.set_item_label(
                    item, display_text, rgb, LABEL_OPACITY
                )

    def update_label_counts(self):
        """Update the counts of all labels in the unique label list."""
        label_counts = {}
        for shape in self.canvas.shapes:
            label = shape.label
            if label in [
                AutoLabelingMode.OBJECT,
                AutoLabelingMode.ADD,
                AutoLabelingMode.REMOVE,
            ]:
                continue
            label_counts[label] = label_counts.get(label, 0) + 1

        for i in range(self.unique_label_list.count()):
            item = self.unique_label_list.item(i)
            label = item.data(Qt.UserRole)
            count = label_counts.get(label, 0)
            display_text = f"{label} ({count})"
            rgb = self._get_rgb_by_label(label)
            self.unique_label_list.set_item_label(
                item, display_text, rgb, LABEL_OPACITY
            )

    def _update_shape_color(self, shape):
        r, g, b = self._get_rgb_by_label(shape.label)
        shape.line_color = QtGui.QColor(r, g, b)
        shape.vertex_fill_color = QtGui.QColor(r, g, b)
        shape.hvertex_fill_color = QtGui.QColor(255, 255, 255)
        shape.fill_color = QtGui.QColor(r, g, b, 128)
        shape.select_line_color = QtGui.QColor(r, g, b)
        shape.select_fill_color = QtGui.QColor(r, g, b, 155)

    def _get_rgb_by_label(self, label, skip_label_info=False):
        if label in self.label_info and not skip_label_info:
            return tuple(self.label_info[label]["color"])
        if self._config["shape_color"] == "auto":
            if not self.unique_label_list.find_items_by_label(label):
                item = self.unique_label_list.create_item_from_label(label)
                self.unique_label_list.addItem(item)
            item = self.unique_label_list.find_items_by_label(label)[0]
            label_id = self.unique_label_list.indexFromItem(item).row() + 1
            label_id += self._config["shift_auto_shape_color"]
            return LABEL_COLORMAP[label_id % len(LABEL_COLORMAP)]
        if (
            self._config["shape_color"] == "manual"
            and self._config["label_colors"]
            and label in self._config["label_colors"]
        ):
            return self._config["label_colors"][label]
        if self._config["default_shape_color"]:
            return self._config["default_shape_color"]
        return (0, 255, 0)

    def remove_labels(self, shapes):
        for shape in shapes:
            item = self.label_list.find_item_by_shape(shape)
            self.label_list.remove_item(item)
        self.update_combo_box()
        self.update_gid_box()
        self._update_all_item_orders()
        self.update_label_counts()
        self.shape_list_changed.emit()

    def _update_all_item_orders(self):
        """Update the order number for all items in the label list."""
        label_counts = {}
        for i, item in enumerate(self.label_list):
            shape = item.shape()
            order = i + 1

            label = shape.label
            label_counts[label] = label_counts.get(label, 0) + 1
            label_specific_order = label_counts[label]

            if shape.group_id is None:
                text = f"{order} {label}({label_specific_order})"
            else:
                text = f"{order} {label}({label_specific_order}) ({shape.group_id})"
            item.setText("{}".format(html.escape(text)))

    def load_shapes(self, shapes, replace=True, update_last_label=True):
        self._no_selection_slot = True
        if replace:
            self.label_list.clear()
        for shape in shapes:
            self.add_label(shape, update_last_label=update_last_label)
        self.label_list.clearSelection()
        self._no_selection_slot = False
        # 全局高亮同步
        if hasattr(self, "_highlight_on") and self._highlight_on:
            for shape in shapes:
                shape.selected = True
                shape.fill = True
        elif hasattr(self, "_highlight_on") and not self._highlight_on:
            for shape in shapes:
                shape.selected = False
                shape.fill = False
        self.canvas.load_shapes(shapes, replace=replace)
        self.canvas.update()
        self.shape_list_changed.emit()

    def _update_object_manager(self):
        """Update the object manager dialog if it's visible."""
        if self.object_manager_dialog and self.object_manager_dialog.isVisible():
            self.object_manager_dialog.update_items([item for item in self.label_list])

    def load_flags(self, flags):
        self.flag_widget.clear()
        for key, flag in flags.items():
            item = QtWidgets.QListWidgetItem(key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if flag else Qt.Unchecked)
            self.flag_widget.addItem(item)

    def update_combo_box(self):
        # Get the unique labels and add them to the Combobox.
        labels_list = []
        for item in self.label_list:
            label = item.shape().label
            labels_list.append(str(label))
        unique_labels_list = list(set(labels_list))

        # Add a null row for showing all the labels
        unique_labels_list.append("")
        unique_labels_list.sort()
        self.label_filter_combobox.update_items(unique_labels_list)

    def update_gid_box(self):
        # Get the unique group ids and add them to the Combobox.
        gid_list = []
        for item in self.label_list:
            gid = item.shape().group_id
            if gid is not None:
                gid_list.append(str(gid))
        unique_gid_list = list(set(gid_list))

        # Add a null row for showing all the labels
        unique_gid_list.append("-1")
        unique_gid_list.sort()
        self.gid_filter_combobox.update_items(unique_gid_list)

    def save_labels(self, filename):
        label_file = LabelFile()
        # Get current shapes
        # Excluding auto labeling special shapes
        shapes = [
            item.shape().to_dict()
            for item in self.label_list
            if item.shape().label
            not in [
                AutoLabelingMode.OBJECT,
                AutoLabelingMode.ADD,
                AutoLabelingMode.REMOVE,
            ]
        ]
        flags = {}
        for i in range(self.flag_widget.count()):
            item = self.flag_widget.item(i)
            key = item.text()
            flag = item.checkState() == Qt.Checked
            flags[key] = flag
        try:
            image_path = osp.relpath(self.image_path, osp.dirname(filename))
            image_data = (
                self.image_data if self._config["store_data"] else None
            )
            if osp.dirname(filename) and not osp.exists(osp.dirname(filename)):
                os.makedirs(osp.dirname(filename))

            label_file.save(
                filename=filename,
                shapes=shapes,
                image_path=image_path,
                image_data=image_data,
                image_height=self.image.height(),
                image_width=self.image.width(),
                other_data=self.other_data,
                flags=flags,
            )
            self.label_file = label_file
            items = self.file_list_widget.findItems(
                self.image_path, Qt.MatchExactly
            )
            if len(items) > 0:
                if len(items) != 1:
                    raise RuntimeError("There are duplicate files.")
                item = items[0]
                item.setCheckState(Qt.Checked)

                # Update color to show manually edited status
                if self.other_data.get("manually_edited", False):
                    color = self._config.get("manually_edited_color", "#FFA500")
                    item.setForeground(QtGui.QColor(color))
                else:
                    # Reset to default color (black) when not manually edited
                    item.setForeground(QtGui.QColor("#000000"))
            # disable allows next and previous image to proceed
            # self.filename = filename
            return True
        except LabelFileError as e:
            self.error_message(
                self.tr("Error saving label data"), self.tr("<b>%s</b>") % e
            )
            return False

    def duplicate_selected_shape(self):
        added_shapes = self.canvas.duplicate_selected_shapes()
        self.label_list.clearSelection()
        for shape in added_shapes:
            self.add_label(shape)
        self.set_dirty()

    def paste_selected_shape(self):
        if self._config["system_clipboard"]:
            clipboard = QtWidgets.QApplication.clipboard()
            json_str = clipboard.text()
            shapes = []
            try:
                shapeDicts = json.loads(json_str)
                for shapeDict in shapeDicts:
                    shapes.append(Shape().load_from_dict(shapeDict))
            except json.JSONDecodeError as e:
                self.error_message(
                    self.tr("Error pasting shapes"),
                    self.tr("Error decoding shapes: %s") % str(e),
                )
                return
            self.load_shapes(shapes, replace=False)
        else:
            self.load_shapes(self._copied_shapes, replace=False)
        self.set_dirty()

    def toggle_system_clipboard(self, system_clipboard):
        self._config["system_clipboard"] = system_clipboard
        self.actions.paste.setEnabled(
            bool(system_clipboard or self._copied_shapes)
        )

    def copy_selected_shape(self):
        if self._config["system_clipboard"]:
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(
                json.dumps([s.to_dict() for s in self.canvas.selected_shapes])
            )
        else:
            self._copied_shapes = [
                s.copy() for s in self.canvas.selected_shapes
            ]
            self.actions.paste.setEnabled(len(self._copied_shapes) > 0)


    def update_label_visibility(self, label, is_visible):
        """标签区勾选同步到对象区，并同步可见性"""
        for item in self.label_list:
            shape = item.shape()
            if shape.label == label:
                # 更新对象区的勾选状态
                item.setCheckState(Qt.Checked if is_visible else Qt.Unchecked)
                shape.visible = is_visible
                self.canvas.set_shape_visible(shape, is_visible)

        # 更新导航器显示
        self.update_navigator_shapes()

    def text_selection_changed(self, index):
        # 禁用这个函数，避免在创建新图形时重置复选框
        return

    def gid_selection_changed(self, index):
        # 禁用这个函数，避免在创建新图形时重置复选框
        return

    def label_selection_changed(self):
        if self._no_selection_slot:
            return
        if self.canvas.editing():
            selected_shapes = []
            for item in self.label_list.selected_items():
                selected_shapes.append(item.shape())
            if selected_shapes:
                self.canvas.select_shapes(selected_shapes)
            else:
                self.canvas.deselect_shape()

    def label_item_changed(self, item):
        shape = item.shape()
        shape.visible = item.checkState() == Qt.Checked
        self.canvas.set_shape_visible(shape, item.checkState() == Qt.Checked)
        
        # 更新导航器显示
        self.update_navigator_shapes()
        
        # 简单的同步逻辑：对象区变化同步到标签区
        label = shape.label
        is_visible = item.checkState() == Qt.Checked
        
        # 检查该标签的所有对象是否都可见
        all_visible = True
        any_visible = False
        for obj_item in self.label_list:
            if obj_item.shape().label == label:
                if obj_item.checkState() == Qt.Checked:
                    any_visible = True
                else:
                    all_visible = False
        
        # 更新标签区：只有全部可见才勾选，全部不可见才取消勾选
        for i in range(self.unique_label_list.count()):
            label_item = self.unique_label_list.item(i)
            if label_item.data(Qt.UserRole) == label:
                if all_visible:
                    label_item.setCheckState(Qt.Checked)
                elif not any_visible:
                    label_item.setCheckState(Qt.Unchecked)
                # 部分可见时保持当前状态
                break

    def label_order_changed(self):
        self.set_dirty()
        self.canvas.load_shapes([item.shape() for item in self.label_list])
        self._update_all_item_orders()

    # Callback functions:
    def new_shape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        items = self.unique_label_list.selectedItems()
        text = None
        if items:
            text = items[0].data(Qt.UserRole)
        flags = {}
        group_id = None
        description = ""
        difficult = False
        kie_linking = []
        new_direction = None

        if self.canvas.shapes[-1].label in [
            AutoLabelingMode.ADD,
            AutoLabelingMode.REMOVE,
        ]:
            text = self.canvas.shapes[-1].label
        elif (
            self._config["display_label_popup"]
            or not text
            or self.canvas.shapes[-1].label == AutoLabelingMode.OBJECT
        ):
            last_label = self.find_last_label()
            if self.digit_to_label is not None:
                text = self.digit_to_label
                self.digit_to_label = None
            elif self._config["auto_use_last_label"] and last_label:
                text = last_label
            else:
                previous_text = self.label_dialog.edit.text()
                (
                    text,
                    flags,
                    group_id,
                    description,
                    difficult,
                    kie_linking,
                    _,  # new_order is not used here
                    new_direction,
                ) = self.label_dialog.pop_up(
                    text,
                    move_mode=self._config.get("move_mode", "auto"),
                    order=None,
                    direction=self.canvas.shapes[-1].direction if self.canvas.shapes[-1].shape_type == "rotation" else 0,
                    shape_type=self.canvas.shapes[-1].shape_type,
                )
                if not text:
                    self.label_dialog.edit.setText(previous_text)

        if text and not self.validate_label(text):
            self.error_message(
                self.tr("Invalid label"),
                self.tr("Invalid label '{}' with validation type '{}'").format(
                    text, self._config["validate_label"]
                ),
            )
            text = ""
            return

        if self.attributes and text:
            text = self.reset_attribute(text)

        if text:
            # 暂时断开标签可见性信号，避免新图形被自动隐藏
            self.unique_label_list.label_visibility_changed.disconnect(self.update_label_visibility)

            self.label_list.clearSelection()
            shape = self.canvas.set_last_label(text, flags)
            shape.group_id = group_id
            shape.description = description
            shape.label = text
            shape.difficult = difficult
            shape.kie_linking = kie_linking
            if shape.shape_type == "rotation" and new_direction is not None:
                shape.direction = new_direction
            self.add_label(shape)

            # 重新连接信号
            self.unique_label_list.label_visibility_changed.connect(self.update_label_visibility)

            self.actions.edit_mode.setEnabled(True)
            self.actions.undo_last_point.setEnabled(False)
            self.actions.undo.setEnabled(True)
            self.set_dirty()
            # Update expand margins dialog colors after adding new shape
            self._update_expand_margins_colors()
        else:
            self.canvas.undo_last_line()
            self.canvas.shapes_backups.pop()

        self.restore_crosshair_if_needed()

    def show_shape(self, shape_height, shape_width, pos):
        """Display annotation width and height while hovering inside.

        Parameters:
        - shape_height (float): The height of the shape.
        - shape_width (float): The width of the shape.
        - pos (QPointF): The current mouse coordinates inside the shape.
        """
        num_images = len(self.image_list)
        basename = osp.basename(str(self.filename))
        if shape_height > 0 and shape_width > 0:
            if num_images and self.filename in self.image_list:
                current_index = self.fn_to_index[str(self.filename)] + 1
                self.status(
                    str(self.tr("X: %d, Y: %d | H: %d, W: %d [%s: %d/%d]"))
                    % (
                        int(pos.x()),
                        int(pos.y()),
                        shape_height,
                        shape_width,
                        basename,
                        current_index,
                        num_images,
                    )
                )
            else:
                self.status(
                    str(self.tr("X: %d, Y: %d | H: %d, W: %d"))
                    % (int(pos.x()), int(pos.y()), shape_height, shape_width)
                )
        elif self.image_path:
            if num_images and self.filename in self.image_list:
                current_index = self.fn_to_index[str(self.filename)] + 1
                self.status(
                    str(self.tr("X: %d, Y: %d [%s: %d/%d]"))
                    % (
                        int(pos.x()),
                        int(pos.y()),
                        basename,
                        current_index,
                        num_images,
                    )
                )
            else:
                self.status(
                    str(self.tr("X: %d, Y: %d")) % (int(pos.x()), int(pos.y()))
                )

    def scroll_request(self, delta, orientation, mode):
        scroll_bar = self.scroll_bars[orientation]
        units = -delta * (0.1 if mode == 0 else 1)
        step = scroll_bar.singleStep() if mode == 0 else scroll_bar.maximum()
        value = scroll_bar.value() + step * units
        self.set_scroll(orientation, value)

    def set_scroll(self, orientation, value):
        self.scroll_bars[orientation].setValue(round(value))
        self.scroll_values[orientation][self.filename] = value
        # Update navigator viewport when scrolling
        self.update_navigator_viewport()

    def on_navigator_request(self, x_ratio, y_ratio):
        """Handle navigation request from navigator widget"""
        if not hasattr(self, 'image') or self.image.isNull():
            return
            
        # Get scroll area and canvas dimensions
        scroll_area = self._central_widget
        canvas_size = self.canvas.size()
        scroll_area_size = scroll_area.viewport().size()
        
        # Calculate target position based on ratios
        target_x = x_ratio * canvas_size.width() - scroll_area_size.width() / 2
        target_y = y_ratio * canvas_size.height() - scroll_area_size.height() / 2
        
        # Set scroll positions
        self.set_scroll(Qt.Horizontal, target_x)
        self.set_scroll(Qt.Vertical, target_y)
    
    def update_navigator_viewport(self):
        """Update the viewport rectangle in the navigator"""
        if not hasattr(self, 'navigator_dialog') or not hasattr(self, 'image'):
            return
            
        if self.image.isNull():
            return
            
        # Get scroll area and canvas dimensions
        scroll_area = self._central_widget
        canvas_size = self.canvas.size()
        scroll_area_size = scroll_area.viewport().size()
        
        if canvas_size.width() <= 0 or canvas_size.height() <= 0:
            return
            
        # Get current scroll positions
        h_scroll = self.scroll_bars[Qt.Horizontal].value()
        v_scroll = self.scroll_bars[Qt.Vertical].value()
        
        # Calculate viewport ratios
        x_ratio = max(0.0, h_scroll / canvas_size.width())
        y_ratio = max(0.0, v_scroll / canvas_size.height())
        width_ratio = min(1.0, scroll_area_size.width() / canvas_size.width())
        height_ratio = min(1.0, scroll_area_size.height() / canvas_size.height())
        
        # Update navigator viewport
        self.navigator_dialog.set_viewport(x_ratio, y_ratio, width_ratio, height_ratio)
        
        # Also update shapes overlay
        self.update_navigator_shapes()
        
    def update_navigator_shapes(self):
        """Update shapes overlay in navigator"""
        if not hasattr(self, 'navigator_dialog') or not self.navigator_dialog.isVisible():
            return
        
        # Get shapes from canvas
        shapes = getattr(self.canvas, 'shapes', [])
        
        # Get visibility info from canvas
        canvas_visible = getattr(self.canvas, 'visible', {})
        
        # Mark highlighted shape
        h_shape = getattr(self.canvas, 'h_hape', None)
        for shape in shapes:
            shape._is_highlighted = (shape == h_shape)
        
        # Update navigator with current shapes (no need for canvas scale/offset anymore)
        self.navigator_dialog.set_shapes(shapes, canvas_visible)

    def on_navigator_zoom_changed(self, zoom_percentage: int, mouse_pos: Optional[QtCore.QPoint] = None) -> None:
        """
        Handle zoom change from navigator controls.

        This method processes zoom changes triggered by navigator controls such as
        sliders, buttons, or mouse wheel events. It includes safety checks to prevent
        operations on null images and handles both mouse-centered and direct zoom changes.

        Args:
            zoom_percentage (int): The target zoom level as a percentage (1-1000).
            mouse_pos (Optional[QtCore.QPoint]): Mouse position for centered zooming.
                If provided, zooming will be centered at this position. Defaults to None.

        Returns:
            None

        Examples:
            >>> # Direct zoom change (from slider/button)
            >>> self.on_navigator_zoom_changed(150)
            
            >>> # Mouse-centered zoom (from wheel event)
            >>> mouse_position = QtCore.QPoint(100, 100)
            >>> self.on_navigator_zoom_changed(120, mouse_position)
            
        Note:
            If no image is loaded, this method returns early to prevent errors.
            Mouse-centered zooming takes precedence over direct zoom setting.
        """
        # Safety check: ensure image is loaded before processing zoom
        if not hasattr(self, 'image') or self.image.isNull():
            return
            
        # Handle mouse-centered zoom (from wheel events)
        if mouse_pos is not None:
            # Convert mouse position from navigator to canvas coordinates
            canvas_pos = self._convert_navigator_pos_to_canvas(mouse_pos)
            if canvas_pos:
                # Save old canvas dimensions for centering calculation
                canvas_width_old = self.canvas.width()
                canvas_height_old = self.canvas.height()
                old_zoom = self.zoom_widget.value()
                
                # Directly set the exact zoom value from navigator (1% precision)
                self.zoom_widget.setValue(zoom_percentage)
                self.zoom_mode = self.MANUAL_ZOOM
                self.zoom_values[self.filename] = (self.zoom_mode, zoom_percentage)
                self.paint_canvas()
                
                # Apply mouse-centered offset adjustment (copied from zoom_request logic)
                canvas_width_new = self.canvas.width()
                canvas_height_new = self.canvas.height()
                
                if canvas_width_old != canvas_width_new:
                    canvas_scale_factor = canvas_width_new / canvas_width_old
                    x_shift = round(canvas_pos.x() * canvas_scale_factor - canvas_pos.x())
                    y_shift = round(canvas_pos.y() * canvas_scale_factor - canvas_pos.y())
                    self.set_scroll(QtCore.Qt.Horizontal, self.scroll_bars[QtCore.Qt.Horizontal].value() + x_shift)
                    self.set_scroll(QtCore.Qt.Vertical, self.scroll_bars[QtCore.Qt.Vertical].value() + y_shift)
                
                return
        
        # Handle direct zoom changes (from slider/button controls)
        # For slider/button zoom, center on the red rectangle center in navigator (like PS navigator)
        if hasattr(self, 'canvas') and hasattr(self.canvas, 'width') and hasattr(self.canvas, 'height'):
            # Get navigator viewport rectangle center - this is the red rectangle in navigator
            if hasattr(self.navigator_dialog, 'navigator'):
                nav_widget = self.navigator_dialog.navigator
                if hasattr(nav_widget, 'viewport_rect') and not nav_widget.viewport_rect.isEmpty():
                    # Calculate red rectangle center in navigator coordinates
                    nav_rect_center_x = nav_widget.viewport_rect.center().x()
                    nav_rect_center_y = nav_widget.viewport_rect.center().y()
                    
                    # Convert navigator red rectangle center to canvas coordinates
                    canvas_pos = self._convert_navigator_pos_to_canvas(
                        QtCore.QPoint(int(nav_rect_center_x), int(nav_rect_center_y))
                    )
                    
                    if canvas_pos:
                        # Save old dimensions
                        canvas_width_old = self.canvas.width()
                        canvas_height_old = self.canvas.height()
                        
                        # Apply zoom
                        self.zoom_widget.setValue(zoom_percentage)
                        self.zoom_mode = self.MANUAL_ZOOM
                        self.zoom_values[self.filename] = (self.zoom_mode, zoom_percentage)
                        self.paint_canvas()
                        
                        # Calculate new dimensions and adjust scrollbars to keep red rectangle center fixed
                        canvas_width_new = self.canvas.width()
                        canvas_height_new = self.canvas.height()
                        
                        if canvas_width_old != canvas_width_new:
                            canvas_scale_factor = canvas_width_new / canvas_width_old
                            # Calculate how much to shift to keep red rectangle center point fixed
                            x_shift = round(canvas_pos.x() * canvas_scale_factor - canvas_pos.x())
                            y_shift = round(canvas_pos.y() * canvas_scale_factor - canvas_pos.y())
                            # Adjust scrollbars to maintain red rectangle center
                            self.set_scroll(QtCore.Qt.Horizontal, self.scroll_bars[QtCore.Qt.Horizontal].value() + x_shift)
                            self.set_scroll(QtCore.Qt.Vertical, self.scroll_bars[QtCore.Qt.Vertical].value() + y_shift)
                        return
            
            # Fallback to simple zoom without centering if navigator info not available
            self.zoom_widget.setValue(zoom_percentage)
            self.zoom_mode = self.MANUAL_ZOOM
            self.zoom_values[self.filename] = (self.zoom_mode, zoom_percentage)
            self.paint_canvas()
        else:
            # Fallback to simple zoom without centering
            self.zoom_widget.setValue(zoom_percentage)
            self.zoom_mode = self.MANUAL_ZOOM
            self.zoom_values[self.filename] = (self.zoom_mode, zoom_percentage)
            self.paint_canvas()
        
    def _convert_navigator_pos_to_canvas(self, navigator_pos: QtCore.QPoint) -> Optional[QtCore.QPoint]:
        """
        Convert navigator mouse position to canvas coordinates.

        This method transforms a mouse position from navigator widget coordinates
        to the corresponding position in the main canvas coordinate system.

        Args:
            navigator_pos (QtCore.QPoint): Mouse position in navigator widget coordinates.

        Returns:
            Optional[QtCore.QPoint]: Corresponding position in canvas coordinates,
                or None if conversion is not possible (e.g., navigator not visible,
                position outside image bounds).

        Examples:
            >>> nav_pos = QtCore.QPoint(50, 30)
            >>> canvas_pos = self._convert_navigator_pos_to_canvas(nav_pos)
            >>> if canvas_pos:
            ...     print(f"Canvas position: ({canvas_pos.x()}, {canvas_pos.y()})")
            
        Note:
            Returns None if navigator is not visible or position is outside image bounds.
        """
        if not hasattr(self, 'navigator_dialog') or not self.navigator_dialog.isVisible():
            return None
            
        navigator_widget = self.navigator_dialog.navigator
        if not navigator_widget.image_rect or navigator_widget.image_rect.isEmpty():
            return None
            
        # Convert navigator position to relative image coordinates
        relative_x = navigator_pos.x() - navigator_widget.image_rect.x()
        relative_y = navigator_pos.y() - navigator_widget.image_rect.y()
        
        # Check if position is within image bounds
        if (relative_x < 0 or relative_x > navigator_widget.image_rect.width() or 
            relative_y < 0 or relative_y > navigator_widget.image_rect.height()):
            return None
            
        # Convert to ratio (0.0 to 1.0)
        x_ratio = relative_x / navigator_widget.image_rect.width()
        y_ratio = relative_y / navigator_widget.image_rect.height()
        
        # Convert to canvas coordinates
        canvas_x = int(x_ratio * self.canvas.width())
        canvas_y = int(y_ratio * self.canvas.height())
        
        return QtCore.QPoint(canvas_x, canvas_y)

    def on_navigator_viewport_update_requested(self):
        """Handle viewport update request from navigator resize"""
        # Delay update to ensure navigator has finished resizing
        QTimer.singleShot(50, self.update_navigator_viewport)

    def toggle_navigator(self):
        """Toggle the navigator window visibility"""
        if self.navigator_dialog.isVisible():
            self.navigator_dialog.hide()
            # Save visibility state to config
            if "navigator" not in self._config:
                self._config["navigator"] = {}
            self._config["navigator"]["visible"] = False
            # Update menu item state
            if hasattr(self, 'actions') and hasattr(self.actions, 'show_navigator'):
                self.actions.show_navigator.setChecked(False)
        else:
            self.navigator_dialog.show()
            # Save visibility state to config
            if "navigator" not in self._config:
                self._config["navigator"] = {}
            self._config["navigator"]["visible"] = True
            # 同时保存当前位置和大小
            self._config["navigator"]["position_x"] = self.navigator_dialog.x()
            self._config["navigator"]["position_y"] = self.navigator_dialog.y()
            self._config["navigator"]["width"] = self.navigator_dialog.width()
            self._config["navigator"]["height"] = self.navigator_dialog.height()
            
            # Update navigator when shown, only if image is loaded
            if hasattr(self, 'image') and not self.image.isNull():
                self.navigator_dialog.set_image(QtGui.QPixmap.fromImage(self.image))
                self.update_navigator_viewport()
            # Update menu item state
            if hasattr(self, 'actions') and hasattr(self.actions, 'show_navigator'):
                self.actions.show_navigator.setChecked(True)
        
        # 立即保存config到文件
        try:
            from anylabeling.config import save_config
            save_config(self._config)
        except Exception as e:
            print(f"Failed to save navigator visibility: {e}")

    def set_zoom(self, value):
        self.actions.fit_width.setChecked(False)
        self.actions.fit_window.setChecked(False)
        self.zoom_mode = self.MANUAL_ZOOM
        self.zoom_widget.setValue(value)
        self.zoom_values[self.filename] = (self.zoom_mode, value)
        # Update navigator zoom controls
        if hasattr(self, 'navigator_dialog'):
            self.navigator_dialog.set_zoom_value(value)

    def add_zoom(self, increment=1.1):
        zoom_value = self.zoom_widget.value() * increment
        if increment > 1:
            zoom_value = math.ceil(zoom_value)
        else:
            zoom_value = math.floor(zoom_value)
        self.set_zoom(zoom_value)

    def zoom_at_mouse_shortcut_triggered(self):
        """
        Zooms in on the canvas at the current mouse position by a configurable percentage.
        """
        if not hasattr(self, 'image') or self.image is None or self.image.isNull():
            return

        # Get current mouse position relative to the canvas
        canvas_mouse_pos = self.canvas.mapFromGlobal(QtGui.QCursor.pos())

        is_mouse_over_canvas = self.canvas.rect().contains(canvas_mouse_pos)
        if not is_mouse_over_canvas:
            # If mouse is not over canvas, use center of the visible part of the canvas
            scroll_area = self._central_widget
            h_bar = scroll_area.horizontalScrollBar()
            v_bar = scroll_area.verticalScrollBar()
            x = h_bar.value() + scroll_area.viewport().width() / 2
            y = v_bar.value() + scroll_area.viewport().height() / 2
            canvas_mouse_pos = QtCore.QPoint(int(x), int(y))

        percentage_increase = self._config["canvas"].get("zoom_at_mouse_percentage_increase", 20)
        current_zoom = self.zoom_widget.value()
        new_zoom = current_zoom + percentage_increase # Add percentage points directly
        new_zoom = math.ceil(new_zoom) # Ensure it's an integer

        # Clamp zoom value to reasonable limits (e.g., 10% to 1000%)
        new_zoom = max(10, min(1000, new_zoom))

        # Apply zoom and adjust scrollbars to keep mouse position centered
        canvas_width_old = self.canvas.width()
        
        self.set_zoom(new_zoom)

        canvas_width_new = self.canvas.width()
        
        if canvas_width_old > 0 and canvas_width_old != canvas_width_new:
            canvas_scale_factor = canvas_width_new / canvas_width_old
            x_shift = round(canvas_mouse_pos.x() * canvas_scale_factor - canvas_mouse_pos.x())
            y_shift = round(canvas_mouse_pos.y() * canvas_scale_factor - canvas_mouse_pos.y())

            self.set_scroll(
                Qt.Horizontal,
                self.scroll_bars[Qt.Horizontal].value() + x_shift,
            )
            self.set_scroll(
                Qt.Vertical,
                self.scroll_bars[Qt.Vertical].value() + y_shift,
            )

    def zoom_request(self, delta, pos):
        canvas_width_old = self.canvas.width()
        canvas_height_old = self.canvas.height()
        
        old_zoom = self.zoom_widget.value()
        
        units = 1.1
        if delta < 0:
            units = 0.9
        self.add_zoom(units)

        canvas_width_new = self.canvas.width()
        canvas_height_new = self.canvas.height()
        
        new_zoom = self.zoom_widget.value()
        
        # Only apply scroll adjustment if canvas size actually changed
        # Remove the restrictive zoom threshold to fix centering at all zoom levels
        if canvas_width_old != canvas_width_new:
            
            canvas_scale_factor = canvas_width_new / canvas_width_old

            x_shift = round(pos.x() * canvas_scale_factor - pos.x())
            y_shift = round(pos.y() * canvas_scale_factor - pos.y())

            self.set_scroll(
                Qt.Horizontal,
                self.scroll_bars[Qt.Horizontal].value() + x_shift,
            )
            self.set_scroll(
                Qt.Vertical,
                self.scroll_bars[Qt.Vertical].value() + y_shift,
            )

    def set_fit_window(self, value=True):
        if value:
            self.actions.fit_width.setChecked(False)
        self.zoom_mode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjust_scale()

    def set_fit_width(self, value=True):
        if value:
            self.actions.fit_window.setChecked(False)
        self.zoom_mode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjust_scale()

    def toggle_crosshair(self):
        """Toggle crosshair visibility."""
        settings = self._config["canvas"]["crosshair"]
        new_show_state = not settings.get("show", True)
        settings["show"] = new_show_state
        self.canvas.set_cross_line(**settings)
        self.actions.toggle_cross_line.setChecked(new_show_state)

    def restore_crosshair_if_needed(self):
        """Restore crosshair to its original state if it was auto-toggled."""
        if self._crosshair_was_toggled_for_drawing:
            self.toggle_crosshair()  # This will turn it from ON back to OFF.
            self._crosshair_was_toggled_for_drawing = False

    def on_drawing_cancelled(self):
        """Slot for when drawing is cancelled on the canvas."""
        self.restore_crosshair_if_needed()

    def set_cross_line(self):
        crosshair_dialog = CrosshairSettingsDialog(**self.crosshair_settings)
        if crosshair_dialog.exec_() == QtWidgets.QDialog.Accepted:
            crosshair_settings = crosshair_dialog.get_settings()
            show = crosshair_settings["show"]
            width = crosshair_settings["width"]
            color = crosshair_settings["color"]
            opacity = crosshair_settings["opacity"]
            style = crosshair_settings.get("style", "dash")  # Get style, default to "dash"
            self.canvas.set_cross_line(show, width, color, opacity, style)
            self._config["canvas"]["crosshair"] = crosshair_settings

    def set_canvas_params(self, key, value):
        self._config[key] = value
        assert hasattr(self.canvas, key), f"Canvas has no attribute {key}"
        setattr(self.canvas, key, value)
        self.canvas.update()

    def on_new_brightness_contrast(self, qimage):
        self.canvas.load_pixmap(
            QtGui.QPixmap.fromImage(qimage), clear_shapes=False
        )

    def brightness_contrast(self, _):
        self.brightness_contrast_dialog.update_image(
            utils.img_data_to_pil(self.image_data)
        )

        brightness, contrast = self.brightness_contrast_values.get(
            self.filename, (None, None)
        )
        if brightness is not None:
            self.brightness_contrast_dialog.slider_brightness.setValue(
                brightness
            )
        if contrast is not None:
            self.brightness_contrast_dialog.slider_contrast.setValue(contrast)

        self.brightness_contrast_dialog.exec_()

        brightness = self.brightness_contrast_dialog.slider_brightness.value()
        contrast = self.brightness_contrast_dialog.slider_contrast.value()
        self.brightness_contrast_values[self.filename] = (brightness, contrast)

    def hide_selected_polygons(self):
        shapes_to_hide = []
        for item in self.label_list:
            if item.shape().selected:
                item.setCheckState(Qt.Unchecked)
                item.shape().visible = False
                shapes_to_hide.append(item.shape())

        self.selected_polygon_stack.extend(shapes_to_hide)
        self.canvas.update()
        # 更新导航器显示
        self.update_navigator_shapes()

    def show_hidden_polygons(self):
        if self.selected_polygon_stack:
            shape_to_show = self.selected_polygon_stack.pop()
            item = self.label_list.find_item_by_shape(shape_to_show)
            if item:
                item.setCheckState(Qt.Checked)
                shape_to_show.visible = True
                self.canvas.update()
                # 更新导航器显示
                self.update_navigator_shapes()
            else:
                logger.warning(
                    f"Shape associated with the hidden item was not found in label list, could not show."
                )

    def get_next_files(self, filename, num_files):
        """Get the next files in the list."""
        if not self.image_list:
            return []
        filenames = []
        current_index = 0
        if filename is not None:
            try:
                current_index = self.fn_to_index[str(filename)]
            except ValueError:
                return []
            filenames.append(filename)
        for _ in range(num_files):
            if current_index + 1 < len(self.image_list):
                filenames.append(self.image_list[current_index + 1])
                current_index += 1
            else:
                filenames.append(self.image_list[-1])
                break
        return filenames

    def inform_next_files(self, filename):
        """Inform the next files to be annotated.
        This list can be used by the user to preload the next files
        or running a background process to process them
        """
        next_files = self.get_next_files(filename, 5)
        if next_files:
            self.next_files_changed.emit(next_files)

    def load_file(self, filename=None):  # noqa: C901
        """Load the specified file, or the last opened file if None."""

        # NOTE(jack): Does we need to save the config here?
        # save_config(self._config)

        # For auto labeling, clear the previous marks
        # and inform the next files to be annotated
        # NOTE(jack): this is not needed for now
        # self.clear_auto_labeling_marks()
        # self.inform_next_files(filename)

        # Changing file_list_widget loads file
        if filename in self.image_list and (
            self.file_list_widget.currentRow()
            != self.fn_to_index[str(filename)]
        ):
            self.file_list_widget.setCurrentRow(
                self.fn_to_index[str(filename)]
            )
            self.file_list_widget.repaint()
            return False

        self.reset_state()
        self.canvas.setEnabled(False)
        if filename is None:
            filename = self.settings.value("filename", "")
        filename = str(filename)
        if not QtCore.QFile.exists(filename):
            self.error_message(
                self.tr("Error opening file"),
                self.tr("No such file: <b>%s</b>") % filename,
            )
            return False

        # assumes same name, but json extension
        self.status(
            str(self.tr("Loading %s...")) % osp.basename(str(filename))
        )
        label_file = osp.splitext(filename)[0] + ".json"
        image_dir = None
        if self.output_dir:
            image_dir = osp.dirname(filename)
            label_file_without_path = osp.basename(label_file)
            label_file = self.output_dir + "/" + label_file_without_path
        if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(
            label_file
        ):
            try:
                self.label_file = LabelFile(label_file, image_dir)
            except LabelFileError as e:
                self.error_message(
                    self.tr("Error opening file"),
                    self.tr(
                        "<p><b>%s</b></p>"
                        "<p>Make sure <i>%s</i> is a valid label file."
                    )
                    % (e, label_file),
                )
                self.status(self.tr("Error reading %s") % label_file)
                return False
            self.image_data = self.label_file.image_data
            self.image_path = osp.join(
                osp.dirname(label_file),
                self.label_file.image_path,
            )
            self.other_data = self.label_file.other_data
            self.shape_text_edit.textChanged.disconnect()
            self.shape_text_edit.setPlainText(
                self.other_data.get("description", "")
            )
            self.shape_text_edit.textChanged.connect(self.shape_text_changed)
        else:
            self.image_data = LabelFile.load_image_file(filename)
            if self.image_data:
                self.image_path = filename
            self.label_file = None

        # Reset the label loop count
        self.label_loop_count = -1

        # TODO(jack): icc profile issue warning
        # - qt.gui.icc: fromIccProfile: failed minimal tag size sanity
        # - qt.gui.icc: fromIccProfile: invalid tag offset alignment
        image = QtGui.QImage.fromData(self.image_data)

        if image.isNull():
            formats = [
                f"*.{fmt.data().decode()}"
                for fmt in QtGui.QImageReader.supportedImageFormats()
            ]
            self.error_message(
                self.tr("Error opening file"),
                self.tr(
                    "<p>Make sure <i>{0}</i> is a valid image file.<br/>"
                    "Supported image formats: {1}</p>"
                ).format(filename, ",".join(formats)),
            )
            self.status(self.tr("Error reading %s") % filename)
            return False
        self.image = image
        self.filename = filename
        
        # Update navigator with new image
        self.navigator_dialog.set_image(QtGui.QPixmap.fromImage(image))
        # Initialize with empty shapes for new image
        self.update_navigator_shapes()
        
        # 如果这是首次加载且导航器应该显示，确保它正确更新
        if hasattr(self, '_should_restore_navigator') and self._should_restore_navigator:
            self._should_restore_navigator = False
            if self.navigator_dialog.isVisible():
                self.update_navigator_viewport()
        
        # Update file info in navigator
        if hasattr(self, 'image_list') and self.filename:
            try:
                current_index = self.fn_to_index.get(str(self.filename), 0) + 1
                total_files = len(self.image_list)
                self.navigator_dialog.set_file_info(self.filename, current_index, total_files)
            except:
                self.navigator_dialog.set_file_info(self.filename, 1, 1)
        
        if self._config["keep_prev"]:
            prev_shapes = self.canvas.shapes
        self.canvas.load_pixmap(QtGui.QPixmap.fromImage(image))

        # load label flags
        flags = {k: False for k in self.image_flags or []}
        if self.label_file:
            for shape in self.label_file.shapes:
                default_flags = {}
                if self._config["label_flags"]:
                    for pattern, keys in self._config["label_flags"].items():
                        if re.match(pattern, shape.label):
                            for key in keys:
                                default_flags[key] = False
                    shape.flags = {
                        **default_flags,
                        **shape.flags,
                    }
            self.update_combo_box()
            self.update_gid_box()
            self.load_shapes(self.label_file.shapes, update_last_label=False)
            self.update_label_counts()
            if self.label_file.flags is not None:
                flags.update(self.label_file.flags)
        self.load_flags(flags)

        # load shapes
        if self._config["keep_prev"] and self.no_shape():
            self.load_shapes(
                prev_shapes, replace=False, update_last_label=False
            )
            self.set_dirty()
        else:
            self.set_clean()
        self.canvas.setEnabled(True)

        if self.tag_sort_dialog:
            pixmap_obj = getattr(self.canvas, "pixmap", None)
            pixmap_copy = pixmap_obj.copy() if pixmap_obj is not None else None
            try:
                shapes_data = [shape.to_dict() for shape in self.canvas.shapes]
            except Exception:  # noqa: BLE001
                shapes_data = []
            self.tag_sort_dialog.set_context(pixmap_copy, shapes_data)

        # set zoom values
        is_initial_load = not self.zoom_values
        if self.filename in self.zoom_values:
            self.zoom_mode = self.zoom_values[self.filename][0]
            self.set_zoom(self.zoom_values[self.filename][1])
        elif is_initial_load or not self._config["keep_prev_scale"]:
            self.adjust_scale(initial=True)
        # set scroll values
        for orientation in self.scroll_values:
            if self.filename in self.scroll_values[orientation]:
                self.set_scroll(
                    orientation, self.scroll_values[orientation][self.filename]
                )
        # set brightness contrast values
        self.brightness_contrast_dialog.update_image(
            utils.img_data_to_pil(self.image_data)
        )

        brightness, contrast = self.brightness_contrast_values.get(
            self.filename, (None, None)
        )
        if self._config["keep_prev_brightness"] and self.recent_files:
            brightness, _ = self.brightness_contrast_values.get(
                self.recent_files[0], (None, None)
            )
        if self._config["keep_prev_contrast"] and self.recent_files:
            _, contrast = self.brightness_contrast_values.get(
                self.recent_files[0], (None, None)
            )
        if brightness is not None:
            self.brightness_contrast_dialog.slider_brightness.setValue(
                brightness
            )
        if contrast is not None:
            self.brightness_contrast_dialog.slider_contrast.setValue(contrast)
        self.brightness_contrast_values[self.filename] = (brightness, contrast)
        if brightness is not None or contrast is not None:
            self.brightness_contrast_dialog.on_new_value()

        self.paint_canvas()
        self.add_recent_file(self.filename)
        self.toggle_actions(True)
        self.canvas.setFocus()
        msg = str(self.tr("Loaded %s")) % osp.basename(str(filename))
        self.status(msg)
        self.update_thumbnail_display()

        # Update expand margins dialog colors if open
        self._update_expand_margins_colors()

        return True

    # QT Overload
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            event.accept()
            return
        super(LabelingWidget, self).keyPressEvent(event)

    def resizeEvent(self, _):
        if (
            self.canvas
            and not self.image.isNull()
            and self.zoom_mode != self.MANUAL_ZOOM
        ):
            self.adjust_scale()
        self.update_thumbnail_pixmap()

    def paint_canvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoom_widget.value()
        self.canvas.adjustSize()
        self.canvas.update()
        # Update navigator viewport after canvas changes
        self.update_navigator_viewport()

    def adjust_scale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoom_mode]()
        value = int(100 * value)
        self.zoom_widget.setValue(value)
        self.zoom_values[self.filename] = (self.zoom_mode, value)
        # Update navigator zoom controls
        if hasattr(self, 'navigator_dialog'):
            self.navigator_dialog.set_zoom_value(value)

    def scale_fit_window(self):
        """Figure out the size of the pixmap to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.central_widget().width() - e
        h1 = self.central_widget().height() - e
        wh_ratio1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        wh_ratio2 = w2 / h2
        return w1 / w2 if wh_ratio2 >= wh_ratio1 else h1 / h2

    def scale_fit_width(self):
        # The epsilon does not seem to work too well here.
        w = self.central_widget().width() - 2.0
        return w / self.canvas.pixmap.width()

    # QT Overload
    def closeEvent(self, event):
        if not self.may_continue():
            event.ignore()
        self.settings.setValue(
            "filename", self.filename if self.filename else ""
        )
        self.settings.setValue("window/size", self.size())
        self.settings.setValue("window/position", self.pos())
        self.settings.setValue("window/state", self.parent.parent.saveState())
        self.settings.setValue("recent_files", self.recent_files)
        self.settings.setValue("recent_folders", self.recent_folders)
        
        # 通知导航器应用正在关闭，避免导航器closeEvent覆盖visible状态
        if hasattr(self, 'navigator_dialog'):
            self.navigator_dialog.app_closing = True
        
        # 保存导航器状态到配置文件
        if hasattr(self, 'navigator_dialog'):
            navigator_visible = self.navigator_dialog.isVisible()
            
            # 确保配置文件中有navigator节点
            if "navigator" not in self._config:
                self._config["navigator"] = {}
            
            # 保存可见性状态（保持当前状态，不强制为False）
            self._config["navigator"]["visible"] = navigator_visible
            
            # 总是保存导航器的位置和大小（无论是否可见）
            self._config["navigator"]["position_x"] = self.navigator_dialog.x()
            self._config["navigator"]["position_y"] = self.navigator_dialog.y()
            self._config["navigator"]["width"] = self.navigator_dialog.width()
            self._config["navigator"]["height"] = self.navigator_dialog.height()
        
        save_config(self._config)
        # ask the use for where to save the labels
        # self.settings.setValue('window/geometry', self.saveGeometry())

    def eventFilter(self, obj, event):
        """Filter events for double-click on dock title."""
        if hasattr(self, "shape_dock") and self.shape_dock and obj is self.shape_dock.titleBarWidget():
            if event.type() == QtCore.QEvent.MouseButtonDblClick:
                self.object_manager()
                return True
        return super(LabelingWidget, self).eventFilter(obj, event)

    # QT Overload
    def dragEnterEvent(self, event):
        extensions = [
            f".{fmt.data().decode().lower()}"
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]
        if event.mimeData().hasUrls():
            items = [i.toLocalFile() for i in event.mimeData().urls()]
            if any(i.lower().endswith(tuple(extensions)) for i in items):
                event.accept()
        else:
            event.ignore()

    # QT Overload
    def dropEvent(self, event):
        if not self.may_continue():
            event.ignore()
            return
        items = [i.toLocalFile() for i in event.mimeData().urls()]
        self.import_dropped_image_files(items)

    def load_recent(self, filename):
        if self.may_continue():
            self.load_file(filename)

    def open_checked_image(self, end_index, step, load=True):
        if not self.may_continue():
            return
        current_index = self.fn_to_index[str(self.filename)]
        for i in range(current_index + step, end_index, step):
            if self.file_list_widget.item(i).checkState() == Qt.Checked:
                self.filename = self.image_list[i]
                if self.filename and load:
                    self.load_file(self.filename)
                break

    def open_prev_unchecked_image(self):
        if self._config["switch_to_checked"]:
            self.open_checked_image(-1, -1)
            return

        if (
            not self.may_continue()
            or len(self.image_list) <= 0
            or self.filename is None
        ):
            return

        current_index = self.fn_to_index[str(self.filename)]
        for i in range(current_index - 1, -1, -1):
            if self.file_list_widget.item(i).checkState() == Qt.Unchecked:
                filename = self.image_list[i]
                if filename:
                    self.load_file(filename)
                break

    def open_next_unchecked_image(self, _value=False):
        if self._config["switch_to_checked"]:
            self.open_checked_image(self.file_list_widget.count(), 1)
            return

        if (
            not self.may_continue()
            or len(self.image_list) <= 0
            or self.filename is None
        ):
            return

        current_index = self.fn_to_index[str(self.filename)]
        for i in range(current_index + 1, len(self.image_list)):
            if self.file_list_widget.item(i).checkState() == Qt.Unchecked:
                filename = self.image_list[i]
                if filename:
                    self.load_file(filename)
                break

    def open_prev_image(self, _value=False):
        if not self.may_continue():
            return

        if len(self.image_list) <= 0:
            return

        if self.filename is None:
            return

        current_index = self.fn_to_index[str(self.filename)]
        if current_index - 1 >= 0:
            filename = self.image_list[current_index - 1]
            if filename:
                self.load_file(filename)

    def open_next_image(self, _value=False, load=True):
        if not self.may_continue():
            return

        if len(self.image_list) <= 0:
            return

        filename = None
        if self.filename is None:
            filename = self.image_list[0]
        else:
            current_index = self.fn_to_index[str(self.filename)]
            if current_index + 1 < len(self.image_list):
                filename = self.image_list[current_index + 1]
            else:
                filename = self.image_list[-1]
        self.filename = filename

        if self.filename and load:
            self.load_file(self.filename)

    # File
    def open_file(self, _value=False):
        if not self.may_continue():
            return
        path = osp.dirname(str(self.filename)) if self.filename else "."
        formats = [
            f"*.{fmt.data().decode()}"
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]
        filters = self.tr("Image & Label files (%s)") % " ".join(
            formats + [f"*{LabelFile.suffix}"]
        )
        file_dialog = FileDialogPreview(self)
        file_dialog.setFileMode(FileDialogPreview.ExistingFile)
        file_dialog.setNameFilter(filters)
        file_dialog.setWindowTitle(
            self.tr("%s - Choose Image or Label file") % __appname__,
        )
        file_dialog.setWindowFilePath(path)
        file_dialog.setViewMode(FileDialogPreview.Detail)
        if file_dialog.exec_():
            filename = file_dialog.selectedFiles()[0]
            if filename:
                self.file_list_widget.clear()
                self.load_file(filename)

    def change_output_dir_dialog(self, _value=False):
        default_output_dir = self.output_dir
        if default_output_dir is None and self.filename:
            default_output_dir = osp.dirname(self.filename)
        if default_output_dir is None:
            default_output_dir = self.current_path()

        output_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("%s - Save/Load Annotations in Directory") % __appname__,
            default_output_dir,
            QtWidgets.QFileDialog.ShowDirsOnly
            | QtWidgets.QFileDialog.DontResolveSymlinks,
        )
        output_dir = str(output_dir)

        if not output_dir:
            return

        self.output_dir = output_dir

        self.statusBar().showMessage(
            self.tr("%s . Annotations will be saved/loaded in %s")
            % ("Change Annotations Dir", self.output_dir)
        )
        self.statusBar().show()

        current_filename = self.filename
        self.import_image_folder(self.last_open_dir, load=False)

        if current_filename in self.image_list:
            # retain currently selected file
            self.file_list_widget.setCurrentRow(
                self.fn_to_index[str(current_filename)]
            )
            self.file_list_widget.repaint()

    def save_file(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        if self.label_file:
            # DL20180323 - overwrite when in directory
            self._save_file(self.label_file.filename)
        elif self.output_file:
            self._save_file(self.output_file)
            self.close()
        else:
            self._save_file(self.save_file_dialog())

    def save_file_as(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._save_file(self.save_file_dialog())

    def save_file_dialog(self):
        caption = self.tr("%s - Choose File") % __appname__
        filters = self.tr("Label files (*%s)") % LabelFile.suffix
        if self.output_dir:
            file_dialog = QtWidgets.QFileDialog(
                self, caption, self.output_dir, filters
            )
        else:
            file_dialog = QtWidgets.QFileDialog(
                self, caption, self.current_path(), filters
            )
        file_dialog.setDefaultSuffix(LabelFile.suffix[1:])
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        file_dialog.setOption(
            QtWidgets.QFileDialog.DontConfirmOverwrite, False
        )
        file_dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, False)
        basename = osp.basename(osp.splitext(self.filename)[0])
        if self.output_dir:
            default_labelfile_name = osp.join(
                self.output_dir, basename + LabelFile.suffix
            )
        else:
            default_labelfile_name = osp.join(
                self.current_path(), basename + LabelFile.suffix
            )
        filename = file_dialog.getSaveFileName(
            self,
            self.tr("Choose File"),
            default_labelfile_name,
            self.tr("Label files (*%s)") % LabelFile.suffix,
        )
        if isinstance(filename, tuple):
            filename, _ = filename
        return filename

    def _save_file(self, filename):
        if filename and self.save_labels(filename):
            self.add_recent_file(filename)
            self.set_clean()

    def close_file(self, _value=False):
        if not self.may_continue():
            return
        self.reset_state()
        self.file_list_widget.clear()
        self.fn_to_index.clear()
        self.last_open_dir = None
        self.set_clean()
        self.toggle_actions(False)
        self.canvas.setEnabled(False)
        self.actions.save_as.setEnabled(False)

    def get_label_file(self):
        if self.filename.lower().endswith(".json"):
            label_file = self.filename
        else:
            label_file = osp.splitext(self.filename)[0] + ".json"

        return label_file

    def get_image_file(self):
        if not self.filename.lower().endswith(".json"):
            image_file = self.filename
        else:
            image_file = self.image_path

        return image_file

    def delete_file(self):
        mb = QtWidgets.QMessageBox
        msg = self.tr(
            "You are about to permanently delete this label file, "
            "proceed anyway?"
        )
        answer = mb.warning(self, self.tr("Attention"), msg, mb.Yes | mb.No)
        if answer != mb.Yes:
            return

        label_file = self.get_label_file()
        if osp.exists(label_file):
            os.remove(label_file)
            logger.info(f"Label file is removed: {label_file}")

            item = self.file_list_widget.currentItem()
            item.setCheckState(Qt.Unchecked)

            filename = self.filename
            self.reset_state()
            self.filename = filename
            if self.filename:
                self.load_file(self.filename)

    def delete_image_file(self):
        if len(self.image_list) < 2:
            return

        mb = QtWidgets.QMessageBox
        msg = self.tr(
            "You are about to permanently delete this image file, "
            "proceed anyway?"
        )
        answer = mb.warning(self, self.tr("Attention"), msg, mb.Yes | mb.No)
        if answer != mb.Yes:
            return

        image_file = self.get_image_file()
        if osp.exists(image_file):
            image_path, image_name = osp.split(image_file)
            save_path = osp.join(image_path, "..", "_delete_")
            os.makedirs(save_path, exist_ok=True)
            save_file = osp.join(save_path, image_name)
            shutil.move(image_file, save_file)
            logger.info(f"Image file is moved to: {osp.realpath(save_file)}")

            label_dir_path = osp.dirname(self.filename)
            if self.output_dir:
                label_dir_path = self.output_dir
            label_name = osp.splitext(image_name)[0] + ".json"
            label_file = osp.join(label_dir_path, label_name)
            if not osp.exists(label_file):
                label_file = osp.join(osp.dirname(image_file), label_name)
            if osp.exists(label_file):
                os.remove(label_file)
                logger.info(f"Label file is removed: {image_file}")

            filename = None
            if self.filename is None:
                filename = self.image_list[0]
            else:
                current_index = self.fn_to_index[str(self.filename)]
                if current_index + 1 < len(self.image_list):
                    filename = self.image_list[current_index + 1]
                else:
                    filename = self.image_list[0]

            self.reset_state()
            if osp.isfile(image_path):
                image_path = osp.dirname(image_path)
            self.import_image_folder(image_path)

            self.filename = filename
            if self.filename:
                self.load_file(self.filename)

    # Message Dialogs. #
    def has_labels(self):
        if self.no_shape():
            self.error_message(
                "No objects labeled",
                "You must label at least one object to save the file.",
            )
            return False
        return True

    def has_label_file(self):
        if self.filename is None:
            return False

        label_file = self.get_label_file()
        return osp.exists(label_file)

    def may_continue(self):
        if not self.dirty:
            return True
        mb = QtWidgets.QMessageBox
        msg = self.tr(
            f'Save annotations to "{self.filename!r}" before closing?'
        )
        answer = mb.question(
            self,
            self.tr("Save annotations?"),
            msg,
            mb.Save | mb.Discard | mb.Cancel,
            mb.Save,
        )
        if answer == mb.Discard:
            return True
        if answer == mb.Save:
            self.save_file()
            return True
        # answer == mb.Cancel
        return False

    def error_message(self, title, message):
        return QtWidgets.QMessageBox.critical(
            self, title, f"<p><b>{title}</b></p>{message}"
        )

    def current_path(self):
        return osp.dirname(str(self.filename)) if self.filename else "."

    def toggle_visibility_shapes(self, value):
        for index, item in enumerate(self.label_list):
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)
            self.label_list[index].shape().visible = True if value else False
        self._config["show_shapes"] = value
        # 更新导航器显示
        self.update_navigator_shapes()

    def remove_selected_point(self):
        self.canvas.remove_selected_point()
        self.canvas.update()
        if self.canvas.h_hape is not None and not self.canvas.h_hape.points:
            self.canvas.delete_shape(self.canvas.h_hape)
            self.remove_labels([self.canvas.h_hape])
            self.set_dirty()
            if self.no_shape():
                for action in self.actions.on_shapes_present:
                    action.setEnabled(False)

    def delete_selected_shape(self):
        self.remove_labels(self.canvas.delete_selected())
        self.set_dirty()
        # Update expand margins dialog colors after shape deletion
        self._update_expand_margins_colors()
        if self.no_shape():
            for action in self.actions.on_shapes_present:
                action.setEnabled(False)

    def copy_shape(self):
        self.canvas.end_move(copy=True)
        for shape in self.canvas.selected_shapes:
            self.add_label(shape)
        self.label_list.clearSelection()
        self.set_dirty()
        # Update expand margins dialog colors after shape copy
        self._update_expand_margins_colors()

    def move_shape(self):
        self.canvas.end_move(copy=False)
        self.set_dirty()

    def open_folder_dialog(self, _value=False, dirpath=None):
        if not self.may_continue():
            return

        default_open_dir_path = dirpath if dirpath else "."
        if self.last_open_dir and osp.exists(self.last_open_dir):
            default_open_dir_path = self.last_open_dir
        else:
            default_open_dir_path = (
                osp.dirname(self.filename) if self.filename else "."
            )

        target_dir_path = str(
            QtWidgets.QFileDialog.getExistingDirectory(
                self,
                self.tr("%s - Open Directory") % __appname__,
                default_open_dir_path,
                QtWidgets.QFileDialog.ShowDirsOnly
                | QtWidgets.QFileDialog.DontResolveSymlinks,
            )
        )

        if not target_dir_path:
            return

        # Read the recursive option from the config
        recursive = self._config.get("load_subfolders", False)
        self.import_image_folder(target_dir_path, recursive=recursive)

    @property
    def image_list(self):
        lst = []
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            # Use UserRole data if available (to handle potential display modifications)
            filename = item.data(Qt.UserRole)
            if not filename:
                filename = item.text()
            lst.append(filename)
        return lst

    def import_dropped_image_files(self, image_files):
        extensions = [
            f".{fmt.data().decode().lower()}"
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]

        self.filename = None
        for file in image_files:
            if file in self.image_list or not file.lower().endswith(
                tuple(extensions)
            ):
                continue
            label_file = osp.splitext(file)[0] + ".json"
            if self.output_dir:
                label_file_without_path = osp.basename(label_file)
                label_file = self.output_dir + "/" + label_file_without_path
            item = QtWidgets.QListWidgetItem(file)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(
                label_file
            ):
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.file_list_widget.addItem(item)
            self.fn_to_index[file] = self.file_list_widget.count() - 1

        if len(self.image_list) > 1:
            self.actions.open_next_image.setEnabled(True)
            self.actions.open_prev_image.setEnabled(True)
            self.actions.open_next_unchecked_image.setEnabled(True)
            self.actions.open_prev_unchecked_image.setEnabled(True)

        self.open_next_image()

    def import_image_folder(self, dirpath, pattern=None, load=True, recursive=None):
        if recursive is None:
            recursive = self._config.get("load_subfolders", False)
        if not self.may_continue() or not dirpath:
            return

        # Add to recent folders history
        # Normalize path to use forward slashes for consistency
        dirpath = str(dirpath).replace('\\', '/')
        if dirpath in self.recent_folders:
            self.recent_folders.remove(dirpath)
        elif len(self.recent_folders) >= self.max_recent_folders:
            self.recent_folders.pop()
        self.recent_folders.insert(0, dirpath)
        self.settings.setValue("recent_folders", self.recent_folders)
        # No need to refresh menu here - it will auto-refresh via aboutToShow

        self.last_open_dir = dirpath
        self.file_list_widget.clear()
        self.fn_to_index = {}
        for filename in utils.scan_all_images(dirpath, recursive=recursive):
            if pattern and pattern not in filename:
                continue
            label_file = osp.splitext(filename)[0] + ".json"
            if self.output_dir:
                label_file_without_path = osp.basename(label_file)
                label_file = self.output_dir + "/" + label_file_without_path

            # Check if file was manually edited
            manually_edited = False
            if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(label_file):
                try:
                    with open(label_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        manually_edited = data.get("manually_edited", False)
                except:
                    pass

            # Create list item with actual filename
            item = QtWidgets.QListWidgetItem(filename)
            item.setData(Qt.UserRole, filename)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(
                label_file
            ):
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

            # Set color for manually edited items
            if manually_edited:
                color = self._config.get("manually_edited_color", "#FFA500")
                item.setForeground(QtGui.QColor(color))

            self.file_list_widget.addItem(item)
            self.fn_to_index[filename] = self.file_list_widget.count() - 1
            # utils.process_image_exif(filename)

        self.actions.open_next_image.setEnabled(True)
        self.actions.open_prev_image.setEnabled(True)
        self.actions.open_next_unchecked_image.setEnabled(True)
        self.actions.open_prev_unchecked_image.setEnabled(True)

        # After repopulating the file list, refresh the expand margins dialog if it's open.
        if self.expand_margins_dialog and self.expand_margins_dialog.isVisible():
            all_labels = self._config.get("labels", [])
            total_files = self.file_list_widget.count()
            # At this point, no item is selected yet, so the current page is temporarily set to 1.
            # The subsequent call to load_file -> file_selection_changed will update it precisely.
            self.expand_margins_dialog.refresh_state(all_labels, total_files, 1)

        # 刷新 "标签排序工具"
        if self.tag_sort_dialog and self.tag_sort_dialog.isVisible():
            total_files = self.file_list_widget.count()
            self.tag_sort_dialog.refresh_state(total_files, 1)

        # 刷新 "双色标签工具"
        if self.label_tool_dialog and self.label_tool_dialog.isVisible():
            total_files = self.file_list_widget.count()
            new_folder_path = self.last_open_dir 
            self.label_tool_dialog.refresh_state(total_files, 1, new_folder_path)

        if load:
            self.filename = None
            self.open_next_image(load=load)

    def toggle_auto_labeling_widget(self):
        """Toggle auto labeling widget visibility."""
        if self.auto_labeling_widget.isVisible():
            self.auto_labeling_widget.hide()
            self.actions.run_all_images.setEnabled(False)
        else:
            self.auto_labeling_widget.show()
            self.actions.run_all_images.setEnabled(True)
        self.update_thumbnail_display()

    @pyqtSlot()
    def new_shapes_from_auto_labeling(self, auto_labeling_result):
        """Apply auto labeling results to the current image."""
        if not self.image or not self.image_path:
            return

        # Clear existing shapes
        if auto_labeling_result.replace:
            self.load_shapes([], replace=True)
            self.label_list.clear()
            self.load_shapes(auto_labeling_result.shapes, replace=True)
        else:  # Just update existing shapes
            # Remove shapes with label AutoLabelingMode.OBJECT
            for shape in self.canvas.shapes:
                if shape.label == AutoLabelingMode.OBJECT:
                    item = self.label_list.find_item_by_shape(shape)
                    self.label_list.remove_item(item)
            self.load_shapes(auto_labeling_result.shapes, replace=False)

        # Set image description
        if auto_labeling_result.description:
            description = auto_labeling_result.description
            self.shape_text_label.setText(self.tr("Image Description"))
            self.shape_text_edit.setPlainText(description)
            self.other_data["description"] = description
            self.shape_text_edit.setDisabled(False)

        # Clear manually_edited flag when AI re-inference
        self.other_data["manually_edited"] = False

        # Mark as dirty but not as manually edited (this is AI inference, not user edit)
        self.set_dirty(mark_as_manually_edited=False)

    def clear_auto_labeling_marks(self):
        """Clear auto labeling marks from the current image."""
        # Clean up label list
        for shape in self.canvas.shapes:
            if shape.label in [
                AutoLabelingMode.OBJECT,
                AutoLabelingMode.ADD,
                AutoLabelingMode.REMOVE,
            ]:
                try:
                    item = self.label_list.find_item_by_shape(shape)
                    self.label_list.remove_item(item)
                except ValueError:
                    pass

        # Clean up unique label list
        for shape_label in [
            AutoLabelingMode.OBJECT,
            AutoLabelingMode.ADD,
            AutoLabelingMode.REMOVE,
        ]:
            for item in self.unique_label_list.find_items_by_label(
                shape_label
            ):
                self.unique_label_list.takeItem(
                    self.unique_label_list.row(item)
                )

        # Remove shapes from the canvas
        self.canvas.shapes = [
            shape
            for shape in self.canvas.shapes
            if shape.label
            not in [
                AutoLabelingMode.OBJECT,
                AutoLabelingMode.ADD,
                AutoLabelingMode.REMOVE,
            ]
        ]
        self.canvas.update()

    def find_last_label(self):
        """
        Find the last label in the label list.
        Exclude labels for auto labeling.
        """

        # Get from dialog history
        last_label = self.label_dialog.get_last_label()
        if last_label:
            return last_label

        # Get selected label from the label list
        items = self.label_list.selected_items()
        if items:
            shape = items[0].data(Qt.UserRole)
            return shape.label

        # Get the last label from the label list
        for item in reversed(self.label_list):
            shape = item.data(Qt.UserRole)
            if shape.label not in [
                AutoLabelingMode.OBJECT,
                AutoLabelingMode.ADD,
                AutoLabelingMode.REMOVE,
            ]:
                return shape.label

        # No label is found
        return ""

    def set_cache_auto_label(self):
        self.auto_labeling_widget.on_cache_auto_label_changed(
            self.cache_auto_label, self.cache_auto_label_group_id
        )

    def finish_auto_labeling_object(self):
        """Finish auto labeling object."""
        has_object, cache_label = False, None
        for shape in self.canvas.shapes:
            if shape.label == AutoLabelingMode.OBJECT:
                cache_label = shape.cache_label
                cache_description = shape.cache_description
                has_object = True
                break

        # If there is no object, do nothing
        if not has_object:
            return

        # Ask a label for the object
        text, flags, group_id, description, difficult, kie_linking = (
            "",
            {},
            None,
            None,
            False,
            [],
        )
        last_label = self.find_last_label()
        if self._config["auto_use_last_label"] and last_label:
            text = last_label
        elif cache_label is not None:
            text = cache_label
            description = cache_description
        else:
            previous_text = self.label_dialog.edit.text()
            (
                text,
                flags,
                group_id,
                description,
                difficult,
                kie_linking,
                _,
                _,
            ) = self.label_dialog.pop_up(
                text=self.find_last_label(),
                flags={},
                group_id=None,
                description=None,
                difficult=False,
                kie_linking=[],
                move_mode=self._config.get("move_mode", "auto"),
            )
            if not text:
                self.label_dialog.edit.setText(previous_text)
                return

        self.cache_auto_label = text
        self.cache_auto_label_group_id = group_id
        if not self.validate_label(text):
            self.error_message(
                self.tr("Invalid label"),
                self.tr("Invalid label '{}' with validation type '{}'").format(
                    text, self._config["validate_label"]
                ),
            )
            return

        if self.attributes and text:
            text = self.reset_attribute(text)

        # Add to label history
        self.label_dialog.add_label_history(text)

        # Update label for the object
        updated_shapes = False
        for shape in self.canvas.shapes:
            if shape.label == AutoLabelingMode.OBJECT:
                updated_shapes = True
                shape.label = text
                shape.flags = flags
                shape.group_id = group_id
                shape.description = description
                shape.difficult = difficult
                shape.kie_linking = kie_linking
                # Update unique label list
                if not self.unique_label_list.find_items_by_label(shape.label):
                    unique_label_item = (
                        self.unique_label_list.create_item_from_label(
                            shape.label
                        )
                    )
                    self.unique_label_list.addItem(unique_label_item)
                    rgb = self._get_rgb_by_label(shape.label)
                    self.unique_label_list.set_item_label(
                        unique_label_item, shape.label, rgb, LABEL_OPACITY
                    )

                # Update label list
                self._update_shape_color(shape)
                item = self.label_list.find_item_by_shape(shape)
                if shape.group_id is None:
                    color = shape.fill_color.getRgb()[:3]
                    item.setText(
                        '{} <font color="#{:02x}{:02x}{:02x}">●</font>'.format(
                            html.escape(shape.label), *color
                        )
                    )
                else:
                    item.setText(f"{shape.label} ({shape.group_id})")

        # Clean up auto labeling objects
        self.clear_auto_labeling_marks()

        # Update shape colors
        for shape in self.canvas.shapes:
            self._update_shape_color(shape)
            color = shape.fill_color.getRgb()[:3]
            item = self.label_list.find_item_by_shape(shape)
            item.setText("{}".format(html.escape(shape.label)))
            item.setBackground(QtGui.QColor(*color, LABEL_OPACITY))
            self.unique_label_list.update_item_color(
                shape.label, color, LABEL_OPACITY
            )

        if updated_shapes:
            self.set_dirty()

    def shape_text_changed(self):
        description = self.shape_text_edit.toPlainText()
        if self.canvas.current is not None:
            self.canvas.current.description = description
        elif self.canvas.editing() and len(self.canvas.selected_shapes) == 1:
            self.canvas.selected_shapes[0].description = description
        else:
            self.other_data["description"] = description
        self.set_dirty()

    def set_text_editing(self, enable):
        """Set text editing."""
        if enable:
            # Enable text editing and set shape text from selected shape
            if len(self.canvas.selected_shapes) == 1:
                self.shape_text_label.setText(self.tr("Object Description"))
                self.shape_text_edit.textChanged.disconnect()
                self.shape_text_edit.setPlainText(
                    self.canvas.selected_shapes[0].description
                )
                self.shape_text_edit.textChanged.connect(
                    self.shape_text_changed
                )
            else:
                self.shape_text_label.setText(self.tr("Image Description"))
                self.shape_text_edit.textChanged.disconnect()
                self.shape_text_edit.setPlainText(
                    self.other_data.get("description", "")
                )
                self.shape_text_edit.textChanged.connect(
                    self.shape_text_changed
                )
            self.shape_text_edit.setDisabled(False)
        else:
            self.shape_text_edit.setDisabled(True)
            self.shape_text_label.setText(
                self.tr("Switch to Edit mode for description editing")
            )
            self.shape_text_edit.textChanged.disconnect()
            self.shape_text_edit.setPlainText("")
            self.shape_text_edit.textChanged.connect(self.shape_text_changed)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.shape_text_edit.setFont(font)
        self.shape_text_label.setFont(font)

    def group_selected_shapes(self):
        self.canvas.group_selected_shapes()
        self.set_dirty()
        self.load_file(self.filename)

    def ungroup_selected_shapes(self):
        self.canvas.ungroup_selected_shapes()
        self.set_dirty()
        self.load_file(self.filename)

    def update_thumbnail_pixmap(self):
        if self.thumbnail_pixmap and not self.thumbnail_pixmap.isNull():
            width = self.thumbnail_image_label.width()
            if width > 0:
                self.thumbnail_image_label.setPixmap(
                    self.thumbnail_pixmap.scaledToWidth(
                        width, QtCore.Qt.SmoothTransformation
                    )
                )

    def update_thumbnail_display(self):
        self.thumbnail_pixmap = None
        self.thumbnail_image_label.clear()
        self.thumbnail_container.hide()

        model_config = (
            self.auto_labeling_widget.model_manager.loaded_model_config
        )
        supported_model_list = list(_THUMBNAIL_RENDER_MODELS.keys())
        if not (
            model_config
            and model_config.get("type") in supported_model_list
            and self.image_list
        ):
            return

        try:
            image_dir = osp.dirname(self.filename)
            parent_dir = osp.dirname(image_dir)
            base_name = osp.splitext(osp.basename(self.filename))[0]
            save_dir, _thumbnail_file_ext = _THUMBNAIL_RENDER_MODELS[
                model_config["type"]
            ]
            thumbnail_dir = osp.join(parent_dir, save_dir)
            thumbnail_path = osp.join(
                thumbnail_dir, base_name + _thumbnail_file_ext
            )
            if not osp.exists(thumbnail_path):
                return

            self.thumbnail_pixmap = QtGui.QPixmap(thumbnail_path)
            if not self.thumbnail_pixmap.isNull():
                self.thumbnail_container.show()
                self.update_thumbnail_pixmap()

        except Exception as e:
            logger.error(f"Failed to load thumbnail image: {str(e)}")

    def on_labels_ordered(self, labels):
        self._config["labels"] = labels
        save_config(self._config)
        self.set_dirty()

    def _adjust_shape_margins(self, shape, margins):
        """Adjusts the margins of a single shape, supporting both rectangle and rotation types."""
        if shape.shape_type not in ["rectangle", "rotation"]:
            return False

        label = shape.label
        if label not in margins:
            return False

        top, bottom, left, right = margins[label]

        if top == 0 and bottom == 0 and left == 0 and right == 0:
            return False

        if shape.shape_type == "rectangle":
            points = shape.points
            xs = [p.x() for p in points]
            ys = [p.y() for p in points]
            x_min, y_min, x_max, y_max = min(xs), min(ys), max(xs), max(ys)

            nx_min = x_min - left
            ny_min = y_min - top
            nx_max = x_max + right
            ny_max = y_max + bottom

            if nx_min >= nx_max or ny_min >= ny_max:
                return False

            shape.points = [
                QtCore.QPointF(nx_min, ny_min),
                QtCore.QPointF(nx_max, ny_min),
                QtCore.QPointF(nx_max, ny_max),
                QtCore.QPointF(nx_min, ny_max),
            ]
            return True

        elif shape.shape_type == "rotation":
            points = np.array([[p.x(), p.y()] for p in shape.points])

            # Calculate center, width, height, and angle
            center = np.mean(points, axis=0)
            width = np.linalg.norm(points[0] - points[1])
            height = np.linalg.norm(points[0] - points[3])

            vec = points[1] - points[0]
            angle = np.arctan2(vec[1], vec[0])

            # Adjust width and height
            new_width = width + left + right
            new_height = height + top + bottom

            if new_width <= 0 or new_height <= 0:
                return False

            # Adjust center based on margin changes
            # This keeps the expansion centered correctly
            center_offset_x = (right - left) / 2.0
            center_offset_y = (bottom - top) / 2.0
            
            dx = center_offset_x * np.cos(angle) - center_offset_y * np.sin(angle)
            dy = center_offset_x * np.sin(angle) + center_offset_y * np.cos(angle)
            
            new_center = center + np.array([dx, dy])

            # Recalculate the four corners
            hw = new_width / 2.0
            hh = new_height / 2.0
            
            cos_a = np.cos(angle)
            sin_a = np.sin(angle)

            new_points = np.array([
                [-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]
            ])
            
            rotation_matrix = np.array([
                [cos_a, -sin_a],
                [sin_a, cos_a]
            ])
            
            rotated_points = np.dot(new_points, rotation_matrix.T)
            final_points = rotated_points + new_center

            shape.points = [QtCore.QPointF(p[0], p[1]) for p in final_points]
            return True
            
        return False

    def on_expand_margins_current(self, margins):
        """Handle applying margins to all shapes in the current image."""
        modified_count = 0
        for shape in self.canvas.shapes:
            if self._adjust_shape_margins(shape, margins):
                modified_count += 1
        
        if modified_count > 0:
            self.canvas.update()
            self.set_dirty()
            self.status(self.tr(f"已更新当前页面上的 {modified_count} 个标注框。"))
            self._update_navigator_title_with_selection()
        else:
            self.status(self.tr("当前页面上没有需要更新的标注框。"))

    def on_expand_margins_selected(self, margins):
        """Handle applying margins to selected shapes in the current image."""
        if not self.canvas.selected_shapes:
            self.status(self.tr("没有选中的标注框。"))
            return

        modified_count = 0
        for shape in self.canvas.selected_shapes:
            if self._adjust_shape_margins(shape, margins):
                modified_count += 1

        if modified_count > 0:
            self.canvas.update()
            self.set_dirty()
            self.status(self.tr(f"已更新选中的 {modified_count} 个标注框。"))
            self._update_navigator_title_with_selection()
        else:
            self.status(self.tr("选中的标注框没有需要更新的。"))

    def on_expand_margins_all(self, margins):
        """Handle applying margins to all shapes in all images."""
        if not self.image_list:
            self.status(self.tr("没有加载图像列表。"))
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            self.tr("确认操作"),
            self.tr(
                f"你确定要将这些边距更改应用到全部 {len(self.image_list)} 个文件的标注吗？\n"
                "这个操作会直接修改文件且无法撤销。"
            ),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        processed_files = 0
        modified_shapes_total = 0

        for image_path in self.image_list:
            label_file_path = osp.splitext(image_path)[0] + ".json"
            if self.output_dir:
                label_file_path = osp.join(self.output_dir, osp.basename(label_file_path))
            
            if not osp.exists(label_file_path):
                continue

            try:
                with open(label_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                shapes_data = data.get("shapes", [])
                modified_in_file = False
                modified_shapes_count = 0

                for shape_dict in shapes_data:
                    shape_type = shape_dict.get("shape_type")
                    label = shape_dict.get("label")

                    if label not in margins:
                        continue
                    
                    top, bottom, left, right = margins[label]
                    if top == 0 and bottom == 0 and left == 0 and right == 0:
                        continue

                    points = shape_dict.get("points", [])
                    if not points: continue

                    if shape_type == "rectangle":
                        xs = [p[0] for p in points]
                        ys = [p[1] for p in points]
                        x_min, y_min, x_max, y_max = min(xs), min(ys), max(xs), max(ys)

                        nx_min = x_min - left
                        ny_min = y_min - top
                        nx_max = x_max + right
                        ny_max = y_max + bottom

                        if nx_min < nx_max and ny_min < ny_max:
                            shape_dict["points"] = [
                                [nx_min, ny_min], [nx_max, ny_min],
                                [nx_max, ny_max], [nx_min, ny_max]
                            ]
                            modified_in_file = True
                            modified_shapes_count += 1
                    
                    elif shape_type == "rotation":
                        np_points = np.array(points)
                        center = np.mean(np_points, axis=0)
                        width = np.linalg.norm(np_points[0] - np_points[1])
                        height = np.linalg.norm(np_points[0] - np_points[3])
                        
                        vec = np_points[1] - np_points[0]
                        angle = np.arctan2(vec[1], vec[0])

                        new_width = width + left + right
                        new_height = height + top + bottom

                        if new_width <= 0 or new_height <= 0:
                            continue

                        center_offset_x = (right - left) / 2.0
                        center_offset_y = (bottom - top) / 2.0
                        
                        dx = center_offset_x * np.cos(angle) - center_offset_y * np.sin(angle)
                        dy = center_offset_x * np.sin(angle) + center_offset_y * np.cos(angle)
                        
                        new_center = center + np.array([dx, dy])

                        hw = new_width / 2.0
                        hh = new_height / 2.0
                        
                        cos_a = np.cos(angle)
                        sin_a = np.sin(angle)

                        new_points_local = np.array([
                            [-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]
                        ])
                        
                        rotation_matrix = np.array([
                            [cos_a, -sin_a],
                            [sin_a, cos_a]
                        ])
                        
                        rotated_points = np.dot(new_points_local, rotation_matrix.T)
                        final_points = rotated_points + new_center

                        shape_dict["points"] = final_points.tolist()
                        modified_in_file = True
                        modified_shapes_count += 1

                if modified_in_file:
                    with open(label_file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    processed_files += 1
                    modified_shapes_total += modified_shapes_count

            except Exception as e:
                logger.error(f"处理文件失败 {label_file_path}: {e}")
                continue
        
        # Reload current file to reflect changes if it was modified
        self.load_file(self.filename)

        self.status(
            self.tr(
                f"处理完成！总共修改了 {processed_files} 个文件中的 {modified_shapes_total} 个标注框。"
            )
        )

    def on_expand_margins_in_range(self, margins, start_index, end_index):
        """Handle applying margins to all shapes in a specified range of images."""
        if not self.image_list:
            self.status(self.tr("没有加载图像列表。"))
            return

        # Validate range
        if not (0 <= start_index < len(self.image_list) and 0 <= end_index < len(self.image_list) and start_index <= end_index):
            self.error_message(self.tr("范围无效"), self.tr("提供的文件范围无效。"))
            return
            
        files_to_process = self.image_list[start_index : end_index + 1]
        num_files = len(files_to_process)

        reply = QtWidgets.QMessageBox.question(
            self,
            self.tr("确认操作"),
            self.tr(
                f"你确定要将这些边距更改应用到从 {start_index + 1} 到 {end_index + 1} 的 {num_files} 个文件的标注吗？\n"
                "这个操作会直接修改文件且无法撤销。"
            ),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        processed_files = 0
        modified_shapes_total = 0

        for image_path in files_to_process:
            label_file_path = osp.splitext(image_path)[0] + ".json"
            if self.output_dir:
                label_file_path = osp.join(self.output_dir, osp.basename(label_file_path))
            
            if not osp.exists(label_file_path):
                continue

            try:
                with open(label_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                shapes_data = data.get("shapes", [])
                modified_in_file = False
                modified_shapes_count = 0

                for shape_dict in shapes_data:
                    shape_type = shape_dict.get("shape_type")
                    label = shape_dict.get("label")

                    if label not in margins:
                        continue
                    
                    top, bottom, left, right = margins[label]
                    if top == 0 and bottom == 0 and left == 0 and right == 0:
                        continue

                    points = shape_dict.get("points", [])
                    if not points: continue

                    if shape_type == "rectangle":
                        xs = [p[0] for p in points]
                        ys = [p[1] for p in points]
                        x_min, y_min, x_max, y_max = min(xs), min(ys), max(xs), max(ys)

                        nx_min = x_min - left
                        ny_min = y_min - top
                        nx_max = x_max + right
                        ny_max = y_max + bottom

                        if nx_min < nx_max and ny_min < ny_max:
                            shape_dict["points"] = [
                                [nx_min, ny_min], [nx_max, ny_min],
                                [nx_max, ny_max], [nx_min, ny_max]
                            ]
                            modified_in_file = True
                            modified_shapes_count += 1
                    
                    elif shape_type == "rotation":
                        np_points = np.array(points)
                        center = np.mean(np_points, axis=0)
                        width = np.linalg.norm(np_points[0] - np_points[1])
                        height = np.linalg.norm(np_points[0] - np_points[3])
                        
                        vec = np_points[1] - np_points[0]
                        angle = np.arctan2(vec[1], vec[0])

                        new_width = width + left + right
                        new_height = height + top + bottom

                        if new_width <= 0 or new_height <= 0:
                            continue

                        center_offset_x = (right - left) / 2.0
                        center_offset_y = (bottom - top) / 2.0
                        
                        dx = center_offset_x * np.cos(angle) - center_offset_y * np.sin(angle)
                        dy = center_offset_x * np.sin(angle) + center_offset_y * np.cos(angle)
                        
                        new_center = center + np.array([dx, dy])

                        hw = new_width / 2.0
                        hh = new_height / 2.0
                        
                        cos_a = np.cos(angle)
                        sin_a = np.sin(angle)

                        new_points_local = np.array([
                            [-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]
                        ])
                        
                        rotation_matrix = np.array([
                            [cos_a, -sin_a],
                            [sin_a, cos_a]
                        ])
                        
                        rotated_points = np.dot(new_points_local, rotation_matrix.T)
                        final_points = rotated_points + new_center

                        shape_dict["points"] = final_points.tolist()
                        modified_in_file = True
                        modified_shapes_count += 1

                if modified_in_file:
                    with open(label_file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    processed_files += 1
                    modified_shapes_total += modified_shapes_count

            except Exception as e:
                logger.error(f"处理文件失败 {label_file_path}: {e}")
                continue
        
        # Reload current file to reflect changes if it was modified
        self.load_file(self.filename)

        self.status(
            self.tr(
                f"处理完成！总共修改了 {processed_files} 个文件中的 {modified_shapes_total} 个标注框。"
            )
        )

    def on_expand_margins_single_label(self, margins):
        """Handle applying margins to a single label on the current page."""
        modified_count = 0
        label_to_apply = list(margins.keys())[0]
        for shape in self.canvas.shapes:
            if shape.label == label_to_apply:
                if self._adjust_shape_margins(shape, margins):
                    modified_count += 1
        
        if modified_count > 0:
            self.canvas.update()
            self.set_dirty()
            self.status(self.tr(f"已更新当前页面上标签为 '{label_to_apply}' 的 {modified_count} 个标注框。"))
            self._update_navigator_title_with_selection()
        else:
            self.status(self.tr(f"当前页面上没有需要更新的 '{label_to_apply}' 标签的标注框。"))

    def on_expand_margins_single_label_selected(self, margins):
        """Handle applying margins to a single label on selected shapes."""
        if not self.canvas.selected_shapes:
            self.status(self.tr("没有选中的标注框。"))
            return

        modified_count = 0
        label_to_apply = list(margins.keys())[0]

        for shape in self.canvas.selected_shapes:
            if shape.label == label_to_apply:
                if self._adjust_shape_margins(shape, margins):
                    modified_count += 1
        
        if modified_count > 0:
            self.canvas.update()
            self.set_dirty()
            self.status(self.tr(f"已更新选中的标签为 '{label_to_apply}' 的 {modified_count} 个标注框。"))
            self._update_navigator_title_with_selection()
        else:
            self.status(self.tr(f"选中的标注框中没有需要更新的 '{label_to_apply}' 标签。"))

    def on_jump_to_image(self, index):
        """Handle jumping to a specific image index."""
        if 0 <= index < self.file_list_widget.count():
            self.file_list_widget.setCurrentRow(index)
            self.status(self.tr(f"已跳转到第 {index + 1} 张图片。"))
        else:
            self.status(self.tr(f"无效的图片索引: {index + 1}"))

    def _update_expand_margins_colors(self):
        """Update colors in expand margins dialog if it's open and visible."""
        if (hasattr(self, 'expand_margins_dialog') and
            self.expand_margins_dialog is not None and
            self.expand_margins_dialog.isVisible()):
            self.expand_margins_dialog.refresh_colors()

    def open_merge_tool(self):
        if not self.image_list:
            self.error_message("无图像", "请先打开一个包含图像的文件夹。")
            return

        if self.merge_tool_dialog is None:
            self.merge_tool_dialog = MergeDialog(self)
            self.merge_tool_dialog.run_current_button.clicked.connect(
                lambda: self.run_merge_task(self.merge_tool_dialog.get_config(), on_current_file=True)
            )
            self.merge_tool_dialog.run_all_button.clicked.connect(
                lambda: self.run_merge_task(self.merge_tool_dialog.get_config(), on_current_file=False)
            )
        
        self.merge_tool_dialog.show()
        self.merge_tool_dialog.raise_()
        self.merge_tool_dialog.activateWindow()

    def run_merge_task(self, config, on_current_file=False):
        if on_current_file:
            if not self.filename:
                self.error_message("无当前文件", "没有打开任何文件。")
                return
            files_to_process = [self.filename]
        else:
            files_to_process = self.image_list

        if not files_to_process:
            self.error_message("无文件", "没有文件可供处理。")
            return

        self.merge_thread = MergeThread(files_to_process, config)
        self.merge_thread.finished.connect(self.on_merge_finished)

        if len(files_to_process) > 1:
            self.merge_progress_dialog = QtWidgets.QProgressDialog(
                "正在合并区域...", "取消", 0, len(files_to_process), self
            )
            self.merge_progress_dialog.setWindowModality(QtCore.Qt.NonModal)
            self.merge_thread.progress.connect(self.merge_progress_dialog.setValue)
            self.merge_thread.progress.connect(lambda _, msg: self.merge_progress_dialog.setLabelText(msg))
            self.merge_thread.finished.connect(self.merge_progress_dialog.close)
            self.merge_progress_dialog.canceled.connect(self.merge_thread.requestInterruption)
            self.merge_progress_dialog.show()
        
        self.merge_thread.start()

    def on_merge_finished(self, message):
        self.load_file(self.filename)
        if self.merge_thread.files and len(self.merge_thread.files) > 1:
            popup = Popup(
                message,
                self,
                icon=utils.new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")

    def open_label_tool(self):
        if not self.last_open_dir:
            self.error_message("错误", "请先打开一个包含图像的文件夹。")
            return

        if self.label_tool_dialog is None:
            self.label_tool_dialog = LabelToolDialog(self.last_open_dir, self)

        # 如果对话框已存在但文件夹已更改，则重新创建
        if self.label_tool_dialog.folder_path != self.last_open_dir:
            self.label_tool_dialog.close()
            self.label_tool_dialog = LabelToolDialog(self.last_open_dir, self)

        self.label_tool_dialog.show()
        self.label_tool_dialog.raise_()
        self.label_tool_dialog.activateWindow()

        if self.label_tool_dialog.folder_path != self.last_open_dir:
            self.label_tool_dialog.close()
            self.label_tool_dialog = LabelToolDialog(self.last_open_dir, self)

    def open_mask_generator(self):
        """打开MASK生成对话框"""
        if self.mask_generator_dialog is None:
            from anylabeling.views.labeling.widgets.mask_generator_dialog import MaskGeneratorDialog
            self.mask_generator_dialog = MaskGeneratorDialog(self)

        self.mask_generator_dialog.show()
        self.mask_generator_dialog.raise_()
        self.mask_generator_dialog.activateWindow()


