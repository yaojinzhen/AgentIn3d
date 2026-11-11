# AssetFactory 生命周期

本文档说明 agent 如何基于 `infinigen.core.placement.factory.AssetFactory` 编写可被 runner 调用的资产工厂。它的定位是生命周期契约，不是普通 helper 清单。

源码依据：

| 源码 | 覆盖内容 |
| --- | --- |
| `infinigen/core/placement/factory.py` | `AssetFactory`、placeholder hooks、`spawn_placeholder`、`spawn_asset`、`make_asset_collection` |
| `infinigen/core/util/math.py` | `FixedSeed`、`int_hash` 随机性契约 |
| `infinigen/core/util/blender.py` | `spawn_asset` 内部使用的 GC、parent、delete helper |

## 何时读取

| 需求 | 是否读取本文档 |
| --- | --- |
| 新建一个 generated asset factory | 是 |
| 判断哪些方法该 override | 是 |
| 理解 `spawn_asset` 如何调用 `create_asset` | 是 |
| 查询 `spawn_cube`、`spawn_cylinder` 参数 | 否，读 `blender_primitive_objects.md` |
| 查询材质赋值 | 否，读 `surface_material_ops.md` |
| 查询 nodegroup 写法 | 否，读 `../node_api/README.md` 并选择 nodegroup authoring 类别 |

## 最小模板

```python
from infinigen.core.placement.factory import AssetFactory
from infinigen.core.util import blender as butil
from infinigen.core.util.math import FixedSeed


class GeneratedAssetFactory(AssetFactory):
    def __init__(self, factory_seed, coarse=False, dimensions=None, spec=None):
        super().__init__(factory_seed=factory_seed, coarse=coarse)
        self.spec = spec or {}
        self.dimensions = dimensions or self.spec.get("dimensions")
        with FixedSeed(factory_seed):
            self.params = self.sample_parameters()

    def sample_parameters(self):
        return {"width": 1.0, "depth": 0.6, "height": 1.2}

    def create_asset(self, i=0, placeholder=None, **params):
        obj = butil.spawn_cube(size=1, name="asset_body")
        obj.dimensions = (
            self.params["width"],
            self.params["depth"],
            self.params["height"],
        )
        butil.apply_transform(obj)
        return obj
```

## 方法职责速查

| 方法/属性 | agent 是否实现 | 作用 |
| --- | --- | --- |
| `__init__` | 通常实现 | 保存 spec、dimensions、采样固定参数 |
| `create_asset` | 必须实现 | 创建高精度资产并返回一个 Blender object |
| `create_placeholder` | 可选 | 创建低精度占位对象 |
| `finalize_placeholders` | 可选 | 对一批 placeholder 做统一后处理 |
| `asset_parameters` | 可选 | 根据距离向 `create_asset` 传入细节参数 |
| `finalize_assets` | 可选 | 批量后处理最终资产 |
| `spawn_placeholder` | 不建议实现 | 调度 `create_placeholder` 并设置 seed/location/rotation |
| `spawn_asset` | 不建议实现 | 生命周期主入口 |
| `make_asset_collection` | 调用方使用 | 批量生成资产集合 |

## `AssetFactory.__init__`

签名：

```python
AssetFactory.__init__(factory_seed=None, coarse=False)
```

参数：

| 参数 | 作用 | 取值建议 |
| --- | --- | --- |
| `factory_seed` | factory 级随机种子；为 `None` 时父类随机生成 | generated factory 应接收并传给 `super()` |
| `coarse` | 低精度/占位模式标记 | 保留参数，正式单体资产通常为 `False` |

行为：

- 设置 `self.factory_seed`。
- 设置 `self.coarse`。
- 不创建 Blender object。

推荐写法：

```python
def __init__(self, factory_seed, coarse=False, dimensions=None, spec=None):
    super().__init__(factory_seed=factory_seed, coarse=coarse)
    self.spec = spec or {}
    self.dimensions = dimensions or self.spec.get("dimensions")
```

## `create_asset`

签名：

```python
create_asset(self, **params) -> bpy.types.Object
```

实际常见形式：

