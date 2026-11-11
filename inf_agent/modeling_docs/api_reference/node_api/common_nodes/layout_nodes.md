# 布局节点

本文档覆盖 `Nodes` 枚举中的布局节点。布局节点只提高 node tree 可读性，不改变生成资产的数值或几何结果。

## `Nodes.Reroute`

**作用**：把一条连接整理为可复用的中转点；单输入可连接到多个下游 socket。

**创建方式**：

```python
coord_route = nw.new_node(
    Nodes.Reroute,
    input_kwargs={"Input": texture_coord},
    label="Shared texture coordinate",
)
```

| `new_node` 参数 | 当前节点的用法 |
| --- | --- |
| `node_type` | `Nodes.Reroute`，对应 `NodeReroute` |
| `input_kwargs` | `Input`：任意可连接 socket |
| `label` | 可选；只在名称能帮助理解共享数据时设置 |

**Input Sockets**：`Input`；类型随连接的数据自动适配。

**Output Sockets**：`Output`；数据和值保持不变，可直接把节点作为后续 `input_kwargs` 的值。

Reroute 不缓存字段、不固定 domain，也不复制数据。只在一个输出分支很多、长连线难读或生成代码需要保留显式共享点时使用；简单链路无需添加。

## 常见错误

| 错误 | 修复 |
| --- | --- |
| 把 Reroute 当作类型转换或缓存节点 | 使用真正的转换/捕获节点 |
| 通过 `attrs` 设置输入 | 使用 `input_kwargs={"Input": socket}` |
| 为每条连接都创建 Reroute | 仅在分支或布局确实需要时添加 |

## 相关文档

- `new_node`、socket 连接和返回值：`../node_wrangler_usage.md`
- socket 类型与兼容：`../socket_attrs_and_compatibility.md`

## 主要来源

- `infinigen/core/nodes/node_info.py`
- `infinigen/core/nodes/node_wrangler.py`
- [Blender 4.2 Reroute Node](https://docs.blender.org/manual/en/4.2/interface/controls/nodes/reroute.html)
