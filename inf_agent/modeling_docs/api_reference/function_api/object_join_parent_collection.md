# Object 组合、父子关系与 Collection

本文档记录单体资产生成中用于合并 object、建立父子层级、组织 collection 和清理临时对象的 API。

源码依据：`infinigen/core/util/blender.py`

## 适用边界

| 目标 | 推荐接口 |
| --- | --- |
| 把多个 mesh 烘焙成一个 mesh object | `join_objects` |
| 保留多个部件，并让它们跟随同一个根对象变换 | `parent_to` |
| 将资产部件放进同一个 Blender collection | `group_in_collection` |
| 将 object 移到指定 collection | `put_in_collection` |
| 清理 boolean cutter 等临时 object | `delete` / `TemporaryObject` |

`join`、`parent` 和 `collection` 不是同一种组合方式：`join` 会改变 mesh 数据；`parent` 只建立 transform 层级；`collection` 只负责场景组织和可见性。

## `join_objects`

签名：

```python
join_objects(objs, check_attributes=False) -> bpy.types.Object
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `objs` | 要合并的 mesh object 序列 | 传非空 `list`；把希望保留为结果主体的 object 放在第一项 |
| `check_attributes` | 合并前统一 named attribute 定义 | object 带有需要保留的 attribute 时设为 `True` |

行为：

- 删除顶点数为 `0` 的输入 object。
- 选择所有非空输入，以 `objs[0]` 为 active object，调用 Blender `object.join`。
- 返回合并后的 active object；其 identity、名称和主要 object 属性来自第一项。
- `check_attributes=True` 时，在第一项上补齐其他输入拥有的 attribute；同名 attribute 的 `data_type` 和 `domain` 不一致会触发断言。
- 使用 Blender 原生 join 规则处理 transform、material slot 和 mesh 数据；不会预先应用 modifier。

推荐用法：

```python
parts = [body, frame, handle]
asset = butil.join_objects(parts, check_attributes=True)
asset.name = "cabinet"
```

边界：

- 只传具有 `data.vertices` 的 mesh object；不要混入 empty、light、curve 或 collection。
- 至少要有一个非空 mesh，否则函数在设置 active object 时失败。
- 合并后，除结果 object 外的输入 object 不应继续使用。
- 要保留可独立运动、独立开关材质或语义明确的部件时，不要 join，使用 `parent_to`。

## `parent_to`

签名：

```python
parent_to(
    a,
    b,
    type="OBJECT",
    keep_transform=False,
    no_inverse=False,
    no_transform=False,
) -> None
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `a` | child object | 第一个参数是子对象 |
| `b` | parent object | 第二个参数是父对象，常用 asset root empty |
| `type` | Blender parenting type | 普通资产层级保持 `"OBJECT"` |
| `keep_transform` | parenting 时是否保持 child 的当前 world transform | 已摆放好的部件通常设为 `True` |
| `no_inverse` | 是否调用 `parent_no_inverse_set` | 只有明确需要无 parent inverse 的局部坐标关系时使用 |
| `no_transform` | parenting 后是否把 child 的 local location 和 rotation 清零 | 挂点与 parent 原点完全对齐时使用；不会清零 scale |

行为：

- 校验 child 和 parent 不是同一个 object。
- 将 `b` 设为 active object后执行 Blender parenting operator。
- `no_transform=True` 时额外将 `a.location` 和 `a.rotation_euler` 设为零。
- 最后校验 `a.parent is b`，失败时抛出 `ValueError`。

推荐用法：

```python
root = butil.spawn_empty("lamp_root", disp_type="CUBE", s=0.5)
for part in [base, pole, shade]:
    butil.parent_to(part, root, keep_transform=True)
return root
```

不要把参数顺序写反。`parent_to(root, part)` 的含义是让 `root` 成为 `part` 的 child。

## Collection API

### `get_collection`

签名：

```python
get_collection(name, reuse=True) -> bpy.types.Collection
```

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `name` | collection 名称 | 使用资产类别或实例用途命名 |
| `reuse` | 是否复用 `bpy.data.collections` 中的同名 collection | 独立临时集合设为 `False` |

不存在可复用 collection 时，函数创建 collection 并链接到 scene 根 collection。

### `put_in_collection`

签名：

