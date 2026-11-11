# 合成器节点

本文档覆盖 `Nodes` 中全部 11 个 Compositor 节点。它们只能用于 `CompositorNodeTree`；资产建模代码不创建或修改 compositor，调用所有权属于外层 runner。即使单体建模不直接调用，这些接口仍完整保留，用于理解和维护 `infinigen/core/rendering/render.py`。

通用 `NodeWrangler.new_node` 参数见 `../node_wrangler_usage.md`。下文中的 `source` 表示 Compositor 图像 socket。

## 快速选择

| 目标 | 节点 |
| --- | --- |
| 读取当前 Scene/View Layer 的渲染结果和 render passes | `Nodes.RenderLayers` |
| 调整亮度/对比度或曝光 | `Nodes.BrightContrast`、`Nodes.Exposure` |
| 拆分、重组颜色通道 | `Nodes.CompSeparateColor`、`Nodes.CompCombineColor` |
| 按 blend mode 混合两幅图像 | `Nodes.CompositorMixRGB` |
| 添加镜头畸变、色散、辉光或光晕 | `Nodes.LensDistortion`、`Nodes.Glare` |
| 写入最终 Render Result | `Nodes.Composite` |
| 临时查看中间结果 | `Nodes.Viewer` |
| 把图像或 passes 写入文件 | `Nodes.OutputFile` |

`RenderLayers`、`Composite` 和 `Viewer` 属于 Infinigen singleton；同一 node tree 中重复 `new_node` 会复用已有节点。`OutputFile` 不是 singleton，可分别创建 PNG、EXR 等输出。

## `Nodes.RenderLayers`

**作用**：从指定 Scene 和 View Layer 读取未经合成的渲染图像及已启用的 render passes。

**创建方式**：

```python
render_layers = nw.new_node(
    Nodes.RenderLayers,
    attrs={"scene": bpy.context.scene, "layer": "ViewLayer"},
)
source = render_layers.outputs["Image"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.RenderLayers`，对应 `CompositorNodeRLayers` |
| `attrs` | 可选 `scene: bpy.types.Scene`、`layer: str` |

**Input Sockets**：无。

**Output Sockets**：始终提供 `Image` 和 `Alpha`；其余输出由目标 View Layer、渲染器和已启用 passes 决定，常见名称包括 `Depth`、`Normal`、`UV`、`Vector`、`Position`、`Shadow`、`AO`、`IndexOB`、`IndexMA`、`Mist`、`Emit` 及 Cycles 分量 passes。`Noisy Image` 只在相应 Cycles denoising pass 可用时出现。

读取某个动态输出前，runner 必须先设置 `view_layer.use_pass_*` 或 `view_layer.cycles.use_pass_*`；不要仅因为 socket 名出现在 Blender RNA 中就假设它已启用。该节点是 singleton，重复调用用于取得同一个 Render Layers 节点，不会创建多个输入场景。

## `Nodes.BrightContrast`

**作用**：对图像进行亮度和对比度校正。Infinigen 后处理默认用它做轻量颜色修正。

**创建方式**：

```python
corrected = nw.new_node(
    Nodes.BrightContrast,
    input_kwargs={"Image": source, "Bright": 1.0, "Contrast": 4.0},
).outputs["Image"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.BrightContrast`，对应 `CompositorNodeBrightContrast` |
| `input_kwargs` | `Image`、`Bright`、`Contrast` |
| `attrs` | 可选 `use_premultiply: bool`，默认 `True` |

**Input Sockets**：`Image`；`Bright`（0 不改变亮度）；`Contrast`（0 不改变对比度）。

**Output Sockets**：`Image`。连续颜色校正时先调整曝光，再做小幅亮度/对比度修正，避免大值导致高光或暗部过度裁切。

## `Nodes.Exposure`

**作用**：按曝光级调整图像强度，比直接增加 Bright 更适合整体曝光补偿。

**创建方式**：

```python
exposed = nw.new_node(
    Nodes.Exposure,
    input_kwargs={"Image": source, "Exposure": 0.5},
).outputs["Image"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Exposure`，对应 `CompositorNodeExposure` |
| `input_kwargs` | `Image`、`Exposure` |

**Input Sockets**：`Image`；`Exposure`（0 保持原图，正值增亮，负值压暗）。

**Output Sockets**：`Image`。这是 runner 级画面处理，不应被单个资产用于补偿自身材质过暗或过亮。

## `Nodes.CompSeparateColor`

**作用**：把图像拆成三个颜色分量和 Alpha，供通道交换、单通道处理或 pass 编码使用。

**创建方式**：

```python
channels = nw.new_node(
    Nodes.CompSeparateColor,
    input_args=[source],
    attrs={"mode": "RGB"},
)
red = channels.outputs[0]
alpha = channels.outputs[3]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CompSeparateColor`，对应 `CompositorNodeSeparateColor` |
| `input_args` / `input_kwargs` | `[source]` 或 `{"Image": source}` |
| `attrs` | `mode`：`RGB`、`HSV`、`HSL`、`YCC`、`YUV`；`YCC` 可再设 `ycc_mode`：`ITUBT601`、`ITUBT709`、`JFIF` |

