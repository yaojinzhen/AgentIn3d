---
id: api-profile-revolve
domain: api
intent: 使用仓库中的 Blender mesh helper 编码截面回转实体
aliases: ["revolve", "profile revolve", "lathe mesh", "旋转网格", "回转建模", "截面回转"]
use_when: "已经选择 profile-revolve-shell Pattern，正在编码旋转截面和闭合拓扑。"
avoid_when: "仍在查找已有 Factory 或尚未完成建模机制选择；应先查询 object 或 pattern。"
source_symbols: ["bpy.data.meshes.new", "bpy.types.Mesh.from_pydata"]
related_patterns: ["profile-revolve-shell"]
documents: ["api_reference/function_api/attributes_and_mesh_data.md", "api_reference/function_api/blender_modifier_ops.md"]
summary: "路由到显式 mesh 数据和 modifier API，不依赖通用 inf_agent 回转 helper。"
---

# 截面回转 API 操作路由

查询结果直接返回显式 mesh 数据与 modifier 叶子文档。如果已有相近的原生器皿或机械 Factory 实现所需拓扑，应优先复用原生实现。
