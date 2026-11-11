---
id: fabric-material
domain: material
intent: 织物、软包、毛巾、地毯和服装的方向性纤维材质
aliases: ["fabric", "textile", "cloth", "upholstery", "rug fabric", "织物", "布料", "软包", "毛巾材质", "地毯材质"]
use_when: "柔性物体需要可读的纤维方向、织纹尺度、粗糙度和克制的颜色变化。"
avoid_when: "目标是皮革、硬塑料、陶瓷、裸露金属或透明薄膜。"
source_symbols: ["infinigen/assets/composition/material_assignments.py:blanket", "infinigen/assets/composition/material_assignments.py:pants", "infinigen/assets/composition/material_assignments.py:towel", "infinigen/assets/composition/material_assignments.py:rug_fabric"]
related_patterns: ["soft-volume-seams"]
summary: "让织纹沿面片和部件方向组织，并按最终像素尺度控制纤维、粗糙度和颜色变化。"
---

# 织物材质

优先从 `material_assignments` 中与对象语义一致的候选池选择，不把 blanket、pants、towel 和
rug 的集合互相视为等价。基础色与粗糙度先满足用户要求，再加入最终画面中可见但不主导的
经纬或纤维变化。织纹方向应与面片、卷绕或缝线方向一致，不能使用各向同性大尺度噪声。

绒面、厚毛巾和短绒地毯可以增加克制的微表面变化，但纤维节点不能替代几何层的填充体积、
接缝、折叠和边缘厚度。正视图检查颜色与图案，斜向高光检查粗糙度和纤维尺度。
