# Attribute 与 Mesh 数据读写

本文档记录生成单体静态资产时直接读写 mesh 数组、named attribute、坐标、法线和自定义三角网格的 API。

源码依据：

- `infinigen/core/surface.py`：Blender named attribute 读写。
- `infinigen/core/util/blender.py`：mesh 构造、坐标转换、bounds 和法线工具。
- `infinigen/assets/utils/decorate.py`：资产代码中广泛复用的 NumPy mesh 读写 helper。

`decorate.py` 位于 `infinigen/assets`，但本页列出的函数被多类资产复用，接口通用，因此作为 Function API 提供。其余带具体造型语义的 decorate helper 不在本页覆盖。

## 导入与选择

```python
import bpy
import numpy as np

from infinigen.assets.utils.decorate import read_co, read_normal, write_co
from infinigen.core import surface
from infinigen.core.util import blender as butil
```

| 目标 | 推荐接口 |
| --- | --- |
| NumPy 读取或修改顶点坐标 | `read_co` / `write_co` |
| 读取 edge、face center、face normal 或 face area | `decorate.py` 中对应 `read_*` helper |
| 直接创建或读取 named attribute | `surface.read_attr_data` / `write_attr_data` / `new_attr_data` |
| 用 geometry nodes 计算 attribute | `surface.write_attribute` 或 `decorate.write_attribute` |
| 从 vertices/faces 创建 mesh | `butil.object_from_VF` |
| local 坐标转 world 坐标 | `butil.apply_matrix_world` |

## 坐标空间约定

| 接口/属性 | 返回空间 |
| --- | --- |
| `read_co`、`read_center`、`read_normal` | object local space |
| `read_base_co` | evaluated mesh 的 object local space |
| `obj.location`、`obj.matrix_world` | object transform / local-to-world transform |
| `apply_matrix_world(obj, verts)` | world space |
| `global_polygon_normal`、`global_vertex_coordinates` | world space |
| `bounds(obj)` | object local-space bounding-box 范围 |

不要把 `read_co(obj)` 的结果直接当成 world coordinates。对象存在 rotation、scale、parent transform 时，用 `apply_matrix_world` 转换。

## 顶点和拓扑数组

以下函数来自 `infinigen/assets/utils/decorate.py`。

| 函数签名 | 参数 | 返回/行为 |
| --- | --- | --- |
| `read_co(obj)` | mesh object | 返回形状 `(V, 3)` 的 local vertex coordinates |
| `write_co(obj, arr)` | `arr` 应为 `(V, 3)` | 将数组展平写入 `vertices.co`；顶点数量不匹配时抛出带 object 信息的 `RuntimeError` |
| `read_edges(obj)` | mesh object | 返回形状 `(E, 2)` 的 vertex-index 数组 |
| `read_edge_center(obj)` | mesh object | 返回形状 `(E, 3)` 的 local edge centers |
| `read_edge_direction(obj)` | mesh object | 返回形状 `(E, 3)` 的归一化 edge directions |
| `read_edge_length(obj)` | mesh object | 返回形状 `(E,)` 的 local edge lengths |

推荐用法：

```python
co = read_co(obj)
x, y, z = co.T
co[:, 2] += 0.03 * np.sin(x * 8.0)
write_co(obj, co)
```

`write_co` 直接修改基础 mesh，不会自动应用 modifier，也不会改变 object transform。修改后若后续逻辑依赖更新后的 mesh 状态，可调用 `obj.data.update()`。

## Face、Loop、UV 和材质索引

以下函数同样来自 `decorate.py`。

| 函数签名 | 返回/行为 | 关键条件 |
| --- | --- | --- |
| `read_center(obj)` | `(F, 3)` local polygon centers | 读取基础 mesh polygons |
| `read_normal(obj)` | `(F, 3)` local polygon normals | 不是 vertex normal，也不是 world normal |
| `read_area(obj)` | `(F,)` local polygon areas | 未计入未应用的 object scale |
| `read_loop_vertices(obj)` | 每个 loop 对应的 vertex index | 长度为 loop count |
| `read_loop_edges(obj)` | 每个 loop 对应的 edge index | 长度为 loop count |
| `read_uv(obj)` | `(L, 2)` active UV coordinates | 必须已有 active UV layer |
| `write_uv(obj, arr)` | 写入 active UV layer | `arr` 应为 `(L, 2)` 且 active UV layer 已存在 |
| `read_material_index(obj)` | `(F,)` polygon material-slot indices | 返回整数数组 |
| `write_material_index(obj, arr)` | 写入 polygon material indices | `arr` 长度必须等于 polygon count |

