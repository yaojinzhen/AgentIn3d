# 室内硬表面材质

本文档记录金属、木材、塑料、橡胶、陶瓷、石材和铺装材质的具体类、shader function、参数及调用限制。透明玻璃、黑玻璃、镜面和半透明塑料转到 `glass_screen_emissive_materials.md`，候选池变量转到 `material_assignments.md`。下方接口索引假定材质语义已经由 `query material` 确定，不承担视觉选材决策。

主要源码：

- `infinigen/assets/materials/metal/**`
- `infinigen/assets/materials/wood/**`
- `infinigen/assets/materials/plastic/**`
- `infinigen/assets/materials/ceramic/**`
- `infinigen/assets/materials/utils/common.py`

## 接口索引

| 需求 | 首选接口 | 说明 |
| --- | --- | --- |
| 普通金属、小五金 | `metal.MetalBasic` | 随机金属色和粗糙度，成本较低 |
| 家电外壳、把手、金属腿 | `metal.BrushedMetal` | 可控制颜色、纹理尺度和 seed |
| 镀锌、颗粒或锤纹表面 | `metal.GalvanizedMetal`、`GrainedMetal`、`HammeredMetal` | 纹理更明显；后两者带 shader displacement |
| 黑色或白色家电金属 | `metal.BrushedBlackMetal`、`WhiteMetal` | 固定风格，参数很少 |
| 普通木制家具 | `wood.Wood` | 连续木纹，适合桌腿、柜体和门板 |
| 柜板、书架板 | `wood.WhitePlywood`、`BlackPlywood`、`BlondePlywood` | 白色、黑色或浅色板材 |
| 桌面木材 | `wood.TableWood` | 固定程序木纹，带 displacement |
| 木地板 | `wood.TiledWood`、`wood.HardwoodFloor` | 前者为错缝木板，后者为规则条板 |
| 不透明塑料 | `plastic.PlasticRough` | 参数明确，优先于随机分流的 `Plastic` |
| 随机塑料外观 | `plastic.Plastic` | 在粗糙和半透明 shader 间随机选择 |
| 黑色塑料部件 | `plastic.BlackPlastic` | 适合电视、灯具和小型塑料件 |
| 陶瓷洁具、餐具 | `ceramic.Ceramic` | 带涂层和细微粗糙度变化 |
| 台面、装饰石材 | `ceramic.Marble` | 程序大理石纹理 |
| 墙面或床架包覆 | `ceramic.Plaster` | 依赖 UV，优先使用 `apply` |
| 砖墙 | `ceramic.Brick` | UV 空间砖纹和 displacement |
| 瓷砖或拼花面 | `ceramic.Tile` | 可指定基础 shader、形状和铺设方向 |

## 统一调用协议

这些材质不是 `AssetFactory`。大多数类实现以下接口中的一部分：

```python
generator = MaterialClass()
material = generator.generate(**kwargs)
material = generator(**kwargs)  # __call__ 通常等于 generate
generator.apply(obj, selection=None, **kwargs)
```

| 接口 | 返回值 | 作用 |
| --- | --- | --- |
| `generate(...)` / `generator(...)` | `bpy.types.Material` | 创建材质，但不赋给 object |
| `apply(obj, selection=None, ...)` | 通常为 `None` | 创建材质并整对象或按 face selection 赋值 |
| `MaterialClass.shader` | shader function | 供 `surface.shaderfunc_to_material`、`surface.add_material` 或自定义组合使用 |

材质类自带的 `apply` 多数调用 `infinigen.assets.materials.utils.common.apply`：`selection` 可为 `None`、`tags.Tag`、FACE attribute 名或数组 mask，字符串也支持 `!attribute` 反选。它与 `surface.assign_material` 不是同一实现；若字符串 attribute 不存在，`common.apply` 会捕获错误并把 face material index 置为 `0`，可能导致新材质没有赋到目标面。因此调用前必须确认 selection attribute 存在。已有 material 的赋值规则见 `../function_api/surface_material_ops.md`。

材质内部使用 NumPy 随机采样；需要稳定结果时在 factory seed 或 `FixedSeed` 作用域内创建材质。

推荐的整对象路径：

```python
from infinigen.assets.materials import metal
from infinigen.core import surface

mat = metal.BrushedMetal()(scale=1.0, seed=17)
surface.assign_material(obj, mat)
```

推荐的局部赋值路径：

```python
metal.BrushedMetal().apply(
    obj,
    selection="handle",
    scale=1.0,
    seed=17,
)
```

