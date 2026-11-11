# Blender 特殊对象

本文档记录 `infinigen.core.util.blender` 中不属于常规 primitive 或 helper 的特殊创建函数。

源码依据：`infinigen/core/util/blender.py`

## 函数总览

| 函数 | 用途 |
| --- | --- |
| `spawn_capsule` | 胶囊形把手、圆头杆件、软圆柱 |

## `spawn_capsule`

签名：

```python
spawn_capsule(rad, height, us=32, vs=16)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `rad` | 胶囊半径 | 把手/圆头杆件常用 `0.015` 到 `0.06` |
| `height` | 两个半球之间的中段长度 | 整体长度约为 `height + 2 * rad` |
| `us` | 水平方向球段数 | 默认 `32`；小物件可用 `16` 或 `24` |
| `vs` | 垂直方向球段数 | 默认 `16`；小物件可用 `8` 或 `12` |

行为：

- 创建名为 `Capsule` 的 mesh object。
- 用 bmesh 创建 UV sphere。
- 将 Z 轴正半球上移 `height`。
- 调用 `shade_smooth`。
- 返回 object。

推荐用法：

```python
handle = butil.spawn_capsule(rad=0.025, height=0.55, us=24, vs=12)
handle.name = "rounded_handle"
# 源码生成范围为 [-rad, height + rad]，先把几何中心移到 local origin。
handle.location.z = -0.55 / 2
butil.apply_transform(handle, loc=True)
handle.rotation_euler[1] = np.pi / 2
handle.location = (0.0, -0.33, 0.9)
```

边界：

| 注意点 | 说明 |
| --- | --- |
| 不接受 `name` | 创建后设置 `handle.name` |
| 不接受 `location` | 创建后设置 `handle.location` |
| 默认沿 Z 轴 | 横向把手需要旋转 |
| 整体长度不是 `height` | 约为 `height + 2 * rad` |
| object origin 不在几何中心 | local Z bounds 约为 `[-rad, height + rad]`，几何中心位于 `height / 2`；需要绕中心旋转时先将几何平移 `-height / 2` 并 apply location |

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 给 `spawn_capsule` 传 `name` 或 `location` | 创建后设置 object 属性 |
| 把 `height` 当作整体长度 | 整体长度约为 `height + 2 * rad` |
| 需要弯曲胶囊杆 | 改用 curve node 或自定义 nodegroup |
