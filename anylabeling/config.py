import os.path as osp
import shutil
import yaml
import importlib.resources as pkg_resources

from anylabeling import configs as anylabeling_configs
from anylabeling.views.labeling.logger import logger


current_config_file = None


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
    user_config_file = osp.join(osp.expanduser("~"), ".YSGxanylabelingrc")
    try:
        # Preserve existing non-null user values when saving
        existing = {}
        if osp.exists(user_config_file):
            try:
                with open(user_config_file, "r", encoding="utf-8") as f:
                    existing = yaml.safe_load(f) or {}
            except Exception:  # noqa
                existing = {}
        merged = _merge_prefer_non_null(existing, config)
        with open(user_config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(merged, f, allow_unicode=True)
    except Exception:  # noqa
        logger.warning(f"Failed to save config: {user_config_file}")


def get_default_config():
    old_cfg_file = osp.join(osp.expanduser("~"), ".anylabelingrc")
    new_cfg_file = osp.join(osp.expanduser("~"), ".YSGxanylabelingrc")
    if osp.exists(old_cfg_file) and not osp.exists(new_cfg_file):
        shutil.copyfile(old_cfg_file, new_cfg_file)

    config_file = "xanylabeling_config.yaml"
    with pkg_resources.open_text(anylabeling_configs, config_file) as f:
        config = yaml.safe_load(f)

    # Save default config to ~/.YSGxanylabelingrc
    if not osp.exists(osp.join(osp.expanduser("~"), ".YSGxanylabelingrc")):
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
    user_config_file = osp.join(osp.expanduser("~"), ".YSGxanylabelingrc")
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
