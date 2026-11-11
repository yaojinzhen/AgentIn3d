---
id: plant-containers-native
domain: object
intent: 花盆、植物容器和带泥土静态盆栽的原生路线
aliases: ["plant pot", "flower pot", "planter", "plant container", "potted plant", "花盆", "植物容器", "盆栽"]
use_when: "创建空花盆、带泥土容器或由花盆与单株植物组成的静态组合资产。"
avoid_when: "目标是植物群落、花园布局、随机场景散布或完整室内绿化。"
source_symbols: ["infinigen/assets/objects/tableware/plant_container.py:PlantPotFactory", "infinigen/assets/objects/tableware/plant_container.py:PlantContainerFactory", "infinigen/assets/objects/tableware/plant_container.py:LargePlantContainerFactory", "infinigen/assets/objects/tableware/pot.py:PotFactory"]
related_patterns: ["profile-revolve-shell", "rigid-assembly", "geometry-nodes-distribution"]
summary: "空容器先使用 PotFactory；需要盆栽时再组合泥土盘和一个明确植物 Factory，避免扩展为场景散布。"
---

# 花盆与植物容器原生参考

只需要容器时优先使用 `PotFactory` 或其轮廓机制。需要完整盆栽时，再检查
`PlantPotFactory`、`PlantContainerFactory` 或 `LargePlantContainerFactory`，确认植物类型和
实例数量可控。花盆必须有真实内腔、口沿和底部，泥土盘位于内腔中，植物根部与泥土接触。
包装 Factory 中的随机植物选择不能覆盖用户明确要求。
