# 玻璃、屏幕与发光材质

本文档记录透明玻璃、体积着色玻璃、深色反射面、镜面、半透明塑料、灯罩、灯泡外壳和发光屏幕材质的具体类、shader function、参数及调用限制。它们对几何厚度、坐标、背板和渲染器的要求不同；先由 `query material` 确定视觉语义，再使用本页接口。

主要源码：

- `infinigen/assets/materials/ceramic/glass.py`
- `infinigen/assets/materials/ceramic/glass_volume.py`
- `infinigen/assets/materials/ceramic/vase.py`
- `infinigen/assets/materials/metal/appliance.py`
- `infinigen/assets/materials/metal/mirror.py`
- `infinigen/assets/materials/plastic/plastic_translucent.py`
- `infinigen/assets/materials/lamp_shaders.py`
- `infinigen/assets/materials/text.py`

## 接口索引

| 需求 | 首选接口 | 关键区别 |
| --- | --- | --- |
| 杯子、玻璃门、透明板 | `ceramic.Glass` | Glass BSDF 表面；无体积吸收 |
| 有厚度的彩色玻璃 | `ceramic.GlassVolume` | Principled transmission + Volume Absorption |
| 随机浅色装饰玻璃 | `ceramic.ColoredGlass` | 随机颜色和粗糙度；不可传参 |
| 关闭的家电屏幕、深色玻璃面板 | `metal.BlackGlass` | 深色 Glossy 表面，不透明也不折射 |
| 镜子 | `metal.Mirror` | 白色、零粗糙度 Glossy 表面 |
| 半透明塑料外壳 | `plastic.PlasticTranslucent` | Glass 与 Glossy 的 Fresnel 混合 |
| 半透灯罩 | `lamp_shaders.LampShade` | 根据 ray 类型混合两种 Principled 外观 |
| 不自发光的灯泡壳 | `shader_lamp_bulb_nonemissive` | Transparent/Translucent 混合，不含 Emission |
| 有随机图案的点亮屏幕 | `text.TextNoBarcode` 或 `text.TextGeneral` | 生成并打包图像，使用 Principled emission |
| 纯色发光面、指示灯、灯丝 | 自定义 emission shader function | 使用 `Nodes.Emission` 或 Principled emission 输入 |

## 调用协议

材质类遵循以下接口中的一部分：

```python
generator = MaterialClass()
material = generator.generate(**kwargs)
material = generator(**kwargs)
generator.apply(obj, selection=None, **kwargs)
```

`generate()` 返回 `bpy.types.Material`，不会自动赋给 object。只有明确实现了 `apply` 的类才能直接处理整对象或 face selection；其余类先生成 material，再使用 `surface.assign_material`。这些类的 `apply` 使用 `materials.utils.common.apply`；字符串 selection attribute 不存在时可能静默回到 material slot `0`，因此必须预先确认 attribute。已有 material 的赋值规则见 `../function_api/surface_material_ops.md`。

```python
from infinigen.assets.materials import ceramic
from infinigen.core import surface

glass_mat = ceramic.Glass()()
surface.assign_material(glass_obj, glass_mat)
```

## 表面玻璃

### `Glass`

接口：

```python
Glass.generate(color=(1, 1, 1, 1), **kwargs)
Glass.apply(obj, selection=None, clear=False, **kwargs)

shader_glass(nw, color=None, is_window=False, **kwargs)
get_glass_color(clear)
```

行为：

- `is_window=False` 创建粗糙度 `0.02`、IOR `1.5` 的 Glass BSDF。
- `is_window=True` 把 IOR 改为 `1.0`，并根据 `LightPath.Is Camera Ray` 在 Transparent 与 Glass 之间混合，用于单层窗口平面的近似处理。
- `generate()` 返回 material；`apply()` 支持局部 selection。

当前实现边界：

- `shader_glass` 计算或接收了 `color`，但没有把它连接到 Glass BSDF，因此 `color` 和 `clear` 当前不会改变可见颜色。
- `Glass.generate()` 只把 `color` 传给 shader，额外 kwargs 不会继续传递；`Glass().generate(is_window=True)` 不会启用窗口路径。
- 需要生成窗口材质时，直接使用 shader function：

```python
from infinigen.assets.materials.ceramic.glass import shader_glass

window_mat = surface.shaderfunc_to_material(
    shader_glass,
    is_window=True,
    name="window_glass",
)
```

`is_window=True` 是对单层平面的项目级近似，不等价于有厚度实体玻璃。杯子、瓶子和厚玻璃板应使用闭合 mesh、向外法线和实际厚度。

### `ColoredGlass`

接口：

```python
ColoredGlass.generate()
shader_colored_glass(nw)
```

