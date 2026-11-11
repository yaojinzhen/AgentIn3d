# 倒角与边选择

本文档记录单体资产中普通硬表面倒角，以及 Infinigen 用于从复杂 geometry nodes 输出中标记并恢复可倒角边的专用流程。

源码依据：`infinigen/core/util/bevelling.py`

普通 modifier 操作同时依赖：`infinigen/core/util/blender.py`

## 推荐导入

```python
from infinigen.core.nodes.node_wrangler import Nodes
from infinigen.core.util import blender as butil
from infinigen.core.util.bevelling import (
    add_bevel,
    complete_bevel,
    complete_no_bevel,
    get_bevel_edges,
)
```

## 方案选择

| 情况 | 推荐方案 |
| --- | --- |
| cube、柜板、门板等普通 mesh 的所有锐边 | `butil.modify_mesh(obj, "BEVEL", ...)` |
| 已有明确 edge index，只倒指定边 | `add_bevel` |
| geometry nodes 输出混合了应倒角与不应倒角的部件 | `complete_bevel` / `complete_no_bevel` 双遍标记流程 |
| 只需要简单的 angle / bevel weight 限制 | Blender BEVEL modifier，见 `blender_modifier_ops.md` |

## 普通硬表面倒角

推荐先应用 scale，再添加 modifier：

```python
obj.dimensions = (width, depth, height)
butil.apply_transform(obj)
butil.modify_mesh(
    obj,
    "BEVEL",
    width=min(width, depth, height) * 0.03,
    segments=3,
    limit_method="ANGLE",
)
```

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `width` | 倒角实际宽度 | 根据资产最小尺寸按比例设置，避免固定大数值 |
| `segments` | 截面分段数 | 室内硬表面通常 `2` 到 `4`；近景圆角再提高 |
| `limit_method` | 限制参与倒角的边 | 常用 `"ANGLE"`、`"WEIGHT"` 或 `"VGROUP"` |
| `angle_limit` | `ANGLE` 模式阈值 | 需要排除较平缓连接时设置 |

普通 modifier 是 generated code 的默认方案。下面的 `get_bevel_edges` 标记协议只用于 node geometry 难以直接表达边选择的情况。

## `get_bevel_edges`

签名：

```python
get_bevel_edges(obj) -> list[int]
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `obj` | 已应用 geometry nodes 的 mesh object | 必须是预处理 pass 生成的 mesh |

行为：

- 计算忽略远距离标记几何后的 local-space bounds。
- 选中两端点同时落在至少两个相同 bounds 平面上的边，即外部 bounding-box corner edges。
- 额外选中第一端点模长位于约 `50,000` 到 `150,000` 的边；这些边由 `complete_bevel(..., preprocess=True)` 平移到 `x=100,000` 附近。
- 返回 mesh edge indices，不修改 object。

限制：

- 结果依赖 local coordinates 和 edge index 顺序。
- 普通几何如果本身位于极大坐标附近，会与内部标记协议冲突。
- bounds 规则会自动包含外包围盒角边，不等于“只返回显式标记边”。
- 预处理输出必须保留一部分未平移的普通参考几何；如果所有 vertices 都被移到远处，`special_bounds` 无法计算正常 bounds。

## `add_bevel`

签名：

```python
add_bevel(obj, edges, offset=0.03, segments=8) -> bpy.types.Object
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `obj` | 要修改的 mesh object | scale 应提前 apply |
| `edges` | edge index iterable | index 必须对应当前 mesh topology |
| `offset` | mesh bevel 宽度 | 使用明显小于最窄局部结构的值 |
| `segments` | bevel 截面分段数 | 常规硬表面可降到 `2` 到 `4`；默认 `8` 成本较高 |

行为：

- 进入 Edit Mode，清空选择并按 index 选择 edges。
- 调用 `bpy.ops.mesh.bevel`，使用绝对 `offset`。
- 直接改变 mesh topology，不保留 modifier。
- 返回同一个 object。

```python
edge_ids = [0, 3, 8, 11]
obj = add_bevel(obj, edge_ids, offset=0.01, segments=3)
```

空 edge list 不会产生有意义的倒角。越界 index 会被自然忽略，因为实现遍历现有 edges 并检查 membership。

