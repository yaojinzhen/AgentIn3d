# 向量、旋转与映射节点

本文档覆盖向量拆装、曲线映射、坐标变换和旋转构造节点。参数表只列当前节点实际使用的 `new_node` 参数；通用语义见 `../node_wrangler_usage.md`。

## 快速选择

| 节点 | 作用 | Node tree |
| --- | --- | --- |
| `Nodes.SeparateXYZ` | Vector 拆为 X/Y/Z | Shader、Geometry |
| `Nodes.CombineXYZ` | X/Y/Z 组合为 Vector | Shader、Geometry |
| `Nodes.VectorCurve` | 分量级曲线映射 Vector | Shader、Geometry |
| `Nodes.VectorRotate` | 围绕中心旋转 Vector | Shader、Geometry |
| `Nodes.AlignEulerToVector` | 让指定局部轴对齐方向 | Geometry |
| `Nodes.Mapping` | 平移、旋转和缩放纹理坐标 | Shader |
| `Nodes.RotateEuler` | 在 Object/Local 空间叠加旋转 | Geometry |

接口以 Blender 4.2 为准。角度和 Euler 常量使用弧度。`AlignEulerToVector`、`RotateEuler` 已被 Blender 归为 deprecated，但仍存在于 Infinigen 的 `Nodes` 枚举并被现有资产大量使用。

## `Nodes.SeparateXYZ`

**作用**：把一个 Vector 拆成三个 Float 分量。

**创建方式**：

```python
xyz = nw.new_node(Nodes.SeparateXYZ, input_kwargs={"Vector": position})
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.SeparateXYZ`，对应 `ShaderNodeSeparateXYZ` |
| `input_kwargs` | `Vector` |

**Input Sockets**：`Vector`（Vector）。

**Output Sockets**：`X`、`Y`、`Z`（Float）。需要指定分量时使用 `xyz.outputs["Z"]`，不要依赖输出索引。

## `Nodes.CombineXYZ`

**作用**：把三个 Float 组合为 Vector。

**创建方式**：

```python
offset = nw.new_node(
    Nodes.CombineXYZ,
    input_kwargs={"X": dx, "Y": dy, "Z": 0.0},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.CombineXYZ`，对应 `ShaderNodeCombineXYZ` |
| `input_kwargs` | `X`、`Y`、`Z` |

**Input Sockets**：`X`、`Y`、`Z`（Float）。

**Output Sockets**：`Vector`。

## `Nodes.VectorCurve`

**作用**：分别用曲线重映射 Vector 的 X、Y、Z 分量，`Fac` 控制原值与映射值的混合。

**创建方式**：

```python
curved = nw.new_node(
    Nodes.VectorCurve,
    input_kwargs={"Fac": 1.0, "Vector": position},
)
node_utils.assign_curve(
    curved.mapping.curves[2],
    [(-1.0, -0.2), (0.0, 0.0), (1.0, 0.8)],
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.VectorCurve`，对应 `ShaderNodeVectorCurve` |
| `input_kwargs` | `Fac`、`Vector` |

**Input Sockets**：`Fac`（Float，通常为 0 到 1）、`Vector`。

**Output Sockets**：`Vector`。

曲线不是 socket 或普通 `attrs`；创建节点后修改 `mapping.curves[0:3]`，依次对应 X/Y/Z。优先用 `node_utils.assign_curve(curve, points, handles=None)`，点按 `(x, y)` 排列。

## `Nodes.VectorRotate`

**作用**：围绕 `Center` 旋转位置、方向或纹理坐标。

**创建方式**：

```python
rotated = nw.new_node(
    Nodes.VectorRotate,
    input_kwargs={
        "Vector": position,
        "Center": (0.0, 0.0, 0.0),
        "Axis": (0.0, 0.0, 1.0),
        "Angle": angle,
    },
    attrs={"rotation_type": "AXIS_ANGLE"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.VectorRotate`，对应 `ShaderNodeVectorRotate` |
| `attrs` | `rotation_type`；可选 `invert: bool` |
| `input_kwargs` | `Vector`、`Center`，以及当前旋转模式需要的 sockets |

**Input Sockets**：

| `rotation_type` | 模式输入 |
| --- | --- |
| `AXIS_ANGLE` | `Axis`、`Angle` |
| `X_AXIS`、`Y_AXIS`、`Z_AXIS` | `Angle` |
| `EULER_XYZ` | `Rotation` |

所有模式都使用 `Vector` 和 `Center`。`invert=True` 应用逆旋转。

**Output Sockets**：`Vector`。

旋转位置时传入真实中心；旋转方向时通常保持 `Center=(0, 0, 0)`。不要把该节点与输出 Rotation 数据的 `RotateEuler` 混用。

## `Nodes.AlignEulerToVector`

**作用**：旋转输入 Rotation，使指定局部轴朝向 `Vector`。

**创建方式**：

