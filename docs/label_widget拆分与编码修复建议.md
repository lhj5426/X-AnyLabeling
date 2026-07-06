# label_widget.py 拆分建议 & 批处理编码修复方案

---

## 一、label_widget.py 拆分方案

当前文件 19,449 行，含 **12 个类**、**~500 个方法**。其中 `LabelingWidget` 单类占约 18,800 行。

### 1.1 现有类结构一览

```
line  111  class ShrinkableWidget          — 自定义收缩 Widget（11行）
line  126  class ShrinkablePushButton      — 自定义收缩按钮（11行）  
line  140  class MergeThread               — 合并线程（52行）
line  191  class TextSplitThread           — 文本拆分线程（130行）
line  321  class AnimatedWebPPreloadThread — WebP预加载线程（27行）
line  348  class ImagePreloadThread        — 图片预加载线程（55行）
line  403  class PageSwitchState           — 翻页状态（8行）
line  411  class TagSortThread             — 标签排序线程（23行）
line  434  class LoadColorsThread          — 颜色加载线程（34行）
line  468  class ClearEditedThread         — 清空编辑线程（74行）
line  542  class ClearDifficultThread      — 清空困难样本线程（68行）
line  610  class LabelingWidget            — ⚠️ 巨无霸主类（18,839行）
```

### 1.2 第一步：先拆出辅助类（低风险，半小时搞定）

这 11 个辅助类可以直接移到独立文件，`label_widget.py` 改成 `import`。

```
anylabeling/views/labeling/
├── label_widget.py              # 只保留 LabelingWidget 类
├── _threads/
│   ├── __init__.py
│   ├── merge_thread.py           # MergeThread
│   ├── text_split_thread.py      # TextSplitThread
│   ├── animated_webp_preload.py  # AnimatedWebPPreloadThread
│   ├── image_preload_thread.py   # ImagePreloadThread
│   ├── tag_sort_thread.py        # TagSortThread
│   ├── load_colors_thread.py     # LoadColorsThread
│   ├── clear_edited_thread.py    # ClearEditedThread
│   └── clear_difficult_thread.py # ClearDifficultThread
├── _widgets/
│   ├── __init__.py
│   ├── shrinkable_widget.py      # ShrinkableWidget
│   └── shrinkable_button.py      # ShrinkablePushButton
└── page_switch_state.py          # PageSwitchState
```

**操作方式**：对每个类，直接 cut + paste 到新文件，在 `label_widget.py` 顶部加一行 import。这 11 个类内部没有跨类耦合，纯机械操作。

### 1.3 第二步：LabelingWidget 按功能域拆分（核心工作）

`LabelingWidget` 的方法可按前缀/功能域分组，对应约 15 个 mixin 文件：

```
anylabeling/views/labeling/
├── label_widget.py                    # 主壳（只含 __init__ + import mixin）
├── _mixins/
│   ├── __init__.py
│   ├── animated_webp_mixin.py         # 54 个动画 WebP 方法（~700行）
│   ├── shape_edit_mixin.py            # 形状编辑: create/copy/paste/delete/undo/redo（~2000行）
│   ├── file_io_mixin.py               # 文件读写: save/load/import/export（~1500行）
│   ├── model_inference_mixin.py       # AI 推理相关: auto_labeling/segmentation/decode（~2000行）
│   ├── dialog_mixin.py                # 各种对话框入口（~2500行）
│   ├── label_mixin.py                 # 标签管理: label_file/label_list/colors（~1000行）
│   ├── canvas_interaction_mixin.py    # 画布交互: zoom/pan/overlay/status（~1500行）
│   ├── navigator_mixin.py             # 导航器相关（~800行）
│   ├── thumbnail_mixin.py             # 缩略图视图（~800行）
│   ├── shortcut_mixin.py              # 快捷键管理（~600行）
│   ├── training_mixin.py              # 训练入口（~400行）
│   ├── merge_textsplit_mixin.py       # 合并/文本拆分（~500行）
│   ├── horizontal_vertical_mixin.py   # 水平/垂直视图（~1000行）
│   └── settings_mixin.py              # 配置/设置（~800行）
```

**Mixin 模式示例**：

```python
# 拆分前（label_widget.py）
class LabelingWidget(QtWidgets.QWidget):
    def __init__(self, ...):
        ...

    def play_animated_webp(self):
        # ~30行逻辑

    def pause_animated_webp(self):
        # ~20行逻辑
    # ... 还有 52 个 animated_webp 方法

# 拆分后
# _mixins/animated_webp_mixin.py
class AnimatedWebPMixin:
    """Animated WebP playback controls."""

    def play_animated_webp(self) -> None:
        ...

    def pause_animated_webp(self) -> None:
        ...

# label_widget.py
from ._mixins.animated_webp_mixin import AnimatedWebPMixin
from ._mixins.shape_edit_mixin import ShapeEditMixin
# ...

class LabelingWidget(
    AnimatedWebPMixin,
    ShapeEditMixin,
    FileIOMixin,
    ModelInferenceMixin,
    QtWidgets.QWidget  # ← 基础类放最后
):
    def __init__(self, ...):
        ...
```

### 1.4 执行顺序建议（按耦合度从低到高）

