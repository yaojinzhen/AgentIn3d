# 可复用资产部件 Helper

本文档记录 `infinigen/assets/objects/**` 中适合跨资产复用的 Geometry Nodes 部件，并对紧密耦合完整 Factory、关节或特定装配的相关接口给出所有权分类。它们的稳定性和复用范围不同，但不会因低频或不适合单体静态资产而从接口参考中消失。

源码依据：

- `infinigen/assets/objects/tables/table_top.py`
- `infinigen/assets/objects/tables/table_utils.py`
- `infinigen/assets/objects/tables/legs/straight.py`
- `infinigen/assets/objects/tables/legs/single_stand.py`
- `infinigen/assets/objects/tables/legs/square.py`
- `infinigen/assets/objects/elements/doors/bar_handle.py`
- `infinigen/assets/objects/lamp/lamp.py`

## 使用边界

同时满足以下条件的 helper 作为本页的主要可复用接口：

1. 输出独立的静态几何，不要求场景约束、相机、仿真或导出上下文。
2. 输入通过 Python 构建参数或明确的 nodegroup socket 给出。
3. 部件概念能用于多个资产，而不是某个完整 factory 的私有装配步骤。
4. 复用比用 primitive 重新建模明显更简单。

具体资产 factory、完整桌架/灯具装配和带关节元数据的部件仍由对象卡、仿真层或精确符号查询负责；本页在后文保留其分类和边界。若只需要规则盒体、圆柱或简单把手，优先使用 `blender_primitive_objects.md`，不要仅因为已有 nodegroup 就增加依赖。

## 装饰器与两类参数

这些函数均由 `@node_utils.to_nodegroup(...)` 装饰。源码中的 authoring 签名包含 `nw`，实际调用装饰后的函数时不传 `nw`：

```python
# 源码 authoring 签名
def nodegroup_generate_table_top(nw: NodeWrangler): ...

# generated code 的运行时调用
group = nodegroup_generate_table_top()
```

参数分为两类：

| 类型 | 传入位置 | 生效时机 |
| --- | --- | --- |
| Python 构建参数 | `nodegroup_generate_leg_straight(**kwargs)` | 创建 nodegroup 时决定其内部结构 |
| nodegroup socket | `nw.new_node(group.name, input_kwargs={...})` | 实例化该 group node 时设置尺寸、材质等值 |

不要把 socket 名传给 Python 函数，也不要把 Python 构建参数写入 `input_kwargs`。

## 推荐导入

```python
from infinigen.assets.objects.elements.doors.bar_handle import (
    nodegroup_beveled_cylinder,
)
from infinigen.assets.objects.lamp.lamp import (
    nodegroup_bulb_rack,
    nodegroup_lamp_head,
)
from infinigen.assets.objects.tables.legs.single_stand import (
    nodegroup_generate_single_stand,
)
from infinigen.assets.objects.tables.legs.square import nodegroup_generate_leg_square
from infinigen.assets.objects.tables.legs.straight import (
    nodegroup_generate_leg_straight,
)
from infinigen.assets.objects.tables.table_top import nodegroup_generate_table_top
from infinigen.assets.objects.tables.table_utils import (
    nodegroup_align_bottom_to_floor,
    nodegroup_n_gon_cylinder,
    nodegroup_n_gon_profile,
)
```

## 接口索引

| 建模目标 | 推荐接口 | 复用等级 |
| --- | --- | --- |
| 圆形、圆角矩形或多边形桌面/板件 | `nodegroup_generate_table_top` | 默认推荐 |
| 将任意 node geometry 的最低 Z 对齐到 0 | `nodegroup_align_bottom_to_floor` | 默认推荐 |
| 生成圆形、椭圆或圆角多边形截面曲线 | `nodegroup_n_gon_profile` | 低层组合 |
| 沿 Z 生成带半径变化的柱体 | `nodegroup_n_gon_cylinder` | 低层组合 |
| 四腿式渐变直桌腿 | `nodegroup_generate_leg_straight` | 条件复用 |
| 中柱式桌腿 | `nodegroup_generate_single_stand` | 条件复用 |
| U 形或闭合框式桌腿 | `nodegroup_generate_leg_square` | 条件复用 |
| 圆角矩形截面的直杆把手 | `nodegroup_beveled_cylinder` | 条件复用 |
| 灯罩支架或包含灯泡的完整灯头 | `nodegroup_bulb_rack` / `nodegroup_lamp_head` | 条件复用 |

## 桌面与板件

### `nodegroup_generate_table_top`

运行时签名：

```python
nodegroup_generate_table_top() -> bpy.types.GeometryNodeTree
```

Socket：

| 名称 | 类型 | 默认值 | 作用与建议 |
| --- | --- | --- | --- |
| `Thickness` | Float | `0.5` | Z 向厚度；家具桌面常从 `0.02` 到 `0.12` 起步 |
| `N-gon` | Int | `0` | 截面边数；`4` 为矩形，较大值形成圆形；不要依赖默认 `0` |
| `Profile Width` | Float | `0.5` | XY 主宽度 |
| `Aspect Ratio` | Float | `0.5` | 次轴宽度相对主宽度的比例；正值 |
| `Fillet Ratio` | Float | `0.2` | 平面轮廓圆角相对宽度的比例；从 `0` 到 `0.25` 起步 |
| `Fillet Radius Vertical` | Float | `0.0` | 上下边缘的竖向圆角；应小于约一半厚度 |

