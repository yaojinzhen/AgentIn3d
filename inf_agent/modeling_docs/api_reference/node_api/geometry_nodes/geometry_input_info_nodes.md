# 几何输入与信息节点

本文档覆盖外部 object/collection/image 信息，以及当前几何字段上下文中的 ID、Position、Normal、Index 和 Radius。参数表只列当前节点实际需要的 `new_node` 参数。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.CollectionInfo` | 引用 collection 并输出实例 |
| `Nodes.ObjectInfo` | 引用 object 的几何和变换 |
| `Nodes.InputID` | 读取稳定 ID，缺失时回退到 Index |
| `Nodes.InputPosition` | 读取当前元素的位置 |
| `Nodes.InputNormal` | 读取当前元素的单位法线 |
| `Nodes.Index` | 读取当前 domain 中的零基索引 |
| `Nodes.IsViewport` | 区分 viewport 与最终渲染求值 |
| `Nodes.ImageInfo` | 读取图像尺寸、帧数和帧率 |
| `Nodes.Radius` | 读取 curve/point cloud 的点半径 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。

## 共性规则

- `CollectionInfo`、`ObjectInfo`、`ImageInfo` 从显式 input data-block 读取信息。
- `InputID`、`InputPosition`、`InputNormal`、`Index`、`Radius` 没有输入；它们是 field，值由下游节点的求值 domain 和几何上下文决定。
- 多输出节点必须显式选择 `outputs["..."]`，不要依赖第一个输出。
- Geometry Nodes 的 `ObjectInfo` 与 Shader 的 `ObjectInfo_Shader` 是不同节点。

## `Nodes.CollectionInfo`

**作用**：把 collection 的对象作为实例引入 node tree，常用于可随机选择的部件集合。

**创建方式**：

```python
collection_info = nw.new_node(
    Nodes.CollectionInfo,
    input_kwargs={
        "Collection": parts,
        "Separate Children": True,
        "Reset Children": True,
    },
    attrs={"transform_space": "RELATIVE"},
)
instances = collection_info.outputs["Instances"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CollectionInfo`，对应 `GeometryNodeCollectionInfo` |
| `attrs` | `transform_space`：`ORIGINAL`/`RELATIVE` |
| `input_kwargs` | `Collection`、`Separate Children`、`Reset Children` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Collection` | Collection | Blender collection 或 Collection socket |
| `Separate Children` | Boolean | `True` 时每个直接子对象/子 collection 成为独立实例 |
| `Reset Children` | Boolean | 分离子项时清除各子项自身变换，使实例原点便于统一放置 |

**Output Sockets**：`Instances`（Geometry）。

`ORIGINAL` 保留相对于 collection offset 的变换；`RELATIVE` 保持 collection 与当前 modifier object 的场景相对位置。用于 `InstanceOnPoints` 的候选集合时通常设置两个 Boolean 为 `True`；需要逐顶点修改时先 `RealizeInstances`。

## `Nodes.ObjectInfo`

**作用**：读取外部 object 的几何、变换矩阵及分解后的 Location、Rotation、Scale。

**创建方式**：

```python
object_info = nw.new_node(
    Nodes.ObjectInfo,
    input_kwargs={"Object": source_obj, "As Instance": False},
    attrs={"transform_space": "RELATIVE"},
)
geometry = object_info.outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ObjectInfo`，对应 `GeometryNodeObjectInfo` |
| `attrs` | `transform_space`：`ORIGINAL`/`RELATIVE` |
| `input_kwargs` | `Object`、`As Instance` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Object` | Object | Blender object 或 Object socket |
| `As Instance` | Boolean | 将整个 object 作为单个实例输出 |

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Transform` | Matrix | 包含 Location、Rotation、Scale 的完整变换 |
| `Location` | Vector | object 位置 |
| `Rotation` | Rotation | object 旋转 |
| `Scale` | Vector | object 缩放 |
| `Geometry` | Geometry | 应用 modifier 后的 object 几何，或单个实例 |

`ORIGINAL` 以输入 object 自身变换为基准，变换输出相对世界原点；`RELATIVE` 把结果转换到当前 modifier object 的相对空间。组合不同 object 的几何时通常使用 `RELATIVE`。只有需要继续实例化或引用非几何对象时才启用 `As Instance`。

## `Nodes.InputID`

**作用**：读取内建 `id` attribute，常用于拓扑变化后仍尽量稳定的随机结果。

**创建方式**：

```python
element_id = nw.new_node(Nodes.InputID).outputs["ID"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.InputID`，对应 `GeometryNodeInputID` |

**Input Sockets**：无。

**Output Sockets**：`ID`（Integer field）。

如果当前几何没有 `id` attribute，输出会回退到 `Index`。需要主动建立稳定 ID 时使用 `SetID`；给 Random Value 连接 ID 可减少拓扑轻微变化引起的随机跳变。

## `Nodes.InputPosition`

**作用**：读取当前元素在几何局部空间中的位置，是坐标建模和程序纹理的主要输入。

**创建方式**：

```python
position = nw.new_node(Nodes.InputPosition).outputs["Position"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.InputPosition`，对应 `GeometryNodeInputPosition` |

**Input Sockets**：无。

**Output Sockets**：`Position`（Vector field）。

在非 Point domain 上，位置由 Point 数据自动插值，例如 edge 上通常是端点位置的平均值；在 Instance domain 上表示实例原点。它不是世界坐标，需要世界或 object 间变换时结合 Object Info。

## `Nodes.InputNormal`

**作用**：读取当前元素的单位法线，用于朝向、表面选择和法向偏移。

**创建方式**：

```python
normal = nw.new_node(Nodes.InputNormal).outputs["Normal"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.InputNormal`，对应 `GeometryNodeInputNormal` |

**Input Sockets**：无。

**Output Sockets**：`Normal`（Vector field）。

Face domain 返回面法线，mesh Point/Edge domain 使用相邻法线插值，Corner domain 返回所属面的法线；curve Point domain 返回与切线垂直的曲线法线。需要曲线路径方向时使用 `CurveTangent`，不要把 Normal 当作 tangent。

## `Nodes.Index`

**作用**：读取当前 domain 中每个元素从 0 开始的内部索引。

**创建方式**：

```python
index = nw.new_node(Nodes.Index).outputs["Index"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Index`，对应 `GeometryNodeInputIndex` |

**Input Sockets**：无。

**Output Sockets**：`Index`（Integer field）。

Index 适合奇偶分组、周期图案和当前拓扑内的查表，但几何生成、删除、合并或 Blender 算法更新都可能改变顺序。需要跨拓扑步骤保持标识时先保存 ID 或 attribute。

## `Nodes.IsViewport`

**作用**：判断 Geometry Nodes 当前是否为 viewport 预览求值。

**创建方式**：

```python
is_viewport = nw.new_node(Nodes.IsViewport).outputs["Is Viewport"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.IsViewport`，对应 `GeometryNodeIsViewport` |

**Input Sockets**：无。

**Output Sockets**：`Is Viewport`（Boolean；viewport 为 `True`，最终渲染为 `False`）。

可配合 `Switch` 降低 viewport 的细分或实例数量。不要用它改变资产的语义结构、材质分区或稳定 ID，否则预览和渲染结果会不一致。

## `Nodes.ImageInfo`

**作用**：读取静态图像、图像序列或视频在指定帧的尺寸与动画信息。

**创建方式**：

```python
image_info = nw.new_node(
    Nodes.ImageInfo,
    input_kwargs={"Image": image, "Frame": 0},
)
aspect = nw.scalar_divide(
    image_info.outputs["Width"],
    image_info.outputs["Height"],
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ImageInfo`，对应 `GeometryNodeImageInfo` |
| `input_kwargs` | `Image`、`Frame` |

**Input Sockets**：`Image`（Image）、`Frame`（Integer）。

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Width` / `Height` | Integer | 指定帧的像素尺寸 |
| `Has Alpha` | Boolean | 指定帧是否含非 1 的 alpha |
| `Frame Count` | Integer | 静态图像为 1 |
| `FPS` | Float | 静态图像为 0 |

该节点只读取元数据，不采样像素；需要颜色值时使用 Geometry Image Texture。`Frame` 只影响逐帧输出，不改变 Frame Count 和 FPS。

## `Nodes.Radius`

**作用**：读取 curve control point 或 point cloud point 的内建半径。

**创建方式**：

```python
radius = nw.new_node(Nodes.Radius).outputs["Radius"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Radius`，对应 `GeometryNodeInputRadius` |

**Input Sockets**：无。

**Output Sockets**：`Radius`（Float field）。

curve radius 会影响 `CurveToMesh` 的截面尺寸，point cloud radius 影响点的显示和后续点处理。Mesh 上通常没有有意义的 radius；设置 curve 或 point 半径分别使用 `SetCurveRadius`、`SetPointRadius`。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把 Geometry Object Info 与 Shader Object Info 混用 | Geometry tree 使用 `Nodes.ObjectInfo` |
| Object/Collection 组合后位置偏移 | 确认 `transform_space`，跨 object 组合通常用 `RELATIVE` |
| 对 Collection Info 输出直接做逐顶点操作 | 先使用 `RealizeInstances` |
| 用 Index 作为长期稳定标识 | 使用 ID，并在必要时通过 `SetID` 建立 |
| 把 Position 当作世界坐标 | 它是当前几何上下文的局部坐标 |
| 用 Image Info 读取像素颜色 | 改用 Geometry Image Texture |

## 相关文档

- `new_node` 与输出选择：`../node_wrangler_usage.md`
- Object/Collection interface：`../nodegroup_authoring.md`
- ID、Position 等字段的存储与求值：`attribute_field_nodes.md`
- Geometry Image Texture：`../common_nodes/texture_nodes.md`
- 实例创建与 realize：`instance_nodes.md`
- Set ID 与几何变换：`geometry_write_shape_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/core/placement/instance_scatter.py`
- `infinigen/assets/utils/nodegroup.py`
- [Blender 4.2 Collection Info](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/input/scene/collection_info.html)
- [Blender 4.2 Object Info](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/input/scene/object_info.html)
- [Blender 4.2 Image Info](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/input/scene/image_info.html)
- [Blender 4.2 Geometry Read Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/geometry/read/index.html)
- [Blender 4.2 Is Viewport](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/input/scene/is_viewport.html)
