# Blender 辅助对象

本文档记录 `infinigen.core.util.blender` 中用于 empty、点、线和辅助 mesh 的创建函数。

源码依据：`infinigen/core/util/blender.py`

## 函数总览

| 函数 | 用途 |
| --- | --- |
| `spawn_empty` | 多部件资产根对象、placeholder、挂点 |
| `spawn_point_cloud` | 自定义点/边 mesh、调试几何 |
| `spawn_vert` | 单点辅助对象 |
| `spawn_line` | 点序列连接成边线 |

## `spawn_empty`

签名：

```python
spawn_empty(name, disp_type="PLAIN_AXES", s=0.1)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `name` | empty object 名称 | 必填，推荐用资产根名称 |
| `disp_type` | viewport 显示形状 | 根对象常用 `"CUBE"`，挂点常用 `"PLAIN_AXES"` |
| `s` | viewport display size | 接近资产 bbox 或保持小尺寸 |

行为：

- 创建无 mesh data 的 object。
- 链接到当前 scene collection。
- 设置 empty display size/type。

推荐用法：

```python
root = butil.spawn_empty("asset_root", disp_type="CUBE", s=1.0)
body.parent = root
door.parent = root
return root
```

边界：

- empty 自身不是可见 mesh。
- `create_asset` 返回 empty 时，必须有可见 mesh 子对象。

## `spawn_point_cloud`

签名：

```python
spawn_point_cloud(name, pts, edges=None)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `name` | object 和 mesh 名称 | 写清楚用途 |
| `pts` | 顶点坐标列表 | 每个点必须是三维坐标 |
| `edges` | 顶点索引边列表 | 不传时只有点，没有边 |

行为：

- 创建 mesh。
- 调用 `mesh.from_pydata(pts, edges, [])`。
- 不创建面。

## `spawn_vert`

签名：

```python
spawn_vert(name="vert")
```

行为：

- 调用 `spawn_point_cloud(name, np.zeros((1, 3)))`。
- 返回单点 mesh object。

用途：

- 调试点。
- 临时空间标记。

## `spawn_line`

签名：

```python
spawn_line(name, pts)
```

参数：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `name` | object 名称 | 写清楚用途 |
| `pts` | 顺序连接的点 | 至少 2 个点才形成边 |

行为：

- 将点序列连接成连续边。
- 不创建面。

示例：

```python
pts = np.array([(0, 0, 0), (0, 0, 1), (0.2, 0, 1.2)])
guide = butil.spawn_line("lamp_arm_guide", pts)
```

边界：

| 目标 | 推荐方案 |
| --- | --- |
| 可见直杆 | `blender_primitive_objects.md` 中的 `spawn_cylinder` |
| 圆头杆件 | `blender_special_objects.md` 中的 `spawn_capsule` |
| 弯曲线缆/把手 | `../node_api/README.md` 中的 Geometry Nodes curve 类别 |

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 返回 empty 但没有 mesh 子对象 | 至少创建一个可见 mesh child |
| 用 `spawn_line` 表示最终可见杆件 | 改用 cylinder、capsule 或 curve node |
| 把 point cloud 当实体 mesh | 需要面时使用 primitive 或自定义 mesh 面数据 |
