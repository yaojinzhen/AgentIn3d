---
id: architectural-decor-native
domain: object
intent: 窗户、墙面装饰、墙架、柱子、抽油烟机、水族箱和气球的原生路线
aliases: ["window", "wall art", "mirror", "wall shelf", "pillar", "range hood", "aquarium", "balloon", "窗户", "墙面画", "镜子", "墙架", "柱子", "抽油烟机", "水族箱", "气球"]
use_when: "创建可独立检查的建筑附属件、墙面物件或室内装饰单体。"
avoid_when: "目标是完整房间、建筑生成、沿房间边界运行的踢脚线工具或带内部生态的完整场景。"
source_symbols: ["infinigen/assets/objects/windows/window.py:WindowFactory", "infinigen/assets/objects/wall_decorations/wall_art.py:WallArtFactory", "infinigen/assets/objects/wall_decorations/wall_art.py:MirrorFactory", "infinigen/assets/objects/wall_decorations/wall_shelf.py:WallShelfFactory", "infinigen/assets/objects/elements/pillars.py:PillarFactory", "infinigen/assets/objects/wall_decorations/range_hood.py:RangeHoodFactory", "infinigen/assets/objects/decor/aquarium_tank.py:AquariumTankFactory", "infinigen/assets/objects/wall_decorations/balloon.py:BalloonFactory"]
related_patterns: ["rigid-assembly", "hard-surface-negative-space", "custom-mesh-loft"]
summary: "按精确对象选择原生 Factory，保留框架、玻璃、支撑面和安装关系；房间级工具不进入单体资产。"
---

# 建筑附属与装饰原生参考

| 类型 | 首选入口 | 重点 |
| --- | --- | --- |
| 窗户 | `WindowFactory` | 框、玻璃格、百叶或窗帘的统一总成 |
| 墙面画/镜子 | `WallArtFactory` / `MirrorFactory` | 平面、倒角框和明确前后层次 |
| 墙架 | `WallShelfFactory` | 板件、侧支撑和墙面安装关系 |
| 柱子/抽油烟机 | `PillarFactory` / `RangeHoodFactory` | 回转分段或轮廓放样，而非方块堆叠 |
| 水族箱 | `AquariumTankFactory` | 玻璃厚度、上下框和内部边界；原生入口当前不等于完整水体场景 |
| 气球 | `BalloonFactory` | 文字或轮廓充气后的连续表面；不引入场景飘动和仿真 |

踢脚线是沿房间轮廓运行的模块函数，不应包装成独立 `AssetFactory`。复杂原生窗户 nodegroup 只在
完整 Factory 可安全实例化时使用，不复制其私有子组。
