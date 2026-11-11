# 位移与法线节点

本文档覆盖 Shader node tree 中的高度位移和法线扰动节点。每个节点的参数表只列当前节点实际需要的 `new_node` 参数；通用参数语义见 `../node_wrangler_usage.md`。

## 快速选择

| 目标 | 节点 | 输出接到 |
| --- | --- | --- |
| 用标量 height field 改变轮廓或由渲染器转为 bump | `Nodes.Displacement` | `MaterialOutput.inputs["Displacement"]` |
| 解码已有 RGB normal map | `Nodes.ShaderNodeNormalMap` | BSDF 的 `Normal` |
| 直接把标量 height 转为局部 shading normal | `Nodes.Bump`，必须 `strict=False` | BSDF 的 `Normal` |

Infinigen 的主路径是 `Nodes.Displacement`：shader 始终输出 displacement，由渲染阶段统一选择 `DISPLACEMENT`、`BUMP`、`BOTH` 或 `NONE`。不要仅因为最终想要 bump 效果就直接使用被项目默认禁止的 `Nodes.Bump`。

## 共性规则

- `Displacement` 输出位移向量，连接 Material Output；Normal Map 和 Bump 输出法线，连接 BSDF。
- normal/bump 只改变光照法线，不改变轮廓和真实自阴影；真实 displacement 需要足够细分的 mesh，并主要面向 Cycles。
- 大尺度起伏应在 geometry 中建模；shader displacement 适合织物、木纹、砖缝、划痕等表面细节。
- 多个高度信号应先用 Math 节点合成，再进入一个 Displacement。多个法线效果则通过后一个节点的 `Normal` 输入串联。
- 资产 shader 负责构建节点图；全局 displacement mode 属于 runner/render 配置，不应在每个材质函数中反复修改。

## `Nodes.Displacement`

**作用**：将标量 height field 转为沿表面法线的位移向量，是 Infinigen 材质细节的默认实现。

**创建方式**：

```python
displacement = nw.new_node(
    Nodes.Displacement,
    input_kwargs={
        "Height": height,
        "Midlevel": 0.5,
        "Scale": 0.008,
    },
    attrs={"space": "OBJECT"},
)
nw.new_node(
    Nodes.MaterialOutput,
    input_kwargs={
        "Surface": surface_shader,
        "Displacement": displacement,
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Displacement`，对应 `ShaderNodeDisplacement` |
| `input_kwargs` | `Height`、`Midlevel`、`Scale`、可选 `Normal` |
| `attrs` | `space`：`OBJECT`（默认）或 `WORLD` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Height` | Float | 高度字段 |
| `Midlevel` | Float | 中性高度；`Height == Midlevel` 时位移为 0 |
| `Scale` | Float | 位移幅度，近似计算为 `(Height - Midlevel) * Scale` |
| `Normal` | Vector | 位移方向；不连接时使用当前表面法线 |

**Output Sockets**：`Displacement`（Vector），应连接 `Nodes.MaterialOutput` 的同名输入。

| height 数据 | 推荐设置 |
| --- | --- |
| `[0, 1]` 灰度高度图 | `Midlevel=0.5`，低于 0.5 向内、高于 0.5 向外 |
| 0 表示无位移的 signed/procedural field | `Midlevel=0.0` |
| 室内物体的细微表面起伏 | 先从物体尺度的约 `0.1%` 到 `1%` 选择 `Scale`，再按渲染结果收敛 |

`space="OBJECT"` 会让位移随 object scale 一起缩放；`WORLD` 忽略 object scale。程序化资产通常使用 `OBJECT`，但非均匀缩放会让位移幅度随轴向变化，生成后应尽量应用 scale 或在最终尺寸上调参。

是否发生真实位移不由本节点单独决定：

| Infinigen render mode | 行为 |
| --- | --- |
| `DISPLACEMENT` | 尝试真实位移；需要足够的 mesh subdivision |
| `BUMP` | 将 Material Output 的 displacement 转为近似法线效果 |
| `BOTH` | 较大细节真实位移，较小细节继续以 bump 表现 |
| `NONE` | 渲染前断开 Material Output 的 displacement 连接 |

该模式由 `infinigen/core/rendering/render.py::set_displacement_mode` 统一设置。单个资产 shader 通常只需正确连接 Displacement。

## `Nodes.ShaderNodeNormalMap`

**作用**：把 RGB 编码的 normal map 解码为表面法线。它处理的是方向贴图，不接受标量高度图。

**创建方式**：

```python
normal = nw.new_node(
    Nodes.ShaderNodeNormalMap,
    input_kwargs={
        "Strength": 1.0,
        "Color": normal_texture.outputs["Color"],
    },
    attrs={"space": "TANGENT", "uv_map": "UVMap"},
).outputs["Normal"]

