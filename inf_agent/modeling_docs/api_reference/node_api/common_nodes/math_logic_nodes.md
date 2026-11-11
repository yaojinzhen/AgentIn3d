# 数学与逻辑节点

本文档覆盖标量/向量运算、范围映射、比较、逻辑和条件分支节点。参数表只列当前节点实际使用的 `new_node` 参数；通用语义见 `../node_wrangler_usage.md`。

## 快速选择

| 节点 | 作用 | Node tree |
| --- | --- | --- |
| `Nodes.VectorMath` | 向量运算、距离、长度和点积 | Shader、Geometry |
| `Nodes.Math` | 标量算术、比较、取整和三角运算 | Shader、Geometry |
| `Nodes.MapRange` | 将 Float/Vector 从一个区间映射到另一区间 | Shader、Geometry |
| `Nodes.BooleanMath` | Boolean 逻辑组合 | Geometry |
| `Nodes.Compare` | 类型化比较并输出 Boolean | Geometry |
| `Nodes.FloatToInt` | Float 转 Integer | Geometry |
| `Nodes.Clamp` | 将 Float 限制在区间内 | Shader、Geometry |
| `Nodes.Invert` | 反转 Color | Shader |
| `Nodes.FloatCurve` | 用曲线非线性映射 Float | Shader、Geometry |
| `Nodes.Switch` | 根据 Boolean 选择两项之一 | Geometry |

接口以 Blender 4.2 为准。`Math`、`VectorMath` 和 `BooleanMath` 有多个同名 inputs，优先使用 `input_args`；其余节点优先使用命名 `input_kwargs`。

## `Nodes.VectorMath`

**作用**：执行向量算术、几何关系和逐分量函数。

**创建方式**：

```python
offset = nw.new_node(
    Nodes.VectorMath,
    input_args=[position, delta],
    attrs={"operation": "ADD"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.VectorMath`，对应 `ShaderNodeVectorMath` |
| `attrs` | `operation`：向量运算类型 |
| `input_args` | 按当前 operation 的 socket 顺序传入参数 |

**Input Sockets**：由 `operation` 决定：

| 输入形式 | `operation` | 输出 |
| --- | --- | --- |
| 1 个 Vector | `NORMALIZE`、`ABSOLUTE`、`FLOOR`、`CEIL`、`FRACTION`、`SINE`、`COSINE`、`TANGENT` | `Vector` |
| 2 个 Vector | `ADD`、`SUBTRACT`、`MULTIPLY`、`DIVIDE`、`CROSS_PRODUCT`、`PROJECT`、`REFLECT`、`MINIMUM`、`MAXIMUM`、`MODULO`、`SNAP` | `Vector` |
| 3 个 Vector | `MULTIPLY_ADD`、`FACEFORWARD`、`WRAP` | `Vector` |
| Vector + Scale | `SCALE` | `Vector` |
| 2 个 Vector + Scale | `REFRACT` | `Vector` |
| 2 个 Vector | `DOT_PRODUCT`、`DISTANCE` | `Value`（Float） |
| 1 个 Vector | `LENGTH` | `Value`（Float） |

**Output Sockets**：见上表；大多数操作输出 `Vector`，`DOT_PRODUCT`、`DISTANCE`、`LENGTH` 输出 `Value`。

`SCALE` 可安全使用 `input_kwargs={"Vector": value, "Scale": factor}`；其他重复命名的 `Vector` sockets 使用 `input_args` 更明确。常用 helper 包括 `nw.vector_math(...)`、`nw.scale(...)` 和 `nw.dot(...)`。

## `Nodes.Math`

**作用**：执行标量算术、比较、取整和三角函数。

**创建方式**：

```python
scaled = nw.new_node(
    Nodes.Math,
    input_args=[value, 2.0],
    attrs={"operation": "MULTIPLY"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Math`，对应 `ShaderNodeMath` |
