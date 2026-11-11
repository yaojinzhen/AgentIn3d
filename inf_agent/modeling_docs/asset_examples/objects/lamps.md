---
id: lamps-native
domain: object
intent: 台灯、落地灯、吸顶灯和吊灯的原生路线
aliases: ["desk lamp", "floor lamp", "ceiling light", "pendant lamp", "chandelier", "台灯", "落地灯", "吸顶灯", "吊灯"]
use_when: "创建具有底座、立柱或吊线、灯架、灯罩、灯泡和可选光源的灯具单体。"
avoid_when: "目标仅是场景照明、灯光布置或不需要可见灯具几何。"
source_symbols: ["infinigen/assets/objects/lamp/lamp.py:LampFactory", "infinigen/assets/objects/lamp/lamp.py:DeskLampFactory", "infinigen/assets/objects/lamp/lamp.py:FloorLampFactory", "infinigen/assets/objects/lamp/ceiling_lights.py:CeilingLightFactory", "infinigen/assets/objects/lamp/ceiling_classic_lamp.py:CeilingClassicLampFactory"]
related_patterns: ["curve-sweep", "profile-revolve-shell", "geometry-nodes-distribution"]
summary: "优先复用匹配灯具 Factory，保留底座、支撑路径、灯头朝向、灯罩厚度和灯泡位置关系。"
---

# 灯具原生参考

台灯和落地灯使用 `LampFactory` 系列的曲线立柱与切线对齐灯头；吸顶灯检查
`CeilingLightFactory`；多臂吊灯使用 `CeilingClassicLampFactory` 的有界重复关系。可见灯罩、
灯泡和金属框架分别建模和赋材质。点光源属于照明行为，不得用它替代灯泡几何，也不要复制
原生文件中的私有灯头或灯架 nodegroup。
