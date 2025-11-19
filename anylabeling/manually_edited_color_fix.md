# 手动编辑颜色功能修复说明

## 修复的Bug

### Bug 1: 颜色管理器的手动编辑颜色无法作用于文件列表
**问题描述**：在颜色管理器中修改"手动编辑颜色"后，文件列表中已标记为手动编辑的文件颜色不会更新。

**原因**：`update_single_setting`方法中对`manually_edited_color`的处理是空的（`pass`），没有触发UI更新。

**修复方案**：
- 在`update_single_setting`方法中添加对`manually_edited_color`的处理
- 当颜色改变时，立即更新当前文件在文件列表中的显示颜色

### Bug 2: 文件列表中手动编辑后的状态会因为页面切换而消失
**问题描述**：当用户手动编辑一个文件后，文件列表中该文件会显示为绿色（或配置的颜色）。但是当切换到其他文件再切换回来时，颜色会消失，变回默认的黑色。

**原因**：
1. `reset_state`方法会清空`self.other_data = {}`
2. `load_file`方法在加载文件后，没有将`self.label_file.other_data`赋值给`self.other_data`
3. 导致`manually_edited`状态丢失

**修复方案**：
- 在`load_file`方法中，加载`label_file`后，立即将`self.label_file.other_data`赋值给`self.other_data`
- 这样可以正确恢复文件的`manually_edited`状态

### Bug 3: 软件重启后手动编辑的颜色不会自动显示
**问题描述**：软件重启后，打开文件夹时，文件列表中已手动编辑的文件不会显示为配置的颜色，必须切换到该文件才会变色。

**原因**：
- 在`import_image_folder`方法中，为了性能优化，没有立即检查每个文件的`manually_edited`状态
- 只有在实际加载文件时才会检查状态并更新颜色

**修复方案**：
- 在`import_image_folder`方法中，创建文件列表项时，如果文件有标注文件，立即读取JSON文件检查`manually_edited`状态
- 如果状态为true，立即设置文件列表项的颜色
- 这样在软件重启后，文件列表会立即显示正确的颜色

## 修改的文件

### views/labeling/label_widget.py

#### 1. 添加获取手动编辑颜色的辅助方法
```python
def _get_manually_edited_color(self):
    """获取手动编辑颜色配置"""
    color_value = self._config.get("manually_edited_color", "#00FF00")  # 默认绿色
    if isinstance(color_value, list):
        # 如果是RGB列表格式
        return QtGui.QColor(*color_value[:3])
    else:
        # 如果是十六进制字符串格式
        return QtGui.QColor(color_value)
```

#### 2. 修改`_update_file_list_item_color`方法
- 使用`_get_manually_edited_color()`获取配置的颜色
- 不再使用`traffic_light_colors`中的`edited`颜色

#### 3. 修改`update_single_setting`方法
- 添加对`manually_edited_color`的处理
- 当颜色改变时，更新当前文件的显示

#### 4. 修改`load_file`方法
- 在加载`label_file`后，立即恢复`other_data`
- 确保`manually_edited`状态不会丢失

#### 5. 修改`import_image_folder`方法
- 在创建文件列表项时，立即检查`manually_edited`状态
- 如果文件被手动编辑过，立即设置颜色
- 确保软件重启后颜色正确显示

## 功能说明

### 手动编辑颜色的作用
- 在颜色管理器中可以配置"手动编辑颜色"
- 当用户手动编辑一个文件后，该文件在文件列表中会显示为配置的颜色
- 这个颜色与红绿灯系统无关，是独立的功能

### 手动编辑状态的保存和恢复
- 当用户编辑文件时，`manually_edited`标志会保存到JSON文件的`other_data`中
- 当切换文件时，会从JSON文件中恢复`manually_edited`状态
- 文件列表中的颜色会根据`manually_edited`状态自动更新

## 测试建议

1. **测试颜色配置更新**：
   - 打开颜色管理器
   - 修改"手动编辑颜色"
   - 检查文件列表中已编辑文件的颜色是否立即更新

2. **测试状态保持**：
   - 手动编辑一个文件
   - 切换到其他文件
   - 再切换回来
   - 检查文件列表中的颜色是否保持

3. **测试新文件**：
   - 打开一个没有标注的文件
   - 添加标注
   - 检查文件列表中的颜色是否变为手动编辑颜色

4. **测试AI推理**：
   - 使用AI推理功能
   - 检查文件列表中的颜色是否不变（AI推理不应标记为手动编辑）

5. **测试软件重启**：
   - 手动编辑几个文件
   - 关闭软件
   - 重新打开软件并打开同一个文件夹
   - 检查文件列表中已编辑文件的颜色是否立即显示
