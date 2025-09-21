
import yaml
import os

def update_labeling_config(mode: str):
    """
    Updates the xanylabeling_config.yaml file to switch between single and dual color labeling modes.
    :param mode: 'single' for single color mode, 'double' for dual color mode.
    """
    config_file_path = os.path.join(os.path.dirname(__file__), 'configs', 'xanylabeling_config.yaml')
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(config_file_path), exist_ok=True)

    config = {}
    if os.path.exists(config_file_path):
        with open(config_file_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file) or {} # Handle empty file case

    if mode == 'single':
        config['double_click_to_edit_label'] = False
        config['label_color_mode'] = 'single'
        config['label_color_map'] = None
    elif mode == 'double':
        config['double_click_to_edit_label'] = True
        config['label_color_mode'] = 'double'
        config['label_color_map'] = {
            'label_1': [255, 0, 0, 128],  # Red with 50% opacity
            'label_2': [0, 0, 255, 128]   # Blue with 50% opacity
        }
    else:
        print(f"Unknown labeling mode: {mode}")
        return

    with open(config_file_path, 'w', encoding='utf-8') as file:
        yaml.safe_dump(config, file, default_flow_style=False, allow_unicode=True)
    print(f"Configuration updated to {mode} mode: {config_file_path}")
