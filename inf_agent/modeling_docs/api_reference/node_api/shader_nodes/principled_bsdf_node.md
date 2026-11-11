# Principled BSDF 节点

本文档单独覆盖 `Nodes.PrincipledBSDF`。它是 Infinigen 室内资产最常用的表面 shader；每个材质只需设置与目标外观相关的少量输入，不要为了“完整”而填满全部 socket。通用 `new_node` 参数见 `../node_wrangler_usage.md`。

Blender 4.2 RNA 还会报告一个禁用的内部 `Weight` socket；它不是可写 API，本文档不将其列入 Input Sockets。

## 快速选择

| 材质目标 | 优先调整 |
| --- | --- |
| 塑料、木材、石材、墙面 | `Base Color`、`Roughness` |
| 金属、拉丝金属 | `Metallic=1`、`Roughness`；需要时再加 `Anisotropic` |
| 陶瓷、清漆表面 | 基础层参数 + `Coat Weight`、`Coat Roughness` |
| 布料 | `Roughness` + 少量 `Sheen Weight` |
| 玻璃、透明塑料 | `Transmission Weight`、`IOR`、`Roughness` |
| 皮肤、蜡等次表面散射 | `Subsurface Weight`、`Subsurface Radius`、`Subsurface Scale` |
| 自发光面板或文字 | `Emission Color`、`Emission Strength` |

复杂材质优先复用 Material API；直接编写节点时，先从 `Base Color`、`Metallic`、`Roughness` 三项开始。

## `Nodes.PrincipledBSDF`

**作用**：用一个物理统一的 shader 组合漫反射、金属、透射、次表面、coat、sheen、emission 和薄膜层。

**创建方式**：

```python
surface_shader = nw.new_node(
    Nodes.PrincipledBSDF,
    input_kwargs={
        "Base Color": (0.08, 0.09, 0.1, 1.0),
        "Metallic": 1.0,
        "Roughness": 0.28,
    },
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.PrincipledBSDF`，对应 `ShaderNodeBsdfPrincipled` |
| `input_kwargs` | 使用下表中的 Blender 4.2 socket 名称 |
| `attrs` | 可选 `distribution`、`subsurface_method` |
| `compat_mode` | 默认 `True` 会执行 Infinigen 的 subsurface 兼容转换 |

**Input Sockets**：按材质层分组如下；仅设置目标外观需要的组。

### 核心输入

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Base Color` | Color | 非金属的漫反射色或金属反射色 |
| `Metallic` | Float | 0 为介电材质，1 为金属；通常不要用中间值模拟脏污，改用 mask 混合 |
| `Roughness` | Float | 0 为锐利反射，1 为粗糙反射；多数室内表面约从 `0.15-0.8` 调整 |
| `IOR` | Float | 透射及介电反射的折射率；常见玻璃约 `1.45-1.52`，水约 `1.33` |
| `Alpha` | Float | 表面不透明度；小于 1 时仍需匹配材质的透明渲染设置 |
| `Normal` | Vector | 基础层法线，接 Normal Map 或明确允许的 Bump 输出 |

### Subsurface 输入

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Subsurface Weight` | Float | 次表面散射权重；硬表面通常保持 0 |
| `Subsurface Radius` | Vector | RGB 三通道的相对散射距离 |
| `Subsurface Scale` | Float | 整体散射尺度；受下文 `compat_mode` 特殊行为影响 |
| `Subsurface IOR` | Float | 仅 `RANDOM_WALK_SKIN` 可用 |
| `Subsurface Anisotropy` | Float | Random Walk 模式中的散射方向性 |

### Specular 与 Anisotropy 输入

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Specular IOR Level` | Float | 相对 IOR 对应值缩放介电镜面反射；通常保持 `0.5` |
| `Specular Tint` | Color | 给介电镜面反射着色；物理材质通常保持白色 |
| `Anisotropic` | Float | 拉长高光，适合拉丝金属 |
| `Anisotropic Rotation` | Float | 绕法线旋转各向异性方向，`0-1` 对应一整圈 |
| `Tangent` | Vector | 显式指定各向异性切线；不连接时使用活动 UV 的切线 |

### Transmission、Coat 与 Sheen 输入

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Transmission Weight` | Float | 0 为不透射，1 为玻璃式透射；实体折射需要合理厚度和闭合几何 |
| `Coat Weight` | Float | 基础材质上方的透明反射层权重 |
| `Coat Roughness` | Float | coat 层粗糙度 |
| `Coat IOR` | Float | coat 层折射率 |
| `Coat Tint` | Color | coat 层颜色；普通清漆保持白色 |
| `Coat Normal` | Vector | 只影响 coat 层的法线 |
| `Sheen Weight` | Float | 布料等表面的掠射角柔和反射 |
| `Sheen Roughness` | Float | sheen 层粗糙度 |
| `Sheen Tint` | Color | sheen 层颜色 |

