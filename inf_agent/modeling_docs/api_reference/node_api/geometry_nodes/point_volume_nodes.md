# 点与体积节点

本文档覆盖 `Nodes` 枚举中的表面点分布、point cloud 编辑以及 points/volume/mesh 转换节点，并补充源码使用的 raw Points primitive。常规单体建模优先使用点分布与实例化；volume 路径适合融合形体或雾状中间表示，但计算成本较高。两类接口均完整保留。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `"GeometryNodePoints"` | 按 Count、Position 和 Radius 从零创建 point cloud |
| `Nodes.DistributePointsOnFaces` | 在 mesh 表面随机或按最小间距分布 points |
| `Nodes.PointsToVertices` | 将 point cloud 转换为只含孤立顶点的 mesh |
| `Nodes.SetPointRadius` | 写入选中 point cloud points 的 radius |
| `Nodes.PointsToVolume` | 在每个 point 周围生成 fog volume |
| `Nodes.VolumeToMesh` | 按 density threshold 提取 volume 表面 mesh |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。这些节点构成一组连续的 point/volume 流程，无需拆分文档。

## 共性规则

- 表面重复物体优先使用 `DistributePointsOnFaces -> InstanceOnPoints`，不要先把 points 转为 volume。
- point cloud 与 mesh vertices 是不同 geometry component。`PointsToVertices` 输出没有 edges 和 faces。
- point radius 不等于实例 scale；实例大小应由 Instance on Points 的 `Scale` 控制。
- `distribute_method` 和 `resolution_mode` 会切换可用 socket，必须先通过 `attrs` 选择模式，再传对应 `input_kwargs`。
- Voxel Size 越小或 Voxel Amount 越大，volume 的内存、计算时间和最终 mesh 面数越高。先用粗分辨率验证形状。

## `"GeometryNodePoints"`

**作用**：从零创建 point cloud；Position 和 Radius 可按新点的 Index 求值。

**创建方式**：

