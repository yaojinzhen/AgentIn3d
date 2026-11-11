# 布料与软质材料

本文档记录针织、织物、皮革、天鹅绒、地毯和图案复合材质的具体类、shader function、坐标要求及调用限制。材质只负责颜色、编织纹理、粗糙度和 shader displacement；视觉材质族先由 `query material` 确定，靠垫鼓起、布料褶皱、缝线、厚度及垂坠形状仍需由网格建模或 cloth simulation 完成。

主要源码：

- `infinigen/assets/materials/fabric/**`
- `infinigen/assets/materials/art.py`

## 接口索引

| 需求 | 首选接口 | 说明 |
| --- | --- | --- |
| 毛衣、厚毯、粗织靠垫 | `fabric.CoarseKnitFabric` | 随机粗针织或砖状编织，Object 坐标，带 displacement |
| 窗帘、床品、细织布 | `fabric.FineKnitFabric` | 细密双向织纹，Object 坐标，带 displacement |
| 有方向的条纹软装 | `fabric.LinedFabric` | 随机色相、饱和度和条纹密度，Object 坐标 |
| 格纹或双色织物 | `fabric.PlaidFabric` | 可控织纹与配色，依赖有效 UV |
| 沙发、软包座椅 | `fabric.SofaFabric` | 高粗糙度和 sheen，读取名为 `UVMap` 的属性 |
| 天鹅绒座椅、装饰靠垫 | `fabric.Velvet` | 强 sheen、各向异性和细密纹理，支持局部 `apply` |
| 皮质座椅、皮革靠垫 | `fabric.Leather` | 皮革颗粒和粗糙度变化，Object 坐标 |
| 地毯、毛巾状表面 | `fabric.Rug` | 高密度颗粒与随机色差，Object 坐标 |
| 带随机图案的毯子或布料 | `art.ArtFabric` | 在随机织物基材上覆盖 UV 图像 |
| 带随机图案的地毯 | `art.ArtRug` | 在 `Rug` 基材上覆盖 UV 图像 |

## 调用协议

基础材质类通常按以下方式使用：

```python
from infinigen.assets.materials import fabric
from infinigen.core import surface

mat = fabric.SofaFabric()()
surface.assign_material(obj, mat)
```

| 接口 | 返回值 | 行为 |
| --- | --- | --- |
| `MaterialClass().generate()` | `bpy.types.Material` | 随机采样并创建材质，不赋给对象 |
| `MaterialClass()()` | `bpy.types.Material` | `__call__` 是 `generate` 的别名 |
| `fabric.Velvet().apply(obj, selection=None, **kwargs)` | `None` | 创建材质并赋给整个对象或指定 face selection |
| `surface.shaderfunc_to_material(shader_fn, **kwargs)` | `bpy.types.Material` | 绕过无参 wrapper，显式控制 shader 参数 |

除 `Velvet` 外，本页基础材质类都没有 `apply`。局部赋值应先生成材质，再使用 `surface.add_material` 等接口。`Velvet.apply` 使用 `materials.utils.common.apply`；字符串 selection attribute 不存在时不会明确报错，并可能把 face material index 重置为 `0`，因此必须预先确认 attribute。已有 material 的赋值规则见 `../function_api/surface_material_ops.md`。

材质内部包含随机采样。需要可复现结果时，应在 factory seed 或 `FixedSeed` 作用域内创建材质；只有显式提供 `seed` 的 shader 才能单独固定其纹理 seed。

## 坐标与几何要求

| 材质 | 坐标来源 | 使用要求 |
| --- | --- | --- |
| `CoarseKnitFabric`、`FineKnitFabric`、`LinedFabric` | Object | 不要求 UV；应用对象缩放后再生成最终外观，避免不同轴纹理密度失衡 |
| `Leather`、`Velvet`、`Rug` | Object | 不要求 UV；对象空间尺度会改变颗粒和织纹观感 |
| `PlaidFabric` | UV | 必须先展开 UV；UV 缩放和方向决定格纹尺度与朝向 |
| `SofaFabric` | named attribute `UVMap` | 应存在名为 `UVMap` 的 UV layer；缺失时纹理可能退化为近似纯色 |
| `ArtFabric`、`ArtRug` | UV Map | 必须有有效 UV；`bbox` 必须在两个方向均有大于 `0.001` 的跨度 |

这些 shader 输出到 Material Output 的 `Displacement`，但不会增加网格厚度或生成真实纤维。是否得到真实位移还取决于渲染器、材质位移设置和网格细分；普通室内资产可将其视为近景表面细节。

