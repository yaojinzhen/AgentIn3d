# `NodeWrangler` 使用

本文档说明生成节点代码时最常用的 `NodeWrangler` 接口。具体节点的 inputs、outputs 和 `attrs` 请通过 `README.md` 查询，不在此重复。

## 导入与初始化

```python
from infinigen.core.nodes.node_info import Nodes
from infinigen.core.nodes.node_wrangler import NodeWrangler

nw = NodeWrangler(node_tree_or_modifier)
```

`node_tree_or_modifier` 必须是 `bpy.types.NodeTree`，或已经绑定 `node_group` 的 `bpy.types.NodesModifier`。只有传入 modifier 时，`expose_input(attribute=...)` 才能配置 modifier attribute input。

## 创建节点：`NodeWrangler.new_node`

```python
new_node(
    node_type,
    input_args=None,
    attrs=None,
    input_kwargs=None,
    label=None,
    expose_input=None,
    compat_mode=True,
    strict=True,
) -> bpy.types.Node
```

| 参数 | 用法 |
| --- | --- |
| `node_type` | 优先使用 `Nodes.*`；也可传已有 nodegroup 的名称 |
| `input_args` | 按索引设置输入；仅用于 socket 顺序明确的节点 |
| `input_kwargs` | 按 socket 名称或索引设置输入；生成代码优先使用名称 |
| `attrs` | node property，如 `{"operation": "MULTIPLY"}`；先于 inputs 设置 |
| `label` | 同时设置 `node.label` 和 `node.name` |
| `expose_input` | 仅供 `Nodes.GroupInput` 批量声明接口，详见 `nodegroup_authoring.md` |
| `compat_mode` | 默认启用旧接口转换；通常不要关闭 |
| `strict` | 默认禁止 `Nodes.Bump`；确有需要时才设为 `False` |

返回值是 node，不是 output socket。多输出节点必须显式选择输出：

```python
cube = nw.new_node(Nodes.MeshCube, input_kwargs={"Size": (1.0, 0.8, 0.6)})
mesh = cube.outputs["Mesh"]

moved = nw.new_node(
    Nodes.Transform,
    input_kwargs={"Geometry": mesh, "Translation": (0.0, 0.0, 0.3)},
)
```

动态 socket 由 `attrs` 决定，应在同一次调用中同时给出。例如先设置 `data_type`、`mode` 或 `operation`，再使用该模式下启用的 socket 名称。

## 输入与输出形式

| 传入值 | 行为 |
| --- | --- |
| 标量、tuple 或普通 list | 写入 input socket 的 `default_value` |
| output socket | 创建 link |
| node | 连接其第一个 enabled output |
| `(node, "Output")` / `(node, index)` | 连接指定 output |
| node/socket list | 逐项连接 multi-input socket |
| `None` | 保留该 input 的 Blender 默认值 |

优先使用命名 socket。仅当同名 socket 无法区分且目标 Blender 版本固定时使用索引。不要依赖多输出节点的“第一个输出”。

```python
joined = nw.new_node(
    Nodes.JoinGeometry,
    input_kwargs={"Geometry": [body.outputs["Mesh"], handle]},
)
```

### `connect_input`

```python
connect_input(input_socket, input_item) -> None
```

连接规则与 `new_node` 相同。常规生成代码优先在 `new_node(..., input_kwargs=...)` 中完成连接；该方法主要用于修改已存在的 node tree。

## 常用 helper

Helper 多数返回 node；`separate` 返回 outputs collection，`capture` 返回两个 sockets。

| 类别 | Helper | 作用 |
| --- | --- | --- |
| 标量数学 | `scalar_add2`、`scalar_sub2`、`scalar_multiply2`、`scalar_divide2`、`scalar_max2`、`power` | 创建对应 `Math` 运算 |
| 多项标量 | `scalar_add`、`scalar_max`、`scalar_multiply` | 组合一个或多个标量 |
| 向量数学 | `add2`、`sub2`、`multiply2`、`divide2`、`scale`、`dot` | 创建对应 `VectorMath` 运算 |
| 多项向量 | `add`、`multiply` | 组合一个或多个向量 |
| 通用运算 | `math`、`vector_math`、`boolean_math`、`compare`、`compare_direction` | 显式指定 operation |
| 随机 | `bernoulli`、`uniform` | 创建 `RandomValue`；显式传 `seed` 以保证可复现 |
| 向量 | `combine`、`separate` | 组合或拆分 XYZ |
| 分支 | `switch`、`vector_switch`、`build_case`、`build_index_case` | 创建字段条件分支 |
| 几何 | `position2point`、`capture`、`curve2mesh` | 常见几何组合 |
| 低频/旧接口 | `geometry2point`、`build_float_curve`、`musgrave` | 先查源码或具体节点文档；`geometry2point` 使用固定合并距离，`musgrave` 会走兼容转换 |

二元别名 `sub`、`divide`、`scalar_sub`、`scalar_divide` 分别对应同名 `*2` helper。

```python
half_height = nw.scalar_multiply(height, 0.5)
offset = nw.combine(0.0, 0.0, half_height)
mask = nw.boolean_math("AND", x_mask, y_mask)
```

低频查找接口 `find`、`find_recursive`、`find_from` 和 `find_to` 用于检查已有 node tree。不要在生成代码中使用 `find_from_recursive` 或 `find_to_recursive`，其当前行为与名称不一致。

`is_socket`、`is_vector_socket` 和 `get_position_translation_seed` 是现有 helper 的内部启发式支持接口，Agent 不应直接依赖。

## 其他行为

```python
new_value(v, label=None) -> bpy.types.Node
force_input_consistency() -> None
```

- `new_value` 创建 `Nodes.Value`，需要 socket 时取 `.outputs[0]`。
- `force_input_consistency` 会为之后创建且未提供 `Vector` 的部分纹理节点自动接入位置。新代码仍推荐显式提供 `Vector`。
- Group Input、Group Output、材质/世界/合成输出等 singleton node 会复用当前 tree 中已有的同类节点。
- `node_type` 若是 `bpy.data.node_groups` 中的名称，会实例化该 nodegroup。
- Group Output 收到新的命名 output 时，可根据所连 socket 自动创建 interface output。

## 生成检查

1. 使用 `Nodes.*`，并从具体节点文档确认 `attrs`、socket 名称及枚举值。
2. 对多输出节点显式使用 `.outputs["..."]`。
3. 对动态节点先设置 `attrs`，再连接当前模式下 enabled 的 socket。
4. multi-input 才传 node/socket list；普通向量 list 作为默认值处理。
5. 保持 `compat_mode=True`，不要用关闭兼容模式掩盖错误接口。
6. 需要可复现随机结果时显式传入 seed。

## 相关文档

- Nodegroup 与 interface：`nodegroup_authoring.md`
- Socket、attrs 与兼容规则：`socket_attrs_and_compatibility.md`
- 具体节点路由：`README.md`
- Geometry Nodes modifier：`../function_api/blender_geometry_node_modifiers.md`
