# 曲线读取与采样节点

本文档覆盖 curve 的位置/方向采样、长度与参数读取、端点选择、分辨率，以及 point/spline 索引互查。参数表只列当前节点实际需要的 `new_node` 参数。

## 快速选择

| 节点 | 作用 |
| --- | --- |
| `Nodes.SampleCurve` | 按 factor 或长度采样曲线位置、方向和字段 |
| `Nodes.CurveLength` | 计算显式输入 Curve 中全部 spline 的总长度 |
| `Nodes.CurveTangent` | 读取当前 curve point 的单位切线 |
| `Nodes.SplineParameter` | 读取控制点沿所属 spline 的 factor、长度和局部索引 |
| `Nodes.SplineLength` | 读取所属 spline 的总长度和控制点数 |
| `Nodes.CurveofPoint` | 从全局 point index 查询 spline 及 spline 内索引 |
| `Nodes.EndpointSelection` | 选择每条 spline 开头和结尾的控制点 |
| `Nodes.PointsofCurve` | 从 spline 查询排序后的 control point index |
| `Nodes.SplineResolution` | 读取每条 spline 的求值分辨率 |

全部节点仅适用于 Geometry node tree，接口以 Blender 4.2 为准。

## 共性规则

- `SampleCurve`、`CurveLength` 接收显式 curve geometry；其他节点是 field，由下游求值上下文决定读取哪条 curve。
- point 指 curve control point；Bezier/NURBS 的 control point 不等于 viewport 中全部 evaluated point。
- `Factor` 通常按弧长归一化，不等同于 control point index 的线性比例。
- point、curve index 会随拓扑修改变化，不应作为持久资产 ID。

## `Nodes.SampleCurve`

**作用**：按归一化 factor 或实际长度，在输入 curves 上采样位置、切线、法线和自定义字段。

**创建方式**：

