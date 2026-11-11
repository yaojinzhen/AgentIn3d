# Blender 基础对象

本文档记录 `infinigen.core.util.blender` 中常用 primitive mesh 创建函数。

源码依据：`infinigen/core/util/blender.py`

## 函数总览

| 函数 | 用途 |
| --- | --- |
| `spawn_cube` | 盒体、柜体、门板、桌面、家电外壳 |
| `spawn_plane` | 零厚度平面、后续挤出/solidify 的起始面 |
| `spawn_cylinder` | 桌腿、灯杆、旋钮、圆杆 |
| `spawn_sphere` | 灯泡、圆按钮、球形端帽 |
| `spawn_icosphere` | 低多边形球体、均匀三角球体 |

## `spawn_cube`

签名：

```python
spawn_cube(size=1, location=(0, 0, 0), scale=(1, 1, 1), name=None)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `size` | cube 基础边长 | 通常设为 `1`，再用 `dimensions` 设置真实尺寸 |
| `location` | 创建时 world location | 可创建后再设置 |
| `scale` | 创建时缩放 | 通常保持 `(1, 1, 1)` |
| `name` | object 名称 | 推荐传清晰部件名 |

行为：

- 调用 `bpy.ops.mesh.primitive_cube_add`。
- world 对齐。
- 返回 active object。

推荐用法：

```python
body = butil.spawn_cube(size=1, name="cabinet_body")
body.dimensions = (1.2, 0.45, 1.8)
butil.apply_transform(body)
```

## `spawn_plane`

签名：

```python
spawn_plane(**kwargs)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `name` | object 名称，从 `kwargs` 中取出 | 推荐传部件名 |
| `size` | plane 边长 | 通常设为 `1` |
| `location` | 创建位置 | 可直接传中心位置 |
| 其他 `kwargs` | 透传给 Blender operator | 只传确认存在的参数 |

行为：

- 调用 `bpy.ops.mesh.primitive_plane_add`。
- 默认 `enter_editmode=False`、`align="WORLD"`。
- 返回 active object。

边界：

- plane 没有厚度。
- 需要门板、桌面、柜板等实体时，优先用薄 `spawn_cube`。

## `spawn_cylinder`

签名：

```python
spawn_cylinder(radius=1.0, depth=2.0, location=(0, 0, 0), scale=(1, 1, 1), name=None)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `radius` | 圆柱半径 | 桌腿/灯杆常用 `0.02` 到 `0.08` |
| `depth` | 沿本地 Z 轴的高度 | 竖直杆设高度；横杆设长度后旋转 |
| `location` | 创建位置 | 竖直杆常用 `z=depth/2` |
| `scale` | 创建时缩放 | 通常保持 `(1, 1, 1)` |
| `name` | object 名称 | 推荐传部件名 |

行为：

- 调用 `bpy.ops.mesh.primitive_cylinder_add`。
- 默认沿 Z 轴。
- wrapper 不暴露 `vertices`、`end_fill_type`。

推荐用法：

```python
leg = butil.spawn_cylinder(radius=0.04, depth=0.75, name="table_leg")
leg.location = (0.45, 0.25, 0.375)
bpy.ops.object.shade_smooth()
```

横向圆杆：

```python
handle = butil.spawn_cylinder(radius=0.025, depth=0.8, name="door_handle")
handle.rotation_euler[1] = np.pi / 2
```

## `spawn_sphere`

签名：

```python
spawn_sphere(radius=1, location=(0, 0, 0), scale=(1, 1, 1), name=None)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `radius` | 球体半径 | 按按钮、灯泡、端帽尺寸设置 |
| `location` | 球心位置 | 可直接放到目标中心 |
| `scale` | 缩放 | 椭球才调整 |
| `name` | object 名称 | 推荐传部件名 |

行为：

- 调用 `bpy.ops.mesh.primitive_uv_sphere_add`。
- 返回 active object。

推荐用法：

```python
bulb = butil.spawn_sphere(radius=0.12, location=(0, 0, 1.35), name="bulb")
bpy.ops.object.shade_smooth()
```

## `spawn_icosphere`

签名：

```python
spawn_icosphere(radius=1, location=(0, 0, 0), scale=(1, 1, 1), name=None)
```

参数同 `spawn_sphere`。

区别：

| 函数 | 特点 |
| --- | --- |
| `spawn_sphere` | UV sphere，适合规则表面和常规材质 |
| `spawn_icosphere` | 三角面较均匀，适合低多边形或均匀三角面需求 |

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 用 plane 表示有厚度部件 | 改用薄 cube |
| 设置 `dimensions` 后立刻做 bevel 但未 apply transform | 先 `butil.apply_transform(obj)` |
| 期望 `spawn_cylinder` 控制分段数 | 直接用 Blender operator 或节点 primitive |
