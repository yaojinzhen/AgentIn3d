# 语义材质候选池

本文档记录 `infinigen.assets.composition.material_assignments` 的候选池变量、权重、别名关系、采样协议和已知源码缺陷。候选池根据“桌面、把手、墙面、软包”等部件语义返回材质生成器；视觉语义由材质卡确定，选中具体生成器后再转到对应 Material API 文档查询参数。

源码：`infinigen/assets/composition/material_assignments.py`

## 核心用法

候选池的元素是 `(generator_class, weight)`，不是已经创建的 material：

```python
from infinigen.assets.composition import material_assignments
from infinigen.core import surface
from infinigen.core.util.random import weighted_sample

generator_cls = weighted_sample(material_assignments.table_top)
material = generator_cls()()
surface.assign_material(obj, material)
```

```python
weighted_sample(reg)
```

| 参数/返回值 | 说明 |
| --- | --- |
| `reg` | 非空的 `(candidate, weight)` 序列；权重应为非负数且总和大于 0 |
| 返回值 | 按归一化权重采样出的 candidate；本文件中通常是材质生成器类 |

`weighted_sample` 只完成一次选择。通常还需第一次 `()` 实例化生成器，第二次 `()` 调用其 `generate`。不要把 `weighted_sample(pool)` 的返回值直接传给 `surface.assign_material`。

需要可复现时，在 `FixedSeed` 作用域内完成“选择 + 材质生成”，因为两步都可能使用 NumPy 随机状态。

## 选择原则

1. 用户只给出资产或部件语义时，使用本页最具体的候选池。
2. 用户已明确指定金属、木材、皮革等表面类型时，直接选择具体材质类，不再随机采样跨材质族候选池。
3. 先采样 class，再生成一次 material；同一对象的同类部件应复用 material，避免每个小零件产生不同随机外观。
4. 候选池是模块级可变对象。生成代码不要原地追加、删除或修改权重；需要定制时先复制。

下表使用 `Class(weight)` 表示源码权重；`A + B` 表示集合拼接，重复 class 的权重会累加为更高概率。

## 基础材质族

| 候选池 | 主要候选 | 用途与边界 |
| --- | --- | --- |
| `woods` | `Wood(1)`；三种 `Plywood(各0.1)` | 普通木制家具；连续木纹占主导 |
| `wood_tiles` | 六种木质 tile/floor class，各 `1` | 木地板与规则拼板；部分 tile wrapper 存在调用问题，见硬表面文档 |
| `metals` | `MetalBasic(3)`、`BrushedMetal(2)`、镀锌/颗粒/锤纹、黑色金属 | 通用金属部件；普通和拉丝金属概率最高 |
| `metal_neutral` | `MetalBasic(1)` | 名称暗示中性色，但源码没有覆盖颜色，仍可能生成彩色金属 |
| `fabrics` | 粗针织、细针织、沙发布各 `1`；`Leather(0.3)` | 通用织物；`PlaidFabric` 在源码中被注释，不会被采样 |
| `plastics` | `Plastic`、`PlasticRough`、`PlasticTranslucent` 各 `1` | 允许不透明与半透明塑料混合 |
| `hard_materials` | 金属、木材、胶合板和塑料 | 不指定具体硬表面类型时使用；候选跨度较大 |
| `metal_plastic` | `MetalBasic` + 三种塑料 | 小型五金、外壳和功能部件 |
| `glasses` | `Glass(1)` | 透明玻璃；`ColoredGlass` 当前被注释 |
| `ceramics` | `Ceramic(1)` | 陶瓷器皿和洁具 |
| `marble` | `Marble(1)`；`MarbleRegular(0.2)`；`MarbleVoronoi(0.2)` | 石材台面和装饰面 |
| `mirrors` | `Mirror(1)` | 镜面 |
| `white_metal` | `WhiteMetal(1)` | 固定白色金属 |
| `decorative_metal` | 拉丝、镀锌、颗粒、锤纹金属各 `1` | 需要明显程序纹理的装饰五金 |

具体接口：

- 金属、木材、塑料、陶瓷和石材：`indoor_hard_surface_materials.md`
- 织物和皮革：`fabric_and_soft_materials.md`
- 玻璃、镜面和半透明塑料：`glass_screen_emissive_materials.md`

