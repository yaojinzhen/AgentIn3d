# Principled Fallback 材质

当现有 Infinigen 材质无法导入、复杂节点网络生成失败、接口与 Blender 版本不兼容，或只需要一个稳定可辨识的占位材质时，使用本页的最小 Principled BSDF fallback。它属于受控 fallback 接口，不替代 `query material` 的视觉选材流程。

Fallback 的目标是保证资产有清晰、可渲染的材质分区，不是复刻木纹、织纹、划痕或复杂玻璃等程序细节。

主要依赖：

- `bpy.data.materials`
- `infinigen.core.surface.shaderfunc_to_material`
- `Nodes.PrincipledBSDF`
- `Nodes.MaterialOutput`

## 使用顺序

1. 优先调用与用户语义匹配的 Material API。
2. 失败时记录原异常，再创建 fallback material。
3. 保留部件级颜色、金属度、粗糙度、透明或发光等关键语义。
4. 使用 `surface.assign_material` 维持原有整对象或局部材质分区。

不要因一个装饰材质失败而让整个资产生成失败；也不要静默吞掉错误，使 fallback 被误认为最终程序材质。

## 推荐接口

```python
def shader_fallback_principled(
    nw,
    base_color=(0.5, 0.5, 0.5, 1.0),
    metallic=0.0,
    roughness=0.5,
    alpha=1.0,
    transmission=0.0,
    ior=1.5,
    sheen=0.0,
    emission_color=(0.0, 0.0, 0.0, 1.0),
    emission_strength=0.0,
):
    return nw.new_node(
        Nodes.PrincipledBSDF,
        input_kwargs={
            "Base Color": base_color,
            "Metallic": metallic,
            "Roughness": roughness,
            "Alpha": alpha,
            "Transmission Weight": transmission,
            "IOR": ior,
            "Sheen Weight": sheen,
            "Emission Color": emission_color,
            "Emission Strength": emission_strength,
        },
    )
```

`surface.shaderfunc_to_material` 会创建 material、删除默认 Principled BSDF，并将返回的 BSDF 自动连接到 Material Output：

```python
from infinigen.core import surface
from infinigen.core.nodes import Nodes

mat = surface.shaderfunc_to_material(
    shader_fallback_principled,
    name="Fallback_CabinetBody",
    base_color=(0.12, 0.16, 0.2, 1.0),
    metallic=0.0,
    roughness=0.48,
)
surface.assign_material(obj, mat)
```

### 参数

| 参数 | 范围/格式 | 作用 |
| --- | --- | --- |
| `base_color` | RGBA 四元组 | 资产或部件的主色；alpha 通常保持 `1`，透明度由独立 `alpha` 控制 |
| `metallic` | 通常 `0` 或 `1` | 非金属或金属；fallback 不用中间值表达局部磨损 |
| `roughness` | `0..1` | 反射模糊程度；越大越哑光 |
| `alpha` | `0..1` | 表面不透明度；小于 1 时还需配置材质透明渲染方式 |
| `transmission` | `0..1` | 玻璃式透射权重；实体玻璃通常使用 `1` |
| `ior` | 大于 `1` | 介电折射率；常见玻璃可从 `1.45..1.52` 选择 |
| `sheen` | `0..1` | 布料掠射角反射；简单织物可使用小值 |
| `emission_color` | RGBA 四元组 | 发光颜色 |
| `emission_strength` | 大于等于 `0` | `0` 关闭发光；发光外观不等于稳定的场景照明 |

这些 socket 名称对应 Blender 4.2。不要使用旧名称 `Transmission`、`Clearcoat` 或 `Emission`。

## 常用预设

| 目标外观 | 参数组合 |
| --- | --- |
| 哑光塑料/涂漆木 | `metallic=0`，`roughness=0.45..0.7` |
| 陶瓷/抛光石材 | `metallic=0`，`roughness=0.15..0.35` |
| 普通金属 | `metallic=1`，`roughness=0.2..0.5` |
| 简化布料 | `metallic=0`，`roughness=0.65..0.9`，`sheen=0.05..0.25` |
| 实体玻璃 | `metallic=0`，`roughness=0..0.12`，`transmission=1`，`ior≈1.5` |
| 发光屏幕 | 深色 `base_color`，非零 `emission_color` 与 `emission_strength` |