## 基础材质类

| 类 | `generate` / `apply` | 行为与推荐用途 |
| --- | --- | --- |
| `CoarseKnitFabric` | `generate()` | 每次从 `get_texture_params()` 采样粗织图案、颜色与位移；适合厚毯和粗织靠垫 |
| `FineKnitFabric` | `generate()` | 随机颜色、粗糙度、经纬密度和位移；适合细织布、窗帘和床品 |
| `LinedFabric` | `generate()` | 随机条纹颜色和密度；适合方向明确的软装面料 |
| `PlaidFabric` | `generate()` | 随机格纹开关和配色；适合已正确展开 UV 的装饰织物 |
| `SofaFabric` | `generate()` | 随机颜色，并在 `0.005` 至 `0.01` 范围采样 displacement strength |
| `Velvet` | `generate()`；`apply(obj, selection=None, **kwargs)` | 随机颜色、粗糙度和纹理混合；需局部赋值时优先使用 `apply` |
| `Leather` | `generate()` | 随机皮革颜色、纹理 seed 和粗糙度映射；适合皮质软包 |
| `Rug` | `generate()` | 在 `0.01` 至 `0.02` 范围采样 displacement strength，并随机颗粒与色差 |

这些 `generate()` 均无参数。需要控制外观时，不要向 wrapper 传参，应调用下一节列出的 shader function。

## 可控 shader 接口

### 粗针织

```python
shader_fabric_base(
    nw,
    _pattern_mixer=1.0,
    _pattern_density=0.15,
    _color=[5, 10.0, 10.0],
    _brick_knit=0.0,
    _knit_resolution=3.0,
    _brick_resolution=40,
    _crease_resolution=200,
    _smoothness=0.7,
    _color_shader_frac=0.01,
)
```

| 参数 | 作用 |
| --- | --- |
| `_pattern_mixer` | 在砖状图案和条纹图案之间混合，通常取 `0..1` |
| `_pattern_density` | 主图案密度；增大后纹理更密 |
| `_color` | 直接作为 RGB 分量组合，不是 HSV |
| `_brick_knit` | 砖状织纹对 displacement 的贡献，通常取 `0..1` |
| `_knit_resolution`、`_brick_resolution` | 细针织颗粒和砖状图案的尺度 |
| `_crease_resolution`、`_smoothness` | 褶皱噪声尺度及平滑偏置 |
| `_color_shader_frac` | 图案色与指定 `_color` 材质的混合比例 |

`shader_coarse_knit_fabric(nw, **kwargs)` 是随机 wrapper：它重新采样整组参数，传入的 `kwargs` 不会覆盖采样结果。需要确定参数时直接使用 `shader_fabric_base`。

### 细针织

```python
shader_material(
    nw,
    _color=(0.2, 0.2, 0.2),
    _roughness=0.4,
    _thread_density_x=200,
    _relative_density_y=1.0,
    _displacement_scale=0.005,
    _map="UV",
)
```

| 参数 | 作用 |
| --- | --- |
| `_color` | RGB 基色 |
| `_roughness` | 两个 Principled BSDF 共用的粗糙度 |
| `_thread_density_x` | 主方向线密度 |
| `_relative_density_y` | 另一方向相对密度；实际密度为两者乘积 |
| `_displacement_scale` | 织纹位移强度 |
| `_map` | Texture Coordinate 输出名，常用 `"Object"` 或 `"UV"` |

`shader_fine_knit_fabric(nw, **kwargs)` 会重新采样参数并强制 `_map="Object"`，传入的 `kwargs` 不生效。需要固定颜色、密度或 UV 映射时直接使用 `shader_material`。

### 条纹布

```python
shader_lined_fur_base(
    nw,
    _hue=0.3,
    _saturation=0.7,
    _line_density=10,
)
```

| 参数 | 作用 |
| --- | --- |
| `_hue` | HSV 色相，通常取 `0..1` |
| `_saturation` | HSV 饱和度，通常取 `0..1` |
| `_line_density` | Wave Texture 尺度；值越大条纹越密 |

`shader_lined_fur_random(nw, **kwargs)` 会随机采样三项参数并忽略传入的 `kwargs`。该材质只构建条纹 shader 和 displacement，不生成毛发几何。

### 格纹布

```python
shader_fabric(
    nw,
    weave_scale=500.0,
    color_scale=None,
    color_1_hsv=None,
    color_2_hsv=None,
    **kwargs,
)
```

