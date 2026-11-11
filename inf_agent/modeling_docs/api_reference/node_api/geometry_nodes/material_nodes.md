# Geometry Nodes 材质节点

本文档覆盖 `Nodes` 枚举中的 Geometry Nodes 材质赋值与 material index 读写节点。它只说明如何把已有材质用于 geometry；材质选择、创建和 shader 内容继续路由到 `../../material_api/README.md`。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.SetMaterial` | 将 Material data-block 赋给选中的几何元素 |
| `Nodes.SetMaterialIndex` | 将选中 mesh faces 指向已有材质列表中的指定索引 |
| `Nodes.MaterialIndex` | 读取当前 mesh face 的材质索引 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。3 个节点内容紧密且篇幅较小，无需拆分文档。

## 共性规则

- Material 是 Blender data-block，shader 节点树属于该 data-block；本组节点不负责创建 shader。
- mesh 的 `material_index` 是 face-domain 内置整数属性，索引从 0 开始。
- 为不同区域赋明确材质时优先使用 `SetMaterial`；只有材质列表顺序已经稳定时才直接读写数字索引。
- `Selection` 在 mesh 上按 face domain 求值。来自 point/edge domain 的 Boolean field 会按 Blender 的 domain 转换规则转为 face selection。
- 多材质通常串联多个 `SetMaterial` 节点，每个节点处理一个 selection。后写入的节点会覆盖重叠区域。

## `Nodes.SetMaterial`

**作用**：给选中的几何元素赋一个已有 Material data-block；若材质已存在于几何的材质列表中，会复用其索引。

**创建方式**：

```python
geometry = nw.new_node(
    Nodes.SetMaterial,
    input_kwargs={
        "Geometry": geometry,
        "Selection": front_faces,
        "Material": front_material,
    },
).outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SetMaterial`，对应 `GeometryNodeSetMaterial` |
| `input_kwargs` | `Geometry`、`Selection`、`Material` |

**Input Sockets**：`Geometry`；`Selection`（Boolean field，默认全选）；`Material`（Material data-block 或 Material socket）。

**Output Sockets**：`Geometry`。

`Material` 可以直接传入 `bpy.types.Material`，也可以连接 node group 的 Material 输入 socket。对 point cloud 和 volume 只能使用单一材质，其 `Selection` field 会被忽略；室内资产的多区域材质主要使用 mesh face selection。

同一几何需要多种材质时，按区域串联节点：

```python
geometry = nw.new_node(
    Nodes.SetMaterial,
    input_kwargs={"Geometry": geometry, "Selection": body_faces, "Material": body_mat},
)
geometry = nw.new_node(
    Nodes.SetMaterial,
    input_kwargs={"Geometry": geometry, "Selection": trim_faces, "Material": trim_mat},
)
```

## `Nodes.SetMaterialIndex`

**作用**：写入所选 mesh faces 的 `material_index`，切换到材质列表中的已有槽位。

**创建方式**：

```python
geometry = nw.new_node(
    Nodes.SetMaterialIndex,
    input_kwargs={
        "Geometry": geometry,
        "Selection": trim_faces,
        "Material Index": 1,
    },
).outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SetMaterialIndex`，对应 `GeometryNodeSetMaterialIndex` |
| `input_kwargs` | `Geometry`、`Selection`、`Material Index` |

**Input Sockets**：`Geometry`；`Selection`（Boolean field，face domain）；`Material Index`（Integer field，最小为 0）。

**Output Sockets**：`Geometry`。

该节点只写索引，不接收 Material data-block，也不用于构建材质。必须先确认输入几何的材质列表及其顺序；否则索引可能指向错误材质。生成新资产时通常直接使用多个 `SetMaterial`，从已有多材质 mesh 继承稳定槽位时才使用本节点。

## `Nodes.MaterialIndex`

**作用**：读取当前 mesh face 在材质列表中的零基索引，常用于按已有材质分区生成 selection。

**创建方式**：

```python
material_index = nw.new_node(
    Nodes.MaterialIndex
).outputs["Material Index"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MaterialIndex`，对应 `GeometryNodeInputMaterialIndex` |

**Input Sockets**：无。

**Output Sockets**：`Material Index`（Integer field，face domain）。

该输出必须连接到会提供 geometry evaluation context 的 field 输入，例如 Compare、Selection 或 Set Position。节点自身不接收 Geometry，脱离下游几何上下文时无法表示某个具体 mesh 的索引值。

```python
is_trim = nw.compare(
    "EQUAL",
    nw.new_node(Nodes.MaterialIndex),
    1,
)
```

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把 shader node group 直接传给 `Material` | 先由 Material API 创建 `bpy.types.Material`，或连接 Material socket |
| 用 `SetMaterialIndex` 指定材质但结果不对 | 该节点只写数字；先确认输入几何已有对应材质槽位 |
| 把 material index 当成从 1 开始 | Blender 使用零基索引，第一个材质是 0 |
| `Selection` 边界与预期不同 | 确认 field 的原始 domain；需要精确面选择时直接生成 face-domain field |
| 多个 `SetMaterial` 的区域重叠 | 后面的节点覆盖前面；让 selections 互斥或明确节点顺序 |
| `MaterialIndex` 没有 Geometry 输入 | 这是 field input node；将输出接到在目标 geometry 上求值的下游节点 |

## 相关文档

- `new_node`、data-block 与 socket 输入：`../node_wrangler_usage.md`
- 材质选择与创建：`../../material_api/README.md`
- Shader 节点树：`../README.md` 的 Shader Nodes 路由
- face selection 与拓扑信息：`mesh_topology_input_nodes.md`
- field 比较和逻辑组合：`../common_nodes/math_logic_nodes.md`
- Blender object 级材质赋值：`../../function_api/surface_material_ops.md`
- 实例材质与 realize 时机：`instance_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/assets/objects/appliances/beverage_fridge.py`
- `infinigen/assets/objects/underwater/urchin.py`
- `infinigen/assets/objects/deformed_trees/hollow.py`
- `infinigen/assets/materials/plant/bark_random.py`
- [Blender 4.2 Material Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/material/index.html)
- [Blender Set Material](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/material/set_material.html)
- [Blender Set Material Index](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/material/set_material_index.html)
- [Blender Material Index](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/material/material_index.html)
