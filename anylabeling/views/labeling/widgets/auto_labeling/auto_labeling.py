import os
import sys
import yaml
import collections

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QPoint, QTimer, Qt
from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QWidget,
)

from anylabeling.services.auto_labeling.model_manager import ModelManager
from anylabeling.services.auto_labeling.types import AutoLabelingMode
from anylabeling.services.auto_labeling import (
    _AUTO_LABELING_IOU_MODELS,
    _AUTO_LABELING_CONF_MODELS,
    _SKIP_PREDICTION_ON_NEW_MARKS_MODELS,
)
from anylabeling.views.labeling.logger import logger
from anylabeling.views.labeling.utils.style import (
    get_lineedit_style,
    get_double_spinbox_style,
    get_normal_button_style,
    get_highlight_button_style,
    get_toggle_button_style,
)
from anylabeling.views.labeling.widgets.api_token_dialog import ApiTokenDialog
from anylabeling.views.labeling.widgets.filter_classes_dialog import FilterClassesDialog
from anylabeling.views.labeling.widgets.searchable_model_dropdown import (
    load_json,
    save_json,
    _MODELS_CONFIG_PATH,
    MAX_CUSTOM_MODELS,
    SearchableModelDropdownPopup,
)


def _normalize_classes(classes):
    if isinstance(classes, dict):
        return list(classes.values())
    return classes or []


