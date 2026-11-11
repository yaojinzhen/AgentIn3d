---
id: api-shader-nodes
domain: api
intent: 使用 NodeWrangler 和明确的 Blender shader 节点创建程序化材质
aliases: ["shader nodes", "NodeWrangler shader", "Principled BSDF", "着色器节点", "材质节点"]
use_when: "材质实现使用 NodeWrangler、Nodes.* 或自定义 shader 节点连接。"
avoid_when: "只复用已经验证的完整材质 Factory，且不编写节点网络。"
source_symbols: ["infinigen.core.nodes.node_wrangler:NodeWrangler", "infinigen.core.nodes.node_info:Nodes"]
related_patterns: []
documents: ["api_reference/node_api/node_wrangler_usage.md", "api_reference/node_api/shader_nodes/principled_bsdf_node.md"]
summary: "先核对 NodeWrangler 的 socket/输出约定，再核对具体 shader 节点的输入与 Blender 版本。"
---

# 着色器节点 API 操作路由

这是一条编码阶段的叶子路由。具体 Texture、ColorRamp、Mapping 等节点应按实际使用的节点名继续读取 `api_reference/node_api` 中对应的叶子文档；不要把本卡当成所有节点的接口定义。
