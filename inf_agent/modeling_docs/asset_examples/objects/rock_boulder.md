---
id: rock-boulder
domain: object
intent: 基于原生实现的巨石和不规则岩石资产
aliases: ["rock", "boulder", "stone", "岩石", "巨石", "石头"]
use_when: "创建具有多尺度自然形变和石材材质的单块紧凑岩石或巨石。"
avoid_when: "目标是地形、岩石群、晶体或精确切割的人造石构件。"
source_symbols: ["infinigen/assets/objects/rocks/boulder.py:BoulderFactory"]
related_patterns: ["irregular-solid"]
summary: "优先采用原生巨石塑形和分层形变，避免只在球体上施加均匀径向噪声。"
---

# 巨石原生参考

检查 `BoulderFactory` 以及它直接调用的形变和材质 helper。区分宏观体块、方向性不规则、细部
起伏、石材 shading 和可信支撑面。自定义实现前先读取 `modeling_patterns/irregular_solid.md`。
