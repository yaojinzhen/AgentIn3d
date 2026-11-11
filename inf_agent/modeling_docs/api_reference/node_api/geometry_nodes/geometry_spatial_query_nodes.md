# 几何空间查询节点

本文档覆盖最近位置查询与射线求交。两者都从显式目标 geometry 采样，但输出含义和适用场景不同。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.Proximity` | 查询目标上的最近位置和距离 |
| `Nodes.Raycast` | 沿指定方向查询目标 mesh 的首次命中 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。

## 共性规则

- 目标 geometry 通过 input socket 显式传入；查询起点是下游求值上下文中的 field。
- `Proximity` 不限制方向；`Raycast` 同时受方向和最大长度限制。
- 目标与采样位置必须位于一致的坐标空间。
- 空目标或分组不匹配时先检查有效性输出，不要直接消费位置和距离。

## `Nodes.Proximity`

**作用**：查找目标 mesh 或 point cloud 上离 `Sample Position` 最近的位置，并返回距离。

**创建方式**：

```python
nearest = nw.new_node(
    Nodes.Proximity,
    input_kwargs={
        "Geometry": target_geometry,
        "Sample Position": sample_position,
    },
    attrs={"target_element": "FACES"},
)
distance = nearest.outputs["Distance"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Proximity`，对应 `GeometryNodeProximity` |
| `attrs` | `target_element`：`POINTS`、`EDGES`、`FACES` |
| `input_kwargs` | `Geometry`、`Group ID`、`Sample Position`、`Sample Group ID` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Geometry` | Geometry | 被查询的 mesh 或 point cloud |
| `Group ID` | Integer field | 在目标 geometry 上划分独立搜索组 |
| `Sample Position` | Vector field | 查询位置，默认使用当前 Position |
| `Sample Group ID` | Integer field | 为每个查询点选择对应目标组 |

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Position` | Vector field | 目标上的最近位置 |
| `Distance` | Float field | 查询点到最近位置的距离 |
| `Is Valid` | Boolean field | 对应目标组中是否存在可采样元素 |

`POINTS` 支持 mesh 顶点和 point cloud，通常最快；`EDGES`、`FACES` 只适用于 mesh，并可返回边或面内部的最近位置。旧 Infinigen 代码可能使用输入名 `"Target"`；Blender 4.2 新代码推荐使用 `"Geometry"`。

## `Nodes.Raycast`

**作用**：从每个 `Source Position` 沿 `Ray Direction` 发射射线，查询目标 mesh 的首次命中及命中处字段。

**创建方式**：

```python
raycast = nw.new_node(
    Nodes.Raycast,
    input_kwargs={
        "Target Geometry": target_mesh,
        "Attribute": target_value,
        "Source Position": source_position,
        "Ray Direction": direction,
        "Ray Length": 5.0,
    },
    attrs={"data_type": "FLOAT_VECTOR", "mapping": "INTERPOLATED"},
)
hit_position = raycast.outputs["Hit Position"]
is_hit = raycast.outputs["Is Hit"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Raycast`，对应 `GeometryNodeRaycast` |
| `attrs` | `data_type` 控制 `Attribute` 类型；`mapping`：`INTERPOLATED` / `NEAREST` |
| `input_kwargs` | `Target Geometry`、`Attribute`、`Source Position`、`Ray Direction`、`Ray Length` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Target Geometry` | Geometry | 射线测试目标，必须包含 mesh |
| `Attribute` | dynamic field | 在目标 mesh 上求值并于命中处采样 |
| `Source Position` | Vector field | 射线起点，默认使用当前 Position |
| `Ray Direction` | Vector field | 射线方向；建议传入非零单位向量 |
| `Ray Length` | Float field | 最大检测距离 |

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Is Hit` | Boolean field | 是否在最大长度内命中 |
| `Hit Position` | Vector field | 命中点 |
| `Hit Normal` | Vector field | 命中表面法线 |
| `Hit Distance` | Float field | 起点到命中点的距离 |
| `Attribute` | dynamic field | 命中处采样值，类型由 `data_type` 决定 |

常用 `data_type` 为 `FLOAT`、`INT`、`FLOAT_VECTOR`、`FLOAT_COLOR`、`BOOLEAN`。`INTERPOLATED` 平滑插值目标顶点/face-corner 字段；`NEAREST` 取最近元素值。只需命中几何信息时可不连接 `Attribute`，但仍应让 `data_type` 与实际读取方式一致。

## 选择对照

| 目标 | 使用 |
| --- | --- |
| 到表面的最短距离或最近点 | `Proximity` + `target_element="FACES"` |
| 到最近顶点的距离 | `Proximity` + `target_element="POINTS"` |
| 沿法线投射到另一表面 | `Raycast` |
| 判断方向上是否被遮挡 | `Raycast.outputs["Is Hit"]` |
| 在命中处读取颜色、法线或 mask | `Raycast` 的动态 `Attribute` |
| 仅按索引或 UV 读取字段 | `geometry_sampling_nodes.md` 中的 Sample 节点 |

## 常见错误

| 错误 | 修复 |
| --- | --- |
| Proximity 使用旧输入名 `Target` | 新代码使用 `Geometry` |
| 查询结果整体偏移或旋转 | 先把目标和采样位置转换到同一空间 |
| Raycast 总是未命中 | 检查方向、`Ray Length`、目标是否为 mesh |
| 未命中时仍直接使用 Hit Position | 用 `Is Hit` 通过 `Switch` 提供回退值 |
| Raycast Attribute 类型不匹配 | 先设置正确 `data_type`，再连接动态 socket |
| 分组采样出现无效值 | 检查 `Group ID` 与 `Sample Group ID` 是否有匹配组 |

## 相关文档

- `new_node` 与动态 socket：`../node_wrangler_usage.md`
- 按索引、最近元素和 UV 采样：`geometry_sampling_nodes.md`
- Position、Normal 字段：`geometry_input_info_nodes.md`
- 坐标与向量运算：`../common_nodes/vector_rotation_mapping_nodes.md`
- 变换目标 geometry：`geometry_write_shape_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/assets/objects/creatures/insects/utils/geom_utils.py`
- `infinigen/assets/objects/creatures/parts/eye_new.py`
- `infinigen/assets/objects/creatures/insects/parts/wing/dragonfly_wing.py`
- [Blender 4.2 Geometry Proximity](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/sample/geometry_proximity.html)
- [Blender 4.2 Raycast](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/sample/raycast.html)
