# Surface 材质操作

本文档记录 `infinigen.core.surface` 中材质创建、添加、赋值和清理相关 API。

源码依据：`infinigen/core/surface.py`

## 函数总览

| 函数 | 作用 |
| --- | --- |
| `shaderfunc_to_material` | 将 Infinigen shader function 转成 `bpy.types.Material` |
| `add_material` | 将 shader function 生成/混合为材质，并赋给对象 |
| `assign_material` | 将已有 material 赋给对象，可按 face selection 局部赋值 |
| `remove_materials` | 移除对象所有 material slots |

## `shaderfunc_to_material`

签名：

```python
shaderfunc_to_material(shader_func, *args, name=None, **kwargs)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `shader_func` | 接收 `NodeWrangler` 并返回 shader node/socket 的函数 | 来自 `assets/materials/**` 或自定义 shader function |
| `*args` | 传给 shader function 的位置参数 | 按 shader function 定义传 |
| `name` | material 名称 | 不传时用 `shader_func.__name__` |
| `**kwargs` | 传给 shader function 的关键字参数 | 只传 shader function 支持的字段 |

行为：

- 新建 material。
- 设置 `material.use_nodes = True`。
- 删除默认 `Principled BSDF`。
- 用 `NodeWrangler` 执行 `shader_func(nw, *args, **kwargs)`。
- 如果 shader function 返回 surface node/socket，自动连接到 `MaterialOutput.Surface`。
- 如果返回 `(surface, volume)`，会额外连接 `MaterialOutput.Volume`。

推荐用法：

```python
mat = surface.shaderfunc_to_material(shader_wood, name="cabinet_wood")
surface.assign_material(obj, mat)
```

边界：

- shader function 必须返回可连接到 material output 的节点或 socket。
- 如果 shader function 内部已经自行创建 output 并返回 `None`，该函数不会再补 surface output。

## `add_material`

签名：

```python
add_material(
    objs,
    shader_func,
    selection=None,
    input_args=None,
    input_kwargs=None,
    name=None,
    reuse=False,
)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `objs` | object 或 object list | 单个对象可直接传 |
| `shader_func` | shader function | 需要返回 shader 输出，尤其在 selection 模式下 |
| `selection` | `None`、attribute 名称或 `tags.Semantics` | `None` 表示整对象赋材质 |
| `input_args` | shader function 位置参数 | 只在 `selection is None` 路径使用；不传时为空 list |
| `input_kwargs` | shader function 关键字参数 | 不传时为空 dict |
| `name` | material 名称 | selection 模式固定使用 `MixedSurface`；整对象模式源码当前不会把该值传给 `shaderfunc_to_material` |
| `reuse` | 是否复用同名 material | selection 模式会复用 `MixedSurface`；整对象模式不要依赖它控制 material 名称 |

行为：

- `selection is None` 时，调用 `shaderfunc_to_material` 创建材质，并设为每个对象的 active material。
- `selection` 是字符串或 `tags.Semantics` 时，创建/复用名为 `MixedSurface` 的材质，通过 attribute 权重混合旧 shader 与新 shader。
- 返回 material。

推荐用法：

```python
surface.add_material(obj, shader_plastic, input_kwargs={"roughness": 0.45})
surface.add_material(obj, shader_metal, selection="handle")
```

边界：

- 源码当前在 `selection is None` 路径中不会把 `name` 传入 `shaderfunc_to_material`；如果需要确定 material 名称，优先使用 `shaderfunc_to_material(..., name=...)` 后再 `assign_material`。
- selection 模式依赖对象上已有对应 attribute。
- selection 模式下 shader function 必须返回输出，否则会报错。
- selection 模式调用 `shader_func(nw, **input_kwargs)`，不会传入 `input_args`；局部材质需要额外参数时应使用关键字参数。
- 如果只是已有 material 赋值，优先用 `assign_material`。

## `assign_material`

签名：

```python
assign_material(
    objs: bpy.types.Object | list[bpy.types.Object],
    material: bpy.types.Material,
    selection: str | np.ndarray | None = None,
)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `objs` | object 或 object list | 无 selection 时优先传单个对象；list 见边界说明 |
| `material` | 已有 material | 可来自 `shaderfunc_to_material` 或材质库 |
| `selection` | `None`、attribute 名称、`!attribute`、或 bool ndarray | `None` 表示整对象赋材质 |

行为：

- `selection is None` 时，设置当前对象的 `active_material`。
- `selection` 是字符串时，从 FACE domain attribute 读取 bool mask。
- `selection` 以 `!` 开头时，使用 attribute 的反选 mask。
- `selection` 是 `np.ndarray` 时，要求 dtype 为 bool。
- 局部赋材质时添加 material slot，并写入 FACE domain 的 `material_index` attribute。

推荐用法：

```python
surface.assign_material(obj, body_mat)
surface.assign_material(obj, handle_mat, selection="handle")
surface.assign_material(obj, screen_mat, selection="screen")
surface.assign_material(obj, body_mat, selection="!screen")
```

边界：

- 源码当前在 `selection is None` 分支内会 `return`，因此传入 object list 时只会给第一个对象赋材质；多对象整对象赋材质应循环调用，或使用 `add_material`。
- selection 模式要求对象已有 material slot，否则会报错。
- selection attribute 应是 FACE domain bool 数据。
- 局部赋材质会依赖 `material_index` attribute；不要手动破坏它。

## `remove_materials`

签名：

```python
remove_materials(obj)
```

参数：

| 参数 | 作用 |
| --- | --- |
| `obj` | 目标 object |

行为：

- 选择对象。
- 从 active material index 0 开始移除所有 material slots。

用途：

- 清空临时材质。
- 重新统一赋材质前清理对象。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把 shader function 当 material 直接传给 `assign_material` | 先用 `shaderfunc_to_material` |
| 期望 `add_material(..., name=...)` 控制整对象 material 名称 | 改用 `shaderfunc_to_material(..., name=...)` + `assign_material` |
| 用 `assign_material([obj1, obj2], mat)` 给多个对象整对象赋材质 | 对每个 object 分别调用，或改用 `add_material` |
| selection attribute 不存在 | 先写 attribute 或改为整对象赋材质 |
| selection mask 不是 bool | 转成 bool ndarray |
| 局部赋材质前对象没有 active material | 先给对象赋一个基础材质 |
