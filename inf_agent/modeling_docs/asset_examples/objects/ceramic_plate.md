---
id: ceramic-plate
domain: object
intent: 基于原生实现的陶瓷盘或浅盘资产
aliases: ["ceramic plate", "plate", "dish", "陶瓷盘", "盘子", "浅盘"]
use_when: "创建具有盘底凹面、盘沿、圈足和陶瓷材质的浅型旋转容器。"
avoid_when: "目标是平坦工业面板或非旋转结构的深容器。"
source_symbols: ["infinigen/assets/objects/tableware/plate.py:PlateFactory"]
related_patterns: ["profile-revolve-shell"]
summary: "使用 PlateFactory 或真实内外剖面；盘内凹腔不能只是实心圆盘上的深色标记。"
---

# 陶瓷盘参考

检查 `PlateFactory` 以及它直接需要的餐具基类。盘底深度、盘沿过渡、壁厚和圈足决定对象身份。
自定义几何应使用同时包含内外轮廓的旋转剖面，并验证凹腔确实存在。
