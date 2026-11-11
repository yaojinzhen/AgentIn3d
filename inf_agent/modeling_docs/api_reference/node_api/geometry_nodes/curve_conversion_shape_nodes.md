# 曲线转换与形状节点

本文档覆盖 curve 插值、几何类型转换、重采样、裁剪、反转、填充与圆角。每节只列当前节点实际需要的 `new_node` 参数；通用参数语义见 `../node_wrangler_usage.md`。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.InterpolateCurves` | 在 points 上由 guide curves 插值生成新曲线 |
| `Nodes.CurveToMesh` | 沿 curve 扫掠 profile，生成管、线缆或轮廓 mesh |
| `Nodes.CurveToPoints` | 按 evaluated points、数量或间距把 curve 转为 point cloud |
| `Nodes.MeshToCurve` | 把选中的 mesh edges 转为 poly curves |
| `Nodes.SubdivideCurve` | 在现有 control points 之间插点 |
| `Nodes.ResampleCurve` | 把 spline 重建为均匀 poly control points |
| `Nodes.TrimCurve` | 按 factor 或长度保留 spline 的一段 |
| `Nodes.ReverseCurve` | 反转 spline 的 control point 顺序 |
| `Nodes.FillCurve` | 将闭合平面曲线填充为 mesh |
| `Nodes.FilletCurve` | 将 curve control point 处的尖角圆整 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。

## 共性规则

- `Selection` 只控制被修改的 points 或 splines；未提供时默认为全选。
- `ResampleCurve`、`CurveToPoints` 的 `mode` 会切换可用 socket，先设 `attrs` 再按对应名称传参。
- control point、evaluated point 和 point cloud point 是不同概念；重采样会改变 point index。

## `Nodes.InterpolateCurves`

**作用**：在输入 points 上，按邻近 guide curves 插值生成高密度曲线。

**创建方式**：

```python
interpolated = nw.new_node(
    Nodes.InterpolateCurves,
    input_kwargs={
        "Guide Curves": guides,
        "Guide Up": guide_normals,
        "Points": roots,
        "Point Up": root_normals,
        "Max Neighbors": 4,
    },
).outputs["Curves"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.InterpolateCurves`，对应 `GeometryNodeInterpolateCurves` |
| `input_kwargs` | `Guide Curves`、`Guide Up`、`Guide Group ID`、`Points`、`Point Up`、`Point Group ID`、`Max Neighbors` |

**Input Sockets**：`Guide Curves`、`Points`（Geometry）；两个 `Up`（Vector field）；两个 `Group ID`、`Max Neighbors`（Integer field）。

**Output Sockets**：`Curves`（guide 与新生成 curves）、`Closest Index`、`Closest Weight`。

`Up` 通常使用曲面法线以稳定旋转；相同 Group ID 才互相插值。该节点面向 guide/hair 工作流，普通管线资产通常直接创建或复制 curve。

## `Nodes.CurveToMesh`

**作用**：沿 curve 扫掠 profile curve，生成具有截面的 mesh。

**创建方式**：

```python
mesh = nw.new_node(
    Nodes.CurveToMesh,
    input_kwargs={"Curve": path, "Profile Curve": profile, "Fill Caps": True},
).outputs["Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CurveToMesh`，对应 `GeometryNodeCurveToMesh` |
| `input_kwargs` | `Curve`、`Profile Curve`、`Fill Caps` |

**Input Sockets**：`Curve`、`Profile Curve`（Geometry）；`Fill Caps`（Boolean，仅闭合 profile 可封端）。

**Output Sockets**：`Mesh`（Geometry）。

path 的 `Radius` 缩放截面，`Tilt` 绕切线旋转截面。生成把手、管道和线缆时，常用 `CurveCircle -> SetCurveRadius -> CurveToMesh`。

## `Nodes.CurveToPoints`

**作用**：沿每条 spline 生成 point cloud，并输出朝向字段。

**创建方式**：

```python
points = nw.new_node(
    Nodes.CurveToPoints,
    input_kwargs={"Curve": curves, "Count": 32},
    attrs={"mode": "COUNT"},
)
rotation = points.outputs["Rotation"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CurveToPoints`，对应 `GeometryNodeCurveToPoints` |
| `attrs` | `mode`：`EVALUATED`、`COUNT` 或 `LENGTH` |
| `input_kwargs` | `Curve`；`COUNT` 使用 `Count`，`LENGTH` 使用 `Length` |

**Input Sockets**：`Curve`；动态 `Count`（每条 spline 的点数）或 `Length`（目标间距）；`EVALUATED` 无额外输入。

**Output Sockets**：`Points`、`Tangent`、`Normal`、`Rotation`。

用于沿路径实例化时把 `Rotation` 连接到 `InstanceOnPoints`。它输出 point cloud；若后续仍需 curve，使用 `ResampleCurve`。

## `Nodes.MeshToCurve`

**作用**：把选中的 mesh edges 转为 poly splines。

**创建方式**：

```python
curves = nw.new_node(
    Nodes.MeshToCurve,
    input_kwargs={"Mesh": mesh, "Selection": edge_mask},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MeshToCurve`，对应 `GeometryNodeMeshToCurve` |
| `input_kwargs` | `Mesh`、`Selection`（edge domain） |

**Input Sockets**：`Mesh`（Geometry）、`Selection`（Boolean field）。

**Output Sockets**：`Curve`（Geometry）。

每个相连的选中 edge 链形成 spline；faces 不保留。分叉拓扑会被拆成多条 spline，后续 point index 不应沿用原 mesh vertex index。

## `Nodes.SubdivideCurve`

**作用**：在每段 curve segment 中插入指定数量的 control points。

**创建方式**：

```python
curves = nw.new_node(
    Nodes.SubdivideCurve,
    input_kwargs={"Curve": curves, "Cuts": 4},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SubdivideCurve`，对应 `GeometryNodeSubdivideCurve` |
| `input_kwargs` | `Curve`、`Cuts`（每段插入数量） |

**Input Sockets**：`Curve`、`Cuts`（Integer field，point domain）。

**Output Sockets**：`Curve`。

它增加控制点并插值属性，适合给后续 `SetPosition` 增加自由度；需要固定数量或近似等距点时使用 `ResampleCurve`。

## `Nodes.ResampleCurve`

**作用**：将选中 splines 重建为沿弧长均匀分布的 poly control points。

**创建方式**：

```python
curves = nw.new_node(
    Nodes.ResampleCurve,
    input_kwargs={"Curve": curves, "Selection": spline_mask, "Count": 64},
    attrs={"mode": "COUNT"},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ResampleCurve`，对应 `GeometryNodeResampleCurve` |
| `attrs` | `mode`：`EVALUATED`、`COUNT` 或 `LENGTH` |
| `input_kwargs` | `Curve`、`Selection`；`COUNT` 使用 `Count`，`LENGTH` 使用 `Length` |

**Input Sockets**：`Curve`；`Selection`（spline domain）；动态 `Count` 或目标 `Length`。

**Output Sockets**：`Curve`。

`EVALUATED` 使用上游求值点；`COUNT` 控制每条 spline 点数；`LENGTH` 控制近似间距。输出为 poly splines，point index 与 spline 类型相关属性会改变。

## `Nodes.TrimCurve`

**作用**：按每条 spline 的归一化 factor 或实际长度保留 `[Start, End]` 区间。

**创建方式**：

```python
trimmed = nw.new_node(
    Nodes.TrimCurve,
    input_kwargs={"Curve": curves, "Selection": spline_mask, "Start": 0.1, "End": 0.9},
    attrs={"mode": "FACTOR"},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.TrimCurve`，对应 `GeometryNodeTrimCurve` |
| `attrs` | `mode`：`FACTOR` 或 `LENGTH` |
| `input_kwargs` | `Curve`、`Selection`、动态类型的 `Start`、`End` |

**Input Sockets**：`Curve`；`Selection`（spline domain）；`Start`、`End`（Factor 或 Distance）。

**Output Sockets**：`Curve`。

`FACTOR` 使用每条 spline 的 `0..1` 弧长比例，`LENGTH` 使用从起点量取的距离。裁剪会产生新的端点；先 `ReverseCurve` 可从相反方向量取。

## `Nodes.ReverseCurve`

**作用**：反转选中 splines 的 control point 顺序和方向。

**创建方式**：

```python
reversed_curves = nw.new_node(
    Nodes.ReverseCurve,
    input_kwargs={"Curve": curves, "Selection": spline_mask},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ReverseCurve`，对应 `GeometryNodeReverseCurve` |
| `input_kwargs` | `Curve`、`Selection`（spline domain） |

**Input Sockets**：`Curve`、`Selection`。

**Output Sockets**：`Curve`。

几何形状不变，但 start/end、tangent 方向和 point 顺序反转；方向敏感的 Trim、Spline Parameter 或 profile 朝向应在反转后重新判断。

## `Nodes.FillCurve`

**作用**：把闭合的平面 splines 填充成 mesh faces。

**创建方式**：

```python
mesh = nw.new_node(
    Nodes.FillCurve,
    input_kwargs={"Curve": outlines, "Group ID": group_id},
    attrs={"mode": "NGONS"},
).outputs["Mesh"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.FillCurve`，对应 `GeometryNodeFillCurve` |
| `attrs` | `mode`：`TRIANGLES` 或 `NGONS` |
| `input_kwargs` | `Curve`、`Group ID` |

**Input Sockets**：`Curve`（闭合平面 curve）、`Group ID`（Integer field，隔离独立填充组）。

**Output Sockets**：`Mesh`。

输入应位于同一局部 XY 平面；开放 spline 不会形成区域。`TRIANGLES` 适合稳定下游拓扑，`NGONS` 更简洁但后续 modifier 可能自行三角化。

## `Nodes.FilletCurve`

**作用**：用圆弧替换 control point 处的尖角。

**创建方式**：

```python
rounded = nw.new_node(
    Nodes.FilletCurve,
    input_kwargs={"Curve": curves, "Count": 8, "Radius": radius, "Limit Radius": True},
    attrs={"mode": "POLY"},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.FilletCurve`，对应 `GeometryNodeFilletCurve` |
| `attrs` | `mode`：`BEZIER` 或 `POLY` |
| `input_kwargs` | `Curve`、`Radius`、`Limit Radius`；`POLY` 还使用 `Count` |

**Input Sockets**：`Curve`；`Radius`（point field）；`Limit Radius`；`POLY` 下的 `Count`。

**Output Sockets**：`Curve`。

`BEZIER` 每个圆角生成两个带 aligned handles 的点，细腻度由 spline resolution 决定；`POLY` 直接由 `Count` 控制点数。开启 `Limit Radius` 可避免相邻圆角重叠。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 给动态节点传入了当前 mode 不存在的 socket | 先设置 `attrs={"mode": ...}`，再使用对应 `Count`、`Length` 或 `Start`/`End` |
| 把 `CurveToPoints` 当作 resampled curve | 需要 curve 输出时改用 `ResampleCurve` |
| Curve to Mesh 截面尺寸与预期不符 | 同时检查 profile 尺寸和 curve `Radius` |
| Fill Curve 没有输出面 | 确认 spline 闭合、共面且位于局部 XY 平面 |
| 重采样后索引或类型相关属性失效 | 在重采样后重新计算 index/selection，必要属性提前 Capture/Store |

## 相关文档

- `new_node`、动态 socket 与 attrs：`../node_wrangler_usage.md`
- curve 长度、参数和采样：`curve_read_sampling_nodes.md`
- curve 属性、handle、resolution 与 point offset：`curve_property_topology_nodes.md`
- curve primitive：`curve_primitive_nodes.md`
- field 捕获与 domain：`attribute_field_nodes.md`
- points 实例化：`instance_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/assets/utils/nodegroup.py`
- `infinigen/assets/utils/nodegroups/curve.py`
- `infinigen/assets/objects/elements/doors/bar_handle.py`
- [Blender 4.2 Curve Operation Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/operations/index.html)
- [Blender 4.2 Curve Write Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/write/index.html)
- [Blender 4.2 Curve Topology Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/topology/index.html)