```python
rotation = nw.new_node(
    Nodes.AlignEulerToVector,
    input_kwargs={"Factor": 1.0, "Vector": normal},
    attrs={"axis": "Z", "pivot_axis": "AUTO"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.AlignEulerToVector`，对应 `FunctionNodeAlignEulerToVector` |
| `attrs` | `axis`：`X`/`Y`/`Z`；`pivot_axis`：`AUTO`/`X`/`Y`/`Z` |
| `input_kwargs` | `Rotation`、`Factor`、`Vector` |

**Input Sockets**：`Rotation`、`Factor`（0 不对齐，1 完全对齐）、`Vector`（目标方向）。

**Output Sockets**：`Rotation`。

`Vector` 应是方向而不是 Rotation。通常使用 `pivot_axis="AUTO"`；指定 pivot 时不要与待对齐的 `axis` 相同。该节点用于给 Instance on Points 构造 Rotation，不用于旋转几何位置。

## `Nodes.Mapping`

**作用**：在 Shader tree 中对纹理坐标执行平移、Euler 旋转和缩放。

**创建方式**：

```python
mapped = nw.new_node(
    Nodes.Mapping,
    input_kwargs={
        "Vector": texcoord,
        "Location": (0.1, 0.0, 0.0),
        "Rotation": (0.0, 0.0, angle),
        "Scale": (2.0, 1.0, 1.0),
    },
    attrs={"vector_type": "POINT"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Mapping`，对应 `ShaderNodeMapping` |
| `attrs` | `vector_type`：`POINT`、`TEXTURE`、`VECTOR`、`NORMAL` |
| `input_kwargs` | `Vector`、`Rotation`、`Scale`；`POINT`/`TEXTURE` 还可用 `Location` |

**Input Sockets**：由 `vector_type` 决定；`Vector`、`Rotation`、`Scale` 始终可用，`Location` 仅用于 `POINT` 和 `TEXTURE`。

**Output Sockets**：`Vector`。

`POINT` 是正向变换，`TEXTURE` 是让纹理视觉上按参数移动/缩放的逆变换，`VECTOR` 忽略平移，`NORMAL` 使用适合非均匀缩放的法线变换并归一化。Blender 4.2 的该节点不能在 Geometry tree 中创建；Geometry 坐标变换使用 Math/VectorMath 或几何变换节点。

## `Nodes.RotateEuler`

**作用**：在已有 Rotation 上叠加 Euler 或 Axis Angle 旋转。

**创建方式**：

```python
rotation = nw.new_node(
    Nodes.RotateEuler,
    input_kwargs={
        "Rotation": base_rotation,
        "Axis": (0.0, 0.0, 1.0),
        "Angle": angle,
    },
    attrs={"rotation_type": "AXIS_ANGLE", "space": "LOCAL"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.RotateEuler`，对应 `FunctionNodeRotateEuler` |
| `attrs` | `rotation_type`：`EULER`/`AXIS_ANGLE`；`space`：`OBJECT`/`LOCAL` |
| `input_kwargs` | `Rotation`，以及 `Rotate By` 或 `Axis` + `Angle` |

**Input Sockets**：

| `rotation_type` | Inputs |
| --- | --- |
| `EULER` | `Rotation`、`Rotate By` |
| `AXIS_ANGLE` | `Rotation`、`Axis`、`Angle` |

**Output Sockets**：`Rotation`。

`LOCAL` 让附加旋转随当前局部轴变化，`OBJECT` 使用对象空间。Blender 4.2 的实际属性名是 `rotation_type`；不要照搬 `node_info.py` 中过时的 `type` 记录。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把 Rotation socket 当作普通方向 Vector | 用 `AlignEulerToVector`/`RotateEuler` 构造 Rotation，用 `VectorRotate` 旋转坐标 |
| 角度按度数传入 | 先用 `math.radians(...)`，或直接传弧度 |
| 在 Geometry tree 创建 `Nodes.Mapping` | 使用 `VectorMath` 或 Geometry 的 Transform 类节点 |
| 用 `attrs` 传 Vector Curve 控制点 | 创建后修改 `mapping.curves` |
| 给 `RotateEuler` 设置 `attrs={"type": ...}` | 使用 `attrs={"rotation_type": ...}` |

## 相关文档

- `new_node` 参数：`../node_wrangler_usage.md`
- 数学与向量运算：`math_logic_nodes.md`
- 纹理采样：`texture_nodes.md`
- 实例旋转：`../geometry_nodes/instance_nodes.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/core/nodes/node_utils.py`
- `infinigen/core/placement/instance_scatter.py`
- [Blender 4.2 Mapping Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/vector/mapping.html)
- [Blender 4.2 Vector Rotate Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/vector/vector_rotate.html)
- [Blender 4.2 Vector Curves Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/vector/curves.html)
- [Blender 4.2 Align Euler to Vector](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/utilities/deprecated/align_euler_to_vector.html)
- [Blender 4.2 Rotate Euler](https://docs.blender.org/manual/en/4.2/modeling/geometry_nodes/utilities/deprecated/rotate_euler.html)