| `attrs` | `operation`；可选 `use_clamp: bool` |
| `input_args` | 按 operation 所需数量传入 Float |

**Input Sockets**：

| 参数数 | `operation` |
| --- | --- |
| 1 | `SQRT`、`INVERSE_SQRT`、`ABSOLUTE`、`EXPONENT`、`SIGN`、`ROUND`、`FLOOR`、`CEIL`、`TRUNC`、`FRACT`、`SINE`、`COSINE`、`TANGENT`、`ARCSINE`、`ARCCOSINE`、`ARCTANGENT`、`SINH`、`COSH`、`TANH`、`RADIANS`、`DEGREES` |
| 2 | `ADD`、`SUBTRACT`、`MULTIPLY`、`DIVIDE`、`POWER`、`LOGARITHM`、`MINIMUM`、`MAXIMUM`、`LESS_THAN`、`GREATER_THAN`、`MODULO`、`FLOORED_MODULO`、`SNAP`、`PINGPONG`、`ARCTAN2` |
| 3 | `MULTIPLY_ADD`、`COMPARE`、`SMOOTH_MIN`、`SMOOTH_MAX`、`WRAP` |

**Output Sockets**：`Value`（Float）。`LESS_THAN`、`GREATER_THAN` 和 `COMPARE` 也输出 `0.0`/`1.0`，不是 Boolean socket。

`use_clamp=True` 将结果限制到 `[0, 1]`。Geometry 中需要类型正确的 Boolean 时优先使用 `Compare`；Shader tree 中没有 `Compare`，可使用 Math 比较。常用 helper 为 `nw.math(...)`、`nw.scalar_add(...)`、`nw.scalar_multiply(...)` 等。

## `Nodes.MapRange`

**作用**：把值从 `[From Min, From Max]` 映射到 `[To Min, To Max]`。

**创建方式**：

```python
mapped = nw.new_node(
    Nodes.MapRange,
    input_kwargs={
        "Value": value,
        "From Min": 0.2,
        "From Max": 0.8,
        "To Min": 0.0,
        "To Max": 1.0,
    },
    attrs={"data_type": "FLOAT", "interpolation_type": "LINEAR"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MapRange`，对应 `ShaderNodeMapRange` |
| `attrs` | `data_type`、`interpolation_type`、`clamp` |
| `input_kwargs` | 命名设置值和输入/输出区间 |

**Input Sockets**：

| `data_type` | 基本 inputs | 附加 input |
| --- | --- | --- |
| `FLOAT` | `Value`、`From Min`、`From Max`、`To Min`、`To Max`（Float） | `STEPPED` 时增加 `Steps` |
| `FLOAT_VECTOR` | `Vector`、`From Min`、`From Max`、`To Min`、`To Max`（Vector） | `STEPPED` 时增加 `Steps` |

**Output Sockets**：`FLOAT` 输出 `Result`；`FLOAT_VECTOR` 输出 `Vector`。

`interpolation_type` 可为 `LINEAR`、`STEPPED`、`SMOOTHSTEP`、`SMOOTHERSTEP`。`clamp=True` 将结果限制在目标区间。输入区间长度不能为零；需要反向映射时交换 `To Min` 和 `To Max`。

## `Nodes.BooleanMath`

**作用**：组合 Geometry Nodes 中的 Boolean 字段。

**创建方式**：

```python
selection = nw.new_node(
    Nodes.BooleanMath,
    input_args=[inside_x, inside_y],
    attrs={"operation": "AND"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.BooleanMath`，对应 `FunctionNodeBooleanMath` |
| `attrs` | `operation`：逻辑运算 |
| `input_args` | `NOT` 传一个 Boolean，其余操作传两个 |

**Input Sockets**：一个或两个同名 `Boolean`。

**Output Sockets**：`Boolean`。

可用 operation：`AND`、`OR`、`NOT`、`NAND`、`NOR`、`XNOR`、`XOR`、`IMPLY`、`NIMPLY`。常用 helper 为 `nw.boolean_math(operation, *values)`。

