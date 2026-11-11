# 几何写入与形状节点

本文档覆盖稳定 ID、逐点位置、整体变换，以及包围盒和凸包派生。参数表只列当前节点实际需要的 `new_node` 参数。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.SetID` | 写入稳定 `id` attribute |
| `Nodes.SetPosition` | 按 field 设置或偏移几何点位置 |
| `Nodes.Transform` | 对整个 geometry 做平移、旋转和缩放 |
| `Nodes.BoundingBox` | 输出轴对齐包围盒及 Min/Max |
| `Nodes.ConvexHull` | 从输入点集生成凸包 mesh |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。

## 共性规则

- `SetPosition` 逐元素求值，`Transform` 对整个组件应用统一变换。
- `Position` 是绝对位置，`Offset` 是在原位置上叠加的位移；只需变形时优先使用 `Offset`。
- `BoundingBox` 和 `ConvexHull` 会派生新 mesh，不是查询后原样传递输入。
- 需要把实例内部真实顶点计入包围或凸包时，先使用 `RealizeInstances`。

## `Nodes.SetID`

**作用**：为选中的 point 或 instance 写入 `id` attribute，使随机结果在部分拓扑变化后更稳定。

**创建方式**：

```python
with_id = nw.new_node(
    Nodes.SetID,
    input_kwargs={
        "Geometry": geometry,
        "Selection": selection,
        "ID": stable_id,
    },
).outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SetID`，对应 `GeometryNodeSetID` |
| `input_kwargs` | `Geometry`、`Selection`、`ID` |

**Input Sockets**：`Geometry`、`Selection`（Boolean field）、`ID`（Integer field）。

**Output Sockets**：`Geometry`。

未连接 `ID` 时默认使用 index。下游用 `Nodes.InputID` 读取；不要把 `Index` 当作跨删除、重排或复制操作的长期稳定标识。

## `Nodes.SetPosition`

**作用**：在 point domain 上设置绝对位置或添加偏移，用于形变、压扁、弯曲和表面扰动。

**创建方式**：

```python
deformed = nw.new_node(
    Nodes.SetPosition,
    input_kwargs={
        "Geometry": geometry,
        "Selection": selection,
        "Offset": offset,
    },
).outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SetPosition`，对应 `GeometryNodeSetPosition` |
| `input_kwargs` | `Geometry`、`Selection`、`Position`、`Offset` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Geometry` | Geometry | 输入 mesh、curve 或 point cloud |
| `Selection` | Boolean field | 限制被修改的点 |
| `Position` | Vector field | 新的绝对局部位置；默认等于原 Position |
| `Offset` | Vector field | 在 `Position` 结果上追加的局部位移 |

**Output Sockets**：`Geometry`。

它不用于逐实例变换；实例应使用 `TranslateInstances`、`RotateInstances`、`ScaleInstances`。噪声位移通常把 `InputNormal * scalar_noise` 接到 `Offset`。

## `Nodes.Transform`

**作用**：对整个 Geometry 统一平移、旋转和缩放，不按 point field 分别求值。

**创建方式**：

```python
placed = nw.new_node(
    Nodes.Transform,
    input_kwargs={
        "Geometry": geometry,
        "Translation": (0.0, 0.0, 0.8),
        "Rotation": (0.0, 0.0, angle),
        "Scale": (1.0, 1.0, 1.0),
    },
).outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Transform`，对应 `GeometryNodeTransform` |
| `attrs` | 可选 `mode`：`COMPONENTS`（默认）/ `MATRIX` |
| `input_kwargs` | `COMPONENTS`：`Geometry`、`Translation`、`Rotation`、`Scale`；`MATRIX`：`Geometry`、`Transform` |

**Input Sockets**：

| `mode` | Sockets |
| --- | --- |
| `COMPONENTS` | `Geometry`、`Translation`、`Rotation`、`Scale` |
| `MATRIX` | `Geometry`、`Transform`（Matrix） |

**Output Sockets**：`Geometry`。

输入变换位于当前 modifier object 的局部空间。逐点变形使用 `SetPosition`；逐实例变换使用 instance 节点。Infinigen 现有资产主要使用默认 `COMPONENTS` 模式。

## `Nodes.BoundingBox`

**作用**：计算输入几何的局部轴对齐包围盒，并输出边界坐标。

**创建方式**：

```python
bounds = nw.new_node(
    Nodes.BoundingBox,
    input_kwargs={"Geometry": geometry},
)
size = nw.sub2(bounds.outputs["Max"], bounds.outputs["Min"])
box = bounds.outputs["Bounding Box"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.BoundingBox`，对应 `GeometryNodeBoundBox` |
| `input_kwargs` | `Geometry` |

**Input Sockets**：`Geometry`。

**Output Sockets**：`Bounding Box`（Mesh）、`Min`（Vector）、`Max`（Vector）。

包围盒与坐标轴对齐，不是最小旋转包围盒。`Max - Min` 得到尺寸，`(Min + Max) / 2` 得到中心。若输入包含未 realize 的 instances，先确认希望按实例组件处理还是计算合并后的真实边界。

## `Nodes.ConvexHull`

**作用**：用输入几何中的点生成包围它们的最小凸 mesh。

**创建方式**：

```python
hull = nw.new_node(
    Nodes.ConvexHull,
    input_kwargs={"Geometry": geometry},
).outputs["Convex Hull"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ConvexHull`，对应 `GeometryNodeConvexHull` |
| `input_kwargs` | `Geometry` |

**Input Sockets**：`Geometry`。

**Output Sockets**：`Convex Hull`（Mesh）。

凸包会填平凹陷和孔洞，适合作为粗略外壳、碰撞体或后续建模基底，不适合保留原始凹形轮廓。多个分离部件一起输入时会生成包围全部部件的共同凸包。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 用 `Transform` 做每点不同的位移 | 使用 `SetPosition` 和 field |
| 同时给 `Position` 与 `Offset`，结果重复位移 | 仅在确实需要绝对位置加增量时同时连接 |
| 用 Set Position 移动未 realize 的实例 | 使用 instance transform 节点 |
| 把 Bounding Box 当成只输出数值的查询 | 它还会创建新的 box mesh |
| 用 Convex Hull 保留凹槽或孔洞 | 使用原 mesh 或 Mesh Boolean 流程 |
| 用 Index 作为稳定随机种子 | 先使用 `SetID`，下游读取 `InputID` |

## 相关文档

- `new_node` 参数：`../node_wrangler_usage.md`
- ID、Position、Normal 读取：`geometry_input_info_nodes.md`
- field 和 attribute：`attribute_field_nodes.md`
- 组件合并、删除与复制：`geometry_structure_nodes.md`
- 实例变换和 realize：`instance_nodes.md`
- Mesh 形状编辑：`mesh_operations_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/assets/objects/appliances/`
- `infinigen/assets/materials/creature/`
- [Blender 4.2 Set ID](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/write/set_id.html)
- [Blender 4.2 Set Position](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/write/set_position.html)
- [Blender 4.2 Transform Geometry](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/operations/transform_geometry.html)
- [Blender 4.2 Bounding Box](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/operations/bounding_box.html)
- [Blender 4.2 Convex Hull](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/operations/convex_hull.html)