```python
put_in_collection(objs, collection, exclusive=True) -> bpy.types.Collection
```

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `objs` | 单个 object 或 object iterable | 可传 object list |
| `collection` | collection object 或名称 | 传名称时内部调用 `get_collection` |
| `exclusive` | 是否先从所有现有 collection unlink | 单体资产整理通常保持 `True` |

`exclusive=False` 会保留原 collection 链接，使一个 object 同时属于多个 collection。函数返回目标 collection。

### `group_in_collection`

签名：

```python
group_in_collection(objs, name, reuse=True, **kwargs) -> bpy.types.Collection
```

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `objs` | object、object list 和 `None` 组成的列表 | 用于汇总可选资产部件 |
| `name` | collection 名称 | 必填 |
| `reuse` | 是否复用同名 collection | 默认 `True` |
| `**kwargs` | 透传给 `put_in_collection` | 常用 `exclusive=False` |

行为：

- 忽略顶层 `None`。
- 将每个顶层 object 及其直接 children 放入 collection。
- 当前实现使用 `traverse_children`，不会继续处理 grandchildren。深层 object tree 应显式使用 `iter_object_tree` 展开。

深层层级示例：

```python
objects = list(butil.iter_object_tree(root))
butil.put_in_collection(objects, "generated_lamp")
```

## Object Tree Helper

| 接口 | 签名 | 行为 |
| --- | --- | --- |
| `iter_object_tree` | `iter_object_tree(obj)` | 递归 yield 根 object 和所有 descendants |
| `traverse_children` | `traverse_children(obj, fn)` | 对根 object 和直接 children 调用 `fn`；不是递归遍历 |
| `unlink` | `unlink(obj)` | 从所有 collection 和 scene 根 collection unlink；object 数据仍存在 |

生成代码优先使用 `iter_object_tree`；`traverse_children` 的名称容易让人误以为它会递归。

## 清理 API

### `delete`

签名：

```python
delete(objs: bpy.types.Object | list[bpy.types.Object]) -> None
```

参数与行为：

- 接受单个 object 或 `list`；不要传 tuple、generator 或 `None`。
- 逐个选择并调用 Blender `object.delete`。
- 对 mesh object，如果删除后 mesh data 没有其他 user，也会移除对应 mesh data。
- 删除是全局对象删除，不只是从当前 collection 移除。

推荐用法：

```python
butil.modify_mesh(body, "BOOLEAN", object=cutter, operation="DIFFERENCE")
butil.delete(cutter)
```

### `TemporaryObject`

签名：

```python
TemporaryObject(obj)
```

这是 context manager。进入时返回 `obj`，退出时如果 object 仍存在则调用 `delete`，也能覆盖代码块内抛出异常的情况。

```python
with butil.TemporaryObject(butil.spawn_cube(name="cutter")) as cutter:
    cutter.dimensions = (0.4, 0.2, 0.3)
    butil.apply_transform(cutter)
    butil.modify_mesh(body, "BOOLEAN", object=cutter, operation="DIFFERENCE")
```

### `delete_collection`

签名：

```python
delete_collection(collection: bpy.types.Collection) -> None
```

该函数删除 collection，并继续删除其中的 object。它适合清理确定为临时且独占的 collection；不要用于包含共享 object 的资产集合，也不要把 object 当作普通 unlink 操作传入。

## 推荐组合策略

| 资产情况 | 推荐 |
| --- | --- |
| 所有部件最终是同一静态表面 | join 后返回 mesh |
| 部件需要保持独立材质、语义或局部变换 | 创建 root empty，逐个 parent |
| 只需要整理 Outliner 或批量控制可见性 | 放入 collection，不改变 parent |
| boolean cutter、测量 mesh 等中间产物 | `TemporaryObject` 或完成后 `delete` |

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把 empty 一并传给 `join_objects` | 只传 mesh object；empty 用作 parent root |
| join 后继续修改原部件引用 | 只保留并使用 `join_objects` 的返回值 |
| 已摆好的部件 parent 后跳位 | 使用 `keep_transform=True` |
| 用 collection 代替 transform parent | 需要整体移动时建立 root parent |
| 认为 `group_in_collection` 会处理任意深度 descendants | 用 `iter_object_tree` 展开后调用 `put_in_collection` |
| boolean 后 cutter 残留 | 用 `TemporaryObject` 或显式 `delete` |