## 家具与家电

| 候选池 | 候选摘要 | 推荐语义 |
| --- | --- | --- |
| `shelf_board` | 金属 + 塑料 + 玻璃 + 木材；三种胶合板权重各 `10` | 柜体层板、书架板；胶合板显著占优 |
| `kitchen_appliance_hard` | `metals` + `PlasticRough(2)` | 冰箱、烤箱、洗碗机硬外壳 |
| `appliance_front_maybeglass` | `metals` + `BlackGlass(4)` + `Glass(10)` | 可能为金属或玻璃的家电正面 |
| `appliance_front_glass` | `BlackGlass(2)` + `Glass(10)` | 明确的家电玻璃面板 |
| `appliance_handle` | `metals` + `PlasticRough(1)` + `Wood(3)` + `WhiteMetal(2)` | 家电把手 |
| `fridge_shelf` | `Glass(1)` + `WhiteMetal(1)` | 冰箱层板和支撑件 |
| `bathroom_touchsurface` | `Ceramic(1)`；拉丝/普通金属各 `0.1` | 浴室洁具接触面 |
| `furniture_leg` | `decorative_metal` + 木材/玻璃/塑料；黑色金属和黑胶合板各 `3` | 桌椅腿和支撑 |
| `furniture_hard_surface` | `PlasticRough(1)` + `Wood(1)` | 简单家具硬表面 |
| `table_top` | 大理石、拼板木、普通木、体积玻璃各 `1`；粗糙塑料 `0.5` | 桌面；这是模块中后一次定义的有效集合 |
| `tableware` | 陶瓷、玻璃、塑料、金属、木材各 `1` | 杯盘餐具；用户指定材质时应直接选具体类 |
| `officechair_seat` | 皮革、木材、粗糙塑料、体积玻璃各 `1` | 办公椅座面候选较宽；软包要求明确时直接用皮革或织物 |
| `bedframe` | `decorative_metal` + `Wood(7)` + `Plaster(2)` | 床架，木材占主导 |
| `large_seat_fabric` | `Velvet(0.3)`、`SofaFabric(0.5)`、`Leather(0.2)` | 沙发和大型软包座椅 |

## 软装与装饰

| 候选池 | 候选摘要 | 推荐语义 |
| --- | --- | --- |
| `abstract_art` | `Art(1)` + `DarkArt(0.5)` | 抽象画、装饰画 |
| `blanket` | `fabrics` + `ArtFabric(3)` | 毯子；图案织物占较高概率 |
| `pants` | `fabrics` + `ArtFabric(5)` | 裤装材质 |
| `towel` | `fabrics` + `ArtRug(2)` + `Rug(5)` | 毛巾和粗纤维织物 |
| `lampshade` | `fabrics` + `LampShade(5)` | 灯罩；专用 LampShade 占主导 |
| `curtain` | 细针织、木材、塑料、玻璃、LampShade | 窗帘及其相关部件的宽候选池；纯布帘优先直接选 `FineKnitFabric` |
| `plain_fabric` | `SofaFabric(1)` | 无图案布面 |
| `rug_fabric` | `fabrics` + `Rug(7)` + `ArtRug(5)`，粗针织累计权重 `2` | 地毯 |
| `graphicdesign` | `Text(1)` + `BasicBSDF(0.1)` | 包装、书封、标签等图像材质 |
| `decorative_hard` | `decorative_metal` + 陶瓷、彩色/体积玻璃、大理石 | 花瓶、花盆和装饰硬物 |
| `cup` | `decorative_hard` + 普通金属、塑料、半透明塑料、玻璃 | 杯子和小型容器 |
| `jar` | 玻璃权重 `8`，另含塑料、陶瓷、彩色/体积玻璃和大理石 | 罐体，玻璃占主导 |
| `frame` | `decorative_metal + woods` | 画框、镜框和结构框 |

`Art` 和 `DarkArt` 继承 `Text.generate(selection=None, bbox=(0, 1, 0, 1), **kwargs)`，依赖有效 UV 且没有 `apply`；`DarkArt` 会额外压暗随机图案。`graphicdesign` 中的 `Text` 参数见 `glass_screen_emissive_materials.md`，`BasicBSDF` 只适合作为低成本占位材质。

`lid` 是 `cup` 的同一列表对象，不是独立副本。

