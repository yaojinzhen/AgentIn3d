# 曲线基础节点

本文档覆盖 `Nodes` 枚举中的基础 curve primitive，并补充室内资产源码高频使用的 raw Arc、Spiral 和 Quadrilateral。每节只列当前节点实际需要的 `new_node` 参数；通用参数语义见 `../node_wrangler_usage.md`。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.QuadraticBezier` | 用三个控制位置生成抛物线形 poly spline |
| `Nodes.CurveCircle` | 按半径或三个空间点生成闭合圆形 poly spline |
| `Nodes.CurveLine` | 按两端点或方向与长度生成直线 poly spline |
| `Nodes.CurveBezierSegment` / `Nodes.BezierSegment` | 用起终点和 handles 生成单段 Bezier spline；二者是同一节点 |
| `"GeometryNodeCurveArc"` | 按半径和角度或三个点生成圆弧 |
| `"GeometryNodeCurveSpiral"` | 生成半径和高度可渐变的螺旋线 |
| `"GeometryNodeCurvePrimitiveQuadrilateral"` | 生成矩形、平行四边形、梯形、风筝形或四点轮廓 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。

## 共性规则

- primitive 坐标位于 node group 的局部空间；整体放置使用 Transform Geometry。
- `Resolution` 决定生成或求值密度，不是 Curve to Mesh 截面的 resolution。
- primitive 只生成 curve component；创建实体管线还需 profile 和 `CurveToMesh`。
- mode 会切换可用 socket，先设置 `attrs` 再传入对应输入。

## `Nodes.QuadraticBezier`

**作用**：按 quadratic Bezier 公式生成经过 Start、End 的抛物线形 poly spline。

**创建方式**：

```python
curve = nw.new_node(
    Nodes.QuadraticBezier,
    input_kwargs={
        "Resolution": 32,
        "Start": (0.0, 0.0, 0.0),
        "Middle": (0.5, 0.0, 1.0),
        "End": (1.0, 0.0, 0.0),
    },
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.QuadraticBezier`，对应 `GeometryNodeCurveQuadraticBezier` |
| `input_kwargs` | `Resolution`、`Start`、`Middle`、`End` |

**Input Sockets**：`Resolution`（Integer，生成的 edge 数）；`Start`、`Middle`、`End`（Vector）。

**Output Sockets**：`Curve`（poly spline）。

`Middle` 是控制位置，曲线通常不经过它；它决定 Start/End 处的切线趋势。需要直接控制两个 Bezier handles 时使用 Bezier Segment。

## `Nodes.CurveCircle`

**作用**：在局部 XY 平面按半径创建圆，或创建经过三个空间点的圆。

**创建方式**：

```python
profile = nw.new_node(
    Nodes.CurveCircle,
    input_kwargs={"Resolution": 16, "Radius": 0.05},
    attrs={"mode": "RADIUS"},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CurveCircle`，对应 `GeometryNodeCurvePrimitiveCircle` |
| `attrs` | `mode`：`RADIUS` 或 `POINTS` |
| `input_kwargs` | 两种模式均用 `Resolution`；`RADIUS` 使用 `Radius`，`POINTS` 使用 `Point 1`、`Point 2`、`Point 3` |

**Input Sockets**：`Resolution`（Integer，圆的 control point 数）；动态 `Radius`（Float distance），或三个 `Point`（Vector）。

**Output Sockets**：`Curve`（闭合 poly spline）；仅 `POINTS` 模式提供 `Center`（Vector）。

`RADIUS` 模式以原点为圆心并位于 XY 平面，常用作 `CurveToMesh` profile。`POINTS` 模式的三个点必须不共线，适合按已有位置确定圆的平面、圆心和半径。

## `Nodes.CurveLine`

**作用**：生成仅含两个 control points 的直线 poly spline。

**创建方式**：

```python
line = nw.new_node(
    Nodes.CurveLine,
    input_kwargs={
        "Start": (0.0, 0.0, 0.0),
        "Direction": (0.0, 0.0, 1.0),
        "Length": 2.0,
    },
    attrs={"mode": "DIRECTION"},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CurveLine`，对应 `GeometryNodeCurvePrimitiveLine` |
| `attrs` | `mode`：`POINTS` 或 `DIRECTION` |
| `input_kwargs` | `POINTS` 使用 `Start`、`End`；`DIRECTION` 使用 `Start`、`Direction`、`Length` |

**Input Sockets**：`Start`、动态 `End`/`Direction`（Vector）；`Length`（Float distance）。

**Output Sockets**：`Curve`（开放 poly spline）。

`DIRECTION` 只使用 Direction 的朝向，不使用其向量长度，最终终点为 `Start + normalize(Direction) * Length`。需要弯曲路径时改用 Bezier 或 Quadratic Bezier。

## `Nodes.CurveBezierSegment` / `Nodes.BezierSegment`

**作用**：用两个 control points 及其 handles 生成单段 Bezier spline。

**创建方式**：

```python
curve = nw.new_node(
    Nodes.CurveBezierSegment,
    input_kwargs={
        "Resolution": 24,
        "Start": (0.0, 0.0, 0.0),
        "Start Handle": (0.0, 0.0, 0.5),
        "End Handle": (1.0, 0.0, 0.5),
        "End": (1.0, 0.0, 0.0),
    },
    attrs={"mode": "POSITION"},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | 推荐 `Nodes.CurveBezierSegment`；`Nodes.BezierSegment` 是同一 `GeometryNodeCurvePrimitiveBezierSegment` 的别名 |
| `attrs` | `mode`：`POSITION` 或 `OFFSET` |
| `input_kwargs` | `Resolution`、`Start`、`Start Handle`、`End Handle`、`End` |

**Input Sockets**：`Resolution`（Integer，求值 edge 数）；四个位置/handle Vector。

**Output Sockets**：`Curve`（含两个 control points 的 Bezier spline）。

`POSITION` 将 handle 输入解释为局部空间绝对位置；`OFFSET` 将它们分别解释为相对 Start/End 的偏移。只改变 handle 表达方式，不改变 socket 名。

## `"GeometryNodeCurveArc"`

**作用**：创建圆弧，常用于圆角桌面轮廓、门铰链路径和弧形支架。

**创建方式**：

```python
arc = nw.new_node(
    "GeometryNodeCurveArc",
    input_kwargs={"Resolution": 16, "Radius": 0.5, "Sweep Angle": 3.1416},
    attrs={"mode": "RADIUS"},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | raw `GeometryNodeCurveArc`；`Nodes` 中没有对应成员 |
| `attrs` | `mode`：`RADIUS` 或 `POINTS` |
| `input_kwargs` | 两种模式共用 `Resolution`、`Connect Center`、`Invert Arc`；`RADIUS` 使用 `Radius`、`Start Angle`、`Sweep Angle`，`POINTS` 使用 `Start`、`Middle`、`End`、`Offset Angle` |

**Input Sockets**：按 mode 使用上述动态输入；角度使用弧度。

**Output Sockets**：`Curve`；`POINTS` 模式还提供 `Center`、`Normal`、`Radius`。

`Connect Center=True` 会增加连接圆心的线段，便于后续 `FillCurve` 形成扇形；普通开放圆弧保持为 `False`。

## `"GeometryNodeCurveSpiral"`

**作用**：创建平面或空间螺旋线，适合灯丝、弹簧轮廓和盘绕装饰。

**创建方式**：

```python
spiral = nw.new_node(
    "GeometryNodeCurveSpiral",
    input_kwargs={
        "Resolution": 64,
        "Rotations": 3.0,
        "Start Radius": 0.1,
        "End Radius": 0.3,
        "Height": 0.5,
    },
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | raw `GeometryNodeCurveSpiral`；`Nodes` 中没有对应成员 |
| `input_kwargs` | `Resolution`、`Rotations`、`Start Radius`、`End Radius`、`Height`、`Reverse` |

**Input Sockets**：上述六项；`Reverse` 反转绕行方向。

**Output Sockets**：`Curve`。

`Height=0` 生成 XY 平面螺旋；Start/End Radius 相同可生成等半径螺旋。高 `Resolution` 会直接增加 control point 数。

## `"GeometryNodeCurvePrimitiveQuadrilateral"`

**作用**：创建闭合四边形 curve，是家电面板、把手截面和桌板轮廓的高频入口。

**创建方式**：

```python
outline = nw.new_node(
    "GeometryNodeCurvePrimitiveQuadrilateral",
    input_kwargs={"Width": 1.0, "Height": 0.6},
    attrs={"mode": "RECTANGLE"},
).outputs["Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | raw `GeometryNodeCurvePrimitiveQuadrilateral`；`Nodes` 中没有对应成员 |
| `attrs` | `mode`：`RECTANGLE`、`PARALLELOGRAM`、`TRAPEZOID`、`KITE`、`POINTS` |
| `input_kwargs` | `RECTANGLE` 使用 `Width`、`Height`；其他模式使用其启用的宽、高、Offset 或 `Point 1..4` |

**Input Sockets**：随 mode 切换；必须先设置 `attrs`，再按节点启用的名称传值。

**Output Sockets**：`Curve`（闭合 poly spline）。

静态单体建模最常用 `RECTANGLE`。需要实体面时接 `FillCurve`；需要圆角轮廓时先接 `FilletCurve`，需要管状矩形框时接 `CurveToMesh`。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 给 mode 不匹配的隐藏 socket 传值 | `RADIUS` 不传 Point，`POINTS` 不传 Radius；Line 同理 |
| 把 Quadratic 的 Middle 当作必经点 | Middle 是控制位置；需要必经中间位置时组合多段曲线 |
| 三点圆没有得到稳定结果 | 确认三个点不同且不共线 |
| Direction 长度没有改变直线长度 | 使用 `Length` socket；Direction 仅控制朝向 |
| OFFSET 模式的 Bezier handle 偏移异常 | Start Handle 相对 Start，End Handle 相对 End |
| Arc 角度按度数传入 | `Start Angle`、`Sweep Angle`、`Offset Angle` 使用弧度 |
| Quadrilateral 给隐藏模式输入传值 | 先设置 `mode`，只传该模式启用的 socket |
| primitive 不能直接显示为实体管 | 继续使用 `CurveCircle` profile 和 `CurveToMesh` |

## 相关文档

- `new_node`、attrs 与动态 socket：`../node_wrangler_usage.md`
- 半径、倾斜和 handle 编辑：`curve_property_topology_nodes.md`
- curve 转 mesh、重采样和圆角：`curve_conversion_shape_nodes.md`
- curve 长度和方向采样：`curve_read_sampling_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/assets/objects/elements/doors/bar_handle.py`
- `infinigen/assets/objects/appliances/dishwasher.py`
- `infinigen/assets/objects/tables/table_top.py`
- `infinigen/assets/objects/lamp/lamp.py`
- `infinigen/assets/objects/organizer/hook.py`
- `infinigen/assets/objects/creatures/insects/parts/wing/dragonfly_wing.py`
- `infinigen/assets/sim_objects/stovetop.py`
- [Blender 4.2 Curve Primitive Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/primitives/index.html)
- [Blender Quadratic Bezier](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/primitives/quadratic_bezier.html)
- [Blender Curve Circle](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/primitives/curve_circle.html)
- [Blender Curve Line](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/primitives/curve_line.html)
- [Blender Bezier Segment](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/primitives/bezier_segment.html)
- [Blender Arc](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/primitives/arc.html)
- [Blender Curve Spiral](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/primitives/curve_spiral.html)
- [Blender Quadrilateral](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/primitives/quadrilateral.html)
