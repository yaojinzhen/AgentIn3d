---
id: api-curve-sweep
domain: api
intent: 使用 Blender 曲线 bevel 沿中心路径生成扫掠几何，并按需转换或求值
aliases: ["curve sweep", "bevel curve", "tube along path", "曲线扫掠", "沿路径生成管线"]
use_when: "已经选择曲线扫掠 Pattern，正在编码把手、电缆、管道、缝线或带状部件。"
avoid_when: "对象主体是宽幅自定义曲面，或尚未完成建模机制选择。"
source_symbols: ["bpy.types.Curve.bevel_depth", "bpy.types.Curve.bevel_resolution"]
related_patterns: ["curve-sweep"]
documents: ["api_reference/function_api/blender_helper_objects.md", "api_reference/function_api/attributes_and_mesh_data.md"]
summary: "路由到曲线辅助对象和 mesh 转换接口，用中心路径生成端点可控的扫掠几何。"
---

# 曲线扫掠 API 操作路由

查询结果直接返回曲线辅助对象和 mesh 转换叶子文档；本文件只是机器路由源，正常建模不需要再次读取。