只有下表明确带 `apply` 的类才能使用第二种路径。其他类应先 `generate()`，再调用 `surface.assign_material`。

## 金属

### 类接口

| 类 | `generate` / `apply` | 用途与边界 |
| --- | --- | --- |
| `MetalBasic` | `generate(selection=None, color_hsv=None, **kwargs)`；`apply(obj, selection=None, **kwargs)` | 通用金属。`generate` 中的 `selection` 和额外 kwargs 不参与生成；`color_hsv` 是 HSV 三元组 |
| `BrushedMetal` | `generate(**kwargs)`；`apply(obj, selection=None, **kwargs)` | 拉丝家电、把手和桌腿；参数完整传给 shader |
| `GalvanizedMetal` | `generate(**kwargs)`；`apply(obj, selection=None, **kwargs)` | 镀锌斑纹；参数完整传给 shader |
| `GrainedMetal` | `generate()`；`apply(obj, selection=None, **kwargs)` | 细颗粒抛光金属并带 displacement；只有 `apply` 可直接接收控制参数 |
| `HammeredMetal` | `generate()`；`apply(obj, selection=None, **kwargs)` | 锤纹金属并带 displacement；只有 `apply` 可直接接收控制参数 |
| `BrushedBlackMetal` | `generate()`；`apply(obj, selection=None, **kwargs)` | 固定深黑各向异性外观；传入 kwargs 不改变 shader |
| `WhiteMetal` | `generate()` | 固定白色拉丝金属；没有 `apply` |
| `Aluminum` | `generate(**kwargs)`；`apply(obj, geo_kwargs=None, shader_kwargs=None, **kwargs)` | 特殊铝材；`apply` 会同时添加未应用的 Geometry Nodes modifier 和材质，不支持 face selection |

### 可控 shader 参数

| Shader function | 参数 | 作用 |
| --- | --- | --- |
| `shader_metal(nw, color_hsv=None, **kwargs)` | `color_hsv` | 金属基色；`None` 时随机采样 |
| `shader_brushed_metal(nw, scale=1.0, base_color_hsv=None, seed=None, **kwargs)` | `scale`、`base_color_hsv`、`seed` | 拉丝密度、HSV 基色和纹理 seed |
| `shader_galvanized_metal(nw, scale=1.0, base_color_hsv=None, seed=None, **kwargs)` | 同上 | 镀锌纹理尺度、颜色和 seed |
| `shader_grained_metal(nw, scale=1.0, base_color_hsv=None, roughness=None, seed=None, **kwargs)` | 增加 `roughness` | `roughness` 是归一化控制值，内部映射到较低的实际粗糙度 |
| `shader_hammered_metal(nw, scale=None, base_color_hsv=None, seed=None, **kwargs)` | `scale`、`base_color_hsv`、`seed` | 锤纹尺度、颜色和 seed；`scale=None` 时随机 |
| `shader_aluminumdisp2tut(nw, rand=False, **input_kwargs)` | `rand` | 是否随机扰动铝纹；其他 `input_kwargs` 当前未读取 |

需要为 `GrainedMetal.generate()` 或 `HammeredMetal.generate()`显式传参时，绕过类的无参 `generate`：

```python
from infinigen.assets.materials.metal.hammered_metal import shader_hammered_metal

mat = surface.shaderfunc_to_material(
    shader_hammered_metal,
    scale=0.9,
    base_color_hsv=(0.58, 0.08, 0.65),
    seed=12,
)
```

`GrainedMetal`、`HammeredMetal`、`Aluminum` 的 displacement 会增加渲染和版本兼容风险。小尺寸物件或远景资产可优先使用 `MetalBasic` 或 `BrushedMetal`。

## 木材与板材

### 类接口

| 类 | `generate` / `apply` | 用途与边界 |
| --- | --- | --- |
| `Wood` | `generate()`；`apply(obj, selection=None, **kwargs)` | 通用连续木纹；`apply` 可传 `color`、`w`、`vertical` |
| `WhitePlywood` | `generate()`；`apply(obj, selection=None, **kwargs)` | 白色柜板；shader kwargs 为 `rgb`、`roughness` |
| `BlackPlywood` | `generate()`；`apply(obj, selection=None, **kwargs)` | 黑色木纹板；支持 `wave_scale`、`dark_scale`、`gray_scale`、`rgb`、`roughness`、`z_axis_texture` |
| `BlondePlywood` | `generate()`；`apply(obj, selection=None, **kwargs)` | 浅色木纹板；支持 `bright_hsv`、`mid_hsv`、`dark_hsv`、`wave_scale`、`roughness`、`z_axis_texture` |
| `TableWood` | `generate()` | 固定桌面木纹，带 shader displacement |
| `TiledWood` | `generate()` | 随机错缝木板；底层 shader 支持 `hscale`、`vscale`、`base_color`、`seed` |
| `HardwoodFloor` | `generate(selection=None, rotation=None)` | 规则条板；`selection` 未使用，`rotation` 为 Euler 三元组 |
| `WoodOld` | `generate()` | 旧木纹；底层 shader 支持 `scale`、`offset`、`rotation` |