```python
sample = nw.new_node(
    Nodes.SampleCurve,
    input_kwargs={
        "Curves": curves,
        "Value": radius,
        "Factor": factor,
        "Curve Index": curve_index,
    },
    attrs={
        "mode": "FACTOR",
        "data_type": "FLOAT",
        "use_all_curves": False,
    },
)
position = sample.outputs["Position"]
sampled_radius = sample.outputs["Value"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SampleCurve`，对应 `GeometryNodeSampleCurve` |
| `attrs` | `mode`：`FACTOR`/`LENGTH`；`data_type` 控制动态 `Value`；`use_all_curves` 控制单 spline 或全部 spline 累计采样 |
| `input_kwargs` | `Curves`、`Value`、`Factor` 或 `Length`；`use_all_curves=False` 时还可用 `Curve Index` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Curves` | Geometry | 包含 curve component 的显式输入 |
| `Value` | dynamic field | 在输入 curves 上求值并于采样点插值 |
| `Factor` / `Length` | Float field | 由 `mode` 决定；分别表示归一化弧长或局部长度 |
| `Curve Index` | Integer field | `use_all_curves=False` 时选择目标 spline |

**Output Sockets**：`Value`（动态类型）、`Position`、`Tangent`、`Normal`（Vector field，后两者为单位向量）。

常用 `data_type` 为 `FLOAT`、`INT`、`FLOAT_VECTOR`、`FLOAT_COLOR`、`BOOLEAN`。`use_all_curves=False` 在指定 spline 内采样；`True` 隐藏 `Curve Index`，按所有 spline 的累计长度采样。旧源码中的输入名 `"Curve"` 会被 Infinigen 兼容层映射为 `"Curves"`，新代码使用当前名称。

## `Nodes.CurveLength`

**作用**：计算显式输入 Curve 中所有 spline 的长度总和。

**创建方式**：

```python
total_length = nw.new_node(
    Nodes.CurveLength,
    input_kwargs={"Curve": curves},
).outputs["Length"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CurveLength`，对应 `GeometryNodeCurveLength` |
| `input_kwargs` | `Curve` |

**Input Sockets**：`Curve`（Geometry）。

**Output Sockets**：`Length`（Float）。

它返回一个整体值；需要每条 spline 各自长度时使用 `SplineLength`。长度基于 evaluated curve，受 spline 分辨率和上游变换影响。

## `Nodes.CurveTangent`

**作用**：读取当前 control point 处沿 spline 前进方向的单位切线。

**创建方式**：

```python
tangent = nw.new_node(Nodes.CurveTangent).outputs["Tangent"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CurveTangent`，对应 `GeometryNodeInputTangent` |

**Input Sockets**：无。

**Output Sockets**：`Tangent`（Vector field）。

常用于实例朝向、生成局部坐标轴或沿路径偏移。需要任意 factor 处的 evaluated tangent 时使用 `SampleCurve.outputs["Tangent"]`。

## `Nodes.SplineParameter`

**作用**：读取 control point 沿所属 spline 的弧长参数和局部索引。

**创建方式**：

```python
parameter = nw.new_node(Nodes.SplineParameter)
factor = parameter.outputs["Factor"]
distance = parameter.outputs["Length"]
index_in_spline = parameter.outputs["Index"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SplineParameter`，对应 `GeometryNodeSplineParameter` |

**Input Sockets**：无。

**Output Sockets**：`Factor`（Float，通常 `0..1`）、`Length`（Float）、`Index`（Integer）。

在 point domain，Factor/Length 表示从 spline 起点到当前 control point 的弧长比例/距离，Index 从每条 spline 的 `0` 重新开始。Bezier/NURBS 上这些值位于 control point；需要平滑的 evaluated 采样位置时改用 `SampleCurve`。循环 spline 的最后控制点参数不包含闭合回起点的最后一段。

## `Nodes.SplineLength`

**作用**：读取当前 spline 的完整长度和 control point 数量。

**创建方式**：

```python
spline_info = nw.new_node(Nodes.SplineLength)
length = spline_info.outputs["Length"]
point_count = spline_info.outputs["Point Count"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SplineLength`，对应 `GeometryNodeSplineLength` |

**Input Sockets**：无。

**Output Sockets**：`Length`（Float field）、`Point Count`（Integer field）。

在 spline domain 每条 spline 得到一个值；在 point domain，同一 spline 的所有点读取相同值。它与 `CurveLength` 的区别是不会把多条 spline 汇总。

## `Nodes.CurveofPoint`

**作用**：把 curve component 的全局 control point index 转换为 spline index 和 spline 内局部 index。

**创建方式**：

```python
curve_of_point = nw.new_node(
    Nodes.CurveofPoint,
    input_kwargs={"Point Index": point_index},
)
curve_index = curve_of_point.outputs["Curve Index"]
local_index = curve_of_point.outputs["Index in Curve"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CurveofPoint`，对应 `GeometryNodeCurveOfPoint` |
| `input_kwargs` | `Point Index` |

**Input Sockets**：`Point Index`（Integer field，全局 point index）。

**Output Sockets**：`Curve Index`、`Index in Curve`（Integer field）。

`Index in Curve` 从每条 spline 的 `0` 开始。需要反向从 spline 找 point index 时使用 `PointsofCurve`。

## `Nodes.EndpointSelection`

**作用**：选择每条 spline 起点和终点附近指定数量的 control points。

**创建方式**：

```python
endpoints = nw.new_node(
    Nodes.EndpointSelection,
    input_kwargs={"Start Size": 1, "End Size": 1},
).outputs["Selection"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.EndpointSelection`，对应 `GeometryNodeCurveEndpointSelection` |
| `input_kwargs` | `Start Size`、`End Size` |

**Input Sockets**：`Start Size`、`End Size`（Integer field，非负）。

**Output Sockets**：`Selection`（Boolean field，point domain）。

选择对每条 spline 独立执行；两端范围重叠时对应点仍只被选中一次。循环 spline 也按内部 control point 顺序定义 start/end。转换为 mesh 前若要保留该 mask，应先 Capture/Store attribute。

## `Nodes.PointsofCurve`

**作用**：从指定 spline 中按权重排序选择一个 control point，并返回其全局 point index。

**创建方式**：

```python
point_lookup = nw.new_node(
    Nodes.PointsofCurve,
    input_kwargs={
        "Curve Index": curve_index,
        "Weights": weights,
        "Sort Index": rank,
    },
)
point_index = point_lookup.outputs["Point Index"]
point_count = point_lookup.outputs["Total"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.PointsofCurve`，对应 `GeometryNodePointsOfCurve` |
| `input_kwargs` | `Curve Index`、`Weights`、`Sort Index` |

**Input Sockets**：`Curve Index`（Integer）、`Weights`（Float field）、`Sort Index`（Integer field）。

**Output Sockets**：`Point Index`（全局 Integer index）、`Total`（该 spline 的 control point 数）。

control points 按 `Weights` 从小到大排序，默认等权时按 point index；`Sort Index` 选择排序后的名次，超过数量时循环。按原始顺序取第 N 个点时保持默认 Weights；按高度、半径等条件排名时传入对应 field。

## `Nodes.SplineResolution`

**作用**：读取每条 spline 用于生成 evaluated points 的分辨率。

**创建方式**：

```python
resolution = nw.new_node(Nodes.SplineResolution).outputs["Resolution"]
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SplineResolution`，对应 `GeometryNodeInputSplineResolution` |

**Input Sockets**：无。

**Output Sockets**：`Resolution`（Integer field，spline domain）。

分辨率影响 Bezier、NURBS、Catmull Rom 的求值密度、采样精度和 Curve to Mesh 成本，不等于 control point 数量。修改它使用 `SetSplineResolution`。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 多 spline 输入时 Sample Curve 采到了错误 spline | 明确 `Curve Index`，或有意设置 `use_all_curves=True` |
| Sample Curve 的 Value socket 类型不匹配 | 先设置与字段一致的 `data_type` |
| 把 Curve Length 当成每条 spline 的长度 | 改用 `SplineLength` |
| 把 Spline Parameter 的 Factor 当作均匀 point index | Factor 按弧长；按索引使用 `Index` |
| Endpoint Selection 转 mesh 后丢失 | 转换前 Capture/Store 该 selection |
| 把 Spline Resolution 当 control point count | 控制点数读取 `SplineLength.outputs["Point Count"]` |

## 相关文档

- `new_node`、动态 socket 与兼容层：`../node_wrangler_usage.md`
- Position、Normal 和 Radius：`geometry_input_info_nodes.md`
- field 捕获与 domain：`attribute_field_nodes.md`
- curve 转换、重采样和形状处理：`curve_conversion_shape_nodes.md`
- curve 属性写入和 Set Spline Resolution：`curve_property_topology_nodes.md`
- curve primitive：`curve_primitive_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/compatibility.py`
- `infinigen/assets/utils/nodegroups/hair.py`
- `infinigen/assets/objects/grassland/flower.py`
- `infinigen/assets/objects/lamp/ceiling_classic_lamp.py`
- [Blender 4.2 Curve Read Nodes](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/read/index.html)
- [Blender 4.2 Sample Curve](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/sample/sample_curve.html)
- [Blender 4.2 Spline Parameter](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/read/spline_parameter.html)
- [Blender 4.2 Curve of Point](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/topology/curve_of_point.html)
- [Blender 4.2 Points of Curve](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/curve/topology/points_of_curve.html)
