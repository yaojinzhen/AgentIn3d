# Blender 几何节点 Modifier

本文档记录通过 `infinigen.core.util.blender` 添加 geometry nodes modifier 和设置 node group 输入的 API。

源码依据：`infinigen/core/util/blender.py`

## 函数总览

| 函数 | 作用 |
| --- | --- |
| `modify_mesh(..., type="NODES", node_group=..., ng_inputs=...)` | 给 object 添加 geometry nodes modifier |
| `set_geomod_inputs` | 根据 node group interface input 名称设置 modifier 输入 |
| `apply_geo` | 应用 object 上的 `NODES` modifier |

## 添加 geometry nodes modifier

推荐形式：

```python
butil.modify_mesh(
    obj,
    "NODES",
    node_group=node_group,
    ng_inputs={
        "Width": width,
        "Height": height,
    },
)
```

相关参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `obj` | 目标 object | 通常是 mesh object |
| `"NODES"` | modifier type | 必须使用该类型 |
| `node_group` | Blender node group | 必须通过 `kwargs` 传入 |
| `ng_inputs` | node group interface input 名称到值的映射 | key 必须匹配 interface socket name |
| `apply` | 是否立即应用 | 静态资产通常为 `True` |

边界：

- `ng_inputs is not None` 时，哪怕传入空字典，`modify_mesh` 也会断言 `type == "NODES"`。
- `ng_inputs is not None` 时，`kwargs` 中必须包含 `node_group`。
- node group 创建方式查询 `../node_api/README.md` 中的 nodegroup authoring 类别。

## `set_geomod_inputs`

签名：

```python
set_geomod_inputs(mod, inputs: dict)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `mod` | geometry nodes modifier | `mod.type` 必须是 `"NODES"` |
| `inputs` | interface input 名称到值的映射 | key 使用 socket display name |

行为：

- 遍历 `mod.node_group.interface.items_tree` 中 `in_out == "INPUT"` 的 socket。
- 用 socket `name` 匹配 `inputs` 的 key。
- 使用 socket `identifier` 写入 `mod[soc.identifier]`。
- 如果 socket 没有 `default_value`，只允许传 `None`。
- 如果 socket 默认值是 `float` 或 `int`，会把输入值转换成相同类型。
- 如果值是 `np.ndarray`，会转成 list。

常见错误：

| 错误 | 后果 | 修复 |
| --- | --- | --- |
| `ng_inputs` key 和 socket name 不一致 | `KeyError` | 使用 node group interface 中的 input 名称 |
| 给 geometry/socket 这类无 `default_value` 的输入传非 `None` | `ValueError` | 这类输入通常需要在 node tree 内连接 |
| 传入不兼容类型 | `TypeError` | 按 socket 类型传 float/int/vector/material |

## `apply_geo`

签名：

```python
apply_geo(obj)
```

参数：

| 参数 | 作用 |
| --- | --- |
| `obj` | 目标 object |

行为：

- 选择目标 object。
- 先把 object 上所有 modifier 的 `show_viewport` 设为 `False`。
- 遍历 object modifiers，仅对 `m.type == "NODES"` 的 modifier 调用 `bpy.ops.object.modifier_apply`。
- 未应用的非 NODES modifier 会保留在 stack 中，但 `show_viewport` 仍为 `False`；函数不会恢复它们原来的可见状态。

建议：

- 新代码优先用 `modify_mesh(obj, "NODES", ..., apply=True)` 或 `apply_modifiers`。
- `apply_geo` 更适合作为兼容旧代码的 helper。确实使用时，应提前保存并在之后恢复其他 modifier 的 `show_viewport` 状态。

常见副作用：用 `apply_geo` 后其他 modifier 在 viewport 中消失，是因为它关闭了所有 modifier 的 `show_viewport`。优先使用 `apply_modifiers`，或手动恢复可见状态。

## 推荐路线

| 需求 | 路由 |
| --- | --- |
| 创建 nodegroup | `../node_api/README.md` 中的 nodegroup authoring 类别 |
| 查询 node 和 socket | `../node_api/README.md` |
| 通过 modifier 挂载 nodegroup | 本文档 |
| 材质/attribute 在节点内传递 | `../node_api/README.md` 中的 Geometry Nodes material/attribute 类别 |

## 常见模板

```python
node_group = build_my_nodegroup()
obj = butil.spawn_cube(size=1, name="geomod_base")
butil.modify_mesh(
    obj,
    "NODES",
    node_group=node_group,
    ng_inputs={
        "Scale": 1.0,
        "Use Detail": True,
    },
)
```

如果需要保留 modifier 供后续调整：

```python
obj, mod = butil.modify_mesh(
    obj,
    "NODES",
    apply=False,
    return_mod=True,
    node_group=node_group,
)
butil.set_geomod_inputs(mod, {"Scale": 1.0})
```
