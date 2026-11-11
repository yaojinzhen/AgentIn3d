---
id: glass-screen-emissive-material
domain: material
intent: 玻璃、屏幕、透明体或发光区域材质
aliases: ["glass", "screen", "emissive", "transparent", "玻璃", "屏幕", "发光材质"]
use_when: "可见区域是玻璃、显示屏、镜片或发光指示器。"
avoid_when: "目标只是通过深色外观模拟玻璃的不透明面板。"
source_symbols: ["inf_agent/modeling_docs/api_reference/material_api/glass_screen_emissive_materials.md"]
related_patterns: ["hard-surface-negative-space"]
summary: "使用经过验证的透射或发光接口，并为玻璃和屏幕建立可读性所需的厚度、内层或背板。"
---

# 玻璃、屏幕与发光材质

单靠材质通常不够：玻璃一般需要厚度以及内部或背衬；屏幕需要明确边界和受控发光；镜片还
依赖正确形状与法线。发光强度要足以辨认，但不能冲淡主体。只有在编写该区域代码时，才继续
查询精确节点或材质函数签名。
