---
id: fruit-skin-material
domain: material
intent: 具有正确色相、粗糙度和受控变化的程序化果皮材质
aliases: ["fruit skin", "apple skin", "果皮", "苹果皮"]
use_when: "果实表面需要自然色彩变化、克制斑点、合理粗糙度和微小起伏。"
avoid_when: "目标是蜡、塑料、涂漆金属或其他非有机涂层。"
source_symbols: ["infinigen/assets/objects/fruits/surfaces/apple_surface.py:shader_apple_shader"]
related_patterns: ["rounded-organic-mass"]
summary: "以要求的果皮色相为基础，叠加宏观与细微变化，但不能漂白结果或用材质破坏轮廓。"
---

# 果皮材质

先在中性光照下确认要求的红色、绿色或黄色基础色，再增加邻近色相的宽幅变化、克制斑点、
中等粗糙度和细微凹凸。噪声应连续并与物体尺度匹配。最终预览不能把红苹果变成浅粉色或
近白色，也不能呈现为均匀的高光塑料。