该材质使用 Glass BSDF，随机生成低饱和度颜色和 `0.05-0.2` 粗糙度。它没有 `apply`，也不能指定颜色；需要确定颜色时应自定义 Glass BSDF，不能依赖 `Glass(color=...)`。

## 体积着色玻璃

### `GlassVolume`

接口：

```python
GlassVolume.generate(**kwargs)
shader_glass_volume(nw, color=None, density=100.0, **kwargs)
```

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `color` | Volume Absorption 的 RGBA 颜色 | `None` 时随机选择透明或高饱和颜色 |
| `density` | 吸收密度 | 与几何厚度共同决定深浅；从低值试起 |
| `**kwargs` | 当前 shader 不读取 | 不要用于猜测额外控制项 |

材质表面使用 `Transmission Weight=1`、`Roughness=0` 的 Principled BSDF，体积端使用 Volume Absorption。它适合有厚度的桌面、瓶身或装饰玻璃，不适合单层 plane。

```python
volume_mat = ceramic.GlassVolume()(
    color=(0.18, 0.55, 0.72, 1.0),
    density=8.0,
)
surface.assign_material(glass_body, volume_mat)
```

默认 `density=100` 对较厚物体可能过深。物体尺度或厚度变化时应同步调整 density；重叠壳体、未闭合 mesh 和反向法线会产生不稳定的吸收或折射结果。

## 深色面板与镜面

| 类 | 接口 | 实际外观 |
| --- | --- | --- |
| `BlackGlass` | `generate()`；`apply(obj, selection=None, **kwargs)` | 近黑色、粗糙度 `0.2` 的 Glossy BSDF；`apply` 不能接收非空 kwargs |
| `Mirror` | `generate()`；`apply(obj, selection=None, **kwargs)` | 白色、粗糙度 `0` 的 Glossy BSDF |

两个类都没有 transmission，不应当作可透视玻璃：

- `BlackGlass` 适合关闭状态的微波炉/烤箱面板、黑色高光饰板或无图案屏幕。
- `Mirror` 适合镜面与高反射装饰件；效果依赖场景中存在可反射内容。
- `shader_black_glass` 不接受 kwargs，因此向 `BlackGlass.apply` 传入额外参数会报错；`shader_mirror` 接受但忽略 kwargs。需要可控粗糙度或颜色时，自定义 Glossy/Principled shader。

```python
from infinigen.assets.materials import metal

metal.BlackGlass().apply(obj, selection="screen")
mirror_mat = metal.Mirror()()
```

## 半透明塑料与灯罩

### `PlasticTranslucent`

接口：

```python
PlasticTranslucent.generate(**kwargs)
PlasticTranslucent.apply(obj, selection=None, **kwargs)
shader_translucent_plastic(nw, clear=False, **input_kwargs)
```

`clear=False` 随机生成彩色塑料，`clear=True` 生成低饱和灰色塑料。shader 随机采样 IOR `1.2-1.6`，并通过 Layer Weight 的 Fresnel 在 Glass 与 Glossy 之间混合。除 `clear` 外的 `input_kwargs` 当前不读取。

```python
from infinigen.assets.materials import plastic

plastic.PlasticTranslucent().apply(
    obj,
    selection="cover",
    clear=True,
)
```

该材质表达半透明塑料外观，不使用 Volume Absorption。需要明确透明玻璃时使用 `Glass`，需要不透明磨砂塑料时使用 `PlasticRough`。

### `LampShade`

接口：

```python
LampShade.generate(selection=None, **kwargs)
LampShade.apply(obj, selection=None, **kwargs)
shader_lampshade(nw)
```

`shader_lampshade` 使用对象随机值生成暖灰颜色，并根据 `LightPath.Is Camera Ray` 混合两个 Principled BSDF。相机 ray 看到粗糙不透明表面；其他 ray 使用带少量 transmission 和 subsurface 的表面。

边界：

- `generate` 中的 `selection` 未使用；`apply` 的 `selection` 用于局部赋值。
- shader function 不接收参数。虽然类签名包含 `**kwargs`，传入非空 kwargs 会导致调用失败。
- 该材质不会创建真实灯光，也没有 emission。

```python
from infinigen.assets.materials.lamp_shaders import LampShade

LampShade().apply(shade_obj)
```

### `shader_lamp_bulb_nonemissive`

签名：

```python
shader_lamp_bulb_nonemissive(nw)
```

该函数根据 ray 类型混合 Transparent 与 Translucent BSDF：相机 ray 使用 Translucent，其他 ray 使用 Transparent。它只表现灯泡外壳，不包含 `Nodes.Emission`，也没有对应材质类：

```python
from infinigen.assets.materials.lamp_shaders import shader_lamp_bulb_nonemissive

bulb_shell_mat = surface.shaderfunc_to_material(
    shader_lamp_bulb_nonemissive,
    name="bulb_shell",
)
```

