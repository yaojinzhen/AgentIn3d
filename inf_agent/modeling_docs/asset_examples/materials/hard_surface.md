---
id: hard-surface-material
domain: material
intent: 涂漆金属、塑料、陶瓷或其他工业涂层硬表面
aliases: ["metal", "plastic", "ceramic", "painted metal", "硬表面材质", "金属", "塑料", "陶瓷"]
use_when: "人造物体需要统一涂层、金属响应、陶瓷釉面或塑料表面。"
avoid_when: "目标是有机表皮、织物、叶片或透明实体。"
source_symbols: ["inf_agent/modeling_docs/api_reference/material_api/indoor_hard_surface_materials.md"]
related_patterns: ["hard-surface-negative-space"]
summary: "先确定符合语义的基础响应，再添加小尺度粗糙度或磨损；不能用同一种纯色 Principled 材质覆盖所有表面。"
---

# 人造硬表面材质

精确接口通过 Material API 查询。涂漆金属除掉漆区域外应保持非金属涂层响应；裸露金属需要
金属高光；陶瓷需要釉面式高光与粗糙度；塑料则随成型工艺和表面处理变化。只在合理且可见的
位置增加磨损，并在添加细微程序化变化前先确认基础色符合要求。
