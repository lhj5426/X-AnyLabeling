# flake8: noqa

from .about_dialog import AboutDialog
from .auto_labeling import AutoLabelingWidget
from .brightness_contrast_dialog import BrightnessContrastDialog
from .canvas import Canvas
from .chatbot_dialog import ChatbotDialog
from .vqa_dialog import VQADialog
from .color_dialog import ColorDialog
from .file_dialog_preview import FileDialogPreview
from .file_filter_dialog import FileFilterDialog
from .filter_label_widget import GroupIDFilterComboBox, LabelFilterComboBox
from .crosshair_settings_dialog import CrosshairSettingsDialog
from .label_dialog import (
    LabelDialog,
    LabelQLineEdit,
    LabelModifyDialog,
    DigitShortcutDialog,
    GroupIDModifyDialog,
)
from .object_manager_dialog import ObjectManagerDialog
from .model_dropdown_widget import SearchBar
from .label_list_widget import HTMLDelegate, LabelListWidget, LabelListWidgetItem # Added HTMLDelegate
from .overview_dialog import OverviewDialog
from .popup import Popup
from .toolbar import ToolBar
from .unique_label_qlist_widget import UniqueLabelQListWidget
from .zoom_widget import ZoomWidget
from .navigator_widget import NavigatorWidget, NavigatorDialog
from .expand_margins_dialog import ExpandMarginsDialog
from .label_category_widget import LabelCategoryWidget
from .merge_dialog import MergeDialog
from .label_tool_dialog import LabelToolDialog
from .tag_sort_dialog import TagSortDialog
from .label_toggle_shortcut_dialog import LabelToggleShortcutDialog
from .angle_correction_dialog import AngleCorrectionDialog
from .alignment_dialog import AlignmentDialog
from .keymap_dialog import KeymapDialog
from .color_manager_dialog import ColorManagerDialog
from .smart_guides_dialog import SmartGuidesDialog
from .shortcut_manager_dialog import ShortcutManagerDialog
from .segmentation_dialog import SegmentationDialog
from .wheel_settings_dialog import WheelSettingsDialog
from .rectangle3_width_dialog import Rectangle3WidthDialog
from .rectangle_scale_dialog import RectangleScaleDialog
from .page_text_dialog import PageTextDialog
from .highlight_settings_dialog import HighlightSettingsDialog
from .label_sync_dialog import LabelSyncDialog


__all__ = [
    "AboutDialog",
    "AutoLabelingWidget",
    "BrightnessContrastDialog",
    "Canvas",
    "ChatbotDialog",
    "VQADialog",
    "ColorDialog",
    "FileDialogPreview",
    "FileFilterDialog",
    "GroupIDFilterComboBox",
    "LabelFilterComboBox",
    "CrosshairSettingsDialog",
    "LabelDialog",
    "LabelQLineEdit",
    "LabelModifyDialog",
    "DigitShortcutDialog",
    "GroupIDModifyDialog",
    "ObjectManagerDialog",
    "SearchBar",
    "HTMLDelegate", # Added HTMLDelegate
    "LabelListWidget",
    "LabelListWidgetItem",
    "OverviewDialog",
    "Popup",
    "ToolBar",
    "UniqueLabelQListWidget",
    "ZoomWidget",
    "NavigatorWidget",
    "NavigatorDialog",
    "ExpandMarginsDialog",
    "LabelCategoryWidget",
    "MergeDialog",
    "LabelToolDialog",
    "TagSortDialog",
    "LabelToggleShortcutDialog",
    "AngleCorrectionDialog",
    "AlignmentDialog",
    "KeymapDialog",
    "ColorManagerDialog",
    "SmartGuidesDialog",
    "ShortcutManagerDialog",
    "SegmentationDialog",
    "Rectangle3WidthDialog",
    "RectangleScaleDialog",
    "PageTextDialog",
    "HighlightSettingsDialog",
    "WheelSettingsDialog",
    "LabelSyncDialog",
]