class AutoLabelingWidget(QWidget):
    new_model_selected = pyqtSignal(str)
    new_custom_model_selected = pyqtSignal(str)
    auto_segmentation_requested = pyqtSignal()
    auto_segmentation_disabled = pyqtSignal()
    auto_labeling_mode_changed = pyqtSignal(AutoLabelingMode)
    clear_auto_labeling_action_requested = pyqtSignal()
    recog_selected_finished = pyqtSignal(str)  # 选中框识别完成，携带描述文本
    finish_auto_labeling_object_action_requested = pyqtSignal()
    cache_auto_label_changed = pyqtSignal()
    auto_decode_mode_changed = pyqtSignal(bool)
    clear_auto_decode_requested = pyqtSignal()

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        current_dir = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_dir, "auto_labeling.ui"), self)

        self.model_manager = ModelManager()
        self.model_manager.new_model_status.connect(self.on_new_model_status)
        self.new_model_selected.connect(self.model_manager.load_model)
        self.new_custom_model_selected.connect(
            self.model_manager.load_custom_model
        )
        self.model_manager.model_loaded.connect(self.update_visible_widgets)
        self.model_manager.model_loaded.connect(self.on_new_model_loaded)
        self.model_manager.new_auto_labeling_result.connect(
            lambda auto_labeling_result: self.parent.new_shapes_from_auto_labeling(
                auto_labeling_result
            )
        )
        self.model_manager.auto_segmentation_model_selected.connect(
            self.auto_segmentation_requested
        )
        self.model_manager.auto_segmentation_model_unselected.connect(
            self.auto_segmentation_disabled
        )
        self.model_manager.output_modes_changed.connect(
            self.on_output_modes_changed
        )
        self.output_select_combobox.currentIndexChanged.connect(
            lambda: self.model_manager.set_output_mode(
                self.output_select_combobox.currentData()
            )
        )
        self.upn_select_combobox.currentIndexChanged.connect(
            self.on_upn_mode_changed
        )
        self.florence2_select_combobox.currentIndexChanged.connect(
            self.on_florence2_mode_changed
        )
        self.gd_select_combobox.currentIndexChanged.connect(
            self.on_gd_mode_changed
        )

        # Disable tools when inference is running
        def set_enable_tools(enable):
            self.model_selection_button.setEnabled(enable)
            self.output_select_combobox.setEnabled(enable)
            self.button_add_point.setEnabled(enable)
            self.button_remove_point.setEnabled(enable)
            self.button_add_rect.setEnabled(enable)
            self.button_clear.setEnabled(enable)
            self.button_finish_object.setEnabled(enable)
            self.button_auto_decode.setEnabled(enable)
            self.upn_select_combobox.setEnabled(enable)
            self.gd_select_combobox.setEnabled(enable)
            self.florence2_select_combobox.setEnabled(enable)

        self.model_manager.prediction_started.connect(
            lambda: set_enable_tools(False)
        )
        self.model_manager.prediction_finished.connect(
            lambda: set_enable_tools(True)
        )

        # Init value
        self.initial_conf_value = 0
        self.initial_iou_value = 0
        self.initial_preserve_annotations_state = False
        self.initial_rotation_state = False
        self.initial_filter_non_rotated_state = False

        # 保存从YAML导入的额外标签（在软件运行期间持久化）
        self.extra_labels_from_yaml = []

        # ===================================
        #  Auto labeling buttons
        # ===================================

        # --- Configuration for: model_selection_button ---
        model_data = self.init_model_data()
        self.model_dropdown = SearchableModelDropdownPopup(model_data)
        self.model_dropdown.hide()
        self.model_dropdown.modelSelected.connect(self.on_model_selected)
        self.model_selection_button.setStyleSheet(get_normal_button_style())
        self.model_selection_button.clicked.connect(self.show_model_dropdown)

        # --- Configuration for: button_run ---
        self.button_run.setShortcut("I")
        self.button_run.setStyleSheet(get_highlight_button_style())
        self.button_run.clicked.connect(self.run_prediction)

        # --- Configuration for: button_recog_selected ---
        self.button_recog_selected.setStyleSheet(get_highlight_button_style())
        self.button_recog_selected.clicked.connect(
            self.run_recognition_on_selected
        )
        # 跨线程安全：子线程完成 OCR 后通过信号更新 UI
        self.recog_selected_finished.connect(
            self._on_recog_selected_finished
        )

        # --- Configuration for: button_recog_all ---
        self.button_recog_all.setStyleSheet(get_highlight_button_style())
        self.button_recog_all.clicked.connect(
            self.run_recognition_on_all
        )

        # --- Configuration for: toggle_use_existing_boxes ---
        self.toggle_use_existing_boxes.setCheckable(True)
        self.toggle_use_existing_boxes.setChecked(False)
        self.toggle_use_existing_boxes.setStyleSheet(
            self._get_replace_button_style("#d9534f", "#c9302c")
        )
        self.toggle_use_existing_boxes.toggled.connect(
            self._on_toggle_use_existing_boxes
        )

        # --- Configuration for: button_detect_only ---
        self.button_detect_only.setStyleSheet(
            self._get_replace_button_style("#f0ad4e", "#ec971f")
        )
        self.button_detect_only.clicked.connect(self.run_detect_only)

        # --- Configuration for: button_reset_tracker ---
        self.button_reset_tracker.setStyleSheet(get_normal_button_style())
        self.button_reset_tracker.clicked.connect(self.on_reset_tracker)

        # --- Configuration for: button_filter_classes ---
        self.button_filter_classes.setStyleSheet(get_normal_button_style())
        self.button_filter_classes.clicked.connect(self.on_filter_classes_clicked)
        self.button_filter_classes.setToolTip(
            self.tr("Configure which labels to display in detection results")
        )

        # --- Configuration for: button_set_api_token ---
        self.button_set_api_token.setStyleSheet(get_normal_button_style())
        self.button_set_api_token.setToolTip(
            self.tr(
                "You can set the API token via the GROUNDING_DINO_API_TOKEN environment variable"
            )
        )
        self.button_set_api_token.clicked.connect(self.on_set_api_token)

        # --- Configuration for: button_send ---
        self.button_send.setStyleSheet(get_highlight_button_style())
        self.button_send.clicked.connect(self.run_vl_prediction)

        # --- Configuration for: edit_conf ---
        self.edit_conf.setStyleSheet(get_double_spinbox_style())
        self.edit_conf.valueChanged.connect(self.on_conf_value_changed)

        # --- Configuration for: edit_iou ---
        self.edit_iou.setStyleSheet(get_double_spinbox_style())
        self.edit_iou.valueChanged.connect(self.on_iou_value_changed)

        # --- Configuration for: edit_text ---
        self.edit_text.setStyleSheet(get_lineedit_style())

        # --- Configuration for: button_add_point ---
        self.button_add_point.setShortcut("Q")
        self.button_add_point.clicked.connect(
            lambda: self.set_auto_labeling_mode(
                AutoLabelingMode.ADD, AutoLabelingMode.POINT
            )
        )

        # --- Configuration for: button_remove_point ---
        self.button_remove_point.setShortcut("E")
        self.button_remove_point.clicked.connect(
            lambda: self.set_auto_labeling_mode(
                AutoLabelingMode.REMOVE, AutoLabelingMode.POINT
            )
        )

        # --- Configuration for: button_add_rect ---
        self.button_add_rect.clicked.connect(
            lambda: self.set_auto_labeling_mode(
                AutoLabelingMode.ADD, AutoLabelingMode.RECTANGLE
            )
        )

        # --- Configuration for: button_clear ---
        self.button_clear.clicked.connect(self.on_clear_clicked)
        self.button_clear.setShortcut("B")

        # --- Configuration for: button_finish_object ---
        self.button_finish_object.clicked.connect(self.on_finish_clicked)
        self.button_finish_object.setShortcut("F")

        # --- Configuration for: button_auto_decode ---
        self.button_auto_decode.setStyleSheet(get_normal_button_style())
        self.button_auto_decode.clicked.connect(self.on_auto_decode_toggled)
        self.button_auto_decode.setToolTip(
            self.tr(
                "Enable auto mask decode mode for continuous point tracking"
            )
        )

        # --- Configuration for: toggle_end2end ---
        self.toggle_end2end.setChecked(True)  # Default: end2end mode ON (NMS OFF)
        self.toggle_end2end.setCheckable(True)
        # 初始状态：End2End 开启（NMS 关闭）- 灰色
        self.toggle_end2end.setStyleSheet(
            self._get_end2end_button_style("#777777", "#666666")
        )
        tooltip_on = self.tr(
            "End-to-end mode (NMS disabled). Click to enable NMS."
        )
        tooltip_off = self.tr(
            "Traditional NMS mode enabled. Click to disable NMS."
        )
        self.toggle_end2end.setToolTip(tooltip_on)
        self.toggle_end2end.clicked.connect(
            lambda checked: self._update_end2end_button_state(checked, tooltip_on, tooltip_off)
        )
        self.toggle_end2end.toggled.connect(
            self.on_end2end_state_changed
        )

        # --- Configuration for: toggle_preserve_existing_annotations ---
        self.toggle_preserve_existing_annotations.setChecked(False)
        self.toggle_preserve_existing_annotations.setCheckable(True)
        # 初始状态：标签覆盖开启 - 红色，表示会覆盖
        self.toggle_preserve_existing_annotations.setStyleSheet(
            self._get_replace_button_style("#d9534f", "#c9302c")
        )
        tooltip_on = self.tr(
            "Existing shapes will be preserved during updates. Click to switch to overwriting."
        )
        tooltip_off = self.tr(
            "Existing shapes will be overwritten by new shapes during updates. Click to switch to preserving."
        )
        self.toggle_preserve_existing_annotations.setToolTip(tooltip_off)
        self.toggle_preserve_existing_annotations.clicked.connect(
            lambda checked: self._update_replace_button_state(checked, tooltip_on, tooltip_off)
        )
        self.toggle_preserve_existing_annotations.toggled.connect(
            self.on_preserve_existing_annotations_state_changed
        )

        # --- Configuration for: toggle_rotation ---
        self.toggle_rotation.setChecked(False)
        self.toggle_rotation.setCheckable(True)
        self.toggle_rotation.setStyleSheet(
            self._get_replace_button_style("#5bc0de", "#46b8da")
        )
        tooltip_on = self.tr(
            "开启旋转矩形检测。点击切换为水平矩形。"
        )
        tooltip_off = self.tr(
            "使用水平矩形（轴对齐）。点击切换为旋转矩形。"
        )
        self._rotation_tooltip_on = tooltip_on
        self._rotation_tooltip_off = tooltip_off
        self.toggle_rotation.setToolTip(tooltip_off)
        self.toggle_rotation.setText(self.tr("旋转关"))
        self.toggle_rotation.clicked.connect(
            lambda checked: self._update_rotation_button_state(checked, tooltip_on, tooltip_off)
        )
        self.toggle_rotation.toggled.connect(
            self.on_rotation_state_changed
        )

        # --- Configuration for: toggle_filter_non_rotated ---
        self.toggle_filter_non_rotated.setChecked(False)
        self.toggle_filter_non_rotated.setCheckable(True)
        self.toggle_filter_non_rotated.setStyleSheet(
            self._get_replace_button_style("#8e44ad", "#7d3c98")
        )
        self.toggle_filter_non_rotated.hide()
        self.toggle_filter_non_rotated.clicked.connect(
            self._update_filter_non_rotated_button_state
        )
        self.toggle_filter_non_rotated.toggled.connect(
            self.on_filter_non_rotated_state_changed
        )

        # ===================================
        #  End of Auto labeling buttons
        # ===================================

        # Hide labeling widgets by default
        self.hide_labeling_widgets()

        # Handle close button
        self.button_close.clicked.connect(self.unload_and_hide)

        self.auto_labeling_mode_changed.connect(self.update_button_colors)
        self.auto_labeling_mode = AutoLabelingMode.NONE
        self.auto_labeling_mode_changed.emit(self.auto_labeling_mode)

        # Populate select combobox with modes
        self.populate_upn_combobox()
        self.populate_florence2_combobox()
        self.populate_gd_combobox()

    def init_model_data(self):
        """Get models data"""
        import hashlib
        
        model_data = {
            "Custom": {
                "load_custom_model": {
                    "selected": False,
                    "favorite": False,
                    "display_name": "...Load Custom Model",
                }
            }
        }
        self.model_info = {
            "load_custom_model": {
                "display_name": "...Load Custom Model",
                "config_path": None,
            }
        }

        # Track loaded config paths to avoid duplicates
        loaded_config_paths = set()

        # First, load from models.json (UI saved data)
        try:
            local_model_data = load_json(_MODELS_CONFIG_PATH)["models_data"]
            for model_name, model_dict in local_model_data.get("Custom", {}).items():
                if model_name == "load_custom_model":
                    continue
                
                config_path = model_dict.get("config_path", "")
                if not config_path or not os.path.exists(config_path):
                    continue

                config_path_normalized = os.path.normpath(os.path.abspath(config_path))
                loaded_config_paths.add(config_path_normalized)

                # Generate unique key based on config path
                unique_id = hashlib.md5(config_path_normalized.encode()).hexdigest()[:8]
                model_key = f"_custom_{unique_id}_{model_dict.get('display_name', 'model')}"

                model_data["Custom"][model_key] = {
                    "selected": False,
                    "favorite": model_dict.get("favorite", False),
                    "display_name": model_dict.get("display_name", model_name),
                    "config_path": config_path,
                }

                self.model_info[model_key] = {
                    "display_name": model_dict.get("display_name", model_name),
                    "config_path": config_path,
                }

        except Exception as _:
            local_model_data = {}

        # Then, load from model_manager (config file data) - only non-custom models
        # Custom models are only loaded from models.json to allow proper clearing
        model_list = self.model_manager.get_model_configs()
        for model_dict in model_list:
            model_name = model_dict.get("name")
            
            # Skip custom models - they are only loaded from models.json
            if model_dict.get("is_custom_model", False):
                continue
            
            provider_name = model_dict.get("provider", "Others")

            if not model_name:
                continue

            if provider_name not in model_data:
                model_data[provider_name] = {}

            # For non-custom models, check local_model_data for favorites etc.
            if (
                provider_name in local_model_data
                and model_name in local_model_data[provider_name]
            ):
                local_model_data[provider_name][model_name]["selected"] = False
                model_data[provider_name].update(
                    local_model_data[provider_name]
                )
            else:
                model_data[provider_name][model_name] = {
                    "selected": False,
                    "favorite": False,
                    "display_name": model_dict.get("display_name", model_name),
                    "config_path": model_dict.get("config_file"),
                }

            self.model_info[model_name] = {
                "display_name": model_dict.get("display_name", model_name),
                "config_path": (
                    None
                    if model_name == "load_custom_model"
                    else model_dict.get("config_file")
                ),
            }

        # Sort the collected model_data
        sorted_model_data = self._sort_model_data(model_data)

        return sorted_model_data

    def _sort_model_data(self, model_data: dict) -> collections.OrderedDict:
        """Sorts the model data dictionary"""

        def top_level_sort_key(key: str):
            if key == "Custom":
                return (0,)
            if key == "Others":
                return (2,)
            return (1, key)

        def inner_sort_key(item: tuple[str, dict]):
            _, model_details = item
            display_name = model_details.get("display_name", "")
            if display_name == "...Load Custom Model":
                return (0,)
            return (1, display_name)

        sorted_top_keys = sorted(model_data.keys(), key=top_level_sort_key)
        sorted_data = collections.OrderedDict()
        for key in sorted_top_keys:
            inner_dict = model_data[key]
            sorted_inner_items = sorted(inner_dict.items(), key=inner_sort_key)
            sorted_data[key] = collections.OrderedDict(sorted_inner_items)
        return sorted_data

    def show_model_dropdown(self):
        """Show the model dropdown"""
        button_pos = self.model_selection_button.mapToGlobal(QPoint(0, 0))
        self.model_dropdown.move(int(button_pos.x()), int(button_pos.y()))
        self.model_dropdown.adjustSize()
        self.model_dropdown.show()

    def on_model_selected(self, provider, model_name):
        """Handle the model selected event"""

        if model_name == "load_custom_model":
            # Unload current model first
            self.model_manager.unload_model()

            # Open file dialog to select "config.yaml" file for model
            file_dialog = QFileDialog(self)
            file_dialog.setFileMode(QFileDialog.ExistingFile)
            file_dialog.setNameFilter("Config file (*.yaml)")

            if file_dialog.exec_():
                self.hide_labeling_widgets()
                config_file = file_dialog.selectedFiles()[0]
                flag = self.model_manager.load_custom_model(config_file)
                if not flag:
                    self.model_selection_button.setText("No Model")
                    return

                # update model_info
                with open(config_file, "r", encoding="utf-8") as f:
                    config_info = yaml.safe_load(f)

                # Use config_file path hash as unique identifier to avoid name conflicts
                import hashlib
                config_file_normalized = os.path.normpath(os.path.abspath(config_file))
                unique_id = hashlib.md5(config_file_normalized.encode()).hexdigest()[:8]
                model_key = f"_custom_{unique_id}_{config_info.get('display_name', 'model')}"

                self.model_info[model_key] = {
                    "display_name": config_info["display_name"],
                    "config_path": config_file,
                }

                # update model_data
                models_data = self.init_model_data()
                models_data["Custom"]["load_custom_model"]["selected"] = False
                
                # Remove any existing entry with the same config_path to avoid duplicates
                for key in list(models_data["Custom"].keys()):
                    if key != "load_custom_model":
                        existing_path = models_data["Custom"][key].get("config_path", "")
                        if os.path.normpath(existing_path) == config_file_normalized:
                            del models_data["Custom"][key]
                
                models_data["Custom"][model_key] = {
                    "selected": True,
                    "favorite": False,
                    "display_name": config_info["display_name"],
                    "config_path": config_file,
                }
                # Update dropdown and save through its method to ensure consistency
                self.model_dropdown.update_models_data(models_data)
                self.model_dropdown.save_models_data()

                self.clear_auto_labeling_action_requested.emit()
                self.model_selection_button.setText(
                    config_info["display_name"]
                )
                self.model_selection_button.setEnabled(False)

            return

        self.clear_auto_labeling_action_requested.emit()
        self.model_selection_button.setText(
            self.model_info[model_name]["display_name"]
        )

        self.model_selection_button.setEnabled(False)
        self.hide_labeling_widgets()

        if provider == "Custom":
            self.model_manager.load_custom_model(
                self.model_info[model_name]["config_path"]
            )
        else:
            self.new_model_selected.emit(
                self.model_info[model_name]["config_path"]
            )

    def populate_upn_combobox(self):
        """Populate UPN combobox with available modes"""
        self.upn_select_combobox.clear()
        # Define modes with display names
        modes = {
            "coarse_grained_prompt": self.tr("Coarse Grained"),
            "fine_grained_prompt": self.tr("Fine Grained"),
        }
        # Add modes to combobox
        for mode, display_name in modes.items():
            self.upn_select_combobox.addItem(display_name, userData=mode)

    def populate_gd_combobox(self):
        """Populate GroundingDino combobox with available modes"""
        self.gd_select_combobox.clear()
        # Define modes with display names
        modes = {
            "GroundingDino_1_6_Pro": "GroundingDino-1.6-Pro",
            "GroundingDino_1_6_Edge": "GroundingDino-1.6-Edge",
            "GroundingDino_1_5_Pro": "GroundingDino-1.5-Pro",
            "GroundingDino_1_5_Edge": "GroundingDino-1.5-Edge",
        }
        # Add modes to combobox
        for mode, display_name in modes.items():
            self.gd_select_combobox.addItem(display_name, userData=mode)

    def populate_florence2_combobox(self):
        """Populate Florence2 combobox with available modes"""
        self.florence2_select_combobox.clear()
        # Define modes with display names
        modes = {
            "caption": self.tr("Caption"),
            "detailed_cap": self.tr("Detailed Caption"),
            "more_detailed_cap": self.tr("More Detailed Caption"),
            "od": self.tr("Object Detection"),
            "region_proposal": self.tr("Region Proposal"),
            "dense_region_cap": self.tr("Dense Region Caption"),
            "refer_exp_seg": self.tr("Refer-Exp Segmentation"),
            "region_to_seg": self.tr("Region to Segmentation"),
            "ovd": self.tr("OVD"),
            "cap_to_pg": self.tr("Caption to Parse Grounding"),
            "region_to_cat": self.tr("Region to Category"),
            "region_to_desc": self.tr("Region to Description"),
            "ocr": self.tr("OCR"),
            "ocr_with_region": self.tr("OCR with Region"),
        }
        # Add modes to combobox
        for mode, display_name in modes.items():
            self.florence2_select_combobox.addItem(display_name, userData=mode)

    @pyqtSlot()
    def update_button_colors(self):
        """Update button colors"""
        for button in [
            self.button_add_point,
            self.button_remove_point,
            self.button_add_rect,
            self.button_clear,
            self.button_finish_object,
        ]:
            button.setStyleSheet(get_normal_button_style())
        if self.auto_labeling_mode == AutoLabelingMode.NONE:
            return
        if self.auto_labeling_mode.edit_mode == AutoLabelingMode.ADD:
            if self.auto_labeling_mode.shape_type == AutoLabelingMode.POINT:
                self.button_add_point.setStyleSheet(
                    get_toggle_button_style(button_color="#90EE90")
                )
            elif (
                self.auto_labeling_mode.shape_type
                == AutoLabelingMode.RECTANGLE
            ):
                self.button_add_rect.setStyleSheet(
                    get_toggle_button_style(button_color="#90EE90")
                )
        elif self.auto_labeling_mode.edit_mode == AutoLabelingMode.REMOVE:
            if self.auto_labeling_mode.shape_type == AutoLabelingMode.POINT:
                self.button_remove_point.setStyleSheet(
                    get_toggle_button_style(button_color="#FFB6C1")
                )

    def set_auto_labeling_mode(self, edit_mode, shape_type=None):
        """Set auto labeling mode"""
        if edit_mode is None:
            self.auto_labeling_mode = AutoLabelingMode.NONE
        else:
            self.auto_labeling_mode = AutoLabelingMode(edit_mode, shape_type)
        self.auto_labeling_mode_changed.emit(self.auto_labeling_mode)

    def run_prediction(self):
        """Run prediction"""
        if self.parent.filename is not None:
            self.model_manager.predict_shapes_threading(
                self.parent.image, self.parent.filename
            )

    def run_vl_prediction(self):
        """Run visual-language prediction"""
        if self.parent.filename is not None and self.edit_text:
            self.model_manager.predict_shapes_threading(
                self.parent.image,
                self.parent.filename,
                text_prompt=self.edit_text.text(),
            )

    def run_recognition_on_selected(self):
        """只对画布上选中的框进行 OCR 识别（跳过全图检测）"""
        if self.parent.filename is None:
            return

        # 获取画布上选中的形状
        selected = self.parent.canvas.selected_shapes
        if not selected:
            self.model_manager.new_model_status.emit(
                self.tr("请先选中要识别的检测框")
            )
            return

        # 检查模型是否支持框识别
        model = self.model_manager.loaded_model_config.get("model")
        if not hasattr(model, "predict_shapes_from_boxes"):
            self.model_manager.new_model_status.emit(
                self.tr("当前模型不支持选中框识别")
            )
            return

        # 提取框坐标，记住对应的 shape 对象
        box_infos = []  # [(shape, [pts])]
        for shape in selected:
            pts = [[int(p.x()), int(p.y())] for p in shape.points]
            box_infos.append((shape, pts))

        if not box_infos:
            return

        self.model_manager.new_model_status.emit(
            self.tr("正在识别选中框...")
        )
        # 不触发 prediction_started，避免加载遮罩遮盖画布

        def _do_ocr():
            import time
            t0 = time.time()
            boxes = [bi[1] for bi in box_infos]
            result, timing = model.predict_shapes_from_boxes(
                self.parent.image, boxes, self.parent.filename
            )
            timing_str = f"[框识别耗时] 读图={timing.get('读图',0):.3f}s  裁剪+识别={timing.get('裁剪+识别',0):.3f}s  总={timing.get('总',0):.3f}s" if timing else f"耗时={time.time()-t0:.3f}s"
            # 打印：选中OCR，带完整坐标和置信度
            fname = os.path.basename(self.parent.filename) if self.parent.filename else "image"
            label = box_infos[0][0].label if box_infos else ""
            out = []
            for i, (shape, _) in enumerate(box_infos):
                if i < len(result.shapes):
                    text = result.shapes[i].description
                    score = result.shapes[i].score
                    out.append([boxes[i], (text, score)])
                    shape.description = text
                    shape.score = score
            print(f"\n[选中OCR] 标签:{label}  {fname} → {timing_str}")
            print(out)
            sys.stdout.flush()
            # 触发画布和标签列表重绘
            self.parent.canvas.update()
            self.parent.label_list.viewport().update()
            # 通过信号把描述文本传回主线程更新 UI
            desc = ""
            if box_infos and len(result.shapes) > 0:
                desc = result.shapes[0].description or ""
            self.recog_selected_finished.emit(desc)
            self.model_manager.new_model_status.emit(
                self.tr("选中框识别完成。查看结果。")
            )

        # 主线程异步执行，避免跨线程 CUDA 上下文切换开销
        QTimer.singleShot(0, _do_ocr)

    def run_recognition_on_all(self):
        """对全图已有的所有框执行 OCR 识别（不运行检测器）"""
        if self.parent.filename is None:
            return

        model = self.model_manager.loaded_model_config.get("model")
        if not hasattr(model, "predict_shapes_from_boxes"):
            self.model_manager.new_model_status.emit(
                self.tr("当前模型不支持框识别")
            )
            return

        # 获取画布上所有框
        all_shapes = list(self.parent.canvas.shapes)
        if not all_shapes:
            self.model_manager.new_model_status.emit(
                self.tr("画布上没有检测框")
            )
            return

        # 读取过滤标签设置（标签名列表）
        filter_classes = self.model_manager.loaded_model_config.get(
            "filter_classes", None
        )

        # 根据过滤标签筛选框
        box_infos = []
        for shape in all_shapes:
            if filter_classes is not None and shape.label not in filter_classes:
                continue
            pts = [[int(p.x()), int(p.y())] for p in shape.points]
            box_infos.append((shape, pts))

        if not box_infos:
            self.model_manager.new_model_status.emit(
                self.tr("没有符合条件的框（已被标签过滤）")
            )
            return

        self.model_manager.new_model_status.emit(
            self.tr(f"正在识别 {len(box_infos)} 个框...")
        )

        def _do_ocr():
            import time
            t0 = time.time()
            boxes = [bi[1] for bi in box_infos]
            result, timing = model.predict_shapes_from_boxes(
                self.parent.image, boxes, self.parent.filename
            )
            timing_str = f"[框识别耗时] 读图={timing.get('读图',0):.3f}s  裁剪+识别={timing.get('裁剪+识别',0):.3f}s  总={timing.get('总',0):.3f}s" if timing else f"耗时={time.time()-t0:.3f}s"
            # 按标签分组，保留完整坐标和置信度，并添加序号
            from collections import defaultdict
            grouped = defaultdict(list)
            for i, (shape, _) in enumerate(box_infos):
                if i < len(result.shapes):
                    text = result.shapes[i].description
                    score = result.shapes[i].score
                    shape.description = text
                    shape.score = score
                    grouped[shape.label].append([boxes[i], (text, score)])

            fname = os.path.basename(self.parent.filename) if self.parent.filename else "image"
            print(f"\n[全图框OCR] {fname}  共{len(box_infos)}个框 → {timing_str}")
            for label, items in sorted(grouped.items()):
                print(f"标签:{label}  ({len(items)}个)")
                for idx, item in enumerate(items, 1):
                    print(f"标签:{label}({idx})")
                    print(f"{item}")
            sys.stdout.flush()

            self.parent.canvas.update()
            self.parent.label_list.viewport().update()
            self.model_manager.new_model_status.emit(
                self.tr(f"全图框识别完成。共处理 {len(box_infos)} 个框。")
            )

        QTimer.singleShot(0, _do_ocr)

    def _on_recog_selected_finished(self, description):
        """主线程回调：更新右侧文本描述"""
        try:
            self.parent.shape_text_edit.textChanged.disconnect()
        except Exception:
            pass
        self.parent.shape_text_edit.setPlainText(description)
        self.parent.shape_text_edit.textChanged.connect(
            self.parent.shape_text_changed
        )

    def unload_and_hide(self):
        """Unload model and hide widget"""
        self.hide()

    def on_new_model_status(self, status):
        self.model_status_label.setText(status)

    def on_new_model_loaded(self, model_config):
        """Enable model select combobox"""
        self.model_selection_button.setEnabled(True)

        # Reset controls to initial values when the model changes
        try:
            if (
                self.model_manager.loaded_model_config["type"]
                in _AUTO_LABELING_IOU_MODELS
            ):
                initial_iou_value = self.model_manager.loaded_model_config[
                    "iou_threshold"
                ]
                self.edit_iou.setValue(initial_iou_value)
            else:
                initial_iou_value = 0.0
                self.edit_iou.setValue(initial_iou_value)
        except Exception as _:
            initial_iou_value = 0.0
            self.edit_iou.setValue(initial_iou_value)

        try:
            if (
                self.model_manager.loaded_model_config["type"]
                in _AUTO_LABELING_CONF_MODELS
            ):
                initial_conf_value = self.model_manager.loaded_model_config[
                    "conf_threshold"
                ]
                self.edit_conf.setValue(initial_conf_value)
            else:
                initial_conf_value = 0.0
                self.edit_conf.setValue(initial_conf_value)
        except Exception as _:
            initial_conf_value = 0.0
            self.edit_conf.setValue(initial_conf_value)

        self.on_reset_tracker()
        self.on_iou_value_changed(initial_iou_value)
        self.on_conf_value_changed(initial_conf_value)
        self.on_preserve_existing_annotations_state_changed(
            self.initial_preserve_annotations_state
        )
        self.on_rotation_state_changed(
            self.initial_rotation_state
        )
        self.on_filter_non_rotated_state_changed(
            self.initial_filter_non_rotated_state
        )

        # Update specific mode in UI if specific model is loaded
        if model_config.get("type") == "upn":
            self.update_upn_mode_ui()
        elif model_config.get("type") == "florence2":
            self.update_florence2_mode_ui()
        elif model_config.get("type") == "groundingdino":
            self.update_groundingdino_mode_ui()

    def update_upn_mode_ui(self):
        """Update UPN mode combobox to reflect current backend state"""
        current_mode = self.model_manager.loaded_model_config[
            "model"
        ].prompt_type
        index = self.upn_select_combobox.findData(current_mode)
        if index != -1:
            self.upn_select_combobox.setCurrentIndex(index)

    def update_groundingdino_mode_ui(self):
        """Update GroundingDino mode combobox to reflect current backend state"""
        current_mode = self.model_manager.loaded_model_config[
            "model"
        ].prompt_type
        index = self.gd_select_combobox.findData(current_mode)
        if index != -1:
            self.gd_select_combobox.setCurrentIndex(index)

    def update_florence2_mode_ui(self):
        """Update Florence2 mode combobox to reflect current backend state"""
        current_mode = self.model_manager.loaded_model_config[
            "model"
        ].prompt_type
        index = self.florence2_select_combobox.findData(current_mode)
        if index != -1:
            self.florence2_select_combobox.setCurrentIndex(index)
        self.update_florence2_widgets(current_mode)

    def on_output_modes_changed(self, output_modes, default_output_mode):
        """Handle output modes changed"""
        # Disconnect onIndexChanged signal to prevent triggering
        # on model select combobox change
        self.output_select_combobox.currentIndexChanged.disconnect()

        self.output_select_combobox.clear()
        for output_mode, display_name in output_modes.items():
            self.output_select_combobox.addItem(
                display_name, userData=output_mode
            )
        self.output_select_combobox.setCurrentIndex(
            self.output_select_combobox.findData(default_output_mode)
        )

        # Reconnect onIndexChanged signal
        self.output_select_combobox.currentIndexChanged.connect(
            lambda: self.model_manager.set_output_mode(
                self.output_select_combobox.currentData()
            )
        )

    def update_visible_widgets(self, model_config):
        """Update widget status"""
        if not model_config or "model" not in model_config:
            return
        widgets = model_config["model"].get_required_widgets()
        for widget_name in widgets:
            if hasattr(self, widget_name):
                getattr(self, widget_name).show()
            else:
                logger.warning(
                    f"Warning: Widget '{widget_name}' not found in AutoLabelingWidget."
                )

    def hide_labeling_widgets(self):
        """Hide labeling widgets by default"""
        widgets = [
            "button_run",
            "button_recog_selected",
            "button_recog_all",
            "button_add_point",
            "button_remove_point",
            "button_add_rect",
            "button_clear",
            "button_finish_object",
            "button_send",
            "edit_text",
            "edit_conf",
            "edit_iou",
            "input_box_thres",
            "input_conf",
            "input_iou",
            "output_label",
            "output_select_combobox",
            "toggle_end2end",
            "toggle_preserve_existing_annotations",
            "button_set_api_token",
            "button_reset_tracker",
            "button_filter_classes",
            "toggle_use_existing_boxes",
            "button_detect_only",
            "toggle_rotation",
            "toggle_filter_non_rotated",
            "upn_select_combobox",
            "gd_select_combobox",
            "florence2_select_combobox",
            "button_auto_decode",
        ]
        for widget in widgets:
            getattr(self, widget).hide()

    def on_new_marks(self, marks):
        """Handle new marks"""
        self.model_manager.set_auto_labeling_marks(marks)
        current_model_name = self.model_manager.loaded_model_config["type"]
        if current_model_name not in _SKIP_PREDICTION_ON_NEW_MARKS_MODELS:
            self.run_prediction()

    def on_open(self):
        pass

    def on_close(self):
        return True

    def on_conf_value_changed(self, value):
        """Handle conf value changed"""
        self.model_manager.set_auto_labeling_conf(value)

    def on_iou_value_changed(self, value):
        """Handle iou value changed"""
        self.model_manager.set_auto_labeling_iou(value)

    def on_preserve_existing_annotations_state_changed(self, state):
        """Handle preserve existing annotations state changed"""
        self.initial_preserve_annotations_state = state
        self.model_manager.set_auto_labeling_preserve_existing_annotations_state(
            state
        )

    def on_rotation_state_changed(self, state):
        """Handle rotation state changed"""
        self.initial_rotation_state = state
        self.model_manager.set_auto_labeling_rotation_state(state)
        self._update_rotation_button_state(
            state, self._rotation_tooltip_on, self._rotation_tooltip_off
        )

    def _on_toggle_use_existing_boxes(self, checked):
        """切换OCR模式：检测+OCR / 使用已有框OCR"""
        if checked:
            self.toggle_use_existing_boxes.setText(self.tr("已有框OCR"))
            self.toggle_use_existing_boxes.setStyleSheet(
                self._get_replace_button_style("#5cb85c", "#4cae4c")
            )
        else:
            self.toggle_use_existing_boxes.setText(self.tr("检测+OCR"))
            self.toggle_use_existing_boxes.setStyleSheet(
                self._get_replace_button_style("#d9534f", "#c9302c")
            )

    def run_detect_only(self):
        """仅检测按钮：只跑检测器画框，不做 OCR"""
        if self.parent.filename is None:
            return

        model = self.model_manager.loaded_model_config.get("model")
        if not model or not hasattr(model, "predict_shapes_detect_only"):
            self.model_manager.new_model_status.emit(
                self.tr("当前模型不支持仅检测")
            )
            return

        def _do():
            result = model.predict_shapes_detect_only(
                self.parent.image, self.parent.filename
            )
            self.model_manager.new_auto_labeling_result.emit(result)

        QTimer.singleShot(0, _do)

    def on_end2end_state_changed(self, state):
        """Handle end2end mode state changed"""
        self.model_manager.set_auto_labeling_end2end_state(state)
        # Update IoU controls based on end2end state
        self.input_iou.setEnabled(not state)
        self.edit_iou.setEnabled(not state)

    def _get_replace_button_style(self, bg_color, hover_color):
        """生成标签覆盖按钮的样式，保持和其他按钮一样的尺寸"""
        return f"""
            QPushButton {{
                height: 24px;
                min-width: 80px;
                padding: 5px 8px;
                border-radius: 8px;
                background-color: {bg_color};
                color: white;
                border: 1px solid #d2d2d7;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {hover_color};
            }}
        """

    def _get_end2end_button_style(self, bg_color, hover_color):
        """生成 End2End 按钮的样式"""
        return f"""
            QPushButton {{
                height: 24px;
                min-width: 80px;
                padding: 5px 8px;
                border-radius: 8px;
                background-color: {bg_color};
                color: white;
                border: 1px solid #d2d2d7;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {hover_color};
            }}
        """

    def _update_replace_button_state(self, checked, tooltip_on, tooltip_off):
        """更新标签覆盖按钮的状态和颜色"""
        self.toggle_preserve_existing_annotations.setToolTip(
            tooltip_on if checked else tooltip_off
        )
        # 去掉括号，直接用"标签覆盖关闭"和"标签覆盖开启"
        self.toggle_preserve_existing_annotations.setText(
            self.tr("标签覆盖关闭") if checked else self.tr("标签覆盖开启")
        )
        # 关闭时绿色，开启时红色
        if checked:
            # 关闭 - 绿色，表示安全，不会覆盖
            self.toggle_preserve_existing_annotations.setStyleSheet(
                self._get_replace_button_style("#5cb85c", "#4cae4c")
            )
        else:
            # 开启 - 红色，表示危险，会覆盖
            self.toggle_preserve_existing_annotations.setStyleSheet(
                self._get_replace_button_style("#d9534f", "#c9302c")
            )

    def _update_rotation_button_state(self, checked, tooltip_on, tooltip_off):
        """更新旋转按钮的状态"""
        self.toggle_rotation.setToolTip(
            tooltip_on if checked else tooltip_off
        )
        self.toggle_rotation.setText(
            self.tr("旋转开") if checked else self.tr("旋转关")
        )
        if checked:
            self.toggle_rotation.setStyleSheet(
                self._get_replace_button_style("#5cb85c", "#4cae4c")
            )
        else:
            self.toggle_rotation.setStyleSheet(
                self._get_replace_button_style("#5bc0de", "#46b8da")
            )
        self.toggle_filter_non_rotated.setVisible(checked)

    def _update_filter_non_rotated_button_state(self, checked):
        """更新过滤非旋转按钮的状态"""
        self.toggle_filter_non_rotated.setText(
            self.tr("过滤水平框开") if checked else self.tr("过滤水平框关")
        )
        if checked:
            self.toggle_filter_non_rotated.setStyleSheet(
                self._get_replace_button_style("#5cb85c", "#4cae4c")
            )
        else:
            self.toggle_filter_non_rotated.setStyleSheet(
                self._get_replace_button_style("#8e44ad", "#7d3c98")
            )

    def on_filter_non_rotated_state_changed(self, state):
        """Handle filter non-rotated state changed"""
        self.initial_filter_non_rotated_state = state
        self.model_manager.set_auto_labeling_filter_non_rotated(state)

    def _update_end2end_button_state(self, checked, tooltip_on, tooltip_off):
        """更新 End2End 按钮的状态和颜色"""
        self.toggle_end2end.setToolTip(
            tooltip_on if checked else tooltip_off
        )
        # checked=True 表示 End2End 开启（NMS 关闭）
        # checked=False 表示 End2End 关闭（NMS 开启）
        self.toggle_end2end.setText(
            self.tr("NMS (关)") if checked else self.tr("NMS (开)")
        )
        if checked:
            # End2End 开启（NMS 关闭）- 灰色
            self.toggle_end2end.setStyleSheet(
                self._get_end2end_button_style("#777777", "#666666")
            )
            # 禁用 IoU 控件
            self.input_iou.setEnabled(False)
            self.edit_iou.setEnabled(False)
        else:
            # End2End 关闭（NMS 开启）- 蓝色
            self.toggle_end2end.setStyleSheet(
                self._get_end2end_button_style("#5bc0de", "#46b8da")
            )
            # 启用 IoU 控件
            self.input_iou.setEnabled(True)
            self.edit_iou.setEnabled(True)

    def on_reset_tracker(self):
        """Handle reset tracker"""
        self.model_manager.set_auto_labeling_reset_tracker()

    def on_set_api_token(self):
        """Show a dialog to input the API token."""
        dialog = ApiTokenDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            token = dialog.get_token()
            try:
                self.model_manager.set_auto_labeling_api_token(token)
            except Exception as e:
                logger.error(f"Error setting API token: {e}")

    def on_filter_classes_clicked(self):
        """Handle filter classes button click - show dialog to configure filter classes"""
        if not self.model_manager.loaded_model_config:
            logger.warning("No model loaded. Please load a model first.")
            return

        # 从右侧标签列表获取所有类别（而不是从模型配置文件读取）
        unique_label_list = self.parent.unique_label_list
        all_classes = []
        for row in range(unique_label_list.count()):
            item = unique_label_list.item(row)
            label_text = item.data(Qt.UserRole)  # 获取标签名称
            if label_text and label_text not in all_classes:
                all_classes.append(label_text)

        # 添加从YAML导入的额外标签
        for label in self.extra_labels_from_yaml:
            if label not in all_classes:
                all_classes.append(label)

        if not all_classes:
            logger.warning("No labels found in the label list. Please add some labels first.")
            return

        # 不读取持久化的过滤配置，每次打开都默认全选（显示所有标签）
        # 只使用当前会话的过滤设置（如果有的话）
        model_config = self.model_manager.loaded_model_config
        current_filter_classes = model_config.get("filter_classes", []) if hasattr(self, '_session_filter_applied') else []

        # 创建非模态对话框，允许同时操作主界面
        # OCR 模式下用 OCR 说明文字，检测模式下用检测说明文字
        model_type = self.model_manager.loaded_model_config.get("type", "")
        if "ppocr" in model_type:
            info_text = self.tr(
                "勾选要执行 OCR 的标签：\n"
                "未勾选的标签将被跳过，不会进行 OCR 识别"
            )
        else:
            info_text = self.tr(
                "勾选要从检测结果中显示的标签：\n"
                "未勾选的标签将被过滤掉，不会在检测结果中显示"
            )
        dialog = FilterClassesDialog(
            all_classes=all_classes,
            current_filter_classes=current_filter_classes,
            extra_labels_from_yaml=self.extra_labels_from_yaml,
            on_yaml_import=self.on_yaml_labels_imported,
            on_apply=self.apply_filter_classes,
            info_text=info_text,
            parent=self
        )

        # 使用 show() 而不是 exec_()，实现非模态显示
        dialog.show()

    def apply_filter_classes(self, selected_classes):
        """应用过滤类别设置"""
        model_config = self.model_manager.loaded_model_config
        if not model_config:
            return

        # 更新模型配置（仅内存中）
        model_config["filter_classes"] = selected_classes
        self._session_filter_applied = True  # 标记本次会话已设置过滤

        # 更新模型的过滤类别设置
        if model_config.get("model"):
            # 获取模型原始的所有类别
            model_classes = _normalize_classes(model_config.get("classes", []))
            # 将类别名称转换为索引
            # 注意：selected_classes 为空列表时应该返回空列表（不显示任何标签）
            # 只有在 selected_classes 为 None 时才返回 None（显示所有标签）
            if selected_classes is not None:
                filter_indices = [
                    i for i, cls in enumerate(model_classes)
                    if cls in selected_classes
                ]
            else:
                filter_indices = None
            model_config["model"].filter_classes = filter_indices

        # 不再保存配置到 YAML 文件，只在当前会话生效

        logger.info(f"Filter classes updated (session only): {selected_classes}")

    def on_yaml_labels_imported(self, new_labels):
        """
        当从YAML导入新标签时的回调函数

        Args:
            new_labels: 新导入的标签列表
        """
        for label in new_labels:
            if label not in self.extra_labels_from_yaml:
                self.extra_labels_from_yaml.append(label)
        logger.info(f"Imported labels from YAML: {new_labels}")

    def on_cache_auto_label_changed(self, text, gid):
        self.model_manager.set_cache_auto_label(text, gid)

    def add_new_prompt(self):
        self.model_manager.set_auto_labeling_prompt()

    @pyqtSlot()
    def on_upn_mode_changed(self):
        """Handle UPN mode change"""
        mode = self.upn_select_combobox.currentData()
        self.model_manager.set_upn_mode(mode)

    @pyqtSlot()
    def on_gd_mode_changed(self):
        """Handle GroundingDino mode change"""
        mode = self.gd_select_combobox.currentData()
        self.model_manager.set_groundingdino_mode(mode)

    @pyqtSlot()
    def on_florence2_mode_changed(self):
        """Handle Florence2 mode change"""
        mode = self.florence2_select_combobox.currentData()
        self.model_manager.set_florence2_mode(mode)
        self.update_florence2_widgets(mode)

    def update_florence2_widgets(self, mode):
        """Update widget visibility based on Florence2 mode"""
        # Check if Florence2 model is loaded
        if (
            not self.model_manager.loaded_model_config
            or self.model_manager.loaded_model_config.get("type")
            != "florence2"
        ):
            return

        # Define which widgets are needed for each mode
        mode_widgets = {
            # Only need run button
            "caption": ["button_run"],
            "detailed_cap": ["button_run"],
            "more_detailed_cap": ["button_run"],
            "ocr": ["button_run", "button_recog_selected", "button_recog_all", "button_filter_classes", "toggle_use_existing_boxes", "button_detect_only"],
            "ocr_with_region": ["button_run"],
            "od": ["button_run"],
            "region_proposal": ["button_run"],
            "dense_region_cap": ["button_run"],
            # Region-based modes need rectangle tools
            "region_to_cat": [
                "button_add_rect",
                "button_clear",
                "button_finish_object",
            ],
            "region_to_desc": [
                "button_add_rect",
                "button_clear",
                "button_finish_object",
            ],
            "region_to_seg": [
                "button_add_rect",
                "button_clear",
                "button_finish_object",
            ],
            # Other modes
            "refer_exp_seg": ["edit_text", "button_send"],
            "cap_to_pg": ["edit_text", "button_send"],
            "ovd": ["edit_text", "button_send"],
        }

        # Define which modes should preserve existing annotations by default
        preserve_annotations_modes = {
            # Modes that should preserve existing annotations (replace=False)
            "region_to_cat": "Replace (Off)",
            "region_to_desc": "Replace (Off)",
            "region_to_seg": "Replace (Off)",
            "refer_exp_seg": "Replace (Off)",
            # Modes that should replace existing annotations (replace=True)
            "caption": "Replace (On)",
            "detailed_cap": "Replace (On)",
            "more_detailed_cap": "Replace (On)",
            "od": "Replace (On)",
            "region_proposal": "Replace (On)",
            "dense_region_cap": "Replace (On)",
            "ovd": "Replace (On)",
            "cap_to_pg": "Replace (On)",
            "ocr": "Replace (On)",
            "ocr_with_region": "Replace (On)",
        }

        # Hide all widgets first
        widgets_to_manage = [
            "edit_text",
            "button_run",
            "button_recog_selected",
            "button_recog_all",
            "button_filter_classes",
            "button_send",
            "button_add_rect",
            "button_clear",
            "button_finish_object",
        ]

        for widget_name in widgets_to_manage:
            getattr(self, widget_name).hide()

        if mode in ["ovd", "cap_to_pg", "refer_exp_seg"]:
            self.edit_text.setPlaceholderText("Enter prompt here...")

        # Show only the widgets needed for current mode
        if mode in mode_widgets:
            for widget_name in mode_widgets[mode]:
                getattr(self, widget_name).show()

            # Show preserve annotations toggle for all modes
            self.toggle_preserve_existing_annotations.show()
            # Set the default state for preserve annotations
            if mode in preserve_annotations_modes:
                # Temporarily disconnect the signal to avoid triggering the callback
                self.toggle_preserve_existing_annotations.toggled.disconnect()
                # Set the state
                self.toggle_preserve_existing_annotations.setText(
                    preserve_annotations_modes[mode]
                )
                # Reconnect the signal
                self.toggle_preserve_existing_annotations.toggled.connect(
                    self.on_preserve_existing_annotations_state_changed
                )
                # Manually trigger the state change to update the model
                self.on_preserve_existing_annotations_state_changed(
                    preserve_annotations_modes[mode]
                )

    def on_auto_decode_toggled(self):
        """Handle AMD button toggle"""
        is_checked = self.button_auto_decode.isChecked()
        self.button_auto_decode.setText(
            "AMD (On)" if is_checked else "AMD (Off)"
        )

        if is_checked:
            self.button_auto_decode.setStyleSheet(
                get_toggle_button_style(button_color="#87CEEB")
            )
        else:
            self.button_auto_decode.setStyleSheet(get_normal_button_style())

        self.auto_decode_mode_changed.emit(is_checked)

    def on_clear_clicked(self):
        """Handle clear button click"""
        self.clear_auto_decode_requested.emit()
        self.clear_auto_labeling_action_requested.emit()

    def on_finish_clicked(self):
        """Handle finish button click"""
        self.clear_auto_decode_requested.emit()
        self.add_new_prompt()
        self.finish_auto_labeling_object_action_requested.emit()
        self.cache_auto_label_changed.emit()
