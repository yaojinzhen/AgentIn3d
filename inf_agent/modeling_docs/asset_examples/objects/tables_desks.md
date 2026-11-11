---
id: tables-desks-native
domain: object
intent: 鸡尾酒桌、边桌、咖啡桌、书桌、桌面和台面的原生路线
aliases: ["cocktail table", "coffee table", "side table", "desk", "countertop", "table top", "鸡尾酒桌", "咖啡桌", "边桌", "书桌", "台面", "桌面"]
use_when: "创建由承载台面、支腿或支撑柱、横撑以及可选柜体顶面组成的桌台单体。"
avoid_when: "目标是已有独立餐桌路由的普通餐桌，或依赖连续雕塑曲面的整体桌体。"
source_symbols: ["infinigen/assets/objects/tables/cocktail_table.py:TableCocktailFactory", "infinigen/assets/objects/tables/dining_table.py:SideTableFactory", "infinigen/assets/objects/tables/dining_table.py:CoffeeTableFactory", "infinigen/assets/objects/tables/table_top.py:TableTopFactory", "infinigen/assets/objects/shelves/simple_desk.py:SimpleDeskFactory", "infinigen/assets/objects/shelves/simple_desk.py:SidetableDeskFactory", "infinigen/assets/objects/shelves/countertop.py:CountertopFactory"]
related_patterns: ["rigid-assembly", "geometry-nodes-distribution"]
summary: "复用相应桌台 Factory 的台面、锚点和支撑布局，保持受力路径、落地接触与材质尺度。"
---

# 桌台与书桌原生参考

鸡尾酒桌、边桌和咖啡桌优先从相应原生 Factory 开始；简单书桌使用规则台面和四角支腿；
`TableTopFactory` 只生成带 SupportSurface 的几何台面，不负责材质；`CountertopFactory` 依赖
底层家具轮廓生成加厚顶板，不应脱离承载体单独调用。原生源码中的 placeholder、空 finalize
或未使用参数必须按 troubleshooting 复核，不能当成可用能力。
