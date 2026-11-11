# Surface BSDF 与 Mix Shader 节点

本文档覆盖 `PrincipledBSDF` 之外的表面 BSDF，以及用于组合 shader 的 `MixShader`。普通室内材质优先使用 `Nodes.PrincipledBSDF`；只有透明、折射、光路切换或分层需求明确时才选择本文档节点。

Blender 4.2 RNA 会为各 BSDF 报告禁用的内部 `Weight` socket；它不是可写 API，本文档不将其列入 Input Sockets。

## 快速选择

| 目标 | 节点 |
| --- | --- |
| 混合两个 shader | `Nodes.MixShader` |
| 只需要漫反射 | `Nodes.DiffuseBSDF` |
| 薄片透光、灯罩或叶片 | `Nodes.TranslucentBSDF` |
| 完全/部分跳过表面 | `Nodes.TransparentBSDF` |
| 反射与折射一体的玻璃 | `Nodes.GlassBSDF` |
| 只计算折射分量 | `Nodes.RefractionBSDF` |
| 只计算反射高光 | `Nodes.GlossyBSDF` |

玻璃、金属和塑料的新代码通常用 `PrincipledBSDF` 更简洁；Glass、Refraction 和 Glossy 主要用于需要显式 shader 分层的图。

## `Nodes.MixShader`

**作用**：按 factor 在线性意义上混合两个 shader closure。

**创建方式**：

```python
shader = nw.new_node(
    Nodes.MixShader,
    input_kwargs={
        "Fac": mask,
        1: shader_a,
        2: shader_b,
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.MixShader`，对应 `ShaderNodeMixShader` |
| `input_args` | 可按位置传 `[fac, shader_a, shader_b]` |
| `input_kwargs` | `Fac`；两个同名 `Shader` socket 必须用索引 `1`、`2` |

**Input Sockets**：

| Socket | 说明 |
| --- | --- |
| `Fac` | 0 选择第一个 shader，1 选择第二个；字段可用于材质 mask 或 Light Path |
| `Shader`（index 1） | 第一个 shader |
| `Shader`（index 2） | 第二个 shader |

**Output Sockets**：`Shader`。不要用字符串 `"Shader"` 同时设置两个输入，重复 socket 名会产生歧义。

## `Nodes.DiffuseBSDF`

**作用**：创建纯漫反射表面；适合简单 matte 分量或与其他 closure 混合。

**创建方式**：

```python
diffuse = nw.new_node(
    Nodes.DiffuseBSDF,
    input_kwargs={"Color": color, "Roughness": 0.4},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.DiffuseBSDF`，对应 `ShaderNodeBsdfDiffuse` |
| `input_kwargs` | `Color`、`Roughness`、可选 `Normal` |

**Input Sockets**：`Color` 控制漫反射色；`Roughness` 控制粗糙漫反射；`Normal` 可覆盖着色法线。

**Output Sockets**：`BSDF`。若材质还需要镜面、coat、metallic 或 transmission，直接使用 `PrincipledBSDF`。

## `Nodes.TranslucentBSDF`

**作用**：让光从薄表面的背面散射出来，适合灯罩、纸张、叶片等无实体内部体积的薄片。

**创建方式**：

```python
translucent = nw.new_node(
    Nodes.TranslucentBSDF,
    input_kwargs={"Color": shade_color},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.TranslucentBSDF`，对应 `ShaderNodeBsdfTranslucent` |
| `input_kwargs` | `Color`、可选 `Normal` |

**Input Sockets**：`Color` 为透射散射颜色；`Normal` 覆盖着色法线。

**Output Sockets**：`BSDF`。它不是透明节点，也不模拟有厚度介质的折射；常与 Principled/Diffuse 用 `MixShader` 组合。

## `Nodes.TransparentBSDF`

**作用**：让光线按颜色权重直接穿过表面，不产生玻璃式折射。

**创建方式**：

```python
transparent = nw.new_node(
    Nodes.TransparentBSDF,
    input_kwargs={"Color": (1.0, 1.0, 1.0, 1.0)},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.TransparentBSDF`，对应 `ShaderNodeBsdfTransparent` |
| `input_kwargs` | `Color` |

**Input Sockets**：`Color`；白色为完全透明，较暗或带色值会降低/改变各颜色通道的透过。

**Output Sockets**：`BSDF`。透明可见性仍受渲染器与材质设置影响。窗口等特殊材质可按 `LightPath` 区分 camera/shadow ray，但不要把此技巧当作真实玻璃。

## `Nodes.GlassBSDF`

**作用**：按 Fresnel 关系组合反射和折射，用于显式玻璃 closure。

**创建方式**：

```python
glass = nw.new_node(
    Nodes.GlassBSDF,
    input_kwargs={
        "Color": glass_color,
        "Roughness": 0.02,
        "IOR": 1.5,
    },
    attrs={"distribution": "MULTI_GGX"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.GlassBSDF`，对应 `ShaderNodeBsdfGlass` |
