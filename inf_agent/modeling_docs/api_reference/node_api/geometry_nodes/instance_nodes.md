# 实例节点

本文档覆盖 `Nodes` 枚举中的实例创建、变换与实现节点，并补充室内资产源码高频使用的 Geometry to Instance。每节只列当前节点实际需要的 `new_node` 参数；通用参数语义见 `../node_wrangler_usage.md`。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `"GeometryNodeGeometryToInstance"` | 把一项或多项现有 geometry 包装为独立实例 |
| `Nodes.InstanceOnPoints` | 在 mesh、curve 或 point cloud 的 point domain 上创建实例 |
| `Nodes.TranslateInstances` | 平移选中的顶层实例 |
| `Nodes.RotateInstances` | 绕指定 pivot 旋转选中的顶层实例 |
| `Nodes.ScaleInstances` | 相对指定 center 缩放选中的顶层实例 |
| `Nodes.RealizeInstances` | 将实例转换为可逐元素编辑的真实几何 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。这些节点属于同一条紧密工作流，无需拆分文档。

## 共性规则

- 常用流程是 `points -> InstanceOnPoints -> Translate/Rotate/Scale Instances -> RealizeInstances`。
- 实例共享底层几何，通常比直接复制 mesh 更省内存。尽量在最终需要逐顶点编辑、合并或整体布尔前再 realize。
- 三个变换节点只修改顶层实例，不修改输入中的真实 geometry，也不会直接进入嵌套实例内部。
- `Selection` 是在 point 或 instance domain 上求值的 Boolean field；可为不同实例提供不同的变换 mask。
- `Local Space=True` 时向量、轴和 pivot/center 相对各实例的初始变换解释；为 `False` 时使用 modifier object 的局部空间。
- Rotation socket 在 Blender 4.2 中是 Rotation 类型；`NodeWrangler` 可接收以弧度表示的 `(x, y, z)` Euler tuple。

## `"GeometryNodeGeometryToInstance"`

**作用**：把输入 geometry 包装成实例，不复制底层数据；常与 Duplicate Elements 或 Instance on Points 组合。

**创建方式**：