```python
def create_asset(self, i=0, placeholder=None, **params):
    ...
```

参数：

| 参数 | 来源 | 作用 |
| --- | --- | --- |
| `i` | `spawn_asset` | 实例 index；与 `factory_seed` 一起决定随机性 |
| `placeholder` | `spawn_asset` | 占位对象；简单资产可忽略 |
| `face_size` | `asset_parameters` | 距离相关目标面尺寸 |
| `distance` | `asset_parameters` | 资产到观察点的距离估计 |
| `vis_distance` | `asset_parameters` | 可见距离估计 |
| `**params` | 调用方覆盖 | 额外生成参数 |

行为：

- 创建资产几何和材质。
- 返回单个 Blender object。
- 可返回 mesh object，也可返回带 mesh 子对象的 empty parent。

最低要求：

- 返回对象存在。
- 至少有一个可见 mesh，或存在可见 mesh 子对象。
- bbox 非零。
- 不保存、导出、渲染。

## `create_placeholder`

签名：

```python
create_placeholder(self, **kwargs) -> bpy.types.Object
```

参数：

| 参数 | 来源 | 作用 |
| --- | --- | --- |
| `**kwargs` | `spawn_placeholder` 透传 | 可能包含 `i`、`loc`、`rot` |

默认行为：

- 返回 `butil.spawn_cube(size=2)`。

何时实现：

| 情况 | 建议 |
| --- | --- |
| 资产比例明显不同于默认 cube | 实现一个近似 bbox 的 placeholder |
| 只生成单体静态资产 | 通常不实现 |
| 需要复杂预览或材质 | 不建议放在 placeholder 中 |

## `asset_parameters`

签名：

```python
asset_parameters(self, distance: float, vis_distance: float) -> dict
```

默认返回：

```python
{
    "face_size": detail.target_face_size(distance),
    "distance": distance,
    "vis_distance": vis_distance,
}
```

参数：

| 参数 | 作用 |
| --- | --- |
| `distance` | 距离估计，用于控制细节密度 |
| `vis_distance` | 可见距离估计 |

何时实现：

- 资产需要根据距离关闭小细节。
- 资产需要根据距离调整 mesh 密度。

多数静态室内单体资产可以不实现。

## `finalize_placeholders`

签名：

```python
finalize_placeholders(self, placeholders: list[bpy.types.Object]) -> None
```

默认实现不做任何处理。场景 placement 流程可能一次传入整批 placeholder；`spawn_asset` 在自行创建 placeholder 时也会以单元素列表调用该 hook。只有 placeholder 之间需要联合调整时才重写，普通单体资产通常保持默认实现。

## `spawn_placeholder`

签名：

```python
spawn_placeholder(self, i, loc, rot) -> bpy.types.Object
```

参数：

| 参数 | 作用 |
| --- | --- |
| `i` | 实例 index，与 `factory_seed` 一起派生稳定 seed |
| `loc` | placeholder 的目标位置 |
| `rot` | placeholder 的目标 Euler rotation |

该方法在 `FixedSeed(int_hash((factory_seed, i)))` 中调用 `create_placeholder(i=i, loc=loc, rot=rot)`，随后设置位置、旋转和名称。placeholder 带 `FOLLOW_PATH` constraint 时不会直接覆盖位置；返回对象已有 parent 时会记录 warning。agent 不应重写该调度方法，应改写 `create_placeholder` 或 `finalize_placeholders`。

## `finalize_assets`

签名：

```python
finalize_assets(self, assets)
```

参数：

| 参数 | 作用 | 取值建议 |
| --- | --- | --- |
| `assets` | 一批已生成对象 | 兼容单个 object 和 list |

推荐写法：

```python
def finalize_assets(self, assets):
    if assets is None:
        return
    if not isinstance(assets, (list, tuple)):
        assets = [assets]
```

适合：

- 批量应用 scratches、edge wear。
- 清理或统一后处理。

不适合：

- 保存 `.blend`。
- 导出 `.glb`。
- 渲染 preview。
- 设置相机或全局场景。

## `spawn_asset`

签名：

