# Nodegroup 编写

本文档说明如何创建可复用 Geometry/Shader nodegroup，以及如何声明 Group Input/Output。普通节点的创建规则见 `node_wrangler_usage.md`。

## 选择入口

| 目标 | 使用 |
| --- | --- |
| 创建可被多处实例化的 Geometry/Shader group | `@node_utils.to_nodegroup(...)` |
| 为单个 object 创建并挂载 Geometry Nodes modifier | `surface.add_geomod(...)` |
| 创建带 Geometry 输入/输出的空 pass-through group | `geometry_node_group_empty_new()` |
| 继续编辑已有 node tree | `NodeWrangler(node_tree)` |

## `to_nodegroup`

```python
from infinigen.core.nodes import node_utils

node_utils.to_nodegroup(
    name=None,
    singleton=False,
    type="GeometryNodeTree",
)
```

| 参数 | 含义 |
| --- | --- |
| `name` | Blender nodegroup 名称；省略时使用被装饰函数名 |
| `singleton` | 按名称复用已有 group；仅用于结构不依赖调用参数的 group |
| `type` | `"GeometryNodeTree"`、`"ShaderNodeTree"` 等 tree 类型 |

装饰后的函数返回 `bpy.types.NodeTree`。`singleton=True` 时名称追加 `" (no gc)"`；若同名 group 已存在，函数参数不会再次参与构建。

```python
@node_utils.to_nodegroup("make_handle", singleton=False, type="GeometryNodeTree")
def make_handle(nw: NodeWrangler, radius=0.03):
    curve = nw.new_node(Nodes.CurveCircle, input_kwargs={"Radius": radius})
    nw.new_node(
        Nodes.GroupOutput,
        input_kwargs={"Geometry": curve.outputs["Curve"]},
        attrs={"is_active_output": True},
    )

handle_group = make_handle(radius=0.04)
```

## `Nodes.GroupInput`

**作用**：读取 nodegroup 对外声明的 inputs，并将它们作为当前 node tree 的 outputs 使用。

**创建方式**：

```python
group_in = nw.new_node(
    Nodes.GroupInput,
    expose_input=[
        ("NodeSocketFloat", "Radius", 0.25),
        ("NodeSocketVector", "Offset", (0.0, 0.0, 0.0)),
    ],
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.GroupInput`，对应 `NodeGroupInput` |
| `expose_input` | `(socket_type, name, default_value)` 列表，批量声明 interface inputs |

**Input Sockets**：无。

**Output Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| 动态命名 | Interface socket 类型 | 每个 nodegroup input 对应一个同名 output |

仅暴露单个 input 时，优先直接使用 `nw.expose_input(...)`。

### `expose_input`

```python
nw.expose_input(
    name,
    val=None,
    attribute=None,
    dtype=None,
    use_namednode=False,
) -> bpy.types.NodeSocket | bpy.types.Node
```

| 参数 | 用法 |
| --- | --- |
| `name` | 唯一的 interface input 名称 |
| `val` | interface 默认值，也可辅助推断 socket 类型 |
| `attribute` | modifier 使用的 mesh attribute 名称 |
| `dtype` | Blender socket class 或支持的 data type；不确定时显式提供 |
| `use_namednode` | 不创建 interface，改为返回 `NamedAttribute` node；仅用于 Geometry Nodes |

默认返回 Group Input 的 output socket；`use_namednode=True` 时返回 `NamedAttribute` node。

推荐显式指定 `dtype`。可靠的常用映射如下：

| 值 | `dtype` |
| --- | --- |
| float | `"NodeSocketFloat"` |
| int | `"NodeSocketInt"` |
| bool | `"NodeSocketBool"` |
| vector | `"NodeSocketVector"` |
| color | `"NodeSocketColor"` |
| geometry | `"NodeSocketGeometry"` |

```python
size = nw.expose_input("Size", val=1.0, dtype="NodeSocketFloat")
axis = nw.expose_input("Axis", val=(0.0, 0.0, 1.0), dtype="NodeSocketVector")
```

同名 input 已存在时会直接复用。不要依赖 tuple、list 或 NumPy array 自动推断 vector/color 类型。

### Modifier attribute input

`attribute` 只有在 `NodeWrangler` 由 modifier 初始化时才能完整配置：

```python
nw = NodeWrangler(modifier)
mask = nw.expose_input(
    "Selection",
    val=False,
    attribute="selection_mask",
    dtype="NodeSocketBool",
)
```

若只传 node tree，`attribute` 无法写入 modifier；除非同时提供 `val` 作为构建 fallback，否则会报错。`use_namednode=True` 需要显式 `dtype`，并直接读取同名 attribute，不创建 interface socket。