**Input Sockets**：`Image`。

**Output Sockets**：索引 0-2 的语义随 `mode` 依次为 RGB、HSV、HSL、Y/Cb/Cr 或 Y/U/V；索引 3 始终为 Alpha。

Blender 4.2 Python RNA 中前三个 socket 的 `name` 仍可能显示为 `Red`、`Green`、`Blue`，即使 `mode` 不是 RGB。非 RGB 模式应按索引读取，避免把 RNA 名称误认为实际颜色语义。

## `Nodes.CompCombineColor`

**作用**：把三个颜色分量和 Alpha 重新组合为图像，是 Separate Color 的逆操作。

**创建方式**：

```python
combined = nw.new_node(
    Nodes.CompCombineColor,
    input_args=[red, green, blue, alpha],
    attrs={"mode": "RGB"},
).outputs["Image"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CompCombineColor`，对应 `CompositorNodeCombineColor` |
| `input_args` | 按 `[分量1, 分量2, 分量3, Alpha]` 传入 |
| `attrs` | `mode` 和 `ycc_mode` 取值与 `CompSeparateColor` 相同 |

**Input Sockets**：索引 0-2 的语义由 `mode` 决定；索引 3 为 `Alpha`。

**Output Sockets**：`Image`。Blender 4.2 RNA 的输入名称仍可能保持 `Red`、`Green`、`Blue`；非 RGB 模式优先使用 `input_args` 或整数索引。

## `Nodes.CompositorMixRGB`

**作用**：按 factor 和 blend mode 混合两幅图像。不要与 Shader/Geometry 的 `Nodes.Mix` 或 shader closure 的 `Nodes.MixShader` 混用。

**创建方式**：

```python
mixed = nw.new_node(
    Nodes.CompositorMixRGB,
    input_kwargs={"Fac": mask, 1: image_a, 2: image_b},
    attrs={"blend_type": "ADD", "use_clamp": False},
).outputs["Image"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CompositorMixRGB`，对应 `CompositorNodeMixRGB` |
| `input_args` | 可按 `[Fac, image_a, image_b]` 传入 |
| `input_kwargs` | `Fac`；两个同名 `Image` 输入使用索引 `1`、`2` |
| `attrs` | `blend_type`、可选 `use_alpha`、`use_clamp` |

**Input Sockets**：`Fac`；`Image`（index 1）；`Image`（index 2）。

**Output Sockets**：`Image`。常用 `blend_type` 为 `MIX`、`MULTIPLY`、`ADD`、`SUBTRACT`、`SCREEN`、`OVERLAY`、`DIFFERENCE`；Blender 4.2 还支持 `DARKEN`、`BURN`、`LIGHTEN`、`DODGE`、`SOFT_LIGHT`、`LINEAR_LIGHT`、`EXCLUSION`、`DIVIDE`、`HUE`、`SATURATION`、`COLOR`、`VALUE`。

## `Nodes.LensDistortion`

**作用**：模拟镜头几何畸变和色散。Infinigen 使用 `Dispersion` 添加轻微色差。

**创建方式**：

```python
distorted = nw.new_node(
    Nodes.LensDistortion,
    input_kwargs={"Image": source, "Distortion": 0.0, "Dispersion": 0.01},
    attrs={"use_fit": True},
).outputs["Image"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.LensDistortion`，对应 `CompositorNodeLensdist` |
| `input_kwargs` | `Image`、`Distortion`、`Dispersion` |
| `attrs` | 可选 `use_projector`、`use_jitter`、`use_fit` |

**Input Sockets**：`Image`；`Distortion`（几何镜头畸变）；`Dispersion`（不同颜色通道的色散）。

**Output Sockets**：`Image`。畸变和色散容易产生黑边或明显伪影，应从接近 0 的小值开始；`use_fit=True` 可缩放结果以减少边缘缺失，但会改变取景范围。

## `Nodes.Glare`

**作用**：从超过阈值的高亮像素生成辉光、光斑或星芒。

**创建方式**：

```python
glare = nw.new_node(
    Nodes.Glare,
    input_kwargs={"Image": source},
    attrs={
        "glare_type": "GHOSTS",
        "quality": "MEDIUM",
        "threshold": 0.5,
        "mix": -0.99,
    },
).outputs["Image"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Glare`，对应 `CompositorNodeGlare` |
| `input_kwargs` | `Image` |
| `attrs` | `glare_type`、`quality` 及下表中类型相关属性 |

**Input Sockets**：`Image`。

**Output Sockets**：`Image`。

