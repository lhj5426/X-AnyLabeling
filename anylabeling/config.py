import os
import os.path as osp
import shutil
import yaml
import importlib.resources as pkg_resources

from anylabeling import configs as anylabeling_configs
from anylabeling.views.labeling.logger import logger


# Active configuration group. The main config file determines the directory
# containing the matching window and dock INI files.
current_config_file = None
DEFAULT_USER_CONFIG_FILE = osp.join(osp.dirname(osp.dirname(osp.abspath(__file__))), "xanylabeling_config.ini")
USER_CONFIG_FILE = DEFAULT_USER_CONFIG_FILE


def resolve_config_file(config_file):
    """Resolve a config file or config directory relative to the app folder."""
    if not config_file:
        return DEFAULT_USER_CONFIG_FILE

    candidate = osp.expanduser(str(config_file))
    if not osp.isabs(candidate):
        # Prefer a path relative to the copied project root.
        candidate = osp.join(_app_dir(), candidate)

    if osp.isdir(candidate):
        candidate = osp.join(candidate, "xanylabeling_config.ini")

    if osp.isfile(candidate):
        return osp.abspath(candidate)

    # Windows batch files can pass non-ASCII folder names with a mismatched
    # code page. If the requested relative name is unreadable, use the only
    # complete configuration group directly under the project root.
    if not osp.isabs(str(config_file)):
        groups = []
        for name in os.listdir(_app_dir()):
            group_dir = osp.join(_app_dir(), name)
            if not osp.isdir(group_dir):
                continue
            main_file = osp.join(group_dir, "xanylabeling_config.ini")
            window_file = osp.join(group_dir, "xanylabeling_window.ini")
            dock_file = osp.join(group_dir, "xanylabeling_dock.ini")
            if osp.isfile(main_file) and osp.isfile(window_file) and osp.isfile(dock_file):
                groups.append(main_file)
        if len(groups) == 1:
            return osp.abspath(groups[0])

    return osp.abspath(candidate)


def set_active_config_file(config_file):
    """Select the configuration group used by all three persisted config files."""
    global current_config_file, USER_CONFIG_FILE
    resolved = resolve_config_file(config_file)
    if resolved and osp.exists(resolved) and osp.isfile(resolved):
        current_config_file = osp.abspath(resolved)
        USER_CONFIG_FILE = current_config_file
    else:
        current_config_file = None
        USER_CONFIG_FILE = DEFAULT_USER_CONFIG_FILE
    return USER_CONFIG_FILE


def get_window_config_file():
    return osp.join(osp.dirname(USER_CONFIG_FILE), "xanylabeling_window.ini")


def get_dock_config_file():
    return osp.join(osp.dirname(USER_CONFIG_FILE), "xanylabeling_dock.ini")


def _app_dir():
    """软件根目录（便携免安装，配置写这里而不是C盘）"""
    return osp.dirname(osp.dirname(osp.abspath(__file__)))




def update_dict(target_dict, new_dict, validate_item=None):
    for key, value in new_dict.items():
        if validate_item:
            validate_item(key, value)
        if key in target_dict and isinstance(target_dict[key], dict) and isinstance(value, dict):
            update_dict(target_dict[key], value, validate_item=validate_item)
        else:
            target_dict[key] = value


def _merge_prefer_non_null(target: dict, source: dict) -> dict:
    """Merge dictionaries, preferring non-null values in source.

    - If a value in source is None, keep target's existing value.
    - If both sides are dict, merge recursively.
    - Otherwise, take source value.
    """
    if not isinstance(target, dict) or not isinstance(source, dict):
        return source if source is not None else target
    result = dict(target)
    for key, src_val in source.items():
        tgt_val = result.get(key)
        if isinstance(tgt_val, dict) and isinstance(src_val, dict):
            result[key] = _merge_prefer_non_null(tgt_val, src_val)
        else:
            result[key] = tgt_val if src_val is None else src_val
    return result


