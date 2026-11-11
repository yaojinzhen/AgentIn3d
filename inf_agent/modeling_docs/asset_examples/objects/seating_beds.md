---
id: seating-beds-native
domain: object
intent: 椅子、办公椅、沙发、床、床垫和枕头的原生路线
aliases: ["chair", "office chair", "bar chair", "sofa", "armchair", "bed", "mattress", "pillow", "椅子", "办公椅", "吧椅", "沙发", "扶手椅", "床", "床垫", "枕头"]
use_when: "创建由刚性支撑、坐垫、靠背、扶手或填充软体共同组成的家具。"
avoid_when: "目标是动态人物座椅交互、实时布料或只包含一块规则硬板的对象。"
source_symbols: ["infinigen/assets/objects/seating/chairs/chair.py:ChairFactory", "infinigen/assets/objects/seating/chairs/bar_chair.py:BarChairFactory", "infinigen/assets/objects/seating/chairs/office_chair.py:OfficeChairFactory", "infinigen/assets/objects/seating/sofa.py:SofaFactory", "infinigen/assets/objects/seating/sofa.py:ArmChairFactory", "infinigen/assets/objects/seating/bed.py:BedFactory", "infinigen/assets/objects/seating/mattress.py:MattressFactory", "infinigen/assets/objects/seating/pillow.py:PillowFactory"]
related_patterns: ["rigid-assembly", "soft-volume-seams", "custom-mesh-loft"]
summary: "将承载框架与软体体积分开选择方法，保持坐垫、靠背、扶手、床垫和枕头的真实接触与压缩关系。"
---

# 座椅、床与软体家具原生参考

硬质椅子先检查 `ChairFactory`；吧椅、办公椅和沙发的原生入口包含专用 Geometry Nodes 装配，
只有完整 Factory 可安全使用时才直接复用。床由床架、床垫、被褥和枕头组成，静态任务不应
复制原生 cloth simulation 链。主轮廓先由框架和软体控制笼确定，再增加缝线、钉花或脚踏等
可见细节。每个坐垫、靠背和床垫都必须与承载结构接触。