## 楼梯与建筑表面

| 候选池 | 候选摘要 | 推荐语义 |
| --- | --- | --- |
| `step` | 织物 + 木材 + 大理石 + 塑料 | 宽泛台阶材质 |
| `rail` | `step` 的同一对象 | 栏杆候选；若要求金属栏杆应直接使用 `metals` |
| `tread` | 木材 + 金属 + 玻璃 | 踏步面 |
| `side` | `rail + metals` | 楼梯侧面 |
| `handrail` | 木材 + 金属 + 织物 | 扶手 |
| `post` | `handrail` 的同一对象 | 立柱 |
| `wall` | `Plaster(2)` + `Tile(1)` | 普通室内墙 |
| `kitchen_wall` | `Plaster(5)` + `Tile(2)` | 厨房墙面 |
| `garage_wall`、`warehouse_wall` | `Concrete(5)` + `Brick(1)` + `Plaster(3)` | 车库和仓库墙 |
| `utility_wall` | `Concrete(1)` + `Brick(2)` + `Plaster(5)` | 设备间墙 |
| `balcony_wall` | `Brick(1)` + `Plaster(5)` | 阳台墙 |
| `bathroom_wall` | `Tile(5)` | 浴室墙 |
| `floor` | 六种木地板 + `Tile(4)` + `Rug(1)` | 普通室内地面 |
| `garage_floor`、`warehouse_floor` | `Concrete(1)` | 车库和仓库地面 |
| `bathroom_floor` | `Tile(1)` | 浴室地面 |
| `balcony_floor` | `bathroom_floor` 的同一对象 | 阳台地面 |
| `office_floor` | 六种木地板 + `Rug(1)` | 办公室地面 |
| `ceiling` | `Plaster(1)` | 普通天花板 |
| `warehouse_ceiling`、`garage_ceiling` | `Concrete(1)` | 仓库和车库天花板 |

## 已知不可直接使用的集合

| 集合/行为 | 问题 | 处理 |
| --- | --- | --- |
| `decorative_fabric` | 尾随逗号使其成为“包含一个 list 的 tuple”，不满足 `(candidate, weight)` 序列协议 | 使用 `list(material_assignments.fabrics) + [(art.ArtFabric, 5.0)]` |
| `utility_floor` | 第三个 candidate 是 `ceramic.tile` 模块，不是可调用的 `ceramic.Tile` 类 | 复制集合并替换为 `(ceramic.Tile, 1.0)` |
| `table_top` 的较早定义 | 同一模块后面再次赋值，前一版本已被覆盖 | 只使用运行时 `material_assignments.table_top` |
| `metal_neutral` | TODO 注释说明应限制中性色，但当前只是 `MetalBasic` | 需要中性色时直接选择固定黑/白金属或显式 shader 参数 |
| `wood_tiles` 中部分 wrapper | 若干 tile wrapper 的参数转发与 `Tile.generate` 不一致 | 按硬表面文档选择已验证类或直接调用 `Tile.generate` |

自然地形、土壤、植物、生物和流体候选池也位于同一源码文件，但不属于室内单体资产的 Material API；不要为生成室内物体而读取或复制这些集合。

## 磨损开关

`wear_tear = [Scratches, EdgeWear]` 是普通 class 列表，`wear_tear_prob = [0.5, 0.5]` 是两个效果各自独立的启用概率，不是供 `weighted_sample` 使用的权重。已有资产分别采样两个 Bernoulli 开关，因此同一对象可能不应用、只应用一种或同时应用两种效果。

`Scratches` wrapper 当前没有把生成的 displacement 连接到 Material Output。新代码应按 `wear_tear_materials.md` 使用修正 helper，或只启用 `EdgeWear`。

## 定制候选池

使用新列表保留全局集合：

```python
from infinigen.assets.composition import material_assignments
from infinigen.assets.materials import wood
from infinigen.core.util.random import weighted_sample

cabinet_pool = list(material_assignments.woods)
cabinet_pool += [(wood.BlackPlywood, 3.0)]

generator_cls = weighted_sample(cabinet_pool)
cabinet_mat = generator_cls()()
```

如果用户要求明确的黑色柜板，不要通过增加权重近似满足；应直接调用 `wood.BlackPlywood()()`。