def save_config(config):
    user_config_file = USER_CONFIG_FILE
    try:
        # Preserve existing non-null user values when saving
        existing = {}
        if osp.exists(user_config_file):
            try:
                with open(user_config_file, "r", encoding="utf-8") as f:
                    existing = yaml.safe_load(f) or {}
            except Exception:  # noqa
                existing = {}
        
        # 保留文件中已有的merge_tool_settings
        existing_merge_settings = existing.get("merge_tool_settings")
        
        merged = _merge_prefer_non_null(existing, config)

        # Force overwrite for label_toggle_shortcuts to handle deletions properly
        if "label_toggle_shortcuts" in config:
            merged["label_toggle_shortcuts"] = config["label_toggle_shortcuts"]
        
        # Force overwrite for expand_margins_edge_mappings to handle deletions properly
        if "expand_margins_edge_mappings" in config:
            merged["expand_margins_edge_mappings"] = config["expand_margins_edge_mappings"]
        
        # Force overwrite for expand_margins_label_row_counts to handle row deletions properly
        if "expand_margins_label_row_counts" in config:
            merged["expand_margins_label_row_counts"] = config["expand_margins_label_row_counts"]
        
        # Force overwrite for expand_margins_values to handle value changes properly
        if "expand_margins_values" in config:
            merged["expand_margins_values"] = config["expand_margins_values"]
        
        # 始终保留文件中已有的merge_tool_settings
        # merge_dialog.py会直接写文件来保存这个设置
        if existing_merge_settings:
            merged["merge_tool_settings"] = existing_merge_settings
            
        with open(user_config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(merged, f, allow_unicode=True)
    except Exception:  # noqa
        logger.warning(f"Failed to save config: {user_config_file}")


def get_default_config():
    old_cfg_file = osp.join(osp.expanduser("~"), ".anylabelingrc")
    new_cfg_file = USER_CONFIG_FILE
    if osp.exists(old_cfg_file) and not osp.exists(new_cfg_file):
        shutil.copyfile(old_cfg_file, new_cfg_file)

    config_file = "xanylabeling_config.yaml"
    with pkg_resources.open_text(anylabeling_configs, config_file) as f:
        config = yaml.safe_load(f)

    # Save default config
    if not osp.exists(USER_CONFIG_FILE):
        save_config(config)

    # Add show_order to the default config
    if "show_order" not in config:
        config["show_order"] = True
    
    return config


def validate_config_item(key, value):
    if key == "validate_label" and value not in [None, "exact"]:
        raise ValueError(
            f"Unexpected value for config key 'validate_label': {value}"
        )
    if key == "shape_color" and value not in [None, "auto", "manual"]:
        raise ValueError(
            f"Unexpected value for config key 'shape_color': {value}"
        )
    if key == "labels" and value is not None and len(value) != len(set(value)):
        raise ValueError(
            f"Duplicates are detected for config key 'labels': {value}"
        )


def get_config(
    config_file_or_yaml=None, config_from_args=None, show_msg=False
):
    # 1. Load default configuration
    config = get_default_config()

    # 2. Load configuration from file or YAML string
    # This is for backward compatibility, and this will be overwritten
    # by user config file.
    if not config_file_or_yaml:
        config_file_or_yaml = current_config_file

    if config_file_or_yaml and osp.exists(config_file_or_yaml):
        if show_msg:
            logger.info(f"Loaded config file from: {config_file_or_yaml}")
        with open(config_file_or_yaml, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f)
        if user_config:
            update_dict(
                config, user_config, validate_item=validate_config_item
            )

    # 3. Load user's config file and merge it.
    user_config_file = USER_CONFIG_FILE
    # Do not load the global config if a custom config file was provided
    is_custom_config = (
        config_file_or_yaml and
        osp.exists(config_file_or_yaml) and
        osp.realpath(config_file_or_yaml) != osp.realpath(user_config_file)
    )
    if not is_custom_config and osp.exists(user_config_file):
        with open(user_config_file, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f)
        if user_config:
            update_dict(
                config, user_config, validate_item=validate_config_item
            )

    # 4. Update configuration with command line arguments
    if config_from_args:
        update_dict(
            config, config_from_args, validate_item=validate_config_item
        )
        if show_msg:
            logger.info(
                f"🔄 Updated config from CLI arguments: {config_from_args}"
            )

    # 5. Persist the merged configuration back to user's file, filling missing keys
    #    while preserving any existing user-specified values.
    try:
        save_config(config)
    except Exception:  # noqa
        pass

    return config