## `Nodes.GroupOutput`

**作用**：声明并写入 nodegroup 对外暴露的 outputs。

**创建方式**：

```python
group_out = nw.new_node(
    Nodes.GroupOutput,
    input_kwargs={
        "Geometry": geometry_socket,
        "Mask": mask_socket,
    },
    attrs={"is_active_output": True},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.GroupOutput`，对应 `NodeGroupOutput` |
| `input_kwargs` | `{output_name: node_or_socket}`；按名称声明并连接 interface outputs |
| `attrs` | `is_active_output: bool`，标记活动 Group Output |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| 动态命名 | Interface socket 类型 | 每个 nodegroup output 对应一个同名 input |

**Output Sockets**：无。

不存在的 interface output 会根据所连 output socket 自动创建。必须遵守：

- 使用命名 `input_kwargs`，不能用位置参数声明新 output。
- 值必须是 node 或 output socket，不能是 Python 常量。
- output 名称之间保持唯一；input 与 output 可以同名，例如 Geometry pass-through。
- Euler vector output 会映射为普通 `NodeSocketVector`。

## 实例化已有 group

`nw.new_node` 可直接接收 nodegroup 名称：

```python
group_node = nw.new_node(
    handle_group.name,
    input_kwargs={"Radius": 0.04},
)
geometry = group_node.outputs["Geometry"]
```

父 node tree 与子 group 类型必须兼容。使用实际返回的 `group.name` 可避免 singleton 后缀或 Blender 重命名导致查找失败。

## 受控实例分布骨架

重复结构应将 points、source instance 和分布参数分开。下面使用仓库当前的 `NodeWrangler` 接口，
替代独立示例中版本敏感的原始 `bpy` node-tree 拼装：

```python
from infinigen.core.nodes import node_utils
from infinigen.core.nodes.node_wrangler import NodeWrangler, Nodes


@node_utils.to_nodegroup(
    "bounded_instance_distribution", singleton=False, type="GeometryNodeTree"
)
def bounded_instance_distribution(nw: NodeWrangler):
    group_input = nw.new_node(
        Nodes.GroupInput,
        expose_input=[
            ("NodeSocketGeometry", "Points", None),
            ("NodeSocketGeometry", "Instance", None),
            ("NodeSocketFloat", "Scale", 1.0),
        ],
    )
    instances = nw.new_node(
        Nodes.InstanceOnPoints,
        input_kwargs={
            "Points": group_input.outputs["Points"],
            "Instance": group_input.outputs["Instance"],
            "Scale": group_input.outputs["Scale"],
        },
    )
    nw.new_node(
        Nodes.GroupOutput,
        input_kwargs={"Geometry": instances},
        attrs={"is_active_output": True},
    )
```

points 的数量、间距、遮罩、方向和种子由上游节点负责，并必须设置有界参数。只有导出或后续修改器
需要时才 realize instances；验证 evaluated geometry，而不是只检查节点组是否存在。

## 辅助接口

| 接口 | 返回/作用 |
| --- | --- |
| `ng_inputs(node_group)` | `{name: interface_socket}` 输入字典 |
| `ng_outputs(node_group)` | `{name: interface_socket}` 输出字典 |
| `geometry_node_group_empty_new()` | 创建名为 `Geometry Nodes` 的 Geometry pass-through group |

`geometry_node_group_empty_new()` 主要服务 modifier 初始化。可复用组件优先使用 `to_nodegroup`。

## Shader group

Shader group 使用相同模式，只需指定 tree 类型，并输出 shader/color/value socket：

```python
@node_utils.to_nodegroup("paint_shader", type="ShaderNodeTree")
def paint_shader(nw):
    bsdf = nw.new_node(Nodes.PrincipledBSDF, input_kwargs={"Roughness": 0.35})
    nw.new_node(Nodes.GroupOutput, input_kwargs={"Shader": bsdf})
```

不要在 Shader group 中使用 Geometry Nodes field 或 geometry interface。

## 生成检查

1. 可复用组件使用稳定且表达职责的 group 名称。
2. 结构依赖函数参数时不要设置 `singleton=True`。
3. vector、color、geometry interface 显式提供 `dtype`。
4. Group Output 只连接 node/socket，并使用命名输出。
5. modifier attribute 绑定使用 modifier-backed `NodeWrangler`。
6. 实例化前确认父子 node tree 类型兼容。

## 相关文档

- 普通节点与连接：`node_wrangler_usage.md`
- Socket 类型和兼容规则：`socket_attrs_and_compatibility.md`
- 创建并挂载 geomod：`../function_api/surface_geomod_ops.md`
- 挂载已有 nodegroup：`../function_api/blender_geometry_node_modifiers.md`
