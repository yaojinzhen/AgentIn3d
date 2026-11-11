# 曲线属性与拓扑节点

本文档覆盖 curve 半径、倾斜、spline 类型、Bezier handle、求值分辨率和相邻 control point 查询。每节只列当前节点实际需要的 `new_node` 参数；通用参数语义见 `../node_wrangler_usage.md`。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.SetCurveRadius` | 写入 control point 半径 |
| `Nodes.SetCurveTilt` | 写入 control point 倾斜角 |
| `Nodes.CurveSplineType` / `Nodes.SplineType` | 转换 spline 类型；二者是同一节点 |
| `Nodes.SetHandlePositions` | 设置 Bezier 左或右 handle 的位置 |
| `Nodes.SetHandleType` | 设置 Bezier 左/右 handle 类型 |
| `Nodes.SetSplineResolution` | 写入 spline 的 evaluated 分辨率 |
| `Nodes.OffsetPointinCurve` | 查询同一 spline 上偏移若干 control points 的索引 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。属性通常应在转换为 mesh/points 前写入；point index 会随重采样和拓扑编辑变化。

## `Nodes.SetCurveRadius`

**作用**：设置选中 control points 的半径，供 curve sweep 或 point 转换读取。

**创建方式**：

```python
curves = nw.new_node(
    Nodes.SetCurveRadius,
    input_kwargs={"Curve": curves, "Selection": mask, "Radius": radius},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SetCurveRadius`，对应 `GeometryNodeSetCurveRadius` |
| `input_kwargs` | `Curve`、`Selection`、`Radius` |

**Input Sockets**：`Curve`；`Selection`（Boolean field）；`Radius`（Float distance field，point domain）。

**Output Sockets**：`Curve`。

`Radius` 是 profile 的缩放因子，不是最终世界单位管径；实际截面还由 profile 尺寸决定。

## `Nodes.SetCurveTilt`

**作用**：设置选中 control points 绕切线方向的倾斜角。

**创建方式**：

```python
curves = nw.new_node(
    Nodes.SetCurveTilt,
    input_kwargs={"Curve": curves, "Selection": mask, "Tilt": angle},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SetCurveTilt`，对应 `GeometryNodeSetCurveTilt` |
| `input_kwargs` | `Curve`、`Selection`、`Tilt` |

**Input Sockets**：`Curve`；`Selection`；`Tilt`（Float angle field，弧度）。

**Output Sockets**：`Curve`。

Tilt 会旋转 curve normal 与 `CurveToMesh` 的 profile 朝向；圆形截面通常看不出变化，非对称截面才需要显式控制。

## `Nodes.CurveSplineType` / `Nodes.SplineType`

**作用**：把选中 splines 转为指定类型。

**创建方式**：

```python
bezier = nw.new_node(
    Nodes.CurveSplineType,
    input_kwargs={"Curve": curves, "Selection": spline_mask},
    attrs={"spline_type": "BEZIER"},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | 推荐 `Nodes.CurveSplineType`；`Nodes.SplineType` 是同一 `GeometryNodeCurveSplineType` 的别名 |
| `attrs` | `spline_type`：`CATMULL_ROM`、`POLY`、`BEZIER`、`NURBS` |
| `input_kwargs` | `Curve`、`Selection`（spline domain） |

**Input Sockets**：`Curve`、`Selection`。

**Output Sockets**：`Curve`。

类型转换可能改变 evaluated 形状和 point 数；设置 Bezier handle 前先转为 `BEZIER`。

## `Nodes.SetHandlePositions`

**作用**：设置 Bezier control point 的左侧或右侧 handle 位置。

**创建方式**：

```python
curves = nw.new_node(
    Nodes.SetHandlePositions,
    input_kwargs={"Curve": bezier, "Selection": mask, "Offset": offset},
    attrs={"mode": "LEFT"},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SetHandlePositions`，对应 `GeometryNodeSetCurveHandlePositions` |
| `attrs` | `mode`：`LEFT` 或 `RIGHT` |
| `input_kwargs` | `Curve`、`Selection`、`Position`、`Offset` |

**Input Sockets**：`Curve`；`Selection`；`Position`、`Offset`（Vector field）。

**Output Sockets**：`Curve`。

只影响 Bezier splines；`Position` 是目标位置，`Offset` 在其上附加相对位移。需要同时修改两侧时创建两个节点。

## `Nodes.SetHandleType`

**作用**：设置选中 Bezier control points 的左侧、右侧或两侧 handle 类型。

**创建方式**：

```python
curves = nw.new_node(
    Nodes.SetHandleType,
    input_kwargs={"Curve": bezier, "Selection": mask},
    attrs={"handle_type": "AUTO", "mode": {"LEFT", "RIGHT"}},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SetHandleType`，对应 `GeometryNodeCurveSetHandles` |
| `attrs` | `handle_type`：`FREE`、`AUTO`、`VECTOR`、`ALIGN`；`mode` 是 `{"LEFT"}`、`{"RIGHT"}` 或两者组成的集合 |
| `input_kwargs` | `Curve`、`Selection` |

**Input Sockets**：`Curve`、`Selection`。

**Output Sockets**：`Curve`。

只影响 Bezier splines。注意 `mode` 是 Python `set`，不是 `"LEFT"` 字符串；手动偏移 handle 前通常先设为 `FREE` 或 `ALIGN`。

## `Nodes.SetSplineResolution`

**作用**：设置选中 splines 每段用于求值的分辨率。

**创建方式**：

```python
curves = nw.new_node(
    Nodes.SetSplineResolution,
    input_kwargs={"Geometry": curves, "Selection": spline_mask, "Resolution": 12},
).outputs["Geometry"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SetSplineResolution`，对应 `GeometryNodeSetSplineResolution` |
| `input_kwargs` | `Geometry`、`Selection`、`Resolution` |

**Input Sockets**：`Geometry`；`Selection`（spline domain）；`Resolution`（Integer field）。

**Output Sockets**：`Geometry`。

当前 socket 名是 `Geometry`，不是 `Curve`。它影响 Bezier/NURBS 等 spline 的 evaluated 密度、采样精度与 `CurveToMesh` 成本，不直接增加 control points。

## `Nodes.OffsetPointinCurve`

**作用**：从指定 control point 沿同一 spline 前后移动若干点，返回目标全局 point index。

**创建方式**：

```python
lookup = nw.new_node(
    Nodes.OffsetPointinCurve,
    input_kwargs={"Point Index": point_index, "Offset": 1},
)
next_index = lookup.outputs["Point Index"]
valid = lookup.outputs["Is Valid Offset"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.OffsetPointinCurve`，对应 `GeometryNodeOffsetPointInCurve` |
| `input_kwargs` | `Point Index`、`Offset` |

**Input Sockets**：`Point Index`、`Offset`（Integer field）。

**Output Sockets**：`Is Valid Offset`（Boolean field）、`Point Index`（Integer field）。

开放 spline 越界时 `Is Valid Offset=False`；循环 spline 会首尾环绕且任意 offset 有效。默认 Point Index 依赖 point-domain 求值上下文。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| Set Handle Type 报 `expected a set` | 把 `mode` 写成 `{"LEFT"}` 或 `{"LEFT", "RIGHT"}` |
| Set Spline Resolution 找不到 `Curve` socket | Blender 4.2 使用 `Geometry` 输入和输出 |
| Set Handle Positions 没有效果 | 先把目标 spline 转为 `BEZIER`，并检查 `LEFT`/`RIGHT` |
| Curve to Mesh 截面尺寸或朝向异常 | 同时检查本文件的 `Radius`、`Tilt` 与 profile 尺寸 |
| Offset Point 查询到错误点 | 在 point domain 求值，并在拓扑修改后重新获取 index |

## 相关文档

- `new_node`、attrs 和 field：`../node_wrangler_usage.md`
- curve 转换、重采样和形状处理：`curve_conversion_shape_nodes.md`
- curve 长度、参数和索引关系：`curve_read_sampling_nodes.md`
- field 捕获与 domain：`attribute_field_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/assets/objects/trees/utils/geometrynodes.py`
- `infinigen/assets/utils/nodegroup.py`
- `infinigen/assets/utils/shortest_path.py`
- [Blender 4.2 Curve Write Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/write/index.html)
- [Blender 4.2 Offset Point in Curve](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/topology/offset_point_in_curve.html)