`Wood.shader` 是：

```python
shader_wood(nw, color=None, w=None, vertical=False, **kwargs)
```

- `color` 使用 RGBA；`None` 时随机木色。
- `w` 控制 4D 程序纹理 seed；`None` 时随机。
- `vertical=True` 会旋转对象坐标，使木纹方向适合另一主轴。

`WhitePlywood`、`BlackPlywood` 和 `BlondePlywood` 在 `__init__` 中保存了随机 `self.params`，但当前 `generate()` 与 `apply()` 不会自动使用它。要使用这些参数，可调用 `instance.apply(obj, **instance.params)`，或把对应 shader function 传给 `surface.shaderfunc_to_material`。

### `get_shelf_material`

签名：

```python
get_shelf_material(name, **kwargs)
```

| `name` | 候选 |
| --- | --- |
| `"white"` | 白色板材或粗糙塑料 |
| `"black_wood"` | 黑色板材或通用木材 |
| `"wood"` | 浅色板材或通用木材 |
| `"glass"` | 玻璃；细节转到玻璃材质文档 |
| `"metal"` | 五种金属 shader 随机选一 |
| 其他值 | 白板、塑料、黑木或木材的默认混合 |

该函数直接返回 `bpy.types.Material`，适合柜体和书架的语义化随机选材；需要确定材质、颜色或 seed 时直接使用具体类。

```python
from infinigen.assets.materials.wood.plywood import get_shelf_material

frame_mat = get_shelf_material("metal", seed=23)
board_mat = get_shelf_material("wood", vertical=True)
```

## 塑料与橡胶

| 类 | `generate` / `apply` | 参数与建议 |
| --- | --- | --- |
| `PlasticRough` | `generate(**kwargs)`；`apply(obj, selection=None, **kwargs)` | 首选不透明塑料；支持 `scale=1.0`、`base_color` RGBA、`roughness`、`seed`、`clear=False` |
| `Plastic` | `generate(clear=None, color_rgba=None, **kwargs)`；`apply(obj, selection=None, clear=None, **kwargs)` | 根据 `rough` 与 `translucent` 数值大小选择粗糙或半透明 shader；外观不如具体类可控 |
| `BlackPlastic` | `generate(**kwargs)`；`apply(obj, selection=None, **kwargs)` | 随机近黑颜色；`generate` 忽略 kwargs，但 `apply` 传入非空 kwargs 会因 shader 不接收参数而报错 |
| `BumpyRubberFloor` | `generate()`；`apply(obj, selection=None, **kwargs)` | 凸点橡胶地面；底层 shader 支持 `scale`、`base_color`、`seed`，只有 `apply` 可直接传参 |

`Plastic.sample_plastic(clear=None, **kwargs)` 读取 `rough` 和 `translucent` 作为分流分数，不是布尔开关。当前实现没有把 `clear` 传给所选 shader；`Plastic.generate(color_rgba=...)` 的颜色也只会被粗糙塑料分支读取。要求确定的不透明颜色时使用 `PlasticRough`：

```python
plastic.PlasticRough().apply(
    obj,
    base_color=(0.04, 0.06, 0.08, 1.0),
    roughness=0.65,
    seed=7,
)
```

透明或半透明塑料使用 `PlasticTranslucent`，并转到 `glass_screen_emissive_materials.md` 查看透射边界。

## 陶瓷、石材与铺装

