---
id: soft-goods-native
domain: object
intent: 毯子、被褥、裤装、上衣、毛巾和地毯的原生静态路线
aliases: ["blanket", "comforter", "pants", "shirt", "towel", "rug", "毯子", "被子", "裤子", "上衣", "衬衫", "毛巾", "地毯"]
use_when: "创建由平面轮廓、厚度、开口、折叠、卷绕或绗缝定义的静态织物单体。"
avoid_when: "需求明确包含实时布料、穿戴动画、碰撞过程或角色绑定。"
source_symbols: ["infinigen/assets/objects/clothes/blanket.py:BlanketFactory", "infinigen/assets/objects/clothes/blanket.py:ComforterFactory", "infinigen/assets/objects/clothes/pants.py:PantsFactory", "infinigen/assets/objects/clothes/shirt.py:ShirtFactory", "infinigen/assets/objects/clothes/towel.py:TowelFactory", "infinigen/assets/objects/elements/rug.py:RugFactory"]
related_patterns: ["soft-volume-seams", "custom-mesh-loft"]
summary: "借鉴原生轮廓、开口、厚度和静态折叠机制，不把布料仿真依赖复制进单体资产。"
---

# 静态软物原生参考

毯子和地毯从二维轮廓、UV 和可控厚度开始；上衣和裤装使用半侧轮廓、镜像和真实领口、袖口或
裤口；毛巾使用有限折叠或卷绕。折痕只出现在压缩、支撑和接触区域，高频随机噪声不能代替
织物结构。需要材质时查询 `materials/fabric.md`。