Fallback 颜色应区分相邻语义部件。例如柜体、把手和屏幕分别使用不同颜色或 metallic/roughness，不要把整个资产降级成单一灰色。

## 透明材质设置

`Alpha < 1` 只改变 shader 输入。Blender 4.2 中还应设置 surface render method：

```python
mat = surface.shaderfunc_to_material(
    shader_fallback_principled,
    name="Fallback_Translucent",
    base_color=(0.25, 0.45, 0.7, 1.0),
    roughness=0.25,
    alpha=0.35,
)

if hasattr(mat, "surface_render_method"):
    mat.surface_render_method = "DITHERED"
elif hasattr(mat, "blend_method"):
    mat.blend_method = "HASHED"
```

`Transmission Weight` 与 `Alpha` 语义不同：

- 玻璃折射使用 `transmission=1`，并提供闭合且有厚度的几何。
- 薄膜式淡出或覆盖层使用 `alpha<1`。
- 只需半透明外观且不要求折射时，可只使用 alpha。

## 纯 `bpy` 后备路径

当 Infinigen 的 `surface` 或 `NodeWrangler` 本身不可用时，直接操作 Blender 默认节点。通过检查 socket 是否存在，可减少版本差异导致的二次失败：

```python
import bpy


def make_bpy_fallback(
    name,
    base_color=(0.5, 0.5, 0.5, 1.0),
    metallic=0.0,
    roughness=0.5,
    alpha=1.0,
    transmission=0.0,
    emission_color=(0.0, 0.0, 0.0, 1.0),
    emission_strength=0.0,
):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")

    values = {
        "Base Color": base_color,
        "Metallic": metallic,
        "Roughness": roughness,
        "Alpha": alpha,
        "Transmission Weight": transmission,
        "Emission Color": emission_color,
        "Emission Strength": emission_strength,
    }
    for socket_name, value in values.items():
        socket = bsdf.inputs.get(socket_name)
        if socket is not None:
            socket.default_value = value

    mat.diffuse_color = (
        base_color[0],
        base_color[1],
        base_color[2],
        alpha,
    )
    if alpha < 1.0:
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
        elif hasattr(mat, "blend_method"):
            mat.blend_method = "HASHED"
    return mat
```

该路径保留 Blender 自动创建的 Principled BSDF 和 Material Output，不依赖 Infinigen 节点枚举。若默认节点被用户偏好或模板修改，应额外检查 `bsdf is not None`，失败时再按 `bl_idname` 查找。

## 失败回退模板

```python
import logging

from infinigen.assets.materials import wood
from infinigen.core import surface

logger = logging.getLogger(__name__)

try:
    mat = wood.Wood()()
except Exception as exc:
    logger.warning("Wood material failed; using fallback: %s", exc)
    mat = surface.shaderfunc_to_material(
        shader_fallback_principled,
        name="Fallback_Wood",
        base_color=(0.32, 0.16, 0.07, 1.0),
        roughness=0.58,
    )

surface.assign_material(obj, mat)
```

只包围可能失败的材质创建调用，不要用一个宽泛的 `try/except` 包住完整资产生成流程。

## 验证清单

- 返回值是 `bpy.types.Material`，且 `use_nodes=True`。
- 节点树有活动 Material Output，Surface 已连接。
- `Base Color`、`Metallic`、`Roughness` 与部件语义一致。
- 透明材质已配置 alpha 渲染方式；玻璃几何具有合理厚度。
- 发光材质在目标渲染器中可见，但场景照明不依赖其偶然采样。
- 多材质资产仍保留屏幕、把手、主体、软包等材质分区。
- fallback material 名称包含资产或部件语义，便于日志和输出检查。

更完整的赋值与 selection 规则见 `../function_api/surface_material_ops.md`；Principled BSDF socket 说明见 `../node_api/shader_nodes/principled_bsdf_node.md`。