| 属性 | 作用 |
| --- | --- |
| `glare_type` | `BLOOM`、`GHOSTS`、`STREAKS`、`FOG_GLOW`、`SIMPLE_STAR` |
| `quality` | `HIGH`、`MEDIUM`、`LOW`；低质量使用较低分辨率计算 |
| `threshold` | 参与效果的亮度阈值 |
| `mix` | `-1` 仅原图，`0` 原图与效果混合，`1` 仅效果 |
| `size` | `BLOOM`/`FOG_GLOW` 范围，Blender 4.2 为 `1-9` |
| `streaks`、`angle_offset`、`fade` | `STREAKS` 的条纹数、角度和衰减 |
| `iterations`、`color_modulation` | 迭代次数和色彩调制，主要用于 `GHOSTS`/`STREAKS` |
| `use_rotate_45` | `SIMPLE_STAR` 旋转 45° |

`mix=-0.99` 是 Infinigen 的轻量 Ghosts 配置，几乎保留原图；不要把高强度 Glare 当作资产发光材质的替代品。

## `Nodes.Composite`

**作用**：把图像写入当前渲染的最终 Composite/Render Result。

**创建方式**：

```python
nw.new_node(
    Nodes.Composite,
    input_kwargs={"Image": source},
    attrs={"use_alpha": True},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Composite`，对应 `CompositorNodeComposite` |
| `input_kwargs` | `Image`、可选 `Alpha` |
| `attrs` | 可选 `use_alpha: bool` |

**Input Sockets**：`Image`；可选 `Alpha`。

**Output Sockets**：无。该节点是 singleton；`show=False` 的中间后处理链不应重新连接它，否则会覆盖最终画面。

## `Nodes.Viewer`

**作用**：把中间结果写入 Blender 的 `Viewer Node` 图像，供调试查看；不会替代 Composite 或保存文件。

**创建方式**：

```python
nw.new_node(
    Nodes.Viewer,
    input_kwargs={"Image": source},
    attrs={"use_alpha": True},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Viewer`，对应 `CompositorNodeViewer` |
| `input_kwargs` | `Image`、可选 `Alpha` |
| `attrs` | 可选 `use_alpha: bool` |

**Input Sockets**：`Image`；可选 `Alpha`。

**Output Sockets**：无。该节点是 singleton，只适合交互调试；无界面批处理不能依赖 Viewer 作为持久输出。

## `Nodes.OutputFile`

**作用**：在渲染时把图像或 render passes 写入磁盘，可创建多个动态输入 slot。

**创建方式**：

```python
output = nw.new_node(
    Nodes.OutputFile,
    attrs={
        "base_path": str(frames_folder),
        "format.file_format": "OPEN_EXR",
        "format.color_mode": "RGB",
    },
)

depth_input = output.file_slots.new("Depth")
output.file_slots[depth_input.name].path = "Depth"
nw.links.new(depth_pass, depth_input)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.OutputFile`，对应 `CompositorNodeOutputFile` |
| `attrs` | `base_path`；嵌套属性如 `format.file_format`、`format.color_mode`、`format.color_depth` |

**Input Sockets**：默认有 `Image`；调用 `file_slots.new(name)` 后增加同名动态图像输入。

**Output Sockets**：无。

`file_slots.new(name)` 返回新建的 input socket，而 `file_slots[...]` 中的 slot 对象保存 `path`；不要访问不存在的 `slot.name`。`base_path` 指向输出目录，slot 的 `path` 控制子路径或文件名前缀，实际文件名还会按渲染帧编号生成。

Infinigen 分别创建 PNG 和 `OPEN_EXR` 节点，并为 material index 等数据 pass 选择 EXR。文件格式、颜色模式、位深和 pass 数据类型必须匹配；创建节点本身不会立即写文件，副作用发生在渲染时，因此该节点只能由 runner 配置。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 在资产 node function 中创建 Compositor 节点 | 交给 `core/rendering/render.py` 或外层 runner |
| 读取未启用的 Render Layers pass | 先启用对应 `view_layer.use_pass_*`，再查询输出 socket |
| 非 RGB Separate/Combine 仍按 `Red` 等名称理解通道 | 按 socket 索引和 `mode` 解释语义 |
| 用字符串 `"Image"` 设置 MixRGB 的两个图像 | 使用索引 `1`、`2` 或 `input_args` |
| 重复创建 Composite/Viewer 期待多个结果 | singleton 会复用；多文件输出使用多个 `OutputFile` |
| 创建 Output File 后立即查找磁盘文件 | 它只在渲染时写入，并自动附加帧编号 |
| 用 Glare 补偿错误的发光材质或曝光 | 先修正材质、灯光和曝光，再使用轻量后处理 |

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/core/rendering/render.py`
- [Blender 4.2 Compositor Nodes](https://docs.blender.org/manual/en/4.2/compositing/types/index.html)
- [Blender 4.2 Render Layers](https://docs.blender.org/manual/en/4.2/compositing/types/input/scene/render_layers.html)
- [Blender 4.2 Separate Color](https://docs.blender.org/manual/en/4.2/compositing/types/color/mix/separate_color.html)
- [Blender 4.2 Glare](https://docs.blender.org/manual/en/4.2/compositing/types/filter/glare.html)