输出：

| 名称 | 类型 | 用途 |
| --- | --- | --- |
| `Geometry` | Geometry | 完整实体桌面，中心大致位于 local Z=0 |
| `Curve` | Geometry | 桌面 XY 轮廓，可用于桌腿 anchor 或其他派生结构 |

行为：使用 `nodegroup_n_gon_cylinder` 生成主体，再构造上下边缘圆角，并标记上下盖面。它适合桌面、台面和规则柜体板件；不负责材质、支撑结构或 world placement。

```python
table_top = nw.new_node(
    nodegroup_generate_table_top().name,
    input_kwargs={
        "Thickness": 0.055,
        "N-gon": 4,
        "Profile Width": 1.4,
        "Aspect Ratio": 0.55,
        "Fillet Ratio": 0.08,
        "Fillet Radius Vertical": 0.012,
    },
)
```

每次调用都会新建 nodegroup，因为源码设置了 `singleton=False`。一个资产构建过程中应先保存返回的 group，再复用其 `name`。

## 低层轮廓与落地对齐

### `nodegroup_n_gon_profile`

```python
nodegroup_n_gon_profile() -> bpy.types.GeometryNodeTree
```

Socket：`Profile N-gon`、`Profile Width`、`Profile Aspect Ratio`、`Profile Fillet Ratio`；输出为 `Output` 曲线。它只生成 XY 截面，不生成实体。

- `Profile N-gon=4` 适合圆角矩形。
- 较大的边数适合近似圆形或椭圆。
- `Profile Aspect Ratio` 控制 Y/X 比例。
- `Profile Fillet Ratio` 是相对值，不是绝对 Blender 单位。

### `nodegroup_n_gon_cylinder`

```python
nodegroup_n_gon_cylinder() -> bpy.types.GeometryNodeTree
```

主要 Socket：

| 名称 | 作用 |
| --- | --- |
| `Radius Curve` | 控制柱体沿高度变化的半径曲线；不能省略 |
| `Height` | 从 local Z=0 向负 Z 延伸的高度 |
| `N-gon` | 截面边数 |
| `Profile Width` / `Aspect Ratio` / `Fillet Ratio` | 截面尺寸和圆角 |
| `Profile Resolution` / `Resolution` | 截面与高度方向采样数；生成资产时避免无条件使用数百级分辨率 |

输出为 `Mesh`、`Profile Curve` 和 `Caps`。优先使用上层桌面或桌腿接口；只有需要自定义半径曲线、轮廓输出或盖面选择时才直接调用本接口。

### `nodegroup_align_bottom_to_floor`

```python
nodegroup_align_bottom_to_floor() -> bpy.types.GeometryNodeTree
```

输入 `Geometry`，输出对齐后的 `Geometry` 和正 Z 位移量 `Offset`。它读取 bounding box 的最小 Z，并将几何整体移动到最低点为 local Z=0。

该接口只改变 node geometry，不改变 object origin，也不考虑 object 的 world transform。需要修改真实 mesh origin 时使用 `assets_object_mesh_helpers.md` 中的 `origin2lowest`。

## 桌腿部件

### 渐变直腿与中柱腿

运行时签名：

```python
nodegroup_generate_leg_straight(**kwargs) -> bpy.types.GeometryNodeTree
nodegroup_generate_single_stand(**kwargs) -> bpy.types.GeometryNodeTree
```

两者都要求 Python 构建参数：

| 参数 | 作用 |
| --- | --- |
| `Leg Curve Control Points` | `(height_factor, radius_factor)` 序列；高度因子通常从 `0` 单调增加到 `1`，半径因子控制沿腿长的粗细变化 |

```python
straight_group = nodegroup_generate_leg_straight(
    **{"Leg Curve Control Points": [(0.0, 1.0), (0.4, 0.9), (1.0, 0.5)]}
)
```

`nodegroup_generate_leg_straight` 的 Socket 为 `Leg Height`、`Leg Diameter`、`Resolution`、`N-gon`、`Fillet Ratio`。`nodegroup_generate_single_stand` 的 Socket 为 `Leg Height`、`Leg Diameter`、`Resolution`。两者输出 `Geometry`，并沿负 Z 延伸；装配时通常需要平移到桌面下方。

建议显式设置正的 `Leg Height`、`Leg Diameter` 和至少可形成有效曲线/截面的 `Resolution`。直腿用 `N-gon=4` 可得方腿，较大值可得圆腿。中柱接口内部同时用 `Resolution` 作为截面边数，因此不要给过低值。

### `nodegroup_generate_leg_square`

```python
nodegroup_generate_leg_square(**kwargs) -> bpy.types.GeometryNodeTree
```

