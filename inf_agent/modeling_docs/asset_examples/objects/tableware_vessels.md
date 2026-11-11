---
id: tableware-vessels-native
domain: object
intent: 杯、碗、瓶、酒杯、罐和盖子的原生回转容器路线
aliases: ["cup", "bowl", "bottle", "wine glass", "can", "jar", "lid", "杯子", "碗", "瓶子", "酒杯", "易拉罐", "罐子", "盖子"]
use_when: "创建主要由轴向轮廓、口沿、内腔、颈部、底足或盖子定义的器皿。"
avoid_when: "对象主要由非回转板件组成，或是需要液体、食品和场景散布的组合资产。"
source_symbols: ["infinigen/assets/objects/tableware/cup.py:CupFactory", "infinigen/assets/objects/tableware/bowl.py:BowlFactory", "infinigen/assets/objects/tableware/bottle.py:BottleFactory", "infinigen/assets/objects/tableware/wineglass.py:WineglassFactory", "infinigen/assets/objects/tableware/can.py:CanFactory", "infinigen/assets/objects/tableware/jar.py:JarFactory", "infinigen/assets/objects/tableware/lid.py:LidFactory"]
related_patterns: ["profile-revolve-shell", "hard-surface-negative-space"]
summary: "使用原生器皿 Factory 或其内外轮廓机制，明确口沿、正壁厚、空腔、颈部和底足。"
---

# 回转器皿原生参考

杯、碗、瓶和酒杯优先采用各自 Factory；自定义时只借鉴剖面与加厚机制。杯把、标签和盖子是
附件，必须从主体轮廓定位。透明酒杯需要可读壁厚和合理法线；碗和杯需要真实内表面；瓶颈、
易拉罐顶盖和罐口不能靠颜色变化代替几何。

`FruitContainerFactory`、`PlantContainerFactory` 等包装 Factory 会加入实例散布或植物，不适合
只生成空容器时直接使用。