```python
spawn_asset(
    self,
    i,
    placeholder=None,
    distance=None,
    vis_distance=0,
    loc=(0, 0, 0),
    rot=(0, 0, 0),
    **kwargs,
)
```

参数：

| 参数 | 作用 |
| --- | --- |
| `i` | 实例 index，必须是 `int` |
| `placeholder` | 已有占位对象；通常由流程管理 |
| `distance` | 细节距离；为 `None` 时使用默认 scatter 距离 |
| `vis_distance` | 可见距离 |
| `loc` | 未提供 placeholder 时的生成位置 |
| `rot` | 未提供 placeholder 时的生成旋转 |
| `**kwargs` | 合并进 `asset_parameters` 后传给 `create_asset` |

关键行为：

```text
spawn_asset
  -> spawn_placeholder 或使用外部 placeholder
  -> 对内部创建的 placeholder 调用 finalize_placeholders([placeholder])
  -> asset_parameters(distance, vis_distance)
  -> params.update(kwargs)
  -> FixedSeed(int_hash((factory_seed, i)))
  -> create_asset(i=i, placeholder=placeholder, **params)
  -> 继承 placeholder 的 location/rotation
  -> 删除内部创建的 placeholder
```

agent 通常不要重写 `spawn_asset`。要改变生成内容，改 `create_asset`；要改变参数，改 `asset_parameters`；要改变占位对象，改 `create_placeholder`。

额外边界：

- `self.coarse=True` 时调用 `spawn_asset` 会直接抛出 `ValueError`；coarse factory 用于 placeholder/低精度流程，不是正式资产细节开关。
- 传入外部 `placeholder` 时，`loc` 和 `rot` 必须保持默认零值；位置与旋转由该 placeholder 提供。
- 未传外部 placeholder 时，内部 placeholder 会在正式资产继承其位置和旋转后被删除。

## `make_asset_collection`

签名：

```python
make_asset_collection(
    spawn_fns,
    n,
    name=None,
    weights=None,
    as_list=False,
    verbose=True,
    centered=False,
    **kwargs,
)
```

参数：

| 参数 | 作用 |
| --- | --- |
| `spawn_fns` | 一个或多个 asset spawn callable |
| `n` | 生成数量 |
| `weights` | 多个 callable 的采样权重 |
| `as_list` | 为 `True` 时返回 object list，否则返回 collection |
| `centered` | 是否把对象移到自身中心附近并应用 transform |
| `**kwargs` | 透传给每次 spawn |

单体资产代码通常不主动调用它。它更适合批量资产集合、测试和 runner 层逻辑，接口仍由本页记录。

## 随机性规则

`spawn_asset` 内部使用：

```python
FixedSeed(int_hash((self.factory_seed, i)))
```

因此同一个 `factory_seed` 和 `i` 应生成稳定结果。

如果在 `__init__` 中采样固定参数，使用：

```python
with FixedSeed(factory_seed):
    self.params = self.sample_parameters()
```

不要在模块 import 时采样随机数或创建 Blender object。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 忘记继承 `AssetFactory` | `class XFactory(AssetFactory)` |
| 忘记调用 `super().__init__` | 在子类 `__init__` 第一段调用 |
| 重写 `spawn_asset` | 改写 `create_asset` / `asset_parameters` / `create_placeholder` |
| `create_asset` 返回 list/tuple | 返回一个 mesh object 或 empty parent |
| 返回 empty 但没有 mesh 子对象 | 至少创建一个可见 mesh child |
| 在 `__init__` 或 import 阶段创建 Blender object | 移到 `create_asset` |

## 相关文档

| 需求 | 文档 |
| --- | --- |
| 选择基础 object 创建 API | `README.md` 的文档路由表 |
| 查询 cube/plane/cylinder/sphere 参数 | `blender_primitive_objects.md` |
| 查询 empty/point/line 参数 | `blender_helper_objects.md` |
| 查询 capsule 参数 | `blender_special_objects.md` |
| 添加普通 modifier 或应用 transform | `blender_modifier_ops.md` |
| 添加 geometry nodes modifier | `blender_geometry_node_modifiers.md` |
| 赋材质 | `surface_material_ops.md` |
