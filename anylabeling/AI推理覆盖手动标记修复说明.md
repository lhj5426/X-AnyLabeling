# AI 推理覆盖手动标记修复说明

**修复日期：** 2025-10-03
**问题描述：** AI 重新推理后，手动编辑标记（橙色）没有被清除
**修复版本：** v3.2.2+

---

## 问题说明

### 原始问题

在使用手动编辑标记功能时，发现以下问题：

1. **单张推理**：AI 推理后，`manually_edited` 标记没有被清除 ❌
2. **批量推理**：AI 批量推理后，`manually_edited` 标记没有被清除 ❌
3. **文件列表颜色**：保存后，如果 `manually_edited = false`，颜色不会恢复成黑色 ❌

### 实际场景

```
1. 老模型推理 → 识别错误（猫识别成狗）
2. 手动修正 → 改成"猫"，文件变橙色（manually_edited = true）
3. 换新模型重新推理 → 新模型能正确识别"猫"
4. 问题：文件仍然是橙色 ❌
5. 导出"仅手动调整的文件" → 错误地导出了新模型已经能识别准确的数据 ❌
```

### 期望行为

```
1. 老模型推理 → 识别错误
2. 手动修正 → 橙色（manually_edited = true）
3. 新模型重新推理 → 黑色（manually_edited = false）✅
4. 如果新模型还是不准 → 再次手动修正 → 橙色
```

**核心逻辑：**
- **橙色** = 当前模型推理不准，需要人工修正的数据
- **黑色** = 模型推理结果（无论准不准）

---

## 修复内容

### 1. 单张 AI 推理时清除标记

**文件：** `views/labeling/label_widget.py`
**位置：** 第 6290-6291 行
**函数：** `new_shapes_from_auto_labeling()`

```python
# Set image description
if auto_labeling_result.description:
    description = auto_labeling_result.description
    self.shape_text_label.setText(self.tr("Image Description"))
    self.shape_text_edit.setPlainText(description)
    self.other_data["description"] = description
    self.shape_text_edit.setDisabled(False)

# Clear manually_edited flag when AI re-inference
self.other_data["manually_edited"] = False  # ← 新增

# Mark as dirty but not as manually edited (this is AI inference, not user edit)
self.set_dirty(mark_as_manually_edited=False)
```

**修复效果：** 单张推理时清除 `manually_edited` 标记 ✅

---

### 2. 批量 AI 推理时清除标记

**文件：** `views/labeling/utils/batch.py`
**位置：** 第 204-213 行
**函数：** `save_auto_labeling_result()`

#### 2.1 更新已存在的文件

```python
if osp.exists(label_file):
    with io_open(label_file, "r") as f:
        data = json.load(f)

    if replace:
        data["shapes"] = new_shapes
        data["description"] = new_description
        # Clear manually_edited flag when AI batch inference
        data["manually_edited"] = False  # ← 新增
    else:
        data["shapes"].extend(new_shapes)
        if "description" in data:
            data["description"] += new_description
        else:
            data["description"] = new_description
        # Clear manually_edited flag when AI batch inference
        data["manually_edited"] = False  # ← 新增
```

#### 2.2 创建新文件

**位置：** 第 234 行

```python
data = {
    "version": __version__,
    "flags": {},
    "shapes": new_shapes,
    "imagePath": image_path,
    "imageData": image_data,
    "imageHeight": image_height,
    "imageWidth": image_width,
    "description": new_description,
    "manually_edited": False,  # ← 新增
}
```

**修复效果：** 批量推理时清除 `manually_edited` 标记 ✅

---

### 3. 保存时恢复默认颜色

**文件：** `views/labeling/label_widget.py`
**位置：** 第 4658-4660 行
**函数：** `save_labels()`

```python
# Update color to show manually edited status
if self.other_data.get("manually_edited", False):
    color = self._config.get("manually_edited_color", "#FFA500")
    item.setForeground(QtGui.QColor(color))
else:
    # Reset to default color (black) when not manually edited
    item.setForeground(QtGui.QColor("#000000"))  # ← 新增
```

**修复效果：** 保存后正确恢复黑色 ✅

---

## 自动刷新机制

