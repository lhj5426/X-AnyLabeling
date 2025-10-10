# 251011-rotation3模式下十字线自动切换功能-实现文档

**功能名称**：`rotation3` 模式下十字线的智能自动切换
**开发日期**：2025-10-11
**开发AI**：gemini 2.5pro
**状态**：✅ 已完成

---

## 📋 功能概述

为 X-AnyLabeling 的 `rotation3`（三点旋转矩形）创建模式，增加了一项智能的十字线自动管理功能。此功能旨在优化用户在“检查标注”和“创建标注”两种状态间切换时的工作流，避免手动开关十字线的繁琐操作。

### 需求背景

- **原始问题**：用户在检查标注时，通常会关闭十字线以获得清晰视野。但当发现遗漏需要立即补画一个 `rotation3` 框时，必须手动开启十字线才能精确对齐。绘制完成后，又需要再次手动关闭，操作流程被打断。
- **用户需求**：希望在进入 `rotation3` 模式时，如果十字线是关闭的，程序能自动、临时地开启它；在本次绘制任务结束后，再自动恢复到原先的关闭状态。

### 功能特点

1. ✅ **智能检测**：在激活 `rotation3` 模式时，自动检测十字线的当前状态。
2. ✅ **自动开启**：如果十字线处于关闭状态，则为本次 `rotation3` 绘制任务自动开启。
3. ✅ **状态保持**：如果十字线原本就是开启的，则在整个过程中保持开启，不做任何干预。
4. ✅ **自动恢复**：在单次 `rotation3` 绘制任务结束后（无论是成功创建还是中途取消），能自动将十字线恢复到任务开始前的状态。
5. ✅ **无缝体验**：用户无需任何手动操作，即可在需要时获得十字线辅助，在不需要时恢复清爽的视图。

---

## 🧠 功能逻辑详解

根据用户的需求，我们将一次 `rotation3` 标注的生命周期分为四个阶段，并精确控制每个阶段的逻辑：

| 阶段 | 名称 | 触发时机 | 核心逻辑 |
|:---:|:---|:---|:---|
| **①** | **激活 (Activation)** | 点击 `rotation3` 按钮或使用快捷键 | 检查十字线状态。如果关闭，则**立即开启**并设置“临时”标记。 |
| **②** | **待画框中 (Pending Draw)** | 激活模式后，首次点击前 | 十字线**保持显示**，辅助用户寻找最佳起始点。 |
| **③** | **画框中 (Drawing)** | 从首次点击到完成三次点击 | 十字线**持续显示**，提供对齐参考。 |
| **④** | **画框结束 (Finished)** | 成功创建形状或按 `Esc` 取消 | 检查“临时”标记。如果存在，则**立即关闭**十字线，恢复原状。 |

---

## 🔧 技术实现

### 修改文件

1.  **`anylabeling/views/labeling/widgets/canvas.py`**
    - **修改类型**：重构与信号新增
    - **说明**：为了能从外部捕获“取消绘制”事件，对 `keyPressEvent` 进行了重构，并增加了一个新的 `drawing_cancelled` 信号。

2.  **`anylabeling/views/labeling/label_widget.py`**
    - **修改类型**：核心逻辑实现
    - **说明**：添加了状态变量和控制方法，实现了完整的自动切换逻辑。

### 详细修改记录

#### 1. `canvas.py` 的修改

- **新增 `drawing_cancelled` 信号**：
  ```python
  drawing_cancelled = QtCore.pyqtSignal()
  ```
- **新增 `cancel_drawing()` 方法**：将原先在 `keyPressEvent` 中的取消逻辑（`self.current = None` 等）封装到此方法中，并增加了信号发射。
  ```python
  def cancel_drawing(self):
      if self.current:
          # ... 原有逻辑 ...
          self.drawing_cancelled.emit() # 发射信号
          self.update()
  ```
- **更新 `keyPressEvent`**：使其在 `Esc` 按下时调用 `self.cancel_drawing()`。

#### 2. `label_widget.py` 的修改

- **新增状态变量 `_crosshair_was_toggled_for_rotation3`**：在 `__init__` 中初始化为 `False`，用于追踪十字线是否被本功能自动开启。

- **连接 `drawing_cancelled` 信号**：
  ```python
  self.canvas.drawing_cancelled.connect(self.on_drawing_cancelled)
  ```

- **新增 `restore_crosshair_if_needed()` 和 `on_drawing_cancelled()` 方法**：
  ```python
  def restore_crosshair_if_needed(self):
      if self._crosshair_was_toggled_for_rotation3:
          self.toggle_crosshair() # 调用之前实现的切换方法
          self._crosshair_was_toggled_for_rotation3 = False

  def on_drawing_cancelled(self):
      self.restore_crosshair_if_needed()
  ```

- **修改 `toggle_draw_mode()` 方法**：
  - **进入 `rotation3` 模式时**：检查 `self._config["canvas"]["crosshair"]["show"]` 的值，如果为 `False`，则调用 `self.toggle_crosshair()` 并将状态变量设为 `True`。
  - **退出 `rotation3` 模式时**：在方法开头增加判断，如果前一个模式是 `rotation3` 且状态变量为 `True`，则调用 `self.restore_crosshair_if_needed()`。

- **修改 `new_shape()` 方法**：
  - 在方法末尾（成功创建或取消标签输入后）增加对 `self.restore_crosshair_if_needed()` 的调用，以处理“画框结束”的场景。

---

## 🧪 测试验证清单

- [x] **主场景测试**：
  - [x] 默认关闭十字线 → 进入 `rotation3` 模式 → 十字线自动开启。
  - [x] 成功绘制一个框 → 十字线自动关闭。
  - [x] 再次进入 `rotation3` 模式 → 十字线再次自动开启。

- [x] **取消场景测试**：
  - [x] 默认关闭十字线 → 进入 `rotation3` 模式 → 十字线自动开启。
  - [x] 绘制过程中按 `Esc` 键 → 十字线自动关闭。

- [x] **切换工具测试**：
  - [x] 默认关闭十字线 → 进入 `rotation3` 模式 → 十字线自动开启。
  - [x] 中途点击“编辑”或其他工具按钮 → 十字线自动关闭。

- [x] **对照组测试**：
  - [x] 默认**开启**十字线 → 进入 `rotation3` 模式 → 十字线保持开启。
  - [x] 绘制结束或取消 → 十字线**依然保持开启**，不受影响。

- [x] **其他模式兼容性测试**：
  - [x] 进入 `rectangle`、`polygon` 等其他模式 → 不触发任何自动切换逻辑。