## `Nodes.Compare`

**作用**：比较两个同类型值，生成 Geometry Nodes Boolean 字段。

**创建方式**：

```python
selected = nw.new_node(
    Nodes.Compare,
    input_kwargs={"A": width, "B": 0.5},
    attrs={"data_type": "FLOAT", "operation": "GREATER_THAN"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Compare`，对应 `FunctionNodeCompare` |
| `attrs` | `data_type`、`operation`；Vector 可设置 `mode` |
| `input_kwargs` | `A`、`B`，按模式增加 `Epsilon`、`C` 或 `Angle` |

**Input Sockets**：可用 socket 和 operation 如下：

| `data_type` | 可用 operation | 附加规则 |
| --- | --- | --- |
| `FLOAT` | `LESS_THAN`、`LESS_EQUAL`、`GREATER_THAN`、`GREATER_EQUAL`、`EQUAL`、`NOT_EQUAL` | 相等比较增加 `Epsilon` |
| `INT` | 同上 | 精确相等，无 `Epsilon` |
| `VECTOR` | 同 Float | 相等比较增加 `Epsilon`；由 `mode` 决定比较方式 |
| `STRING` | `EQUAL`、`NOT_EQUAL` | - |
| `RGBA` | `EQUAL`、`NOT_EQUAL`、`BRIGHTER`、`DARKER` | 相等比较增加 `Epsilon` |

**Output Sockets**：`Result`（Boolean）。

Vector `mode` 可为 `ELEMENT`、`LENGTH`、`AVERAGE`、`DOT_PRODUCT`、`DIRECTION`；`DOT_PRODUCT` 增加 `C`，`DIRECTION` 增加 `Angle`。虽然 Blender RNA 元数据会列出更多类型，Blender 4.2 运行时只接受表中的五种 `data_type`。

## `Nodes.FloatToInt`

**作用**：在 Geometry tree 中把 Float 转为 Integer。

**创建方式**：

```python
count = nw.new_node(
    Nodes.FloatToInt,
    input_kwargs={"Float": value},
    attrs={"rounding_mode": "FLOOR"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.FloatToInt`，对应 `FunctionNodeFloatToInt` |
| `attrs` | `rounding_mode` |
| `input_kwargs` | `Float` |

**Input Sockets**：`Float`（Float）。

**Output Sockets**：`Integer`（Integer）。

`rounding_mode` 可为 `ROUND`、`FLOOR`、`CEILING`、`TRUNCATE`。负数处理中，`FLOOR` 向负无穷，`CEILING` 向正无穷，`TRUNCATE` 向零。

## `Nodes.Clamp`

**作用**：将 Float 限制在 Min 和 Max 之间。

**创建方式**：

```python
clamped = nw.new_node(
    Nodes.Clamp,
    input_kwargs={"Value": value, "Min": 0.0, "Max": 1.0},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Clamp`，对应 `ShaderNodeClamp` |
| `attrs` | 可选 `clamp_type`：`MINMAX` 或 `RANGE` |
| `input_kwargs` | `Value`、`Min`、`Max` |

**Input Sockets**：`Value`、`Min`、`Max`（Float）。

**Output Sockets**：`Result`（Float）。

`MINMAX` 直接按 Min/Max 限制；`RANGE` 在 `Min > Max` 时自动交换边界。通常保持默认 `MINMAX`，并确保 `Min <= Max`。

## `Nodes.Invert`

**作用**：在 Shader tree 中按 `Fac` 混合原颜色和反色。

**创建方式**：

```python
inverted = nw.new_node(
    Nodes.Invert,
    input_kwargs={"Fac": 1.0, "Color": source_color},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Invert`，对应 `ShaderNodeInvert` |
| `input_kwargs` | `Fac`、`Color` |

