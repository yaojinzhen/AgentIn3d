# Socket、Attrs 与兼容性

本文档只保留编写节点代码时需要的跨节点规则。具体节点的 socket、`attrs` 和枚举值以 `README.md` 指向的分类文档为准。

## 创建节点时的三类信息

| 信息 | `new_node` 参数 | 示例 |
| --- | --- | --- |
| 节点类型 | `node_type` | `Nodes.Math` |
| socket 输入 | `input_args` / `input_kwargs` | `{"Geometry": mesh}` |
| node property | `attrs` | `{"operation": "MULTIPLY"}` |

```python
result = nw.new_node(
    Nodes.Math,
    input_kwargs={0: a, 1: b},
    attrs={"operation": "MULTIPLY", "use_clamp": False},
)
```

`attrs` 不是 socket。它经常决定哪些 sockets 可用，因此 NodeWrangler 先设置 `attrs`，再解析 inputs。

## Socket 解析规则

### Input

`input_kwargs` 优先使用 socket 名称：

1. 查找同名且 enabled 的 input。
2. 未找到时回退到 Blender collection lookup。
3. 最终 socket disabled 时记录 warning，后续赋值或连接仍可能失败。

索引只适合存在多个同名 enabled socket，或项目已固定 Blender 版本的情况。动态节点设置 `mode`、`data_type` 等 `attrs` 后，应使用该模式下的 socket 名称。

### Output

| 输入形式 | 解析结果 |
| --- | --- |
| output socket | socket 本身 |
| node | 第一个 enabled output |
| `(node, "Name")` | 指定名称的 enabled output |
| `(node, index)` | 指定索引的 output |
| Python 常量 | 不生成 output，尝试写入 input 默认值 |

多输出节点应显式选择 `.outputs["..."]`。选择到 disabled output 会抛出 `ValueError`。

### 常量与 multi-input

- 标量、tuple 和普通 list 写入 `default_value`。
- node/socket 创建 link。
- 包含 node/socket 的 list 只可传给 multi-input socket。
- `None` 跳过该 input。

Capture Attribute 的 sockets 由 capture items 动态生成，优先使用 `nw.capture(...)` 或该节点分类文档中的当前写法，不要照搬旧版本索引。

## `attrs` 规则

```python
node = nw.new_node(
    Nodes.FloatCurve,
    attrs={"mapping.use_clip": False},
)
```

- key 支持点分隔属性路径。
- NodeWrangler 不验证 property 名称和枚举值；错误由 Blender RNA 抛出。
- `NODE_ATTRS_AVAILABLE` 是 transpiler 的导出元数据，不是允许设置的属性白名单。
- Color Ramp 等嵌套数据应使用专用 helper，或创建节点后修改 Blender 数据对象。

Agent 不需要读取完整 `NODE_ATTRS_AVAILABLE`。生成代码时直接查具体节点文档；只有维护 transpiler 时才查 `node_info.py`。

## 类型词汇

Blender 4.2 的类型词汇取决于正在设置的接口，不能把一种节点的枚举套到另一种节点。

| 接口 | Float | Int | Vector | Color | Boolean |
| --- | --- | --- | --- | --- | --- |
| socket `type`（只读） | `VALUE` | `INT` | `VECTOR` | `RGBA` | `BOOLEAN` |
| interface socket class | `NodeSocketFloat` | `NodeSocketInt` | `NodeSocketVector` | `NodeSocketColor` | `NodeSocketBool` |
| Mesh attribute `data_type` | `FLOAT` | `INT` | `FLOAT_VECTOR` | `FLOAT_COLOR` / `BYTE_COLOR` | `BOOLEAN` |

节点 property 必须按节点区分。下面的集合经过 Blender 4.2 实际赋值验证：

| 节点 / property | 可赋值集合 |
| --- | --- |
| Named Attribute `node.data_type` | `FLOAT`、`INT`、`FLOAT_VECTOR`、`FLOAT_COLOR`、`BOOLEAN`、`QUATERNION`、`FLOAT4X4` |
| Capture Attribute `capture_items[i].data_type` | `FLOAT`、`INT`、`FLOAT_VECTOR`、`FLOAT_COLOR`、`BOOLEAN`、`QUATERNION`、`FLOAT4X4` |
| Random Value `node.data_type` | `FLOAT`、`INT`、`FLOAT_VECTOR`、`BOOLEAN` |
| Mix `node.data_type`（Shader tree） | `FLOAT`、`VECTOR`、`RGBA` |
| Mix `node.data_type`（Geometry tree） | `FLOAT`、`VECTOR`、`RGBA`、`ROTATION` |

Capture Attribute 在 Blender 4.2 没有可直接设置的 `node.data_type`。其
`capture_items.new(socket_type, name)` 构造参数使用 socket 词汇，如 `VECTOR`、`RGBA`；
创建后的 item `data_type` 则为 `FLOAT_VECTOR`、`FLOAT_COLOR`。
`nw.capture(...)` / Infinigen 兼容入口的 `attrs["data_type"]` 使用字段类型词汇，
由封装创建 capture item；两者不能混用。