当前实现不读取 `kwargs`，调用时不传参数即可。它生成的是 U 形或闭合框式支撑，不是一根方柱。

| Socket | 作用 |
| --- | --- |
| `Width` / `Height` | 支撑框横向跨度与高度 |
| `Fillet Radius` | 支撑路径转角圆角 |
| `Has Bottom Connector` | 是否连接底部形成闭合框 |
| `Profile N-gon` | 杆件截面边数 |
| `Profile Width` / `Profile Aspect Ratio` | 杆件截面尺寸 |
| `Profile Fillet Ratio` | 杆件截面圆角比例 |

输出为 `Geometry`。常见桌子使用两个实例，并沿桌面长轴分置；实例数量和摆放不由本 nodegroup 负责。

## 把手部件

### `nodegroup_beveled_cylinder`

```python
nodegroup_beveled_cylinder() -> bpy.types.GeometryNodeTree
```

| Socket | 作用 |
| --- | --- |
| `width` | 截面整体缩放 |
| `aspect_ratio` | 圆角矩形截面的高宽比例 |
| `height` | 沿 local Z 的杆件长度 |

输出 `Geometry`。名称虽为 cylinder，实际是圆角矩形截面的直杆，适合柜门、抽屉或电器把手主体。接口 socket 使用小写名称，必须按源码精确拼写。端座、旋转与门板间距应在调用方组合；简单圆杆把手可直接使用 `spawn_cylinder` 或 `spawn_capsule`。

`nodegroup_handle_end` 归类为门推杆端座内部件；`nodegroup_push_bar_handle` 归类为输出 Parent/Child/Joint 元数据的仿真关节装配接口。两者仍可通过精确符号查询定位，但不应被误当作普通静态把手 helper。

## 灯具部件

### `nodegroup_bulb_rack`

```python
nodegroup_bulb_rack() -> bpy.types.GeometryNodeTree
```

Socket 为 `Thickness`、`Amount`、`InnerRadius`、`OuterRadius`、`InnerHeight`、`OuterHeight`，输出 `Geometry`。它在内外圆之间生成径向支杆，适合灯罩支架。`Amount` 应为正整数，半径和厚度应为正值。

### `nodegroup_lamp_head`

```python
nodegroup_lamp_head() -> bpy.types.GeometryNodeTree
```

| Socket | 作用 |
| --- | --- |
| `ShadeHeight` | 灯罩总高度 |
| `TopRadius` / `BotRadius` | 灯罩上下口半径 |
| `ReverseBulb` | 控制灯罩和支架的上下方向；见下方实现限制 |
| `RackThickness` / `RackHeight` | 内部支架尺寸 |
| `BlackMaterial` | 支架材质 |
| `LampshadeMaterial` | 灯罩及灯泡相关材质 |
| `MetalMaterial` | 灯泡金属底座材质 |

输出 `Geometry`，包含灯罩、支架和固定比例灯泡。当前源码没有把 `ReverseBulb` 转发给内部 `nodegroup_reversiable_bulb` 的 `Reverse` socket，因此不能依赖它真正翻转灯泡几何；它目前只改变灯罩路径和支架高度方向。该接口适合台灯、落地灯和吊灯的头部，但内部使用较高曲线分辨率，批量生成前应评估网格成本。只需灯罩外壳时，直接用曲线旋转/截锥建模通常更轻。

## 相关接口的分类与所有权

| 源码接口/类型 | 主归属 | 原因 |
| --- | --- | --- |
| `TableTopFactory` 及完整 table factories | 对象 Factory 接口 | 包含随机参数和完整资产生命周期，不是部件 API；由对象卡和精确符号索引定位 |
| `nodegroup_create_legs_and_strechers` | 桌架完整装配 helper | socket 多且保留 `Strecher` 拼写，强耦合桌架装配 |
| `nodegroup_push_bar_handle` | 仿真关节装配 helper | 输出关节 Parent/Child 和 joint metadata，依赖 articulation 约定 |
| cabinet 内部 knob/door nodegroup | 柜体私有装配 helper | 将门宽、边距和部件位置烘焙在接口中，不是独立把手 |
| `nodegroup_lamp_geometry` | 灯具完整装配 helper | 负责完整灯具随机装配，已越过可复用部件边界 |
| wheeled leg、chair wheel | 家具交互部件 helper | 复杂度和交互语义高，应由对应对象卡或仿真所有权说明路由 |
| seating、pillow、mattress 私有 helper | 软体对象私有 helper | 主要服务单一 Factory，由对应对象卡和精确符号索引定位 |

## 生成代码检查清单

1. 确认接口的主归属：本页可复用部件、对象 Factory 私有 helper，或仿真/关节装配接口。
2. 区分 Python 构建参数与 nodegroup socket。
3. 精确保留 socket 的大小写、空格和源码拼写。
4. 显式设置源码中无效或危险的零默认值，如腿高、桌面 `N-gon`。
5. 在 local coordinates 完成几何，再由调用方处理材质、parenting 和最终 placement。
6. 同一资产内缓存 `singleton=False` 返回的 nodegroup，避免重复创建数据块。
