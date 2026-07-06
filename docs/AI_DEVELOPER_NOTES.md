# AI Developer Notes - 每个 AI 接手时先读这个

> **版本**: Hmogai_260702 | **基座**: X-AnyLabeling v3.2.2
> **用途**: 漫画 OCR 标注与翻译工具
> **最后更新**: 2026-07-06

---

## 0. 快速启动

```bash
conda activate yolov26          # 主环境
python anylabeling/app.py
```

备选环境：`xanylabeling`（旧环境，不推荐）

---

## 1. 硬约束 - 必须遵守

### 1.1 `label_widget.py` 已封仓 (19,449 行)

**禁止往 `anylabeling/views/labeling/label_widget.py` 里新增任何方法、属性、或类。**

| 场景 | 正确做法 | 禁止做法 |
|:---|:---|:---|
| 新增功能/对话框 | 写到 `widgets/` 下独立文件 | 往 label_widget.py 里加方法 |
| 新增工具类/线程 | 写到 `widgets/` 下独立文件 | 塞到 label_widget.py 末尾 |
| 修改已有功能 | 只改对应的方法体，不新增 | 新增 helper 方法扔进同一个文件 |

**原因**：多 AI 接力导致该文件膨胀到近 2 万行，每次新增都在雪上加霜。这文件已经是"遗产代码"，只减不增。

### 1.2 编码必须 UTF-8

- 所有 `.py` 文件第一行或第二行必须有 `# -*- encoding: utf-8 -*-`
- 所有 `.bat` 文件第一行必须是 `chcp 65001 >nul`
- 所有注释用中文没问题，但必须是 UTF-8 编码

**禁止 GBK 编码的中文注释。** 会导致下个 AI 打开看到乱码。

### 1.3 改完必须更新 CHANGELOG

项目已有 `CHANGELOG.md`，每次改完代码后，**在文件顶部（最新版本号下）追加一条记录**：

```markdown
### [日期] - 简短标题
- [模块] 做了什么改动
- 涉及文件：xxx.py, yyy.py
```

例如：
```markdown
### [2026-07-03] - 新增正圆角方形矩形工具
- [widgets] 新增 rounded_rect_dialog.py，快捷键 Y
- [label_widget] 在工具栏注册新工具入口
- 涉及文件：widgets/rounded_rect_dialog.py, label_widget.py
```

**为什么**：没有 Git 仓库，这是唯一能追溯"谁改了啥"的方式。下次 AI 接手看 CHANGELOG 就知道最近的改动。

### 1.4 不要装新依赖除非必要

现有依赖列表见 `requirements.txt` 和 `requirements-gpu.txt`。

如果确实需要新包，在 CHANGELOG 里说明原因，并同步更新 `requirements.txt`（非 GPU 包）或 `requirements-gpu.txt`（GPU 相关包）。

---

## 2. 软约束 - 强烈建议

### 2.1 新文件放哪

| 内容类型 | 存放路径 |
|:---|:---|
| 新对话框 | `anylabeling/views/labeling/widgets/xxx_dialog.py` |
| 新 Widget/面板 | `anylabeling/views/labeling/widgets/xxx_widget.py` |
| 纯工具函数（无 UI） | `anylabeling/views/labeling/widgets/xxx_utils.py` |
| AI 推理服务 | `anylabeling/services/auto_labeling/` |
| 配置文件 | 项目根目录 `xxx.json` 或 `xxx.ini` |

### 2.2 文件命名规范

参考已有 63 个 widget 文件的命名：
- **对话框**: `xxx_dialog.py`（如 `char_render_dialog.py`）
- **Widget**: `xxx_widget.py`（如 `model_dropdown_widget.py`）
- **工具/管理器**: `xxx_xxx.py`（如 `smart_guides_dialog.py`）

文件名全部小写 + 下划线，对应类名用大驼峰：
```python
# 文件: magnifier_settings_dialog.py
class MagnifierSettingsDialog(QtWidgets.QDialog):
    ...
```

### 2.3 Import 约定

优先用相对导入：
```python
from .widgets.char_render_dialog import CharRenderDialog
from .widgets import (Canvas, AutoLabelingWidget, ...)
```

