---
id: kitchen-appliances-native
domain: object
intent: 冰箱、洗碗机、微波炉和烤箱的原生家电路线
aliases: ["refrigerator", "fridge", "dishwasher", "microwave", "oven", "冰箱", "饮料冰箱", "洗碗机", "微波炉", "烤箱"]
use_when: "创建具有箱体、门板、把手、搁架、控制件或玻璃观察窗的厨房家电。"
avoid_when: "目标是小型手持电器、完全开放的机械设备或不具有家电箱体结构的对象。"
source_symbols: ["infinigen/assets/objects/appliances/beverage_fridge.py:BeverageFridgeFactory", "infinigen/assets/objects/appliances/dishwasher.py:DishwasherFactory", "infinigen/assets/objects/appliances/microwave.py:MicrowaveFactory", "infinigen/assets/objects/appliances/oven.py:OvenFactory"]
related_patterns: ["hard-surface-negative-space", "rigid-assembly"]
summary: "优先复用对应原生 Factory；箱体、门板和附件共享坐标系，观察窗、内腔和把手必须具有真实结构。"
---

# 厨房家电原生参考

| 对象 | 首选入口 | 应保留的机制 |
| --- | --- | --- |
| 冰箱 | `BeverageFridgeFactory` | 空心箱体、门板、搁架、把手和分区材质 |
| 洗碗机 | `DishwasherFactory` | 箱体、门板、碗架与控制区域 |
| 微波炉 | `MicrowaveFactory` | 布尔内腔、玻璃门、转盘与控制面板 |
| 烤箱 | `OvenFactory` | 玻璃门、搁架、加热管与可选炉架 |

先尝试直接实例化匹配 Factory，再通过参数或窄适配满足颜色和比例。不要复制各文件内重复定义的
私有 hollow-cube、center 或专用 nodegroup。材质先查询硬表面路由；玻璃观察窗再查询玻璃/屏幕
材质。文字与控制件只有在最终预览可见时才增加。
