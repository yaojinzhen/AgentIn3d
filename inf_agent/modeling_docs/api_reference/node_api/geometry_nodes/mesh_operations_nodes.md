# Mesh 操作节点

本文档覆盖 mesh 的细分、布尔、挤出、缩放、平滑、翻面、拆边、三角化，以及向 points/curve 的转换。每节只列当前节点实际需要的 `new_node` 参数；通用参数语义见 `../node_wrangler_usage.md`。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.SubdivideMesh` | 线性增加面和顶点，不平滑整体形状 |
| `Nodes.SubdivisionSurface` | 使用 Catmull-Clark 细分并平滑表面 |
| `Nodes.MeshToPoints` | 按 vertex、edge、face 或 corner 生成 point cloud |
| `Nodes.MeshBoolean` | 对实体 mesh 求交集、并集或差集 |
| `Nodes.SetShadeSmooth` | 在 face/edge domain 写入平滑着色状态 |
| `Nodes.DualMesh` | 交换 mesh 的 face 与 vertex 拓扑角色 |
| `Nodes.ScaleElements` | 按连接的 face/edge 岛缩放元素 |
| `Nodes.ExtrudeMesh` | 挤出 vertex、edge 或 face，并输出新顶面/侧面 selection |
| `Nodes.FlipFaces` | 反转选中面的绕序和法线方向 |
| `Nodes.EdgePathToCurve` | 根据 next-vertex 字段把 mesh edge 路径转为 curves |
| `Nodes.SplitEdges` | 断开选中 edge 两侧面的拓扑连接 |
| `Nodes.Triangulate` | 按指定算法把 quad/ngon 转为三角面 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。

## 共性规则

- 除 `MeshToPoints` 和 `EdgePathToCurve` 外，本组节点仍输出 mesh；类型转换后不要继续假设原 mesh domain 存在。
- 挤出、布尔、细分、拆边和三角化都会改变 index；持久数据应使用 ID 或在拓扑修改后重算 selection。
- `Selection` 的原生 domain 由节点模式决定，尽量在对应 domain 上构造 field。
- 高级别 subdivision 和复杂 Boolean 成本较高；资产生成代码优先使用满足轮廓需求的最低复杂度。

## `Nodes.SubdivideMesh`

**作用**：按简单线性插值细分每个面，增加拓扑但不执行 Catmull-Clark 平滑。

**创建方式**：

```python
mesh = nw.new_node(
    Nodes.SubdivideMesh,
    input_kwargs={"Mesh": mesh, "Level": 2},
).outputs["Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SubdivideMesh`，对应 `GeometryNodeSubdivideMesh` |
| `input_kwargs` | `Mesh`、`Level` |

**Input Sockets**：`Mesh`（Geometry）、`Level`（Integer，递归细分次数）。

**Output Sockets**：`Mesh`。

适合增加 `SetPosition` 可用的顶点密度；需要圆滑外形时改用 `SubdivisionSurface`。面数随 Level 快速增长，不要用高 Level 代替合理基础拓扑。

## `Nodes.SubdivisionSurface`

**作用**：使用 Catmull-Clark 算法细分并平滑 mesh，可由 crease 字段保留硬边。

**创建方式**：

```python
smooth = nw.new_node(
    Nodes.SubdivisionSurface,
    input_kwargs={"Mesh": mesh, "Level": 2, "Edge Crease": crease},
    attrs={"uv_smooth": "PRESERVE_BOUNDARIES", "boundary_smooth": "ALL"},
).outputs["Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SubdivisionSurface`，对应 `GeometryNodeSubdivisionSurface` |
| `attrs` | `boundary_smooth`：`ALL`/`PRESERVE_CORNERS`；`uv_smooth`：`NONE`、`PRESERVE_CORNERS`、`PRESERVE_CORNERS_AND_JUNCTIONS`、`PRESERVE_CORNERS_JUNCTIONS_AND_CONCAVE`、`PRESERVE_BOUNDARIES`、`SMOOTH_ALL` |
| `input_kwargs` | `Mesh`、`Level`、`Edge Crease`、`Vertex Crease` |

**Input Sockets**：`Mesh`、`Level`；`Edge Crease`、`Vertex Crease`（Float factor field，分别在 edge/point domain）。

**Output Sockets**：`Mesh`。

`0` crease 完全平滑，`1` 尽量保持尖锐。硬表面资产应先规划支撑边或 crease；Level 通常保持 `1..3`。

## `Nodes.MeshToPoints`

**作用**：从选中 mesh 元素生成 point cloud。

**创建方式**：

```python
points = nw.new_node(
    Nodes.MeshToPoints,
    input_kwargs={"Mesh": mesh, "Selection": mask, "Radius": 0.02},
    attrs={"mode": "VERTICES"},
).outputs["Points"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MeshToPoints`，对应 `GeometryNodeMeshToPoints` |
| `attrs` | `mode`：`VERTICES`、`EDGES`、`FACES` 或 `CORNERS` |
| `input_kwargs` | `Mesh`、`Selection`、`Position`、`Radius` |

**Input Sockets**：`Mesh`；`Selection`；`Position`（Vector field）；`Radius`（Float distance field）。

**Output Sockets**：`Points`（point cloud）。

默认 Position 分别是 vertex 位置、edge 中点、face 顶点平均位置或 corner 对应顶点位置；`CORNERS` 的多个点可能重合。常与 `InstanceOnPoints` 组合。

## `Nodes.MeshBoolean`

**作用**：对输入 mesh 的封闭体积执行交集、并集或差集。

**创建方式**：

```python
result = nw.new_node(
    Nodes.MeshBoolean,
    input_kwargs={"Mesh 1": body, "Mesh 2": [cutter_a, cutter_b]},
    attrs={"operation": "DIFFERENCE"},
).outputs["Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MeshBoolean`，对应 `GeometryNodeMeshBoolean` |
| `attrs` | `operation`：`INTERSECT`、`UNION` 或 `DIFFERENCE` |
| `input_kwargs` | `DIFFERENCE` 使用 `Mesh 1` 和 multi-input `Mesh 2`；其他模式只使用 multi-input `Mesh 2`；可选 `Self Intersection`、`Hole Tolerant` |

**Input Sockets**：动态 `Mesh 1`；`Mesh 2`（Geometry multi-input）；两个容错 Boolean。

**Output Sockets**：`Mesh`。Blender 4.2 RNA 仍列出但禁用了 `Intersecting Edges`，生成代码不要依赖该输出。

`DIFFERENCE` 从 Mesh 1 减去全部 Mesh 2；`UNION` 合并体积；`INTERSECT` 只保留共同体积。优先使用封闭 manifold mesh；仅在输入确有自交或孔洞导致失败时开启容错选项，因为它们会增加成本。

## `Nodes.SetShadeSmooth`

**作用**：写入 mesh 的 smooth/flat shading 标记，不改变顶点位置和拓扑。

**创建方式**：

```python
smooth = nw.new_node(
    Nodes.SetShadeSmooth,
    input_kwargs={"Geometry": mesh, "Selection": faces, "Shade Smooth": True},
    attrs={"domain": "FACE"},
).outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SetShadeSmooth`，对应 `GeometryNodeSetShadeSmooth` |
| `attrs` | `domain`：`FACE` 或 `EDGE` |
| `input_kwargs` | `Geometry`、`Selection`、`Shade Smooth` |

**Input Sockets**：`Geometry`；`Selection`、`Shade Smooth`（Boolean field）。

**Output Sockets**：`Geometry`。

`FACE` 控制面的平滑着色；`EDGE` 控制跨边法线是否平滑。它只改变 shading attribute；若轮廓仍有棱角，需要 subdivision 或更多几何。

## `Nodes.DualMesh`

**作用**：把原 mesh 的 face 转成 vertex、vertex 转成 face，生成对偶拓扑。

**创建方式**：

```python
dual = nw.new_node(
    Nodes.DualMesh,
    input_kwargs={"Mesh": mesh, "Keep Boundaries": True},
).outputs["Dual Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.DualMesh`，对应 `GeometryNodeDualMesh` |
| `input_kwargs` | `Mesh`、`Keep Boundaries` |

**Input Sockets**：`Mesh`、`Keep Boundaries`（Boolean）。

**Output Sockets**：`Dual Mesh`。

优先用于 manifold mesh；三角网格会得到以多边形为主的均匀对偶结构。`Keep Boundaries=True` 通过额外几何保留开放边界，边界附近不进行完整对偶转换。

## `Nodes.ScaleElements`

**作用**：围绕每个选中 face/edge 岛的中心，整体缩放其共享顶点。

**创建方式**：

```python
scaled = nw.new_node(
    Nodes.ScaleElements,
    input_kwargs={"Geometry": mesh, "Selection": faces, "Scale": 0.9},
    attrs={"domain": "FACE", "scale_mode": "UNIFORM"},
).outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ScaleElements`，对应 `GeometryNodeScaleElements` |
| `attrs` | `domain`：`FACE`/`EDGE`；`scale_mode`：`UNIFORM`/`SINGLE_AXIS` |
| `input_kwargs` | `Geometry`、`Selection`、`Scale`、`Center`；`SINGLE_AXIS` 还使用 `Axis` |

**Input Sockets**：`Geometry`；`Selection`；`Scale`（Float field）；`Center`、动态 `Axis`（Vector field）。

**Output Sockets**：`Geometry`。

相连且共享顶点的选中元素作为一组缩放，Center 和 Scale 会在组内平均。`SINGLE_AXIS` 内部归一化 Axis，只使用方向。

## `Nodes.ExtrudeMesh`

**作用**：挤出选中的 vertex、edge 或 face，并提供新顶层与侧面 selection。

**创建方式**：

```python
extrude = nw.new_node(
    Nodes.ExtrudeMesh,
    input_kwargs={
        "Mesh": mesh,
        "Selection": faces,
        "Offset Scale": height,
        "Individual": False,
    },
    attrs={"mode": "FACES"},
)
mesh = extrude.outputs["Mesh"]
side_faces = extrude.outputs["Side"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ExtrudeMesh`，对应 `GeometryNodeExtrudeMesh` |
| `attrs` | `mode`：`VERTICES`、`EDGES` 或 `FACES` |
| `input_kwargs` | `Mesh`、`Selection`、`Offset`、`Offset Scale`；仅 `FACES` 使用 `Individual` |

**Input Sockets**：`Mesh`；`Selection`；`Offset`（Vector field）；`Offset Scale`（Float）；动态 `Individual`。

**Output Sockets**：`Mesh`、`Top`、`Side`。后两者是 Boolean field，其 domain 随 mode 变化。

Vertex 模式生成新边，Edge 模式生成连接 quad，Face 模式挤出连通区域或独立面。节点不保留原位置的背面；使用 `Top`/`Side` 给新区域设置材质或继续缩放。

## `Nodes.FlipFaces`

**作用**：反转选中面的顶点/edge 绕序，从而反转法线方向。

**创建方式**：

```python
mesh = nw.new_node(
    Nodes.FlipFaces,
    input_kwargs={"Mesh": mesh, "Selection": faces},
).outputs["Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.FlipFaces`，对应 `GeometryNodeFlipFaces` |
| `input_kwargs` | `Mesh`、`Selection`（face domain） |

**Input Sockets**：`Mesh`、`Selection`。

**Output Sockets**：`Mesh`。

该节点改变 face corner 顺序，不是直接编辑 normal；选中面的 corner-domain attribute 顺序也会反转。常用于修复挤出或程序化拼面产生的朝向。

## `Nodes.EdgePathToCurve`

**作用**：从选中起点沿每个 vertex 的 Next Vertex Index 追踪 mesh edges，并输出路径 curves。

**创建方式**：

```python
paths = nw.new_node(
    Nodes.EdgePathToCurve,
    input_kwargs={
        "Mesh": mesh,
        "Start Vertices": starts,
        "Next Vertex Index": shortest.outputs["Next Vertex Index"],
    },
).outputs["Curves"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.EdgePathToCurve`，对应 `GeometryNodeEdgePathsToCurves` |
| `input_kwargs` | `Mesh`、`Start Vertices`、`Next Vertex Index` |

**Input Sockets**：`Mesh`；`Start Vertices`（Boolean，point domain）；`Next Vertex Index`（Integer field）。

**Output Sockets**：`Curves`（Geometry）。

通常把 `ShortestEdgePath.outputs["Next Vertex Index"]` 直接连接到本节点；每个 start vertex 生成一条追踪路径。Next index 必须指向相邻 vertex，否则路径可能提前终止。

## `Nodes.SplitEdges`

**作用**：复制必要的 vertex/edge，断开选中 edge 两侧 face 的拓扑连接。

**创建方式**：

```python
mesh = nw.new_node(
    Nodes.SplitEdges,
    input_kwargs={"Mesh": mesh, "Selection": edges},
).outputs["Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SplitEdges`，对应 `GeometryNodeSplitEdges` |
| `input_kwargs` | `Mesh`、`Selection`（edge domain） |

**Input Sockets**：`Mesh`、`Selection`。

**Output Sockets**：`Mesh`。

位置通常不变，但相邻面不再共享顶点，可随后独立缩放或移动。受合法 mesh 拓扑约束，实际拆分 edge 数可能与 selection 数不同。

## `Nodes.Triangulate`

**作用**：把选中 quad/ngon 按指定算法转换为三角面。

**创建方式**：

```python
mesh = nw.new_node(
    Nodes.Triangulate,
    input_kwargs={"Mesh": mesh, "Selection": faces, "Minimum Vertices": 4},
    attrs={"quad_method": "SHORTEST_DIAGONAL", "ngon_method": "BEAUTY"},
).outputs["Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Triangulate`，对应 `GeometryNodeTriangulate` |
| `attrs` | `quad_method`：`BEAUTY`、`FIXED`、`FIXED_ALTERNATE`、`SHORTEST_DIAGONAL`、`LONGEST_DIAGONAL`；`ngon_method`：`BEAUTY`/`CLIP` |
| `input_kwargs` | `Mesh`、`Selection`（face domain）、`Minimum Vertices` |

**Input Sockets**：`Mesh`、`Selection`、`Minimum Vertices`（Integer）。

**Output Sockets**：`Mesh`。

`Minimum Vertices=5` 可保留 quad、只处理 ngon。需要稳定导出或后续算法只接受三角面时使用；三角化后 face/corner index 会变化。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| Subdivide Mesh 没有变圆滑 | 它是线性细分；改用 `SubdivisionSurface` |
| Subdivision Surface 面数失控 | 降低 Level，并在基础拓扑上使用 crease/支撑边 |
| Boolean Difference 结果反了 | `Mesh 1` 是保留主体，`Mesh 2` 是 cutters |
| Boolean 出现破面或极慢 | 优先修复 manifold/自交，仅按需开启容错选项 |
| Extrude 后无法区分新面 | 直接保存并使用 `Top`、`Side` 输出 field |
| Scale Elements 的相邻面一起缩放 | 相连选择会成组；先 Split Edges 或调整 selection |
| Edge Path 没有形成完整 curve | Next Vertex Index 必须沿真实相邻 edge 指向终点 |
| Shade Smooth 后轮廓仍有棱角 | shading 不改变几何，增加 subdivision 或修改拓扑 |
| 拆边/三角化后旧 index 失效 | 在拓扑操作后重新计算 index 与 selection |

## 相关文档

- `new_node`、动态 socket 与 attrs：`../node_wrangler_usage.md`
- mesh 岛、邻接和最短路径：`mesh_topology_input_nodes.md`
- primitive mesh 创建：`mesh_primitive_nodes.md`
- 几何筛选、删除、合并与焊接：`geometry_structure_nodes.md`
- field 捕获与具名属性：`attribute_field_nodes.md`
- points 实例化：`instance_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/assets/utils/shortest_path.py`
- `infinigen/assets/objects/corals/star.py`
- `infinigen/assets/objects/corals/tube.py`
- `infinigen/assets/objects/rocks/boulder.py`
- [Blender 4.2 Mesh Operation Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/operations/index.html)
- [Blender 4.2 Set Shade Smooth](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/write/set_shade_smooth.html)
- [Blender 4.2 Mesh Boolean](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/operations/mesh_boolean.html)
- [Blender 4.2 Extrude Mesh](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/operations/extrude_mesh.html)
- [Blender 4.2 Triangulate](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/operations/triangulate.html)
