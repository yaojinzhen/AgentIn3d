# Surface 几何 Modifier 操作

本文档记录 `infinigen.core.surface` 中用于从 Python node function 创建 geometry nodes modifier、输出 attribute 和禁用可选 operator 的接口。

源码依据：`infinigen/core/surface.py`

## 函数总览

| 函数/类 | 作用 |
| --- | --- |
| `add_geomod` | 用 `geo_func(nw, ...)` 创建并挂载 geometry nodes modifier |
| `write_attribute` | 用 node function 计算并写出 attribute |
| `NoApply` | 作为 no-op surface/scatter operator |

## `add_geomod`

签名：

```python
add_geomod(
    objs,
    geo_func,
    name=None,
    apply=False,
    reuse=False,
    input_args=None,
    input_kwargs=None,
    attributes=None,
    show_viewport=True,
    selection=None,
    domains=None,
    input_attributes=None,
)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `objs` | object 或 object list | 可传单个对象 |
| `geo_func` | 接收 `NodeWrangler` 的 geometry node function | 函数内部创建 node tree |
| `name` | modifier / node group 名称 | 不传时用 `geo_func.__name__` |
| `apply` | 是否立即应用 modifier | 静态资产通常设 `True` |
| `reuse` | 是否复用同名 node group | 多对象共享同一 node group 时可用 |
| `input_args` | 传给 `geo_func` 的位置参数 | 不传时为空 list |
| `input_kwargs` | 传给 `geo_func` 的关键字参数 | 不传时为空 dict |
| `attributes` | 非 Geometry 输出对应的 attribute 名称 | node group 有额外输出时必须匹配 |
| `show_viewport` | modifier viewport 可见性 | 默认 `True` |
| `selection` | 传给 `geo_func` 的 selection | 会写入 `input_kwargs["selection"]` |
| `domains` | 输出 attribute 的 domain | 默认每个 attribute 都是 `"POINT"` |
| `input_attributes` | node group 输入 attribute 名称 | Geometry 输入应保留 `None` |

行为：

- 为每个 object 创建 `NODES` modifier。
- 第一个 object 创建或复用 node group。
- 用 `NodeWrangler(mod)` 调用 `geo_func(nw, *input_args, **input_kwargs)`。
- 后续对象复用同一个 node group。
- 将 node group 的非 Geometry 输出映射为 modifier 输出 attribute。
- `apply=True` 时调用 `butil.apply_modifiers(obj, name)` 并返回 `None`。
- `apply=False` 时返回最后创建的 modifier。

推荐用法：

```python
surface.add_geomod(
    obj,
    geometry_nodes,
    apply=True,
    input_kwargs=obj_params,
    attributes=[],
)
```

输出 attribute：

```python
surface.add_geomod(
    obj,
    geo_radius,
    apply=True,
    input_args=[0.03, 16],
    attributes=["radius"],
)
```

边界：

- `attributes` 数量必须等于 node group 非 Geometry 输出数量。
- `domains` 数量应与 `attributes` 一致。
- 如果只是已有 node group 要挂载到对象，优先读 `blender_geometry_node_modifiers.md`。

## `write_attribute`

签名：

```python
write_attribute(objs, node_func, name=None, data_type=None, apply=False)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `objs` | object 或 object list | 目标对象 |
| `node_func` | 接收 `NodeWrangler` 并返回要 capture 的值 | 输出 socket 类型用于推断 data type |
| `name` | attribute 名称 | 不传时用 `node_func.__name__` |
| `data_type` | attribute data type | 不传时从输出 socket 推断 |
| `apply` | 是否应用 modifier | 需要立刻读 attribute 时设 `True` |

行为：

- 包装一个内部 geometry node function。
- 使用 `CaptureAttribute` 捕获 `node_func(nw)` 的输出。
- 通过 `add_geomod(..., attributes=[name])` 写出 attribute。
- 返回 attribute name。

推荐用法：

```python
def screen_mask(nw):
    ...
    return mask

attr_name = surface.write_attribute(obj, screen_mask, name="screen", apply=True)
```

如果后续要用 `assign_material(selection="screen")`，通常需要 `apply=True`，确保 attribute 已写入 mesh 数据。

## `NoApply`

签名：

```python
class NoApply:
    @staticmethod
    def apply(objs, *args, **kwargs):
        return objs, []
```

作用：

- 作为可选 material/scatter/surface operator 的 no-op 替身。
- 调用 `.apply(...)` 时不修改对象，返回 `(objs, [])`。

用途：

```python
self.optional_effect = surface.NoApply
```

边界：

- `NoApply` 是占位 operator，不是材质。
- 不要把它传给 `assign_material`。

## 与 `butil.modify_mesh("NODES")` 的区别

| 接口 | 适用场景 |
| --- | --- |
| `surface.add_geomod` | 有 Python `geo_func(nw, ...)`，希望创建 node group 并可输出 attribute |
| `butil.modify_mesh(..., "NODES")` | 已有 node group，只需要作为 modifier 挂载并设置 interface input |

## 常见错误

| 错误 | 修复 |
| --- | --- |
| `attributes` 数量与非 Geometry 输出不一致 | 调整 node group 输出或 attributes 列表 |
| 写出 attribute 后立刻读，但 `apply=False` | 设置 `apply=True` |
| 把 Geometry 输入也写进 `input_attributes` | Geometry 输入应保留 `None` |
| 用 `add_geomod` 只为挂已有 node group | 改用 `blender_geometry_node_modifiers.md` 中的 `modify_mesh("NODES")` |
