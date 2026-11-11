# Mesh 基础节点

本文档覆盖 `Nodes` 枚举中的基础 mesh primitive，并补充 Infinigen 资产源码高频使用的 Cylinder 与 Cone。每节只列当前节点实际需要的 `new_node` 参数；通用参数语义见 `../node_wrangler_usage.md`。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.MeshCircle` | 创建边环、单个 N-gon 或三角扇形圆面 |
| `Nodes.MeshGrid` | 创建位于 XY 平面的规则矩形网格 |
| `Nodes.MeshLine` | 按偏移或首尾位置创建点线 mesh |
| `Nodes.MeshUVSphere` | 创建以四边形为主、两极为三角形的 UV sphere |
| `Nodes.MeshIcoSphere` / `Nodes.IcoSphere` | 创建三角面分布均匀的 icosphere；二者是同一节点 |
| `Nodes.MeshCube` | 创建可沿三个轴细分的长方体 |
| `"GeometryNodeMeshCylinder"` | 创建圆柱或棱柱；不是 `Nodes` 枚举成员 |
| `"GeometryNodeMeshCone"` | 创建圆锥、棱锥或截锥；不是 `Nodes` 枚举成员 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。8 个实际节点数量与篇幅适中，因此不拆分文档。

## 共性规则

- primitive 以 node group 局部原点为中心；平面位于 XY，Cylinder/Cone 的深度沿 Z。整体放置继续使用 Transform Geometry。
- 分段数直接影响拓扑和执行成本。先使用满足轮廓的最低值，避免对 Icosphere 使用过高 `Subdivisions`。
- Grid、UV Sphere、Icosphere、Cube、Cylinder 和 Cone 的 `UV Map` 是 face-corner field，不会自动成为具名 UV 层；需要持久化时使用 Store Named Attribute，domain 设为 `CORNER`。
- Mesh Circle 与 Mesh Line 不提供 `UV Map`。需要纹理坐标时后续生成或展开。

## `Nodes.MeshCircle`

**作用**：在 XY 平面创建圆形边环，并可选择不填充、N-gon 填充或三角扇填充。

**创建方式**：

```python
circle = nw.new_node(
    Nodes.MeshCircle,
    input_kwargs={"Vertices": 32, "Radius": 0.5},
    attrs={"fill_type": "NGON"},
).outputs["Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MeshCircle`，对应 `GeometryNodeMeshCircle` |
| `attrs` | `fill_type`：`NONE`、`NGON` 或 `TRIANGLE_FAN` |
| `input_kwargs` | `Vertices`、`Radius` |

**Input Sockets**：`Vertices`（Integer，圆周顶点数，至少 3）；`Radius`（Float distance）。

**Output Sockets**：`Mesh`。

`NONE` 只生成边环；`NGON` 生成单个面；`TRIANGLE_FAN` 增加中心点并生成三角面。需要可径向变形的圆盘时优先使用三角扇。

## `Nodes.MeshGrid`

**作用**：在 XY 平面创建可分别控制尺寸和 X/Y 顶点数的矩形网格。

**创建方式**：

```python
grid = nw.new_node(
    Nodes.MeshGrid,
    input_kwargs={
        "Size X": 2.0,
        "Size Y": 1.0,
        "Vertices X": 8,
        "Vertices Y": 4,
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MeshGrid`，对应 `GeometryNodeMeshGrid` |
| `input_kwargs` | `Size X`、`Size Y`、`Vertices X`、`Vertices Y` |

**Input Sockets**：`Size X`、`Size Y`（Float distance）；`Vertices X`、`Vertices Y`（Integer，各至少 2）。

**Output Sockets**：`Mesh`；`UV Map`（Vector field）。

顶点数是每个方向的顶点总数，不是面数；对应面数为 `(Vertices X - 1) * (Vertices Y - 1)`。只需一个矩形面时两个顶点数均设为 2。

## `Nodes.MeshLine`

**作用**：创建由顶点和边组成的直线 mesh，适合生成实例点列、路径索引或后续转换为 curve。

**创建方式**：

```python
line = nw.new_node(
    Nodes.MeshLine,
    input_kwargs={
        "Count": 9,
        "Start Location": (-1.0, 0.0, 0.0),
        "Offset": (1.0, 0.0, 0.0),
    },
    attrs={"mode": "END_POINTS", "count_mode": "TOTAL"},
).outputs["Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MeshLine`，对应 `GeometryNodeMeshLine` |
| `attrs` | `mode`：`OFFSET` 或 `END_POINTS`；后者还使用 `count_mode`：`TOTAL` 或 `RESOLUTION` |
| `input_kwargs` | `Start Location`；`OFFSET` 使用 `Count`、`Offset`；`END_POINTS` 使用 `Offset` 作为终点，并按 count mode 使用 `Count` 或 `Resolution` |

**Input Sockets**：`Start Location`（Vector）；`Offset`（Vector，动态语义）；`Count`（Integer）或 `Resolution`（Float distance）。

**Output Sockets**：`Mesh`。

`OFFSET` 中每个顶点相对前一顶点移动 `Offset`。`END_POINTS` 中同一个 Python socket 键 `Offset` 在界面显示为 `End Location`，表示绝对终点；不要向 `input_kwargs` 传 `"End Location"`。`TOTAL` 固定顶点总数，`RESOLUTION` 按目标边长尽量铺满首尾区间。

## `Nodes.MeshUVSphere`

**作用**：创建包含规则经纬拓扑的球体，主体为四边形，两极为三角扇。

**创建方式**：

```python
sphere = nw.new_node(
    Nodes.MeshUVSphere,
    input_kwargs={"Segments": 32, "Rings": 16, "Radius": 0.5},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MeshUVSphere`，对应 `GeometryNodeMeshUVSphere` |
| `input_kwargs` | `Segments`、`Rings`、`Radius` |

**Input Sockets**：`Segments`（Integer，经向分段，至少 3）；`Rings`（Integer，纬向分段，至少 2）；`Radius`（Float distance）。

**Output Sockets**：`Mesh`；`UV Map`（Vector field）。

规则经纬拓扑便于按高度或经纬方向选择，但两极存在拓扑汇聚。若更看重三角面均匀性或各向同性变形，改用 Icosphere。

## `Nodes.MeshIcoSphere` / `Nodes.IcoSphere`

**作用**：创建由近似等尺寸三角面组成的球体。

**创建方式**：

```python
sphere = nw.new_node(
    Nodes.MeshIcoSphere,
    input_kwargs={"Radius": 0.5, "Subdivisions": 3},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | 推荐 `Nodes.MeshIcoSphere`；`Nodes.IcoSphere` 是同一 `GeometryNodeMeshIcoSphere` 的别名 |
| `input_kwargs` | `Radius`、`Subdivisions` |

**Input Sockets**：`Radius`（Float distance）；`Subdivisions`（Integer）。

**Output Sockets**：`Mesh`；`UV Map`（Vector field）。

`Subdivisions=1` 是基础二十面体；每提高一级，面数约变为原来的 4 倍。资产生成通常使用 1 到 4，除非确有近景轮廓需求，不要继续提高。

## `Nodes.MeshCube`

**作用**：创建以原点为中心、可沿 X/Y/Z 分段的长方体。

**创建方式**：

```python
cube = nw.new_node(
    Nodes.MeshCube,
    input_kwargs={
        "Size": (2.0, 1.0, 0.5),
        "Vertices X": 2,
        "Vertices Y": 2,
        "Vertices Z": 2,
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MeshCube`，对应 `GeometryNodeMeshCube` |
| `input_kwargs` | `Size`、`Vertices X`、`Vertices Y`、`Vertices Z` |

**Input Sockets**：`Size`（Vector，三个轴的完整尺寸）；`Vertices X/Y/Z`（Integer，各轴顶点数，至少 2）。

**Output Sockets**：`Mesh`；`UV Map`（Vector field）。

`Size` 不是半尺寸。三个顶点数均为 2 时得到普通长方体；只有需要面内变形或更密 field 采样时才增加分段。

## `"GeometryNodeMeshCylinder"`

**作用**：创建沿局部 Z 轴的圆柱或低边数棱柱。该节点不在 `Nodes` 枚举中，但被 Infinigen 室内资产源码广泛使用。

**创建方式**：

```python
cylinder = nw.new_node(
    "GeometryNodeMeshCylinder",
    input_kwargs={
        "Vertices": 24,
        "Side Segments": 1,
        "Fill Segments": 1,
        "Radius": 0.4,
        "Depth": 1.2,
    },
    attrs={"fill_type": "NGON"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | raw `bl_idname`：`"GeometryNodeMeshCylinder"` |
| `attrs` | `fill_type`：`NONE`、`NGON` 或 `TRIANGLE_FAN` |
| `input_kwargs` | `Vertices`、`Side Segments`、动态 `Fill Segments`、`Radius`、`Depth` |

**Input Sockets**：`Vertices`（Integer，环向顶点数，至少 3）；`Side Segments`（Integer，纵向分段，至少 1）；`Fill Segments`（Integer，仅填充时启用）；`Radius`、`Depth`（Float distance）。

**Output Sockets**：`Mesh`；`Top`、`Side`、`Bottom`（Boolean fields）；`UV Map`（Vector field）。

`fill_type=NONE` 时不传 `Fill Segments`，Top/Bottom 改为选择边环；有盖时选择对应端面。将 `Vertices` 设为 3、4、6 等低值可生成棱柱。

## `"GeometryNodeMeshCone"`

**作用**：创建沿局部 Z 轴的圆锥、棱锥或上下半径不同的截锥。该节点不在 `Nodes` 枚举中。

**创建方式**：

```python
cone = nw.new_node(
    "GeometryNodeMeshCone",
    input_kwargs={
        "Vertices": 24,
        "Side Segments": 1,
        "Fill Segments": 1,
        "Radius Top": 0.1,
        "Radius Bottom": 0.4,
        "Depth": 1.2,
    },
    attrs={"fill_type": "NGON"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | raw `bl_idname`：`"GeometryNodeMeshCone"` |
| `attrs` | `fill_type`：`NONE`、`NGON` 或 `TRIANGLE_FAN` |
| `input_kwargs` | `Vertices`、`Side Segments`、动态 `Fill Segments`、`Radius Top`、`Radius Bottom`、`Depth` |

**Input Sockets**：`Vertices`（Integer，环向顶点数，至少 3）；`Side Segments`（Integer，纵向分段，至少 1）；`Fill Segments`（Integer，仅填充时启用）；`Radius Top`、`Radius Bottom`、`Depth`（Float distance）。

**Output Sockets**：`Mesh`；`Top`、`Bottom`、`Side`（Boolean fields）；`UV Map`（Vector field）。

一个半径为 0 时对应端收束为顶点；两个半径都大于 0 时生成截锥；二者都为 0 时只生成一条线。低 `Vertices` 值可生成棱锥或截棱锥。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| Mesh Line 的终点参数报找不到 socket | `END_POINTS` 模式仍使用 Python 键 `Offset`，不要传 `"End Location"` |
| Mesh Line 的 `Resolution` 不生效 | 同时设置 `mode="END_POINTS"` 和 `count_mode="RESOLUTION"` |
| Circle/Cylinder/Cone 的填充结果不对 | 先设置 `fill_type`，`NONE` 模式不传 `Fill Segments` |
| 直接把 `UV Map` 当作已存储 UV 层 | 用 Store Named Attribute 写入 face-corner domain |
| Cube 或 Grid 的顶点数被当作面数 | 每轴面数比该轴顶点数少 1 |
| Icosphere 导致节点树明显变慢 | 降低 `Subdivisions`；每增加一级，面数约增至 4 倍 |

## 相关文档

- `new_node`、raw `bl_idname` 与 attrs：`../node_wrangler_usage.md`
- primitive 的移动、旋转与缩放：`geometry_write_shape_nodes.md`
- 细分、挤出、布尔和拓扑修改：`mesh_operations_nodes.md`
- UV field 的持久化：`attribute_field_nodes.md`
- 材质分配：`material_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/assets/objects/organizer/hook.py`
- `infinigen/assets/objects/organizer/plate_rack.py`
- `infinigen/assets/objects/seating/sofa.py`
- `infinigen/assets/objects/lamp/ceiling_classic_lamp.py`
- [Blender 4.2 Mesh Primitive Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/primitives/index.html)
- [Blender Mesh Circle](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/primitives/mesh_circle.html)
- [Blender Mesh Line](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/primitives/mesh_line.html)
- [Blender Grid](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/primitives/grid.html)
- [Blender Cube](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/primitives/cube.html)
- [Blender UV Sphere](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/primitives/uv_sphere.html)
- [Blender Icosphere](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/primitives/icosphere.html)
- [Blender Cylinder](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/primitives/cylinder.html)
- [Blender Cone](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/primitives/cone.html)