```python
points = nw.new_node(
    "GeometryNodePoints",
    input_kwargs={"Count": 8, "Position": (0.0, 0.0, 0.0), "Radius": 0.05},
).outputs["Points"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | raw `GeometryNodePoints`；`Nodes` 中没有对应成员 |
| `input_kwargs` | `Count`、`Position`、`Radius` |

**Input Sockets**：`Count`（Integer）；`Position`（Vector field）；`Radius`（Float distance field）。

**Output Sockets**：`Points`（point cloud）。

由于节点从零生成几何，Position/Radius 字段只能依赖新 points 的 Index 等可在该上下文求值的信息，不能依赖外部 Position field。只需要一个空 point cloud 占位时可设 `Count=0`。

## `Nodes.DistributePointsOnFaces`

**作用**：在输入 mesh 的选中 faces 上生成 point cloud，并输出表面法线和便于实例朝向的 rotation。

**创建方式**：

```python
points = nw.new_node(
    Nodes.DistributePointsOnFaces,
    input_kwargs={
        "Mesh": surface_mesh,
        "Selection": allowed_faces,
        "Distance Min": 0.08,
        "Density Max": 100.0,
        "Density Factor": 1.0,
        "Seed": 7,
    },
    attrs={"distribute_method": "POISSON"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.DistributePointsOnFaces`，对应 `GeometryNodeDistributePointsOnFaces` |
| `attrs` | `distribute_method`：`RANDOM` 或 `POISSON` |
| `input_kwargs` | 共用 `Mesh`、`Selection`、`Seed`；`RANDOM` 使用 `Density`；`POISSON` 使用 `Distance Min`、`Density Max`、`Density Factor` |

**Input Sockets**：

| 模式 | 可用输入 |
| --- | --- |
| `RANDOM` | `Mesh`、`Selection`、`Density`、`Seed` |
| `POISSON` | `Mesh`、`Selection`、`Distance Min`、`Density Max`、`Density Factor`、`Seed` |

**Output Sockets**：`Points`（point cloud）；`Normal`（Vector field）；`Rotation`（Rotation field）。

`RANDOM` 最快，`Density` 表示单位面积的期望点数。`POISSON` 用 `Distance Min` 避免点过近，最终密度由 `Density Max * Density Factor` 控制，但仍受最小间距上限约束。

输入的 point、face-corner 和 face attributes 会插值到新 points，并生成稳定 `id`。`Rotation` 让局部 Z 轴对齐表面 Normal，但绕法线的切向朝向没有唯一解；需要稳定朝向时继续用 rotation/vector 节点约束。

## `Nodes.PointsToVertices`

**作用**：将选中的 point cloud points 转换为 mesh vertices，保留位置并丢弃 point cloud component。

**创建方式**：

```python
vertices = nw.new_node(
    Nodes.PointsToVertices,
    input_kwargs={"Points": points, "Selection": True},
).outputs["Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.PointsToVertices`，对应 `GeometryNodePointsToVertices` |
| `input_kwargs` | `Points`、`Selection` |

**Input Sockets**：`Points`（Geometry，point cloud）；`Selection`（Boolean field）。

**Output Sockets**：`Mesh`。

输出每个选中 point 对应一个孤立 vertex，不自动连接 edges 或 faces。Infinigen 用它将程序化分布位置转换为可应用 modifier、读取 `mesh.vertices` 或导出的临时 mesh。

## `Nodes.SetPointRadius`

**作用**：设置选中 point cloud points 的内置 `radius` 属性。

**创建方式**：

```python
points = nw.new_node(
    Nodes.SetPointRadius,
    input_kwargs={
        "Points": points,
        "Selection": selected_points,
        "Radius": 0.05,
    },
).outputs["Points"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SetPointRadius`，对应 `GeometryNodeSetPointRadius` |
| `input_kwargs` | `Points`、`Selection`、`Radius` |

**Input Sockets**：`Points`（Geometry，point cloud）；`Selection`（Boolean field）；`Radius`（Float distance field）。

**Output Sockets**：`Points`。

Radius 控制 point cloud 的显示和供后续 field 读取，不会自动缩放 Instance on Points 的实例。需要在 Points to Volume 中使用该属性时，将 Radius input node 的输出连接到后者的 `Radius` socket，或直接给该 socket 传相同 field。

## `Nodes.PointsToVolume`

**作用**：以每个输入 point 为中心生成球形 fog density，并合并为名为 `density` 的 volume grid。

**创建方式**：

```python
volume = nw.new_node(
    Nodes.PointsToVolume,
    input_kwargs={
        "Points": points,
        "Density": 1.0,
        "Voxel Size": 0.03,
        "Radius": 0.08,
    },
    attrs={"resolution_mode": "VOXEL_SIZE"},
).outputs["Volume"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.PointsToVolume`，对应 `GeometryNodePointsToVolume` |
| `attrs` | `resolution_mode`：`VOXEL_AMOUNT` 或 `VOXEL_SIZE` |
| `input_kwargs` | 共用 `Points`、`Density`、`Radius`；按模式使用 `Voxel Amount` 或 `Voxel Size` |

**Input Sockets**：`Points`（Geometry）；`Density`（Float field）；动态 `Voxel Amount`（Float）或 `Voxel Size`（Float distance）；`Radius`（Float distance field）。

**Output Sockets**：`Volume`。

`VOXEL_AMOUNT` 指定包围盒对角线方向的大致 voxel 数，物体尺寸改变时 voxel size 随之改变。`VOXEL_SIZE` 固定单个 voxel 的边长，更适合需要跨尺寸或动画保持分辨率稳定的流程。

`Density` 是每个球形区域写入的 fog density，不是 point 数量。Point 坐标或边界极大、Voxel Size 过小都会产生昂贵或不稳定的体素网格。

## `Nodes.VolumeToMesh`

**作用**：按 density 等值面将 volume grid 转换为 mesh。

**创建方式**：

```python
mesh = nw.new_node(
    Nodes.VolumeToMesh,
    input_kwargs={
        "Volume": volume,
        "Threshold": 0.1,
        "Adaptivity": 0.0,
    },
    attrs={"resolution_mode": "GRID"},
).outputs["Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.VolumeToMesh`，对应 `GeometryNodeVolumeToMesh` |
| `attrs` | `resolution_mode`：`GRID`、`VOXEL_AMOUNT` 或 `VOXEL_SIZE` |
| `input_kwargs` | 共用 `Volume`、`Threshold`、`Adaptivity`；后两种模式分别增加 `Voxel Amount` 或 `Voxel Size` |

**Input Sockets**：`Volume`；动态 `Voxel Amount` 或 `Voxel Size`；`Threshold`（Float）；`Adaptivity`（Float factor）。

**Output Sockets**：`Mesh`。

`GRID` 直接沿用输入 volume grid 的分辨率，处理 Points to Volume 输出时通常最直接。`VOXEL_AMOUNT` 和 `VOXEL_SIZE` 会按指定分辨率重采样每个输入 grid。

Density 大于 `Threshold` 的 voxels 被视为内部，mesh 在内外边界生成；提高 threshold 通常会收缩表面。`Adaptivity` 会在细节较少处简化拓扑，降低面数但可能改变轮廓。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| `POISSON` 模式仍传 `Density` | 改传 `Density Max` 与 `Density Factor` |
| 分布数量提高后不再增加 | `Distance Min` 已限制最大可容纳密度 |
| Points to Vertices 后没有面 | 该节点只创建孤立 vertices；需要表面时使用实例、凸包或其他建面流程 |
| Set Point Radius 没有改变实例尺寸 | 改写 Instance on Points 的 `Scale` |
| Points 的 Position 接入外部 Position field | 该节点没有外部几何上下文；改用 Index 构造位置或从已有几何生成 points |
| `Voxel Size` 或 `Voxel Amount` 报找不到 socket | 先将 `resolution_mode` 设置为匹配模式 |
| volume 流程突然很慢或内存上涨 | 增大 Voxel Size、降低 Voxel Amount 或减少 points |
| Volume to Mesh 表面消失 | 检查 `Threshold` 是否高于 density grid 的有效值 |
| 转换后的 mesh 没有预期材质 | Volume to Mesh 后使用 Set Material 重新赋材质 |

## 相关文档

- `new_node`、attrs 与动态 socket：`../node_wrangler_usage.md`
- points 上创建实例：`instance_nodes.md`
- Radius、Normal 和 Position field：`geometry_input_info_nodes.md`
- mesh primitive 与后续拓扑操作：`mesh_primitive_nodes.md`、`mesh_operations_nodes.md`
- geometry 合并与转换：`geometry_structure_nodes.md`
- volume 转换后的材质：`material_nodes.md`
- 向量和 rotation 调整：`../common_nodes/vector_rotation_mapping_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/placement/placement.py`
- `infinigen/core/placement/instance_scatter.py`
- `infinigen/assets/objects/cactus/spike.py`
- `infinigen/assets/objects/cloud/node.py`
- `infinigen/assets/objects/tables/table_utils.py`
- [Blender Points](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/point/points.html)
- [Blender 4.2 Distribute Points on Faces](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/point/distribute_points_on_faces.html)
- [Blender Points to Vertices](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/point/points_to_vertices.html)
- [Blender Set Point Radius](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/point/set_point_radius.html)
- [Blender Points to Volume](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/point/points_to_volume.html)
- [Blender Volume to Mesh](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/volume/operations/volume_to_mesh.html)