**Input Sockets**：`Fac`（Float）、`Color`（Color）。

**Output Sockets**：`Color`（Color）。

该节点不能创建在 Geometry tree。反转标量 mask 时使用 `Math` 的 `SUBTRACT`，计算 `1 - value`，避免不必要的 Color 转换。

## `Nodes.FloatCurve`

**作用**：使用可编辑曲线对 Float 做非线性映射。

**创建方式**：

```python
curve = nw.new_node(
    Nodes.FloatCurve,
    input_kwargs={"Factor": 1.0, "Value": value},
)
node_utils.assign_curve(
    curve.mapping.curves[0],
    [(0.0, 0.0), (0.4, 0.2), (1.0, 1.0)],
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.FloatCurve`，对应 `ShaderNodeFloatCurve` |
| `input_kwargs` | `Factor`：曲线影响强度；`Value`：待映射值 |

**Input Sockets**：`Factor`、`Value`（Float）。

**Output Sockets**：`Value`（Float）。

曲线控制点不是 inputs；使用 `node_utils.assign_curve(mapping.curves[0], points, handles=None)` 设置。简单线性区间转换优先使用 `MapRange`。

## `Nodes.Switch`

**作用**：根据 Boolean 输出 `False` 或 `True` 分支中的一项。

**创建方式**：

```python
chosen = nw.new_node(
    Nodes.Switch,
    input_kwargs={"Switch": condition, "False": value_a, "True": value_b},
    attrs={"input_type": "FLOAT"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Switch`，对应 `GeometryNodeSwitch` |
| `attrs` | `input_type`：分支和输出的数据类型 |
| `input_kwargs` | `Switch`、`False`、`True` |

**Input Sockets**：`Switch`（Boolean）；`False`、`True` 的类型由 `input_type` 决定。

**Output Sockets**：`Output`，类型由 `input_type` 决定。

常用 `input_type`：`FLOAT`、`INT`、`BOOLEAN`、`VECTOR`、`ROTATION`、`MATRIX`、`STRING`、`RGBA`、`OBJECT`、`IMAGE`、`GEOMETRY`、`COLLECTION`、`MATERIAL`。`MENU` 只用于相容的 menu interface；Blender 4.2 不接受元数据中残留的 `TEXTURE`。可使用 `nw.switch(...)` 或 `nw.vector_switch(...)`。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 用同名 `input_kwargs` 设置 Math 的多个输入 | 对 Math、VectorMath、BooleanMath 使用 `input_args` |
| 假设所有 VectorMath 都输出 Vector | `DOT_PRODUCT`、`DISTANCE`、`LENGTH` 输出 `Value` |
| Vector Map Range 读取 `outputs["Result"]` | 使用 `outputs["Vector"]` |
| Geometry selection 使用 Math 的比较结果 | 使用输出 Boolean 的 `Compare` |
| Compare 使用 RNA 中列出但运行时不支持的 data type | 限定为 `FLOAT`、`INT`、`VECTOR`、`STRING`、`RGBA` |
| FloatCurve 控制点放入 `input_kwargs` | 创建后调用 `node_utils.assign_curve` |
| Switch 未先设置 `input_type` | 在同一次 `new_node` 调用中通过 `attrs` 设置 |

## 相关文档

- `new_node` 与数学 helper：`../node_wrangler_usage.md`
- 动态 socket 与属性：`../socket_attrs_and_compatibility.md`
- 常量和随机字段：`value_input_nodes.md`
- 向量拆分、组合和旋转：`vector_rotation_mapping_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/core/nodes/node_utils.py`
- [Blender 4.2 Math Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/converter/math.html)
- [Blender 4.2 Vector Math Node](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/utilities/vector/vector_math.html)
- [Blender 4.2 Compare Node](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/utilities/math/compare.html)
- [Blender 4.2 Switch Node](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/utilities/switch.html)
- [Blender 4.2 Clamp Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/converter/clamp.html)