面筛选示例：

```python
centers = read_center(obj)
normals = read_normal(obj)
top_faces = (normals[:, 2] > 0.9) & (centers[:, 2] > 0.2)
```

这里的 center 和 normal 都是 local space。对象 rotation 尚未应用时，`normal[:, 2]` 不代表 world-space 朝上。

## Named Attribute 数据

以下函数来自 `infinigen.core.surface`，直接操作 `obj.data.attributes`。

### `read_attr_data`

签名：

```python
read_attr_data(obj, attr, domain="POINT", result_dtype=None) -> np.ndarray
```

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `obj` | 目标 mesh object | attribute 必须在 `obj.data.attributes` 中 |
| `attr` | attribute name 或 attribute object | 优先传名称，函数会自动读取其 domain |
| `domain` | 传 attribute object 时用于确定元素数量 | 支持 `"POINT"`、`"EDGE"`、`"FACE"` |
| `result_dtype` | NumPy 输出 dtype | 常规类型不传；读取颜色等未配置默认 dtype 的类型时显式传入 |

行为：

- 根据 domain 分别使用 vertex、edge 或 polygon count。
- 根据 attribute data type 选择 Blender `foreach_get` field。
- scalar 返回 `(N,)`；多分量值返回 `(N, dim)`。
- attribute name 不存在、domain 不支持或 data type 映射不完整时会抛错。

### `write_attr_data`

签名：

```python
write_attr_data(obj, attr, data, type="FLOAT", domain="POINT") -> None
```

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `obj` | 目标 mesh object | 必须支持 mesh attributes |
| `attr` | attribute name 或 object | 名称不存在时自动创建 |
| `data` | NumPy array | 第一维数量必须匹配 domain 元素数 |
| `type` | 新建 attribute 的 Blender data type | 已存在 attribute 时该参数被忽略 |
| `domain` | 新建 attribute 的 domain | 已存在 attribute 时该参数被忽略 |

行为：将 `data.reshape(-1)` 写入 attribute 对应的 `value`、`vector` 或 `color` field。

### `new_attr_data`

签名：

```python
new_attr_data(obj, attr, type, domain, data) -> None
```

该函数要求 `attr` 是尚不存在的字符串名称；它总是新建 attribute 后写入数据。需要“存在则覆盖，不存在则创建”时使用 `write_attr_data`。

推荐用法：

```python
height = read_co(obj)[:, 2].astype(np.float32)
surface.write_attr_data(
    obj,
    "height_mask",
    height,
    type="FLOAT",
    domain="POINT",
)

mask = surface.read_attr_data(obj, "height_mask")
```

### 其他 attribute helper

| 接口 | 作用 | 静态单体建模建议 |
| --- | --- | --- |
| `set_active(obj, name)` | 将 named attribute 设为 active | 仅在后续 Blender operator 依赖 active attribute 时使用；名称必须存在 |
| `smooth_attribute(obj, name, iters=20, weight=0.05, verbose=False)` | 沿 mesh edges 迭代平滑 POINT attribute | 当前实现按多分量数组组织广播，优先用于 vector attribute；scalar mask 不建议直接使用 |
| `attribute_to_vertex_group(obj, attr, name=None, min_thresh=0, binary=False)` | 将 scalar attribute 转成 vertex group | 当前版本与 `read_attr_data` 的一维 scalar 返回形状不匹配，不作为 generated code 默认 API |

## 用 Geometry Nodes 写 Attribute

有两种相近接口：

| 接口 | 行为 | 适用情况 |
| --- | --- | --- |
| `surface.write_attribute(objs, node_func, name=None, data_type=None, apply=False)` | Capture node function 输出，并通过 geomod 暴露为 attribute | 需要复用 `surface.add_geomod` 的输出 attribute 机制 |
| `decorate.write_attribute(obj, fn, name, domain="POINT", data_type="FLOAT")` | 创建 `StoreNamedAttribute` geomod 并立即 apply | 需要直接把 field 固化为 named attribute |

`decorate.write_attribute` 的 `fn` 会交给 `surface.eval_argument`，可使用 callable、常数、向量或 attribute input 名称。callable 可接收 `nw`，并按参数名选择性接收 `position`。