| `input_kwargs` | `Color`、`Roughness`、`IOR`、可选 `Normal` |
| `attrs` | `distribution`：`BECKMANN`、`GGX`、`MULTI_GGX` |

**Input Sockets**：`Color` 控制各波长透射；`Roughness` 控制模糊反射/折射；`IOR` 控制折射；`Normal` 覆盖法线。

**Output Sockets**：`BSDF`。实体玻璃应使用闭合且有厚度的几何。单层窗口可参考 Material API 的专用玻璃实现。

## `Nodes.RefractionBSDF`

**作用**：只生成折射分量，不包含 Glass BSDF 的 Fresnel 反射。

**创建方式**：

```python
refraction = nw.new_node(
    Nodes.RefractionBSDF,
    input_kwargs={"Color": color, "Roughness": 0.05, "IOR": 1.45},
    attrs={"distribution": "GGX"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.RefractionBSDF`，对应 `ShaderNodeBsdfRefraction` |
| `input_kwargs` | `Color`、`Roughness`、`IOR`、可选 `Normal` |
| `attrs` | `distribution`：`BECKMANN` 或 `GGX` |

**Input Sockets**：`Color`、`Roughness`、`IOR`、`Normal`，语义与 Glass 的折射部分一致。

**Output Sockets**：`BSDF`。Infinigen 资产源码没有直接创建该节点；新资产优先使用 Glass 或 Principled Transmission。只有明确要自行用 Fresnel 混合反射/折射时使用。

## `Nodes.GlossyBSDF`

**作用**：创建纯反射 closure，支持粗糙度和各向异性。

**创建方式**：

```python
glossy = nw.new_node(
    Nodes.GlossyBSDF,
    input_kwargs={
        "Color": reflection_color,
        "Roughness": 0.2,
        "Anisotropy": 0.6,
    },
    attrs={"distribution": "MULTI_GGX"},
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.GlossyBSDF`，对应 `ShaderNodeBsdfGlossy` |
| `input_kwargs` | `Color`、`Roughness`、`Anisotropy`、`Rotation`、可选 `Normal`、`Tangent` |
| `attrs` | `distribution`：`BECKMANN`、`GGX`、`ASHIKHMIN_SHIRLEY`、`MULTI_GGX` |

**Input Sockets**：

| Socket | 说明 |
| --- | --- |
| `Color` | 反射颜色 |
| `Roughness` | 反射模糊程度 |
| `Anisotropy` / `Rotation` | 高光拉伸量与方向 |
| `Normal` / `Tangent` | 着色法线与各向异性方向 |

**Output Sockets**：`BSDF`。新金属通常使用 Principled 的 `Metallic`、`Roughness` 和 `Anisotropic`；本节点适合显式反射层或维护已有 Infinigen 图。

## 选择与组合规则

- `MixShader` 是 closure 混合，不等于 `Nodes.Mix` 的颜色/数值混合。
- `Fac` mask 若表示“B 区域”，应把 B shader 接 index 2；反接会翻转材质区域。
- 玻璃优先级通常为 Material API > Principled Transmission > Glass BSDF > 手工 Fresnel + Refraction/Glossy。
- `TransparentBSDF`、`TranslucentBSDF` 和 `GlassBSDF` 语义不同，不应互相替代。
- 每个 surface graph 最终连接一个 `MaterialOutput.inputs["Surface"]`。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| `input_kwargs={"Shader": ...}` 试图设置 Mix 的两个 shader | 用整数 key `1`、`2`，或用 `input_args` |
| 把颜色 socket 接到 `MixShader` | 颜色用 `Nodes.Mix`；MixShader 只接 Shader 输出 |
| 用 Transparent 模拟有厚度玻璃 | 使用 Principled Transmission 或 Glass BSDF |
| 用 Translucent 模拟透明窗口 | Translucent 是薄表面散射，不是直接透过 |
| Refraction 材质没有反射 | 这是节点定义；使用 Glass，或用 Fresnel 与 Glossy 混合 |
| 新金属只使用 Glossy | 优先用 Principled Metallic，能保留统一 PBR 参数 |

## 相关文档

- Principled BSDF：`principled_bsdf_node.md`
- Shader 输入、Fresnel 与 Light Path：`shader_input_nodes.md`
- Normal 与 Displacement：`displacement_normal_nodes.md`
- Material Output：`shader_world_output_nodes.md`
- Material API：`../../material_api/README.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/assets/materials/ceramic/glass.py`
- `infinigen/assets/materials/lamp_shaders.py`
- `infinigen/assets/materials/metal/appliance.py`
- `infinigen/assets/objects/windows/window.py`
- [Blender 4.2 Shader Nodes](https://docs.blender.org/manual/en/4.2/render/shader_nodes/shader/index.html)
- [Blender 4.2 Mix Shader](https://docs.blender.org/manual/en/4.2/render/shader_nodes/shader/mix.html)
- [Blender 4.2 Glass BSDF](https://docs.blender.org/manual/en/4.2/render/shader_nodes/shader/glass.html)
