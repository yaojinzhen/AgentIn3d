---
id: cabinet-storage-native
domain: object
intent: 书柜、单柜、厨房柜、柜门和抽屉的原生装配路线
aliases: ["bookcase", "cabinet", "kitchen cabinet", "drawer", "shelf", "书柜", "柜子", "橱柜", "抽屉", "柜门", "置物架"]
use_when: "创建由侧板、隔板、背板、门、抽屉、旋钮和附件组成的柜架单体。"
avoid_when: "目标是连续曲面的一体式收纳体，或完整厨房空间与墙体布局。"
source_symbols: ["infinigen/assets/objects/shelves/simple_bookcase.py:SimpleBookcaseFactory", "infinigen/assets/objects/shelves/single_cabinet.py:SingleCabinetFactory", "infinigen/assets/objects/shelves/kitchen_cabinet.py:KitchenCabinetFactory", "infinigen/assets/objects/shelves/cabinet.py:CabinetFactory", "infinigen/assets/objects/shelves/drawers.py:CabinetDrawerBaseFactory", "infinigen/assets/objects/shelves/doors.py:CabinetDoorBaseFactory"]
related_patterns: ["rigid-assembly", "hard-surface-negative-space", "geometry-nodes-distribution"]
summary: "使用共享框架装配板件、隔层、门和抽屉，保持厚度、间隙、铰链侧和把手接触一致。"
---

# 柜架与收纳原生参考

开放书柜从 `SimpleBookcaseFactory` 开始；单柜和厨房柜分别检查 `SingleCabinetFactory`、
`KitchenCabinetFactory`；需要可动门结构时再研究 `CabinetFactory`，但静态资产不复制关节元数据。
门和抽屉应从柜体开口尺寸推导，保持统一板厚、合理门缝和真实把手安装。完整厨房空间由多个柜体
组合，不属于单个柜子的默认入口。
