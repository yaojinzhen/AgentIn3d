---
id: api-object-mesh
domain: api
intent: 创建、变换、倒角、连接、设定父子关系并管理 Blender mesh 对象
aliases: ["mesh object", "spawn cube", "join objects", "parent object", "bevel", "网格对象", "倒角", "对象父子关系"]
use_when: "正在编码规则刚性部件，或处理最终对象所有权、局部变换和层级。"
avoid_when: "仍在选择形态策略或查找精确原生对象实现。"
source_symbols: ["infinigen.core.util.blender", "bpy.types.Object"]
related_patterns: ["rigid-assembly", "hard-surface-negative-space"]
documents: ["api_reference/function_api/blender_primitive_objects.md", "api_reference/function_api/object_join_parent_collection.md", "api_reference/function_api/beveling_and_edges.md"]
summary: "路由到 primitive/object、join/parent、transform 和 bevel 的最小叶子文档。"
---

# Object 与 Mesh API 操作路由

查询结果直接返回 primitive、对象所有权和倒角叶子文档；精确函数名应由符号索引直达其主叶子文档。