### 最小类型示例

此片段可直接在 Blender 4.2 Python 环境执行：

```python
import bpy

geo = bpy.data.node_groups.new("type_example_geometry", "GeometryNodeTree")
named = geo.nodes.new("GeometryNodeInputNamedAttribute")
named.data_type = "FLOAT_COLOR"
assert named.outputs["Attribute"].type == "RGBA"

capture = geo.nodes.new("GeometryNodeCaptureAttribute")
captured = capture.capture_items.new("VECTOR", "Position")
assert captured.data_type == "FLOAT_VECTOR"
captured.data_type = "FLOAT_COLOR"

random = geo.nodes.new("FunctionNodeRandomValue")
random.data_type = "FLOAT_VECTOR"

shader = bpy.data.node_groups.new("type_example_shader", "ShaderNodeTree")
mix = shader.nodes.new("ShaderNodeMix")
mix.data_type = "VECTOR"
mix.data_type = "RGBA"
```

使用边界：

- `expose_input(dtype=...)` 优先传 interface socket class。
- Named Attribute 的颜色用 `FLOAT_COLOR`；Shader Mix 的颜色用 `RGBA`、向量用 `VECTOR`。
- Geometry、Object、Collection、Material、Shader 等 interface 类型必须显式传对应 socket class。
- 不要依赖 tuple、list 或 NumPy array 自动推断 interface 类型；当前 `PYTYPE_TO_DATATYPE` 对 NumPy vector 的映射并不可靠。
- RNA 静态 `enum_items` 可能包含节点当前不接受的选项；以目标节点、tree 和实际赋值为准。

Group Output 自动创建 interface 时，`NodeSocketVectorEuler` 会映射为 `NodeSocketVector`，其他 socket class 默认原样使用。

## Compatibility mode

`new_node(..., compat_mode=True)` 默认处理以下旧接口。新代码应优先使用“推荐写法”，兼容层主要用于既有资产代码。

| 传入节点 | 兼容行为 | 新代码推荐 |
| --- | --- | --- |
| `Nodes.MixRGB` | 转为 `Nodes.Mix`，重命名 Factor/A/B sockets | 直接使用 `Nodes.Mix` |
| `Nodes.TransferAttribute` | 按 mapping 转为 Sample Index 或 Sample Nearest Surface；`NEAREST` 不支持 | 直接使用目标 Sample 节点 |
| `Nodes.SampleCurve` | 将旧 `Curve` input 改名为 `Curves` | 使用 `Curves` |
| `Nodes.MusgraveTexture` | 近似转换为 Noise Texture | 直接设计 Noise Texture 参数 |
| `Nodes.CaptureAttribute` | 创建动态 capture items 并设置类型 | 优先使用 `nw.capture`，必要时显式 `data_type` |
| `Nodes.PrincipledBSDF` | 适配新版 subsurface inputs | 使用目标 Blender 版本的当前 socket 名称 |

兼容函数可能原地修改传入的 `input_args`、`input_kwargs` 和 `attrs`。不要在多次 `new_node` 调用间复用同一份可变 dict/list。

仅当代码已经使用目标 Blender 的当前接口并经过 Blender 验证时，才考虑 `compat_mode=False`。关闭它不会修复错误 socket，也不会绕过 `strict=True` 对 `Nodes.Bump` 的限制。

## Singleton 与别名

Group Input/Output、材质/世界/合成输出、Viewer、Render Layers 和 Light Output 属于 singleton nodes；重复创建会复用当前 tree 中的第一个同类节点，并继续修改其 inputs/attrs。

以下名称指向相同 `bl_idname`，生成代码在同一文件内保持一种命名即可：

| 等价名称 |
| --- |
| `CurveSplineType` / `SplineType` |
| `CurveBezierSegment` / `BezierSegment` |
| `DeleteGeometry` / `DeleteGeom` |
| `IcoSphere` / `MeshIcoSphere` |

## 生成检查

1. 从具体节点文档确认 `attrs`、枚举值及 enabled socket 名称。
2. 不把 `attrs` 当作 inputs，也不混用 socket class 与 `data_type`。
3. 对多输出和动态 socket 显式命名。
4. Capture Attribute 常量输入显式指定 `data_type` 和 `domain`。
5. 新代码避免生成 `MixRGB`、`TransferAttribute` 和 `MusgraveTexture`。
6. 不复用可能被兼容函数修改的 dict/list。

## 相关文档

- `new_node`、连接形式与 helper：`node_wrangler_usage.md`
- Group Input/Output：`nodegroup_authoring.md`
- 具体节点路由：`README.md`
- Modifier interface input：`../function_api/blender_geometry_node_modifiers.md`
