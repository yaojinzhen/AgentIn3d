# 磨损与划痕材质

本文档记录在已有材质节点树上叠加边缘磨损和划痕的类、shader/geometry helper、参数及调用限制。磨损类不会创建基础材质，必须在对象完成材质赋值后调用。

主要源码：

- `infinigen/assets/materials/wear_tear/edge_wear.py`
- `infinigen/assets/materials/wear_tear/scratches.py`

## 接口索引

| 需求 | 接口 | 当前状态 |
| --- | --- | --- |
| 掉漆边缘、边缘露底和局部刮擦 | `EdgeWear.apply_over` / `apply` | 可直接使用 |
| 只有凹凸划痕、不改变基础颜色 | `Scratches.apply_over` / `apply` | 当前连接逻辑无效，需使用文档中的修正 helper |
| 显式构建划痕 displacement | `scratch_shader` | 可复用，但需调用方连接到 Material Output |
| 自定义边缘磨损节点组合 | `shader_edge_tear_free_node_group` | 低层接口；需传入原始 surface 与 displacement |

## 前置条件

- `obj` 应是带 `data.materials` 的 mesh object。
- 每个目标 material 必须启用 nodes，并包含 Material Output。
- `EdgeWear` 还要求 Material Output 的 `Surface` 已连接。
- 两类效果都会遍历对象的所有 material slots；`selection` 参数当前未使用，不能限制到某个 face selection 或 material slot。
- 纹理使用 Object 坐标；对象尺寸和未应用缩放会改变磨损尺度。
- shader displacement 是否产生真实凹凸取决于渲染器、材质设置和网格细分。

## `EdgeWear`

```python
EdgeWear().apply_over(
    obj,
    selection=None,
    **shader_kwargs,
)

EdgeWear().apply(obj)
```

| 接口 | 参数 | 行为 |
| --- | --- | --- |
| `apply_over` | 单个 `obj`；未使用的 `selection`；可选磨损参数 | 修改对象所有现有材质的节点树 |
| `apply` | 单个 object 或 object iterable | 对每个对象调用无参数的 `apply_over`，因此使用随机参数 |

当 `shader_kwargs` 为空时，`get_edge_wear_params()` 为一次调用生成一组随机参数，并将同一组参数应用到对象的全部材质。效果会：

1. 读取原 Surface 与可选 Displacement。
2. 混合掉漆、露底和划痕表面。
3. 将新增 displacement 与原 displacement 相加。
4. 给最终 Mix Shader 标记 `label="wear_tear"`。

再次调用时，只要节点树中存在该标签，就会跳过，避免重复叠加。

### 边缘磨损参数

```python
shader_edge_tear_free_node_group(
    nw,
    original_bsdf,
    original_displacement,
    _worn_off_opacity=0.5,
    _worn_off_radius=0.015,
    _scratch_radius=0.01,
    _worn_off_mask_randomness=2.0,
    _edge_base_color_hue=1.0,
    _edge_base_color_whiteness=0.1,
    _scratch_mask_randomness=0.5,
    _scratch_density=5.0,
    _scratch_opacity=0.2,
)
```

| 参数 | 作用 | 随机 helper 的范围 |
| --- | --- | --- |
| `_worn_off_opacity` | 掉漆区域混合强度 | `0.01..1.0`；源码 `uniform(0.01)` 将 `0.01` 作为下界 |
| `_worn_off_radius` | Bevel 节点检测边缘的半径 | `0.005..0.01` |
| `_scratch_radius` | 细刮擦边缘检测半径 | `0.01..0.03` |
| `_worn_off_mask_randomness` | 掉漆 mask 噪声尺度 | `2.5..3.0` |
| `_edge_base_color_hue` | 露底层 HSV 色相 | `0..1` |
| `_edge_base_color_whiteness` | 露底层亮度/白度控制 | `0.1..0.6` |
| `_scratch_mask_randomness` | 划痕 mask 噪声尺度 | 约 `0.1..10` |
| `_scratch_density` | 划痕密度 | `1.5..10` |
| `_scratch_opacity` | 划痕表面混合强度 | `0.5..1.0` |

`original_bsdf` 应是连接到 Material Output Surface 的 shader node；`original_displacement` 可为 `None` 或已有 displacement node。普通调用优先使用 `EdgeWear.apply_over`，不要手动管理这两个参数。

推荐用法：