## Geometry Nodes 双遍标记

### `complete_bevel`

签名：

```python
complete_bevel(nw, geometry, preprocess)
```

### `complete_no_bevel`

签名：

```python
complete_no_bevel(nw, geometry, preprocess)
```

共同参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `nw` | 当前 `NodeWrangler` | 必须属于 geometry node group |
| `geometry` | 要分类的 geometry socket | 在 Join Geometry 前分别包装各部件 |
| `preprocess` | 是否构建 edge-detection pass | 由 nodegroup 的 Python 参数控制 |

共同行为：

- 两个函数都先添加 `RealizeInstances`，即使 `preprocess=False` 也会 realize。
- `complete_bevel(..., True)` 将 geometry 平移 `(100000, 0, 0)`。
- `complete_no_bevel(..., True)` 将 geometry 平移 `(200000, 0, 0)`。
- `preprocess=False` 时只返回 realized geometry，不平移。

nodegroup 中的分类模式：

```python
def nodegroup_appliance(nw, preprocess=False, **params):
    body = build_body(nw, **params)
    controls = build_controls(nw, **params)

    body = complete_bevel(nw, body, preprocess)
    controls = complete_no_bevel(nw, controls, preprocess)

    return nw.new_node(
        Nodes.JoinGeometry,
        input_kwargs={"Geometry": [body, controls]},
    )
```

完整调用顺序：

```python
# Pass 1: 生成带远距离标记的临时 mesh，提取 edge indices。
probe = butil.spawn_cube()
butil.modify_mesh(
    probe,
    "NODES",
    node_group=nodegroup_appliance(preprocess=True),
    ng_inputs=params,
    apply=True,
)
edge_ids = get_bevel_edges(probe)
butil.delete(probe)

# Pass 2: 用完全相同参数生成正常 mesh，再按相同 edge indices 倒角。
obj = butil.spawn_cube()
butil.modify_mesh(
    obj,
    "NODES",
    node_group=nodegroup_appliance(preprocess=False),
    ng_inputs=params,
    apply=True,
)
obj = add_bevel(obj, edge_ids, offset=0.01, segments=3)
```

## 双遍流程的不变量

两个 pass 必须满足：

- node group topology 完全一致。
- `ng_inputs` 完全一致。
- geometry 的创建顺序、Join Geometry 顺序和 Realize Instances 结果一致。
- 预处理 pass 中包含用于计算 bounds 的未平移参考 geometry。
- Python 随机参数在 pass 之前已经固定并复用，不能每个 pass 重新采样。
- 如果 nodegroup builder 有缓存机制，`preprocess=True` 和 `False` 必须能构建对应的不同 node tree，不能错误复用第一次结果。

任何会改变 edge count 或 edge ordering 的差异，都可能让第二遍倒角落在错误位置。

## 内部 Helper

| 函数 | 作用 | 使用建议 |
| --- | --- | --- |
| `special_bounds(obj)` | 忽略模长大于 `50000` 的标记顶点后计算 bounds | 由 `get_bevel_edges` 内部调用 |
| `on_bound_edges(point, min, max)` | 标记 point 位于哪些 bounds 平面 | 由 `get_bevel_edges` 内部调用 |

generated code 不应直接依赖这两个内部 helper。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 简单 cube 也使用双遍标记 | 改用普通 BEVEL modifier |
| 设置 dimensions 后未 apply scale | 倒角前调用 `butil.apply_transform(obj)` |
| 两遍之间重新随机采样参数 | 在 `FixedSeed` 下提前采样一次，并复用 params |
| 预处理时把全部 geometry 都包装成 bevel/no-bevel 标记 | 保留未平移的参考 geometry，或对简单全倒角对象改用普通 modifier |
| 第一遍和第二遍 Join Geometry 顺序不同 | 保持 node topology 和构建顺序完全一致 |
| `offset` 大于局部最小结构 | 按最小尺寸设较小比例，必要时降低 segments |
| `add_bevel` 后继续使用旧 edge indices | mesh topology 已改变，重新计算或停止按旧 index 操作 |
| 希望保留可调 modifier，却调用 `add_bevel` | 使用 `butil.modify_mesh(..., "BEVEL", apply=False)` |
