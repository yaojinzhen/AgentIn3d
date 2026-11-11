---
id: dining-table
domain: object
intent: 基于原生实现的餐桌刚性装配
aliases: ["dining table", "table", "餐桌", "桌子"]
use_when: "创建由桌面、桌腿或支撑框架以及可选横撑和细节组成的餐桌。"
avoid_when: "目标是依赖连续曲面外壳形成身份的一体式雕塑桌。"
source_symbols: ["infinigen/assets/objects/tables/dining_table.py:TableDiningFactory", "infinigen/assets/objects/tables/dining_table.py:geometry_assemble_table"]
related_patterns: ["rigid-assembly", "geometry-nodes-distribution"]
summary: "复用原生桌体装配或坐标逻辑；真实刚性部件可以使用 primitive，但接触关系必须经过设计。"
---

# 餐桌参考

从 `TableDiningFactory` 开始。其装配和桌腿生成逻辑可用于确定支撑位置、重复关系和变化。
模块化餐桌可以使用 primitive，但桌面厚度、边缘处理、横撑、桌腿接触和材质尺度都必须有意设计。
