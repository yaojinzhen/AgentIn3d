---
id: api-material-assignment
domain: api
intent: 创建 Infinigen 或 Blender 材质，并将其赋予 mesh 整体或选定面
aliases: ["material assignment", "assign material", "shader material", "材质赋值", "创建材质"]
use_when: "已经通过材质卡确定视觉语义，正在编码材质创建或赋值调用。"
avoid_when: "仍在选择视觉材质族；此时应先使用 query material。"
source_symbols: ["infinigen.core.surface:shaderfunc", "infinigen.core.util.blender"]
related_patterns: []
documents: ["api_reference/function_api/surface_material_ops.md", "api_reference/material_api/material_assignments.md"]
summary: "路由到材质赋值与 surface 操作叶子文档，不重复加载材质示例。"
---

# 材质创建与赋值 API 操作路由

查询结果直接返回 surface 操作与材质候选池叶子文档；视觉材质族仍先由 query material 确定。
