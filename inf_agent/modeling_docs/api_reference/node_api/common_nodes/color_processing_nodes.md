# 颜色处理节点

本文档覆盖颜色混合、映射、调整、拆分和组合节点。参数表只列当前节点实际使用的 `new_node` 参数；通用语义见 `../node_wrangler_usage.md`。

## 快速选择

| 节点 | 作用 | Node tree | 建议 |
| --- | --- | --- | --- |
| `Nodes.Mix` | 混合 Float、Vector、Color 或 Rotation | Shader、Geometry | 新代码首选 |
| `Nodes.ColorRamp` | 将 Float 映射为颜色 | Shader、Geometry | 新代码首选 |
| `Nodes.RGBCurve` | 按曲线调整颜色通道 | Shader、Geometry | 非线性颜色校正 |
| `Nodes.HueSaturationValue` | 调整 HSV | Shader | Shader 颜色调整 |
| `Nodes.BlackBody` | 将色温转换为颜色 | Shader、Geometry | 灯光和发光颜色 |
| `Nodes.SeparateColor` / `Nodes.CombineColor` | 拆分/组合 RGB、HSV、HSL | Shader | Shader 首选 |
| `Nodes.FunctionCombineColor` | 组合颜色及 Alpha | Geometry | Geometry 首选 |
| `Nodes.MixRGB` | 旧版颜色混合 | Shader、Geometry | 仅兼容旧代码 |
| `Nodes.SeparateRGB` / `Nodes.CombineRGB` | 旧版 RGB 拆分/组合 | Shader、Geometry | 仅兼容或补足 Geometry |
| `Nodes.CombineHSV` | 旧版 HSV 组合 | Shader | 仅兼容旧代码 |

接口以 Blender 4.2 为准。新代码使用命名 `input_kwargs`；带 `mode` 的 Color 节点即使处于 HSV/HSL 模式，Python socket key 仍为 `Red`、`Green`、`Blue`。

## `Nodes.Mix`

**作用**：根据 `Factor` 在 `A` 和 `B` 间混合数据；Color 模式支持 blend mode。

**创建方式**：

```python
mixed = nw.new_node(
    Nodes.Mix,
    input_kwargs={"Factor": mask, "A": color_a, "B": color_b},
    attrs={"data_type": "RGBA", "blend_type": "MIX"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Mix`，对应 `ShaderNodeMix` |