```python
prototype = nw.new_node(
    "GeometryNodeGeometryToInstance",
    input_kwargs={"Geometry": part_geometry},
).outputs["Instances"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | raw `GeometryNodeGeometryToInstance`；`Nodes` 中没有对应成员 |
| `input_kwargs` | `Geometry`（multi-input，可传单项或 geometry/socket 列表） |

**Input Sockets**：`Geometry`（multi-input）。

**Output Sockets**：`Instances`（Geometry）。

每个连接到 multi-input 的 geometry 成为独立顶层实例；与 `JoinGeometry` 不同，本节点不合并底层数据。生成可供 `Pick Instance=True` 选择的候选集合，或在 `DuplicateElements(domain="INSTANCE")` 前包装真实几何时优先使用。

## `Nodes.InstanceOnPoints`

**作用**：在输入几何的选中 points 上引用同一份几何，生成轻量实例。

**创建方式**：

```python
instances = nw.new_node(
    Nodes.InstanceOnPoints,
    input_kwargs={
        "Points": points,
        "Selection": True,
        "Instance": prototype,
        "Rotation": (0.0, 0.0, 0.0),
        "Scale": (1.0, 1.0, 1.0),
    },
).outputs["Instances"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.InstanceOnPoints`，对应 `GeometryNodeInstanceOnPoints` |
| `input_kwargs` | `Points`、`Selection`、`Instance`、`Pick Instance`、`Instance Index`、`Rotation`、`Scale` |

**Input Sockets**：`Points`（Geometry）；`Selection`（Boolean field）；`Instance`（Geometry）；`Pick Instance`（Boolean）；`Instance Index`（Integer field）；`Rotation`（Rotation field）；`Scale`（Vector field）。

**Output Sockets**：`Instances`（Geometry）。

`Points` 可来自 mesh vertices、curve control points 或 point cloud；原 points geometry 不会包含在输出中。Point-domain attributes 会传递到生成结果的 instance domain。

`Pick Instance=False` 时，每个点放置整个 `Instance` 输入。设为 `True` 时，输入应包含多个独立实例，节点按 `Instance Index` 选择其中一个；越界索引会循环到有效范围。

## `Nodes.TranslateInstances`

**作用**：平移选中的顶层实例，并保留实例共享关系。

**创建方式**：

```python
instances = nw.new_node(
    Nodes.TranslateInstances,
    input_kwargs={
        "Instances": instances,
        "Selection": selection,
        "Translation": (0.0, 0.0, 0.2),
        "Local Space": True,
    },
).outputs["Instances"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.TranslateInstances`，对应 `GeometryNodeTranslateInstances` |
| `input_kwargs` | `Instances`、`Selection`、`Translation`、`Local Space` |

**Input Sockets**：`Instances`（Geometry）；`Selection`（Boolean field）；`Translation`（Vector field）；`Local Space`（Boolean field）。

**Output Sockets**：`Instances`（Geometry）。

`Local Space=True` 时 `(0, 0, d)` 沿每个实例自身的 Z 轴移动，适合按表面法线方向抬升散布物；为 `False` 时所有实例按 node group 坐标的同一方向移动。

## `Nodes.RotateInstances`

**作用**：让选中的顶层实例绕指定 pivot 旋转。

**创建方式**：

```python
instances = nw.new_node(
    Nodes.RotateInstances,
    input_kwargs={
        "Instances": instances,
        "Selection": selection,
        "Rotation": (0.0, 0.0, 0.5),
        "Pivot Point": (0.0, 0.0, 0.0),
        "Local Space": True,
    },
).outputs["Instances"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.RotateInstances`，对应 `GeometryNodeRotateInstances` |
| `input_kwargs` | `Instances`、`Selection`、`Rotation`、`Pivot Point`、`Local Space` |

**Input Sockets**：`Instances`（Geometry）；`Selection`（Boolean field）；`Rotation`（Rotation field）；`Pivot Point`（Vector field）；`Local Space`（Boolean field）。

**Output Sockets**：`Instances`（Geometry）。

`Local Space=True` 时 Rotation 轴和 Pivot Point 相对每个实例的初始 transform；默认 pivot `(0, 0, 0)` 即实例自身原点。关闭后，rotation 与 pivot 都在 modifier object 的局部空间中解释，可让一组实例围绕同一个外部位置旋转。

## `Nodes.ScaleInstances`

**作用**：相对指定 center 对选中的顶层实例进行逐轴缩放。

**创建方式**：

```python
instances = nw.new_node(
    Nodes.ScaleInstances,
    input_kwargs={
        "Instances": instances,
        "Selection": selection,
        "Scale": (1.0, 1.0, 1.5),
        "Center": (0.0, 0.0, 0.0),
        "Local Space": True,
    },
).outputs["Instances"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ScaleInstances`，对应 `GeometryNodeScaleInstances` |
| `input_kwargs` | `Instances`、`Selection`、`Scale`、`Center`、`Local Space` |

**Input Sockets**：`Instances`（Geometry）；`Selection`（Boolean field）；`Scale`（Vector field）；`Center`（Vector field）；`Local Space`（Boolean field）。

**Output Sockets**：`Instances`（Geometry）。

`Center` 不一定是实例原点：缩放时实例原点也会相对该位置移动。需要只改变实例自身尺寸时保持 `Center=(0, 0, 0)` 且启用 local space；负 scale 会镜像对应轴。

## `Nodes.RealizeInstances`

**作用**：将选中的实例转换为真实 mesh、curve、point cloud 或 volume component，使后续节点能够逐元素处理。

**创建方式**：

```python
geometry = nw.new_node(
    Nodes.RealizeInstances,
    input_kwargs={
        "Geometry": instances,
        "Selection": True,
        "Realize All": True,
    },
).outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.RealizeInstances`，对应 `GeometryNodeRealizeInstances` |
| `input_kwargs` | `Geometry`、`Selection`、`Realize All`、`Depth` |

**Input Sockets**：`Geometry`；`Selection`（Boolean field，选择顶层实例）；`Realize All`（Boolean）；`Depth`（Integer）。

**Output Sockets**：`Geometry`。

`Realize All=True` 会实现所选顶层实例下的全部嵌套层级，并忽略 `Depth`。若只想展开有限层级，设为 `False` 并传入 `Depth`；未选实例保持为实例。

实现后 instance-domain attributes 会传播到真实几何；若底层几何已有同名属性，底层几何值优先。大量复杂实例会显著增加几何数据量，因此不要仅为材质设置或整体实例变换而提前 realize。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| `InstanceOnPoints` 输出缺少原始 points mesh | 该节点只输出新实例；需要保留原几何时再用 Join Geometry 合并 |
| `Pick Instance=True` 却每个点仍出现整组几何 | 确认 `Instance` 输入包含独立 instances，而不是已 realize/join 的单个 mesh |
| 用 Join Geometry 构建可选实例集合 | 改用 Geometry to Instance 保留独立实例 |
| 实例沿不同方向移动或旋转 | 检查 `Local Space`；统一 node group 方向时设为 `False` |
| Rotation 数值被当成角度 | tuple 使用弧度；90 度应写为约 `1.5708` |
| mesh 节点无法逐顶点修改实例内部 | 在该操作前使用 Realize Instances |
| Realize 后节点树变慢或内存上涨 | 将 realize 后移，并降低实例数或 prototype 复杂度 |
| 设置了 `Depth` 但结果仍全部展开 | 将 `Realize All` 设为 `False` |

## 相关文档

- `new_node` 与 field 输入：`../node_wrangler_usage.md`
- points 的生成与曲线采样：`curve_conversion_shape_nodes.md`、`point_volume_nodes.md`
- primitive prototype：`mesh_primitive_nodes.md`
- 实例朝向所需向量/旋转：`../common_nodes/vector_rotation_mapping_nodes.md`
- realize 后的 mesh 修改：`mesh_operations_nodes.md`
- 合并实例输出与原始几何：`geometry_structure_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/placement/instance_scatter.py`
- `infinigen/assets/objects/cactus/spike.py`
- `infinigen/assets/objects/organizer/hook.py`
- `infinigen/assets/objects/appliances/beverage_fridge.py`
- `infinigen/assets/objects/appliances/dishwasher.py`
- `infinigen/assets/objects/creatures/insects/utils/geom_utils.py`
- [Blender 4.2 Instances Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/instances/index.html)
- [Blender Geometry to Instance](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/geometry_to_instance.html)
- [Blender Instance on Points](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/instances/instance_on_points.html)
- [Blender Translate Instances](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/instances/translate_instances.html)
- [Blender Rotate Instances](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/instances/rotate_instances.html)
- [Blender Scale Instances](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/instances/scale_instances.html)
- [Blender Realize Instances](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/instances/realize_instances.html)
