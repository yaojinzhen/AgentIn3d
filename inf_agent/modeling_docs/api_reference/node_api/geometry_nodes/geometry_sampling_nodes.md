# 几何采样节点

本文档覆盖从显式输入的另一份 geometry 或 mesh 查找、采样和传递字段。当前字段上下文中的 attribute 与 field 操作见 `attribute_field_nodes.md`。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.TransferAttribute` | 已移除的旧采样接口，仅用于识别历史代码 |
| `Nodes.SampleIndex` | 按已知索引从指定几何采样 |
| `Nodes.SampleNearest` | 查找离指定位置最近元素的索引 |
| `Nodes.SampleNearestSurface` | 按最近 mesh 表面位置插值采样 |
| `Nodes.SampleUVSurface` | 按 UV 坐标采样 mesh 字段 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。动态采样节点必须在创建时通过 `attrs={"data_type": ...}` 确定 socket 类型，再用 `input_kwargs` 按名称连接。

常用 `data_type` 为 `FLOAT`、`INT`、`FLOAT_VECTOR`、`FLOAT_COLOR`、`BOOLEAN`；必要时可用 `QUATERNION`、`FLOAT4X4`。

## `Nodes.TransferAttribute`

**作用**：表示 Blender 3.4 前的 Transfer Attribute，当前 Blender 已移除。

**创建方式**：新代码不要创建该节点，按旧 `mapping` 直接改写：

```python
sampled = nw.new_node(
    Nodes.SampleNearestSurface,
    input_kwargs={
        "Mesh": source_geometry,
        "Value": source_value,
        "Sample Position": target_position,
    },
    attrs={"data_type": "FLOAT_VECTOR"},
)
```

| `new_node` 参数 | 历史接口 |
| --- | --- |
| `node_type` | `Nodes.TransferAttribute`，旧 `GeometryNodeAttributeTransfer` |
| `attrs` | `mapping`：`INDEX` 或 `NEAREST_FACE_INTERPOLATED`；`data_type` |
| `input_kwargs` | 旧名称 `Source`、`Attribute`、`Index`/`Source Position` |

**Input Sockets**：Blender 4.2 无实际节点。`INDEX` 对应 `SampleIndex`；`NEAREST_FACE_INTERPOLATED` 对应 `SampleNearestSurface`。

**Output Sockets**：替代节点的 `Value`。

当前 Infinigen 兼容路径会保留已失效的 `mapping` 属性，无法在 Blender 4.2 成功创建替代节点；`NEAREST` 也没有自动转换。生成代码必须直接使用目标 Sample 节点。

## `Nodes.SampleIndex`

**作用**：按索引从显式输入几何的指定 domain 读取字段。

**创建方式**：

```python
sampled = nw.new_node(
    Nodes.SampleIndex,
    input_kwargs={"Geometry": source, "Value": source_position, "Index": index},
    attrs={"data_type": "FLOAT_VECTOR", "domain": "POINT", "clamp": False},
)
value = sampled.outputs["Value"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SampleIndex`，对应 `GeometryNodeSampleIndex` |
| `attrs` | `data_type`、`domain`、`clamp: bool` |
| `input_kwargs` | `Geometry`、`Value`、`Index` |

**Input Sockets**：`Geometry`、`Value`（在该几何上求值）、`Index`（Integer）。

**Output Sockets**：`Value`（动态类型）。

`clamp=False` 时越界索引返回默认值；开启后限制到有效范围。没有 Geometry input、只访问当前上下文时改用 `FieldAtIndex`。

## `Nodes.SampleNearest`

**作用**：在显式输入的 point cloud 或 mesh 中查找离指定位置最近的元素，并返回其索引。

**创建方式**：

```python
nearest = nw.new_node(
    Nodes.SampleNearest,
    input_kwargs={"Geometry": source, "Sample Position": target_position},
    attrs={"domain": "POINT"},
)
nearest_index = nearest.outputs["Index"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SampleNearest`，对应 `GeometryNodeSampleNearest` |
| `attrs` | `domain`：`POINT`、`EDGE`、`FACE`、`CORNER` |
| `input_kwargs` | `Geometry`、`Sample Position` |

**Input Sockets**：`Geometry`、`Sample Position`（Vector）。

**Output Sockets**：`Index`（Integer）。

它只返回离散索引，不返回距离或插值值。`POINT` 支持 point cloud 和 mesh，其余 domain 仅适用于 mesh。通常把 `Index` 连接到 `SampleIndex`；需要连续表面插值时直接使用 `SampleNearestSurface`。不要与无 Geometry input 的 Blender `Index of Nearest` 节点混淆，后者尚未收录在 `Nodes` 枚举中。

## `Nodes.SampleNearestSurface`

**作用**：在源 mesh 上寻找离采样位置最近的表面点，并插值该位置的字段。

**创建方式**：

```python
sampled = nw.new_node(
    Nodes.SampleNearestSurface,
    input_kwargs={
        "Mesh": source_mesh,
        "Value": source_normal,
        "Sample Position": target_position,
    },
    attrs={"data_type": "FLOAT_VECTOR"},
)
normal = sampled.outputs["Value"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SampleNearestSurface`，对应 `GeometryNodeSampleNearestSurface` |
| `attrs` | `data_type`：常用字段类型或 `QUATERNION`/`FLOAT4X4` |
| `input_kwargs` | `Mesh`、`Value`、`Sample Position`；可选 `Group ID`、`Sample Group ID` |

**Input Sockets**：`Mesh`、`Value`、`Sample Position`；两个 Group ID 可把源面和采样点限制在匹配分组中。

**Output Sockets**：`Value`（动态类型）、`Is Valid`（Boolean）。

该节点按 mesh 表面插值，适合 remesh 前后传递位置、法线和 mask；松散点与边不会参与表面采样。

## `Nodes.SampleUVSurface`

**作用**：在源 mesh 的 UV Map 上定位表面，并采样该位置的字段。

**创建方式**：

```python
sampled = nw.new_node(
    Nodes.SampleUVSurface,
    input_kwargs={
        "Mesh": source_mesh,
        "Value": source_color,
        "UV Map": source_uv,
        "Sample UV": target_uv,
    },
    attrs={"data_type": "FLOAT_COLOR"},
)
color = sampled.outputs["Value"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SampleUVSurface`，对应 `GeometryNodeSampleUVSurface` |
| `attrs` | `data_type`：常用字段类型或 `QUATERNION`/`FLOAT4X4` |
| `input_kwargs` | `Mesh`、`Value`、`UV Map`、`Sample UV` |

**Input Sockets**：`Mesh`、`Value`、`UV Map`（源 mesh 的 UV 字段）、`Sample UV`（目标 UV 坐标）。

**Output Sockets**：`Value`（动态类型）、`Is Valid`（Boolean）。

`UV Map` 通常来自 `NamedAttribute` 读取的 UV attribute；重叠 UV 可能命中任一重叠面，超出有效 UV 表面时检查 `Is Valid`。

## 选择指南

| 需求 | 节点 |
| --- | --- |
| 已知源元素索引 | `SampleIndex` |
| 最近离散元素 | `SampleNearest` + `SampleIndex` |
| 最近 mesh 表面的连续插值 | `SampleNearestSurface` |
| 按 UV 对应关系传值 | `SampleUVSurface` |
| 读取旧 Transfer Attribute 代码 | 按 `mapping` 改写为 Sample 节点 |

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 创建动态节点后再修改 `data_type` | 在同一次 `new_node` 调用的 `attrs` 中设置 |
| 用 Sample Index 读取当前字段上下文 | 改用 `attribute_field_nodes.md` 中的 Field at Index |
| 用 Sample Nearest 期待插值值 | 它只输出索引；改用 Sample Nearest Surface |
| 忽略 `Is Valid` | 采样源可能为空或 UV 无匹配，必要时处理失败分支 |
| 在新代码使用 `Nodes.TransferAttribute` | 直接改写为对应 Sample 节点 |

## 相关文档

- `new_node` 与连接规则：`../node_wrangler_usage.md`
- 动态 socket 与兼容层：`../socket_attrs_and_compatibility.md`
- 当前上下文 attribute 与 field：`attribute_field_nodes.md`
- Position、Normal、Index、ID：`geometry_input_info_nodes.md`
- Raycast 与 Proximity：`geometry_spatial_query_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/core/nodes/compatibility.py`
- `infinigen/core/nodes/nodegroups/transfer_attributes.py`
- [Blender 4.2 Sample Geometry Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/sample/index.html)
- [Blender 4.2 Mesh Sample Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/sample/index.html)