| `attrs` | `data_type`；按需设置 `blend_type`、`factor_mode`、`clamp_factor`、`clamp_result` |
| `input_kwargs` | `Factor`、`A`、`B` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Factor` | Float；Vector 非统一模式下为 Vector | `0` 选择 `A`，`1` 选择 `B` |
| `A` / `B` | 由 `data_type` 决定 | 待混合的两项 |

**Output Sockets**：`Result`，类型由 `data_type` 决定。

`data_type` 可为 `FLOAT`、`VECTOR`、`RGBA`；`ROTATION` 仅用于 Geometry。`factor_mode` 只影响 Vector。Color 常用 `blend_type` 包括 `MIX`、`MULTIPLY`、`ADD`、`SUBTRACT`、`SCREEN`、`OVERLAY`、`DIFFERENCE`、`HUE`、`SATURATION`、`COLOR`、`VALUE`。

使用 `clamp_factor` 限制 Factor，Color 结果需要限制时设置 `clamp_result`。不要复制源码中的 `6`、`7`、`outputs[2]` 等动态 socket 索引。

## `Nodes.ColorRamp`

**作用**：用颜色控制点将 Float 映射为 Color 和 Alpha，常用于 mask、色带和阈值。

**创建方式**：

```python
ramp = nw.new_node(Nodes.ColorRamp, input_kwargs={"Fac": factor})
ramp.color_ramp.elements[0].color = (0.02, 0.03, 0.04, 1.0)
ramp.color_ramp.elements[1].color = (0.7, 0.75, 0.8, 1.0)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ColorRamp`，对应 `ShaderNodeValToRGB` |
| `input_kwargs` | `Fac`：查询色带的 Float |

**Input Sockets**：`Fac`（Float）。

**Output Sockets**：`Color`（Color）、`Alpha`（Float）。

| 嵌套配置 | 可用值或作用 |
| --- | --- |
| `color_ramp.elements[i].position/color` | 设置控制点；增加控制点使用 `elements.new(position)` |
| `color_ramp.interpolation` | `LINEAR`、`EASE`、`CONSTANT`、`CARDINAL`、`B_SPLINE` |
| `color_ramp.color_mode` | `RGB`、`HSV`、`HSL` |
| `color_ramp.hue_interpolation` | `NEAR`、`FAR`、`CW`、`CCW` |

已有 positions/colors 列表时可使用 `node_utils.build_color_ramp(...)`；该 helper 的 `mode` 默认是 `HSV`。

## `Nodes.RGBCurve`

**作用**：通过 Combined、Red、Green、Blue 四条曲线进行非线性颜色校正。

**创建方式**：

```python
curve = nw.new_node(
    Nodes.RGBCurve,
    input_kwargs={"Fac": 1.0, "Color": source_color},
)
node_utils.assign_curve(
    curve.mapping.curves[0],
    [(0.0, 0.0), (0.4, 0.3), (1.0, 1.0)],
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.RGBCurve`，对应 `ShaderNodeRGBCurve` |
| `input_kwargs` | `Fac`：影响强度；`Color`：待调整颜色 |

**Input Sockets**：`Fac`（Float）、`Color`（Color）。

**Output Sockets**：`Color`（Color）。

`mapping.curves[0:4]` 依次为 Combined、Red、Green、Blue。使用 `node_utils.assign_curve(curve, points, handles=None)` 配置 `(input, output)` 控制点。

## `Nodes.HueSaturationValue`

**作用**：在 HSV 色彩模型中调整 Shader 颜色。

**创建方式**：

```python
adjusted = nw.new_node(
    Nodes.HueSaturationValue,
    input_kwargs={
        "Hue": 0.5,
        "Saturation": 0.8,
        "Value": 1.1,
        "Fac": mask,
        "Color": source_color,
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.HueSaturationValue`，对应 `ShaderNodeHueSaturation` |
| `input_kwargs` | `Hue`、`Saturation`、`Value`、`Fac`、`Color` |

**Input Sockets**：`Hue=0.5`、`Saturation=1`、`Value=1` 表示不改变对应分量；`Fac` 控制整体影响。

**Output Sockets**：`Color`（Color）。

该节点仅用于 Shader tree；组合 HSV 分量应使用 `CombineColor`。

## `Nodes.BlackBody`

**作用**：将 Kelvin 色温转换为近似黑体辐射颜色。

**创建方式**：

```python
blackbody = nw.new_node(
    Nodes.BlackBody,
    input_kwargs={"Temperature": 4700.0},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.BlackBody`，对应 `ShaderNodeBlackbody` |
| `input_kwargs` | `Temperature`：Kelvin 色温 |

**Input Sockets**：`Temperature`（Float）；低温偏暖，高温偏冷。

**Output Sockets**：`Color`（Color）。

该节点可用于 Shader 和 Geometry tree。它只生成颜色，发光效果还需连接 `Emission` 等节点。

## `Nodes.SeparateColor`

**作用**：在 Shader tree 中按 RGB、HSV 或 HSL 拆分颜色。

**创建方式**：

```python
separated = nw.new_node(
    Nodes.SeparateColor,
    input_kwargs={"Color": source_color},
    attrs={"mode": "HSV"},
)
hue = separated.outputs["Red"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SeparateColor`，对应 `ShaderNodeSeparateColor` |
| `attrs` | `mode`：`RGB`、`HSV` 或 `HSL` |
| `input_kwargs` | `Color` |

**Input Sockets**：`Color`（Color）。

**Output Sockets**：

| Socket key | `RGB` | `HSV` | `HSL` |
| --- | --- | --- | --- |
| `Red` | Red | Hue | Hue |
| `Green` | Green | Saturation | Saturation |
| `Blue` | Blue | Value | Lightness |

## `Nodes.CombineColor`

**作用**：在 Shader tree 中按 RGB、HSV 或 HSL 组合颜色。

**创建方式**：

```python
combined = nw.new_node(
    Nodes.CombineColor,
    input_kwargs={"Red": hue, "Green": saturation, "Blue": value},
    attrs={"mode": "HSV"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CombineColor`，对应 `ShaderNodeCombineColor` |
| `attrs` | `mode`：`RGB`、`HSV` 或 `HSL` |
| `input_kwargs` | `Red`、`Green`、`Blue`；语义与 `SeparateColor` 的输出表相同 |

**Input Sockets**：`Red`、`Green`、`Blue`（Float）。

**Output Sockets**：`Color`（Color）。

该 Shader 版本没有 Alpha input。

## `Nodes.FunctionCombineColor`

**作用**：在 Geometry tree 中组合 RGB、HSV 或 HSL，并可设置 Alpha。

**创建方式**：

```python
combined = nw.new_node(
    Nodes.FunctionCombineColor,
    input_kwargs={
        "Red": hue,
        "Green": saturation,
        "Blue": value,
        "Alpha": 1.0,
    },
    attrs={"mode": "HSV"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.FunctionCombineColor`，对应 `FunctionNodeCombineColor` |
| `attrs` | `mode`：`RGB`、`HSV` 或 `HSL` |
| `input_kwargs` | `Red`、`Green`、`Blue`、可选 `Alpha` |

**Input Sockets**：`Red`、`Green`、`Blue`、`Alpha`（Float）。

**Output Sockets**：`Color`（Color）。

## `Nodes.MixRGB`

**作用**：旧版 Mix RGB；默认兼容模式将其转换为 `Nodes.Mix` 的 Color 模式。

**创建方式**：

```python
mixed = nw.new_node(
    Nodes.MixRGB,
    input_kwargs={"Fac": mask, "Color1": color_a, "Color2": color_b},
    attrs={"blend_type": "MULTIPLY"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MixRGB`，对应 `ShaderNodeMixRGB`（legacy） |
| `input_kwargs` | `Fac`、`Color1`、`Color2` 映射为 `Factor`、`A`、`B` |
| `attrs` | `blend_type`；兼容层补充 `data_type="RGBA"` |
| `compat_mode` | 默认 `True`，返回实际的 `Nodes.Mix` |

**Input Sockets**：兼容调用使用 `Fac`、`Color1`、`Color2`。

**Output Sockets**：默认兼容模式为 `Result`；关闭兼容时原始节点为 `Color`。

新代码直接使用 `Nodes.Mix`。旧 `use_clamp` 应改为 `clamp_result`。

## `Nodes.SeparateRGB`

**作用**：旧版 RGB-only 拆分节点。

**创建方式**：

```python
separated = nw.new_node(
    Nodes.SeparateRGB,
    input_kwargs={"Image": source_color},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SeparateRGB`，对应 `ShaderNodeSeparateRGB` |
| `input_kwargs` | `Image` |

**Input Sockets**：`Image`（Color）。

**Output Sockets**：`R`、`G`、`B`（Float）。

可用于 Shader 和 Geometry。`node_info.py` 列出的 `mode` 在 Blender 4.2 中不存在，不要设置。

## `Nodes.CombineRGB`

**作用**：旧版 RGB-only 组合节点。

**创建方式**：

```python
combined = nw.new_node(
    Nodes.CombineRGB,
    input_kwargs={"R": red, "G": green, "B": blue},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CombineRGB`，对应 `ShaderNodeCombineRGB` |
| `input_kwargs` | `R`、`G`、`B` |

**Input Sockets**：`R`、`G`、`B`（Float）。

**Output Sockets**：`Image`（Color）。

可用于 Shader 和 Geometry。不要设置 `node_info.py` 中过时的 `mode`；新代码使用对应的 Combine Color。

## `Nodes.CombineHSV`

**作用**：旧版 Shader HSV-only 组合节点。

**创建方式**：

```python
combined = nw.new_node(
    Nodes.CombineHSV,
    input_kwargs={"H": hue, "S": saturation, "V": value},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CombineHSV`，对应 `ShaderNodeCombineHSV` |
| `input_kwargs` | `H`、`S`、`V` |

**Input Sockets**：`H`、`S`、`V`（Float）。

**Output Sockets**：`Color`（Color）。

新代码使用 `CombineColor`，设置 `mode="HSV"`，并通过 `Red`、`Green`、`Blue` 传入 H、S、V。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 为 `Mix` 使用数字 socket 索引 | 设置 `data_type` 后使用 `Factor`、`A`、`B`、`Result` |
| 把 Color Ramp 控制点放入 `input_kwargs` | 修改 `color_ramp.elements` 或使用 `build_color_ramp` |
| 在 Geometry tree 创建 `SeparateColor` / `CombineColor` | 使用 tree 支持的 legacy RGB 节点或 `FunctionCombineColor` |
| HSV/HSL 模式使用 `Hue` 等 socket key | 仍使用 `Red`、`Green`、`Blue` |
| 给 `SeparateRGB` / `CombineRGB` 设置 `mode` | Blender 4.2 中不存在该属性 |

## 相关文档

- `new_node` 参数：`../node_wrangler_usage.md`
- 动态 socket 与兼容：`../socket_attrs_and_compatibility.md`
- 数学节点：`math_logic_nodes.md`
- 程序纹理：`texture_nodes.md`
- Principled Shader：`../shader_nodes/principled_bsdf_node.md`
- 专用 BSDF 与 Shader 混合：`../shader_nodes/surface_bsdf_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/core/nodes/node_utils.py`
- `infinigen/core/nodes/compatibility.py`
- [Blender 4.2 Mix Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/converter/mix.html)
- [Blender 4.2 Color Ramp Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/converter/color_ramp.html)
- [Blender 4.2 RGB Curves Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/color/rgb_curves.html)
- [Blender 4.2 Combine/Separate Color](https://docs.blender.org/manual/en/4.2/render/shader_nodes/converter/combine_color.html)
- [Blender 4.2 Hue/Saturation/Value](https://docs.blender.org/manual/en/4.2/render/shader_nodes/color/hue_saturation.html)
- [Blender 4.2 Blackbody](https://docs.blender.org/manual/en/4.2/render/shader_nodes/converter/blackbody.html)
