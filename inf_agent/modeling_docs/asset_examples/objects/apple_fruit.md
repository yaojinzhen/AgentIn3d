---
id: apple-fruit
domain: object
intent: 基于原生实现的程序化苹果资产
aliases: ["apple", "mature apple", "red apple", "green apple", "苹果", "成熟苹果"]
use_when: "创建苹果，或具有顶部凹陷、果梗和程序化果皮的近似圆润果实。"
avoid_when: "目标果实具有根本不同的分瓣、尖刺或细长形态。"
source_symbols: ["infinigen/assets/objects/fruits/apple.py:FruitFactoryApple", "infinigen/assets/objects/fruits/surfaces/apple_surface.py:shader_apple_shader"]
related_patterns: ["rounded-organic-mass"]
summary: "优先使用原生苹果 Factory 和 shader，保留肩部、凹陷和果梗特征，不能重新制作成带噪声的球体。"
---

# 苹果原生参考

先检查 `FruitFactoryApple`，并且只沿用它直接依赖的通用果实和苹果表面实现。优先复用或窄适配
其剖面、两极塑形、果梗/花萼连接和果皮 shader。原始 UV 球、南瓜式分瓣、苍白材质或悬空
圆柱果梗都属于质量退化。

下一步读取 `modeling_patterns/rounded_organic_mass.md`；只有适配具体调用时才查询精确符号。
