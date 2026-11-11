---
id: api-geometry-nodes
domain: api
intent: 使用 NodeWrangler 编写或适配 Geometry Nodes 节点组
aliases: ["geometry nodes", "NodeWrangler", "node group", "几何节点", "节点组编写"]
use_when: "已选 Pattern 确实需要字段驱动的重复、mask、分支或求值分布，正在进入节点编码。"
avoid_when: "直接 mesh、curve 或少量固定重复更简单，或尚未完成建模机制选择。"
source_symbols: ["infinigen.core.nodes.node_wrangler:NodeWrangler", "infinigen.core.nodes.node_utils:nodegroup"]
related_patterns: ["geometry-nodes-distribution"]
documents: ["api_reference/node_api/nodegroup_authoring.md", "api_reference/node_api/node_wrangler_usage.md"]
summary: "路由到 nodegroup 编写契约和当前节点族叶子文档，避免读取完整节点目录。"
---

# Geometry Nodes API 操作路由

查询结果直接返回 nodegroup 与 NodeWrangler 契约；具体 Nodes.* 或 bl_idname 应继续使用精确 API 查询直达所属节点叶子文档。
