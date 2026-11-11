---
id: broadleaf-leaf
domain: object
intent: 基于原生实现的程序化绿色阔叶资产
aliases: ["broadleaf", "green broadleaf", "broad leaf", "leaf", "阔叶", "绿色阔叶", "叶片"]
use_when: "创建单片阔叶，并需要清楚表现轮廓、叶柄、主脉、侧脉、弯曲和绿色材质。"
avoid_when: "目标是针叶、复叶簇、棕榈叶或其他结构根本不同的叶片。"
source_symbols: ["infinigen/assets/objects/leaves/leaf_broadleaf.py:LeafFactoryBroadleaf", "infinigen/assets/objects/leaves/leaf_broadleaf.py:geo_leaf_broadleaf"]
related_patterns: ["thin-organic-surface", "geometry-nodes-distribution"]
summary: "使用原生阔叶的几何和材质坐标机制，避免以矩形平面叠加通用噪声。"
---

# 阔叶原生参考

读取 `LeafFactoryBroadleaf`、`geo_leaf_broadleaf`，以及所选路径实际使用的形状、叶脉和材质
节点组。保留连接轮廓、叶柄、主脉、侧脉、形变和 shader 的共享纵向坐标系。下一步读取
`modeling_patterns/thin_organic_surface.md`；只有确实需要分布机制时才增加 Geometry Nodes Pattern。
