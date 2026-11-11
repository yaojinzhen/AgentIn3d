# 几何结构节点

本文档覆盖几何组件拆分、合并、筛选、删除、焊接和复制。参数表只列当前节点实际需要的 `new_node` 参数。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.SeparateComponents` | 按 mesh、curve、point cloud、volume、instances 拆分组件 |
| `Nodes.JoinGeometry` | 把多个几何输入合并到同一个 Geometry 中 |
| `Nodes.MergeByDistance` | 按距离焊接 mesh 顶点或 point cloud 点 |
| `Nodes.SeparateGeometry` | 按 selection 输出选中与未选中两部分 |
| `Nodes.DeleteGeometry` / `Nodes.DeleteGeom` | 删除选中的几何元素 |
| `Nodes.DuplicateElements` | 按 domain 复制元素并输出副本索引 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。

## 共性规则

- `SeparateComponents` 按组件类型拆分；`SeparateGeometry` 按 Boolean field 拆分。
- `JoinGeometry` 保留不同组件类型，不等同于 mesh Boolean，也不会自动 realize instances。
- `Selection` 是 field，其求值 domain 由节点的 `domain` 决定。
- `DeleteGeometry` 与 `DeleteGeom` 都对应 `GeometryNodeDeleteGeometry`；新代码统一使用 `Nodes.DeleteGeometry`。

## `Nodes.SeparateComponents`

**作用**：把一个 Geometry 中并存的组件类型拆到独立输出。

**创建方式**：

```python
parts = nw.new_node(
    Nodes.SeparateComponents,
    input_kwargs={"Geometry": geometry},
)
mesh = parts.outputs["Mesh"]
instances = parts.outputs["Instances"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SeparateComponents`，对应 `GeometryNodeSeparateComponents` |
| `input_kwargs` | `Geometry` |

**Input Sockets**：`Geometry`。

**Output Sockets**：`Mesh`、`Curve`、`Point Cloud`、`Volume`、`Instances`。

实例内部的 mesh/curve 不会进入对应组件输出；需要访问实例内部组件时先使用 `RealizeInstances`。

## `Nodes.JoinGeometry`

**作用**：把多个 Geometry 合并为一个可继续传递的 Geometry。

**创建方式**：

```python
joined = nw.new_node(
    Nodes.JoinGeometry,
    input_kwargs={"Geometry": [body, handle, trim]},
).outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.JoinGeometry`，对应 `GeometryNodeJoinGeometry` |
| `input_kwargs` | `Geometry`；multi-input socket，可传节点/socket 列表 |

**Input Sockets**：`Geometry`（multi-input）。

**Output Sockets**：`Geometry`。

不同类型的组件会并存在输出中；多个 mesh 的材质槽和同名 attribute 会被合并。一个结果不能合并多个 volume 组件。需要 mesh 并集或切割时使用 `MeshBoolean`；组合实例输出时不要仅为 Join 而提前 realize。

## `Nodes.MergeByDistance`

**作用**：合并距离小于阈值的 mesh 顶点或 point cloud 点，常用于焊接拼接缝和清理重复点。

**创建方式**：

```python
welded = nw.new_node(
    Nodes.MergeByDistance,
    input_kwargs={
        "Geometry": geometry,
        "Selection": weld_mask,
        "Distance": 0.001,
    },
    attrs={"mode": "ALL"},
).outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MergeByDistance`，对应 `GeometryNodeMergeByDistance` |
| `attrs` | `mode`：`ALL` / `CONNECTED` |
| `input_kwargs` | `Geometry`、`Selection`、`Distance` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Geometry` | Geometry | 输入 mesh 或 point cloud |
| `Selection` | Boolean field | 仅选中的点参与搜索与合并 |
| `Distance` | Float | 最大合并距离，使用对象局部空间单位 |

**Output Sockets**：`Geometry`。

`ALL` 可合并互不连接部分中的近邻点；`CONNECTED` 只在已有拓扑连接范围内合并。阈值应与资产尺寸成比例，室内物体通常从毫米量级开始测试；大 selection 和大阈值会增加搜索开销。

## `Nodes.SeparateGeometry`

**作用**：在指定 domain 上求值 selection，并输出选中部分与反选部分。

**创建方式**：

```python
split = nw.new_node(
    Nodes.SeparateGeometry,
    input_kwargs={"Geometry": geometry, "Selection": face_mask},
    attrs={"domain": "FACE"},
)
selected = split.outputs["Selection"]
remainder = split.outputs["Inverted"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SeparateGeometry`，对应 `GeometryNodeSeparateGeometry` |
| `attrs` | `domain`：`POINT`、`EDGE`、`FACE`、`CURVE`、`INSTANCE`、`LAYER` |
| `input_kwargs` | `Geometry`、`Selection` |

**Input Sockets**：`Geometry`、`Selection`（Boolean field）。

**Output Sockets**：`Selection`、`Inverted`（Geometry）。

mesh 建模通常使用 `POINT`、`EDGE` 或 `FACE`；整条 spline 使用 `CURVE`；顶层实例使用 `INSTANCE`。`LAYER` 面向 Grease Pencil layer，静态单体资产通常不使用，但接口仍保留在本页。

## `Nodes.DeleteGeometry` / `Nodes.DeleteGeom`

**作用**：删除 selection 为 `True` 的元素，只保留一个 Geometry 输出。

**创建方式**：

```python
trimmed = nw.new_node(
    Nodes.DeleteGeometry,
    input_kwargs={"Geometry": geometry, "Selection": remove_mask},
    attrs={"domain": "FACE", "mode": "ALL"},
).outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | 推荐 `Nodes.DeleteGeometry`；`Nodes.DeleteGeom` 是同一 `bl_idname` 的兼容别名 |
| `attrs` | `domain`：`POINT`、`EDGE`、`FACE`、`CURVE`、`INSTANCE`、`LAYER`；`mode`：`ALL`、`EDGE_FACE`、`ONLY_FACE` |
| `input_kwargs` | `Geometry`、`Selection` |

**Input Sockets**：`Geometry`、`Selection`（Boolean field）。

**Output Sockets**：`Geometry`。

`mode` 只影响 mesh 删除行为：`ALL` 删除选中元素及依赖它的拓扑，`EDGE_FACE` 保留顶点，`ONLY_FACE` 只删除面。需要同时保留删除部分时改用 `SeparateGeometry`。

## `Nodes.DuplicateElements`

**作用**：复制选中的 point、edge、face、spline 或 instance，并为每份副本生成索引。

**创建方式**：

```python
duplicates = nw.new_node(
    Nodes.DuplicateElements,
    input_kwargs={
        "Geometry": geometry,
        "Selection": selection,
        "Amount": count,
    },
    attrs={"domain": "INSTANCE"},
)
geometry = duplicates.outputs["Geometry"]
copy_index = duplicates.outputs["Duplicate Index"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.DuplicateElements`，对应 `GeometryNodeDuplicateElements` |
| `attrs` | `domain`：`POINT`、`EDGE`、`FACE`、`SPLINE`、`INSTANCE` |
| `input_kwargs` | `Geometry`、`Selection`、`Amount` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Geometry` | Geometry | 待复制几何 |
| `Selection` | Boolean field | 决定哪些元素参与复制 |
| `Amount` | Integer field | 每个输入元素的输出份数；`0` 会移除该元素 |

**Output Sockets**：`Geometry`、`Duplicate Index`（Integer field，从 `0` 到 `Amount - 1`）。

复制结果初始位置重合，通常用 `Duplicate Index` 计算位移或旋转。大量重复部件优先复制 `INSTANCE`；直接复制 mesh face/point 会快速增加真实拓扑。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 用 `SeparateComponents` 处理 Boolean mask | 使用 `SeparateGeometry` |
| 认为 `JoinGeometry` 会执行 mesh 并集 | 使用 `MeshBoolean` |
| `JoinGeometry` 只连接了列表中的第一个输入 | 把节点/socket 列表传给 multi-input `Geometry` |
| Merge by Distance 破坏细小结构 | 缩小 `Distance`，并限制 `Selection` |
| 需要两部分却用了 Delete Geometry | 改用 `SeparateGeometry` 的两个输出 |
| 复制后看不到阵列效果 | 用 `Duplicate Index` 驱动位置，或改用实例节点 |

## 相关文档

- `new_node` 与 multi-input：`../node_wrangler_usage.md`
- field、domain 与 selection：`attribute_field_nodes.md`
- Set ID、位置和整体变换：`geometry_write_shape_nodes.md`
- Mesh Boolean 与拓扑编辑：`mesh_operations_nodes.md`
- 实例生成与变换：`instance_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/assets/objects/appliances/`
- `infinigen/assets/objects/cactus/`
- [Blender 4.2 Geometry Operations](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/operations/index.html)
- [Blender 4.2 Join Geometry](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/join_geometry.html)
- [Blender 4.2 Separate Geometry](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/operations/separate_geometry.html)
- [Blender 4.2 Duplicate Elements](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/operations/duplicate_elements.html)
