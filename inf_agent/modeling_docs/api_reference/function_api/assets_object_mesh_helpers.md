# Assets Object 与 Mesh 辅助接口

本文档记录 `infinigen/assets/utils` 中被多类资产复用、适合静态单体资产代码使用的 object 和 mesh helper。

源码依据：

- `infinigen/assets/utils/object.py`
- `infinigen/assets/utils/decorate.py`
- `infinigen/assets/utils/mesh.py`
- `infinigen/assets/utils/misc.py`

这些接口位于 `infinigen/assets`，稳定性低于 `infinigen/core`。存在功能等价的 core API 时优先使用 core；本页主要补充 origin 对齐、bbox、数组驱动 mesh 编辑和少量高复用拓扑操作。

## 推荐导入

```python
import bpy
import numpy as np

from infinigen.assets.utils.decorate import (
    displace_vertices,
    remove_faces,
    remove_vertices,
    select_edges,
    select_faces,
    set_shade_smooth,
    subsurface2face_size,
)
from infinigen.assets.utils.mesh import polygon_angles, prepare_for_boolean
from infinigen.assets.utils.object import (
    data2mesh,
    mesh2obj,
    new_bbox,
    new_bbox_2d,
    origin2lowest,
    separate_loose,
)
from infinigen.core.util import blender as butil
```

## 选择表

| 目标 | 推荐接口 |
| --- | --- |
| 将 mesh 原点移到底部并冻结位置 | `origin2lowest` |
| 从 min/max 坐标快速创建 box | `new_bbox` / `new_bbox_2d` |
| 从 vertices、edges、faces 创建并链接 object | `data2mesh` -> `mesh2obj` |
| 用 NumPy/callable 位移顶点 | `displace_vertices` |
| 按坐标条件删除或选择 mesh elements | `remove_*` / `select_*` |
| loose parts 中只保留最大连通块 | `separate_loose` |
| 根据当前平均面面积启发式细分 | `subsurface2face_size` |
| boolean 前合并重复/近距离顶点 | `prepare_for_boolean` |

坐标、法线、attribute 的基础读取见 `attributes_and_mesh_data.md`；join 和 object tree 见 `object_join_parent_collection.md`。

## Origin 对齐

### `origin2lowest`

签名：

```python
origin2lowest(obj, vertical=False, centered=False, approximate=False) -> None
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `obj` | 目标 mesh object | 应已有顶点，并在 world placement 和 parenting 之前调用 |
| `vertical` | 是否只沿 local Z 移动原点 | 家具落地对齐通常设为 `True` |
| `centered` | 是否让 XY 使用 bbox center，同时 Z 对齐最低点 | 需要底面中心为原点时设为 `True` |
| `approximate` | 是否用最低约 10% 顶点均值估计 XY | 底部有离群尖点时使用；小于 10 个顶点不建议 |

行为：

- 读取 local vertex coordinates 并找到最低 Z 顶点。
- 根据模式设置 `obj.location`，随后调用 `butil.apply_transform(obj, loc=True)`。
- 因为 `apply_transform` 的 `rot` 和 `scale` 默认仍为 `True`，location、rotation 和 scale 都会烘焙进 mesh。
- 最终 object transform 回到 identity 附近。
- 空 mesh 直接返回。

```python
leg = new_bbox(-0.03, 0.03, -0.03, 0.03, 0.0, 0.7)
origin2lowest(leg, centered=True)
```

`vertical=True` 只重算 Z，不重新居中几何的 XY；但 object 原有的 X/Y location 仍会随完整 transform 一起烘焙。`centered=True` 和 `approximate=True` 同时为真时，源码优先采用 `approximate` 分支。

### 其他方向

| 函数 | 行为 | 限制 |
| --- | --- | --- |
| `origin2highest(obj)` | 将 local Z 最高顶点移到原点并 apply 全部 transform | 空 mesh 会在 `argmax` 处失败 |
| `origin2leftmost(obj)` | 将 local X 最小顶点移到原点并 apply 全部 transform | 其余轴也按该顶点对齐，不只是 X |

需要只沿某一轴对齐时，优先直接计算坐标并只设置对应 location 分量。

## 自定义 Mesh 创建

### `bpy.types.Mesh.from_pydata`

Blender 外部 API；检索别名为 `Mesh.from_pydata` 和 `from_pydata`。
它不属于仓库源码，不能传给 `read --symbol`。使用实例方法
`mesh.from_pydata(vertices, edges, faces)`：vertices 是三维坐标，edges 是索引对，
faces 是顶点索引环；已有 faces 时 edges 可为空。调用后执行 `mesh.update()`。
该方法填充 mesh 数据，不创建 object，也不链接场景；调用者需要创建 object 并链接 collection。
顶点索引、面绕序与闭合性由调用者保证；不能用深色面代替孔洞。

以下是可直接保存为 asset.py 的 1 米蓝色立方体示例（Blender 4.2）：

```python
import bpy
from infinigen.core.placement.factory import AssetFactory

