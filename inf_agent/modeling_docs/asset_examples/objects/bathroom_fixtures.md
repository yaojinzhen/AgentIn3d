---
id: bathroom-fixtures-native
domain: object
intent: 浴缸、水槽、马桶和卫浴五金的原生路线
aliases: ["bathtub", "bathroom sink", "standing sink", "toilet", "bathroom hardware", "浴缸", "浴室水槽", "立柱水槽", "马桶", "卫浴五金"]
use_when: "创建具有陶瓷空腔、排水结构、立柱、座圈、水箱或金属附件的卫浴单体。"
avoid_when: "目标是完整浴室空间、管网系统或需要可动水流和仿真的场景。"
source_symbols: ["infinigen/assets/objects/bathroom/bathtub.py:BathtubFactory", "infinigen/assets/objects/bathroom/bathroom_sink.py:BathroomSinkFactory", "infinigen/assets/objects/bathroom/bathroom_sink.py:StandingSinkFactory", "infinigen/assets/objects/bathroom/toilet.py:ToiletFactory", "infinigen/assets/objects/bathroom/hardware.py:HardwareFactory"]
related_patterns: ["profile-revolve-shell", "hard-surface-negative-space", "curve-sweep"]
summary: "复用原生陶瓷轮廓和空腔机制，保持排水件、水龙头、座圈与主体的真实贴合。"
---

# 卫浴单体原生参考

浴缸、水槽和马桶的身份由内外轮廓、正壁厚和真实空腔决定，不能用实心外形加深色贴片替代。
水槽优先检查 `BathroomSinkFactory`，立柱式水槽使用 `StandingSinkFactory`；水龙头和卫浴五金只
复用所需公开入口，不复制 bathroom 文件内的私有 `make_bowl`、`make_tube` 或曲线 helper。

陶瓷主体与金属排水件、龙头和按钮应分配独立材质。所有附件从盆体、水箱或墙面安装座的局部
坐标推导，斜视图中确认接触和开口深度。