```python
from infinigen.assets.utils.decorate import write_attribute

def height_field(nw, position):
    return nw.separate(position)[2]

write_attribute(obj, height_field, "height", domain="POINT", data_type="FLOAT")
```

`surface.write_attribute` 的完整参数和 apply 语义见 `surface_geomod_ops.md`。

## 自定义 Mesh 构造

### `objectdata_from_VF`

签名：

```python
objectdata_from_VF(vertices, faces) -> bpy.types.Mesh
```

| 参数 | 作用 | 约束 |
| --- | --- | --- |
| `vertices` | `(V, 3)` NumPy 坐标数组 | 会转换为 `float32` |
| `faces` | `(F, 3)` 顶点索引数组 | 当前实现只支持三角面 |

函数批量创建 vertices、loops 和 polygons，计算 edges，并返回未绑定 object 的 mesh data。

### `object_from_VF`

签名：

```python
object_from_VF(vertices, faces, name) -> bpy.types.Object
```

该函数用 `objectdata_from_VF` 创建 mesh object，并将 rotation 设为零。返回的 object 不会自动链接到 scene collection，必须显式链接：

```python
obj = butil.object_from_VF(vertices, faces, "custom_panel")
bpy.context.collection.objects.link(obj)
```

如果 faces 不是三角形，先三角化索引；不要把 quad 数组直接传给该接口。

### Trimesh 转换

| 接口 | 行为 | 限制 |
| --- | --- | --- |
| `object_from_trimesh(mesh, name, material=None)` | 从 trimesh 创建 Blender object，并复制 POINT vertex attributes | object 不会自动链接；同名 Blender object 会被删除 |
| `object_to_trimesh(obj)` | 将 Blender mesh 转成 `trimesh.Trimesh` | 只适合已三角化 mesh；只应依赖 POINT-domain vertex attributes |
| `object_to_vertex_attributes(obj)` | 将 attributes 读为 NumPy dict | 按 vertex count 分配，非 POINT-domain attribute 不可靠 |

只有算法明确依赖 trimesh 时才使用这些转换；普通资产建模优先使用 Blender primitive、modifier 和 geometry nodes。低频转换接口仍完整保留。

## 空间、Bounds 与法线工具

| 函数签名 | 行为 | 注意 |
| --- | --- | --- |
| `apply_matrix_world(obj, verts)` | 将 `(N, 3)` local coordinates 转为 world coordinates | 返回 NumPy array |
| `bounds(obj)` | 返回 `(min_corner, max_corner)` | 基于 `obj.bound_box`，结果是 local space |
| `surface_area(obj)` | 用 bmesh 求基础 mesh 的总面积 | 未应用 object scale 不计入面积 |
| `global_polygon_normal(obj, polygon, rev_normal=False)` | 用 object world rotation 转换并归一化 polygon normal | 忽略非均匀 scale 对法线的逆转置影响；非均匀 scale 应先 apply transform |
| `global_vertex_coordinates(obj, local_vertex)` | 返回一个 Blender vertex 的 world coordinate | 参数是 vertex object，不是 NumPy 坐标 |
| `recalc_normals(obj, inside=False)` | 在 Edit Mode 重算法线 | `inside=True` 令法线朝内 |

`read_base_co(obj)` 会从 evaluated object 调用 `to_mesh()` 并读取 modifier 后的坐标，返回 object local coordinates。当前 helper 没有调用 `to_mesh_clear()`；不要在大循环中反复使用，以免累积临时 evaluated mesh。常规基础 mesh 读写仍使用 `read_co`；需要可管理的独立 evaluated mesh object 时使用 `butil.to_mesh`，并显式清理返回对象。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把 `read_co`、`read_normal` 当 world-space 数据 | 使用 `apply_matrix_world` 或对应 global helper |
| `write_co` 的顶点数量与 mesh 不一致 | 保持数组形状为 `(len(obj.data.vertices), 3)` |
| 写入已存在 attribute 时仍期待 `type` / `domain` 生效 | 先验证现有定义；需要不同定义时删除后重建 |
| attribute domain 为 `FACE` 却传 vertex-count 数据 | 数据第一维必须匹配 polygon count |
| 读取颜色 attribute 时依赖自动 dtype | 显式传 `result_dtype=np.float32` |
| 给 `object_from_VF` 传 quad faces | 先三角化为 `(F, 3)` |
| 创建 `object_from_VF` 后场景中看不到 object | 将返回 object link 到 collection |
| 用 face local normal 判断 world 朝向 | 先 apply rotation，或使用 world-space normal helper |
