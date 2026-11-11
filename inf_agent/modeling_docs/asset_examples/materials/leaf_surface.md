---
id: leaf-surface-material
domain: material
intent: 自然绿色叶面、主脉和侧脉材质
aliases: ["leaf material", "green leaf", "叶片材质", "绿色叶面"]
use_when: "叶片需要自然绿色基础、叶面与叶脉变化、粗糙度以及可选的克制透光。"
avoid_when: "目标是干纸、塑料仿真叶或不透明刚性面板。"
source_symbols: ["infinigen/assets/objects/leaves/leaf_broadleaf.py:shader_material"]
related_patterns: ["thin-organic-surface"]
summary: "保持中等明度的绿色叶面和结构相关变化；不能因为存在节点图就接受近白色结果。"
---

# 叶面材质

兼容时优先使用原生阔叶 shader 路径。否则应让叶面保持明确绿色，沿结构坐标轻微改变色相和
明度，以不过度鲜艳的对比区分主脉与侧脉，并克制使用粗糙度和透光。必须在主体占据足够像素
的正视图和斜视图中共同检查。