| 优先级 | 模块 | 理由 |
|:---:|:---|:---|
| 1 | `animated_webp_mixin.py` | 54 个方法全部 `_animated_webp_*` 或 `play/pause_animated_webp`，内聚性好 |
| 2 | `navigator_mixin.py` | `_navigator_*` 前缀，与主类耦合最轻 |
| 3 | `thumbnail_mixin.py` | `_thumbnail_*` + `on_thumbnail_*` |
| 4 | `horizontal_vertical_mixin.py` | 独立视图逻辑 |
| 5 | `file_io_mixin.py` | `save_*` / `load_*` / `import_*` |
| 6 | `merge_textsplit_mixin.py` | 独立功能 |
| 7 | `shortcut_mixin.py` | `digit_shortcut_*` / `keyPressEvent` |
| 8 | `training_mixin.py` | 训练入口 |
| 9 | `label_mixin.py` | 标签管理 |
| 10 | `dialog_mixin.py` | 对话框（耦合最多，放最后） |
| 11 | `shape_edit_mixin.py` | 形状编辑核心（耦合最多） |
| 12 | `canvas_interaction_mixin.py` | 画布交互核心（耦合最多） |
| 13 | `model_inference_mixin.py` | AI 推理（耦合最多） |
| 14 | `settings_mixin.py` | 配置 |

### 1.5 关键注意事项

1. **Mixin 中访问 `self.xxx` 属性时**，IDE 会提示属性未定义。可以通过在 mixin 类开头添加类型注解解决：
   ```python
   class AnimatedWebPMixin:
       if TYPE_CHECKING:
           # 由 LabelingWidget 提供
           canvas: Canvas
           image_list: list
           current_index: int
   ```

2. **信号连接 (`self.xxx.connect`)** 保留在 `LabelingWidget.__init__` 中，不要移到 mixin。

3. **每次只移一个模块，移完立刻跑起来测试**，不要一次性全拆。

4. **不需要一口气全拆完**——先拆线程类 + animated_webp（约 700 行），效果立竿见影。

---

## 二、批处理文件编码修复

### 2.1 问题诊断

`一键修GPU和日期号.bat` 使用了 `chcp 65001`（UTF-8 代码页），但文件内的中文注释字节实际是 **GBK** 编码：

| 当前乱码 | 原始意图 | GBK 字节 |
|:---|:---|:---|
| `REM ȡǰļ` | `REM 取当前文件夹` | `C8 A1 B5 B1 C7 B0 CE C4 BC FE BC D0` → 实际只有 `C8 A1 C7 B0 C4 BC`（已损坏） |
| `REM ȡ` | `REM 取日期号` | 已损坏 |
| `REM ļ·` | `REM 设置文件路径` | 已损坏 |
| `REM ʱļ` | `REM 创建临时文件` | 已损坏 |
| `REM 滻ԭļ` | `REM 替换原文件` | 已损坏 |

根本原因：文件在 GBK 编辑器中创建、后又用 UTF-8 编辑器打开/保存，导致双字节 GBK 字符被当作 Latin-1 重新编码，部分字节丢失/替换，**原始中文已不可完全恢复**。

### 2.2 修复方案：重写中文注释

由于原始中文已损坏，直接按代码逻辑反推注释含义并重写为正确 UTF-8：

```batch
@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM 获取当前文件夹名
for %%* in (.) do set "folder=%%~nx*"

REM 从文件夹名提取日期号（格式: X-Name-Hmogai260702）
for /f "tokens=3 delims=-" %%a in ("%folder%") do set "date=%%a"
set "date=!date:mogai=mogai_!"

REM 设置目标文件路径
set "file=anylabeling\app_info.py"
set "tempfile=anylabeling\app_info_temp.py"

REM 生成临时文件并修改 appname 和 preferred_device
> "%tempfile%" (
    for /f "usebackq tokens=* delims=" %%l in ("%file%") do (
        set "line=%%l"

        echo !line! | findstr /b /c:"__appname__ =" >nul
        if !errorlevel! == 0 (
            echo __appname__ = "!date!_X-AnyLabeling"
        ) else (
            echo !line! | findstr /b /c:"__preferred_device__ =" >nul
            if !errorlevel! == 0 (
                echo __preferred_device__ = "GPU"  # GPU or CPU
            ) else (
                echo !line!
            )
        )
    )
)

REM 用临时文件替换原文件
move /y "%tempfile%" "%file%" >nul

echo 成功修改 __appname__ 和 __preferred_device__
set /p dummy=请按任意键继续. . .
```

### 2.3 通用规避建议

1. **批处理文件不用中文注释**——用英文或直接用 Python 脚本替代
2. **如果必须用中文**，确保文件保存为 **UTF-8 with BOM**（记事本另存为 → UTF-8），`chcp 65001` 配合 BOM 兼容性最好
3. **长远方案**：把 `.bat` 启动逻辑改写为 Python 脚本，彻底避免编码问题：

```python
# run_labeling.py（替代所有 .bat）
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

env_map = {
    "xanylabeling": "xanylabeling",
    "yolov26": "yolov26",
}
env_name = env_map.get(sys.argv[1], "yolov26")

subprocess.run(
    ["conda", "run", "-n", env_name, "python", "anylabeling/app.py"] + sys.argv[2:],
    check=True,
)
```

这样所有 .bat 启动方式替换为：
```
conda run -n yolov26 python run_labeling.py
```

---

## 三、工作量估算

| 任务 | 预估时间 | 难度 |
|:---|:---:|:---|
| 拆出 11 个辅助线程/Widget 类 | 30 分钟 | 低 |
| 拆 animated_webp_mixin | 1 小时 | 中 |
| 拆 navigator + thumbnail + h_v | 2 小时 | 中 |
| 拆 shape_edit + canvas + dialog | 4-6 小时 | **高**（耦合最多） |
| 其余 mixin | 3-4 小时 | 中 |
| 重写所有 .bat 注释 | 15 分钟 | 低 |
| .bat 改写为统一 Python 启动 | 1 小时 | 低 |
| **合计** | **12-15 小时** | — |

建议从低风险任务开始：先修批处理编码 + 拆线程类，跑通后再逐步拆分 LabelingWidget。
