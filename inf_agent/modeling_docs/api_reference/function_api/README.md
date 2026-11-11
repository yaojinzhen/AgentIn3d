# Function API 路由

本目录记录 Infinigen Python 类、函数和 helper。名称沿用 `function_api`，但其实际范围包括类、生命周期、函数、装饰器、上下文管理器、模块级候选池入口以及低频或受所有权限制的接口。

## 文档类型

| 类型 | 文档 | 职责 |
| --- | --- | --- |
| Factory 契约 | `asset_factory_lifecycle.md` | `AssetFactory` 方法、seed、placeholder 和批量生命周期 |
| Blender object/mesh | `blender_primitive_objects.md`、`blender_special_objects.md`、`blender_helper_objects.md`、`assets_object_mesh_helpers.md` | 创建 object、显式 mesh、bbox、origin 和数组编辑 |
| Modifier 与 surface | `blender_modifier_ops.md`、`blender_geometry_node_modifiers.md`、`surface_geomod_ops.md` | 普通 modifier、Geometry Nodes modifier 和 attribute 写入 |
| Object 所有权 | `object_join_parent_collection.md` | join、parent、collection、object tree 和清理 |
| Mesh 数据与边 | `attributes_and_mesh_data.md`、`beveling_and_edges.md` | 坐标、拓扑、attribute、边选择和倒角 |
| 材质操作 | `surface_material_ops.md` | 从 shader function 创建材质并赋给 object/selection |
| 数学与随机 | `math_random_sampling.md` | 固定 seed、hash、分布和加权采样 |
| 原生组件接口 | `reusable_component_helpers.md` | 可复用 nodegroup/helper 的精确参数与 socket，不承担完整对象选择 |
| 范围与所有权 | `excluded_or_deferred_core_apis.md` | 记录场景、仿真、渲染、导出等接口的归属；“不由资产代码调用”不等于从 API 文档删除 |

完整对象 Factory 的选择仍由 `query object` 负责；本目录只在调用或适配具体 Python 接口时使用。

优先使用精确的 `query api` 结果。需要手动回退时，建议先读取与当前代码操作对应的一份叶子文档，再按需补充：

| 代码操作 | 叶子文档 |
| --- | --- |
| `AssetFactory` 生命周期 | `asset_factory_lifecycle.md` |
| cube、cylinder、sphere、plane | `blender_primitive_objects.md` |
| capsule 等特殊基础对象 | `blender_special_objects.md` |
| EMPTY、辅助线和辅助点 | `blender_helper_objects.md` |
| modifier 与 transform | `blender_modifier_ops.md` |
| 挂载现有 Geometry Nodes group | `blender_geometry_node_modifiers.md` |
| join、parent、collection 和清理 | `object_join_parent_collection.md` |
| 创建和赋予材质 | `surface_material_ops.md` |
| 挂载 geometry function | `surface_geomod_ops.md` |
| 显式顶点、面和 attribute 数据 | `attributes_and_mesh_data.md` |
| 倒角与边选择 | `beveling_and_edges.md` |
| 可复现随机采样 | `math_random_sampling.md` |
| 通用 object/mesh helper | `assets_object_mesh_helpers.md` |
| 经筛选的原生可复用组件 | `reusable_component_helpers.md` |
| 当前流程排除或暂缓的 Core API | `excluded_or_deferred_core_apis.md` |

本目录负责签名、参数、副作用、上下文要求、稳定性和源码限制，不负责选择资产形态。形态由已选 `modeling_patterns` 文档决定；已有完整 Factory 仍属于对象参考，不能因为出现在源码中就视为稳定公共 helper。

不得因接口低频、当前 Skill 不直接调用或属于 runner/scene/simulation 而删除其记录。此类接口应留在最接近其技术职责的文档中，并显式标注调用所有权与替代入口。

不要先读本表再加载所有叶子文档。写到具体调用时再查询精确符号，并保持单次读取范围最小。
