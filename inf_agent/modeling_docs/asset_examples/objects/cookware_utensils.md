---
id: cookware-utensils-native
domain: object
intent: 锅具、餐具和厨房手工具的原生路线
aliases: ["pan", "pot", "fork", "spoon", "knife", "chopsticks", "spatula", "平底锅", "锅", "叉子", "勺子", "餐刀", "筷子", "锅铲"]
use_when: "创建具有锅体、提手、薄片轮廓、护边或手柄的厨房器具。"
avoid_when: "目标是回转饮水容器、大型厨房空间或要求工作动画的电器。"
source_symbols: ["infinigen/assets/objects/tableware/pan.py:PanFactory", "infinigen/assets/objects/tableware/pot.py:PotFactory", "infinigen/assets/objects/tableware/fork.py:ForkFactory", "infinigen/assets/objects/tableware/spoon.py:SpoonFactory", "infinigen/assets/objects/tableware/knife.py:KnifeFactory", "infinigen/assets/objects/tableware/chopsticks.py:ChopsticksFactory", "infinigen/assets/objects/organizer/hook.py:SpatulaBaseFactory"]
related_patterns: ["profile-revolve-shell", "rigid-assembly", "curve-sweep"]
summary: "锅体使用连续壳体，薄餐具使用显式轮廓与厚度，所有手柄和提手必须真实连接主体。"
---

# 锅具与餐具原生参考

平底锅和锅优先复用 `PanFactory`、`PotFactory` 的锅壁和把手关系；叉、勺、刀采用平面轮廓、
护边和可控厚度；锅铲由铲板、真实开孔和曲线手柄组成。规则部件可使用 primitive，但锅体和
薄片轮廓不能由方块堆叠。检查握柄连接、提手对称、口沿厚度和放置支撑面。