```python
from infinigen.assets.materials.wear_tear.edge_wear import EdgeWear

EdgeWear().apply_over(
    obj,
    _worn_off_opacity=0.008,
    _worn_off_radius=0.007,
    _scratch_radius=0.015,
    _worn_off_mask_randomness=2.7,
    _edge_base_color_hue=0.08,
    _edge_base_color_whiteness=0.3,
    _scratch_mask_randomness=3.0,
    _scratch_density=5.0,
    _scratch_opacity=0.65,
)
```

## `Scratches`

```python
Scratches().apply_over(
    obj,
    selection=None,
    **shader_kwargs,
)

Scratches().apply(obj=None)
```

| 接口 | 声明行为 | 当前实现边界 |
| --- | --- | --- |
| `apply_over` | 为对象全部材质创建划痕 displacement | 使用 `find("MaterialOutput")` 无法匹配 `ShaderNodeOutputMaterial`，生成节点后没有连接输出 |
| `apply` | 接受单个 object 或 iterable | `obj=None` 虽是默认值，但调用后会处理 `None` 并报错；必须显式传对象 |

此外，marker 被写到 `NodeWrangler` 而不是 Blender node，重复调用不会被检测，会持续增加无效节点。当前代码不要直接调用 `Scratches.apply` 或 `apply_over`。

### 划痕参数

```python
scratch_shader(
    nw,
    original_bsdf,
    angle1=45.0,
    angle2=-20.0,
    scratch_scale=20.0,
    scratch_mask_ratio=0.8,
    scratch_mask_noise=10.0,
    scratch_depth=0.1,
)
```

| 参数 | 作用 | `get_scratch_params()` 范围 |
| --- | --- | --- |
| `original_bsdf` | 当前未使用，可传 `None` | - |
| `angle1`、`angle2` | 两组交叉划痕的 Mapping 旋转角输入 | `10..80`、`-80..-10` |
| `scratch_scale` | 划痕纹理密度 | 对数采样 `5..80` |
| `scratch_mask_ratio` | 划痕 mask 混合比例 | 对数采样 `0.01..0.9` |
| `scratch_mask_noise` | 大尺度 mask 噪声 | 对数采样 `5..40` |
| `scratch_depth` | Displacement Scale | 对数采样 `0.1..1.0` |

`scratch_shader` 返回 `{"Displacement": displacement_node}`，不会创建或连接 Material Output。

### 修正连接 helper

下面的 helper 保留已有 displacement、正确查找 Material Output，并用 node label 防止重复应用：

```python
from infinigen.assets.materials.wear_tear.scratches import (
    get_scratch_params,
    scratch_shader,
)
from infinigen.core.nodes import Nodes, NodeWrangler


def apply_scratches(obj, **params):
    if not params:
        params = get_scratch_params()

    for mat in obj.data.materials:
        if mat is None or not mat.use_nodes:
            continue

        nw = NodeWrangler(mat.node_tree)
        if any(node.label == "scratch" for node in nw.nodes):
            continue

        outputs = nw.find(Nodes.MaterialOutput)
        if not outputs:
            continue
        output = outputs[0]

        scratch = scratch_shader(nw, None, **params)["Displacement"]
        old_links = list(output.inputs["Displacement"].links)
        if old_links:
            combined = nw.new_node(
                Nodes.VectorMath,
                input_kwargs={0: old_links[0].from_socket, 1: scratch},
                attrs={"operation": "ADD"},
            )
            final_displacement = combined
        else:
            final_displacement = scratch

        nw.links.new(
            final_displacement.outputs[0],
            output.inputs["Displacement"],
        )
        scratch.label = "scratch"
```

先调用该 helper，再调用 `EdgeWear.apply_over`；后者会读取并保留已有 scratch displacement。反向执行时，必须确保自定义 scratch helper 仍将旧 displacement 相加。

## 使用边界

1. 磨损适合金属、喷漆木材、塑料和硬质家具；布料、玻璃、镜面及透明材质通常不应随机叠加 `EdgeWear`。
2. 不要对共享 material 的单个对象独立添加磨损：节点树修改会影响所有复用该 material 的对象。需要独立磨损时先复制 material。
3. 大量节点会增加材质编译和渲染成本。中远景资产优先省略磨损，或用更简单的 roughness/bump mask。
4. `material_assignments.wear_tear` 是两个 class 的普通列表，不能传给 `weighted_sample`。对应的 `wear_tear_prob=[0.5, 0.5]` 表示 `Scratches` 与 `EdgeWear` 各自独立的启用概率，不是二选一权重；当前应排除无效的 `Scratches` wrapper，或改用本文修正 helper。