class MeshBoxFactory(AssetFactory):
    def create_asset(self, **params):
        width = 1.0
        vertices = [(x * width, y, z)
                    for z in (0.0, 1.0)
                    for x, y in ((-0.5, -0.5), (0.5, -0.5),
                                 (0.5, 0.5), (-0.5, 0.5))]
        faces = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4),
                 (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        mesh = bpy.data.meshes.new("box_mesh")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new("box", mesh)
        bpy.context.collection.objects.link(obj)
        material = bpy.data.materials.new("blue")
        material.diffuse_color = (0.03, 0.15, 0.8, 1.0)
        obj.data.materials.append(material)
        return obj
```

### `data2mesh`

签名：

```python
data2mesh(vertices=(), edges=(), faces=(), name="") -> bpy.types.Mesh
```

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `vertices` | 三维坐标序列 | 顶点 index 是 edges/faces 的基础 |
| `edges` | `(i, j)` 序列 | 可为空 |
| `faces` | vertex-index polygon 序列 | 支持三角形、quad 和 n-gon |
| `name` | mesh datablock 名称 | 使用可识别名称 |

函数调用 Blender `mesh.from_pydata` 并 `update`，但不创建 object，也不链接 scene。

### `mesh2obj`

签名：

```python
mesh2obj(mesh) -> bpy.types.Object
```

行为：

- 用 `mesh.name` 创建 object。
- 链接到 scene 根 collection。
- 将其设为 active object。
- 返回 object。

```python
mesh = data2mesh(
    vertices=[(-0.5, 0, 0), (0.5, 0, 0), (0.5, 0, 1), (-0.5, 0, 1)],
    faces=[(0, 1, 2, 3)],
    name="panel",
)
panel = mesh2obj(mesh)
```

如果只有三角面并希望批量写 NumPy 数组，也可以使用 `attributes_and_mesh_data.md` 中的 `butil.object_from_VF`；注意后者不会自动 link。

### 截面环桥接

连续非回转外壳可由顶点数量和绕序一致的截面环桥接。下面的代码骨架保留了原建模示例中有价值的
拓扑算法，并使用 `mesh2obj` 确保结果已经链接到场景：

```python
def bridge_sections(name, sections):
    ring_size = len(sections[0])
    if len(sections) < 2 or ring_size < 3:
        raise ValueError("need at least two rings with three points each")
    if any(len(ring) != ring_size for ring in sections):
        raise ValueError("section rings must have compatible vertex counts")

    vertices = [point for ring in sections for point in ring]
    faces = []
    for row in range(len(sections) - 1):
        current = row * ring_size
        following = (row + 1) * ring_size
        for column in range(ring_size):
            nxt = (column + 1) % ring_size
            faces.append(
                (current + column, current + nxt, following + nxt, following + column)
            )

    mesh = data2mesh(vertices=vertices, faces=faces, name=f"{name}_mesh")
    return mesh2obj(mesh)
```

调用方仍需根据真实轮廓设计截面坐标，并明确处理封口、内外壁和法线。若相邻截面的起始顶点或绕序
不一致，会产生整体扭转；细分不能修复该问题。

## BBox Helper

### `new_bbox`

签名：

```python
new_bbox(x, x_, y, y_, z, z_) -> bpy.types.Object
```

六个参数分别是 local X/Y/Z 的最小值和最大值。函数创建 cube，将其平移和缩放到指定 bounds，然后 apply location、rotation 和 scale。

```python
side_panel = new_bbox(
    -width / 2,
    -width / 2 + thickness,
    -depth / 2,
    depth / 2,
    0,
    height,
)
```

每一轴都应满足 `min <= max`。反向区间会产生负 scale 并可能导致 normals 方向问题。

### `new_bbox_2d`

签名：

```python
new_bbox_2d(x, x_, y, y_, z=0) -> bpy.types.Object
```

创建位于指定 Z 的 rectangular plane，并 apply transform。它没有厚度；需要实体板时使用 `new_bbox`，或随后添加 SOLIDIFY。

## 其他 Shape Wrapper

| 函数 | 默认几何语义 | 使用建议 |
| --- | --- | --- |
| `new_base_circle(**kwargs)` | Blender circle，默认中心在原点 | 需要只包含边的圆环基础 mesh 时使用 |
| `new_cylinder(**kwargs)` | 默认 `depth=1`、中心位于 `z=0.5`，因此底面在 `z=0`；随后 apply location | 需要“从地面向上”的单位圆柱时使用 |
| `new_base_cylinder(**kwargs)` | 使用 Blender cylinder 默认中心，随后 apply location | 需要以调用位置为几何中心时使用 |
| `new_grid(**kwargs)` | Blender grid，默认位于原点并 apply location | cloth 或规则细分平面起点 |
| `new_line(subdivisions=1, scale=1.0)` | 沿 local +X 从 `0` 到 `scale` 的 edge chain | 只创建线，不创建可见表面 |

`new_cube`、`new_plane`、`new_icosphere` 与 core object creation API 重复。新 generated code 优先读 `blender_primitive_objects.md`，不要仅因为已有资产使用旧 wrapper 就复制它。

`new_circle` 的默认 location 是 `(1, 0, 0)` 且会 apply location，语义容易误判；优先显式传 location，或使用 `new_base_circle`。

## 顶点位移

### `displace_vertices`

签名：

```python
displace_vertices(obj, fn) -> None
```

`fn` 支持两种形式：

| 形式 | 行为 |
| --- | --- |
| callable `fn(x, y, z)` | 应返回 `(dx, dy, dz)`，每项可为 scalar 或长度 `V` 的数组 |
| iterable / NumPy array | 直接执行 `co += fn`，推荐形状为 `(V, 3)` |

```python
def soften_front(x, y, z):
    return 0, -0.01 * np.exp(-(z / 0.2) ** 2), 0

displace_vertices(panel, soften_front)
```

函数读写基础 mesh 的 local coordinates。它不沿 normal 自动位移，也不会增加 topology；需要更细表面时先 subdivision。

## 删除 Mesh Elements

以下函数接受 bool mask/iterable，或一个基于 element center coordinates 的 callable。

| 函数签名 | callable 输入 | 行为 |
| --- | --- | --- |
| `remove_vertices(obj, to_delete)` | vertex `(x, y, z)` | 删除 mask 为真的 vertices 及相连 geometry |
| `remove_edges(obj, to_delete)` | edge-center `(x, y, z)` | 以 `EDGES_FACES` context 删除 edges |
| `remove_faces(obj, to_delete, remove_loose=True)` | face-center `(x, y, z)` | 只删除 faces；默认继续删除 loose edges |

```python
remove_faces(panel, lambda x, y, z: z < 0.05)
```

mask 长度必须匹配对应 element count。删除操作会改变后续 index，不要继续使用删除前缓存的 vertex/edge/face indices。

## 选择 Mesh Elements

| 函数签名 | callable 输入 | 结果 |
| --- | --- | --- |
| `select_vertices(obj, to_select)` | vertex coordinates | 清空旧选择并选择匹配 vertices |
| `select_edges(obj, to_select)` | edge centers | 清空旧选择并选择匹配 edges |
| `select_faces(obj, to_select)` | face centers | 清空旧选择并选择匹配 faces |

函数返回原 object，并将选择保留在 mesh 上，供后续 Blender operator 使用。

```python
select_edges(frame, lambda x, y, z: z > height - 1e-4)
with butil.ViewportMode(frame, "EDIT"):
    bpy.ops.mesh.bevel(offset=0.01, segments=3)
```

callable 看到的是 local-space center，而不是 world coordinates。仅为按 edge index 倒角时，也可以使用 `beveling_and_edges.md` 中的 `add_bevel`。

## 其他高复用 Mesh Helper

### `separate_loose`

签名：

```python
separate_loose(obj) -> bpy.types.Object
```

函数按 loose parts 分离 object，以 vertex count 选择最大部分，删除其余部分并返回最大 object。该操作是破坏性的；如果需要保留全部组件，直接使用 `butil.split_object(obj, mode="LOOSE")`。

### `subsurface2face_size`

签名：

```python
subsurface2face_size(obj, face_size) -> None
```

读取当前平均 polygon area，根据 `ceil(log2(mean_area / face_size))` 启发式选择 SUBSURF levels，并立即应用。`face_size` 必须为正；这是经验性细分强度，不保证最终 face area 精确等于目标值。

### `set_shade_smooth`

签名：

```python
set_shade_smooth(obj) -> None
```

将所有 FACE-domain `use_smooth` 值写为 `1`。它只改变 shading flag，不添加 subdivision，也不会修复错误 normals。

### `prepare_for_boolean`

签名：

```python
prepare_for_boolean(obj) -> None
```

先应用 WELD modifier，再在 Edit Mode 执行 remove doubles。适合 boolean 前清理近距离重复顶点，但不能保证 mesh 一定 manifold。

### `polygon_angles`

签名：

```python
polygon_angles(n, min_angle=np.pi / 6, max_angle=2*np.pi / 3)
```

尝试生成 `[0, 2*pi)` 内排序后的随机角度，并约束相邻角差；100 次失败后退化为随机旋转的均匀角度。适合不规则截面轮廓。约束必须与 `n` 相容，否则通常走 fallback。

## 低频与上下文敏感接口

以下接口仍属于完整 API 参考，但由于副作用、重复能力或特定依赖，不作为 generated asset 的首选调用：

| 接口 | 原因与替代方案 |
| --- | --- |
| `assets.utils.object.join_objects` | join 后强制把 location/rotation/scale 设为 identity，容易改变结果位置；使用 `butil.join_objects` |
| `assets.utils.misc.assign_material` | 与 core surface API 重复；使用 `surface.assign_material` 或 `surface.add_material` |
| `assets.utils.misc.toggle_show` | 当前 recursive 分支错误调用 `toggle_hide`，不要作为显示层级 API |
| `trimesh2obj` / `obj2trimesh` | 已在 `attributes_and_mesh_data.md` 说明转换边界，且 `obj2trimesh` 会先破坏性三角化输入 |
| `mesh.bevel` / `reset_preset` | 随机选择装饰线脚 profile，属于特定造型策略，不是通用硬表面 bevel |
| `build_prism_mesh` / `build_convex_mesh` | 带固定随机造型假设，更适合作为具体资产示例 |
| `snap_mesh` / tree/LineString helpers | 算法重、依赖 Shapely/Trimesh，且面向特殊线网处理；需要特殊线网时按需使用，接口继续保留 |
| `make_normalized_factory` | 改写 factory 输出方向和原点，属于 factory adapter，不是普通 mesh helper |

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 使用 `new_bbox` 后再次按原 bounds 平移 | 其坐标已烘焙进 mesh，object transform 已 apply |
| `origin2lowest` 后期待保留原 object transform | helper 会 apply location、rotation 和 scale；需要保留时先复制或自行计算 |
| `displace_vertices` 返回单个 `(V,)` 数组 | callable 应返回三个分量，或直接传 `(V, 3)` array |
| 删除 elements 后继续使用旧 indices | 删除后重新读取 topology |
| 把 element callable 的坐标当 world space | helper 使用 local coordinates |
| `separate_loose` 后寻找被删除的小组件 | 需要全部组件时使用 `butil.split_object` |
| 用 assets primitive wrapper 替代已有 core API | 优先路由到 `blender_primitive_objects.md` |