## 图案屏幕

`text.py` 会用 Matplotlib/PIL 生成随机图案，将图像打包到 Blender，并通过 UV Image Texture 构建 Principled 材质。`emission > 0` 时，图像颜色连接到 `Emission Color`，基础表面改为深色。

| 接口 | 参数 | 说明 |
| --- | --- | --- |
| `Text(has_barcode=True, emission=0)` | `has_barcode`、`emission` | 创建可配置生成器 |
| `Text.generate(selection=None, bbox=(0, 1, 0, 1), **kwargs)` | `bbox` | `selection` 未使用；返回 material |
| `TextGeneral.generate(selection=None, bbox=(0, 1, 0, 1), has_barcode=True, emission=0, **kwargs)` | 全部配置一次传入 | 通用入口 |
| `TextNoBarcode.generate(selection=None, bbox=(0, 1, 0, 1), emission=0, **kwargs)` | 禁止条码 | 更适合电视和显示面板 |

`bbox=(xmin, xmax, ymin, ymax)` 的两个跨度都必须大于 `0.001`。目标面需要有效 UV；这些类没有 `apply`，应生成后按 screen face selection 赋值。局部赋值前，object 必须已有基础材质。

```python
from infinigen.assets.materials import text

screen_mat = text.TextNoBarcode().generate(
    bbox=(0.0, 1.0, 0.0, 0.5625),
    emission=2.5,
)
surface.assign_material(obj, screen_mat, selection="screen")
```

该路径会创建并打包图像，比纯色 shader 更重。用户只要求关闭屏幕时用 `BlackGlass`；只要求纯色亮屏、指示灯或灯丝时使用下面的最小 emission shader。

## 最小发光材质

Infinigen 没有与上述灯泡 helper 对应的通用发光材质类。生成代码可定义小型 shader function：

```python
from infinigen.core import surface
from infinigen.core.nodes.node_wrangler import Nodes, NodeWrangler


def shader_emissive(
    nw: NodeWrangler,
    color=(1.0, 0.55, 0.18, 1.0),
    strength=4.0,
):
    emission = nw.new_node(
        Nodes.Emission,
        input_kwargs={"Color": color, "Strength": strength},
    )
    nw.new_node(
        Nodes.MaterialOutput,
        input_kwargs={"Surface": emission},
    )


emissive_mat = surface.shaderfunc_to_material(
    shader_emissive,
    color=(1.0, 0.75, 0.35, 1.0),
    strength=5.0,
)
```

弱发光面板也可使用 Principled BSDF 的 `Emission Color` 和 `Emission Strength`。发光材质主要控制物体外观；是否有效照亮场景取决于渲染器、采样、发光面积和全局设置。需要稳定的灯具照明时，由场景层创建 Blender light；`infinigen/assets/lighting/indoor_lights.py` 的 `PointLampFactory` 是参考实现，不属于材质 API。

## 已知陷阱

| 情况 | 处理 |
| --- | --- |
| `Glass(color=...)` 没有颜色变化 | 当前 `shader_glass` 未把 color 连接到 Glass BSDF；改写 shader 或使用 `ColoredGlass` |
| 向 `Glass.apply` 传 `color=...` | 该方法已经把随机 color 作为位置参数传入 shader，会造成重复参数；不要传 color |
| `Glass().generate(is_window=True)` 没有效果 | 类的 `generate` 不转发 kwargs；直接用 `shader_glass` 创建 material |
| 把 `BlackGlass` 当作透明玻璃 | 它是深色 Glossy 表面；需要透视时使用 `Glass` |
| 在单层 plane 上使用 `GlassVolume` | 改用闭合、有厚度的 mesh，或使用窗口近似 |
| `LampShade().generate(color=...)` 报错 | `shader_lampshade` 无参数；不要传 kwargs |
| 期望 `shader_lamp_bulb_nonemissive` 发光 | 它只创建灯泡壳；另建 emission 材质或场景灯光 |
| 点亮屏幕没有图案或方向错误 | 先给目标面生成正确 UV，并检查传入的 `bbox` |
| 发光材质很亮却没有可靠照明 | 使用场景 light 承担照明，材质只负责可见发光外观 |

## 相关文档

- 材质创建与局部赋值：`../function_api/surface_material_ops.md`
- Glass、Glossy、Transparent 和 Translucent 节点：`../node_api/shader_nodes/surface_bsdf_nodes.md`
- Principled transmission 与 emission：`../node_api/shader_nodes/principled_bsdf_node.md`
- Emission 和 Volume 节点：`../node_api/shader_nodes/emission_volume_hair_nodes.md`
- 金属、木材、陶瓷和不透明塑料：`indoor_hard_surface_materials.md`
- 按资产语义选材：`material_assignments.md`