| 类 | `generate` / `apply` | 用途与边界 |
| --- | --- | --- |
| `Ceramic` | `generate()`；`apply(obj, selection=None, clear=False, **kwargs)` | 洁具和餐具；`apply` 可控制 `clear`、`roughness_min`、`roughness_max` |
| `Marble` | `generate(**kwargs)`；`apply(obj, selection=None, **kwargs)` | 通用大理石；当前 shader 不读取 kwargs |
| `MarbleRegular` | `generate()` | 规则条带大理石 |
| `MarbleVoronoi` | `generate()` | 高对比 Voronoi 大理石 |
| `Concrete` | `generate()` | 裂纹混凝土；需要参数时直接调用 `shader_concrete` |
| `Plaster` | `generate(plaster_colored=None, **kwargs)`；`apply(obj, selection=None, plaster_colored=None, **kwargs)` | 灰泥；`apply` 会先执行 UV unwrap，优先于单独 `generate` |
| `Brick` | `generate()` | 砖纹；底层 `shader_brick(nw, height=None, **kwargs)` 可控制砖行高度 |
| `Tile` | `generate(selection=None, vertical=False, shader_func=None, scale=None, alternating=None, shape=None, **kwargs)` | 将基础 shader 铺成方形、矩形、六边形、错缝、交叉或复合图案 |
| `VaseCeramic` | `generate(**kwargs)` | 深色高光陶瓷；kwargs 当前未读取 |

`shader_concrete` 的可控参数为：

```python
shader_concrete(
    nw,
    scale=1.0,
    base_color_hsv=None,
    seed=None,
    roughness=None,
    crack_amount=None,
    crack_scale=None,
    snake_crack=None,
    **kwargs,
)
```

`base_color_hsv` 是 HSV 三元组；`crack_amount` 控制裂纹量，`crack_scale` 控制裂纹尺度，`snake_crack` 控制蜿蜒特征。`Concrete.generate()` 不接收这些参数，需通过 `surface.shaderfunc_to_material(shader_concrete, ...)` 创建可控材质。

### `Tile.generate`

`shape` 可取 `"square"`、`"rectangle"`、`"hexagon"`、`"staggered"`、`"crossed"`、`"composite"`；`None` 时随机。`vertical=True` 用于墙面方向，`scale` 越大图案越密，`alternating` 控制不同砖块是否使用不同随机种子。

必须使用关键字传递 `shader_func` 和 `shape`，因为前两个位置参数是未使用的 `selection` 与 `vertical`：

```python
from infinigen.assets.materials.ceramic import tile
from infinigen.assets.materials.wood.wood import shader_wood

mat = tile.Tile().generate(
    shader_func=shader_wood,
    shape="staggered",
    scale=1.2,
    vertical=False,
    alternating=True,
)
surface.assign_material(obj, mat)
```

不指定 `shader_func` 时，候选还包含 bone、dirt、stone 和 cobblestone 等非室内基础 shader。生成室内材质时应显式传入 `shader_wood`、`shader_ceramic` 或 `shader_marble`。

## 已知陷阱

| 情况 | 处理 |
| --- | --- |
| 把材质生成器实例直接传给 `SetMaterial` | 先调用 `generator()` 或 `generate()` 得到 `bpy.types.Material` |
| 对没有 `apply` 的类调用 `.apply(...)` | 先生成 material，再用 `surface.assign_material` |
| 用位置参数调用 `Tile.generate(shader_func, shape)` | 改为 `shader_func=...`、`shape=...` |
| 使用 `CompositeWoodTile`、`CrossedWoodTile`、`HexagonWoodTile`、`SquareWoodTile`、`StaggeredWoodTile` 或 `NonWoodTile` | 这些 wrapper 当前把参数按错误位置传给 `Tile.generate`；新代码直接调用 `Tile.generate` |
| 期望 `WhitePlywood().params` 自动生效 | 显式把 params 传给 `apply` 或对应 shader function |
| 对 `GrainedMetal.generate()` 或 `HammeredMetal.generate()` 传控制参数 | 改用 `.apply(..., **kwargs)`，或直接用对应 shader function 创建 material |
| 对 `Concrete.generate()` 传控制参数 | `Concrete` 没有 `apply`；直接用 `surface.shaderfunc_to_material(shader_concrete, **kwargs)` |
| 在没有稳定随机上下文时重复创建材质 | 在 factory seed / `FixedSeed` 内创建，必要时显式传 `seed` |
| 用本文档处理玻璃、镜面或透光塑料 | 转到 `glass_screen_emissive_materials.md` |

## 相关文档

- 材质创建和局部赋值：`../function_api/surface_material_ops.md`
- Shader 节点接口：`../node_api/README.md`
- Geometry Nodes 材质节点：`../node_api/geometry_nodes/material_nodes.md`
- 按资产语义选材：`material_assignments.md`
- 玻璃、镜面、屏幕和发光：`glass_screen_emissive_materials.md`
