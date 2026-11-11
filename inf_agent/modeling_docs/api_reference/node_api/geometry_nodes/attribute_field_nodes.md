# Attribute 与 Field 节点

本文档覆盖当前几何上下文中的属性读写、字段统计、domain 转换、模糊、索引求值和累计。参数表只列当前节点实际需要的 `new_node` 参数；跨几何采样见 `geometry_sampling_nodes.md`。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.CaptureAttribute` | 在当前几何上保存匿名 attribute |
| `Nodes.AttributeStatistic` | 统计整个 domain 上的字段 |
| `Nodes.DomainSize` | 获取 mesh、curve 等组件的元素数量 |
| `Nodes.StoreNamedAttribute` | 把字段写入具名 attribute |
| `Nodes.NamedAttribute` | 按名称读取 attribute |
| `Nodes.EvaluateonDomain` | 在指定 domain 求值并自动转换到使用端 domain |
| `Nodes.BlurAttribute` | 在相邻元素间平滑字段 |
| `Nodes.FieldAtIndex` | 按索引读取当前字段上下文中的值 |
| `Nodes.AccumulateField` | 按顺序和分组累计字段 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。

## 共性规则

多数动态节点通过 `attrs={"data_type": ...}` 确定 socket 类型，再用 `input_kwargs` 按名称连接。下表是字段类型词汇，具体节点仅支持其章节列出的子集；Capture Attribute 的原生 Blender API 使用 `capture_items`，见下文及 `socket_attrs_and_compatibility.md`。

| 类型集合 | `data_type` |
| --- | --- |
| 常用字段 | `FLOAT`、`INT`、`FLOAT_VECTOR`、`FLOAT_COLOR`、`BOOLEAN` |
| Rotation / Matrix | `QUATERNION`、`FLOAT4X4` |
| 仅 Store Named Attribute 额外支持 | `BYTE_COLOR`、`FLOAT2`、`INT8` |

常用 mesh domain 为 `POINT`、`EDGE`、`FACE`、`CORNER`；curve 使用 `POINT` 或 `CURVE`，instance 使用 `INSTANCE`。`LAYER` 面向 Grease Pencil，不是静态单体资产的常规选择，但接口仍保留在本页。

## `Nodes.CaptureAttribute`

**作用**：在几何上保存匿名 attribute，使字段能穿过拓扑转换，并继续通过 socket 引用。

**创建方式**：

```python
capture = nw.new_node(
    Nodes.CaptureAttribute,
    input_kwargs={"Geometry": geometry, "Value": position},
    attrs={"data_type": "FLOAT_VECTOR", "domain": "POINT"},
)
geometry = capture.outputs["Geometry"]
captured_position = capture.outputs["Attribute"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CaptureAttribute`，对应 `GeometryNodeCaptureAttribute` |
| `attrs` | `data_type`、`domain` |
| `input_kwargs` | `Geometry`、`Value` |

**Input Sockets**：`Geometry`；`Value` 为 Infinigen 兼容入口，Blender 4.2 创建的动态 socket 名为 `Attribute`。

**Output Sockets**：`Geometry`、`Attribute`（类型由 `data_type` 决定）。

这里的 `attrs["data_type"]` 是 Infinigen 兼容入口，Blender 4.2 原生节点没有 `node.data_type`：直接使用 bpy 时先调用 `capture.capture_items.new("VECTOR", "Attribute")` 创建向量 socket；该 item 的 `data_type` 为 `FLOAT_VECTOR`。颜色对应构造参数 `RGBA` / item 属性 `FLOAT_COLOR`。

必须让后续节点使用这里的 `Geometry` 输出，否则匿名 attribute 不会随另一条几何分支传播。单字段也可用 `geometry, value = nw.capture(geometry, field, attrs={...})`。

## `Nodes.AttributeStatistic`

**作用**：在指定 domain 和 selection 上计算字段的整体统计量。

**创建方式**：

```python
stats = nw.new_node(
    Nodes.AttributeStatistic,
    input_kwargs={"Geometry": geometry, "Selection": selection, "Attribute": position},
    attrs={"data_type": "FLOAT_VECTOR", "domain": "POINT"},
)
center = stats.outputs["Mean"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.AttributeStatistic`，对应 `GeometryNodeAttributeStatistic` |
| `attrs` | `data_type`：仅 `FLOAT`/`FLOAT_VECTOR`；`domain` |
| `input_kwargs` | `Geometry`、`Selection`、`Attribute` |

**Input Sockets**：`Geometry`、`Selection`（Boolean）、`Attribute`（Float 或 Vector）。

**Output Sockets**：`Mean`、`Median`、`Sum`、`Min`、`Max`、`Range`、`Standard Deviation`、`Variance`，类型与 `data_type` 一致。

结果是整份数据的单值，不是逐元素字段。空 selection 的统计结果不应作为可靠尺寸或位置使用。

## `Nodes.DomainSize`

**作用**：返回指定几何组件各 domain 的元素数量。

**创建方式**：

```python
size = nw.new_node(
    Nodes.DomainSize,
    input_kwargs={"Geometry": geometry},
    attrs={"component": "MESH"},
)
face_count = size.outputs["Face Count"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.DomainSize`，对应 `GeometryNodeAttributeDomainSize` |
| `attrs` | `component`：`MESH`、`POINTCLOUD`、`CURVE`、`INSTANCES` |
| `input_kwargs` | `Geometry` |

**Input Sockets**：`Geometry`。

**Output Sockets**：

| `component` | 启用的 Integer 输出 |
| --- | --- |
| `MESH` | `Point Count`、`Edge Count`、`Face Count`、`Face Corner Count` |
| `POINTCLOUD` | `Point Count` |
| `CURVE` | `Point Count`、`Spline Count` |
| `INSTANCES` | `Instance Count` |

## `Nodes.StoreNamedAttribute`

**作用**：把字段写入几何上的具名 attribute，供后续节点、材质或 modifier 外部读取。

**创建方式**：

```python
stored = nw.new_node(
    Nodes.StoreNamedAttribute,
    input_kwargs={
        "Geometry": geometry,
        "Selection": selection,
        "Name": "panel_mask",
        "Value": 1.0,
    },
    attrs={"data_type": "FLOAT", "domain": "FACE"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.StoreNamedAttribute`，对应 `GeometryNodeStoreNamedAttribute` |
| `attrs` | `data_type`、`domain` |
| `input_kwargs` | `Geometry`、`Selection`、`Name`、`Value` |

**Input Sockets**：`Geometry`、`Selection`、`Name`（String）、`Value`（动态类型）。

**Output Sockets**：`Geometry`。

同一 node tree 内传递临时数据优先用 Capture，只有需要跨 nodegroup、材质或 Blender 数据层访问时才命名。名称应使用稳定的 ASCII 标识，并避免覆盖 `position`、`id` 等内建 attribute。

## `Nodes.NamedAttribute`

**作用**：从当前字段上下文的几何中按名称读取 attribute。

**创建方式**：

```python
mask_attr = nw.new_node(
    Nodes.NamedAttribute,
    input_kwargs={"Name": "panel_mask"},
    attrs={"data_type": "FLOAT"},
)
mask = mask_attr.outputs["Attribute"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.NamedAttribute`，对应 `GeometryNodeInputNamedAttribute` |
| `attrs` | `data_type`：常用字段类型或 `QUATERNION`/`FLOAT4X4` |
| `input_kwargs` | `Name` |

**Input Sockets**：`Name`（String）。

**Output Sockets**：`Attribute`（动态类型）、`Exists`（Boolean）。

`data_type` 必须与存储类型一致；缺失时 `Attribute` 返回该类型默认值。需要区分“缺失”和“值为零”时使用 `Exists`。

## `Nodes.EvaluateonDomain`

**作用**：先在指定 domain 求值，再按 Blender 的 domain 插值规则转换到字段使用端。

**创建方式**：

```python
face_value = nw.new_node(
    Nodes.EvaluateonDomain,
    input_kwargs={"Value": point_value},
    attrs={"data_type": "FLOAT", "domain": "FACE"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.EvaluateonDomain`，对应 `GeometryNodeFieldOnDomain` |
| `attrs` | `data_type`：常用字段类型或 `QUATERNION`/`FLOAT4X4`；`domain` |
| `input_kwargs` | `Value` |

**Input Sockets**：`Value`（动态类型）。

**Output Sockets**：`Value`（动态类型）。

节点没有 Geometry input，使用下游节点提供的字段上下文。`Nodes` 成员名固定为 `EvaluateonDomain`，其中 `on` 为小写。

## `Nodes.BlurAttribute`

**作用**：在相邻 mesh 或 curve 元素间重复混合字段，生成平滑权重或颜色。

**创建方式**：

```python
blurred = nw.new_node(
    Nodes.BlurAttribute,
    input_kwargs={"Value": weight, "Iterations": 4, "Weight": 1.0},
    attrs={"data_type": "FLOAT"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.BlurAttribute`，对应 `GeometryNodeBlurAttribute` |
| `attrs` | `data_type`：`FLOAT`、`INT`、`FLOAT_VECTOR`、`FLOAT_COLOR` |
| `input_kwargs` | `Value`、`Iterations`、`Weight` |

**Input Sockets**：`Value`（动态类型）、`Iterations`（Integer）、`Weight`（Float）。

**Output Sockets**：`Value`（动态类型）。

domain 来自下游字段上下文；支持 mesh point/edge/face 和 curve point，不支持 face corner、instance 或 Boolean。迭代次数会直接增加计算量。

## `Nodes.FieldAtIndex`

**作用**：按索引读取当前字段上下文中指定 domain 的值；Blender UI 名称为 Evaluate at Index。

**创建方式**：

```python
previous = nw.new_node(
    Nodes.FieldAtIndex,
    input_kwargs={"Index": previous_index, "Value": field},
    attrs={"data_type": "FLOAT", "domain": "POINT"},
)
value = previous.outputs["Value"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.FieldAtIndex`，对应 `GeometryNodeFieldAtIndex` |
| `attrs` | `data_type`：常用字段类型或 `QUATERNION`/`FLOAT4X4`；`domain` |
| `input_kwargs` | `Index`、`Value` |

**Input Sockets**：`Index`（Integer）、`Value`（动态类型）。

**Output Sockets**：`Value`（动态类型）。

它没有 Geometry input，只能访问当前上下文几何。源几何由显式 socket 提供时改用 `SampleIndex`。

## `Nodes.AccumulateField`

**作用**：按 domain 索引顺序累计字段，并可通过 Group ID 分组独立累计。

**创建方式**：

```python
accumulated = nw.new_node(
    Nodes.AccumulateField,
    input_kwargs={"Value": segment_length, "Group ID": spline_index},
    attrs={"data_type": "FLOAT", "domain": "POINT"},
)
distance_before = accumulated.outputs["Trailing"]
group_length = accumulated.outputs["Total"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.AccumulateField`，对应 `GeometryNodeAccumulateField` |
| `attrs` | `data_type`：`FLOAT`、`INT`、`FLOAT_VECTOR`、`TRANSFORM`；`domain` |
| `input_kwargs` | `Value`、`Group ID` |

**Input Sockets**：`Value`（动态类型）、`Group ID`（Integer）。

**Output Sockets**：`Leading`（含当前元素）、`Trailing`（不含当前元素）、`Total`（该组总和）。

累计顺序由 domain 索引决定，不代表空间距离；几何重排后顺序可能变化。沿曲线累计时通常用 curve/spline 标识作为 Group ID。

## 选择指南

| 需求 | 节点 |
| --- | --- |
| 字段穿过拓扑转换且只在当前几何链使用 | `CaptureAttribute` |
| 数据需要按名称跨 nodegroup、材质或 modifier 使用 | `StoreNamedAttribute` + `NamedAttribute` |
| 在当前上下文按索引读取 | `FieldAtIndex` |
| 自动在 domain 间转换 | `EvaluateonDomain` |
| 统计整个 domain 或分组累计 | `AttributeStatistic` / `AccumulateField` |
| 从显式输入的另一份几何采样 | `geometry_sampling_nodes.md` |

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 创建动态节点后再修改 `data_type` | 在同一次 `new_node` 调用的 `attrs` 中设置 |
| Capture 后继续使用原始 Geometry 分支 | 使用 Capture 的 `Geometry` 输出 |
| 用 Named Attribute 读取未验证名称 | 必要时检查 `Exists` |
| 用 Field at Index 读取另一份几何 | 改用 `geometry_sampling_nodes.md` 中的 Sample Index |
| 把 RNA 列出的所有 attribute 类型都传给节点 | 使用本文各节点明确列出的实际可设置类型 |

## 相关文档

- `new_node` 与连接规则：`../node_wrangler_usage.md`
- 动态 socket 与兼容层：`../socket_attrs_and_compatibility.md`
- 跨几何字段采样：`geometry_sampling_nodes.md`
- Position、Normal、Index、ID：`geometry_input_info_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/core/nodes/compatibility.py`
- `infinigen/core/surface.py`
- [Blender 4.2 Attribute Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/attribute/index.html)
- [Blender 4.2 Field Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/utilities/field/index.html)
- [Blender 4.2 Python API Change Log](https://docs.blender.org/api/4.2/change_log.html)