### Emission 与 Thin Film 输入

| Socket | 类型 | 说明 |
| --- | --- | --- |
| `Emission Color` | Color | 表面发光颜色 |
| `Emission Strength` | Float | 发光强度；0 关闭 emission |
| `Thin Film Thickness` | Float | 薄膜厚度，0 关闭虹彩薄膜效果 |
| `Thin Film IOR` | Float | 薄膜折射率 |

**Output Sockets**：`BSDF`（Shader），连接 `Nodes.MaterialOutput.inputs["Surface"]` 或 `Nodes.MixShader`。

## 节点属性

| `attrs` | 可选值 | 建议 |
| --- | --- | --- |
| `distribution` | `GGX`、`MULTI_GGX` | 默认 `MULTI_GGX`；仅在明确需要更快的单次散射近似时改为 `GGX` |
| `subsurface_method` | `BURLEY`、`RANDOM_WALK`、`RANDOM_WALK_SKIN` | 普通轻量 SSS 可用 `BURLEY`；闭合几何的高质量 SSS 使用 Random Walk；皮肤专用输入只在 `RANDOM_WALK_SKIN` 可用 |

`attrs` 会改变可用输入：`BURLEY` 不使用 `Subsurface IOR` 和 `Subsurface Anisotropy`；`RANDOM_WALK` 使用 Anisotropy；`RANDOM_WALK_SKIN` 同时使用 IOR 和 Anisotropy。

## Infinigen 兼容行为

`NodeWrangler.new_node` 默认 `compat_mode=True`，对本节点执行以下转换：

1. 无条件把 `Subsurface Scale` 写为 `1`，即使调用方传入了其他值。
2. 移除旧版 `Subsurface Color` 并记录 warning；Blender 4.2 已没有该 socket。

新生成代码不要传 `Subsurface Color`。若确实需要 Blender 4.2 的非 1 `Subsurface Scale`，应在确认全部 socket 都使用当前接口后设置 `compat_mode=False`：

```python
wax = nw.new_node(
    Nodes.PrincipledBSDF,
    input_kwargs={
        "Base Color": (0.8, 0.5, 0.25, 1.0),
        "Subsurface Weight": 0.2,
        "Subsurface Radius": (1.0, 0.35, 0.2),
        "Subsurface Scale": 0.03,
    },
    compat_mode=False,
)
```

只为设置常规 PBR 参数时保持默认 `compat_mode=True`。

## 常用参数组合

| 外观 | 最小组合 |
| --- | --- |
| 哑光塑料 | `Metallic=0`，`Roughness=0.35-0.65` |
| 抛光金属 | `Metallic=1`，`Roughness=0.08-0.3` |
| 拉丝金属 | 抛光金属 + `Anisotropic=0.4-0.9`，并提供稳定 Tangent/UV |
| 釉面陶瓷 | `Roughness=0.2-0.45`，`Coat Weight=0.3-1`，低 `Coat Roughness` |
| 布料 | `Roughness=0.5-0.9`，`Sheen Weight=0.05-0.35` |
| 实体玻璃 | `Transmission Weight=1`，`Roughness=0-0.15`，`IOR` 约 1.5 |

这些区间只用于初始化搜索，不是固定材质标准；最终值应与资产尺寸、纹理尺度和灯光共同验证。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 使用旧 socket `Transmission`、`Clearcoat`、`Emission` | Blender 4.2 使用 `Transmission Weight`、`Coat Weight`、`Emission Color` |
| 传入 `Subsurface Color` 后颜色没有生效 | 该旧输入会被兼容层移除；使用 `Base Color` |
| 设置 `Subsurface Scale=0.03` 却得到 1 | 默认兼容层会覆盖；确认接口后使用 `compat_mode=False` |
| `Alpha<1` 但渲染仍不透明 | 同步配置材质透明模式；或用 Transparent BSDF 明确混合 |
| 用 `Metallic=0.5` 表示一半区域生锈 | 用材质 mask 在金属和非金属参数间混合 |
| 玻璃只有单层平面却期待正确实体折射 | 为物体提供厚度，或采用项目的窗口专用材质路径 |

## 相关文档

- 其他表面 BSDF 与 Mix Shader：`surface_bsdf_nodes.md`
- Emission、Volume 与 Hair：`emission_volume_hair_nodes.md`
- Normal 与 Displacement：`displacement_normal_nodes.md`
- Material Output：`shader_world_output_nodes.md`
- 版本兼容：`../socket_attrs_and_compatibility.md`
- 材质 API：`../../material_api/README.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- `infinigen/core/nodes/compatibility.py`
- `infinigen/assets/materials/ceramic/ceramic.py`
- `infinigen/assets/materials/lamp_shaders.py`
- `infinigen/assets/materials/metal/appliance.py`
- [Blender 4.2 Principled BSDF](https://docs.blender.org/manual/en/4.2/render/shader_nodes/shader/principled.html)
