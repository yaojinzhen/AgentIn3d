---
id: hard-surface-negative-space
domain: pattern
intent: 构造制造件外壳、面板、真实开孔、槽口、空腔和凹陷细节
aliases: ["hard surface", "negative space", "opening", "slot", "cavity", "硬表面", "负空间", "开孔", "凹槽"]
use_when: "制造件识别依赖受控边缘、面板厚度或真实孔洞与凹陷。"
avoid_when: "特征只是印刷图案，或对象是没有制造开孔的柔性、有机表面。"
source_symbols: ["bpy.types.BooleanModifier", "infinigen.core.util.blender"]
related_patterns: ["custom-mesh-loft", "rigid-assembly"]
summary: "根据语义区分开孔、凹陷、装配缝和印刷线，并为真实负空间建立边界、内壁和合理倒角。"
---

# 硬表面与负空间

通孔、通风槽和把手开口必须能看到背景或内壁，可使用 boolean difference、内外边界环或包含开口的
profile/loft。凹陷需要低于承载面并具有可读边缘或底面。深色圆柱、平面、贴花和 bump 不能代替孔洞；
印刷标记则不需要 boolean。切割后隐藏或移除 cutter，并检查 evaluated mesh、法线和非流形区域。

## 方法专属验证

至少用两个视图确认每个开孔与凹陷。透视图验证内壁、深度和边缘高光，正交图验证位置和重复关系。
检查零厚度、共面重叠、仅相切 cutter、细长碎面和过大的 bevel。

