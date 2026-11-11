---
id: mushroom-native
domain: object
intent: 基于原生菌盖、菌柄和生长机制的蘑菇资产
aliases: ["mushroom", "toadstool", "fungus", "蘑菇", "菌菇"]
use_when: "创建由菌盖、盖下结构、菌柄及可选物种细节组成的单个蘑菇。"
avoid_when: "目标是蘑菇群落或场景散布，而不是可独立检查的单体资产。"
source_symbols: ["infinigen/assets/objects/mushroom/generate.py:MushroomFactory", "infinigen/assets/objects/mushroom/cap.py:MushroomCapFactory", "infinigen/assets/objects/mushroom/stem.py:MushroomStemFactory"]
related_patterns: ["radial-cap-stem", "geometry-nodes-distribution"]
summary: "复用原生菌盖、菌柄装配和盖下结构机制，不能只把半球放在圆柱上。"
---

# 蘑菇原生参考

从 `MushroomFactory` 开始，只检查所选组合需要的菌盖和菌柄 Factory。保留可信的盖缘与盖下
结构，使渐细菌柄自然进入菌盖，并保持受控不对称。只有在最终画面可见时才增加菌褶、孔洞、
斑点或鳞片。
