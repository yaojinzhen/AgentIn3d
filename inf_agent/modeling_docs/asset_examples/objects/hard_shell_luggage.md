---
id: hard-shell-luggage
domain: object
intent: 硬壳行李箱或旅行箱的形态路线
aliases: ["hard-shell luggage", "hard shell suitcase", "suitcase", "行李箱", "硬壳旅行箱"]
use_when: "创建具有圆角双壳、接缝或拉链、把手、轮组和加强筋的静态行李箱。"
avoid_when: "需求包含开合动画、软布行李或完整旅行场景。"
source_symbols: []
related_patterns: ["custom-mesh-loft", "curve-sweep", "rigid-assembly"]
summary: "使用连续放样外壳并结合曲线和刚性附件，避免把多个倒角方盒简单堆叠。"
---

# 硬壳行李箱形态参考

使用圆角截面或受控自定义曲面构造两半外壳。接缝和拉链应依附外壳边界，把手与轮组应从局部
表面坐标框架定位，并确认把手底座和轮罩真实接触箱体。
