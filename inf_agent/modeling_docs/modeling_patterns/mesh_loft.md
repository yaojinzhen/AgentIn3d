---
id: custom-mesh-loft
domain: pattern
intent: 通过有序截面或显式拓扑构造连续、非回转的外壳和实体
aliases: ["custom mesh", "loft", "bridged sections", "自定义网格", "放样", "截面桥接"]
use_when: "连续曲面沿某个方向改变形状，无法由 primitive 或简单回转准确表达。"
avoid_when: "原生 Factory、回转轮廓或曲线扫掠已经能直接表达主体。"
source_symbols: ["bpy.data.meshes.new", "mesh.from_pydata"]
related_patterns: ["profile-revolve-shell", "rounded-organic-mass"]
summary: "用少量兼容截面建立连续表面，再处理封口、厚度、细分和法线。"
---

# 自定义网格与放样

每个截面应包含中心、朝向和轮廓，并保持兼容的顶点数量、顺序与绕向。只在轮廓或结构发生变化处
增加截面；对齐对应顶点后再桥接。可见壁厚使用内外表面或 solidify 类机制。低频不对称可以改变
截面中心和尺度，微观位移不能改变主轮廓。需要代码骨架时查询 API 的 explicit vertices/faces，并读取
`../api_reference/function_api/assets_object_mesh_helpers.md` 中的“截面环桥接”。
当前 Blender 4.2 运行时没有可赋值的 `mesh.use_auto_smooth` / `mesh.auto_smooth_angle`；
需要折线棱边时按面设置 smooth 或显式标记 sharp edge，可用 `lint` 检查已知 API 问题，再预览并观察实际表面。

## 方法专属验证

检查截面错位、桥接扭转、封口夹点、自相交和波浪轮廓。正交视图应符合截面计划，透视高光应连续。
增加顶点或 subdivision 不能修复错误截面和比例。
