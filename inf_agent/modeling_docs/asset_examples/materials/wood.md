---
id: wood-material
domain: material
intent: 木材纹理的颜色、粗糙度、尺度与方向
aliases: ["wood", "wooden", "timber", "木材", "木纹"]
use_when: "结构件或果梗需要呈现木材质感，且纹理应沿生长方向或加工轴线排列。"
avoid_when: "部件为涂漆、金属或陶瓷表面，或者尺寸小到不应看到明显木纹。"
source_symbols: ["infinigen/assets/materials/wood"]
related_patterns: ["rigid-assembly"]
summary: "让纹理沿部件轴向排列，保持合理基础色与粗糙度，避免各向同性噪声和尺寸过大的条纹。"
---

# 木材材质

存在经过验证的原生木材材质时优先选用。果梗、木板或把手的纹理应与长轴一致，颜色和粗糙度
变化必须符合部件尺度；细小苹果梗只需要微妙纹理，不能出现桌面尺度的年轮。最后在斜向高光
下确认材质响应。