### 批量推理完成后自动刷新

**文件：** `views/labeling/utils/batch.py`
**位置：** 第 159 行
**函数：** `finish_processing()`

```python
def finish_processing(self, progress_dialog):
    self.filename = self.image_list[self.current_index]
    self.import_image_folder(osp.dirname(self.filename))  # ← 重新加载文件夹
    # ...
```

**刷新逻辑：**

`import_image_folder()` 会重新读取所有文件的 `manually_edited` 字段并更新颜色：

```python
# Check if file was manually edited
manually_edited = False
if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(label_file):
    try:
        with open(label_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            manually_edited = data.get("manually_edited", False)
    except:
        pass

# Set color for manually edited items
if manually_edited:
    color = self._config.get("manually_edited_color", "#FFA500")
    item.setForeground(QtGui.QColor(color))
```

**结果：** 批量推理完成后，文件列表自动刷新，橙色标记正确更新 ✅

---

## 修复后的完整流程

### 场景 1：单张推理

```
1. 文件：image001.jpg（橙色，manually_edited = true）
2. 点击"运行推理"→ AI 推理
3. 保存 → manually_edited = false
4. 文件列表更新 → 黑色 ✅
```

### 场景 2：批量推理

```
1. 文件夹：
   - image001.jpg（橙色）
   - image002.jpg（黑色）
   - image003.jpg（橙色）

2. 点击"批量推理"→ AI 批量推理所有图片

3. 批量推理完成：
   - 所有文件的 manually_edited = false
   - 自动刷新文件列表

4. 文件列表：
   - image001.jpg（黑色）✅
   - image002.jpg（黑色）✅
   - image003.jpg（黑色）✅
```

### 场景 3：手动修改后再次推理

```
1. AI 推理 → 黑色
2. 手动修改 → 橙色（manually_edited = true）
3. 再次 AI 推理 → 黑色（manually_edited = false）✅
4. 如果 AI 推理还是不准 → 再次手动修改 → 橙色
```

---

## 导出行为

### 修复前 ❌

```
导出"仅手动调整的文件"：
- 导出了老模型推理不准、经过手动修正的文件
- 也导出了新模型已经能识别准确的文件（错误）
```

### 修复后 ✅

```
导出"仅手动调整的文件"：
- 只导出当前模型推理不准、经过人工修正的文件
- 不导出新模型已经能识别准确的文件
```

---

## 测试验证

### 测试用例 1：单张推理清除标记

1. 手动修改一个文件 → 橙色
2. 对该文件进行单张推理
3. **预期结果：** 文件变成黑色 ✅

### 测试用例 2：批量推理清除标记

1. 手动修改 3 个文件 → 全部橙色
2. 对整个文件夹进行批量推理
3. **预期结果：** 批量完成后，所有文件变成黑色 ✅

### 测试用例 3：导出筛选

1. 批量推理 10 个文件 → 全部黑色
2. 手动修改其中 2 个文件 → 2 个橙色，8 个黑色
3. 导出"仅手动调整的文件"
4. **预期结果：** 只导出 2 个橙色文件 ✅

---

## 修改文件清单

| 文件 | 修改行数 | 修改内容 |
|------|---------|---------|
| `views/labeling/label_widget.py` | 6290-6291 | 单张推理时清除 manually_edited |
| `views/labeling/label_widget.py` | 4658-4660 | 保存时恢复黑色 |
| `views/labeling/utils/batch.py` | 204-213 | 批量推理时清除 manually_edited（更新已存在文件） |
| `views/labeling/utils/batch.py` | 234 | 批量推理时清除 manually_edited（新建文件） |

---

## 相关文档

- [手动编辑标记功能说明.md](./手动编辑标记功能说明.md) - 手动编辑标记功能的完整说明

---

## 更新日志

| 日期 | 版本 | 修改内容 |
|-----|------|---------|
| 2025-10-03 | v3.2.2+ | 修复 AI 推理不清除 manually_edited 标记的问题 |
| 2025-10-03 | v3.2.2+ | 修复保存后不恢复黑色的问题 |
| 2025-10-03 | v3.2.2+ | 批量推理和单张推理都正确清除标记 |

---

**文档结束**