| 参数 | 作用 |
| --- | --- |
| `weave_scale` | UV 空间织纹密度 |
| `color_scale` | 颜色图案密度；`0` 为单色，正值生成双色格纹；`None` 时随机选择 |
| `color_1_hsv`、`color_2_hsv` | 两组 HSV 颜色；`None` 时从 Infinigen 调色函数采样 |
| `kwargs` | 当前实现未使用 |

### 沙发布、地毯和天鹅绒

| Shader function | 参数 | 作用 |
| --- | --- | --- |
| `shader_sofa_fabric(nw, scale=1, strength=0.01, **kwargs)` | `scale`、`strength` | `scale` 缩放 `UVMap` 坐标；`strength` 控制 displacement |
| `shader_rug(nw, strength=0.01, **kwargs)` | `strength` | 控制地毯颗粒 displacement；颜色、粗糙度和图案尺度仍随机 |
| `shader_velvet(nw, **kwargs)` | 无可控外观参数 | 颜色、粗糙度和混合比例均在函数内部随机；额外 kwargs 被忽略 |

### 皮革

```python
shader_leather(
    nw,
    scale=1.0,
    base_color_hsv=None,
    seed=None,
    **kwargs,
)
```

| 参数 | 作用 |
| --- | --- |
| `scale` | 同时缩放大尺度噪声和细颗粒；增大后颗粒更密 |
| `seed` | 4D Noise/Voronoi 的纹理 seed；`None` 时随机采样 |
| `base_color_hsv` | 当前实现会被 `colors.leather_hsv()` 覆盖，传入值不生效 |
| `kwargs` | 当前实现未使用 |

需要固定皮革颜色时，应复制或封装 shader 并修正 `base_color_hsv` 的覆盖行为；只需稳定纹理布局时显式提供 `seed` 即可。

## 图案复合材质

```python
art.ArtFabric().generate(
    selection=None,
    bbox=(0, 1, 0, 1),
    **kwargs,
)

art.ArtRug().generate(
    selection=None,
    bbox=(0, 1, 0, 1),
    **kwargs,
)
```

| 接口 | 基础材质 | 行为 |
| --- | --- | --- |
| `ArtFabric` | 从粗针织、细针织、皮革、沙发布 shader 中加权随机选择 | 生成随机二维图案，将图像颜色接入基础材质的 Principled BSDF |
| `ArtRug` | `shader_rug` | 生成随机二维图案，将图像颜色接入地毯基础材质 |

参数说明：

- `bbox=(xmin, xmax, ymin, ymax)` 控制图像布局范围；两个轴的跨度都必须大于 `0.001`。
- `selection` 和额外 `kwargs` 当前不会参与材质生成。
- 两类材质继承 `Text` 的图像生成流程，会创建 Blender image，成本高于纯程序 shader。
- 它们没有 `apply`；生成后使用 `surface.assign_material` 或局部材质赋值接口。

## 推荐用法

确定参数的细织布：

```python
from infinigen.assets.materials.fabric.fine_knit_fabric import shader_material
from infinigen.core import surface

mat = surface.shaderfunc_to_material(
    shader_material,
    _color=(0.18, 0.28, 0.36),
    _roughness=0.75,
    _thread_density_x=220,
    _relative_density_y=0.9,
    _displacement_scale=0.002,
    _map="Object",
)
surface.assign_material(obj, mat)
```

局部天鹅绒软包：

```python
from infinigen.assets.materials import fabric

fabric.Velvet().apply(obj, selection="upholstery")
```

带图案地毯：

```python
from infinigen.assets.materials import art
from infinigen.core import surface

mat = art.ArtRug().generate(bbox=(0, 1.6, 0, 1))
surface.assign_material(rug_obj, mat)
```

## 选择与边界

1. 远景或大批量资产优先使用 `SofaFabric`、`Leather` 或简化 Principled 材质；粗针织、天鹅绒、地毯和图案复合材质的节点数与纹理成本更高。
2. 需要明确配色时优先直接调用 `shader_material`、`shader_lined_fur_base` 或 `shader_fabric`；多数类 wrapper 只提供随机外观。
3. `PlaidFabric`、`SofaFabric`、`ArtFabric` 和 `ArtRug` 应在 UV 准备完成后赋值。更改 UV 后无需重建材质，但外观会随 UV 改变。
4. `ArtFabric` 和 `ArtRug` 用于随机装饰图案，不适合需要可读文字、指定 logo 或精确贴图的资产。
5. 材质不负责软体物理。布料铺盖、窗帘垂坠、靠垫充气和床品褶皱应由对应资产 factory、网格 modifier 或 cloth simulation 完成。