surface_shader = nw.new_node(
    Nodes.PrincipledBSDF,
    input_kwargs={"Normal": normal},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.ShaderNodeNormalMap`，对应 `ShaderNodeNormalMap` |
| `input_kwargs` | `Strength`、`Color` |
| `attrs` | `space`；切线空间可选 `uv_map: str` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Strength` | Float | 0 为无效果，1 为贴图原始强度 |
| `Color` | Color | RGB normal 数据；中性切线空间法线通常为 `(0.5, 0.5, 1.0)` |

**Output Sockets**：`Normal`（Vector），连接到 BSDF 或下一个法线节点的 `Normal` 输入。

| `space` | 用途 |
| --- | --- |
| `TANGENT` | 标准 normal map；必须与模型 UV 和贴图使用的 UV 一致 |
| `OBJECT` / `WORLD` | 分别解码 object-space / world-space normal map |
| `BLENDER_OBJECT` / `BLENDER_WORLD` | 兼容旧 Blender 坐标约定，不用于新生成贴图 |

读取 normal map 的 Image Texture 应使用 Non-Color data。`uv_map` 只对 `TANGENT` 有意义；为空时使用 active render UV map。若 Color 未连接，默认中性值不会添加细节；读取几何法线应改用 `Nodes.NewGeometry.outputs["Normal"]`。

## `Nodes.Bump`

**作用**：从标量 height field 计算扰动法线，不改变真实几何。

**创建方式**：

```python
bump = nw.new_node(
    Nodes.Bump,
    input_kwargs={
        "Strength": 0.25,
        "Distance": 0.005,
        "Height": height,
    },
    attrs={"invert": False},
    strict=False,
)

surface_shader = nw.new_node(
    Nodes.PrincipledBSDF,
    input_kwargs={"Normal": bump.outputs["Normal"]},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Bump`，对应 `ShaderNodeBump` |
| `input_kwargs` | `Strength`、`Distance`、`Height`、可选 `Normal` |
| `attrs` | 可选 `invert: bool` |
| `strict` | 必须显式设为 `False`；默认 `True` 会抛出 `ValueError` |

**Input Sockets**：

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Strength` | Float | 法线扰动强度；从较小值开始，避免掠射角伪影 |
| `Distance` | Float | height 对应的表面偏移尺度 |
| `Height` | Float | 标量高度纹理 |
| `Normal` | Vector | 基础法线；用于在已有 Normal Map/Bump 之后叠加 |

**Output Sockets**：`Normal`（Vector）。

`invert=True` 交换凸起与凹陷方向。Blender 4.2 的该节点没有 `Filter Width` socket；不要照搬更新版本的接口。

Infinigen 默认禁止本节点，是为了让 displacement graph 保持统一并由 render mode 决定使用真实位移还是 bump。只有需要“局部修改某个 BSDF 的法线，但不影响 Material Output displacement”等明确流程时才使用 `strict=False`。

## 常见组合

将 normal map 作为基础，再叠加程序化微小 bump：

```python
base_normal = nw.new_node(
    Nodes.ShaderNodeNormalMap,
    input_kwargs={"Color": normal_texture.outputs["Color"]},
).outputs["Normal"]

detail_normal = nw.new_node(
    Nodes.Bump,
    input_kwargs={
        "Strength": 0.15,
        "Distance": 0.002,
        "Height": detail_height,
        "Normal": base_normal,
    },
    strict=False,
).outputs["Normal"]
```

若没有局部 BSDF 法线需求，优先把 `detail_height` 接入 `Nodes.Displacement`，让 Infinigen render mode 统一选择真实位移或 bump。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把灰度 height map 接到 Normal Map 的 `Color` | height 使用 Displacement；特殊局部流程才使用 Bump |
| 把 RGB normal map 接到 Displacement 的 `Height` | 使用 `Nodes.ShaderNodeNormalMap` 并连接 BSDF `Normal` |
| 创建 `Nodes.Bump` 时触发 `ValueError` | 这是项目预期限制；优先改用 Displacement，确需 Bump 才设 `strict=False` |
| Displacement 节点存在但没有效果 | 确认连接到 Material Output、render mode 非 `NONE`，且真实位移时 mesh 足够细分 |
| `[0, 1]` 高度图整体向外偏移 | 使用 `Midlevel=0.5`；只有 0 表示中性时才设为 0 |
| normal map 方向或接缝错误 | Image Texture 使用 Non-Color，并确认 `space`、UV map 与贴图烘焙设置一致 |
| 用空 Normal Map 节点读取表面法线 | 使用 `Nodes.NewGeometry.outputs["Normal"]` |
| 在 Blender 4.2 设置 Bump 的 `Filter Width` | 该 socket 属于更新接口，当前运行时不存在 |

## 相关文档

- 节点创建和 `strict`：`../node_wrangler_usage.md`
- Shader 坐标、UV 与几何法线：`shader_input_nodes.md`
- Image Texture 与程序纹理：`../common_nodes/texture_nodes.md`
- Principled BSDF 的 `Normal` 输入：`principled_bsdf_node.md`
- 其他 BSDF 的 `Normal` 输入：`surface_bsdf_nodes.md`
- Material Output 的 Displacement 输入：`shader_world_output_nodes.md`
- object 级材质创建与赋值：`../../function_api/surface_material_ops.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/core/rendering/render.py`
- `infinigen/core/util/blender.py`
- `infinigen/assets/materials/ceramic/brick.py`
- `infinigen/assets/materials/fabric/sofa_fabric.py`
- `infinigen/assets/materials/wear_tear/scratches.py`
- [Blender 4.2 Normal Map Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/vector/normal_map.html)
- [Blender 4.2 Displacement Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/vector/displacement.html)
- [Blender 4.2 Bump Node](https://docs.blender.org/manual/en/4.2/render/shader_nodes/vector/bump.html)
- [Blender Material Displacement](https://docs.blender.org/manual/en/4.2/render/materials/components/displacement.html)
