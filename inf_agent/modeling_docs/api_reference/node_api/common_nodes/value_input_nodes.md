# 数值与输入节点

本文档覆盖常量输入和随机字段节点。每个节点的参数表只列出当前节点实际需要的 `new_node` 参数；通用参数语义见 `../node_wrangler_usage.md`。

## 快速选择

| 节点 | 作用 | Node tree |
| --- | --- | --- |
| `Nodes.Value` | 固定 Float | Shader、Geometry |
| `Nodes.RGB` | 固定 RGBA 颜色 | Shader |
| `Nodes.Boolean` | 固定 Boolean | Geometry |
| `Nodes.Integer` | 固定 Integer | Geometry |
| `Nodes.Vector` | 固定 Vector | Geometry |
| `Nodes.InputColor` | 固定 RGBA 颜色 | Geometry |
| `Nodes.RandomValue` | 随机 Float、Integer、Vector 或 Boolean 字段 | Geometry |

Node tree 限制以项目使用的 Blender 4.2 为准。

## `Nodes.Value`

**作用**：提供固定 Float，适合复用同一标量或添加 label、driver、keyframe。

**创建方式**：

```python
roughness = nw.new_node(Nodes.Value)
roughness.outputs["Value"].default_value = 0.35
value = roughness.outputs["Value"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Value`，对应 `ShaderNodeValue` |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Value` | Float | `default_value` 中保存的固定浮点值 |

简单标量可使用 `nw.new_value(0.35, label="Roughness")`。该节点没有 input，不能用 `input_args` 或 `input_kwargs` 设置数值。

## `Nodes.RGB`

**作用**：提供固定 RGBA 颜色，适合在多个 Shader 节点间复用颜色。

**创建方式**：

```python
base_color = nw.new_node(Nodes.RGB)
base_color.outputs["Color"].default_value = (0.12, 0.32, 0.55, 1.0)
color = base_color.outputs["Color"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.RGB`，对应 `ShaderNodeRGB` |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Color` | Color | `default_value` 中保存的 RGBA 颜色 |

不要用 `attrs={"color": ...}` 设置输出；`Node.color` 是节点编辑器的显示颜色。

## `Nodes.Boolean`

**作用**：提供固定布尔值，常用于 Geometry Nodes 的 selection 或功能开关。

**创建方式**：

```python
enabled = nw.new_node(Nodes.Boolean, attrs={"boolean": True})
mask = enabled.outputs["Boolean"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Boolean`，对应 `FunctionNodeInputBool` |
| `attrs` | `boolean: bool`，设置输出的固定值 |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Boolean` | Boolean | `attrs["boolean"]` 设置的固定值 |

## `Nodes.Integer`

**作用**：提供固定整数，常用于数量、分辨率或索引参数。

**创建方式**：

```python
count = nw.new_node(Nodes.Integer, attrs={"integer": 12})
count_value = count.outputs["Integer"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Integer`，对应 `FunctionNodeInputInt` |
| `attrs` | `integer: int`，设置输出的固定值 |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Integer` | Integer | `attrs["integer"]` 设置的固定值 |

## `Nodes.Vector`

**作用**：提供固定三维向量，常用于方向、位置、旋转或缩放。

**创建方式**：

```python
axis = nw.new_node(
    Nodes.Vector,
    attrs={"vector": (0.0, 0.0, 1.0)},
)
direction = axis.outputs["Vector"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Vector`，对应 `FunctionNodeInputVector` |
| `attrs` | `vector: Vector`，三个 Float 组成的固定向量 |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Vector` | Vector | `attrs["vector"]` 设置的固定向量 |

## `Nodes.InputColor`

**作用**：提供固定 RGBA 颜色，常用于 Geometry Nodes 的颜色 attribute 或材质参数。

**创建方式**：

```python
color = nw.new_node(
    Nodes.InputColor,
    attrs={"value": (0.15, 0.45, 0.8, 1.0)},
)
rgba = color.outputs["Color"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.InputColor`，对应 `FunctionNodeInputColor` |
| `attrs` | `value: Color`，四个 Float 组成的固定 RGBA 颜色 |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Color` | Color | `attrs["value"]` 设置的固定颜色 |

Blender 4.2 将 Python 属性从 `color` 改名为 `value`。当前 `node_transpiler/transpiler.py` 仍包含旧名称，生成的新代码应使用 `value`。

## `Nodes.RandomValue`

**作用**：根据元素 `ID` 和 `Seed` 生成随机字段，适合尺寸扰动、随机偏移和随机 selection。

**创建方式**：

```python
size_jitter = nw.new_node(
    Nodes.RandomValue,
    input_kwargs={"Min": 0.9, "Max": 1.1, "Seed": 17},
    attrs={"data_type": "FLOAT"},
)
value = size_jitter.outputs["Value"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.RandomValue`，对应 `FunctionNodeRandomValue` |
| `attrs` | `data_type`：`FLOAT`、`INT`、`FLOAT_VECTOR` 或 `BOOLEAN` |
| `input_kwargs` | 按名称设置当前 `data_type` 启用的 sockets |

`data_type` 会改变启用的 sockets，因此不要使用依赖 socket 顺序的 `input_args`。

**Input Sockets**：

| `data_type` | Socket | 类型 | 说明 |
| --- | --- | --- | --- |
| `FLOAT` | `Min` / `Max` | Float | 浮点随机范围 |
| `INT` | `Min` / `Max` | Integer | 整数随机范围 |
| `FLOAT_VECTOR` | `Min` / `Max` | Vector | 各分量的随机范围 |
| `BOOLEAN` | `Probability` | Float | 输出 `True` 的概率，范围 `[0, 1]` |
| 全部 | `ID` | Integer | 区分元素；默认使用上下文 `id`，否则回退到 index |
| 全部 | `Seed` | Integer | 切换到另一组确定性随机结果 |

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Value` | 由 `data_type` 决定 | 当前元素的随机值 |

| Helper | 作用 |
| --- | --- |
| `nw.uniform(low, high, seed, data_type="FLOAT")` | 创建 Float、Integer 或 Vector Random Value；`low` 为 iterable 时自动使用 `FLOAT_VECTOR` |
| `nw.bernoulli(prob, seed)` | 创建 Boolean Random Value |

省略 helper 的 `seed` 会在构建 node tree 时调用 `np.random.randint`。需要调用点级别的可复现性时显式传 seed；拓扑重排后仍需稳定结果时，先生成稳定 ID 并连接 `ID`。

## 共性规则

单次使用的值优先直接传给目标节点的 `input_kwargs`：

```python
cube = nw.new_node(Nodes.MeshCube, input_kwargs={"Size": (1.0, 0.8, 0.6)})
```

同一值连接到多个节点、需要明确 socket 类型，或需要 label、driver、keyframe 时，再创建独立常量节点。

- `Nodes.Value` 可创建在 Shader 和 Geometry node tree。
- `Nodes.RGB` 只能创建在 Shader node tree。
- `Nodes.Boolean`、`Nodes.Integer`、`Nodes.Vector`、`Nodes.InputColor` 和 `Nodes.RandomValue` 只能创建在 Geometry node tree。
- Geometry Nodes 中单次 Float 或 Color 通常直接传 Python 常量；需要公开参数时使用 Group Input。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把 `attrs` 中的节点属性误认为 Input Socket | 通过节点参数表和 Input Sockets 分别查询 |
| 用 `input_kwargs` 设置无 input 的常量节点 | 设置对应 `attrs`，或设置 output 的 `default_value` |
| 用 `attrs={"color": ...}` 设置 `Nodes.RGB` | 设置 `outputs["Color"].default_value` |
| 在 Blender 4.2 对 `Nodes.InputColor` 设置 `color` | 使用 `attrs={"value": ...}` |
| 创建 Random Value 后再修改 `data_type` | 在同一次 `new_node` 调用中设置 `attrs={"data_type": ...}` |
| 依赖 Random Value 的数字 socket 索引 | 使用 `Min`、`Max`、`Probability`、`ID`、`Seed` 和 `Value` |

## 相关文档

- `new_node` 通用参数：`../node_wrangler_usage.md`
- Socket 与动态类型：`../socket_attrs_and_compatibility.md`
- 数学和条件处理：`math_logic_nodes.md`
- Geometry 的 ID 与 Index：`../geometry_nodes/geometry_input_info_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/core/nodes/node_transpiler/transpiler.py`
- [Blender 4.2 Constant Input Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/input/constant/index.html)
- [Blender 4.2 Random Value Node](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/utilities/random_value.html)
- [Blender 4.2 Python API Change Log](https://docs.blender.org/api/4.2/change_log.html)