**禁止**在 label_widget.py 里用绝对 import 引入 widget（已有几处遗留的绝对 import，属于历史债务，别学）：
```python
# 不要这样
from anylabeling.views.labeling.widgets.wheel_settings_dialog import WheelSettingsDialog
# 应该这样
from .widgets.wheel_settings_dialog import WheelSettingsDialog
```

### 2.4 方法命名

- 私有方法加下划线前缀：`def _my_internal_helper(self):`
- 信号槽回调统一 `on_` 前缀：`def on_button_clicked(self):`
- 别用拼音命名 - 用英文描述功能

---

## 3. 关键文件地图

### 核心架构（改这里要特别小心）

| 文件 | 行数 | 职责 | 注意事项 |
|:---|:---|:---|:---|
| `anylabeling/views/labeling/label_widget.py` | 19,449 | **主窗口逻辑（遗产）** | 已封仓，别再往里加了 |
| `anylabeling/views/labeling/widgets/canvas.py` | ~10,500 | 画布渲染、鼠标交互、标注显示 | 大量定制逻辑，Shift拖拽/缩放；新增 batch_label_changed 信号 |
| `anylabeling/views/labeling/shape.py` | ~8,300 | 形状定义：矩形、多边形、rotation3 等 | 新增形状类型在这里 |
| `anylabeling/views/labeling/label_file.py` | - | 标注文件 I/O | 修改保存/加载格式在这里 |
| `anylabeling/app.py` | - | 应用入口 | - |

### 本分支定制功能地图

| 功能 | 涉及文件 | 标记 |
|:---|:---|:---|
| **rotation3 形状**（三击定点旋转矩形） | `shape.py`（定义）, `canvas.py`（渲染）, `label_widget.py`（创建逻辑） | 快捷键 H |
| **OCR 文本替换** | `ocr_text_replace.py`, `ocr_text_replace.json` | 表格 UI，按标签过滤 |
| **字符渲染** | `char_render_dialog.py`, `char_render_rules.json` | 逐字控制角度/偏移 |
| **fast_send 转发** | `fast_send.py` | WM_COPYDATA + EnumWindows |
| **animated WebP** | `animated_webp_support.py`, `animated_webp_view.py` | label_widget 内 54 个 `_animated_webp_*` 方法 |
| **缩略图查看器** | `thumbnail_viewer_dialog.py` | 瀑布流布局 |
| **水平/垂直查看器** | `horizontal_viewer_dialog.py`, `vertical_viewer_dialog.py` | 批量查看 |
| **对齐工具** | `alignment_dialog.py` | - |
| **smart guides** | `smart_guides_dialog.py` | 智能参考线 |
| **crosshair 设置** | `crosshair_settings_dialog.py` | 十字准星 |
| **magnifier 设置** | `magnifier_settings_dialog.py` | 放大镜 |
| **常高亮设置** | `highlight_settings_dialog.py` | 根目录有 .bat 一键设置 |
| **滚轮设置** | `wheel_settings_dialog.py` | - |
| **标签分类** | `label_category_widget.py`, `label_list_widget.py` | - |
| **标签排序** | `tag_sort_dialog.py` | - |
| **标签同步** | `label_sync_dialog.py` | 跨文件标签同步 |
| **图片分类管理器** | `image_category_manager_dialog.py` | - |
| **文字拆分** | `text_split_dialog.py` | - |
| **逐页文字** | `page_text_dialog.py` | - |
| **区域批量删除** | `region_batch_delete_dialog.py` | - |
| **矩形缩放** | `rectangle_scale_dialog.py` | - |
| **矩形间距** | `rectangle_spacing_guide.py` | - |
| **扩展边距** | `expand_margins_dialog.py` | - |
| **安全边距** | `safety_border_settings_dialog.py` | - |
| **包含检测** | `containment_detection_dialog.py` | - |
| **双色工具** | `dual_color_tool_dialog.py` | - |
| **AI 模型** | `services/auto_labeling/`, `searchable_model_dropdown.py`, `model_dropdown_widget.py` | YOLO26 + Manga OCR |
| **API Token 管理** | `api_token_dialog.py` | - |
| **快捷键管理** | `shortcut_manager_dialog.py`, `keymap_dialog.py` | - |
| **color manager** | `color_manager_dialog.py` | - |
| **overview 概览** | `overview_dialog.py` | - |
| **zoom 控件** | `zoom_widget.py` | - |
| **导航控件** | `navigator_widget.py` | - |
| **亮度/对比度** | `brightness_contrast_dialog.py` | - |
| **角度校正** | `angle_correction_dialog.py` | - |
| **文件名过滤** | `file_filter_dialog.py` | - |
| **AI 聊天** | `chatbot_dialog.py` | - |
| **VQA** | `vqa_dialog.py` | - |
| **escapable list** | `escapable_qlist_widget.py` | 按 Esc 取消全选 |
| **unique label list** | `unique_label_qlist_widget.py` | 唯一标签列表 |
| **popup** | `popup.py` | 弹窗工具 |
| **masks** | `mask_generator_dialog.py`, `segmentation_dialog.py` | - |
| **traffic light** | `mainwindow_widgets/traffic_light_dialog.py` | - |
| **about** | `about_dialog.py` | 关于对话框 |
| **路径线/框选设置** | `path_selection_settings_dialog.py` | 多选自动改标签模式（Tool 菜单）详见 `docs/path_selection_label_mode.md` |

