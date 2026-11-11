# Node API 路由

本目录记录 `NodeWrangler`、nodegroup authoring、Blender 节点、socket、`attrs` 和仓库版本兼容事实。是否应采用 Geometry Nodes 由 `modeling_patterns` 决定，本目录只回答选定机制后如何正确编码。

## 完整分类

| 分类 | 目录或文档 | 收录范围 |
| --- | --- | --- |
| NodeWrangler 与 group 契约 | `node_wrangler_usage.md`、`nodegroup_authoring.md`、`socket_attrs_and_compatibility.md` | 创建、连接、interface、类型、singleton 与兼容层 |
| 共用/功能型节点 | `common_nodes/` | 数值、输入、数学、逻辑、向量、映射、颜色、纹理和布局节点 |
| Geometry Nodes | `geometry_nodes/` | attribute/field、采样、结构、空间查询、mesh、curve、instance、point、volume、material 和 text geometry |
| Shader/World/Light Nodes | `shader_nodes/` | shader 输入、BSDF、normal/displacement、texture 依赖、emission、volume、hair、material/world/light output |
| Compositor Nodes | `compositor_nodes/` | render layer、颜色处理、镜头效果、viewer、composite 和文件输出 |

分类依据是节点树和技术功能，不是使用频率。`WorldOutput`、`PrincipledVolume`、Hair、Compositor、文件输出等接口即使不属于单体资产代码的所有权，也必须保留并在对应文档中标注调用边界。

优先使用精确的 `query api` 查询 `Nodes.*`、原始 `bl_idname` 或明确的节点操作。需要手动回退时，先读取通用契约，再只进入一个节点分类：

| 当前问题 | 文档或目录 |
| --- | --- |
| 创建、连接和复用 nodegroup | `nodegroup_authoring.md` |
| `NodeWrangler.new_node` 通用调用 | `node_wrangler_usage.md` |
| socket、`attrs`、数据类型或版本行为 | `socket_attrs_and_compatibility.md` |
| 数值、数学、向量、纹理和颜色节点 | `common_nodes/` |
| field、采样、mesh/curve 操作和实例 | `geometry_nodes/` |
| BSDF、输入坐标、normal/displacement 和输出 | `shader_nodes/` |
| Compositor 维护性查阅 | `compositor_nodes/` |

单体 generated asset 不拥有 compositor、world、camera、render 或 export 流水线，但这些接口仍属于完整 Node API 参考。节点或 nodegroup 存在也不代表几何和材质质量合格，仍需检查 evaluated geometry 与实际渲染结果。

每个 `Nodes.*` 公开名称必须在一份叶子文档中拥有唯一主标题；共享同一 `bl_idname` 的公开别名应在同一标题并列。仓库实际使用但尚未进入 `Nodes` 枚举的原始 `bl_idname` 也必须归入对应 Geometry、Shader 或 Compositor 文档。

不要为了编写一个 nodegroup 读取完整节点目录；代码到达具体节点时再查询对应叶子文档。
