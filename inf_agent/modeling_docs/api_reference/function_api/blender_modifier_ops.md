# Blender Modifier 操作

本文档记录 `infinigen.core.util.blender` 中普通 modifier、transform apply 和 mesh 转换相关 API。

源码依据：`infinigen/core/util/blender.py`

## 函数总览

| 函数 | 作用 |
| --- | --- |
| `modify_mesh` | 新建 modifier，设置属性，并可立即应用 |
| `apply_modifiers` | 应用一个、多个或全部 modifier |
| `apply_transform` | 将 object 的 location/rotation/scale 应用到 mesh 数据 |
| `to_mesh` | 从 evaluated object 创建一个 mesh copy |
| `move_modifier` | 将 modifier 移到指定 stack index |

## `modify_mesh`

签名：

```python
modify_mesh(
    obj,
    type,
    apply=True,
    name=None,
    return_mod=False,
    ng_inputs=None,
    show_viewport=None,
    **kwargs,
) -> bpy.types.Object
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `obj` | 要添加 modifier 的 Blender object | 应是支持该 modifier 的 object |
| `type` | Blender modifier type，如 `"BEVEL"`、`"BOOLEAN"` | 使用 Blender modifier 枚举字符串 |
| `apply` | 是否立即应用 modifier | 生成静态资产通常为 `True` |
| `name` | modifier 名称 | 不传时自动生成 |
| `return_mod` | 是否返回 modifier 对象 | 需要后续调整时设为 `True` |
| `ng_inputs` | geometry nodes 输入 | 仅 `type=="NODES"` 时使用；详见 `blender_geometry_node_modifiers.md` |
| `show_viewport` | modifier viewport 可见性 | 不传时为 `not apply` |
| `**kwargs` | 透传为 modifier 属性 | 只传确定存在的 Blender 属性 |

行为：

- 调用 `obj.modifiers.new(name, type)`。
- 对 `kwargs` 执行 `setattr(mod, k, v)`。
- 如果 `ng_inputs` 不为空，调用 `set_geomod_inputs`。
- `apply=True` 时调用 `apply_modifiers(obj, mod=mod)`。
- `return_mod=True` 时返回 `(obj, mod)`，但如果已应用则第二项为 `None`。

推荐用法：

```python
butil.modify_mesh(obj, "BEVEL", width=0.02, segments=3)
butil.modify_mesh(obj, "SOLIDIFY", thickness=0.03, offset=1)
butil.modify_mesh(obj, "BOOLEAN", object=cutter, operation="DIFFERENCE")
```

## 常用 modifier 类型

| 类型 | 常用参数 | 用途 |
| --- | --- | --- |
| `"BEVEL"` | `width`, `segments` | 硬表面倒角、圆润边缘 |
| `"SOLIDIFY"` | `thickness`, `offset` | 给 plane/薄面加厚 |
| `"BOOLEAN"` | `object`, `operation` | 用 cutter 做差集/交集/并集 |
| `"SUBSURF"` | `levels`, `render_levels` | 细分曲面 |
| `"MIRROR"` | `use_axis` | 对称复制 |
| `"SIMPLE_DEFORM"` | `deform_method`, `angle` | taper、bend、stretch 等变形 |
| `"WELD"` | `merge_threshold` | 合并近距离顶点 |
| `"TRIANGULATE"` | `min_vertices` | 三角化 |
| `"SMOOTH"` | `factor`, `iterations` | 平滑 mesh |
| `"DISPLACE"` | `texture`, `strength`, `mid_level` | 基于 texture 扰动表面 |
| `"REMESH"` | `mode`, `octree_depth` | 重建 mesh |

这些参数来自 Blender modifier 属性，不是 Infinigen 自定义参数。若不确定属性名，应查 Blender API 或参考已有资产实现。

## `apply_modifiers`

签名：

```python
apply_modifiers(obj, mod=None, quiet=True)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `obj` | 目标 object | 必须有 modifiers |
| `mod` | `None`、modifier、modifier name、或 list | `None` 表示应用全部 |
| `quiet` | 是否 suppress Blender operator 输出 | 默认保持 `True` |

行为：

- 如果 `mod is None`，应用 `obj.modifiers` 中全部 modifier。
- 如果 `mod` 是字符串，按名称从 `obj.modifiers` 取 modifier。
- 使用 `bpy.ops.object.modifier_apply` 应用。
- 应用后调用 `purge_empty_materials(obj)`。
- 普通 modifier apply 失败会继续抛错。`NODES` modifier 抛出 `RuntimeError` 时，兼容分支会移除该 modifier 并清空 object mesh，而不是保留原几何；不要把它当作无损失败处理。

推荐用法：

```python
butil.apply_modifiers(obj)
butil.apply_modifiers(obj, mod="Bevel")
```

## `apply_transform`

签名：

```python
apply_transform(obj, loc=False, rot=True, scale=True)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `obj` | 目标 object | 通常是 mesh object |
| `loc` | 是否应用 location | 大多数建模步骤保持 `False`；需要冻结位置时设 `True` |
| `rot` | 是否应用 rotation | 默认 `True` |
| `scale` | 是否应用 scale | 默认 `True` |

行为：

- 选择目标对象。
- 调用 `bpy.ops.object.transform_apply(location=loc, rotation=rot, scale=scale)`。

常用模式：

```python
obj.dimensions = (width, depth, height)
butil.apply_transform(obj)
```

注意：`apply_transform(obj, True)` 中的 `True` 对应 `loc=True`，会把 location 也应用到 mesh 数据。默认建议使用 `butil.apply_transform(obj)`；只有需要冻结 world location 时才传 `loc=True`。

## `to_mesh`

签名：

```python
to_mesh(object, context=bpy.context)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `object` | evaluated 来源对象 | 可以带 modifier |
| `context` | Blender context | 通常不传 |

行为：

- 从 evaluated depsgraph 创建新 mesh。
- 新对象名称为 `object.name + "_mesh"`。
- 复制 `matrix_world`。
- 链接到当前 collection。
- 选择新对象并设为 active。
- 不删除原对象。

适合：

- 需要保留原对象，同时得到烘焙后的 mesh copy。
- 在进一步 mesh 编辑前把 modifier 结果固化成新对象。

## `move_modifier`

签名：

```python
move_modifier(obj, mod, i)
```

参数：

| 参数 | 作用 |
| --- | --- |
| `obj` | 目标 object |
| `mod` | modifier object |
| `i` | 目标 stack index |

行为：

- 调用 `bpy.ops.object.modifier_move_to_index`。

静态单体资产很少需要主动调整 modifier stack。只有多个未应用 modifier 的顺序重要时再使用，接口仍保留供该场景调用。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 认为 `NODES` modifier apply 失败会保留原 mesh | 兼容分支可能清空 mesh；只对已验证可应用的 nodegroup 调用 `apply_modifiers` |
| 设置 `dimensions` 后直接 bevel，未 apply transform | 先 `butil.apply_transform(obj)` |
| `BOOLEAN` 后忘记删除 cutter | boolean 应用后用 delete helper 清理 cutter |
| `modify_mesh(..., apply=True, return_mod=True)` 后继续使用返回的 mod | 已应用时 mod 返回为 `None` |
| 给 modifier 传不存在的属性名 | 使用 Blender modifier 属性名，或参考已有资产 |
| 把 `NODES` modifier 输入当普通 `kwargs` 传 | 用 `ng_inputs`，并读 `blender_geometry_node_modifiers.md` |