### 模型文件

| 模型 | 路径 | 大小 | 用途 |
|:---|:---|:---|:---|
| Manga OCR | `models/manga_ocr/` | ~500MB | 漫画文字识别 |
| YOLO26 系列 | `models/` 配置在 `xanylabeling_config.ini` | - | 漫画气泡/框检测 |

### 外部配置

| 文件 | 用途 |
|:---|:---|
| `xanylabeling_config.ini` | 主配置：标签列表、模型设置 |
| `CCC.YSGxanylabelingrc` | 个性化配置备份 |
| `ocr_text_replace.json` | OCR 文本替换规则 |
| `char_render_rules.json` | 字符渲染规则 |
| `biaoqian.txt` | 标签列表文本版 |

---

## 4. Conda 环境

| 环境名 | 位置 | 用途 | 注意事项 |
|:---|:---|:---|:---|
| `yolov26` | conda 默认位置 | **主环境** | Python 3.10，含 PyTorch + GPU |
| `xanylabeling` | conda 默认位置 | 备用/旧环境 | 不要删，部分脚本可能引用 |

启动相关批处理：
- `一键修GPU和日期号.bat` - 修复 GPU 设置和日期格式（中文注释损坏，需修复）
- `根目录下双击一键设置常高亮等个性化X-AnyLabeling.py` - 个性化设置脚本

环境列表详见 `my_env_list.txt`。

---

## 5. 已知技术债务

| 问题 | 严重程度 | 说明 |
|:---|:---|:---|
| label_widget.py 近 2 万行 | 高 | 已封仓，不再新增。将来逐步用 Mixin 拆分 |
| 无版本管理 | 高 | 手动上传 GitHub，依赖 CHANGELOG.md 记录改动 |
| 批处理编码损坏 | 中 | `一键修GPU和日期号.bat` 中文 GBK-UTF-8 二次损坏 |
| 示例 JSON 含不雅内容 | 中 | `ocr_text_replace.json`、`char_render_rules.json` 示例词需清理 |
| 绝对/相对 import 混用 | 低 | label_widget.py 内有几处绝对 import |
| 重复 import（math, numpy） | 低 | label_widget.py 顶部重复导入 |

---

## 6. 开发流程 Checklist

每次改代码前：

- [ ] 读了这份文件
- [ ] 确认改动不会往 label_widget.py 里加新方法
- [ ] 确认新功能写到正确的路径
- [ ] 确认文件编码是 UTF-8

每次改完代码后：

- [ ] 在 CHANGELOG.md 顶部追加一条修改记录
- [ ] 确认列出了所有涉及的文件
- [ ] 如果加了新依赖，更新 `requirements.txt`
- [ ] 如果新增了重要功能，在这份文件的 3 里加上一行记录

---

---

> **给下个 AI 的话**：这份文件是前人踩坑攒出来的。读完再动手，别重蹈覆辙。改完代码记得写 CHANGELOG，不然下个人根本不知道你改了啥。
