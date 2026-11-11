# Mesh 拓扑输入节点

本文档覆盖 mesh 岛、边端点、边角度、面面积、邻接数量和最短边路径。参数表只列当前节点实际需要的 `new_node` 参数。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.MeshIsland` | 读取连通岛索引与岛数量 |
| `Nodes.InputEdgeVertices` | 读取每条边的两个顶点索引和位置 |
| `Nodes.InputEdgeAngle` | 读取相邻面的有符号/无符号夹角 |
| `Nodes.InputMeshFaceArea` | 读取每个面的表面积 |
| `Nodes.ShortestEdgePath` | 计算各顶点到目标顶点的最低成本路径 |
| `Nodes.EdgeNeighbors` | 读取每条边连接的面数量 |
| `Nodes.FaceNeighbors` | 读取面的顶点数和相邻面数 |
| `Nodes.VertexNeighbors` | 读取顶点连接的顶点数和面数 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。

## 共性规则

- 这些节点不接收显式 mesh socket，而是在下游节点提供的当前 mesh 上求值。
- 除 `ShortestEdgePath` 外均无输入和节点属性；输出是 field，不是当前场景中某个固定 mesh 的立即计算结果。
- 每个输出都有原生 domain；连接到其他 domain 时 Blender 会插值。拓扑判断应尽量在原生 domain 上使用。
- mesh 拓扑改变后，index、岛编号和邻接数量都可能变化。

## `Nodes.MeshIsland`

**作用**：识别由边连接形成的独立 mesh 岛。

**创建方式**：

```python
islands = nw.new_node(Nodes.MeshIsland)
island_index = islands.outputs["Island Index"]
island_count = islands.outputs["Island Count"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MeshIsland`，对应 `GeometryNodeInputMeshIsland` |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Island Index` | Integer field | 每个顶点所属连通岛的编号 |
| `Island Count` | Integer | 当前 mesh 的岛总数，不随元素变化 |

两个顶点只要通过边连通就属于同一岛；仅空间重合但没有边连接仍是不同岛。编号由内部顶点顺序决定，适合分组和随机 seed，不应作为跨拓扑修改的持久资产 ID。

## `Nodes.InputEdgeVertices`

**作用**：在 edge domain 上读取每条边两端的顶点索引和位置。

**创建方式**：

```python
edge_vertices = nw.new_node(Nodes.InputEdgeVertices)
p1 = edge_vertices.outputs["Position 1"]
p2 = edge_vertices.outputs["Position 2"]
edge_length = nw.vector_math("DISTANCE", p1, p2)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.InputEdgeVertices`，对应 `GeometryNodeInputMeshEdgeVertices` |

**Input Sockets**：无。

**Output Sockets**：`Vertex Index 1`、`Vertex Index 2`（Integer field），`Position 1`、`Position 2`（Vector field）。

两端的 `1`/`2` 顺序是任意的，不要据此推断边方向。Position 输出等价于用对应 vertex index 在 point domain 读取 Position，适合直接计算长度或方向。

## `Nodes.InputEdgeAngle`

**作用**：在 edge domain 上计算一条边两侧面的夹角。

**创建方式**：

```python
edge_angle = nw.new_node(Nodes.InputEdgeAngle)
sharpness = edge_angle.outputs["Unsigned Angle"]
signed_angle = edge_angle.outputs["Signed Angle"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.InputEdgeAngle`，对应 `GeometryNodeInputMeshEdgeAngle` |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Unsigned Angle` | Float field | 最小夹角，范围 `[0, pi]` |
| `Signed Angle` | Float field | 凹边为正、凸边为负，用于区分折叠方向 |

单位为弧度。平边、边界边和其他非流形边输出 `0`，因此“角度为零”不能单独证明一条边是平坦内边；需要结合 `EdgeNeighbors.outputs["Face Count"] == 2`。不区分凹凸时优先使用计算稍轻的 `Unsigned Angle`。

## `Nodes.InputMeshFaceArea`

**作用**：在 face domain 上读取每个面的表面积。

**创建方式**：

```python
face_area = nw.new_node(Nodes.InputMeshFaceArea).outputs["Area"]
large_faces = nw.compare("GREATER_THAN", face_area, 0.1)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.InputMeshFaceArea`，对应 `GeometryNodeInputMeshFaceArea` |

**Input Sockets**：无。

**Output Sockets**：`Area`（Float field，Blender unit 的平方）。

面积来自当前 node tree 中的 mesh 局部空间。非平面 quad/n-gon 的结果可能只是近似；需要与可见三角划分严格一致时先使用 `Triangulate`。计算整个 mesh 面积时把该 field 传给 face domain 的 `AttributeStatistic`。

## `Nodes.ShortestEdgePath`

**作用**：沿 mesh 边计算每个顶点到最近目标顶点的最低累计成本路径。

**创建方式**：

```python
paths = nw.new_node(
    Nodes.ShortestEdgePath,
    input_kwargs={
        "End Vertex": end_selection,
        "Edge Cost": edge_length,
    },
)
next_vertex = paths.outputs["Next Vertex Index"]
total_cost = paths.outputs["Total Cost"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ShortestEdgePath`，对应 `GeometryNodeInputShortestEdgePaths` |
| `input_kwargs` | `End Vertex`、`Edge Cost` |

**Input Sockets**：

| Socket | 类型 | 原生 domain | 说明 |
| --- | --- | --- | --- |
| `End Vertex` | Boolean field | Point | 标记路径终点；可有多个终点 |
| `Edge Cost` | Float field | Edge | 经过每条边的非负成本；常用边长 |

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Next Vertex Index` | Integer field | 每个顶点沿最低成本路径前进时的下一个顶点索引 |
| `Total Cost` | Float field | 从当前顶点到最近终点的剩余累计成本 |

该节点输出的是路径编码，不直接生成 selection 或 curve。通常把 `Next Vertex Index` 传给 `EdgePathToCurve`；若要按真实距离寻路，可用 `InputEdgeVertices` 的两个 Position 计算 `Edge Cost`。避免负成本，并确保每个相关连通岛至少有一个 `End Vertex`。

## `Nodes.EdgeNeighbors`

**作用**：在 edge domain 上读取每条边连接的面数量。

**创建方式**：

```python
face_count = nw.new_node(Nodes.EdgeNeighbors).outputs["Face Count"]
boundary = nw.compare("EQUAL", face_count, 1)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.EdgeNeighbors`，对应 `GeometryNodeInputMeshEdgeNeighbors` |

**Input Sockets**：无。

**Output Sockets**：`Face Count`（Integer field）。

`0` 表示 loose edge，`1` 表示边界边，`2` 通常表示流形内边，大于 `2` 表示非流形边。它适合补足 `InputEdgeAngle` 无法区分平边与边界边的问题。

## `Nodes.FaceNeighbors`

**作用**：在 face domain 上读取每个面的顶点数量和共享边的相邻面数量。

**创建方式**：

```python
face_neighbors = nw.new_node(Nodes.FaceNeighbors)
vertex_count = face_neighbors.outputs["Vertex Count"]
neighbor_count = face_neighbors.outputs["Face Count"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.FaceNeighbors`，对应 `GeometryNodeInputMeshFaceNeighbors` |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Vertex Count` | Integer field | 当前 face 的顶点数，可区分 triangle、quad 和 n-gon |
| `Face Count` | Integer field | 与当前 face 共享边的其他 face 数量 |

`Vertex Count` 可用于筛选 n-gon；`Face Count` 可识别边界附近或异常连接的面。不要把后者理解为仅共享一个顶点的所有面。

## `Nodes.VertexNeighbors`

**作用**：在 point domain 上读取每个顶点通过边连接的顶点数，以及包含该顶点的面数。

**创建方式**：

```python
neighbors = nw.new_node(Nodes.VertexNeighbors)
valence = neighbors.outputs["Vertex Count"]
incident_faces = neighbors.outputs["Face Count"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.VertexNeighbors`，对应 `GeometryNodeInputMeshVertexNeighbors` |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Vertex Count` | Integer field | 通过边直接连接的相邻顶点数，即 vertex valence |
| `Face Count` | Integer field | 包含当前顶点的面数 |

`Vertex Count == 0` 可识别 loose vertex，规则网格内部通常为 `4`。边界、极点和非流形拓扑需要结合两个输出判断，不能只靠一个固定 valence。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把无输入节点理解为读取任意指定 mesh | 它们在下游提供的当前 mesh 上求值 |
| 依赖 Edge Vertices 的 `1`/`2` 推断方向 | 两端顺序不保证稳定 |
| 用 Edge Angle 的零值识别平边 | 同时要求 Edge Neighbors 的 `Face Count == 2` |
| 把 Face Neighbors 的 Vertex Count 当相邻顶点数 | 它是当前 face 自身的顶点数 |
| Shortest Edge Path 没有产生曲线 | 把 `Next Vertex Index` 连接到 `EdgePathToCurve` |
| 拓扑修改后仍依赖原 index 或岛编号 | 在修改前保存稳定 ID/attribute，或修改后重新计算 |

## 相关文档

- `new_node` 与 field 输出：`../node_wrangler_usage.md`
- Index、Position 和 Normal：`geometry_input_info_nodes.md`
- field domain 与统计：`attribute_field_nodes.md`
- 几何筛选与删除：`geometry_structure_nodes.md`
- Edge Path、Triangulate 和 mesh 操作：`mesh_operations_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/assets/utils/shortest_path.py`
- `infinigen/assets/objects/corals/fan.py`
- `infinigen/assets/objects/rocks/boulder.py`
- `infinigen/assets/objects/underwater/urchin.py`
- [Blender 4.2 Mesh Read Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/read/index.html)
- [Blender 4.2 Edge Vertices](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/read/edge_vertices.html)
- [Blender 4.2 Edge Angle](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/read/edge_angle.html)
- [Blender 4.2 Mesh Island](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/read/mesh_island.html)
- [Blender 4.2 Shortest Edge Paths](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/mesh/read/shortest_edge_paths.html)
